"""Root layout: sidebar navigation + page container."""

from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, dcc, html

NAV_PRIMARY = [
    {"label": "Import", "icon": "bi-folder2-open", "href": "/"},
    {"label": "Project", "icon": "bi-archive", "href": "/project"},
    {"label": "Report", "icon": "bi-file-earmark-text", "href": "/export"},
    {"label": "Compare", "icon": "bi-intersect", "href": "/compare"},
]

NAV_ANALYSIS = [
    {"label": "DSC", "icon": "bi-graph-up", "href": "/dsc"},
    {"label": "TGA", "icon": "bi-graph-down", "href": "/tga"},
    {"label": "DTA", "icon": "bi-bar-chart", "href": "/dta"},
    {"label": "FTIR", "icon": "bi-border-style", "href": "/ftir"},
    {"label": "RAMAN", "icon": "bi-lightbulb", "href": "/raman", "disabled": True},
    {"label": "XRD", "icon": "bi-bullseye", "href": "/xrd", "disabled": True},
]

NAV_MANAGEMENT = [
    {"label": "About", "icon": "bi-info-circle", "href": "/about"},
]


def _nav_section(title: str, items: list[dict]) -> html.Div:
    links = []
    for item in items:
        disabled = item.get("disabled", False)
        link = dbc.NavLink(
            [html.I(className=f"bi {item['icon']} me-2"), item["label"]],
            href=item["href"],
            active="exact",
            disabled=disabled,
            className="sidebar-nav-link",
        )
        links.append(link)
    return html.Div(
        [html.Div(title, className="sidebar-section-label"), dbc.Nav(links, vertical=True)],
        className="mb-2",
    )


def _sidebar() -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.Div("MaterialScope", className="sidebar-brand"),
                    html.Div(
                        "Multimodal materials characterization workbench",
                        className="sidebar-version",
                    ),
                ],
                className="px-3 pt-3 pb-2",
            ),
            html.Hr(className="sidebar-hr"),
            html.Div(
                [
                    _nav_section("Primary", NAV_PRIMARY),
                    _nav_section("Analysis", NAV_ANALYSIS),
                    _nav_section("Management", NAV_MANAGEMENT),
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
        className="sidebar d-flex flex-column",
    )


def build_layout() -> html.Div:
    return html.Div(
        [
            dcc.Store(id="project-id", storage_type="session"),
            dcc.Store(id="workspace-data", storage_type="memory"),
            dcc.Store(id="workspace-refresh", storage_type="memory", data=0),
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
