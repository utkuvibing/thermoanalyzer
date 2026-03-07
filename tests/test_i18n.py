"""Regression coverage for bilingual UI helpers."""

from utils import i18n


def test_tx_returns_turkish_when_language_is_tr(monkeypatch):
    monkeypatch.setattr(i18n, "get_language", lambda: "tr")

    assert i18n.tx("Merhaba {name}", "Hello {name}", name="Dunya") == "Merhaba Dunya"


def test_tx_returns_english_when_language_is_en(monkeypatch):
    monkeypatch.setattr(i18n, "get_language", lambda: "en")

    assert i18n.tx("Merhaba", "Hello") == "Hello"


def test_t_uses_registered_translation_keys(monkeypatch):
    monkeypatch.setattr(i18n, "get_language", lambda: "en")

    assert i18n.t("tga.title") == "TGA Analysis"
