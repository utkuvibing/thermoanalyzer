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
from utils.license_manager import APP_VERSION, commercial_mode_enabled, load_license_state
from utils.runtime_flags import preview_modules_enabled
from utils.session_state import ensure_session_state

load_dotenv(dotenv_path=Path(__file__).resolve().with_name(".env"), override=False)

st.set_page_config(
    page_title="MaterialScope",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

ensure_session_state()
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
    st.session_state["library_status"] = maybe_refresh_library_manifest(st.session_state.get("license_state"))
except Exception:
    st.session_state["library_status"] = None

# --- Professional CSS ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root {
    --ta-ink: #0F172A;
    --ta-muted: #516072;
    --ta-border: #D6DEE8;
    --ta-panel: rgba(255,255,255,0.88);
    --ta-panel-strong: #FFFFFF;
    --ta-accent: #0E7490;
    --ta-accent-strong: #155E75;
    --ta-gold: #B45309;
    --ta-bg-top: #F3F6F9;
    --ta-bg-bottom: #E7EDF2;
}

/* Global font */
html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    color: var(--ta-ink);
}

.stApp {
    background:
        radial-gradient(circle at top right, rgba(14,116,144,0.10), transparent 32%),
        linear-gradient(180deg, var(--ta-bg-top) 0%, var(--ta-bg-bottom) 100%);
}

/* Dark sidebar - NETZSCH / TA Instruments style */
section[data-testid="stSidebar"] {
    background:
        linear-gradient(180deg, #0F172A 0%, #18263A 100%) !important;
    color: #E2E8F0 !important;
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
    color: #E2E8F0 !important;
}
section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stRadio label,
section[data-testid="stSidebar"] .stSegmentedControl label {
    color: #A9B8CC !important;
}
section[data-testid="stSidebar"] .stSegmentedControl {
    margin-top: 0 !important;
    margin-bottom: 0.2rem !important;
}
section[data-testid="stSidebar"] .stSegmentedControl [role="radiogroup"] {
    gap: 0.18rem !important;
}
section[data-testid="stSidebar"] .stSegmentedControl [role="radio"] {
    min-height: 1.9rem !important;
    padding: 0.2rem 0.58rem !important;
    font-size: 0.72rem !important;
    border-radius: 8px !important;
}
section[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.1) !important;
}

/* Metric cards - clean scientific style */
div[data-testid="stMetric"] {
    background: linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(247,250,252,0.92) 100%);
    border: 1px solid var(--ta-border);
    border-radius: 16px;
    padding: 14px 18px;
    box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
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
    background-color: rgba(255,255,255,0.72);
    border: 1px solid var(--ta-border);
    border-radius: 14px;
    padding: 4px 8px;
}
button[data-baseweb="tab"] {
    font-weight: 500 !important;
    font-size: 0.85rem !important;
    color: #425466 !important;
    border-bottom: 2px solid transparent !important;
    padding: 10px 16px !important;
    border-radius: 10px !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: var(--ta-accent-strong) !important;
    border-bottom: 2px solid transparent !important;
    font-weight: 600 !important;
    background: rgba(14,116,144,0.08) !important;
}

/* Primary buttons - corporate blue */
div.stButton > button[kind="primary"],
div.stButton > button {
    background: linear-gradient(180deg, var(--ta-accent) 0%, var(--ta-accent-strong) 100%) !important;
    color: white !important;
    border: none !important;
    font-weight: 600 !important;
    border-radius: 12px !important;
    transition: transform 0.18s ease, box-shadow 0.18s ease !important;
    box-shadow: 0 10px 24px rgba(14,116,144,0.22);
}
div.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 14px 28px rgba(14,116,144,0.28);
}

/* Download buttons - professional green */
div.stDownloadButton > button {
    background: linear-gradient(180deg, #0F766E 0%, #115E59 100%) !important;
    color: white !important;
    border: none !important;
    font-weight: 600 !important;
    border-radius: 12px !important;
}
div.stDownloadButton > button:hover {
    transform: translateY(-1px);
}

/* File uploader - dashed border, clean */
div[data-testid="stFileUploader"] > div:first-child {
    border: 2px dashed #AEBECD !important;
    border-radius: 18px !important;
    background: rgba(255,255,255,0.74) !important;
    transition: border-color 0.2s !important;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.6);
}
div[data-testid="stFileUploader"] > div:first-child:hover {
    border-color: var(--ta-accent) !important;
}

/* Status bar class - plot footer info bar */
.status-bar {
    font-family: 'IBM Plex Mono', 'Consolas', 'Monaco', monospace;
    font-size: 0.75rem;
    color: #445163;
    background: rgba(255,255,255,0.8);
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
    font-size: 1.28rem;
    letter-spacing: 0.04em;
    color: #FFFFFF !important;
    padding: 0 0 0.08rem 0;
    margin-top: -0.08rem;
}
.sidebar-version {
    font-size: 0.72rem;
    color: #94A3B8 !important;
    letter-spacing: 0.01em;
    line-height: 1.42;
    max-width: 15rem;
    margin-bottom: 0.12rem;
}
.sidebar-license {
    font-size: 0.7rem;
    color: #A7B6C9 !important;
    margin-top: 0.18rem;
    line-height: 1.25;
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

/* Dataframe styling */
div[data-testid="stDataFrame"] {
    border: 1px solid var(--ta-border);
    border-radius: 16px;
    overflow: hidden;
}

div[data-testid="stMarkdownContainer"] p {
    color: var(--ta-muted);
}

.ta-hero {
    position: relative;
    overflow: hidden;
    margin: 0 0 1.4rem 0;
    padding: 1.5rem 1.6rem;
    border-radius: 26px;
    border: 1px solid rgba(15,23,42,0.06);
    background:
        radial-gradient(circle at top right, rgba(180,83,9,0.10), transparent 26%),
        linear-gradient(135deg, rgba(255,255,255,0.96) 0%, rgba(243,247,250,0.92) 100%);
    box-shadow: 0 20px 40px rgba(15, 23, 42, 0.08);
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
""", unsafe_allow_html=True)

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
        ,
        unsafe_allow_html=True,
    )
    header_meta_col, header_lang_col = st.columns([1.15, 0.95], gap="small")
    with header_meta_col:
        st.markdown(f'<div class="sidebar-license">License: {license_label}</div>', unsafe_allow_html=True)
    with header_lang_col:
        st.segmented_control(
            "language",
            options=list(SUPPORTED_LANGUAGES.keys()),
            format_func=lambda code: SUPPORTED_LANGUAGES[code],
            key="ui_language",
            selection_mode="single",
            label_visibility="collapsed",
        )
    n_datasets = len(st.session_state.get("datasets", {}))
    if n_datasets > 0:
        st.markdown(
            f'<div class="sidebar-badge">{n_datasets} dataset{"s" if n_datasets != 1 else ""} loaded</div>',
            unsafe_allow_html=True,
        )

def _render_sidebar_page_section(title: str, page_items: list[tuple], current_path: str, *, collapsible: bool = False, expanded: bool = True) -> None:
    """Render one grouped sidebar navigation section."""
    def _render_items() -> None:
        for page, label, icon, path in page_items:
            st.page_link(page, label=label, icon=icon, disabled=(path == current_path))

    if collapsible:
        with st.expander(title, expanded=expanded):
            _render_items()
        return

    st.markdown(f'<div class="sidebar-section-label">{title}</div>', unsafe_allow_html=True)
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
    (st.Page(home_render, title=t("nav.import"), icon="📂", default=True, url_path="import"), t("nav.import"), "📂", "import"),
    (st.Page(project_render, title=t("nav.project"), icon="🗂️", url_path="project"), t("nav.project"), "🗂️", "project"),
    (st.Page(compare_render, title=t("nav.compare"), icon="🧪", url_path="compare"), t("nav.compare"), "🧪", "compare"),
    (st.Page(export_render, title=t("nav.report"), icon="📝", url_path="report"), t("nav.report"), "📝", "report"),
]
analysis_pages = [
    (st.Page(dsc_render, title=t("nav.dsc"), icon="📈", url_path="dsc"), t("nav.dsc"), "📈", "dsc"),
    (st.Page(tga_render, title=t("nav.tga"), icon="📉", url_path="tga"), t("nav.tga"), "📉", "tga"),
    (st.Page(dta_render, title=tx("DTA Analizi", "DTA Analysis"), icon="📊", url_path="dta"), tx("DTA Analizi", "DTA Analysis"), "📊", "dta"),
    (st.Page(ftir_render, title=t("nav.ftir"), icon="🧬", url_path="ftir"), t("nav.ftir"), "🧬", "ftir"),
    (st.Page(raman_render, title=t("nav.raman"), icon="🔦", url_path="raman"), t("nav.raman"), "🔦", "raman"),
    (st.Page(xrd_render, title=t("nav.xrd"), icon="🧿", url_path="xrd"), t("nav.xrd"), "🧿", "xrd"),
]
management_pages = [
    (st.Page(library_render, title=tx("Kütüphane", "Library"), icon="🗃️", url_path="library"), tx("Kütüphane", "Library"), "🗃️", "library"),
    (st.Page(license_render, title=t("nav.license"), icon="🔐", url_path="license"), t("nav.license"), "🔐", "license"),
    (st.Page(about_render, title=t("nav.about"), icon="ℹ️", url_path="about"), t("nav.about"), "ℹ️", "about"),
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
            st.Page(kinetics_render, title=tx("Kinetik Analiz (Deneysel)", "Kinetic Analysis (Experimental)"), icon="⚡", url_path="kinetics"),
            tx("Kinetik Analiz (Deneysel)", "Kinetic Analysis (Experimental)"),
            "⚡",
            "kinetics",
        ),
        (
            st.Page(deconv_render, title=tx("Pik Dekonvolüsyonu (Deneysel)", "Peak Deconvolution (Experimental)"), icon="🔍", url_path="deconvolution"),
            tx("Pik Dekonvolüsyonu (Deneysel)", "Peak Deconvolution (Experimental)"),
            "🔍",
            "deconvolution",
        ),
    ]
    pages[t("nav.preview")] = [page for page, _, _, _ in preview_pages]

pg = st.navigation(pages, position="hidden")
current_path = next((path for page, _, _, path in (primary_pages + analysis_pages + management_pages + preview_pages) if page == pg), "")

with st.sidebar:
    _render_sidebar_page_section(t("nav.primary"), primary_pages, current_path)
    _render_sidebar_page_section(t("nav.analyses"), analysis_pages, current_path)
    _render_sidebar_page_section(t("nav.management"), management_pages, current_path)
    if preview_pages:
        _render_sidebar_page_section(t("nav.preview"), preview_pages, current_path, collapsible=True, expanded=False)
    st.markdown("---")

# --- Pipeline history in sidebar ---
with st.sidebar:
    with st.expander(t("sidebar.pipeline"), expanded=False):
        render_history_sidebar()

pg.run()
