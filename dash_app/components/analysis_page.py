"""Shared analysis-page primitives for stable modality Dash pages.

Reusable layout blocks, callback helpers, and display components used by
DSC, TGA, and future modality pages.  Modality-specific logic (figures,
specialised cards, extra selectors) stays inside each page module.
"""

from __future__ import annotations

from typing import Any

import dash_bootstrap_components as dbc
from dash import dcc, html

from utils.i18n import normalize_ui_locale, translate_ui


def _loc(locale_data: str | None) -> str:
    return normalize_ui_locale(locale_data)


def _metric_label(locale_data: str | None, label_key_or_text: str) -> str:
    if label_key_or_text.startswith("dash."):
        return translate_ui(_loc(locale_data), label_key_or_text)
    return label_key_or_text


# ---------------------------------------------------------------------------
# Metric card
# ---------------------------------------------------------------------------

def metric_card(label: str, value: str) -> dbc.Card:
    """Small KPI card used in result summary rows."""
    return dbc.Card(
        dbc.CardBody(
            [html.Small(label, className="text-muted text-uppercase"), html.H4(value, className="mb-0")]
        )
    )


def metrics_row(
    pairs: list[tuple[str, str]],
    *,
    heading: str | None = None,
    locale_data: str | None = None,
) -> html.Div:
    """Row of metric cards with a heading.

    Parameters
    ----------
    pairs : list of (label_key, value) tuples
        *label_key* is either a ``dash.analysis.*`` translation key or a literal label string.
    heading : optional literal heading; if omitted, uses translated Result Summary.
    locale_data : ``ui-locale`` store value for translation.
    """
    loc = _loc(locale_data)
    resolved_heading = heading if heading is not None else translate_ui(loc, "dash.analysis.result_summary")
    cards = [
        dbc.Col(metric_card(_metric_label(locale_data, label), value), md=max(3, 12 // max(len(pairs), 1)))
        for label, value in pairs
    ]
    return html.Div(
        [html.H5(resolved_heading, className="mb-3"), dbc.Row(cards, className="g-3")]
    )


# ---------------------------------------------------------------------------
# Dataset selection helpers
# ---------------------------------------------------------------------------

def eligible_datasets(datasets: list[dict], eligible_types: set[str]) -> list[dict]:
    """Filter datasets whose ``data_type`` (upper-cased) is in *eligible_types*."""
    return [d for d in datasets if (d.get("data_type") or "").upper() in eligible_types]


def dataset_options(datasets: list[dict]) -> list[dict]:
    """Build ``dbc.Select`` option dicts from a dataset list."""
    return [
        {
            "label": f"{d.get('display_name', d.get('key', '?'))} ({d.get('data_type', '?')})",
            "value": d["key"],
        }
        for d in datasets
    ]


def dataset_selector_block(
    *,
    selector_id: str,
    empty_msg: str,
    eligible: list[dict],
    all_datasets: list[dict],
    eligible_types: set[str],
    active_dataset: str | None = None,
    locale_data: str | None = None,
) -> tuple[html.Div, bool]:
    """Build the dataset selector area and disabled state.

    Returns
    -------
    (children, disabled) : tuple
        *children* is the content for the ``<id>-dataset-selector-area`` div.
        *disabled* is the run button disabled state.
    """
    loc = _loc(locale_data)
    if not eligible:
        type_labels = ", ".join(sorted(eligible_types))
        text = translate_ui(loc, "dash.analysis.no_eligible_prefix", types=type_labels, empty=empty_msg)
        return html.P(text, className="text-muted"), True

    options = dataset_options(eligible)
    default_value = None
    if active_dataset:
        eligible_keys = {d["key"] for d in eligible}
        if active_dataset in eligible_keys:
            default_value = active_dataset

    selector = dbc.Select(
        id=selector_id,
        options=options,
        value=default_value or (options[0]["value"] if options else None),
    )
    type_labels = ", ".join(sorted(eligible_types))
    info = html.P(
        translate_ui(
            loc,
            "dash.analysis.eligible_count",
            eligible=len(eligible),
            total=len(all_datasets),
            types=type_labels,
        ),
        className="text-muted small mt-2",
    )
    return html.Div([selector, info]), False


# ---------------------------------------------------------------------------
# Layout building blocks
# ---------------------------------------------------------------------------

def dataset_selection_card(selector_area_id: str, *, card_title_id: str) -> dbc.Card:
    """Card with a placeholder div for the dataset selector."""
    return dbc.Card(
        dbc.CardBody(
            [
                html.H5(id=card_title_id, children="", className="mb-3"),
                html.Div(id=selector_area_id),
            ]
        ),
        className="mb-4",
    )


def workflow_template_card(
    select_id: str,
    description_id: str,
    options: list[dict],
    default_value: str,
    *,
    card_title_id: str,
) -> dbc.Card:
    """Card with a workflow-template ``dbc.Select`` and description."""
    return dbc.Card(
        dbc.CardBody(
            [
                html.H5(id=card_title_id, children="", className="mb-3"),
                dbc.Select(id=select_id, options=options, value=default_value),
                html.P("", className="text-muted small mt-2", id=description_id),
            ]
        ),
        className="mb-4",
    )


def execute_card(status_id: str, button_id: str, *, card_title_id: str) -> dbc.Card:
    """Card with run-status area and execute button (label filled via locale callback)."""
    return dbc.Card(
        dbc.CardBody(
            [
                html.H5(id=card_title_id, children="", className="mb-3"),
                html.Div(id=status_id),
                dbc.Button("", id=button_id, color="primary", className="w-100", disabled=True),
            ]
        ),
        className="mb-4",
    )


def result_placeholder_card(div_id: str) -> dbc.Card:
    """Generic card wrapping a result display div."""
    return dbc.Card(dbc.CardBody(html.Div(id=div_id)), className="mb-4")


def analysis_page_stores(refresh_id: str, latest_result_id: str) -> list[dcc.Store]:
    """Two ``dcc.Store`` elements needed by every analysis page."""
    return [
        dcc.Store(id=refresh_id, data=0),
        dcc.Store(id=latest_result_id),
    ]


# ---------------------------------------------------------------------------
# Execute callback helpers
# ---------------------------------------------------------------------------

def interpret_run_result(result: dict[str, Any], *, locale_data: str | None = None) -> tuple[Any, bool, str | None]:
    """Interpret an ``analysis_run`` API response.

    Returns
    -------
    (status_alert, saved, result_id)
        *status_alert* : a ``dbc.Alert`` to show the user.
        *saved* : True when the result was persisted.
        *result_id* : the saved result id (None if not saved).
    """
    loc = _loc(locale_data)
    status = result.get("execution_status", "unknown")
    result_id = result.get("result_id")
    failure = result.get("failure_reason")
    validation = result.get("validation", {})

    if status == "saved" and result_id:
        alert = dbc.Alert(
            translate_ui(
                loc,
                "dash.analysis.interpret_saved",
                rid=result_id,
                vstatus=validation.get("status", translate_ui(loc, "dash.analysis.na")),
                warnings=validation.get("warning_count", 0),
            ),
            color="success",
        )
        return alert, True, result_id

    if status == "blocked":
        alert = dbc.Alert(
            translate_ui(loc, "dash.analysis.interpret_blocked", reason=failure or translate_ui(loc, "dash.analysis.na")),
            color="warning",
        )
        return alert, False, None

    alert = dbc.Alert(
        translate_ui(loc, "dash.analysis.interpret_failed", reason=failure or translate_ui(loc, "dash.analysis.na")),
        color="danger",
    )
    return alert, False, None


# ---------------------------------------------------------------------------
# Processing details
# ---------------------------------------------------------------------------

def processing_details_section(
    processing: dict,
    *,
    extra_lines: list[html.P] | None = None,
    locale_data: str | None = None,
) -> html.Div:
    """Render processing details shared by all modality pages.

    Parameters
    ----------
    processing : dict
        The ``processing`` payload from the result detail response.
    extra_lines : list of html.P, optional
        Modality-specific lines appended after the shared ones.
    locale_data : ``ui-locale`` store value for translation.
    """
    loc = _loc(locale_data)
    signal_pipeline = processing.get("signal_pipeline", {})

    lines: list[Any] = [
        html.H5(translate_ui(loc, "dash.analysis.processing_title"), className="mb-3"),
        html.P(
            translate_ui(
                loc,
                "dash.analysis.processing_workflow",
                label=processing.get("workflow_template_label", translate_ui(loc, "dash.analysis.na")),
                version=processing.get("workflow_template_version", "?"),
            )
        ),
        html.P(
            translate_ui(
                loc,
                "dash.analysis.processing_smoothing",
                detail=signal_pipeline.get("smoothing", {}),
            )
        ),
    ]

    if extra_lines:
        lines.extend(extra_lines)

    return html.Div(lines)


# ---------------------------------------------------------------------------
# Empty state helpers
# ---------------------------------------------------------------------------

def empty_result_msg(*, text: str | None = None, locale_data: str | None = None) -> html.P:
    if text is not None:
        return html.P(text, className="text-muted")
    return html.P(translate_ui(_loc(locale_data), "dash.analysis.empty_run_result"), className="text-muted")


def no_data_figure_msg(*, text: str | None = None, locale_data: str | None = None) -> html.P:
    if text is not None:
        return html.P(text, className="text-muted")
    return html.P(translate_ui(_loc(locale_data), "dash.analysis.empty_figure"), className="text-muted")


# ---------------------------------------------------------------------------
# Sample name resolution
# ---------------------------------------------------------------------------

def resolve_sample_name(
    summary: dict,
    result_meta: dict,
    *,
    fallback_display_name: str | None = None,
    locale_data: str | None = None,
) -> str:
    """Resolve the best available sample name for display.

    Fallback chain (first non-empty value wins):
      1. ``summary["sample_name"]`` -- set from dataset metadata during analysis
      2. ``fallback_display_name`` -- typically from the dataset list's display_name
      3. ``result_meta["dataset_key"]`` -- the raw key, with extension stripped
      4. Translated ``dash.analysis.na`` -- last resort
    """
    loc = _loc(locale_data)
    name = summary.get("sample_name")
    if name and str(name).strip():
        return str(name).strip()

    if fallback_display_name and str(fallback_display_name).strip():
        return str(fallback_display_name).strip()

    dataset_key = result_meta.get("dataset_key") or ""
    if dataset_key:
        for ext in (".csv", ".txt", ".dat", ".xls", ".xlsx"):
            if dataset_key.lower().endswith(ext):
                dataset_key = dataset_key[: -len(ext)]
                break
        if dataset_key.strip():
            return dataset_key.strip()

    return translate_ui(loc, "dash.analysis.na")
