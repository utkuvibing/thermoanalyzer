"""Tests for the RAMAN Dash analysis page module."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = str(Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import dash_bootstrap_components as dbc
from dash import dcc, html


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


def _import_raman_page():
    import dash_app.pages.raman as mod

    return mod


def test_raman_page_module_imports():
    mod = _import_raman_page()
    assert hasattr(mod, "layout")
    assert hasattr(mod, "_RAMAN_WORKFLOW_TEMPLATES")
    assert hasattr(mod, "_RAMAN_ELIGIBLE_TYPES")


def test_raman_page_is_registered():
    import dash

    _import_raman_page()
    pages = dash.page_registry
    raman_pages = {key: value for key, value in pages.items() if "raman" in key.lower()}
    assert len(raman_pages) >= 1, "RAMAN page not found in dash.page_registry"


def test_raman_workflow_templates_have_expected_ids():
    mod = _import_raman_page()

    ids = {t["id"] for t in mod._RAMAN_WORKFLOW_TEMPLATES}
    assert "raman.general" in ids
    assert "raman.polymorph_screening" in ids
    assert len(mod._TEMPLATE_OPTIONS) == len(mod._RAMAN_WORKFLOW_TEMPLATES)


def test_raman_eligible_types():
    mod = _import_raman_page()
    assert "RAMAN" in mod._RAMAN_ELIGIBLE_TYPES
    assert "UNKNOWN" in mod._RAMAN_ELIGIBLE_TYPES


def test_layout_contains_key_div_ids():
    mod = _import_raman_page()
    layout_str = str(mod.layout)

    expected_ids = [
        "raman-dataset-selector-area",
        "raman-template-select",
        "raman-run-btn",
        "raman-result-metrics",
        "raman-result-figure",
        "raman-result-match-cards",
        "raman-result-table",
        "raman-result-processing",
        "raman-refresh",
        "raman-latest-result-id",
    ]
    for div_id in expected_ids:
        assert div_id in layout_str, f"Missing layout element: {div_id}"


def test_layout_places_figure_before_match_cards():
    mod = _import_raman_page()
    layout_str = str(mod.layout)
    assert layout_str.index("raman-result-figure") < layout_str.index("raman-result-match-cards")


def test_build_match_cards_empty():
    mod = _import_raman_page()
    result = mod._build_match_cards([], None)
    assert isinstance(result, html.Div)
    assert "No library matches found" in str(result)


def test_build_match_cards_with_data():
    mod = _import_raman_page()
    rows = [
        {
            "candidate_name": "CNT reference",
            "normalized_score": 0.91,
            "confidence_band": "high_confidence",
            "library_provider": "OpenSpecy",
            "evidence": {"shared_peak_count": 4, "observed_peak_count": 6},
        }
    ]
    result = mod._build_match_cards(rows, "CNT reference")
    result_html = str(result)
    assert "Top match: CNT reference" in result_html
    assert "Match 1" in result_html


def test_build_figure_uses_corrected_as_primary_trace(monkeypatch):
    mod = _import_raman_page()
    import dash_app.api_client as api_client

    monkeypatch.setattr(
        api_client,
        "analysis_state_curves",
        lambda _project_id, _analysis_type, _dataset_key: {
            "temperature": [300.0, 600.0, 900.0, 1200.0],
            "raw_signal": [10.0, 25.0, 18.0, 12.0],
            "smoothed": [11.0, 24.0, 17.0, 11.5],
            "baseline": [2.0, 2.0, 2.0, 2.0],
            "corrected": [9.0, 22.0, 15.0, 9.5],
        },
    )

    graph = mod._build_figure("proj-1", "dataset-1", {"sample_name": "CNT Run"})

    assert isinstance(graph, dcc.Graph)
    corrected_trace = next(trace for trace in graph.figure.data if trace.name == "Query Spectrum")
    raw_trace = next(trace for trace in graph.figure.data if trace.name == "Imported Spectrum")
    assert corrected_trace.line.width == 3.2
    assert raw_trace.opacity < 0.5
    assert graph.figure.layout.xaxis.autorange != "reversed"
    assert graph.figure.layout.yaxis.range is not None


def test_build_match_table_empty():
    mod = _import_raman_page()
    result = mod._build_match_table([])
    assert "No match data." in str(result)


def test_raman_dash_page_import_and_run_via_server():
    """Smoke test: import RAMAN data and run analysis through the combined server."""
    import base64

    from fastapi.testclient import TestClient

    from dash_app.sample_data import resolve_sample_request
    from dash_app.server import create_combined_app

    app = create_combined_app()
    client = TestClient(app)

    workspace = client.post("/workspace/new")
    assert workspace.status_code == 200
    project_id = workspace.json()["project_id"]

    sample_path, sample_type = resolve_sample_request("load-sample-raman")
    assert sample_path is not None
    assert sample_type == "RAMAN"

    payload = base64.b64encode(sample_path.read_bytes()).decode("ascii")
    imported = client.post(
        "/dataset/import",
        json={
            "project_id": project_id,
            "file_name": sample_path.name,
            "file_base64": payload,
            "data_type": "RAMAN",
        },
    )
    assert imported.status_code == 200
    dataset_key = imported.json()["dataset"]["key"]
    assert imported.json()["dataset"]["data_type"] == "RAMAN"

    run_response = client.post(
        "/analysis/run",
        json={
            "project_id": project_id,
            "dataset_key": dataset_key,
            "analysis_type": "RAMAN",
            "workflow_template_id": "raman.general",
        },
    )
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["execution_status"] == "saved"
    assert run_payload["result_id"].startswith("raman_")

    detail_response = client.get(f"/workspace/{project_id}/results/{run_payload['result_id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["processing"]["workflow_template_id"] == "raman.general"
    assert detail["summary"]["candidate_count"] >= 0

    curves_response = client.get(f"/workspace/{project_id}/analysis-state/RAMAN/{dataset_key}")
    assert curves_response.status_code == 200
    curves = curves_response.json()
    assert "temperature" in curves
    assert "raw_signal" in curves
    assert len(curves["temperature"]) > 0
