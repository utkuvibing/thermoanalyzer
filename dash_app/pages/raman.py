"""RAMAN analysis page -- backend-driven stable first slice."""

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

dash.register_page(__name__, path="/raman", title="RAMAN Analysis - MaterialScope")

_RAMAN_WORKFLOW_TEMPLATES = [
    {"id": "raman.general", "label": "General Raman"},
    {"id": "raman.polymorph_screening", "label": "Polymorph Screening"},
]
_TEMPLATE_OPTIONS = [{"label": t["label"], "value": t["id"]} for t in _RAMAN_WORKFLOW_TEMPLATES]
_RAMAN_ELIGIBLE_TYPES = {"RAMAN", "UNKNOWN"}

_CONFIDENCE_COLORS = {
    "high_confidence": "#059669",
    "moderate_confidence": "#D97706",
    "low_confidence": "#DC2626",
    "no_match": "#6B7280",
}

_RAMAN_FIGURE_COLORS = {
    "query": "#0F172A",
    "smoothed": "#0369A1",
    "raw": "#94A3B8",
    "baseline": "#7C3AED",
    "grid": "rgba(148, 163, 184, 0.18)",
    "axis": "#475569",
    "panel": "#FCFDFE",
}


def _match_card(row: dict, idx: int) -> dbc.Card:
    score = row.get("normalized_score", 0.0)
    band = str(row.get("confidence_band", "no_match")).lower()
    color = _CONFIDENCE_COLORS.get(band, "#6B7280")
    candidate_name = row.get("candidate_name", "Unknown")
    provider = row.get("library_provider", "")
    evidence = row.get("evidence", {})

    return dbc.Card(
        dbc.CardBody(
            [
                html.Div(
                    [
                        html.I(className="bi bi-soundwave me-2", style={"color": color, "fontSize": "1.1rem"}),
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
                            md=5,
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
                            [html.Small("Provider", className="text-muted d-block"), html.Span(provider or "--")],
                            md=3,
                        ),
                    ],
                    className="g-2",
                ),
            ]
        ),
        className="mb-2",
    )


layout = html.Div(
    analysis_page_stores("raman-refresh", "raman-latest-result-id")
    + [
        page_header(
            "RAMAN Analysis",
            "Select a RAMAN-eligible dataset, choose a workflow template, and run spectral matching.",
            badge="Analysis",
        ),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dataset_selection_card("raman-dataset-selector-area"),
                        workflow_template_card(
                            "raman-template-select",
                            "raman-template-description",
                            _TEMPLATE_OPTIONS,
                            "raman.general",
                        ),
                        execute_card("raman-run-status", "raman-run-btn", "Run RAMAN Analysis"),
                    ],
                    md=4,
                ),
                dbc.Col(
                    [
                        result_placeholder_card("raman-result-metrics"),
                        result_placeholder_card("raman-result-figure"),
                        result_placeholder_card("raman-result-match-cards"),
                        result_placeholder_card("raman-result-table"),
                        result_placeholder_card("raman-result-processing"),
                    ],
                    md=8,
                ),
            ]
        ),
    ]
)

_TEMPLATE_DESCRIPTIONS = {
    "raman.general": "General Raman: Moving-average smoothing, linear baseline, SNV normalization, cosine similarity matching.",
    "raman.polymorph_screening": "Polymorph Screening: Shorter smoothing window, denser peak extraction, Pearson-focused matching.",
}


@callback(
    Output("raman-template-description", "children"),
    Input("raman-template-select", "value"),
)
def update_template_description(template_id):
    return _TEMPLATE_DESCRIPTIONS.get(template_id, "RAMAN analysis workflow.")


@callback(
    Output("raman-dataset-selector-area", "children"),
    Output("raman-run-btn", "disabled"),
    Input("project-id", "data"),
    Input("raman-refresh", "data"),
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
        selector_id="raman-dataset-select",
        empty_msg="Import a RAMAN file first.",
        eligible=eligible_datasets(all_datasets, _RAMAN_ELIGIBLE_TYPES),
        all_datasets=all_datasets,
        eligible_types=_RAMAN_ELIGIBLE_TYPES,
        active_dataset=payload.get("active_dataset"),
    )


@callback(
    Output("raman-run-status", "children"),
    Output("raman-refresh", "data", allow_duplicate=True),
    Output("raman-latest-result-id", "data", allow_duplicate=True),
    Output("workspace-refresh", "data", allow_duplicate=True),
    Input("raman-run-btn", "n_clicks"),
    State("project-id", "data"),
    State("raman-dataset-select", "value"),
    State("raman-template-select", "value"),
    State("raman-refresh", "data"),
    State("workspace-refresh", "data"),
    prevent_initial_call=True,
)
def run_raman_analysis(n_clicks, project_id, dataset_key, template_id, refresh_val, global_refresh):
    if not n_clicks or not project_id or not dataset_key:
        raise dash.exceptions.PreventUpdate

    from dash_app.api_client import analysis_run

    try:
        result = analysis_run(
            project_id=project_id,
            dataset_key=dataset_key,
            analysis_type="RAMAN",
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
    Output("raman-result-metrics", "children"),
    Output("raman-result-match-cards", "children"),
    Output("raman-result-figure", "children"),
    Output("raman-result-table", "children"),
    Output("raman-result-processing", "children"),
    Input("raman-latest-result-id", "data"),
    Input("raman-refresh", "data"),
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

    peak_count = summary.get("peak_count", 0)
    match_status = str(summary.get("match_status", "no_match")).replace("_", " ").title()
    top_score = summary.get("top_match_score", 0.0)
    sample_name = resolve_sample_name(summary, result_meta)
    top_score_str = f"{top_score:.4f}" if top_score else "N/A"

    metrics = metrics_row(
        [
            ("Peaks", str(peak_count)),
            ("Match Status", match_status),
            ("Top Score", top_score_str),
            ("Sample", sample_name),
        ]
    )

    match_cards = _build_match_cards(rows, summary.get("top_match_name"))

    dataset_key = result_meta.get("dataset_key")
    figure_area = empty_msg
    if dataset_key:
        figure_area = _build_figure(project_id, dataset_key, summary)

    table_area = _build_match_table(rows)

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


def _build_match_cards(rows: list, top_match_name: str | None) -> html.Div:
    if not rows:
        return html.Div(
            [html.H5("Library Matches", className="mb-3"), html.P("No library matches found.", className="text-muted")]
        )

    cards = [html.H5("Library Matches", className="mb-3")]
    if top_match_name:
        cards.append(html.P(f"Top match: {top_match_name}", className="mb-3"))
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
        curves = analysis_state_curves(project_id, "RAMAN", dataset_key)
    except Exception:
        curves = {}

    raman_shift = curves.get("temperature", [])
    raw_signal = curves.get("raw_signal", [])
    smoothed = curves.get("smoothed", [])
    baseline = curves.get("baseline", [])
    corrected = curves.get("corrected", [])

    if not raman_shift:
        return no_data_figure_msg()

    sample_name = resolve_sample_name(summary, {}, fallback_display_name=dataset_key)
    has_corrected = bool(corrected and len(corrected) == len(raman_shift))
    has_smoothed = bool(smoothed and len(smoothed) == len(raman_shift))
    has_baseline = bool(baseline and len(baseline) == len(raman_shift))
    has_overlay = has_smoothed or has_corrected or has_baseline
    dominant_signal = corrected if has_corrected else smoothed if has_smoothed else raw_signal
    dominant_name = "Query Spectrum" if has_corrected else "Smoothed Spectrum" if has_smoothed else "Imported Spectrum"
    y_range = _y_axis_range(dominant_signal, raw_signal, smoothed, baseline)

    fig = go.Figure()

    if baseline and len(baseline) == len(raman_shift):
        fig.add_trace(
            go.Scatter(
                x=raman_shift,
                y=baseline,
                mode="lines",
                name="Estimated Baseline",
                line=dict(color=_RAMAN_FIGURE_COLORS["baseline"], width=1.3, dash="dash"),
                opacity=0.7,
            )
        )

    if raw_signal and len(raw_signal) == len(raman_shift):
        fig.add_trace(
            go.Scatter(
                x=raman_shift,
                y=raw_signal,
                mode="lines",
                name="Imported Spectrum",
                line=dict(color=_RAMAN_FIGURE_COLORS["raw"], width=1.6),
                opacity=0.45 if has_overlay else 0.95,
            )
        )

    if has_smoothed:
        fig.add_trace(
            go.Scatter(
                x=raman_shift,
                y=smoothed,
                mode="lines",
                name="Smoothed Spectrum",
                line=dict(color=_RAMAN_FIGURE_COLORS["smoothed"], width=2.0),
                opacity=0.9 if has_corrected else 1.0,
            )
        )

    if has_corrected:
        fig.add_trace(
            go.Scatter(
                x=raman_shift,
                y=corrected,
                mode="lines",
                name="Query Spectrum",
                line=dict(color=_RAMAN_FIGURE_COLORS["query"], width=3.2),
            )
        )

    fig.update_layout(
        title=("RAMAN Query Spectrum" f"<br><span style='font-size:0.82em;color:#64748B'>{sample_name}</span>"),
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=_RAMAN_FIGURE_COLORS["panel"],
        hovermode="x unified",
        xaxis_title="Raman Shift (cm^-1)",
        yaxis_title="Intensity (a.u.)",
        xaxis=dict(
            showgrid=True,
            gridcolor=_RAMAN_FIGURE_COLORS["grid"],
            linecolor=_RAMAN_FIGURE_COLORS["axis"],
            tickfont=dict(size=12, color=_RAMAN_FIGURE_COLORS["axis"]),
            title_font=dict(size=13, color=_RAMAN_FIGURE_COLORS["axis"]),
            zeroline=False,
        ),
        yaxis=dict(
            range=y_range,
            showgrid=True,
            gridcolor=_RAMAN_FIGURE_COLORS["grid"],
            linecolor=_RAMAN_FIGURE_COLORS["axis"],
            tickfont=dict(size=12, color=_RAMAN_FIGURE_COLORS["axis"]),
            title_font=dict(size=13, color=_RAMAN_FIGURE_COLORS["axis"]),
            zeroline=False,
        ),
        margin=dict(l=64, r=28, t=82, b=56),
        height=520,
        title_font=dict(size=20, color=_RAMAN_FIGURE_COLORS["query"]),
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
            dataset_table(rows, columns, table_id="raman-matches-table"),
        ]
    )
