"""Theme tokens for the Dash UI, extracted from the Streamlit app.py."""

from __future__ import annotations

THEME_TOKENS: dict[str, dict[str, str]] = {
    "light": {
        "ink": "#0F172A",
        "muted": "#5A6578",
        "border": "#D1D9E0",
        "panel": "#FFFFFF",
        "panel_strong": "#F8FAFC",
        "accent": "#0E7490",
        "accent_strong": "#155E75",
        "gold": "#B45309",
        "bg_top": "#F0F2F5",
        "bg_bottom": "#E8EBF0",
        "sidebar_bg": "#0F172A",
        "sidebar_text": "#E2E8F0",
        "sidebar_muted": "#A9B8CC",
        "input_bg": "#FAFBFC",
        "input_border": "#D1D9E0",
    },
    "dark": {
        "ink": "#E5EEF8",
        "muted": "#9CA3AF",
        "border": "#4B4B52",
        "panel": "rgba(47,47,52,0.84)",
        "panel_strong": "#2A2A2F",
        "accent": "#1597A8",
        "accent_strong": "#0F6E86",
        "gold": "#F59E0B",
        "bg_top": "#36363B",
        "bg_bottom": "#36363B",
        "sidebar_bg": "#1C1A1A",
        "sidebar_text": "#E2E8F0",
        "sidebar_muted": "#9FB0C7",
        "input_bg": "rgba(54,54,59,0.95)",
        "input_border": "#4B4B52",
    },
}

FONT_FAMILY = "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif"
MONO_FAMILY = "'IBM Plex Mono', 'Consolas', 'Monaco', monospace"

PLOT_THEME = {
    "light": {
        "template": "plotly_white",
        "text": "#102033",
        "paper_bg": "#F7FAFC",
        "plot_bg": "#FFFFFF",
        "grid": "#D8E1EA",
    },
    "dark": {
        "template": "plotly_dark",
        "text": "#E5EEF8",
        "paper_bg": "#0F172A",
        "plot_bg": "#111C30",
        "grid": "#314055",
    },
}
