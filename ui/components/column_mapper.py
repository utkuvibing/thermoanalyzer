"""Column mapping widget for mapping file columns to standard thermal data columns."""

import streamlit as st
import pandas as pd


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
    none_option = ["-- None --"]
    col_options = none_option + columns

    st.subheader("Column Mapping")

    detected_type = guessed_mapping.get("data_type", "unknown")
    type_options = ["DSC", "TGA", "DTA"]
    default_idx = 0
    if data_type and data_type in type_options:
        default_idx = type_options.index(data_type)
    elif detected_type in type_options:
        default_idx = type_options.index(detected_type)

    selected_type = st.selectbox(
        "Data Type",
        type_options,
        index=default_idx,
        key=f"{key_prefix}_type",
    )

    # Signal label depends on data type
    signal_labels = {
        "DSC": "Heat Flow Column",
        "TGA": "Mass / Weight Column",
        "DTA": "ΔT / Signal Column",
    }
    signal_label = signal_labels.get(selected_type, "Signal Column")

    col1, col2, col3 = st.columns(3)

    # Temperature column
    with col1:
        temp_guess = guessed_mapping.get("temperature")
        temp_default = col_options.index(temp_guess) if temp_guess in columns else 0
        temp_col = st.selectbox(
            "Temperature Column",
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
            "Time Column (optional)",
            col_options,
            index=time_default,
            key=f"{key_prefix}_time",
        )

    # Metadata inputs
    st.subheader("Sample Metadata")
    meta_col1, meta_col2, meta_col3 = st.columns(3)
    with meta_col1:
        sample_name = st.text_input("Sample Name", value="", key=f"{key_prefix}_name")
    with meta_col2:
        sample_mass = st.number_input(
            "Sample Mass (mg)", min_value=0.0, value=0.0,
            step=0.1, format="%.2f", key=f"{key_prefix}_mass",
        )
    with meta_col3:
        heating_rate = st.number_input(
            "Heating Rate (°C/min)", min_value=0.0, value=10.0,
            step=1.0, format="%.1f", key=f"{key_prefix}_rate",
        )

    # Validation
    errors = []
    if temp_col == "-- None --":
        errors.append("Temperature column is required.")
    if sig_col == "-- None --":
        errors.append("Signal column is required.")
    if temp_col != "-- None --" and temp_col == sig_col:
        errors.append("Temperature and signal columns must be different.")

    if errors:
        for e in errors:
            st.warning(e)
        return None

    mapping = {
        "temperature": temp_col if temp_col != "-- None --" else None,
        "signal": sig_col if sig_col != "-- None --" else None,
        "time": time_col if time_col != "-- None --" else None,
        "data_type": selected_type,
        "metadata": {
            "sample_name": sample_name or "Unknown",
            "sample_mass": sample_mass if sample_mass > 0 else None,
            "heating_rate": heating_rate if heating_rate > 0 else None,
        },
    }
    return mapping
