"""Export page -- download results CSV and DOCX reports."""

from __future__ import annotations

import base64

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, dcc, html

from dash_app.components.chrome import page_header

dash.register_page(__name__, path="/export", title="Export - MaterialScope")


layout = html.Div([
    page_header(
        "Report & Export",
        "Export analysis results and generate professional reports.",
        badge="Export",
    ),

    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H5("Export Preparation", className="mb-3"),
                    dcc.Loading(html.Div(id="export-prep")),
                ])
            ], className="mb-4"),
        ], md=7),

        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H5("Download", className="mb-3"),
                    dbc.Button(
                        [html.I(className="bi bi-filetype-csv me-2"), "Results CSV"],
                        id="download-csv-btn",
                        color="primary",
                        className="d-block mb-2 w-100",
                    ),
                    dbc.Button(
                        [html.I(className="bi bi-file-earmark-word me-2"), "Report DOCX"],
                        id="download-docx-btn",
                        color="primary",
                        className="d-block mb-2 w-100",
                    ),
                    html.Div(id="download-status", className="mt-2"),
                    dcc.Download(id="export-download"),
                ])
            ], className="mb-4"),
        ], md=5),
    ]),
])


@callback(
    Output("export-prep", "children"),
    Input("project-id", "data"),
)
def load_export_prep(project_id):
    if not project_id:
        return html.P("No workspace active.", className="text-muted")

    from dash_app.api_client import export_preparation

    try:
        data = export_preparation(project_id)
    except Exception as exc:
        return html.P(f"Error: {exc}", className="text-danger")

    results = data.get("exportable_results", [])
    if not results:
        return html.P(
            "No exportable results yet. Run an analysis first.",
            className="text-muted",
        )

    rows = []
    for r in results:
        rows.append(
            dbc.ListGroupItem([
                html.Div([
                    html.Strong(r.get("analysis_type", "?")),
                    dbc.Badge(r.get("status", "?"), className="ms-2"),
                ]),
                html.Small(
                    f"Dataset: {r.get('dataset_key', '?')} | ID: {r.get('id', '?')}",
                    className="text-muted",
                ),
            ])
        )

    branding = data.get("branding", {})
    outputs = data.get("supported_outputs", [])

    return html.Div([
        dbc.ListGroup(rows, flush=True, className="mb-3"),
        html.Small(
            f"Report title: {branding.get('report_title', 'N/A')} | "
            f"Supported: {', '.join(outputs)}",
            className="text-muted",
        ),
    ])


@callback(
    Output("download-status", "children", allow_duplicate=True),
    Output("export-download", "data", allow_duplicate=True),
    Input("download-csv-btn", "n_clicks"),
    State("project-id", "data"),
    prevent_initial_call=True,
)
def download_csv(n_clicks, project_id):
    if not project_id:
        return dbc.Alert("No workspace.", color="warning"), dash.no_update

    from dash_app.api_client import export_results_csv

    try:
        result = export_results_csv(project_id)
    except Exception as exc:
        return dbc.Alert(f"Export failed: {exc}", color="danger"), dash.no_update

    artifact_b64 = result.get("artifact_base64", "")
    file_name = result.get("file_name", "materialscope_results.csv")
    content = base64.b64decode(artifact_b64)

    return (
        dbc.Alert(
            f"CSV ready: {len(result.get('included_result_ids', []))} results.",
            color="success",
        ),
        dcc.send_bytes(content, file_name),
    )


@callback(
    Output("download-status", "children"),
    Output("export-download", "data"),
    Input("download-docx-btn", "n_clicks"),
    State("project-id", "data"),
    prevent_initial_call=True,
)
def download_docx(n_clicks, project_id):
    if not project_id:
        return dbc.Alert("No workspace.", color="warning"), dash.no_update

    from dash_app.api_client import export_report_docx

    try:
        result = export_report_docx(project_id)
    except Exception as exc:
        return dbc.Alert(f"Export failed: {exc}", color="danger"), dash.no_update

    artifact_b64 = result.get("artifact_base64", "")
    file_name = result.get("file_name", "materialscope_report.docx")
    content = base64.b64decode(artifact_b64)

    return (
        dbc.Alert(
            f"DOCX ready: {len(result.get('included_result_ids', []))} results.",
            color="success",
        ),
        dcc.send_bytes(content, file_name),
    )
