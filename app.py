"""ThermoAnalyzer - Streamlit entrypoint.

Vendor-independent thermal analysis data processing tool.
Supports DSC, TGA, and DTA data analysis.

Run with: streamlit run app.py
"""

import streamlit as st

st.set_page_config(
    page_title="ThermoAnalyzer",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Professional CSS ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* Global font */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Dark sidebar - NETZSCH / TA Instruments style */
section[data-testid="stSidebar"] {
    background-color: #1A1A2E !important;
    color: #E0E0E0 !important;
}
section[data-testid="stSidebar"] * {
    color: #E0E0E0 !important;
}
section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stRadio label {
    color: #B0B0C0 !important;
}
section[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.1) !important;
}

/* Metric cards - clean scientific style */
div[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid #E2E6ED;
    border-radius: 6px;
    padding: 12px 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
div[data-testid="stMetric"] label {
    font-size: 0.7rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    color: #6B7280 !important;
}
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    font-size: 1.3rem !important;
    font-weight: 700 !important;
    color: #1A1A2E !important;
}

/* Tab ribbon - professional grey background */
div[data-testid="stTabs"] > div:first-child {
    background-color: #F0F2F6;
    border-radius: 6px 6px 0 0;
    padding: 0 8px;
}
button[data-baseweb="tab"] {
    font-weight: 500 !important;
    font-size: 0.85rem !important;
    color: #4B5563 !important;
    border-bottom: 2px solid transparent !important;
    padding: 10px 16px !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: #0B5394 !important;
    border-bottom: 2px solid #0B5394 !important;
    font-weight: 600 !important;
}

/* Primary buttons - corporate blue */
div.stButton > button[kind="primary"],
div.stButton > button {
    background-color: #0B5394 !important;
    color: white !important;
    border: none !important;
    font-weight: 500 !important;
    border-radius: 4px !important;
    transition: background-color 0.2s !important;
}
div.stButton > button:hover {
    background-color: #094075 !important;
}

/* Download buttons - professional green */
div.stDownloadButton > button {
    background-color: #047857 !important;
    color: white !important;
    border: none !important;
    font-weight: 500 !important;
}
div.stDownloadButton > button:hover {
    background-color: #065F46 !important;
}

/* File uploader - dashed border, clean */
div[data-testid="stFileUploader"] > div:first-child {
    border: 2px dashed #CBD5E1 !important;
    border-radius: 8px !important;
    background: #F8FAFC !important;
    transition: border-color 0.2s !important;
}
div[data-testid="stFileUploader"] > div:first-child:hover {
    border-color: #0B5394 !important;
}

/* Status bar class - plot footer info bar */
.status-bar {
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 0.75rem;
    color: #6B7280;
    background: #F3F4F6;
    border: 1px solid #E5E7EB;
    border-radius: 0 0 6px 6px;
    padding: 6px 12px;
    margin-top: -8px;
    margin-bottom: 16px;
}

/* Sidebar branding */
.sidebar-brand {
    font-family: 'Inter', sans-serif;
    font-weight: 700;
    font-size: 1.1rem;
    letter-spacing: 0.08em;
    color: #FFFFFF !important;
    padding: 8px 0 4px 0;
}
.sidebar-version {
    font-size: 0.7rem;
    color: #7B8BA3 !important;
    letter-spacing: 0.05em;
}
.sidebar-badge {
    display: inline-block;
    background: #0B5394;
    color: #FFFFFF !important;
    font-size: 0.7rem;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 10px;
    margin-top: 4px;
}

/* Expander styling */
details[data-testid="stExpander"] summary {
    font-weight: 500 !important;
}

/* Dataframe styling */
div[data-testid="stDataFrame"] {
    border: 1px solid #E2E6ED;
    border-radius: 6px;
}
</style>
""", unsafe_allow_html=True)

# --- Sidebar branding ---
with st.sidebar:
    st.markdown(
        '<div class="sidebar-brand">THERMOANALYZER</div>'
        '<div class="sidebar-version">v1.0 &middot; Thermal Analysis Suite</div>',
        unsafe_allow_html=True,
    )
    n_datasets = len(st.session_state.get("datasets", {}))
    if n_datasets > 0:
        st.markdown(
            f'<div class="sidebar-badge">{n_datasets} dataset{"s" if n_datasets != 1 else ""} loaded</div>',
            unsafe_allow_html=True,
        )
    st.markdown("---")

# --- Page imports ---
from ui.components.history_tracker import render_history_sidebar
from ui.home import render as home_render
from ui.dsc_page import render as dsc_render
from ui.tga_page import render as tga_render
from ui.dta_page import render as dta_render
from ui.kinetics_page import render as kinetics_render
from ui.deconvolution_page import render as deconv_render
from ui.export_page import render as export_render

# --- Navigation ---
pages = {
    "Data": [
        st.Page(home_render, title="Import Data", icon="📂", default=True, url_path="upload"),
    ],
    "Analysis": [
        st.Page(dsc_render, title="DSC Analysis", icon="📈", url_path="dsc"),
        st.Page(tga_render, title="TGA Analysis", icon="📉", url_path="tga"),
        st.Page(dta_render, title="DTA Analysis", icon="📊", url_path="dta"),
        st.Page(kinetics_render, title="Kinetic Analysis", icon="⚡", url_path="kinetics"),
        st.Page(deconv_render, title="Peak Deconvolution", icon="🔍", url_path="deconvolution"),
    ],
    "Output": [
        st.Page(export_render, title="Export & Report", icon="💾", url_path="export"),
    ],
}

pg = st.navigation(pages)

# --- Pipeline history in sidebar ---
with st.sidebar:
    with st.expander("Analysis Pipeline", expanded=False):
        render_history_sidebar()

# --- About panel & footer in sidebar ---
with st.sidebar:
    st.markdown("---")
    with st.expander("About ThermoAnalyzer"):
        st.markdown(
            "**ThermoAnalyzer v1.0**\n\n"
            "Open-source, vendor-independent thermal analysis data processing tool.\n\n"
            "**Standards Compliance**\n"
            "- ASTM E967 — DSC Temperature & Enthalpy Calibration\n"
            "- ASTM E1131 — Compositional Analysis by TGA\n"
            "- ASTM E1356 — Glass Transition by DSC\n"
            "- ICTAC Kinetics Committee recommendations for kinetic computations\n\n"
            "**Citation**"
        )
        st.code(
            "@software{thermoanalyzer,\n"
            "  title  = {ThermoAnalyzer},\n"
            "  version = {1.0},\n"
            "  year   = {2025},\n"
            "  note   = {Open-source thermal analysis suite}\n"
            "}",
            language="bibtex",
        )
        st.caption(
            "Built with Streamlit + Plotly + SciPy\n\n"
            "License: MIT"
        )

pg.run()
