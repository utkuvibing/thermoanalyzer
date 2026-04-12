from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _repo_text(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_home_page_avoids_duplicate_title_after_shared_header():
    home_page = _repo_text("ui/home.py")

    assert 'render_page_header(t("home.title"), t("home.caption"), badge=t("home.hero_badge"))' in home_page
    assert 'st.header(t("home.title"))' not in home_page
    assert "Kararlı ürün yüzeyi şu zincire odaklanır" in home_page


def test_dta_page_uses_shared_header_chrome():
    dta_page = _repo_text("ui/dta_page.py")

    assert 'render_page_header(t("dta.title"), t("dta.caption"), badge=t("dta.hero_badge"))' in dta_page
    assert 'st.title(tx("DTA Analizi", "DTA Analysis"))' not in dta_page


def test_stable_analysis_pages_render_workflow_guides():
    dsc_page = _repo_text("ui/dsc_page.py")
    dta_page = _repo_text("ui/dta_page.py")
    tga_page = _repo_text("ui/tga_page.py")
    spectral_page = _repo_text("ui/spectral_page.py")
    xrd_page = _repo_text("ui/xrd_page.py")
    guides = _repo_text("ui/components/workflow_guide.py")

    assert 'render_analysis_workflow_guide("DSC")' in dsc_page
    assert 'render_analysis_workflow_guide("DTA")' in dta_page
    assert 'render_tga_workflow_guide()' in tga_page
    assert "render_analysis_workflow_guide(token)" in spectral_page
    assert 'render_analysis_workflow_guide("XRD")' in xrd_page
    for token in ['"DSC"', '"DTA"', '"TGA"', '"FTIR"', '"RAMAN"', '"XRD"']:
        assert token in guides


def test_analysis_hero_copy_uses_full_modality_expansions():
    i18n = _repo_text("utils/i18n.py")

    assert "Differential Scanning Calorimetry Workflow" in i18n
    assert "Thermogravimetric Analysis Workflow" in i18n
    assert "Differential Thermal Analysis Workflow" in i18n
    assert "Fourier Transform Infrared Workflow" in i18n
    assert "Raman Spectroscopy Workflow" in i18n
    assert "X-Ray Diffraction Workflow" in i18n


def test_project_page_sidebar_hint_matches_sidebar_actions():
    project_page = _repo_text("ui/project_page.py")
    i18n = _repo_text("utils/i18n.py")

    assert 'st.info(t("project.sidebar_hint"))' in project_page
    assert '"project.sidebar_hint"' in i18n
    assert "Proje Dosyasını Hazırla" in i18n
    assert "Load Selected Project" in i18n
    assert 'overview_tab, actions_tab = st.tabs(' in project_page
    assert 'key="project_prepare_page"' in project_page
    assert 'key="project_load_btn_page"' in project_page
    assert 'action_cards_col, upload_panel_col = st.columns([1.6, 1.0], gap="large")' in project_page
    assert 'st.subheader(_tx(lang, "Hızlı İşlemler", "Quick Actions"))' in project_page
    assert 'st.subheader(_tx(lang, "Proje Yükle", "Load Project"))' in project_page
    assert 'status_lines = [' in project_page
    assert 'st.session_state["project_confirm_clear"] = True' in project_page
    assert 'st.session_state["project_confirm_load"] = True' in project_page


def test_about_page_is_navigation_item_not_license_tab():
    app_entry = _repo_text("app.py")
    license_page = _repo_text("ui/license_page.py")
    about_page = _repo_text("ui/about_page.py")

    assert 'with st.expander(t("sidebar.about"))' not in app_entry
    assert 'st.Page(about_render, title=t("nav.about"), icon="ℹ️", url_path="about")' in app_entry
    assert 'activation_tab, branding_tab = st.tabs([' in license_page
    assert "about_tab" not in license_page
    assert 'render_page_header(t("about.title"), t("about.caption"), badge=t("about.hero_badge"))' in about_page


def test_sidebar_and_about_copy_do_not_show_version_or_preview_disabled_note():
    app_entry = _repo_text("app.py")
    about_page = _repo_text("ui/about_page.py")

    assert 'v{APP_VERSION}' not in app_entry
    assert 'st.sidebar.caption(t("app.preview_disabled"))' not in app_entry
    assert "MaterialScope v" not in about_page


def test_sidebar_navigation_uses_grouped_scientific_structure():
    app_entry = _repo_text("app.py")
    session_state = _repo_text("utils/session_state.py")
    i18n = _repo_text("utils/i18n.py")

    assert 't("nav.primary")' in app_entry
    assert 't("nav.analyses")' in app_entry
    assert 't("nav.management")' in app_entry
    assert 'st.navigation(pages, position="hidden")' in app_entry
    assert '_render_sidebar_page_section(t("nav.primary"), primary_pages, current_path)' in app_entry
    assert 'label_visibility="collapsed"' in app_entry
    assert 'header_meta_col, header_lang_col = st.columns([1.15, 0.95], gap="small")' in app_entry
    assert '_render_sidebar_page_section(t("nav.analyses"), analysis_pages, current_path)' in app_entry
    analyses_call_idx = app_entry.index('_render_sidebar_page_section(t("nav.analyses"), analysis_pages, current_path)')
    assert 'collapsible=True' not in app_entry[max(0, analyses_call_idx - 40): analyses_call_idx + 120]
    assert 'with st.expander(t("sidebar.project"), expanded=False):' not in app_entry
    import_idx = app_entry.index('st.Page(home_render, title=t("nav.import"), icon="📂", default=True, url_path="import")')
    project_idx = app_entry.index('st.Page(project_render, title=t("nav.project"), icon="🗂️", url_path="project")')
    compare_idx = app_entry.index('st.Page(compare_render, title=t("nav.compare"), icon="🧪", url_path="compare")')
    report_idx = app_entry.index('st.Page(export_render, title=t("nav.report"), icon="📝", url_path="report")')
    assert import_idx < project_idx < compare_idx < report_idx
    brand_idx = app_entry.index('f\'<div class="sidebar-brand">{t("app.brand")}</div>\'')
    license_idx = app_entry.index('f\'<div class="sidebar-license">License: {license_label}</div>\'')
    segmented_idx = app_entry.index('st.segmented_control(')
    assert brand_idx < license_idx < segmented_idx
    assert 'key="ui_theme"' in app_entry
    assert '"ui_theme": "light"' in session_state
    assert '"nav.primary"' in i18n
    assert '"nav.analyses"' in i18n
    assert '"nav.management"' in i18n
