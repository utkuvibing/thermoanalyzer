"""Dash-facing locale helpers (thin wrapper over shared ``utils.i18n`` translations).

All user-visible strings for the Dash app should resolve through :func:`t` so the
sidebar ``ui-locale`` store and pages share one catalog (``utils.i18n.TRANSLATIONS``).
"""

from __future__ import annotations

from typing import Any, Final

from utils.i18n import normalize_ui_locale, translate_ui

DEFAULT_LOCALE: Final[str] = "en"
SUPPORTED_LOCALES: Final[tuple[str, ...]] = ("en", "tr")


def normalize_locale(locale: str | None) -> str:
    """Normalize locale to ``en`` or ``tr`` (BCP-47 prefixes accepted)."""
    return normalize_ui_locale(locale)


def t(locale: str | None, key: str, **kwargs: Any) -> str:
    """Translate *key* for Dash using explicit *locale* (same catalog as Streamlit-free ``translate_ui``)."""
    return translate_ui(locale, key, **kwargs)
