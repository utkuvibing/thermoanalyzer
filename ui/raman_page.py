"""Raman analysis page wrapper."""

from ui.spectral_page import render_spectral_page


def render() -> None:
    render_spectral_page(
        "RAMAN",
        title_key="raman.title",
        caption_key="raman.caption",
        badge_key="raman.hero_badge",
    )
