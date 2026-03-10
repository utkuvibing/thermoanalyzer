"""DTA Analysis page - Full DTA processing pipeline with interactive controls.

Tabs:
    Raw Data           - DTA curve (delta-T vs temperature) with dataset info.
    Smoothing          - Apply smoothing and inspect the derivative.
    Baseline Correction - Remove instrumental drift; visualise corrected signal.
    Peak Analysis      - Detect exothermic / endothermic events with DTAProcessor.
    Results Summary    - Metric cards for all detected peaks; save to session.
"""

import streamlit as st
import numpy as np
import pandas as pd

from core.preprocessing import smooth_signal, compute_derivative
from core.baseline import correct_baseline, AVAILABLE_METHODS
from core.peak_analysis import find_thermal_peaks, characterize_peaks
from core.dta_processor import DTAProcessor, DTAResult
from core.processing_schema import ensure_processing_payload, update_processing_step
from core.result_serialization import serialize_dta_result
from core.validation import validate_thermal_dataset
from ui.components.plot_builder import create_dta_plot, create_thermal_plot, fig_to_bytes, PLOTLY_CONFIG
from ui.components.history_tracker import _log_event
from ui.components.quality_dashboard import render_quality_dashboard
from utils.reference_data import render_reference_comparison
from utils.i18n import tx
from utils.session_state import (
    advance_analysis_render_revision,
    init_analysis_state_history,
    push_analysis_undo_snapshot,
    redo_analysis_state,
    reset_analysis_state,
    undo_analysis_state,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chart_key(selected_key, slot, state):
    return f"dta_chart_{selected_key}_{slot}_{state.get('_render_revision', 0)}"


def _plot_with_status(fig, status_text, *, chart_key):
    """Render a plotly chart followed by a status bar."""
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, key=chart_key)
    st.markdown(
        f'<div class="status-bar">{status_text}</div>',
        unsafe_allow_html=True,
    )


def _get_dta_datasets():
    """Return datasets suitable for DTA analysis (DTA type or unknown)."""
    datasets = st.session_state.get("datasets", {})
    return {k: v for k, v in datasets.items() if v.data_type in ("DTA", "unknown")}


def _format_opt(value, fmt=".2f", suffix=""):
    """Format an optional float; return 'N/A' when None."""
    if value is None:
        return "N/A"
    return f"{value:{fmt}}{suffix}"


def _store_dta_result(selected_key, dataset, temperature, signal, state):
    """Persist an experimental DTA result record."""
    figures = st.session_state.setdefault("figures", {})
    figure_key = f"DTA Analysis - {selected_key}"
    figure_keys = []
    display_signal = state["corrected"] if state.get("corrected") is not None else state["smoothed"] if state.get("smoothed") is not None else signal
    fig_save = create_dta_plot(
        temperature,
        display_signal,
        title=tx("DTA Analizi - {dataset}", "DTA Analysis - {dataset}", dataset=selected_key),
        baseline=state.get("baseline"),
        peaks=state.get("peaks"),
    )
    try:
        figures[figure_key] = fig_to_bytes(fig_save)
        figure_keys.append(figure_key)
    except Exception:
        pass

    processing_payload = ensure_processing_payload(
        state.get("processing"),
        analysis_type="DTA",
        workflow_template="dta.general",
    )
    if state.get("smoothed") is not None:
        processing_payload = update_processing_step(
            processing_payload,
            "smoothing",
            {"status": "applied"},
            analysis_type="DTA",
        )
    if state.get("baseline") is not None:
        processing_payload = update_processing_step(
            processing_payload,
            "baseline",
            {"status": "applied"},
            analysis_type="DTA",
        )
    if state.get("peaks"):
        processing_payload = update_processing_step(
            processing_payload,
            "peak_detection",
            {"peak_count": len(state.get("peaks") or [])},
            analysis_type="DTA",
        )
    state["processing"] = processing_payload

    record = serialize_dta_result(
        selected_key,
        dataset,
        state.get("peaks") or [],
        artifacts={"figure_keys": figure_keys},
        processing=processing_payload,
        validation=validate_thermal_dataset(dataset, analysis_type="DTA", processing=processing_payload),
        review={"commercial_scope": "preview_dta"},
    )
    st.session_state.setdefault("results", {})[record["id"]] = record


# ---------------------------------------------------------------------------
# render()
# ---------------------------------------------------------------------------

def render():
    st.title(tx("DTA Analizi", "DTA Analysis"))
    st.warning(
        tx(
            "Deneysel modül: DTA sonuçları kullanılabilir, ancak bu iş akışı proje kalıcılığı ve raporlama için Faz 1 kararlılık garantisinin dışındadır.",
            "Experimental module: DTA results remain available, but this workflow is outside the Phase 1 stability guarantee for project persistence and reporting.",
        )
    )

    dta_datasets = _get_dta_datasets()
    if not dta_datasets:
        st.warning(
            tx("Henüz DTA veri seti yüklenmedi. Veri yüklemek için **Veri Al** sayfasına gidin.", "No DTA datasets loaded. Go to the **Import Runs** page to load data.")
        )
        return

    # Dataset selection
    selected_key = st.selectbox(
        tx("Veri Seti Seç", "Select Dataset"),
        list(dta_datasets.keys()),
        key="dta_dataset_select",
    )
    dataset = dta_datasets[selected_key]

    temperature = dataset.data["temperature"].values
    signal = dataset.data["signal"].values

    # Initialise per-dataset processing state
    state_key = f"dta_state_{selected_key}"
    default_state = {
        "smoothed": None,
        "baseline": None,
        "corrected": None,
        "peaks": None,
        "processing": ensure_processing_payload(analysis_type="DTA", workflow_template="dta.general"),
    }
    if state_key not in st.session_state:
        st.session_state[state_key] = dict(default_state)
    state = st.session_state[state_key]
    init_analysis_state_history(state)
    state["processing"] = ensure_processing_payload(state.get("processing"), analysis_type="DTA")
    tracked_keys = tuple(default_state.keys())

    # y-axis label: DTA uses delta-T in µV
    y_label = f"\u0394T ({dataset.units.get('signal', '\u00b5V')})"

    undo_count = len(state.get("_undo_stack", []))
    redo_count = len(state.get("_redo_stack", []))
    control_cols = st.columns([1, 1, 1, 3])
    with control_cols[0]:
        if st.button(tx("Geri Al", "Undo"), key=f"dta_undo_{selected_key}", disabled=undo_count == 0):
            if undo_analysis_state(state, default_state):
                advance_analysis_render_revision(state)
                _log_event(
                    tx("İşlem Geri Alındı", "Undo Applied"),
                    tx("DTA görünümü bir önceki adıma döndürüldü.", "DTA view restored to the previous step."),
                    tx("DTA Analizi", "DTA Analysis"),
                    dataset_key=selected_key,
                )
                st.rerun()
    with control_cols[1]:
        if st.button(tx("İleri Al", "Redo"), key=f"dta_redo_{selected_key}", disabled=redo_count == 0):
            if redo_analysis_state(state, default_state):
                advance_analysis_render_revision(state)
                _log_event(
                    tx("İşlem İleri Alındı", "Redo Applied"),
                    tx("DTA görünümü bir sonraki adıma taşındı.", "DTA view advanced to the next step."),
                    tx("DTA Analizi", "DTA Analysis"),
                    dataset_key=selected_key,
                )
                st.rerun()
    with control_cols[2]:
        if st.button(tx("Varsayılana Dön", "Reset to Default"), key=f"dta_reset_{selected_key}"):
            if reset_analysis_state(state, default_state):
                advance_analysis_render_revision(state)
                _log_event(
                    tx("Varsayılana Dönüldü", "Reset to Default"),
                    tx("DTA işlem durumu temizlendi.", "DTA processing state was cleared."),
                    tx("DTA Analizi", "DTA Analysis"),
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

    # Build tabs
    tab_raw, tab_smooth, tab_baseline, tab_peaks, tab_results = st.tabs(
        [
            tx("Ham Veri", "Raw Data"),
            tx("Yumuşatma", "Smoothing"),
            tx("Baz Çizgisi Düzeltmesi", "Baseline Correction"),
            tx("Pik Analizi", "Peak Analysis"),
            tx("Sonuç Özeti", "Results Summary"),
        ]
    )

    # =========================================================================
    # TAB 1 - RAW DATA
    # =========================================================================
    with tab_raw:
        st.subheader(tx("Ham DTA Verisi", "Raw DTA Data"))

        fig = create_dta_plot(
            temperature,
            signal,
            title=tx("Ham DTA - {name}", "Raw DTA - {name}", name=dataset.metadata.get("file_name", "")),
        )
        _plot_with_status(
            fig,
                tx(
                    "Aralık: {t_min:.1f} – {t_max:.1f} °C &nbsp;│&nbsp; Nokta: {points} &nbsp;│&nbsp; ΔT p-p: {delta:.4f}",
                    "Range: {t_min:.1f} – {t_max:.1f} °C &nbsp;│&nbsp; Points: {points} &nbsp;│&nbsp; ΔT p-p: {delta:.4f}",
                    t_min=float(temperature.min()),
                    t_max=float(temperature.max()),
                    points=f"{len(temperature):,}",
                    delta=float(signal.max() - signal.min()),
                ),
            chart_key=_chart_key(selected_key, "raw", state),
        )

        render_quality_dashboard(temperature, signal, key_prefix=f"dta_qd_{selected_key}")

        col_info, col_meta = st.columns(2)

        with col_info:
            st.write(
                f"**{tx('Sıcaklık aralığı', 'Temperature range')}:** "
                f"{temperature.min():.1f} - {temperature.max():.1f} °C"
            )
            st.write(f"**{tx('Veri noktası', 'Data points')}:** {len(temperature)}")
            sig_range = signal.max() - signal.min()
            st.write(f"**{tx('Sinyal tepe-tepe değeri', 'Signal peak-to-peak')}:** {sig_range:.4f}")

        with col_meta:
            st.write(f"**{tx('Numune', 'Sample')}:** {dataset.metadata.get('sample_name', tx('Yok', 'N/A'))}")
            if dataset.metadata.get("sample_mass"):
                st.write(f"**{tx('Kütle', 'Mass')}:** {dataset.metadata['sample_mass']} mg")
            if dataset.metadata.get("heating_rate"):
                st.write(
                    f"**{tx('Isıtma Hızı', 'Heating Rate')}:** {dataset.metadata['heating_rate']} °C/min"
                )
            st.write(
                f"**{tx('Cihaz', 'Instrument')}:** {dataset.metadata.get('instrument', tx('Yok', 'N/A'))}"
            )

    # =========================================================================
    # TAB 2 - SMOOTHING
    # =========================================================================
    with tab_smooth:
        st.subheader(tx("Sinyal Yumuşatma", "Signal Smoothing"))

        col_ctrl, col_plot = st.columns([1, 3])

        with col_ctrl:
            smooth_method = st.selectbox(
                tx("Yumuşatma Yöntemi", "Smoothing Method"),
                ["savgol", "moving_average", "gaussian"],
                key="dta_smooth_method",
                help=tx(
                    "Savitzky-Golay pik şeklini en iyi korur. Hareketli ortalama en basit seçenektir. Gaussian çok gürültülü veri için uygundur.",
                    "Savitzky-Golay preserves peak shape best. Moving average is simplest. Gaussian is good for very noisy data.",
                ),
            )

            if smooth_method == "savgol":
                sg_window = st.slider(
                    tx("Pencere Uzunluğu", "Window Length"), 5, 51, 11, step=2, key="dta_sg_window",
                    help=tx(
                        "Yumuşatma penceresindeki nokta sayısı. Daha büyük değerler eğriyi daha fazla yumuşatır ancak dar pikleri bozabilir.",
                        "Number of points in the smoothing window. Larger values smooth more but may distort narrow peaks.",
                    ),
                )
                sg_poly = st.slider(
                    tx("Polinom Derecesi", "Polynomial Order"), 1, 7, 3, key="dta_sg_poly",
                    help=tx(
                        "Savitzky-Golay uyumu için polinom derecesi. Daha yüksek dereceler keskin özellikleri daha iyi izler.",
                        "Polynomial degree for Savitzky-Golay fit. Higher orders follow sharp features better.",
                    ),
                )
                smooth_kwargs = {"window_length": sg_window, "polyorder": sg_poly}
            elif smooth_method == "moving_average":
                ma_window = st.slider(
                    tx("Pencere Boyutu", "Window Size"), 3, 51, 11, step=2, key="dta_ma_window",
                    help=tx(
                        "Ortalaması alınacak nokta sayısı. Daha büyük pencereler daha yumuşak sonuç verir.",
                        "Number of points averaged. Larger windows give smoother results.",
                    ),
                )
                smooth_kwargs = {"window": ma_window}
            else:
                gauss_sigma = st.slider(
                    tx("Sigma", "Sigma"), 0.5, 10.0, 2.0, step=0.5, key="dta_gauss_sigma",
                    help=tx(
                        "Gaussian çekirdeğinin standart sapması. Daha yüksek değerler daha agresif yumuşatma uygular.",
                        "Standard deviation of the Gaussian kernel. Higher values smooth more aggressively.",
                    ),
                )
                smooth_kwargs = {"sigma": gauss_sigma}

            if st.button(tx("Yumuşatmayı Uygula", "Apply Smoothing"), key="dta_apply_smooth"):
                try:
                    smoothed = smooth_signal(
                        signal, method=smooth_method, **smooth_kwargs
                    )
                    push_analysis_undo_snapshot(state, tracked_keys)
                    state["smoothed"] = smoothed
                    state["processing"] = update_processing_step(
                        state.get("processing"),
                        "smoothing",
                        {"method": smooth_method, **smooth_kwargs},
                        analysis_type="DTA",
                    )
                    advance_analysis_render_revision(state)
                    _log_event(tx("Yumuşatma Uygulandı", "Smoothing Applied"), f"{tx('Yöntem', 'Method')}: {smooth_method}", tx("DTA Analizi", "DTA Analysis"))
                    # Reset downstream results when input signal changes
                    state["baseline"] = None
                    state["corrected"] = None
                    state["peaks"] = None
                    st.success(tx("Yumuşatma uygulandı.", "Smoothing applied."))
                except Exception as exc:
                    st.error(tx("Yumuşatma başarısız oldu: {error}", "Smoothing failed: {error}", error=exc))

        with col_plot:
            smoothed_for_plot = state.get("smoothed")
            fig = create_dta_plot(
                temperature,
                signal,
                title=tx("Yumuşatılmış DTA Sinyali", "Smoothed DTA Signal"),
                smoothed=smoothed_for_plot,
            )
            st.plotly_chart(
                fig,
                use_container_width=True,
                config=PLOTLY_CONFIG,
                key=_chart_key(selected_key, "smoothing", state),
            )

        # Optional first-derivative view
        if st.checkbox(tx("Türevi Göster", "Show Derivative"), key="dta_show_deriv"):
            working = (
                state["smoothed"]
                if state.get("smoothed") is not None
                else signal
            )
            deriv = compute_derivative(temperature, working, smooth_first=False)
            fig_d = create_thermal_plot(
                temperature,
                deriv,
                title=tx("d(ΔT)/dT (Birinci Türev)", "d(ΔT)/dT (First Derivative)"),
                y_label=tx("d(ΔT)/dT", "d(ΔT)/dT"),
                color="#2EC4B6",
            )
            st.plotly_chart(
                fig_d,
                use_container_width=True,
                config=PLOTLY_CONFIG,
                key=_chart_key(selected_key, "smoothing_derivative", state),
            )

    # =========================================================================
    # TAB 3 - BASELINE CORRECTION
    # =========================================================================
    with tab_baseline:
        st.subheader(tx("Baz Çizgisi Düzeltmesi", "Baseline Correction"))

        col_ctrl3, col_plot3 = st.columns([1, 3])

        with col_ctrl3:
            baseline_method = st.selectbox(
                tx("Baz Çizgisi Yöntemi", "Baseline Method"),
                list(AVAILABLE_METHODS.keys()),
                format_func=lambda x: f"{x} - {AVAILABLE_METHODS[x]}",
                key="dta_baseline_method",
                help=tx(
                    "ASLS ve AirPLS çoğu DTA verisinde iyi çalışır. Polinom yöntemleri basit baz çizgileri için uygundur. SNIP karmaşık arka planlarda daha dayanıklıdır.",
                    "ASLS and AirPLS work well for most DTA data. Polynomial methods suit simple baselines. SNIP is robust for complex backgrounds.",
                ),
            )

            # Method-specific parameters
            bl_kwargs: dict = {}
            if baseline_method in ("asls", "airpls"):
                lam = st.number_input(
                    tx("Lambda (yumuşaklık)", "Lambda (smoothness)"),
                    value=1e6,
                    format="%.0e",
                    key="dta_bl_lam",
                )
                bl_kwargs["lam"] = lam
                if baseline_method == "asls":
                    p_val = st.number_input(
                        tx("Asimetri (p)", "Asymmetry (p)"),
                        value=0.01,
                        format="%.3f",
                        key="dta_bl_p",
                    )
                    bl_kwargs["p"] = p_val
            elif baseline_method in ("modpoly", "imodpoly"):
                poly_order = st.slider(
                    tx("Polinom Derecesi", "Polynomial Order"), 1, 10, 6, key="dta_bl_poly"
                )
                bl_kwargs["poly_order"] = poly_order
            elif baseline_method == "snip":
                max_hw = st.slider(
                    tx("Maksimum Yarım Pencere", "Max Half Window"), 5, 100, 40, key="dta_bl_snip"
                )
                bl_kwargs["max_half_window"] = max_hw

            use_region = st.checkbox(tx("Bölgeyle sınırla", "Restrict to region"), key="dta_bl_region")
            bl_region = None
            if use_region:
                r_min = st.number_input(
                    tx("Bölge minimumu (°C)", "Region min (°C)"),
                    value=float(temperature.min()),
                    key="dta_bl_rmin",
                )
                r_max = st.number_input(
                    tx("Bölge maksimumu (°C)", "Region max (°C)"),
                    value=float(temperature.max()),
                    key="dta_bl_rmax",
                )
                bl_region = (r_min, r_max)

            if st.button(tx("Baz Çizgisi Düzeltmesini Uygula", "Apply Baseline Correction"), key="dta_apply_bl"):
                working = (
                    state["smoothed"]
                    if state.get("smoothed") is not None
                    else signal
                )
                try:
                    corrected, baseline = correct_baseline(
                        temperature,
                        working,
                        method=baseline_method,
                        region=bl_region,
                        **bl_kwargs,
                    )
                    push_analysis_undo_snapshot(state, tracked_keys)
                    state["baseline"] = baseline
                    state["corrected"] = corrected
                    baseline_payload = {"method": baseline_method, **bl_kwargs}
                    if bl_region is not None:
                        baseline_payload["region"] = list(bl_region)
                    state["processing"] = update_processing_step(
                        state.get("processing"),
                        "baseline",
                        baseline_payload,
                        analysis_type="DTA",
                    )
                    # Reset peaks when baseline changes
                    state["peaks"] = None
                    advance_analysis_render_revision(state)
                    _log_event(tx("Baz Çizgisi Düzeltildi", "Baseline Corrected"), f"{tx('Yöntem', 'Method')}: {baseline_method}", tx("DTA Analizi", "DTA Analysis"))
                    st.success(tx("Baz çizgisi düzeltmesi uygulandı ({method}).", "Baseline correction applied ({method}).", method=baseline_method))
                except Exception as exc:
                    st.error(tx("Baz çizgisi düzeltmesi başarısız oldu: {error}", "Baseline correction failed: {error}", error=exc))

        with col_plot3:
            working_signal = (
                state["smoothed"]
                if state.get("smoothed") is not None
                else signal
            )

            # Show the working signal with baseline overlay
            fig_bl = create_dta_plot(
                temperature,
                working_signal,
                title=tx("Baz Çizgisi Düzeltmesi", "Baseline Correction"),
                baseline=state.get("baseline"),
            )
            st.plotly_chart(
                fig_bl,
                use_container_width=True,
                config=PLOTLY_CONFIG,
                key=_chart_key(selected_key, "baseline", state),
            )

            # Show the corrected signal when available
            if state.get("corrected") is not None:
                fig_corr = create_thermal_plot(
                    temperature,
                    state["corrected"],
                    title=tx("Baz Çizgisi Düzeltilmiş Sinyal", "Baseline-Corrected Signal"),
                    y_label=tx("Düzeltilmiş {label}", "Corrected {label}", label=y_label),
                    color="#2EC4B6",
                )
                st.plotly_chart(
                    fig_corr,
                    use_container_width=True,
                    config=PLOTLY_CONFIG,
                    key=_chart_key(selected_key, "baseline_corrected", state),
                )

    # =========================================================================
    # TAB 4 - PEAK ANALYSIS
    # =========================================================================
    with tab_peaks:
        st.subheader(tx("Pik Tespiti ve Karakterizasyonu", "Peak Detection and Characterization"))

        col_ctrl4, col_plot4 = st.columns([1, 3])

        with col_ctrl4:
            # Determine the best available signal for peak finding
            if state.get("corrected") is not None:
                working_for_peaks = state["corrected"]
            elif state.get("smoothed") is not None:
                working_for_peaks = state["smoothed"]
                st.info(
                    tx(
                        "Yumuşatılmış sinyal kullanılıyor. Daha iyi pik karakterizasyonu için baz çizgisi düzeltmesi uygulayın.",
                        "Using smoothed signal. Apply baseline correction for better peak characterization.",
                    )
                )
            else:
                working_for_peaks = signal
                st.info(
                    tx(
                        "Ham sinyal kullanılıyor. Daha iyi sonuç için yumuşatma ve baz çizgisi düzeltmesi uygulayın.",
                        "Using raw signal. Apply smoothing and baseline correction for better results.",
                    )
                )

            detect_exo = st.checkbox(
                tx("Ekzotermik pikleri algıla", "Detect exothermic peaks"), value=True, key="dta_detect_exo"
            )
            detect_endo = st.checkbox(
                tx("Endotermik pikleri algıla", "Detect endothermic peaks"), value=True, key="dta_detect_endo"
            )

            prominence = st.number_input(
                tx("Minimum Belirginlik (0 = otomatik)", "Min Prominence (0 = auto)"),
                value=0.0,
                format="%.4f",
                key="dta_peak_prom",
                help=tx(
                    "Minimum pik belirginliği. Sinyal tepe-tepe aralığının %5'i kadar uyarlamalı varsayılan eşik için 0 kullanın.",
                    "Minimum peak prominence. Set to 0 to use an adaptive default of 5% of the signal peak-to-peak range.",
                ),
            )
            min_distance = st.number_input(
                tx("Minimum Mesafe (nokta, 0 = otomatik)", "Min Distance (points, 0 = auto)"),
                value=0,
                step=1,
                key="dta_peak_dist",
                help=tx(
                    "Komşu pikler arasında gereken minimum veri noktası sayısı. Gürültünün ayrı pik olarak algılanmasını önlemek için artırın.",
                    "Minimum number of data points between adjacent peaks. Increase to avoid detecting noise as separate peaks.",
                ),
            )

            if st.button(tx("Pikleri Bul", "Find Peaks"), key="dta_find_peaks"):
                try:
                    processor = DTAProcessor(
                        temperature,
                        working_for_peaks,
                        metadata=dataset.metadata,
                    )

                    # Build keyword arguments for find_peaks
                    fp_kwargs: dict = {}
                    if prominence > 0:
                        fp_kwargs["prominence"] = prominence
                    if min_distance > 0:
                        fp_kwargs["distance"] = min_distance

                    processor.find_peaks(
                        prominence=prominence if prominence > 0 else None,
                        detect_endothermic=detect_endo,
                        detect_exothermic=detect_exo,
                        **({"distance": min_distance} if min_distance > 0 else {}),
                    )

                    result: DTAResult = processor.get_result()

                    # Run characterize_peaks to fill onset/endset/area/FWHM
                    baseline_arr = state.get("baseline")
                    if result.peaks:
                        result.peaks = characterize_peaks(
                            temperature,
                            working_for_peaks,
                            result.peaks,
                            baseline=baseline_arr,
                        )

                    push_analysis_undo_snapshot(state, tracked_keys)
                    state["peaks"] = result.peaks
                    peak_payload = {
                        "detect_endothermic": detect_endo,
                        "detect_exothermic": detect_exo,
                        "prominence": prominence if prominence > 0 else None,
                        "distance": min_distance if min_distance > 0 else None,
                        "peak_count": len(result.peaks),
                    }
                    state["processing"] = update_processing_step(
                        state.get("processing"),
                        "peak_detection",
                        peak_payload,
                        analysis_type="DTA",
                    )
                    advance_analysis_render_revision(state)
                    _log_event(tx("Pikler Tespit Edildi", "Peaks Detected"), tx("{count} pik bulundu", "{count} peak(s) found", count=len(result.peaks)), tx("DTA Analizi", "DTA Analysis"))
                    st.success(tx("{count} pik bulundu.", "Found {count} peak(s).", count=len(result.peaks)))
                except Exception as exc:
                    st.error(tx("Pik tespiti başarısız oldu: {error}", "Peak detection failed: {error}", error=exc))

        with col_plot4:
            # Resolve the signal to display in the plot
            if state.get("corrected") is not None:
                display_signal = state["corrected"]
            elif state.get("smoothed") is not None:
                display_signal = state["smoothed"]
            else:
                display_signal = signal

            fig_peaks = create_dta_plot(
                temperature,
                display_signal,
                title=tx("Pik Analizi", "Peak Analysis"),
                baseline=state.get("baseline"),
                peaks=state.get("peaks"),
            )
            st.plotly_chart(
                fig_peaks,
                use_container_width=True,
                config=PLOTLY_CONFIG,
                key=_chart_key(selected_key, "peaks", state),
            )

        # Peak results table
        if state.get("peaks"):
            st.subheader(tx("Pik Sonuçları", "Peak Results"))
            rows = []
            for i, p in enumerate(state["peaks"]):
                direction = getattr(p, "direction", None)
                if direction is None:
                    direction = p.peak_type  # fallback to peak_type field
                rows.append(
                    {
                        tx("Pik #", "Peak #"): i + 1,
                        tx("Tip", "Type"): direction,
                        tx("Pik T (°C)", "Peak T (°C)"): f"{p.peak_temperature:.2f}",
                        tx("Başlangıç T (°C)", "Onset T (°C)"): (
                            f"{p.onset_temperature:.2f}"
                            if p.onset_temperature is not None
                            else tx("Yok", "N/A")
                        ),
                        tx("Bitiş T (°C)", "Endset T (°C)"): (
                            f"{p.endset_temperature:.2f}"
                            if p.endset_temperature is not None
                            else tx("Yok", "N/A")
                        ),
                        tx("Yükseklik", "Height"): (
                            f"{p.height:.4f}" if p.height is not None else tx("Yok", "N/A")
                        ),
                        tx("Alan", "Area"): (
                            f"{p.area:.3f}" if p.area is not None else tx("Yok", "N/A")
                        ),
                        tx("FWHM (°C)", "FWHM (°C)"): (
                            f"{p.fwhm:.2f}" if p.fwhm is not None else tx("Yok", "N/A")
                        ),
                    }
                )
            df_peaks = pd.DataFrame(rows)
            st.dataframe(df_peaks, use_container_width=True, hide_index=True)

    # =========================================================================
    # TAB 5 - RESULTS SUMMARY
    # =========================================================================
    with tab_results:
        st.subheader(tx("Analiz Özeti", "Analysis Summary"))

        if not state.get("peaks"):
            st.info(tx("Burada sonuç görmek için önce pik analizi çalıştırın.", "Run peak analysis first to see results here."))
            return

        # Dataset metadata header
        st.markdown(f"**{tx('Veri Seti', 'Dataset')}:** {dataset.metadata.get('file_name', selected_key)}")
        st.markdown(f"**{tx('Numune', 'Sample')}:** {dataset.metadata.get('sample_name', tx('Yok', 'N/A'))}")
        if dataset.metadata.get("sample_mass"):
            st.markdown(f"**{tx('Kütle', 'Mass')}:** {dataset.metadata['sample_mass']} mg")
        if dataset.metadata.get("heating_rate"):
            st.markdown(
                f"**{tx('Isıtma Hızı', 'Heating Rate')}:** {dataset.metadata['heating_rate']} °C/min"
            )

        st.divider()

        for i, p in enumerate(state["peaks"]):
            direction = getattr(p, "direction", p.peak_type)
            with st.container():
                st.markdown(f"### {tx('Pik', 'Peak')} {i + 1} ({direction})")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric(tx("Pik T", "Peak T"), f"{p.peak_temperature:.1f} °C")
                c2.metric(
                    tx("Başlangıç", "Onset"),
                    (
                        f"{p.onset_temperature:.1f} °C"
                        if p.onset_temperature is not None
                        else tx("Yok", "N/A")
                    ),
                )
                c3.metric(
                    tx("Bitiş", "Endset"),
                    (
                        f"{p.endset_temperature:.1f} °C"
                        if p.endset_temperature is not None
                        else tx("Yok", "N/A")
                    ),
                )
                c4.metric(
                    "FWHM",
                    (
                        f"{p.fwhm:.1f} °C"
                        if p.fwhm is not None
                        else tx("Yok", "N/A")
                    ),
                )
                ref_info = render_reference_comparison(p.peak_temperature, "DTA")
                if ref_info:
                    st.markdown(ref_info)

        st.divider()

        if st.button(tx("Sonuçları Oturuma Kaydet", "Save Results to Session"), key="dta_save_results"):
            _store_dta_result(selected_key, dataset, temperature, signal, state)
            st.success(tx("Deneysel DTA sonuçları kaydedildi. İndirmek için Rapor Merkezi'ne gidin.", "Experimental DTA results saved. Go to Report Center to download."))
