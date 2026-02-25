"""TGA Analysis page - Full TGA processing pipeline with interactive controls.

Tabs:
    Raw Data       - TGA curve (mass % vs temperature) with dataset info.
    Smoothing/DTG  - Apply smoothing; overlay TGA and DTG on dual y-axes.
    Step Analysis  - Auto-detect mass-loss steps via TGAProcessor; annotated
                     plot with step regions; results table.
    Results Summary - Metric cards for all detected steps; save to session.
"""

import streamlit as st
import numpy as np
import pandas as pd

from core.preprocessing import smooth_signal, compute_derivative, normalize_by_mass
from core.tga_processor import TGAProcessor, TGAResult, MassLossStep
from ui.components.plot_builder import create_tga_plot, create_thermal_plot, fig_to_bytes, THERMAL_COLORS, PLOTLY_CONFIG
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


def _get_tga_datasets():
    """Return datasets suitable for TGA analysis (TGA type or unknown)."""
    datasets = st.session_state.get("datasets", {})
    return {k: v for k, v in datasets.items() if v.data_type in ("TGA", "unknown")}


def _format_opt(value, fmt=".2f", suffix=""):
    """Format an optional float for display; return 'N/A' when None."""
    if value is None:
        return "N/A"
    return f"{value:{fmt}}{suffix}"


# ---------------------------------------------------------------------------
# render()
# ---------------------------------------------------------------------------

def render():
    st.title("TGA Analysis")

    tga_datasets = _get_tga_datasets()
    if not tga_datasets:
        st.warning(
            "No TGA datasets loaded. Go to the **Upload Data** page to load data."
        )
        return

    # Dataset selection
    selected_key = st.selectbox(
        "Select Dataset",
        list(tga_datasets.keys()),
        key="tga_dataset_select",
    )
    dataset = tga_datasets[selected_key]

    temperature = dataset.data["temperature"].values
    mass_signal = dataset.data["signal"].values

    # Initialise per-dataset processing state
    state_key = f"tga_state_{selected_key}"
    if state_key not in st.session_state:
        st.session_state[state_key] = {
            "smoothed": None,
            "dtg": None,
            "tga_result": None,
        }
    state = st.session_state[state_key]

    # Build tabs
    tab_raw, tab_smooth, tab_steps, tab_results = st.tabs(
        ["Raw Data", "Smoothing / DTG", "Step Analysis", "Results Summary"]
    )

    # =========================================================================
    # TAB 1 - RAW DATA
    # =========================================================================
    with tab_raw:
        st.subheader("Raw TGA Data")

        mass_label = f"Mass ({dataset.units.get('signal', '%')})"

        fig = create_tga_plot(
            temperature, mass_signal,
            title=f"Raw TGA - {dataset.metadata.get('file_name', '')}",
        )
        _plot_with_status(
            fig,
            f"Range: {float(temperature.min()):.1f} \u2013 {float(temperature.max()):.1f} \u00b0C &nbsp;\u2502&nbsp; "
            f"Points: {len(temperature):,} &nbsp;\u2502&nbsp; "
            f"Mass: {float(mass_signal.min()):.2f} \u2013 {float(mass_signal.max()):.2f}",
        )

        render_quality_dashboard(temperature, mass_signal, key_prefix=f"tga_qd_{selected_key}")

        col_info, col_meta = st.columns(2)

        with col_info:
            t_min = float(temperature.min())
            t_max = float(temperature.max())
            st.write(f"**Temperature range:** {t_min:.1f} - {t_max:.1f} °C")
            st.write(f"**Data points:** {len(temperature)}")

            mass_min = float(mass_signal.min())
            mass_max = float(mass_signal.max())
            total_raw_loss = mass_max - mass_min
            st.write(f"**Mass range:** {mass_min:.2f} - {mass_max:.2f}")
            st.write(f"**Apparent total mass change:** {total_raw_loss:.2f}")

        with col_meta:
            sample_name = dataset.metadata.get("sample_name", "N/A")
            sample_mass = dataset.metadata.get("sample_mass")
            heating_rate = dataset.metadata.get("heating_rate")
            instrument = dataset.metadata.get("instrument", "N/A")

            st.write(f"**Sample name:** {sample_name}")
            if sample_mass:
                st.write(f"**Sample mass:** {sample_mass} mg")
            if heating_rate:
                st.write(f"**Heating rate:** {heating_rate} °C/min")
            st.write(f"**Instrument:** {instrument}")

    # =========================================================================
    # TAB 2 - SMOOTHING / DTG
    # =========================================================================
    with tab_smooth:
        st.subheader("Smoothing and DTG")

        col_ctrl, col_plot = st.columns([1, 3])

        with col_ctrl:
            smooth_method = st.selectbox(
                "Smoothing Method",
                ["savgol", "moving_average", "gaussian"],
                key="tga_smooth_method",
                help="Savitzky-Golay preserves step edges best. Moving average is simplest. "
                     "Gaussian is good for very noisy data.",
            )

            if smooth_method == "savgol":
                sg_window = st.slider(
                    "Window Length", 5, 51, 11, step=2, key="tga_sg_window",
                    help="Number of points in the smoothing window. Larger values smooth more but may distort step edges.",
                )
                sg_poly = st.slider(
                    "Polynomial Order", 1, 7, 3, key="tga_sg_poly",
                    help="Polynomial degree for Savitzky-Golay fit. Higher orders follow sharp features better.",
                )
                smooth_kwargs = {"window_length": sg_window, "polyorder": sg_poly}
            elif smooth_method == "moving_average":
                ma_window = st.slider(
                    "Window Size", 3, 51, 11, step=2, key="tga_ma_window",
                    help="Number of points averaged. Larger windows give smoother results.",
                )
                smooth_kwargs = {"window": ma_window}
            else:
                gauss_sigma = st.slider(
                    "Sigma", 0.5, 10.0, 2.0, step=0.5, key="tga_gauss_sigma",
                    help="Standard deviation of the Gaussian kernel. Higher values smooth more aggressively.",
                )
                smooth_kwargs = {"sigma": gauss_sigma}

            show_dtg = st.checkbox("Show DTG overlay", value=True, key="tga_show_dtg")

            smooth_dtg_extra = st.checkbox(
                "Smooth DTG signal", value=True, key="tga_smooth_dtg"
            )

            if st.button("Apply Smoothing", key="tga_apply_smooth"):
                try:
                    smoothed = smooth_signal(
                        mass_signal, method=smooth_method, **smooth_kwargs
                    )
                    state["smoothed"] = smoothed
                    _log_event("Smoothing Applied", f"Method: {smooth_method}", "TGA Analysis")

                    # Compute DTG from the smoothed signal
                    dtg = compute_derivative(
                        temperature, smoothed, order=1, smooth_first=False
                    )
                    if smooth_dtg_extra:
                        dtg = smooth_signal(
                            dtg, method="savgol", window_length=11, polyorder=3
                        )
                    state["dtg"] = dtg
                    st.success("Smoothing applied. DTG computed.")
                except Exception as exc:
                    st.error(f"Smoothing failed: {exc}")

        with col_plot:
            smoothed_for_plot = state.get("smoothed")
            dtg_for_plot = state.get("dtg") if show_dtg else None

            fig = create_tga_plot(
                temperature,
                mass_signal if smoothed_for_plot is None else smoothed_for_plot,
                title="TGA with DTG Overlay",
                dtg=dtg_for_plot,
            )

            # When we have both raw and smoothed, add raw as a faint background
            if smoothed_for_plot is not None:
                import plotly.graph_objects as go
                fig.add_trace(
                    go.Scatter(
                        x=temperature,
                        y=mass_signal,
                        mode="lines",
                        name="Raw",
                        line=dict(color="#CCCCCC", width=1),
                        opacity=0.5,
                    ),
                    # secondary_y argument only works on subplot figures;
                    # create_tga_plot returns a subplot fig when dtg is given.
                    **({"secondary_y": False} if dtg_for_plot is not None else {}),
                )

            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        # Optional standalone derivative view when DTG overlay is off
        if not show_dtg and state.get("dtg") is not None:
            fig_dtg = create_thermal_plot(
                temperature,
                state["dtg"],
                title="DTG Curve (dm/dT)",
                y_label="DTG (%/°C)",
                color=THERMAL_COLORS[1],
            )
            st.plotly_chart(fig_dtg, use_container_width=True, config=PLOTLY_CONFIG)

    # =========================================================================
    # TAB 3 - STEP ANALYSIS
    # =========================================================================
    with tab_steps:
        st.subheader("Mass-Loss Step Detection")

        col_ctrl2, col_plot2 = st.columns([1, 3])

        with col_ctrl2:
            st.markdown("**Detection Parameters**")

            prominence_input = st.number_input(
                "DTG Prominence (0 = auto)",
                value=0.0,
                min_value=0.0,
                format="%.4f",
                key="tga_prominence",
                help=(
                    "Minimum peak prominence of the DTG signal for a step to be "
                    "detected. Set to 0 to use an adaptive threshold (5% of max "
                    "DTG value)."
                ),
            )

            min_mass_loss = st.number_input(
                "Min Mass Loss (%)",
                value=0.5,
                min_value=0.0,
                max_value=100.0,
                format="%.2f",
                key="tga_min_mass_loss",
                help="Steps with a mass change smaller than this threshold are discarded. "
                     "Increase to filter out minor mass-loss artifacts.",
            )

            st.markdown("**Smoothing for Step Detection**")
            step_smooth_method = st.selectbox(
                "Smoothing Method",
                ["savgol", "moving_average", "gaussian"],
                key="tga_step_smooth_method",
            )
            step_sg_window = st.slider(
                "Window Length", 5, 51, 11, step=2, key="tga_step_sg_window"
            )
            step_sg_poly = st.slider(
                "Polynomial Order", 1, 7, 3, key="tga_step_sg_poly"
            )

            initial_mass = dataset.metadata.get("sample_mass")

            if st.button("Detect Steps", key="tga_detect_steps"):
                prom_kwarg = prominence_input if prominence_input > 0.0 else None
                try:
                    step_smooth_kwargs: dict = {}
                    if step_smooth_method == "savgol":
                        step_smooth_kwargs = {
                            "window_length": step_sg_window,
                            "polyorder": step_sg_poly,
                        }

                    processor = TGAProcessor(
                        temperature,
                        mass_signal,
                        initial_mass_mg=initial_mass,
                        metadata=dataset.metadata,
                    )
                    result: TGAResult = processor.process(
                        smooth_method=step_smooth_method,
                        smooth_dtg=True,
                        prominence=prom_kwarg,
                        min_mass_loss=min_mass_loss,
                        **step_smooth_kwargs,
                    )
                    state["tga_result"] = result
                    # Also expose the smoothed / DTG computed by the processor
                    state["smoothed"] = result.smoothed_signal
                    state["dtg"] = result.dtg_signal

                    n_steps = len(result.steps)
                    _log_event(
                        "Steps Detected",
                        f"{n_steps} step(s), total loss: {result.total_mass_loss_percent:.2f}%",
                        "TGA Analysis",
                    )
                    st.success(
                        f"Detected {n_steps} step{'s' if n_steps != 1 else ''}. "
                        f"Total mass loss: {result.total_mass_loss_percent:.2f} %  |  "
                        f"Residue: {result.residue_percent:.2f} %"
                    )
                except Exception as exc:
                    st.error(f"Step detection failed: {exc}")

        with col_plot2:
            result: TGAResult = state.get("tga_result")

            if result is not None:
                smoothed_display = result.smoothed_signal
                dtg_display = result.dtg_signal
                steps_display = result.steps if result.steps else None
            else:
                smoothed_display = state.get("smoothed")
                dtg_display = state.get("dtg")
                steps_display = None

            fig_steps = create_tga_plot(
                temperature,
                mass_signal if smoothed_display is None else smoothed_display,
                title="Step Detection",
                dtg=dtg_display,
                steps=steps_display,
            )
            st.plotly_chart(fig_steps, use_container_width=True, config=PLOTLY_CONFIG)

        # Results table
        if state.get("tga_result") is not None:
            result = state["tga_result"]
            if result.steps:
                st.subheader("Detected Steps")
                rows = []
                for i, step in enumerate(result.steps):
                    row = {
                        "Step #": i + 1,
                        "Onset T (°C)": f"{step.onset_temperature:.1f}",
                        "Midpoint T (°C)": f"{step.midpoint_temperature:.1f}",
                        "Endset T (°C)": f"{step.endset_temperature:.1f}",
                        "Mass Loss (%)": f"{step.mass_loss_percent:.2f}",
                        "Residue (%)": _format_opt(step.residual_percent, ".2f"),
                    }
                    if step.mass_loss_mg is not None:
                        row["Mass Loss (mg)"] = f"{step.mass_loss_mg:.3f}"
                    rows.append(row)

                df_steps = pd.DataFrame(rows)
                st.dataframe(df_steps, use_container_width=True, hide_index=True)
            else:
                st.info(
                    "No steps detected with the current parameters. "
                    "Try lowering the prominence or min mass loss threshold."
                )

    # =========================================================================
    # TAB 4 - RESULTS SUMMARY
    # =========================================================================
    with tab_results:
        st.subheader("Analysis Summary")

        result: TGAResult = state.get("tga_result")

        if result is None:
            st.info("Run step detection first (Step Analysis tab) to see results here.")
            return

        # Dataset metadata header
        st.markdown(f"**Dataset:** {dataset.metadata.get('file_name', selected_key)}")
        st.markdown(f"**Sample:** {dataset.metadata.get('sample_name', 'N/A')}")
        if dataset.metadata.get("sample_mass"):
            st.markdown(f"**Mass:** {dataset.metadata['sample_mass']} mg")
        if dataset.metadata.get("heating_rate"):
            st.markdown(f"**Heating Rate:** {dataset.metadata['heating_rate']} °C/min")
        if dataset.metadata.get("atmosphere"):
            st.markdown(f"**Atmosphere:** {dataset.metadata['atmosphere']}")

        st.divider()

        # Overall metrics
        ov1, ov2, ov3 = st.columns(3)
        ov1.metric("Total Mass Loss", f"{result.total_mass_loss_percent:.2f} %")
        ov2.metric("Final Residue", f"{result.residue_percent:.2f} %")
        ov3.metric("Steps Detected", str(len(result.steps)))

        st.divider()

        # Per-step metric cards
        if result.steps:
            for i, step in enumerate(result.steps):
                st.markdown(f"### Step {i + 1}")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Onset T", f"{step.onset_temperature:.1f} °C")
                c2.metric("Midpoint T", f"{step.midpoint_temperature:.1f} °C")
                c3.metric("Endset T", f"{step.endset_temperature:.1f} °C")
                c4.metric("Mass Loss", f"{step.mass_loss_percent:.2f} %")
                ref_info = render_reference_comparison(step.midpoint_temperature, "TGA")
                if ref_info:
                    st.markdown(ref_info)

                d1, d2 = st.columns(2)
                d1.metric(
                    "Residue after step",
                    _format_opt(step.residual_percent, ".2f", " %"),
                )
                if step.mass_loss_mg is not None:
                    d2.metric("Mass Loss (abs)", f"{step.mass_loss_mg:.3f} mg")
        else:
            st.info("No mass-loss steps were detected.")

        st.divider()

        # Save to session state
        if st.button("Save Results to Session", key="tga_save_results"):
            if "results" not in st.session_state:
                st.session_state.results = {}
            st.session_state.results[f"tga_{selected_key}"] = {
                "steps": result.steps,
                "total_mass_loss_percent": result.total_mass_loss_percent,
                "residue_percent": result.residue_percent,
                "dataset_key": selected_key,
                "analysis_type": "TGA",
                "metadata": dataset.metadata,
            }
            # Save figure for report embedding
            figures = st.session_state.setdefault("figures", {})
            fig_save = create_tga_plot(
                temperature,
                result.smoothed_signal if result.smoothed_signal is not None else mass_signal,
                title=f"TGA Step Analysis - {selected_key}",
                dtg=result.dtg_signal,
                steps=result.steps,
            )
            try:
                figures[f"TGA Step Analysis - {selected_key}"] = fig_to_bytes(fig_save)
            except Exception:
                pass
            st.success("Results saved. Go to the Export & Report page to download.")
