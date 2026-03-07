"""Shared UI chrome helpers."""

from __future__ import annotations

import streamlit as st


def render_page_header(title: str, caption: str, badge: str | None = None) -> None:
    """Render a styled page hero."""
    badge_html = f'<div class="ta-hero-badge">{badge}</div>' if badge else ""
    st.markdown(
        (
            '<section class="ta-hero">'
            f"{badge_html}"
            f'<h1 class="ta-hero-title">{title}</h1>'
            f'<p class="ta-hero-copy">{caption}</p>'
            "</section>"
        ),
        unsafe_allow_html=True,
    )
