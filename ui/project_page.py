"""Project workspace overview page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.result_serialization import split_valid_results
from ui.components.chrome import render_page_header
from utils.i18n import t


def render():
    render_page_header(t("project.title"), t("project.caption"), badge=t("project.hero_badge"))
    lang = st.session_state.get("ui_language", "tr")

    datasets = st.session_state.get("datasets", {})
    valid_results, issues = split_valid_results(st.session_state.get("results", {}))
    figures = st.session_state.get("figures", {}) or {}
    workspace = st.session_state.get("comparison_workspace", {}) or {}

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Veri Seti" if lang == "tr" else "Datasets", str(len(datasets)))
    m2.metric("Kayıtlı Sonuç" if lang == "tr" else "Saved Results", str(len(valid_results)))
    m3.metric("Görsel" if lang == "tr" else "Figures", str(len(figures)))
    m4.metric("Geçmiş Adımı" if lang == "tr" else "History Steps", str(len(st.session_state.get("analysis_history", []))))

    if datasets:
        st.subheader("Yüklenen Koşular" if lang == "tr" else "Loaded Runs")
        dataset_rows = []
        for key, dataset in datasets.items():
            dataset_rows.append(
                {
                    ("Anahtar" if lang == "tr" else "Key"): key,
                    ("Tip" if lang == "tr" else "Type"): dataset.data_type,
                    "Vendor": dataset.metadata.get("vendor", "Generic"),
                    ("Numune" if lang == "tr" else "Sample"): dataset.metadata.get("sample_name") or ("Adsız" if lang == "tr" else "Unnamed"),
                    ("Isıtma Hızı" if lang == "tr" else "Heating Rate"): dataset.metadata.get("heating_rate") or "—",
                    ("Nokta" if lang == "tr" else "Points"): len(dataset.data),
                }
            )
        st.dataframe(pd.DataFrame(dataset_rows), width="stretch", hide_index=True)

    if valid_results:
        st.subheader("Kayıtlı Sonuç Kayıtları" if lang == "tr" else "Saved Result Records")
        result_rows = []
        for record in valid_results.values():
            result_rows.append(
                {
                    "ID": record["id"],
                    ("Tip" if lang == "tr" else "Type"): record["analysis_type"],
                    ("Durum" if lang == "tr" else "Status"): record["status"],
                    ("Veri Seti" if lang == "tr" else "Dataset"): record.get("dataset_key") or "—",
                    ("Satır" if lang == "tr" else "Rows"): len(record.get("rows", [])),
                }
            )
        st.dataframe(pd.DataFrame(result_rows), width="stretch", hide_index=True)

    if workspace.get("selected_datasets"):
        st.subheader("Karşılaştırma Alanı" if lang == "tr" else "Comparison Workspace")
        st.write(f"**{'Tip' if lang == 'tr' else 'Type'}:** {workspace.get('analysis_type', 'N/A')}")
        st.write(f"**{'Seçili koşular' if lang == 'tr' else 'Selected runs'}:** {', '.join(workspace['selected_datasets'])}")
        if workspace.get("figure_key"):
            st.write(f"**{'Kaydedilen görsel' if lang == 'tr' else 'Saved figure'}:** {workspace['figure_key']}")
        if workspace.get("notes"):
            st.write(f"**{'Notlar' if lang == 'tr' else 'Notes'}**")
            st.write(workspace["notes"])

    if issues:
        st.warning("Bazı sonuç kayıtları eksik; export sırasında atlanacak." if lang == "tr" else "Some result records are incomplete and will be skipped from exports.")
        for issue in issues:
            st.caption(f"- {issue}")

    st.info(
        "Sidebar’daki `Proje` panelinden yeni proje açabilir, dosyaya kaydedebilir ve proje yükleyebilirsin."
        if lang == "tr"
        else "Use the sidebar `Project` panel for `New Project`, `Save Project to File`, and `Load Project`."
    )

