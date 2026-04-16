"""DTA analysis page -- backend-driven first analysis slice.

Lets the user:
  1. Select an eligible DTA dataset from the workspace
  2. Select a DTA workflow template
  3. Run analysis through the backend /analysis/run endpoint
  4. View result summary cards, DTA curve figure (raw / smoothed /
     baseline / corrected), detected peak / event cards and table,
     and processing details
  5. Auto-refresh workspace/report/compare state after a successful run
"""

from __future__ import annotations

import copy
import math
from typing import Any

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, dcc, html
import plotly.graph_objects as go

from dash_app.components.analysis_page import (
    analysis_page_stores,
    dataset_selection_card,
    dataset_selector_block,
    eligible_datasets,
    empty_result_msg,
    execute_card,
    interpret_run_result,
    metrics_row,
    no_data_figure_msg,
    processing_details_section,
    resolve_sample_name,
    result_placeholder_card,
    workflow_template_card,
)
from dash_app.components.chrome import page_header
from dash_app.components.data_preview import dataset_table
from dash_app.theme import apply_figure_theme
from utils.i18n import normalize_ui_locale, translate_ui

dash.register_page(__name__, path="/dta", title="DTA Analysis - MaterialScope")

_DTA_TEMPLATE_IDS = ["dta.general", "dta.thermal_events"]
_DTA_ELIGIBLE_TYPES = {"DTA", "UNKNOWN"}

_DTA_WORKFLOW_TEMPLATES = [
    {"id": "dta.general", "label": "General DTA"},
    {"id": "dta.thermal_events", "label": "Thermal Event Screening"},
]
_TEMPLATE_OPTIONS = [{"label": t["label"], "value": t["id"]} for t in _DTA_WORKFLOW_TEMPLATES]
_TEMPLATE_DESCRIPTIONS = {
    "dta.general": (
        "General DTA: Savitzky-Golay smoothing, ASLS baseline, bidirectional peak detection (exothermic + endothermic)."
    ),
    "dta.thermal_events": (
        "Thermal Event Screening: Wider smoothing window, more permissive peak detection for complex thermal histories."
    ),
}

_DIRECTION_COLORS = {
    "exo": "#DC2626",
    "endo": "#2563EB",
    "exotherm": "#DC2626",
    "endotherm": "#2563EB",
}
_DIRECTION_ICONS = {
    "exo": "bi-arrow-up-circle",
    "endo": "bi-arrow-down-circle",
    "exotherm": "bi-arrow-up-circle",
    "endotherm": "bi-arrow-down-circle",
}
_DIRECTION_GUIDE_COLORS = {
    "exo": "rgba(220, 38, 38, 0.22)",
    "endo": "rgba(37, 99, 235, 0.22)",
    "exotherm": "rgba(220, 38, 38, 0.22)",
    "endotherm": "rgba(37, 99, 235, 0.22)",
}

_ANNOTATION_MIN_SEP = 15.0
_PRIMARY_EVENT_LIMIT = 4
_EMPTY_SAMPLE_TOKENS = {"", "unknown", "n/a", "na", "none", "null", "unnamed"}

# Smoothing defaults mirror core/batch_runner._DTA_TEMPLATE_DEFAULTS["dta.general"]
_SMOOTH_METHODS = ("savgol", "moving_average", "gaussian")
_DTA_SMOOTHING_DEFAULTS: dict[str, dict] = {
    "savgol": {"method": "savgol", "window_length": 11, "polyorder": 3},
    "moving_average": {"method": "moving_average", "window_length": 11},
    "gaussian": {"method": "gaussian", "sigma": 2.0},
}
# Baseline defaults mirror core/batch_runner._DTA_TEMPLATE_DEFAULTS["dta.general"]["baseline"]
# plus the pybaselines asls default kwargs (lam=1e6, p=0.01) documented in core/baseline.py.
# Phase 2a exposes the three most common DTA baseline methods; additional methods
# (polynomial, modpoly, imodpoly, snip, spline, airpls) remain reachable through the
# same override channel without UI work.
_BASELINE_METHODS = ("asls", "linear", "rubberband")
_DTA_BASELINE_DEFAULTS: dict[str, dict] = {
    "asls": {"method": "asls", "lam": 1e6, "p": 0.01},
    "linear": {"method": "linear"},
    "rubberband": {"method": "rubberband"},
}
# Peak-detection defaults mirror core/batch_runner._DTA_TEMPLATE_DEFAULTS["dta.general"]["peak_detection"]
# with two UI-visible knobs added (prominence, distance) that core/dta_processor.find_peaks already
# accepts (prominence=None -> adaptive 5% of p-p range; distance forwarded to find_thermal_peaks kwargs).
# prominence == 0.0 is the sentinel "auto / adaptive".
_DTA_PEAK_DETECTION_DEFAULTS: dict = {
    "detect_endothermic": True,
    "detect_exothermic": True,
    "prominence": 0.0,
    "distance": 1,
}
_UNDO_STACK_LIMIT = 32


def _default_processing_draft() -> dict:
    """Return a fresh default processing-draft payload for DTA.

    Includes all three user-tunable sections exposed in Phases 1 + 2a so that a
    single undo/redo/reset stack covers every control.
    """
    return {
        "smoothing": copy.deepcopy(_DTA_SMOOTHING_DEFAULTS["savgol"]),
        "baseline": copy.deepcopy(_DTA_BASELINE_DEFAULTS["asls"]),
        "peak_detection": copy.deepcopy(_DTA_PEAK_DETECTION_DEFAULTS),
    }


def _normalize_smoothing_values(method: str | None, window_length, polyorder, sigma) -> dict:
    """Build a canonical signal_pipeline.smoothing values dict from raw control inputs."""
    token = str(method or "savgol").strip().lower()
    if token not in _SMOOTH_METHODS:
        token = "savgol"
    if token == "savgol":
        wl = _coerce_int_positive(window_length, default=11, minimum=5)
        if wl % 2 == 0:
            wl += 1
        po = _coerce_int_positive(polyorder, default=3, minimum=1)
        po = min(po, max(wl - 2, 1))
        return {"method": "savgol", "window_length": wl, "polyorder": po}
    if token == "moving_average":
        wl = _coerce_int_positive(window_length, default=11, minimum=3)
        if wl % 2 == 0:
            wl += 1
        return {"method": "moving_average", "window_length": wl}
    sg = _coerce_float_positive(sigma, default=2.0, minimum=0.1)
    return {"method": "gaussian", "sigma": sg}


def _coerce_int_positive(value, *, default: int, minimum: int) -> int:
    try:
        if value in (None, ""):
            return max(default, minimum)
        parsed = int(float(value))
    except (TypeError, ValueError):
        return max(default, minimum)
    return max(parsed, minimum)


def _coerce_float_positive(value, *, default: float, minimum: float) -> float:
    try:
        if value in (None, ""):
            return max(default, minimum)
        parsed = float(value)
    except (TypeError, ValueError):
        return max(default, minimum)
    if not math.isfinite(parsed):
        return max(default, minimum)
    return max(parsed, minimum)


def _apply_draft_section(draft: dict | None, section: str, values: dict) -> dict:
    """Return a new draft with *section* replaced by *values* (deep copied)."""
    next_draft = copy.deepcopy(draft or {})
    next_draft[section] = copy.deepcopy(values)
    return next_draft


def _push_undo(undo: list | None, snapshot: dict | None) -> list:
    stack = list(undo or [])
    stack.append(copy.deepcopy(snapshot or {}))
    if len(stack) > _UNDO_STACK_LIMIT:
        stack = stack[-_UNDO_STACK_LIMIT:]
    return stack


def _do_undo(draft: dict, undo: list | None, redo: list | None) -> tuple[dict, list, list]:
    """Pop from undo into draft, pushing current draft onto redo. No-op when empty."""
    undo_stack = list(undo or [])
    redo_stack = list(redo or [])
    if not undo_stack:
        return copy.deepcopy(draft or {}), undo_stack, redo_stack
    previous = undo_stack.pop()
    redo_stack.append(copy.deepcopy(draft or {}))
    return copy.deepcopy(previous), undo_stack, redo_stack


def _do_redo(draft: dict, undo: list | None, redo: list | None) -> tuple[dict, list, list]:
    """Pop from redo into draft, pushing current draft onto undo. No-op when empty."""
    undo_stack = list(undo or [])
    redo_stack = list(redo or [])
    if not redo_stack:
        return copy.deepcopy(draft or {}), undo_stack, redo_stack
    following = redo_stack.pop()
    undo_stack.append(copy.deepcopy(draft or {}))
    return copy.deepcopy(following), undo_stack, redo_stack


def _do_reset(
    draft: dict,
    undo: list | None,
    redo: list | None,
    defaults: dict | None,
) -> tuple[dict, list, list]:
    """Restore defaults, pushing current draft to undo, clearing redo."""
    reset_target = copy.deepcopy(defaults or _default_processing_draft())
    if (draft or {}) == reset_target:
        return reset_target, list(undo or []), list(redo or [])
    undo_stack = _push_undo(undo, draft)
    return reset_target, undo_stack, []


def _smoothing_overrides_from_draft(draft: dict | None) -> dict:
    """Extract the smoothing section override if the draft carries one."""
    section = (draft or {}).get("smoothing")
    if not isinstance(section, dict):
        return {}
    return {"smoothing": copy.deepcopy(section)}


def _normalize_baseline_values(method: str | None, lam, p) -> dict:
    """Build a canonical signal_pipeline.baseline values dict from raw control inputs.

    Only the three methods wired into the Phase 2a UI (``asls``, ``linear``,
    ``rubberband``) are emitted. Unknown methods fall back to ``asls`` so a stale
    draft never produces an invalid payload.
    """
    token = str(method or "asls").strip().lower()
    if token not in _BASELINE_METHODS:
        token = "asls"
    if token == "asls":
        lam_value = _coerce_float_positive(lam, default=1e6, minimum=1e-3)
        p_value = _coerce_float_in_range(p, default=0.01, minimum=1e-4, maximum=0.5)
        return {"method": "asls", "lam": lam_value, "p": p_value}
    return {"method": token}


def _normalize_peak_detection_values(detect_endo, detect_exo, prominence, distance) -> dict:
    """Build a canonical analysis_steps.peak_detection values dict from raw inputs."""
    endo = _coerce_bool(detect_endo, default=True)
    exo = _coerce_bool(detect_exo, default=True)
    prom = _coerce_float_non_negative(prominence, default=0.0, minimum=0.0)
    dist = _coerce_int_positive(distance, default=1, minimum=1)
    return {
        "detect_endothermic": endo,
        "detect_exothermic": exo,
        "prominence": prom,
        "distance": dist,
    }


def _coerce_float_in_range(value, *, default: float, minimum: float, maximum: float) -> float:
    parsed = _coerce_float_positive(value, default=default, minimum=minimum)
    if parsed > maximum:
        return maximum
    return parsed


def _coerce_float_non_negative(value, *, default: float, minimum: float) -> float:
    try:
        if value in (None, ""):
            return max(default, minimum)
        parsed = float(value)
    except (TypeError, ValueError):
        return max(default, minimum)
    if not math.isfinite(parsed) or parsed < minimum:
        return max(default, minimum)
    return parsed


def _coerce_bool(value, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    token = str(value).strip().lower()
    if token in {"true", "1", "yes", "on"}:
        return True
    if token in {"false", "0", "no", "off", ""}:
        return False
    return default


def _baseline_overrides_from_draft(draft: dict | None) -> dict:
    """Extract the baseline section override if the draft carries one."""
    section = (draft or {}).get("baseline")
    if not isinstance(section, dict):
        return {}
    return {"baseline": copy.deepcopy(section)}


def _peak_detection_overrides_from_draft(draft: dict | None) -> dict:
    """Extract the peak_detection section override if the draft carries one."""
    section = (draft or {}).get("peak_detection")
    if not isinstance(section, dict):
        return {}
    return {"peak_detection": copy.deepcopy(section)}


def _overrides_from_draft(draft: dict | None) -> dict:
    """Union of all Dash-side DTA override sections present in *draft*.

    Returns a dict suitable for the ``processing_overrides`` payload on
    ``/analysis/run``; empty dict when no section is present so callers can
    forward ``None`` and skip the field entirely.
    """
    combined: dict = {}
    combined.update(_smoothing_overrides_from_draft(draft))
    combined.update(_baseline_overrides_from_draft(draft))
    combined.update(_peak_detection_overrides_from_draft(draft))
    return combined


def _loc(locale_data: str | None) -> str:
    return normalize_ui_locale(locale_data)


def _clean_sample_token(value) -> str | None:
    token = str(value or "").strip()
    if not token or token.lower() in _EMPTY_SAMPLE_TOKENS:
        return None
    return token


def _dataset_key_stem_token(dataset_key) -> str | None:
    """Strip common data extensions from *dataset_key* for filename-like comparisons.

    Extension list kept aligned with ``resolve_sample_name`` in
    ``dash_app.components.analysis_page``.
    """
    key = str(dataset_key or "").strip()
    if not key:
        return None
    lowered = key.lower()
    for ext in (".csv", ".txt", ".dat", ".xls", ".xlsx"):
        if lowered.endswith(ext):
            key = key[: -len(ext)]
            break
    return _clean_sample_token(key)


def _normalize_direction(value) -> str:
    token = str(value or "").strip().lower()
    if token.startswith("exo"):
        return "exotherm"
    if token.startswith("endo"):
        return "endotherm"
    return token


def _direction_label(direction: str, loc: str) -> str:
    normalized = _normalize_direction(direction)
    if normalized == "exotherm":
        return translate_ui(loc, "dash.analysis.dta.direction.exo")
    if normalized == "endotherm":
        return translate_ui(loc, "dash.analysis.dta.direction.endo")
    if not normalized or normalized == "unknown":
        return translate_ui(loc, "dash.analysis.dta.direction.unknown")
    return str(direction).strip().title() or translate_ui(loc, "dash.analysis.dta.direction.unknown")


def _coerce_float(value) -> float | None:
    try:
        if value in (None, ""):
            return None
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _event_rows(rows: list[dict]) -> list[dict]:
    return [dict(row) for row in (rows or []) if isinstance(row, dict)]


def _derive_event_metrics(summary: dict, rows: list[dict]) -> tuple[int, int, int]:
    derived_exo = 0
    derived_endo = 0
    for row in rows:
        direction = _normalize_direction(row.get("direction", row.get("peak_type")))
        if direction == "exotherm":
            derived_exo += 1
        elif direction == "endotherm":
            derived_endo += 1

    peak_count = len(rows) or int(summary.get("peak_count") or 0)
    exo_count = derived_exo
    endo_count = derived_endo
    if not rows:
        exo_count = int(summary.get("exotherm_count", summary.get("exo_count")) or 0)
        endo_count = int(summary.get("endotherm_count", summary.get("endo_count")) or 0)
        if peak_count <= 0 and (exo_count or endo_count):
            peak_count = exo_count + endo_count
    return peak_count, exo_count, endo_count


def _resolve_dta_sample_name(
    summary: dict,
    result_meta: dict,
    dataset_detail: dict | None = None,
    *,
    locale_data: str | None = None,
) -> str:
    dataset_detail = dataset_detail or {}
    dataset_summary = dataset_detail.get("dataset", {}) or {}
    metadata = dataset_detail.get("metadata", {}) or {}

    fallback_display = (
        _clean_sample_token(dataset_summary.get("display_name"))
        or _clean_sample_token(metadata.get("display_name"))
        or _clean_sample_token(summary.get("display_name"))
        or _clean_sample_token(dataset_summary.get("sample_name"))
        or _clean_sample_token(metadata.get("sample_name"))
        or _clean_sample_token(metadata.get("file_name"))
    )
    normalized_summary = dict(summary or {})
    cleaned_summary_name = _clean_sample_token(normalized_summary.get("sample_name"))
    normalized_summary["sample_name"] = cleaned_summary_name

    # Narrow override: filename-like persisted sample_name should not hide a
    # richer workspace display_name when it differs.
    if fallback_display and cleaned_summary_name:
        fb = str(fallback_display).strip()
        sn_cf = str(cleaned_summary_name).casefold()
        if fb.casefold() != sn_cf:
            meta_file = _clean_sample_token(metadata.get("file_name"))
            key_stem = _dataset_key_stem_token((result_meta or {}).get("dataset_key"))
            matches_meta_file = bool(meta_file and str(meta_file).casefold() == sn_cf)
            matches_key_stem = bool(key_stem and str(key_stem).casefold() == sn_cf)
            if matches_meta_file or matches_key_stem:
                normalized_summary["sample_name"] = None

    return resolve_sample_name(normalized_summary, result_meta or {}, fallback_display_name=fallback_display, locale_data=locale_data)


def _event_priority(row: dict) -> tuple[float, float, float]:
    area = abs(_coerce_float(row.get("area")) or 0.0)
    height = abs(_coerce_float(row.get("height")) or 0.0)
    peak_temp = _coerce_float(row.get("peak_temperature"))
    return area, height, -(peak_temp if peak_temp is not None else float("inf"))


def _sort_events_by_temperature(rows: list[dict]) -> list[dict]:
    return sorted(
        rows,
        key=lambda row: (_coerce_float(row.get("peak_temperature")) is None, _coerce_float(row.get("peak_temperature")) or 0.0),
    )


def _split_primary_events(rows: list[dict], limit: int = _PRIMARY_EVENT_LIMIT) -> tuple[list[dict], list[dict]]:
    if len(rows) <= limit:
        return _sort_events_by_temperature(rows), []

    indexed_rows = list(enumerate(rows))
    selected = sorted(indexed_rows, key=lambda item: _event_priority(item[1]), reverse=True)[:limit]
    selected_indices = {index for index, _row in selected}
    primary = _sort_events_by_temperature([row for index, row in indexed_rows if index in selected_indices])
    secondary = _sort_events_by_temperature([row for index, row in indexed_rows if index not in selected_indices])
    return primary, secondary


def _series_values(series: list) -> list[float]:
    values: list[float] = []
    for item in series or []:
        parsed = _coerce_float(item)
        if parsed is not None:
            values.append(parsed)
    return values


def _series_for_temperature(series: list, temperature: list[float]) -> list[float]:
    return series if series and len(series) == len(temperature) else []


def _compute_y_axis_range(*series_collection: list[float]) -> list[float] | None:
    values: list[float] = []
    for series in series_collection:
        values.extend(_series_values(series))
    if not values:
        return None

    lower = min(values)
    upper = max(values)
    span = upper - lower
    if span <= 0:
        pad = max(abs(upper) * 0.12, 1.0)
    else:
        pad = span * 0.12
    return [lower - pad, upper + pad]


def _peak_card(row: dict, idx: int, loc: str = "en") -> dbc.Card:
    direction = _normalize_direction(row.get("direction", row.get("peak_type", "unknown")))
    color = _DIRECTION_COLORS.get(direction, "#6B7280")
    icon = _DIRECTION_ICONS.get(direction, "bi-circle")
    direction_label = _direction_label(direction, loc)

    pt = row.get("peak_temperature")
    onset = row.get("onset_temperature")
    endset = row.get("endset_temperature")
    area = row.get("area")
    fwhm = row.get("fwhm")
    height = row.get("height")

    return dbc.Card(
        dbc.CardBody(
            [
                html.Div(
                    [
                        html.I(className=f"bi {icon} me-2", style={"color": color, "fontSize": "1.1rem"}),
                        html.Strong(translate_ui(loc, "dash.analysis.label.peak_n", n=idx + 1), className="me-2"),
                        html.Span(
                            direction_label,
                            className="badge",
                            style={"backgroundColor": color, "color": "white", "fontSize": "0.75rem"},
                        ),
                        html.Span(f"  {pt:.1f} C" if pt is not None else "  --", className="ms-2"),
                    ],
                    className="mb-2",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.Small(translate_ui(loc, "dash.analysis.label.onset"), className="text-muted d-block"),
                                html.Span(f"{onset:.1f}" if onset is not None else "--"),
                            ],
                            md=3,
                        ),
                        dbc.Col(
                            [
                                html.Small(translate_ui(loc, "dash.analysis.label.endset"), className="text-muted d-block"),
                                html.Span(f"{endset:.1f}" if endset is not None else "--"),
                            ],
                            md=3,
                        ),
                        dbc.Col(
                            [
                                html.Small(translate_ui(loc, "dash.analysis.label.area"), className="text-muted d-block"),
                                html.Span(f"{area:.3f}" if area is not None else "--"),
                            ],
                            md=3,
                        ),
                        dbc.Col(
                            [
                                html.Small(translate_ui(loc, "dash.analysis.label.fwhm"), className="text-muted d-block"),
                                html.Span(f"{fwhm:.1f}" if fwhm is not None else "--"),
                                html.Small(f" {translate_ui(loc, 'dash.analysis.label.height')}", className="text-muted ms-2"),
                                html.Span(f"{height:.3f}" if height is not None else "--"),
                            ],
                            md=3,
                        ),
                    ],
                    className="g-2",
                ),
            ]
        ),
        className="mb-2 h-100",
    )


def _smoothing_controls_card() -> dbc.Card:
    """User-tunable smoothing controls with Apply / Undo / Redo / Reset.

    Phase 1 scope: smoothing only. Draft params are held in dcc.Store and
    flushed to the backend only when the Run button is clicked.
    """
    method_options = [
        {"label": "Savitzky-Golay", "value": "savgol"},
        {"label": "Moving Average", "value": "moving_average"},
        {"label": "Gaussian", "value": "gaussian"},
    ]
    return dbc.Card(
        dbc.CardBody(
            [
                html.H5(id="dta-smoothing-card-title", className="card-title mb-3"),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Label(id="dta-smooth-method-label", html_for="dta-smooth-method"),
                                dbc.Select(
                                    id="dta-smooth-method",
                                    options=method_options,
                                    value="savgol",
                                ),
                                html.Small(
                                    id="dta-smooth-method-hint",
                                    className="form-text text-muted d-block mt-1",
                                ),
                            ],
                            md=12,
                        ),
                    ],
                    className="mb-2",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Label(id="dta-smooth-window-label", html_for="dta-smooth-window"),
                                dbc.Input(
                                    id="dta-smooth-window",
                                    type="number",
                                    min=3,
                                    max=51,
                                    step=2,
                                    value=11,
                                ),
                                html.Small(
                                    id="dta-smooth-window-hint",
                                    className="form-text text-muted d-block mt-1",
                                ),
                            ],
                            md=4,
                        ),
                        dbc.Col(
                            [
                                dbc.Label(id="dta-smooth-polyorder-label", html_for="dta-smooth-polyorder"),
                                dbc.Input(
                                    id="dta-smooth-polyorder",
                                    type="number",
                                    min=1,
                                    max=7,
                                    step=1,
                                    value=3,
                                ),
                                html.Small(
                                    id="dta-smooth-polyorder-hint",
                                    className="form-text text-muted d-block mt-1",
                                ),
                            ],
                            md=4,
                        ),
                        dbc.Col(
                            [
                                dbc.Label(id="dta-smooth-sigma-label", html_for="dta-smooth-sigma"),
                                dbc.Input(
                                    id="dta-smooth-sigma",
                                    type="number",
                                    min=0.1,
                                    max=10.0,
                                    step=0.1,
                                    value=2.0,
                                    disabled=True,
                                ),
                                html.Small(
                                    id="dta-smooth-sigma-hint",
                                    className="form-text text-muted d-block mt-1",
                                ),
                            ],
                            md=4,
                        ),
                    ],
                    className="g-2 mb-2",
                ),
                dbc.ButtonGroup(
                    [
                        dbc.Button(id="dta-smooth-apply-btn", color="primary", size="sm"),
                        dbc.Button(id="dta-undo-btn", color="secondary", size="sm", outline=True),
                        dbc.Button(id="dta-redo-btn", color="secondary", size="sm", outline=True),
                        dbc.Button(id="dta-reset-btn", color="secondary", size="sm", outline=True),
                    ],
                    className="mb-2",
                ),
                html.Div(id="dta-smooth-status", className="small text-muted"),
            ]
        ),
        className="mb-3",
    )


def _baseline_controls_card() -> dbc.Card:
    """User-tunable baseline controls (Phase 2a).

    Method ∈ {asls, linear, rubberband}; lam + p are gated on asls. Apply pushes
    the current draft onto the shared undo stack, mutates ``draft["baseline"]``,
    and clears redo. Undo/Redo/Reset are the shared buttons from the smoothing
    card; they operate on the full draft atomically.
    """
    method_options = [
        {"label": "AsLS", "value": "asls"},
        {"label": "Linear", "value": "linear"},
        {"label": "Rubberband", "value": "rubberband"},
    ]
    return dbc.Card(
        dbc.CardBody(
            [
                html.H5(id="dta-baseline-card-title", className="card-title mb-3"),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Label(id="dta-baseline-method-label", html_for="dta-baseline-method"),
                                dbc.Select(
                                    id="dta-baseline-method",
                                    options=method_options,
                                    value="asls",
                                ),
                                html.Small(
                                    id="dta-baseline-method-hint",
                                    className="form-text text-muted d-block mt-1",
                                ),
                            ],
                            md=12,
                        ),
                    ],
                    className="mb-2",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Label(id="dta-baseline-lam-label", html_for="dta-baseline-lam"),
                                dbc.Input(
                                    id="dta-baseline-lam",
                                    type="number",
                                    min=1e-3,
                                    step=1e5,
                                    value=1e6,
                                ),
                                html.Small(
                                    id="dta-baseline-lam-hint",
                                    className="form-text text-muted d-block mt-1",
                                ),
                            ],
                            md=6,
                        ),
                        dbc.Col(
                            [
                                dbc.Label(id="dta-baseline-p-label", html_for="dta-baseline-p"),
                                dbc.Input(
                                    id="dta-baseline-p",
                                    type="number",
                                    min=1e-4,
                                    max=0.5,
                                    step=0.005,
                                    value=0.01,
                                ),
                                html.Small(
                                    id="dta-baseline-p-hint",
                                    className="form-text text-muted d-block mt-1",
                                ),
                            ],
                            md=6,
                        ),
                    ],
                    className="g-2 mb-2",
                ),
                dbc.Button(
                    id="dta-baseline-apply-btn",
                    color="primary",
                    size="sm",
                    className="mb-2",
                ),
                html.Div(id="dta-baseline-status", className="small text-muted"),
            ]
        ),
        className="mb-3",
    )


def _peak_controls_card() -> dbc.Card:
    """User-tunable peak-detection controls (Phase 2a).

    Endo/exo checkboxes mirror ``core.dta_processor.find_peaks`` kwargs.
    ``prominence == 0`` is the adaptive-threshold sentinel (find_peaks derives
    5 % of the signal peak-to-peak range when prominence is falsy). ``distance``
    is forwarded to ``find_thermal_peaks`` via ``**kwargs``.
    """
    return dbc.Card(
        dbc.CardBody(
            [
                html.H5(id="dta-peak-card-title", className="card-title mb-3"),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Checkbox(
                                    id="dta-peak-detect-exo",
                                    label=" ",
                                    value=True,
                                ),
                                html.Small(
                                    id="dta-peak-detect-exo-hint",
                                    className="form-text text-muted d-block mt-1",
                                ),
                            ],
                            md=6,
                        ),
                        dbc.Col(
                            [
                                dbc.Checkbox(
                                    id="dta-peak-detect-endo",
                                    label=" ",
                                    value=True,
                                ),
                                html.Small(
                                    id="dta-peak-detect-endo-hint",
                                    className="form-text text-muted d-block mt-1",
                                ),
                            ],
                            md=6,
                        ),
                    ],
                    className="g-2 mb-2",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Label(id="dta-peak-prominence-label", html_for="dta-peak-prominence"),
                                dbc.Input(
                                    id="dta-peak-prominence",
                                    type="number",
                                    min=0.0,
                                    step=0.005,
                                    value=0.0,
                                ),
                                html.Small(
                                    id="dta-peak-prominence-hint",
                                    className="form-text text-muted d-block mt-1",
                                ),
                            ],
                            md=6,
                        ),
                        dbc.Col(
                            [
                                dbc.Label(id="dta-peak-distance-label", html_for="dta-peak-distance"),
                                dbc.Input(
                                    id="dta-peak-distance",
                                    type="number",
                                    min=1,
                                    step=1,
                                    value=1,
                                ),
                                html.Small(
                                    id="dta-peak-distance-hint",
                                    className="form-text text-muted d-block mt-1",
                                ),
                            ],
                            md=6,
                        ),
                    ],
                    className="g-2 mb-2",
                ),
                dbc.Button(
                    id="dta-peak-apply-btn",
                    color="primary",
                    size="sm",
                    className="mb-2",
                ),
                html.Div(id="dta-peak-status", className="small text-muted"),
            ]
        ),
        className="mb-3",
    )


def _literature_compare_card() -> dbc.Card:
    """Manual literature compare panel (Phase 2b).

    Gated on a saved DTA ``result_id`` (set by the run callback). Users pick
    ``max_claims`` and the persist flag, then click Compare to call the backend
    ``/literature/compare`` endpoint via ``api_client.literature_compare``.
    Output renders a compact claims + comparisons + citations summary.
    """
    return dbc.Card(
        dbc.CardBody(
            [
                html.H5(id="dta-literature-card-title", className="card-title mb-3"),
                html.Div(id="dta-literature-hint", className="small text-muted mb-2"),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Label(
                                    id="dta-literature-max-claims-label",
                                    html_for="dta-literature-max-claims",
                                ),
                                dbc.Input(
                                    id="dta-literature-max-claims",
                                    type="number",
                                    min=1,
                                    max=10,
                                    step=1,
                                    value=3,
                                ),
                            ],
                            md=6,
                        ),
                        dbc.Col(
                            [
                                dbc.Checklist(
                                    id="dta-literature-persist",
                                    options=[{"label": "", "value": "persist"}],
                                    value=[],
                                    switch=True,
                                    className="mt-4",
                                ),
                                dbc.Label(
                                    id="dta-literature-persist-label",
                                    html_for="dta-literature-persist",
                                    className="small",
                                ),
                            ],
                            md=6,
                        ),
                    ],
                    className="g-2 mb-2",
                ),
                dbc.Button(
                    id="dta-literature-compare-btn",
                    color="primary",
                    size="sm",
                    disabled=True,
                    className="mb-2",
                ),
                html.Div(id="dta-literature-status", className="small text-muted"),
                html.Div(id="dta-literature-output", className="mt-2"),
            ]
        ),
        className="mb-3",
    )


def _processing_draft_stores() -> list:
    """dcc.Store components that hold the DTA smoothing draft and undo/redo stacks."""
    defaults = _default_processing_draft()
    return [
        dcc.Store(id="dta-processing-default", data=defaults),
        dcc.Store(id="dta-processing-draft", data=copy.deepcopy(defaults)),
        dcc.Store(id="dta-processing-undo", data=[]),
        dcc.Store(id="dta-processing-redo", data=[]),
        dcc.Store(id="dta-figure-captured", data={}),
        dcc.Store(id="dta-preset-refresh", data=0),
    ]


_DTA_PRESET_ANALYSIS_TYPE = "DTA"


def _preset_controls_card() -> dbc.Card:
    """Processing-preset panel for the DTA page (Phase 3b).

    Exposes preset save / apply / delete against the backend ``/presets/DTA``
    endpoints. Apply restores the saved ``workflow_template_id`` + ``processing``
    sections onto the active draft while pushing the previous draft onto the
    shared undo stack, so an accidental apply can be reverted with the Undo
    button that already lives inside the Processing tab.
    """
    return dbc.Card(
        dbc.CardBody(
            [
                html.H5(id="dta-preset-card-title", className="card-title mb-1"),
                html.Small(
                    id="dta-preset-help",
                    className="form-text text-muted d-block mb-2",
                ),
                html.Div(id="dta-preset-caption", className="small text-muted mb-2"),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Label(
                                    id="dta-preset-select-label",
                                    html_for="dta-preset-select",
                                ),
                                dbc.Select(
                                    id="dta-preset-select",
                                    options=[],
                                    value=None,
                                ),
                            ],
                            md=12,
                        ),
                    ],
                    className="mb-2",
                ),
                dbc.ButtonGroup(
                    [
                        dbc.Button(
                            id="dta-preset-apply-btn",
                            color="primary",
                            size="sm",
                            disabled=True,
                        ),
                        dbc.Button(
                            id="dta-preset-delete-btn",
                            color="secondary",
                            size="sm",
                            outline=True,
                            disabled=True,
                        ),
                    ],
                    className="mb-3",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Label(
                                    id="dta-preset-save-name-label",
                                    html_for="dta-preset-save-name",
                                ),
                                dbc.Input(
                                    id="dta-preset-save-name",
                                    type="text",
                                    value="",
                                    maxLength=80,
                                ),
                            ],
                            md=12,
                        ),
                    ],
                    className="mb-2",
                ),
                dbc.Button(
                    id="dta-preset-save-btn",
                    color="primary",
                    size="sm",
                    className="mb-2",
                ),
                html.Div(id="dta-preset-status", className="small text-muted"),
            ]
        ),
        className="mb-3",
    )


def _dta_left_column_tabs() -> dbc.Tabs:
    """Stepwise Setup / Processing / Run tabs for the DTA left column (Phase 3a).

    All existing card-builder output IDs remain mounted — ``dbc.Tab`` children are
    eagerly rendered in the DOM, so existing callbacks bound to element IDs inside
    these cards continue to fire without changes.
    """
    return dbc.Tabs(
        [
            dbc.Tab(
                [
                    dataset_selection_card(
                        "dta-dataset-selector-area",
                        card_title_id="dta-dataset-card-title",
                    ),
                    workflow_template_card(
                        "dta-template-select",
                        "dta-template-description",
                        [],
                        "dta.general",
                        card_title_id="dta-workflow-card-title",
                    ),
                ],
                tab_id="dta-tab-setup",
                label_class_name="ta-tab-label",
                id="dta-tab-setup-shell",
            ),
            dbc.Tab(
                [
                    _preset_controls_card(),
                    _smoothing_controls_card(),
                    _baseline_controls_card(),
                    _peak_controls_card(),
                ],
                tab_id="dta-tab-processing",
                label_class_name="ta-tab-label",
                id="dta-tab-processing-shell",
            ),
            dbc.Tab(
                [
                    execute_card(
                        "dta-run-status",
                        "dta-run-btn",
                        card_title_id="dta-execute-card-title",
                    ),
                ],
                tab_id="dta-tab-run",
                label_class_name="ta-tab-label",
                id="dta-tab-run-shell",
            ),
        ],
        id="dta-left-tabs",
        active_tab="dta-tab-setup",
        className="mb-3",
    )


layout = html.Div(
    analysis_page_stores("dta-refresh", "dta-latest-result-id")
    + _processing_draft_stores()
    + [
        html.Div(id="dta-hero-slot"),
        dbc.Row(
            [
                dbc.Col(
                    [_dta_left_column_tabs()],
                    md=4,
                ),
                dbc.Col(
                    [
                        result_placeholder_card("dta-result-dataset-summary"),
                        result_placeholder_card("dta-result-metrics"),
                        result_placeholder_card("dta-result-figure"),
                        result_placeholder_card("dta-result-peak-cards"),
                        result_placeholder_card("dta-result-table"),
                        result_placeholder_card("dta-result-processing"),
                        _literature_compare_card(),
                    ],
                    md=8,
                ),
            ]
        ),
    ]
)


@callback(
    Output("dta-hero-slot", "children"),
    Output("dta-dataset-card-title", "children"),
    Output("dta-workflow-card-title", "children"),
    Output("dta-execute-card-title", "children"),
    Output("dta-run-btn", "children"),
    Output("dta-template-select", "options"),
    Output("dta-template-select", "value"),
    Output("dta-template-description", "children"),
    Input("ui-locale", "data"),
    Input("dta-template-select", "value"),
)
def render_dta_locale_chrome(locale_data, template_id):
    loc = _loc(locale_data)
    hero = page_header(
        translate_ui(loc, "dash.analysis.dta.title"),
        translate_ui(loc, "dash.analysis.dta.caption"),
        badge=translate_ui(loc, "dash.analysis.badge"),
    )
    opts = [{"label": translate_ui(loc, f"dash.analysis.dta.template.{tid}.label"), "value": tid} for tid in _DTA_TEMPLATE_IDS]
    valid = {o["value"] for o in opts}
    tid = template_id if template_id in valid else "dta.general"
    desc_key = f"dash.analysis.dta.template.{tid}.desc"
    desc = translate_ui(loc, desc_key)
    if desc == desc_key:
        desc = translate_ui(loc, "dash.analysis.dta.workflow_fallback")
    return (
        hero,
        translate_ui(loc, "dash.analysis.dataset_selection_title"),
        translate_ui(loc, "dash.analysis.workflow_template_title"),
        translate_ui(loc, "dash.analysis.execute_title"),
        translate_ui(loc, "dash.analysis.dta.run_btn"),
        opts,
        tid,
        desc,
    )


@callback(
    Output("dta-tab-setup-shell", "label"),
    Output("dta-tab-processing-shell", "label"),
    Output("dta-tab-run-shell", "label"),
    Input("ui-locale", "data"),
)
def render_dta_tab_chrome(locale_data):
    """Localize the three DTA stepwise tab labels (Phase 3a).

    Reuses the ``dash.analysis.dta.tab.*`` bundle entries so TR / EN flip in sync
    with every other DTA chrome callback.
    """
    loc = _loc(locale_data)
    return (
        translate_ui(loc, "dash.analysis.dta.tab.setup"),
        translate_ui(loc, "dash.analysis.dta.tab.processing"),
        translate_ui(loc, "dash.analysis.dta.tab.run"),
    )


@callback(
    Output("dta-preset-card-title", "children"),
    Output("dta-preset-select-label", "children"),
    Output("dta-preset-select", "placeholder"),
    Output("dta-preset-apply-btn", "children"),
    Output("dta-preset-delete-btn", "children"),
    Output("dta-preset-save-name-label", "children"),
    Output("dta-preset-save-name", "placeholder"),
    Output("dta-preset-save-btn", "children"),
    Output("dta-preset-help", "children"),
    Input("ui-locale", "data"),
)
def render_dta_preset_chrome(locale_data):
    """Localize the DTA preset panel chrome (Phase 3b)."""
    loc = _loc(locale_data)
    return (
        translate_ui(loc, "dash.analysis.dta.presets.title"),
        translate_ui(loc, "dash.analysis.dta.presets.select_label"),
        translate_ui(loc, "dash.analysis.dta.presets.select_placeholder"),
        translate_ui(loc, "dash.analysis.dta.presets.apply_btn"),
        translate_ui(loc, "dash.analysis.dta.presets.delete_btn"),
        translate_ui(loc, "dash.analysis.dta.presets.save_name_label"),
        translate_ui(loc, "dash.analysis.dta.presets.save_name_placeholder"),
        translate_ui(loc, "dash.analysis.dta.presets.save_btn"),
        translate_ui(loc, "dash.analysis.dta.presets.help.overview"),
    )


@callback(
    Output("dta-preset-select", "options"),
    Output("dta-preset-caption", "children"),
    Input("dta-preset-refresh", "data"),
    Input("ui-locale", "data"),
)
def refresh_dta_preset_options(refresh_token, locale_data):
    """Populate the DTA preset dropdown + count caption on load and after save/delete."""
    from dash_app import api_client

    loc = _loc(locale_data)
    try:
        payload = api_client.list_analysis_presets(_DTA_PRESET_ANALYSIS_TYPE)
    except Exception as exc:  # noqa: BLE001
        message = translate_ui(loc, "dash.analysis.dta.presets.list_failed").format(error=str(exc))
        return [], message

    presets = payload.get("presets") or []
    options = [
        {"label": item.get("preset_name", ""), "value": item.get("preset_name", "")}
        for item in presets
        if isinstance(item, dict) and item.get("preset_name")
    ]
    caption = translate_ui(loc, "dash.analysis.dta.presets.caption").format(
        analysis_type=payload.get("analysis_type", _DTA_PRESET_ANALYSIS_TYPE),
        count=int(payload.get("count", len(options)) or 0),
        max_count=int(payload.get("max_count", 10) or 10),
    )
    return options, caption


@callback(
    Output("dta-preset-apply-btn", "disabled"),
    Output("dta-preset-delete-btn", "disabled"),
    Input("dta-preset-select", "value"),
)
def toggle_dta_preset_action_buttons(selected_name):
    """Disable Apply/Delete until the user picks a preset from the dropdown."""
    has_selection = bool(str(selected_name or "").strip())
    return (not has_selection, not has_selection)


@callback(
    Output("dta-processing-draft", "data", allow_duplicate=True),
    Output("dta-processing-undo", "data", allow_duplicate=True),
    Output("dta-processing-redo", "data", allow_duplicate=True),
    Output("dta-template-select", "value", allow_duplicate=True),
    Output("dta-preset-status", "children", allow_duplicate=True),
    Input("dta-preset-apply-btn", "n_clicks"),
    State("dta-preset-select", "value"),
    State("dta-processing-draft", "data"),
    State("dta-processing-undo", "data"),
    State("ui-locale", "data"),
    prevent_initial_call=True,
)
def apply_dta_preset(n_clicks, selected_name, draft, undo, locale_data):
    """Load the selected preset, push current draft onto undo, and apply its sections."""
    from dash_app import api_client

    loc = _loc(locale_data)
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    name = str(selected_name or "").strip()
    if not name:
        return (
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            translate_ui(loc, "dash.analysis.dta.presets.select_required"),
        )
    try:
        payload = api_client.load_analysis_preset(_DTA_PRESET_ANALYSIS_TYPE, name)
    except Exception as exc:  # noqa: BLE001
        return (
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            translate_ui(loc, "dash.analysis.dta.presets.apply_failed").format(error=str(exc)),
        )

    processing = dict(payload.get("processing") or {})
    next_draft = copy.deepcopy(draft or _default_processing_draft())
    for section in ("smoothing", "baseline", "peak_detection"):
        values = processing.get(section)
        if isinstance(values, dict):
            next_draft[section] = copy.deepcopy(values)

    template_id_raw = str(payload.get("workflow_template_id") or "").strip()
    template_output = template_id_raw if template_id_raw in _DTA_TEMPLATE_IDS else dash.no_update

    next_undo = _push_undo(undo, draft)
    status = translate_ui(loc, "dash.analysis.dta.presets.applied").format(preset=name)
    return next_draft, next_undo, [], template_output, status


@callback(
    Output("dta-preset-refresh", "data", allow_duplicate=True),
    Output("dta-preset-save-name", "value", allow_duplicate=True),
    Output("dta-preset-status", "children", allow_duplicate=True),
    Input("dta-preset-save-btn", "n_clicks"),
    State("dta-preset-save-name", "value"),
    State("dta-processing-draft", "data"),
    State("dta-template-select", "value"),
    State("dta-preset-refresh", "data"),
    State("ui-locale", "data"),
    prevent_initial_call=True,
)
def save_dta_preset(n_clicks, save_name, draft, template_id, refresh_token, locale_data):
    """Persist the current draft + template as a new preset (or update an existing one)."""
    from dash_app import api_client

    loc = _loc(locale_data)
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    name = str(save_name or "").strip()
    if not name:
        return (
            dash.no_update,
            dash.no_update,
            translate_ui(loc, "dash.analysis.dta.presets.save_name_required"),
        )
    try:
        response = api_client.save_analysis_preset(
            _DTA_PRESET_ANALYSIS_TYPE,
            name,
            workflow_template_id=str(template_id or "").strip() or None,
            processing=_overrides_from_draft(draft or {}),
        )
    except Exception as exc:  # noqa: BLE001
        return (
            dash.no_update,
            dash.no_update,
            translate_ui(loc, "dash.analysis.dta.presets.save_failed").format(error=str(exc)),
        )
    resolved_template = str(response.get("workflow_template_id") or template_id or "")
    status = translate_ui(loc, "dash.analysis.dta.presets.saved").format(
        preset=name, template=resolved_template
    )
    return int(refresh_token or 0) + 1, "", status


@callback(
    Output("dta-preset-refresh", "data", allow_duplicate=True),
    Output("dta-preset-select", "value", allow_duplicate=True),
    Output("dta-preset-status", "children", allow_duplicate=True),
    Input("dta-preset-delete-btn", "n_clicks"),
    State("dta-preset-select", "value"),
    State("dta-preset-refresh", "data"),
    State("ui-locale", "data"),
    prevent_initial_call=True,
)
def delete_dta_preset(n_clicks, selected_name, refresh_token, locale_data):
    """Remove a saved preset and refresh the dropdown."""
    from dash_app import api_client

    loc = _loc(locale_data)
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    name = str(selected_name or "").strip()
    if not name:
        return (
            dash.no_update,
            dash.no_update,
            translate_ui(loc, "dash.analysis.dta.presets.select_required"),
        )
    try:
        api_client.delete_analysis_preset(_DTA_PRESET_ANALYSIS_TYPE, name)
    except Exception as exc:  # noqa: BLE001
        return (
            dash.no_update,
            dash.no_update,
            translate_ui(loc, "dash.analysis.dta.presets.delete_failed").format(error=str(exc)),
        )
    status = translate_ui(loc, "dash.analysis.dta.presets.deleted").format(preset=name)
    return int(refresh_token or 0) + 1, None, status


@callback(
    Output("dta-dataset-selector-area", "children"),
    Output("dta-run-btn", "disabled"),
    Input("project-id", "data"),
    Input("dta-refresh", "data"),
    Input("ui-locale", "data"),
)
def load_eligible_datasets(project_id, _refresh, locale_data):
    loc = _loc(locale_data)
    if not project_id:
        return html.P(translate_ui(loc, "dash.analysis.workspace_inactive"), className="text-muted"), True

    from dash_app.api_client import workspace_datasets

    try:
        payload = workspace_datasets(project_id)
    except Exception as exc:
        return dbc.Alert(translate_ui(loc, "dash.analysis.error_loading_datasets", error=str(exc)), color="danger"), True

    all_datasets = payload.get("datasets", [])
    return dataset_selector_block(
        selector_id="dta-dataset-select",
        empty_msg=translate_ui(loc, "dash.analysis.dta.empty_import"),
        eligible=eligible_datasets(all_datasets, _DTA_ELIGIBLE_TYPES),
        all_datasets=all_datasets,
        eligible_types=_DTA_ELIGIBLE_TYPES,
        active_dataset=payload.get("active_dataset"),
        locale_data=locale_data,
    )


@callback(
    Output("dta-run-status", "children"),
    Output("dta-refresh", "data", allow_duplicate=True),
    Output("dta-latest-result-id", "data", allow_duplicate=True),
    Output("workspace-refresh", "data", allow_duplicate=True),
    Input("dta-run-btn", "n_clicks"),
    State("project-id", "data"),
    State("dta-dataset-select", "value"),
    State("dta-template-select", "value"),
    State("dta-refresh", "data"),
    State("workspace-refresh", "data"),
    State("ui-locale", "data"),
    State("dta-processing-draft", "data"),
    prevent_initial_call=True,
)
def run_dta_analysis(
    n_clicks,
    project_id,
    dataset_key,
    template_id,
    refresh_val,
    global_refresh,
    locale_data,
    processing_draft,
):
    loc = _loc(locale_data)
    if not n_clicks or not project_id or not dataset_key:
        raise dash.exceptions.PreventUpdate

    from dash_app.api_client import analysis_run

    overrides = _overrides_from_draft(processing_draft) or None
    try:
        result = analysis_run(
            project_id=project_id,
            dataset_key=dataset_key,
            analysis_type="DTA",
            workflow_template_id=template_id,
            processing_overrides=overrides,
        )
    except Exception as exc:
        return dbc.Alert(translate_ui(loc, "dash.analysis.analysis_failed", error=str(exc)), color="danger"), dash.no_update, dash.no_update, dash.no_update

    alert, saved, result_id = interpret_run_result(result, locale_data=locale_data)
    refresh = (refresh_val or 0) + 1
    if saved:
        return alert, refresh, result_id, (global_refresh or 0) + 1
    return alert, refresh, dash.no_update, dash.no_update


@callback(
    Output("dta-result-dataset-summary", "children"),
    Output("dta-result-metrics", "children"),
    Output("dta-result-peak-cards", "children"),
    Output("dta-result-figure", "children"),
    Output("dta-result-table", "children"),
    Output("dta-result-processing", "children"),
    Input("dta-latest-result-id", "data"),
    Input("dta-refresh", "data"),
    Input("ui-theme", "data"),
    Input("ui-locale", "data"),
    State("project-id", "data"),
)
def display_result(result_id, _refresh, ui_theme, locale_data, project_id):
    loc = _loc(locale_data)
    empty_msg = empty_result_msg(locale_data=locale_data)
    summary_empty = html.P(
        translate_ui(loc, "dash.analysis.dta.summary.empty"),
        className="text-muted",
    )
    if not result_id or not project_id:
        return summary_empty, empty_msg, empty_msg, empty_msg, empty_msg, empty_msg

    from dash_app.api_client import workspace_dataset_detail, workspace_result_detail

    try:
        detail = workspace_result_detail(project_id, result_id)
    except Exception as exc:
        err = dbc.Alert(translate_ui(loc, "dash.analysis.error_loading_result", error=str(exc)), color="danger")
        return summary_empty, err, empty_msg, empty_msg, empty_msg, empty_msg

    summary = detail.get("summary", {})
    result_meta = detail.get("result", {})
    processing = detail.get("processing", {})
    rows = _event_rows(detail.get("rows") or detail.get("rows_preview") or [])
    dataset_key = result_meta.get("dataset_key")

    dataset_detail = {}
    if dataset_key:
        try:
            dataset_detail = workspace_dataset_detail(project_id, dataset_key)
        except Exception:
            dataset_detail = {}

    dataset_summary_panel = _build_dta_dataset_summary(
        dataset_detail,
        summary,
        result_meta,
        loc,
        locale_data=locale_data,
    )

    peak_count, exo_count, endo_count = _derive_event_metrics(summary, rows)
    sample_name = _resolve_dta_sample_name(summary, result_meta, dataset_detail, locale_data=locale_data)

    metrics = metrics_row(
        [
            ("dash.analysis.metric.events", str(peak_count)),
            ("dash.analysis.metric.exothermic", str(exo_count)),
            ("dash.analysis.metric.endothermic", str(endo_count)),
            ("dash.analysis.metric.sample", sample_name),
        ],
        locale_data=locale_data,
    )

    peak_cards = _build_peak_cards(rows, loc)

    figure_area = empty_msg
    if dataset_key:
        figure_area = _build_figure(project_id, dataset_key, sample_name, rows, ui_theme, loc, locale_data)

    table_area = _build_peak_table(rows, loc)

    method_context = processing.get("method_context", {})
    na = translate_ui(loc, "dash.analysis.na")
    proc_view = processing_details_section(
        processing,
        extra_lines=[
            html.P(translate_ui(loc, "dash.analysis.dta.baseline", detail=processing.get("signal_pipeline", {}).get("baseline", {}))),
            html.P(translate_ui(loc, "dash.analysis.dta.peak_detection", detail=processing.get("analysis_steps", {}).get("peak_detection", {}))),
            html.P(translate_ui(loc, "dash.analysis.dta.sign_convention", detail=method_context.get("sign_convention_label", na)), className="mb-0"),
        ],
        locale_data=locale_data,
    )

    return dataset_summary_panel, metrics, peak_cards, figure_area, table_area, proc_view


def _format_dataset_metadata_value(value: Any) -> str | None:
    """Return a trimmed string for metadata values or None when empty."""
    if value is None:
        return None
    if isinstance(value, float):
        if value != value:  # NaN guard
            return None
        text = f"{value:g}"
    else:
        text = str(value).strip()
    return text or None


def _build_dta_dataset_summary(
    dataset_detail: dict,
    summary: dict,
    result_meta: dict,
    loc: str,
    *,
    locale_data: str | None = None,
) -> html.Div:
    """Render the Streamlit-parity dataset metadata block.

    Mirrors ``ui/dta_page.py::_render_dta_results`` lines 742-750 — shows
    dataset file name, sample name, sample mass, and heating rate when
    available. Falls back gracefully when any field is missing.
    """

    metadata = (dataset_detail or {}).get("metadata") or {}
    dataset_summary = (dataset_detail or {}).get("dataset") or {}
    na = translate_ui(loc, "dash.analysis.na")

    dataset_label = (
        _format_dataset_metadata_value(metadata.get("file_name"))
        or _format_dataset_metadata_value(dataset_summary.get("display_name"))
        or _format_dataset_metadata_value(result_meta.get("dataset_key"))
        or na
    )

    sample_label = _resolve_dta_sample_name(
        summary or {}, result_meta or {}, dataset_detail, locale_data=locale_data
    ) or na

    rows: list[Any] = [
        html.Dt(
            translate_ui(loc, "dash.analysis.dta.summary.dataset_label"),
            className="col-sm-4 text-muted",
        ),
        html.Dd(dataset_label, className="col-sm-8 mb-2"),
        html.Dt(
            translate_ui(loc, "dash.analysis.dta.summary.sample_label"),
            className="col-sm-4 text-muted",
        ),
        html.Dd(sample_label, className="col-sm-8 mb-2"),
    ]

    mass_value = _format_dataset_metadata_value(metadata.get("sample_mass"))
    if mass_value is not None:
        mass_unit = translate_ui(loc, "dash.analysis.dta.summary.mass_unit")
        rows.extend(
            [
                html.Dt(
                    translate_ui(loc, "dash.analysis.dta.summary.mass_label"),
                    className="col-sm-4 text-muted",
                ),
                html.Dd(f"{mass_value} {mass_unit}", className="col-sm-8 mb-2"),
            ]
        )

    heating_value = _format_dataset_metadata_value(
        metadata.get("heating_rate")
        if metadata.get("heating_rate") is not None
        else dataset_summary.get("heating_rate")
    )
    if heating_value is not None:
        heating_unit = translate_ui(loc, "dash.analysis.dta.summary.heating_rate_unit")
        rows.extend(
            [
                html.Dt(
                    translate_ui(loc, "dash.analysis.dta.summary.heating_rate_label"),
                    className="col-sm-4 text-muted",
                ),
                html.Dd(f"{heating_value} {heating_unit}", className="col-sm-8 mb-0"),
            ]
        )

    return html.Div(
        [
            html.H5(
                translate_ui(loc, "dash.analysis.dta.summary.card_title"),
                className="mb-3",
            ),
            html.Dl(rows, className="row mb-0", id="dta-dataset-summary-dl"),
        ],
        id="dta-dataset-summary-body",
    )


def _build_peak_cards(rows: list, loc: str = "en") -> html.Div:
    if not rows:
        return html.Div(
            [
                html.H5(translate_ui(loc, "dash.analysis.section.key_thermal_events"), className="mb-3"),
                html.P(translate_ui(loc, "dash.analysis.state.no_thermal_events"), className="text-muted"),
            ]
        )

    primary_rows, secondary_rows = _split_primary_events(rows)
    cards = [
        html.H5(translate_ui(loc, "dash.analysis.section.key_thermal_events"), className="mb-2"),
        html.P(
            translate_ui(
                loc,
                "dash.analysis.dta.events_cards_intro",
                shown=len(primary_rows),
                total=len(rows),
            ),
            className="text-muted small mb-3",
        ),
        dbc.Row(
            [dbc.Col(_peak_card(row, idx, loc), md=6) for idx, row in enumerate(primary_rows)],
            className="g-3",
        ),
    ]

    if secondary_rows:
        cards.append(
            html.Details(
                [
                    html.Summary(translate_ui(loc, "dash.analysis.dta.show_more_events", n=len(secondary_rows)), className="small"),
                    html.Div(
                        dataset_table(
                            secondary_rows,
                            ["direction", "peak_temperature", "onset_temperature", "endset_temperature", "area", "height"],
                            table_id="dta-secondary-events-table",
                        ),
                        className="mt-3",
                    ),
                ],
                className="mt-3",
            )
        )
    return html.Div(cards)


def _primary_trace_name(corrected: list, smoothed: list, raw_signal: list, loc: str) -> tuple[str, str]:
    if corrected:
        return translate_ui(loc, "dash.analysis.figure.legend_dta_primary_corrected"), "#047857"
    if smoothed:
        return translate_ui(loc, "dash.analysis.figure.legend_dta_primary_smoothed"), "#0E7490"
    return translate_ui(loc, "dash.analysis.figure.legend_dta_primary_raw"), "#475569"


def _build_dta_go_figure(
    project_id: str,
    dataset_key: str,
    sample_name: str,
    peak_rows: list,
    ui_theme: str | None,
    loc: str = "en",
) -> go.Figure | None:
    """Build the DTA Plotly figure, or return None when data is missing.

    Separated from ``_build_figure`` so the figure-capture callback can reuse
    the same plotting logic without constructing a ``dcc.Graph`` wrapper.
    """
    from dash_app.api_client import analysis_state_curves

    try:
        curves = analysis_state_curves(project_id, "DTA", dataset_key)
    except Exception:
        curves = {}

    temperature = curves.get("temperature", [])
    raw_signal = _series_for_temperature(curves.get("raw_signal", []), temperature)
    smoothed = _series_for_temperature(curves.get("smoothed", []), temperature)
    baseline = _series_for_temperature(curves.get("baseline", []), temperature)
    corrected = _series_for_temperature(curves.get("corrected", []), temperature)

    if not temperature:
        return None

    primary_signal = corrected or smoothed or raw_signal
    if not primary_signal:
        return None

    fig = go.Figure()
    primary_name, primary_color = _primary_trace_name(corrected, smoothed, raw_signal, loc)
    y_range = _compute_y_axis_range(primary_signal, baseline, smoothed if corrected else [], raw_signal if not (corrected or smoothed) else [])

    legend_raw = translate_ui(loc, "dash.analysis.figure.legend_raw_signal")
    legend_smooth = translate_ui(loc, "dash.analysis.figure.legend_smoothed")
    legend_base = translate_ui(loc, "dash.analysis.figure.legend_baseline")
    legend_primary_smoothed = translate_ui(loc, "dash.analysis.figure.legend_dta_primary_smoothed")

    if raw_signal:
        fig.add_trace(
            go.Scatter(
                x=temperature,
                y=raw_signal,
                mode="lines",
                name=legend_raw,
                line=dict(color="#94A3B8", width=1.0 if primary_name != legend_raw else 1.8),
                opacity=0.24 if primary_name != legend_raw else 0.9,
            )
        )

    if smoothed and primary_name != legend_primary_smoothed:
        fig.add_trace(
            go.Scatter(
                x=temperature,
                y=smoothed,
                mode="lines",
                name=legend_smooth,
                line=dict(color="#0891B2", width=1.5),
                opacity=0.9,
            )
        )

    if baseline:
        fig.add_trace(
            go.Scatter(
                x=temperature,
                y=baseline,
                mode="lines",
                name=legend_base,
                line=dict(color="#64748B", width=1.0, dash="dot"),
                opacity=0.8,
            )
        )

    fig.add_trace(
        go.Scatter(
            x=temperature,
            y=primary_signal,
            mode="lines",
            name=primary_name,
            line=dict(color=primary_color, width=2.8),
            opacity=1.0,
        )
    )

    primary_rows, _secondary_rows = _split_primary_events(peak_rows, limit=min(_PRIMARY_EVENT_LIMIT, len(peak_rows) or 0))
    primary_ids = {id(row) for row in primary_rows}
    guide_rows = primary_rows if len(peak_rows) > _PRIMARY_EVENT_LIMIT else _sort_events_by_temperature(peak_rows)
    annotate_guides = len(guide_rows) <= 3
    annotated_temps: list[float] = []

    for row in guide_rows:
        direction = _normalize_direction(row.get("direction", row.get("peak_type")))
        guide_color = _DIRECTION_GUIDE_COLORS.get(direction, "rgba(100, 116, 139, 0.18)")
        onset = _coerce_float(row.get("onset_temperature"))
        endset = _coerce_float(row.get("endset_temperature"))
        if onset is not None:
            fig.add_vline(
                x=onset,
                line=dict(color=guide_color, width=1, dash="dot"),
                annotation_text=translate_ui(loc, "dash.analysis.figure.annot_on", v=f"{onset:.1f}") if annotate_guides else None,
                annotation_position="top left",
            )
        if endset is not None:
            fig.add_vline(
                x=endset,
                line=dict(color=guide_color, width=1, dash="dot"),
                annotation_text=translate_ui(loc, "dash.analysis.figure.annot_end", v=f"{endset:.1f}") if annotate_guides else None,
                annotation_position="top left",
            )

    for row in _sort_events_by_temperature(peak_rows):
        pt = _coerce_float(row.get("peak_temperature"))
        if pt is None or not temperature:
            continue
        direction = _normalize_direction(row.get("direction", row.get("peak_type", "unknown")))
        color = _DIRECTION_COLORS.get(direction, "#B45309")
        idx = min(range(len(temperature)), key=lambda i: abs(temperature[i] - pt))
        too_close = any(abs(pt - t) < _ANNOTATION_MIN_SEP for t in annotated_temps)
        is_primary = id(row) in primary_ids
        text_str = f"{pt:.1f}" if is_primary and not too_close else ""
        fig.add_trace(
            go.Scatter(
                x=[temperature[idx]],
                y=[primary_signal[idx]],
                mode="markers+text",
                marker=dict(
                    size=11 if is_primary else 8,
                    color=color,
                    symbol="diamond",
                    line=dict(color="white", width=1.2),
                ),
                text=[text_str],
                textposition="top center",
                textfont=dict(size=9, color=color),
                name=f"{_direction_label(direction, loc)} {pt:.1f} C",
                showlegend=False,
            )
        )
        if text_str:
            annotated_temps.append(pt)

    fig.update_layout(
        title=translate_ui(loc, "dash.analysis.figure.title_dta", name=sample_name),
        xaxis_title=translate_ui(loc, "dash.analysis.figure.axis_temperature_c"),
        yaxis_title=translate_ui(loc, "dash.analysis.figure.axis_delta_t"),
        hovermode="x unified",
        margin=dict(l=56, r=24, t=56, b=48),
        height=560,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    apply_figure_theme(fig, ui_theme)
    fig.update_yaxes(range=y_range)
    return fig


def _build_figure(
    project_id: str,
    dataset_key: str,
    sample_name: str,
    peak_rows: list,
    ui_theme: str | None,
    loc: str = "en",
    locale_data: str | None = None,
) -> html.Div:
    _ld = locale_data if locale_data is not None else loc
    from dash_app.api_client import analysis_state_curves

    try:
        curves = analysis_state_curves(project_id, "DTA", dataset_key)
    except Exception:
        curves = {}
    if not curves.get("temperature"):
        return no_data_figure_msg(locale_data=_ld)

    fig = _build_dta_go_figure(project_id, dataset_key, sample_name, peak_rows, ui_theme, loc)
    if fig is None:
        return no_data_figure_msg(text=translate_ui(loc, "dash.analysis.dta.no_plot_signal"), locale_data=_ld)
    return dcc.Graph(figure=fig, config={"displaylogo": False, "responsive": True}, className="ta-plot")


def _build_peak_table(rows: list, loc: str = "en") -> html.Div:
    if not rows:
        return html.Div(
            [
                html.H5(translate_ui(loc, "dash.analysis.section.all_event_details"), className="mb-3"),
                html.P(translate_ui(loc, "dash.analysis.state.no_event_data"), className="text-muted"),
            ]
        )

    columns = [
        "direction",
        "peak_temperature",
        "onset_temperature",
        "endset_temperature",
        "area",
        "fwhm",
        "height",
    ]
    return html.Div(
        [
            html.H5(translate_ui(loc, "dash.analysis.section.all_event_details"), className="mb-3"),
            dataset_table(rows, columns, table_id="dta-peaks-table"),
        ]
    )


def _smoothing_status_text(draft: dict | None, loc: str) -> str:
    """Build a concise status line summarizing the current smoothing draft."""
    values = (draft or {}).get("smoothing") or {}
    method = str(values.get("method") or "savgol")
    method_label = {"savgol": "Savitzky-Golay", "moving_average": "Moving Average", "gaussian": "Gaussian"}.get(method, method)
    parts = [f"{method_label}"]
    if "window_length" in values:
        parts.append(f"window={values['window_length']}")
    if "polyorder" in values:
        parts.append(f"polyorder={values['polyorder']}")
    if "sigma" in values:
        parts.append(f"sigma={values['sigma']}")
    applied = translate_ui(loc, "dash.analysis.dta.smoothing.applied")
    if applied == "dash.analysis.dta.smoothing.applied":
        applied = "Applied"
    return f"{applied}: {' - '.join(parts)}"


@callback(
    Output("dta-smoothing-card-title", "children"),
    Output("dta-smooth-method-label", "children"),
    Output("dta-smooth-window-label", "children"),
    Output("dta-smooth-polyorder-label", "children"),
    Output("dta-smooth-sigma-label", "children"),
    Output("dta-smooth-apply-btn", "children"),
    Output("dta-undo-btn", "children"),
    Output("dta-redo-btn", "children"),
    Output("dta-reset-btn", "children"),
    Output("dta-smooth-method-hint", "children"),
    Output("dta-smooth-window-hint", "children"),
    Output("dta-smooth-polyorder-hint", "children"),
    Output("dta-smooth-sigma-hint", "children"),
    Input("ui-locale", "data"),
)
def render_dta_smoothing_chrome(locale_data):
    loc = _loc(locale_data)

    def _t(key: str, fallback: str) -> str:
        value = translate_ui(loc, key)
        return fallback if value == key else value

    return (
        _t("dash.analysis.dta.smoothing.title", "Smoothing"),
        _t("dash.analysis.dta.smoothing.method", "Smoothing Method"),
        _t("dash.analysis.dta.smoothing.window", "Window Length"),
        _t("dash.analysis.dta.smoothing.polyorder", "Polynomial Order"),
        _t("dash.analysis.dta.smoothing.sigma", "Sigma"),
        _t("dash.analysis.dta.smoothing.apply_btn", "Apply Smoothing"),
        _t("dash.analysis.dta.undo_btn", "Undo"),
        _t("dash.analysis.dta.redo_btn", "Redo"),
        _t("dash.analysis.dta.reset_btn", "Reset"),
        _t(
            "dash.analysis.dta.smoothing.help.method",
            "Savitzky-Golay preserves peak shape; Moving Average is simple and fast; Gaussian gives the smoothest curve.",
        ),
        _t(
            "dash.analysis.dta.smoothing.help.window",
            "Number of points averaged. Larger values smooth more but can blur small peaks. Must be odd; try 7-15 for typical DTA traces.",
        ),
        _t(
            "dash.analysis.dta.smoothing.help.polyorder",
            "Polynomial order for Savitzky-Golay. Higher orders preserve sharp peaks but may re-introduce noise. Usually 2-4.",
        ),
        _t(
            "dash.analysis.dta.smoothing.help.sigma",
            "Gaussian kernel width. Larger sigma = stronger smoothing. Start from 1.0-3.0 and raise if the baseline is still noisy.",
        ),
    )


@callback(
    Output("dta-smooth-window", "disabled"),
    Output("dta-smooth-polyorder", "disabled"),
    Output("dta-smooth-sigma", "disabled"),
    Input("dta-smooth-method", "value"),
)
def toggle_smoothing_inputs(method):
    token = str(method or "savgol").strip().lower()
    if token == "savgol":
        return False, False, True
    if token == "moving_average":
        return False, True, True
    return True, True, False


@callback(
    Output("dta-processing-draft", "data", allow_duplicate=True),
    Output("dta-processing-undo", "data", allow_duplicate=True),
    Output("dta-processing-redo", "data", allow_duplicate=True),
    Input("dta-smooth-apply-btn", "n_clicks"),
    State("dta-smooth-method", "value"),
    State("dta-smooth-window", "value"),
    State("dta-smooth-polyorder", "value"),
    State("dta-smooth-sigma", "value"),
    State("dta-processing-draft", "data"),
    State("dta-processing-undo", "data"),
    prevent_initial_call=True,
)
def apply_smoothing(n_clicks, method, window, polyorder, sigma, draft, undo):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    values = _normalize_smoothing_values(method, window, polyorder, sigma)
    next_undo = _push_undo(undo, draft)
    next_draft = _apply_draft_section(draft, "smoothing", values)
    return next_draft, next_undo, []


@callback(
    Output("dta-processing-draft", "data", allow_duplicate=True),
    Output("dta-processing-undo", "data", allow_duplicate=True),
    Output("dta-processing-redo", "data", allow_duplicate=True),
    Input("dta-undo-btn", "n_clicks"),
    State("dta-processing-draft", "data"),
    State("dta-processing-undo", "data"),
    State("dta-processing-redo", "data"),
    prevent_initial_call=True,
)
def undo_processing(n_clicks, draft, undo, redo):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    next_draft, next_undo, next_redo = _do_undo(draft or {}, undo, redo)
    return next_draft, next_undo, next_redo


@callback(
    Output("dta-processing-draft", "data", allow_duplicate=True),
    Output("dta-processing-undo", "data", allow_duplicate=True),
    Output("dta-processing-redo", "data", allow_duplicate=True),
    Input("dta-redo-btn", "n_clicks"),
    State("dta-processing-draft", "data"),
    State("dta-processing-undo", "data"),
    State("dta-processing-redo", "data"),
    prevent_initial_call=True,
)
def redo_processing(n_clicks, draft, undo, redo):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    next_draft, next_undo, next_redo = _do_redo(draft or {}, undo, redo)
    return next_draft, next_undo, next_redo


@callback(
    Output("dta-processing-draft", "data", allow_duplicate=True),
    Output("dta-processing-undo", "data", allow_duplicate=True),
    Output("dta-processing-redo", "data", allow_duplicate=True),
    Input("dta-reset-btn", "n_clicks"),
    State("dta-processing-draft", "data"),
    State("dta-processing-undo", "data"),
    State("dta-processing-redo", "data"),
    State("dta-processing-default", "data"),
    prevent_initial_call=True,
)
def reset_processing(n_clicks, draft, undo, redo, defaults):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    next_draft, next_undo, next_redo = _do_reset(draft or {}, undo, redo, defaults)
    return next_draft, next_undo, next_redo


@callback(
    Output("dta-smooth-method", "value"),
    Output("dta-smooth-window", "value"),
    Output("dta-smooth-polyorder", "value"),
    Output("dta-smooth-sigma", "value"),
    Output("dta-smooth-status", "children"),
    Output("dta-undo-btn", "disabled"),
    Output("dta-redo-btn", "disabled"),
    Output("dta-reset-btn", "disabled"),
    Input("dta-processing-draft", "data"),
    Input("dta-processing-undo", "data"),
    Input("dta-processing-redo", "data"),
    Input("dta-processing-default", "data"),
    Input("ui-locale", "data"),
)
def sync_smoothing_controls(draft, undo, redo, defaults, locale_data):
    loc = _loc(locale_data)
    values = (draft or {}).get("smoothing") or {}
    method = str(values.get("method") or "savgol")
    window_length = values.get("window_length", 11)
    polyorder = values.get("polyorder", 3)
    sigma = values.get("sigma", 2.0)
    status = _smoothing_status_text(draft, loc)
    undo_disabled = not bool(undo)
    redo_disabled = not bool(redo)
    reset_disabled = (draft or {}) == (defaults or {})
    return method, window_length, polyorder, sigma, status, undo_disabled, redo_disabled, reset_disabled


def _baseline_status_text(draft: dict | None, loc: str) -> str:
    """Build a concise status line summarizing the current baseline draft."""
    values = (draft or {}).get("baseline") or {}
    method = str(values.get("method") or "asls")
    method_label = {"asls": "AsLS", "linear": "Linear", "rubberband": "Rubberband"}.get(method, method)
    parts = [method_label]
    if method == "asls":
        if "lam" in values:
            parts.append(f"lam={values['lam']:g}")
        if "p" in values:
            parts.append(f"p={values['p']:g}")
    applied = translate_ui(loc, "dash.analysis.dta.baseline.applied")
    if applied == "dash.analysis.dta.baseline.applied":
        applied = "Applied"
    return f"{applied}: {' - '.join(parts)}"


def _peak_status_text(draft: dict | None, loc: str) -> str:
    """Build a concise status line summarizing the current peak-detection draft."""
    values = (draft or {}).get("peak_detection") or {}
    flags = []
    if values.get("detect_exothermic", True):
        flags.append("exo")
    if values.get("detect_endothermic", True):
        flags.append("endo")
    parts = ["/".join(flags) if flags else "none"]
    prom = values.get("prominence")
    if prom is not None:
        parts.append("prominence=auto" if float(prom) == 0.0 else f"prominence={prom:g}")
    dist = values.get("distance")
    if dist is not None:
        parts.append(f"distance={int(dist)}")
    applied = translate_ui(loc, "dash.analysis.dta.peaks.applied")
    if applied == "dash.analysis.dta.peaks.applied":
        applied = "Applied"
    return f"{applied}: {' - '.join(parts)}"


@callback(
    Output("dta-baseline-card-title", "children"),
    Output("dta-baseline-method-label", "children"),
    Output("dta-baseline-lam-label", "children"),
    Output("dta-baseline-p-label", "children"),
    Output("dta-baseline-apply-btn", "children"),
    Output("dta-baseline-method-hint", "children"),
    Output("dta-baseline-lam-hint", "children"),
    Output("dta-baseline-p-hint", "children"),
    Input("ui-locale", "data"),
)
def render_dta_baseline_chrome(locale_data):
    loc = _loc(locale_data)

    def _t(key: str, fallback: str) -> str:
        value = translate_ui(loc, key)
        return fallback if value == key else value

    return (
        _t("dash.analysis.dta.baseline.title", "Baseline"),
        _t("dash.analysis.dta.baseline.method", "Baseline Method"),
        _t("dash.analysis.dta.baseline.lam", "Lambda (asls)"),
        _t("dash.analysis.dta.baseline.p", "Asymmetry p (asls)"),
        _t("dash.analysis.dta.baseline.apply_btn", "Apply Baseline"),
        _t(
            "dash.analysis.dta.baseline.help.method",
            "AsLS handles curved drifting baselines; Linear fits a straight line (fast, good for short ranges); Rubberband wraps the signal from below.",
        ),
        _t(
            "dash.analysis.dta.baseline.help.lam",
            "AsLS baseline stiffness. Higher values (1e7+) keep the baseline flat; lower values (1e4) let it follow peaks — risks absorbing real events.",
        ),
        _t(
            "dash.analysis.dta.baseline.help.p",
            "AsLS asymmetry. Small values (0.001-0.01) push the baseline below exothermic peaks; use 0.1-0.5 when the baseline should pass above endotherms.",
        ),
    )


@callback(
    Output("dta-peak-card-title", "children"),
    Output("dta-peak-detect-exo", "label"),
    Output("dta-peak-detect-endo", "label"),
    Output("dta-peak-prominence-label", "children"),
    Output("dta-peak-distance-label", "children"),
    Output("dta-peak-apply-btn", "children"),
    Output("dta-peak-detect-exo-hint", "children"),
    Output("dta-peak-detect-endo-hint", "children"),
    Output("dta-peak-prominence-hint", "children"),
    Output("dta-peak-distance-hint", "children"),
    Input("ui-locale", "data"),
)
def render_dta_peak_chrome(locale_data):
    loc = _loc(locale_data)

    def _t(key: str, fallback: str) -> str:
        value = translate_ui(loc, key)
        return fallback if value == key else value

    return (
        _t("dash.analysis.dta.peaks.title", "Peak Detection"),
        _t("dash.analysis.dta.peaks.detect_exo", "Detect Exothermic"),
        _t("dash.analysis.dta.peaks.detect_endo", "Detect Endothermic"),
        _t("dash.analysis.dta.peaks.prominence", "Prominence (0 = auto)"),
        _t("dash.analysis.dta.peaks.distance", "Min Distance (samples)"),
        _t("dash.analysis.dta.peaks.apply_btn", "Apply Peaks"),
        _t(
            "dash.analysis.dta.peaks.help.detect_exo",
            "Report exothermic peaks (heat-releasing events such as crystallization or oxidation).",
        ),
        _t(
            "dash.analysis.dta.peaks.help.detect_endo",
            "Report endothermic peaks (heat-absorbing events such as melting or decomposition).",
        ),
        _t(
            "dash.analysis.dta.peaks.help.prominence",
            "Minimum relative height a peak must stand above its surroundings. 0 = auto-threshold (~5% of signal range). Raise to ignore noise; lower to catch subtle events.",
        ),
        _t(
            "dash.analysis.dta.peaks.help.distance",
            "Minimum sample separation between adjacent peaks. Raise to merge closely-spaced events into one; lower to keep doublets separate.",
        ),
    )


@callback(
    Output("dta-baseline-lam", "disabled"),
    Output("dta-baseline-p", "disabled"),
    Input("dta-baseline-method", "value"),
)
def toggle_baseline_inputs(method):
    token = str(method or "asls").strip().lower()
    if token == "asls":
        return False, False
    return True, True


@callback(
    Output("dta-processing-draft", "data", allow_duplicate=True),
    Output("dta-processing-undo", "data", allow_duplicate=True),
    Output("dta-processing-redo", "data", allow_duplicate=True),
    Input("dta-baseline-apply-btn", "n_clicks"),
    State("dta-baseline-method", "value"),
    State("dta-baseline-lam", "value"),
    State("dta-baseline-p", "value"),
    State("dta-processing-draft", "data"),
    State("dta-processing-undo", "data"),
    prevent_initial_call=True,
)
def apply_baseline(n_clicks, method, lam, p, draft, undo):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    values = _normalize_baseline_values(method, lam, p)
    next_undo = _push_undo(undo, draft)
    next_draft = _apply_draft_section(draft, "baseline", values)
    return next_draft, next_undo, []


@callback(
    Output("dta-processing-draft", "data", allow_duplicate=True),
    Output("dta-processing-undo", "data", allow_duplicate=True),
    Output("dta-processing-redo", "data", allow_duplicate=True),
    Input("dta-peak-apply-btn", "n_clicks"),
    State("dta-peak-detect-exo", "value"),
    State("dta-peak-detect-endo", "value"),
    State("dta-peak-prominence", "value"),
    State("dta-peak-distance", "value"),
    State("dta-processing-draft", "data"),
    State("dta-processing-undo", "data"),
    prevent_initial_call=True,
)
def apply_peak_detection(n_clicks, detect_exo, detect_endo, prominence, distance, draft, undo):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    values = _normalize_peak_detection_values(detect_endo, detect_exo, prominence, distance)
    next_undo = _push_undo(undo, draft)
    next_draft = _apply_draft_section(draft, "peak_detection", values)
    return next_draft, next_undo, []


@callback(
    Output("dta-baseline-method", "value"),
    Output("dta-baseline-lam", "value"),
    Output("dta-baseline-p", "value"),
    Output("dta-baseline-status", "children"),
    Input("dta-processing-draft", "data"),
    Input("ui-locale", "data"),
)
def sync_baseline_controls(draft, locale_data):
    loc = _loc(locale_data)
    values = (draft or {}).get("baseline") or {}
    method = str(values.get("method") or "asls")
    lam = values.get("lam", 1e6)
    p = values.get("p", 0.01)
    status = _baseline_status_text(draft, loc)
    return method, lam, p, status


@callback(
    Output("dta-peak-detect-exo", "value"),
    Output("dta-peak-detect-endo", "value"),
    Output("dta-peak-prominence", "value"),
    Output("dta-peak-distance", "value"),
    Output("dta-peak-status", "children"),
    Input("dta-processing-draft", "data"),
    Input("ui-locale", "data"),
)
def sync_peak_controls(draft, locale_data):
    loc = _loc(locale_data)
    values = (draft or {}).get("peak_detection") or {}
    detect_exo = bool(values.get("detect_exothermic", True))
    detect_endo = bool(values.get("detect_endothermic", True))
    prominence = values.get("prominence", 0.0)
    distance = values.get("distance", 1)
    status = _peak_status_text(draft, loc)
    return detect_exo, detect_endo, prominence, distance, status


# ---------------------------------------------------------------------------
# Phase 2b: Literature Compare panel + Figure capture for Report Center
# ---------------------------------------------------------------------------


def _literature_t(loc: str, key: str, fallback: str) -> str:
    """Translate with a literal fallback when the key is missing from the bundle."""
    value = translate_ui(loc, key)
    return fallback if value == key else value


@callback(
    Output("dta-literature-card-title", "children"),
    Output("dta-literature-hint", "children"),
    Output("dta-literature-max-claims-label", "children"),
    Output("dta-literature-persist-label", "children"),
    Output("dta-literature-compare-btn", "children"),
    Input("ui-locale", "data"),
    Input("dta-latest-result-id", "data"),
)
def render_dta_literature_chrome(locale_data, result_id):
    loc = _loc(locale_data)
    if result_id:
        hint = _literature_t(
            loc,
            "dash.analysis.dta.literature.ready",
            "Compare the saved DTA result to literature sources.",
        )
    else:
        hint = _literature_t(
            loc,
            "dash.analysis.dta.literature.empty",
            "Run a DTA analysis first to enable literature comparison.",
        )
    return (
        _literature_t(loc, "dash.analysis.dta.literature.title", "Literature Compare"),
        hint,
        _literature_t(loc, "dash.analysis.dta.literature.max_claims", "Max Claims"),
        _literature_t(loc, "dash.analysis.dta.literature.persist", "Persist to project"),
        _literature_t(loc, "dash.analysis.dta.literature.compare_btn", "Compare"),
    )


@callback(
    Output("dta-literature-compare-btn", "disabled"),
    Input("dta-latest-result-id", "data"),
)
def toggle_literature_compare_button(result_id):
    return not bool(result_id)


def _render_literature_output(payload: dict, loc: str) -> html.Div:
    """Render claims / comparisons / citations from the literature compare payload."""
    claims = payload.get("literature_claims") or []
    comparisons = payload.get("literature_comparisons") or []
    citations = payload.get("citations") or []

    def _section(heading_key: str, fallback: str, items: list[dict], empty_key: str, empty_fallback: str):
        title = html.H6(_literature_t(loc, heading_key, fallback), className="mt-2 mb-1")
        if not items:
            return html.Div(
                [title, html.P(_literature_t(loc, empty_key, empty_fallback), className="small text-muted")],
            )
        list_items = []
        for entry in items:
            if not isinstance(entry, dict):
                continue
            text = (
                entry.get("statement")
                or entry.get("claim")
                or entry.get("title")
                or entry.get("summary")
                or ""
            )
            source = entry.get("source") or entry.get("provider") or entry.get("doi") or ""
            head = str(text).strip() or "-"
            tail = f" ({source})" if source else ""
            list_items.append(html.Li(f"{head}{tail}", className="small"))
        return html.Div([title, html.Ul(list_items, className="mb-0 ps-3")])

    return html.Div(
        [
            _section(
                "dash.analysis.dta.literature.claims",
                "Claims",
                claims,
                "dash.analysis.dta.literature.claims_empty",
                "No claims returned.",
            ),
            _section(
                "dash.analysis.dta.literature.comparisons",
                "Comparisons",
                comparisons,
                "dash.analysis.dta.literature.comparisons_empty",
                "No comparisons returned.",
            ),
            _section(
                "dash.analysis.dta.literature.citations",
                "Citations",
                citations,
                "dash.analysis.dta.literature.citations_empty",
                "No citations returned.",
            ),
        ]
    )


@callback(
    Output("dta-literature-output", "children"),
    Output("dta-literature-status", "children"),
    Input("dta-literature-compare-btn", "n_clicks"),
    State("project-id", "data"),
    State("dta-latest-result-id", "data"),
    State("dta-literature-max-claims", "value"),
    State("dta-literature-persist", "value"),
    State("ui-locale", "data"),
    prevent_initial_call=True,
)
def compare_dta_literature(n_clicks, project_id, result_id, max_claims, persist_values, locale_data):
    loc = _loc(locale_data)
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    if not project_id or not result_id:
        msg = _literature_t(
            loc,
            "dash.analysis.dta.literature.missing_result",
            "Run a DTA analysis first.",
        )
        return dash.no_update, dbc.Alert(msg, color="warning", className="py-1 small")

    claims_limit = _coerce_int_positive(max_claims, default=3, minimum=1)
    persist = bool(persist_values) and "persist" in (persist_values or [])

    from dash_app.api_client import literature_compare

    try:
        payload = literature_compare(
            project_id,
            result_id,
            max_claims=claims_limit,
            persist=persist,
        )
    except Exception as exc:
        err = dbc.Alert(
            _literature_t(
                loc,
                "dash.analysis.dta.literature.error",
                "Literature compare failed: {error}",
            ).replace("{error}", str(exc)),
            color="danger",
            className="py-1 small",
        )
        return dash.no_update, err

    status = dbc.Alert(
        _literature_t(
            loc,
            "dash.analysis.dta.literature.success",
            "Literature comparison retrieved.",
        ),
        color="success",
        className="py-1 small",
    )
    return _render_literature_output(payload, loc), status


def _capture_dta_figure_png(
    project_id: str,
    dataset_key: str,
    sample_name: str,
    peak_rows: list,
    ui_theme: str | None,
    loc: str,
) -> bytes | None:
    """Build the DTA figure as PNG bytes; return None on any failure.

    Uses ``plotly.io.to_image`` (kaleido) and swallows errors so the capture
    callback never breaks the rest of the UI if kaleido is unavailable.
    """
    fig = _build_dta_go_figure(project_id, dataset_key, sample_name, peak_rows, ui_theme, loc)
    if fig is None:
        return None
    try:
        import plotly.io as pio

        return pio.to_image(fig, format="png", engine="kaleido")
    except Exception:
        return None


@callback(
    Output("dta-figure-captured", "data"),
    Input("dta-latest-result-id", "data"),
    State("project-id", "data"),
    State("dta-figure-captured", "data"),
    State("ui-theme", "data"),
    State("ui-locale", "data"),
    prevent_initial_call=True,
)
def capture_dta_figure(result_id, project_id, captured, ui_theme, locale_data):
    """Render a PNG of the saved DTA figure and register it with the backend.

    Fires once per saved ``result_id`` (dedup via ``dta-figure-captured`` store).
    Failures degrade silently: the Report Center simply won't have a figure.
    """
    if not result_id or not project_id:
        raise dash.exceptions.PreventUpdate

    captured = dict(captured or {})
    if captured.get(result_id):
        raise dash.exceptions.PreventUpdate

    loc = _loc(locale_data)

    from dash_app.api_client import (
        register_result_figure,
        workspace_dataset_detail,
        workspace_result_detail,
    )

    try:
        detail = workspace_result_detail(project_id, result_id)
    except Exception:
        captured[result_id] = {"status": "error", "stage": "detail"}
        return captured

    result_meta = detail.get("result", {}) or {}
    summary = detail.get("summary", {}) or {}
    dataset_key = result_meta.get("dataset_key")
    rows = _event_rows(detail.get("rows") or detail.get("rows_preview") or [])

    if not dataset_key:
        captured[result_id] = {"status": "skipped", "reason": "missing_dataset_key"}
        return captured

    dataset_detail: dict = {}
    try:
        dataset_detail = workspace_dataset_detail(project_id, dataset_key)
    except Exception:
        dataset_detail = {}
    sample_name = _resolve_dta_sample_name(summary, result_meta, dataset_detail, locale_data=locale_data)

    png_bytes = _capture_dta_figure_png(project_id, dataset_key, sample_name, rows, ui_theme, loc)
    if not png_bytes:
        captured[result_id] = {"status": "skipped", "reason": "render_failed"}
        return captured

    label = f"DTA Analysis - {dataset_key}"
    try:
        register_result_figure(project_id, result_id, png_bytes, label=label, replace=True)
    except Exception:
        captured[result_id] = {"status": "error", "stage": "register", "label": label}
        return captured

    captured[result_id] = {"status": "ok", "label": label}
    return captured
