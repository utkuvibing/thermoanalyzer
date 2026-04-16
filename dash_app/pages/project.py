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
from utils.i18n import normalize_ui_locale, translate_ui

dash.register_page(__name__, path="/project", title="Project - MaterialScope")

LEGACY_PROJECT_EXTENSION = ".thermozip"


def _loc(locale_data: str | None) -> str:
    return normalize_ui_locale(locale_data)


def _allowed_project_archive_filename(file_name: str | None) -> bool:
    if not file_name:
        return False
    lower = file_name.lower()
    return lower.endswith(".scopezip") or lower.endswith(".thermozip")


def _metric_card(label: str, value: str) -> dbc.Card:
    return dbc.Card(dbc.CardBody([html.Small(label, className="text-muted text-uppercase"), html.H4(value, className="mb-0")]))


def _next_step(loc: str, summary: dict, compare_workspace: dict) -> str:
    if summary.get("dataset_count", 0) <= 0:
        return translate_ui(loc, "project.dash.next_step_import", import_nav=translate_ui(loc, "nav.import"))
    if summary.get("result_count", 0) <= 0:
        return translate_ui(loc, "project.dash.next_step_results")
    if not (compare_workspace or {}).get("selected_datasets"):
        return translate_ui(loc, "project.dash.next_step_compare", compare_nav=translate_ui(loc, "nav.compare"))
    return translate_ui(loc, "project.dash.next_step_report", report_nav=translate_ui(loc, "nav.report"))


def _can_prepare_archive(summary: dict) -> bool:
    return any(
        summary.get(key, 0) > 0
        for key in ("result_count", "figure_count", "analysis_history_count")
    )


layout = html.Div(
    [
        dcc.Store(id="project-page-refresh", data=0),
        dcc.Store(id="pending-project-upload"),
        dcc.Store(id="project-confirm-action"),
        dcc.Store(id="project-save-eligibility", data={"can_prepare_archive": False}),
        html.Div(id="project-header-slot"),
        html.Div(id="project-guidance-slot", className="mb-2"),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Card(dbc.CardBody(html.Div(id="workspace-summary")), className="mb-4"),
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.Div(id="project-confirm-message"),
                                    html.Div(
                                        id="project-confirm-actions",
                                        style={"display": "none"},
                                        children=[
                                            dbc.Row(
                                                [
                                                    dbc.Col(
                                                        dbc.Button(
                                                            translate_ui("en", "project.dash.confirm_generic"),
                                                            id="project-confirm-btn",
                                                            color="danger",
                                                            className="w-100",
                                                        ),
                                                        md=4,
                                                    ),
                                                    dbc.Col(
                                                        dbc.Button(
                                                            translate_ui("en", "project.dash.prepare_archive_first"),
                                                            id="project-prepare-first-btn",
                                                            color="primary",
                                                            className="w-100 d-none",
                                                            disabled=True,
                                                            n_clicks=0,
                                                        ),
                                                        md=4,
                                                    ),
                                                    dbc.Col(
                                                        dbc.Button(
                                                            translate_ui("en", "project.dash.cancel"),
                                                            id="project-cancel-btn",
                                                            color="secondary",
                                                            className="w-100",
                                                        ),
                                                        md=4,
                                                    ),
                                                ],
                                                className="g-2",
                                            ),
                                        ],
                                    ),
                                ]
                            ),
                            className="mb-4",
                        ),
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
                                    html.H5(id="project-qa-title", className="mb-3"),
                                    dbc.Button(id="new-workspace-btn", color="secondary", className="w-100 mb-2"),
                                    dbc.Button(id="save-project-btn", color="primary", className="w-100 mb-3"),
                                    html.Div(id="save-project-output"),
                                    dcc.Download(id="project-download"),
                                    html.Hr(),
                                    html.H5(id="project-load-title", className="mb-3"),
                                    dcc.Upload(
                                        id="project-upload",
                                        children=html.Div(
                                            [
                                                html.I(className="bi bi-folder2-open me-2"),
                                                html.Span(id="project-upload-caption"),
                                            ],
                                            className="text-center py-3",
                                        ),
                                        className="upload-zone",
                                    ),
                                    html.Div(id="selected-project-upload", className="small text-muted mt-2"),
                                    dbc.Button(id="load-project-btn", color="primary", className="w-100 mt-3"),
                                    html.Div(id="load-project-output", className="mt-3"),
                                ]
                            ),
                            className="mb-4",
                        ),
                        dbc.Card(dbc.CardBody(html.Div(id="compare-summary-panel")), className="mb-4"),
                    ],
                    md=4,
                ),
            ]
        ),
    ]
)


@callback(
    Output("project-header-slot", "children"),
    Output("project-guidance-slot", "children"),
    Input("ui-locale", "data"),
)
def render_project_locale_chrome(locale_data):
    loc = _loc(locale_data)
    header = page_header(
        translate_ui(loc, "project.title"),
        translate_ui(loc, "project.caption"),
        badge=translate_ui(loc, "project.hero_badge"),
    )
    guidance = html.Div(
        [
            guidance_block(
                translate_ui(loc, "project.dash.guidance_title"),
                body=translate_ui(loc, "project.dash.guidance_body"),
            ),
            typical_workflow_block(
                [
                    translate_ui(loc, "project.dash.workflow_step1"),
                    translate_ui(loc, "project.dash.workflow_step2"),
                    translate_ui(loc, "project.dash.workflow_step3"),
                ],
                title=translate_ui(loc, "project.dash.workflow_title"),
            ),
        ]
    )
    return header, guidance


@callback(
    Output("project-qa-title", "children"),
    Output("new-workspace-btn", "children"),
    Output("save-project-btn", "children"),
    Output("project-load-title", "children"),
    Output("project-upload-caption", "children"),
    Output("load-project-btn", "children"),
    Input("ui-locale", "data"),
)
def render_project_quick_action_labels(locale_data):
    loc = _loc(locale_data)
    return (
        translate_ui(loc, "project.dash.quick_actions"),
        translate_ui(loc, "project.dash.start_new_workspace"),
        translate_ui(loc, "project.dash.prepare_and_download"),
        translate_ui(loc, "sidebar.project.load"),
        translate_ui(loc, "project.dash.upload_cta"),
        translate_ui(loc, "sidebar.project.load_selected"),
    )


@callback(
    Output("project-prepare-first-btn", "children"),
    Output("project-cancel-btn", "children"),
    Input("ui-locale", "data"),
)
def sync_prepare_and_cancel_labels(locale_data):
    loc = _loc(locale_data)
    return translate_ui(loc, "project.dash.prepare_archive_first"), translate_ui(loc, "project.dash.cancel")


@callback(
    Output("pending-project-upload", "data"),
    Output("selected-project-upload", "children"),
    Input("project-upload", "contents"),
    State("project-upload", "filename"),
    State("ui-locale", "data"),
    prevent_initial_call=True,
)
def stage_project_upload(contents, file_name, locale_data):
    if not contents:
        raise dash.exceptions.PreventUpdate
    loc = _loc(locale_data)
    _, content_string = contents.split(",", 1)
    name = file_name or f"project{PROJECT_EXTENSION}"
    if not _allowed_project_archive_filename(name):
        return None, dbc.Alert(translate_ui(loc, "project.dash.invalid_archive_extension"), color="warning", className="mb-0 py-2")
    payload = {"file_name": name, "archive_base64": content_string}
    prefix = translate_ui(loc, "project.dash.selected_archive_prefix")
    return payload, f"{prefix} {payload['file_name']}"


@callback(
    Output("workspace-summary", "children"),
    Output("workspace-datasets-panel", "children"),
    Output("workspace-results-panel", "children"),
    Output("compare-summary-panel", "children"),
    Output("project-save-eligibility", "data"),
    Input("project-id", "data"),
    Input("project-page-refresh", "data"),
    Input("workspace-refresh", "data"),
    Input("ui-locale", "data"),
)
def load_workspace(project_id, _refresh, _global_refresh, locale_data):
    loc = _loc(locale_data)
    if not project_id:
        empty = prereq_or_empty_help(
            translate_ui(loc, "project.dash.workspace_required_body"),
            title=translate_ui(loc, "project.dash.workspace_required_title"),
        )
        return empty, empty, empty, empty, {"can_prepare_archive": False}

    from dash_app.api_client import workspace_context, workspace_datasets, workspace_results

    try:
        context = workspace_context(project_id)
        datasets_payload = workspace_datasets(project_id)
        results_payload = workspace_results(project_id)
    except Exception as exc:
        error = html.P(
            f"{translate_ui(loc, 'project.dash.error_prefix')} {exc}",
            className="text-danger",
        )
        return error, error, error, error, {"can_prepare_archive": False}

    summary = context.get("summary", {})
    compare_workspace = context.get("compare_workspace") or {}
    can_prepare_archive = _can_prepare_archive(summary)
    metrics = dbc.Row(
        [
            dbc.Col(_metric_card(translate_ui(loc, "project.dash.metric_datasets"), str(summary.get("dataset_count", 0))), md=3),
            dbc.Col(
                _metric_card(translate_ui(loc, "project.dash.metric_saved_results"), str(summary.get("result_count", 0))),
                md=3,
            ),
            dbc.Col(_metric_card(translate_ui(loc, "project.dash.metric_figures"), str(summary.get("figure_count", 0))), md=3),
            dbc.Col(
                _metric_card(translate_ui(loc, "project.dash.metric_history_steps"), str(summary.get("analysis_history_count", 0))),
                md=3,
            ),
        ],
        className="g-3 mb-3",
    )
    active_name = (context.get("active_dataset") or {}).get("display_name") or translate_ui(loc, "project.dash.none_label")
    cmp_state = (
        translate_ui(loc, "project.dash.compare_ready")
        if compare_workspace.get("selected_datasets")
        else translate_ui(loc, "project.dash.compare_empty")
    )
    arch_detail = (
        translate_ui(loc, "project.dash.archive_ready_detail")
        if can_prepare_archive
        else translate_ui(loc, "project.dash.archive_needs_detail")
    )
    status_lines = html.Ul(
        [
            html.Li(translate_ui(loc, "project.dash.active_dataset", name=active_name)),
            html.Li(translate_ui(loc, "project.dash.compare_workspace_status", state=cmp_state)),
            html.Li(translate_ui(loc, "project.dash.archive_status", detail=arch_detail)),
        ],
        className="mb-3",
    )
    summary_block = html.Div(
        [metrics, next_step_block(_next_step(loc, summary, compare_workspace), locale=loc), status_lines]
    )

    dataset_rows = datasets_payload.get("datasets", [])
    if dataset_rows:
        dataset_table_view = html.Div(
            [
                html.H5(translate_ui(loc, "project.dash.loaded_runs"), className="mb-3"),
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
                html.H5(translate_ui(loc, "project.dash.loaded_runs"), className="mb-3"),
                prereq_or_empty_help(
                    translate_ui(loc, "project.dash.no_loaded_runs_body"),
                    tone="secondary",
                    title=translate_ui(loc, "project.dash.no_loaded_runs_title"),
                ),
            ]
        )

    result_rows = results_payload.get("results", [])
    result_issues = results_payload.get("issues", [])
    if result_rows:
        results_content = [
            html.H5(translate_ui(loc, "project.dash.saved_result_records"), className="mb-3"),
            dataset_table(
                result_rows,
                ["id", "analysis_type", "status", "dataset_key", "workflow_template", "saved_at_utc"],
                table_id="project-results-table",
            ),
        ]
        if result_issues:
            results_content.insert(
                1,
                dbc.Alert(
                    [
                        html.Div(translate_ui(loc, "project.dash.results_incomplete_hint"), className="fw-semibold mb-1"),
                        html.Ul([html.Li(issue) for issue in result_issues], className="mb-0"),
                    ],
                    color="warning",
                    className="mb-3",
                ),
            )
        results_view = html.Div([*results_content])
    else:
        results_view = html.Div(
            [
                html.H5(translate_ui(loc, "project.dash.saved_result_records"), className="mb-3"),
                prereq_or_empty_help(
                    translate_ui(loc, "project.dash.no_saved_results_body"),
                    tone="secondary",
                    title=translate_ui(loc, "project.dash.no_saved_results_title"),
                ),
            ]
        )

    none_l = translate_ui(loc, "project.dash.none_label")
    na_l = translate_ui(loc, "project.dash.na_label")
    compare_view = html.Div(
        [
            html.H5(translate_ui(loc, "project.dash.compare_workspace"), className="mb-3"),
            html.P(f"{translate_ui(loc, 'project.dash.analysis_type')} {compare_workspace.get('analysis_type', na_l)}", className="mb-1"),
            html.P(
                f"{translate_ui(loc, 'project.dash.selected_runs')} "
                f"{', '.join(compare_workspace.get('selected_datasets') or []) or none_l}",
                className="mb-1",
            ),
            html.P(
                f"{translate_ui(loc, 'project.dash.saved_figure')} {compare_workspace.get('figure_key') or none_l}",
                className="mb-1",
            ),
            html.P(compare_workspace.get("notes") or translate_ui(loc, "project.dash.no_compare_notes"), className="text-muted"),
        ]
    )

    return summary_block, dataset_table_view, results_view, compare_view, {"can_prepare_archive": can_prepare_archive}


@callback(
    Output("project-confirm-action", "data"),
    Output("project-confirm-message", "children"),
    Output("project-confirm-actions", "style"),
    Output("project-prepare-first-btn", "disabled"),
    Output("project-prepare-first-btn", "className"),
    Output("project-confirm-btn", "children"),
    Output("load-project-output", "children"),
    Input("new-workspace-btn", "n_clicks"),
    Input("load-project-btn", "n_clicks"),
    State("project-id", "data"),
    State("pending-project-upload", "data"),
    State("ui-locale", "data"),
    prevent_initial_call=True,
)
def request_project_action(new_clicks, load_clicks, project_id, pending_upload, locale_data):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    loc = _loc(locale_data)
    from dash_app.api_client import workspace_context

    context = workspace_context(project_id) if project_id else {"summary": {}}
    summary = context.get("summary", {})
    has_content = any(
        summary.get(key, 0) > 0
        for key in ("dataset_count", "result_count", "figure_count", "analysis_history_count")
    ) or bool((context.get("compare_workspace") or {}).get("selected_datasets"))
    can_prepare = _can_prepare_archive(summary)

    if button_id == "new-workspace-btn":
        action = {"action": "new"}
        alert_body = (
            translate_ui(loc, "project.dash.clear_workspace_warning")
            if has_content
            else translate_ui(loc, "project.dash.clear_workspace_confirm")
        )
        panel_msg = dbc.Alert(alert_body, color="warning")
        prepare_cls = "w-100" if (has_content and can_prepare) else "w-100 d-none"
        prepare_disabled = not (has_content and can_prepare)
        confirm_label = (
            translate_ui(loc, "project.dash.confirm_clear")
            if has_content
            else translate_ui(loc, "project.dash.confirm_generic")
        )
        return (
            action,
            panel_msg,
            {"display": "block"},
            prepare_disabled,
            prepare_cls,
            confirm_label,
            dash.no_update,
        )

    if not pending_upload:
        return (
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dbc.Alert(translate_ui(loc, "project.dash.choose_archive_first"), color="warning"),
        )
    if has_content:
        action = {"action": "load"}
        panel_msg = dbc.Alert(translate_ui(loc, "project.dash.load_replace_warning"), color="warning")
        return (
            action,
            panel_msg,
            {"display": "block"},
            True,
            "w-100 d-none",
            translate_ui(loc, "project.dash.continue_loading"),
            dash.no_update,
        )
    action = {"action": "load"}
    panel_msg = dbc.Alert(translate_ui(loc, "project.dash.load_confirm_simple"), color="warning")
    return (
        action,
        panel_msg,
        {"display": "block"},
        True,
        "w-100 d-none",
        translate_ui(loc, "project.dash.continue_loading"),
        dash.no_update,
    )


@callback(
    Output("project-id", "data", allow_duplicate=True),
    Output("project-page-refresh", "data", allow_duplicate=True),
    Output("project-confirm-message", "children", allow_duplicate=True),
    Output("project-confirm-actions", "style", allow_duplicate=True),
    Output("project-prepare-first-btn", "disabled", allow_duplicate=True),
    Output("project-prepare-first-btn", "className", allow_duplicate=True),
    Output("project-confirm-btn", "children", allow_duplicate=True),
    Output("project-confirm-action", "data", allow_duplicate=True),
    Output("pending-project-upload", "data", allow_duplicate=True),
    Output("load-project-output", "children", allow_duplicate=True),
    Input("project-confirm-btn", "n_clicks"),
    Input("project-cancel-btn", "n_clicks"),
    State("project-confirm-action", "data"),
    State("pending-project-upload", "data"),
    State("project-page-refresh", "data"),
    State("ui-locale", "data"),
    prevent_initial_call=True,
)
def resolve_project_action(confirm_clicks, cancel_clicks, action, pending_upload, refresh_value, locale_data):
    ctx = dash.callback_context
    if not ctx.triggered or not action:
        raise dash.exceptions.PreventUpdate

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    loc = _loc(locale_data)

    def _cleared_panel():
        return (
            "",
            {"display": "none"},
            True,
            "w-100 d-none",
            translate_ui(loc, "project.dash.confirm_generic"),
        )

    if button_id == "project-cancel-btn":
        msg, style, prep_dis, prep_cls, confirm_lbl = _cleared_panel()
        return (
            dash.no_update,
            dash.no_update,
            msg,
            style,
            prep_dis,
            prep_cls,
            confirm_lbl,
            None,
            dash.no_update,
            dbc.Alert(translate_ui(loc, "project.dash.action_cancelled"), color="secondary"),
        )

    from dash_app.api_client import project_load, workspace_new

    if action.get("action") == "new":
        result = workspace_new()
        msg, style, prep_dis, prep_cls, confirm_lbl = _cleared_panel()
        return (
            result.get("project_id"),
            int(refresh_value or 0) + 1,
            msg,
            style,
            prep_dis,
            prep_cls,
            confirm_lbl,
            None,
            dash.no_update,
            dbc.Alert(translate_ui(loc, "project.dash.workspace_cleared"), color="success"),
        )

    if action.get("action") == "load" and pending_upload:
        result = project_load(pending_upload["archive_base64"])
        summary = result.get("summary", {})
        msg, style, prep_dis, prep_cls, confirm_lbl = _cleared_panel()
        return (
            result.get("project_id"),
            int(refresh_value or 0) + 1,
            msg,
            style,
            prep_dis,
            prep_cls,
            confirm_lbl,
            None,
            None,
            dbc.Alert(
                translate_ui(
                    loc,
                    "project.dash.project_loaded",
                    datasets=summary.get("dataset_count", 0),
                    results=summary.get("result_count", 0),
                ),
                color="success",
            ),
        )

    raise dash.exceptions.PreventUpdate


def _run_project_save(project_id: str | None, save_eligibility: dict | None, loc: str):
    if not project_id:
        return (
            prereq_or_empty_help(
                translate_ui(loc, "project.dash.no_workspace_save_body"),
                title=translate_ui(loc, "project.dash.no_workspace_save_title"),
            ),
            dash.no_update,
        )
    if not bool((save_eligibility or {}).get("can_prepare_archive")):
        return (
            dbc.Alert(translate_ui(loc, "project.dash.archive_eligibility_warning"), color="warning"),
            dash.no_update,
        )

    from dash_app.api_client import project_save

    try:
        result = project_save(project_id)
    except Exception as exc:
        return (
            dbc.Alert(translate_ui(loc, "project.dash.save_failed", error=exc), color="danger"),
            dash.no_update,
        )

    archive_b64 = result.get("archive_base64", "")
    file_name = result.get("file_name", f"materialscope_project{PROJECT_EXTENSION}")
    archive_bytes = base64.b64decode(archive_b64)
    return (
        dbc.Alert(translate_ui(loc, "project.dash.archive_downloading"), color="success"),
        dcc.send_bytes(archive_bytes, file_name),
    )


@callback(
    Output("save-project-output", "children"),
    Output("project-download", "data"),
    Input("save-project-btn", "n_clicks"),
    Input("project-prepare-first-btn", "n_clicks"),
    State("project-id", "data"),
    State("project-save-eligibility", "data"),
    State("ui-locale", "data"),
    prevent_initial_call=True,
)
def save_project(save_clicks, prepare_clicks, project_id, save_eligibility, locale_data):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate
    prop = ctx.triggered[0]["prop_id"]
    trigger = prop.split(".")[0]
    if trigger not in ("save-project-btn", "project-prepare-first-btn"):
        raise dash.exceptions.PreventUpdate
    loc = _loc(locale_data)
    return _run_project_save(project_id, save_eligibility, loc)


@callback(
    Output("save-project-btn", "disabled"),
    Input("project-id", "data"),
    Input("project-save-eligibility", "data"),
)
def toggle_save_project_button(project_id, save_eligibility):
    return not (project_id and bool((save_eligibility or {}).get("can_prepare_archive")))
