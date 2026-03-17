"""XRD Analysis page - multi-tab stable qualitative phase-screening workflow."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.batch_runner import execute_batch_template
from core.modalities import analysis_state_key
from core.processing_schema import (
    ensure_processing_payload,
    get_workflow_templates,
    set_workflow_template,
    update_method_context,
    update_processing_step,
)
from core.validation import validate_thermal_dataset
from core.xrd_display import (
    format_scientific_formula_text,
    xrd_candidate_display_name as resolve_xrd_candidate_display_name,
    xrd_candidate_display_payload as resolve_xrd_candidate_display_payload,
    xrd_candidate_display_variants as resolve_xrd_candidate_display_variants,
)
from ui.components.chrome import render_page_header
from ui.components.history_tracker import _log_event
from ui.components.preset_manager import render_processing_preset_panel, seed_pending_workflow_template
from ui.components.plot_builder import (
    PLOTLY_CONFIG,
    THERMAL_COLORS,
    apply_professional_plot_theme,
    create_thermal_plot,
    fig_to_bytes,
)
from utils.diagnostics import record_exception
from utils.i18n import t, tx
from utils.license_manager import APP_VERSION


_XRD_TEMPLATE_DEFAULTS = {
    "xrd.general": {
        "axis_normalization": {"sort_axis": True, "deduplicate": "first", "axis_min": None, "axis_max": None},
        "smoothing": {"method": "savgol", "window_length": 11, "polyorder": 3},
        "baseline": {"method": "rolling_minimum", "window_length": 31, "smoothing_window": 9},
        "peak_detection": {"method": "scipy_find_peaks", "prominence": 0.08, "distance": 6, "width": 2, "max_peaks": 12},
        "method_context": {
            "xrd_match_metric": "peak_overlap_weighted",
            "xrd_match_tolerance_deg": 0.28,
            "xrd_match_top_n": 5,
            "xrd_match_minimum_score": 0.42,
            "xrd_match_intensity_weight": 0.35,
            "xrd_match_major_peak_fraction": 0.4,
        },
    },
    "xrd.phase_screening": {
        "axis_normalization": {"sort_axis": True, "deduplicate": "first", "axis_min": 5.0, "axis_max": 90.0},
        "smoothing": {"method": "savgol", "window_length": 15, "polyorder": 3},
        "baseline": {"method": "rolling_minimum", "window_length": 41, "smoothing_window": 9},
        "peak_detection": {"method": "scipy_find_peaks", "prominence": 0.12, "distance": 8, "width": 3, "max_peaks": 16},
        "method_context": {
            "xrd_match_metric": "peak_overlap_weighted",
            "xrd_match_tolerance_deg": 0.24,
            "xrd_match_top_n": 7,
            "xrd_match_minimum_score": 0.45,
            "xrd_match_intensity_weight": 0.4,
            "xrd_match_major_peak_fraction": 0.45,
        },
    },
}

_XRD_PLOT_DEFAULTS = {
    "show_peak_labels": True,
    "label_density_mode": "smart",
    "max_labels": 10,
    "min_label_intensity_ratio": 0.12,
    "marker_size": 8,
    "label_position_precision": 2,
    "label_intensity_precision": 0,
    "show_matched_peaks": True,
    "show_unmatched_observed": True,
    "show_unmatched_reference": True,
    "show_match_connectors": False,
    "show_match_labels": False,
    "style_preset": "color_shape",
    "only_selected_candidate": True,
    "x_range_enabled": False,
    "x_min": None,
    "x_max": None,
    "y_range_enabled": False,
    "y_min": None,
    "y_max": None,
    "log_y": False,
    "line_width": 2.0,
}

_XRD_MATCH_STYLE = {
    "matched_observed": {"color": "#22C55E", "symbol": "diamond"},
    "unmatched_observed": {"color": "#EF4444", "symbol": "x"},
    "matched_reference": {"color": "#2563EB", "symbol": "square"},
    "unmatched_reference": {"color": "#F59E0B", "symbol": "triangle-up"},
}


def _coerce_plot_bool(value, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return bool(value) if value not in (None, "") else fallback


def _coerce_plot_int(value, fallback: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = fallback
    return max(minimum, min(maximum, parsed))


def _coerce_plot_float(value, fallback: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = fallback
    return max(minimum, min(maximum, parsed))


def _coerce_optional_plot_float(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_xrd_plot_settings(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    source = payload if isinstance(payload, Mapping) else {}
    settings = dict(_XRD_PLOT_DEFAULTS)
    settings["show_peak_labels"] = _coerce_plot_bool(source.get("show_peak_labels"), settings["show_peak_labels"])
    label_density = str(source.get("label_density_mode") or settings["label_density_mode"]).strip().lower()
    settings["label_density_mode"] = label_density if label_density in {"smart", "all", "selected"} else "smart"
    settings["max_labels"] = _coerce_plot_int(source.get("max_labels"), settings["max_labels"], 1, 60)
    settings["min_label_intensity_ratio"] = _coerce_plot_float(
        source.get("min_label_intensity_ratio"),
        settings["min_label_intensity_ratio"],
        0.0,
        1.0,
    )
    settings["marker_size"] = _coerce_plot_int(source.get("marker_size"), settings["marker_size"], 4, 20)
    settings["label_position_precision"] = _coerce_plot_int(
        source.get("label_position_precision"),
        settings["label_position_precision"],
        1,
        5,
    )
    settings["label_intensity_precision"] = _coerce_plot_int(
        source.get("label_intensity_precision"),
        settings["label_intensity_precision"],
        0,
        4,
    )
    settings["show_matched_peaks"] = _coerce_plot_bool(source.get("show_matched_peaks"), settings["show_matched_peaks"])
    settings["show_unmatched_observed"] = _coerce_plot_bool(
        source.get("show_unmatched_observed"),
        settings["show_unmatched_observed"],
    )
    settings["show_unmatched_reference"] = _coerce_plot_bool(
        source.get("show_unmatched_reference"),
        settings["show_unmatched_reference"],
    )
    settings["show_match_connectors"] = _coerce_plot_bool(
        source.get("show_match_connectors"),
        settings["show_match_connectors"],
    )
    settings["show_match_labels"] = _coerce_plot_bool(source.get("show_match_labels"), settings["show_match_labels"])
    style_preset = str(source.get("style_preset") or settings["style_preset"]).strip().lower()
    settings["style_preset"] = style_preset if style_preset in {"color_shape", "color_only", "shape_only"} else "color_shape"
    settings["only_selected_candidate"] = _coerce_plot_bool(
        source.get("only_selected_candidate"),
        settings["only_selected_candidate"],
    )
    settings["x_range_enabled"] = _coerce_plot_bool(source.get("x_range_enabled"), settings["x_range_enabled"])
    settings["x_min"] = _coerce_optional_plot_float(source.get("x_min"))
    settings["x_max"] = _coerce_optional_plot_float(source.get("x_max"))
    if (
        settings["x_range_enabled"]
        and settings["x_min"] is not None
        and settings["x_max"] is not None
        and settings["x_min"] > settings["x_max"]
    ):
        settings["x_min"], settings["x_max"] = settings["x_max"], settings["x_min"]
    settings["y_range_enabled"] = _coerce_plot_bool(source.get("y_range_enabled"), settings["y_range_enabled"])
    settings["y_min"] = _coerce_optional_plot_float(source.get("y_min"))
    settings["y_max"] = _coerce_optional_plot_float(source.get("y_max"))
    if (
        settings["y_range_enabled"]
        and settings["y_min"] is not None
        and settings["y_max"] is not None
        and settings["y_min"] > settings["y_max"]
    ):
        settings["y_min"], settings["y_max"] = settings["y_max"], settings["y_min"]
    settings["log_y"] = _coerce_plot_bool(source.get("log_y"), settings["log_y"])
    settings["line_width"] = _coerce_plot_float(source.get("line_width"), float(settings["line_width"]), 0.8, 5.0)
    return settings


def _xrd_plot_settings_from_processing(processing: Mapping[str, Any] | None) -> dict[str, Any]:
    method_context = ((processing or {}).get("method_context") or {}) if isinstance(processing, Mapping) else {}
    return _normalize_xrd_plot_settings(method_context.get("xrd_plot_settings"))


def _xrd_peak_label(position: float, intensity: float, *, settings: Mapping[str, Any], lang: str) -> str:
    pos_precision = int(settings.get("label_position_precision", 2))
    intensity_precision = int(settings.get("label_intensity_precision", 0))
    angle_unit = "°" if lang == "tr" else " deg"
    return f"{position:.{pos_precision}f}{angle_unit} | I={intensity:.{intensity_precision}f}"


def _pick_peak_label_indices(peaks: list[dict[str, float]], settings: Mapping[str, Any]) -> set[int]:
    if not peaks or not bool(settings.get("show_peak_labels", True)):
        return set()

    label_mode = str(settings.get("label_density_mode") or "smart").lower()
    if label_mode == "selected":
        label_mode = "smart"

    max_labels = int(settings.get("max_labels", 10))
    if max_labels <= 0:
        return set()

    intensities = [max(float(item.get("intensity", 0.0)), 0.0) for item in peaks]
    max_intensity = max(intensities) if intensities else 0.0
    ratio_threshold = float(settings.get("min_label_intensity_ratio", 0.12))
    threshold = max_intensity * max(ratio_threshold, 0.0)

    ranked_indices = sorted(
        range(len(peaks)),
        key=lambda idx: (
            -float(peaks[idx].get("intensity", 0.0)),
            float(peaks[idx].get("position", 0.0)),
            idx,
        ),
    )
    ranked_order = {idx: order for order, idx in enumerate(ranked_indices)}
    if label_mode == "all":
        selected = set(ranked_indices[:max_labels])
    else:
        selected = {
            idx
            for idx in ranked_indices
            if float(peaks[idx].get("intensity", 0.0)) >= threshold
        }
        if len(selected) > max_labels:
            selected = set(sorted(selected, key=lambda idx: ranked_order[idx])[:max_labels])
        if not selected:
            selected = set(ranked_indices[: max(1, min(max_labels, len(ranked_indices)))])
    return selected


def _short_candidate_label(candidate_name: str | None, *, max_len: int = 20) -> str:
    text = str(candidate_name or "").strip()
    if not text:
        return "N/A"
    if len(text) <= max_len:
        return text
    return f"{text[: max_len - 1]}…"


def _xrd_candidate_display_payload(
    match_or_row: Mapping[str, Any] | None,
    reference_entry: Mapping[str, Any] | None = None,
) -> dict[str, str | None]:
    return resolve_xrd_candidate_display_payload(match_or_row, reference_entry)


def _xrd_candidate_display_variants(
    match_or_row: Mapping[str, Any] | None,
    reference_entry: Mapping[str, Any] | None = None,
) -> dict[str, str | None]:
    return resolve_xrd_candidate_display_variants(match_or_row, reference_entry)


def _xrd_candidate_display_name(
    match_or_row: Mapping[str, Any] | None,
    reference_entry: Mapping[str, Any] | None = None,
    *,
    target: str = "plain",
) -> str | None:
    return resolve_xrd_candidate_display_name(match_or_row, reference_entry, target=target)


def _xrd_visible_candidate_name(
    match_or_row: Mapping[str, Any] | None,
    reference_entry: Mapping[str, Any] | None = None,
) -> str | None:
    return _xrd_candidate_display_name(match_or_row, reference_entry, target="unicode")


def _xrd_selected_candidate_label(selected_match: Mapping[str, Any] | None) -> str:
    display_name = _xrd_visible_candidate_name(selected_match) or "N/A"
    rank = int((selected_match or {}).get("rank") or 0)
    return f"{display_name} (#{rank})" if rank > 0 else display_name


def _xrd_match_peak_label(pair: Mapping[str, Any], *, lang: str) -> str:
    try:
        delta_value = float(pair.get("delta_position"))
    except (TypeError, ValueError):
        return ""
    comparison_space = str(pair.get("comparison_space") or "two_theta").strip().lower()
    if comparison_space == "d_spacing":
        return f"Δd={delta_value:.3f} Å"
    return f"{tx('Δ2θ', 'Δ2θ')}: {delta_value:.2f}°"


def _xrd_candidate_hover_lines(selected_match: Mapping[str, Any] | None) -> list[str]:
    payload = _xrd_candidate_display_payload(selected_match)
    evidence = dict(((selected_match or {}).get("evidence") or {}))
    provider = str(
        (selected_match or {}).get("library_provider")
        or evidence.get("library_provider")
        or payload.get("library_provider")
        or ""
    ).strip()
    package = str(
        (selected_match or {}).get("library_package")
        or evidence.get("library_package")
        or payload.get("library_package")
        or ""
    ).strip()
    candidate_id = str((selected_match or {}).get("candidate_id") or payload.get("candidate_id") or "").strip()
    source_id = str(payload.get("source_id") or "").strip()
    formula = str(payload.get("formula_pretty") or payload.get("formula") or "").strip()
    raw_label = str((selected_match or {}).get("candidate_name") or "").strip()
    display_name = str(_xrd_visible_candidate_name(selected_match) or raw_label or candidate_id or source_id or "N/A").strip()
    scientific_formula = format_scientific_formula_text(formula, target="unicode") if formula else ""

    lines = [f"<b>{tx('Aday', 'Candidate')}</b>: {display_name}"]
    if scientific_formula and scientific_formula != display_name:
        lines.append(f"<b>{tx('Formül', 'Formula')}</b>: {scientific_formula}")
    if provider:
        lines.append(f"<b>{tx('Provider', 'Provider')}</b>: {provider}")
    if package:
        lines.append(f"<b>{tx('Paket', 'Package')}</b>: {package}")
    if candidate_id:
        lines.append(f"<b>{tx('Aday Kimliği', 'Candidate ID')}</b>: {candidate_id}")
    if source_id:
        lines.append(f"<b>{tx('Kaynak Kimliği', 'Source ID')}</b>: {source_id}")
    if raw_label and raw_label not in {display_name, candidate_id, source_id}:
        lines.append(f"<b>{tx('Ham Etiket', 'Raw Label')}</b>: {raw_label}")
    return lines


def _xrd_selected_candidate_caption(selected_match: Mapping[str, Any] | None, *, lang: str) -> str:
    if not selected_match:
        return ""
    payload = _xrd_candidate_display_payload(selected_match)
    provider = str((selected_match or {}).get("library_provider") or payload.get("library_provider") or "").strip() or "N/A"
    package = str((selected_match or {}).get("library_package") or payload.get("library_package") or "").strip() or "N/A"
    candidate_id = str((selected_match or {}).get("candidate_id") or payload.get("candidate_id") or "").strip() or "N/A"
    source_id = str(payload.get("source_id") or "").strip() or "N/A"
    return tx(
        "Seçili aday: {label} | Provider/Paket: {provider} / {package} | Aday ID: {candidate_id} | Kaynak ID: {source_id}",
        "Selected candidate: {label} | Provider/Package: {provider} / {package} | Candidate ID: {candidate_id} | Source ID: {source_id}",
        label=_xrd_selected_candidate_label(selected_match),
        provider=provider,
        package=package,
        candidate_id=candidate_id,
        source_id=source_id,
    )


def _reference_marker_y(value: Any, observed_max_intensity: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = 0.0
    if parsed <= 1.5:
        return max(parsed * max(observed_max_intensity, 1.0), 0.0)
    return max(parsed, 0.0)


def _xrd_match_marker_style(kind: str, settings: Mapping[str, Any]) -> dict[str, Any]:
    base = dict(_XRD_MATCH_STYLE.get(kind) or {"color": "#94A3B8", "symbol": "circle"})
    style_preset = str(settings.get("style_preset") or "color_shape").lower()
    if style_preset == "color_only":
        base["symbol"] = "circle"
    elif style_preset == "shape_only":
        base["color"] = "#CBD5E1"
    return base


def _get_xrd_datasets():
    datasets = st.session_state.get("datasets", {})
    return {
        key: ds
        for key, ds in datasets.items()
        if str(getattr(ds, "data_type", "UNKNOWN") or "UNKNOWN").upper() in {"XRD", "UNKNOWN"}
    }


def _x_axis_label(dataset, lang: str) -> str:
    axis_unit = (
        dataset.metadata.get("xrd_axis_unit")
        or (dataset.units or {}).get("temperature")
        or "degree_2theta"
    )
    if str(axis_unit).lower() in {"angstrom", "a"}:
        return "d (Å)" if lang == "tr" else "d (A)"
    return "2θ (derece)" if lang == "tr" else "2θ (degree)"


def _to_array(value):
    if isinstance(value, np.ndarray):
        return value
    if isinstance(value, list):
        try:
            return np.asarray(value, dtype=float)
        except Exception:
            return None
    return None


def _build_raw_plot(dataset_key, dataset, lang: str):
    axis = np.asarray(dataset.data["temperature"].values, dtype=float)
    raw_signal = np.asarray(dataset.data["signal"].values, dtype=float)
    return create_thermal_plot(
        axis,
        raw_signal,
        title=tx("Ham XRD - {dataset}", "Raw XRD - {dataset}", dataset=dataset_key),
        x_label=_x_axis_label(dataset, lang),
        y_label=tx("Yoğunluk", "Intensity"),
        name=tx("Ham", "Raw"),
    )


def _build_processed_plot(
    dataset_key,
    dataset,
    state,
    lang: str,
    *,
    plot_settings: Mapping[str, Any] | None = None,
    selected_match: Mapping[str, Any] | None = None,
):
    axis = np.asarray(dataset.data["temperature"].values, dtype=float)
    raw_signal = np.asarray(dataset.data["signal"].values, dtype=float)
    settings = _normalize_xrd_plot_settings(plot_settings)
    line_width = float(settings.get("line_width", 2.0))
    plot_title = tx("XRD Analizi - {dataset}", "XRD Analysis - {dataset}", dataset=dataset_key)
    fig = create_thermal_plot(
        axis,
        raw_signal,
        title=plot_title,
        x_label=_x_axis_label(dataset, lang),
        y_label=tx("Yoğunluk", "Intensity"),
        name=tx("Ham", "Raw"),
    )

    smoothed = _to_array((state or {}).get("smoothed"))
    corrected = _to_array((state or {}).get("corrected"))
    peaks = (state or {}).get("peaks") or []
    peak_x: list[float] = []
    peak_y: list[float] = []
    peak_text: list[str] = []
    subtitle: str | None = None

    if smoothed is not None and smoothed.shape[0] == axis.shape[0]:
        fig.add_trace(
            go.Scatter(
                x=axis,
                y=smoothed,
                mode="lines",
                name=tx("Yumuşatılmış", "Smoothed"),
                line=dict(color=THERMAL_COLORS[5], width=max(0.8, line_width - 0.2)),
            )
        )
    if corrected is not None and corrected.shape[0] == axis.shape[0]:
        fig.add_trace(
            go.Scatter(
                x=axis,
                y=corrected,
                mode="lines",
                name=tx("Arkaplan Düzeltilmiş", "Background Corrected"),
                line=dict(color=THERMAL_COLORS[2], width=line_width),
            )
        )
    if peaks:
        label_indices = _pick_peak_label_indices(peaks, settings)
        peak_x = [float(item.get("position", 0.0)) for item in peaks]
        peak_y = [float(item.get("intensity", 0.0)) for item in peaks]
        peak_text = [
            _xrd_peak_label(peak_x[idx], peak_y[idx], settings=settings, lang=lang) if idx in label_indices else ""
            for idx in range(len(peaks))
        ]
        fig.add_trace(
            go.Scatter(
                x=peak_x,
                y=peak_y,
                mode="markers",
                name=tx("Pikler", "Peaks"),
                marker=dict(color=THERMAL_COLORS[1], size=int(settings.get("marker_size", 8)), symbol="diamond"),
                hovertemplate="<b>2θ</b>: %{x:.4f}<br><b>Intensity</b>: %{y:.3f}<extra></extra>",
            )
        )

    if selected_match:
        evidence = dict((selected_match.get("evidence") or {}))
        matched_pairs = [item for item in (evidence.get("matched_peak_pairs") or []) if isinstance(item, Mapping)]
        unmatched_observed = [item for item in (evidence.get("unmatched_observed_peaks") or []) if isinstance(item, Mapping)]
        unmatched_reference = [item for item in (evidence.get("unmatched_reference_peaks") or []) if isinstance(item, Mapping)]
        candidate_label = _xrd_selected_candidate_label(selected_match)
        observed_max = max([float(item.get("intensity", 0.0)) for item in peaks] + [1.0])
        hover_suffix = "".join(f"<br>{line}" for line in _xrd_candidate_hover_lines(selected_match))
        subtitle = tx(
            "Seçili aday: {label}",
            "Selected candidate: {label}",
            label=_short_candidate_label(candidate_label, max_len=52),
        )

        if settings.get("show_match_connectors", True):
            for pair in matched_pairs:
                try:
                    obs_x = float(pair.get("observed_position"))
                    obs_y = float(pair.get("observed_intensity"))
                    ref_x = float(pair.get("reference_position"))
                    ref_y = _reference_marker_y(pair.get("reference_intensity"), observed_max)
                except (TypeError, ValueError):
                    continue
                fig.add_shape(
                    type="line",
                    x0=obs_x,
                    y0=obs_y,
                    x1=ref_x,
                    y1=ref_y,
                    line=dict(color="rgba(148, 163, 184, 0.55)", width=1.0, dash="dot"),
                )

        if settings.get("show_matched_peaks", True) and matched_pairs:
            matched_obs_style = _xrd_match_marker_style("matched_observed", settings)
            matched_ref_style = _xrd_match_marker_style("matched_reference", settings)
            matched_x = [float(item.get("observed_position", 0.0)) for item in matched_pairs]
            matched_y = [float(item.get("observed_intensity", 0.0)) for item in matched_pairs]
            matched_text = (
                [_xrd_match_peak_label(item, lang=lang) for item in matched_pairs]
                if settings.get("show_match_labels", True)
                else None
            )
            matched_hover = [
                (
                    f"<b>Observed 2θ</b>: {float(item.get('observed_position', 0.0)):.4f}"
                    f"<br><b>Observed Intensity</b>: {float(item.get('observed_intensity', 0.0)):.3f}"
                    f"<br><b>{tx('Δ2θ', 'Δ2θ')}</b>: {float(item.get('delta_position') or 0.0):.4f}"
                    f"{hover_suffix}"
                )
                for item in matched_pairs
            ]
            matched_ref_hover = [
                (
                    f"<b>Reference 2θ</b>: {float(item.get('reference_position', 0.0)):.4f}"
                    f"<br><b>Scaled Ref Intensity</b>: {float(_reference_marker_y(item.get('reference_intensity'), observed_max)):.3f}"
                    f"<br><b>{tx('Δ2θ', 'Δ2θ')}</b>: {float(item.get('delta_position') or 0.0):.4f}"
                    f"{hover_suffix}"
                )
                for item in matched_pairs
            ]
            fig.add_trace(
                go.Scatter(
                    x=matched_x,
                    y=matched_y,
                    mode="markers+text" if matched_text else "markers",
                    name=tx("Eşleşen Pikler", "Matched Peaks"),
                    marker=dict(
                        color=matched_obs_style["color"],
                        size=int(settings.get("marker_size", 8)) + 1,
                        symbol=matched_obs_style["symbol"],
                        line=dict(width=1, color="#052E16"),
                    ),
                    text=matched_text,
                    textposition="top center",
                    textfont=dict(size=9.5, color="#3F5E4B"),
                    hovertext=matched_hover,
                    hoverinfo="text",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=[float(item.get("reference_position", 0.0)) for item in matched_pairs],
                    y=[_reference_marker_y(item.get("reference_intensity"), observed_max) for item in matched_pairs],
                    mode="markers",
                    name=tx("Eşleşen Referans Pik", "Matched Reference Peaks"),
                    marker=dict(
                        color=matched_ref_style["color"],
                        size=int(settings.get("marker_size", 8)),
                        symbol=matched_ref_style["symbol"],
                    ),
                    hovertext=matched_ref_hover,
                    hoverinfo="text",
                )
            )

        if settings.get("show_unmatched_observed", True) and unmatched_observed:
            unmatched_obs_style = _xrd_match_marker_style("unmatched_observed", settings)
            unmatched_obs_hover = [
                (
                    f"<b>Observed 2θ</b>: {float(item.get('position', 0.0)):.4f}"
                    f"<br><b>Intensity</b>: {float(item.get('intensity', 0.0)):.3f}"
                    f"{hover_suffix}"
                )
                for item in unmatched_observed
            ]
            fig.add_trace(
                go.Scatter(
                    x=[float(item.get("position", 0.0)) for item in unmatched_observed],
                    y=[float(item.get("intensity", 0.0)) for item in unmatched_observed],
                    mode="markers",
                    name=tx("Eşleşmeyen Gözlenen Pik", "Unmatched Observed Peaks"),
                    marker=dict(
                        color=unmatched_obs_style["color"],
                        size=int(settings.get("marker_size", 8)),
                        symbol=unmatched_obs_style["symbol"],
                    ),
                    hovertext=unmatched_obs_hover,
                    hoverinfo="text",
                )
            )

        if settings.get("show_unmatched_reference", True) and unmatched_reference:
            unmatched_ref_style = _xrd_match_marker_style("unmatched_reference", settings)
            ref_y = [_reference_marker_y(item.get("intensity"), observed_max) for item in unmatched_reference]
            ref_hover = [
                (
                    f"<b>Reference 2θ</b>: {float(item.get('position', 0.0)):.4f}"
                    f"<br><b>Scaled Ref Intensity</b>: {float(y_val):.3f}"
                    f"<br><b>Major Peak</b>: {'yes' if bool(item.get('is_major')) else 'no'}"
                    f"{hover_suffix}"
                )
                for item, y_val in zip(unmatched_reference, ref_y)
            ]
            fig.add_trace(
                go.Scatter(
                    x=[float(item.get("position", 0.0)) for item in unmatched_reference],
                    y=ref_y,
                    mode="markers",
                    name=tx("Eşleşmeyen Referans Pik", "Unmatched Reference Peaks"),
                    marker=dict(
                        color=unmatched_ref_style["color"],
                        size=int(settings.get("marker_size", 8)),
                        symbol=unmatched_ref_style["symbol"],
                    ),
                    hovertext=ref_hover,
                    hoverinfo="text",
                )
            )

    if any(peak_text):
        fig.add_trace(
            go.Scatter(
                x=peak_x,
                y=peak_y,
                mode="text",
                text=peak_text,
                textposition="top center",
                textfont=dict(size=10.5, color="#475569"),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    for trace in fig.data:
        if "lines" not in str(getattr(trace, "mode", "")):
            continue
        trace.line.width = line_width

    x_min = settings.get("x_min")
    x_max = settings.get("x_max")
    if settings.get("x_range_enabled") and x_min is not None and x_max is not None:
        fig.update_xaxes(range=[float(x_min), float(x_max)])
    else:
        fig.update_xaxes(autorange=True)

    y_min = settings.get("y_min")
    y_max = settings.get("y_max")
    if settings.get("log_y"):
        fig.update_yaxes(type="log")
        if settings.get("y_range_enabled") and y_min is not None and y_max is not None:
            fig.update_yaxes(range=[np.log10(max(float(y_min), 1e-6)), np.log10(max(float(y_max), 1e-6))])
    else:
        fig.update_yaxes(type="linear")
        if settings.get("y_range_enabled") and y_min is not None and y_max is not None:
            fig.update_yaxes(range=[float(y_min), float(y_max)])

    apply_professional_plot_theme(
        fig,
        title=plot_title,
        subtitle=subtitle,
        legend_mode="compact" if selected_match else "auto",
    )
    return fig


def _merge_with_defaults(existing, defaults):
    payload = dict(defaults or {})
    if isinstance(existing, dict):
        payload.update(existing)
    return payload


def _seed_xrd_processing_defaults(processing, workflow_template_id: str, dataset):
    defaults = _XRD_TEMPLATE_DEFAULTS.get(workflow_template_id, _XRD_TEMPLATE_DEFAULTS["xrd.general"])
    seeded = ensure_processing_payload(processing, analysis_type="XRD")
    for section_name in ("axis_normalization", "smoothing", "baseline", "peak_detection"):
        current = ((seeded.get("signal_pipeline") or {}).get(section_name) if section_name != "peak_detection" else (seeded.get("analysis_steps") or {}).get(section_name))
        merged = _merge_with_defaults(current, defaults.get(section_name))
        seeded = update_processing_step(seeded, section_name, merged, analysis_type="XRD")

    context_defaults = dict(defaults.get("method_context") or {})
    context_defaults["xrd_axis_role"] = dataset.metadata.get("xrd_axis_role") or "two_theta"
    context_defaults["xrd_axis_unit"] = dataset.metadata.get("xrd_axis_unit") or (dataset.units or {}).get("temperature") or "degree_2theta"
    context_defaults["xrd_wavelength_angstrom"] = dataset.metadata.get("xrd_wavelength_angstrom")
    seeded = update_method_context(seeded, _merge_with_defaults((seeded.get("method_context") or {}), context_defaults), analysis_type="XRD")
    return seeded


def _xrd_axis_review_required(dataset, processing) -> bool:
    method_context = ((processing or {}).get("method_context") or {}) if isinstance(processing, Mapping) else {}
    if method_context.get("xrd_axis_mapping_review_required") is not None:
        return bool(method_context.get("xrd_axis_mapping_review_required"))
    return bool((getattr(dataset, "metadata", {}) or {}).get("xrd_axis_mapping_review_required"))


def _xrd_current_wavelength(dataset, processing) -> float | None:
    method_context = ((processing or {}).get("method_context") or {}) if isinstance(processing, Mapping) else {}
    raw_value = method_context.get("xrd_wavelength_angstrom")
    if raw_value in (None, ""):
        raw_value = (getattr(dataset, "metadata", {}) or {}).get("xrd_wavelength_angstrom")
    try:
        if raw_value in (None, ""):
            return None
        return float(raw_value)
    except (TypeError, ValueError):
        return None


def _is_resolved_xrd_import_warning(warning: str, *, wavelength_recorded: bool) -> bool:
    token = str(warning or "").strip().lower()
    if not token:
        return False
    axis_warning = (
        "2theta/angle" in token
        or "review axis mapping" in token
        or ("xrd axis column" in token and "not explicitly labeled" in token)
        or "diffraction-angle axis" in token
    )
    wavelength_warning = (
        "xrd wavelength was not provided" in token
        or "xrd wavelength is not recorded" in token
        or "set xrd_wavelength_angstrom" in token
        or "phase-matching provenance remains incomplete" in token
    )
    return axis_warning or (wavelength_recorded and wavelength_warning)


def _apply_xrd_input_review(*, dataset, state, wavelength_angstrom: float | None) -> None:
    metadata = getattr(dataset, "metadata", {}) or {}
    units = getattr(dataset, "units", {}) or {}
    metadata["xrd_axis_role"] = "two_theta"
    metadata["xrd_axis_unit"] = "degree_2theta"
    metadata["xrd_axis_mapping_confirmed"] = True
    metadata["xrd_axis_mapping_review_required"] = False
    metadata["xrd_stable_matching_blocked"] = False
    units["temperature"] = "degree_2theta"
    if wavelength_angstrom is not None and wavelength_angstrom > 0:
        metadata["xrd_wavelength_angstrom"] = float(wavelength_angstrom)
        metadata["xrd_provenance_state"] = "complete"
        metadata["xrd_provenance_warning"] = ""
    else:
        metadata["xrd_wavelength_angstrom"] = None
        metadata["xrd_provenance_state"] = "incomplete"
        metadata["xrd_provenance_warning"] = (
            "XRD wavelength is not recorded; qualitative phase matching provenance remains incomplete."
        )
    state["processing"] = update_method_context(
        state.get("processing"),
        {
            "xrd_axis_role": metadata["xrd_axis_role"],
            "xrd_axis_unit": metadata["xrd_axis_unit"],
            "xrd_axis_mapping_review_required": False,
            "xrd_stable_matching_blocked": False,
            "xrd_wavelength_angstrom": metadata.get("xrd_wavelength_angstrom"),
            "xrd_provenance_state": metadata.get("xrd_provenance_state"),
            "xrd_provenance_warning": metadata.get("xrd_provenance_warning"),
        },
        analysis_type="XRD",
    )
    existing_warnings = [str(w) for w in (metadata.get("import_warnings") or []) if w]
    remaining_warnings = [
        warning
        for warning in existing_warnings
        if not _is_resolved_xrd_import_warning(
            warning,
            wavelength_recorded=metadata.get("xrd_wavelength_angstrom") not in (None, ""),
        )
    ]
    resolved_any_warning = len(remaining_warnings) != len(existing_warnings)
    metadata["import_warnings"] = remaining_warnings
    metadata["import_review_required"] = bool(remaining_warnings)
    import_confidence = str(metadata.get("import_confidence") or "").strip().lower()
    if resolved_any_warning and import_confidence == "review":
        metadata["import_confidence"] = "medium" if remaining_warnings else "high"
    state["processing"] = update_method_context(
        state.get("processing"),
        {
            "xrd_import_warnings_cleared": True,
            "import_confidence": metadata.get("import_confidence"),
            "import_review_required": metadata.get("import_review_required"),
            "import_warnings": list(remaining_warnings),
        },
        analysis_type="XRD",
    )


def _render_xrd_input_review_panel(*, dataset_key: str, dataset, state, lang: str) -> None:
    review_required = _xrd_axis_review_required(dataset, state.get("processing"))
    current_wavelength = _xrd_current_wavelength(dataset, state.get("processing"))
    if not review_required and current_wavelength is not None:
        return

    axis_column = (
        (getattr(dataset, "metadata", {}) or {}).get("xrd_axis_column")
        or (getattr(dataset, "original_columns", {}) or {}).get("temperature")
        or "temperature"
    )
    with st.expander(tx("XRD Girdi İncelemesi", "XRD Input Review"), expanded=review_required):
        if review_required:
            st.warning(
                tx(
                    f"`{axis_column}` kolonu 2theta/açı olarak açık etiketli değil. Kararlı XRD eşleştirmesi için bu ekseni açıkça onaylayın.",
                    f"The `{axis_column}` column is not explicitly labeled as 2theta/angle. Confirm this axis before stable XRD matching.",
                )
            )
        if current_wavelength is None:
            st.info(
                tx(
                    "XRD dalgaboyu kayıtlı değil. Eşleştirme yine çalışabilir, ancak provenance eksik kalır.",
                    "XRD wavelength is not recorded. Matching can still run, but provenance remains incomplete.",
                )
            )

        confirm_axis = st.checkbox(
            tx(
                f"`{axis_column}` kolonunun XRD 2θ / difraksiyon açısı ekseni olduğunu onaylıyorum.",
                f"I confirm that `{axis_column}` is the XRD 2theta / diffraction-angle axis.",
            ),
            value=not review_required,
            key=f"xrd_axis_review_confirm_{dataset_key}",
        )
        wavelength_value = st.number_input(
            tx("XRD Dalgaboyu (Å)", "XRD Wavelength (Å)"),
            min_value=0.0,
            value=float(current_wavelength or 1.5406),
            step=0.0001,
            format="%.4f",
            key=f"xrd_axis_review_wavelength_{dataset_key}",
        )
        if st.button(tx("XRD Girdi Onayını Uygula", "Apply XRD Input Review"), key=f"xrd_axis_review_apply_{dataset_key}"):
            if review_required and not confirm_axis:
                st.error(
                    tx(
                        "Kararlı XRD akışına devam etmek için ekseni 2theta/açı olarak onaylayın.",
                        "Confirm the axis as 2theta/angle before continuing in the stable XRD flow.",
                    )
                )
                return
            _apply_xrd_input_review(
                dataset=dataset,
                state=state,
                wavelength_angstrom=float(wavelength_value) if wavelength_value > 0 else None,
            )
            _log_event(
                tx("XRD Girdi Onayı Uygulandı", "XRD Input Review Applied"),
                tx(
                    "{axis_column} kolonu 2theta/açı ekseni olarak onaylandı.",
                    "{axis_column} was confirmed as the 2theta/angle axis.",
                    axis_column=str(axis_column),
                ),
                t("xrd.title"),
                dataset_key=dataset_key,
                parameters={
                    "axis_column": str(axis_column),
                    "wavelength_angstrom": float(wavelength_value) if wavelength_value > 0 else None,
                },
            )
            st.rerun()


def _find_xrd_record(results, dataset_key: str):
    if not isinstance(results, dict):
        return None

    direct = results.get(f"xrd_{dataset_key}")
    if isinstance(direct, dict):
        return direct

    fallbacks = []
    for record in results.values():
        if not isinstance(record, dict):
            continue
        if str(record.get("analysis_type") or "").upper() != "XRD":
            continue
        if str(record.get("dataset_key") or "") != str(dataset_key):
            continue
        provenance = record.get("provenance") or {}
        timestamp = provenance.get("timestamp_utc") or provenance.get("created_at") or ""
        fallbacks.append((str(timestamp), record))

    if not fallbacks:
        return None

    fallbacks.sort(key=lambda item: item[0])
    return fallbacks[-1][1]


def _resolve_xrd_matches(current_state, record):
    state_matches = (current_state or {}).get("matches") or (current_state or {}).get("phase_candidates") or []
    if state_matches:
        return list(state_matches)

    rows = (record or {}).get("rows") or []
    normalized = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "rank": row.get("rank") or index,
                "candidate_id": row.get("candidate_id"),
                "candidate_name": row.get("candidate_name"),
                "display_name": row.get("display_name"),
                "phase_name": row.get("phase_name"),
                "formula_pretty": row.get("formula_pretty"),
                "formula": row.get("formula"),
                "source_id": row.get("source_id"),
                "normalized_score": row.get("normalized_score"),
                "confidence_band": row.get("confidence_band"),
                "library_provider": row.get("library_provider"),
                "library_package": row.get("library_package"),
                "library_version": row.get("library_version"),
                "evidence": row.get("evidence") or {},
            }
        )
    return normalized


def _xrd_best_candidate_name(summary: dict | None, matches: list[dict] | None) -> str | None:
    summary = summary or {}
    candidate_name = _xrd_visible_candidate_name(summary)
    if candidate_name not in (None, ""):
        return str(candidate_name)
    top = matches[0] if matches else None
    if isinstance(top, dict):
        return str(_xrd_visible_candidate_name(top) or top.get("candidate_name") or top.get("candidate_id") or "") or None
    return None


def _xrd_best_candidate_score(summary: dict | None, matches: list[dict] | None) -> float | None:
    summary = summary or {}
    value = summary.get("top_candidate_score")
    if value in (None, ""):
        top = matches[0] if matches else None
        value = (top or {}).get("normalized_score") if isinstance(top, dict) else None
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _xrd_figure_key(dataset_key: str) -> str:
    return f"XRD Analysis - {dataset_key}"


def _xrd_control_key(dataset_key: str, slot: str, state: dict) -> str:
    return f"xrd_{slot}_{dataset_key}_{state.get('_render_revision', 0)}"


def _xrd_control_value(dataset_key: str, slot: str, state: dict, fallback):
    return st.session_state.get(_xrd_control_key(dataset_key, slot, state), fallback)


def _sync_xrd_processing_from_controls(processing, *, dataset_key: str, dataset, state: dict):
    payload = ensure_processing_payload(processing, analysis_type="XRD")
    signal_pipeline = payload.get("signal_pipeline") or {}
    analysis_steps = payload.get("analysis_steps") or {}
    method_context = payload.get("method_context") or {}

    axis_defaults = signal_pipeline.get("axis_normalization") or {}
    smooth_defaults = signal_pipeline.get("smoothing") or {}
    baseline_defaults = signal_pipeline.get("baseline") or {}
    peak_defaults = analysis_steps.get("peak_detection") or {}
    plot_defaults = _normalize_xrd_plot_settings(method_context.get("xrd_plot_settings"))

    default_axis_min = float(dataset.data["temperature"].min())
    default_axis_max = float(dataset.data["temperature"].max())
    restrict_range = bool(
        _xrd_control_value(
            dataset_key,
            "restrict",
            state,
            axis_defaults.get("axis_min") not in (None, "") or axis_defaults.get("axis_max") not in (None, ""),
        )
    )
    axis_min = float(
        _xrd_control_value(
            dataset_key,
            "axis_min",
            state,
            axis_defaults.get("axis_min") if axis_defaults.get("axis_min") is not None else default_axis_min,
        )
    )
    axis_max = float(
        _xrd_control_value(
            dataset_key,
            "axis_max",
            state,
            axis_defaults.get("axis_max") if axis_defaults.get("axis_max") is not None else default_axis_max,
        )
    )

    payload = update_processing_step(
        payload,
        "axis_normalization",
        {
            "sort_axis": True,
            "deduplicate": "first",
            "axis_min": axis_min if restrict_range else None,
            "axis_max": axis_max if restrict_range else None,
        },
        analysis_type="XRD",
    )
    payload = update_processing_step(
        payload,
        "smoothing",
        {
            "method": str(_xrd_control_value(dataset_key, "smooth_method", state, smooth_defaults.get("method") or "savgol")),
            "window_length": int(_xrd_control_value(dataset_key, "smooth_window", state, smooth_defaults.get("window_length") or 11)),
            "polyorder": int(_xrd_control_value(dataset_key, "smooth_poly", state, smooth_defaults.get("polyorder") or 3)),
        },
        analysis_type="XRD",
    )
    payload = update_processing_step(
        payload,
        "baseline",
        {
            "method": str(_xrd_control_value(dataset_key, "baseline_method", state, baseline_defaults.get("method") or "rolling_minimum")),
            "window_length": int(_xrd_control_value(dataset_key, "baseline_window", state, baseline_defaults.get("window_length") or 31)),
            "smoothing_window": int(_xrd_control_value(dataset_key, "baseline_smooth", state, baseline_defaults.get("smoothing_window") or 9)),
        },
        analysis_type="XRD",
    )
    payload = update_processing_step(
        payload,
        "peak_detection",
        {
            "method": "scipy_find_peaks",
            "prominence": float(_xrd_control_value(dataset_key, "peak_prom", state, peak_defaults.get("prominence") or 0.08)),
            "distance": int(_xrd_control_value(dataset_key, "peak_dist", state, peak_defaults.get("distance") or 6)),
            "width": int(_xrd_control_value(dataset_key, "peak_width", state, peak_defaults.get("width") or 2)),
            "max_peaks": int(_xrd_control_value(dataset_key, "peak_max", state, peak_defaults.get("max_peaks") or 12)),
        },
        analysis_type="XRD",
    )
    payload = update_method_context(
        payload,
        {
            "xrd_match_metric": "peak_overlap_weighted",
            "xrd_match_tolerance_deg": float(_xrd_control_value(dataset_key, "match_tol", state, method_context.get("xrd_match_tolerance_deg") or 0.28)),
            "xrd_match_top_n": int(_xrd_control_value(dataset_key, "match_topn", state, method_context.get("xrd_match_top_n") or 5)),
            "xrd_match_minimum_score": float(_xrd_control_value(dataset_key, "match_min", state, method_context.get("xrd_match_minimum_score") or 0.42)),
            "xrd_match_intensity_weight": float(_xrd_control_value(dataset_key, "match_iw", state, method_context.get("xrd_match_intensity_weight") or 0.35)),
            "xrd_match_major_peak_fraction": float(_xrd_control_value(dataset_key, "match_major", state, method_context.get("xrd_match_major_peak_fraction") or 0.4)),
            "xrd_plot_settings": _normalize_xrd_plot_settings(
                {
                    "show_peak_labels": _xrd_control_value(dataset_key, "plot_peak_labels", state, plot_defaults["show_peak_labels"]),
                    "label_density_mode": _xrd_control_value(dataset_key, "plot_label_density", state, plot_defaults["label_density_mode"]),
                    "max_labels": _xrd_control_value(dataset_key, "plot_max_labels", state, plot_defaults["max_labels"]),
                    "min_label_intensity_ratio": _xrd_control_value(
                        dataset_key,
                        "plot_label_min_ratio",
                        state,
                        plot_defaults["min_label_intensity_ratio"],
                    ),
                    "marker_size": _xrd_control_value(dataset_key, "plot_marker_size", state, plot_defaults["marker_size"]),
                    "label_position_precision": _xrd_control_value(
                        dataset_key,
                        "plot_pos_precision",
                        state,
                        plot_defaults["label_position_precision"],
                    ),
                    "label_intensity_precision": _xrd_control_value(
                        dataset_key,
                        "plot_int_precision",
                        state,
                        plot_defaults["label_intensity_precision"],
                    ),
                    "show_matched_peaks": _xrd_control_value(
                        dataset_key,
                        "plot_show_matched",
                        state,
                        plot_defaults["show_matched_peaks"],
                    ),
                    "show_unmatched_observed": _xrd_control_value(
                        dataset_key,
                        "plot_show_unmatched_obs",
                        state,
                        plot_defaults["show_unmatched_observed"],
                    ),
                    "show_unmatched_reference": _xrd_control_value(
                        dataset_key,
                        "plot_show_unmatched_ref",
                        state,
                        plot_defaults["show_unmatched_reference"],
                    ),
                    "show_match_connectors": _xrd_control_value(
                        dataset_key,
                        "plot_show_connectors",
                        state,
                        plot_defaults["show_match_connectors"],
                    ),
                    "show_match_labels": _xrd_control_value(
                        dataset_key,
                        "plot_show_match_labels",
                        state,
                        plot_defaults["show_match_labels"],
                    ),
                    "style_preset": _xrd_control_value(dataset_key, "plot_style", state, plot_defaults["style_preset"]),
                    "only_selected_candidate": True,
                    "x_range_enabled": _xrd_control_value(dataset_key, "plot_x_range", state, plot_defaults["x_range_enabled"]),
                    "x_min": _xrd_control_value(dataset_key, "plot_x_min", state, plot_defaults["x_min"]),
                    "x_max": _xrd_control_value(dataset_key, "plot_x_max", state, plot_defaults["x_max"]),
                    "y_range_enabled": _xrd_control_value(dataset_key, "plot_y_range", state, plot_defaults["y_range_enabled"]),
                    "y_min": _xrd_control_value(dataset_key, "plot_y_min", state, plot_defaults["y_min"]),
                    "y_max": _xrd_control_value(dataset_key, "plot_y_max", state, plot_defaults["y_max"]),
                    "log_y": _xrd_control_value(dataset_key, "plot_log_y", state, plot_defaults["log_y"]),
                    "line_width": _xrd_control_value(dataset_key, "plot_line_width", state, plot_defaults["line_width"]),
                }
            ),
        },
        analysis_type="XRD",
    )
    return payload


def _render_xrd_plot_settings_panel(dataset_key: str, state: dict, settings: Mapping[str, Any], dataset=None) -> dict[str, Any]:
    with st.expander(tx("Grafik Ayarları", "Plot Settings"), expanded=False):
        if st.button(
            tx("Autoscale Sıfırla", "Reset Autoscale"),
            key=_xrd_control_key(dataset_key, "plot_reset_autoscale", state),
        ):
            st.session_state[_xrd_control_key(dataset_key, "plot_x_range", state)] = False
            st.session_state[_xrd_control_key(dataset_key, "plot_y_range", state)] = False
            st.session_state.pop(_xrd_control_key(dataset_key, "plot_x_min", state), None)
            st.session_state.pop(_xrd_control_key(dataset_key, "plot_x_max", state), None)
            st.session_state.pop(_xrd_control_key(dataset_key, "plot_y_min", state), None)
            st.session_state.pop(_xrd_control_key(dataset_key, "plot_y_max", state), None)
            st.rerun()

        left, right = st.columns(2)
        with left:
            show_peak_labels = st.checkbox(
                tx("Pik etiketlerini göster (2θ + I)", "Show peak labels (2θ + I)"),
                value=bool(settings.get("show_peak_labels", True)),
                key=_xrd_control_key(dataset_key, "plot_peak_labels", state),
            )
            label_density_mode = st.selectbox(
                tx("Etiket yoğunluğu", "Label density"),
                ["smart", "all", "selected"],
                index=["smart", "all", "selected"].index(str(settings.get("label_density_mode") or "smart")),
                format_func=lambda item: {
                    "smart": tx("Akıllı filtre", "Smart filter"),
                    "all": tx("Hepsini göster", "Show all"),
                    "selected": tx("Seçili odak", "Selected focus"),
                }.get(item, item),
                key=_xrd_control_key(dataset_key, "plot_label_density", state),
            )
            max_labels = st.slider(
                tx("Maks etiket sayısı", "Max label count"),
                1,
                60,
                int(settings.get("max_labels", 10)),
                key=_xrd_control_key(dataset_key, "plot_max_labels", state),
            )
            min_label_ratio = st.slider(
                tx("Etiket min yoğunluk oranı", "Label min intensity ratio"),
                0.0,
                1.0,
                float(settings.get("min_label_intensity_ratio", 0.12)),
                0.01,
                key=_xrd_control_key(dataset_key, "plot_label_min_ratio", state),
            )
            marker_size = st.slider(
                tx("Marker boyutu", "Marker size"),
                4,
                20,
                int(settings.get("marker_size", 8)),
                key=_xrd_control_key(dataset_key, "plot_marker_size", state),
            )
            x_range_enabled = st.checkbox(
                tx("X aralığını sabitle", "Lock X range"),
                value=bool(settings.get("x_range_enabled", False)),
                key=_xrd_control_key(dataset_key, "plot_x_range", state),
            )
            fallback_x_min = 0.0
            fallback_x_max = 100.0
            try:
                if dataset is not None:
                    axis = np.asarray(dataset.data["temperature"].values, dtype=float)
                    if axis.size:
                        fallback_x_min = float(np.nanmin(axis))
                        fallback_x_max = float(np.nanmax(axis))
            except Exception:
                pass
            x_min = st.number_input(
                tx("X min", "X min"),
                value=float(settings.get("x_min") if settings.get("x_min") is not None else fallback_x_min),
                key=_xrd_control_key(dataset_key, "plot_x_min", state),
                disabled=not x_range_enabled,
            )
            x_max = st.number_input(
                tx("X max", "X max"),
                value=float(settings.get("x_max") if settings.get("x_max") is not None else fallback_x_max),
                key=_xrd_control_key(dataset_key, "plot_x_max", state),
                disabled=not x_range_enabled,
            )
            line_width = st.slider(
                tx("Çizgi kalınlığı", "Line width"),
                0.8,
                5.0,
                float(settings.get("line_width", 2.0)),
                0.1,
                key=_xrd_control_key(dataset_key, "plot_line_width", state),
            )
        with right:
            position_precision = st.slider(
                tx("2θ hassasiyet", "2θ precision"),
                1,
                5,
                int(settings.get("label_position_precision", 2)),
                key=_xrd_control_key(dataset_key, "plot_pos_precision", state),
            )
            intensity_precision = st.slider(
                tx("Yoğunluk hassasiyet", "Intensity precision"),
                0,
                4,
                int(settings.get("label_intensity_precision", 0)),
                key=_xrd_control_key(dataset_key, "plot_int_precision", state),
            )
            style_preset = st.selectbox(
                tx("Renk/şekil kodlaması", "Color/shape encoding"),
                ["color_shape", "color_only", "shape_only"],
                index=["color_shape", "color_only", "shape_only"].index(str(settings.get("style_preset") or "color_shape")),
                format_func=lambda item: {
                    "color_shape": tx("Renk + Şekil", "Color + Shape"),
                    "color_only": tx("Sadece Renk", "Color only"),
                    "shape_only": tx("Sadece Şekil", "Shape only"),
                }.get(item, item),
                key=_xrd_control_key(dataset_key, "plot_style", state),
            )
            show_matched = st.checkbox(
                tx("Eşleşen pikleri göster", "Show matched peaks"),
                value=bool(settings.get("show_matched_peaks", True)),
                key=_xrd_control_key(dataset_key, "plot_show_matched", state),
            )
            show_match_labels = st.checkbox(
                tx("Kısa eşleşme etiketleri", "Short match labels"),
                value=bool(settings.get("show_match_labels", True)),
                key=_xrd_control_key(dataset_key, "plot_show_match_labels", state),
            )
            show_unmatched_obs = st.checkbox(
                tx("Eşleşmeyen gözlenen pikleri göster", "Show unmatched observed peaks"),
                value=bool(settings.get("show_unmatched_observed", True)),
                key=_xrd_control_key(dataset_key, "plot_show_unmatched_obs", state),
            )
            show_unmatched_ref = st.checkbox(
                tx("Eşleşmeyen referans pikleri göster", "Show unmatched reference peaks"),
                value=bool(settings.get("show_unmatched_reference", True)),
                key=_xrd_control_key(dataset_key, "plot_show_unmatched_ref", state),
            )
            show_connectors = st.checkbox(
                tx("Observed-Reference bağlantı çizgileri", "Observed-Reference connector lines"),
                value=bool(settings.get("show_match_connectors", True)),
                key=_xrd_control_key(dataset_key, "plot_show_connectors", state),
            )
            y_range_enabled = st.checkbox(
                tx("Y aralığını sabitle", "Lock Y range"),
                value=bool(settings.get("y_range_enabled", False)),
                key=_xrd_control_key(dataset_key, "plot_y_range", state),
            )
            fallback_y_min = 0.0
            fallback_y_max = 10000.0
            try:
                if dataset is not None:
                    signal = np.asarray(dataset.data["signal"].values, dtype=float)
                    if signal.size:
                        fallback_y_min = float(np.nanmin(signal))
                        fallback_y_max = float(np.nanmax(signal))
            except Exception:
                pass
            y_min = st.number_input(
                tx("Y min", "Y min"),
                value=float(settings.get("y_min") if settings.get("y_min") is not None else fallback_y_min),
                key=_xrd_control_key(dataset_key, "plot_y_min", state),
                disabled=not y_range_enabled,
            )
            y_max = st.number_input(
                tx("Y max", "Y max"),
                value=float(settings.get("y_max") if settings.get("y_max") is not None else fallback_y_max),
                key=_xrd_control_key(dataset_key, "plot_y_max", state),
                disabled=not y_range_enabled,
            )
            log_y = st.checkbox(
                tx("Log Y ölçeği", "Log Y scale"),
                value=bool(settings.get("log_y", False)),
                key=_xrd_control_key(dataset_key, "plot_log_y", state),
            )

    return _normalize_xrd_plot_settings(
        {
            "show_peak_labels": show_peak_labels,
            "label_density_mode": label_density_mode,
            "max_labels": max_labels,
            "min_label_intensity_ratio": min_label_ratio,
            "marker_size": marker_size,
            "label_position_precision": position_precision,
            "label_intensity_precision": intensity_precision,
            "show_matched_peaks": show_matched,
            "show_unmatched_observed": show_unmatched_obs,
            "show_unmatched_reference": show_unmatched_ref,
            "show_match_connectors": show_connectors,
            "show_match_labels": show_match_labels,
            "style_preset": style_preset,
            "only_selected_candidate": True,
            "x_range_enabled": x_range_enabled,
            "x_min": x_min,
            "x_max": x_max,
            "y_range_enabled": y_range_enabled,
            "y_min": y_min,
            "y_max": y_max,
            "log_y": log_y,
            "line_width": line_width,
        }
    )


def _slug_token(value: Any, fallback: str = "snapshot") -> str:
    raw = str(value or "").strip()
    if not raw:
        return fallback
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in raw)
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    if not cleaned:
        return fallback
    return cleaned[:42]


def _xrd_snapshot_figure_key(dataset_key: str, selected_match: Mapping[str, Any] | None) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rank = int((selected_match or {}).get("rank") or 0)
    candidate = _slug_token(_xrd_candidate_display_name(selected_match) or (selected_match or {}).get("candidate_id") or "candidate")
    return f"XRD Snapshot - {dataset_key} - {timestamp} - r{rank}_{candidate}"


def _upsert_xrd_record_figure_artifacts(
    record: dict[str, Any],
    *,
    figure_key: str,
    snapshot_metadata: Mapping[str, Any] | None = None,
    set_primary: bool = False,
    max_snapshots: int = 10,
) -> dict[str, Any]:
    updated_record = dict(record or {})
    artifacts = dict(updated_record.get("artifacts") or {})

    figure_keys = [str(item) for item in (artifacts.get("figure_keys") or []) if item not in (None, "")]
    if figure_key not in figure_keys:
        figure_keys.append(figure_key)
    artifacts["figure_keys"] = figure_keys

    if snapshot_metadata is not None:
        snapshots = [dict(item) for item in (artifacts.get("figure_snapshots") or []) if isinstance(item, Mapping)]
        snapshots = [item for item in snapshots if str(item.get("figure_key") or "") != figure_key]
        snapshots.append(dict(snapshot_metadata))
        if len(snapshots) > max_snapshots:
            snapshots = snapshots[-max_snapshots:]
        artifacts["figure_snapshots"] = snapshots

    if set_primary:
        artifacts["report_figure_key"] = figure_key
    elif artifacts.get("report_figure_key") in (None, ""):
        artifacts["report_figure_key"] = figure_key

    updated_record["artifacts"] = artifacts
    return updated_record


def _attach_xrd_report_figure(record, *, dataset_key: str, dataset, state, lang: str, figures_store):
    figure_key = _xrd_figure_key(dataset_key)
    plot_settings = _xrd_plot_settings_from_processing((state or {}).get("processing") or {})
    figures_store[figure_key] = fig_to_bytes(
        _build_processed_plot(
            dataset_key,
            dataset,
            state,
            lang,
            plot_settings=plot_settings,
        )
    )

    updated_record = _upsert_xrd_record_figure_artifacts(
        dict(record or {}),
        figure_key=figure_key,
        snapshot_metadata={
            "figure_key": figure_key,
            "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source_tab": "result_summary",
            "snapshot_type": "default_result_figure",
        },
        set_primary=False,
    )
    return updated_record, figure_key


def _save_xrd_result_to_session(record, *, dataset_key: str, dataset, state, lang: str):
    figures_store = st.session_state.setdefault("figures", {})
    updated_record, figure_key = _attach_xrd_report_figure(
        record,
        dataset_key=dataset_key,
        dataset=dataset,
        state=state,
        lang=lang,
        figures_store=figures_store,
    )
    st.session_state.setdefault("results", {})[updated_record["id"]] = updated_record
    return updated_record, figure_key


def _save_xrd_graph_snapshot_to_session(
    *,
    record: dict[str, Any],
    dataset_key: str,
    dataset,
    state: dict[str, Any],
    lang: str,
    selected_match: Mapping[str, Any] | None,
    plot_settings: Mapping[str, Any],
    set_primary: bool,
) -> tuple[dict[str, Any], str]:
    figure_key = _xrd_snapshot_figure_key(dataset_key, selected_match)
    fig = _build_processed_plot(
        dataset_key,
        dataset,
        state,
        lang,
        plot_settings=plot_settings,
        selected_match=selected_match,
    )

    figures_store = st.session_state.setdefault("figures", {})
    figures_store[figure_key] = fig_to_bytes(fig, format="png")
    figure_outputs = st.session_state.setdefault("figure_outputs", {})
    outputs = {"png": figures_store[figure_key]}
    try:
        outputs["svg"] = fig_to_bytes(fig, format="svg")
    except Exception:
        pass
    figure_outputs[figure_key] = outputs

    existing_snapshot_keys = {
        str(item.get("figure_key"))
        for item in (((record or {}).get("artifacts") or {}).get("figure_snapshots") or [])
        if isinstance(item, Mapping) and item.get("figure_key")
    }

    metadata = {
        "figure_key": figure_key,
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_tab": "phase_candidates",
        "selected_candidate_id": (selected_match or {}).get("candidate_id"),
        "selected_candidate_name": (selected_match or {}).get("candidate_name"),
        "selected_candidate_display_name": _xrd_candidate_display_name(selected_match),
        "selected_candidate_display_name_unicode": _xrd_visible_candidate_name(selected_match),
        "selected_candidate_rank": (selected_match or {}).get("rank"),
        "plot_settings": dict(plot_settings or {}),
        "layer_flags": {
            "show_matched_peaks": bool((plot_settings or {}).get("show_matched_peaks", True)),
            "show_unmatched_observed": bool((plot_settings or {}).get("show_unmatched_observed", True)),
            "show_unmatched_reference": bool((plot_settings or {}).get("show_unmatched_reference", True)),
            "show_match_connectors": bool((plot_settings or {}).get("show_match_connectors", True)),
            "show_peak_labels": bool((plot_settings or {}).get("show_peak_labels", True)),
        },
    }

    updated_record = _upsert_xrd_record_figure_artifacts(
        dict(record or {}),
        figure_key=figure_key,
        snapshot_metadata=metadata,
        set_primary=set_primary,
    )
    kept_snapshot_keys = {
        str(item.get("figure_key"))
        for item in ((updated_record.get("artifacts") or {}).get("figure_snapshots") or [])
        if isinstance(item, Mapping) and item.get("figure_key")
    }
    for stale_key in sorted(existing_snapshot_keys - kept_snapshot_keys):
        figures_store.pop(stale_key, None)
        figure_outputs.pop(stale_key, None)
    st.session_state.setdefault("results", {})[updated_record["id"]] = updated_record
    return updated_record, figure_key


def render():
    lang = st.session_state.get("ui_language", "tr")
    render_page_header(t("xrd.title"), t("xrd.caption"), badge=t("xrd.hero_badge"))
    st.info(
        tx(
            "Kararlı XRD akışı axis normalizasyonu, pik çıkarımı ve nitel faz adayı eşleşmesini deterministik parametrelerle çalıştırır.",
            "Stable XRD flow executes axis normalization, peak extraction, and qualitative phase-candidate matching with deterministic parameters.",
        )
    )

    xrd_datasets = _get_xrd_datasets()
    if not xrd_datasets:
        st.warning(
            tx(
                "Henüz XRD veri seti yüklenmedi. Veri yüklemek için **Veri Al** sayfasına gidin.",
                "No XRD datasets loaded. Go to **Import Runs** to load a dataset.",
            )
        )
        return

    selected_key = st.selectbox(
        tx("Veri Seti Seç", "Select Dataset"),
        list(xrd_datasets.keys()),
        key="xrd_dataset_select",
    )
    dataset = xrd_datasets[selected_key]
    state_key = analysis_state_key("XRD", selected_key)
    state = st.session_state.setdefault(state_key, {})
    state["processing"] = ensure_processing_payload(state.get("processing"), analysis_type="XRD")

    templates = get_workflow_templates("XRD")
    template_labels = {entry["id"]: entry["label"] for entry in templates}
    template_ids = list(template_labels)
    if not template_ids:
        st.error(tx("XRD iş akışı şablonu bulunamadı.", "No XRD workflow templates were found."))
        return

    current_template = state["processing"].get("workflow_template_id")
    seed_pending_workflow_template(f"xrd_template_{selected_key}")
    default_index = template_ids.index(current_template) if current_template in template_ids else 0
    workflow_template_id = st.selectbox(
        tx("İş Akışı Şablonu", "Workflow Template"),
        template_ids,
        format_func=lambda template_id: template_labels.get(template_id, template_id),
        index=default_index,
        key=f"xrd_template_{selected_key}",
    )
    state["processing"] = set_workflow_template(
        state.get("processing"),
        workflow_template_id,
        analysis_type="XRD",
        workflow_template_label=template_labels.get(workflow_template_id),
    )
    state["processing"] = _seed_xrd_processing_defaults(state.get("processing"), workflow_template_id, dataset)
    state["processing"] = _sync_xrd_processing_from_controls(
        state.get("processing"),
        dataset_key=selected_key,
        dataset=dataset,
        state=state,
    )
    render_processing_preset_panel(
        analysis_type="XRD",
        state=state,
        key_prefix=f"xrd_presets_{selected_key}",
        workflow_select_key=f"xrd_template_{selected_key}",
    )

    _render_xrd_input_review_panel(
        dataset_key=selected_key,
        dataset=dataset,
        state=state,
        lang=lang,
    )
    dataset_validation = validate_thermal_dataset(dataset, analysis_type="XRD", processing=state.get("processing"))
    if dataset_validation["status"] == "fail":
        st.error(
            tx(
                "Veri seti kararlı XRD iş akışına alınmadı: {issues}",
                "Dataset is blocked from the stable XRD workflow: {issues}",
                issues="; ".join(dataset_validation["issues"]),
            )
        )
        return
    if dataset_validation["warnings"]:
        with st.expander(tx("Veri Doğrulama", "Dataset Validation"), expanded=False):
            for warning in dataset_validation["warnings"]:
                st.warning(warning)

    tab_raw, tab_pipeline, tab_peaks, tab_matches, tab_results = st.tabs(
        [
            tx("Ham Veri", "Raw Data"),
            tx("İşlem Parametreleri", "Processing Parameters"),
            tx("Pikler", "Peaks"),
            tx("Faz Adayları", "Phase Candidates"),
            tx("Sonuç Özeti", "Results Summary"),
        ]
    )

    with tab_raw:
        st.plotly_chart(
            _build_raw_plot(selected_key, dataset, lang),
            width="stretch",
            config=PLOTLY_CONFIG,
            key=f"xrd_raw_{selected_key}",
        )
        c1, c2, c3 = st.columns(3)
        c1.metric(tx("Nokta", "Points"), str(len(dataset.data)))
        c2.metric(
            tx("2θ Min", "2θ Min"),
            f"{float(dataset.data['temperature'].min()):.3f}",
        )
        c3.metric(
            tx("2θ Max", "2θ Max"),
            f"{float(dataset.data['temperature'].max()):.3f}",
        )

    with tab_pipeline:
        defaults_signal = state["processing"].get("signal_pipeline") or {}
        defaults_steps = state["processing"].get("analysis_steps") or {}
        defaults_context = state["processing"].get("method_context") or {}
        axis_defaults = defaults_signal.get("axis_normalization") or {}
        smooth_defaults = defaults_signal.get("smoothing") or {}
        baseline_defaults = defaults_signal.get("baseline") or {}
        peak_defaults = defaults_steps.get("peak_detection") or {}

        controls_col, preview_col = st.columns([1, 2])
        with controls_col:
            restrict_range = st.checkbox(
                tx("2θ aralığını sınırla", "Restrict 2θ range"),
                value=axis_defaults.get("axis_min") not in (None, "") or axis_defaults.get("axis_max") not in (None, ""),
                key=_xrd_control_key(selected_key, "restrict", state),
            )
            default_axis_min = float(dataset.data["temperature"].min())
            default_axis_max = float(dataset.data["temperature"].max())
            axis_min = st.number_input(
                tx("2θ minimum", "2θ minimum"),
                value=float(axis_defaults.get("axis_min") if axis_defaults.get("axis_min") is not None else default_axis_min),
                key=_xrd_control_key(selected_key, "axis_min", state),
            )
            axis_max = st.number_input(
                tx("2θ maksimum", "2θ maximum"),
                value=float(axis_defaults.get("axis_max") if axis_defaults.get("axis_max") is not None else default_axis_max),
                key=_xrd_control_key(selected_key, "axis_max", state),
            )

            smooth_method = st.selectbox(
                tx("Yumuşatma", "Smoothing"),
                ["savgol", "moving_average", "none"],
                index=["savgol", "moving_average", "none"].index(
                    str(smooth_defaults.get("method") or "savgol").lower()
                )
                if str(smooth_defaults.get("method") or "savgol").lower() in {"savgol", "moving_average", "none"}
                else 0,
                key=_xrd_control_key(selected_key, "smooth_method", state),
            )
            smooth_window = st.slider(
                tx("Yumuşatma Penceresi", "Smoothing Window"),
                3,
                101,
                int(smooth_defaults.get("window_length") or 11),
                step=2,
                key=_xrd_control_key(selected_key, "smooth_window", state),
            )
            smooth_poly = st.slider(
                tx("Polinom Derecesi", "Polynomial Order"),
                1,
                9,
                int(smooth_defaults.get("polyorder") or 3),
                key=_xrd_control_key(selected_key, "smooth_poly", state),
            )

            baseline_method = st.selectbox(
                tx("Arkaplan Yöntemi", "Baseline Method"),
                ["rolling_minimum", "linear", "none"],
                index=["rolling_minimum", "linear", "none"].index(
                    str(baseline_defaults.get("method") or "rolling_minimum").lower()
                )
                if str(baseline_defaults.get("method") or "rolling_minimum").lower() in {"rolling_minimum", "linear", "none"}
                else 0,
                key=_xrd_control_key(selected_key, "baseline_method", state),
            )
            baseline_window = st.slider(
                tx("Arkaplan Penceresi", "Baseline Window"),
                3,
                201,
                int(baseline_defaults.get("window_length") or 31),
                step=2,
                key=_xrd_control_key(selected_key, "baseline_window", state),
            )
            baseline_smooth = st.slider(
                tx("Arkaplan Yumuşatma", "Baseline Smoothing"),
                3,
                81,
                int(baseline_defaults.get("smoothing_window") or 9),
                step=2,
                key=_xrd_control_key(selected_key, "baseline_smooth", state),
            )

            peak_prominence = st.number_input(
                tx("Pik Belirginliği", "Peak Prominence"),
                min_value=0.001,
                max_value=10.0,
                value=float(peak_defaults.get("prominence") or 0.08),
                format="%.3f",
                key=_xrd_control_key(selected_key, "peak_prom", state),
            )
            peak_distance = st.number_input(
                tx("Pik Mesafesi", "Peak Distance"),
                min_value=1,
                max_value=200,
                value=int(peak_defaults.get("distance") or 6),
                key=_xrd_control_key(selected_key, "peak_dist", state),
            )
            peak_width = st.number_input(
                tx("Pik Genişliği", "Peak Width"),
                min_value=1,
                max_value=200,
                value=int(peak_defaults.get("width") or 2),
                key=_xrd_control_key(selected_key, "peak_width", state),
            )
            peak_max = st.number_input(
                tx("Maks Pik", "Max Peaks"),
                min_value=1,
                max_value=200,
                value=int(peak_defaults.get("max_peaks") or 12),
                key=_xrd_control_key(selected_key, "peak_max", state),
            )

            match_tolerance = st.number_input(
                tx("Eşleşme Toleransı (°)", "Match Tolerance (°)"),
                min_value=0.01,
                max_value=2.0,
                value=float(defaults_context.get("xrd_match_tolerance_deg") or 0.28),
                format="%.3f",
                key=_xrd_control_key(selected_key, "match_tol", state),
            )
            match_min_score = st.slider(
                tx("Minimum Eşleşme Skoru", "Minimum Match Score"),
                0.0,
                1.0,
                float(defaults_context.get("xrd_match_minimum_score") or 0.42),
                0.01,
                key=_xrd_control_key(selected_key, "match_min", state),
            )
            match_top_n = st.number_input(
                tx("Aday Sayısı", "Top Candidate Count"),
                min_value=1,
                max_value=20,
                value=int(defaults_context.get("xrd_match_top_n") or 5),
                key=_xrd_control_key(selected_key, "match_topn", state),
            )
            match_intensity_weight = st.slider(
                tx("Yoğunluk Ağırlığı", "Intensity Weight"),
                0.0,
                1.0,
                float(defaults_context.get("xrd_match_intensity_weight") or 0.35),
                0.01,
                key=_xrd_control_key(selected_key, "match_iw", state),
            )
            match_major_fraction = st.slider(
                tx("Majör Pik Eşiği", "Major Peak Fraction"),
                0.0,
                1.0,
                float(defaults_context.get("xrd_match_major_peak_fraction") or 0.4),
                0.01,
                key=_xrd_control_key(selected_key, "match_major", state),
            )

            if st.button(tx("XRD Analizini Çalıştır", "Run XRD Analysis"), key=_xrd_control_key(selected_key, "run", state)):
                processing = ensure_processing_payload(state.get("processing"), analysis_type="XRD")
                processing = update_processing_step(
                    processing,
                    "axis_normalization",
                    {
                        "sort_axis": True,
                        "deduplicate": "first",
                        "axis_min": float(axis_min) if restrict_range else None,
                        "axis_max": float(axis_max) if restrict_range else None,
                    },
                    analysis_type="XRD",
                )
                processing = update_processing_step(
                    processing,
                    "smoothing",
                    {
                        "method": smooth_method,
                        "window_length": int(smooth_window),
                        "polyorder": int(smooth_poly),
                    },
                    analysis_type="XRD",
                )
                processing = update_processing_step(
                    processing,
                    "baseline",
                    {
                        "method": baseline_method,
                        "window_length": int(baseline_window),
                        "smoothing_window": int(baseline_smooth),
                    },
                    analysis_type="XRD",
                )
                processing = update_processing_step(
                    processing,
                    "peak_detection",
                    {
                        "method": "scipy_find_peaks",
                        "prominence": float(peak_prominence),
                        "distance": int(peak_distance),
                        "width": int(peak_width),
                        "max_peaks": int(peak_max),
                    },
                    analysis_type="XRD",
                )
                processing = update_method_context(
                    processing,
                    {
                        "xrd_match_metric": "peak_overlap_weighted",
                        "xrd_match_tolerance_deg": float(match_tolerance),
                        "xrd_match_top_n": int(match_top_n),
                        "xrd_match_minimum_score": float(match_min_score),
                        "xrd_match_intensity_weight": float(match_intensity_weight),
                        "xrd_match_major_peak_fraction": float(match_major_fraction),
                    },
                    analysis_type="XRD",
                )
                state["processing"] = processing
                outcome = execute_batch_template(
                    dataset_key=selected_key,
                    dataset=dataset,
                    analysis_type="XRD",
                    workflow_template_id=workflow_template_id,
                    existing_processing=state.get("processing"),
                    analysis_history=st.session_state.get("analysis_history", []),
                    analyst_name=(st.session_state.get("branding", {}) or {}).get("analyst_name"),
                    app_version=APP_VERSION,
                    batch_run_id=f"xrd_single_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                )

                status = outcome.get("status")
                if status == "saved":
                    st.session_state[state_key] = outcome.get("state") or {}
                    st.session_state[state_key]["processing"] = outcome.get("processing")
                    record = outcome.get("record")
                    if record:
                        st.session_state.setdefault("results", {})[record["id"]] = record
                        current_saved_state = st.session_state.get(state_key, {})
                        try:
                            record, _ = _save_xrd_result_to_session(
                                record,
                                dataset_key=selected_key,
                                dataset=dataset,
                                state=current_saved_state,
                                lang=lang,
                            )
                        except Exception as exc:
                            error_id = record_exception(
                                st.session_state,
                                area="xrd_analysis",
                                action="save_figure",
                                message="Saving XRD figure for report generation failed.",
                                context={"dataset_key": selected_key, "result_id": record.get("id")},
                                exception=exc,
                            )
                            st.warning(
                                tx(
                                    "XRD sonucu kaydedildi ancak rapor grafiği hazırlanamadı: {error}",
                                    "XRD result was saved, but the report figure could not be prepared: {error}",
                                    error=f"{exc} (Error ID: {error_id})",
                                )
                            )
                        st.success(
                            tx(
                                "XRD sonucu kaydedildi: {result_id}",
                                "XRD result saved: {result_id}",
                                result_id=record["id"],
                            )
                        )
                        _log_event(
                            tx("XRD Analizi Çalıştırıldı", "XRD Analysis Executed"),
                            tx(
                                "{dataset} için {template} ile nitel faz adayı eşleşmesi kaydedildi.",
                                "Saved qualitative phase-candidate matching for {dataset} using {template}.",
                                dataset=selected_key,
                                template=workflow_template_id,
                            ),
                            t("xrd.title"),
                            dataset_key=selected_key,
                            result_id=record["id"],
                        )
                elif status == "blocked":
                    issues = "; ".join((outcome.get("validation") or {}).get("issues") or [])
                    st.error(
                        tx(
                            "XRD çalıştırması doğrulama tarafından bloklandı: {issues}",
                            "XRD run was blocked by validation: {issues}",
                            issues=issues or tx("Bilinmeyen neden", "Unknown reason"),
                        )
                    )
                else:
                    failure_reason = (outcome.get("summary_row") or {}).get("failure_reason") or tx(
                        "Bilinmeyen hata", "Unknown error"
                    )
                    st.error(tx("XRD çalıştırması başarısız oldu: {reason}", "XRD run failed: {reason}", reason=failure_reason))

        with preview_col:
            st.caption(
                tx(
                    "Şablon parametreleri + bu paneldeki override değerleri aynı çalıştırmada uygulanır.",
                    "Template defaults and the overrides from this panel are applied in the same run.",
                )
            )
            preview_plot_settings = _xrd_plot_settings_from_processing((st.session_state.get(state_key, {}) or {}).get("processing"))
            st.plotly_chart(
                _build_processed_plot(
                    selected_key,
                    dataset,
                    st.session_state.get(state_key, {}),
                    lang,
                    plot_settings=preview_plot_settings,
                ),
                width="stretch",
                config=PLOTLY_CONFIG,
                key=f"xrd_pipeline_plot_{selected_key}",
            )

    with tab_peaks:
        current_state = st.session_state.get(state_key, {})
        current_plot_settings = _xrd_plot_settings_from_processing((current_state.get("processing") or {}))
        current_plot_settings = _render_xrd_plot_settings_panel(selected_key, current_state, current_plot_settings, dataset=dataset)
        st.plotly_chart(
            _build_processed_plot(
                selected_key,
                dataset,
                current_state,
                lang,
                plot_settings=current_plot_settings,
            ),
            width="stretch",
            config=PLOTLY_CONFIG,
            key=f"xrd_peak_plot_{selected_key}",
        )
        peaks = current_state.get("peaks") or []
        if peaks:
            st.subheader(tx("Tespit Edilen Pikler", "Detected Peaks"))
            st.dataframe(pd.DataFrame(peaks), width="stretch", hide_index=True)
        else:
            st.info(tx("Henüz pik tespit edilmedi.", "No peaks detected yet."))

    with tab_matches:
        current_state = st.session_state.get(state_key, {})
        record = _find_xrd_record(st.session_state.get("results"), selected_key)
        matches = _resolve_xrd_matches(current_state, record)
        summary = (record or {}).get("summary") or {}
        method_context = ((current_state.get("processing") or {}).get("method_context") or {})

        reference_count_raw = summary.get("reference_candidate_count", method_context.get("xrd_reference_candidate_count", 0))
        try:
            reference_count = int(reference_count_raw or 0)
        except (TypeError, ValueError):
            reference_count = 0

        top = matches[0] if matches else None
        peak_count = len(current_state.get("peaks") or [])
        if peak_count == 0:
            try:
                peak_count = int(summary.get("peak_count") or 0)
            except (TypeError, ValueError):
                peak_count = 0

        best_candidate_name = _xrd_best_candidate_name(summary, matches)
        best_candidate_score = _xrd_best_candidate_score(summary, matches)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(tx("Pik Sayısı", "Peak Count"), str(peak_count))
        m2.metric(tx("En İyi Aday", "Best Candidate"), best_candidate_name or tx("Yok", "None"))
        m3.metric(tx("Aday Skoru", "Candidate Score"), f"{best_candidate_score:.3f}" if best_candidate_score is not None else "N/A")
        m4.metric(tx("Kabul Durumu", "Accepted Match Status"), str(summary.get("match_status") or tx("Yok", "None")))
        if summary.get("library_result_source"):
            st.caption(
                tx(
                    "Library sonuç kaynağı: {source}",
                    "Library result source: {source}",
                    source=summary.get("library_result_source"),
                )
            )
        if summary.get("library_request_id"):
            st.caption(f"Cloud Request ID: `{summary.get('library_request_id')}`")
        if summary.get("library_offline_limited_mode"):
            st.warning(
                tx(
                    "Sınırlı offline fallback modu aktif. Sonuçlar tam cloud kapsamını temsil etmeyebilir.",
                    "Limited offline fallback mode is active. Results may not represent full cloud coverage.",
                )
            )

        if reference_count == 0:
            st.warning(
                tx(
                    "Kurulu bir XRD referans paketi bulunamadı. Önce Kütüphane sayfasından sync yapın veya veri seti metadata içine `xrd_reference_library` ekleyin.",
                    "No installed XRD reference package is available. Sync the Library page first or add `xrd_reference_library` to the dataset metadata.",
                )
            )
        elif str(summary.get("match_status") or "").lower() == "no_match" and summary.get("top_candidate_reason_below_threshold"):
            st.info(
                tx(
                    "En iyi aday kabul edilmedi: {reason}",
                    "Best candidate was not accepted: {reason}",
                    reason=summary.get("top_candidate_reason_below_threshold"),
                )
            )

        if matches:
            candidate_options = []
            option_to_match: dict[str, dict[str, Any]] = {}
            for item in matches:
                try:
                    display_score = float(item.get("normalized_score", 0.0))
                except (TypeError, ValueError):
                    display_score = 0.0
                candidate_name = str(_xrd_visible_candidate_name(item) or item.get("candidate_name") or item.get("candidate_id") or "N/A")
                option = f"#{int(item.get('rank') or 0)} {candidate_name} | {display_score:.3f}"
                candidate_options.append(option)
                option_to_match[option] = item

            selected_option = st.selectbox(
                tx("Grafik aday overlay", "Candidate overlay"),
                candidate_options,
                key=_xrd_control_key(selected_key, "match_candidate", current_state),
            )
            selected_match = option_to_match.get(selected_option) or matches[0]
            matches_plot_settings = _xrd_plot_settings_from_processing((current_state.get("processing") or {}))
            st.plotly_chart(
                _build_processed_plot(
                    selected_key,
                    dataset,
                    current_state,
                    lang,
                    plot_settings=matches_plot_settings,
                    selected_match=selected_match,
                ),
                width="stretch",
                config=PLOTLY_CONFIG,
                key=f"xrd_match_plot_{selected_key}",
            )
            selected_evidence = dict((selected_match.get("evidence") or {}))
            st.caption(_xrd_selected_candidate_caption(selected_match, lang=lang))
            st.caption(
                tx(
                    "Seçili aday grafikte renk/şekil ile gösterildi. Eşleşen pikler, eşleşmeyen gözlenen/referans pikler ve bağlantı çizgileri Grafik Ayarları'ndan yönetilir.",
                    "Selected candidate is highlighted with color/shape. Matched peaks, unmatched observed/reference peaks, and connector lines are controlled from Plot Settings.",
                )
            )
            snapshot_col, primary_col = st.columns(2)
            with snapshot_col:
                if st.button(
                    tx("Snapshot Kaydet", "Save Snapshot"),
                    key=_xrd_control_key(selected_key, "save_snapshot", current_state),
                    disabled=record is None,
                ):
                    try:
                        updated_record, snapshot_key = _save_xrd_graph_snapshot_to_session(
                            record=record,
                            dataset_key=selected_key,
                            dataset=dataset,
                            state=current_state,
                            lang=lang,
                            selected_match=selected_match,
                            plot_settings=matches_plot_settings,
                            set_primary=False,
                        )
                        record = updated_record
                        st.success(
                            tx(
                                "Snapshot kaydedildi: {key}",
                                "Snapshot saved: {key}",
                                key=snapshot_key,
                            )
                        )
                    except Exception as exc:
                        error_id = record_exception(
                            st.session_state,
                            area="xrd_analysis",
                            action="save_snapshot",
                            message="Saving XRD snapshot failed.",
                            context={"dataset_key": selected_key, "result_id": (record or {}).get("id")},
                            exception=exc,
                        )
                        st.error(
                            tx(
                                "Snapshot kaydı başarısız: {error}",
                                "Snapshot save failed: {error}",
                                error=f"{exc} (Error ID: {error_id})",
                            )
                        )
            with primary_col:
                if st.button(
                    tx("Bu Grafiği Raporda Kullan", "Use This Graph in Report"),
                    key=_xrd_control_key(selected_key, "use_snapshot_report", current_state),
                    disabled=record is None,
                ):
                    try:
                        updated_record, snapshot_key = _save_xrd_graph_snapshot_to_session(
                            record=record,
                            dataset_key=selected_key,
                            dataset=dataset,
                            state=current_state,
                            lang=lang,
                            selected_match=selected_match,
                            plot_settings=matches_plot_settings,
                            set_primary=True,
                        )
                        record = updated_record
                        st.success(
                            tx(
                                "Primary rapor grafiği seçildi: {key}",
                                "Primary report figure selected: {key}",
                                key=snapshot_key,
                            )
                        )
                    except Exception as exc:
                        error_id = record_exception(
                            st.session_state,
                            area="xrd_analysis",
                            action="use_snapshot_report",
                            message="Setting XRD primary report figure failed.",
                            context={"dataset_key": selected_key, "result_id": (record or {}).get("id")},
                            exception=exc,
                        )
                        st.error(
                            tx(
                                "Rapor figürü seçimi başarısız: {error}",
                                "Setting report figure failed: {error}",
                                error=f"{exc} (Error ID: {error_id})",
                            )
                        )

            if record is None:
                st.caption(
                    tx(
                        "Snapshot/rapor figürü için önce sonucu kaydetmiş olmanız gerekir.",
                        "Save the result first to enable snapshot/report figure actions.",
                    )
                )
            else:
                primary_figure_key = ((record.get("artifacts") or {}).get("report_figure_key") or "")
                if primary_figure_key:
                    st.caption(
                        tx(
                            "Primary rapor grafiği: {key}",
                            "Primary report figure: {key}",
                            key=primary_figure_key,
                        )
                    )
            if not (selected_evidence.get("matched_peak_pairs") or []):
                st.info(
                    tx(
                        "Seçili aday için tolerans içinde eşleşen pik çifti bulunamadı.",
                        "No peak pairs were matched within tolerance for the selected candidate.",
                    )
                )

            rows = []
            for item in matches:
                evidence = item.get("evidence") or {}
                rows.append(
                    {
                        tx("Sıra", "Rank"): item.get("rank"),
                        tx("Aday", "Candidate"): _xrd_visible_candidate_name(item),
                        tx("Ham Etiket", "Raw Label"): item.get("candidate_name"),
                        tx("Aday ID", "Candidate ID"): item.get("candidate_id"),
                        tx("Kaynak ID", "Source ID"): item.get("source_id"),
                        tx("Skor", "Score"): item.get("normalized_score"),
                        tx("Güven", "Confidence"): item.get("confidence_band"),
                        tx("Ortak Pik", "Shared Peaks"): evidence.get("shared_peak_count"),
                        tx("Ağırlıklı Örtüşme", "Weighted Overlap"): evidence.get("weighted_overlap_score"),
                        tx("Kapsama", "Coverage"): evidence.get("coverage_ratio"),
                        tx("Ortalama Δ2θ", "Mean Δ2θ"): evidence.get("mean_delta_position"),
                        tx("Eşleşmeyen Majör Pik", "Unmatched Major Peaks"): evidence.get("unmatched_major_peak_count"),
                        tx("Provider", "Provider"): item.get("library_provider"),
                        tx("Paket", "Package"): item.get("library_package"),
                    }
                )
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        else:
            st.info(tx("Henüz faz adayı yok.", "No phase candidates yet."))

    with tab_results:
        current_state = st.session_state.get(state_key, {})
        record = _find_xrd_record(st.session_state.get("results"), selected_key)
        if not record:
            derived_matches = _resolve_xrd_matches(current_state, None)
            derived_top = derived_matches[0] if derived_matches else None
            derived_summary = {
                "peak_count": len(current_state.get("peaks") or []),
                "candidate_count": len(derived_matches),
                "match_status": "matched" if derived_matches else "no_match",
                "top_phase": derived_top.get("candidate_name") if derived_top else None,
                "top_phase_display_name": _xrd_candidate_display_name(derived_top) if derived_top else None,
                "top_phase_display_name_unicode": _xrd_visible_candidate_name(derived_top) if derived_top else None,
                "top_phase_score": float(derived_top.get("normalized_score", 0.0)) if derived_top else 0.0,
                "top_candidate_name": derived_top.get("candidate_name") if derived_top else None,
                "top_candidate_display_name": _xrd_candidate_display_name(derived_top) if derived_top else None,
                "top_candidate_display_name_unicode": _xrd_visible_candidate_name(derived_top) if derived_top else None,
                "top_candidate_score": float(derived_top.get("normalized_score", 0.0)) if derived_top else None,
                "top_candidate_shared_peak_count": ((derived_top or {}).get("evidence") or {}).get("shared_peak_count"),
                "top_candidate_weighted_overlap_score": ((derived_top or {}).get("evidence") or {}).get("weighted_overlap_score"),
                "top_candidate_coverage_ratio": ((derived_top or {}).get("evidence") or {}).get("coverage_ratio"),
                "top_candidate_mean_delta_position": ((derived_top or {}).get("evidence") or {}).get("mean_delta_position"),
                "top_candidate_unmatched_major_peak_count": ((derived_top or {}).get("evidence") or {}).get("unmatched_major_peak_count"),
            }
            if derived_summary["peak_count"] > 0:
                st.warning(
                    tx(
                        "Kalıcı kayıt bulunamadı; aşağıdaki özet yalnızca mevcut oturum state'inden türetildi.",
                        "No persisted result record was found; the summary below is derived from in-session state only.",
                    )
                )
                summary_rows = [{"key": key, "value": value} for key, value in derived_summary.items()]
                st.dataframe(pd.DataFrame(summary_rows), width="stretch", hide_index=True)
            else:
                st.info(
                    tx(
                        "Kaydedilmiş XRD sonucu bulunamadı. Parametreleri ayarlayıp analizi çalıştırın.",
                        "No saved XRD result found. Configure parameters and run analysis first.",
                    )
                )
            return

        summary = record.get("summary") or {}
        st.markdown(f"**Result ID:** `{record.get('id')}`")
        st.markdown(f"**{tx('Durum', 'Status')}:** {record.get('status')}")
        best_candidate_name = _xrd_best_candidate_name(summary, matches=[])
        best_candidate_score = _xrd_best_candidate_score(summary, matches=[])
        result_m1, result_m2, result_m3, result_m4 = st.columns(4)
        result_m1.metric(tx("Kabul Durumu", "Accepted Match Status"), str(summary.get("match_status") or "N/A"))
        result_m2.metric(tx("En İyi Aday", "Best Candidate"), best_candidate_name or tx("Yok", "None"))
        result_m3.metric(
            tx("Aday Skoru", "Candidate Score"),
            f"{best_candidate_score:.3f}" if best_candidate_score is not None else "N/A",
        )
        result_m4.metric(tx("Güven Bandı", "Confidence Band"), str(summary.get("confidence_band") or "N/A"))
        if summary.get("library_result_source"):
            st.caption(
                tx(
                    "Library sonuç kaynağı: {source}",
                    "Library result source: {source}",
                    source=summary.get("library_result_source"),
                )
            )
        if summary.get("library_request_id"):
            st.caption(f"Cloud Request ID: `{summary.get('library_request_id')}`")
        if summary.get("library_offline_limited_mode"):
            st.warning(
                tx(
                    "Sınırlı offline fallback modu aktif. Sonuçlar tam cloud kapsamını temsil etmeyebilir.",
                    "Limited offline fallback mode is active. Results may not represent full cloud coverage.",
                )
            )
        if summary.get("caution_code"):
            st.warning(
                tx(
                    "Caution kodu: {code} | {message}",
                    "Caution code: {code} | {message}",
                    code=summary.get("caution_code"),
                    message=summary.get("caution_message") or tx("Mesaj yok", "No message"),
                )
            )
        if summary.get("top_candidate_reason_below_threshold"):
            evidence_rows = [
                {
                    tx("Alan", "Field"): tx("En İyi Aday", "Best Candidate"),
                    tx("Değer", "Value"): best_candidate_name or tx("Yok", "None"),
                },
                {
                    tx("Alan", "Field"): tx("Aday Skoru", "Candidate Score"),
                    tx("Değer", "Value"): f"{best_candidate_score:.3f}" if best_candidate_score is not None else "N/A",
                },
                {
                    tx("Alan", "Field"): tx("Provider / Paket", "Provider / Package"),
                    tx("Değer", "Value"): (
                        f"{summary.get('top_candidate_provider') or 'N/A'} / {summary.get('top_candidate_package') or 'N/A'}"
                    ),
                },
                {
                    tx("Alan", "Field"): tx("Ortak Pik", "Shared Peaks"),
                    tx("Değer", "Value"): summary.get("top_candidate_shared_peak_count"),
                },
                {
                    tx("Alan", "Field"): tx("Ağırlıklı Örtüşme", "Weighted Overlap"),
                    tx("Değer", "Value"): summary.get("top_candidate_weighted_overlap_score"),
                },
                {
                    tx("Alan", "Field"): tx("Kapsama", "Coverage"),
                    tx("Değer", "Value"): summary.get("top_candidate_coverage_ratio"),
                },
                {
                    tx("Alan", "Field"): tx("Ortalama Δ2θ", "Mean Δ2θ"),
                    tx("Değer", "Value"): summary.get("top_candidate_mean_delta_position"),
                },
                {
                    tx("Alan", "Field"): tx("Eşleşmeyen Majör Pik", "Unmatched Major Peaks"),
                    tx("Değer", "Value"): summary.get("top_candidate_unmatched_major_peak_count"),
                },
                {
                    tx("Alan", "Field"): tx("Neden Kabul Edilmedi", "Why It Was Not Accepted"),
                    tx("Değer", "Value"): summary.get("top_candidate_reason_below_threshold"),
                },
            ]
            st.subheader(tx("En İyi Aday Özeti", "Best Candidate Summary"))
            st.dataframe(pd.DataFrame(evidence_rows), width="stretch", hide_index=True)
        summary_rows = [{"key": key, "value": value} for key, value in summary.items()]
        st.dataframe(pd.DataFrame(summary_rows), width="stretch", hide_index=True)
        artifacts = record.get("artifacts") or {}
        attached_figures = [str(item) for item in (artifacts.get("figure_keys") or []) if item not in (None, "")]
        primary_figure_key = str(artifacts.get("report_figure_key") or "")
        if primary_figure_key in attached_figures:
            st.caption(
                tx(
                    "Primary rapor grafiği hazır: {figure}",
                    "Primary report figure ready: {figure}",
                    figure=primary_figure_key,
                )
            )
        elif _xrd_figure_key(selected_key) in attached_figures:
            st.caption(
                tx(
                    "Bu sonuç rapor merkezine grafik ile birlikte hazır.",
                    "This result is ready for the Report Center together with its figure.",
                )
            )

        st.divider()

        if st.button(tx("Sonuç ve Grafiği Oturuma Kaydet", "Save Result and Figure to Session"), key=f"xrd_save_results_{selected_key}"):
            try:
                record, _ = _save_xrd_result_to_session(
                    record,
                    dataset_key=selected_key,
                    dataset=dataset,
                    state=current_state,
                    lang=lang,
                )
                _log_event(
                    tx("Sonuçlar Kaydedildi", "Results Saved"),
                    tx(
                        "XRD sonucu ve grafik rapor merkezi için kaydedildi.",
                        "XRD result and figure were saved for the Report Center.",
                    ),
                    t("xrd.title"),
                    dataset_key=selected_key,
                    result_id=record["id"],
                )
                st.success(
                    tx(
                        "XRD sonucu ve grafiği kaydedildi. İndirmek için Rapor Merkezi'ne gidin.",
                        "XRD result and figure were saved. Go to Report Center to download.",
                    )
                )
            except Exception as exc:
                error_id = record_exception(
                    st.session_state,
                    area="xrd_analysis",
                    action="save_results",
                    message="Saving XRD results failed.",
                    context={"dataset_key": selected_key, "result_id": record.get("id")},
                    exception=exc,
                )
                st.error(
                    tx(
                        "XRD sonuçları kaydedilemedi: {error}",
                        "Saving XRD results failed: {error}",
                        error=f"{exc} (Error ID: {error_id})",
                    )
                )

