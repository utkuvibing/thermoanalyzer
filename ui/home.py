"""Home page - Data upload and column mapping."""

import os

import pandas as pd
import streamlit as st

from core.data_io import detect_file_format, read_thermal_data
from ui.components.chrome import render_page_header
from ui.components.column_mapper import render_column_mapper
from ui.components.data_preview import render_data_preview
from ui.components.history_tracker import _log_event
from ui.components.plot_builder import PLOTLY_CONFIG, create_thermal_plot
from ui.components.workflow_guide import render_home_workflow_guide
from utils.i18n import t, tx
from utils.session_state import ensure_session_state


def render():
    ensure_session_state()

    render_page_header(t("home.title"), t("home.caption"), badge=t("home.hero_badge"))
    render_home_workflow_guide()

    datasets = st.session_state.get("datasets", {})
    if datasets:
        vendors = {ds.metadata.get("vendor", "Generic") for ds in datasets.values()}
        dsc_count = sum(1 for ds in datasets.values() if ds.data_type == "DSC")
        tga_count = sum(1 for ds in datasets.values() if ds.data_type == "TGA")
        m1, m2, m3 = st.columns(3)
        m1.metric(tx("Yüklü Koşu", "Loaded Runs"), str(len(datasets)))
        m2.metric("DSC / TGA", f"{dsc_count} / {tga_count}")
        m3.metric(tx("Vendor Sayısı", "Vendors"), str(len(vendors)))

    st.header(t("home.title"))

    upload_tab, sample_tab = st.tabs(
        [
            tx("Dosya Yükle", "Upload File"),
            tx("Örnek Veri Yükle", "Load Sample Data"),
        ]
    )

    with upload_tab:
        uploaded_files = st.file_uploader(
            tx("Termal analiz dosyalarını seç", "Choose thermal analysis data files"),
            type=["csv", "txt", "tsv", "xlsx", "xls"],
            accept_multiple_files=True,
            key="file_uploader",
        )

        if uploaded_files:
            for uploaded_file in uploaded_files:
                file_key = uploaded_file.name
                if file_key in st.session_state.datasets:
                    continue

                st.subheader(f"{tx('İşleniyor', 'Processing')}: {uploaded_file.name}")

                try:
                    dataset = read_thermal_data(uploaded_file)
                    guessed = {
                        "temperature": dataset.original_columns.get("temperature"),
                        "signal": dataset.original_columns.get("signal"),
                        "time": dataset.original_columns.get("time"),
                        "data_type": dataset.data_type,
                    }

                    with st.expander(tx("Kolon Eşlemeyi Düzenle", "Adjust Column Mapping"), expanded=False):
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
                            raw_df,
                            guessed_mapping=guessed,
                            key_prefix=f"map_{file_key}",
                        )

                        if mapping and st.button(tx("Kolonları Yeniden Eşle", "Re-map Columns"), key=f"remap_{file_key}"):
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

                    dataset.metadata.setdefault("file_name", uploaded_file.name)
                    dataset.metadata.setdefault("display_name", uploaded_file.name)
                    st.session_state.datasets[file_key] = dataset
                    st.session_state.active_dataset = file_key
                    _log_event(
                        tx("Veri Yüklendi", "Data Loaded"),
                        f"{uploaded_file.name} ({dataset.data_type}, {dataset.metadata.get('vendor', 'Generic')}, {len(dataset.data)} pts)",
                        t("home.title"),
                    )
                    st.success(
                        tx(
                            "**{file_name}** dosyası **{data_type}** olarak **{vendor}** kaynağından yüklendi ({points} nokta).",
                            "Loaded **{file_name}** as **{data_type}** data from **{vendor}** ({points} points).",
                            file_name=uploaded_file.name,
                            data_type=dataset.data_type,
                            vendor=dataset.metadata.get("vendor", "Generic"),
                            points=len(dataset.data),
                        )
                    )

                except Exception as error:
                    st.error(
                        tx(
                            "{file_name} yüklenirken hata oluştu: {error}",
                            "Error loading {file_name}: {error}",
                            file_name=uploaded_file.name,
                            error=error,
                        )
                    )

                    try:
                        uploaded_file.seek(0)
                        raw_ext = os.path.splitext(uploaded_file.name)[1].lower()
                        if raw_ext in (".xlsx", ".xls"):
                            raw_df = pd.read_excel(uploaded_file)
                        else:
                            raw_df = pd.read_csv(uploaded_file)
                        uploaded_file.seek(0)

                        st.write(tx("Lütfen kolonları manuel eşleyin:", "Please map columns manually:"))
                        mapping = render_column_mapper(raw_df, key_prefix=f"fallback_{file_key}")

                        if mapping and st.button(tx("Eşleme ile Yükle", "Load with Mapping"), key=f"load_{file_key}"):
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
                            dataset.metadata.setdefault("display_name", uploaded_file.name)
                            st.session_state.datasets[file_key] = dataset
                            st.session_state.active_dataset = file_key
                            st.rerun()
                    except Exception as fallback_error:
                        st.error(
                            tx(
                                "Dosya ayrıştırılamadı: {error}",
                                "Could not parse file: {error}",
                                error=fallback_error,
                            )
                        )

    with sample_tab:
        st.markdown(tx("Test için örnek veriyi yükleyin:", "Load built-in sample data for testing:"))

        sample_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sample_data")

        sample_files = {
            tx("DSC - Polimer Erime", "DSC - Polymer Melting"): "dsc_polymer_melting.csv",
            tx("TGA - Kalsiyum Oksalat", "TGA - Calcium Oxalate"): "tga_calcium_oxalate.csv",
            tx("DSC - Çoklu Isıtma Hızı Kissinger", "DSC - Multi-Rate Kissinger"): "dsc_multirate_kissinger.csv",
        }

        for label, filename in sample_files.items():
            filepath = os.path.join(sample_dir, filename)
            if os.path.exists(filepath):
                if st.button(f"{tx('Yükle', 'Load')}: {label}", key=f"sample_{filename}"):
                    try:
                        dataset = read_thermal_data(filepath)
                        dataset.metadata["file_name"] = filename
                        dataset.metadata.setdefault("display_name", filename)
                        st.session_state.datasets[filename] = dataset
                        st.session_state.active_dataset = filename
                        _log_event(
                            tx("Veri Yüklendi", "Data Loaded"),
                            f"{label} ({dataset.data_type}, {dataset.metadata.get('vendor', 'Generic')}, {len(dataset.data)} pts)",
                            t("home.title"),
                        )
                        st.success(tx("**{label}** yüklendi.", "Loaded **{label}**.", label=label))
                        st.rerun()
                    except Exception as error:
                        st.error(
                            tx(
                                "Örnek veri yüklenemedi: {error}",
                                "Error loading sample: {error}",
                                error=error,
                            )
                        )

    if st.session_state.datasets:
        st.divider()
        st.header(tx("Yüklenen Veri Setleri", "Loaded Datasets"))

        dataset_names = list(st.session_state.datasets.keys())
        active_dataset = st.session_state.get("active_dataset")
        default_index = dataset_names.index(active_dataset) if active_dataset in dataset_names else 0

        cols = st.columns([3, 1])
        with cols[0]:
            selected = st.selectbox(
                tx("Görüntülenecek / analiz edilecek veri seti", "Select dataset to view or analyze"),
                dataset_names,
                index=default_index,
                key="dataset_selector",
            )
        with cols[1]:
            if st.button(tx("Kaldır", "Remove"), key="remove_dataset"):
                del st.session_state.datasets[selected]
                st.session_state.pop(f"dsc_state_{selected}", None)
                st.session_state.pop(f"tga_state_{selected}", None)
                st.session_state.pop(f"dta_state_{selected}", None)
                workspace = st.session_state.get("comparison_workspace", {})
                if workspace.get("selected_datasets"):
                    workspace["selected_datasets"] = [
                        key for key in workspace["selected_datasets"] if key != selected
                    ]
                    if not workspace["selected_datasets"]:
                        workspace["figure_key"] = None
                for result_key in list(st.session_state.get("results", {}).keys()):
                    if st.session_state.results[result_key].get("dataset_key") == selected:
                        del st.session_state.results[result_key]
                if st.session_state.active_dataset == selected:
                    st.session_state.active_dataset = None
                st.rerun()

        st.session_state.active_dataset = selected

        if selected:
            dataset = st.session_state.datasets[selected]

            info_cols = st.columns(4)
            info_cols[0].metric(tx("Tip", "Type"), dataset.data_type)
            info_cols[1].metric("Vendor", dataset.metadata.get("vendor", "Generic"))
            info_cols[2].metric(tx("Nokta", "Points"), str(len(dataset.data)))
            info_cols[3].metric(
                tx("Isıtma Hızı", "Heating Rate"),
                str(dataset.metadata.get("heating_rate") or "—"),
            )

            render_data_preview(dataset, key_prefix=f"prev_{selected}")

            st.subheader(tx("Hızlı Görünüm", "Quick View"))
            if "temperature" in dataset.data.columns and "signal" in dataset.data.columns:
                if dataset.data_type == "DSC":
                    y_label = tx(
                        f"Isı Akışı ({dataset.units.get('signal', 'mW')})",
                        f"Heat Flow ({dataset.units.get('signal', 'mW')})",
                    )
                elif dataset.data_type == "TGA":
                    y_label = tx(
                        f"Kütle ({dataset.units.get('signal', '%')})",
                        f"Mass ({dataset.units.get('signal', '%')})",
                    )
                elif dataset.data_type == "DTA":
                    y_label = f"ΔT ({dataset.units.get('signal', 'µV')})"
                else:
                    y_label = tx("Sinyal", "Signal")

                fig = create_thermal_plot(
                    dataset.data["temperature"].values,
                    dataset.data["signal"].values,
                    title=f"{dataset.data_type} - {dataset.metadata.get('file_name', tx('Veri', 'Data'))}",
                    x_label=tx(
                        f"Sıcaklık ({dataset.units.get('temperature', '°C')})",
                        f"Temperature ({dataset.units.get('temperature', '°C')})",
                    ),
                    y_label=y_label,
                )
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        st.markdown(
            (
                '<div class="status-bar">'
                + tx(
                    "Önerilen sonraki adım: çoklu overlay için Karşılaştırma Alanı'na geçin veya aktif koşu için doğrudan DSC / TGA analizini açın.",
                    "Recommended next step: open Compare Workspace for multi-run overlays, or continue directly into DSC / TGA analysis for the active run.",
                )
                + "</div>"
            ),
            unsafe_allow_html=True,
        )
