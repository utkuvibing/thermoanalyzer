"""DSC analysis page -- backend-driven first analysis slice.

Lets the user:
  1. Select an eligible DSC dataset from the workspace
  2. Select a DSC workflow template
  3. Run analysis through the backend /analysis/run endpoint
  4. View execution status, result summary, and DSC figure/preview
  5. Enriched display: Tg metric cards, smoothed/baseline/corrected overlay,
     labelled peak cards, auto-refresh of Project/Compare/Report pages
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

dash.register_page(__name__, path="/dsc", title="DSC Analysis - MaterialScope")

_DSC_WORKFLOW_TEMPLATES = [
    {"id": "dsc.general", "label": "General DSC"},
    {"id": "dsc.polymer_tg", "label": "Polymer Tg"},
    {"id": "dsc.polymer_melting_crystallization", "label": "Polymer Melting/Crystallization"},
]

_TEMPLATE_OPTIONS = [{"label": t["label"], "value": t["id"]} for t in _DSC_WORKFLOW_TEMPLATES]

_DSC_ELIGIBLE_TYPES = {"DSC", "DTA", "UNKNOWN"}

_PEAK_TYPE_COLORS = {
    "endotherm": "#0E7490",
    "exotherm": "#DC2626",
    "step": "#7C3AED",
}
_PEAK_TYPE_ICONS = {
    "endotherm": "bi-arrow-down-circle",
    "exotherm": "bi-arrow-up-circle",
    "step": "bi-arrow-right-circle",
}


# ---------------------------------------------------------------------------
# DSC-specific cards
# ---------------------------------------------------------------------------

def _tg_card(midpoint: float, onset: float, endset: float, delta_cp: float, idx: int = 0) -> dbc.Card:
    return dbc.Card(
        dbc.CardBody(
            [
                html.H6(f"Glass Transition {idx + 1}", className="mb-2"),
                dbc.Row(
                    [
                        dbc.Col([html.Small("Midpoint", className="text-muted"), html.H5(f"{midpoint:.1f} C", className="mb-0 text-danger")], md=3),
                        dbc.Col([html.Small("Onset", className="text-muted"), html.H5(f"{onset:.1f} C", className="mb-0 text-warning")], md=3),
                        dbc.Col([html.Small("Endset", className="text-muted"), html.H5(f"{endset:.1f} C", className="mb-0 text-warning")], md=3),
                        dbc.Col([html.Small("dCp", className="text-muted"), html.H5(f"{delta_cp:.4f}", className="mb-0")], md=3),
                    ],
                    className="g-2",
                ),
            ]
        ),
        className="mb-2",
    )


def _peak_card(row: dict, idx: int) -> dbc.Card:
    peak_type = str(row.get("peak_type", "unknown")).lower()
    color = _PEAK_TYPE_COLORS.get(peak_type, "#6B7280")
    icon = _PEAK_TYPE_ICONS.get(peak_type, "bi-circle")
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
                            peak_type.title(),
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
    analysis_page_stores("dsc-refresh", "dsc-latest-result-id")
    + [
        page_header(
            "DSC Analysis",
            "Select a DSC-eligible dataset, choose a workflow template, and run thermal analysis.",
            badge="Analysis",
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dataset_selection_card("dsc-dataset-selector-area"),
                        workflow_template_card(
                            "dsc-template-select",
                            "dsc-template-description",
                            _TEMPLATE_OPTIONS,
                            "dsc.general",
                        ),
                        execute_card("dsc-run-status", "dsc-run-btn", "Run DSC Analysis"),
                    ],
                    md=4,
                ),
                dbc.Col(
                    [
                        result_placeholder_card("dsc-result-metrics"),
                        result_placeholder_card("dsc-result-tg-cards"),
                        result_placeholder_card("dsc-result-figure"),
                        result_placeholder_card("dsc-result-table"),
                        result_placeholder_card("dsc-result-processing"),
                    ],
                    md=8,
                ),
            ]
        ),
    ]
)


_TEMPLATE_DESCRIPTIONS = {
    "dsc.general": "General DSC: Savitzky-Golay smoothing, ASLS baseline, peak detection (both directions), automatic Tg detection.",
    "dsc.polymer_tg": "Polymer Tg: Wider smoothing window for clearer glass transition, ASLS baseline, automatic Tg detection.",
    "dsc.polymer_melting_crystallization": "Polymer Melting/Crystallization: Standard smoothing, ASLS baseline, peak detection for melting and crystallization events.",
}


@callback(
    Output("dsc-template-description", "children"),
    Input("dsc-template-select", "value"),
)
def update_template_description(template_id):
    return _TEMPLATE_DESCRIPTIONS.get(template_id, "DSC analysis workflow.")


@callback(
    Output("dsc-dataset-selector-area", "children"),
    Output("dsc-run-btn", "disabled"),
    Input("project-id", "data"),
    Input("dsc-refresh", "data"),
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
        selector_id="dsc-dataset-select",
        empty_msg="Import a DSC file first.",
        eligible=eligible_datasets(all_datasets, _DSC_ELIGIBLE_TYPES),
        all_datasets=all_datasets,
        eligible_types=_DSC_ELIGIBLE_TYPES,
        active_dataset=payload.get("active_dataset"),
    )


@callback(
    Output("dsc-run-status", "children"),
    Output("dsc-refresh", "data", allow_duplicate=True),
    Output("dsc-latest-result-id", "data", allow_duplicate=True),
    Output("workspace-refresh", "data", allow_duplicate=True),
    Input("dsc-run-btn", "n_clicks"),
    State("project-id", "data"),
    State("dsc-dataset-select", "value"),
    State("dsc-template-select", "value"),
    State("dsc-refresh", "data"),
    State("workspace-refresh", "data"),
    prevent_initial_call=True,
)
def run_dsc_analysis(n_clicks, project_id, dataset_key, template_id, refresh_val, global_refresh):
    if not n_clicks or not project_id or not dataset_key:
        raise dash.exceptions.PreventUpdate

    from dash_app.api_client import analysis_run

    try:
        result = analysis_run(
            project_id=project_id,
            dataset_key=dataset_key,
            analysis_type="DSC",
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
    Output("dsc-result-metrics", "children"),
    Output("dsc-result-tg-cards", "children"),
    Output("dsc-result-figure", "children"),
    Output("dsc-result-table", "children"),
    Output("dsc-result-processing", "children"),
    Input("dsc-latest-result-id", "data"),
    Input("dsc-refresh", "data"),
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
    tg_count = summary.get("glass_transition_count", 0)
    sample_name = summary.get("sample_name") or result_meta.get("dataset_key", "N/A")
    metrics = metrics_row([
        ("Peaks", str(peak_count)),
        ("Glass Transitions", str(tg_count)),
        ("Template", str(processing.get("workflow_template_label", "N/A"))),
        ("Sample", str(sample_name)),
    ])

    # --- Tg metric cards ---
    tg_cards = _build_tg_cards(summary)

    # --- Figure with smoothed/baseline/corrected overlay ---
    dataset_key = result_meta.get("dataset_key")
    figure_area = empty_msg
    if dataset_key:
        figure_area = _build_figure(project_id, dataset_key, summary, rows)

    # --- Peak cards + table ---
    table_area = _build_peak_section(rows)

    # --- Processing info ---
    proc_view = processing_details_section(
        processing,
        extra_lines=[
            html.P(f"Baseline: {processing.get('signal_pipeline', {}).get('baseline', {})}"),
            html.P(f"Peak Detection: {processing.get('analysis_steps', {}).get('peak_detection', {})}"),
            html.P(f"Tg Detection: {processing.get('analysis_steps', {}).get('glass_transition', {})}"),
            html.P(f"Sign Convention: {processing.get('method_context', {}).get('sign_convention_label', 'N/A')}", className="mb-0"),
        ],
    )

    return metrics, tg_cards, figure_area, table_area, proc_view


# ---------------------------------------------------------------------------
# DSC-specific builders
# ---------------------------------------------------------------------------

def _build_tg_cards(summary: dict) -> html.Div:
    tg_mid = summary.get("tg_midpoint")
    tg_onset = summary.get("tg_onset")
    tg_endset = summary.get("tg_endset")
    delta_cp = summary.get("delta_cp")
    tg_count = summary.get("glass_transition_count", 0)

    if tg_count == 0 or tg_mid is None:
        return html.Div(
            [html.H5("Glass Transitions", className="mb-3"), html.P("Not detected.", className="text-muted")]
        )

    cards = [html.H5("Glass Transitions", className="mb-3")]
    cards.append(_tg_card(tg_mid, tg_onset, tg_endset, delta_cp, idx=0))
    if tg_count > 1:
        cards.append(html.P(f"... and {tg_count - 1} more transition(s).", className="text-muted small"))
    return html.Div(cards)


def _build_figure(project_id: str, dataset_key: str, summary: dict, peak_rows: list) -> html.Div:
    from dash_app.api_client import analysis_state_curves

    try:
        curves = analysis_state_curves(project_id, "DSC", dataset_key)
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

    tg_midpoint = summary.get("tg_midpoint")
    tg_onset = summary.get("tg_onset")
    tg_endset = summary.get("tg_endset")
    tg_count = summary.get("glass_transition_count", 0)
    sample_name = summary.get("sample_name", dataset_key)

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

    for row in peak_rows:
        pt = row.get("peak_temperature")
        if pt is None:
            continue
        peak_type = str(row.get("peak_type", "unknown")).lower()
        color = _PEAK_TYPE_COLORS.get(peak_type, "#B45309")
        idx = min(range(len(temperature)), key=lambda i: abs(temperature[i] - pt)) if temperature else None
        if idx is not None:
            fig.add_trace(
                go.Scatter(
                    x=[temperature[idx]], y=[raw_signal[idx]], mode="markers+text",
                    marker=dict(size=10, color=color, symbol="diamond"),
                    text=[f"{pt:.1f}"], textposition="bottom center",
                    textfont=dict(size=9, color=color),
                    name=f"{peak_type.title()} {pt:.1f} C", showlegend=False,
                )
            )

    if tg_count > 0 and tg_midpoint is not None:
        fig.add_vline(x=tg_midpoint, line=dict(color="#EF4444", width=2, dash="dash"), annotation_text=f"Tg mid {tg_midpoint:.1f}")
        if tg_onset is not None:
            fig.add_vline(x=tg_onset, line=dict(color="#F59E0B", width=1, dash="dot"), annotation_text=f"Onset {tg_onset:.1f}")
        if tg_endset is not None:
            fig.add_vline(x=tg_endset, line=dict(color="#F59E0B", width=1, dash="dot"), annotation_text=f"Endset {tg_endset:.1f}")

    fig.update_layout(
        title=f"DSC - {sample_name}", template="plotly_white",
        xaxis_title="Temperature (C)", yaxis_title="Heat Flow (a.u.)",
        margin=dict(l=56, r=24, t=56, b=48), height=480,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return dcc.Graph(figure=fig, config={"displaylogo": False, "responsive": True})


def _build_peak_section(rows: list) -> html.Div:
    if not rows:
        return html.Div([html.H5("Detected Peaks", className="mb-3"), html.P("No peaks detected.", className="text-muted")])

    cards = [html.H5("Detected Peaks", className="mb-3")]
    for idx, row in enumerate(rows):
        cards.append(_peak_card(row, idx))

    cards.append(html.Hr(className="my-3"))
    cards.append(dataset_table(
        rows,
        ["peak_type", "peak_temperature", "onset_temperature", "endset_temperature", "area", "fwhm", "height"],
        table_id="dsc-peaks-table",
    ))
    return html.Div(cards)
