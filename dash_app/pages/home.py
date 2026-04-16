"""Import page -- modality-first, multi-step import wizard with rich dataset cards."""

from __future__ import annotations

import base64

import dash
import dash_bootstrap_components as dbc
from dash import ALL, Input, Output, State, callback, clientside_callback, dcc, html

from dash_app.components.chrome import page_header
from dash_app.components.data_preview import (
    dataset_table,
    metadata_list,
    metric_cards,
    original_columns_list,
    quick_plot,
    stats_table,
)
from dash_app.components.page_guidance import (
    guidance_block,
    next_step_block,
    prereq_or_empty_help,
    typical_workflow_block,
)
from dash_app.components.stepper import stepper_indicator
from dash_app.import_preview import build_import_preview
from dash_app.sample_data import list_sample_specs, resolve_sample_request
from utils.i18n import TRANSLATIONS, normalize_ui_locale, translate_ui

dash.register_page(__name__, path="/", title="Import - MaterialScope")

_NONE_VALUE = "__NONE__"

_MODALITY_OPTIONS = ["DSC", "TGA", "DTA", "FTIR", "RAMAN", "XRD"]


def _loc(locale_data: str | None) -> str:
    return normalize_ui_locale(locale_data)


def _modality_axis_label(loc: str, modality: str) -> str:
    tok = (modality or "").strip().upper()
    if not tok:
        return translate_ui(loc, "dash.home.axis_column_generic")
    key = f"dash.home.modality_axis.{tok.lower()}"
    if key in TRANSLATIONS:
        return translate_ui(loc, key)
    return translate_ui(loc, "dash.home.axis_column_generic")


def _modality_signal_label(loc: str, modality: str) -> str:
    tok = (modality or "").strip().upper()
    if not tok:
        return translate_ui(loc, "dash.home.signal_column_generic")
    key = f"dash.home.modality_signal.{tok.lower()}"
    if key in TRANSLATIONS:
        return translate_ui(loc, key)
    return translate_ui(loc, "dash.home.signal_column_generic")


def _modality_desc(loc: str, modality: str) -> str:
    tok = (modality or "").strip().upper()
    if not tok:
        return ""
    key = f"dash.home.modality_desc.{tok.lower()}"
    if key in TRANSLATIONS:
        return translate_ui(loc, key)
    return ""


def _wizard_steps(loc: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for i in range(1, 7):
        out.append(
            {
                "label": translate_ui(loc, f"dash.home.stepper.step{i}_label"),
                "description": translate_ui(loc, f"dash.home.stepper.step{i}_desc"),
            }
        )
    return out


def _mapping_options(columns: list[str], loc: str) -> list[dict[str, str]]:
    return [{"label": translate_ui(loc, "dash.home.mapping_none"), "value": _NONE_VALUE}] + [
        {"label": column, "value": column}
        for column in columns
    ]


def _summary_card(label: str, value: str) -> dbc.Card:
    return dbc.Card(
        dbc.CardBody([html.Small(label, className="text-muted text-uppercase"), html.H4(value, className="mb-0")])
    )


def _build_metrics(datasets: list[dict], loc: str) -> dbc.Row:
    vendors = {item.get("vendor", "Generic") for item in datasets}
    by_type = {
        token: sum(1 for item in datasets if item.get("data_type") == token)
        for token in _MODALITY_OPTIONS
    }
    type_summary = " / ".join(str(by_type[token]) for token in _MODALITY_OPTIONS)
    return dbc.Row(
        [
            dbc.Col(_summary_card(translate_ui(loc, "dash.home.metric_loaded_runs"), str(len(datasets))), md=4),
            dbc.Col(_summary_card(translate_ui(loc, "dash.home.metric_type_breakdown"), type_summary), md=4),
            dbc.Col(_summary_card(translate_ui(loc, "dash.home.metric_vendors"), str(len(vendors))), md=4),
        ],
        className="g-3 mb-4",
    )


def _sample_buttons() -> list[dbc.Col]:
    cols: list[dbc.Col] = []
    for spec in list_sample_specs():
        cols.append(
            dbc.Col(
                dbc.Button(
                    spec["label"],
                    id={"type": "sample-load", "sample_id": spec["id"]},
                    color="secondary",
                    className="w-100",
                ),
                md=6,
                className="mb-2",
            )
        )
    return cols


def _modality_select_buttons() -> html.Div:
    """Render modality selection as large button group (descriptions filled by locale callback)."""
    buttons = []
    for token in _MODALITY_OPTIONS:
        buttons.append(
            dbc.Col(
                dbc.Button(
                    [
                        html.Div(token, className="fw-bold fs-5"),
                        html.Small(
                            id={"type": "modality-desc", "modality": token},
                            className="d-block mt-1 text-start",
                            style={"fontSize": "0.7rem"},
                            children="",
                        ),
                    ],
                    id={"type": "modality-select", "modality": token},
                    color="outline-secondary",
                    className="w-100 text-start p-3 modality-btn",
                ),
                md=4,
                className="mb-2",
            )
        )
    return dbc.Row(buttons)


def _validation_status_badge(status: str, loc: str) -> html.Span:
    color_map = {
        "pass": "success",
        "pass_with_review": "info",
        "warn": "warning",
        "fail": "danger",
    }
    color = color_map.get(status, "secondary")
    badge_key = f"dash.home.validation_badge.{status}"
    if badge_key in TRANSLATIONS:
        label = translate_ui(loc, badge_key)
    else:
        label = translate_ui(loc, "dash.home.validation_badge.unknown")
    return dbc.Badge(label, color=color, className="fs-6")


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

layout = html.Div(
    [
        # -- Stores --
        dcc.Store(id="import-wizard-step", data=0),
        dcc.Store(id="import-selected-modality", data=""),
        dcc.Store(id="pending-upload-files", data=[]),
        dcc.Store(id="pending-import-preview"),
        dcc.Store(id="import-review-data"),
        dcc.Store(id="home-refresh", data=0),

        html.Div(id="home-hero-slot"),
        html.Div(id="home-guidance-slot", className="mb-2"),

        # -- Wizard stepper indicator --
        html.Div(id="wizard-stepper-display"),
        html.Div(id="import-metrics"),

        # =============================================
        # STEP 1: Modality Selection
        # =============================================
        html.Div(
            id="wizard-step-1",
            children=[
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.H5(id="home-step1-title", children="", className="mb-3"),
                            html.P(id="home-step1-intro", children="", className="text-muted"),
                            _modality_select_buttons(),
                            html.Div(id="modality-select-status", className="mt-2"),
                        ]
                    ),
                    className="mb-4",
                ),
            ],
        ),

        # =============================================
        # STEP 2: File Upload + Sample Data
        # =============================================
        html.Div(
            id="wizard-step-2",
            children=[
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.H5(id="step2-title", children="", className="mb-3"),
                            html.Div(id="step2-modality-badge", className="mb-3"),
                            dcc.Upload(
                                id="file-upload",
                                children=html.Div(
                                    [
                                        html.I(className="bi bi-cloud-arrow-up fs-1 d-block mb-2 text-muted"),
                                        html.Div(id="home-upload-caption", className="text-center"),
                                    ],
                                    className="text-center py-4",
                                ),
                                className="upload-zone",
                                multiple=True,
                            ),
                            html.Div(id="upload-status", className="mt-3"),
                            dbc.Select(id="pending-file-select", className="mt-3"),
                            html.Div(id="pending-file-help", className="small text-muted mt-2"),
                            html.Hr(className="my-4"),
                            html.H5(id="home-sample-title", children="", className="mb-3"),
                            html.P(id="home-sample-intro", children="", className="text-muted"),
                            dbc.Row(_sample_buttons()),
                            html.Div(id="sample-status", className="mt-3"),
                        ]
                    ),
                    className="mb-4",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            dbc.Button("", id="step2-prev-btn", color="secondary", outline=True),
                            width="auto",
                        ),
                        dbc.Col(
                            dbc.Button("", id="step2-next-btn", color="primary"),
                            width="auto",
                        ),
                    ],
                    className="g-2",
                ),
            ],
            style={"display": "none"},
        ),

        # =============================================
        # STEP 3: Raw Preview
        # =============================================
        html.Div(
            id="wizard-step-3",
            children=[
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.H5(id="home-step3-title", children="", className="mb-3"),
                            html.Div(id="mapping-preview-status", className="mb-3"),
                            html.Div(id="mapping-preview-table"),
                        ]
                    ),
                    className="mb-4",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            dbc.Button("", id="step3-prev-btn", color="secondary", outline=True),
                            width="auto",
                        ),
                        dbc.Col(
                            dbc.Button("", id="step3-next-btn", color="primary"),
                            width="auto",
                        ),
                    ],
                    className="g-2",
                ),
            ],
            style={"display": "none"},
        ),

        # =============================================
        # STEP 4: Column Mapping
        # =============================================
        html.Div(
            id="wizard-step-4",
            children=[
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.H5(id="home-step4-title", children="", className="mb-3"),
                            html.P(id="home-step4-intro", children="", className="text-muted"),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            dbc.Label(id="mapping-axis-label", children="Axis Column", className="mt-3"),
                                            dbc.Select(id="mapping-temp-select"),
                                        ],
                                        md=4,
                                    ),
                                    dbc.Col(
                                        [
                                            dbc.Label(id="mapping-signal-label", children="Signal Column", className="mt-3"),
                                            dbc.Select(id="mapping-signal-select"),
                                        ],
                                        md=4,
                                    ),
                                    dbc.Col(
                                        [
                                            dbc.Label(id="home-mapping-time-label", children="", className="mt-3"),
                                            dbc.Select(id="mapping-time-select"),
                                        ],
                                        md=4,
                                    ),
                                ],
                                className="g-3",
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            dbc.Label(id="home-mapping-sample-name-label", children="", className="mt-3"),
                                            dbc.Input(id="mapping-sample-name", type="text"),
                                        ],
                                        md=4,
                                    ),
                                    dbc.Col(
                                        [
                                            dbc.Label(id="home-mapping-sample-mass-label", children="", className="mt-3"),
                                            dbc.Input(id="mapping-sample-mass", type="number", value=0),
                                        ],
                                        md=4,
                                    ),
                                    dbc.Col(
                                        [
                                            dbc.Label(id="mapping-rate-label", children="Heating Rate (°C/min)", className="mt-3"),
                                            dbc.Input(id="mapping-heating-rate", type="number", value=10),
                                        ],
                                        md=4,
                                    ),
                                ],
                                className="g-3",
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            dbc.Label(id="home-mapping-xrd-label", children="", className="mt-3"),
                                            dbc.Input(id="mapping-xrd-wavelength", type="number", value=1.5406),
                                        ],
                                        md=4,
                                    ),
                                ],
                                className="g-3",
                                id="xrd-wavelength-row",
                            ),
                        ]
                    ),
                    className="mb-4",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            dbc.Button("", id="step4-prev-btn", color="secondary", outline=True),
                            width="auto",
                        ),
                        dbc.Col(
                            dbc.Button("", id="step4-next-btn", color="primary"),
                            width="auto",
                        ),
                    ],
                    className="g-2",
                ),
            ],
            style={"display": "none"},
        ),

        # =============================================
        # STEP 5: Unit / Metadata Review
        # =============================================
        html.Div(
            id="wizard-step-5",
            children=[
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.H5(id="home-step5-title", children="", className="mb-3"),
                            html.Div(id="review-unit-status"),
                            html.Div(id="review-metadata-summary"),
                            html.Div(id="review-warnings-list"),
                        ]
                    ),
                    className="mb-4",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            dbc.Button("", id="step5-prev-btn", color="secondary", outline=True),
                            width="auto",
                        ),
                        dbc.Col(
                            dbc.Button("", id="step5-next-btn", color="primary"),
                            width="auto",
                        ),
                    ],
                    className="g-2",
                ),
            ],
            style={"display": "none"},
        ),

        # =============================================
        # STEP 6: Validation Summary + Confirm
        # =============================================
        html.Div(
            id="wizard-step-6",
            children=[
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.H5(id="home-step6-title", children="", className="mb-3"),
                            html.Div(id="validation-summary-status"),
                            html.Div(id="validation-summary-warnings"),
                            html.Div(id="validation-summary-details"),
                            html.Hr(className="my-3"),
                            dbc.Button(
                                "",
                                id="import-mapped-btn",
                                color="success",
                                size="lg",
                                className="w-100",
                            ),
                        ]
                    ),
                    className="mb-4",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            dbc.Button("", id="step6-prev-btn", color="secondary", outline=True),
                            width="auto",
                        ),
                    ],
                    className="g-2",
                ),
            ],
            style={"display": "none"},
        ),

        # =============================================
        # Loaded Datasets Panel (always visible)
        # =============================================
        html.Hr(className="my-4"),
        html.H5(id="home-loaded-title", children="", className="mb-3"),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Card(
                            dbc.CardBody(
                                [
                                    html.Div(id="datasets-table"),
                                    dbc.Row(
                                        [
                                            dbc.Col(
                                                [
                                                    dbc.Label(id="home-active-dataset-label", children=""),
                                                    dbc.Select(id="active-dataset-select"),
                                                ],
                                                md=9,
                                            ),
                                            dbc.Col(
                                                dbc.Button(
                                                    "",
                                                    id="remove-dataset-btn",
                                                    color="secondary",
                                                    className="ta-btn-remove w-100",
                                                ),
                                                md=3,
                                                className="d-flex align-items-center",
                                            ),
                                        ],
                                        className="g-2 align-items-center",
                                    ),
                                    html.Div(id="dataset-action-status", className="mt-3"),
                                ]
                            ),
                            className="mb-4",
                        ),
                    ],
                    md=6,
                ),
                dbc.Col(
                    [
                        dbc.Card(
                            dbc.CardBody([html.Div(id="dataset-detail-panel")]),
                            className="mb-4",
                        ),
                    ],
                    md=6,
                ),
            ]
        ),
    ]
)


@callback(
    Output("home-hero-slot", "children"),
    Output("home-guidance-slot", "children"),
    Output("home-step1-title", "children"),
    Output("home-step1-intro", "children"),
    Output("step2-title", "children"),
    Output("home-upload-caption", "children"),
    Output("home-sample-title", "children"),
    Output("home-sample-intro", "children"),
    Output("step2-prev-btn", "children"),
    Output("step2-next-btn", "children"),
    Output("home-step3-title", "children"),
    Output("step3-prev-btn", "children"),
    Output("step3-next-btn", "children"),
    Output("home-step4-title", "children"),
    Output("home-step4-intro", "children"),
    Output("step4-prev-btn", "children"),
    Output("step4-next-btn", "children"),
    Output("home-step5-title", "children"),
    Output("step5-prev-btn", "children"),
    Output("step5-next-btn", "children"),
    Output("home-step6-title", "children"),
    Output("step6-prev-btn", "children"),
    Output("import-mapped-btn", "children"),
    Output("home-loaded-title", "children"),
    Output("home-mapping-time-label", "children"),
    Output("home-mapping-sample-name-label", "children"),
    Output("home-mapping-sample-mass-label", "children"),
    Output("home-mapping-xrd-label", "children"),
    Output("home-active-dataset-label", "children"),
    Output("remove-dataset-btn", "children"),
    Input("ui-locale", "data"),
    prevent_initial_call=False,
)
def render_home_locale_chrome(locale_data):
    loc = _loc(locale_data)
    hero = page_header(
        translate_ui(loc, "dash.home.title"),
        translate_ui(loc, "dash.home.caption"),
        badge=translate_ui(loc, "dash.home.badge"),
    )
    guidance = html.Div(
        [
            guidance_block(
                translate_ui(loc, "dash.home.guidance_title"),
                body=translate_ui(loc, "dash.home.guidance_body"),
            ),
        ]
    )
    upload_caption = [
        translate_ui(loc, "dash.home.upload_drop"),
        html.A(translate_ui(loc, "dash.home.upload_browse"), className="ta-link-emphasis"),
    ]
    return (
        hero,
        guidance,
        translate_ui(loc, "dash.home.step1_title"),
        translate_ui(loc, "dash.home.step1_intro"),
        translate_ui(loc, "dash.home.step2_title"),
        upload_caption,
        translate_ui(loc, "dash.home.sample_section_title"),
        translate_ui(loc, "dash.home.sample_section_intro"),
        translate_ui(loc, "dash.home.btn_back"),
        translate_ui(loc, "dash.home.btn_next_preview"),
        translate_ui(loc, "dash.home.step3_title"),
        translate_ui(loc, "dash.home.btn_back"),
        translate_ui(loc, "dash.home.btn_next_map"),
        translate_ui(loc, "dash.home.step4_title"),
        translate_ui(loc, "dash.home.step4_intro"),
        translate_ui(loc, "dash.home.btn_back"),
        translate_ui(loc, "dash.home.btn_next_review"),
        translate_ui(loc, "dash.home.step5_title"),
        translate_ui(loc, "dash.home.btn_back"),
        translate_ui(loc, "dash.home.btn_next_confirm"),
        translate_ui(loc, "dash.home.step6_title"),
        translate_ui(loc, "dash.home.btn_back"),
        translate_ui(loc, "dash.home.btn_confirm_import"),
        translate_ui(loc, "dash.home.loaded_datasets_title"),
        translate_ui(loc, "dash.home.label_time_optional"),
        translate_ui(loc, "dash.home.label_sample_name"),
        translate_ui(loc, "dash.home.label_sample_mass"),
        translate_ui(loc, "dash.home.label_xrd_wavelength"),
        translate_ui(loc, "dash.home.label_active_dataset"),
        translate_ui(loc, "dash.home.btn_remove"),
    )


@callback(
    Output({"type": "modality-desc", "modality": ALL}, "children"),
    Input("ui-locale", "data"),
    prevent_initial_call=False,
)
def render_home_modality_descriptions(locale_data):
    loc = _loc(locale_data)
    return [translate_ui(loc, f"dash.home.modality_desc.{token.lower()}") for token in _MODALITY_OPTIONS]


# ---------------------------------------------------------------------------
# Step 1: Modality Selection
# ---------------------------------------------------------------------------

@callback(
    Output("import-selected-modality", "data"),
    Output("import-wizard-step", "data", allow_duplicate=True),
    Output("modality-select-status", "children"),
    Input({"type": "modality-select", "modality": ALL}, "n_clicks"),
    State({"type": "modality-select", "modality": ALL}, "id"),
    State("ui-locale", "data"),
    prevent_initial_call=True,
)
def select_modality(_clicks, ids, locale_data):
    loc = _loc(locale_data)
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate
    triggered = ctx.triggered_id
    if not isinstance(triggered, dict):
        raise dash.exceptions.PreventUpdate
    modality = triggered.get("modality", "")
    if modality not in _MODALITY_OPTIONS:
        raise dash.exceptions.PreventUpdate
    status = dbc.Alert(
        translate_ui(loc, "dash.home.modality_selected", modality=modality, desc=_modality_desc(loc, modality)),
        color="success",
        dismissable=True,
    )
    return modality, 1, status


# ---------------------------------------------------------------------------
# Wizard Navigation (step visibility)
# ---------------------------------------------------------------------------

@callback(
    Output("wizard-stepper-display", "children"),
    Output("wizard-step-1", "style"),
    Output("wizard-step-2", "style"),
    Output("wizard-step-3", "style"),
    Output("wizard-step-4", "style"),
    Output("wizard-step-5", "style"),
    Output("wizard-step-6", "style"),
    Output("step2-modality-badge", "children"),
    Output("mapping-axis-label", "children"),
    Output("mapping-signal-label", "children"),
    Output("mapping-rate-label", "children"),
    Input("import-wizard-step", "data"),
    Input("ui-locale", "data"),
    State("import-selected-modality", "data"),
    prevent_initial_call=False,
)
def update_wizard_visibility(step, locale_data, modality):
    loc = _loc(locale_data)
    step = int(step or 0)
    modality = modality or ""
    display = {"display": "block"}
    hidden = {"display": "none"}
    styles = [hidden] * 6
    if 0 <= step < 6:
        styles[step] = display

    stepper = stepper_indicator(_wizard_steps(loc), step)
    badge = dbc.Badge(modality, color="primary", className="fs-6") if modality else ""
    axis_label = _modality_axis_label(loc, modality)
    signal_label = _modality_signal_label(loc, modality)
    rate_label = translate_ui(loc, "dash.home.heating_rate_label")

    return (
        stepper,
        styles[0], styles[1], styles[2], styles[3], styles[4], styles[5],
        badge,
        axis_label,
        signal_label,
        rate_label,
    )


@callback(
    Output("import-wizard-step", "data", allow_duplicate=True),
    Input("step2-prev-btn", "n_clicks"),
    Input("step2-next-btn", "n_clicks"),
    Input("step3-prev-btn", "n_clicks"),
    Input("step3-next-btn", "n_clicks"),
    Input("step4-prev-btn", "n_clicks"),
    Input("step4-next-btn", "n_clicks"),
    Input("step5-prev-btn", "n_clicks"),
    Input("step5-next-btn", "n_clicks"),
    Input("step6-prev-btn", "n_clicks"),
    State("import-wizard-step", "data"),
    prevent_initial_call=True,
)
def navigate_wizard(c2p, c2n, c3p, c3n, c4p, c4n, c5p, c5n, c6p, step):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate
    step = int(step or 0)
    triggered_id = ctx.triggered_id
    step_map = {
        "step2-prev-btn": 0, "step2-next-btn": 2,
        "step3-prev-btn": 1, "step3-next-btn": 3,
        "step4-prev-btn": 2, "step4-next-btn": 4,
        "step5-prev-btn": 3, "step5-next-btn": 5,
        "step6-prev-btn": 4,
    }
    target = step_map.get(triggered_id)
    if target is None:
        raise dash.exceptions.PreventUpdate
    return target


# ---------------------------------------------------------------------------
# Step 2: File Upload
# ---------------------------------------------------------------------------

@callback(
    Output("upload-status", "children"),
    Output("pending-upload-files", "data"),
    Output("pending-file-select", "value"),
    Input("file-upload", "contents"),
    State("file-upload", "filename"),
    State("pending-upload-files", "data"),
    State("ui-locale", "data"),
    prevent_initial_call=True,
)
def collect_pending_uploads(contents_list, filenames, pending_files, locale_data):
    loc = _loc(locale_data)
    if not contents_list:
        return dash.no_update, dash.no_update, dash.no_update

    pending_files = list(pending_files or [])
    existing = {item["file_name"] for item in pending_files}
    added = []
    for content, file_name in zip(contents_list, filenames):
        _, content_string = content.split(",", 1)
        if file_name in existing:
            continue
        pending_files.append({"file_name": file_name, "file_base64": content_string})
        added.append(file_name)

    if not added:
        return dbc.Alert(translate_ui(loc, "dash.home.upload_queued_dup"), color="info"), pending_files, dash.no_update

    return (
        dbc.Alert(translate_ui(loc, "dash.home.upload_queued_ok", files=", ".join(added)), color="success", dismissable=True),
        pending_files,
        added[0],
    )


@callback(
    Output("pending-file-select", "options"),
    Output("pending-file-help", "children"),
    Input("pending-upload-files", "data"),
    Input("ui-locale", "data"),
)
def pending_file_options(pending_files, locale_data):
    loc = _loc(locale_data)
    items = pending_files or []
    options = [{"label": item["file_name"], "value": item["file_name"]} for item in items]
    help_text = (
        translate_ui(loc, "dash.home.pending_help_empty")
        if not items
        else translate_ui(loc, "dash.home.pending_help_count", count=len(items))
    )
    return options, help_text


# ---------------------------------------------------------------------------
# Steps 3-4: Preview + Column Mapping (modality-aware)
# ---------------------------------------------------------------------------

@callback(
    Output("pending-import-preview", "data"),
    Output("mapping-preview-status", "children"),
    Output("mapping-preview-table", "children"),
    Output("mapping-temp-select", "options"),
    Output("mapping-temp-select", "value"),
    Output("mapping-signal-select", "options"),
    Output("mapping-signal-select", "value"),
    Output("mapping-time-select", "options"),
    Output("mapping-time-select", "value"),
    Output("mapping-sample-name", "value"),
    Output("mapping-sample-mass", "value"),
    Output("mapping-heating-rate", "value"),
    Output("mapping-xrd-wavelength", "value"),
    Output("xrd-wavelength-row", "style"),
    Input("pending-file-select", "value"),
    Input("import-selected-modality", "data"),
    State("pending-upload-files", "data"),
    State("ui-locale", "data"),
    prevent_initial_call=False,
)
def build_pending_preview(selected_file, modality, pending_files, locale_data):
    loc = _loc(locale_data)
    modality = modality or ""
    empty_options = _mapping_options([], loc)
    empty_result = (
        None,
        prereq_or_empty_help(
            translate_ui(loc, "dash.home.prereq_select_file_body"),
            tone="secondary",
            title=translate_ui(loc, "dash.home.prereq_select_file_title"),
            locale=loc,
        ),
        "",
        empty_options, _NONE_VALUE,
        empty_options, _NONE_VALUE,
        empty_options, _NONE_VALUE,
        "", 0, 10, 1.5406,
        {"display": "none"},
    )

    if not selected_file:
        return empty_result

    pending = next((item for item in (pending_files or []) if item["file_name"] == selected_file), None)
    if pending is None:
        raise dash.exceptions.PreventUpdate

    try:
        preview = build_import_preview(
            pending["file_name"],
            pending["file_base64"],
            modality=modality or None,
        )
    except Exception as exc:
        return (
            None,
            dbc.Alert(translate_ui(loc, "dash.home.preview_failed", error=str(exc)), color="danger"),
            "",
            empty_options, _NONE_VALUE,
            empty_options, _NONE_VALUE,
            empty_options, _NONE_VALUE,
            "", 0, 10, 1.5406,
            {"display": "block" if modality == "XRD" else "none"},
        )

    guessed = preview.get("guessed_mapping") or {}
    columns = preview["columns"]
    options = _mapping_options(columns, loc)

    suggested_type = str(
        guessed.get("inferred_analysis_type")
        or guessed.get("data_type")
        or modality
        or "DSC"
    ).upper()
    if suggested_type not in set(_MODALITY_OPTIONS):
        suggested_type = modality or "DSC"

    preview_rows = preview["preview_rows"]
    table = dataset_table(preview_rows, columns, page_size=min(10, len(preview_rows)), table_id="raw-preview-table")

    confidence = (guessed.get("confidence") or {}).get("overall", "review")
    warnings = guessed.get("warnings") or []
    status_color = "success" if confidence == "high" else ("warning" if confidence == "medium" else "info")
    status_text = translate_ui(
        loc,
        "dash.home.preview_status",
        file=preview["file_name"],
        rows=preview["row_count"],
        dtype=suggested_type,
        conf=confidence,
    )
    if warnings:
        status_text += translate_ui(loc, "dash.home.preview_warnings_suffix", n=len(warnings))
    status = dbc.Alert(status_text, color=status_color)

    def _pick(column_name: str | None) -> str:
        return column_name if column_name in columns else _NONE_VALUE

    xrd_style = {"display": "block"} if modality == "XRD" else {"display": "none"}

    return (
        preview,
        status,
        table,
        options, _pick(guessed.get("temperature")),
        options, _pick(guessed.get("signal")),
        options, _pick(guessed.get("time")),
        "", 0, 10, 1.5406,
        xrd_style,
    )


# ---------------------------------------------------------------------------
# Step 5: Review units/metadata
# ---------------------------------------------------------------------------

@callback(
    Output("review-unit-status", "children"),
    Output("review-metadata-summary", "children"),
    Output("review-warnings-list", "children"),
    Output("import-review-data", "data"),
    Input("import-wizard-step", "data"),
    State("pending-import-preview", "data"),
    State("import-selected-modality", "data"),
    State("mapping-temp-select", "value"),
    State("mapping-signal-select", "value"),
    State("mapping-time-select", "value"),
    State("mapping-sample-name", "value"),
    State("mapping-sample-mass", "value"),
    State("mapping-heating-rate", "value"),
    State("mapping-xrd-wavelength", "value"),
    State("ui-locale", "data"),
    prevent_initial_call=False,
)
def build_review_data(
    step, preview, modality,
    temp_col, signal_col, time_col,
    sample_name, sample_mass, heating_rate, xrd_wavelength,
    locale_data,
):
    loc = _loc(locale_data)
    step = int(step or 0)
    if step != 4:
        raise dash.exceptions.PreventUpdate

    if not preview:
        return (
            prereq_or_empty_help(
                translate_ui(loc, "dash.home.prereq_no_preview_for_review_body"),
                title=translate_ui(loc, "dash.home.title_no_data"),
                locale=loc,
            ),
            "",
            "",
            None,
        )

    guessed = preview.get("guessed_mapping") or {}
    modality = modality or ""
    confidence = (guessed.get("confidence") or {}).get("overall", "review")
    warnings = guessed.get("warnings") or []

    # Unit review
    detected_x_unit = guessed.get("inferred_signal_unit", "unknown")
    columns = preview.get("columns", [])

    # Build review display
    unit_rows = []
    if temp_col and temp_col != _NONE_VALUE:
        unit_rows.append(html.Tr([html.Td(translate_ui(loc, "dash.home.review_td_axis")), html.Td(temp_col)]))
    if signal_col and signal_col != _NONE_VALUE:
        unit_rows.append(html.Tr([html.Td(translate_ui(loc, "dash.home.review_td_signal")), html.Td(signal_col)]))
    if time_col and time_col != _NONE_VALUE:
        unit_rows.append(html.Tr([html.Td(translate_ui(loc, "dash.home.review_td_time")), html.Td(time_col)]))

    unit_table = dbc.Table(
        [
            html.Thead(
                html.Tr(
                    [
                        html.Th(translate_ui(loc, "dash.home.review_th_role")),
                        html.Th(translate_ui(loc, "dash.home.review_th_column")),
                    ]
                )
            )
        ]
        + [html.Tbody(unit_rows)],
        bordered=True,
        size="sm",
        className="mt-2",
    )

    # Suspicious unit combos via modality specs
    spec_warnings = []
    if modality:
        try:
            from core.modality_specs import check_suspicious_unit_combo
            x_unit = guessed.get("inferred_x_unit", "")
            y_unit = guessed.get("inferred_signal_unit", "")
            spec_warnings = check_suspicious_unit_combo(modality, x_unit, y_unit)
        except ImportError:
            pass

    all_warnings = warnings + spec_warnings
    warning_items = []
    if all_warnings:
        for w in all_warnings:
            warning_items.append(html.Li(w, className="text-warning"))
        warning_list = html.Ul(warning_items, className="mt-2")
    else:
        warning_list = html.P(translate_ui(loc, "dash.home.no_warnings"), className="text-success")

    # Confidence badge
    conf_color = {"high": "success", "medium": "warning", "review": "info"}.get(confidence, "secondary")
    conf_badge = dbc.Badge(translate_ui(loc, "dash.home.confidence_badge", value=confidence), color=conf_color, className="me-2")

    # Metadata summary
    meta_items = []
    meta_items.append(
        html.Tr([html.Td(translate_ui(loc, "dash.home.meta_modality")), html.Td(dbc.Badge(modality, color="primary"))])
    )
    meta_items.append(
        html.Tr(
            [
                html.Td(translate_ui(loc, "dash.home.meta_sample_name")),
                html.Td(sample_name or translate_ui(loc, "dash.home.meta_unknown")),
            ]
        )
    )
    mass_display = (
        translate_ui(loc, "dash.home.meta_mass_fmt", value=sample_mass)
        if sample_mass
        else translate_ui(loc, "dash.home.meta_not_set")
    )
    meta_items.append(html.Tr([html.Td(translate_ui(loc, "dash.home.meta_sample_mass")), html.Td(mass_display)]))
    if modality in {"DSC", "TGA", "DTA"}:
        rate_display = (
            translate_ui(loc, "dash.home.meta_rate_fmt", value=heating_rate)
            if heating_rate
            else translate_ui(loc, "dash.home.meta_not_set")
        )
        meta_items.append(html.Tr([html.Td(translate_ui(loc, "dash.home.meta_heating_rate")), html.Td(rate_display)]))
    if modality == "XRD":
        wl_display = (
            translate_ui(loc, "dash.home.meta_wavelength_fmt", value=xrd_wavelength)
            if xrd_wavelength
            else translate_ui(loc, "dash.home.meta_not_set")
        )
        meta_items.append(html.Tr([html.Td(translate_ui(loc, "dash.home.meta_wavelength")), html.Td(wl_display)]))

    meta_table = dbc.Table(
        [
            html.Thead(
                html.Tr(
                    [
                        html.Th(translate_ui(loc, "dash.home.meta_th_field")),
                        html.Th(translate_ui(loc, "dash.home.meta_th_value")),
                    ]
                )
            )
        ]
        + [html.Tbody(meta_items)],
        bordered=True,
        size="sm",
        className="mt-2",
    )

    review_data = {
        "modality": modality,
        "confidence": confidence,
        "temp_col": temp_col,
        "signal_col": signal_col,
        "time_col": time_col,
        "sample_name": sample_name,
        "sample_mass": sample_mass,
        "heating_rate": heating_rate,
        "xrd_wavelength": xrd_wavelength,
        "warnings": all_warnings,
    }

    return (
        html.Div([conf_badge, html.Span(translate_ui(loc, "dash.home.label_unit_review")), unit_table]),
        html.Div([html.Strong(translate_ui(loc, "dash.home.label_metadata_summary")), meta_table]),
        html.Div([html.Strong(translate_ui(loc, "dash.home.label_warnings_flags")), warning_list]),
        review_data,
    )


# ---------------------------------------------------------------------------
# Step 6: Validation summary
# ---------------------------------------------------------------------------

@callback(
    Output("validation-summary-status", "children"),
    Output("validation-summary-warnings", "children"),
    Output("validation-summary-details", "children"),
    Input("import-wizard-step", "data"),
    State("import-review-data", "data"),
    State("ui-locale", "data"),
    prevent_initial_call=False,
)
def build_validation_summary(step, review_data, locale_data):
    loc = _loc(locale_data)
    step = int(step or 0)
    if step != 5:
        raise dash.exceptions.PreventUpdate

    if not review_data:
        return (
            prereq_or_empty_help(
                translate_ui(loc, "dash.home.prereq_no_review_data_body"),
                title=translate_ui(loc, "dash.home.title_no_data"),
                locale=loc,
            ),
            "",
            "",
        )

    modality = review_data.get("modality", "")
    confidence = review_data.get("confidence", "review")
    warnings = review_data.get("warnings") or []
    temp_col = review_data.get("temp_col", "")
    signal_col = review_data.get("signal_col", "")

    # Determine validation status
    has_blocking = temp_col == _NONE_VALUE or signal_col == _NONE_VALUE
    if has_blocking:
        status = "fail"
    elif confidence == "review" or any("suspicious" in w.lower() or "unusual" in w.lower() for w in warnings):
        status = "pass_with_review"
    elif warnings:
        status = "warn"
    else:
        status = "pass"

    status_badge = _validation_status_badge(status, loc)
    vt_key = f"dash.home.validation_text.{status}"
    status_text = translate_ui(loc, vt_key) if vt_key in TRANSLATIONS else ""

    status_display = html.Div(
        [
            html.H6(translate_ui(loc, "dash.home.label_import_status"), className="d-inline me-2"),
            status_badge,
            html.P(status_text, className="mt-2"),
        ],
        className="mb-3",
    )

    warning_display = ""
    if warnings:
        items = [html.Li(w, className="text-warning") for w in warnings]
        warning_display = html.Div([html.Strong(translate_ui(loc, "dash.home.label_warnings_block")), html.Ul(items, className="mt-1")])

    details = html.Div(
        [
            html.Strong(translate_ui(loc, "dash.home.label_summary")),
            html.Ul(
                [
                    html.Li(translate_ui(loc, "dash.home.summary_li_technique", value=modality)),
                    html.Li(translate_ui(loc, "dash.home.summary_li_axis", value=temp_col)),
                    html.Li(translate_ui(loc, "dash.home.summary_li_signal", value=signal_col)),
                    html.Li(translate_ui(loc, "dash.home.summary_li_confidence", value=confidence)),
                ]
            ),
        ]
    )

    return status_display, warning_display, details


# ---------------------------------------------------------------------------
# Confirm Import
# ---------------------------------------------------------------------------

@callback(
    Output("upload-status", "children", allow_duplicate=True),
    Output("pending-upload-files", "data", allow_duplicate=True),
    Output("pending-file-select", "value", allow_duplicate=True),
    Output("home-refresh", "data", allow_duplicate=True),
    Output("import-wizard-step", "data", allow_duplicate=True),
    Input("import-mapped-btn", "n_clicks"),
    State("project-id", "data"),
    State("pending-import-preview", "data"),
    State("pending-upload-files", "data"),
    State("pending-file-select", "value"),
    State("import-selected-modality", "data"),
    State("mapping-temp-select", "value"),
    State("mapping-signal-select", "value"),
    State("mapping-time-select", "value"),
    State("mapping-sample-name", "value"),
    State("mapping-sample-mass", "value"),
    State("mapping-heating-rate", "value"),
    State("mapping-xrd-wavelength", "value"),
    State("home-refresh", "data"),
    State("ui-locale", "data"),
    prevent_initial_call=True,
)
def import_with_mapping(
    n_clicks,
    project_id,
    preview,
    pending_files,
    selected_file,
    modality,
    temp_col,
    signal_col,
    time_col,
    sample_name,
    sample_mass,
    heating_rate,
    xrd_wavelength,
    refresh_value,
    locale_data,
):
    loc = _loc(locale_data)
    if not n_clicks:
        raise dash.exceptions.PreventUpdate

    if not project_id:
        return (
            prereq_or_empty_help(
                translate_ui(loc, "dash.home.prereq_workspace_import_body"),
                title=translate_ui(loc, "dash.home.prereq_workspace_import_title"),
                locale=loc,
            ),
            dash.no_update, dash.no_update, dash.no_update, dash.no_update,
        )

    if not preview:
        return (
            prereq_or_empty_help(
                translate_ui(loc, "dash.home.prereq_preview_required_body"),
                tone="secondary",
                title=translate_ui(loc, "dash.home.prereq_preview_required_title"),
                locale=loc,
            ),
            dash.no_update, dash.no_update, dash.no_update, dash.no_update,
        )

    if temp_col == _NONE_VALUE or signal_col == _NONE_VALUE:
        return (
            dbc.Alert(translate_ui(loc, "dash.home.import_axis_signal_required"), color="warning"),
            dash.no_update, dash.no_update, dash.no_update, dash.no_update,
        )

    available_columns = set(preview.get("columns", []))
    if temp_col not in available_columns or signal_col not in available_columns:
        return (
            dbc.Alert(translate_ui(loc, "dash.home.import_mapping_stale"), color="warning"),
            dash.no_update, dash.no_update, dash.no_update, dash.no_update,
        )

    from dash_app.api_client import dataset_import as api_dataset_import

    data_type = modality or "DSC"
    metadata = {
        "sample_name": sample_name or "Unknown",
        "sample_mass": float(sample_mass) if sample_mass not in (None, "", 0, 0.0) else None,
        "heating_rate": float(heating_rate) if data_type not in {"XRD", "FTIR", "RAMAN"} and heating_rate not in (None, "", 0, 0.0) else None,
        "xrd_wavelength_angstrom": float(xrd_wavelength) if data_type == "XRD" and xrd_wavelength not in (None, "", 0, 0.0) else None,
    }
    column_mapping = {
        "temperature": temp_col,
        "signal": signal_col,
    }
    if time_col and time_col != _NONE_VALUE:
        column_mapping["time"] = time_col

    try:
        result = api_dataset_import(
            project_id,
            preview["file_name"],
            preview["file_base64"],
            data_type=data_type,
            column_mapping=column_mapping,
            metadata=metadata,
        )
    except Exception as exc:
        exc_msg = str(exc)
        hint = ""
        if "thermal-analysis bounds" in exc_msg or "Temperature range" in exc_msg:
            hint = translate_ui(loc, "dash.home.import_hint_wavenumber")
        elif "strictly increasing" in exc_msg:
            hint = translate_ui(loc, "dash.home.import_hint_monotonic")
        return (
            dbc.Alert(translate_ui(loc, "dash.home.import_failed", error=exc_msg) + hint, color="danger", dismissable=True),
            dash.no_update, dash.no_update, dash.no_update, dash.no_update,
        )

    remaining = [item for item in (pending_files or []) if item["file_name"] != selected_file]
    next_selected = remaining[0]["file_name"] if remaining else None
    ds = result.get("dataset", {})
    return (
        dbc.Alert(
            [
                translate_ui(
                    loc,
                    "dash.home.import_success",
                    name=ds.get("display_name", preview["file_name"]),
                    dtype=ds.get("data_type", "?"),
                ),
                " ",
                translate_ui(loc, "dash.home.import_success_next"),
            ],
            color="success",
            dismissable=True,
        ),
        remaining,
        next_selected,
        int(refresh_value or 0) + 1,
        0,  # Reset wizard to step 0
    )


# ---------------------------------------------------------------------------
# Sample Data
# ---------------------------------------------------------------------------

@callback(
    Output("sample-status", "children"),
    Output("home-refresh", "data", allow_duplicate=True),
    Input({"type": "sample-load", "sample_id": ALL}, "n_clicks"),
    State({"type": "sample-load", "sample_id": ALL}, "id"),
    State("project-id", "data"),
    State("home-refresh", "data"),
    State("ui-locale", "data"),
    prevent_initial_call=True,
)
def load_sample(_clicks, ids, project_id, refresh_value, locale_data):
    loc = _loc(locale_data)
    if not project_id:
        return (
            prereq_or_empty_help(
                translate_ui(loc, "dash.home.prereq_workspace_sample_body"),
                title=translate_ui(loc, "dash.home.prereq_workspace_import_title"),
                locale=loc,
            ),
            dash.no_update,
        )
    ctx = dash.callback_context
    triggered = ctx.triggered_id
    if not triggered:
        raise dash.exceptions.PreventUpdate

    button_id = triggered.get("sample_id") if isinstance(triggered, dict) else None
    sample_path, dtype = resolve_sample_request(button_id or "")
    if sample_path is None or dtype is None:
        raise dash.exceptions.PreventUpdate

    if not sample_path.exists():
        return dbc.Alert(translate_ui(loc, "dash.home.sample_not_found", name=sample_path.name), color="warning"), dash.no_update

    from dash_app.api_client import dataset_import

    try:
        result = dataset_import(
            project_id,
            sample_path.name,
            base64.b64encode(sample_path.read_bytes()).decode("ascii"),
            data_type=dtype,
        )
    except Exception as exc:
        return dbc.Alert(translate_ui(loc, "dash.home.sample_load_failed", error=str(exc)), color="danger"), dash.no_update

    dataset = result.get("dataset", {})
    return (
        dbc.Alert(
            translate_ui(loc, "dash.home.sample_loaded", name=dataset.get("display_name", sample_path.name)),
            color="success",
            dismissable=True,
        ),
        int(refresh_value or 0) + 1,
    )


# ---------------------------------------------------------------------------
# Loaded Datasets Panel
# ---------------------------------------------------------------------------

@callback(
    Output("import-metrics", "children"),
    Output("datasets-table", "children"),
    Output("active-dataset-select", "options"),
    Output("active-dataset-select", "value"),
    Input("project-id", "data"),
    Input("home-refresh", "data"),
    Input("ui-theme", "data"),
    Input("ui-locale", "data"),
    prevent_initial_call=False,
)
def load_workspace_datasets(project_id, _refresh, _ui_theme, locale_data):
    loc = _loc(locale_data)
    if not project_id:
        return (
            "",
            prereq_or_empty_help(
                translate_ui(loc, "dash.home.prereq_workspace_import_body"),
                title=translate_ui(loc, "dash.home.prereq_workspace_import_title"),
                locale=loc,
            ),
            [],
            None,
        )

    from dash_app.api_client import workspace_datasets

    try:
        payload = workspace_datasets(project_id)
    except Exception as exc:
        error = html.P([translate_ui(loc, "dash.home.error_prefix"), " ", str(exc)], className="text-danger")
        return "", error, [], None

    datasets = payload.get("datasets", [])
    if not datasets:
        return (
            _build_metrics([], loc),
            prereq_or_empty_help(
                translate_ui(loc, "dash.home.prereq_no_datasets_body"),
                tone="secondary",
                title=translate_ui(loc, "dash.home.prereq_no_datasets_title"),
                locale=loc,
            ),
            [],
            None,
        )

    rows = [
        {
            "key": item.get("key"),
            "display_name": item.get("display_name"),
            "data_type": item.get("data_type"),
            "vendor": item.get("vendor"),
            "sample_name": item.get("sample_name"),
            "points": item.get("points"),
            "validation_status": item.get("validation_status"),
        }
        for item in datasets
    ]
    table = dataset_table(rows, ["key", "display_name", "data_type", "vendor", "sample_name", "points", "validation_status"], table_id="datasets-summary-table")
    options = [{"label": item.get("display_name", item.get("key")), "value": item.get("key")} for item in datasets]
    return _build_metrics(datasets, loc), table, options, payload.get("active_dataset")


@callback(
    Output("home-refresh", "data", allow_duplicate=True),
    Input("active-dataset-select", "value"),
    State("project-id", "data"),
    State("home-refresh", "data"),
    prevent_initial_call=True,
)
def set_active_dataset(dataset_key, project_id, refresh_value):
    if not dataset_key or not project_id:
        raise dash.exceptions.PreventUpdate
    from dash_app.api_client import workspace_set_active_dataset

    workspace_set_active_dataset(project_id, dataset_key)
    return int(refresh_value or 0) + 1


@callback(
    Output("dataset-action-status", "children"),
    Output("home-refresh", "data", allow_duplicate=True),
    Input("remove-dataset-btn", "n_clicks"),
    State("active-dataset-select", "value"),
    State("project-id", "data"),
    State("home-refresh", "data"),
    State("ui-locale", "data"),
    prevent_initial_call=True,
)
def remove_dataset(n_clicks, dataset_key, project_id, refresh_value, locale_data):
    loc = _loc(locale_data)
    if not n_clicks or not dataset_key or not project_id:
        raise dash.exceptions.PreventUpdate

    from dash_app.api_client import workspace_delete_dataset

    try:
        workspace_delete_dataset(project_id, dataset_key)
    except Exception as exc:
        return dbc.Alert(translate_ui(loc, "dash.home.remove_fail", error=str(exc)), color="danger"), dash.no_update
    return dbc.Alert(translate_ui(loc, "dash.home.remove_ok", key=dataset_key), color="warning"), int(refresh_value or 0) + 1


@callback(
    Output("dataset-detail-panel", "children"),
    Input("project-id", "data"),
    Input("active-dataset-select", "value"),
    Input("home-refresh", "data"),
    Input("ui-theme", "data"),
    Input("ui-locale", "data"),
    prevent_initial_call=False,
)
def load_active_dataset_detail(project_id, dataset_key, _refresh, ui_theme, locale_data):
    loc = _loc(locale_data)
    if not project_id:
        return prereq_or_empty_help(
            translate_ui(loc, "dash.home.prereq_workspace_detail_body"),
            title=translate_ui(loc, "dash.home.prereq_workspace_import_title"),
            locale=loc,
        )
    if not dataset_key:
        return prereq_or_empty_help(
            translate_ui(loc, "dash.home.prereq_select_dataset_body"),
            tone="secondary",
            title=translate_ui(loc, "dash.home.prereq_select_dataset_title"),
            locale=loc,
        )

    from dash_app.api_client import workspace_dataset_data, workspace_dataset_detail

    try:
        detail = workspace_dataset_detail(project_id, dataset_key)
        data_payload = workspace_dataset_data(project_id, dataset_key)
    except Exception as exc:
        return html.P([translate_ui(loc, "dash.home.error_prefix"), " ", str(exc)], className="text-danger")

    rows = data_payload.get("rows", [])
    columns = data_payload.get("columns", [])
    preview_rows = rows[:10]

    return html.Div(
        [
            html.H5(detail.get("dataset", {}).get("display_name", dataset_key), className="mb-3"),
            metric_cards(detail),
            dbc.Accordion(
                [
                    dbc.AccordionItem(metadata_list(detail), title=translate_ui(loc, "dash.home.detail_metadata")),
                    dbc.AccordionItem(original_columns_list(detail), title=translate_ui(loc, "dash.home.detail_columns")),
                    dbc.AccordionItem(
                        dataset_table(preview_rows, columns, page_size=min(10, len(preview_rows) or 1), table_id="active-dataset-table"),
                        title=translate_ui(loc, "dash.home.detail_preview"),
                    ),
                    dbc.AccordionItem(stats_table(rows, columns), title=translate_ui(loc, "dash.home.detail_stats")),
                ],
                start_collapsed=True,
                always_open=True,
                className="mb-3",
            ),
            html.H6(translate_ui(loc, "dash.home.detail_quick_view"), className="mb-2"),
            quick_plot(rows, detail, ui_theme=ui_theme),
        ]
    )
