"""XRD Analysis page - multi-tab stable qualitative phase-screening workflow."""

from __future__ import annotations

from datetime import datetime

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
from ui.components.chrome import render_page_header
from ui.components.history_tracker import _log_event
from ui.components.preset_manager import render_processing_preset_panel, seed_pending_workflow_template
from ui.components.plot_builder import PLOTLY_CONFIG, create_thermal_plot, fig_to_bytes
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


def _build_processed_plot(dataset_key, dataset, state, lang: str):
    axis = np.asarray(dataset.data["temperature"].values, dtype=float)
    raw_signal = np.asarray(dataset.data["signal"].values, dtype=float)
    fig = create_thermal_plot(
        axis,
        raw_signal,
        title=tx("XRD Analizi - {dataset}", "XRD Analysis - {dataset}", dataset=dataset_key),
        x_label=_x_axis_label(dataset, lang),
        y_label=tx("Yoğunluk", "Intensity"),
        name=tx("Ham", "Raw"),
    )

    smoothed = _to_array((state or {}).get("smoothed"))
    corrected = _to_array((state or {}).get("corrected"))
    peaks = (state or {}).get("peaks") or []

    if smoothed is not None and smoothed.shape[0] == axis.shape[0]:
        fig.add_trace(
            go.Scatter(
                x=axis,
                y=smoothed,
                mode="lines",
                name=tx("Yumuşatılmış", "Smoothed"),
                line=dict(color="#0EA5E9", width=1.8),
            )
        )
    if corrected is not None and corrected.shape[0] == axis.shape[0]:
        fig.add_trace(
            go.Scatter(
                x=axis,
                y=corrected,
                mode="lines",
                name=tx("Arkaplan Düzeltilmiş", "Background Corrected"),
                line=dict(color="#16A34A", width=2.0),
            )
        )
    if peaks:
        fig.add_trace(
            go.Scatter(
                x=[float(item.get("position", 0.0)) for item in peaks],
                y=[float(item.get("intensity", 0.0)) for item in peaks],
                mode="markers",
                name=tx("Pikler", "Peaks"),
                marker=dict(color="#DC2626", size=8, symbol="diamond"),
            )
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
                "normalized_score": row.get("normalized_score"),
                "confidence_band": row.get("confidence_band"),
                "evidence": row.get("evidence") or {},
            }
        )
    return normalized


def _xrd_best_candidate_name(summary: dict | None, matches: list[dict] | None) -> str | None:
    summary = summary or {}
    candidate_name = summary.get("top_candidate_name") or summary.get("top_candidate_id")
    if candidate_name not in (None, ""):
        return str(candidate_name)
    top = matches[0] if matches else None
    if isinstance(top, dict):
        return str(top.get("candidate_name") or top.get("candidate_id") or "") or None
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
        },
        analysis_type="XRD",
    )
    return payload


def _attach_xrd_report_figure(record, *, dataset_key: str, dataset, state, lang: str, figures_store):
    figure_key = _xrd_figure_key(dataset_key)
    figures_store[figure_key] = fig_to_bytes(_build_processed_plot(dataset_key, dataset, state, lang))

    updated_record = dict(record or {})
    artifacts = dict(updated_record.get("artifacts") or {})
    figure_keys = [
        str(item)
        for item in (artifacts.get("figure_keys") or [])
        if item not in (None, "", figure_key)
    ]
    figure_keys.append(figure_key)
    artifacts["figure_keys"] = figure_keys
    updated_record["artifacts"] = artifacts
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
            use_container_width=True,
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
            st.plotly_chart(
                _build_processed_plot(selected_key, dataset, st.session_state.get(state_key, {}), lang),
                use_container_width=True,
                config=PLOTLY_CONFIG,
                key=f"xrd_pipeline_plot_{selected_key}",
            )

    with tab_peaks:
        current_state = st.session_state.get(state_key, {})
        st.plotly_chart(
            _build_processed_plot(selected_key, dataset, current_state, lang),
            use_container_width=True,
            config=PLOTLY_CONFIG,
            key=f"xrd_peak_plot_{selected_key}",
        )
        peaks = current_state.get("peaks") or []
        if peaks:
            st.subheader(tx("Tespit Edilen Pikler", "Detected Peaks"))
            st.dataframe(pd.DataFrame(peaks), use_container_width=True, hide_index=True)
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
            rows = []
            for item in matches:
                evidence = item.get("evidence") or {}
                rows.append(
                    {
                        tx("Sıra", "Rank"): item.get("rank"),
                        tx("Aday", "Candidate"): item.get("candidate_name"),
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
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
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
                "top_phase_score": float(derived_top.get("normalized_score", 0.0)) if derived_top else 0.0,
                "top_candidate_name": derived_top.get("candidate_name") if derived_top else None,
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
                st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
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
            st.dataframe(pd.DataFrame(evidence_rows), use_container_width=True, hide_index=True)
        summary_rows = [{"key": key, "value": value} for key, value in summary.items()]
        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
        attached_figures = [str(item) for item in ((record.get("artifacts") or {}).get("figure_keys") or []) if item not in (None, "")]
        if _xrd_figure_key(selected_key) in attached_figures:
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
