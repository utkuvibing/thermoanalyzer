"""DSC Analysis page - Full DSC processing pipeline with interactive controls."""

import streamlit as st
import numpy as np

from core.preprocessing import smooth_signal, compute_derivative, normalize_by_mass
from core.baseline import correct_baseline, AVAILABLE_METHODS
from core.peak_analysis import find_thermal_peaks, characterize_peaks
from core.dsc_processor import DSCProcessor
from ui.components.plot_builder import create_dsc_plot, create_thermal_plot, fig_to_bytes, PLOTLY_CONFIG
from ui.components.history_tracker import _log_event
from ui.components.quality_dashboard import render_quality_dashboard
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
    return {k: v for k, v in datasets.items() if v.data_type in ("DSC", "DTA", "unknown")}


def render():
    st.title("DSC Analysis")

    dsc_datasets = _get_dsc_datasets()
    if not dsc_datasets:
        st.warning("No DSC datasets loaded. Go to **Upload Data** page to load data.")
        return

    # Dataset selection
    selected_key = st.selectbox("Select Dataset", list(dsc_datasets.keys()), key="dsc_dataset_select")
    dataset = dsc_datasets[selected_key]

    temperature = dataset.data["temperature"].values
    signal = dataset.data["signal"].values

    # Initialize processing state
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

    # --- Tabs ---
    tab_raw, tab_smooth, tab_baseline, tab_peaks, tab_results = st.tabs(
        ["Raw Data", "Smoothing", "Baseline Correction", "Peak Analysis", "Results Summary"]
    )

    # ===================== RAW DATA TAB =====================
    with tab_raw:
        st.subheader("Raw DSC Data")

        y_label = f"Heat Flow ({dataset.units.get('signal', 'mW')})"

        fig = create_thermal_plot(
            temperature, signal,
            title=f"Raw DSC - {dataset.metadata.get('file_name', '')}",
            y_label=y_label,
        )
        _plot_with_status(
            fig,
            f"Range: {temperature.min():.1f} \u2013 {temperature.max():.1f} \u00b0C &nbsp;\u2502&nbsp; "
            f"Points: {len(temperature):,}",
        )

        render_quality_dashboard(temperature, signal, key_prefix=f"dsc_qd_{selected_key}")

        # Normalize option
        col1, col2 = st.columns(2)
        with col1:
            mass = dataset.metadata.get("sample_mass")
            if mass and mass > 0:
                st.info(f"Sample mass: {mass} mg")
                if st.checkbox("Normalize by mass", key="dsc_normalize"):
                    signal = normalize_by_mass(signal, mass)
                    y_label = "Heat Flow (mW/mg)"
                    st.success("Signal normalized by sample mass")

        with col2:
            st.write(f"**Temperature range:** {temperature.min():.1f} - {temperature.max():.1f} °C")
            st.write(f"**Data points:** {len(temperature)}")

    # ===================== SMOOTHING TAB =====================
    with tab_smooth:
        st.subheader("Signal Smoothing")

        col1, col2 = st.columns([1, 3])

        with col1:
            smooth_method = st.selectbox(
                "Smoothing Method",
                ["savgol", "moving_average", "gaussian"],
                key="dsc_smooth_method",
                help="Savitzky-Golay preserves peak shape best. Moving average is simplest. "
                     "Gaussian is good for very noisy data.",
            )

            if smooth_method == "savgol":
                window = st.slider("Window Length", 5, 51, 11, step=2, key="dsc_sg_window",
                                   help="Number of points in the smoothing window. Larger values give smoother curves but may distort narrow peaks.")
                polyorder = st.slider("Polynomial Order", 1, 7, 3, key="dsc_sg_poly",
                                      help="Polynomial degree for Savitzky-Golay fit. Higher orders follow sharp features better but smooth less.")
                smooth_kwargs = {"window_length": window, "polyorder": polyorder}
            elif smooth_method == "moving_average":
                window = st.slider("Window Size", 3, 51, 11, step=2, key="dsc_ma_window",
                                   help="Number of points averaged. Larger windows give smoother results.")
                smooth_kwargs = {"window": window}
            else:
                sigma = st.slider("Sigma", 0.5, 10.0, 2.0, step=0.5, key="dsc_gauss_sigma",
                                  help="Standard deviation of the Gaussian kernel. Higher values smooth more aggressively.")
                smooth_kwargs = {"sigma": sigma}

            if st.button("Apply Smoothing", key="dsc_apply_smooth"):
                smoothed = smooth_signal(signal, method=smooth_method, **smooth_kwargs)
                state["smoothed"] = smoothed
                _log_event("Smoothing Applied", f"Method: {smooth_method}", "DSC Analysis")
                st.success("Smoothing applied!")

        with col2:
            smoothed = state.get("smoothed")
            fig = create_dsc_plot(
                temperature, signal,
                title="Smoothed DSC",
                y_label=y_label,
                smoothed=smoothed,
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        # Derivative view
        if st.checkbox("Show Derivative", key="dsc_show_deriv"):
            working_signal = smoothed if smoothed is not None else signal
            deriv = compute_derivative(temperature, working_signal, smooth_first=False)
            fig_d = create_thermal_plot(
                temperature, deriv,
                title="dHF/dT (First Derivative)",
                y_label="dHF/dT",
                color="#2EC4B6",
            )
            st.plotly_chart(fig_d, use_container_width=True, config=PLOTLY_CONFIG)

    # ===================== BASELINE CORRECTION TAB =====================
    with tab_baseline:
        st.subheader("Baseline Correction")

        col1, col2 = st.columns([1, 3])

        with col1:
            baseline_method = st.selectbox(
                "Baseline Method",
                list(AVAILABLE_METHODS.keys()),
                format_func=lambda x: f"{x} - {AVAILABLE_METHODS[x]}",
                key="dsc_baseline_method",
                help="ASLS and AirPLS work well for most DSC data. Polynomial methods suit simple baselines. "
                     "SNIP is robust for complex backgrounds.",
            )

            # Method-specific parameters
            bl_kwargs = {}
            if baseline_method in ("asls", "airpls"):
                lam = st.number_input("Lambda (smoothness)", value=1e6,
                                      format="%.0e", key="dsc_bl_lam")
                bl_kwargs["lam"] = lam
                if baseline_method == "asls":
                    p = st.number_input("Asymmetry (p)", value=0.01,
                                        format="%.3f", key="dsc_bl_p")
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
                r_min = st.number_input("Region min (°C)", value=float(temperature.min()),
                                        key="dsc_bl_rmin")
                r_max = st.number_input("Region max (°C)", value=float(temperature.max()),
                                        key="dsc_bl_rmax")
                region = (r_min, r_max)

            if st.button("Apply Baseline Correction", key="dsc_apply_bl"):
                working_signal = state.get("smoothed") if state.get("smoothed") is not None else signal
                try:
                    corrected, baseline = correct_baseline(
                        temperature, working_signal,
                        method=baseline_method, region=region, **bl_kwargs,
                    )
                    state["baseline"] = baseline
                    state["corrected"] = corrected
                    _log_event("Baseline Corrected", f"Method: {baseline_method}", "DSC Analysis")
                    st.success(f"Baseline correction applied ({baseline_method})")
                except Exception as e:
                    st.error(f"Baseline correction failed: {e}")

        with col2:
            working_signal = state.get("smoothed") if state.get("smoothed") is not None else signal
            fig = create_dsc_plot(
                temperature, working_signal,
                title="Baseline Correction",
                y_label=y_label,
                baseline=state.get("baseline"),
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

            if state.get("corrected") is not None:
                fig2 = create_thermal_plot(
                    temperature, state["corrected"],
                    title="Baseline-Corrected Signal",
                    y_label=f"Corrected {y_label}",
                    color="#2EC4B6",
                )
                st.plotly_chart(fig2, use_container_width=True, config=PLOTLY_CONFIG)

    # ===================== PEAK ANALYSIS TAB =====================
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
                "Min Prominence (0=auto)", value=0.0,
                format="%.3f", key="dsc_peak_prom",
                help="Minimum height difference between a peak and its surrounding valleys. "
                     "Set to 0 for automatic threshold (5% of signal range).",
            )
            min_distance = st.number_input(
                "Min Distance (points, 0=auto)", value=0,
                step=1, key="dsc_peak_dist",
                help="Minimum number of data points between adjacent peaks. "
                     "Increase to avoid detecting noise as separate peaks.",
            )

            if st.button("Find Peaks", key="dsc_find_peaks"):
                kwargs = {"direction": dir_map[direction]}
                if prominence > 0:
                    kwargs["prominence"] = prominence
                if min_distance > 0:
                    kwargs["distance"] = min_distance

                try:
                    peaks = find_thermal_peaks(temperature, working, **kwargs)
                    baseline_for_peaks = state.get("baseline")
                    peaks = characterize_peaks(temperature, working, peaks, baseline=baseline_for_peaks)
                    state["peaks"] = peaks
                    tg_result = DSCProcessor(temperature, working).detect_glass_transition().get_result()
                    state["glass_transitions"] = tg_result.glass_transitions
                    _log_event("Peaks Detected", f"{len(peaks)} peak(s) found", "DSC Analysis")
                    st.success(f"Found {len(peaks)} peak(s)")
                except Exception as e:
                    st.error(f"Peak detection failed: {e}")

        with col2:
            fig = create_dsc_plot(
                temperature, working,
                title="Peak Analysis",
                y_label=y_label,
                baseline=state.get("baseline"),
                peaks=state.get("peaks"),
                glass_transitions=state.get("glass_transitions"),
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        # Peak results table
        if state.get("peaks"):
            st.subheader("Peak Results")
            import pandas as pd
            rows = []
            for i, p in enumerate(state["peaks"]):
                rows.append({
                    "Peak #": i + 1,
                    "Type": p.peak_type,
                    "Peak T (°C)": f"{p.peak_temperature:.2f}",
                    "Onset T (°C)": f"{p.onset_temperature:.2f}" if p.onset_temperature else "N/A",
                    "Endset T (°C)": f"{p.endset_temperature:.2f}" if p.endset_temperature else "N/A",
                    "Area (J/g)": f"{p.area:.3f}" if p.area else "N/A",
                    "FWHM (°C)": f"{p.fwhm:.2f}" if p.fwhm else "N/A",
                    "Height": f"{p.height:.4f}" if p.height else "N/A",
                })
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Store results for export
            if "results" not in st.session_state:
                st.session_state.results = {}
                st.session_state.results[f"dsc_{selected_key}"] = {
                    "peaks": state["peaks"],
                    "baseline": state.get("baseline"),
                    "corrected": state.get("corrected"),
                    "glass_transitions": state.get("glass_transitions", []),
                    "dataset_key": selected_key,
                    "analysis_type": "DSC",
                }

    # ===================== RESULTS SUMMARY TAB =====================
    with tab_results:
        st.subheader("Analysis Summary")

        if not state.get("peaks"):
            st.info("Run peak analysis first to see results here.")
        else:
            st.markdown(f"**Dataset:** {dataset.metadata.get('file_name', selected_key)}")
            st.markdown(f"**Sample:** {dataset.metadata.get('sample_name', 'N/A')}")
            if dataset.metadata.get("sample_mass"):
                st.markdown(f"**Mass:** {dataset.metadata['sample_mass']} mg")
            if dataset.metadata.get("heating_rate"):
                st.markdown(f"**Heating Rate:** {dataset.metadata['heating_rate']} °C/min")

            st.divider()

            for i, p in enumerate(state["peaks"]):
                with st.container():
                    st.markdown(f"### Peak {i+1} ({p.peak_type})")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Peak Temp", f"{p.peak_temperature:.1f} °C")
                    c2.metric("Onset", f"{p.onset_temperature:.1f} °C" if p.onset_temperature else "N/A")
                    c3.metric("Enthalpy", f"{p.area:.2f} J/g" if p.area else "N/A")
                    c4.metric("FWHM", f"{p.fwhm:.1f} °C" if p.fwhm else "N/A")
                    ref_info = render_reference_comparison(p.peak_temperature, "DSC")
                    if ref_info:
                        st.markdown(ref_info)

            # Quick export button
            if st.button("Save Results to Session", key="dsc_save_results"):
                if "results" not in st.session_state:
                    st.session_state.results = {}
                st.session_state.results[f"dsc_{selected_key}"] = {
                    "peaks": state["peaks"],
                    "baseline": state.get("baseline"),
                    "corrected": state.get("corrected"),
                    "glass_transitions": state.get("glass_transitions", []),
                    "dataset_key": selected_key,
                    "analysis_type": "DSC",
                    "metadata": dataset.metadata,
                }
                # Save figure for report embedding
                figures = st.session_state.setdefault("figures", {})
                working = state.get("corrected")
                if working is None:
                    working = state.get("smoothed") if state.get("smoothed") is not None else signal
                fig_save = create_dsc_plot(
                    temperature, working,
                    title=f"DSC Peak Analysis - {selected_key}",
                    baseline=state.get("baseline"),
                    peaks=state.get("peaks"),
                    glass_transitions=state.get("glass_transitions"),
                )
                try:
                    figures[f"DSC Peak Analysis - {selected_key}"] = fig_to_bytes(fig_save)
                except Exception:
                    pass
                st.success("Results saved! Go to Export & Report page to download.")
