"""Root layout: sidebar navigation + page container."""

from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, dcc, html

from dash_app.i18n import SUPPORTED_LOCALES, normalize_locale, t

NAV_PRIMARY_DEF: list[tuple[str, str, str]] = [
    ("nav.import", "bi-folder2-open", "/"),
    ("nav.project", "bi-archive", "/project"),
    ("nav.report", "bi-file-earmark-text", "/export"),
    ("nav.compare", "bi-intersect", "/compare"),
]

NAV_ANALYSIS_DEF: list[tuple[str, str, str]] = [
    ("nav.dsc", "bi-graph-up", "/dsc"),
    ("nav.tga", "bi-graph-down", "/tga"),
    ("nav.dta", "bi-bar-chart", "/dta"),
    ("nav.ftir", "bi-border-style", "/ftir"),
    ("nav.raman", "bi-lightbulb", "/raman"),
    ("nav.xrd", "bi-bullseye", "/xrd"),
]

NAV_MANAGEMENT_DEF: list[tuple[str, str, str]] = [
    ("nav.about", "bi-info-circle", "/about"),
]


def _sidebar_history(locale: str) -> html.Div:
    loc = normalize_locale(locale)
    return html.Div(
        [
            html.Div(
                t(loc, "sidebar.history_title"),
                className="sidebar-section-label",
            ),
            html.Div(
                id="sidebar-history-panel",
                children=html.Small(t(loc, "sidebar.history_empty"), className="text-muted"),
                className="sidebar-history-list",
            ),
        ],
        className="px-3 pb-2",
    )


def _nav_section(locale: str, title_key: str, defs: list[tuple[str, str, str]]) -> html.Div:
    links = []
    for label_key, icon, href in defs:
        link = dbc.NavLink(
            [html.I(className=f"bi {icon} me-2"), t(locale, label_key)],
            href=href,
            active="exact",
            disabled=False,
            className="sidebar-nav-link",
        )
        links.append(link)
    return html.Div(
        [
            html.Div(t(locale, title_key), className="sidebar-section-label"),
            dbc.Nav(links, vertical=True),
        ],
        className="mb-2",
    )


def _sidebar_controls(locale: str, theme: str) -> html.Div:
    theme = theme if theme in ("light", "dark") else "light"
    next_is_dark = theme == "light"
    tip = t(locale, "ui.theme_use_dark" if next_is_dark else "ui.theme_use_light")
    label_cur = t(locale, "ui.theme_current_light" if theme == "light" else "ui.theme_current_dark")
    return html.Div(
        [
            html.Div(
                t(locale, "ui.theme_hint"),
                className="sidebar-control-group-label",
            ),
            dbc.Button(
                [
                    html.I(className=("bi bi-moon-stars" if next_is_dark else "bi bi-sun")),
                    html.Span(label_cur, className="ms-2 sidebar-theme-btn-text"),
                ],
                id="theme-toggle",
                color="light",
                outline=True,
                size="sm",
                className="sidebar-theme-btn w-100 mb-2",
                n_clicks=0,
                title=tip,
            ),
            html.Div(
                t(locale, "ui.language"),
                className="sidebar-control-group-label",
            ),
            html.Div(
                dcc.Dropdown(
                    id="locale-select",
                    options=[
                        {"label": "English", "value": "en"},
                        {"label": "Türkçe", "value": "tr"},
                    ],
                    value=normalize_locale(locale),
                    clearable=False,
                    searchable=False,
                    className="ta-dropdown ta-dropdown--sidebar",
                ),
                className="sidebar-locale-wrap",
            ),
        ],
        className="sidebar-controls px-3 pb-2",
    )


def build_sidebar_inner(locale: str, theme: str) -> html.Div:
    loc = normalize_locale(locale)
    return html.Div(
        [
            html.Div(
                [
                    html.Div("MaterialScope", className="sidebar-brand"),
                    html.Div(t(loc, "dash.sidebar.tagline"), className="sidebar-version"),
                ],
                className="px-3 pt-3 pb-2",
            ),
            _sidebar_controls(loc, theme),
            html.Hr(className="sidebar-hr"),
            html.Div(
                [
                    _nav_section(loc, "nav.section_primary", NAV_PRIMARY_DEF),
                    _nav_section(loc, "nav.section_analysis", NAV_ANALYSIS_DEF),
                    _nav_section(loc, "nav.section_management", NAV_MANAGEMENT_DEF),
                    html.Hr(className="sidebar-hr my-2"),
                    _sidebar_history(loc),
                ],
                className="px-2",
            ),
            html.Div(
                [
                    html.Hr(className="sidebar-hr"),
                    html.Div(id="sidebar-dataset-badge", className="px-3 pb-3"),
                ],
                className="mt-auto",
            ),
        ],
        className="d-flex flex-column h-100",
    )


def _sidebar() -> html.Div:
    return html.Div(
        [
            html.Div(
                id="sidebar-inner",
                children=build_sidebar_inner("en", "light"),
            ),
        ],
        className="sidebar d-flex flex-column",
    )


def build_layout() -> html.Div:
    return html.Div(
        [
            dcc.Store(id="project-id", storage_type="session"),
            dcc.Store(id="workspace-data", storage_type="memory"),
            dcc.Store(id="workspace-refresh", storage_type="memory", data=0),
            dcc.Store(id="ui-theme", data="light", storage_type="session"),
            dcc.Store(id="ui-locale", data="en", storage_type="session"),
            html.Div(id="_clientside-theme-holder", style={"display": "none"}),
            dcc.Location(id="url", refresh="callback-nav"),
            html.Div(
                [
                    html.Div(_sidebar(), className="sidebar-container"),
                    html.Div(
                        dash.page_container,
                        className="main-content",
                    ),
                ],
                className="app-wrapper",
            ),
        ]
    )


def register_clientside_theme(app: dash.Dash) -> None:
    app.clientside_callback(
        """
        function(theme) {
            const t = (theme === 'dark') ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', t);
            return '';
        }
        """,
        Output("_clientside-theme-holder", "children"),
        Input("ui-theme", "data"),
    )


@callback(
    Output("sidebar-inner", "children"),
    Input("ui-locale", "data"),
    Input("ui-theme", "data"),
)
def render_sidebar(locale: str | None, theme: str | None) -> html.Div:
    th = theme if theme in ("light", "dark") else "light"
    return build_sidebar_inner(normalize_locale(locale), th)


@callback(
    Output("ui-theme", "data"),
    Input("theme-toggle", "n_clicks"),
    State("ui-theme", "data"),
    prevent_initial_call=True,
)
def toggle_ui_theme(n_clicks: int | None, current: str | None) -> str:
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    cur = current if current in ("light", "dark") else "light"
    return "dark" if cur == "light" else "light"


@callback(
    Output("ui-locale", "data"),
    Input("locale-select", "value"),
    prevent_initial_call=True,
)
def persist_ui_locale(value: str | None) -> str:
    if not value:
        return "en"
    v = str(value).lower().split("-", 1)[0]
    return v if v in SUPPORTED_LOCALES else "en"


@callback(
    Output("project-id", "data"),
    Input("project-id", "data"),
    prevent_initial_call=False,
)
def ensure_project(current_id):
    """Auto-create a workspace on first load; validate stale ids after server restart."""
    from dash_app.api_client import workspace_new, workspace_summary

    if current_id:
        try:
            resp = workspace_summary(current_id)
            if resp.get("project_id"):
                return dash.no_update
        except Exception:
            pass  # project_id is stale (server restart) — fall through to create new

    try:
        result = workspace_new()
        return result.get("project_id")
    except Exception:
        return None


@callback(
    Output("sidebar-history-panel", "children"),
    Input("project-id", "data"),
    Input("workspace-refresh", "data"),
    Input("ui-locale", "data"),
    prevent_initial_call=False,
)
def refresh_sidebar_history(project_id, _refresh, locale):
    loc = normalize_locale(locale)
    if not project_id:
        return html.Small(t(loc, "sidebar.history_empty"), className="text-muted")

    from dash_app.api_client import workspace_context

    try:
        context = workspace_context(project_id)
    except Exception:
        return html.Small(t(loc, "sidebar.history_empty"), className="text-muted")

    history = context.get("recent_history") or []
    if not history:
        return html.Small(t(loc, "sidebar.history_empty"), className="text-muted")

    items = []
    for item in history:
        ts = item.get("timestamp", "--")
        action = item.get("action", "?")
        detail = item.get("details", "")
        label = f"{action}"
        if detail:
            label += f" — {detail}"
        items.append(
            html.Li(
                [html.Small(ts, className="d-block text-muted sidebar-history-ts"), html.Span(label)],
                className="sidebar-history-item",
            )
        )
    return html.Ul(items, className="sidebar-history-list mb-0")
