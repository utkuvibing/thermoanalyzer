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

import math

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


def _loc(locale_data: str | None) -> str:
    return normalize_ui_locale(locale_data)


def _clean_sample_token(value) -> str | None:
    token = str(value or "").strip()
    if not token or token.lower() in _EMPTY_SAMPLE_TOKENS:
        return None
    return token


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
    normalized_summary["sample_name"] = _clean_sample_token(normalized_summary.get("sample_name"))
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


layout = html.Div(
    analysis_page_stores("dta-refresh", "dta-latest-result-id")
    + [
        html.Div(id="dta-hero-slot"),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dataset_selection_card("dta-dataset-selector-area", card_title_id="dta-dataset-card-title"),
                        workflow_template_card(
                            "dta-template-select",
                            "dta-template-description",
                            [],
                            "dta.general",
                            card_title_id="dta-workflow-card-title",
                        ),
                        execute_card("dta-run-status", "dta-run-btn", card_title_id="dta-execute-card-title"),
                    ],
                    md=4,
                ),
                dbc.Col(
                    [
                        result_placeholder_card("dta-result-metrics"),
                        result_placeholder_card("dta-result-figure"),
                        result_placeholder_card("dta-result-peak-cards"),
                        result_placeholder_card("dta-result-table"),
                        result_placeholder_card("dta-result-processing"),
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
    prevent_initial_call=True,
)
def run_dta_analysis(n_clicks, project_id, dataset_key, template_id, refresh_val, global_refresh, locale_data):
    loc = _loc(locale_data)
    if not n_clicks or not project_id or not dataset_key:
        raise dash.exceptions.PreventUpdate

    from dash_app.api_client import analysis_run

    try:
        result = analysis_run(
            project_id=project_id,
            dataset_key=dataset_key,
            analysis_type="DTA",
            workflow_template_id=template_id,
        )
    except Exception as exc:
        return dbc.Alert(translate_ui(loc, "dash.analysis.analysis_failed", error=str(exc)), color="danger"), dash.no_update, dash.no_update, dash.no_update

    alert, saved, result_id = interpret_run_result(result, locale_data=locale_data)
    refresh = (refresh_val or 0) + 1
    if saved:
        return alert, refresh, result_id, (global_refresh or 0) + 1
    return alert, refresh, dash.no_update, dash.no_update


@callback(
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
    if not result_id or not project_id:
        return empty_msg, empty_msg, empty_msg, empty_msg, empty_msg

    from dash_app.api_client import workspace_dataset_detail, workspace_result_detail

    try:
        detail = workspace_result_detail(project_id, result_id)
    except Exception as exc:
        err = dbc.Alert(translate_ui(loc, "dash.analysis.error_loading_result", error=str(exc)), color="danger")
        return err, empty_msg, empty_msg, empty_msg, empty_msg

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

    return metrics, peak_cards, figure_area, table_area, proc_view


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


def _build_figure(
    project_id: str,
    dataset_key: str,
    sample_name: str,
    peak_rows: list,
    ui_theme: str | None,
    loc: str = "en",
    locale_data: str | None = None,
) -> html.Div:
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

    _ld = locale_data if locale_data is not None else loc
    if not temperature:
        return no_data_figure_msg(locale_data=_ld)

    primary_signal = corrected or smoothed or raw_signal
    if not primary_signal:
        return no_data_figure_msg(text=translate_ui(loc, "dash.analysis.dta.no_plot_signal"), locale_data=_ld)

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
