"""FTIR analysis page -- backend-driven first analysis slice.

Lets the user:
  1. Select an eligible FTIR dataset from the workspace
  2. Select an FTIR workflow template
  3. Run analysis through the backend /analysis/run endpoint
  4. View result summary cards, FTIR spectrum figure, detected peaks /
     feature table, library match results, and processing details
  5. Auto-refresh workspace/report/compare state after a successful run
"""

from __future__ import annotations

import math

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

dash.register_page(__name__, path="/ftir", title="FTIR Analysis - MaterialScope")

_FTIR_WORKFLOW_TEMPLATES = [
    {"id": "ftir.general", "label": "General FTIR"},
    {"id": "ftir.functional_groups", "label": "Functional Group Screening"},
]

_TEMPLATE_OPTIONS = [{"label": t["label"], "value": t["id"]} for t in _FTIR_WORKFLOW_TEMPLATES]

_FTIR_ELIGIBLE_TYPES = {"FTIR", "UNKNOWN"}

_CONFIDENCE_COLORS = {
    "high_confidence": "#059669",
    "moderate_confidence": "#D97706",
    "low_confidence": "#DC2626",
    "no_match": "#6B7280",
}

_FTIR_FIGURE_COLORS = {
    "query": "#0F172A",
    "smoothed": "#0E7490",
    "raw": "#94A3B8",
    "baseline": "#B45309",
    "grid": "rgba(148, 163, 184, 0.18)",
    "axis": "#475569",
    "panel": "#FCFDFE",
}


# ---------------------------------------------------------------------------
# FTIR-specific cards
# ---------------------------------------------------------------------------

def _match_card(row: dict, idx: int) -> dbc.Card:
    score = row.get("normalized_score", 0.0)
    band = str(row.get("confidence_band", "no_match")).lower()
    color = _CONFIDENCE_COLORS.get(band, "#6B7280")
    candidate_name = row.get("candidate_name", "Unknown")
    candidate_id = row.get("candidate_id", "")
    provider = row.get("library_provider", "")
    package = row.get("library_package", "")
    evidence = row.get("evidence", {})

    return dbc.Card(
        dbc.CardBody(
            [
                html.Div(
                    [
                        html.I(className="bi bi-search me-2", style={"color": color, "fontSize": "1.1rem"}),
                        html.Strong(f"Match {idx + 1}", className="me-2"),
                        html.Span(
                            band.replace("_", " ").title(),
                            className="badge",
                            style={"backgroundColor": color, "color": "white", "fontSize": "0.75rem"},
                        ),
                    ],
                    className="mb-2",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            [html.Small("Candidate", className="text-muted d-block"), html.Span(candidate_name)],
                            md=4,
                        ),
                        dbc.Col(
                            [html.Small("Score", className="text-muted d-block"), html.Span(f"{score:.4f}")],
                            md=2,
                        ),
                        dbc.Col(
                            [
                                html.Small("Peak Overlap", className="text-muted d-block"),
                                html.Span(
                                    f"{evidence.get('shared_peak_count', '--')}/{evidence.get('observed_peak_count', '--')}"
                                ),
                            ],
                            md=2,
                        ),
                        dbc.Col(
                            [
                                html.Small("Provider", className="text-muted d-block"),
                                html.Span(provider or "--"),
                            ],
                            md=4,
                        ),
                    ],
                    className="g-2",
                ),
                *(
                    [html.P(f"ID: {candidate_id}", className="text-muted small mb-0 mt-1")]
                    if candidate_id else []
                ),
            ]
        ),
        className="mb-2",
    )


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

layout = html.Div(
    analysis_page_stores("ftir-refresh", "ftir-latest-result-id")
    + [
        page_header(
            "FTIR Analysis",
            "Select an FTIR-eligible dataset, choose a workflow template, and run spectral analysis.",
            badge="Analysis",
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dataset_selection_card("ftir-dataset-selector-area"),
                        workflow_template_card(
                            "ftir-template-select",
                            "ftir-template-description",
                            _TEMPLATE_OPTIONS,
                            "ftir.general",
                        ),
                        execute_card("ftir-run-status", "ftir-run-btn", "Run FTIR Analysis"),
                    ],
                    md=4,
                ),
                dbc.Col(
                    [
                        result_placeholder_card("ftir-result-metrics"),
                        result_placeholder_card("ftir-result-match-cards"),
                        result_placeholder_card("ftir-result-figure"),
                        result_placeholder_card("ftir-result-table"),
                        result_placeholder_card("ftir-result-processing"),
                    ],
                    md=8,
                ),
            ]
        ),
    ]
)

_TEMPLATE_DESCRIPTIONS = {
    "ftir.general": "General FTIR: Moving-average smoothing, linear baseline, vector normalization, peak detection, cosine/Pearson similarity matching.",
    "ftir.functional_groups": "Functional Group Screening: Shorter smoothing window, more permissive peak detection, broader similarity matching for functional group identification.",
}


@callback(
    Output("ftir-template-description", "children"),
    Input("ftir-template-select", "value"),
)
def update_template_description(template_id):
    return _TEMPLATE_DESCRIPTIONS.get(template_id, "FTIR analysis workflow.")


@callback(
    Output("ftir-dataset-selector-area", "children"),
    Output("ftir-run-btn", "disabled"),
    Input("project-id", "data"),
    Input("ftir-refresh", "data"),
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
        selector_id="ftir-dataset-select",
        empty_msg="Import an FTIR file first.",
        eligible=eligible_datasets(all_datasets, _FTIR_ELIGIBLE_TYPES),
        all_datasets=all_datasets,
        eligible_types=_FTIR_ELIGIBLE_TYPES,
        active_dataset=payload.get("active_dataset"),
    )


@callback(
    Output("ftir-run-status", "children"),
    Output("ftir-refresh", "data", allow_duplicate=True),
    Output("ftir-latest-result-id", "data", allow_duplicate=True),
    Output("workspace-refresh", "data", allow_duplicate=True),
    Input("ftir-run-btn", "n_clicks"),
    State("project-id", "data"),
    State("ftir-dataset-select", "value"),
    State("ftir-template-select", "value"),
    State("ftir-refresh", "data"),
    State("workspace-refresh", "data"),
    prevent_initial_call=True,
)
def run_ftir_analysis(n_clicks, project_id, dataset_key, template_id, refresh_val, global_refresh):
    if not n_clicks or not project_id or not dataset_key:
        raise dash.exceptions.PreventUpdate

    from dash_app.api_client import analysis_run

    try:
        result = analysis_run(
            project_id=project_id,
            dataset_key=dataset_key,
            analysis_type="FTIR",
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
    Output("ftir-result-metrics", "children"),
    Output("ftir-result-match-cards", "children"),
    Output("ftir-result-figure", "children"),
    Output("ftir-result-table", "children"),
    Output("ftir-result-processing", "children"),
    Input("ftir-latest-result-id", "data"),
    Input("ftir-refresh", "data"),
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
    match_status = str(summary.get("match_status", "no_match")).replace("_", " ").title()
    candidate_count = summary.get("candidate_count", 0)
    top_score = summary.get("top_match_score", 0.0)
    sample_name = resolve_sample_name(summary, result_meta)

    top_score_str = f"{top_score:.4f}" if top_score else "N/A"
    top_match_name = summary.get("top_match_name")

    metrics = metrics_row([
        ("Peaks", str(peak_count)),
        ("Match Status", match_status),
        ("Top Score", top_score_str),
        ("Sample", sample_name),
    ])

    # --- Match cards ---
    match_cards = _build_match_cards(rows, top_match_name)

    # --- Figure ---
    dataset_key = result_meta.get("dataset_key")
    figure_area = empty_msg
    if dataset_key:
        figure_area = _build_figure(project_id, dataset_key, summary)

    # --- Match table ---
    table_area = _build_match_table(rows)

    # --- Processing info ---
    method_context = processing.get("method_context", {})
    proc_view = processing_details_section(
        processing,
        extra_lines=[
            html.P(f"Baseline: {processing.get('signal_pipeline', {}).get('baseline', {})}"),
            html.P(f"Normalization: {processing.get('signal_pipeline', {}).get('normalization', {})}"),
            html.P(f"Peak Detection: {processing.get('analysis_steps', {}).get('peak_detection', {})}"),
            html.P(f"Similarity Matching: {processing.get('analysis_steps', {}).get('similarity_matching', {})}"),
            html.P(
                f"Library: {method_context.get('library_access_mode', 'N/A')} "
                f"(source: {method_context.get('library_result_source', 'N/A')})",
                className="mb-0",
            ),
        ],
    )

    return metrics, match_cards, figure_area, table_area, proc_view


# ---------------------------------------------------------------------------
# FTIR-specific builders
# ---------------------------------------------------------------------------

def _build_match_cards(rows: list, top_match_name: str | None) -> html.Div:
    if not rows:
        return html.Div(
            [html.H5("Library Matches", className="mb-3"), html.P("No library matches found.", className="text-muted")]
        )

    cards = [html.H5("Library Matches", className="mb-3")]
    if top_match_name:
        cards.append(
            html.P(
                f"Top match: {top_match_name}",
                className="mb-3",
            )
        )
    for idx, row in enumerate(rows):
        cards.append(_match_card(row, idx))
    return html.Div(cards)


def _finite_series(values: list | None) -> list[float]:
    series: list[float] = []
    for value in values or []:
        if value is None:
            continue
        numeric = float(value)
        if math.isfinite(numeric):
            series.append(numeric)
    return series


def _y_axis_range(*series: list | None) -> list[float] | None:
    values: list[float] = []
    for entry in series:
        values.extend(_finite_series(entry))
    if not values:
        return None
    y_min = min(values)
    y_max = max(values)
    span = y_max - y_min
    padding = span * 0.08 if span > 0 else max(abs(y_max) * 0.12, 0.05)
    return [y_min - padding, y_max + padding]


def _build_figure(project_id: str, dataset_key: str, summary: dict) -> html.Div:
    from dash_app.api_client import analysis_state_curves

    try:
        curves = analysis_state_curves(project_id, "FTIR", dataset_key)
    except Exception:
        curves = {}

    # For FTIR, "temperature" holds wavenumber values
    wavenumber = curves.get("temperature", [])
    raw_signal = curves.get("raw_signal", [])
    smoothed = curves.get("smoothed", [])
    baseline = curves.get("baseline", [])
    corrected = curves.get("corrected", [])
    has_overlay = curves.get("has_smoothed") or curves.get("has_baseline") or curves.get("has_corrected")

    if not wavenumber:
        return no_data_figure_msg()

    sample_name = resolve_sample_name(summary, {}, fallback_display_name=dataset_key)
    has_corrected = bool(corrected and len(corrected) == len(wavenumber))
    has_smoothed = bool(smoothed and len(smoothed) == len(wavenumber))
    dominant_signal = corrected if has_corrected else smoothed if has_smoothed else raw_signal
    dominant_name = "Query Spectrum" if has_corrected else "Smoothed Spectrum" if has_smoothed else "Imported Spectrum"
    y_range = _y_axis_range(dominant_signal, raw_signal, smoothed, baseline)

    fig = go.Figure()

    if baseline and len(baseline) == len(wavenumber):
        fig.add_trace(
            go.Scatter(
                x=wavenumber,
                y=baseline,
                mode="lines",
                name="Estimated Baseline",
                line=dict(color=_FTIR_FIGURE_COLORS["baseline"], width=1.3, dash="dash"),
                opacity=0.7,
            )
        )

    if raw_signal and len(raw_signal) == len(wavenumber):
        fig.add_trace(
            go.Scatter(
                x=wavenumber,
                y=raw_signal,
                mode="lines",
                name="Imported Spectrum",
                line=dict(color=_FTIR_FIGURE_COLORS["raw"], width=1.6),
                opacity=0.45 if has_overlay else 0.95,
            )
        )

    if has_smoothed:
        fig.add_trace(
            go.Scatter(
                x=wavenumber,
                y=smoothed,
                mode="lines",
                name="Smoothed Spectrum",
                line=dict(color=_FTIR_FIGURE_COLORS["smoothed"], width=2.0),
                opacity=0.9 if has_corrected else 1.0,
            )
        )

    if has_corrected:
        fig.add_trace(
            go.Scatter(
                x=wavenumber,
                y=corrected,
                mode="lines",
                name="Query Spectrum",
                line=dict(color=_FTIR_FIGURE_COLORS["query"], width=3.2),
            )
        )

    # FTIR spectra conventionally displayed with wavenumber decreasing (left = high, right = low)
    fig.update_layout(
        title=(
            "FTIR Query Spectrum"
            f"<br><span style='font-size:0.82em;color:#64748B'>{sample_name}</span>"
        ),
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=_FTIR_FIGURE_COLORS["panel"],
        hovermode="x unified",
        xaxis_title="Wavenumber (cm\u207b\u00b9)",
        yaxis_title="Signal (a.u.)",
        xaxis=dict(
            autorange="reversed",
            showgrid=True,
            gridcolor=_FTIR_FIGURE_COLORS["grid"],
            linecolor=_FTIR_FIGURE_COLORS["axis"],
            tickfont=dict(size=12, color=_FTIR_FIGURE_COLORS["axis"]),
            title_font=dict(size=13, color=_FTIR_FIGURE_COLORS["axis"]),
            zeroline=False,
        ),
        yaxis=dict(
            range=y_range,
            showgrid=True,
            gridcolor=_FTIR_FIGURE_COLORS["grid"],
            linecolor=_FTIR_FIGURE_COLORS["axis"],
            tickfont=dict(size=12, color=_FTIR_FIGURE_COLORS["axis"]),
            title_font=dict(size=13, color=_FTIR_FIGURE_COLORS["axis"]),
            zeroline=False,
        ),
        margin=dict(l=64, r=28, t=82, b=56),
        height=520,
        title_font=dict(size=20, color=_FTIR_FIGURE_COLORS["query"]),
        title_x=0.01,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            bgcolor="rgba(255,255,255,0.84)",
            bordercolor="rgba(148, 163, 184, 0.35)",
            borderwidth=1,
            font=dict(size=12, color="#334155"),
        ),
        hoverlabel=dict(bgcolor="rgba(255,255,255,0.96)", font=dict(color="#0F172A")),
    )
    if fig.data and dominant_name != "Query Spectrum":
        fig.data[-1].name = dominant_name
    return dcc.Graph(figure=fig, config={"displaylogo": False, "responsive": True})


def _build_match_table(rows: list) -> html.Div:
    if not rows:
        return html.Div(
            [html.H5("Match Data Table", className="mb-3"), html.P("No match data.", className="text-muted")]
        )

    columns = [
        "rank",
        "candidate_id",
        "candidate_name",
        "normalized_score",
        "confidence_band",
        "library_provider",
        "library_package",
    ]
    return html.Div(
        [
            html.H5("Match Data Table", className="mb-3"),
            dataset_table(rows, columns, table_id="ftir-matches-table"),
        ]
    )
