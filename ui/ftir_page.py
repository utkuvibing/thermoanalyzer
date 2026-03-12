"""FTIR analysis page wrapper."""

from ui.spectral_page import render_spectral_page


def render() -> None:
    render_spectral_page(
        "FTIR",
        title_key="ftir.title",
        caption_key="ftir.caption",
        badge_key="ftir.hero_badge",
    )
