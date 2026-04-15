"""Compare workspace -- best-available analysis-state overlays, raw import mode, and batch runs."""

from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, dcc, html
import plotly.graph_objects as go

from core.modalities import get_modality, stable_analysis_types
from core.processing_schema import get_workflow_templates
from dash_app.compare_curve_utils import axis_titles, pick_best_series
from dash_app.components.chrome import page_header
from dash_app.components.data_preview import dataset_table
from dash_app.components.page_guidance import (
    guidance_block,
    next_step_block,
    prereq_or_empty_help,
    typical_workflow_block,
)
from dash_app.theme import apply_figure_theme

dash.register_page(__name__, path="/compare", title="Compare - MaterialScope")


def _eligible_dataset(dataset: dict, analysis_type: str) -> bool:
    modality = get_modality(analysis_type)
    if modality is None:
        return False
    return modality.adapter.is_dataset_eligible(str(dataset.get("data_type") or "UNKNOWN"))


def _available_types(datasets: list[dict]) -> list[str]:
    options: list[str] = []
    for token in stable_analysis_types():
        if any(_eligible_dataset(dataset, token) for dataset in datasets):
            options.append(token)
    return options


def _compare_prereq_state(datasets: list[dict], analysis_type: str | None, selected_runs: list[str] | None) -> str | None:
    """Return a human-readable prerequisite state for compare guidance."""
    if not datasets:
        return "no_datasets"
    available_types = _available_types(datasets)
    if not available_types:
        return "no_eligible_types"
    if not analysis_type:
        return "select_analysis_type"
    run_count = len(selected_runs or [])
    if run_count < 2:
        return "insufficient_overlay_runs"
    return None


layout = html.Div(
    [
        dcc.Store(id="compare-refresh", data=0),
        page_header(
            "Compare Workspace",
            "Overlay runs with best-available processed curves or raw import data; run batch templates across selected datasets.",
            badge="Compare",
        ),
        html.Div(
            [
                guidance_block(
                    "What this page does",
                    body=(
                        "Build a reusable compare workspace by selecting analysis type and runs, then "
                        "overlaying curves in best-available or raw mode."
                    ),
                ),
                typical_workflow_block(
                    [
                        "Choose an analysis type compatible with your imported runs.",
                        "Select runs and review the overlay (2+ runs recommended for comparison).",
                        "Save compare workspace, then open Report Center to include compare context.",
                    ],
                    title="Typical workflow",
                ),
                guidance_block(
                    "Usage notes",
                    bullets=[
                        "Overlay comparison requires at least two selected runs.",
                        "Batch execution can run with one or more selected runs.",
                    ],
                    tone="secondary",
                ),
                next_step_block("Save Compare Workspace before generating report outputs."),
            ],
            className="mb-2",
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    dbc.Label("Analysis Type"),
                                    dbc.Select(id="compare-analysis-type"),
                                    dbc.Label("Selected Runs", className="mt-3"),
                                    dcc.Dropdown(id="compare-selected-runs", multi=True, className="ta-dropdown"),
                                    dbc.Label("Overlay signal", className="mt-3"),
                                    dbc.RadioItems(
                                        id="compare-signal-mode",
                                        options=[
                                            {"label": "Best available (analysis state)", "value": "best"},
                                            {"label": "Raw import data", "value": "raw"},
                                        ],
                                        value="best",
                                        inline=False,
                                    ),
                                    dbc.Label("Workspace Notes", className="mt-3"),
                                    dbc.Textarea(id="compare-notes", style={"height": "120px"}),
                                    dbc.Button("Save Compare Workspace", id="save-compare-workspace-btn", color="primary", className="mt-3"),
                                    html.Div(id="compare-status", className="mt-3"),
                                ]
                            ),
                            className="mb-4",
                        ),
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.H5("Batch template", className="mb-3"),
                                    dbc.Label("Workflow template"),
                                    dbc.Select(id="compare-batch-template-select"),
                                    dbc.Button(
                                        "Run batch on selected runs",
                                        id="compare-batch-run-btn",
                                        color="secondary",
                                        className="mt-3",
                                    ),
                                    html.Div(id="compare-batch-status", className="mt-3"),
                                ]
                            ),
                            className="mb-4",
                        ),
                        dbc.Card(dbc.CardBody(html.Div(id="compare-overlay-panel")), className="mb-4"),
                    ],
                    md=8,
                ),
                dbc.Col(
                    [
                        dbc.Card(dbc.CardBody(html.Div(id="compare-summary-panel")), className="mb-4"),
                        dbc.Card(dbc.CardBody(html.Div(id="compare-saved-result-preview")), className="mb-4"),
                        dbc.Card(dbc.CardBody(html.Div(id="compare-batch-summary-panel")), className="mb-4"),
                    ],
                    md=4,
                ),
            ]
        ),
    ]
)


@callback(
    Output("compare-analysis-type", "options"),
    Output("compare-analysis-type", "value"),
    Output("compare-selected-runs", "options"),
    Output("compare-selected-runs", "value"),
    Output("compare-notes", "value"),
    Input("project-id", "data"),
    Input("compare-refresh", "data"),
    Input("workspace-refresh", "data"),
    prevent_initial_call=False,
)
def load_compare_workspace(project_id, _refresh, _global_refresh):
    if not project_id:
        return [], None, [], [], ""

    from dash_app.api_client import compare_workspace, workspace_datasets

    datasets = workspace_datasets(project_id).get("datasets", [])
    available_types = _available_types(datasets)
    if not available_types:
        return [], None, [], [], ""

    workspace = compare_workspace(project_id).get("compare_workspace", {})
    analysis_type = workspace.get("analysis_type")
    if analysis_type not in available_types:
        analysis_type = available_types[0]
    eligible = [item for item in datasets if _eligible_dataset(item, analysis_type)]
    run_options = [{"label": item.get("display_name", item.get("key")), "value": item.get("key")} for item in eligible]
    selected = [key for key in (workspace.get("selected_datasets") or []) if key in {item["value"] for item in run_options}]
    return (
        [{"label": token, "value": token} for token in available_types],
        analysis_type,
        run_options,
        selected,
        workspace.get("notes") or "",
    )


@callback(
    Output("compare-selected-runs", "options", allow_duplicate=True),
    Output("compare-selected-runs", "value", allow_duplicate=True),
    Input("compare-analysis-type", "value"),
    State("project-id", "data"),
    State("compare-selected-runs", "value"),
    prevent_initial_call=True,
)
def update_compare_eligible_runs(analysis_type, project_id, selected_runs):
    if not analysis_type or not project_id:
        raise dash.exceptions.PreventUpdate
    from dash_app.api_client import workspace_datasets

    datasets = workspace_datasets(project_id).get("datasets", [])
    eligible = [item for item in datasets if _eligible_dataset(item, analysis_type)]
    run_options = [{"label": item.get("display_name", item.get("key")), "value": item.get("key")} for item in eligible]
    allowed = {item["value"] for item in run_options}
    selected = [key for key in (selected_runs or []) if key in allowed]
    return run_options, selected


@callback(
    Output("compare-batch-template-select", "options"),
    Output("compare-batch-template-select", "value"),
    Input("compare-analysis-type", "value"),
    Input("project-id", "data"),
    Input("compare-refresh", "data"),
    prevent_initial_call=False,
)
def load_batch_templates(analysis_type, project_id, _refresh):
    if not project_id or not analysis_type:
        return [], None
    templates = get_workflow_templates(analysis_type)
    options = [{"label": entry.get("label", entry["id"]), "value": entry["id"]} for entry in templates]
    default_value = options[0]["value"] if options else None
    return options, default_value


@callback(
    Output("compare-status", "children"),
    Output("compare-refresh", "data", allow_duplicate=True),
    Input("save-compare-workspace-btn", "n_clicks"),
    State("project-id", "data"),
    State("compare-analysis-type", "value"),
    State("compare-selected-runs", "value"),
    State("compare-notes", "value"),
    State("compare-refresh", "data"),
    prevent_initial_call=True,
)
def save_compare_workspace(n_clicks, project_id, analysis_type, selected_runs, notes, refresh_value):
    if not n_clicks or not project_id or not analysis_type:
        raise dash.exceptions.PreventUpdate
    from dash_app.api_client import update_compare_workspace

    try:
        update_compare_workspace(
            project_id,
            analysis_type=analysis_type,
            selected_datasets=selected_runs or [],
            notes=notes or "",
        )
    except Exception as exc:
        return dbc.Alert(f"Compare workspace save failed: {exc}", color="danger"), dash.no_update
    return dbc.Alert("Compare workspace saved.", color="success"), int(refresh_value or 0) + 1


@callback(
    Output("compare-batch-status", "children"),
    Output("compare-refresh", "data", allow_duplicate=True),
    Output("workspace-refresh", "data", allow_duplicate=True),
    Input("compare-batch-run-btn", "n_clicks"),
    State("project-id", "data"),
    State("compare-analysis-type", "value"),
    State("compare-selected-runs", "value"),
    State("compare-batch-template-select", "value"),
    State("compare-refresh", "data"),
    State("workspace-refresh", "data"),
    prevent_initial_call=True,
)
def run_compare_batch(n_clicks, project_id, analysis_type, selected_runs, template_id, compare_refresh, workspace_refresh):
    if not n_clicks or not project_id or not analysis_type:
        raise dash.exceptions.PreventUpdate
    selected_runs = selected_runs or []
    if len(selected_runs) < 1:
        return dbc.Alert("Select at least one dataset for batch run.", color="warning"), dash.no_update, dash.no_update

    from dash_app.api_client import workspace_batch_run

    try:
        result = workspace_batch_run(
            project_id,
            analysis_type=analysis_type,
            workflow_template_id=template_id,
            dataset_keys=selected_runs,
        )
    except Exception as exc:
        return dbc.Alert(f"Batch run failed: {exc}", color="danger"), dash.no_update, dash.no_update

    outcomes = result.get("outcomes") or {}
    msg = (
        f"Batch complete: saved={outcomes.get('saved', 0)}, blocked={outcomes.get('blocked', 0)}, "
        f"failed={outcomes.get('failed', 0)}."
    )
    alert = dbc.Alert(msg, color="success")
    return (
        alert,
        int(compare_refresh or 0) + 1,
        int(workspace_refresh or 0) + 1,
    )


@callback(
    Output("compare-overlay-panel", "children"),
    Output("compare-summary-panel", "children"),
    Output("compare-saved-result-preview", "children"),
    Output("compare-batch-summary-panel", "children"),
    Input("project-id", "data"),
    Input("compare-analysis-type", "value"),
    Input("compare-selected-runs", "value"),
    Input("compare-signal-mode", "value"),
    Input("compare-refresh", "data"),
    Input("workspace-refresh", "data"),
    Input("ui-theme", "data"),
    prevent_initial_call=False,
)
def render_compare_workspace(
    project_id, analysis_type, selected_runs, signal_mode, _compare_refresh, _workspace_refresh, ui_theme
):
    if not project_id:
        empty = prereq_or_empty_help(
            "No active workspace. Import datasets and save analysis results before using Compare.",
            title="Workspace required",
        )
        return empty, empty, empty, empty

    from dash_app.api_client import (
        analysis_state_curves,
        compare_workspace,
        workspace_dataset_data,
        workspace_datasets,
        workspace_results,
    )

    datasets = {item.get("key"): item for item in workspace_datasets(project_id).get("datasets", [])}
    selected_runs = selected_runs or []
    results = workspace_results(project_id).get("results", [])
    result_keys = {
        item.get("dataset_key")
        for item in results
        if item.get("analysis_type") == analysis_type
    }
    cmp = compare_workspace(project_id).get("compare_workspace", {})
    prereq_state = _compare_prereq_state(list(datasets.values()), analysis_type, selected_runs)

    if prereq_state == "no_datasets":
        empty = prereq_or_empty_help(
            "No datasets loaded. Import runs first, then return to build compare overlays.",
            title="Datasets required",
        )
        return empty, empty, empty, empty
    if prereq_state == "no_eligible_types":
        empty = prereq_or_empty_help(
            "Datasets are loaded but none are eligible for stable compare analysis types. Check dataset data types in Import/Project.",
            title="No eligible analysis type",
        )
        return empty, empty, empty, empty
    if prereq_state == "select_analysis_type":
        empty = prereq_or_empty_help(
            "Select an analysis type to load eligible runs and build the compare workspace.",
            tone="secondary",
            title="Analysis type required",
        )
        return empty, empty, empty, empty

    if len(selected_runs) < 2:
        overlay = prereq_or_empty_help(
            "Select at least two runs to build an overlay. Batch execution can still run with one selected run.",
            tone="secondary",
            title="More runs needed for overlay",
        )
    else:
        fig = go.Figure()
        x_title, y_title = axis_titles(analysis_type)
        use_best = str(signal_mode or "best").lower() == "best"

        for dataset_key in selected_runs:
            label_base = datasets.get(dataset_key, {}).get("display_name", dataset_key)
            if use_best:
                try:
                    curves = analysis_state_curves(project_id, analysis_type, dataset_key)
                except Exception:
                    curves = {}
                picked = pick_best_series(curves) if curves else None
                if picked:
                    xs, ys, src = picked
                    fig.add_trace(
                        go.Scatter(
                            x=xs,
                            y=ys,
                            mode="lines",
                            name=f"{label_base} ({src})",
                        )
                    )
                else:
                    payload = workspace_dataset_data(project_id, dataset_key)
                    rows = payload.get("rows", [])
                    columns = payload.get("columns", [])
                    x_column = "temperature" if "temperature" in columns else (columns[0] if columns else None)
                    preferred_y = next(
                        (item for item in ["signal", "heat_flow", "mass_percent", "intensity", "absorbance"] if item in columns),
                        None,
                    )
                    y_column = preferred_y or (columns[1] if len(columns) > 1 else None)
                    if x_column and y_column:
                        x = [row.get(x_column) for row in rows]
                        y = [row.get(y_column) for row in rows]
                        x_title = x_column
                        y_title = y_column
                        fig.add_trace(
                            go.Scatter(
                                x=x,
                                y=y,
                                mode="lines",
                                name=f"{label_base} (raw fallback)",
                            )
                        )
            else:
                payload = workspace_dataset_data(project_id, dataset_key)
                rows = payload.get("rows", [])
                columns = payload.get("columns", [])
                x_column = "temperature" if "temperature" in columns else (columns[0] if columns else None)
                preferred_y = next(
                    (item for item in ["signal", "heat_flow", "mass_percent", "intensity", "absorbance"] if item in columns),
                    None,
                )
                y_column = preferred_y or (columns[1] if len(columns) > 1 else None)
                if x_column and y_column:
                    x = [row.get(x_column) for row in rows]
                    y = [row.get(y_column) for row in rows]
                    x_title = x_column
                    y_title = y_column
                    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", name=f"{label_base} (raw)"))

        mode_caption = "Best available (analysis state)" if use_best else "Raw import data"
        if not fig.data:
            overlay = html.P(
                "Could not build an overlay for the current selection (missing data columns or empty analysis state).",
                className="text-muted",
            )
        else:
            fig.update_layout(
                title=f"{analysis_type} Compare — {mode_caption}",
                xaxis_title=x_title,
                yaxis_title=y_title,
                margin=dict(l=48, r=24, t=56, b=48),
                height=420,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            )
            apply_figure_theme(fig, ui_theme)
            overlay = dcc.Graph(figure=fig, config={"displaylogo": False, "responsive": True}, className="ta-plot")

    summary_rows = []
    for dataset_key in selected_runs:
        dataset = datasets.get(dataset_key) or {}
        summary_rows.append(
            {
                "run": dataset_key,
                "sample_name": dataset.get("sample_name"),
                "vendor": dataset.get("vendor"),
                "heating_rate": dataset.get("heating_rate"),
                "points": dataset.get("points"),
                "saved_result": "Yes" if dataset_key in result_keys else "No",
            }
        )
    summary = html.Div(
        [
            html.H5("Workspace Summary", className="mb-3"),
            dataset_table(summary_rows, ["run", "sample_name", "vendor", "heating_rate", "points", "saved_result"], table_id="compare-summary-table")
            if summary_rows
            else html.P("No runs selected yet.", className="text-muted"),
        ]
    )

    preview_rows = [
        {
            "id": item.get("id"),
            "dataset_key": item.get("dataset_key"),
            "status": item.get("status"),
            "saved_at_utc": item.get("saved_at_utc"),
        }
        for item in results
        if item.get("analysis_type") == analysis_type and item.get("dataset_key") in selected_runs
    ]
    preview = html.Div(
        [
            html.H5("Saved Result Preview", className="mb-3"),
            dataset_table(preview_rows, ["id", "dataset_key", "status", "saved_at_utc"], table_id="compare-result-preview-table")
            if preview_rows
            else html.P("No saved results for the selected runs yet.", className="text-muted"),
        ]
    )

    batch_children: list = [html.H5("Last batch", className="mb-3")]
    feedback = cmp.get("batch_last_feedback") or {}
    if feedback:
        batch_children.append(
            html.P(
                f"Outcomes: saved={feedback.get('saved', 0)}, blocked={feedback.get('blocked', 0)}, failed={feedback.get('failed', 0)}.",
                className="small",
            )
        )
    if cmp.get("batch_template_id"):
        batch_children.append(html.P(f"Template: {cmp.get('batch_template_label') or cmp.get('batch_template_id')}", className="small text-muted"))
    batch_summary = cmp.get("batch_summary") or []
    if batch_summary:
        cols = [k for k in batch_summary[0].keys()][:8]
        batch_children.append(dataset_table(batch_summary, cols, table_id="compare-batch-summary-table"))
    else:
        batch_children.append(html.P("No batch run recorded yet for this workspace.", className="text-muted small"))
    batch_panel = html.Div(batch_children)

    return overlay, summary, preview, batch_panel
