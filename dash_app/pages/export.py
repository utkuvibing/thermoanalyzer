"""Report center page -- parity-focused exports and branding."""

from __future__ import annotations

import base64
import io
import zipfile

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, dcc, html
import pandas as pd

from dash_app.components.chrome import page_header
from dash_app.components.data_preview import dataset_table
from dash_app.components.page_guidance import (
    guidance_block,
    next_step_block,
    prereq_or_empty_help,
    typical_workflow_block,
)

dash.register_page(__name__, path="/export", title="Export - MaterialScope")


layout = html.Div(
    [
        dcc.Store(id="report-refresh", data=0),
        page_header(
            "Report Center",
            "Preview report payloads, edit branding, export data/results, and generate branded reports.",
            badge="Export",
        ),
        html.Div(
            [
                guidance_block(
                    "What this page does",
                    body=(
                        "Prepare export artifacts from the active workspace: raw data tables, normalized results, "
                        "and branded DOCX/PDF reports."
                    ),
                ),
                typical_workflow_block(
                    [
                        "Verify workspace readiness in Project (datasets/results available).",
                        "Set branding fields and confirm export selections.",
                        "Export data/results or generate the report package.",
                    ],
                    title="Typical workflow",
                ),
                next_step_block(
                    "If exports are incomplete, save missing analysis results first and return to this page."
                ),
            ],
            className="mb-2",
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Card(dbc.CardBody(html.Div(id="report-preview-panel")), className="mb-4"),
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    dbc.Tabs(
                                        [
                                            dbc.Tab(
                                                [
                                                    html.Div(
                                                        [
                                                            html.H5("Export Raw / Imported Data", className="mt-3 mb-3"),
                                                            dbc.Select(id="data-export-format", options=[{"label": "CSV", "value": "csv"}, {"label": "Excel (XLSX)", "value": "xlsx"}], value="xlsx"),
                                                            dbc.Label("Select datasets", className="mt-3"),
                                                            html.Div(
                                                                id="data-export-datasets-shell",
                                                                children=dcc.Dropdown(
                                                                    id="data-export-datasets",
                                                                    multi=True,
                                                                    className="ta-dropdown",
                                                                ),
                                                            ),
                                                            dbc.Button("Prepare Data Export", id="prepare-data-export-btn", color="primary", className="mt-3"),
                                                        ]
                                                    )
                                                ],
                                                label="Export Data",
                                            ),
                                            dbc.Tab(
                                                [
                                                    html.Div(
                                                        [
                                                            html.H5("Export Normalized Results", className="mt-3 mb-3"),
                                                            dbc.Select(id="result-export-format", options=[{"label": "CSV", "value": "csv"}, {"label": "Excel (XLSX)", "value": "xlsx"}], value="csv"),
                                                            dbc.Label("Select result records", className="mt-3"),
                                                            html.Div(
                                                                id="result-export-results-shell",
                                                                children=dcc.Dropdown(
                                                                    id="result-export-results",
                                                                    multi=True,
                                                                    className="ta-dropdown",
                                                                ),
                                                            ),
                                                            dbc.Button("Prepare Result Export", id="prepare-result-export-btn", color="primary", className="mt-3"),
                                                        ]
                                                    )
                                                ],
                                                label="Export Results",
                                            ),
                                            dbc.Tab(
                                                [
                                                    html.Div(
                                                        [
                                                            html.H5("Generate Branded Report", className="mt-3 mb-3"),
                                                            dbc.Select(id="report-export-format", options=[{"label": "DOCX", "value": "docx"}, {"label": "PDF", "value": "pdf"}], value="docx"),
                                                            dbc.Checkbox(id="report-include-figures", value=True, className="mt-3"),
                                                            dbc.Label("Include figures", html_for="report-include-figures", className="ms-2"),
                                                            dbc.Label("Select result records", className="mt-3 d-block"),
                                                            html.Div(
                                                                id="report-export-results-shell",
                                                                children=dcc.Dropdown(
                                                                    id="report-export-results",
                                                                    multi=True,
                                                                    className="ta-dropdown",
                                                                ),
                                                            ),
                                                            dbc.Button("Prepare Report", id="prepare-report-export-btn", color="primary", className="mt-3"),
                                                        ]
                                                    )
                                                ],
                                                label="Generate Report",
                                            ),
                                        ]
                                    ),
                                    html.Div(id="export-status", className="mt-3"),
                                    dcc.Download(id="export-download"),
                                ]
                            ),
                            className="mb-4",
                        ),
                    ],
                    md=8,
                ),
                dbc.Col(
                    [
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.H5("Branding", className="mb-3"),
                                    dbc.Label("Report Title"),
                                    dbc.Input(id="branding-report-title", type="text"),
                                    dbc.Label("Company", className="mt-3"),
                                    dbc.Input(id="branding-company-name", type="text"),
                                    dbc.Label("Laboratory", className="mt-3"),
                                    dbc.Input(id="branding-lab-name", type="text"),
                                    dbc.Label("Analyst", className="mt-3"),
                                    dbc.Input(id="branding-analyst-name", type="text"),
                                    dbc.Label("Default Report Notes", className="mt-3"),
                                    dbc.Textarea(id="branding-report-notes", style={"height": "140px"}),
                                    dbc.Label("Logo (PNG/JPG)", className="mt-3"),
                                    dcc.Upload(
                                        id="branding-logo-upload",
                                        children=html.Div([html.I(className="bi bi-image me-2"), "Upload logo"], className="text-center py-3"),
                                        className="upload-zone",
                                    ),
                                    dbc.Button("Save Branding", id="save-branding-btn", color="primary", className="w-100 mt-3"),
                                    html.Div(id="branding-status", className="mt-3"),
                                    html.Div(id="branding-logo-preview", className="mt-3"),
                                ]
                            ),
                            className="mb-4",
                        )
                    ],
                    md=4,
                ),
            ]
        ),
    ]
)


@callback(
    Output("data-export-datasets-shell", "children"),
    Output("result-export-results-shell", "children"),
    Output("report-export-results-shell", "children"),
    Input("ui-theme", "data"),
    State("data-export-datasets", "options"),
    State("data-export-datasets", "value"),
    State("result-export-results", "options"),
    State("result-export-results", "value"),
    State("report-export-results", "options"),
    State("report-export-results", "value"),
    prevent_initial_call=True,
)
def remount_export_dropdowns(
    _ui_theme,
    data_options,
    data_value,
    result_options,
    result_value,
    report_options,
    report_value,
):
    return (
        dcc.Dropdown(
            id="data-export-datasets",
            multi=True,
            className="ta-dropdown",
            options=data_options or [],
            value=data_value or [],
        ),
        dcc.Dropdown(
            id="result-export-results",
            multi=True,
            className="ta-dropdown",
            options=result_options or [],
            value=result_value or [],
        ),
        dcc.Dropdown(
            id="report-export-results",
            multi=True,
            className="ta-dropdown",
            options=report_options or [],
            value=report_value or [],
        ),
    )


@callback(
    Output("report-preview-panel", "children"),
    Output("data-export-datasets", "options"),
    Output("data-export-datasets", "value"),
    Output("result-export-results", "options"),
    Output("result-export-results", "value"),
    Output("report-export-results", "options"),
    Output("report-export-results", "value"),
    Input("project-id", "data"),
    Input("report-refresh", "data"),
    Input("workspace-refresh", "data"),
)
def load_report_center(project_id, _refresh, _global_refresh):
    if not project_id:
        empty = prereq_or_empty_help(
            "No active workspace. Import data and save results before preparing exports.",
            title="Workspace required",
        )
        return empty, [], [], [], [], [], []

    from dash_app.api_client import export_preparation, workspace_datasets

    try:
        prep = export_preparation(project_id)
        datasets_payload = workspace_datasets(project_id)
    except Exception as exc:
        error = html.P(f"Error: {exc}", className="text-danger")
        return error, [], [], [], [], [], []

    results = prep.get("exportable_results", [])
    skipped = prep.get("skipped_record_issues", [])
    branding = prep.get("branding", {})
    compare_workspace = prep.get("compare_workspace") or {}

    metrics = dbc.Row(
        [
            dbc.Col(dbc.Card(dbc.CardBody([html.Small("Datasets", className="text-muted text-uppercase"), html.H4(str(prep.get("summary", {}).get("dataset_count", 0)))])), md=3),
            dbc.Col(dbc.Card(dbc.CardBody([html.Small("Stable Analyses", className="text-muted text-uppercase"), html.H4(str(sum(1 for item in results if item.get("status") == "stable")))])), md=3),
            dbc.Col(dbc.Card(dbc.CardBody([html.Small("Preview Analyses", className="text-muted text-uppercase"), html.H4(str(sum(1 for item in results if item.get("status") == "experimental")))])), md=3),
            dbc.Col(dbc.Card(dbc.CardBody([html.Small("Supported Outputs", className="text-muted text-uppercase"), html.H4(str(len(prep.get("supported_outputs", []))))])), md=3),
        ],
        className="g-3 mb-3",
    )
    result_rows = [
        {
            "id": item.get("id"),
            "analysis_type": item.get("analysis_type"),
            "status": item.get("status"),
            "dataset_key": item.get("dataset_key"),
            "saved_at_utc": item.get("saved_at_utc"),
        }
        for item in results
    ]
    preview_children = [
        metrics,
        html.H5("Branding Preview", className="mb-2"),
        html.Ul(
            [
                html.Li(f"Report Title: {branding.get('report_title', 'MaterialScope Professional Report')}"),
                html.Li(f"Company: {branding.get('company_name') or 'Not set'}"),
                html.Li(f"Laboratory: {branding.get('lab_name') or 'Not set'}"),
                html.Li(f"Analyst: {branding.get('analyst_name') or 'Not set'}"),
            ],
            className="mb-3",
        ),
        html.H5("Compare Workspace Preview", className="mb-2"),
        html.P(f"Analysis Type: {compare_workspace.get('analysis_type', 'N/A')}", className="mb-1"),
        html.P(f"Selected Runs: {', '.join(compare_workspace.get('selected_datasets') or []) or 'None'}", className="mb-1"),
        html.P(compare_workspace.get("notes") or "No compare notes yet.", className="text-muted"),
    ]
    if result_rows:
        preview_children.extend([html.H5("Report Package", className="mt-3 mb-2"), dataset_table(result_rows, ["id", "analysis_type", "status", "dataset_key", "saved_at_utc"], table_id="report-package-table")])
    else:
        preview_children.append(
            prereq_or_empty_help(
                "No normalized result records are saved yet. Run analyses and save results before exporting result tables or reports.",
                tone="secondary",
                title="Results required for report outputs",
            )
        )
    if skipped:
        preview_children.append(dbc.Alert([html.Div("Some saved records are incomplete and will be skipped."), html.Ul([html.Li(issue) for issue in skipped])], color="warning"))

    dataset_options = [{"label": item.get("display_name", item.get("key")), "value": item.get("key")} for item in datasets_payload.get("datasets", [])]
    dataset_values = [item["value"] for item in dataset_options]
    result_options = [{"label": f"{item.get('analysis_type')} | {item.get('id')}", "value": item.get("id")} for item in results]
    result_values = [item["value"] for item in result_options]
    return html.Div(preview_children), dataset_options, dataset_values, result_options, result_values, result_options, result_values


@callback(
    Output("branding-report-title", "value"),
    Output("branding-company-name", "value"),
    Output("branding-lab-name", "value"),
    Output("branding-analyst-name", "value"),
    Output("branding-report-notes", "value"),
    Output("branding-logo-preview", "children"),
    Input("project-id", "data"),
    Input("report-refresh", "data"),
    Input("workspace-refresh", "data"),
)
def load_branding(project_id, _refresh, _global_refresh):
    if not project_id:
        return "MaterialScope Professional Report", "", "", "", "", ""
    from dash_app.api_client import workspace_branding

    payload = workspace_branding(project_id).get("branding", {})
    logo_b64 = payload.get("logo_base64")
    logo_preview = ""
    if logo_b64:
        logo_preview = html.Div(
            [
                html.Img(src=f"data:image/png;base64,{logo_b64}", style={"maxWidth": "100%", "maxHeight": "180px"}),
                html.Div(f"Current logo: {payload.get('logo_name') or 'branding_logo'}", className="small text-muted mt-2"),
            ]
        )
    return (
        payload.get("report_title") or "MaterialScope Professional Report",
        payload.get("company_name") or "",
        payload.get("lab_name") or "",
        payload.get("analyst_name") or "",
        payload.get("report_notes") or "",
        logo_preview,
    )


@callback(
    Output("branding-status", "children"),
    Output("report-refresh", "data", allow_duplicate=True),
    Input("save-branding-btn", "n_clicks"),
    State("project-id", "data"),
    State("branding-report-title", "value"),
    State("branding-company-name", "value"),
    State("branding-lab-name", "value"),
    State("branding-analyst-name", "value"),
    State("branding-report-notes", "value"),
    State("branding-logo-upload", "contents"),
    State("branding-logo-upload", "filename"),
    State("report-refresh", "data"),
    prevent_initial_call=True,
)
def save_branding(n_clicks, project_id, report_title, company_name, lab_name, analyst_name, report_notes, logo_contents, logo_name, refresh_value):
    if not n_clicks or not project_id:
        raise dash.exceptions.PreventUpdate
    from dash_app.api_client import update_workspace_branding

    payload = {
        "report_title": report_title,
        "company_name": company_name,
        "lab_name": lab_name,
        "analyst_name": analyst_name,
        "report_notes": report_notes,
    }
    if logo_contents:
        _, content_string = logo_contents.split(",", 1)
        payload["logo_base64"] = content_string
        payload["logo_name"] = logo_name
    try:
        update_workspace_branding(project_id, payload)
    except Exception as exc:
        return dbc.Alert(f"Branding save failed: {exc}", color="danger"), dash.no_update
    return dbc.Alert("Branding updated for the current workspace.", color="success"), int(refresh_value or 0) + 1


@callback(
    Output("export-status", "children", allow_duplicate=True),
    Output("export-download", "data", allow_duplicate=True),
    Input("prepare-data-export-btn", "n_clicks"),
    State("project-id", "data"),
    State("data-export-format", "value"),
    State("data-export-datasets", "value"),
    prevent_initial_call=True,
)
def export_data_files(n_clicks, project_id, export_format, dataset_keys):
    if not n_clicks or not project_id:
        if n_clicks and not project_id:
            return prereq_or_empty_help(
                "No active workspace. Load datasets before exporting raw/imported data.",
                title="Workspace required",
            ), dash.no_update
        raise dash.exceptions.PreventUpdate
    if not dataset_keys:
        return prereq_or_empty_help(
            "Select at least one dataset for raw/imported data export.",
            title="Dataset selection required",
        ), dash.no_update

    from dash_app.api_client import workspace_dataset_data

    try:
        payloads = [workspace_dataset_data(project_id, dataset_key) for dataset_key in dataset_keys]
    except Exception as exc:
        return dbc.Alert(f"Data export failed: {exc}", color="danger"), dash.no_update

    if export_format == "csv":
        if len(payloads) == 1:
            payload = payloads[0]
            frame = pd.DataFrame(payload.get("rows", []))
            return (
                dbc.Alert(f"CSV ready: {payload['dataset_key']}", color="success"),
                dcc.send_bytes(frame.to_csv(index=False).encode("utf-8"), f"{payload['dataset_key']}_export.csv"),
            )
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for payload in payloads:
                frame = pd.DataFrame(payload.get("rows", []))
                archive.writestr(f"{payload['dataset_key']}_export.csv", frame.to_csv(index=False))
        buffer.seek(0)
        return dbc.Alert(f"Prepared {len(payloads)} CSV files as ZIP.", color="success"), dcc.send_bytes(buffer.getvalue(), "materialscope_data_exports.zip")

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for payload in payloads:
            frame = pd.DataFrame(payload.get("rows", []))
            sheet_name = str(payload["dataset_key"])[:31]
            frame.to_excel(writer, sheet_name=sheet_name, index=False)
    buffer.seek(0)
    return dbc.Alert(f"Workbook ready: {len(payloads)} dataset(s).", color="success"), dcc.send_bytes(buffer.getvalue(), "materialscope_data.xlsx")


@callback(
    Output("export-status", "children", allow_duplicate=True),
    Output("export-download", "data", allow_duplicate=True),
    Input("prepare-result-export-btn", "n_clicks"),
    State("project-id", "data"),
    State("result-export-format", "value"),
    State("result-export-results", "value"),
    prevent_initial_call=True,
)
def export_result_files(n_clicks, project_id, export_format, selected_result_ids):
    if not n_clicks or not project_id:
        if n_clicks and not project_id:
            return prereq_or_empty_help(
                "No active workspace. Save analysis results before exporting result tables.",
                title="Workspace required",
            ), dash.no_update
        raise dash.exceptions.PreventUpdate
    if not selected_result_ids:
        return prereq_or_empty_help(
            "Select at least one saved result record for result export.",
            title="Result selection required",
        ), dash.no_update
    from dash_app.api_client import export_results_csv, export_results_xlsx

    try:
        result = export_results_csv(project_id, selected_result_ids) if export_format == "csv" else export_results_xlsx(project_id, selected_result_ids)
    except Exception as exc:
        return dbc.Alert(f"Result export failed: {exc}", color="danger"), dash.no_update
    artifact = base64.b64decode(result["artifact_base64"])
    return dbc.Alert(f"{result['output_type']} ready: {len(result.get('included_result_ids', []))} results.", color="success"), dcc.send_bytes(artifact, result["file_name"])


@callback(
    Output("export-status", "children"),
    Output("export-download", "data"),
    Input("prepare-report-export-btn", "n_clicks"),
    State("project-id", "data"),
    State("report-export-format", "value"),
    State("report-export-results", "value"),
    State("report-include-figures", "value"),
    prevent_initial_call=True,
)
def export_report_files(n_clicks, project_id, export_format, selected_result_ids, include_figures):
    if not n_clicks or not project_id:
        if n_clicks and not project_id:
            return prereq_or_empty_help(
                "No active workspace. Save analysis results before generating reports.",
                title="Workspace required",
            ), dash.no_update
        raise dash.exceptions.PreventUpdate
    if not selected_result_ids:
        return prereq_or_empty_help(
            "Select at least one saved result record to generate a report.",
            title="Result selection required",
        ), dash.no_update
    from dash_app.api_client import export_report_docx, export_report_pdf

    try:
        result = (
            export_report_docx(project_id, selected_result_ids, include_figures=bool(include_figures))
            if export_format == "docx"
            else export_report_pdf(project_id, selected_result_ids, include_figures=bool(include_figures))
        )
    except Exception as exc:
        return dbc.Alert(f"Report export failed: {exc}", color="danger"), dash.no_update
    artifact = base64.b64decode(result["artifact_base64"])
    return dbc.Alert(f"{result['output_type']} ready: {len(result.get('included_result_ids', []))} results.", color="success"), dcc.send_bytes(artifact, result["file_name"])
