"""Home page - Data upload and column mapping."""

import os

import pandas as pd
import streamlit as st

from core.data_io import detect_file_format, read_thermal_data
from core.validation import validate_thermal_dataset
from ui.components.chrome import render_page_header
from ui.components.column_mapper import render_column_mapper
from ui.components.data_preview import render_data_preview
from ui.components.history_tracker import _log_event
from ui.components.plot_builder import PLOTLY_CONFIG, create_thermal_plot
from ui.components.workflow_guide import render_home_workflow_guide
from utils.diagnostics import record_exception
from utils.i18n import t, tx
from utils.session_state import ensure_session_state


def render():
    ensure_session_state()

    render_page_header(t("home.title"), t("home.caption"), badge=t("home.hero_badge"))
    render_home_workflow_guide()
    st.info(
        tx(
            "Bu beta build'de kararlı akış Veri Alma -> Karşılaştırma Alanı -> DSC/TGA/DTA/FTIR/RAMAN/XRD Analizi -> Toplu Şablon Uygulayıcı -> Rapor/Proje Kaydı zinciridir. Kinetik ve dekonvolüsyon modülleri önizleme kapsamındadır.",
            "In this beta build, the stable workflow is Import -> Compare Workspace -> DSC/TGA/DTA/FTIR/RAMAN/XRD Analysis -> Batch Template Runner -> Report/Project Save. Kinetics and deconvolution remain preview modules.",
        )
    )

    datasets = st.session_state.get("datasets", {})
    if datasets:
        vendors = {ds.metadata.get("vendor", "Generic") for ds in datasets.values()}
        dsc_count = sum(1 for ds in datasets.values() if ds.data_type == "DSC")
        tga_count = sum(1 for ds in datasets.values() if ds.data_type == "TGA")
        dta_count = sum(1 for ds in datasets.values() if ds.data_type == "DTA")
        ftir_count = sum(1 for ds in datasets.values() if ds.data_type == "FTIR")
        raman_count = sum(1 for ds in datasets.values() if ds.data_type == "RAMAN")
        xrd_count = sum(1 for ds in datasets.values() if ds.data_type == "XRD")
        m1, m2, m3 = st.columns(3)
        m1.metric(tx("Yüklü Koşu", "Loaded Runs"), str(len(datasets)))
        m2.metric("D / T / DTA / F / R / X", f"{dsc_count} / {tga_count} / {dta_count} / {ftir_count} / {raman_count} / {xrd_count}")
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
                    validation = validate_thermal_dataset(dataset, analysis_type=dataset.data_type)
                    if validation["status"] == "fail":
                        st.error(
                            tx(
                                "{file_name} kararlı iş akışına alınmadı: {issues}",
                                "{file_name} was blocked from the stable workflow: {issues}",
                                file_name=uploaded_file.name,
                                issues="; ".join(validation["issues"]),
                            )
                        )
                        continue
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
                        dataset_key=file_key,
                        parameters={"validation_status": validation["status"]},
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
                    if dataset.metadata.get("import_review_required"):
                        st.warning(
                            tx(
                                "İçe aktarma otomatik ama inceleme gerektiriyor. Veri tipi, kolonlar ve sinyal birimini analizden önce kontrol edin.",
                                "Import completed with review flags. Confirm the data type, columns, and signal unit before analysis.",
                            )
                        )
                    st.caption(
                        tx(
                            "İçe aktarım güveni: {confidence} | Algılanan tip: {analysis_type} | Algılanan vendor: {vendor}",
                            "Import confidence: {confidence} | Inferred type: {analysis_type} | Inferred vendor: {vendor}",
                            confidence=str(dataset.metadata.get("import_confidence", "n/a")).upper(),
                            analysis_type=dataset.metadata.get("inferred_analysis_type", dataset.data_type),
                            vendor=dataset.metadata.get("inferred_vendor", dataset.metadata.get("vendor", "Generic")),
                        )
                    )
                    emitted_warnings = []
                    for warning in (dataset.metadata.get("import_warnings", []) or []) + (validation["warnings"] or []):
                        if warning and warning not in emitted_warnings:
                            emitted_warnings.append(warning)
                            st.warning(warning)

                except Exception as error:
                    error_id = record_exception(
                        st.session_state,
                        area="import",
                        action="initial_import",
                        message="Import pipeline failed while reading uploaded data.",
                        context={"file_name": uploaded_file.name},
                        exception=error,
                    )
                    st.error(
                        tx(
                            "{file_name} yüklenirken hata oluştu: {error}",
                            "Error loading {file_name}: {error}",
                            file_name=uploaded_file.name,
                            error=f"{error} (Error ID: {error_id})",
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
                            validation = validate_thermal_dataset(dataset, analysis_type=dataset.data_type)
                            if validation["status"] == "fail":
                                st.error(
                                    tx(
                                        "Yeniden eşlenen veri kararlı iş akışına alınmadı: {issues}",
                                        "Re-mapped dataset was blocked from the stable workflow: {issues}",
                                        issues="; ".join(validation["issues"]),
                                    )
                                )
                                continue
                            validation = validate_thermal_dataset(dataset, analysis_type=dataset.data_type)
                            if validation["status"] == "fail":
                                st.error(
                                    tx(
                                        "Eşleme sonrası veri kararlı iş akışına alınmadı: {issues}",
                                        "Mapped dataset was blocked from the stable workflow: {issues}",
                                        issues="; ".join(validation["issues"]),
                                    )
                                )
                                continue
                            dataset.metadata["file_name"] = uploaded_file.name
                            dataset.metadata.setdefault("display_name", uploaded_file.name)
                            st.session_state.datasets[file_key] = dataset
                            st.session_state.active_dataset = file_key
                            for warning in validation["warnings"]:
                                st.warning(warning)
                            st.rerun()
                    except Exception as fallback_error:
                        error_id = record_exception(
                            st.session_state,
                            area="import",
                            action="fallback_import",
                            message="Fallback import with manual column mapping failed.",
                            context={"file_name": uploaded_file.name},
                            exception=fallback_error,
                        )
                        st.error(
                            tx(
                                "Dosya ayrıştırılamadı: {error}",
                                "Could not parse file: {error}",
                                error=f"{fallback_error} (Error ID: {error_id})",
                            )
                        )

    with sample_tab:
        st.markdown(tx("Test için örnek veriyi yükleyin:", "Load built-in sample data for testing:"))

        sample_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sample_data")

        sample_files = {
            tx("DSC - Polimer Erime", "DSC - Polymer Melting"): {
                "filename": "dsc_polymer_melting.csv",
                "data_type": "DSC",
            },
            tx("TGA - Kalsiyum Oksalat", "TGA - Calcium Oxalate"): {
                "filename": "tga_calcium_oxalate.csv",
                "data_type": "TGA",
            },
            tx("DSC - Çoklu Isıtma Hızı Kissinger", "DSC - Multi-Rate Kissinger"): {
                "filename": "dsc_multirate_kissinger.csv",
                "data_type": "DSC",
            },
            tx("DTA - TNAA (5 °C/dk, Mendeley)", "DTA - TNAA (5 °C/min, Mendeley)"): {
                "filename": "dta_tnaa_5c_mendeley.csv",
                "data_type": "DTA",
            },
            tx("FTIR - Particleboard (50 g, Figshare)", "FTIR - Particleboard (50 g, Figshare)"): {
                "filename": "ftir_particleboard_50g_figshare.csv",
                "data_type": "FTIR",
            },
            tx("Raman - CNT Spectrum (Figshare)", "Raman - CNT Spectrum (Figshare)"): {
                "filename": "raman_cnt_figshare.csv",
                "data_type": "RAMAN",
            },
            tx("XRD - 2024-0304 (Zenodo)", "XRD - 2024-0304 (Zenodo)"): {
                "filename": "xrd_2024_0304_zenodo.csv",
                "data_type": "XRD",
            },
        }

        for label, spec in sample_files.items():
            filename = spec["filename"]
            forced_data_type = spec.get("data_type")
            filepath = os.path.join(sample_dir, filename)
            if os.path.exists(filepath):
                if st.button(f"{tx('Yükle', 'Load')}: {label}", key=f"sample_{filename}"):
                    try:
                        dataset = read_thermal_data(filepath, data_type=forced_data_type)
                        validation = validate_thermal_dataset(dataset, analysis_type=dataset.data_type)
                        if validation["status"] == "fail":
                            st.error(
                                tx(
                                    "Örnek veri kararlı iş akışına alınmadı: {issues}",
                                    "Sample dataset was blocked from the stable workflow: {issues}",
                                    issues="; ".join(validation["issues"]),
                                )
                            )
                            continue
                        dataset.metadata["file_name"] = filename
                        dataset.metadata.setdefault("display_name", filename)
                        st.session_state.datasets[filename] = dataset
                        st.session_state.active_dataset = filename
                        _log_event(
                            tx("Veri Yüklendi", "Data Loaded"),
                            f"{label} ({dataset.data_type}, {dataset.metadata.get('vendor', 'Generic')}, {len(dataset.data)} pts)",
                            t("home.title"),
                            dataset_key=filename,
                            parameters={"validation_status": validation["status"]},
                        )
                        st.success(tx("**{label}** yüklendi.", "Loaded **{label}**.", label=label))
                        st.caption(
                            tx(
                                "İçe aktarım güveni: {confidence}",
                                "Import confidence: {confidence}",
                                confidence=str(dataset.metadata.get("import_confidence", "n/a")).upper(),
                            )
                        )
                        emitted_warnings = []
                        for warning in (dataset.metadata.get("import_warnings", []) or []) + (validation["warnings"] or []):
                            if warning and warning not in emitted_warnings:
                                emitted_warnings.append(warning)
                                st.warning(warning)
                        st.rerun()
                    except Exception as error:
                        error_id = record_exception(
                            st.session_state,
                            area="import",
                            action="sample_import",
                            message="Built-in sample import failed.",
                            context={"file_name": filename},
                            exception=error,
                        )
                        st.error(
                            tx(
                                "Örnek veri yüklenemedi: {error}",
                                "Error loading sample: {error}",
                                error=f"{error} (Error ID: {error_id})",
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
                st.session_state.pop(f"ftir_state_{selected}", None)
                st.session_state.pop(f"raman_state_{selected}", None)
                st.session_state.pop(f"xrd_state_{selected}", None)
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
                elif dataset.data_type == "FTIR":
                    y_label = tx(
                        f"Absorbans ({dataset.units.get('signal', 'a.u.')})",
                        f"Absorbance ({dataset.units.get('signal', 'a.u.')})",
                    )
                elif dataset.data_type == "RAMAN":
                    y_label = tx(
                        f"Yoğunluk ({dataset.units.get('signal', 'counts')})",
                        f"Intensity ({dataset.units.get('signal', 'counts')})",
                    )
                elif dataset.data_type == "XRD":
                    y_label = tx(
                        f"Yoğunluk ({dataset.units.get('signal', 'counts')})",
                        f"Intensity ({dataset.units.get('signal', 'counts')})",
                    )
                else:
                    y_label = tx("Sinyal", "Signal")

                if dataset.data_type == "FTIR":
                    x_label = tx(
                        f"Dalgasayısı ({dataset.units.get('temperature', 'cm^-1')})",
                        f"Wavenumber ({dataset.units.get('temperature', 'cm^-1')})",
                    )
                elif dataset.data_type == "RAMAN":
                    x_label = tx(
                        f"Raman Kayması ({dataset.units.get('temperature', 'cm^-1')})",
                        f"Raman Shift ({dataset.units.get('temperature', 'cm^-1')})",
                    )
                elif dataset.data_type == "XRD":
                    x_label = tx(
                        f"2θ ({dataset.units.get('temperature', 'degree_2theta')})",
                        f"2θ ({dataset.units.get('temperature', 'degree_2theta')})",
                    )
                else:
                    x_label = tx(
                        f"Sıcaklık ({dataset.units.get('temperature', '°C')})",
                        f"Temperature ({dataset.units.get('temperature', '°C')})",
                    )

                fig = create_thermal_plot(
                    dataset.data["temperature"].values,
                    dataset.data["signal"].values,
                    title=f"{dataset.data_type} - {dataset.metadata.get('file_name', tx('Veri', 'Data'))}",
                    x_label=x_label,
                    y_label=y_label,
                )
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        st.markdown(
            (
                '<div class="status-bar">'
                + tx(
                    "Önerilen sonraki adım: çoklu overlay için Karşılaştırma Alanı'na geçin veya aktif koşu için doğrudan DSC / TGA / DTA / FTIR / RAMAN / XRD analizini açın.",
                    "Recommended next step: open Compare Workspace for multi-run overlays, or continue directly into DSC / TGA / DTA / FTIR / RAMAN / XRD analysis for the active run.",
                )
                + "</div>"
            ),
            unsafe_allow_html=True,
        )
