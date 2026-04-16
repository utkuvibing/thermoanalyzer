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
    resolve_sample_name,
    result_placeholder_card,
    workflow_template_card,
)
from dash_app.components.chrome import page_header
from dash_app.components.data_preview import dataset_table
from dash_app.theme import PLOT_THEME, apply_figure_theme, normalize_ui_theme
from utils.i18n import normalize_ui_locale, translate_ui

dash.register_page(__name__, path="/tga", title="TGA Analysis - MaterialScope")

_TGA_TEMPLATE_IDS = ["tga.general", "tga.single_step_decomposition", "tga.multi_step_decomposition"]
_TGA_UNIT_MODE_IDS = ["auto", "percent", "absolute_mass"]
_TGA_ELIGIBLE_TYPES = {"TGA", "UNKNOWN"}


def _loc(locale_data: str | None) -> str:
    return normalize_ui_locale(locale_data)


def _step_card(step: dict, idx: int, loc: str) -> dbc.Card:
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
                        html.Strong(translate_ui(loc, "dash.analysis.label.step_n", n=idx + 1), className="me-2"),
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
                        dbc.Col(
                            [
                                html.Small(translate_ui(loc, "dash.analysis.label.onset"), className="text-muted d-block"),
                                html.Span(f"{onset:.1f} C" if onset is not None else "--"),
                            ],
                            md=3,
                        ),
                        dbc.Col(
                            [
                                html.Small(translate_ui(loc, "dash.analysis.label.midpoint"), className="text-muted d-block"),
                                html.Span(f"{midpoint:.1f} C" if midpoint is not None else "--"),
                            ],
                            md=3,
                        ),
                        dbc.Col(
                            [
                                html.Small(translate_ui(loc, "dash.analysis.label.endset"), className="text-muted d-block"),
                                html.Span(f"{endset:.1f} C" if endset is not None else "--"),
                            ],
                            md=3,
                        ),
                        dbc.Col(
                            [
                                html.Small(translate_ui(loc, "dash.analysis.label.mass_loss"), className="text-muted d-block"),
                                html.Span(f"{mass_loss:.2f} %" if mass_loss is not None else "--"),
                                html.Small(f" {translate_ui(loc, 'dash.analysis.label.residual')}", className="text-muted ms-1"),
                                html.Span(f"{residual:.1f} %" if residual is not None else "--"),
                            ],
                            md=3,
                        ),
                    ],
                    className="g-2",
                ),
                *(
                    [html.P(translate_ui(loc, "dash.analysis.tga.mass_loss_mg", v=mass_loss_mg), className="text-muted small mb-0 mt-1")]
                    if mass_loss_mg is not None
                    else []
                ),
            ]
        ),
        className="mb-2",
    )


def _unit_mode_card() -> dbc.Card:
    return dbc.Card(
        dbc.CardBody(
            [
                html.H5(id="tga-unit-card-title", children="", className="mb-3"),
                dbc.Select(id="tga-unit-mode-select", options=[], value="auto"),
                html.P("", className="text-muted small mt-2", id="tga-unit-mode-description"),
            ]
        ),
        className="mb-4",
    )


layout = html.Div(
    analysis_page_stores("tga-refresh", "tga-latest-result-id")
    + [
        html.Div(id="tga-hero-slot"),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dataset_selection_card("tga-dataset-selector-area", card_title_id="tga-dataset-card-title"),
                        _unit_mode_card(),
                        workflow_template_card(
                            "tga-template-select",
                            "tga-template-description",
                            [],
                            "tga.general",
                            card_title_id="tga-workflow-card-title",
                        ),
                        execute_card("tga-run-status", "tga-run-btn", card_title_id="tga-execute-card-title"),
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


@callback(
    Output("tga-hero-slot", "children"),
    Output("tga-dataset-card-title", "children"),
    Output("tga-unit-card-title", "children"),
    Output("tga-workflow-card-title", "children"),
    Output("tga-execute-card-title", "children"),
    Output("tga-run-btn", "children"),
    Output("tga-template-select", "options"),
    Output("tga-template-select", "value"),
    Output("tga-template-description", "children"),
    Output("tga-unit-mode-select", "options"),
    Output("tga-unit-mode-select", "value"),
    Input("ui-locale", "data"),
    Input("tga-template-select", "value"),
    Input("tga-unit-mode-select", "value"),
)
def render_tga_locale_chrome(locale_data, template_id, unit_mode):
    loc = _loc(locale_data)
    hero = page_header(
        translate_ui(loc, "dash.analysis.tga.title"),
        translate_ui(loc, "dash.analysis.tga.caption"),
        badge=translate_ui(loc, "dash.analysis.badge"),
    )
    opts = [{"label": translate_ui(loc, f"dash.analysis.tga.template.{tid}.label"), "value": tid} for tid in _TGA_TEMPLATE_IDS]
    valid_t = {o["value"] for o in opts}
    tid = template_id if template_id in valid_t else "tga.general"
    desc_key = f"dash.analysis.tga.template.{tid}.desc"
    desc = translate_ui(loc, desc_key)
    if desc == desc_key:
        desc = translate_ui(loc, "dash.analysis.tga.workflow_fallback")

    unit_opts = [{"label": translate_ui(loc, f"dash.analysis.tga.unit.{m}.label"), "value": m} for m in _TGA_UNIT_MODE_IDS]
    valid_u = {o["value"] for o in unit_opts}
    uval = unit_mode if unit_mode in valid_u else "auto"

    return (
        hero,
        translate_ui(loc, "dash.analysis.dataset_selection_title"),
        translate_ui(loc, "dash.analysis.unit_mode_title"),
        translate_ui(loc, "dash.analysis.workflow_template_title"),
        translate_ui(loc, "dash.analysis.execute_title"),
        translate_ui(loc, "dash.analysis.tga.run_btn"),
        opts,
        tid,
        desc,
        unit_opts,
        uval,
    )


@callback(
    Output("tga-unit-mode-description", "children"),
    Input("ui-locale", "data"),
    Input("tga-unit-mode-select", "value"),
)
def update_tga_unit_mode_description(locale_data, unit_mode):
    loc = _loc(locale_data)
    mid = unit_mode or "auto"
    key = f"dash.analysis.tga.unit.{mid}.desc"
    text = translate_ui(loc, key)
    if text == key:
        text = translate_ui(loc, "dash.analysis.tga.unit.fallback")
    return text


@callback(
    Output("tga-dataset-selector-area", "children"),
    Output("tga-run-btn", "disabled"),
    Input("project-id", "data"),
    Input("tga-refresh", "data"),
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
        selector_id="tga-dataset-select",
        empty_msg=translate_ui(loc, "dash.analysis.tga.empty_import"),
        eligible=eligible_datasets(all_datasets, _TGA_ELIGIBLE_TYPES),
        all_datasets=all_datasets,
        eligible_types=_TGA_ELIGIBLE_TYPES,
        active_dataset=payload.get("active_dataset"),
        locale_data=locale_data,
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
    State("ui-locale", "data"),
    prevent_initial_call=True,
)
def run_tga_analysis(n_clicks, project_id, dataset_key, template_id, unit_mode, refresh_val, global_refresh, locale_data):
    loc = _loc(locale_data)
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
        return dbc.Alert(translate_ui(loc, "dash.analysis.analysis_failed", error=str(exc)), color="danger"), dash.no_update, dash.no_update, dash.no_update

    alert, saved, result_id = interpret_run_result(result, locale_data=locale_data)
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

    step_count = summary.get("step_count", 0)
    total_mass_loss = summary.get("total_mass_loss_percent")
    residue = summary.get("residue_percent")
    sample_name = resolve_sample_name(summary, result_meta, locale_data=locale_data)
    na = translate_ui(loc, "dash.analysis.na")

    total_loss_str = f"{total_mass_loss:.2f} %" if total_mass_loss is not None else na
    residue_str = f"{residue:.1f} %" if residue is not None else na

    metrics = metrics_row(
        [
            ("dash.analysis.metric.steps", str(step_count)),
            ("dash.analysis.metric.total_mass_loss", total_loss_str),
            ("dash.analysis.metric.residue", residue_str),
            ("dash.analysis.metric.sample", sample_name),
        ],
        locale_data=locale_data,
    )

    step_cards = _build_step_cards(rows, loc)

    dataset_key = result_meta.get("dataset_key")
    figure_area = empty_msg
    if dataset_key:
        figure_area = _build_figure(project_id, dataset_key, summary, rows, ui_theme, loc)

    table_area = _build_step_table(rows, loc)

    method_context = processing.get("method_context", {})
    unit_label = method_context.get("tga_unit_mode_resolved_label", method_context.get("tga_unit_mode_label", na))
    unit_inference = method_context.get("tga_unit_inference_basis", na)
    proc_view = processing_details_section(
        processing,
        extra_lines=[
            html.P(translate_ui(loc, "dash.analysis.tga.step_detection", detail=processing.get("analysis_steps", {}).get("step_detection", {}))),
            html.P(
                translate_ui(
                    loc,
                    "dash.analysis.tga.unit_mode_line",
                    label=unit_label,
                    basis=unit_inference,
                )
            ),
            html.P(translate_ui(loc, "dash.analysis.tga.calibration", detail=method_context.get("calibration_state", na)), className="mb-0"),
        ],
        locale_data=locale_data,
    )

    return metrics, step_cards, figure_area, table_area, proc_view


def _build_step_cards(rows: list, loc: str) -> html.Div:
    if not rows:
        return html.Div(
            [
                html.H5(translate_ui(loc, "dash.analysis.section.detected_steps"), className="mb-3"),
                html.P(translate_ui(loc, "dash.analysis.state.no_steps"), className="text-muted"),
            ]
        )

    cards = [html.H5(translate_ui(loc, "dash.analysis.section.detected_steps"), className="mb-3")]
    for idx, row in enumerate(rows):
        cards.append(_step_card(row, idx, loc))
    return html.Div(cards)


def _build_figure(project_id: str, dataset_key: str, summary: dict, step_rows: list, ui_theme: str | None, loc: str) -> html.Div:
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
        return no_data_figure_msg(locale_data=loc)

    sample_name = resolve_sample_name(summary, {}, fallback_display_name=dataset_key, locale_data=loc)

    fig = go.Figure()

    raw_alpha = 0.35 if has_smoothed else 1.0
    raw_width = 1.0 if has_smoothed else 1.5
    fig.add_trace(
        go.Scatter(
            x=temperature,
            y=raw_signal,
            mode="lines",
            name=translate_ui(loc, "dash.analysis.figure.legend_raw_mass"),
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
                name=translate_ui(loc, "dash.analysis.figure.legend_smoothed_mass"),
                line=dict(color="#0E7490", width=1.5),
            )
        )

    if dtg and len(dtg) == len(temperature):
        fig.add_trace(
            go.Scatter(
                x=temperature,
                y=dtg,
                mode="lines",
                name=translate_ui(loc, "dash.analysis.figure.legend_dtg"),
                line=dict(color="#DC2626", width=1.2),
                yaxis="y2",
            )
        )

    _ANNOTATION_MIN_SEP = 15.0
    annotated_temps: list[float] = []

    for row in step_rows:
        midpoint = row.get("midpoint_temperature")
        if midpoint is not None and temperature:
            idx = min(range(len(temperature)), key=lambda i: abs(temperature[i] - midpoint))
            too_close = any(abs(midpoint - t) < _ANNOTATION_MIN_SEP for t in annotated_temps)
            text_str = f"{midpoint:.1f}" if not too_close else ""
            fig.add_trace(
                go.Scatter(
                    x=[temperature[idx]],
                    y=[raw_signal[idx]],
                    mode="markers+text",
                    marker=dict(size=10, color="#059669", symbol="diamond"),
                    text=[text_str],
                    textposition="bottom center",
                    textfont=dict(size=9, color="#059669"),
                    name=translate_ui(loc, "dash.analysis.figure.step_mid", v=f"{midpoint:.1f}"),
                    showlegend=False,
                )
            )
            if text_str:
                annotated_temps.append(midpoint)

    n_steps = len(step_rows)
    annotate_onset_endset = n_steps <= 4

    for row in step_rows:
        onset = row.get("onset_temperature")
        endset = row.get("endset_temperature")
        if onset is not None:
            ann_text = translate_ui(loc, "dash.analysis.figure.annot_on", v=f"{onset:.1f}") if annotate_onset_endset else ""
            fig.add_vline(
                x=onset,
                line=dict(color="#F59E0B", width=1, dash="dot"),
                annotation_text=ann_text or None,
                annotation_position="top left",
            )
        if endset is not None:
            ann_text = translate_ui(loc, "dash.analysis.figure.annot_end", v=f"{endset:.1f}") if annotate_onset_endset else ""
            fig.add_vline(
                x=endset,
                line=dict(color="#F59E0B", width=1, dash="dot"),
                annotation_text=ann_text or None,
                annotation_position="top left",
            )

    fig.update_layout(
        title=translate_ui(loc, "dash.analysis.figure.title_tga", name=sample_name),
        xaxis_title=translate_ui(loc, "dash.analysis.figure.axis_temperature_c"),
        yaxis_title=translate_ui(loc, "dash.analysis.figure.axis_mass_pct"),
        yaxis2=dict(title=translate_ui(loc, "dash.analysis.figure.axis_dtg"), overlaying="y", side="right", showgrid=False) if has_dtg else {},
        margin=dict(l=56, r=56, t=56, b=48),
        height=480,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    apply_figure_theme(fig, ui_theme)
    if has_dtg:
        ink = PLOT_THEME[normalize_ui_theme(ui_theme)]["text"]
        fig.update_layout(
            yaxis2=dict(
                title=dict(text=translate_ui(loc, "dash.analysis.figure.axis_dtg"), font=dict(color=ink)),
                overlaying="y",
                side="right",
                showgrid=False,
                tickfont=dict(color=ink),
            )
        )
    return dcc.Graph(figure=fig, config={"displaylogo": False, "responsive": True}, className="ta-plot")


def _build_step_table(rows: list, loc: str) -> html.Div:
    if not rows:
        return html.Div(
            [
                html.H5(translate_ui(loc, "dash.analysis.section.step_table"), className="mb-3"),
                html.P(translate_ui(loc, "dash.analysis.state.no_step_data"), className="text-muted"),
            ]
        )

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
            html.H5(translate_ui(loc, "dash.analysis.section.step_table"), className="mb-3"),
            dataset_table(rows, columns, table_id="tga-steps-table"),
        ]
    )
