"""ThermoAnalyzer - Streamlit entrypoint.

Vendor-independent thermal analysis data processing tool.
Supports DSC, TGA, DTA, FTIR, RAMAN, and XRD data analysis.

Run with: streamlit run app.py
"""

import streamlit as st

from core.reference_library import maybe_refresh_library_manifest
from core.project_io import PROJECT_EXTENSION, save_project_archive, load_project_archive
from utils.diagnostics import configure_diagnostics_logger, record_exception
from utils.i18n import SUPPORTED_LANGUAGES, t, tx
from utils.license_manager import APP_VERSION, commercial_mode_enabled, license_allows_write, load_license_state
from utils.session_state import clear_project_state, ensure_session_state, replace_project_state

st.set_page_config(
    page_title="ThermoAnalyzer Professional",
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
section[data-testid="stSidebar"] * {
    color: #E2E8F0 !important;
}
section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stRadio label,
section[data-testid="stSidebar"] .stSegmentedControl label {
    color: #A9B8CC !important;
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
    font-family: 'IBM Plex Sans', sans-serif;
    font-weight: 700;
    font-size: 1.05rem;
    letter-spacing: 0.12em;
    color: #FFFFFF !important;
    padding: 8px 0 4px 0;
}
.sidebar-version {
    font-size: 0.7rem;
    color: #94A3B8 !important;
    letter-spacing: 0.05em;
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

/* Expander styling */
details[data-testid="stExpander"] summary {
    font-weight: 500 !important;
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
    st.segmented_control(
        t("app.language"),
        options=list(SUPPORTED_LANGUAGES.keys()),
        format_func=lambda code: SUPPORTED_LANGUAGES[code],
        key="ui_language",
        selection_mode="single",
    )
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
        f'<div class="sidebar-version">v{APP_VERSION} &middot; {t("app.tagline")}</div>',
        unsafe_allow_html=True,
    )
    n_datasets = len(st.session_state.get("datasets", {}))
    if n_datasets > 0:
        st.markdown(
            f'<div class="sidebar-badge">{n_datasets} dataset{"s" if n_datasets != 1 else ""} loaded</div>',
            unsafe_allow_html=True,
        )
    st.caption(f"License: {license_label}")
    st.markdown("---")


def _render_project_sidebar():
    """Render project save/load actions in the sidebar."""
    st.markdown(f"**{t('sidebar.project')}**")
    st.caption(t("sidebar.project.caption"))

    has_project_data = bool(st.session_state.get("datasets") or st.session_state.get("results"))
    if st.button(t("sidebar.project.new"), key="project_new"):
        clear_project_state()
        st.rerun()

    if has_project_data:
        can_write = license_allows_write(st.session_state.get("license_state"))
        if st.button(
            t("sidebar.project.prepare"),
            key="project_prepare",
            disabled=not can_write,
            help="Build the archive first, then download it explicitly.",
        ):
            try:
                st.session_state["project_archive_bytes"] = save_project_archive(st.session_state)
                st.session_state["project_archive_ready"] = True
            except Exception as exc:
                error_id = record_exception(
                    st.session_state,
                    area="project_load",
                    action="project_prepare",
                    message="Preparing project archive failed.",
                    context={"dataset_count": len(st.session_state.get("datasets", {}))},
                    exception=exc,
                )
                st.error(f"Project archive preparation failed: {exc} (Error ID: {error_id})")

        if st.session_state.get("project_archive_ready") and st.session_state.get("project_archive_bytes"):
            st.download_button(
                t("sidebar.project.download"),
                data=st.session_state["project_archive_bytes"],
                file_name=f"thermoanalyzer_project{PROJECT_EXTENSION}",
                mime="application/zip",
                key="project_save",
                on_click="ignore",
                help="This button only appears after you explicitly prepare the archive.",
            )
    else:
        st.caption("No datasets or saved results yet.")

    uploaded_project = st.file_uploader(
        t("sidebar.project.load"),
        type=[PROJECT_EXTENSION.lstrip(".")],
        key="project_loader",
        help="Load a previously saved ThermoAnalyzer project archive.",
    )
    if uploaded_project is not None and st.button(t("sidebar.project.load_selected"), key="project_load_btn"):
        try:
            project_state = load_project_archive(uploaded_project)
            replace_project_state(project_state)
            st.success("Project loaded.")
            st.rerun()
        except Exception as exc:
            error_id = record_exception(
                st.session_state,
                area="project_load",
                action="project_load",
                message="Loading project archive failed.",
                context={"file_name": getattr(uploaded_project, "name", "")},
                exception=exc,
            )
            st.error(f"Project load failed: {exc} (Error ID: {error_id})")

# --- Page imports ---
from ui.components.history_tracker import render_history_sidebar
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
show_preview_tools = st.sidebar.toggle(
    t("app.preview_toggle"),
    value=False,
    help=t("app.preview_toggle_help"),
)
pages = {
    tx("Ana Akış", "Primary"): [
        st.Page(home_render, title=t("nav.import"), icon="📂", default=True, url_path="import"),
        st.Page(compare_render, title=t("nav.compare"), icon="🧪", url_path="compare"),
        st.Page(dsc_render, title=t("nav.dsc"), icon="📈", url_path="dsc"),
        st.Page(tga_render, title=t("nav.tga"), icon="📉", url_path="tga"),
        st.Page(dta_render, title=tx("DTA Analizi", "DTA Analysis"), icon="📊", url_path="dta"),
        st.Page(ftir_render, title=t("nav.ftir"), icon="🧬", url_path="ftir"),
        st.Page(raman_render, title=t("nav.raman"), icon="🔦", url_path="raman"),
        st.Page(xrd_render, title=t("nav.xrd"), icon="🧿", url_path="xrd"),
        st.Page(library_render, title=tx("Kütüphane", "Library"), icon="🗃️", url_path="library"),
        st.Page(export_render, title=t("nav.report"), icon="📝", url_path="report"),
        st.Page(project_render, title=t("nav.project"), icon="🗂️", url_path="project"),
        st.Page(license_render, title=t("nav.license"), icon="🔐", url_path="license"),
    ],
}
if show_preview_tools:
    pages[t("nav.preview")] = [
        st.Page(kinetics_render, title=tx("Kinetik Analiz (Deneysel)", "Kinetic Analysis (Experimental)"), icon="⚡", url_path="kinetics"),
        st.Page(deconv_render, title=tx("Pik Dekonvolüsyonu (Deneysel)", "Peak Deconvolution (Experimental)"), icon="🔍", url_path="deconvolution"),
    ]

pg = st.navigation(pages)

# --- Pipeline history in sidebar ---
with st.sidebar:
    _render_project_sidebar()
    st.markdown("---")
    with st.expander(t("sidebar.pipeline"), expanded=False):
        render_history_sidebar()

# --- About panel & footer in sidebar ---
with st.sidebar:
    st.markdown("---")
    with st.expander(t("sidebar.about")):
        if st.session_state.get("ui_language", "tr") == "tr":
            st.markdown(
                f"**ThermoAnalyzer Professional v{APP_VERSION}**\n\n"
                "QC ve Ar-Ge laboratuvarları için cihazdan bağımsız DSC/TGA/DTA/FTIR/RAMAN/XRD çalışma alanı.\n\n"
                "**Kararlı beta kapsamı**\n"
                "- CSV/TXT/XLSX DSC, TGA, DTA, FTIR, RAMAN ve XRD koşularını içe aktar\n"
                "- DSC, TGA, DTA, FTIR, RAMAN ve XRD analiz akışlarını çalıştır\n"
                "- Çoklu koşuları Karşılaştırma Alanı ve Toplu Şablon Uygulayıcı ile yönet\n"
                "- Kararlı sonuçları proje durumu, rapor ve export akışıyla sakla\n\n"
                "**Laboratuvar önizleme modülleri**\n"
                "- Kinetik ve dekonvolüsyon modülleri önizleme anahtarı arkasında kalır ve ticari stabilite sözüne dahil değildir.\n\n"
                "**Referans standartlar**\n"
                "- ASTM E967 — DSC sıcaklık ve entalpi kalibrasyonu\n"
                "- ASTM E1131 — TGA ile kompozisyon analizi\n"
                "- ASTM E1356 — DSC ile cam geçişi\n"
                "- ICTAC kinetik analiz rehberleri"
            )
            st.caption(
                "Pilot kabuk: Streamlit\n"
                "Ticari yön: offline masaüstü kabuk + yıllık cihaz lisansı"
            )
        else:
            st.markdown(
                f"**ThermoAnalyzer Professional v{APP_VERSION}**\n\n"
                "Vendor-independent DSC/TGA/DTA/FTIR/RAMAN/XRD workbench for QC and R&D labs.\n\n"
                "**Stable beta scope**\n"
                "- Import DSC, TGA, DTA, FTIR, RAMAN, and XRD runs from CSV/TXT/XLSX exports\n"
                "- Execute stable DSC, TGA, DTA, FTIR, RAMAN, and XRD analysis workflows\n"
                "- Manage multiple runs through Compare Workspace and the Batch Template Runner\n"
                "- Save stable results through the current project, report, and export flows\n\n"
                "**Lab Preview modules**\n"
                "- Kinetics and deconvolution stay available behind the preview toggle and are excluded from the commercial stability promise.\n\n"
                "**Reference standards**\n"
                "- ASTM E967 — DSC Temperature & Enthalpy Calibration\n"
                "- ASTM E1131 — Compositional Analysis by TGA\n"
                "- ASTM E1356 — Glass Transition by DSC\n"
                "- ICTAC kinetic analysis guidance"
            )
            st.caption(
                "Pilot shell: Streamlit\n"
                "Commercial direction: offline desktop shell + annual device licensing"
            )

pg.run()
