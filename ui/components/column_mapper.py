"""Column mapping widget for mapping file columns to standard thermal data columns."""

import streamlit as st
import pandas as pd

from utils.i18n import tx


def render_column_mapper(df, guessed_mapping=None, data_type=None, key_prefix="colmap"):
    """Render column mapping UI and return user-confirmed mapping.

    Parameters
    ----------
    df : pd.DataFrame
        The loaded dataframe with original columns.
    guessed_mapping : dict, optional
        Auto-detected mapping: {'temperature': col, 'signal': col, 'time': col, 'data_type': str}
    data_type : str, optional
        Override data type ('DSC', 'TGA', 'DTA').
    key_prefix : str
        Unique key prefix for Streamlit widgets.

    Returns
    -------
    dict or None
        Confirmed mapping dict, or None if user hasn't confirmed yet.
    """
    if guessed_mapping is None:
        guessed_mapping = {}

    columns = list(df.columns)
    none_label = tx("-- Yok --", "-- None --")
    none_option = [none_label]
    col_options = none_option + columns

    st.subheader(tx("Kolon Eşleme", "Column Mapping"))

    detected_type = guessed_mapping.get("data_type", "unknown")
    type_options = ["DSC", "TGA", "DTA", "FTIR", "RAMAN"]
    default_idx = 0
    if data_type and data_type in type_options:
        default_idx = type_options.index(data_type)
    elif detected_type in type_options:
        default_idx = type_options.index(detected_type)

    selected_type = st.selectbox(
        tx("Veri Tipi", "Data Type"),
        type_options,
        index=default_idx,
        key=f"{key_prefix}_type",
    )

    # Signal label depends on data type
    signal_labels = {
        "DSC": tx("Isı Akışı Kolonu", "Heat Flow Column"),
        "TGA": tx("Kütle / Ağırlık Kolonu", "Mass / Weight Column"),
        "DTA": tx("ΔT / Sinyal Kolonu", "ΔT / Signal Column"),
        "FTIR": tx("Absorbans / Geçirgenlik Kolonu", "Absorbance / Transmittance Column"),
        "RAMAN": tx("Raman Yoğunluk Kolonu", "Raman Intensity Column"),
    }
    signal_label = signal_labels.get(selected_type, tx("Sinyal Kolonu", "Signal Column"))
    axis_labels = {
        "FTIR": tx("Dalga Sayısı Kolonu", "Wavenumber Column"),
        "RAMAN": tx("Raman Shift Kolonu", "Raman Shift Column"),
    }
    axis_label = axis_labels.get(selected_type, tx("Sıcaklık Kolonu", "Temperature Column"))

    col1, col2, col3 = st.columns(3)

    # Temperature column
    with col1:
        temp_guess = guessed_mapping.get("temperature")
        temp_default = col_options.index(temp_guess) if temp_guess in columns else 0
        temp_col = st.selectbox(
            axis_label,
            col_options,
            index=temp_default,
            key=f"{key_prefix}_temp",
        )

    # Signal column
    with col2:
        sig_guess = guessed_mapping.get("signal")
        sig_default = col_options.index(sig_guess) if sig_guess in columns else 0
        sig_col = st.selectbox(
            signal_label,
            col_options,
            index=sig_default,
            key=f"{key_prefix}_signal",
        )

    # Time column (optional)
    with col3:
        time_guess = guessed_mapping.get("time")
        time_default = col_options.index(time_guess) if time_guess in columns else 0
        time_col = st.selectbox(
            tx("Zaman Kolonu (opsiyonel)", "Time Column (optional)"),
            col_options,
            index=time_default,
            key=f"{key_prefix}_time",
        )

    # Metadata inputs
    st.subheader(tx("Numune Metadatası", "Sample Metadata"))
    meta_col1, meta_col2, meta_col3 = st.columns(3)
    with meta_col1:
        sample_name = st.text_input(tx("Numune Adı", "Sample Name"), value="", key=f"{key_prefix}_name")
    with meta_col2:
        sample_mass = st.number_input(
            tx("Numune Kütlesi (mg)", "Sample Mass (mg)"), min_value=0.0, value=0.0,
            step=0.1, format="%.2f", key=f"{key_prefix}_mass",
        )
    with meta_col3:
        heating_rate = st.number_input(
            tx("Isıtma Hızı (°C/dk)", "Heating Rate (°C/min)"), min_value=0.0, value=10.0,
            step=1.0, format="%.1f", key=f"{key_prefix}_rate",
        )

    # Validation
    errors = []
    if temp_col == none_label:
        errors.append(tx("Sıcaklık kolonu zorunludur.", "Temperature column is required."))
    if sig_col == none_label:
        errors.append(tx("Sinyal kolonu zorunludur.", "Signal column is required."))
    if temp_col != none_label and temp_col == sig_col:
        errors.append(tx("Sıcaklık ve sinyal kolonları farklı olmalıdır.", "Temperature and signal columns must be different."))

    if errors:
        for e in errors:
            st.warning(e)
        return None

    mapping = {
        "temperature": temp_col if temp_col != none_label else None,
        "signal": sig_col if sig_col != none_label else None,
        "time": time_col if time_col != none_label else None,
        "data_type": selected_type,
        "metadata": {
            "sample_name": sample_name or tx("Bilinmiyor", "Unknown"),
            "sample_mass": sample_mass if sample_mass > 0 else None,
            "heating_rate": heating_rate if heating_rate > 0 else None,
        },
    }
    return mapping
