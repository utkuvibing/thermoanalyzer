"""Project workspace page -- parity-focused workspace operations."""

from __future__ import annotations

import base64

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, dcc, html

from core.project_io import PROJECT_EXTENSION
from dash_app.components.chrome import page_header
from dash_app.components.data_preview import dataset_table
from dash_app.components.page_guidance import (
    guidance_block,
    next_step_block,
    prereq_or_empty_help,
    typical_workflow_block,
)

dash.register_page(__name__, path="/project", title="Project - MaterialScope")


def _metric_card(label: str, value: str) -> dbc.Card:
    return dbc.Card(dbc.CardBody([html.Small(label, className="text-muted text-uppercase"), html.H4(value, className="mb-0")]))


def _next_step(summary: dict, compare_workspace: dict) -> str:
    if summary.get("dataset_count", 0) <= 0:
        return "Start by loading runs from Import."
    if summary.get("result_count", 0) <= 0:
        return "Next step: save at least one analysis result."
    if not (compare_workspace or {}).get("selected_datasets"):
        return "Next step: prepare a Compare workspace."
    return "Next step: generate the output package in Report Center."


layout = html.Div(
    [
        dcc.Store(id="project-page-refresh", data=0),
        dcc.Store(id="pending-project-upload"),
        dcc.Store(id="project-confirm-action"),
        page_header(
            "Project Workspace",
            "Save, load, reset, and inspect the current analysis workspace.",
            badge="Workspace",
        ),
        html.Div(
            [
                guidance_block(
                    "What this page does",
                    body=(
                        "Use this page as the workspace checkpoint: verify loaded runs, review saved results, "
                        "inspect compare state, and manage archive save/load operations."
                    ),
                ),
                typical_workflow_block(
                    [
                        "Import datasets on the Import page.",
                        "Use Project Workspace to verify dataset and saved-result counts.",
                        "Proceed to Compare and Report when the workspace summary is ready.",
                    ],
                    title="Typical workflow",
                ),
                next_step_block("Use the workspace summary panel to identify the immediate next action."),
            ],
            className="mb-2",
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Card(dbc.CardBody(html.Div(id="workspace-summary")), className="mb-4"),
                        dbc.Card(dbc.CardBody(html.Div(id="project-confirm-panel")), className="mb-4"),
                        dbc.Card(dbc.CardBody(html.Div(id="workspace-datasets-panel")), className="mb-4"),
                        dbc.Card(dbc.CardBody(html.Div(id="workspace-results-panel")), className="mb-4"),
                    ],
                    md=8,
                ),
                dbc.Col(
                    [
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.H5("Quick Actions", className="mb-3"),
                                    dbc.Button("Start New Workspace", id="new-workspace-btn", color="secondary", className="w-100 mb-2"),
                                    dbc.Button("Prepare & Download Archive", id="save-project-btn", color="primary", className="w-100 mb-3"),
                                    html.Div(id="save-project-output"),
                                    dcc.Download(id="project-download"),
                                    html.Hr(),
                                    html.H5("Load Project", className="mb-3"),
                                    dcc.Upload(
                                        id="project-upload",
                                        children=html.Div([html.I(className="bi bi-folder2-open me-2"), f"Upload {PROJECT_EXTENSION} archive"], className="text-center py-3"),
                                        className="upload-zone",
                                    ),
                                    html.Div(id="selected-project-upload", className="small text-muted mt-2"),
                                    dbc.Button("Load Selected Archive", id="load-project-btn", color="primary", className="w-100 mt-3"),
                                    html.Div(id="load-project-output", className="mt-3"),
                                ]
                            ),
                            className="mb-4",
                        ),
                        dbc.Card(dbc.CardBody(html.Div(id="compare-summary-panel")), className="mb-4"),
                        dbc.Card(dbc.CardBody(html.Div(id="history-panel")), className="mb-4"),
                    ],
                    md=4,
                ),
            ]
        ),
    ]
)


@callback(
    Output("pending-project-upload", "data"),
    Output("selected-project-upload", "children"),
    Input("project-upload", "contents"),
    State("project-upload", "filename"),
    prevent_initial_call=True,
)
def stage_project_upload(contents, file_name):
    if not contents:
        raise dash.exceptions.PreventUpdate
    _, content_string = contents.split(",", 1)
    payload = {"file_name": file_name or f"project{PROJECT_EXTENSION}", "archive_base64": content_string}
    return payload, f"Selected archive: {payload['file_name']}"


@callback(
    Output("workspace-summary", "children"),
    Output("workspace-datasets-panel", "children"),
    Output("workspace-results-panel", "children"),
    Output("compare-summary-panel", "children"),
    Output("history-panel", "children"),
    Input("project-id", "data"),
    Input("project-page-refresh", "data"),
    Input("workspace-refresh", "data"),
)
def load_workspace(project_id, _refresh, _global_refresh):
    if not project_id:
        empty = prereq_or_empty_help(
            "No active workspace. Go to Import to load runs or use Quick Actions here to start/load a workspace.",
            title="Workspace required",
        )
        return empty, empty, empty, empty, empty

    from dash_app.api_client import workspace_context, workspace_datasets, workspace_results

    try:
        context = workspace_context(project_id)
        datasets_payload = workspace_datasets(project_id)
        results_payload = workspace_results(project_id)
    except Exception as exc:
        error = html.P(f"Error: {exc}", className="text-danger")
        return error, error, error, error, error

    summary = context.get("summary", {})
    compare_workspace = context.get("compare_workspace") or {}
    metrics = dbc.Row(
        [
            dbc.Col(_metric_card("Datasets", str(summary.get("dataset_count", 0))), md=3),
            dbc.Col(_metric_card("Saved Results", str(summary.get("result_count", 0))), md=3),
            dbc.Col(_metric_card("Figures", str(summary.get("figure_count", 0))), md=3),
            dbc.Col(_metric_card("History Steps", str(summary.get("analysis_history_count", 0))), md=3),
        ],
        className="g-3 mb-3",
    )
    status_lines = html.Ul(
        [
            html.Li(f"Active dataset: {(context.get('active_dataset') or {}).get('display_name', 'None')}"),
            html.Li(f"Compare workspace: {'Ready' if compare_workspace.get('selected_datasets') else 'Empty'}"),
            html.Li("Archive status: Ready on request"),
        ],
        className="mb-3",
    )
    summary_block = html.Div([metrics, next_step_block(_next_step(summary, compare_workspace)), status_lines])

    dataset_rows = datasets_payload.get("datasets", [])
    if dataset_rows:
        dataset_table_view = html.Div(
            [
                html.H5("Loaded Runs", className="mb-3"),
                dataset_table(
                    dataset_rows,
                    ["key", "display_name", "data_type", "vendor", "sample_name", "heating_rate", "points", "validation_status"],
                    table_id="project-datasets-table",
                ),
            ]
        )
    else:
        dataset_table_view = html.Div(
            [
                html.H5("Loaded Runs", className="mb-3"),
                prereq_or_empty_help(
                    "No datasets loaded. Import runs first to populate this workspace.",
                    tone="secondary",
                    title="No loaded runs",
                ),
            ]
        )

    result_rows = results_payload.get("results", [])
    if result_rows:
        results_view = html.Div(
            [
                html.H5("Saved Result Records", className="mb-3"),
                dataset_table(
                    result_rows,
                    ["id", "analysis_type", "status", "dataset_key", "workflow_template", "saved_at_utc"],
                    table_id="project-results-table",
                ),
            ]
        )
    else:
        results_view = html.Div(
            [
                html.H5("Saved Result Records", className="mb-3"),
                prereq_or_empty_help(
                    "No saved results yet. Run analyses, then return here to confirm result records.",
                    tone="secondary",
                    title="No saved results",
                ),
            ]
        )

    compare_view = html.Div(
        [
            html.H5("Compare Workspace", className="mb-3"),
            html.P(f"Analysis Type: {compare_workspace.get('analysis_type', 'N/A')}", className="mb-1"),
            html.P(
                f"Selected Runs: {', '.join(compare_workspace.get('selected_datasets') or []) or 'None'}",
                className="mb-1",
            ),
            html.P(f"Saved Figure: {compare_workspace.get('figure_key') or 'None'}", className="mb-1"),
            html.P(compare_workspace.get("notes") or "No compare notes yet.", className="text-muted"),
        ]
    )

    history = context.get("recent_history") or []
    if history:
        history_view = html.Div(
            [
                html.H5("Recent History", className="mb-3"),
                html.Ul(
                    [
                        html.Li(f"{item.get('timestamp', '--')} - {item.get('action', 'Unknown')} - {item.get('details', '')}")
                        for item in history
                    ],
                    className="mb-0",
                ),
            ]
        )
    else:
        history_view = html.Div(
            [
                html.H5("Recent History", className="mb-3"),
                prereq_or_empty_help(
                    "No workflow history yet. Actions such as import, analysis save, compare updates, and archive operations will appear here.",
                    tone="secondary",
                    title="No history entries",
                ),
            ]
        )

    return summary_block, dataset_table_view, results_view, compare_view, history_view


@callback(
    Output("project-confirm-action", "data"),
    Output("project-confirm-panel", "children"),
    Output("load-project-output", "children", allow_duplicate=True),
    Input("new-workspace-btn", "n_clicks"),
    Input("load-project-btn", "n_clicks"),
    State("project-id", "data"),
    State("pending-project-upload", "data"),
    prevent_initial_call=True,
)
def request_project_action(new_clicks, load_clicks, project_id, pending_upload):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    from dash_app.api_client import workspace_context

    context = workspace_context(project_id) if project_id else {"summary": {}}
    summary = context.get("summary", {})
    has_content = any(
        summary.get(key, 0) > 0
        for key in ("dataset_count", "result_count", "figure_count", "analysis_history_count")
    ) or bool((context.get("compare_workspace") or {}).get("selected_datasets"))

    if button_id == "new-workspace-btn":
        action = {"action": "new"}
        panel = html.Div(
            [
                dbc.Alert(
                    "The current workspace will be cleared. Confirm to start a fresh workspace."
                    if has_content
                    else "Confirm to start a fresh workspace.",
                    color="warning",
                ),
                dbc.Row(
                    [
                        dbc.Col(dbc.Button("Confirm", id="project-confirm-btn", color="danger", className="w-100"), md=6),
                        dbc.Col(dbc.Button("Cancel", id="project-cancel-btn", color="secondary", className="w-100"), md=6),
                    ],
                    className="g-2",
                ),
            ]
        )
        return action, panel, dash.no_update

    if not pending_upload:
        return dash.no_update, dash.no_update, dbc.Alert("Choose a project archive first.", color="warning")
    if has_content:
        action = {"action": "load"}
        panel = html.Div(
            [
                dbc.Alert("Loading the selected archive will replace the current workspace. Confirm to continue.", color="warning"),
                dbc.Row(
                    [
                        dbc.Col(dbc.Button("Confirm", id="project-confirm-btn", color="danger", className="w-100"), md=6),
                        dbc.Col(dbc.Button("Cancel", id="project-cancel-btn", color="secondary", className="w-100"), md=6),
                    ],
                    className="g-2",
                ),
            ]
        )
        return action, panel, dash.no_update
    action = {"action": "load"}
    panel = html.Div(
        [
            dbc.Alert(
                "Loading the selected archive will replace the current workspace. Confirm to continue."
                if has_content
                else "Confirm to load the selected archive.",
                color="warning",
            ),
            dbc.Row(
                [
                    dbc.Col(dbc.Button("Confirm", id="project-confirm-btn", color="danger", className="w-100"), md=6),
                    dbc.Col(dbc.Button("Cancel", id="project-cancel-btn", color="secondary", className="w-100"), md=6),
                ],
                className="g-2",
            ),
        ]
    )
    return action, panel, dash.no_update


@callback(
    Output("project-id", "data", allow_duplicate=True),
    Output("project-page-refresh", "data", allow_duplicate=True),
    Output("project-confirm-panel", "children", allow_duplicate=True),
    Output("project-confirm-action", "data", allow_duplicate=True),
    Output("pending-project-upload", "data", allow_duplicate=True),
    Output("load-project-output", "children"),
    Input("project-confirm-btn", "n_clicks"),
    Input("project-cancel-btn", "n_clicks"),
    State("project-confirm-action", "data"),
    State("pending-project-upload", "data"),
    State("project-page-refresh", "data"),
    prevent_initial_call=True,
)
def resolve_project_action(confirm_clicks, cancel_clicks, action, pending_upload, refresh_value):
    ctx = dash.callback_context
    if not ctx.triggered or not action:
        raise dash.exceptions.PreventUpdate

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    if button_id == "project-cancel-btn":
        return dash.no_update, dash.no_update, "", None, dash.no_update, dbc.Alert("Project action cancelled.", color="secondary")

    from dash_app.api_client import project_load, workspace_new

    if action.get("action") == "new":
        result = workspace_new()
        return result.get("project_id"), int(refresh_value or 0) + 1, "", None, dash.no_update, dbc.Alert("Started a fresh workspace.", color="success")

    if action.get("action") == "load" and pending_upload:
        result = project_load(pending_upload["archive_base64"])
        summary = result.get("summary", {})
        return (
            result.get("project_id"),
            int(refresh_value or 0) + 1,
            "",
            None,
            None,
            dbc.Alert(
                f"Project loaded: {summary.get('dataset_count', 0)} datasets, {summary.get('result_count', 0)} results.",
                color="success",
            ),
        )

    raise dash.exceptions.PreventUpdate


@callback(
    Output("save-project-output", "children"),
    Output("project-download", "data"),
    Input("save-project-btn", "n_clicks"),
    State("project-id", "data"),
    prevent_initial_call=True,
)
def save_project(n_clicks, project_id):
    if not project_id:
        return prereq_or_empty_help(
            "No active workspace to save. Import data or load a project archive first.",
            title="Workspace required",
        ), dash.no_update

    from dash_app.api_client import project_save

    try:
        result = project_save(project_id)
    except Exception as exc:
        return dbc.Alert(f"Save failed: {exc}", color="danger"), dash.no_update

    archive_b64 = result.get("archive_base64", "")
    file_name = result.get("file_name", f"materialscope_project{PROJECT_EXTENSION}")
    archive_bytes = base64.b64decode(archive_b64)
    return dbc.Alert("Archive prepared. Downloading...", color="success"), dcc.send_bytes(archive_bytes, file_name)
