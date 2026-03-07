"""DSC Analysis page - Full DSC processing pipeline with interactive controls."""

import numpy as np
import streamlit as st

from core.preprocessing import smooth_signal, compute_derivative, normalize_by_mass
from core.baseline import correct_baseline, AVAILABLE_METHODS
from core.peak_analysis import find_thermal_peaks, characterize_peaks
from core.dsc_processor import DSCProcessor
from core.result_serialization import serialize_dsc_result
from ui.components.chrome import render_page_header
from ui.components.plot_builder import (
    create_dsc_plot,
    create_thermal_plot,
    fig_to_bytes,
    PLOTLY_CONFIG,
)
from ui.components.history_tracker import _log_event
from ui.components.quality_dashboard import render_quality_dashboard
from utils.i18n import t
from utils.reference_data import render_reference_comparison


def _plot_with_status(fig, status_text):
    """Render a plotly chart followed by a status bar."""
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
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
        title=f"DSC Analysis - {selected_key}",
        baseline=state.get("baseline"),
        peaks=state.get("peaks"),
    )
    for tg in state.get("glass_transitions") or []:
        fig.add_vline(x=tg.tg_onset, line_dash="dot", line_color="#6B7280", opacity=0.5)
        fig.add_vline(x=tg.tg_midpoint, line_dash="dash", line_color="#0B5394", opacity=0.7)
        fig.add_vline(x=tg.tg_endset, line_dash="dot", line_color="#6B7280", opacity=0.5)
    return fig


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

    record = serialize_dsc_result(
        selected_key,
        dataset,
        state.get("peaks") or [],
        glass_transitions=state.get("glass_transitions") or [],
        artifacts={"figure_keys": figure_keys},
    )
    st.session_state.setdefault("results", {})[record["id"]] = record


def render():
    render_page_header(t("dsc.title"), t("dsc.caption"))

    dsc_datasets = _get_dsc_datasets()
    if not dsc_datasets:
        st.warning("No DSC datasets loaded. Go to **Import Data** to load a dataset.")
        return

    selected_key = st.selectbox("Select Dataset", list(dsc_datasets.keys()), key="dsc_dataset_select")
    dataset = dsc_datasets[selected_key]

    temperature = dataset.data["temperature"].values
    signal = dataset.data["signal"].values
    y_label = f"Heat Flow ({dataset.units.get('signal', 'mW')})"

    state_key = f"dsc_state_{selected_key}"
    if state_key not in st.session_state:
        st.session_state[state_key] = {
            "smoothed": None,
            "baseline": None,
            "corrected": None,
            "peaks": None,
            "glass_transitions": [],
            "processor": None,
        }
    state = st.session_state[state_key]

    tab_raw, tab_smooth, tab_baseline, tab_tg, tab_peaks, tab_results = st.tabs(
        ["Raw Data", "Smoothing", "Baseline Correction", "Glass Transition (Tg)", "Peak Analysis", "Results Summary"]
    )

    with tab_raw:
        st.subheader("Raw DSC Data")

        fig = create_thermal_plot(
            temperature,
            signal,
            title=f"Raw DSC - {dataset.metadata.get('file_name', '')}",
            y_label=y_label,
        )
        _plot_with_status(
            fig,
            f"Range: {temperature.min():.1f} – {temperature.max():.1f} °C &nbsp;│&nbsp; "
            f"Points: {len(temperature):,}",
        )

        render_quality_dashboard(temperature, signal, key_prefix=f"dsc_qd_{selected_key}")

        col1, col2 = st.columns(2)
        with col1:
            mass = dataset.metadata.get("sample_mass")
            if mass and mass > 0:
                st.info(f"Sample mass: {mass} mg")
                if st.checkbox("Normalize by mass", key="dsc_normalize"):
                    normalize_by_mass(signal, mass)
                    st.success("Signal can be normalized during processing/export workflows.")

        with col2:
            st.write(f"**Temperature range:** {temperature.min():.1f} - {temperature.max():.1f} °C")
            st.write(f"**Data points:** {len(temperature)}")

    with tab_smooth:
        st.subheader("Signal Smoothing")

        col1, col2 = st.columns([1, 3])

        with col1:
            smooth_method = st.selectbox(
                "Smoothing Method",
                ["savgol", "moving_average", "gaussian"],
                key="dsc_smooth_method",
                help="Savitzky-Golay preserves peak shape best. Moving average is simplest. Gaussian is good for very noisy data.",
            )

            if smooth_method == "savgol":
                window = st.slider(
                    "Window Length",
                    5,
                    51,
                    11,
                    step=2,
                    key="dsc_sg_window",
                    help="Number of points in the smoothing window. Larger values give smoother curves but may distort narrow peaks.",
                )
                polyorder = st.slider(
                    "Polynomial Order",
                    1,
                    7,
                    3,
                    key="dsc_sg_poly",
                    help="Polynomial degree for Savitzky-Golay fit. Higher orders follow sharp features better but smooth less.",
                )
                smooth_kwargs = {"window_length": window, "polyorder": polyorder}
            elif smooth_method == "moving_average":
                window = st.slider(
                    "Window Size",
                    3,
                    51,
                    11,
                    step=2,
                    key="dsc_ma_window",
                    help="Number of points averaged. Larger windows give smoother results.",
                )
                smooth_kwargs = {"window": window}
            else:
                sigma = st.slider(
                    "Sigma",
                    0.5,
                    10.0,
                    2.0,
                    step=0.5,
                    key="dsc_gauss_sigma",
                    help="Standard deviation of the Gaussian kernel. Higher values smooth more aggressively.",
                )
                smooth_kwargs = {"sigma": sigma}

            if st.button("Apply Smoothing", key="dsc_apply_smooth"):
                smoothed = smooth_signal(signal, method=smooth_method, **smooth_kwargs)
                state["smoothed"] = smoothed
                state["baseline"] = None
                state["corrected"] = None
                state["peaks"] = None
                state["glass_transitions"] = []
                _log_event("Smoothing Applied", f"Method: {smooth_method}", "DSC Analysis")
                st.success("Smoothing applied.")

        with col2:
            fig = create_dsc_plot(
                temperature,
                signal,
                title="Smoothed DSC",
                y_label=y_label,
                smoothed=state.get("smoothed"),
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        if st.checkbox("Show Derivative", key="dsc_show_deriv"):
            working_signal = state.get("smoothed") if state.get("smoothed") is not None else signal
            deriv = compute_derivative(temperature, working_signal, smooth_first=False)
            fig_d = create_thermal_plot(
                temperature,
                deriv,
                title="dHF/dT (First Derivative)",
                y_label="dHF/dT",
                color="#2EC4B6",
            )
            st.plotly_chart(fig_d, use_container_width=True, config=PLOTLY_CONFIG)

    with tab_baseline:
        st.subheader("Baseline Correction")

        col1, col2 = st.columns([1, 3])

        with col1:
            baseline_method = st.selectbox(
                "Baseline Method",
                list(AVAILABLE_METHODS.keys()),
                format_func=lambda x: f"{x} - {AVAILABLE_METHODS[x]}",
                key="dsc_baseline_method",
                help="ASLS and AirPLS work well for most DSC data. Polynomial methods suit simple baselines. SNIP is robust for complex backgrounds.",
            )

            bl_kwargs = {}
            if baseline_method in ("asls", "airpls"):
                lam = st.number_input("Lambda (smoothness)", value=1e6, format="%.0e", key="dsc_bl_lam")
                bl_kwargs["lam"] = lam
                if baseline_method == "asls":
                    p = st.number_input("Asymmetry (p)", value=0.01, format="%.3f", key="dsc_bl_p")
                    bl_kwargs["p"] = p
            elif baseline_method in ("modpoly", "imodpoly"):
                poly_order = st.slider("Polynomial Order", 1, 10, 6, key="dsc_bl_poly")
                bl_kwargs["poly_order"] = poly_order
            elif baseline_method == "snip":
                max_hw = st.slider("Max Half Window", 5, 100, 40, key="dsc_bl_snip")
                bl_kwargs["max_half_window"] = max_hw

            use_region = st.checkbox("Restrict to region", key="dsc_bl_region")
            region = None
            if use_region:
                r_min = st.number_input("Region min (°C)", value=float(temperature.min()), key="dsc_bl_rmin")
                r_max = st.number_input("Region max (°C)", value=float(temperature.max()), key="dsc_bl_rmax")
                region = (r_min, r_max)

            if st.button("Apply Baseline Correction", key="dsc_apply_bl"):
                working_signal = state.get("smoothed") if state.get("smoothed") is not None else signal
                try:
                    corrected, baseline = correct_baseline(
                        temperature,
                        working_signal,
                        method=baseline_method,
                        region=region,
                        **bl_kwargs,
                    )
                    state["baseline"] = baseline
                    state["corrected"] = corrected
                    state["peaks"] = None
                    state["glass_transitions"] = []
                    _log_event("Baseline Corrected", f"Method: {baseline_method}", "DSC Analysis")
                    st.success(f"Baseline correction applied ({baseline_method})")
                except Exception as exc:
                    st.error(f"Baseline correction failed: {exc}")

        with col2:
            working_signal = state.get("smoothed") if state.get("smoothed") is not None else signal
            fig = create_dsc_plot(
                temperature,
                working_signal,
                title="Baseline Correction",
                y_label=y_label,
                baseline=state.get("baseline"),
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

            if state.get("corrected") is not None:
                fig2 = create_thermal_plot(
                    temperature,
                    state["corrected"],
                    title="Baseline-Corrected Signal",
                    y_label=f"Corrected {y_label}",
                    color="#2EC4B6",
                )
                st.plotly_chart(fig2, use_container_width=True, config=PLOTLY_CONFIG)

    with tab_tg:
        st.subheader("Glass Transition Detection")
        st.caption("Use the current working DSC signal to estimate Tg onset, midpoint, endset, and ΔCp.")

        col1, col2 = st.columns([1, 3])
        working_signal = _get_working_signal(state, signal)

        with col1:
            st.write("**Search options**")
            use_region = st.checkbox("Restrict Tg search region", key="dsc_tg_region")
            tg_region = None
            if use_region:
                tg_min = st.number_input("Tg region min (°C)", value=float(temperature.min()), key="dsc_tg_rmin")
                tg_max = st.number_input("Tg region max (°C)", value=float(temperature.max()), key="dsc_tg_rmax")
                tg_region = (tg_min, tg_max)

            if st.button("Detect Tg", key="dsc_detect_tg"):
                try:
                    processor = DSCProcessor(
                        temperature,
                        working_signal,
                        sample_mass=dataset.metadata.get("sample_mass"),
                        heating_rate=dataset.metadata.get("heating_rate"),
                    )
                    processor.detect_glass_transition(region=tg_region)
                    glass_transitions = processor.get_result().glass_transitions
                    state["glass_transitions"] = glass_transitions
                    _log_event("Glass Transition Detected", f"{len(glass_transitions)} Tg event(s)", "DSC Analysis")
                    if glass_transitions:
                        st.success(f"Detected {len(glass_transitions)} Tg event(s).")
                    else:
                        st.info("No Tg event was detected for the current signal/region.")
                except Exception as exc:
                    st.error(f"Tg detection failed: {exc}")

        with col2:
            fig_tg = create_thermal_plot(
                temperature,
                working_signal,
                title="Glass Transition View",
                y_label="Signal",
            )
            for tg in state.get("glass_transitions") or []:
                fig_tg.add_vline(x=tg.tg_onset, line_dash="dot", line_color="#6B7280", annotation_text=f"Onset {tg.tg_onset:.1f}°C")
                fig_tg.add_vline(x=tg.tg_midpoint, line_dash="dash", line_color="#0B5394", annotation_text=f"Tg {tg.tg_midpoint:.1f}°C")
                fig_tg.add_vline(x=tg.tg_endset, line_dash="dot", line_color="#6B7280", annotation_text=f"Endset {tg.tg_endset:.1f}°C")
            st.plotly_chart(fig_tg, use_container_width=True, config=PLOTLY_CONFIG)

        if state.get("glass_transitions"):
            st.subheader("Detected Tg Events")
            for index, tg in enumerate(state["glass_transitions"], start=1):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric(f"Tg {index}", f"{tg.tg_midpoint:.1f} °C")
                c2.metric("Onset", f"{tg.tg_onset:.1f} °C")
                c3.metric("Endset", f"{tg.tg_endset:.1f} °C")
                c4.metric("ΔCp", f"{tg.delta_cp:.3f}")

    with tab_peaks:
        st.subheader("Peak Detection & Characterization")

        col1, col2 = st.columns([1, 3])

        with col1:
            working = state.get("corrected")
            if working is None:
                working = state.get("smoothed") if state.get("smoothed") is not None else signal
                st.info("Using raw/smoothed signal. Apply baseline correction for better results.")

            direction = st.selectbox(
                "Peak Direction",
                ["both", "up (endotherm)", "down (exotherm)"],
                key="dsc_peak_dir",
                help="Select which direction of peaks to detect. 'Both' finds endothermic and exothermic events.",
            )
            dir_map = {"both": "both", "up (endotherm)": "up", "down (exotherm)": "down"}

            prominence = st.number_input(
                "Min Prominence (0=auto)",
                value=0.0,
                format="%.3f",
                key="dsc_peak_prom",
                help="Minimum height difference between a peak and its surrounding valleys. Set to 0 for automatic threshold (5% of signal range).",
            )
            min_distance = st.number_input(
                "Min Distance (points, 0=auto)",
                value=0,
                step=1,
                key="dsc_peak_dist",
                help="Minimum number of data points between adjacent peaks. Increase to avoid detecting noise as separate peaks.",
            )

            if st.button("Find Peaks", key="dsc_find_peaks"):
                kwargs = {"direction": dir_map[direction]}
                if prominence > 0:
                    kwargs["prominence"] = prominence
                if min_distance > 0:
                    kwargs["distance"] = min_distance

                try:
                    peaks = find_thermal_peaks(temperature, working, **kwargs)
                    baseline_for_peaks = np.zeros_like(working) if state.get("corrected") is not None else state.get("baseline")
                    peaks = characterize_peaks(temperature, working, peaks, baseline=baseline_for_peaks)
                    state["peaks"] = peaks
                    _log_event("Peaks Detected", f"{len(peaks)} peak(s) found", "DSC Analysis")
                    st.success(f"Found {len(peaks)} peak(s)")
                except Exception as exc:
                    st.error(f"Peak detection failed: {exc}")

        with col2:
            fig = create_dsc_plot(
                temperature,
                working,
                title="Peak Analysis",
                y_label=y_label,
                baseline=state.get("baseline"),
                peaks=state.get("peaks"),
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        if state.get("peaks"):
            st.subheader("Peak Results")
            import pandas as pd

            rows = []
            for i, peak in enumerate(state["peaks"]):
                rows.append(
                    {
                        "Peak #": i + 1,
                        "Type": peak.peak_type,
                        "Peak T (°C)": f"{peak.peak_temperature:.2f}",
                        "Onset T (°C)": f"{peak.onset_temperature:.2f}" if peak.onset_temperature is not None else "N/A",
                        "Endset T (°C)": f"{peak.endset_temperature:.2f}" if peak.endset_temperature is not None else "N/A",
                        "Area (J/g)": f"{peak.area:.3f}" if peak.area is not None else "N/A",
                        "FWHM (°C)": f"{peak.fwhm:.2f}" if peak.fwhm is not None else "N/A",
                        "Height": f"{peak.height:.4f}" if peak.height is not None else "N/A",
                    }
                )
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with tab_results:
        st.subheader("Analysis Summary")

        peaks = state.get("peaks") or []
        glass_transitions = state.get("glass_transitions") or []
        if not peaks and not glass_transitions:
            st.info("Run peak analysis or Tg detection first to see results here.")
            return

        st.markdown(f"**Dataset:** {dataset.metadata.get('file_name', selected_key)}")
        st.markdown(f"**Sample:** {dataset.metadata.get('sample_name', 'N/A')}")
        if dataset.metadata.get("sample_mass"):
            st.markdown(f"**Mass:** {dataset.metadata['sample_mass']} mg")
        if dataset.metadata.get("heating_rate"):
            st.markdown(f"**Heating Rate:** {dataset.metadata['heating_rate']} °C/min")

        st.divider()

        if glass_transitions:
            st.markdown("### Glass Transition")
            for index, tg in enumerate(glass_transitions, start=1):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric(f"Tg {index}", f"{tg.tg_midpoint:.1f} °C")
                c2.metric("Onset", f"{tg.tg_onset:.1f} °C")
                c3.metric("Endset", f"{tg.tg_endset:.1f} °C")
                c4.metric("ΔCp", f"{tg.delta_cp:.3f}")
            st.divider()

        if peaks:
            for i, peak in enumerate(peaks):
                with st.container():
                    st.markdown(f"### Peak {i + 1} ({peak.peak_type})")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Peak Temp", f"{peak.peak_temperature:.1f} °C")
                    c2.metric("Onset", f"{peak.onset_temperature:.1f} °C" if peak.onset_temperature is not None else "N/A")
                    c3.metric("Enthalpy", f"{peak.area:.2f} J/g" if peak.area is not None else "N/A")
                    c4.metric("FWHM", f"{peak.fwhm:.1f} °C" if peak.fwhm is not None else "N/A")
                    ref_info = render_reference_comparison(peak.peak_temperature, "DSC")
                    if ref_info:
                        st.markdown(ref_info)

            st.divider()

        if st.button("Save Results to Session", key="dsc_save_results"):
            _store_dsc_result(selected_key, dataset, temperature, signal, state)
            st.success("Stable DSC results saved. Go to Export & Report to download.")
