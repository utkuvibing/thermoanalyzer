"""Tests for the DTA Dash analysis page module."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

# Ensure project root is importable
_ROOT = str(Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import dash_bootstrap_components as dbc
from dash import html


# ---------------------------------------------------------------------------
# Fixture: ensure a Dash app exists before page module import
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _ensure_dash_app():
    """Create a minimal Dash app so dash.register_page() works."""
    import dash
    try:
        dash.get_app()
    except Exception:
        app = dash.Dash(
            __name__,
            use_pages=True,
            pages_folder="",
            suppress_callback_exceptions=True,
        )
        app.layout = html.Div(dash.page_container)
    yield


def _import_dta_page():
    """Import (or reimport) the DTA page module."""
    import dash_app.pages.dta as mod
    return mod


# ---------------------------------------------------------------------------
# Module import
# ---------------------------------------------------------------------------

def test_dta_page_module_imports():
    """DTA page module should import without errors."""
    mod = _import_dta_page()
    assert hasattr(mod, "layout")
    assert hasattr(mod, "_DTA_WORKFLOW_TEMPLATES")
    assert hasattr(mod, "_DTA_ELIGIBLE_TYPES")


def test_dta_page_is_registered():
    """DTA page should be a registered Dash page."""
    import dash
    _import_dta_page()
    pages = dash.page_registry
    dta_pages = {k: v for k, v in pages.items() if "dta" in k.lower()}
    assert len(dta_pages) >= 1, "DTA page not found in dash.page_registry"


# ---------------------------------------------------------------------------
# Workflow templates
# ---------------------------------------------------------------------------

def test_dta_workflow_templates_have_expected_ids():
    mod = _import_dta_page()

    ids = {t["id"] for t in mod._DTA_WORKFLOW_TEMPLATES}
    assert "dta.general" in ids
    assert "dta.thermal_events" in ids
    assert len(mod._TEMPLATE_OPTIONS) == len(mod._DTA_WORKFLOW_TEMPLATES)
    for opt in mod._TEMPLATE_OPTIONS:
        assert "label" in opt
        assert "value" in opt


def test_dta_eligible_types():
    mod = _import_dta_page()
    assert "DTA" in mod._DTA_ELIGIBLE_TYPES
    assert "UNKNOWN" in mod._DTA_ELIGIBLE_TYPES


# ---------------------------------------------------------------------------
# Layout structure
# ---------------------------------------------------------------------------

def test_layout_contains_key_div_ids():
    mod = _import_dta_page()
    layout = mod.layout

    layout_str = str(layout)
    expected_ids = [
        "dta-dataset-selector-area",
        "dta-template-select",
        "dta-run-btn",
        "dta-result-metrics",
        "dta-result-peak-cards",
        "dta-result-figure",
        "dta-result-table",
        "dta-result-processing",
        "dta-refresh",
        "dta-latest-result-id",
    ]
    for div_id in expected_ids:
        assert div_id in layout_str, f"Missing layout element: {div_id}"


# ---------------------------------------------------------------------------
# Peak card rendering
# ---------------------------------------------------------------------------

def test_peak_card_renders_exothermic():
    mod = _import_dta_page()

    row = {
        "direction": "exo",
        "peak_temperature": 250.0,
        "onset_temperature": 240.0,
        "endset_temperature": 260.0,
        "area": 1.234,
        "fwhm": 15.0,
        "height": 0.5,
    }
    card = mod._peak_card(row, 0)
    assert isinstance(card, dbc.Card)
    card_html = str(card)
    assert "Exo" in card_html
    assert "250.0" in card_html


def test_peak_card_renders_endothermic():
    mod = _import_dta_page()

    row = {
        "direction": "endo",
        "peak_temperature": 180.0,
        "onset_temperature": 170.0,
        "endset_temperature": 190.0,
        "area": 0.8,
        "fwhm": 12.0,
        "height": 0.3,
    }
    card = mod._peak_card(row, 1)
    card_html = str(card)
    assert "Endo" in card_html
    assert "180.0" in card_html


def test_peak_card_handles_missing_fields():
    mod = _import_dta_page()

    row = {"peak_temperature": 200.0}
    card = mod._peak_card(row, 0)
    assert isinstance(card, dbc.Card)
    card_html = str(card)
    assert "200.0" in card_html
    assert "--" in card_html


# ---------------------------------------------------------------------------
# Build helpers
# ---------------------------------------------------------------------------

def test_build_peak_cards_empty():
    mod = _import_dta_page()

    result = mod._build_peak_cards([])
    assert isinstance(result, html.Div)
    result_html = str(result)
    assert "No thermal events detected" in result_html


def test_build_peak_cards_with_data():
    mod = _import_dta_page()

    rows = [
        {"direction": "exo", "peak_temperature": 250.0, "onset_temperature": 240.0,
         "endset_temperature": 260.0, "area": 1.0, "fwhm": 15.0, "height": 0.5},
        {"direction": "endo", "peak_temperature": 180.0, "onset_temperature": 170.0,
         "endset_temperature": 190.0, "area": 0.8, "fwhm": 12.0, "height": 0.3},
    ]
    result = mod._build_peak_cards(rows)
    result_html = str(result)
    assert "Peak 1" in result_html
    assert "Peak 2" in result_html
    assert "Exo" in result_html
    assert "Endo" in result_html


def test_build_peak_table_empty():
    mod = _import_dta_page()

    result = mod._build_peak_table([])
    result_html = str(result)
    assert "No event data" in result_html


def test_build_peak_table_with_data():
    mod = _import_dta_page()

    rows = [
        {"direction": "exo", "peak_temperature": 250.0, "onset_temperature": 240.0,
         "endset_temperature": 260.0, "area": 1.0, "fwhm": 15.0, "height": 0.5},
    ]
    result = mod._build_peak_table(rows)
    result_html = str(result)
    assert "Event Data Table" in result_html


# ---------------------------------------------------------------------------
# Template descriptions
# ---------------------------------------------------------------------------

def test_template_descriptions_cover_all_templates():
    mod = _import_dta_page()

    for t in mod._DTA_WORKFLOW_TEMPLATES:
        assert t["id"] in mod._TEMPLATE_DESCRIPTIONS, f"Missing description for {t['id']}"


# ---------------------------------------------------------------------------
# Integration: DTA page with Dash server
# ---------------------------------------------------------------------------

def test_dta_dash_page_import_and_run_via_server():
    """Smoke test: import DTA data and run analysis through the combined server."""
    import base64

    from fastapi.testclient import TestClient
    from dash_app.sample_data import resolve_sample_request
    from dash_app.server import create_combined_app

    app = create_combined_app()
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200

    workspace = client.post("/workspace/new")
    assert workspace.status_code == 200
    project_id = workspace.json()["project_id"]

    # Import a DSC file as DTA (DSC data is valid DTA input in the real
    # processor -- both are thermal differential signals)
    sample_path, _ = resolve_sample_request("load-sample-dsc")
    assert sample_path is not None
    payload = base64.b64encode(sample_path.read_bytes()).decode("ascii")

    imported = client.post(
        "/dataset/import",
        json={
            "project_id": project_id,
            "file_name": sample_path.name,
            "file_base64": payload,
            "data_type": "DTA",
        },
    )
    assert imported.status_code == 200
    dataset_key = imported.json()["dataset"]["key"]
    assert imported.json()["dataset"]["data_type"] == "DTA"

    # Run DTA analysis
    run_response = client.post(
        "/analysis/run",
        json={
            "project_id": project_id,
            "dataset_key": dataset_key,
            "analysis_type": "DTA",
            "workflow_template_id": "dta.general",
        },
    )
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["execution_status"] == "saved"
    assert run_payload["result_id"].startswith("dta_")

    result_id = run_payload["result_id"]

    # Fetch result detail
    detail_response = client.get(f"/workspace/{project_id}/results/{result_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["processing"]["workflow_template_id"] == "dta.general"

    # Fetch analysis-state curves
    curves_response = client.get(f"/workspace/{project_id}/analysis-state/DTA/{dataset_key}")
    assert curves_response.status_code == 200
    curves = curves_response.json()
    assert "temperature" in curves
    assert "raw_signal" in curves
    assert len(curves["temperature"]) > 0


def test_dta_analysis_state_curves_sorted_temperature():
    """Verify DTA analysis-state curves return sorted temperature axis."""
    import base64

    from fastapi.testclient import TestClient
    from dash_app.sample_data import resolve_sample_request
    from dash_app.server import create_combined_app

    app = create_combined_app()
    client = TestClient(app)

    workspace = client.post("/workspace/new")
    project_id = workspace.json()["project_id"]

    sample_path, _ = resolve_sample_request("load-sample-dsc")
    payload = base64.b64encode(sample_path.read_bytes()).decode("ascii")

    imported = client.post(
        "/dataset/import",
        json={
            "project_id": project_id,
            "file_name": sample_path.name,
            "file_base64": payload,
            "data_type": "DTA",
        },
    )
    dataset_key = imported.json()["dataset"]["key"]

    client.post(
        "/analysis/run",
        json={
            "project_id": project_id,
            "dataset_key": dataset_key,
            "analysis_type": "DTA",
            "workflow_template_id": "dta.general",
        },
    )

    curves = client.get(f"/workspace/{project_id}/analysis-state/DTA/{dataset_key}").json()
    temps = curves["temperature"]
    assert temps == sorted(temps)
