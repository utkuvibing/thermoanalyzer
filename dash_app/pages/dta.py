"""DTA analysis page -- backend-driven first analysis slice.

Lets the user:
  1. Select an eligible DTA dataset from the workspace
  2. Select a DTA workflow template
  3. Run analysis through the backend /analysis/run endpoint
  4. View result summary cards, DTA curve figure (raw / smoothed /
     baseline / corrected), detected peak / event cards and table,
     and processing details
  5. Auto-refresh workspace/report/compare state after a successful run
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
    resolve_sample_name,
    result_placeholder_card,
    workflow_template_card,
)
from dash_app.components.chrome import page_header
from dash_app.components.data_preview import dataset_table

dash.register_page(__name__, path="/dta", title="DTA Analysis - MaterialScope")

_DTA_WORKFLOW_TEMPLATES = [
    {"id": "dta.general", "label": "General DTA"},
    {"id": "dta.thermal_events", "label": "Thermal Event Screening"},
]

_TEMPLATE_OPTIONS = [{"label": t["label"], "value": t["id"]} for t in _DTA_WORKFLOW_TEMPLATES]

_DTA_ELIGIBLE_TYPES = {"DTA", "UNKNOWN"}

_DIRECTION_COLORS = {
    "exo": "#DC2626",
    "endo": "#0E7490",
    "exotherm": "#DC2626",
    "endotherm": "#0E7490",
}
_DIRECTION_ICONS = {
    "exo": "bi-arrow-up-circle",
    "endo": "bi-arrow-down-circle",
    "exotherm": "bi-arrow-up-circle",
    "endotherm": "bi-arrow-down-circle",
}

_ANNOTATION_MIN_SEP = 15.0  # degC -- suppress label when peaks are too close


# ---------------------------------------------------------------------------
# DTA-specific cards
# ---------------------------------------------------------------------------

def _peak_card(row: dict, idx: int) -> dbc.Card:
    direction = str(row.get("direction", row.get("peak_type", "unknown")).lower())
    color = _DIRECTION_COLORS.get(direction, "#6B7280")
    icon = _DIRECTION_ICONS.get(direction, "bi-circle")
    direction_label = direction.replace("exotherm", "exo").replace("endotherm", "endo").title()

    pt = row.get("peak_temperature")
    onset = row.get("onset_temperature")
    endset = row.get("endset_temperature")
    area = row.get("area")
    fwhm = row.get("fwhm")
    height = row.get("height")

    return dbc.Card(
        dbc.CardBody(
            [
                html.Div(
                    [
                        html.I(className=f"bi {icon} me-2", style={"color": color, "fontSize": "1.1rem"}),
                        html.Strong(f"Peak {idx + 1}", className="me-2"),
                        html.Span(
                            direction_label,
                            className="badge",
                            style={"backgroundColor": color, "color": "white", "fontSize": "0.75rem"},
                        ),
                        html.Span(f"  {pt:.1f} C" if pt is not None else "  --", className="ms-2"),
                    ],
                    className="mb-2",
                ),
                dbc.Row(
                    [
                        dbc.Col([html.Small("Onset", className="text-muted d-block"), html.Span(f"{onset:.1f}" if onset is not None else "--")], md=3),
                        dbc.Col([html.Small("Endset", className="text-muted d-block"), html.Span(f"{endset:.1f}" if endset is not None else "--")], md=3),
                        dbc.Col([html.Small("Area", className="text-muted d-block"), html.Span(f"{area:.3f}" if area is not None else "--")], md=3),
                        dbc.Col(
                            [
                                html.Small("FWHM", className="text-muted d-block"),
                                html.Span(f"{fwhm:.1f}" if fwhm is not None else "--"),
                                html.Small(" Height", className="text-muted ms-2"),
                                html.Span(f"{height:.3f}" if height is not None else "--"),
                            ],
                            md=3,
                        ),
                    ],
                    className="g-2",
                ),
            ]
        ),
        className="mb-2",
    )


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

layout = html.Div(
    analysis_page_stores("dta-refresh", "dta-latest-result-id")
    + [
        page_header(
            "DTA Analysis",
            "Select a DTA-eligible dataset, choose a workflow template, and run differential thermal analysis.",
            badge="Analysis",
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dataset_selection_card("dta-dataset-selector-area"),
                        workflow_template_card(
                            "dta-template-select",
                            "dta-template-description",
                            _TEMPLATE_OPTIONS,
                            "dta.general",
                        ),
                        execute_card("dta-run-status", "dta-run-btn", "Run DTA Analysis"),
                    ],
                    md=4,
                ),
                dbc.Col(
                    [
                        result_placeholder_card("dta-result-metrics"),
                        result_placeholder_card("dta-result-peak-cards"),
                        result_placeholder_card("dta-result-figure"),
                        result_placeholder_card("dta-result-table"),
                        result_placeholder_card("dta-result-processing"),
                    ],
                    md=8,
                ),
            ]
        ),
    ]
)

_TEMPLATE_DESCRIPTIONS = {
    "dta.general": "General DTA: Savitzky-Golay smoothing, ASLS baseline, bidirectional peak detection (exothermic + endothermic).",
    "dta.thermal_events": "Thermal Event Screening: Wider smoothing window, more permissive peak detection for complex thermal histories.",
}


@callback(
    Output("dta-template-description", "children"),
    Input("dta-template-select", "value"),
)
def update_template_description(template_id):
    return _TEMPLATE_DESCRIPTIONS.get(template_id, "DTA analysis workflow.")


@callback(
    Output("dta-dataset-selector-area", "children"),
    Output("dta-run-btn", "disabled"),
    Input("project-id", "data"),
    Input("dta-refresh", "data"),
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
        selector_id="dta-dataset-select",
        empty_msg="Import a DTA file first.",
        eligible=eligible_datasets(all_datasets, _DTA_ELIGIBLE_TYPES),
        all_datasets=all_datasets,
        eligible_types=_DTA_ELIGIBLE_TYPES,
        active_dataset=payload.get("active_dataset"),
    )


@callback(
    Output("dta-run-status", "children"),
    Output("dta-refresh", "data", allow_duplicate=True),
    Output("dta-latest-result-id", "data", allow_duplicate=True),
    Output("workspace-refresh", "data", allow_duplicate=True),
    Input("dta-run-btn", "n_clicks"),
    State("project-id", "data"),
    State("dta-dataset-select", "value"),
    State("dta-template-select", "value"),
    State("dta-refresh", "data"),
    State("workspace-refresh", "data"),
    prevent_initial_call=True,
)
def run_dta_analysis(n_clicks, project_id, dataset_key, template_id, refresh_val, global_refresh):
    if not n_clicks or not project_id or not dataset_key:
        raise dash.exceptions.PreventUpdate

    from dash_app.api_client import analysis_run

    try:
        result = analysis_run(
            project_id=project_id,
            dataset_key=dataset_key,
            analysis_type="DTA",
            workflow_template_id=template_id,
        )
    except Exception as exc:
        return dbc.Alert(f"Analysis failed: {exc}", color="danger"), dash.no_update, dash.no_update, dash.no_update

    alert, saved, result_id = interpret_run_result(result)
    refresh = (refresh_val or 0) + 1
    if saved:
        return alert, refresh, result_id, (global_refresh or 0) + 1
    return alert, refresh, dash.no_update, dash.no_update


@callback(
    Output("dta-result-metrics", "children"),
    Output("dta-result-peak-cards", "children"),
    Output("dta-result-figure", "children"),
    Output("dta-result-table", "children"),
    Output("dta-result-processing", "children"),
    Input("dta-latest-result-id", "data"),
    Input("dta-refresh", "data"),
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
    peak_count = summary.get("peak_count", 0)
    exo_count = summary.get("exotherm_count", summary.get("exo_count", 0))
    endo_count = summary.get("endotherm_count", summary.get("endo_count", 0))
    sample_name = resolve_sample_name(summary, result_meta)

    metrics = metrics_row([
        ("Peaks", str(peak_count)),
        ("Exothermic", str(exo_count)),
        ("Endothermic", str(endo_count)),
        ("Sample", sample_name),
    ])

    # --- Peak cards ---
    peak_cards = _build_peak_cards(rows)

    # --- Figure with smoothed/baseline/corrected overlay ---
    dataset_key = result_meta.get("dataset_key")
    figure_area = empty_msg
    if dataset_key:
        figure_area = _build_figure(project_id, dataset_key, summary, rows)

    # --- Peak table ---
    table_area = _build_peak_table(rows)

    # --- Processing info ---
    method_context = processing.get("method_context", {})
    proc_view = processing_details_section(
        processing,
        extra_lines=[
            html.P(f"Baseline: {processing.get('signal_pipeline', {}).get('baseline', {})}"),
            html.P(f"Peak Detection: {processing.get('analysis_steps', {}).get('peak_detection', {})}"),
            html.P(f"Sign Convention: {method_context.get('sign_convention_label', 'N/A')}", className="mb-0"),
        ],
    )

    return metrics, peak_cards, figure_area, table_area, proc_view


# ---------------------------------------------------------------------------
# DTA-specific builders
# ---------------------------------------------------------------------------

def _build_peak_cards(rows: list) -> html.Div:
    if not rows:
        return html.Div(
            [html.H5("Detected Events", className="mb-3"), html.P("No thermal events detected.", className="text-muted")]
        )

    cards = [html.H5("Detected Events", className="mb-3")]
    for idx, row in enumerate(rows):
        cards.append(_peak_card(row, idx))
    return html.Div(cards)


def _build_figure(project_id: str, dataset_key: str, summary: dict, peak_rows: list) -> html.Div:
    from dash_app.api_client import analysis_state_curves

    try:
        curves = analysis_state_curves(project_id, "DTA", dataset_key)
    except Exception:
        curves = {}

    temperature = curves.get("temperature", [])
    raw_signal = curves.get("raw_signal", [])
    smoothed = curves.get("smoothed", [])
    baseline = curves.get("baseline", [])
    corrected = curves.get("corrected", [])
    has_overlay = curves.get("has_smoothed") or curves.get("has_baseline") or curves.get("has_corrected")

    if not temperature:
        return no_data_figure_msg()

    sample_name = resolve_sample_name(summary, {}, fallback_display_name=dataset_key)

    fig = go.Figure()

    raw_alpha = 0.35 if has_overlay else 1.0
    raw_width = 1.0 if has_overlay else 1.5
    fig.add_trace(
        go.Scatter(
            x=temperature, y=raw_signal, mode="lines", name="Raw Signal",
            line=dict(color="#94A3B8", width=raw_width), opacity=raw_alpha,
        )
    )

    if smoothed and len(smoothed) == len(temperature):
        fig.add_trace(
            go.Scatter(x=temperature, y=smoothed, mode="lines", name="Smoothed", line=dict(color="#0E7490", width=1.5))
        )

    if baseline and len(baseline) == len(temperature):
        fig.add_trace(
            go.Scatter(x=temperature, y=baseline, mode="lines", name="Baseline", line=dict(color="#6B7280", width=1, dash="dash"))
        )

    if corrected and len(corrected) == len(temperature):
        fig.add_trace(
            go.Scatter(x=temperature, y=corrected, mode="lines", name="Corrected", line=dict(color="#059669", width=1.5))
        )

    # Peak markers with direction-colored diamonds
    annotated_temps: list[float] = []

    for row in peak_rows:
        pt = row.get("peak_temperature")
        if pt is None:
            continue
        direction = str(row.get("direction", row.get("peak_type", "unknown")).lower())
        color = _DIRECTION_COLORS.get(direction, "#B45309")
        idx = min(range(len(temperature)), key=lambda i: abs(temperature[i] - pt)) if temperature else None
        if idx is not None:
            too_close = any(abs(pt - t) < _ANNOTATION_MIN_SEP for t in annotated_temps)
            text_str = f"{pt:.1f}" if not too_close else ""
            fig.add_trace(
                go.Scatter(
                    x=[temperature[idx]], y=[raw_signal[idx]], mode="markers+text",
                    marker=dict(size=10, color=color, symbol="diamond"),
                    text=[text_str], textposition="bottom center",
                    textfont=dict(size=9, color=color),
                    name=f"{direction.title()} {pt:.1f} C", showlegend=False,
                )
            )
            if text_str:
                annotated_temps.append(pt)

    fig.update_layout(
        title=f"DTA - {sample_name}", template="plotly_white",
        xaxis_title="Temperature (C)", yaxis_title="Delta-T (a.u.)",
        margin=dict(l=56, r=24, t=56, b=48), height=480,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return dcc.Graph(figure=fig, config={"displaylogo": False, "responsive": True})


def _build_peak_table(rows: list) -> html.Div:
    if not rows:
        return html.Div(
            [html.H5("Event Data Table", className="mb-3"), html.P("No event data.", className="text-muted")]
        )

    columns = [
        "direction",
        "peak_temperature",
        "onset_temperature",
        "endset_temperature",
        "area",
        "fwhm",
        "height",
    ]
    return html.Div(
        [
            html.H5("Event Data Table", className="mb-3"),
            dataset_table(rows, columns, table_id="dta-peaks-table"),
        ]
    )
