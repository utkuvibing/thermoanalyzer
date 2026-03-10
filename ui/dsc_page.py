"""DSC Analysis page - Full DSC processing pipeline with interactive controls."""

import numpy as np
import streamlit as st

from core.preprocessing import smooth_signal, compute_derivative, normalize_by_mass
from core.baseline import correct_baseline, AVAILABLE_METHODS
from core.processing_schema import (
    ensure_processing_payload,
    get_workflow_templates,
    set_workflow_template,
    update_method_context,
    update_processing_step,
)
from core.provenance import build_calibration_reference_context, build_result_provenance
from core.peak_analysis import find_thermal_peaks, characterize_peaks
from core.dsc_processor import DSCProcessor
from core.result_serialization import serialize_dsc_result
from core.validation import validate_thermal_dataset
from ui.components.chrome import render_page_header
from ui.components.plot_builder import (
    create_dsc_plot,
    create_thermal_plot,
    fig_to_bytes,
    PLOTLY_CONFIG,
)
from ui.components.history_tracker import _log_event
from ui.components.quality_dashboard import render_quality_dashboard
from utils.diagnostics import record_exception
from utils.i18n import t, tx
from utils.license_manager import APP_VERSION
from utils.reference_data import render_reference_comparison
from utils.session_state import (
    advance_analysis_render_revision,
    init_analysis_state_history,
    push_analysis_undo_snapshot,
    redo_analysis_state,
    reset_analysis_state,
    undo_analysis_state,
)


def _chart_key(selected_key, slot, state):
    return f"dsc_chart_{selected_key}_{slot}_{state.get('_render_revision', 0)}"


def _plot_with_status(fig, status_text, *, chart_key):
    """Render a plotly chart followed by a status bar."""
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, key=chart_key)
    st.markdown(
        f'<div class="status-bar">{status_text}</div>',
        unsafe_allow_html=True,
    )


def _get_dsc_datasets():
    """Get datasets suitable for DSC analysis."""
    datasets = st.session_state.get("datasets", {})
    return {k: v for k, v in datasets.items() if v.data_type in ("DSC", "DTA", "UNKNOWN", "unknown")}


def _get_working_signal(state, raw_signal):
    if state.get("corrected") is not None:
        return state["corrected"]
    if state.get("smoothed") is not None:
        return state["smoothed"]
    return raw_signal


def _build_dsc_figure(selected_key, temperature, signal, state):
    """Build the canonical DSC figure used for exports."""
    working_signal = _get_working_signal(state, signal)
    fig = create_dsc_plot(
        temperature,
        working_signal,
        title=tx("DSC Analizi - {dataset}", "DSC Analysis - {dataset}", dataset=selected_key),
        baseline=state.get("baseline"),
        peaks=state.get("peaks"),
    )
    for tg in state.get("glass_transitions") or []:
        fig.add_vline(x=tg.tg_onset, line_dash="dot", line_color="#6B7280", opacity=0.5)
        fig.add_vline(x=tg.tg_midpoint, line_dash="dash", line_color="#0B5394", opacity=0.7)
        fig.add_vline(x=tg.tg_endset, line_dash="dot", line_color="#6B7280", opacity=0.5)
    return fig


def _select_dsc_reference_temperature(state):
    """Return the best available DSC event temperature for reference checking."""
    peaks = state.get("peaks") or []
    if peaks:
        return getattr(peaks[0], "peak_temperature", None)
    glass_transitions = state.get("glass_transitions") or []
    if glass_transitions:
        return getattr(glass_transitions[0], "tg_midpoint", None)
    return None


def _store_dsc_result(selected_key, dataset, temperature, signal, state):
    """Persist the normalized DSC result record and linked figure."""
    figures = st.session_state.setdefault("figures", {})
    figure_key = f"DSC Analysis - {selected_key}"
    figure_keys = []
    fig_save = _build_dsc_figure(selected_key, temperature, signal, state)
    try:
        figures[figure_key] = fig_to_bytes(fig_save)
        figure_keys.append(figure_key)
    except Exception:
        pass
    calibration_context = build_calibration_reference_context(
        dataset=dataset,
        analysis_type="DSC",
        reference_temperature_c=_select_dsc_reference_temperature(state),
    )
    processing_payload = update_method_context(
        state.get("processing"),
        calibration_context,
        analysis_type="DSC",
    )
    state["processing"] = processing_payload

    record = serialize_dsc_result(
        selected_key,
        dataset,
        state.get("peaks") or [],
        glass_transitions=state.get("glass_transitions") or [],
        artifacts={"figure_keys": figure_keys},
        processing=processing_payload,
        provenance=build_result_provenance(
            dataset=dataset,
            dataset_key=selected_key,
            analysis_history=st.session_state.get("analysis_history", []),
            app_version=APP_VERSION,
            analyst_name=(st.session_state.get("branding", {}) or {}).get("analyst_name"),
            extra={
                "calibration_state": calibration_context.get("calibration_state"),
                "reference_state": calibration_context.get("reference_state"),
                "reference_name": calibration_context.get("reference_name"),
                "reference_delta_c": calibration_context.get("reference_delta_c"),
            },
        ),
        validation=validate_thermal_dataset(dataset, analysis_type="DSC", processing=processing_payload),
        review={"commercial_scope": "stable_dsc"},
    )
    st.session_state.setdefault("results", {})[record["id"]] = record


def render():
    render_page_header(t("dsc.title"), t("dsc.caption"))

    dsc_datasets = _get_dsc_datasets()
    if not dsc_datasets:
        st.warning(tx("Henüz DSC verisi yüklenmedi. Veri seti yüklemek için **Veri Al** sayfasına gidin.", "No DSC datasets loaded. Go to **Import Runs** to load a dataset."))
        return

    selected_key = st.selectbox(tx("Veri Seti Seç", "Select Dataset"), list(dsc_datasets.keys()), key="dsc_dataset_select")
    dataset = dsc_datasets[selected_key]
    state_key = f"dsc_state_{selected_key}"
    default_state = {
        "smoothed": None,
        "baseline": None,
        "corrected": None,
        "peaks": None,
        "glass_transitions": [],
        "processing": ensure_processing_payload(analysis_type="DSC", workflow_template=tx("Genel DSC", "General DSC")),
    }
    if state_key not in st.session_state:
        st.session_state[state_key] = {
            "processor": None,
            **default_state,
        }
    state = st.session_state[state_key]
    init_analysis_state_history(state)
    state["processing"] = ensure_processing_payload(state.get("processing"), analysis_type="DSC")

    workflow_catalog = get_workflow_templates("DSC")
    workflow_labels = {entry["id"]: entry["label"] for entry in workflow_catalog}
    workflow_options = list(workflow_labels.keys())
    current_template = state["processing"].get("workflow_template_id")
    template_index = workflow_options.index(current_template) if current_template in workflow_options else 0
    workflow_template_id = st.selectbox(
        tx("İş Akışı Şablonu", "Workflow Template"),
        workflow_options,
        format_func=lambda template_id: workflow_labels.get(template_id, template_id),
        index=template_index,
        key=f"dsc_template_{selected_key}",
    )
    state["processing"] = set_workflow_template(
        state.get("processing"),
        workflow_template_id,
        analysis_type="DSC",
        workflow_template_label=workflow_labels.get(workflow_template_id),
    )

    dataset_validation = validate_thermal_dataset(dataset, analysis_type="DSC", processing=state.get("processing"))
    if dataset_validation["status"] == "fail":
        st.error(tx("Veri seti kararlı DSC iş akışına alınmadı: ", "Dataset is blocked from the stable DSC workflow: ") + "; ".join(dataset_validation["issues"]))
        return
    if dataset_validation["warnings"]:
        with st.expander(tx("Veri Doğrulama", "Dataset Validation"), expanded=False):
            for warning in dataset_validation["warnings"]:
                st.warning(warning)

    temperature = dataset.data["temperature"].values
    signal = dataset.data["signal"].values
    y_label = f"Heat Flow ({dataset.units.get('signal', 'mW')})"
    tracked_keys = tuple(default_state.keys())

    undo_count = len(state.get("_undo_stack", []))
    redo_count = len(state.get("_redo_stack", []))
    control_cols = st.columns([1, 1, 1, 3])
    with control_cols[0]:
        if st.button(tx("Geri Al", "Undo"), key=f"dsc_undo_{selected_key}", disabled=undo_count == 0):
            if undo_analysis_state(state, default_state):
                advance_analysis_render_revision(state)
                _log_event(
                    tx("İşlem Geri Alındı", "Undo Applied"),
                    tx("DSC görünümü bir önceki adıma döndürüldü.", "DSC view restored to the previous step."),
                    t("dsc.title"),
                    dataset_key=selected_key,
                )
                st.rerun()
    with control_cols[1]:
        if st.button(tx("İleri Al", "Redo"), key=f"dsc_redo_{selected_key}", disabled=redo_count == 0):
            if redo_analysis_state(state, default_state):
                advance_analysis_render_revision(state)
                _log_event(
                    tx("İşlem İleri Alındı", "Redo Applied"),
                    tx("DSC görünümü bir sonraki adıma taşındı.", "DSC view advanced to the next step."),
                    t("dsc.title"),
                    dataset_key=selected_key,
                )
                st.rerun()
    with control_cols[2]:
        if st.button(tx("Varsayılana Dön", "Reset to Default"), key=f"dsc_reset_{selected_key}"):
            if reset_analysis_state(state, default_state):
                advance_analysis_render_revision(state)
                _log_event(
                    tx("Varsayılana Dönüldü", "Reset to Default"),
                    tx("DSC işlem durumu temizlendi.", "DSC processing state was cleared."),
                    t("dsc.title"),
                    dataset_key=selected_key,
                )
                st.rerun()
    with control_cols[3]:
        st.caption(
            tx(
                "Geçmiş: {undo} geri alınabilir, {redo} ileri alınabilir.",
                "History: {undo} undo available, {redo} redo available.",
                undo=undo_count,
                redo=redo_count,
            )
        )

    tab_raw, tab_smooth, tab_baseline, tab_tg, tab_peaks, tab_results = st.tabs(
        [
            tx("Ham Veri", "Raw Data"),
            tx("Yumuşatma", "Smoothing"),
            tx("Baz Çizgisi Düzeltmesi", "Baseline Correction"),
            tx("Cam Geçişi (Tg)", "Glass Transition (Tg)"),
            tx("Pik Analizi", "Peak Analysis"),
            tx("Sonuç Özeti", "Results Summary"),
        ]
    )

    with tab_raw:
        st.subheader(tx("Ham DSC Verisi", "Raw DSC Data"))

        fig = create_thermal_plot(
            temperature,
            signal,
            title=tx("Ham DSC - {name}", "Raw DSC - {name}", name=dataset.metadata.get("file_name", "")),
            y_label=y_label,
        )
        _plot_with_status(
            fig,
            tx(
                "Aralık: {t_min:.1f} – {t_max:.1f} °C &nbsp;│&nbsp; Nokta: {points}",
                "Range: {t_min:.1f} – {t_max:.1f} °C &nbsp;│&nbsp; Points: {points}",
                t_min=float(temperature.min()),
                t_max=float(temperature.max()),
                points=f"{len(temperature):,}",
            ),
            chart_key=_chart_key(selected_key, "raw", state),
        )

        render_quality_dashboard(temperature, signal, key_prefix=f"dsc_qd_{selected_key}")

        col1, col2 = st.columns(2)
        with col1:
            mass = dataset.metadata.get("sample_mass")
            if mass and mass > 0:
                st.info(tx("Numune kütlesi: {mass} mg", "Sample mass: {mass} mg", mass=mass))
                if st.checkbox(tx("Kütleye göre normalize et", "Normalize by mass"), key="dsc_normalize"):
                    normalize_by_mass(signal, mass)
                    st.success(tx("Sinyal işleme ve dışa aktarım akışlarında kütleye göre normalize edilebilir.", "Signal can be normalized during processing/export workflows."))

        with col2:
            st.write(f"**{tx('Sıcaklık aralığı', 'Temperature range')}:** {temperature.min():.1f} - {temperature.max():.1f} °C")
            st.write(f"**{tx('Veri noktası', 'Data points')}:** {len(temperature)}")

    with tab_smooth:
        st.subheader(tx("Sinyal Yumuşatma", "Signal Smoothing"))

        col1, col2 = st.columns([1, 3])

        with col1:
            smooth_method = st.selectbox(
                tx("Yumuşatma Yöntemi", "Smoothing Method"),
                ["savgol", "moving_average", "gaussian"],
                key="dsc_smooth_method",
                help=tx("Savitzky-Golay pik şeklini en iyi korur. Hareketli ortalama en basit seçenektir. Gaussian çok gürültülü veri için uygundur.", "Savitzky-Golay preserves peak shape best. Moving average is simplest. Gaussian is good for very noisy data."),
            )

            if smooth_method == "savgol":
                window = st.slider(
                    tx("Pencere Uzunluğu", "Window Length"),
                    5,
                    51,
                    11,
                    step=2,
                    key="dsc_sg_window",
                    help=tx("Yumuşatma penceresindeki nokta sayısı. Daha büyük değerler eğriyi daha fazla yumuşatır ancak dar pikleri bozabilir.", "Number of points in the smoothing window. Larger values give smoother curves but may distort narrow peaks."),
                )
                polyorder = st.slider(
                    tx("Polinom Derecesi", "Polynomial Order"),
                    1,
                    7,
                    3,
                    key="dsc_sg_poly",
                    help=tx("Savitzky-Golay uyumu için polinom derecesi. Daha yüksek dereceler keskin özellikleri daha iyi izler ama daha az yumuşatır.", "Polynomial degree for Savitzky-Golay fit. Higher orders follow sharp features better but smooth less."),
                )
                smooth_kwargs = {"window_length": window, "polyorder": polyorder}
            elif smooth_method == "moving_average":
                window = st.slider(
                    tx("Pencere Boyutu", "Window Size"),
                    3,
                    51,
                    11,
                    step=2,
                    key="dsc_ma_window",
                    help=tx("Ortalaması alınacak nokta sayısı. Daha büyük pencereler daha yumuşak sonuç verir.", "Number of points averaged. Larger windows give smoother results."),
                )
                smooth_kwargs = {"window": window}
            else:
                sigma = st.slider(
                    tx("Sigma", "Sigma"),
                    0.5,
                    10.0,
                    2.0,
                    step=0.5,
                    key="dsc_gauss_sigma",
                    help=tx("Gaussian çekirdeğinin standart sapması. Daha yüksek değerler daha agresif yumuşatma uygular.", "Standard deviation of the Gaussian kernel. Higher values smooth more aggressively."),
                )
                smooth_kwargs = {"sigma": sigma}

            if st.button(tx("Yumuşatmayı Uygula", "Apply Smoothing"), key="dsc_apply_smooth"):
                smoothed = smooth_signal(signal, method=smooth_method, **smooth_kwargs)
                push_analysis_undo_snapshot(state, tracked_keys)
                state["smoothed"] = smoothed
                state["baseline"] = None
                state["corrected"] = None
                state["peaks"] = None
                state["glass_transitions"] = []
                state["processing"] = update_processing_step(
                    state.get("processing"),
                    "smoothing",
                    {"method": smooth_method, **smooth_kwargs},
                    analysis_type="DSC",
                )
                advance_analysis_render_revision(state)
                _log_event(
                    tx("Yumuşatma Uygulandı", "Smoothing Applied"),
                    f"{tx('Yöntem', 'Method')}: {smooth_method}",
                    t("dsc.title"),
                    dataset_key=selected_key,
                    parameters={"method": smooth_method, **smooth_kwargs},
                )
                st.success(tx("Yumuşatma uygulandı.", "Smoothing applied."))

        with col2:
            fig = create_dsc_plot(
                temperature,
                signal,
                title=tx("Yumuşatılmış DSC", "Smoothed DSC"),
                y_label=y_label,
                smoothed=state.get("smoothed"),
            )
            st.plotly_chart(
                fig,
                use_container_width=True,
                config=PLOTLY_CONFIG,
                key=_chart_key(selected_key, "smoothing", state),
            )

        if st.checkbox(tx("Türevi Göster", "Show Derivative"), key="dsc_show_deriv"):
            working_signal = state.get("smoothed") if state.get("smoothed") is not None else signal
            deriv = compute_derivative(temperature, working_signal, smooth_first=False)
            fig_d = create_thermal_plot(
                temperature,
                deriv,
                title=tx("dHF/dT (Birinci Türev)", "dHF/dT (First Derivative)"),
                y_label=tx("dHF/dT", "dHF/dT"),
                color="#2EC4B6",
            )
            st.plotly_chart(
                fig_d,
                use_container_width=True,
                config=PLOTLY_CONFIG,
                key=_chart_key(selected_key, "smoothing_derivative", state),
            )

    with tab_baseline:
        st.subheader(tx("Baz Çizgisi Düzeltmesi", "Baseline Correction"))

        col1, col2 = st.columns([1, 3])

        with col1:
            baseline_method = st.selectbox(
                tx("Baz Çizgisi Yöntemi", "Baseline Method"),
                list(AVAILABLE_METHODS.keys()),
                format_func=lambda x: f"{x} - {AVAILABLE_METHODS[x]}",
                key="dsc_baseline_method",
                help=tx("ASLS ve AirPLS çoğu DSC verisinde iyi çalışır. Polinom yöntemleri basit baz çizgileri için uygundur. SNIP karmaşık arka planlarda daha dayanıklıdır.", "ASLS and AirPLS work well for most DSC data. Polynomial methods suit simple baselines. SNIP is robust for complex backgrounds."),
            )

            bl_kwargs = {}
            if baseline_method in ("asls", "airpls"):
                lam = st.number_input(tx("Lambda (yumuşaklık)", "Lambda (smoothness)"), value=1e6, format="%.0e", key="dsc_bl_lam")
                bl_kwargs["lam"] = lam
                if baseline_method == "asls":
                    p = st.number_input(tx("Asimetri (p)", "Asymmetry (p)"), value=0.01, format="%.3f", key="dsc_bl_p")
                    bl_kwargs["p"] = p
            elif baseline_method in ("modpoly", "imodpoly"):
                poly_order = st.slider(tx("Polinom Derecesi", "Polynomial Order"), 1, 10, 6, key="dsc_bl_poly")
                bl_kwargs["poly_order"] = poly_order
            elif baseline_method == "snip":
                max_hw = st.slider(tx("Maksimum Yarım Pencere", "Max Half Window"), 5, 100, 40, key="dsc_bl_snip")
                bl_kwargs["max_half_window"] = max_hw

            use_region = st.checkbox(tx("Bölgeyle sınırla", "Restrict to region"), key="dsc_bl_region")
            region = None
            if use_region:
                r_min = st.number_input(tx("Bölge minimumu (°C)", "Region min (°C)"), value=float(temperature.min()), key="dsc_bl_rmin")
                r_max = st.number_input(tx("Bölge maksimumu (°C)", "Region max (°C)"), value=float(temperature.max()), key="dsc_bl_rmax")
                region = (r_min, r_max)

            if st.button(tx("Baz Çizgisi Düzeltmesini Uygula", "Apply Baseline Correction"), key="dsc_apply_bl"):
                working_signal = state.get("smoothed") if state.get("smoothed") is not None else signal
                try:
                    corrected, baseline = correct_baseline(
                        temperature,
                        working_signal,
                        method=baseline_method,
                        region=region,
                        **bl_kwargs,
                    )
                    push_analysis_undo_snapshot(state, tracked_keys)
                    state["baseline"] = baseline
                    state["corrected"] = corrected
                    state["peaks"] = None
                    state["glass_transitions"] = []
                    state["processing"] = update_processing_step(
                        state.get("processing"),
                        "baseline",
                        {
                            "method": baseline_method,
                            "region": region,
                            **bl_kwargs,
                        },
                        analysis_type="DSC",
                    )
                    advance_analysis_render_revision(state)
                    _log_event(
                        tx("Baz Çizgisi Düzeltildi", "Baseline Corrected"),
                        f"{tx('Yöntem', 'Method')}: {baseline_method}",
                        t("dsc.title"),
                        dataset_key=selected_key,
                        parameters={"method": baseline_method, "region": region, **bl_kwargs},
                    )
                    st.success(tx("Baz çizgisi düzeltmesi uygulandı ({method}).", "Baseline correction applied ({method})", method=baseline_method))
                except Exception as exc:
                    error_id = record_exception(
                        st.session_state,
                        area="dsc_analysis",
                        action="baseline_correction",
                        message="DSC baseline correction failed.",
                        context={"dataset_key": selected_key, "method": baseline_method},
                        exception=exc,
                    )
                    st.error(tx("Baz çizgisi düzeltmesi başarısız oldu: {error}", "Baseline correction failed: {error}", error=f"{exc} (Error ID: {error_id})"))

        with col2:
            working_signal = state.get("smoothed") if state.get("smoothed") is not None else signal
            fig = create_dsc_plot(
                temperature,
                working_signal,
                title=tx("Baz Çizgisi Düzeltmesi", "Baseline Correction"),
                y_label=y_label,
                baseline=state.get("baseline"),
            )
            st.plotly_chart(
                fig,
                use_container_width=True,
                config=PLOTLY_CONFIG,
                key=_chart_key(selected_key, "baseline", state),
            )

            if state.get("corrected") is not None:
                fig2 = create_thermal_plot(
                    temperature,
                    state["corrected"],
                    title=tx("Baz Çizgisi Düzeltilmiş Sinyal", "Baseline-Corrected Signal"),
                    y_label=tx("Düzeltilmiş {label}", "Corrected {label}", label=y_label),
                    color="#2EC4B6",
                )
                st.plotly_chart(
                    fig2,
                    use_container_width=True,
                    config=PLOTLY_CONFIG,
                    key=_chart_key(selected_key, "baseline_corrected", state),
                )

    with tab_tg:
        st.subheader(tx("Cam Geçişi Tespiti", "Glass Transition Detection"))
        st.caption(tx("Mevcut DSC çalışma sinyalini kullanarak Tg başlangıç, orta nokta, bitiş ve ΔCp değerlerini tahmin edin.", "Use the current working DSC signal to estimate Tg onset, midpoint, endset, and ΔCp."))

        col1, col2 = st.columns([1, 3])
        working_signal = _get_working_signal(state, signal)

        with col1:
            st.write(f"**{tx('Arama seçenekleri', 'Search options')}**")
            use_region = st.checkbox(tx("Tg arama bölgesini sınırla", "Restrict Tg search region"), key="dsc_tg_region")
            tg_region = None
            if use_region:
                tg_min = st.number_input(tx("Tg bölgesi minimumu (°C)", "Tg region min (°C)"), value=float(temperature.min()), key="dsc_tg_rmin")
                tg_max = st.number_input(tx("Tg bölgesi maksimumu (°C)", "Tg region max (°C)"), value=float(temperature.max()), key="dsc_tg_rmax")
                tg_region = (tg_min, tg_max)

            if st.button(tx("Tg Tespit Et", "Detect Tg"), key="dsc_detect_tg"):
                try:
                    processor = DSCProcessor(
                        temperature,
                        working_signal,
                        sample_mass=dataset.metadata.get("sample_mass"),
                        heating_rate=dataset.metadata.get("heating_rate"),
                    )
                    processor.detect_glass_transition(region=tg_region)
                    glass_transitions = processor.get_result().glass_transitions
                    push_analysis_undo_snapshot(state, tracked_keys)
                    state["glass_transitions"] = glass_transitions
                    state["processing"] = update_processing_step(
                        state.get("processing"),
                        "glass_transition",
                        {"region": tg_region, "event_count": len(glass_transitions)},
                        analysis_type="DSC",
                    )
                    advance_analysis_render_revision(state)
                    _log_event(
                        tx("Cam Geçişi Tespit Edildi", "Glass Transition Detected"),
                        tx("{count} Tg olayı", "{count} Tg event(s)", count=len(glass_transitions)),
                        t("dsc.title"),
                        dataset_key=selected_key,
                        parameters={"region": tg_region, "event_count": len(glass_transitions)},
                    )
                    if glass_transitions:
                        st.success(tx("{count} Tg olayı tespit edildi.", "Detected {count} Tg event(s).", count=len(glass_transitions)))
                    else:
                        st.info(tx("Geçerli sinyal/bölge için Tg olayı tespit edilmedi.", "No Tg event was detected for the current signal/region."))
                except Exception as exc:
                    error_id = record_exception(
                        st.session_state,
                        area="dsc_analysis",
                        action="glass_transition_detection",
                        message="DSC Tg detection failed.",
                        context={"dataset_key": selected_key, "region": tg_region},
                        exception=exc,
                    )
                    st.error(tx("Tg tespiti başarısız oldu: {error}", "Tg detection failed: {error}", error=f"{exc} (Error ID: {error_id})"))

        with col2:
            fig_tg = create_thermal_plot(
                temperature,
                working_signal,
                title=tx("Cam Geçişi Görünümü", "Glass Transition View"),
                y_label=tx("Sinyal", "Signal"),
            )
            for tg in state.get("glass_transitions") or []:
                fig_tg.add_vline(x=tg.tg_onset, line_dash="dot", line_color="#6B7280", annotation_text=tx("Başlangıç {value:.1f}°C", "Onset {value:.1f}°C", value=tg.tg_onset))
                fig_tg.add_vline(x=tg.tg_midpoint, line_dash="dash", line_color="#0B5394", annotation_text=tx("Tg {value:.1f}°C", "Tg {value:.1f}°C", value=tg.tg_midpoint))
                fig_tg.add_vline(x=tg.tg_endset, line_dash="dot", line_color="#6B7280", annotation_text=tx("Bitiş {value:.1f}°C", "Endset {value:.1f}°C", value=tg.tg_endset))
            st.plotly_chart(
                fig_tg,
                use_container_width=True,
                config=PLOTLY_CONFIG,
                key=_chart_key(selected_key, "tg", state),
            )

        if state.get("glass_transitions"):
            st.subheader(tx("Tespit Edilen Tg Olayları", "Detected Tg Events"))
            for index, tg in enumerate(state["glass_transitions"], start=1):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric(f"Tg {index}", f"{tg.tg_midpoint:.1f} °C")
                c2.metric(tx("Başlangıç", "Onset"), f"{tg.tg_onset:.1f} °C")
                c3.metric(tx("Bitiş", "Endset"), f"{tg.tg_endset:.1f} °C")
                c4.metric("ΔCp", f"{tg.delta_cp:.3f}")

    with tab_peaks:
        st.subheader(tx("Pik Tespiti ve Karakterizasyonu", "Peak Detection & Characterization"))

        col1, col2 = st.columns([1, 3])

        with col1:
            working = state.get("corrected")
            if working is None:
                working = state.get("smoothed") if state.get("smoothed") is not None else signal
                st.info(tx("Ham/yumuşatılmış sinyal kullanılıyor. Daha iyi sonuç için baz çizgisi düzeltmesi uygulayın.", "Using raw/smoothed signal. Apply baseline correction for better results."))

            direction = st.selectbox(
                tx("Pik Yönü", "Peak Direction"),
                [
                    tx("her ikisi", "both"),
                    tx("yukarı (endotermik)", "up (endotherm)"),
                    tx("aşağı (ekzotermik)", "down (exotherm)"),
                ],
                key="dsc_peak_dir",
                help=tx("Hangi yöndeki piklerin tespit edileceğini seçin. 'Her ikisi' hem endotermik hem ekzotermik olayları bulur.", "Select which direction of peaks to detect. 'Both' finds endothermic and exothermic events."),
            )
            dir_map = {
                tx("her ikisi", "both"): "both",
                tx("yukarı (endotermik)", "up (endotherm)"): "up",
                tx("aşağı (ekzotermik)", "down (exotherm)"): "down",
            }

            prominence = st.number_input(
                tx("Minimum Belirginlik (0=otomatik)", "Min Prominence (0=auto)"),
                value=0.0,
                format="%.3f",
                key="dsc_peak_prom",
                help=tx("Bir pik ile çevresindeki vadiler arasındaki minimum yükseklik farkı. Otomatik eşik için 0 kullanın (sinyal aralığının %5'i).", "Minimum height difference between a peak and its surrounding valleys. Set to 0 for automatic threshold (5% of signal range)."),
            )
            min_distance = st.number_input(
                tx("Minimum Mesafe (nokta, 0=otomatik)", "Min Distance (points, 0=auto)"),
                value=0,
                step=1,
                key="dsc_peak_dist",
                help=tx("Komşu pikler arasında gereken minimum veri noktası sayısı. Gürültünün ayrı pik olarak algılanmasını önlemek için artırın.", "Minimum number of data points between adjacent peaks. Increase to avoid detecting noise as separate peaks."),
            )

            if st.button(tx("Pikleri Bul", "Find Peaks"), key="dsc_find_peaks"):
                kwargs = {"direction": dir_map[direction]}
                if prominence > 0:
                    kwargs["prominence"] = prominence
                if min_distance > 0:
                    kwargs["distance"] = min_distance

                try:
                    peaks = find_thermal_peaks(temperature, working, **kwargs)
                    baseline_for_peaks = np.zeros_like(working) if state.get("corrected") is not None else state.get("baseline")
                    peaks = characterize_peaks(temperature, working, peaks, baseline=baseline_for_peaks)
                    push_analysis_undo_snapshot(state, tracked_keys)
                    state["peaks"] = peaks
                    state["processing"] = update_processing_step(
                        state.get("processing"),
                        "peak_detection",
                        {"peak_count": len(peaks), **kwargs},
                        analysis_type="DSC",
                    )
                    advance_analysis_render_revision(state)
                    _log_event(
                        tx("Pikler Tespit Edildi", "Peaks Detected"),
                        tx("{count} pik bulundu", "{count} peak(s) found", count=len(peaks)),
                        t("dsc.title"),
                        dataset_key=selected_key,
                        parameters={"peak_count": len(peaks), **kwargs},
                    )
                    st.success(tx("{count} pik bulundu.", "Found {count} peak(s)", count=len(peaks)))
                except Exception as exc:
                    error_id = record_exception(
                        st.session_state,
                        area="dsc_analysis",
                        action="peak_detection",
                        message="DSC peak detection failed.",
                        context={"dataset_key": selected_key, "direction": dir_map[direction]},
                        exception=exc,
                    )
                    st.error(tx("Pik tespiti başarısız oldu: {error}", "Peak detection failed: {error}", error=f"{exc} (Error ID: {error_id})"))

        with col2:
            fig = create_dsc_plot(
                temperature,
                working,
                title=tx("Pik Analizi", "Peak Analysis"),
                y_label=y_label,
                baseline=state.get("baseline"),
                peaks=state.get("peaks"),
            )
            st.plotly_chart(
                fig,
                use_container_width=True,
                config=PLOTLY_CONFIG,
                key=_chart_key(selected_key, "peaks", state),
            )

        if state.get("peaks"):
            st.subheader(tx("Pik Sonuçları", "Peak Results"))
            import pandas as pd

            rows = []
            for i, peak in enumerate(state["peaks"]):
                rows.append(
                    {
                        tx("Pik #", "Peak #"): i + 1,
                        tx("Tip", "Type"): peak.peak_type,
                        tx("Pik T (°C)", "Peak T (°C)"): f"{peak.peak_temperature:.2f}",
                        tx("Başlangıç T (°C)", "Onset T (°C)"): f"{peak.onset_temperature:.2f}" if peak.onset_temperature is not None else tx("Yok", "N/A"),
                        tx("Bitiş T (°C)", "Endset T (°C)"): f"{peak.endset_temperature:.2f}" if peak.endset_temperature is not None else tx("Yok", "N/A"),
                        tx("Alan (J/g)", "Area (J/g)"): f"{peak.area:.3f}" if peak.area is not None else tx("Yok", "N/A"),
                        tx("FWHM (°C)", "FWHM (°C)"): f"{peak.fwhm:.2f}" if peak.fwhm is not None else tx("Yok", "N/A"),
                        tx("Yükseklik", "Height"): f"{peak.height:.4f}" if peak.height is not None else tx("Yok", "N/A"),
                    }
                )
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with tab_results:
        st.subheader(tx("Analiz Özeti", "Analysis Summary"))

        peaks = state.get("peaks") or []
        glass_transitions = state.get("glass_transitions") or []
        if not peaks and not glass_transitions:
            st.info(tx("Burada sonuç görmek için önce pik analizi veya Tg tespiti çalıştırın.", "Run peak analysis or Tg detection first to see results here."))
            return

        st.markdown(f"**{tx('Veri Seti', 'Dataset')}:** {dataset.metadata.get('file_name', selected_key)}")
        st.markdown(f"**{tx('Numune', 'Sample')}:** {dataset.metadata.get('sample_name', tx('Yok', 'N/A'))}")
        if dataset.metadata.get("sample_mass"):
            st.markdown(f"**{tx('Kütle', 'Mass')}:** {dataset.metadata['sample_mass']} mg")
        if dataset.metadata.get("heating_rate"):
            st.markdown(f"**{tx('Isıtma Hızı', 'Heating Rate')}:** {dataset.metadata['heating_rate']} °C/min")

        st.divider()

        if glass_transitions:
            st.markdown(f"### {tx('Cam Geçişi', 'Glass Transition')}")
            for index, tg in enumerate(glass_transitions, start=1):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric(f"Tg {index}", f"{tg.tg_midpoint:.1f} °C")
                c2.metric(tx("Başlangıç", "Onset"), f"{tg.tg_onset:.1f} °C")
                c3.metric(tx("Bitiş", "Endset"), f"{tg.tg_endset:.1f} °C")
                c4.metric("ΔCp", f"{tg.delta_cp:.3f}")
            st.divider()

        if peaks:
            for i, peak in enumerate(peaks):
                with st.container():
                    st.markdown(f"### {tx('Pik', 'Peak')} {i + 1} ({peak.peak_type})")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric(tx("Pik Sıcaklığı", "Peak Temp"), f"{peak.peak_temperature:.1f} °C")
                    c2.metric(tx("Başlangıç", "Onset"), f"{peak.onset_temperature:.1f} °C" if peak.onset_temperature is not None else tx("Yok", "N/A"))
                    c3.metric(tx("Entalpi", "Enthalpy"), f"{peak.area:.2f} J/g" if peak.area is not None else tx("Yok", "N/A"))
                    c4.metric("FWHM", f"{peak.fwhm:.1f} °C" if peak.fwhm is not None else tx("Yok", "N/A"))
                    ref_info = render_reference_comparison(peak.peak_temperature, "DSC")
                    if ref_info:
                        st.markdown(ref_info)

            st.divider()

        if st.button(tx("Sonuçları Oturuma Kaydet", "Save Results to Session"), key="dsc_save_results"):
            try:
                _store_dsc_result(selected_key, dataset, temperature, signal, state)
                _log_event(tx("Sonuçlar Kaydedildi", "Results Saved"), tx("Kararlı DSC sonucu kaydedildi", "Stable DSC result saved"), t("dsc.title"), dataset_key=selected_key, result_id=f"dsc_{selected_key}")
                st.success(tx("Kararlı DSC sonuçları kaydedildi. İndirmek için Rapor Merkezi'ne gidin.", "Stable DSC results saved. Go to Report Center to download."))
            except Exception as exc:
                error_id = record_exception(
                    st.session_state,
                    area="dsc_analysis",
                    action="save_results",
                    message="Saving DSC results failed.",
                    context={"dataset_key": selected_key},
                    exception=exc,
                )
                st.error(tx("DSC sonuçları kaydedilemedi: {error}", "Saving DSC results failed: {error}", error=f"{exc} (Error ID: {error_id})"))
