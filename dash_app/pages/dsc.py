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
    resolve_sample_name,
    result_placeholder_card,
    workflow_template_card,
)
from dash_app.components.chrome import page_header
from dash_app.components.data_preview import dataset_table
from dash_app.theme import apply_figure_theme
from utils.i18n import normalize_ui_locale, translate_ui

dash.register_page(__name__, path="/dsc", title="DSC Analysis - MaterialScope")

_DSC_TEMPLATE_IDS = ["dsc.general", "dsc.polymer_tg", "dsc.polymer_melting_crystallization"]


def _loc(locale_data: str | None) -> str:
    return normalize_ui_locale(locale_data)

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

def _tg_card(midpoint: float, onset: float, endset: float, delta_cp: float, idx: int, loc: str) -> dbc.Card:
    return dbc.Card(
        dbc.CardBody(
            [
                html.H6(translate_ui(loc, "dash.analysis.label.glass_transition_n", n=idx + 1), className="mb-2"),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.Small(translate_ui(loc, "dash.analysis.label.midpoint"), className="text-muted"),
                                html.H5(f"{midpoint:.1f} °C", className="mb-0 text-danger"),
                            ],
                            md=3,
                        ),
                        dbc.Col(
                            [
                                html.Small(translate_ui(loc, "dash.analysis.label.onset"), className="text-muted"),
                                html.H5(f"{onset:.1f} °C", className="mb-0 text-warning"),
                            ],
                            md=3,
                        ),
                        dbc.Col(
                            [
                                html.Small(translate_ui(loc, "dash.analysis.label.endset"), className="text-muted"),
                                html.H5(f"{endset:.1f} °C", className="mb-0 text-warning"),
                            ],
                            md=3,
                        ),
                        dbc.Col(
                            [
                                html.Small(translate_ui(loc, "dash.analysis.label.dcp"), className="text-muted"),
                                html.H5(f"{delta_cp:.4f}", className="mb-0"),
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


def _peak_card(row: dict, idx: int, loc: str) -> dbc.Card:
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
                        html.Strong(translate_ui(loc, "dash.analysis.label.peak_n", n=idx + 1), className="me-2"),
                        html.Span(
                            peak_type.title(),
                            className="badge",
                            style={"backgroundColor": color, "color": "white", "fontSize": "0.75rem"},
                        ),
                        html.Span(f"  {pt:.1f} °C" if pt is not None else "  --", className="ms-2"),
                    ],
                    className="mb-2",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.Small(translate_ui(loc, "dash.analysis.label.onset"), className="text-muted d-block"),
                                html.Span(f"{onset:.1f}" if onset is not None else "--"),
                            ],
                            md=3,
                        ),
                        dbc.Col(
                            [
                                html.Small(translate_ui(loc, "dash.analysis.label.endset"), className="text-muted d-block"),
                                html.Span(f"{endset:.1f}" if endset is not None else "--"),
                            ],
                            md=3,
                        ),
                        dbc.Col(
                            [
                                html.Small(translate_ui(loc, "dash.analysis.label.area"), className="text-muted d-block"),
                                html.Span(f"{area:.3f}" if area is not None else "--"),
                            ],
                            md=3,
                        ),
                        dbc.Col(
                            [
                                html.Small(translate_ui(loc, "dash.analysis.label.fwhm"), className="text-muted d-block"),
                                html.Span(f"{fwhm:.1f}" if fwhm is not None else "--"),
                                html.Small(f" {translate_ui(loc, 'dash.analysis.label.height')}", className="text-muted ms-2"),
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
        html.Div(id="dsc-hero-slot"),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dataset_selection_card("dsc-dataset-selector-area", card_title_id="dsc-dataset-card-title"),
                        workflow_template_card(
                            "dsc-template-select",
                            "dsc-template-description",
                            [],
                            "dsc.general",
                            card_title_id="dsc-workflow-card-title",
                        ),
                        execute_card("dsc-run-status", "dsc-run-btn", card_title_id="dsc-execute-card-title"),
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


@callback(
    Output("dsc-hero-slot", "children"),
    Output("dsc-dataset-card-title", "children"),
    Output("dsc-workflow-card-title", "children"),
    Output("dsc-execute-card-title", "children"),
    Output("dsc-run-btn", "children"),
    Output("dsc-template-select", "options"),
    Output("dsc-template-select", "value"),
    Output("dsc-template-description", "children"),
    Input("ui-locale", "data"),
    Input("dsc-template-select", "value"),
)
def render_dsc_locale_chrome(locale_data, template_id):
    loc = _loc(locale_data)
    hero = page_header(
        translate_ui(loc, "dash.analysis.dsc.title"),
        translate_ui(loc, "dash.analysis.dsc.caption"),
        badge=translate_ui(loc, "dash.analysis.badge"),
    )
    opts = [
        {"label": translate_ui(loc, f"dash.analysis.dsc.template.{tid}.label"), "value": tid} for tid in _DSC_TEMPLATE_IDS
    ]
    valid = {o["value"] for o in opts}
    tid = template_id if template_id in valid else "dsc.general"
    desc_key = f"dash.analysis.dsc.template.{tid}.desc"
    desc = translate_ui(loc, desc_key)
    if desc == desc_key:
        desc = translate_ui(loc, "dash.analysis.dsc.workflow_fallback")
    return (
        hero,
        translate_ui(loc, "dash.analysis.dataset_selection_title"),
        translate_ui(loc, "dash.analysis.workflow_template_title"),
        translate_ui(loc, "dash.analysis.execute_title"),
        translate_ui(loc, "dash.analysis.dsc.run_btn"),
        opts,
        tid,
        desc,
    )


@callback(
    Output("dsc-dataset-selector-area", "children"),
    Output("dsc-run-btn", "disabled"),
    Input("project-id", "data"),
    Input("dsc-refresh", "data"),
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
        selector_id="dsc-dataset-select",
        empty_msg=translate_ui(loc, "dash.analysis.dsc.empty_import"),
        eligible=eligible_datasets(all_datasets, _DSC_ELIGIBLE_TYPES),
        all_datasets=all_datasets,
        eligible_types=_DSC_ELIGIBLE_TYPES,
        active_dataset=payload.get("active_dataset"),
        locale_data=locale_data,
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
    State("ui-locale", "data"),
    prevent_initial_call=True,
)
def run_dsc_analysis(n_clicks, project_id, dataset_key, template_id, refresh_val, global_refresh, locale_data):
    loc = _loc(locale_data)
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
        return dbc.Alert(translate_ui(loc, "dash.analysis.analysis_failed", error=str(exc)), color="danger"), dash.no_update, dash.no_update, dash.no_update

    alert, saved, result_id = interpret_run_result(result, locale_data=locale_data)
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

    # --- Metrics row ---
    peak_count = summary.get("peak_count", 0)
    tg_count = summary.get("glass_transition_count", 0)
    sample_name = resolve_sample_name(summary, result_meta, locale_data=locale_data)
    na = translate_ui(loc, "dash.analysis.na")
    metrics = metrics_row(
        [
            ("dash.analysis.metric.peaks", str(peak_count)),
            ("dash.analysis.metric.glass_transitions", str(tg_count)),
            ("dash.analysis.metric.template", str(processing.get("workflow_template_label", na))),
            ("dash.analysis.metric.sample", sample_name),
        ],
        locale_data=locale_data,
    )

    # --- Tg metric cards ---
    tg_cards = _build_tg_cards(summary, loc)

    # --- Figure with smoothed/baseline/corrected overlay ---
    dataset_key = result_meta.get("dataset_key")
    figure_area = empty_msg
    if dataset_key:
        figure_area = _build_figure(project_id, dataset_key, summary, rows, ui_theme, loc)

    # --- Peak cards + table ---
    table_area = _build_peak_section(rows, loc)

    # --- Processing info ---
    proc_view = processing_details_section(
        processing,
        extra_lines=[
            html.P(translate_ui(loc, "dash.analysis.dsc.baseline", detail=processing.get("signal_pipeline", {}).get("baseline", {}))),
            html.P(
                translate_ui(
                    loc,
                    "dash.analysis.dsc.peak_detection",
                    detail=processing.get("analysis_steps", {}).get("peak_detection", {}),
                )
            ),
            html.P(
                translate_ui(
                    loc,
                    "dash.analysis.dsc.tg_detection",
                    detail=processing.get("analysis_steps", {}).get("glass_transition", {}),
                )
            ),
            html.P(
                translate_ui(
                    loc,
                    "dash.analysis.dsc.sign_convention",
                    detail=processing.get("method_context", {}).get("sign_convention_label", na),
                ),
                className="mb-0",
            ),
        ],
        locale_data=locale_data,
    )

    return metrics, tg_cards, figure_area, table_area, proc_view


# ---------------------------------------------------------------------------
# DSC-specific builders
# ---------------------------------------------------------------------------

def _build_tg_cards(summary: dict, loc: str) -> html.Div:
    tg_mid = summary.get("tg_midpoint")
    tg_onset = summary.get("tg_onset")
    tg_endset = summary.get("tg_endset")
    delta_cp = summary.get("delta_cp")
    tg_count = summary.get("glass_transition_count", 0)

    if tg_count == 0 or tg_mid is None:
        return html.Div(
            [
                html.H5(translate_ui(loc, "dash.analysis.section.glass_transitions"), className="mb-3"),
                html.P(translate_ui(loc, "dash.analysis.state.not_detected"), className="text-muted"),
            ]
        )

    cards = [html.H5(translate_ui(loc, "dash.analysis.section.glass_transitions"), className="mb-3")]
    cards.append(_tg_card(tg_mid, tg_onset, tg_endset, delta_cp, idx=0, loc=loc))
    if tg_count > 1:
        cards.append(
            html.P(translate_ui(loc, "dash.analysis.state.more_transitions", n=tg_count - 1), className="text-muted small")
        )
    return html.Div(cards)


def _build_figure(project_id: str, dataset_key: str, summary: dict, peak_rows: list, ui_theme: str | None, loc: str) -> html.Div:
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
        return no_data_figure_msg(locale_data=loc)

    tg_midpoint = summary.get("tg_midpoint")
    tg_onset = summary.get("tg_onset")
    tg_endset = summary.get("tg_endset")
    tg_count = summary.get("glass_transition_count", 0)
    sample_name = resolve_sample_name(summary, {}, fallback_display_name=dataset_key, locale_data=loc)

    fig = go.Figure()

    raw_alpha = 0.35 if has_overlay else 1.0
    raw_width = 1.0 if has_overlay else 1.5
    fig.add_trace(
        go.Scatter(
            x=temperature,
            y=raw_signal,
            mode="lines",
            name=translate_ui(loc, "dash.analysis.figure.legend_raw_signal"),
            line=dict(color="#94A3B8", width=raw_width),
            opacity=raw_alpha,
        )
    )

    if smoothed and len(smoothed) == len(temperature):
        fig.add_trace(
            go.Scatter(
                x=temperature,
                y=smoothed,
                mode="lines",
                name=translate_ui(loc, "dash.analysis.figure.legend_smoothed"),
                line=dict(color="#0E7490", width=1.5),
            )
        )

    if baseline and len(baseline) == len(temperature):
        fig.add_trace(
            go.Scatter(
                x=temperature,
                y=baseline,
                mode="lines",
                name=translate_ui(loc, "dash.analysis.figure.legend_baseline"),
                line=dict(color="#6B7280", width=1, dash="dash"),
            )
        )

    if corrected and len(corrected) == len(temperature):
        fig.add_trace(
            go.Scatter(
                x=temperature,
                y=corrected,
                mode="lines",
                name=translate_ui(loc, "dash.analysis.figure.legend_corrected"),
                line=dict(color="#059669", width=1.5),
            )
        )

    # Collect peak temperatures to detect label overlaps with Tg lines
    _ANNOTATION_MIN_SEP = 15.0  # C -- suppress label if closer than this to another
    annotated_temps: list[float] = []

    for row in peak_rows:
        pt = row.get("peak_temperature")
        if pt is None:
            continue
        peak_type = str(row.get("peak_type", "unknown")).lower()
        color = _PEAK_TYPE_COLORS.get(peak_type, "#B45309")
        idx = min(range(len(temperature)), key=lambda i: abs(temperature[i] - pt)) if temperature else None
        if idx is not None:
            # Only show text label if not too close to an already-annotated temp
            too_close = any(abs(pt - t) < _ANNOTATION_MIN_SEP for t in annotated_temps)
            text_str = f"{pt:.1f}" if not too_close else ""
            fig.add_trace(
                go.Scatter(
                    x=[temperature[idx]], y=[raw_signal[idx]], mode="markers+text",
                    marker=dict(size=10, color=color, symbol="diamond"),
                    text=[text_str], textposition="bottom center",
                    textfont=dict(size=9, color=color),
                    name=f"{peak_type.title()} {pt:.1f} °C",
                    showlegend=False,
                )
            )
            if text_str:
                annotated_temps.append(pt)

    # Tg vertical lines -- always show midpoint; onset/endset only when
    # far enough apart to avoid overlapping annotations
    if tg_count > 0 and tg_midpoint is not None:
        fig.add_vline(
            x=tg_midpoint,
            line=dict(color="#EF4444", width=2, dash="dash"),
            annotation_text=translate_ui(loc, "dash.analysis.figure.annot_tg", v=f"{tg_midpoint:.1f}"),
            annotation_position="top left",
        )
        annotated_temps.append(tg_midpoint)

        if tg_onset is not None and all(abs(tg_onset - t) >= _ANNOTATION_MIN_SEP for t in annotated_temps):
            fig.add_vline(
                x=tg_onset,
                line=dict(color="#F59E0B", width=1, dash="dot"),
                annotation_text=translate_ui(loc, "dash.analysis.figure.annot_on", v=f"{tg_onset:.1f}"),
                annotation_position="top left",
            )
            annotated_temps.append(tg_onset)

        if tg_endset is not None and all(abs(tg_endset - t) >= _ANNOTATION_MIN_SEP for t in annotated_temps):
            fig.add_vline(
                x=tg_endset,
                line=dict(color="#F59E0B", width=1, dash="dot"),
                annotation_text=translate_ui(loc, "dash.analysis.figure.annot_end", v=f"{tg_endset:.1f}"),
                annotation_position="top left",
            )

    fig.update_layout(
        title=translate_ui(loc, "dash.analysis.figure.title_dsc", name=sample_name),
        xaxis_title=translate_ui(loc, "dash.analysis.figure.axis_temperature_c"),
        yaxis_title=translate_ui(loc, "dash.analysis.figure.axis_heat_flow"),
        margin=dict(l=56, r=24, t=56, b=48),
        height=480,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    apply_figure_theme(fig, ui_theme)
    return dcc.Graph(figure=fig, config={"displaylogo": False, "responsive": True}, className="ta-plot")


def _build_peak_section(rows: list, loc: str) -> html.Div:
    if not rows:
        return html.Div(
            [
                html.H5(translate_ui(loc, "dash.analysis.section.detected_peaks"), className="mb-3"),
                html.P(translate_ui(loc, "dash.analysis.state.no_peaks"), className="text-muted"),
            ]
        )

    cards = [html.H5(translate_ui(loc, "dash.analysis.section.detected_peaks"), className="mb-3")]
    for idx, row in enumerate(rows):
        cards.append(_peak_card(row, idx, loc))

    cards.append(html.Hr(className="my-3"))
    cards.append(dataset_table(
        rows,
        ["peak_type", "peak_temperature", "onset_temperature", "endset_temperature", "area", "fwhm", "height"],
        table_id="dsc-peaks-table",
    ))
    return html.Div(cards)
