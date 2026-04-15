"""Import page -- parity-focused dataset import and management."""

from __future__ import annotations

import base64

import dash
import dash_bootstrap_components as dbc
from dash import ALL, Input, Output, State, callback, dcc, html

from dash_app.components.chrome import page_header
from dash_app.components.data_preview import (
    dataset_table,
    metadata_list,
    metric_cards,
    original_columns_list,
    quick_plot,
    stats_table,
)
from dash_app.components.page_guidance import (
    guidance_block,
    next_step_block,
    prereq_or_empty_help,
    typical_workflow_block,
)
from dash_app.import_preview import build_import_preview
from dash_app.sample_data import list_sample_specs, resolve_sample_request

dash.register_page(__name__, path="/", title="Import - MaterialScope")

_NONE_VALUE = "__NONE__"
_DATA_TYPE_OPTIONS = [{"label": token, "value": token} for token in ["DSC", "TGA", "DTA", "FTIR", "RAMAN", "XRD"]]


def _mapping_options(columns: list[str]) -> list[dict[str, str]]:
    return [{"label": "-- None --", "value": _NONE_VALUE}] + [
        {"label": column, "value": column}
        for column in columns
    ]


def _summary_card(label: str, value: str) -> dbc.Card:
    return dbc.Card(dbc.CardBody([html.Small(label, className="text-muted text-uppercase"), html.H4(value, className="mb-0")]))


def _build_metrics(datasets: list[dict]) -> dbc.Row:
    vendors = {item.get("vendor", "Generic") for item in datasets}
    by_type = {
        token: sum(1 for item in datasets if item.get("data_type") == token)
        for token in ["DSC", "TGA", "DTA", "FTIR", "RAMAN", "XRD"]
    }
    type_summary = " / ".join(str(by_type[token]) for token in ["DSC", "TGA", "DTA", "FTIR", "RAMAN", "XRD"])
    return dbc.Row(
        [
            dbc.Col(_summary_card("Loaded Runs", str(len(datasets))), md=4),
            dbc.Col(_summary_card("D / T / DTA / F / R / X", type_summary), md=4),
            dbc.Col(_summary_card("Vendors", str(len(vendors))), md=4),
        ],
        className="g-3 mb-4",
    )


def _sample_buttons() -> list[dbc.Col]:
    cols: list[dbc.Col] = []
    for spec in list_sample_specs():
        cols.append(
            dbc.Col(
                dbc.Button(
                    spec["label"],
                    id={"type": "sample-load", "sample_id": spec["id"]},
                    color="secondary",
                    className="w-100",
                ),
                md=6,
                className="mb-2",
            )
        )
    return cols


layout = html.Div(
    [
        dcc.Store(id="pending-upload-files", data=[]),
        dcc.Store(id="pending-import-preview"),
        dcc.Store(id="home-refresh", data=0),
        page_header(
            "Data Import",
            "Upload, map, preview, and manage thermal analysis runs before analysis pages are migrated.",
            badge="Import",
        ),
        html.Div(
            [
                guidance_block(
                    "What this page does",
                    body=(
                        "Import raw or sample datasets into the active workspace, "
                        "validate column mapping, and inspect loaded runs before downstream work."
                    ),
                ),
                typical_workflow_block(
                    [
                        "Upload a file (or load sample data), then preview and map axis/signal columns.",
                        "Import the run and set an active dataset from the loaded dataset panel.",
                        "Open Project Workspace to confirm workspace status before Compare or Report.",
                    ],
                    title="How to use this page",
                ),
                next_step_block(
                    "After at least one dataset is loaded, use Project Workspace as the checkpoint for save/load and downstream readiness."
                ),
            ],
            className="mb-2",
        ),
        html.Div(id="import-metrics"),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    dbc.Tabs(
                                        [
                                            dbc.Tab(
                                                [
                                                    html.Div(
                                                        [
                                                            html.H5("Upload Files", className="mt-3 mb-3"),
                                                            dcc.Upload(
                                                                id="file-upload",
                                                                children=html.Div(
                                                                    [
                                                                        html.I(className="bi bi-cloud-arrow-up fs-1 d-block mb-2 text-muted"),
                                                                        "Drag and drop files here, or ",
                                                                        html.A("browse", className="ta-link-emphasis"),
                                                                    ],
                                                                    className="text-center py-4",
                                                                ),
                                                                className="upload-zone",
                                                                multiple=True,
                                                            ),
                                                            html.Div(id="upload-status", className="mt-3"),
                                                            dbc.Select(id="pending-file-select", className="mt-3"),
                                                            html.Div(id="pending-file-help", className="small text-muted mt-2"),
                                                            html.Div(id="mapping-preview-status", className="mt-3"),
                                                            html.Div(id="mapping-preview-table", className="mt-3"),
                                                            dbc.Row(
                                                                [
                                                                    dbc.Col(
                                                                        [
                                                                            dbc.Label("Data Type", className="mt-3"),
                                                                            dbc.Select(id="mapping-datatype-select", options=_DATA_TYPE_OPTIONS),
                                                                        ],
                                                                        md=4,
                                                                    ),
                                                                    dbc.Col(
                                                                        [
                                                                            dbc.Label("Axis Column", className="mt-3"),
                                                                            dbc.Select(id="mapping-temp-select"),
                                                                        ],
                                                                        md=4,
                                                                    ),
                                                                    dbc.Col(
                                                                        [
                                                                            dbc.Label("Signal Column", className="mt-3"),
                                                                            dbc.Select(id="mapping-signal-select"),
                                                                        ],
                                                                        md=4,
                                                                    ),
                                                                ],
                                                                className="g-3",
                                                            ),
                                                            dbc.Row(
                                                                [
                                                                    dbc.Col(
                                                                        [
                                                                            dbc.Label("Time Column", className="mt-3"),
                                                                            dbc.Select(id="mapping-time-select"),
                                                                        ],
                                                                        md=4,
                                                                    ),
                                                                    dbc.Col(
                                                                        [
                                                                            dbc.Label("Sample Name", className="mt-3"),
                                                                            dbc.Input(id="mapping-sample-name", type="text"),
                                                                        ],
                                                                        md=4,
                                                                    ),
                                                                    dbc.Col(
                                                                        [
                                                                            dbc.Label("Sample Mass (mg)", className="mt-3"),
                                                                            dbc.Input(id="mapping-sample-mass", type="number", value=0),
                                                                        ],
                                                                        md=4,
                                                                    ),
                                                                ],
                                                                className="g-3",
                                                            ),
                                                            dbc.Row(
                                                                [
                                                                    dbc.Col(
                                                                        [
                                                                            dbc.Label("Heating Rate (°C/min)", className="mt-3"),
                                                                            dbc.Input(id="mapping-heating-rate", type="number", value=10),
                                                                        ],
                                                                        md=6,
                                                                    ),
                                                                    dbc.Col(
                                                                        [
                                                                            dbc.Label("XRD Wavelength (Å)", className="mt-3"),
                                                                            dbc.Input(id="mapping-xrd-wavelength", type="number", value=1.5406),
                                                                        ],
                                                                        md=6,
                                                                    ),
                                                                ],
                                                                className="g-3",
                                                            ),
                                                            dbc.Button("Import with Mapping", id="import-mapped-btn", color="primary", className="mt-3"),
                                                        ]
                                                    )
                                                ],
                                                label="Upload File",
                                            ),
                                            dbc.Tab(
                                                [
                                                    html.Div(
                                                        [
                                                            html.H5("Load Sample Data", className="mt-3 mb-3"),
                                                            html.P("Load built-in sample datasets used across the current Streamlit product surface.", className="text-muted"),
                                                            dbc.Row(_sample_buttons()),
                                                            html.Div(id="sample-status", className="mt-3"),
                                                        ]
                                                    )
                                                ],
                                                label="Load Sample Data",
                                            ),
                                        ]
                                    ),
                                ]
                            ),
                            className="mb-4",
                        )
                    ],
                    md=6,
                ),
                dbc.Col(
                    [
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.H5("Loaded Datasets", className="mb-3"),
                                    html.Div(id="datasets-table"),
                                    dbc.Row(
                                        [
                                            dbc.Col(
                                                [
                                                    dbc.Label("Active Dataset"),
                                                    dbc.Select(id="active-dataset-select"),
                                                ],
                                                md=9,
                                            ),
                                            dbc.Col(
                                                dbc.Button(
                                                    "Remove",
                                                    id="remove-dataset-btn",
                                                    color="secondary",
                                                    className="ta-btn-remove w-100",
                                                ),
                                                md=3,
                                                className="d-flex align-items-center",
                                            ),
                                        ],
                                        className="g-2 align-items-center",
                                    ),
                                    html.Div(id="dataset-action-status", className="mt-3"),
                                ]
                            ),
                            className="mb-4",
                        ),
                        dbc.Card(
                            dbc.CardBody([html.Div(id="dataset-detail-panel")]),
                            className="mb-4",
                        ),
                    ],
                    md=6,
                ),
            ]
        ),
    ]
)


@callback(
    Output("upload-status", "children"),
    Output("pending-upload-files", "data"),
    Output("pending-file-select", "value"),
    Input("file-upload", "contents"),
    State("file-upload", "filename"),
    State("pending-upload-files", "data"),
    prevent_initial_call=True,
)
def collect_pending_uploads(contents_list, filenames, pending_files):
    if not contents_list:
        return dash.no_update, dash.no_update, dash.no_update

    pending_files = list(pending_files or [])
    existing = {item["file_name"] for item in pending_files}
    added = []
    for content, file_name in zip(contents_list, filenames):
        _, content_string = content.split(",", 1)
        if file_name in existing:
            continue
        pending_files.append({"file_name": file_name, "file_base64": content_string})
        added.append(file_name)

    if not added:
        return dbc.Alert("Files already queued for import preview.", color="info"), pending_files, dash.no_update

    return (
        dbc.Alert(f"Queued for preview: {', '.join(added)}", color="success", dismissable=True),
        pending_files,
        added[0],
    )


@callback(
    Output("pending-file-select", "options"),
    Output("pending-file-help", "children"),
    Input("pending-upload-files", "data"),
)
def pending_file_options(pending_files):
    items = pending_files or []
    options = [{"label": item["file_name"], "value": item["file_name"]} for item in items]
    help_text = (
        "Upload a file to preview, map, and import into the workspace."
        if not items
        else f"{len(items)} pending file(s) ready for preview and import."
    )
    return options, help_text


@callback(
    Output("pending-import-preview", "data"),
    Output("mapping-preview-status", "children"),
    Output("mapping-preview-table", "children"),
    Output("mapping-datatype-select", "value"),
    Output("mapping-temp-select", "options"),
    Output("mapping-temp-select", "value"),
    Output("mapping-signal-select", "options"),
    Output("mapping-signal-select", "value"),
    Output("mapping-time-select", "options"),
    Output("mapping-time-select", "value"),
    Output("mapping-sample-name", "value"),
    Output("mapping-sample-mass", "value"),
    Output("mapping-heating-rate", "value"),
    Output("mapping-xrd-wavelength", "value"),
    Input("pending-file-select", "value"),
    Input("ui-theme", "data"),
    State("pending-upload-files", "data"),
    prevent_initial_call=False,
)
def build_pending_preview(selected_file, _ui_theme, pending_files):
    if not selected_file:
        empty_options = _mapping_options([])
        return (
            None,
            prereq_or_empty_help(
                "Upload a file in the Upload File tab, then select it here to preview and map columns.",
                tone="secondary",
                title="No file selected",
            ),
            "",
            "DSC",
            empty_options,
            _NONE_VALUE,
            empty_options,
            _NONE_VALUE,
            empty_options,
            _NONE_VALUE,
            "",
            0,
            10,
            1.5406,
        )

    pending = next((item for item in (pending_files or []) if item["file_name"] == selected_file), None)
    if pending is None:
        raise dash.exceptions.PreventUpdate

    try:
        preview = build_import_preview(pending["file_name"], pending["file_base64"])
    except Exception as exc:
        empty_options = _mapping_options([])
        return (
            None,
            dbc.Alert(f"Preview failed: {exc}", color="danger"),
            "",
            "DSC",
            empty_options,
            _NONE_VALUE,
            empty_options,
            _NONE_VALUE,
            empty_options,
            _NONE_VALUE,
            "",
            0,
            10,
            1.5406,
        )

    guessed = preview.get("guessed_mapping") or {}
    columns = preview["columns"]
    options = _mapping_options(columns)

    suggested_type = str(
        guessed.get("suggested_data_type")
        or guessed.get("inferred_analysis_type")
        or guessed.get("data_type")
        or "DSC"
    ).upper()
    if suggested_type not in {item["value"] for item in _DATA_TYPE_OPTIONS}:
        suggested_type = "DSC"

    preview_rows = preview["preview_rows"]
    table = dataset_table(preview_rows, columns, page_size=min(10, len(preview_rows)), table_id="raw-preview-table")
    status = dbc.Alert(
        f"Preview ready: {preview['file_name']} | rows={preview['row_count']} | suggested type={suggested_type}",
        color="info",
    )

    def _pick(column_name: str | None) -> str:
        return column_name if column_name in columns else _NONE_VALUE

    return (
        preview,
        status,
        table,
        suggested_type,
        options,
        _pick(guessed.get("temperature")),
        options,
        _pick(guessed.get("signal")),
        options,
        _pick(guessed.get("time")),
        "",
        0,
        10,
        1.5406,
    )


@callback(
    Output("upload-status", "children", allow_duplicate=True),
    Output("pending-upload-files", "data", allow_duplicate=True),
    Output("pending-file-select", "value", allow_duplicate=True),
    Output("home-refresh", "data", allow_duplicate=True),
    Input("import-mapped-btn", "n_clicks"),
    State("project-id", "data"),
    State("pending-import-preview", "data"),
    State("pending-upload-files", "data"),
    State("pending-file-select", "value"),
    State("mapping-datatype-select", "value"),
    State("mapping-temp-select", "value"),
    State("mapping-signal-select", "value"),
    State("mapping-time-select", "value"),
    State("mapping-sample-name", "value"),
    State("mapping-sample-mass", "value"),
    State("mapping-heating-rate", "value"),
    State("mapping-xrd-wavelength", "value"),
    State("home-refresh", "data"),
    prevent_initial_call=True,
)
def import_with_mapping(
    n_clicks,
    project_id,
    preview,
    pending_files,
    selected_file,
    data_type,
    temp_col,
    signal_col,
    time_col,
    sample_name,
    sample_mass,
    heating_rate,
    xrd_wavelength,
    refresh_value,
):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate

    if not project_id:
        return (
            prereq_or_empty_help(
                "No active workspace. Open Project Workspace to start or load one, then import again.",
                title="Workspace required",
            ),
            dash.no_update,
            dash.no_update,
            dash.no_update,
        )

    if not preview:
        return (
            prereq_or_empty_help(
                "Select a pending file to build a preview before importing.",
                tone="secondary",
                title="Preview required",
            ),
            dash.no_update,
            dash.no_update,
            dash.no_update,
        )

    if temp_col == _NONE_VALUE or signal_col == _NONE_VALUE:
        return (
            dbc.Alert("Axis and signal columns are required.", color="warning"),
            dash.no_update,
            dash.no_update,
            dash.no_update,
        )

    available_columns = set(preview.get("columns", []))
    if temp_col not in available_columns or signal_col not in available_columns:
        return (
            dbc.Alert(
                "Column mapping is stale. Select the file again, then re-map axis and signal columns.",
                color="warning",
            ),
            dash.no_update,
            dash.no_update,
            dash.no_update,
        )

    from dash_app.api_client import dataset_import

    metadata = {
        "sample_name": sample_name or "Unknown",
        "sample_mass": float(sample_mass) if sample_mass not in (None, "", 0, 0.0) else None,
        "heating_rate": float(heating_rate) if data_type != "XRD" and heating_rate not in (None, "", 0, 0.0) else None,
        "xrd_wavelength_angstrom": float(xrd_wavelength) if data_type == "XRD" and xrd_wavelength not in (None, "", 0, 0.0) else None,
    }
    column_mapping = {
        "temperature": temp_col,
        "signal": signal_col,
    }
    if time_col and time_col != _NONE_VALUE:
        column_mapping["time"] = time_col

    try:
        result = dataset_import(
            project_id,
            preview["file_name"],
            preview["file_base64"],
            data_type=data_type,
            column_mapping=column_mapping,
            metadata=metadata,
        )
    except Exception as exc:
        exc_msg = str(exc)
        hint = ""
        if "thermal-analysis bounds" in exc_msg or "Temperature range" in exc_msg:
            hint = " Hint: the axis range looks like wavenumber data -- try selecting FTIR or RAMAN as the data type."
        elif "strictly increasing" in exc_msg:
            hint = " Hint: the axis is not monotonic -- check column mapping or try FTIR/RAMAN for spectral data."
        return (
            dbc.Alert(f"Import failed: {exc_msg}{hint}", color="danger", dismissable=True),
            dash.no_update,
            dash.no_update,
            dash.no_update,
        )

    remaining = [item for item in (pending_files or []) if item["file_name"] != selected_file]
    next_selected = remaining[0]["file_name"] if remaining else None
    ds = result.get("dataset", {})
    return (
        dbc.Alert(
            (
                f"Imported: {ds.get('display_name', preview['file_name'])} ({ds.get('data_type', '?')}). "
                "Next: confirm workspace status in Project Workspace."
            ),
            color="success",
            dismissable=True,
        ),
        remaining,
        next_selected,
        int(refresh_value or 0) + 1,
    )


@callback(
    Output("sample-status", "children"),
    Output("home-refresh", "data", allow_duplicate=True),
    Input({"type": "sample-load", "sample_id": ALL}, "n_clicks"),
    State({"type": "sample-load", "sample_id": ALL}, "id"),
    State("project-id", "data"),
    State("home-refresh", "data"),
    prevent_initial_call=True,
)
def load_sample(_clicks, ids, project_id, refresh_value):
    if not project_id:
        return (
            prereq_or_empty_help(
                "No active workspace. Open Project Workspace to start or load one, then load sample data.",
                title="Workspace required",
            ),
            dash.no_update,
        )
    ctx = dash.callback_context
    triggered = ctx.triggered_id
    if not triggered:
        raise dash.exceptions.PreventUpdate

    button_id = triggered.get("sample_id") if isinstance(triggered, dict) else None
    sample_path, dtype = resolve_sample_request(button_id or "")
    if sample_path is None or dtype is None:
        raise dash.exceptions.PreventUpdate

    if not sample_path.exists():
        return dbc.Alert(f"Sample file not found: {sample_path.name}", color="warning"), dash.no_update

    from dash_app.api_client import dataset_import

    try:
        result = dataset_import(
            project_id,
            sample_path.name,
            base64.b64encode(sample_path.read_bytes()).decode("ascii"),
            data_type=dtype,
        )
    except Exception as exc:
        return dbc.Alert(f"Sample load failed: {exc}", color="danger"), dash.no_update

    dataset = result.get("dataset", {})
    return (
        dbc.Alert(
            f"Loaded sample: {dataset.get('display_name', sample_path.name)}",
            color="success",
            dismissable=True,
        ),
        int(refresh_value or 0) + 1,
    )


@callback(
    Output("import-metrics", "children"),
    Output("datasets-table", "children"),
    Output("active-dataset-select", "options"),
    Output("active-dataset-select", "value"),
    Input("project-id", "data"),
    Input("home-refresh", "data"),
    Input("ui-theme", "data"),
    prevent_initial_call=False,
)
def load_workspace_datasets(project_id, _refresh, _ui_theme):
    if not project_id:
        return (
            "",
            prereq_or_empty_help(
                "No active workspace. Open Project Workspace to create or load a workspace, then return to Import.",
                title="Workspace required",
            ),
            [],
            None,
        )

    from dash_app.api_client import workspace_datasets

    try:
        payload = workspace_datasets(project_id)
    except Exception as exc:
        error = html.P(f"Error: {exc}", className="text-danger")
        return "", error, [], None

    datasets = payload.get("datasets", [])
    if not datasets:
        return (
            _build_metrics([]),
            prereq_or_empty_help(
                "No datasets are loaded yet. Upload files or load sample datasets to populate this workspace.",
                tone="secondary",
                title="No datasets in workspace",
            ),
            [],
            None,
        )

    rows = [
        {
            "key": item.get("key"),
            "display_name": item.get("display_name"),
            "data_type": item.get("data_type"),
            "vendor": item.get("vendor"),
            "sample_name": item.get("sample_name"),
            "points": item.get("points"),
            "validation_status": item.get("validation_status"),
        }
        for item in datasets
    ]
    table = dataset_table(rows, ["key", "display_name", "data_type", "vendor", "sample_name", "points", "validation_status"], table_id="datasets-summary-table")
    options = [{"label": item.get("display_name", item.get("key")), "value": item.get("key")} for item in datasets]
    return _build_metrics(datasets), table, options, payload.get("active_dataset")


@callback(
    Output("home-refresh", "data", allow_duplicate=True),
    Input("active-dataset-select", "value"),
    State("project-id", "data"),
    State("home-refresh", "data"),
    prevent_initial_call=True,
)
def set_active_dataset(dataset_key, project_id, refresh_value):
    if not dataset_key or not project_id:
        raise dash.exceptions.PreventUpdate
    from dash_app.api_client import workspace_set_active_dataset

    workspace_set_active_dataset(project_id, dataset_key)
    return int(refresh_value or 0) + 1


@callback(
    Output("dataset-action-status", "children"),
    Output("home-refresh", "data", allow_duplicate=True),
    Input("remove-dataset-btn", "n_clicks"),
    State("active-dataset-select", "value"),
    State("project-id", "data"),
    State("home-refresh", "data"),
    prevent_initial_call=True,
)
def remove_dataset(n_clicks, dataset_key, project_id, refresh_value):
    if not n_clicks or not dataset_key or not project_id:
        raise dash.exceptions.PreventUpdate

    from dash_app.api_client import workspace_delete_dataset

    try:
        workspace_delete_dataset(project_id, dataset_key)
    except Exception as exc:
        return dbc.Alert(f"Remove failed: {exc}", color="danger"), dash.no_update
    return dbc.Alert(f"Removed dataset: {dataset_key}", color="warning"), int(refresh_value or 0) + 1


@callback(
    Output("dataset-detail-panel", "children"),
    Input("project-id", "data"),
    Input("active-dataset-select", "value"),
    Input("home-refresh", "data"),
    Input("ui-theme", "data"),
    prevent_initial_call=False,
)
def load_active_dataset_detail(project_id, dataset_key, _refresh, ui_theme):
    if not project_id:
        return prereq_or_empty_help(
            "No active workspace. Start or load a workspace in Project, then import datasets here.",
            title="Workspace required",
        )
    if not dataset_key:
        return prereq_or_empty_help(
            "Select an active dataset from the Loaded Datasets panel to inspect metadata, preview, and quick plot.",
            tone="secondary",
            title="Select a dataset",
        )

    from dash_app.api_client import workspace_dataset_data, workspace_dataset_detail

    try:
        detail = workspace_dataset_detail(project_id, dataset_key)
        data_payload = workspace_dataset_data(project_id, dataset_key)
    except Exception as exc:
        return html.P(f"Error: {exc}", className="text-danger")

    rows = data_payload.get("rows", [])
    columns = data_payload.get("columns", [])
    preview_rows = rows[:10]

    return html.Div(
        [
            html.H5(detail.get("dataset", {}).get("display_name", dataset_key), className="mb-3"),
            metric_cards(detail),
            dbc.Accordion(
                [
                    dbc.AccordionItem(metadata_list(detail), title="Metadata"),
                    dbc.AccordionItem(original_columns_list(detail), title="Column Mapping"),
                    dbc.AccordionItem(dataset_table(preview_rows, columns, page_size=min(10, len(preview_rows) or 1), table_id="active-dataset-table"), title="Data Preview"),
                    dbc.AccordionItem(stats_table(rows, columns), title="Statistics"),
                ],
                start_collapsed=True,
                always_open=True,
                className="mb-3",
            ),
            html.H6("Quick View", className="mb-2"),
            quick_plot(rows, detail, ui_theme=ui_theme),
        ]
    )
