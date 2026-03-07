"""Shared Streamlit session-state helpers."""

from __future__ import annotations

import copy

import streamlit as st


SESSION_DEFAULTS = {
    "ui_language": "tr",
    "datasets": {},
    "active_dataset": None,
    "results": {},
    "figures": {},
    "analysis_history": [],
    "branding": {
        "report_title": "ThermoAnalyzer Professional Report",
        "company_name": "",
        "lab_name": "",
        "analyst_name": "",
        "report_notes": "",
        "logo_bytes": None,
        "logo_name": "",
    },
    "comparison_workspace": {
        "analysis_type": "DSC",
        "selected_datasets": [],
        "notes": "",
        "figure_key": None,
        "saved_at": None,
    },
}

EPHEMERAL_KEYS = {
    "kissinger_result",
    "ofw_results",
    "deconv_result",
    "project_archive_bytes",
    "project_archive_ready",
    "prepared_data_exports",
    "prepared_results_csv",
    "prepared_results_xlsx",
    "prepared_report_docx",
    "prepared_report_pdf",
}

ANALYSIS_PREFIXES = ("dsc_state_", "tga_state_", "dta_state_")


def ensure_session_state() -> None:
    """Initialize shared session-state keys."""
    for key, default in SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = copy.deepcopy(default)


def clear_project_state() -> None:
    """Clear all project-related session-state entries."""
    keys = list(st.session_state.keys())
    for key in keys:
        if key in SESSION_DEFAULTS or key in EPHEMERAL_KEYS or key.startswith(ANALYSIS_PREFIXES):
            del st.session_state[key]
    ensure_session_state()


def replace_project_state(project_state: dict) -> None:
    """Replace current project state with a loaded project."""
    clear_project_state()
    for key, value in project_state.items():
        st.session_state[key] = value
    ensure_session_state()
