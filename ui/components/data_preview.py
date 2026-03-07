"""Data preview widget for displaying loaded thermal datasets."""

import streamlit as st
import pandas as pd

from utils.i18n import tx


def render_data_preview(dataset, key_prefix="preview"):
    """Render a data preview section for a ThermalDataset."""
    st.subheader(tx("Veri Önizleme", "Data Preview"))

    # Compact 4-column metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(tx("Veri Tipi", "Data Type"), dataset.data_type)
    c2.metric(tx("Nokta", "Points"), f"{len(dataset.data):,}")
    c3.metric(tx("Kolon", "Columns"), len(dataset.data.columns))
    mass = dataset.metadata.get("sample_mass")
    c4.metric(tx("Numune Kütlesi", "Sample Mass"), f"{mass} mg" if mass else tx("Yok", "N/A"))

    # Temperature range as status bar
    if "temperature" in dataset.data.columns:
        temps = dataset.data["temperature"]
        t_unit = dataset.units.get("temperature", "\u00b0C")
        st.markdown(
            f'<div class="status-bar">'
            f'T<sub>min</sub> {temps.min():.2f} {t_unit} &nbsp;\u2502&nbsp; '
            f'T<sub>max</sub> {temps.max():.2f} {t_unit} &nbsp;\u2502&nbsp; '
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
