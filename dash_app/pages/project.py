"""Project workspace page -- save/load project archives, workspace overview."""

from __future__ import annotations

import base64

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, dcc, html

from dash_app.components.chrome import page_header

dash.register_page(__name__, path="/project", title="Project - MaterialScope")


layout = html.Div([
    page_header(
        "Project Workspace",
        "Save, load, and review your analysis workspace.",
        badge="Workspace",
    ),

    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H5("Workspace Summary", className="mb-3"),
                    dcc.Loading(html.Div(id="workspace-summary")),
                ])
            ], className="mb-4"),

            dbc.Card([
                dbc.CardBody([
                    html.H5("Results", className="mb-3"),
                    dcc.Loading(html.Div(id="results-list")),
                ])
            ], className="mb-4"),
        ], md=7),

        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H5("Save Project", className="mb-3"),
                    html.P(
                        "Download the current workspace as a project archive.",
                        className="text-muted",
                    ),
                    dbc.Button(
                        "Prepare Archive",
                        id="save-project-btn",
                        color="primary",
                        className="mb-2",
                    ),
                    html.Div(id="save-project-output"),
                    dcc.Download(id="project-download"),
                ])
            ], className="mb-4"),

            dbc.Card([
                dbc.CardBody([
                    html.H5("Load Project", className="mb-3"),
                    dcc.Upload(
                        id="project-upload",
                        children=html.Div([
                            html.I(className="bi bi-folder2-open me-2"),
                            "Upload .mscope archive",
                        ], className="text-center py-3"),
                        className="upload-zone",
                    ),
                    html.Div(id="load-project-output", className="mt-2"),
                ])
            ], className="mb-4"),
        ], md=5),
    ]),
])


@callback(
    Output("workspace-summary", "children"),
    Output("results-list", "children"),
    Input("project-id", "data"),
)
def load_workspace(project_id):
    if not project_id:
        return html.P("No workspace.", className="text-muted"), ""

    from dash_app.api_client import workspace_context

    try:
        ctx = workspace_context(project_id)
    except Exception as exc:
        return html.P(f"Error: {exc}", className="text-danger"), ""

    summary = ctx.get("summary", {})
    metrics = dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Small("Datasets", className="text-muted text-uppercase"),
            html.H3(str(summary.get("dataset_count", 0))),
        ])), md=3),
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Small("Results", className="text-muted text-uppercase"),
            html.H3(str(summary.get("result_count", 0))),
        ])), md=3),
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Small("Figures", className="text-muted text-uppercase"),
            html.H3(str(summary.get("figure_count", 0))),
        ])), md=3),
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Small("History Steps", className="text-muted text-uppercase"),
            html.H3(str(summary.get("analysis_history_count", 0))),
        ])), md=3),
    ], className="mb-3")

    active = ctx.get("active_dataset")
    active_info = ""
    if active:
        active_info = dbc.Alert(
            f"Active dataset: {active.get('display_name', active.get('key', '?'))} "
            f"({active.get('data_type', '?')})",
            color="info",
        )

    from dash_app.api_client import workspace_results

    try:
        results_data = workspace_results(project_id)
    except Exception:
        results_data = {"results": []}

    results = results_data.get("results", [])
    if not results:
        results_content = html.P("No saved results yet.", className="text-muted")
    else:
        rows = []
        for r in results:
            badge_color = {"stable": "success", "experimental": "info"}.get(
                r.get("status", ""), "secondary"
            )
            rows.append(
                dbc.ListGroupItem([
                    html.Div([
                        html.Strong(r.get("analysis_type", "?")),
                        dbc.Badge(r.get("status", "?"), color=badge_color, className="ms-2"),
                    ]),
                    html.Small(
                        f"Dataset: {r.get('dataset_key', '?')} | "
                        f"Template: {r.get('workflow_template', 'default')}",
                        className="text-muted",
                    ),
                ])
            )
        results_content = dbc.ListGroup(rows, flush=True)

    return html.Div([metrics, active_info]), results_content


@callback(
    Output("save-project-output", "children"),
    Output("project-download", "data"),
    Input("save-project-btn", "n_clicks"),
    State("project-id", "data"),
    prevent_initial_call=True,
)
def save_project(n_clicks, project_id):
    if not project_id:
        return dbc.Alert("No workspace to save.", color="warning"), dash.no_update

    from dash_app.api_client import project_save

    try:
        result = project_save(project_id)
    except Exception as exc:
        return dbc.Alert(f"Save failed: {exc}", color="danger"), dash.no_update

    archive_b64 = result.get("archive_base64", "")
    file_name = result.get("file_name", "materialscope_project.mscope")
    archive_bytes = base64.b64decode(archive_b64)

    return (
        dbc.Alert("Archive prepared. Downloading...", color="success"),
        dcc.send_bytes(archive_bytes, file_name),
    )


@callback(
    Output("load-project-output", "children"),
    Output("project-id", "data", allow_duplicate=True),
    Input("project-upload", "contents"),
    prevent_initial_call=True,
)
def load_project(contents):
    if not contents:
        return dash.no_update, dash.no_update

    _, content_string = contents.split(",", 1)

    from dash_app.api_client import project_load

    try:
        result = project_load(content_string)
    except Exception as exc:
        return dbc.Alert(f"Load failed: {exc}", color="danger"), dash.no_update

    new_project_id = result.get("project_id")
    summary = result.get("summary", {})
    return (
        dbc.Alert(
            f"Project loaded: {summary.get('dataset_count', 0)} datasets, "
            f"{summary.get('result_count', 0)} results.",
            color="success",
        ),
        new_project_id,
    )
