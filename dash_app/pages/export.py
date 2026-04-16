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
from utils.i18n import normalize_ui_locale, translate_ui

dash.register_page(__name__, path="/export", title="Export - MaterialScope")


def _loc(locale_data: str | None) -> str:
    return normalize_ui_locale(locale_data)


def _build_export_workbench(loc: str) -> dbc.Card:
    return dbc.Card(
        dbc.CardBody(
            [
                dbc.Tabs(
                    [
                        dbc.Tab(
                            [
                                html.Div(
                                    [
                                        html.H5(
                                            translate_ui(loc, "dash.export.section_raw_data"),
                                            className="mt-3 mb-3",
                                        ),
                                        dbc.Select(
                                            id="data-export-format",
                                            options=[
                                                {"label": translate_ui(loc, "dash.export.label_csv"), "value": "csv"},
                                                {"label": translate_ui(loc, "dash.export.label_xlsx"), "value": "xlsx"},
                                            ],
                                            value="xlsx",
                                        ),
                                        dbc.Label(translate_ui(loc, "dash.export.label_select_datasets"), className="mt-3"),
                                        html.Div(
                                            id="data-export-datasets-shell",
                                            children=dcc.Dropdown(
                                                id="data-export-datasets",
                                                multi=True,
                                                className="ta-dropdown",
                                            ),
                                        ),
                                        dbc.Button(
                                            translate_ui(loc, "dash.export.btn_prepare_data"),
                                            id="prepare-data-export-btn",
                                            color="primary",
                                            className="mt-3",
                                        ),
                                    ]
                                )
                            ],
                            label=translate_ui(loc, "dash.export.tab_export_data"),
                        ),
                        dbc.Tab(
                            [
                                html.Div(
                                    [
                                        html.H5(
                                            translate_ui(loc, "dash.export.section_results"),
                                            className="mt-3 mb-3",
                                        ),
                                        dbc.Select(
                                            id="result-export-format",
                                            options=[
                                                {"label": translate_ui(loc, "dash.export.label_csv"), "value": "csv"},
                                                {"label": translate_ui(loc, "dash.export.label_xlsx"), "value": "xlsx"},
                                            ],
                                            value="csv",
                                        ),
                                        dbc.Label(translate_ui(loc, "dash.export.label_select_results"), className="mt-3"),
                                        html.Div(
                                            id="result-export-results-shell",
                                            children=dcc.Dropdown(
                                                id="result-export-results",
                                                multi=True,
                                                className="ta-dropdown",
                                            ),
                                        ),
                                        dbc.Button(
                                            translate_ui(loc, "dash.export.btn_prepare_results"),
                                            id="prepare-result-export-btn",
                                            color="primary",
                                            className="mt-3",
                                        ),
                                    ]
                                )
                            ],
                            label=translate_ui(loc, "dash.export.tab_export_results"),
                        ),
                        dbc.Tab(
                            [
                                html.Div(
                                    [
                                        html.H5(
                                            translate_ui(loc, "dash.export.section_report"),
                                            className="mt-3 mb-3",
                                        ),
                                        dbc.Select(
                                            id="report-export-format",
                                            options=[
                                                {"label": translate_ui(loc, "dash.export.label_docx"), "value": "docx"},
                                                {"label": translate_ui(loc, "dash.export.label_pdf"), "value": "pdf"},
                                            ],
                                            value="docx",
                                        ),
                                        dbc.Checkbox(id="report-include-figures", value=True, className="mt-3"),
                                        dbc.Label(
                                            translate_ui(loc, "dash.export.label_include_figures"),
                                            html_for="report-include-figures",
                                            className="ms-2",
                                        ),
                                        dbc.Label(
                                            translate_ui(loc, "dash.export.label_select_results"),
                                            className="mt-3 d-block",
                                        ),
                                        html.Div(
                                            id="report-export-results-shell",
                                            children=dcc.Dropdown(
                                                id="report-export-results",
                                                multi=True,
                                                className="ta-dropdown",
                                            ),
                                        ),
                                        dbc.Button(
                                            translate_ui(loc, "dash.export.btn_prepare_report"),
                                            id="prepare-report-export-btn",
                                            color="primary",
                                            className="mt-3",
                                        ),
                                    ]
                                )
                            ],
                            label=translate_ui(loc, "dash.export.tab_generate_report"),
                        ),
                    ]
                ),
                html.Div(id="export-status", className="mt-3"),
                dcc.Download(id="export-download"),
            ]
        ),
        className="mb-4",
    )


def _build_branding_card(loc: str) -> dbc.Card:
    return dbc.Card(
        dbc.CardBody(
            [
                html.H5(translate_ui(loc, "dash.export.branding_title"), className="mb-3"),
                dbc.Label(translate_ui(loc, "dash.export.branding_report_title")),
                dbc.Input(id="branding-report-title", type="text"),
                dbc.Label(translate_ui(loc, "dash.export.branding_company"), className="mt-3"),
                dbc.Input(id="branding-company-name", type="text"),
                dbc.Label(translate_ui(loc, "dash.export.branding_lab"), className="mt-3"),
                dbc.Input(id="branding-lab-name", type="text"),
                dbc.Label(translate_ui(loc, "dash.export.branding_analyst"), className="mt-3"),
                dbc.Input(id="branding-analyst-name", type="text"),
                dbc.Label(translate_ui(loc, "dash.export.branding_notes"), className="mt-3"),
                dbc.Textarea(id="branding-report-notes", style={"height": "140px"}),
                dbc.Label(translate_ui(loc, "dash.export.branding_logo"), className="mt-3"),
                dcc.Upload(
                    id="branding-logo-upload",
                    children=html.Div(
                        [
                            html.I(className="bi bi-image me-2"),
                            translate_ui(loc, "dash.export.branding_upload_logo"),
                        ],
                        className="text-center py-3",
                    ),
                    className="upload-zone",
                ),
                dbc.Button(
                    translate_ui(loc, "dash.export.btn_save_branding"),
                    id="save-branding-btn",
                    color="primary",
                    className="w-100 mt-3",
                ),
                html.Div(id="branding-status", className="mt-3"),
                html.Div(id="branding-logo-preview", className="mt-3"),
            ]
        ),
        className="mb-4",
    )


layout = html.Div(
    [
        dcc.Store(id="report-refresh", data=0),
        html.Div(id="export-hero-slot"),
        html.Div(id="export-guidance-slot", className="mb-2"),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Card(dbc.CardBody(html.Div(id="report-preview-panel")), className="mb-4"),
                        html.Div(id="export-workbench-slot"),
                    ],
                    md=8,
                ),
                dbc.Col([html.Div(id="export-branding-slot")], md=4),
            ]
        ),
    ]
)


@callback(
    Output("export-hero-slot", "children"),
    Output("export-guidance-slot", "children"),
    Output("export-workbench-slot", "children"),
    Output("export-branding-slot", "children"),
    Input("ui-locale", "data"),
    prevent_initial_call=False,
)
def render_export_locale_chrome(locale_data):
    loc = _loc(locale_data)
    hero = page_header(
        translate_ui(loc, "dash.export.title"),
        translate_ui(loc, "dash.export.caption"),
        badge=translate_ui(loc, "dash.export.badge"),
    )
    guidance = html.Div(
        [
            guidance_block(
                translate_ui(loc, "dash.export.guidance_what_title"),
                body=translate_ui(loc, "dash.export.guidance_what_body"),
            ),
            typical_workflow_block(
                [
                    translate_ui(loc, "dash.export.workflow_step1"),
                    translate_ui(loc, "dash.export.workflow_step2"),
                    translate_ui(loc, "dash.export.workflow_step3"),
                ],
                locale=loc,
            ),
            next_step_block(translate_ui(loc, "dash.export.next_step_body"), locale=loc),
        ]
    )
    return hero, guidance, _build_export_workbench(loc), _build_branding_card(loc)


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
    Input("ui-locale", "data"),
)
def load_report_center(project_id, _refresh, _global_refresh, locale_data):
    loc = _loc(locale_data)
    default_title = translate_ui(loc, "dash.export.default_report_title")
    if not project_id:
        empty = prereq_or_empty_help(
            translate_ui(loc, "dash.export.prereq_workspace_body"),
            title=translate_ui(loc, "dash.export.prereq_workspace_title"),
            locale=loc,
        )
        return empty, [], [], [], [], [], []

    from dash_app.api_client import export_preparation, workspace_datasets

    try:
        prep = export_preparation(project_id)
        datasets_payload = workspace_datasets(project_id)
    except Exception as exc:
        error = html.P(
            [translate_ui(loc, "dash.export.error_prefix"), " ", str(exc)],
            className="text-danger",
        )
        return error, [], [], [], [], [], []

    results = prep.get("exportable_results", [])
    skipped = prep.get("skipped_record_issues", [])
    branding = prep.get("branding", {})
    compare_workspace = prep.get("compare_workspace") or {}

    metrics = dbc.Row(
        [
            dbc.Col(
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.Small(translate_ui(loc, "dash.export.metric_datasets"), className="text-muted text-uppercase"),
                            html.H4(str(prep.get("summary", {}).get("dataset_count", 0))),
                        ]
                    )
                ),
                md=3,
            ),
            dbc.Col(
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.Small(translate_ui(loc, "dash.export.metric_stable"), className="text-muted text-uppercase"),
                            html.H4(str(sum(1 for item in results if item.get("status") == "stable"))),
                        ]
                    )
                ),
                md=3,
            ),
            dbc.Col(
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.Small(translate_ui(loc, "dash.export.metric_preview"), className="text-muted text-uppercase"),
                            html.H4(str(sum(1 for item in results if item.get("status") == "experimental"))),
                        ]
                    )
                ),
                md=3,
            ),
            dbc.Col(
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.Small(translate_ui(loc, "dash.export.metric_outputs"), className="text-muted text-uppercase"),
                            html.H4(str(len(prep.get("supported_outputs", [])))),
                        ]
                    )
                ),
                md=3,
            ),
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
        html.H5(translate_ui(loc, "dash.export.preview_branding"), className="mb-2"),
        html.Ul(
            [
                html.Li(
                    translate_ui(
                        loc,
                        "dash.export.preview_li_report_title",
                        value=branding.get("report_title") or default_title,
                    )
                ),
                html.Li(
                    translate_ui(
                        loc,
                        "dash.export.preview_li_company",
                        value=branding.get("company_name") or translate_ui(loc, "dash.export.not_set"),
                    )
                ),
                html.Li(
                    translate_ui(
                        loc,
                        "dash.export.preview_li_lab",
                        value=branding.get("lab_name") or translate_ui(loc, "dash.export.not_set"),
                    )
                ),
                html.Li(
                    translate_ui(
                        loc,
                        "dash.export.preview_li_analyst",
                        value=branding.get("analyst_name") or translate_ui(loc, "dash.export.not_set"),
                    )
                ),
            ],
            className="mb-3",
        ),
        html.H5(translate_ui(loc, "dash.export.preview_compare"), className="mb-2"),
        html.P(
            translate_ui(
                loc,
                "dash.export.analysis_type",
                value=compare_workspace.get("analysis_type") or translate_ui(loc, "dash.export.na"),
            ),
            className="mb-1",
        ),
        html.P(
            translate_ui(
                loc,
                "dash.export.selected_runs",
                value=", ".join(compare_workspace.get("selected_datasets") or []) or translate_ui(loc, "dash.export.none"),
            ),
            className="mb-1",
        ),
        html.P(compare_workspace.get("notes") or translate_ui(loc, "dash.export.no_compare_notes"), className="text-muted"),
    ]
    if result_rows:
        preview_children.extend(
            [
                html.H5(translate_ui(loc, "dash.export.preview_report_pkg"), className="mt-3 mb-2"),
                dataset_table(result_rows, ["id", "analysis_type", "status", "dataset_key", "saved_at_utc"], table_id="report-package-table"),
            ]
        )
    else:
        preview_children.append(
            prereq_or_empty_help(
                translate_ui(loc, "dash.export.prereq_results_body"),
                tone="secondary",
                title=translate_ui(loc, "dash.export.prereq_results_title"),
                locale=loc,
            )
        )
    if skipped:
        preview_children.append(
            dbc.Alert(
                [
                    html.Div(translate_ui(loc, "dash.export.records_incomplete")),
                    html.Ul([html.Li(issue) for issue in skipped]),
                ],
                color="warning",
            )
        )

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
    Input("ui-locale", "data"),
)
def load_branding(project_id, _refresh, _global_refresh, locale_data):
    loc = _loc(locale_data)
    default_title = translate_ui(loc, "dash.export.default_report_title")
    if not project_id:
        return default_title, "", "", "", "", ""
    from dash_app.api_client import workspace_branding

    payload = workspace_branding(project_id).get("branding", {})
    logo_b64 = payload.get("logo_base64")
    logo_preview = ""
    if logo_b64:
        logo_preview = html.Div(
            [
                html.Img(src=f"data:image/png;base64,{logo_b64}", style={"maxWidth": "100%", "maxHeight": "180px"}),
                html.Div(
                    translate_ui(
                        loc,
                        "dash.export.logo_current",
                        name=payload.get("logo_name") or "branding_logo",
                    ),
                    className="small text-muted mt-2",
                ),
            ]
        )
    return (
        payload.get("report_title") or default_title,
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
    State("ui-locale", "data"),
    prevent_initial_call=True,
)
def save_branding(
    n_clicks,
    project_id,
    report_title,
    company_name,
    lab_name,
    analyst_name,
    report_notes,
    logo_contents,
    logo_name,
    refresh_value,
    locale_data,
):
    loc = _loc(locale_data)
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
        return dbc.Alert(translate_ui(loc, "dash.export.branding_save_fail", error=str(exc)), color="danger"), dash.no_update
    return dbc.Alert(translate_ui(loc, "dash.export.branding_save_ok"), color="success"), int(refresh_value or 0) + 1


@callback(
    Output("export-status", "children", allow_duplicate=True),
    Output("export-download", "data", allow_duplicate=True),
    Input("prepare-data-export-btn", "n_clicks"),
    State("project-id", "data"),
    State("data-export-format", "value"),
    State("data-export-datasets", "value"),
    State("ui-locale", "data"),
    prevent_initial_call=True,
)
def export_data_files(n_clicks, project_id, export_format, dataset_keys, locale_data):
    loc = _loc(locale_data)
    if not n_clicks or not project_id:
        if n_clicks and not project_id:
            return prereq_or_empty_help(
                translate_ui(loc, "dash.export.prereq_workspace_data"),
                title=translate_ui(loc, "dash.export.prereq_workspace_title"),
                locale=loc,
            ), dash.no_update
        raise dash.exceptions.PreventUpdate
    if not dataset_keys:
        return prereq_or_empty_help(
            translate_ui(loc, "dash.export.prereq_select_datasets"),
            title=translate_ui(loc, "dash.export.prereq_title_select_datasets"),
            locale=loc,
        ), dash.no_update

    from dash_app.api_client import workspace_dataset_data

    try:
        payloads = [workspace_dataset_data(project_id, dataset_key) for dataset_key in dataset_keys]
    except Exception as exc:
        return dbc.Alert(translate_ui(loc, "dash.export.data_export_fail", error=str(exc)), color="danger"), dash.no_update

    if export_format == "csv":
        if len(payloads) == 1:
            payload = payloads[0]
            frame = pd.DataFrame(payload.get("rows", []))
            return (
                dbc.Alert(translate_ui(loc, "dash.export.data_csv_ready", key=payload["dataset_key"]), color="success"),
                dcc.send_bytes(frame.to_csv(index=False).encode("utf-8"), f"{payload['dataset_key']}_export.csv"),
            )
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for payload in payloads:
                frame = pd.DataFrame(payload.get("rows", []))
                archive.writestr(f"{payload['dataset_key']}_export.csv", frame.to_csv(index=False))
        buffer.seek(0)
        return (
            dbc.Alert(translate_ui(loc, "dash.export.data_zip_ready", count=len(payloads)), color="success"),
            dcc.send_bytes(buffer.getvalue(), "materialscope_data_exports.zip"),
        )

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for payload in payloads:
            frame = pd.DataFrame(payload.get("rows", []))
            sheet_name = str(payload["dataset_key"])[:31]
            frame.to_excel(writer, sheet_name=sheet_name, index=False)
    buffer.seek(0)
    return (
        dbc.Alert(translate_ui(loc, "dash.export.data_xlsx_ready", count=len(payloads)), color="success"),
        dcc.send_bytes(buffer.getvalue(), "materialscope_data.xlsx"),
    )


@callback(
    Output("export-status", "children", allow_duplicate=True),
    Output("export-download", "data", allow_duplicate=True),
    Input("prepare-result-export-btn", "n_clicks"),
    State("project-id", "data"),
    State("result-export-format", "value"),
    State("result-export-results", "value"),
    State("ui-locale", "data"),
    prevent_initial_call=True,
)
def export_result_files(n_clicks, project_id, export_format, selected_result_ids, locale_data):
    loc = _loc(locale_data)
    if not n_clicks or not project_id:
        if n_clicks and not project_id:
            return prereq_or_empty_help(
                translate_ui(loc, "dash.export.prereq_workspace_results"),
                title=translate_ui(loc, "dash.export.prereq_workspace_title"),
                locale=loc,
            ), dash.no_update
        raise dash.exceptions.PreventUpdate
    if not selected_result_ids:
        return prereq_or_empty_help(
            translate_ui(loc, "dash.export.prereq_select_results"),
            title=translate_ui(loc, "dash.export.prereq_title_select_results"),
            locale=loc,
        ), dash.no_update
    from dash_app.api_client import export_results_csv, export_results_xlsx

    try:
        result = export_results_csv(project_id, selected_result_ids) if export_format == "csv" else export_results_xlsx(project_id, selected_result_ids)
    except Exception as exc:
        return dbc.Alert(translate_ui(loc, "dash.export.result_export_fail", error=str(exc)), color="danger"), dash.no_update
    artifact = base64.b64decode(result["artifact_base64"])
    return (
        dbc.Alert(
            translate_ui(
                loc,
                "dash.export.result_ready",
                otype=result["output_type"],
                count=len(result.get("included_result_ids", [])),
            ),
            color="success",
        ),
        dcc.send_bytes(artifact, result["file_name"]),
    )


@callback(
    Output("export-status", "children"),
    Output("export-download", "data"),
    Input("prepare-report-export-btn", "n_clicks"),
    State("project-id", "data"),
    State("report-export-format", "value"),
    State("report-export-results", "value"),
    State("report-include-figures", "value"),
    State("ui-locale", "data"),
    prevent_initial_call=True,
)
def export_report_files(n_clicks, project_id, export_format, selected_result_ids, include_figures, locale_data):
    loc = _loc(locale_data)
    if not n_clicks or not project_id:
        if n_clicks and not project_id:
            return prereq_or_empty_help(
                translate_ui(loc, "dash.export.prereq_workspace_report"),
                title=translate_ui(loc, "dash.export.prereq_workspace_title"),
                locale=loc,
            ), dash.no_update
        raise dash.exceptions.PreventUpdate
    if not selected_result_ids:
        return prereq_or_empty_help(
            translate_ui(loc, "dash.export.prereq_select_report_results"),
            title=translate_ui(loc, "dash.export.prereq_title_select_results"),
            locale=loc,
        ), dash.no_update
    from dash_app.api_client import export_report_docx, export_report_pdf

    try:
        result = (
            export_report_docx(project_id, selected_result_ids, include_figures=bool(include_figures))
            if export_format == "docx"
            else export_report_pdf(project_id, selected_result_ids, include_figures=bool(include_figures))
        )
    except Exception as exc:
        return dbc.Alert(translate_ui(loc, "dash.export.report_export_fail", error=str(exc)), color="danger"), dash.no_update
    artifact = base64.b64decode(result["artifact_base64"])
    return (
        dbc.Alert(
            translate_ui(
                loc,
                "dash.export.result_ready",
                otype=result["output_type"],
                count=len(result.get("included_result_ids", [])),
            ),
            color="success",
        ),
        dcc.send_bytes(artifact, result["file_name"]),
    )
