"""XRD analysis page -- backend-driven stable first slice."""

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
from dash_app.theme import PLOT_THEME, apply_figure_theme, normalize_ui_theme
from utils.i18n import normalize_ui_locale, translate_ui

dash.register_page(__name__, path="/xrd", title="XRD Analysis - MaterialScope")

_XRD_TEMPLATE_IDS = ["xrd.general", "xrd.phase_screening"]
_XRD_ELIGIBLE_TYPES = {"XRD", "UNKNOWN"}
_XRD_WORKFLOW_TEMPLATES = [
    {"id": "xrd.general", "label": "General XRD"},
    {"id": "xrd.phase_screening", "label": "Phase Screening"},
]
_TEMPLATE_OPTIONS = [{"label": t["label"], "value": t["id"]} for t in _XRD_WORKFLOW_TEMPLATES]

_CONFIDENCE_COLORS = {
    "high_confidence": "#059669",
    "moderate_confidence": "#D97706",
    "low_confidence": "#DC2626",
    "no_match": "#6B7280",
}


def _loc(locale_data: str | None) -> str:
    return normalize_ui_locale(locale_data)


def _coerce_float(value) -> float | None:
    try:
        if value in (None, ""):
            return None
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


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


def _display_candidate_name(row: dict, loc: str) -> str:
    for key in ("display_name_unicode", "display_name", "candidate_name", "phase_name", "candidate_id"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return translate_ui(loc, "dash.analysis.xrd.candidate_unknown")


def _match_card(row: dict, idx: int, loc: str = "en") -> dbc.Card:
    score = _coerce_float(row.get("normalized_score")) or 0.0
    confidence = str(row.get("confidence_band", "no_match")).lower()
    color = _CONFIDENCE_COLORS.get(confidence, "#6B7280")
    evidence = row.get("evidence", {})
    shared_peaks = evidence.get("shared_peak_count", "--")
    overlap_score = evidence.get("weighted_overlap_score", "--")
    mean_delta = evidence.get("mean_delta_position", "--")
    coverage_ratio = evidence.get("coverage_ratio", "--")
    provider = str(row.get("library_provider") or "--")
    formula = str(row.get("formula_unicode") or row.get("formula_pretty") or row.get("formula") or "--")
    candidate = _display_candidate_name(row, loc)

    return dbc.Card(
        dbc.CardBody(
            [
                html.Div(
                    [
                        html.I(className="bi bi-bullseye me-2", style={"color": color, "fontSize": "1.1rem"}),
                        html.Strong(translate_ui(loc, "dash.analysis.label.candidate_n", n=idx + 1), className="me-2"),
                        html.Span(
                            _confidence_band_label(loc, confidence),
                            className="badge",
                            style={"backgroundColor": color, "color": "white", "fontSize": "0.75rem"},
                        ),
                    ],
                    className="mb-2",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            [html.Small(translate_ui(loc, "dash.analysis.label.phase"), className="text-muted d-block"), html.Span(candidate)],
                            md=4,
                        ),
                        dbc.Col(
                            [html.Small(translate_ui(loc, "dash.analysis.label.formula"), className="text-muted d-block"), html.Span(formula)],
                            md=2,
                        ),
                        dbc.Col(
                            [html.Small(translate_ui(loc, "dash.analysis.label.score"), className="text-muted d-block"), html.Span(f"{score:.4f}")],
                            md=2,
                        ),
                        dbc.Col(
                            [
                                html.Small(translate_ui(loc, "dash.analysis.label.shared_peaks"), className="text-muted d-block"),
                                html.Span(shared_peaks),
                            ],
                            md=2,
                        ),
                        dbc.Col(
                            [html.Small(translate_ui(loc, "dash.analysis.label.provider"), className="text-muted d-block"), html.Span(provider)],
                            md=2,
                        ),
                    ],
                    className="g-2",
                ),
                html.Hr(className="my-2"),
                html.P(
                    translate_ui(
                        loc,
                        "dash.analysis.xrd.match_detail_line",
                        overlap=overlap_score,
                        coverage=coverage_ratio,
                        delta=mean_delta,
                    ),
                    className="mb-0 text-muted small",
                ),
            ]
        ),
        className="mb-2",
    )


layout = html.Div(
    analysis_page_stores("xrd-refresh", "xrd-latest-result-id")
    + [
        html.Div(id="xrd-hero-slot"),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dataset_selection_card("xrd-dataset-selector-area", card_title_id="xrd-dataset-card-title"),
                        workflow_template_card(
                            "xrd-template-select",
                            "xrd-template-description",
                            [],
                            "xrd.general",
                            card_title_id="xrd-workflow-card-title",
                        ),
                        execute_card("xrd-run-status", "xrd-run-btn", card_title_id="xrd-execute-card-title"),
                    ],
                    md=4,
                ),
                dbc.Col(
                    [
                        result_placeholder_card("xrd-result-metrics"),
                        result_placeholder_card("xrd-result-figure"),
                        result_placeholder_card("xrd-result-candidate-cards"),
                        result_placeholder_card("xrd-result-table"),
                        result_placeholder_card("xrd-result-processing"),
                    ],
                    md=8,
                ),
            ]
        ),
    ]
)


@callback(
    Output("xrd-hero-slot", "children"),
    Output("xrd-dataset-card-title", "children"),
    Output("xrd-workflow-card-title", "children"),
    Output("xrd-execute-card-title", "children"),
    Output("xrd-run-btn", "children"),
    Output("xrd-template-select", "options"),
    Output("xrd-template-select", "value"),
    Output("xrd-template-description", "children"),
    Input("ui-locale", "data"),
    Input("xrd-template-select", "value"),
)
def render_xrd_locale_chrome(locale_data, template_id):
    loc = _loc(locale_data)
    hero = page_header(
        translate_ui(loc, "dash.analysis.xrd.title"),
        translate_ui(loc, "dash.analysis.xrd.caption"),
        badge=translate_ui(loc, "dash.analysis.badge"),
    )
    opts = [{"label": translate_ui(loc, f"dash.analysis.xrd.template.{tid}.label"), "value": tid} for tid in _XRD_TEMPLATE_IDS]
    valid = {o["value"] for o in opts}
    tid = template_id if template_id in valid else "xrd.general"
    desc_key = f"dash.analysis.xrd.template.{tid}.desc"
    desc = translate_ui(loc, desc_key)
    if desc == desc_key:
        desc = translate_ui(loc, "dash.analysis.xrd.workflow_fallback")
    return (
        hero,
        translate_ui(loc, "dash.analysis.dataset_selection_title"),
        translate_ui(loc, "dash.analysis.workflow_template_title"),
        translate_ui(loc, "dash.analysis.execute_title"),
        translate_ui(loc, "dash.analysis.xrd.run_btn"),
        opts,
        tid,
        desc,
    )


@callback(
    Output("xrd-dataset-selector-area", "children"),
    Output("xrd-run-btn", "disabled"),
    Input("project-id", "data"),
    Input("xrd-refresh", "data"),
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
        selector_id="xrd-dataset-select",
        empty_msg=translate_ui(loc, "dash.analysis.xrd.empty_import"),
        eligible=eligible_datasets(all_datasets, _XRD_ELIGIBLE_TYPES),
        all_datasets=all_datasets,
        eligible_types=_XRD_ELIGIBLE_TYPES,
        active_dataset=payload.get("active_dataset"),
        locale_data=locale_data,
    )


@callback(
    Output("xrd-run-status", "children"),
    Output("xrd-refresh", "data", allow_duplicate=True),
    Output("xrd-latest-result-id", "data", allow_duplicate=True),
    Output("workspace-refresh", "data", allow_duplicate=True),
    Input("xrd-run-btn", "n_clicks"),
    State("project-id", "data"),
    State("xrd-dataset-select", "value"),
    State("xrd-template-select", "value"),
    State("xrd-refresh", "data"),
    State("workspace-refresh", "data"),
    State("ui-locale", "data"),
    prevent_initial_call=True,
)
def run_xrd_analysis(n_clicks, project_id, dataset_key, template_id, refresh_val, global_refresh, locale_data):
    loc = _loc(locale_data)
    if not n_clicks or not project_id or not dataset_key:
        raise dash.exceptions.PreventUpdate

    from dash_app.api_client import analysis_run

    try:
        result = analysis_run(
            project_id=project_id,
            dataset_key=dataset_key,
            analysis_type="XRD",
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
    Output("xrd-result-metrics", "children"),
    Output("xrd-result-candidate-cards", "children"),
    Output("xrd-result-figure", "children"),
    Output("xrd-result-table", "children"),
    Output("xrd-result-processing", "children"),
    Input("xrd-latest-result-id", "data"),
    Input("xrd-refresh", "data"),
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
    rows = detail.get("rows") or detail.get("rows_preview") or []

    match_status = _match_status_label(loc, summary.get("match_status"))
    top_score = _coerce_float(summary.get("top_candidate_score"))
    na = translate_ui(loc, "dash.analysis.na")
    top_score_str = f"{top_score:.4f}" if top_score is not None else na
    peak_count = int(summary.get("peak_count") or 0)
    candidate_count = int(summary.get("candidate_count") or len(rows or []))
    sample_name = resolve_sample_name(summary, result_meta, locale_data=locale_data)

    metrics = metrics_row(
        [
            ("dash.analysis.metric.match_status", match_status),
            ("dash.analysis.metric.top_candidate_score", top_score_str),
            ("dash.analysis.metric.detected_peaks", str(peak_count)),
            ("dash.analysis.metric.candidates", str(candidate_count)),
            ("dash.analysis.metric.sample", sample_name),
        ],
        locale_data=locale_data,
    )

    candidate_cards = _build_match_cards(rows, summary, loc)

    dataset_key = result_meta.get("dataset_key")
    figure_area = empty_msg
    if dataset_key:
        figure_area = _build_figure(project_id, dataset_key, summary, processing, ui_theme, loc, locale_data)

    table_area = _build_match_table(rows, loc)
    method_context = processing.get("method_context", {})
    provenance_state = str(
        summary.get("xrd_provenance_state")
        or method_context.get("xrd_provenance_state")
        or "unknown"
    )
    provenance_warning = str(
        summary.get("xrd_provenance_warning")
        or method_context.get("xrd_provenance_warning")
        or ""
    ).strip()
    axis_role = str(method_context.get("xrd_axis_role") or "two_theta")
    wavelength = method_context.get("xrd_wavelength_angstrom")
    wl_display = (
        str(wavelength)
        if wavelength not in (None, "")
        else translate_ui(loc, "dash.analysis.xrd.wavelength_not_provided")
    )

    proc_extra = [
        html.P(translate_ui(loc, "dash.analysis.xrd.axis_role_note", role=axis_role)),
        html.P(translate_ui(loc, "dash.analysis.xrd.wavelength_line", value=wl_display)),
        html.P(translate_ui(loc, "dash.analysis.xrd.provenance_state", state=provenance_state)),
    ]
    if provenance_warning:
        proc_extra.append(html.P(translate_ui(loc, "dash.analysis.xrd.provenance_warning", warning=provenance_warning)))
    proc_extra.extend(
        [
            html.P(translate_ui(loc, "dash.analysis.xrd.qualitative_notice")),
            html.P(
                translate_ui(loc, "dash.analysis.xrd.peak_detection", detail=processing.get("analysis_steps", {}).get("peak_detection", {})),
                className="mb-0",
            ),
        ]
    )

    proc_view = processing_details_section(processing, extra_lines=proc_extra, locale_data=locale_data)
    return metrics, candidate_cards, figure_area, table_area, proc_view


def _build_match_cards(rows: list, summary: dict, loc: str = "en") -> html.Div:
    cards: list = [html.H5(translate_ui(loc, "dash.analysis.section.candidate_matches"), className="mb-3")]
    caution_message = str(summary.get("caution_message") or "").strip()
    if caution_message:
        cards.append(dbc.Alert(caution_message, color="warning", className="mb-3"))

    top_name = str(
        summary.get("top_candidate_display_name")
        or summary.get("top_candidate_name")
        or summary.get("top_phase_display_name")
        or summary.get("top_phase")
        or ""
    ).strip()
    if top_name:
        cards.append(html.P(translate_ui(loc, "dash.analysis.xrd.top_candidate", name=top_name), className="mb-2"))

    if not rows:
        cards.append(html.P(translate_ui(loc, "dash.analysis.state.no_candidate_matches"), className="text-muted"))
        return html.Div(cards)

    for idx, row in enumerate(rows):
        cards.append(_match_card(row, idx, loc))
    return html.Div(cards)


def _build_figure(
    project_id: str,
    dataset_key: str,
    summary: dict,
    processing: dict,
    ui_theme: str | None,
    loc: str = "en",
    locale_data: str | None = None,
) -> html.Div:
    from dash_app.api_client import analysis_state_curves

    try:
        curves = analysis_state_curves(project_id, "XRD", dataset_key)
    except Exception:
        curves = {}

    axis = curves.get("temperature", [])
    raw_signal = curves.get("raw_signal", [])
    smoothed = curves.get("smoothed", [])
    baseline = curves.get("baseline", [])
    corrected = curves.get("corrected", [])

    _ld = locale_data if locale_data is not None else loc
    if not axis:
        return no_data_figure_msg(locale_data=_ld)

    has_corrected = bool(corrected and len(corrected) == len(axis))
    has_smoothed = bool(smoothed and len(smoothed) == len(axis))
    has_raw = bool(raw_signal and len(raw_signal) == len(axis))
    has_baseline = bool(baseline and len(baseline) == len(axis))
    if not any((has_corrected, has_smoothed, has_raw)):
        return no_data_figure_msg(text=translate_ui(loc, "dash.analysis.xrd.no_plot_signal"), locale_data=_ld)

    primary_signal = corrected if has_corrected else smoothed if has_smoothed else raw_signal
    legend_raw = translate_ui(loc, "dash.analysis.figure.legend_raw_diffractogram")
    legend_smooth = translate_ui(loc, "dash.analysis.figure.legend_smoothed_diffractogram")
    legend_corr = translate_ui(loc, "dash.analysis.figure.legend_corrected_diffractogram")
    primary_name = legend_corr if has_corrected else legend_smooth if has_smoothed else legend_raw
    has_overlay = has_corrected or has_smoothed
    sample_name = resolve_sample_name(summary, {}, fallback_display_name=dataset_key, locale_data=loc)
    tone = normalize_ui_theme(ui_theme)
    pt = PLOT_THEME[tone]
    muted = "#66645E" if tone == "light" else "#9E9A93"
    line_primary = pt["text"]
    method_context = processing.get("method_context", {})
    axis_role = str(method_context.get("xrd_axis_role") or "two_theta").strip().lower()
    if axis_role in {"two_theta", ""}:
        axis_title = translate_ui(loc, "dash.analysis.figure.axis_two_theta")
    else:
        axis_title = translate_ui(loc, "dash.analysis.figure.axis_x_generic", role=axis_role)

    fig = go.Figure()
    if has_raw:
        fig.add_trace(
            go.Scatter(
                x=axis,
                y=raw_signal,
                mode="lines",
                name=legend_raw,
                line=dict(color="#94A3B8", width=1.4),
                opacity=0.35 if has_overlay else 0.95,
            )
        )
    if has_smoothed:
        fig.add_trace(
            go.Scatter(
                x=axis,
                y=smoothed,
                mode="lines",
                name=legend_smooth,
                line=dict(color="#0369A1", width=2.0),
                opacity=0.85 if has_corrected else 1.0,
            )
        )
    if has_baseline:
        fig.add_trace(
            go.Scatter(
                x=axis,
                y=baseline,
                mode="lines",
                name=translate_ui(loc, "dash.analysis.figure.legend_baseline"),
                line=dict(color="#6D28D9", width=1.2, dash="dash"),
                opacity=0.7,
            )
        )

    fig.add_trace(
        go.Scatter(
            x=axis,
            y=primary_signal,
            mode="lines",
            name=primary_name,
            line=dict(color=line_primary, width=3.0),
        )
    )

    title_main = translate_ui(loc, "dash.analysis.figure.title_xrd_main")
    fig.update_layout(
        title=(f"{title_main}<br><span style='font-size:0.82em;color:{muted}'>{sample_name}</span>"),
        paper_bgcolor=pt["paper_bg"],
        plot_bgcolor=pt["plot_bg"],
        hovermode="x unified",
        xaxis_title=axis_title,
        yaxis_title=translate_ui(loc, "dash.analysis.figure.axis_intensity_au"),
        margin=dict(l=64, r=28, t=82, b=56),
        height=520,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    apply_figure_theme(fig, ui_theme)
    return dcc.Graph(figure=fig, config={"displaylogo": False, "responsive": True}, className="ta-plot")


def _build_match_table(rows: list, loc: str = "en") -> html.Div:
    if not rows:
        return html.Div(
            [
                html.H5(translate_ui(loc, "dash.analysis.section.candidate_evidence_table"), className="mb-3"),
                html.P(translate_ui(loc, "dash.analysis.state.no_match_data"), className="text-muted"),
            ]
        )

    columns = [
        "rank",
        "candidate_id",
        "display_name_unicode",
        "formula_unicode",
        "normalized_score",
        "confidence_band",
        "library_provider",
        "library_package",
    ]
    return html.Div(
        [
            html.H5(translate_ui(loc, "dash.analysis.section.candidate_evidence_table"), className="mb-3"),
            dataset_table(rows, columns, table_id="xrd-matches-table"),
        ]
    )
