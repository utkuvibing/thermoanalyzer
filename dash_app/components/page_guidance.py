"""Reusable guidance blocks for non-analysis Dash pages."""

from __future__ import annotations

from collections.abc import Sequence

import dash_bootstrap_components as dbc
from dash import html


def guidance_block(
    title: str,
    body: str | None = None,
    bullets: Sequence[str] | None = None,
    *,
    tone: str = "info",
) -> dbc.Alert:
    """Generic guidance callout with optional body and bullet list."""
    children: list = [html.H6(title, className="mb-2")]
    if body:
        children.append(html.P(body, className="mb-2" if bullets else "mb-0"))
    if bullets:
        items = [item for item in bullets if item]
        if items:
            children.append(html.Ul([html.Li(item) for item in items], className="mb-0 ps-3"))
    return dbc.Alert(children, color=tone, className="mb-3")


def typical_workflow_block(steps: Sequence[str], *, title: str = "Typical workflow") -> dbc.Alert:
    """Ordered step-by-step workflow guidance."""
    items = [step for step in steps if step]
    return dbc.Alert(
        [
            html.H6(title, className="mb-2"),
            html.Ol([html.Li(step) for step in items], className="mb-0 ps-3"),
        ],
        color="secondary",
        className="mb-3",
    )


def next_step_block(text: str) -> dbc.Alert:
    """Short recommended next action for the current page state."""
    return guidance_block("Next recommended step", body=text, tone="info")


def prereq_or_empty_help(
    text: str,
    *,
    tone: str = "warning",
    title: str = "What to do first",
) -> dbc.Alert:
    """Actionable prerequisite or empty-state guidance."""
    return guidance_block(title, body=text, tone=tone)
