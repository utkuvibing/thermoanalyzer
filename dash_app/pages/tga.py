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

from dash_app.components.analysis_page import (
    analysis_page_stores,
    dataset_selection_card,
    dataset_selector_block,
    eligible_datasets,
    empty_result_msg,
    execute_card,
    interpret_run_result,
    metrics_row,
    no_data_figure_msg,
    processing_details_section,
    result_placeholder_card,
    workflow_template_card,
)
from dash_app.components.chrome import page_header
from dash_app.components.data_preview import dataset_table

dash.register_page(__name__, path="/tga", title="TGA Analysis - MaterialScope")

_TGA_WORKFLOW_TEMPLATES = [
    {"id": "tga.general", "label": "General TGA"},
    {"id": "tga.single_step_decomposition", "label": "Single-Step Decomposition"},
    {"id": "tga.multi_step_decomposition", "label": "Multi-Step Decomposition"},
]

_TEMPLATE_OPTIONS = [{"label": t["label"], "value": t["id"]} for t in _TGA_WORKFLOW_TEMPLATES]

_TGA_ELIGIBLE_TYPES = {"TGA", "UNKNOWN"}

_TGA_UNIT_MODES = [
    {"id": "auto", "label": "Auto"},
    {"id": "percent", "label": "Percent (%)"},
    {"id": "absolute_mass", "label": "Absolute Mass (mg)"},
]

_UNIT_MODE_OPTIONS = [{"label": m["label"], "value": m["id"]} for m in _TGA_UNIT_MODES]


# ---------------------------------------------------------------------------
# TGA-specific cards
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# TGA-specific: unit mode card
# ---------------------------------------------------------------------------

def _unit_mode_card() -> dbc.Card:
    return dbc.Card(
        dbc.CardBody(
            [
                html.H5("Unit Mode", className="mb-3"),
                dbc.Select(id="tga-unit-mode-select", options=_UNIT_MODE_OPTIONS, value="auto"),
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
    )


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

layout = html.Div(
    analysis_page_stores("tga-refresh", "tga-latest-result-id")
    + [
        page_header(
            "TGA Analysis",
            "Select a TGA-eligible dataset, choose unit mode and workflow template, and run thermogravimetric analysis.",
            badge="Analysis",
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dataset_selection_card("tga-dataset-selector-area"),
                        _unit_mode_card(),
                        workflow_template_card(
                            "tga-template-select",
                            "tga-template-description",
                            _TEMPLATE_OPTIONS,
                            "tga.general",
                        ),
                        execute_card("tga-run-status", "tga-run-btn", "Run TGA Analysis"),
                    ],
                    md=4,
                ),
                dbc.Col(
                    [
                        result_placeholder_card("tga-result-metrics"),
                        result_placeholder_card("tga-result-step-cards"),
                        result_placeholder_card("tga-result-figure"),
                        result_placeholder_card("tga-result-table"),
                        result_placeholder_card("tga-result-processing"),
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
    return dataset_selector_block(
        selector_id="tga-dataset-select",
        empty_msg="Import a TGA file first.",
        eligible=eligible_datasets(all_datasets, _TGA_ELIGIBLE_TYPES),
        all_datasets=all_datasets,
        eligible_types=_TGA_ELIGIBLE_TYPES,
        active_dataset=payload.get("active_dataset"),
    )


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

    alert, saved, result_id = interpret_run_result(result)
    refresh = (refresh_val or 0) + 1
    if saved:
        return alert, refresh, result_id, (global_refresh or 0) + 1
    return alert, refresh, dash.no_update, dash.no_update


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
    empty_msg = empty_result_msg()
    if not result_id or not project_id:
        return empty_msg, empty_msg, empty_msg, empty_msg, empty_msg

    from dash_app.api_client import workspace_result_detail

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

    metrics = metrics_row([
        ("Steps", str(step_count)),
        ("Total Mass Loss", total_loss_str),
        ("Residue", residue_str),
        ("Sample", str(sample_name)),
    ])

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
    method_context = processing.get("method_context", {})
    unit_label = method_context.get("tga_unit_mode_resolved_label", method_context.get("tga_unit_mode_label", "N/A"))
    unit_inference = method_context.get("tga_unit_inference_basis", "N/A")
    proc_view = processing_details_section(
        processing,
        extra_lines=[
            html.P(f"Step Detection: {processing.get('analysis_steps', {}).get('step_detection', {})}"),
            html.P(f"Unit Mode: {unit_label} (basis: {unit_inference})"),
            html.P(f"Calibration: {method_context.get('calibration_state', 'N/A')}", className="mb-0"),
        ],
    )

    return metrics, step_cards, figure_area, table_area, proc_view


# ---------------------------------------------------------------------------
# TGA-specific builders
# ---------------------------------------------------------------------------

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
        return no_data_figure_msg()

    sample_name = summary.get("sample_name", dataset_key)

    fig = go.Figure()

    raw_alpha = 0.35 if has_smoothed else 1.0
    raw_width = 1.0 if has_smoothed else 1.5
    fig.add_trace(
        go.Scatter(
            x=temperature, y=raw_signal, mode="lines", name="Raw Mass",
            line=dict(color="#94A3B8", width=raw_width), opacity=raw_alpha,
        )
    )

    if smoothed and len(smoothed) == len(temperature):
        fig.add_trace(
            go.Scatter(x=temperature, y=smoothed, mode="lines", name="Smoothed Mass", line=dict(color="#0E7490", width=1.5))
        )

    if dtg and len(dtg) == len(temperature):
        fig.add_trace(
            go.Scatter(
                x=temperature, y=dtg, mode="lines", name="DTG (dm/dT)",
                line=dict(color="#DC2626", width=1.2), yaxis="y2",
            )
        )

    for row in step_rows:
        midpoint = row.get("midpoint_temperature")
        if midpoint is not None and temperature:
            idx = min(range(len(temperature)), key=lambda i: abs(temperature[i] - midpoint))
            fig.add_trace(
                go.Scatter(
                    x=[temperature[idx]], y=[raw_signal[idx]], mode="markers+text",
                    marker=dict(size=10, color="#059669", symbol="diamond"),
                    text=[f"{midpoint:.1f}"], textposition="bottom center",
                    textfont=dict(size=9, color="#059669"),
                    name=f"Step mid {midpoint:.1f} C", showlegend=False,
                )
            )

    for row in step_rows:
        onset = row.get("onset_temperature")
        endset = row.get("endset_temperature")
        if onset is not None:
            fig.add_vline(x=onset, line=dict(color="#F59E0B", width=1, dash="dot"), annotation_text=f"Onset {onset:.1f}")
        if endset is not None:
            fig.add_vline(x=endset, line=dict(color="#F59E0B", width=1, dash="dot"), annotation_text=f"Endset {endset:.1f}")

    fig.update_layout(
        title=f"TGA - {sample_name}", template="plotly_white",
        xaxis_title="Temperature (C)", yaxis_title="Mass (%)",
        yaxis2=dict(title="DTG (%/C)", overlaying="y", side="right", showgrid=False) if has_dtg else {},
        margin=dict(l=56, r=56, t=56, b=48), height=480,
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
