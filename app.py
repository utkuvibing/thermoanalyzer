"""MaterialScope - Streamlit entrypoint.

Vendor-independent thermal analysis data processing tool.
Supports DSC, TGA, DTA, FTIR, RAMAN, and XRD data analysis.

Run with: streamlit run app.py
"""

from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from core.reference_library import maybe_refresh_library_manifest
from utils.diagnostics import configure_diagnostics_logger
from utils.i18n import SUPPORTED_LANGUAGES, t, tx
from utils.license_manager import (
    APP_VERSION,
    commercial_mode_enabled,
    load_license_state,
)
from utils.runtime_flags import preview_modules_enabled
from utils.session_state import ensure_session_state, get_ui_theme

load_dotenv(dotenv_path=Path(__file__).resolve().with_name(".env"), override=False)

st.set_page_config(
    page_title="MaterialScope",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _theme_tokens(theme_mode: str) -> dict[str, str]:
    if theme_mode == "dark":
        return {
            "ink": "#E5EEF8",
            "muted": "#B8C6D8",
            "border": "#38506B",
            "panel": "rgba(17,24,39,0.84)",
            "panel_strong": "#121A2C",
            "accent": "#1597A8",
            "accent_strong": "#0F6E86",
            "gold": "#F59E0B",
            "bg_top": "#0A1422",
            "bg_bottom": "#132235",
            "sidebar_top": "#020817",
            "sidebar_bottom": "#0D1727",
            "sidebar_text": "#E2E8F0",
            "sidebar_muted": "#9FB0C7",
            "metric_bg": "linear-gradient(180deg, rgba(21,30,48,0.92) 0%, rgba(17,24,39,0.88) 100%)",
            "tab_bg": "rgba(17,24,39,0.76)",
            "tab_text": "#D2DEED",
            "tab_active": "rgba(21,151,168,0.24)",
            "field_bg": "rgba(19,31,49,0.76)",
            "field_gloss": "rgba(255,255,255,0.07)",
            "status_bg": "rgba(17,24,39,0.88)",
            "status_text": "#D5E1F0",
            "disabled_bg": "#314359",
            "disabled_ink": "#D6E0EB",
            "input_bg": "rgba(18,29,46,0.92)",
            "input_border": "#4A607B",
            "hero_start": "rgba(16,24,38,0.97)",
            "hero_overlay": "rgba(245,158,11,0.14)",
            "hero_end": "rgba(35,31,34,0.92)",
            "shadow": "rgba(2,6,23,0.36)",
            "alert_info_bg": "rgba(8,145,178,0.18)",
            "alert_info_border": "rgba(34,211,238,0.26)",
            "alert_warning_bg": "rgba(217,119,6,0.18)",
            "alert_warning_border": "rgba(251,191,36,0.24)",
            "alert_success_bg": "rgba(5,150,105,0.18)",
            "alert_success_border": "rgba(52,211,153,0.24)",
            "alert_error_bg": "rgba(220,38,38,0.18)",
            "alert_error_border": "rgba(248,113,113,0.24)",
        }
    return {
        "ink": "#0F172A",
        "muted": "#5A6578",
        "border": "#D1D9E0",
        "panel": "#FFFFFF",
        "panel_strong": "#F8FAFC",
        "accent": "#0E7490",
        "accent_strong": "#155E75",
        "gold": "#B45309",
        "bg_top": "#F0F2F5",
        "bg_bottom": "#E8EBF0",
        "sidebar_top": "#0F172A",
        "sidebar_bottom": "#18263A",
        "sidebar_text": "#E2E8F0",
        "sidebar_muted": "#A9B8CC",
        "metric_bg": "linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%)",
        "tab_bg": "#FFFFFF",
        "tab_text": "#3E5267",
        "tab_active": "rgba(14,116,144,0.12)",
        "field_bg": "#FAFBFC",
        "field_gloss": "rgba(255,255,255,0.36)",
        "status_bg": "#FFFFFF",
        "status_text": "#445163",
        "disabled_bg": "#C9D6E2",
        "disabled_ink": "#415264",
        "input_bg": "#FAFBFC",
        "input_border": "#D1D9E0",
        "hero_start": "rgba(245,248,251,0.95)",
        "hero_overlay": "rgba(180,83,9,0.08)",
        "hero_end": "rgba(235,240,245,0.90)",
        "shadow": "rgba(15,23,42,0.08)",
        "alert_info_bg": "rgba(8,145,178,0.12)",
        "alert_info_border": "rgba(14,116,144,0.20)",
        "alert_warning_bg": "rgba(217,119,6,0.12)",
        "alert_warning_border": "rgba(217,119,6,0.18)",
        "alert_success_bg": "rgba(5,150,105,0.12)",
        "alert_success_border": "rgba(5,150,105,0.18)",
        "alert_error_bg": "rgba(220,38,38,0.12)",
        "alert_error_border": "rgba(220,38,38,0.18)",
    }


ensure_session_state()
theme_mode = get_ui_theme()
theme_tokens = _theme_tokens(theme_mode)
st.session_state["diagnostics_log_path"] = configure_diagnostics_logger()
try:
    st.session_state["license_state"] = load_license_state(app_version=APP_VERSION)
except Exception as exc:
    st.session_state["license_state"] = {
        "status": "unlicensed" if commercial_mode_enabled() else "development",
        "message": f"Stored license could not be loaded: {exc}",
        "license": None,
        "days_remaining": None,
        "source": None,
        "commercial_mode": commercial_mode_enabled(),
    }
try:
    st.session_state["library_status"] = maybe_refresh_library_manifest(
        st.session_state.get("license_state")
    )
except Exception:
    st.session_state["library_status"] = None

# --- Professional CSS ---
theme_root_css = "\n".join(
    [
        f"    --ta-ink: {theme_tokens['ink']};",
        f"    --ta-muted: {theme_tokens['muted']};",
        f"    --ta-border: {theme_tokens['border']};",
        f"    --ta-panel: {theme_tokens['panel']};",
        f"    --ta-panel-strong: {theme_tokens['panel_strong']};",
        f"    --ta-accent: {theme_tokens['accent']};",
        f"    --ta-accent-strong: {theme_tokens['accent_strong']};",
        f"    --ta-gold: {theme_tokens['gold']};",
        f"    --ta-bg-top: {theme_tokens['bg_top']};",
        f"    --ta-bg-bottom: {theme_tokens['bg_bottom']};",
        f"    --ta-sidebar-top: {theme_tokens['sidebar_top']};",
        f"    --ta-sidebar-bottom: {theme_tokens['sidebar_bottom']};",
        f"    --ta-sidebar-text: {theme_tokens['sidebar_text']};",
        f"    --ta-sidebar-muted: {theme_tokens['sidebar_muted']};",
        f"    --ta-metric-bg: {theme_tokens['metric_bg']};",
        f"    --ta-tab-bg: {theme_tokens['tab_bg']};",
        f"    --ta-tab-text: {theme_tokens['tab_text']};",
        f"    --ta-tab-active: {theme_tokens['tab_active']};",
        f"    --ta-field-bg: {theme_tokens['field_bg']};",
        f"    --ta-field-gloss: {theme_tokens['field_gloss']};",
        f"    --ta-status-bg: {theme_tokens['status_bg']};",
        f"    --ta-status-text: {theme_tokens['status_text']};",
        f"    --ta-disabled-bg: {theme_tokens['disabled_bg']};",
        f"    --ta-disabled-ink: {theme_tokens['disabled_ink']};",
        f"    --ta-input-bg: {theme_tokens['input_bg']};",
        f"    --ta-input-border: {theme_tokens['input_border']};",
        f"    --ta-hero-start: {theme_tokens['hero_start']};",
        f"    --ta-hero-overlay: {theme_tokens['hero_overlay']};",
        f"    --ta-hero-end: {theme_tokens['hero_end']};",
        f"    --ta-shadow: {theme_tokens['shadow']};",
        f"    --ta-alert-info-bg: {theme_tokens['alert_info_bg']};",
        f"    --ta-alert-info-border: {theme_tokens['alert_info_border']};",
        f"    --ta-alert-warning-bg: {theme_tokens['alert_warning_bg']};",
        f"    --ta-alert-warning-border: {theme_tokens['alert_warning_border']};",
        f"    --ta-alert-success-bg: {theme_tokens['alert_success_bg']};",
        f"    --ta-alert-success-border: {theme_tokens['alert_success_border']};",
        f"    --ta-alert-error-bg: {theme_tokens['alert_error_bg']};",
        f"    --ta-alert-error-border: {theme_tokens['alert_error_border']};",
    ]
)
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root {
"""
    + theme_root_css
    + """
}

/* Global font */
html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    color: var(--ta-ink);
    background: transparent;
}

.stApp {
    background:
        radial-gradient(circle at top right, rgba(14,116,144,0.10), transparent 32%),
        linear-gradient(180deg, var(--ta-bg-top) 0%, var(--ta-bg-bottom) 100%);
}

.stApp, .stApp p, .stApp li, .stApp label, .stApp span, .stApp div {
    color: inherit;
}

[data-testid="stAppViewContainer"],
[data-testid="stHeader"] {
    background: transparent !important;
}

/* Dark sidebar - NETZSCH / TA Instruments style */
section[data-testid="stSidebar"] {
    background:
        linear-gradient(180deg, var(--ta-sidebar-top) 0%, var(--ta-sidebar-bottom) 100%) !important;
    color: var(--ta-sidebar-text) !important;
    border-right: 1px solid rgba(255,255,255,0.06);
}
section[data-testid="stSidebar"] div[data-testid="stSidebarHeader"] {
    padding-top: 0 !important;
    padding-bottom: 0.05rem !important;
}
section[data-testid="stSidebar"] div[data-testid="stSidebarUserContent"] {
    padding-top: 0 !important;
}
section[data-testid="stSidebar"] div[data-testid="stSidebarUserContent"] > div:first-child {
    margin-top: -0.55rem !important;
}
section[data-testid="stSidebar"] * {
    color: var(--ta-sidebar-text) !important;
}
section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stRadio label,
section[data-testid="stSidebar"] .stSegmentedControl label {
    color: var(--ta-sidebar-muted) !important;
}
section[data-testid="stSidebar"] .stSegmentedControl {
    margin-top: 0 !important;
    margin-bottom: 0.16rem !important;
}
section[data-testid="stSidebar"] .stSegmentedControl [data-baseweb="button-group"] {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}
section[data-testid="stSidebar"] .stSegmentedControl > div {
    width: fit-content !important;
    margin-left: auto !important;
}
section[data-testid="stSidebar"] .stSegmentedControl [role="radiogroup"] {
    gap: 0.14rem !important;
    flex-wrap: nowrap !important;
    width: fit-content !important;
    margin-left: auto !important;
}
section[data-testid="stSidebar"] .stSegmentedControl button,
section[data-testid="stSidebar"] [data-baseweb="button-group"] button,
section[data-testid="stSidebar"] .stSegmentedControl [role="radio"] {
    min-height: 1.55rem !important;
    min-width: 2.05rem !important;
    padding: 0.08rem 0.38rem !important;
    font-size: 0.63rem !important;
    line-height: 1 !important;
    border-radius: 4px !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    background: rgba(18, 29, 46, 0.72) !important;
    color: var(--ta-sidebar-text) !important;
    box-shadow: none !important;
}
section[data-testid="stSidebar"] .stSegmentedControl button[aria-pressed="true"],
section[data-testid="stSidebar"] [data-baseweb="button-group"] button[aria-pressed="true"],
section[data-testid="stSidebar"] [data-baseweb="button-group"] button[class*="segmented_controlActive"],
section[data-testid="stSidebar"] .stSegmentedControl [role="radio"][aria-checked="true"] {
    background: linear-gradient(180deg, var(--ta-accent) 0%, var(--ta-accent-strong) 100%) !important;
    color: #F8FAFC !important;
    border-color: rgba(255,255,255,0.12) !important;
}
section[data-testid="stSidebar"] .stSegmentedControl button[aria-pressed="false"],
section[data-testid="stSidebar"] [data-baseweb="button-group"] button[aria-pressed="false"],
section[data-testid="stSidebar"] .stSegmentedControl [role="radio"]:not([aria-checked="true"]) {
    background: rgba(18, 29, 46, 0.72) !important;
    color: var(--ta-sidebar-text) !important;
}
section[data-testid="stSidebar"] .stSegmentedControl button *,
section[data-testid="stSidebar"] [data-baseweb="button-group"] button *,
section[data-testid="stSidebar"] .stSegmentedControl [role="radio"] p {
    font-size: 0.63rem !important;
    line-height: 1 !important;
    color: inherit !important;
}
section[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.1) !important;
}

/* Metric cards - clean scientific style */
div[data-testid="stMetric"] {
    background: var(--ta-metric-bg);
    border: 1px solid var(--ta-border);
    border-radius: 16px;
    padding: 14px 18px;
    box-shadow: 0 10px 28px var(--ta-shadow);
}
div[data-testid="stMetric"] label {
    font-size: 0.7rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    color: var(--ta-muted) !important;
}
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    font-size: 1.3rem !important;
    font-weight: 700 !important;
    color: var(--ta-ink) !important;
}

/* Tab ribbon - professional grey background */
div[data-testid="stTabs"] > div:first-child {
    background-color: var(--ta-tab-bg);
    border: 1px solid var(--ta-border);
    border-radius: 14px;
    padding: 4px 8px;
}
button[data-baseweb="tab"] {
    font-weight: 500 !important;
    font-size: 0.85rem !important;
    color: var(--ta-tab-text) !important;
    border-bottom: 2px solid transparent !important;
    padding: 10px 16px !important;
    border-radius: 10px !important;
    background: transparent !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: var(--ta-accent-strong) !important;
    border-bottom: 2px solid transparent !important;
    font-weight: 600 !important;
    background: var(--ta-tab-active) !important;
    box-shadow: inset 0 0 0 1px rgba(14,116,144,0.18);
}

/* Primary buttons - corporate blue */
div.stButton > button[kind="primary"],
div.stButton > button {
    background: linear-gradient(180deg, var(--ta-accent) 0%, var(--ta-accent-strong) 100%) !important;
    color: white !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
    font-weight: 600 !important;
    border-radius: 12px !important;
    transition: transform 0.18s ease, box-shadow 0.18s ease !important;
    box-shadow: 0 10px 24px rgba(14,116,144,0.22), inset 0 1px 0 rgba(255,255,255,0.16);
}
div.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 14px 28px rgba(14,116,144,0.28);
}
div.stButton > button p,
div.stDownloadButton > button p {
    color: inherit !important;
}
div.stButton > button:disabled,
div.stDownloadButton > button:disabled {
    background: var(--ta-disabled-bg) !important;
    color: var(--ta-disabled-ink) !important;
    box-shadow: none !important;
    opacity: 1 !important;
    cursor: not-allowed !important;
}

/* Download buttons - professional green */
div.stDownloadButton > button {
    background: linear-gradient(180deg, #0F766E 0%, #115E59 100%) !important;
    color: white !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
    font-weight: 600 !important;
    border-radius: 12px !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.16);
}
div.stDownloadButton > button:hover {
    transform: translateY(-1px);
}

/* File uploader - dashed border, clean */
div[data-testid="stFileUploader"] > div:first-child,
div[data-testid="stFileUploaderDropzone"] {
    border: 2px dashed var(--ta-input-border) !important;
    border-radius: 18px !important;
    background: var(--ta-input-bg) !important;
    transition: border-color 0.2s !important;
    box-shadow: inset 0 1px 0 var(--ta-field-gloss);
    color: var(--ta-ink) !important;
}
/* Target the inner dropzone specifically */
[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"] {
    background: var(--ta-input-bg) !important;
}
[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"] > div {
    background: var(--ta-input-bg) !important;
}
div[data-testid="stFileUploader"] > div:first-child:hover,
div[data-testid="stFileUploaderDropzone"]:hover {
    border-color: var(--ta-accent) !important;
}
div[data-testid="stFileUploader"],
div[data-testid="stFileUploader"] * {
    color: var(--ta-ink) !important;
}
div[data-testid="stFileUploaderDropzoneInstructions"] {
    color: var(--ta-ink) !important;
}
div[data-testid="stFileUploaderDropzoneInstructions"] small,
div[data-testid="stFileUploaderDropzoneInstructions"] span,
div[data-testid="stFileUploaderDropzoneInstructions"] p {
    color: var(--ta-muted) !important;
}
div[data-testid="stFileUploader"] small,
div[data-testid="stFileUploader"] p,
div[data-testid="stFileUploader"] span:not([data-testid="stBaseButton-secondary"]) {
    color: var(--ta-muted) !important;
}
div[data-testid="stFileUploader"] svg {
    color: var(--ta-accent) !important;
    stroke: currentColor !important;
}
/* Browse files button */
[data-testid="stFileUploader"] [data-testid="stBaseButton-secondary"] {
    background: var(--ta-accent) !important;
    color: white !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
    border-radius: 10px !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.16) !important;
}
[data-testid="stFileUploader"] [data-testid="stBaseButton-secondary"] * {
    color: white !important;
}

/* Status bar class - plot footer info bar */
.status-bar {
    font-family: 'IBM Plex Mono', 'Consolas', 'Monaco', monospace;
    font-size: 0.75rem;
    color: var(--ta-status-text);
    background: var(--ta-status-bg);
    border: 1px solid var(--ta-border);
    border-radius: 0 0 14px 14px;
    padding: 8px 14px;
    margin-top: -8px;
    margin-bottom: 16px;
}

/* Sidebar branding */
.sidebar-brand {
    font-family: 'IBM Plex Mono', 'IBM Plex Sans', sans-serif;
    font-weight: 700;
    font-size: 1.18rem;
    letter-spacing: 0.02em;
    color: #FFFFFF !important;
    padding: 0;
    margin: 0 0 0.05rem 0;
    line-height: 1.25;
}
.sidebar-version {
    font-size: 0.78rem;
    color: #C1D0E0 !important;
    letter-spacing: 0.01em;
    line-height: 1.35;
    margin-bottom: 0;
    font-weight: 400;
}
.sidebar-license {
    font-size: 0.7rem;
    color: #94A7BE !important;
    margin-top: 0.15rem;
    margin-bottom: 0.1rem;
    line-height: 1.3;
}

/* Controls row below brand */
.sidebar-controls-row > div[data-testid="stVerticalBlock"] {
    gap: 0 !important;
    padding-top: 0 !important;
}
.sidebar-controls-row .stSegmentedControl {
    margin-top: 0 !important;
    margin-bottom: 0 !important;
}
.sidebar-controls-row .stSegmentedControl > div {
    width: fit-content !important;
}
.sidebar-badge {
    display: inline-block;
    background: rgba(14,116,144,0.22);
    color: #FFFFFF !important;
    font-size: 0.7rem;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 999px;
    margin-top: 4px;
    border: 1px solid rgba(255,255,255,0.08);
}

.sidebar-section-label {
    margin: 0.45rem 0 0.3rem 0;
    color: #C9D4E3 !important;
    font-size: 0.84rem;
    font-weight: 700;
    letter-spacing: 0.01em;
    text-transform: none;
}

.sidebar-nav-item-active {
    border-left-color: rgba(148, 196, 215, 0.88) !important;
    background: linear-gradient(90deg, rgba(148,196,215,0.11) 0%, rgba(148,196,215,0.03) 100%) !important;
}
section[data-testid="stSidebar"] div[data-testid="stPageLink-NavLink"] {
    margin: 0.06rem 0 0.16rem 0 !important;
}
section[data-testid="stSidebar"] div[data-testid="stPageLink-NavLink"] a,
section[data-testid="stSidebar"] div[data-testid="stPageLink-NavLink"] span[aria-disabled="true"] {
    display: grid !important;
    grid-template-columns: 1rem 1fr !important;
    align-items: center !important;
    column-gap: 0.6rem !important;
    padding: 0.38rem 0.45rem 0.38rem 0.7rem !important;
    margin: 0 !important;
    border-left: 2px solid transparent !important;
    border-radius: 0 10px 10px 0 !important;
    text-decoration: none !important;
    transition: background-color 0.14s ease, border-color 0.14s ease, color 0.14s ease !important;
    min-height: 2.1rem !important;
}
section[data-testid="stSidebar"] div[data-testid="stPageLink-NavLink"] a:hover {
    background: rgba(255,255,255,0.04) !important;
    border-left-color: rgba(201, 212, 227, 0.45) !important;
}
section[data-testid="stSidebar"] div[data-testid="stPageLink-NavLink"] a p,
section[data-testid="stSidebar"] div[data-testid="stPageLink-NavLink"] span[aria-disabled="true"] p {
    color: #DCE5F1 !important;
    font-size: 0.92rem !important;
    font-weight: 500 !important;
    line-height: 1.22 !important;
    margin: 0 !important;
}
section[data-testid="stSidebar"] div[data-testid="stPageLink-NavLink"] a[data-current-page="true"],
section[data-testid="stSidebar"] div[data-testid="stPageLink-NavLink"] span[aria-disabled="true"] {
    border-left-color: rgba(148, 196, 215, 0.88) !important;
    background: linear-gradient(90deg, rgba(148,196,215,0.11) 0%, rgba(148,196,215,0.03) 100%) !important;
}
section[data-testid="stSidebar"] div[data-testid="stPageLink-NavLink"] a[data-current-page="true"] p,
section[data-testid="stSidebar"] div[data-testid="stPageLink-NavLink"] span[aria-disabled="true"] p {
    color: #F2F6FB !important;
    font-weight: 600 !important;
}

/* Expander styling */
details[data-testid="stExpander"] summary {
    font-weight: 500 !important;
    color: var(--ta-ink) !important;
}
section[data-testid="stSidebar"] details[data-testid="stExpander"] {
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 12px !important;
    background: rgba(255,255,255,0.02) !important;
    margin: 0.25rem 0 0.4rem 0 !important;
}
section[data-testid="stSidebar"] details[data-testid="stExpander"] summary {
    padding-top: 0.2rem !important;
    padding-bottom: 0.2rem !important;
}
details[data-testid="stExpander"] {
    background: var(--ta-panel) !important;
    border: 1px solid var(--ta-border) !important;
    border-radius: 16px !important;
}

/* Dataframe styling */
div[data-testid="stDataFrame"] {
    border: 1px solid var(--ta-border);
    border-radius: 16px;
    overflow: hidden;
}

div[data-testid="stMarkdownContainer"] p {
    color: var(--ta-muted);
}
div[data-testid="stMarkdownContainer"] li,
div[data-testid="stCaptionContainer"],
div[data-testid="stCaptionContainer"] p {
    color: var(--ta-muted) !important;
}

div[data-testid="stVerticalBlockBorderWrapper"] {
    background: linear-gradient(180deg, var(--ta-panel) 0%, var(--ta-panel-strong) 100%) !important;
    border: 1px solid var(--ta-border) !important;
    box-shadow: 0 10px 28px var(--ta-shadow);
}

div[data-baseweb="notification"],
div[data-testid="stAlert"] {
    border-radius: 16px !important;
    border: 1px solid var(--ta-border) !important;
    background: var(--ta-panel) !important;
}
div[data-baseweb="notification"] *,
div[data-testid="stAlert"] * {
    color: var(--ta-ink) !important;
}
div[data-testid="stAlert"][kind="info"],
div[data-baseweb="notification"][kind="info"] {
    background: var(--ta-alert-info-bg) !important;
    border-color: var(--ta-alert-info-border) !important;
}
div[data-testid="stAlert"][kind="warning"],
div[data-baseweb="notification"][kind="warning"] {
    background: var(--ta-alert-warning-bg) !important;
    border-color: var(--ta-alert-warning-border) !important;
}
div[data-testid="stAlert"][kind="success"],
div[data-baseweb="notification"][kind="success"] {
    background: var(--ta-alert-success-bg) !important;
    border-color: var(--ta-alert-success-border) !important;
}
div[data-testid="stAlert"][kind="error"],
div[data-baseweb="notification"][kind="error"] {
    background: var(--ta-alert-error-bg) !important;
    border-color: var(--ta-alert-error-border) !important;
}

div[data-baseweb="base-input"] > div,
div[data-baseweb="select"] > div,
div[data-testid="stNumberInputContainer"] input,
div[data-testid="stTextInputRootElement"] input,
div[data-testid="stTextArea"] textarea {
    background: var(--ta-input-bg) !important;
    color: var(--ta-ink) !important;
    border-color: var(--ta-input-border) !important;
}

.stSelectbox svg,
.stMultiSelect svg,
.stNumberInput svg {
    color: var(--ta-muted) !important;
}

.ta-hero {
    position: relative;
    overflow: hidden;
    margin: 0 0 1.4rem 0;
    padding: 1.5rem 1.6rem;
    border-radius: 26px;
    border: 1px solid var(--ta-border);
    background:
        radial-gradient(circle at top right, var(--ta-hero-overlay), transparent 26%),
        linear-gradient(135deg, var(--ta-hero-start) 0%, var(--ta-hero-end) 100%);
    box-shadow: 0 20px 40px var(--ta-shadow);
}

.ta-hero-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.35rem 0.75rem;
    border-radius: 999px;
    background: rgba(180,83,9,0.10);
    color: var(--ta-gold);
    font-size: 0.74rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin-bottom: 0.9rem;
}

.ta-hero-title {
    margin: 0;
    color: var(--ta-ink);
    font-size: 2rem;
    line-height: 1.05;
    letter-spacing: -0.03em;
}

.ta-hero-copy {
    max-width: 880px;
    margin: 0.7rem 0 0 0;
    color: var(--ta-muted);
    font-size: 1rem;
    line-height: 1.6;
}
</style>
""",
    unsafe_allow_html=True,
)


def _theme_option_label(mode: str) -> str:
    return {
        "light": "☀",
        "dark": "☾",
    }.get(mode, mode)


# --- Sidebar branding ---
with st.sidebar:
    license_state = st.session_state.get("license_state", {})
    license_label = {
        "development": t("app.license.development"),
        "trial": t("app.license.trial"),
        "activated": t("app.license.activated"),
        "expired_read_only": t("app.license.read_only"),
        "unlicensed": t("app.license.unlicensed"),
    }.get(license_state.get("status"), t("app.license.development"))

    st.markdown(
        f'<div class="sidebar-brand">{t("app.brand")}</div>'
        f'<div class="sidebar-version">{t("app.tagline")}</div>'
        f'<div class="sidebar-license">License: {license_label}</div>',
        unsafe_allow_html=True,
    )

    lang_col, theme_col = st.columns([1, 1], gap="small")
    with lang_col:
        st.segmented_control(
            "language",
            options=list(SUPPORTED_LANGUAGES.keys()),
            format_func=lambda code: SUPPORTED_LANGUAGES[code],
            key="ui_language",
            selection_mode="single",
            label_visibility="collapsed",
        )
    with theme_col:
        st.segmented_control(
            "theme",
            options=["light", "dark"],
            format_func=_theme_option_label,
            key="ui_theme",
            selection_mode="single",
            label_visibility="collapsed",
        )

    n_datasets = len(st.session_state.get("datasets", {}))
    if n_datasets > 0:
        st.markdown(
            f'<div class="sidebar-badge">{n_datasets} dataset{"s" if n_datasets != 1 else ""} loaded</div>',
            unsafe_allow_html=True,
        )


def _render_sidebar_page_section(
    title: str,
    page_items: list[tuple],
    current_path: str,
    *,
    collapsible: bool = False,
    expanded: bool = True,
) -> None:
    """Render one grouped sidebar navigation section."""

    def _render_items() -> None:
        for page, label, icon, path in page_items:
            st.page_link(page, label=label, icon=icon, disabled=(path == current_path))

    if collapsible:
        with st.expander(title, expanded=expanded):
            _render_items()
        return

    st.markdown(
        f'<div class="sidebar-section-label">{title}</div>', unsafe_allow_html=True
    )
    _render_items()


# --- Page imports ---
from ui.components.history_tracker import render_history_sidebar
from ui.about_page import render as about_render
from ui.home import render as home_render
from ui.compare_page import render as compare_render
from ui.dsc_page import render as dsc_render
from ui.tga_page import render as tga_render
from ui.project_page import render as project_render
from ui.license_page import render as license_render
from ui.library_page import render as library_render
from ui.dta_page import render as dta_render
from ui.ftir_page import render as ftir_render
from ui.raman_page import render as raman_render
from ui.xrd_page import render as xrd_render
from ui.kinetics_page import render as kinetics_render
from ui.deconvolution_page import render as deconv_render
from ui.export_page import render as export_render

# --- Navigation ---
preview_modules_available = preview_modules_enabled(default=False)
if preview_modules_available:
    show_preview_tools = st.sidebar.toggle(
        t("app.preview_toggle"),
        value=False,
        help=t("app.preview_toggle_help"),
    )
else:
    show_preview_tools = False

primary_pages = [
    (
        st.Page(
            home_render,
            title=t("nav.import"),
            icon="📂",
            default=True,
            url_path="import",
        ),
        t("nav.import"),
        "📂",
        "import",
    ),
    (
        st.Page(project_render, title=t("nav.project"), icon="🗂️", url_path="project"),
        t("nav.project"),
        "🗂️",
        "project",
    ),
    (
        st.Page(compare_render, title=t("nav.compare"), icon="🧪", url_path="compare"),
        t("nav.compare"),
        "🧪",
        "compare",
    ),
    (
        st.Page(export_render, title=t("nav.report"), icon="📝", url_path="report"),
        t("nav.report"),
        "📝",
        "report",
    ),
]
analysis_pages = [
    (
        st.Page(dsc_render, title=t("nav.dsc"), icon="📈", url_path="dsc"),
        t("nav.dsc"),
        "📈",
        "dsc",
    ),
    (
        st.Page(tga_render, title=t("nav.tga"), icon="📉", url_path="tga"),
        t("nav.tga"),
        "📉",
        "tga",
    ),
    (
        st.Page(
            dta_render,
            title=tx("DTA Analizi", "DTA Analysis"),
            icon="📊",
            url_path="dta",
        ),
        tx("DTA Analizi", "DTA Analysis"),
        "📊",
        "dta",
    ),
    (
        st.Page(ftir_render, title=t("nav.ftir"), icon="🧬", url_path="ftir"),
        t("nav.ftir"),
        "🧬",
        "ftir",
    ),
    (
        st.Page(raman_render, title=t("nav.raman"), icon="🔦", url_path="raman"),
        t("nav.raman"),
        "🔦",
        "raman",
    ),
    (
        st.Page(xrd_render, title=t("nav.xrd"), icon="🧿", url_path="xrd"),
        t("nav.xrd"),
        "🧿",
        "xrd",
    ),
]
management_pages = [
    (
        st.Page(
            library_render,
            title=tx("Kütüphane", "Library"),
            icon="🗃️",
            url_path="library",
        ),
        tx("Kütüphane", "Library"),
        "🗃️",
        "library",
    ),
    (
        st.Page(license_render, title=t("nav.license"), icon="🔐", url_path="license"),
        t("nav.license"),
        "🔐",
        "license",
    ),
    (
        st.Page(about_render, title=t("nav.about"), icon="ℹ️", url_path="about"),
        t("nav.about"),
        "ℹ️",
        "about",
    ),
]

pages = {
    t("nav.primary"): [page for page, _, _, _ in primary_pages],
    t("nav.analyses"): [page for page, _, _, _ in analysis_pages],
    t("nav.management"): [page for page, _, _, _ in management_pages],
}
preview_pages = []
if show_preview_tools:
    preview_pages = [
        (
            st.Page(
                kinetics_render,
                title=tx(
                    "Kinetik Analiz (Deneysel)", "Kinetic Analysis (Experimental)"
                ),
                icon="⚡",
                url_path="kinetics",
            ),
            tx("Kinetik Analiz (Deneysel)", "Kinetic Analysis (Experimental)"),
            "⚡",
            "kinetics",
        ),
        (
            st.Page(
                deconv_render,
                title=tx(
                    "Pik Dekonvolüsyonu (Deneysel)", "Peak Deconvolution (Experimental)"
                ),
                icon="🔍",
                url_path="deconvolution",
            ),
            tx("Pik Dekonvolüsyonu (Deneysel)", "Peak Deconvolution (Experimental)"),
            "🔍",
            "deconvolution",
        ),
    ]
    pages[t("nav.preview")] = [page for page, _, _, _ in preview_pages]

pg = st.navigation(pages, position="hidden")
current_path = next(
    (
        path
        for page, _, _, path in (
            primary_pages + analysis_pages + management_pages + preview_pages
        )
        if page == pg
    ),
    "",
)

with st.sidebar:
    _render_sidebar_page_section(t("nav.primary"), primary_pages, current_path)
    _render_sidebar_page_section(t("nav.analyses"), analysis_pages, current_path)
    _render_sidebar_page_section(t("nav.management"), management_pages, current_path)
    if preview_pages:
        _render_sidebar_page_section(
            t("nav.preview"),
            preview_pages,
            current_path,
            collapsible=True,
            expanded=False,
        )
    st.markdown("---")

# --- Pipeline history in sidebar ---
with st.sidebar:
    with st.expander(t("sidebar.pipeline"), expanded=False):
        render_history_sidebar()

pg.run()
