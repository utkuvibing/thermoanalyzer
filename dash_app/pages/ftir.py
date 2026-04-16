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
from dash_app.theme import PLOT_THEME, normalize_ui_theme
from utils.i18n import normalize_ui_locale, translate_ui

dash.register_page(__name__, path="/ftir", title="FTIR Analysis - MaterialScope")

_FTIR_TEMPLATE_IDS = ["ftir.general", "ftir.functional_groups"]
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


def _loc(locale_data: str | None) -> str:
    return normalize_ui_locale(locale_data)


def _confidence_band_label(loc: str, band: str) -> str:
    token = str(band or "no_match").lower().replace(" ", "_")
    key = f"dash.analysis.confidence.{token}"
    text = translate_ui(loc, key)
    if text == key:
        return str(band).replace("_", " ").title()
    return text


def _match_status_label(loc: str, raw: str | None) -> str:
    token = str(raw or "no_match").lower().replace(" ", "_")
    key = f"dash.analysis.match_status.{token}"
    text = translate_ui(loc, key)
    if text == key:
        s = str(raw or "").replace("_", " ").strip()
        return s.title() if s else translate_ui(loc, "dash.analysis.na")
    return text


def _match_card(row: dict, idx: int, loc: str) -> dbc.Card:
    score = row.get("normalized_score", 0.0)
    band = str(row.get("confidence_band", "no_match")).lower()
    color = _CONFIDENCE_COLORS.get(band, "#6B7280")
    candidate_name = row.get("candidate_name", translate_ui(loc, "dash.analysis.unknown_candidate"))
    candidate_id = row.get("candidate_id", "")
    provider = row.get("library_provider", "")
    evidence = row.get("evidence", {})

    return dbc.Card(
        dbc.CardBody(
            [
                html.Div(
                    [
                        html.I(className="bi bi-search me-2", style={"color": color, "fontSize": "1.1rem"}),
                        html.Strong(translate_ui(loc, "dash.analysis.label.match_n", n=idx + 1), className="me-2"),
                        html.Span(
                            _confidence_band_label(loc, band),
                            className="badge",
                            style={"backgroundColor": color, "color": "white", "fontSize": "0.75rem"},
                        ),
                    ],
                    className="mb-2",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            [html.Small(translate_ui(loc, "dash.analysis.label.candidate"), className="text-muted d-block"), html.Span(candidate_name)],
                            md=4,
                        ),
                        dbc.Col(
                            [html.Small(translate_ui(loc, "dash.analysis.label.score"), className="text-muted d-block"), html.Span(f"{score:.4f}")],
                            md=2,
                        ),
                        dbc.Col(
                            [
                                html.Small(translate_ui(loc, "dash.analysis.label.peak_overlap"), className="text-muted d-block"),
                                html.Span(
                                    f"{evidence.get('shared_peak_count', '--')}/{evidence.get('observed_peak_count', '--')}"
                                ),
                            ],
                            md=2,
                        ),
                        dbc.Col(
                            [
                                html.Small(translate_ui(loc, "dash.analysis.label.provider"), className="text-muted d-block"),
                                html.Span(provider or "--"),
                            ],
                            md=4,
                        ),
                    ],
                    className="g-2",
                ),
                *(
                    [html.P(translate_ui(loc, "dash.analysis.id_label", id=candidate_id), className="text-muted small mb-0 mt-1")]
                    if candidate_id
                    else []
                ),
            ]
        ),
        className="mb-2",
    )


layout = html.Div(
    analysis_page_stores("ftir-refresh", "ftir-latest-result-id")
    + [
        html.Div(id="ftir-hero-slot"),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dataset_selection_card("ftir-dataset-selector-area", card_title_id="ftir-dataset-card-title"),
                        workflow_template_card(
                            "ftir-template-select",
                            "ftir-template-description",
                            [],
                            "ftir.general",
                            card_title_id="ftir-workflow-card-title",
                        ),
                        execute_card("ftir-run-status", "ftir-run-btn", card_title_id="ftir-execute-card-title"),
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


@callback(
    Output("ftir-hero-slot", "children"),
    Output("ftir-dataset-card-title", "children"),
    Output("ftir-workflow-card-title", "children"),
    Output("ftir-execute-card-title", "children"),
    Output("ftir-run-btn", "children"),
    Output("ftir-template-select", "options"),
    Output("ftir-template-select", "value"),
    Output("ftir-template-description", "children"),
    Input("ui-locale", "data"),
    Input("ftir-template-select", "value"),
)
def render_ftir_locale_chrome(locale_data, template_id):
    loc = _loc(locale_data)
    hero = page_header(
        translate_ui(loc, "dash.analysis.ftir.title"),
        translate_ui(loc, "dash.analysis.ftir.caption"),
        badge=translate_ui(loc, "dash.analysis.badge"),
    )
    opts = [{"label": translate_ui(loc, f"dash.analysis.ftir.template.{tid}.label"), "value": tid} for tid in _FTIR_TEMPLATE_IDS]
    valid = {o["value"] for o in opts}
    tid = template_id if template_id in valid else "ftir.general"
    desc_key = f"dash.analysis.ftir.template.{tid}.desc"
    desc = translate_ui(loc, desc_key)
    if desc == desc_key:
        desc = translate_ui(loc, "dash.analysis.ftir.workflow_fallback")
    return (
        hero,
        translate_ui(loc, "dash.analysis.dataset_selection_title"),
        translate_ui(loc, "dash.analysis.workflow_template_title"),
        translate_ui(loc, "dash.analysis.execute_title"),
        translate_ui(loc, "dash.analysis.ftir.run_btn"),
        opts,
        tid,
        desc,
    )


@callback(
    Output("ftir-dataset-selector-area", "children"),
    Output("ftir-run-btn", "disabled"),
    Input("project-id", "data"),
    Input("ftir-refresh", "data"),
    Input("ui-locale", "data"),
)
def load_eligible_datasets(project_id, _refresh, locale_data):
    loc = _loc(locale_data)
    if not project_id:
        return html.P(translate_ui(loc, "dash.analysis.workspace_inactive"), className="text-muted"), True

    from dash_app.api_client import workspace_datasets

    try:
        payload = workspace_datasets(project_id)
    except Exception as exc:
        return dbc.Alert(translate_ui(loc, "dash.analysis.error_loading_datasets", error=str(exc)), color="danger"), True

    all_datasets = payload.get("datasets", [])
    return dataset_selector_block(
        selector_id="ftir-dataset-select",
        empty_msg=translate_ui(loc, "dash.analysis.ftir.empty_import"),
        eligible=eligible_datasets(all_datasets, _FTIR_ELIGIBLE_TYPES),
        all_datasets=all_datasets,
        eligible_types=_FTIR_ELIGIBLE_TYPES,
        active_dataset=payload.get("active_dataset"),
        locale_data=locale_data,
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
    State("ui-locale", "data"),
    prevent_initial_call=True,
)
def run_ftir_analysis(n_clicks, project_id, dataset_key, template_id, refresh_val, global_refresh, locale_data):
    loc = _loc(locale_data)
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
        return dbc.Alert(translate_ui(loc, "dash.analysis.analysis_failed", error=str(exc)), color="danger"), dash.no_update, dash.no_update, dash.no_update

    alert, saved, result_id = interpret_run_result(result, locale_data=locale_data)
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
    Input("ui-theme", "data"),
    Input("ui-locale", "data"),
    State("project-id", "data"),
)
def display_result(result_id, _refresh, ui_theme, locale_data, project_id):
    loc = _loc(locale_data)
    empty_msg = empty_result_msg(locale_data=locale_data)
    if not result_id or not project_id:
        return empty_msg, empty_msg, empty_msg, empty_msg, empty_msg

    from dash_app.api_client import workspace_result_detail

    try:
        detail = workspace_result_detail(project_id, result_id)
    except Exception as exc:
        err = dbc.Alert(translate_ui(loc, "dash.analysis.error_loading_result", error=str(exc)), color="danger")
        return err, empty_msg, empty_msg, empty_msg, empty_msg

    summary = detail.get("summary", {})
    result_meta = detail.get("result", {})
    processing = detail.get("processing", {})
    rows = detail.get("rows_preview", [])

    peak_count = summary.get("peak_count", 0)
    match_status = _match_status_label(loc, summary.get("match_status"))
    top_score = summary.get("top_match_score", 0.0)
    sample_name = resolve_sample_name(summary, result_meta, locale_data=locale_data)
    na = translate_ui(loc, "dash.analysis.na")

    top_score_str = f"{top_score:.4f}" if top_score else na

    metrics = metrics_row(
        [
            ("dash.analysis.metric.peaks", str(peak_count)),
            ("dash.analysis.metric.match_status", match_status),
            ("dash.analysis.metric.top_score", top_score_str),
            ("dash.analysis.metric.sample", sample_name),
        ],
        locale_data=locale_data,
    )

    match_cards = _build_match_cards(rows, summary.get("top_match_name"), loc)

    dataset_key = result_meta.get("dataset_key")
    figure_area = empty_msg
    if dataset_key:
        figure_area = _build_figure(project_id, dataset_key, summary, ui_theme, loc)

    table_area = _build_match_table(rows, loc)

    method_context = processing.get("method_context", {})
    proc_view = processing_details_section(
        processing,
        extra_lines=[
            html.P(translate_ui(loc, "dash.analysis.ftir.baseline", detail=processing.get("signal_pipeline", {}).get("baseline", {}))),
            html.P(translate_ui(loc, "dash.analysis.ftir.normalization", detail=processing.get("signal_pipeline", {}).get("normalization", {}))),
            html.P(translate_ui(loc, "dash.analysis.ftir.peak_detection", detail=processing.get("analysis_steps", {}).get("peak_detection", {}))),
            html.P(translate_ui(loc, "dash.analysis.ftir.similarity_matching", detail=processing.get("analysis_steps", {}).get("similarity_matching", {}))),
            html.P(
                translate_ui(
                    loc,
                    "dash.analysis.ftir.library",
                    mode=method_context.get("library_access_mode", na),
                    source=method_context.get("library_result_source", na),
                ),
                className="mb-0",
            ),
        ],
        locale_data=locale_data,
    )

    return metrics, match_cards, figure_area, table_area, proc_view


def _build_match_cards(rows: list, top_match_name: str | None, loc: str) -> html.Div:
    if not rows:
        return html.Div(
            [
                html.H5(translate_ui(loc, "dash.analysis.section.library_matches"), className="mb-3"),
                html.P(translate_ui(loc, "dash.analysis.state.no_library_matches"), className="text-muted"),
            ]
        )

    cards = [html.H5(translate_ui(loc, "dash.analysis.section.library_matches"), className="mb-3")]
    if top_match_name:
        cards.append(html.P(translate_ui(loc, "dash.analysis.ftir.top_match", name=top_match_name), className="mb-3"))
    for idx, row in enumerate(rows):
        cards.append(_match_card(row, idx, loc))
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


def _build_figure(project_id: str, dataset_key: str, summary: dict, ui_theme: str | None, loc: str) -> html.Div:
    from dash_app.api_client import analysis_state_curves

    try:
        curves = analysis_state_curves(project_id, "FTIR", dataset_key)
    except Exception:
        curves = {}

    wavenumber = curves.get("temperature", [])
    raw_signal = curves.get("raw_signal", [])
    smoothed = curves.get("smoothed", [])
    baseline = curves.get("baseline", [])
    corrected = curves.get("corrected", [])
    has_overlay = curves.get("has_smoothed") or curves.get("has_baseline") or curves.get("has_corrected")

    if not wavenumber:
        return no_data_figure_msg(locale_data=loc)

    sample_name = resolve_sample_name(summary, {}, fallback_display_name=dataset_key, locale_data=loc)
    tone = normalize_ui_theme(ui_theme)
    pt = PLOT_THEME[tone]
    muted = "#66645E" if tone == "light" else "#9E9A93"
    legend_bg = "rgba(255,255,255,0.9)" if tone == "light" else "rgba(26,25,23,0.94)"
    hover_bg = "rgba(255,255,255,0.96)" if tone == "light" else "rgba(34,33,30,0.96)"
    hover_fg = "#1C1A1A" if tone == "light" else "#EEEDEA"
    has_corrected = bool(corrected and len(corrected) == len(wavenumber))
    has_smoothed = bool(smoothed and len(smoothed) == len(wavenumber))
    dominant_signal = corrected if has_corrected else smoothed if has_smoothed else raw_signal
    legend_query = translate_ui(loc, "dash.analysis.figure.legend_query_spectrum")
    legend_smooth = translate_ui(loc, "dash.analysis.figure.legend_smoothed_spectrum")
    legend_imported = translate_ui(loc, "dash.analysis.figure.legend_imported_spectrum")
    dominant_name = legend_query if has_corrected else legend_smooth if has_smoothed else legend_imported
    y_range = _y_axis_range(dominant_signal, raw_signal, smoothed, baseline)

    fig = go.Figure()

    if baseline and len(baseline) == len(wavenumber):
        fig.add_trace(
            go.Scatter(
                x=wavenumber,
                y=baseline,
                mode="lines",
                name=translate_ui(loc, "dash.analysis.figure.legend_estimated_baseline"),
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
                name=legend_imported,
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
                name=legend_smooth,
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
                name=legend_query,
                line=dict(color=_FTIR_FIGURE_COLORS["query"], width=3.2),
            )
        )

    title_main = translate_ui(loc, "dash.analysis.figure.title_ftir_main")
    fig.update_layout(
        title=(f"{title_main}<br><span style='font-size:0.82em;color:{muted}'>{sample_name}</span>"),
        paper_bgcolor=pt["paper_bg"],
        plot_bgcolor=pt["plot_bg"],
        hovermode="x unified",
        xaxis_title=translate_ui(loc, "dash.analysis.figure.axis_wavenumber"),
        yaxis_title=translate_ui(loc, "dash.analysis.figure.axis_signal_au"),
        xaxis=dict(
            autorange="reversed",
            showgrid=True,
            gridcolor=pt["grid"],
            linecolor=pt["grid"],
            tickfont=dict(size=12, color=pt["text"]),
            title_font=dict(size=13, color=pt["text"]),
            zeroline=False,
        ),
        yaxis=dict(
            range=y_range,
            showgrid=True,
            gridcolor=pt["grid"],
            linecolor=pt["grid"],
            tickfont=dict(size=12, color=pt["text"]),
            title_font=dict(size=13, color=pt["text"]),
            zeroline=False,
        ),
        margin=dict(l=64, r=28, t=82, b=56),
        height=520,
        title_font=dict(size=20, color=pt["text"]),
        title_x=0.01,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            bgcolor=legend_bg,
            bordercolor=pt["grid"],
            borderwidth=1,
            font=dict(size=12, color=pt["text"]),
        ),
        hoverlabel=dict(bgcolor=hover_bg, font=dict(color=hover_fg)),
    )
    if fig.data and dominant_name != legend_query:
        fig.data[-1].name = dominant_name
    fig.update_layout(template=pt["template"])
    return dcc.Graph(figure=fig, config={"displaylogo": False, "responsive": True}, className="ta-plot")


def _build_match_table(rows: list, loc: str) -> html.Div:
    if not rows:
        return html.Div(
            [
                html.H5(translate_ui(loc, "dash.analysis.section.match_data_table"), className="mb-3"),
                html.P(translate_ui(loc, "dash.analysis.state.no_match_data"), className="text-muted"),
            ]
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
            html.H5(translate_ui(loc, "dash.analysis.section.match_data_table"), className="mb-3"),
            dataset_table(rows, columns, table_id="ftir-matches-table"),
        ]
    )
