"""Kinetic Analysis page - Kissinger, OFW, Friedman methods."""

import streamlit as st
import numpy as np
import pandas as pd

from core.kinetics import kissinger_analysis, ozawa_flynn_wall_analysis, compute_conversion
from ui.components.plot_builder import create_kissinger_plot, create_multirate_overlay, create_thermal_plot, fig_to_bytes, THERMAL_COLORS, PLOTLY_CONFIG
from ui.components.history_tracker import _log_event


def render():
    st.title("Kinetic Analysis")
    st.markdown("Multi-heating-rate methods for activation energy determination.")

    datasets = st.session_state.get("datasets", {})
    if not datasets:
        st.warning("No datasets loaded. Go to **Upload Data** page first.")
        return

    # --- Method selection ---
    method = st.selectbox(
        "Kinetic Method",
        ["Kissinger", "Ozawa-Flynn-Wall"],
        key="kinetics_method",
        help="Kissinger: single Ea from peak temperature shift. "
             "OFW: isoconversional Ea at each conversion level (more detailed).",
    )

    st.divider()

    if method == "Kissinger":
        _render_kissinger(datasets)
    elif method == "Ozawa-Flynn-Wall":
        _render_ofw(datasets)


def _render_kissinger(datasets):
    """Kissinger analysis: requires peak temperatures at different heating rates."""
    st.subheader("Kissinger Analysis")
    st.markdown(
        "Determine activation energy from peak temperature shift with heating rate. "
        "Plot: ln(β/Tp²) vs 1000/Tp"
    )

    input_tab, result_tab = st.tabs(["Input Data", "Results"])

    with input_tab:
        input_mode = st.radio(
            "Input Mode",
            ["Manual Entry", "From Loaded Datasets"],
            key="kiss_input_mode",
            horizontal=True,
        )

        if input_mode == "Manual Entry":
            st.markdown("Enter heating rates and corresponding peak temperatures:")

            n_rates = st.number_input("Number of heating rates", 2, 10, 4, key="kiss_n_rates")

            rates = []
            temps = []
            cols = st.columns(2)
            for i in range(n_rates):
                with cols[0]:
                    r = st.number_input(
                        f"β_{i+1} (°C/min)", value=float((i + 1) * 5),
                        min_value=0.1, key=f"kiss_rate_{i}",
                    )
                    rates.append(r)
                with cols[1]:
                    t = st.number_input(
                        f"Tp_{i+1} (°C)", value=250.0 + i * 8.0,
                        key=f"kiss_temp_{i}",
                    )
                    temps.append(t)

            if st.button("Run Kissinger Analysis", key="kiss_run_manual"):
                try:
                    result = kissinger_analysis(rates, temps)
                    st.session_state["kissinger_result"] = result
                    _log_event("Kissinger Analysis", f"Ea={result.activation_energy:.1f} kJ/mol", "Kinetic Analysis")
                    st.success("Analysis complete!")
                except Exception as e:
                    st.error(f"Analysis failed: {e}")

        else:
            st.markdown("Select datasets at different heating rates and specify peak temperatures:")
            dataset_keys = list(datasets.keys())

            n_rates = st.number_input("Number of datasets", 2, 10, min(4, len(dataset_keys)),
                                      key="kiss_n_ds")
            rates = []
            temps = []
            for i in range(n_rates):
                col1, col2, col3 = st.columns(3)
                with col1:
                    ds_key = st.selectbox(
                        f"Dataset {i+1}", dataset_keys,
                        key=f"kiss_ds_{i}",
                    )
                with col2:
                    hr = datasets[ds_key].metadata.get("heating_rate", 10.0)
                    r = st.number_input(
                        f"Heating rate (°C/min)", value=float(hr),
                        min_value=0.1, key=f"kiss_dsrate_{i}",
                    )
                    rates.append(r)
                with col3:
                    t = st.number_input(
                        f"Peak T (°C)", value=260.0 + i * 5.0,
                        key=f"kiss_dstemp_{i}",
                    )
                    temps.append(t)

            if st.button("Run Kissinger Analysis", key="kiss_run_ds"):
                try:
                    result = kissinger_analysis(rates, temps)
                    st.session_state["kissinger_result"] = result
                    _log_event("Kissinger Analysis", f"Ea={result.activation_energy:.1f} kJ/mol", "Kinetic Analysis")
                    st.success("Analysis complete!")
                except Exception as e:
                    st.error(f"Analysis failed: {e}")

    with result_tab:
        result = st.session_state.get("kissinger_result")
        if result is None:
            st.info("Run the analysis first.")
            return

        col1, col2, col3 = st.columns(3)
        col1.metric("Activation Energy", f"{result.activation_energy:.1f} kJ/mol")
        col2.metric("R²", f"{result.r_squared:.6f}")
        if result.pre_exponential is not None:
            col3.metric("ln(A)", f"{result.pre_exponential:.2f}")

        # Kissinger plot
        if result.plot_data:
            fig = create_kissinger_plot(
                result.plot_data["inv_tp"],
                result.plot_data["ln_beta_tp2"],
                result.activation_energy,
                result.pre_exponential or 0,
                result.r_squared or 0,
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        # Store for export
        if "results" not in st.session_state:
            st.session_state.results = {}
        st.session_state.results["kissinger"] = {
            "activation_energy_kJ_mol": result.activation_energy,
            "r_squared": result.r_squared,
            "ln_A": result.pre_exponential,
            "analysis_type": "Kissinger",
        }
        # Save figure for report embedding
        if result.plot_data:
            figures = st.session_state.setdefault("figures", {})
            fig_k = create_kissinger_plot(
                result.plot_data["inv_tp"],
                result.plot_data["ln_beta_tp2"],
                result.activation_energy,
                result.pre_exponential or 0,
                result.r_squared or 0,
            )
            try:
                figures["Kissinger Plot"] = fig_to_bytes(fig_k)
            except Exception:
                pass


def _render_ofw(datasets):
    """Ozawa-Flynn-Wall isoconversional analysis."""
    st.subheader("Ozawa-Flynn-Wall Analysis")
    st.markdown(
        "Isoconversional method: determine Ea at different conversion levels. "
        "Requires TGA or DSC curves at multiple heating rates."
    )

    dataset_keys = list(datasets.keys())
    if len(dataset_keys) < 2:
        st.warning("At least 2 datasets at different heating rates are needed.")
        return

    selected_keys = st.multiselect(
        "Select datasets (different heating rates)",
        dataset_keys,
        default=dataset_keys[:min(4, len(dataset_keys))],
        key="ofw_datasets",
    )

    if len(selected_keys) < 2:
        st.warning("Select at least 2 datasets.")
        return

    # Heating rates
    rates = []
    for key in selected_keys:
        ds = datasets[key]
        hr = ds.metadata.get("heating_rate", 10.0)
        r = st.number_input(
            f"Heating rate for {key} (°C/min)",
            value=float(hr), min_value=0.1,
            key=f"ofw_rate_{key}",
        )
        rates.append(r)

    # Alpha range
    col1, col2, col3 = st.columns(3)
    with col1:
        alpha_min = st.number_input("α min", value=0.1, min_value=0.01, max_value=0.9, key="ofw_amin",
                                    help="Lowest conversion fraction to analyze. Avoid <0.05 due to noise.")
    with col2:
        alpha_max = st.number_input("α max", value=0.9, min_value=0.1, max_value=0.99, key="ofw_amax",
                                    help="Highest conversion fraction to analyze. Avoid >0.95 due to noise.")
    with col3:
        alpha_step = st.number_input("α step", value=0.05, min_value=0.01, max_value=0.2, key="ofw_astep",
                                     help="Spacing between conversion levels. Smaller values give finer resolution.")

    alpha_values = np.arange(alpha_min, alpha_max + alpha_step / 2, alpha_step)

    if st.button("Run OFW Analysis", key="ofw_run"):
        try:
            temp_data = []
            conv_data = []
            for key in selected_keys:
                ds = datasets[key]
                temp = ds.data["temperature"].values
                sig = ds.data["signal"].values
                alpha = compute_conversion(temp, sig)
                temp_data.append(temp)
                conv_data.append(alpha)

            results = ozawa_flynn_wall_analysis(
                rates, temp_data, conv_data,
                alpha_values=alpha_values,
            )
            st.session_state["ofw_results"] = results
            _log_event("OFW Analysis", f"{len(results)} conversion points", "Kinetic Analysis")
            st.success(f"Analysis complete! {len(results)} conversion points analyzed.")
        except Exception as e:
            st.error(f"Analysis failed: {e}")

    # Results
    ofw_results = st.session_state.get("ofw_results")
    if ofw_results:
        st.subheader("Results: Ea vs Conversion")

        rows = []
        alphas_plot = []
        eas_plot = []
        for r in ofw_results:
            if r.plot_data and "alpha" in r.plot_data:
                alpha_val = r.plot_data["alpha"]
            else:
                alpha_val = None
            rows.append({
                "α": f"{alpha_val:.2f}" if alpha_val else "N/A",
                "Ea (kJ/mol)": f"{r.activation_energy:.1f}",
                "R²": f"{r.r_squared:.4f}" if r.r_squared else "N/A",
            })
            if alpha_val is not None:
                alphas_plot.append(alpha_val)
                eas_plot.append(r.activation_energy)

        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        if alphas_plot:
            fig = create_thermal_plot(
                np.array(alphas_plot), np.array(eas_plot),
                title="Activation Energy vs Conversion",
                x_label="Conversion (α)",
                y_label="Ea (kJ/mol)",
                name="Ea",
                color=THERMAL_COLORS[0],
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        # Store for export
        if "results" not in st.session_state:
            st.session_state.results = {}
        st.session_state.results["ofw"] = {
            "analysis_type": "Ozawa-Flynn-Wall",
            "data": [{"alpha": r.plot_data.get("alpha") if r.plot_data else None,
                       "Ea_kJ_mol": r.activation_energy,
                       "R2": r.r_squared} for r in ofw_results],
        }
