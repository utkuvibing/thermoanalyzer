"""Home page - Data upload and column mapping."""

import streamlit as st
import pandas as pd
import os

from core.data_io import read_thermal_data, guess_columns, detect_file_format, ThermalDataset
from ui.components.column_mapper import render_column_mapper
from ui.components.data_preview import render_data_preview
from ui.components.plot_builder import create_thermal_plot, PLOTLY_CONFIG
from ui.components.history_tracker import _log_event


def render():
    st.title("ThermoAnalyzer")
    st.caption("Vendor-independent thermal analysis data processing \u2014 DSC \u00b7 TGA \u00b7 DTA")

    # Initialize session state
    if "datasets" not in st.session_state:
        st.session_state.datasets = {}
    if "active_dataset" not in st.session_state:
        st.session_state.active_dataset = None

    # --- File Upload Section ---
    st.header("Import Data")

    upload_tab, sample_tab = st.tabs(["Upload File", "Load Sample Data"])

    with upload_tab:
        uploaded_files = st.file_uploader(
            "Choose thermal analysis data files",
            type=["csv", "txt", "tsv", "xlsx", "xls"],
            accept_multiple_files=True,
            key="file_uploader",
        )

        if uploaded_files:
            for uploaded_file in uploaded_files:
                file_key = uploaded_file.name
                if file_key in st.session_state.datasets:
                    continue

                st.subheader(f"Processing: {uploaded_file.name}")

                try:
                    # Try auto-detection first
                    dataset = read_thermal_data(uploaded_file)
                    guessed = {
                        "temperature": dataset.original_columns.get("temperature"),
                        "signal": dataset.original_columns.get("signal"),
                        "time": dataset.original_columns.get("time"),
                        "data_type": dataset.data_type,
                    }

                    with st.expander("Adjust Column Mapping", expanded=False):
                        # Show the raw dataframe columns for manual mapping
                        uploaded_file.seek(0)
                        raw_ext = os.path.splitext(uploaded_file.name)[1].lower()
                        if raw_ext in (".xlsx", ".xls"):
                            raw_df = pd.read_excel(uploaded_file)
                        else:
                            fmt = detect_file_format(uploaded_file)
                            uploaded_file.seek(0)
                            raw_df = pd.read_csv(
                                uploaded_file,
                                sep=fmt.get("delimiter", ","),
                                header=fmt.get("header_row", 0),
                                encoding=fmt.get("encoding", "utf-8"),
                            )
                        uploaded_file.seek(0)

                        mapping = render_column_mapper(
                            raw_df, guessed_mapping=guessed,
                            key_prefix=f"map_{file_key}",
                        )

                        if mapping and st.button("Re-map Columns", key=f"remap_{file_key}"):
                            uploaded_file.seek(0)
                            col_map = {}
                            if mapping["temperature"]:
                                col_map["temperature"] = mapping["temperature"]
                            if mapping["signal"]:
                                col_map["signal"] = mapping["signal"]
                            if mapping.get("time"):
                                col_map["time"] = mapping["time"]
                            dataset = read_thermal_data(
                                uploaded_file,
                                column_mapping=col_map,
                                data_type=mapping["data_type"],
                                metadata=mapping["metadata"],
                            )

                    # Store dataset
                    dataset.metadata.setdefault("file_name", uploaded_file.name)
                    st.session_state.datasets[file_key] = dataset
                    _log_event(
                        "Data Loaded",
                        f"{uploaded_file.name} ({dataset.data_type}, {len(dataset.data)} pts)",
                        "Import Data",
                    )
                    st.success(f"Loaded **{uploaded_file.name}** as **{dataset.data_type}** data "
                               f"({len(dataset.data)} points)")

                except Exception as e:
                    st.error(f"Error loading {uploaded_file.name}: {e}")

                    # Fallback: show raw data and manual mapping
                    try:
                        uploaded_file.seek(0)
                        raw_ext = os.path.splitext(uploaded_file.name)[1].lower()
                        if raw_ext in (".xlsx", ".xls"):
                            raw_df = pd.read_excel(uploaded_file)
                        else:
                            raw_df = pd.read_csv(uploaded_file)
                        uploaded_file.seek(0)

                        st.write("Please map columns manually:")
                        mapping = render_column_mapper(
                            raw_df, key_prefix=f"fallback_{file_key}",
                        )

                        if mapping and st.button("Load with Mapping", key=f"load_{file_key}"):
                            uploaded_file.seek(0)
                            col_map = {}
                            if mapping["temperature"]:
                                col_map["temperature"] = mapping["temperature"]
                            if mapping["signal"]:
                                col_map["signal"] = mapping["signal"]
                            if mapping.get("time"):
                                col_map["time"] = mapping["time"]
                            dataset = read_thermal_data(
                                uploaded_file,
                                column_mapping=col_map,
                                data_type=mapping["data_type"],
                                metadata=mapping["metadata"],
                            )
                            dataset.metadata["file_name"] = uploaded_file.name
                            st.session_state.datasets[file_key] = dataset
                            st.rerun()
                    except Exception as e2:
                        st.error(f"Could not parse file: {e2}")

    with sample_tab:
        st.markdown("Load built-in sample data for testing:")

        sample_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sample_data")

        sample_files = {
            "DSC - Polymer Melting": "dsc_polymer_melting.csv",
            "TGA - Calcium Oxalate": "tga_calcium_oxalate.csv",
            "DSC - Multi-Rate Kissinger": "dsc_multirate_kissinger.csv",
        }

        for label, filename in sample_files.items():
            filepath = os.path.join(sample_dir, filename)
            if os.path.exists(filepath):
                if st.button(f"Load: {label}", key=f"sample_{filename}"):
                    try:
                        dataset = read_thermal_data(filepath)
                        dataset.metadata["file_name"] = filename
                        st.session_state.datasets[filename] = dataset
                        _log_event(
                            "Data Loaded",
                            f"{label} ({dataset.data_type}, {len(dataset.data)} pts)",
                            "Import Data",
                        )
                        st.success(f"Loaded **{label}**")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error loading sample: {e}")

    # --- Dataset Manager ---
    if st.session_state.datasets:
        st.divider()
        st.header("Loaded Datasets")

        dataset_names = list(st.session_state.datasets.keys())

        cols = st.columns([3, 1])
        with cols[0]:
            selected = st.selectbox(
                "Select dataset to view/analyze",
                dataset_names,
                key="dataset_selector",
            )
        with cols[1]:
            if st.button("Remove", key="remove_dataset"):
                del st.session_state.datasets[selected]
                if st.session_state.active_dataset == selected:
                    st.session_state.active_dataset = None
                st.rerun()

        st.session_state.active_dataset = selected

        if selected:
            dataset = st.session_state.datasets[selected]

            # Preview
            render_data_preview(dataset, key_prefix=f"prev_{selected}")

            # Quick plot
            st.subheader("Quick View")
            if "temperature" in dataset.data.columns and "signal" in dataset.data.columns:
                y_label = "Signal"
                if dataset.data_type == "DSC":
                    y_label = f"Heat Flow ({dataset.units.get('signal', 'mW')})"
                elif dataset.data_type == "TGA":
                    y_label = f"Mass ({dataset.units.get('signal', '%')})"
                elif dataset.data_type == "DTA":
                    y_label = f"ΔT ({dataset.units.get('signal', 'µV')})"

                fig = create_thermal_plot(
                    dataset.data["temperature"].values,
                    dataset.data["signal"].values,
                    title=f"{dataset.data_type} - {dataset.metadata.get('file_name', 'Data')}",
                    x_label=f"Temperature ({dataset.units.get('temperature', '°C')})",
                    y_label=y_label,
                )
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        # Navigation hint
        st.markdown(
            '<div class="status-bar">Navigate to DSC Analysis, TGA Analysis, or DTA Analysis from the sidebar to process your data.</div>',
            unsafe_allow_html=True,
        )
