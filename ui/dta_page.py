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
from ui.components.plot_builder import create_dta_plot, create_thermal_plot, fig_to_bytes, PLOTLY_CONFIG
from ui.components.history_tracker import _log_event
from ui.components.quality_dashboard import render_quality_dashboard
from utils.reference_data import render_reference_comparison


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _plot_with_status(fig, status_text):
    """Render a plotly chart followed by a status bar."""
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
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


# ---------------------------------------------------------------------------
# render()
# ---------------------------------------------------------------------------

def render():
    st.title("DTA Analysis")

    dta_datasets = _get_dta_datasets()
    if not dta_datasets:
        st.warning(
            "No DTA datasets loaded. Go to the **Upload Data** page to load data."
        )
        return

    # Dataset selection
    selected_key = st.selectbox(
        "Select Dataset",
        list(dta_datasets.keys()),
        key="dta_dataset_select",
    )
    dataset = dta_datasets[selected_key]

    temperature = dataset.data["temperature"].values
    signal = dataset.data["signal"].values

    # Initialise per-dataset processing state
    state_key = f"dta_state_{selected_key}"
    if state_key not in st.session_state:
        st.session_state[state_key] = {
            "smoothed": None,
            "baseline": None,
            "corrected": None,
            "peaks": None,
        }
    state = st.session_state[state_key]

    # y-axis label: DTA uses delta-T in µV
    y_label = f"\u0394T ({dataset.units.get('signal', '\u00b5V')})"

    # Build tabs
    tab_raw, tab_smooth, tab_baseline, tab_peaks, tab_results = st.tabs(
        [
            "Raw Data",
            "Smoothing",
            "Baseline Correction",
            "Peak Analysis",
            "Results Summary",
        ]
    )

    # =========================================================================
    # TAB 1 - RAW DATA
    # =========================================================================
    with tab_raw:
        st.subheader("Raw DTA Data")

        fig = create_dta_plot(
            temperature,
            signal,
            title=f"Raw DTA - {dataset.metadata.get('file_name', '')}",
        )
        _plot_with_status(
            fig,
            f"Range: {temperature.min():.1f} \u2013 {temperature.max():.1f} \u00b0C &nbsp;\u2502&nbsp; "
            f"Points: {len(temperature):,} &nbsp;\u2502&nbsp; "
            f"\u0394T p-p: {(signal.max() - signal.min()):.4f}",
        )

        render_quality_dashboard(temperature, signal, key_prefix=f"dta_qd_{selected_key}")

        col_info, col_meta = st.columns(2)

        with col_info:
            st.write(
                f"**Temperature range:** "
                f"{temperature.min():.1f} - {temperature.max():.1f} °C"
            )
            st.write(f"**Data points:** {len(temperature)}")
            sig_range = signal.max() - signal.min()
            st.write(f"**Signal peak-to-peak:** {sig_range:.4f}")

        with col_meta:
            st.write(f"**Sample:** {dataset.metadata.get('sample_name', 'N/A')}")
            if dataset.metadata.get("sample_mass"):
                st.write(f"**Mass:** {dataset.metadata['sample_mass']} mg")
            if dataset.metadata.get("heating_rate"):
                st.write(
                    f"**Heating Rate:** {dataset.metadata['heating_rate']} °C/min"
                )
            st.write(
                f"**Instrument:** {dataset.metadata.get('instrument', 'N/A')}"
            )

    # =========================================================================
    # TAB 2 - SMOOTHING
    # =========================================================================
    with tab_smooth:
        st.subheader("Signal Smoothing")

        col_ctrl, col_plot = st.columns([1, 3])

        with col_ctrl:
            smooth_method = st.selectbox(
                "Smoothing Method",
                ["savgol", "moving_average", "gaussian"],
                key="dta_smooth_method",
                help="Savitzky-Golay preserves peak shape best. Moving average is simplest. "
                     "Gaussian is good for very noisy data.",
            )

            if smooth_method == "savgol":
                sg_window = st.slider(
                    "Window Length", 5, 51, 11, step=2, key="dta_sg_window",
                    help="Number of points in the smoothing window. Larger values smooth more but may distort narrow peaks.",
                )
                sg_poly = st.slider(
                    "Polynomial Order", 1, 7, 3, key="dta_sg_poly",
                    help="Polynomial degree for Savitzky-Golay fit. Higher orders follow sharp features better.",
                )
                smooth_kwargs = {"window_length": sg_window, "polyorder": sg_poly}
            elif smooth_method == "moving_average":
                ma_window = st.slider(
                    "Window Size", 3, 51, 11, step=2, key="dta_ma_window",
                    help="Number of points averaged. Larger windows give smoother results.",
                )
                smooth_kwargs = {"window": ma_window}
            else:
                gauss_sigma = st.slider(
                    "Sigma", 0.5, 10.0, 2.0, step=0.5, key="dta_gauss_sigma",
                    help="Standard deviation of the Gaussian kernel. Higher values smooth more aggressively.",
                )
                smooth_kwargs = {"sigma": gauss_sigma}

            if st.button("Apply Smoothing", key="dta_apply_smooth"):
                try:
                    smoothed = smooth_signal(
                        signal, method=smooth_method, **smooth_kwargs
                    )
                    state["smoothed"] = smoothed
                    _log_event("Smoothing Applied", f"Method: {smooth_method}", "DTA Analysis")
                    # Reset downstream results when input signal changes
                    state["baseline"] = None
                    state["corrected"] = None
                    state["peaks"] = None
                    st.success("Smoothing applied.")
                except Exception as exc:
                    st.error(f"Smoothing failed: {exc}")

        with col_plot:
            smoothed_for_plot = state.get("smoothed")
            fig = create_dta_plot(
                temperature,
                signal,
                title="Smoothed DTA Signal",
                smoothed=smoothed_for_plot,
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        # Optional first-derivative view
        if st.checkbox("Show Derivative", key="dta_show_deriv"):
            working = (
                state["smoothed"]
                if state.get("smoothed") is not None
                else signal
            )
            deriv = compute_derivative(temperature, working, smooth_first=False)
            fig_d = create_thermal_plot(
                temperature,
                deriv,
                title="d(\u0394T)/dT (First Derivative)",
                y_label="d(\u0394T)/dT",
                color="#2EC4B6",
            )
            st.plotly_chart(fig_d, use_container_width=True, config=PLOTLY_CONFIG)

    # =========================================================================
    # TAB 3 - BASELINE CORRECTION
    # =========================================================================
    with tab_baseline:
        st.subheader("Baseline Correction")

        col_ctrl3, col_plot3 = st.columns([1, 3])

        with col_ctrl3:
            baseline_method = st.selectbox(
                "Baseline Method",
                list(AVAILABLE_METHODS.keys()),
                format_func=lambda x: f"{x} - {AVAILABLE_METHODS[x]}",
                key="dta_baseline_method",
                help="ASLS and AirPLS work well for most DTA data. Polynomial methods suit simple baselines. "
                     "SNIP is robust for complex backgrounds.",
            )

            # Method-specific parameters
            bl_kwargs: dict = {}
            if baseline_method in ("asls", "airpls"):
                lam = st.number_input(
                    "Lambda (smoothness)",
                    value=1e6,
                    format="%.0e",
                    key="dta_bl_lam",
                )
                bl_kwargs["lam"] = lam
                if baseline_method == "asls":
                    p_val = st.number_input(
                        "Asymmetry (p)",
                        value=0.01,
                        format="%.3f",
                        key="dta_bl_p",
                    )
                    bl_kwargs["p"] = p_val
            elif baseline_method in ("modpoly", "imodpoly"):
                poly_order = st.slider(
                    "Polynomial Order", 1, 10, 6, key="dta_bl_poly"
                )
                bl_kwargs["poly_order"] = poly_order
            elif baseline_method == "snip":
                max_hw = st.slider(
                    "Max Half Window", 5, 100, 40, key="dta_bl_snip"
                )
                bl_kwargs["max_half_window"] = max_hw

            use_region = st.checkbox("Restrict to region", key="dta_bl_region")
            bl_region = None
            if use_region:
                r_min = st.number_input(
                    "Region min (°C)",
                    value=float(temperature.min()),
                    key="dta_bl_rmin",
                )
                r_max = st.number_input(
                    "Region max (°C)",
                    value=float(temperature.max()),
                    key="dta_bl_rmax",
                )
                bl_region = (r_min, r_max)

            if st.button("Apply Baseline Correction", key="dta_apply_bl"):
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
                    state["baseline"] = baseline
                    state["corrected"] = corrected
                    # Reset peaks when baseline changes
                    state["peaks"] = None
                    _log_event("Baseline Corrected", f"Method: {baseline_method}", "DTA Analysis")
                    st.success(f"Baseline correction applied ({baseline_method}).")
                except Exception as exc:
                    st.error(f"Baseline correction failed: {exc}")

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
                title="Baseline Correction",
                baseline=state.get("baseline"),
            )
            st.plotly_chart(fig_bl, use_container_width=True, config=PLOTLY_CONFIG)

            # Show the corrected signal when available
            if state.get("corrected") is not None:
                fig_corr = create_thermal_plot(
                    temperature,
                    state["corrected"],
                    title="Baseline-Corrected Signal",
                    y_label=f"Corrected {y_label}",
                    color="#2EC4B6",
                )
                st.plotly_chart(fig_corr, use_container_width=True, config=PLOTLY_CONFIG)

    # =========================================================================
    # TAB 4 - PEAK ANALYSIS
    # =========================================================================
    with tab_peaks:
        st.subheader("Peak Detection and Characterization")

        col_ctrl4, col_plot4 = st.columns([1, 3])

        with col_ctrl4:
            # Determine the best available signal for peak finding
            if state.get("corrected") is not None:
                working_for_peaks = state["corrected"]
            elif state.get("smoothed") is not None:
                working_for_peaks = state["smoothed"]
                st.info(
                    "Using smoothed signal. Apply baseline correction for "
                    "better peak characterization."
                )
            else:
                working_for_peaks = signal
                st.info(
                    "Using raw signal. Apply smoothing and baseline correction "
                    "for better results."
                )

            detect_exo = st.checkbox(
                "Detect exothermic peaks", value=True, key="dta_detect_exo"
            )
            detect_endo = st.checkbox(
                "Detect endothermic peaks", value=True, key="dta_detect_endo"
            )

            prominence = st.number_input(
                "Min Prominence (0 = auto)",
                value=0.0,
                format="%.4f",
                key="dta_peak_prom",
                help=(
                    "Minimum peak prominence. Set to 0 to use an adaptive "
                    "default of 5% of the signal peak-to-peak range."
                ),
            )
            min_distance = st.number_input(
                "Min Distance (points, 0 = auto)",
                value=0,
                step=1,
                key="dta_peak_dist",
                help="Minimum number of data points between adjacent peaks. "
                     "Increase to avoid detecting noise as separate peaks.",
            )

            if st.button("Find Peaks", key="dta_find_peaks"):
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

                    state["peaks"] = result.peaks
                    _log_event("Peaks Detected", f"{len(result.peaks)} peak(s) found", "DTA Analysis")
                    st.success(f"Found {len(result.peaks)} peak(s).")
                except Exception as exc:
                    st.error(f"Peak detection failed: {exc}")

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
                title="Peak Analysis",
                baseline=state.get("baseline"),
                peaks=state.get("peaks"),
            )
            st.plotly_chart(fig_peaks, use_container_width=True, config=PLOTLY_CONFIG)

        # Peak results table
        if state.get("peaks"):
            st.subheader("Peak Results")
            rows = []
            for i, p in enumerate(state["peaks"]):
                direction = getattr(p, "direction", None)
                if direction is None:
                    direction = p.peak_type  # fallback to peak_type field
                rows.append(
                    {
                        "Peak #": i + 1,
                        "Type": direction,
                        "Peak T (°C)": f"{p.peak_temperature:.2f}",
                        "Onset T (°C)": (
                            f"{p.onset_temperature:.2f}"
                            if p.onset_temperature is not None
                            else "N/A"
                        ),
                        "Endset T (°C)": (
                            f"{p.endset_temperature:.2f}"
                            if p.endset_temperature is not None
                            else "N/A"
                        ),
                        "Height": (
                            f"{p.height:.4f}" if p.height is not None else "N/A"
                        ),
                        "Area": (
                            f"{p.area:.3f}" if p.area is not None else "N/A"
                        ),
                        "FWHM (°C)": (
                            f"{p.fwhm:.2f}" if p.fwhm is not None else "N/A"
                        ),
                    }
                )
            df_peaks = pd.DataFrame(rows)
            st.dataframe(df_peaks, use_container_width=True, hide_index=True)

            # Store results so the export page can pick them up
            if "results" not in st.session_state:
                st.session_state.results = {}
            st.session_state.results[f"dta_{selected_key}"] = {
                "peaks": state["peaks"],
                "dataset_key": selected_key,
                "analysis_type": "DTA",
            }

    # =========================================================================
    # TAB 5 - RESULTS SUMMARY
    # =========================================================================
    with tab_results:
        st.subheader("Analysis Summary")

        if not state.get("peaks"):
            st.info("Run peak analysis first to see results here.")
            return

        # Dataset metadata header
        st.markdown(f"**Dataset:** {dataset.metadata.get('file_name', selected_key)}")
        st.markdown(f"**Sample:** {dataset.metadata.get('sample_name', 'N/A')}")
        if dataset.metadata.get("sample_mass"):
            st.markdown(f"**Mass:** {dataset.metadata['sample_mass']} mg")
        if dataset.metadata.get("heating_rate"):
            st.markdown(
                f"**Heating Rate:** {dataset.metadata['heating_rate']} °C/min"
            )

        st.divider()

        for i, p in enumerate(state["peaks"]):
            direction = getattr(p, "direction", p.peak_type)
            with st.container():
                st.markdown(f"### Peak {i + 1} ({direction})")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Peak T", f"{p.peak_temperature:.1f} °C")
                c2.metric(
                    "Onset",
                    (
                        f"{p.onset_temperature:.1f} °C"
                        if p.onset_temperature is not None
                        else "N/A"
                    ),
                )
                c3.metric(
                    "Endset",
                    (
                        f"{p.endset_temperature:.1f} °C"
                        if p.endset_temperature is not None
                        else "N/A"
                    ),
                )
                c4.metric(
                    "FWHM",
                    (
                        f"{p.fwhm:.1f} °C"
                        if p.fwhm is not None
                        else "N/A"
                    ),
                )
                ref_info = render_reference_comparison(p.peak_temperature, "DTA")
                if ref_info:
                    st.markdown(ref_info)

        st.divider()

        if st.button("Save Results to Session", key="dta_save_results"):
            if "results" not in st.session_state:
                st.session_state.results = {}
            st.session_state.results[f"dta_{selected_key}"] = {
                "peaks": state["peaks"],
                "dataset_key": selected_key,
                "analysis_type": "DTA",
                "metadata": dataset.metadata,
            }
            # Save figure for report embedding
            figures = st.session_state.setdefault("figures", {})
            display_signal = state.get("corrected") or state.get("smoothed") or signal
            fig_save = create_dta_plot(
                temperature, display_signal,
                title=f"DTA Peak Analysis - {selected_key}",
                baseline=state.get("baseline"),
                peaks=state.get("peaks"),
            )
            try:
                figures[f"DTA Peak Analysis - {selected_key}"] = fig_to_bytes(fig_save)
            except Exception:
                pass
            st.success("Results saved. Go to the Export & Report page to download.")
