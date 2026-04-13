"""Import page -- file upload and dataset management."""

from __future__ import annotations

import base64

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, dash_table, dcc, html

from dash_app.components.chrome import page_header

dash.register_page(__name__, path="/", title="Import - MaterialScope")


layout = html.Div([
    page_header(
        "Data Import",
        "Upload thermal analysis data files. Supported formats: CSV, TXT, XLSX.",
        badge="Import",
    ),

    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H5("Upload Files", className="mb-3"),
                    dcc.Upload(
                        id="file-upload",
                        children=html.Div([
                            html.I(className="bi bi-cloud-arrow-up fs-1 d-block mb-2 text-muted"),
                            "Drag and drop files here, or ",
                            html.A("browse", className="text-primary"),
                        ], className="text-center py-4"),
                        className="upload-zone",
                        multiple=True,
                    ),
                    html.Div(id="upload-status", className="mt-3"),
                ])
            ], className="mb-4"),

            dbc.Card([
                dbc.CardBody([
                    html.H5("Sample Data", className="mb-3"),
                    html.P(
                        "Load built-in sample datasets for testing.",
                        className="text-muted",
                    ),
                    dbc.Button(
                        "Load DSC Sample",
                        id="load-sample-dsc",
                        color="secondary",
                        size="sm",
                        className="me-2",
                    ),
                    dbc.Button(
                        "Load TGA Sample",
                        id="load-sample-tga",
                        color="secondary",
                        size="sm",
                    ),
                    html.Div(id="sample-status", className="mt-2"),
                ])
            ], className="mb-4"),
        ], md=5),

        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H5("Loaded Datasets", className="mb-3"),
                    dcc.Loading(
                        html.Div(id="dataset-list"),
                        type="default",
                    ),
                ])
            ], className="mb-4"),

            dbc.Card([
                dbc.CardBody([
                    html.H5("Quick Analysis", className="mb-3"),
                    html.P(
                        "Select a dataset and run automated analysis using "
                        "default workflow templates.",
                        className="text-muted",
                    ),
                    dbc.Select(
                        id="analysis-dataset-select",
                        placeholder="Select dataset...",
                        className="mb-2",
                    ),
                    dbc.Select(
                        id="analysis-type-select",
                        options=[
                            {"label": t, "value": t}
                            for t in ["DSC", "TGA", "DTA", "FTIR", "RAMAN", "XRD"]
                        ],
                        placeholder="Analysis type...",
                        className="mb-2",
                    ),
                    dbc.Button(
                        "Run Analysis",
                        id="run-analysis-btn",
                        color="primary",
                        disabled=True,
                    ),
                    html.Div(id="analysis-status", className="mt-3"),
                ])
            ]),
        ], md=7),
    ]),
])


@callback(
    Output("upload-status", "children"),
    Output("dataset-list", "children", allow_duplicate=True),
    Output("analysis-dataset-select", "options", allow_duplicate=True),
    Input("file-upload", "contents"),
    State("file-upload", "filename"),
    State("project-id", "data"),
    prevent_initial_call=True,
)
def handle_upload(contents_list, filenames, project_id):
    if not contents_list or not project_id:
        return dash.no_update, dash.no_update, dash.no_update

    from dash_app.api_client import dataset_import

    messages = []
    for content, fname in zip(contents_list, filenames):
        _, content_string = content.split(",", 1)
        try:
            result = dataset_import(project_id, fname, content_string)
            ds = result.get("dataset", {})
            messages.append(
                dbc.Alert(
                    f"Imported: {ds.get('display_name', fname)} ({ds.get('data_type', '?')})",
                    color="success",
                    dismissable=True,
                )
            )
        except Exception as exc:
            messages.append(
                dbc.Alert(f"Failed: {fname} -- {exc}", color="danger", dismissable=True)
            )

    ds_list, ds_options = _fetch_datasets(project_id)
    return html.Div(messages), ds_list, ds_options


@callback(
    Output("dataset-list", "children"),
    Output("analysis-dataset-select", "options"),
    Input("project-id", "data"),
    prevent_initial_call=False,
)
def load_datasets(project_id):
    if not project_id:
        return html.P("No workspace active.", className="text-muted"), []
    return _fetch_datasets(project_id)


def _fetch_datasets(project_id: str):
    from dash_app.api_client import workspace_datasets

    try:
        data = workspace_datasets(project_id)
    except Exception as exc:
        return html.P(f"Error: {exc}", className="text-danger"), []

    datasets = data.get("datasets", [])
    if not datasets:
        return html.P("No datasets loaded yet.", className="text-muted"), []

    rows = []
    for ds in datasets:
        badge_color = {"pass": "success", "warn": "warning", "fail": "danger"}.get(
            ds.get("validation_status", ""), "secondary"
        )
        rows.append(
            dbc.ListGroupItem([
                html.Div([
                    html.Strong(ds.get("display_name", ds.get("key", "?"))),
                    dbc.Badge(
                        ds.get("data_type", "?"),
                        color="info",
                        className="ms-2",
                    ),
                    dbc.Badge(
                        ds.get("validation_status", "?"),
                        color=badge_color,
                        className="ms-1",
                    ),
                ]),
                html.Small(
                    f"{ds.get('points', 0)} points | {ds.get('vendor', 'Generic')}",
                    className="text-muted",
                ),
            ])
        )

    options = [
        {"label": ds.get("display_name", ds.get("key")), "value": ds.get("key")}
        for ds in datasets
    ]
    return dbc.ListGroup(rows, flush=True), options


@callback(
    Output("run-analysis-btn", "disabled"),
    Input("analysis-dataset-select", "value"),
    Input("analysis-type-select", "value"),
)
def toggle_run_btn(dataset_key, analysis_type):
    return not (dataset_key and analysis_type)


@callback(
    Output("analysis-status", "children"),
    Output("dataset-list", "children", allow_duplicate=True),
    Input("run-analysis-btn", "n_clicks"),
    State("analysis-dataset-select", "value"),
    State("analysis-type-select", "value"),
    State("project-id", "data"),
    prevent_initial_call=True,
)
def run_analysis(n_clicks, dataset_key, analysis_type, project_id):
    if not n_clicks or not project_id or not dataset_key or not analysis_type:
        return dash.no_update, dash.no_update

    from dash_app.api_client import analysis_run

    try:
        result = analysis_run(project_id, dataset_key, analysis_type)
    except Exception as exc:
        return dbc.Alert(f"Analysis failed: {exc}", color="danger"), dash.no_update

    status = result.get("execution_status", "unknown")
    if status == "saved":
        msg = dbc.Alert(
            f"Analysis completed: {analysis_type} on {dataset_key} "
            f"(result {result.get('result_id', '?')})",
            color="success",
        )
    elif status == "blocked":
        msg = dbc.Alert(
            f"Analysis blocked: {result.get('failure_reason', 'validation issue')}",
            color="warning",
        )
    else:
        msg = dbc.Alert(
            f"Analysis failed: {result.get('failure_reason', 'unknown')}",
            color="danger",
        )

    ds_list, _ = _fetch_datasets(project_id)
    return msg, ds_list


@callback(
    Output("sample-status", "children"),
    Output("dataset-list", "children", allow_duplicate=True),
    Output("analysis-dataset-select", "options", allow_duplicate=True),
    Input("load-sample-dsc", "n_clicks"),
    Input("load-sample-tga", "n_clicks"),
    State("project-id", "data"),
    prevent_initial_call=True,
)
def load_sample(dsc_clicks, tga_clicks, project_id):
    if not project_id:
        return dash.no_update, dash.no_update, dash.no_update

    import os

    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update, dash.no_update

    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    sample_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sample_data")

    sample_map = {
        "load-sample-dsc": ("sample_dsc.csv", "DSC"),
        "load-sample-tga": ("sample_tga.csv", "TGA"),
    }

    fname, dtype = sample_map.get(button_id, (None, None))
    if not fname:
        return dash.no_update, dash.no_update, dash.no_update

    fpath = os.path.join(sample_dir, fname)
    if not os.path.exists(fpath):
        return (
            dbc.Alert(f"Sample file not found: {fname}", color="warning"),
            dash.no_update,
            dash.no_update,
        )

    with open(fpath, "rb") as f:
        file_b64 = base64.b64encode(f.read()).decode("ascii")

    from dash_app.api_client import dataset_import

    try:
        result = dataset_import(project_id, fname, file_b64, data_type=dtype)
        ds = result.get("dataset", {})
        msg = dbc.Alert(
            f"Loaded sample: {ds.get('display_name', fname)}",
            color="success",
            dismissable=True,
        )
    except Exception as exc:
        msg = dbc.Alert(f"Failed: {exc}", color="danger")

    ds_list, ds_options = _fetch_datasets(project_id)
    return msg, ds_list, ds_options
