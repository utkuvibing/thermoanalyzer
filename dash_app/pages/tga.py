"""TGA analysis page -- backend-driven first analysis slice.

Lets the user:
  1. Select an eligible TGA dataset from the workspace
  2. Select a TGA unit mode (auto / percent / absolute_mass)
  3. Select a TGA workflow template
  4. Run analysis through the backend /analysis/run endpoint
  5. View result summary cards, raw mass vs temperature figure,
     DTG overlay, step table, and processing details
  6. Auto-refresh workspace/report/compare state after a successful run
"""

from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, dcc, html
import plotly.graph_objects as go

from dash_app.components.chrome import page_header
from dash_app.components.data_preview import dataset_table

dash.register_page(__name__, path="/tga", title="TGA Analysis - MaterialScope")

_TGA_WORKFLOW_TEMPLATES = [
    {"id": "tga.general", "label": "General TGA"},
    {"id": "tga.single_step_decomposition", "label": "Single-Step Decomposition"},
    {"id": "tga.multi_step_decomposition", "label": "Multi-Step Decomposition"},
]

_TEMPLATE_OPTIONS = [{"label": t["label"], "value": t["id"]} for t in _TGA_WORKFLOW_TEMPLATES]

_TGA_UNIT_MODES = [
    {"id": "auto", "label": "Auto"},
    {"id": "percent", "label": "Percent (%)"},
    {"id": "absolute_mass", "label": "Absolute Mass (mg)"},
]

_UNIT_MODE_OPTIONS = [{"label": m["label"], "value": m["id"]} for m in _TGA_UNIT_MODES]


def _metric_card(label: str, value: str) -> dbc.Card:
    return dbc.Card(
        dbc.CardBody([html.Small(label, className="text-muted text-uppercase"), html.H4(value, className="mb-0")])
    )


def _step_card(step: dict, idx: int) -> dbc.Card:
    onset = step.get("onset_temperature")
    midpoint = step.get("midpoint_temperature")
    endset = step.get("endset_temperature")
    mass_loss = step.get("mass_loss_percent")
    residual = step.get("residual_percent")
    mass_loss_mg = step.get("mass_loss_mg")
    return dbc.Card(
        dbc.CardBody(
            [
                html.Div(
                    [
                        html.I(className="bi bi-arrow-down-circle me-2", style={"color": "#059669", "fontSize": "1.1rem"}),
                        html.Strong(f"Step {idx + 1}", className="me-2"),
                        html.Span(
                            f"{mass_loss:.2f} %" if mass_loss is not None else "--",
                            className="badge",
                            style={"backgroundColor": "#059669", "color": "white", "fontSize": "0.75rem"},
                        ),
                    ],
                    className="mb-2",
                ),
                dbc.Row(
                    [
                        dbc.Col([html.Small("Onset", className="text-muted d-block"), html.Span(f"{onset:.1f} C" if onset is not None else "--")], md=3),
                        dbc.Col([html.Small("Midpoint", className="text-muted d-block"), html.Span(f"{midpoint:.1f} C" if midpoint is not None else "--")], md=3),
                        dbc.Col([html.Small("Endset", className="text-muted d-block"), html.Span(f"{endset:.1f} C" if endset is not None else "--")], md=3),
                        dbc.Col(
                            [
                                html.Small("Mass Loss", className="text-muted d-block"),
                                html.Span(f"{mass_loss:.2f} %" if mass_loss is not None else "--"),
                                html.Small(" Residual", className="text-muted ms-1"),
                                html.Span(f"{residual:.1f} %" if residual is not None else "--"),
                            ],
                            md=3,
                        ),
                    ],
                    className="g-2",
                ),
                *(
                    [html.P(f"Mass loss: {mass_loss_mg:.3f} mg", className="text-muted small mb-0 mt-1")]
                    if mass_loss_mg is not None else []
                ),
            ]
        ),
        className="mb-2",
    )


def _eligible_datasets(datasets: list[dict]) -> list[dict]:
    eligible_types = {"TGA", "UNKNOWN"}
    return [d for d in datasets if (d.get("data_type") or "").upper() in eligible_types]


def _dataset_options(datasets: list[dict]) -> list[dict]:
    return [
        {"label": f"{d.get('display_name', d.get('key', '?'))} ({d.get('data_type', '?')})", "value": d["key"]}
        for d in datasets
    ]


layout = html.Div(
    [
        dcc.Store(id="tga-refresh", data=0),
        dcc.Store(id="tga-latest-result-id"),
        page_header(
            "TGA Analysis",
            "Select a TGA-eligible dataset, choose unit mode and workflow template, and run thermogravimetric analysis.",
            badge="Analysis",
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.H5("Dataset Selection", className="mb-3"),
                                    html.Div(id="tga-dataset-selector-area"),
                                ]
                            ),
                            className="mb-4",
                        ),
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.H5("Unit Mode", className="mb-3"),
                                    dbc.Select(
                                        id="tga-unit-mode-select",
                                        options=_UNIT_MODE_OPTIONS,
                                        value="auto",
                                    ),
                                    html.P(
                                        "Auto: infer from signal range and unit metadata. "
                                        "Percent: signal is mass %. "
                                        "Absolute Mass: signal is mg, will be converted to %.",
                                        className="text-muted small mt-2",
                                        id="tga-unit-mode-description",
                                    ),
                                ]
                            ),
                            className="mb-4",
                        ),
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.H5("Workflow Template", className="mb-3"),
                                    dbc.Select(
                                        id="tga-template-select",
                                        options=_TEMPLATE_OPTIONS,
                                        value="tga.general",
                                    ),
                                    html.P(
                                        "General TGA: smoothing + DTG computation + step detection.",
                                        className="text-muted small mt-2",
                                        id="tga-template-description",
                                    ),
                                ]
                            ),
                            className="mb-4",
                        ),
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.H5("Execute", className="mb-3"),
                                    html.Div(id="tga-run-status"),
                                    dbc.Button(
                                        "Run TGA Analysis",
                                        id="tga-run-btn",
                                        color="primary",
                                        className="w-100",
                                        disabled=True,
                                    ),
                                ]
                            ),
                            className="mb-4",
                        ),
                    ],
                    md=4,
                ),
                dbc.Col(
                    [
                        dbc.Card(
                            dbc.CardBody(html.Div(id="tga-result-metrics")),
                            className="mb-4",
                        ),
                        dbc.Card(
                            dbc.CardBody(html.Div(id="tga-result-step-cards")),
                            className="mb-4",
                        ),
                        dbc.Card(
                            dbc.CardBody(html.Div(id="tga-result-figure")),
                            className="mb-4",
                        ),
                        dbc.Card(
                            dbc.CardBody(html.Div(id="tga-result-table")),
                            className="mb-4",
                        ),
                        dbc.Card(
                            dbc.CardBody(html.Div(id="tga-result-processing")),
                            className="mb-4",
                        ),
                    ],
                    md=8,
                ),
            ]
        ),
    ]
)

_TEMPLATE_DESCRIPTIONS = {
    "tga.general": "General TGA: Savitzky-Golay smoothing, DTG computation, step detection via DTG peak finding.",
    "tga.single_step_decomposition": "Single-Step Decomposition: Standard smoothing, DTG peak detection for a single mass-loss event.",
    "tga.multi_step_decomposition": "Multi-Step Decomposition: Wider smoothing window, lower mass-loss threshold for multiple overlapping steps.",
}

_UNIT_MODE_DESCRIPTIONS = {
    "auto": "Auto: infer from signal range and unit metadata. Best for most cases.",
    "percent": "Percent: signal is mass %. Use when data is already normalized to 100%.",
    "absolute_mass": "Absolute Mass: signal is in mg. Will be converted to % using initial mass reference.",
}


@callback(
    Output("tga-template-description", "children"),
    Input("tga-template-select", "value"),
)
def update_template_description(template_id):
    return _TEMPLATE_DESCRIPTIONS.get(template_id, "TGA analysis workflow.")


@callback(
    Output("tga-unit-mode-description", "children"),
    Input("tga-unit-mode-select", "value"),
)
def update_unit_mode_description(unit_mode):
    return _UNIT_MODE_DESCRIPTIONS.get(unit_mode, "TGA unit mode.")


@callback(
    Output("tga-dataset-selector-area", "children"),
    Output("tga-run-btn", "disabled"),
    Input("project-id", "data"),
    Input("tga-refresh", "data"),
)
def load_eligible_datasets(project_id, _refresh):
    if not project_id:
        return html.P("No workspace active. Create one first.", className="text-muted"), True

    from dash_app.api_client import workspace_datasets

    try:
        payload = workspace_datasets(project_id)
    except Exception as exc:
        return dbc.Alert(f"Error loading datasets: {exc}", color="danger"), True

    all_datasets = payload.get("datasets", [])
    eligible = _eligible_datasets(all_datasets)

    if not eligible:
        return html.P("No TGA-eligible datasets found. Import a TGA file first.", className="text-muted"), True

    options = _dataset_options(eligible)
    active = payload.get("active_dataset")
    default_value = None
    if active:
        eligible_keys = {d["key"] for d in eligible}
        if active in eligible_keys:
            default_value = active

    selector = dbc.Select(
        id="tga-dataset-select",
        options=options,
        value=default_value or (options[0]["value"] if options else None),
    )
    info = html.P(
        f"{len(eligible)} of {len(all_datasets)} datasets are TGA-eligible "
        f"(types: TGA, UNKNOWN).",
        className="text-muted small mt-2",
    )
    return html.Div([selector, info]), False


@callback(
    Output("tga-run-status", "children"),
    Output("tga-refresh", "data", allow_duplicate=True),
    Output("tga-latest-result-id", "data", allow_duplicate=True),
    Output("workspace-refresh", "data", allow_duplicate=True),
    Input("tga-run-btn", "n_clicks"),
    State("project-id", "data"),
    State("tga-dataset-select", "value"),
    State("tga-template-select", "value"),
    State("tga-unit-mode-select", "value"),
    State("tga-refresh", "data"),
    State("workspace-refresh", "data"),
    prevent_initial_call=True,
)
def run_tga_analysis(n_clicks, project_id, dataset_key, template_id, unit_mode, refresh_val, global_refresh):
    if not n_clicks or not project_id or not dataset_key:
        raise dash.exceptions.PreventUpdate

    from dash_app.api_client import analysis_run

    try:
        result = analysis_run(
            project_id=project_id,
            dataset_key=dataset_key,
            analysis_type="TGA",
            workflow_template_id=template_id,
            unit_mode=unit_mode if unit_mode and unit_mode != "auto" else None,
        )
    except Exception as exc:
        return dbc.Alert(f"Analysis failed: {exc}", color="danger"), dash.no_update, dash.no_update, dash.no_update

    status = result.get("execution_status", "unknown")
    result_id = result.get("result_id")
    failure = result.get("failure_reason")
    validation = result.get("validation", {})

    if status == "saved" and result_id:
        msg = dbc.Alert(
            f"Analysis saved (result: {result_id}). "
            f"Validation: {validation.get('status', 'N/A')}, "
            f"warnings: {validation.get('warning_count', 0)}.",
            color="success",
        )
        return msg, (refresh_val or 0) + 1, result_id, (global_refresh or 0) + 1

    if status == "blocked":
        return dbc.Alert(f"Analysis blocked: {failure}", color="warning"), (refresh_val or 0) + 1, dash.no_update, dash.no_update

    return dbc.Alert(f"Analysis failed: {failure or 'Unknown error'}", color="danger"), (refresh_val or 0) + 1, dash.no_update, dash.no_update


@callback(
    Output("tga-result-metrics", "children"),
    Output("tga-result-step-cards", "children"),
    Output("tga-result-figure", "children"),
    Output("tga-result-table", "children"),
    Output("tga-result-processing", "children"),
    Input("tga-latest-result-id", "data"),
    Input("tga-refresh", "data"),
    State("project-id", "data"),
)
def display_result(result_id, _refresh, project_id):
    empty_msg = html.P("Run an analysis to see results here.", className="text-muted")
    if not result_id or not project_id:
        return empty_msg, empty_msg, empty_msg, empty_msg, empty_msg

    from dash_app.api_client import workspace_result_detail, analysis_state_curves

    try:
        detail = workspace_result_detail(project_id, result_id)
    except Exception as exc:
        err = dbc.Alert(f"Error loading result: {exc}", color="danger")
        return err, empty_msg, empty_msg, empty_msg, empty_msg

    summary = detail.get("summary", {})
    result_meta = detail.get("result", {})
    processing = detail.get("processing", {})
    rows = detail.get("rows_preview", [])

    # --- Metrics row ---
    step_count = summary.get("step_count", 0)
    total_mass_loss = summary.get("total_mass_loss_percent")
    residue = summary.get("residue_percent")
    sample_name = summary.get("sample_name") or result_meta.get("dataset_key", "N/A")

    total_loss_str = f"{total_mass_loss:.2f} %" if total_mass_loss is not None else "N/A"
    residue_str = f"{residue:.1f} %" if residue is not None else "N/A"

    metrics = html.Div(
        [
            html.H5("Result Summary", className="mb-3"),
            dbc.Row(
                [
                    dbc.Col(_metric_card("Steps", str(step_count)), md=3),
                    dbc.Col(_metric_card("Total Mass Loss", total_loss_str), md=3),
                    dbc.Col(_metric_card("Residue", residue_str), md=3),
                    dbc.Col(_metric_card("Sample", str(sample_name)), md=3),
                ],
                className="g-3",
            ),
        ]
    )

    # --- Step cards ---
    step_cards = _build_step_cards(rows)

    # --- Figure with mass vs temperature and DTG overlay ---
    dataset_key = result_meta.get("dataset_key")
    figure_area = empty_msg
    if dataset_key:
        figure_area = _build_figure(project_id, dataset_key, summary, rows)

    # --- Step table ---
    table_area = _build_step_table(rows)

    # --- Processing info ---
    proc_view = _build_processing_section(processing)

    return metrics, step_cards, figure_area, table_area, proc_view


def _build_step_cards(rows: list) -> html.Div:
    if not rows:
        return html.Div(
            [html.H5("Detected Steps", className="mb-3"), html.P("No steps detected.", className="text-muted")]
        )

    cards = [html.H5("Detected Steps", className="mb-3")]
    for idx, row in enumerate(rows):
        cards.append(_step_card(row, idx))
    return html.Div(cards)


def _build_figure(project_id: str, dataset_key: str, summary: dict, step_rows: list) -> html.Div:
    from dash_app.api_client import analysis_state_curves

    try:
        curves = analysis_state_curves(project_id, "TGA", dataset_key)
    except Exception:
        curves = {}

    temperature = curves.get("temperature", [])
    raw_signal = curves.get("raw_signal", [])
    smoothed = curves.get("smoothed", [])
    dtg = curves.get("dtg", [])
    has_smoothed = curves.get("has_smoothed")
    has_dtg = curves.get("has_dtg")

    if not temperature:
        return html.P("No data available for plotting.", className="text-muted")

    sample_name = summary.get("sample_name", dataset_key)

    fig = go.Figure()

    # Raw mass signal (faint when smoothed overlay exists)
    raw_alpha = 0.35 if has_smoothed else 1.0
    raw_width = 1.0 if has_smoothed else 1.5
    fig.add_trace(
        go.Scatter(
            x=temperature,
            y=raw_signal,
            mode="lines",
            name="Raw Mass",
            line=dict(color="#94A3B8", width=raw_width),
            opacity=raw_alpha,
        )
    )

    # Smoothed TGA mass curve
    if smoothed and len(smoothed) == len(temperature):
        fig.add_trace(
            go.Scatter(
                x=temperature,
                y=smoothed,
                mode="lines",
                name="Smoothed Mass",
                line=dict(color="#0E7490", width=1.5),
            )
        )

    # DTG overlay on secondary y-axis
    if dtg and len(dtg) == len(temperature):
        fig.add_trace(
            go.Scatter(
                x=temperature,
                y=dtg,
                mode="lines",
                name="DTG (dm/dT)",
                line=dict(color="#DC2626", width=1.2),
                yaxis="y2",
            )
        )

    # Step onset/midpoint/endset markers
    for row in step_rows:
        onset = row.get("onset_temperature")
        midpoint = row.get("midpoint_temperature")
        endset = row.get("endset_temperature")
        mass_loss = row.get("mass_loss_percent")
        if midpoint is not None and temperature:
            idx = min(range(len(temperature)), key=lambda i: abs(temperature[i] - midpoint))
            fig.add_trace(
                go.Scatter(
                    x=[temperature[idx]],
                    y=[raw_signal[idx]],
                    mode="markers+text",
                    marker=dict(size=10, color="#059669", symbol="diamond"),
                    text=[f"{midpoint:.1f}"],
                    textposition="bottom center",
                    textfont=dict(size=9, color="#059669"),
                    name=f"Step mid {midpoint:.1f} C",
                    showlegend=False,
                )
            )

    # Step vertical lines for onset/endset
    for row in step_rows:
        onset = row.get("onset_temperature")
        endset = row.get("endset_temperature")
        if onset is not None:
            fig.add_vline(x=onset, line=dict(color="#F59E0B", width=1, dash="dot"), annotation_text=f"Onset {onset:.1f}")
        if endset is not None:
            fig.add_vline(x=endset, line=dict(color="#F59E0B", width=1, dash="dot"), annotation_text=f"Endset {endset:.1f}")

    fig.update_layout(
        title=f"TGA - {sample_name}",
        template="plotly_white",
        xaxis_title="Temperature (C)",
        yaxis_title="Mass (%)",
        yaxis2=dict(
            title="DTG (%/C)",
            overlaying="y",
            side="right",
            showgrid=False,
        ) if has_dtg else {},
        margin=dict(l=56, r=56, t=56, b=48),
        height=480,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return dcc.Graph(figure=fig, config={"displaylogo": False, "responsive": True})


def _build_step_table(rows: list) -> html.Div:
    if not rows:
        return html.Div([html.H5("Step Data Table", className="mb-3"), html.P("No step data.", className="text-muted")])

    columns = [
        "onset_temperature",
        "midpoint_temperature",
        "endset_temperature",
        "mass_loss_percent",
        "mass_loss_mg",
        "residual_percent",
    ]
    return html.Div(
        [
            html.H5("Step Data Table", className="mb-3"),
            dataset_table(rows, columns, table_id="tga-steps-table"),
        ]
    )


def _build_processing_section(processing: dict) -> html.Div:
    signal_pipeline = processing.get("signal_pipeline", {})
    analysis_steps = processing.get("analysis_steps", {})
    method_context = processing.get("method_context", {})
    unit_label = method_context.get("tga_unit_mode_resolved_label", method_context.get("tga_unit_mode_label", "N/A"))
    unit_inference = method_context.get("tga_unit_inference_basis", "N/A")
    return html.Div(
        [
            html.H5("Processing Details", className="mb-3"),
            html.P(f"Workflow: {processing.get('workflow_template_label', 'N/A')} (v{processing.get('workflow_template_version', '?')})"),
            html.P(f"Smoothing: {signal_pipeline.get('smoothing', {})}"),
            html.P(f"Step Detection: {analysis_steps.get('step_detection', {})}"),
            html.P(f"Unit Mode: {unit_label} (basis: {unit_inference})"),
            html.P(f"Calibration: {method_context.get('calibration_state', 'N/A')}", className="mb-0"),
        ]
    )
