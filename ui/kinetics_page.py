"""Kinetic Analysis page - experimental Kissinger and OFW methods."""

import streamlit as st
import numpy as np
import pandas as pd

from core.kinetics import kissinger_analysis, ozawa_flynn_wall_analysis, compute_conversion
from core.result_serialization import serialize_kissinger_result, serialize_ofw_results
from ui.components.plot_builder import create_kissinger_plot, create_thermal_plot, fig_to_bytes, THERMAL_COLORS, PLOTLY_CONFIG
from ui.components.history_tracker import _log_event


def _store_kissinger_result(result):
    """Persist the normalized experimental Kissinger result."""
    figure_keys = []
    if result.plot_data:
        figures = st.session_state.setdefault("figures", {})
        figure_key = "Kissinger Plot"
        fig_k = create_kissinger_plot(
            result.plot_data["inv_tp"],
            result.plot_data["ln_beta_tp2"],
            result.activation_energy,
            result.pre_exponential or 0,
            result.r_squared or 0,
        )
        try:
            figures[figure_key] = fig_to_bytes(fig_k)
            figure_keys.append(figure_key)
        except Exception:
            pass

    record = serialize_kissinger_result(result, artifacts={"figure_keys": figure_keys})
    st.session_state.setdefault("results", {})[record["id"]] = record


def _store_ofw_results(results):
    """Persist normalized experimental OFW results."""
    record = serialize_ofw_results(results, artifacts={})
    st.session_state.setdefault("results", {})[record["id"]] = record


def _collect_dataset_checks(dataset_keys, datasets, heating_rates):
    """Return dataset-type and input validation issues for kinetics runs."""
    issues = []
    if len(dataset_keys) < 2:
        issues.append("Select at least two datasets.")
        return None, issues

    if len(set(dataset_keys)) != len(dataset_keys):
        issues.append("Select each dataset only once.")

    data_types = [datasets[key].data_type for key in dataset_keys]
    stable_types = [dtype for dtype in data_types if dtype in ("DSC", "TGA")]
    if len(stable_types) != len(data_types):
        issues.append("Only DSC and TGA datasets are supported in this experimental kinetics workflow.")
        return None, issues

    dataset_type = stable_types[0]
    if any(dtype != dataset_type for dtype in stable_types):
        issues.append("Kinetics requires datasets of the same analysis type.")

    valid_rates = [float(rate) for rate in heating_rates if rate is not None and float(rate) > 0]
    if len(valid_rates) != len(heating_rates):
        issues.append("All selected datasets need a positive heating rate.")
    elif len(set(round(rate, 6) for rate in valid_rates)) < 2:
        issues.append("Heating rates must contain at least two distinct values.")

    return dataset_type, issues


def render():
    st.title("Kinetic Analysis")
    st.warning(
        "Experimental module: kinetics remains available for exploratory work, but it is not part of the Phase 1 stable workflow."
    )
    st.markdown("Multi-heating-rate methods for activation energy determination.")

    datasets = st.session_state.get("datasets", {})
    if not datasets:
        st.warning("No datasets loaded. Go to **Import Data** first.")
        return

    method = st.selectbox(
        "Kinetic Method",
        ["Kissinger", "Ozawa-Flynn-Wall"],
        key="kinetics_method",
        help="Kissinger: single Ea from peak temperature shift. OFW: isoconversional Ea at each conversion level.",
    )

    st.divider()
    if method == "Kissinger":
        _render_kissinger(datasets)
    else:
        _render_ofw(datasets)


def _render_kissinger(datasets):
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
                    rate = st.number_input(
                        f"β_{i+1} (°C/min)",
                        value=float((i + 1) * 5),
                        min_value=0.1,
                        key=f"kiss_rate_{i}",
                    )
                    rates.append(rate)
                with cols[1]:
                    temp = st.number_input(
                        f"Tp_{i+1} (°C)",
                        value=250.0 + i * 8.0,
                        key=f"kiss_temp_{i}",
                    )
                    temps.append(temp)

            if st.button("Run Kissinger Analysis", key="kiss_run_manual"):
                try:
                    result = kissinger_analysis(rates, temps)
                    st.session_state["kissinger_result"] = result
                    _log_event("Kissinger Analysis", f"Ea={result.activation_energy:.1f} kJ/mol", "Kinetic Analysis")
                    st.success("Analysis complete.")
                except Exception as exc:
                    st.error(f"Analysis failed: {exc}")

        else:
            st.markdown("Select datasets at different heating rates and specify peak temperatures:")
            dataset_keys = list(datasets.keys())

            n_rates = st.number_input("Number of datasets", 2, 10, min(4, len(dataset_keys)), key="kiss_n_ds")
            selected_dataset_keys = []
            rates = []
            temps = []

            for i in range(n_rates):
                col1, col2, col3 = st.columns(3)
                with col1:
                    ds_key = st.selectbox(f"Dataset {i+1}", dataset_keys, key=f"kiss_ds_{i}")
                    selected_dataset_keys.append(ds_key)
                with col2:
                    hr = datasets[ds_key].metadata.get("heating_rate", 10.0) or 10.0
                    rate = st.number_input(
                        f"Heating rate (°C/min)",
                        value=float(hr),
                        min_value=0.1,
                        key=f"kiss_dsrate_{i}",
                    )
                    rates.append(rate)
                with col3:
                    temp = st.number_input(
                        f"Peak T (°C)",
                        value=260.0 + i * 5.0,
                        key=f"kiss_dstemp_{i}",
                    )
                    temps.append(temp)

            _, issues = _collect_dataset_checks(selected_dataset_keys, datasets, rates)
            for issue in issues:
                st.warning(issue)

            if st.button("Run Kissinger Analysis", key="kiss_run_ds", disabled=bool(issues)):
                try:
                    result = kissinger_analysis(rates, temps)
                    st.session_state["kissinger_result"] = result
                    _log_event("Kissinger Analysis", f"Ea={result.activation_energy:.1f} kJ/mol", "Kinetic Analysis")
                    st.success("Analysis complete.")
                except Exception as exc:
                    st.error(f"Analysis failed: {exc}")

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

        if result.plot_data:
            fig = create_kissinger_plot(
                result.plot_data["inv_tp"],
                result.plot_data["ln_beta_tp2"],
                result.activation_energy,
                result.pre_exponential or 0,
                result.r_squared or 0,
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        _store_kissinger_result(result)


def _render_ofw(datasets):
    st.subheader("Ozawa-Flynn-Wall Analysis")
    st.markdown(
        "Isoconversional method: determine Ea at different conversion levels. "
        "Requires consistent DSC or TGA curves at multiple heating rates."
    )

    dataset_keys = list(datasets.keys())
    if len(dataset_keys) < 2:
        st.warning("At least 2 datasets at different heating rates are needed.")
        return

    selected_keys = st.multiselect(
        "Select datasets (different heating rates)",
        dataset_keys,
        default=dataset_keys[: min(4, len(dataset_keys))],
        key="ofw_datasets",
    )

    if len(selected_keys) < 2:
        st.warning("Select at least 2 datasets.")
        return

    rates = []
    for key in selected_keys:
        ds = datasets[key]
        hr = ds.metadata.get("heating_rate", 10.0) or 0.0
        rate = st.number_input(
            f"Heating rate for {key} (°C/min)",
            value=float(hr),
            min_value=0.0,
            key=f"ofw_rate_{key}",
        )
        rates.append(rate)

    col1, col2, col3 = st.columns(3)
    with col1:
        alpha_min = st.number_input(
            "α min",
            value=0.1,
            min_value=0.01,
            max_value=0.9,
            key="ofw_amin",
            help="Lowest conversion fraction to analyze. Avoid <0.05 due to noise.",
        )
    with col2:
        alpha_max = st.number_input(
            "α max",
            value=0.9,
            min_value=0.1,
            max_value=0.99,
            key="ofw_amax",
            help="Highest conversion fraction to analyze. Avoid >0.95 due to noise.",
        )
    with col3:
        alpha_step = st.number_input(
            "α step",
            value=0.05,
            min_value=0.01,
            max_value=0.2,
            key="ofw_astep",
            help="Spacing between conversion levels. Smaller values give finer resolution.",
        )

    dataset_type, issues = _collect_dataset_checks(selected_keys, datasets, rates)
    if alpha_min >= alpha_max:
        issues.append("α min must be smaller than α max.")

    if dataset_type == "DSC":
        for key in selected_keys:
            dsc_state = st.session_state.get(f"dsc_state_{key}", {})
            if dsc_state.get("corrected") is None:
                issues.append(f"Run baseline correction for DSC dataset '{key}' before OFW analysis.")

    for issue in issues:
        st.warning(issue)

    alpha_values = np.arange(alpha_min, alpha_max + alpha_step / 2, alpha_step)

    if st.button("Run OFW Analysis", key="ofw_run", disabled=bool(issues)):
        try:
            temp_data = []
            conv_data = []
            for key in selected_keys:
                ds = datasets[key]
                temp = ds.data["temperature"].values
                if dataset_type == "TGA":
                    sig = ds.data["signal"].values
                    alpha = compute_conversion(temp, sig, mode="tga")
                else:
                    corrected = st.session_state[f"dsc_state_{key}"]["corrected"]
                    alpha = compute_conversion(
                        temp,
                        corrected,
                        baseline=np.zeros_like(corrected),
                        mode="dsc",
                    )
                temp_data.append(temp)
                conv_data.append(alpha)

            results = ozawa_flynn_wall_analysis(
                rates,
                temp_data,
                conv_data,
                alpha_values=alpha_values,
            )
            st.session_state["ofw_results"] = results
            _log_event("OFW Analysis", f"{len(results)} conversion points", "Kinetic Analysis")
            st.success(f"Analysis complete. {len(results)} conversion points analyzed.")
        except Exception as exc:
            st.error(f"Analysis failed: {exc}")

    ofw_results = st.session_state.get("ofw_results")
    if ofw_results:
        st.subheader("Results: Ea vs Conversion")

        rows = []
        alphas_plot = []
        eas_plot = []
        for result in ofw_results:
            alpha_val = result.plot_data.get("alpha") if result.plot_data else None
            rows.append(
                {
                    "α": f"{alpha_val:.2f}" if alpha_val is not None else "N/A",
                    "Ea (kJ/mol)": f"{result.activation_energy:.1f}",
                    "R²": f"{result.r_squared:.4f}" if result.r_squared is not None else "N/A",
                }
            )
            if alpha_val is not None:
                alphas_plot.append(alpha_val)
                eas_plot.append(result.activation_energy)

        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        if alphas_plot:
            fig = create_thermal_plot(
                np.array(alphas_plot),
                np.array(eas_plot),
                title="Activation Energy vs Conversion",
                x_label="Conversion (α)",
                y_label="Ea (kJ/mol)",
                name="Ea",
                color=THERMAL_COLORS[0],
            )
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        _store_ofw_results(ofw_results)
