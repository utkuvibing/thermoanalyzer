"""Reusable guidance blocks for non-analysis Dash pages."""

from __future__ import annotations

from collections.abc import Sequence

import dash_bootstrap_components as dbc
from dash import html

from utils.i18n import normalize_ui_locale, translate_ui


def guidance_block(
    title: str,
    body: str | None = None,
    bullets: Sequence[str] | None = None,
    *,
    tone: str = "info",
) -> dbc.Alert:
    """Generic guidance callout with optional body and bullet list."""
    tone_key = str(tone or "info").lower()
    children: list = [html.H6(title, className="ta-guidance-title mb-2")]
    if body:
        children.append(html.P(body, className=f"ta-guidance-body {'mb-2' if bullets else 'mb-0'}"))
    if bullets:
        items = [item for item in bullets if item]
        if items:
            children.append(
                html.Ul(
                    [html.Li(item, className="ta-guidance-item") for item in items],
                    className="ta-guidance-list mb-0 ps-3",
                )
            )
    return dbc.Alert(children, color=tone_key, className=f"ta-guidance ta-guidance--{tone_key} mb-3")


def typical_workflow_block(
    steps: Sequence[str],
    *,
    title: str | None = None,
    locale: str | None = None,
) -> dbc.Alert:
    """Ordered step-by-step workflow guidance."""
    loc = normalize_ui_locale(locale)
    resolved_title = title if title is not None else translate_ui(loc, "dash.guidance.typical_workflow_title")
    items = [step for step in steps if step]
    return dbc.Alert(
        [
            html.H6(resolved_title, className="ta-guidance-title mb-2"),
            html.Ol([html.Li(step, className="ta-guidance-item") for step in items], className="ta-guidance-list mb-0 ps-3"),
        ],
        color="secondary",
        className="ta-guidance ta-guidance--secondary ta-guidance--workflow mb-3",
    )


def next_step_block(text: str, *, title: str | None = None, locale: str | None = None) -> dbc.Alert:
    """Short recommended next action for the current page state."""
    loc = normalize_ui_locale(locale)
    resolved_title = title if title is not None else translate_ui(loc, "dash.guidance.next_step_title")
    return guidance_block(resolved_title, body=text, tone="info")


def prereq_or_empty_help(
    text: str,
    *,
    tone: str = "warning",
    title: str | None = None,
    locale: str | None = None,
) -> dbc.Alert:
    """Actionable prerequisite or empty-state guidance."""
    loc = normalize_ui_locale(locale)
    resolved_title = title if title is not None else translate_ui(loc, "dash.guidance.prereq_title")
    return guidance_block(resolved_title, body=text, tone=tone)
