"""Shared analysis-page primitives for stable modality Dash pages.

Reusable layout blocks, callback helpers, and display components used by
DSC, TGA, and future modality pages.  Modality-specific logic (figures,
specialised cards, extra selectors) stays inside each page module.
"""

from __future__ import annotations

from typing import Any

import dash_bootstrap_components as dbc
from dash import dcc, html


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


def metrics_row(pairs: list[tuple[str, str]], *, heading: str = "Result Summary") -> html.Div:
    """Row of metric cards with a heading.

    Parameters
    ----------
    pairs : list of (label, value) tuples
    heading : section title
    """
    cards = [dbc.Col(metric_card(label, value), md=max(3, 12 // max(len(pairs), 1))) for label, value in pairs]
    return html.Div(
        [html.H5(heading, className="mb-3"), dbc.Row(cards, className="g-3")]
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
) -> tuple[html.Div, bool]:
    """Build the dataset selector area and disabled state.

    Returns
    -------
    (children, disabled) : tuple
        *children* is the content for the ``<id>-dataset-selector-area`` div.
        *disabled* is the run button disabled state.
    """
    if not eligible:
        type_labels = ", ".join(sorted(eligible_types))
        return html.P(f"No eligible datasets found ({type_labels}). {empty_msg}", className="text-muted"), True

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
        f"{len(eligible)} of {len(all_datasets)} datasets are eligible (types: {type_labels}).",
        className="text-muted small mt-2",
    )
    return html.Div([selector, info]), False


# ---------------------------------------------------------------------------
# Layout building blocks
# ---------------------------------------------------------------------------

def dataset_selection_card(selector_area_id: str) -> dbc.Card:
    """Card with a placeholder div for the dataset selector."""
    return dbc.Card(
        dbc.CardBody(
            [
                html.H5("Dataset Selection", className="mb-3"),
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
) -> dbc.Card:
    """Card with a workflow-template ``dbc.Select`` and description."""
    return dbc.Card(
        dbc.CardBody(
            [
                html.H5("Workflow Template", className="mb-3"),
                dbc.Select(id=select_id, options=options, value=default_value),
                html.P("", className="text-muted small mt-2", id=description_id),
            ]
        ),
        className="mb-4",
    )


def execute_card(
    status_id: str,
    button_id: str,
    button_label: str = "Run Analysis",
) -> dbc.Card:
    """Card with run-status area and execute button."""
    return dbc.Card(
        dbc.CardBody(
            [
                html.H5("Execute", className="mb-3"),
                html.Div(id=status_id),
                dbc.Button(button_label, id=button_id, color="primary", className="w-100", disabled=True),
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

def interpret_run_result(result: dict[str, Any]) -> tuple[Any, bool, str | None]:
    """Interpret an ``analysis_run`` API response.

    Returns
    -------
    (status_alert, saved, result_id)
        *status_alert* : a ``dbc.Alert`` to show the user.
        *saved* : True when the result was persisted.
        *result_id* : the saved result id (None if not saved).
    """
    status = result.get("execution_status", "unknown")
    result_id = result.get("result_id")
    failure = result.get("failure_reason")
    validation = result.get("validation", {})

    if status == "saved" and result_id:
        alert = dbc.Alert(
            f"Analysis saved (result: {result_id}). "
            f"Validation: {validation.get('status', 'N/A')}, "
            f"warnings: {validation.get('warning_count', 0)}.",
            color="success",
        )
        return alert, True, result_id

    if status == "blocked":
        alert = dbc.Alert(f"Analysis blocked: {failure}", color="warning")
        return alert, False, None

    alert = dbc.Alert(f"Analysis failed: {failure or 'Unknown error'}", color="danger")
    return alert, False, None


# ---------------------------------------------------------------------------
# Processing details
# ---------------------------------------------------------------------------

def processing_details_section(processing: dict, *, extra_lines: list[html.P] | None = None) -> html.Div:
    """Render processing details shared by all modality pages.

    Parameters
    ----------
    processing : dict
        The ``processing`` payload from the result detail response.
    extra_lines : list of html.P, optional
        Modality-specific lines appended after the shared ones.
    """
    signal_pipeline = processing.get("signal_pipeline", {})
    analysis_steps = processing.get("analysis_steps", {})

    lines: list[Any] = [
        html.H5("Processing Details", className="mb-3"),
        html.P(f"Workflow: {processing.get('workflow_template_label', 'N/A')} (v{processing.get('workflow_template_version', '?')})"),
        html.P(f"Smoothing: {signal_pipeline.get('smoothing', {})}"),
    ]

    if extra_lines:
        lines.extend(extra_lines)

    return html.Div(lines)


# ---------------------------------------------------------------------------
# Empty state helpers
# ---------------------------------------------------------------------------

def empty_result_msg(text: str = "Run an analysis to see results here.") -> html.P:
    return html.P(text, className="text-muted")


def no_data_figure_msg(text: str = "No data available for plotting.") -> html.P:
    return html.P(text, className="text-muted")
