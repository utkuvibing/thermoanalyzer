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


def test_project_page_sidebar_hint_matches_sidebar_actions():
    project_page = _repo_text("ui/project_page.py")
    i18n = _repo_text("utils/i18n.py")

    assert 'st.info(t("project.sidebar_hint"))' in project_page
    assert '"project.sidebar_hint"' in i18n
    assert "Proje Dosyasını Hazırla" in i18n
    assert "Load Selected Project" in i18n
