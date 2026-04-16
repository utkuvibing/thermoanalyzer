"""Dash chrome: i18n helpers and root layout wiring."""

from __future__ import annotations

from dash_app.app import create_dash_app
from dash_app.i18n import normalize_locale, t


def test_normalize_locale_accepts_bcp47_prefix():
    assert normalize_locale("tr-TR") == "tr"
    assert normalize_locale("EN") == "en"
    assert normalize_locale("xx") == "en"


def test_t_turkish_nav_labels():
    assert t("tr", "nav.import") == "Veri Al"
    assert t("tr", "nav.section_primary") == "Ana"
    assert t("en", "nav.import") == "Import Runs"


def test_create_dash_app_layout_has_theme_stores_and_holder():
    app = create_dash_app()
    layout_repr = str(app.layout)
    assert "ui-theme" in layout_repr
    assert "ui-locale" in layout_repr
    assert "_clientside-theme-holder" in layout_repr
