"""Reusable page header component (mirrors ui/components/chrome.py)."""

from __future__ import annotations

from dash import html


def page_header(title: str, caption: str = "", badge: str = "") -> html.Div:
    children = []
    if badge:
        children.append(
            html.Span(badge, className="ta-hero-badge")
        )
    children.append(html.H2(title, className="ta-hero-title"))
    if caption:
        children.append(html.P(caption, className="ta-hero-copy"))
    return html.Div(children, className="ta-hero")
