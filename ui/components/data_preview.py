"""Data preview widget for displaying loaded thermal datasets."""

import streamlit as st
import pandas as pd

from utils.i18n import tx


def render_data_preview(dataset, key_prefix="preview"):
    """Render a data preview section for a ThermalDataset."""
    st.subheader(tx("Veri Önizleme", "Data Preview"))

    # Compact 5-column metrics
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(tx("Veri Tipi", "Data Type"), dataset.data_type)
    c2.metric(tx("Nokta", "Points"), f"{len(dataset.data):,}")
    c3.metric(tx("Kolon", "Columns"), len(dataset.data.columns))
    mass = dataset.metadata.get("sample_mass")
    c4.metric(tx("Numune Kütlesi", "Sample Mass"), f"{mass} mg" if mass else tx("Yok", "N/A"))
    c5.metric(tx("İçe Aktarım Güveni", "Import Confidence"), str(dataset.metadata.get("import_confidence", "N/A")).upper())

    # Temperature range as status bar
    if "temperature" in dataset.data.columns:
        temps = dataset.data["temperature"]
        t_unit = dataset.units.get("temperature", "\u00b0C")
        if str(getattr(dataset, "data_type", "")).upper() == "XRD":
            min_label = tx("2\u03b8<sub>min</sub>", "2\u03b8<sub>min</sub>")
            max_label = tx("2\u03b8<sub>max</sub>", "2\u03b8<sub>max</sub>")
        else:
            min_label = "T<sub>min</sub>"
            max_label = "T<sub>max</sub>"
        st.markdown(
            f'<div class="status-bar">'
            f'{min_label} {temps.min():.2f} {t_unit} &nbsp;\u2502&nbsp; '
            f'{max_label} {temps.max():.2f} {t_unit} &nbsp;\u2502&nbsp; '
            f'N = {len(temps):,} {tx("nokta", "points")}'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Metadata as 2-column grid
    meta_items = [(k, v) for k, v in dataset.metadata.items() if v is not None and v != ""]
    if meta_items:
        with st.expander(tx("Metaveri", "Metadata"), expanded=False):
            mid = (len(meta_items) + 1) // 2
            mc1, mc2 = st.columns(2)
            with mc1:
                for k, v in meta_items[:mid]:
                    st.write(f"**{k}:** {v}")
            with mc2:
                for k, v in meta_items[mid:]:
                    st.write(f"**{k}:** {v}")

    import_warnings = [str(item) for item in (dataset.metadata.get("import_warnings") or []) if item]
    if import_warnings or dataset.metadata.get("import_review_required"):
        with st.expander(tx("İçe Aktarım İncelemesi", "Import Review"), expanded=False):
            st.write(
                f"**{tx('Algılanan analiz tipi', 'Inferred analysis type')}:** "
                f"{dataset.metadata.get('inferred_analysis_type', 'N/A')}"
            )
            st.write(
                f"**{tx('Algılanan sinyal birimi', 'Inferred signal unit')}:** "
                f"{dataset.metadata.get('inferred_signal_unit', 'N/A')}"
            )
            st.write(
                f"**{tx('Algılanan vendor', 'Inferred vendor')}:** "
                f"{dataset.metadata.get('inferred_vendor', dataset.metadata.get('vendor', 'N/A'))}"
            )
            st.write(
                f"**{tx('Vendor güveni', 'Vendor confidence')}:** "
                f"{dataset.metadata.get('vendor_detection_confidence', 'N/A')}"
            )
            for warning in import_warnings:
                st.warning(warning)

    with st.expander(tx("Kolon Eşleme", "Column Mapping"), expanded=False):
        for std_name, orig_name in dataset.original_columns.items():
            st.write(f"`{std_name}` \u2190 *{orig_name}*")

    with st.expander(tx("Birimler", "Units"), expanded=False):
        for k, v in dataset.units.items():
            st.write(f"**{k}:** {v}")

    num_rows = st.slider(
        tx("Gösterilecek satır", "Rows to display"), 5, min(100, len(dataset.data)), 10,
        key=f"{key_prefix}_rows",
    )
    st.dataframe(dataset.data.head(num_rows), use_container_width=True)

    # Statistics in a collapsed expander
    with st.expander(tx("İstatistikler", "Statistics"), expanded=False):
        st.dataframe(
            dataset.data.describe().round(4),
            use_container_width=True,
        )
