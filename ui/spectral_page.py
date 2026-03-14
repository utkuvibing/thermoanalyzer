"""Shared FTIR/RAMAN stable analysis page built on batch templates."""

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
    update_processing_step,
)
from core.validation import validate_thermal_dataset
from ui.components.chrome import render_page_header
from ui.components.history_tracker import _log_event
from ui.components.preset_manager import render_processing_preset_panel
from ui.components.plot_builder import PLOTLY_CONFIG, create_thermal_plot
from utils.i18n import t, tx
from utils.license_manager import APP_VERSION


_SPECTRAL_TEMPLATE_DEFAULTS = {
    "FTIR": {
        "ftir.general": {
            "smoothing": {"method": "moving_average", "window_length": 11},
            "baseline": {"method": "linear"},
            "normalization": {"method": "vector"},
            "peak_detection": {"prominence": 0.05, "min_distance": 6, "max_peaks": 12},
            "similarity_matching": {"metric": "cosine", "top_n": 3, "minimum_score": 0.45},
        },
        "ftir.functional_groups": {
            "smoothing": {"method": "moving_average", "window_length": 9},
            "baseline": {"method": "linear"},
            "normalization": {"method": "vector"},
            "peak_detection": {"prominence": 0.04, "min_distance": 5, "max_peaks": 16},
            "similarity_matching": {"metric": "cosine", "top_n": 5, "minimum_score": 0.42},
        },
    },
    "RAMAN": {
        "raman.general": {
            "smoothing": {"method": "moving_average", "window_length": 9},
            "baseline": {"method": "linear"},
            "normalization": {"method": "snv"},
            "peak_detection": {"prominence": 0.04, "min_distance": 5, "max_peaks": 14},
            "similarity_matching": {"metric": "cosine", "top_n": 3, "minimum_score": 0.45},
        },
        "raman.polymorph_screening": {
            "smoothing": {"method": "moving_average", "window_length": 7},
            "baseline": {"method": "linear"},
            "normalization": {"method": "snv"},
            "peak_detection": {"prominence": 0.03, "min_distance": 4, "max_peaks": 18},
            "similarity_matching": {"metric": "pearson", "top_n": 5, "minimum_score": 0.4},
        },
    },
}


def _get_spectral_datasets(analysis_type: str):
    datasets = st.session_state.get("datasets", {})
    token = str(analysis_type or "").upper()
    return {
        key: ds
        for key, ds in datasets.items()
        if str(getattr(ds, "data_type", "UNKNOWN") or "UNKNOWN").upper() in {token, "UNKNOWN"}
    }


def _x_axis_label(analysis_type: str, dataset) -> str:
    unit = (dataset.units or {}).get("temperature", "cm^-1")
    if analysis_type == "FTIR":
        return tx(f"Dalgasayısı ({unit})", f"Wavenumber ({unit})")
    return tx(f"Raman Kayması ({unit})", f"Raman Shift ({unit})")


def _y_axis_label(analysis_type: str, dataset) -> str:
    unit = (dataset.units or {}).get("signal", "a.u.")
    if analysis_type == "FTIR":
        return tx(f"Absorbans ({unit})", f"Absorbance ({unit})")
    return tx(f"Yoğunluk ({unit})", f"Intensity ({unit})")


def _to_array(value):
    if isinstance(value, np.ndarray):
        return value
    if isinstance(value, list):
        try:
            return np.asarray(value, dtype=float)
        except Exception:
            return None
    return None


def _build_plot(dataset_key: str, dataset, state: dict, analysis_type: str):
    axis = np.asarray(dataset.data["temperature"].values, dtype=float)
    raw = np.asarray(dataset.data["signal"].values, dtype=float)
    fig = create_thermal_plot(
        axis,
        raw,
        title=tx("{analysis_type} Analizi - {dataset}", "{analysis_type} Analysis - {dataset}", analysis_type=analysis_type, dataset=dataset_key),
        x_label=_x_axis_label(analysis_type, dataset),
        y_label=_y_axis_label(analysis_type, dataset),
        name=tx("Ham", "Raw"),
    )

    smoothed = _to_array((state or {}).get("smoothed"))
    corrected = _to_array((state or {}).get("corrected"))
    normalized = _to_array((state or {}).get("normalized"))
    peaks = (state or {}).get("peaks") or []

    if smoothed is not None and smoothed.shape[0] == axis.shape[0]:
        fig.add_trace(
            go.Scatter(
                x=axis,
                y=smoothed,
                mode="lines",
                name=tx("Yumuşatılmış", "Smoothed"),
                line=dict(color="#0EA5E9", width=1.7),
            )
        )
    if corrected is not None and corrected.shape[0] == axis.shape[0]:
        fig.add_trace(
            go.Scatter(
                x=axis,
                y=corrected,
                mode="lines",
                name=tx("Baz Çizgisi Düzeltilmiş", "Baseline Corrected"),
                line=dict(color="#16A34A", width=1.8),
            )
        )
    if normalized is not None and normalized.shape[0] == axis.shape[0]:
        fig.add_trace(
            go.Scatter(
                x=axis,
                y=normalized,
                mode="lines",
                name=tx("Normalize", "Normalized"),
                line=dict(color="#7C3AED", width=1.6, dash="dot"),
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


def _seed_spectral_processing_defaults(token: str, processing, workflow_template_id: str, dataset):
    by_type = _SPECTRAL_TEMPLATE_DEFAULTS.get(token, {})
    defaults = by_type.get(workflow_template_id) or next(iter(by_type.values()), {})
    seeded = ensure_processing_payload(processing, analysis_type=token)
    for section_name in ("smoothing", "baseline", "normalization"):
        current = (seeded.get("signal_pipeline") or {}).get(section_name)
        seeded = update_processing_step(
            seeded,
            section_name,
            _merge_with_defaults(current, defaults.get(section_name)),
            analysis_type=token,
        )
    for section_name in ("peak_detection", "similarity_matching"):
        current = (seeded.get("analysis_steps") or {}).get(section_name)
        seeded = update_processing_step(
            seeded,
            section_name,
            _merge_with_defaults(current, defaults.get(section_name)),
            analysis_type=token,
        )
    return seeded


def render_spectral_page(
    analysis_type: str,
    *,
    title_key: str,
    caption_key: str,
    badge_key: str,
) -> None:
    token = str(analysis_type or "").upper()
    page_slug = token.lower()
    render_page_header(t(title_key), t(caption_key), badge=t(badge_key))
    st.info(
        tx(
            "{analysis_type} kararlı akışı ön işleme, pik çıkarımı ve benzerlik aday sıralamasını tek workflow içinde üretir.",
            "Stable {analysis_type} flow applies preprocessing, peak extraction, and similarity-candidate ranking in one workflow.",
            analysis_type=token,
        )
    )

    spectral_datasets = _get_spectral_datasets(token)
    if not spectral_datasets:
        st.warning(
            tx(
                "Henüz {analysis_type} veri seti yüklenmedi. Veri yüklemek için **Veri Al** sayfasına gidin.",
                "No {analysis_type} datasets loaded. Go to **Import Runs** to load a dataset.",
                analysis_type=token,
            )
        )
        return

    selected_key = st.selectbox(
        tx("Veri Seti Seç", "Select Dataset"),
        list(spectral_datasets.keys()),
        key=f"{page_slug}_dataset_select",
    )
    dataset = spectral_datasets[selected_key]
    state_key = analysis_state_key(token, selected_key)
    state = st.session_state.setdefault(state_key, {})
    state["processing"] = ensure_processing_payload(state.get("processing"), analysis_type=token)

    templates = get_workflow_templates(token)
    template_labels = {entry["id"]: entry["label"] for entry in templates}
    template_ids = list(template_labels)
    if not template_ids:
        st.error(tx("{analysis_type} iş akışı şablonu bulunamadı.", "No {analysis_type} workflow templates were found.", analysis_type=token))
        return

    current_template = state["processing"].get("workflow_template_id")
    default_index = template_ids.index(current_template) if current_template in template_ids else 0
    workflow_template_id = st.selectbox(
        tx("İş Akışı Şablonu", "Workflow Template"),
        template_ids,
        format_func=lambda template_id: template_labels.get(template_id, template_id),
        index=default_index,
        key=f"{page_slug}_template_{selected_key}",
    )
    state["processing"] = set_workflow_template(
        state.get("processing"),
        workflow_template_id,
        analysis_type=token,
        workflow_template_label=template_labels.get(workflow_template_id),
    )
    render_processing_preset_panel(
        analysis_type=token,
        state=state,
        key_prefix=f"{page_slug}_presets_{selected_key}",
        workflow_select_key=f"{page_slug}_template_{selected_key}",
    )
    state["processing"] = _seed_spectral_processing_defaults(token, state.get("processing"), workflow_template_id, dataset)

    dataset_validation = validate_thermal_dataset(dataset, analysis_type=token, processing=state.get("processing"))
    if dataset_validation["status"] == "fail":
        st.error(
            tx(
                "Veri seti kararlı {analysis_type} iş akışına alınmadı: {issues}",
                "Dataset is blocked from the stable {analysis_type} workflow: {issues}",
                analysis_type=token,
                issues="; ".join(dataset_validation["issues"]),
            )
        )
        return
    if dataset_validation["warnings"]:
        with st.expander(tx("Veri Doğrulama", "Dataset Validation"), expanded=False):
            for warning in dataset_validation["warnings"]:
                st.warning(warning)

    tab_raw, tab_pipeline, tab_processed, tab_matches, tab_results = st.tabs(
        [
            tx("Ham Veri", "Raw Data"),
            tx("İşlem Parametreleri", "Processing Parameters"),
            tx("İşlenmiş Sinyal", "Processed Signal"),
            tx("Aday Eşleşmeler", "Candidate Matches"),
            tx("Sonuç Özeti", "Results Summary"),
        ]
    )

    with tab_raw:
        st.plotly_chart(
            create_thermal_plot(
                dataset.data["temperature"].values,
                dataset.data["signal"].values,
                title=tx("Ham {analysis_type} - {dataset}", "Raw {analysis_type} - {dataset}", analysis_type=token, dataset=selected_key),
                x_label=_x_axis_label(token, dataset),
                y_label=_y_axis_label(token, dataset),
            ),
            use_container_width=True,
            config=PLOTLY_CONFIG,
            key=f"{page_slug}_raw_chart_{selected_key}",
        )

    with tab_pipeline:
        defaults = {
            "smoothing": (state["processing"].get("signal_pipeline") or {}).get("smoothing") or {},
            "baseline": (state["processing"].get("signal_pipeline") or {}).get("baseline") or {},
            "normalization": (state["processing"].get("signal_pipeline") or {}).get("normalization") or {},
            "peak_detection": (state["processing"].get("analysis_steps") or {}).get("peak_detection") or {},
            "similarity_matching": (state["processing"].get("analysis_steps") or {}).get("similarity_matching") or {},
        }

        col_controls, col_text = st.columns([1, 2])
        with col_controls:
            smooth_method = st.selectbox(
                tx("Yumuşatma", "Smoothing"),
                ["moving_average", "none"],
                index=0 if str(defaults["smoothing"].get("method", "moving_average")).lower() != "none" else 1,
                key=f"{page_slug}_smooth_method_{selected_key}",
            )
            window_length = st.slider(
                tx("Yumuşatma Penceresi", "Smoothing Window"),
                3,
                81,
                int(defaults["smoothing"].get("window_length") or 9),
                step=2,
                key=f"{page_slug}_smooth_window_{selected_key}",
            )
            baseline_method = st.selectbox(
                tx("Baz Çizgisi", "Baseline"),
                ["linear", "none"],
                index=0 if str(defaults["baseline"].get("method", "linear")).lower() != "none" else 1,
                key=f"{page_slug}_baseline_method_{selected_key}",
            )
            normalization_method = st.selectbox(
                tx("Normalize", "Normalization"),
                ["vector", "snv", "max"],
                index=["vector", "snv", "max"].index(
                    str(defaults["normalization"].get("method") or "vector").lower()
                )
                if str(defaults["normalization"].get("method") or "vector").lower() in {"vector", "snv", "max"}
                else 0,
                key=f"{page_slug}_norm_method_{selected_key}",
            )
            prominence = st.number_input(
                tx("Pik Belirginliği", "Peak Prominence"),
                min_value=0.001,
                max_value=1.0,
                value=float(defaults["peak_detection"].get("prominence") or 0.05),
                format="%.3f",
                key=f"{page_slug}_prominence_{selected_key}",
            )
            min_distance = st.number_input(
                tx("Pik Min Mesafe", "Peak Min Distance"),
                min_value=1,
                max_value=50,
                value=int(defaults["peak_detection"].get("min_distance") or 5),
                key=f"{page_slug}_min_distance_{selected_key}",
            )
            max_peaks = st.number_input(
                tx("Maks Pik", "Max Peaks"),
                min_value=1,
                max_value=100,
                value=int(defaults["peak_detection"].get("max_peaks") or 12),
                key=f"{page_slug}_max_peaks_{selected_key}",
            )
            metric = st.selectbox(
                tx("Benzerlik Metriği", "Similarity Metric"),
                ["cosine", "pearson"],
                index=0 if str(defaults["similarity_matching"].get("metric", "cosine")).lower() != "pearson" else 1,
                key=f"{page_slug}_metric_{selected_key}",
            )
            top_n = st.number_input(
                tx("Aday Sayısı", "Top N Candidates"),
                min_value=1,
                max_value=20,
                value=int(defaults["similarity_matching"].get("top_n") or 3),
                key=f"{page_slug}_topn_{selected_key}",
            )
            min_score = st.slider(
                tx("Minimum Skor", "Minimum Score"),
                0.0,
                1.0,
                float(defaults["similarity_matching"].get("minimum_score") or 0.45),
                0.01,
                key=f"{page_slug}_min_score_{selected_key}",
            )

            if st.button(tx("Analizi Çalıştır", "Run Analysis"), key=f"{page_slug}_run_{selected_key}"):
                processing = ensure_processing_payload(state.get("processing"), analysis_type=token)
                processing = update_processing_step(
                    processing,
                    "smoothing",
                    {
                        "method": smooth_method,
                        "window_length": int(window_length),
                    },
                    analysis_type=token,
                )
                processing = update_processing_step(
                    processing,
                    "baseline",
                    {"method": baseline_method},
                    analysis_type=token,
                )
                processing = update_processing_step(
                    processing,
                    "normalization",
                    {"method": normalization_method},
                    analysis_type=token,
                )
                processing = update_processing_step(
                    processing,
                    "peak_detection",
                    {
                        "prominence": float(prominence),
                        "min_distance": int(min_distance),
                        "max_peaks": int(max_peaks),
                    },
                    analysis_type=token,
                )
                processing = update_processing_step(
                    processing,
                    "similarity_matching",
                    {
                        "metric": metric,
                        "top_n": int(top_n),
                        "minimum_score": float(min_score),
                    },
                    analysis_type=token,
                )
                state["processing"] = processing
                outcome = execute_batch_template(
                    dataset_key=selected_key,
                    dataset=dataset,
                    analysis_type=token,
                    workflow_template_id=workflow_template_id,
                    existing_processing=state.get("processing"),
                    analysis_history=st.session_state.get("analysis_history", []),
                    analyst_name=(st.session_state.get("branding", {}) or {}).get("analyst_name"),
                    app_version=APP_VERSION,
                    batch_run_id=f"{page_slug}_single_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                )

                status = outcome.get("status")
                if status == "saved":
                    st.session_state[state_key] = outcome.get("state") or {}
                    st.session_state[state_key]["processing"] = outcome.get("processing")
                    record = outcome.get("record")
                    if record:
                        st.session_state.setdefault("results", {})[record["id"]] = record
                        st.success(
                            tx(
                                "{analysis_type} sonucu kaydedildi: {result_id}",
                                "{analysis_type} result saved: {result_id}",
                                analysis_type=token,
                                result_id=record["id"],
                            )
                        )
                        _log_event(
                            tx("{analysis_type} Analizi Çalıştırıldı", "{analysis_type} Analysis Executed", analysis_type=token),
                            tx(
                                "{dataset} için {template} ile spektral aday eşleşmesi kaydedildi.",
                                "Saved spectral candidate matching for {dataset} using {template}.",
                                dataset=selected_key,
                                template=workflow_template_id,
                            ),
                            t(title_key),
                            dataset_key=selected_key,
                            result_id=record["id"],
                        )
                elif status == "blocked":
                    issues = "; ".join((outcome.get("validation") or {}).get("issues") or [])
                    st.error(
                        tx(
                            "{analysis_type} çalıştırması doğrulama tarafından bloklandı: {issues}",
                            "{analysis_type} run was blocked by validation: {issues}",
                            analysis_type=token,
                            issues=issues or tx("Bilinmeyen neden", "Unknown reason"),
                        )
                    )
                else:
                    failure_reason = (outcome.get("summary_row") or {}).get("failure_reason") or tx(
                        "Bilinmeyen hata", "Unknown error"
                    )
                    st.error(
                        tx(
                            "{analysis_type} çalıştırması başarısız oldu: {reason}",
                            "{analysis_type} run failed: {reason}",
                            analysis_type=token,
                            reason=failure_reason,
                        )
                    )
        with col_text:
            st.caption(
                tx(
                    "Bu panel smoothing/baseline/normalize/pik ve eşleşme parametrelerini tek çalıştırmada uygular.",
                    "This panel applies smoothing/baseline/normalization/peak and matching parameters in one run.",
                )
            )
            st.plotly_chart(
                _build_plot(selected_key, dataset, st.session_state.get(state_key, {}), token),
                use_container_width=True,
                config=PLOTLY_CONFIG,
                key=f"{page_slug}_pipeline_plot_{selected_key}",
            )

    with tab_processed:
        current = st.session_state.get(state_key, {})
        st.plotly_chart(
            _build_plot(selected_key, dataset, current, token),
            use_container_width=True,
            config=PLOTLY_CONFIG,
            key=f"{page_slug}_processed_plot_{selected_key}",
        )
        peaks = current.get("peaks") or []
        if peaks:
            st.subheader(tx("Tespit Edilen Pikler", "Detected Peaks"))
            st.dataframe(pd.DataFrame(peaks), use_container_width=True, hide_index=True)
        else:
            st.info(tx("Henüz pik tespit edilmedi.", "No peaks detected yet."))

    with tab_matches:
        current = st.session_state.get(state_key, {})
        matches = current.get("matches") or []
        top = matches[0] if matches else None
        c1, c2, c3 = st.columns(3)
        c1.metric(tx("Pik Sayısı", "Peak Count"), str(len(current.get("peaks") or [])))
        c2.metric(
            tx("En İyi Aday", "Top Candidate"),
            str(top.get("candidate_name")) if top else tx("Yok", "None"),
        )
        c3.metric(
            tx("Skor", "Score"),
            f"{float(top.get('normalized_score', 0.0)):.3f}" if top else "0.000",
        )
        if matches:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            tx("Sıra", "Rank"): item.get("rank"),
                            tx("Aday", "Candidate"): item.get("candidate_name"),
                            tx("Skor", "Score"): item.get("normalized_score"),
                            tx("Güven", "Confidence"): item.get("confidence_band"),
                            tx("Ortak Pik", "Shared Peaks"): (item.get("evidence") or {}).get("shared_peak_count"),
                        }
                        for item in matches
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info(tx("Henüz aday eşleşme yok.", "No candidate matches yet."))

    with tab_results:
        result_id = f"{page_slug}_{selected_key}"
        record = (st.session_state.get("results") or {}).get(result_id)
        if not record:
            st.info(
                tx(
                    "Kaydedilmiş sonuç bulunamadı. Parametreleri ayarlayıp Analizi Çalıştır butonunu kullanın.",
                    "No saved result found. Configure parameters and run analysis first.",
                )
            )
            return

        summary = record.get("summary") or {}
        st.markdown(f"**Result ID:** `{record.get('id')}`")
        st.markdown(f"**{tx('Durum', 'Status')}:** {record.get('status')}")
        if summary.get("caution_code"):
            st.warning(
                tx(
                    "Caution kodu: {code}",
                    "Caution code: {code}",
                    code=summary.get("caution_code"),
                )
            )
        summary_rows = [{"key": key, "value": value} for key, value in summary.items()]
        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
