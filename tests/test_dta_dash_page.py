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
from dash import dcc, html


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


def test_layout_places_figure_before_peak_cards():
    mod = _import_dta_page()
    layout_str = str(mod.layout)
    assert layout_str.index("dta-result-figure") < layout_str.index("dta-result-peak-cards")


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


def test_build_peak_cards_compacts_secondary_events():
    mod = _import_dta_page()

    rows = [
        {
            "direction": "exo" if idx % 2 == 0 else "endo",
            "peak_temperature": 120.0 + idx * 15.0,
            "onset_temperature": 115.0 + idx * 15.0,
            "endset_temperature": 125.0 + idx * 15.0,
            "area": float(10 - idx),
            "height": float(5 - idx * 0.2),
        }
        for idx in range(6)
    ]
    result = mod._build_peak_cards(rows)
    result_html = str(result)
    assert result_html.count("Peak ") == 4
    assert "Show 2 additional event(s)" in result_html


def test_derive_event_metrics_falls_back_to_rows_when_summary_counts_missing():
    mod = _import_dta_page()

    peak_count, exo_count, endo_count = mod._derive_event_metrics(
        {"peak_count": 3},
        [
            {"peak_type": "exo"},
            {"peak_type": "endotherm"},
            {"direction": "exo"},
        ],
    )

    assert peak_count == 3
    assert exo_count == 2
    assert endo_count == 1


def test_derive_event_metrics_prefers_rows_over_stale_summary_counts():
    mod = _import_dta_page()

    peak_count, exo_count, endo_count = mod._derive_event_metrics(
        {"peak_count": 9, "exotherm_count": 0, "endotherm_count": 0},
        [
            {"direction": "exo"},
            {"direction": "endo"},
        ],
    )

    assert peak_count == 2
    assert exo_count == 1
    assert endo_count == 1


def test_resolve_dta_sample_name_prefers_dataset_display_name_over_unknown():
    mod = _import_dta_page()

    sample_name = mod._resolve_dta_sample_name(
        {"sample_name": "Unknown"},
        {"dataset_key": "dta_run.csv"},
        {
            "dataset": {"display_name": "Ore Blend DTA Run"},
            "metadata": {"sample_name": "Ore Blend"},
        },
    )

    assert sample_name == "Ore Blend DTA Run"


def test_resolve_dta_sample_name_prefers_sample_name_over_file_name():
    mod = _import_dta_page()

    sample_name = mod._resolve_dta_sample_name(
        {"sample_name": "Unknown"},
        {"dataset_key": "dta_run.csv"},
        {
            "dataset": {"display_name": ""},
            "metadata": {"file_name": "raw_run.csv", "sample_name": "Ore Blend"},
        },
    )

    assert sample_name == "Ore Blend"


def test_resolve_dta_sample_name_prefers_workspace_display_when_summary_is_file_like_token():
    """Low-signal summary (mirrors file name or dataset-key stem) must not hide display_name."""
    mod = _import_dta_page()

    assert (
        mod._resolve_dta_sample_name(
            {"sample_name": "lab_import.csv"},
            {"dataset_key": "proj_lab_import_01.csv"},
            {
                "dataset": {"display_name": "Li-Ion Cell Batch A"},
                "metadata": {"file_name": "lab_import.csv"},
            },
        )
        == "Li-Ion Cell Batch A"
    )

    assert (
        mod._resolve_dta_sample_name(
            {"sample_name": "proj_run_dta"},
            {"dataset_key": "proj_run_dta.xlsx"},
            {
                "dataset": {"display_name": "Furnace Ramp Study"},
                "metadata": {},
            },
        )
        == "Furnace Ramp Study"
    )


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
    assert "All Event Details" in result_html


def test_build_figure_uses_corrected_as_primary_trace(monkeypatch):
    mod = _import_dta_page()
    import dash_app.api_client as api_client

    monkeypatch.setattr(
        api_client,
        "analysis_state_curves",
        lambda _project_id, _analysis_type, _dataset_key: {
            "temperature": [100.0, 150.0, 200.0, 250.0],
            "raw_signal": [0.0, 1.2, -0.3, 0.6],
            "smoothed": [0.1, 1.0, -0.1, 0.5],
            "baseline": [0.05, 0.05, 0.05, 0.05],
            "corrected": [0.05, 0.95, -0.15, 0.45],
        },
    )

    graph = mod._build_figure(
        "proj-1",
        "dataset-1",
        "Synthetic DTA Run",
        [
            {
                "direction": "exo",
                "peak_temperature": 150.0,
                "onset_temperature": 140.0,
                "endset_temperature": 165.0,
                "area": 2.5,
                "height": 0.8,
            }
        ],
        "light",
    )

    assert isinstance(graph, dcc.Graph)
    corrected_trace = next(trace for trace in graph.figure.data if trace.name == "Corrected Signal")
    raw_trace = next(trace for trace in graph.figure.data if trace.name == "Raw Signal")
    assert corrected_trace.line.width == 2.8
    assert raw_trace.opacity < 0.3
    assert graph.figure.layout.height == 560
    assert graph.figure.layout.yaxis.range is not None
    assert len(graph.figure.layout.shapes) >= 2


def test_build_figure_handles_missing_primary_signal(monkeypatch):
    mod = _import_dta_page()
    import dash_app.api_client as api_client

    monkeypatch.setattr(
        api_client,
        "analysis_state_curves",
        lambda _project_id, _analysis_type, _dataset_key: {
            "temperature": [100.0, 150.0, 200.0],
            "raw_signal": [0.0, 1.0],
            "smoothed": [],
            "baseline": [0.1, 0.1, 0.1],
            "corrected": [],
        },
    )

    result = mod._build_figure(
        "proj-1",
        "dataset-1",
        "Synthetic DTA Run",
        [{"direction": "exo", "peak_temperature": 150.0}],
        "light",
    )

    assert isinstance(result, html.P)
    assert "No processed DTA signal is available" in str(result)


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
    assert isinstance(detail["rows"], list)
    assert detail["row_count"] == len(detail["rows"])
    assert "exotherm_count" in detail["summary"]
    assert "endotherm_count" in detail["summary"]

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


# ---------------------------------------------------------------------------
# Phase 1: smoothing draft / undo / redo / reset helpers
# ---------------------------------------------------------------------------

def test_default_processing_draft_matches_template_smoothing_defaults():
    mod = _import_dta_page()

    defaults = mod._default_processing_draft()
    assert defaults["smoothing"] == {
        "method": "savgol",
        "window_length": 11,
        "polyorder": 3,
    }


def test_normalize_smoothing_values_enforces_odd_window_and_bounds():
    mod = _import_dta_page()

    savgol = mod._normalize_smoothing_values("savgol", window_length=12, polyorder=3, sigma=None)
    assert savgol == {"method": "savgol", "window_length": 13, "polyorder": 3}

    mov_avg = mod._normalize_smoothing_values("moving_average", window_length=8, polyorder=None, sigma=None)
    assert mov_avg == {"method": "moving_average", "window_length": 9}

    gauss = mod._normalize_smoothing_values("gaussian", window_length=None, polyorder=None, sigma=1.5)
    assert gauss == {"method": "gaussian", "sigma": 1.5}

    # Unknown method falls back to savgol defaults (sanitizes bad input)
    fallback = mod._normalize_smoothing_values("exotic", window_length=15, polyorder=3, sigma=None)
    assert fallback == {"method": "savgol", "window_length": 15, "polyorder": 3}


def test_apply_draft_section_does_not_mutate_input():
    mod = _import_dta_page()

    base = mod._default_processing_draft()
    next_draft = mod._apply_draft_section(
        base, "smoothing", {"method": "gaussian", "sigma": 3.5}
    )

    assert base["smoothing"]["method"] == "savgol"  # unchanged
    assert next_draft["smoothing"] == {"method": "gaussian", "sigma": 3.5}


def test_undo_redo_cycle_restores_previous_and_future_drafts():
    mod = _import_dta_page()

    draft0 = mod._default_processing_draft()
    draft1 = mod._apply_draft_section(
        draft0, "smoothing", {"method": "savgol", "window_length": 21, "polyorder": 3}
    )
    undo_stack = mod._push_undo([], draft0)

    # Undo brings draft0 back and pushes draft1 onto redo
    restored, undo_after, redo_after = mod._do_undo(draft1, undo_stack, [])
    assert restored == draft0
    assert undo_after == []
    assert redo_after == [draft1]

    # Redo restores draft1 and pushes draft0 back onto undo
    reapplied, undo_next, redo_next = mod._do_redo(restored, undo_after, redo_after)
    assert reapplied == draft1
    assert undo_next == [draft0]
    assert redo_next == []


def test_undo_on_empty_stack_is_noop():
    mod = _import_dta_page()

    draft = mod._default_processing_draft()
    restored, undo_after, redo_after = mod._do_undo(draft, [], [])
    assert restored == draft
    assert undo_after == []
    assert redo_after == []


def test_reset_restores_defaults_and_pushes_current_to_undo():
    mod = _import_dta_page()

    defaults = mod._default_processing_draft()
    draft = mod._apply_draft_section(
        defaults, "smoothing", {"method": "gaussian", "sigma": 4.0}
    )

    next_draft, next_undo, next_redo = mod._do_reset(draft, [], [{"stale": True}], defaults)
    assert next_draft == defaults
    assert next_undo == [draft]
    # Reset clears redo stack even when previously populated
    assert next_redo == []

    # Reset when already at defaults is a no-op (does not push to undo)
    same_draft, same_undo, same_redo = mod._do_reset(defaults, [], [], defaults)
    assert same_draft == defaults
    assert same_undo == []
    assert same_redo == []


def test_smoothing_overrides_from_draft_returns_only_smoothing_section():
    mod = _import_dta_page()

    assert mod._smoothing_overrides_from_draft(None) == {}
    assert mod._smoothing_overrides_from_draft({}) == {}
    overrides = mod._smoothing_overrides_from_draft(
        {"smoothing": {"method": "savgol", "window_length": 21, "polyorder": 3}, "other": {}}
    )
    assert overrides == {"smoothing": {"method": "savgol", "window_length": 21, "polyorder": 3}}


def test_layout_includes_phase1_stores_and_smoothing_controls():
    mod = _import_dta_page()

    layout_str = str(mod.layout)
    for element_id in (
        "dta-processing-default",
        "dta-processing-draft",
        "dta-processing-undo",
        "dta-processing-redo",
        "dta-smooth-method",
        "dta-smooth-window",
        "dta-smooth-polyorder",
        "dta-smooth-sigma",
        "dta-smooth-apply-btn",
        "dta-undo-btn",
        "dta-redo-btn",
        "dta-reset-btn",
        "dta-smooth-status",
    ):
        assert element_id in layout_str, f"Missing Phase 1 element: {element_id}"


# ---------------------------------------------------------------------------
# Phase 1: backend override propagation via /analysis/run
# ---------------------------------------------------------------------------

def test_dta_analysis_run_honors_smoothing_overrides():
    """Per-step overrides must win over template defaults in persisted processing."""
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

    run_response = client.post(
        "/analysis/run",
        json={
            "project_id": project_id,
            "dataset_key": dataset_key,
            "analysis_type": "DTA",
            "workflow_template_id": "dta.general",
            "processing_overrides": {
                "smoothing": {"method": "savgol", "window_length": 21, "polyorder": 3},
            },
        },
    )
    assert run_response.status_code == 200, run_response.text
    run_payload = run_response.json()
    assert run_payload["execution_status"] == "saved"
    result_id = run_payload["result_id"]

    detail = client.get(f"/workspace/{project_id}/results/{result_id}").json()
    smoothing = (detail.get("processing") or {}).get("signal_pipeline", {}).get("smoothing", {})
    assert smoothing.get("window_length") == 21
    assert smoothing.get("method") == "savgol"


def test_dta_analysis_run_rejects_unsupported_override_section():
    """Unknown processing sections for DTA must return a 400."""
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

    run_response = client.post(
        "/analysis/run",
        json={
            "project_id": project_id,
            "dataset_key": dataset_key,
            "analysis_type": "DTA",
            "workflow_template_id": "dta.general",
            # normalization is NOT a DTA pipeline section
            "processing_overrides": {"normalization": {"method": "vector"}},
        },
    )
    assert run_response.status_code == 400, run_response.text


def test_dta_api_client_forwards_processing_overrides(monkeypatch):
    """dash_app.api_client.analysis_run must forward processing_overrides in the POST body."""
    import dash_app.api_client as api_client

    captured: dict = {}

    class _FakeResponse:
        status_code = 200

        def json(self):
            return {"execution_status": "saved", "result_id": "dta_fake"}

        def raise_for_status(self):
            return None

    class _FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def post(self, url, json=None):  # noqa: A002 - match httpx signature
            captured["url"] = url
            captured["json"] = json
            return _FakeResponse()

    monkeypatch.setattr(api_client, "_client", lambda: _FakeClient())
    monkeypatch.setattr(api_client, "_raise_with_detail", lambda _r: None)

    result = api_client.analysis_run(
        project_id="proj-1",
        dataset_key="ds-1",
        analysis_type="DTA",
        workflow_template_id="dta.general",
        processing_overrides={"smoothing": {"method": "savgol", "window_length": 21, "polyorder": 3}},
    )
    assert result == {"execution_status": "saved", "result_id": "dta_fake"}
    assert captured["url"] == "/analysis/run"
    assert captured["json"]["processing_overrides"] == {
        "smoothing": {"method": "savgol", "window_length": 21, "polyorder": 3}
    }


# ---------------------------------------------------------------------------
# Phase 2a: baseline + peak-detection draft helpers + layout + backend parity
# ---------------------------------------------------------------------------

def test_default_processing_draft_includes_baseline_and_peak_sections():
    """Phase 2a extends the draft so the shared undo/redo/reset stack covers all controls."""
    mod = _import_dta_page()

    defaults = mod._default_processing_draft()
    assert defaults["baseline"] == {"method": "asls", "lam": 1e6, "p": 0.01}
    assert defaults["peak_detection"] == {
        "detect_endothermic": True,
        "detect_exothermic": True,
        "prominence": 0.0,
        "distance": 1,
    }
    assert set(defaults) == {"smoothing", "baseline", "peak_detection"}


def test_normalize_baseline_values_gates_asls_params():
    mod = _import_dta_page()

    asls = mod._normalize_baseline_values("asls", lam=50000, p=0.02)
    assert asls == {"method": "asls", "lam": 50000.0, "p": 0.02}

    linear = mod._normalize_baseline_values("linear", lam=123, p=0.5)
    assert linear == {"method": "linear"}

    rubber = mod._normalize_baseline_values("rubberband", lam=None, p=None)
    assert rubber == {"method": "rubberband"}

    fallback = mod._normalize_baseline_values("exotic", lam=None, p=None)
    assert fallback == {"method": "asls", "lam": 1e6, "p": 0.01}

    clamped = mod._normalize_baseline_values("asls", lam=-5, p=1.5)
    assert clamped["method"] == "asls"
    assert clamped["lam"] == 1e-3
    assert clamped["p"] == 0.5


def test_normalize_peak_detection_values_coerces_inputs():
    mod = _import_dta_page()

    defaults = mod._normalize_peak_detection_values(True, True, 0.0, 1)
    assert defaults == {
        "detect_endothermic": True,
        "detect_exothermic": True,
        "prominence": 0.0,
        "distance": 1,
    }

    tuned = mod._normalize_peak_detection_values(False, True, "0.05", "5")
    assert tuned == {
        "detect_endothermic": False,
        "detect_exothermic": True,
        "prominence": 0.05,
        "distance": 5,
    }

    clamped = mod._normalize_peak_detection_values(None, None, -1.0, 0)
    assert clamped == {
        "detect_endothermic": True,
        "detect_exothermic": True,
        "prominence": 0.0,
        "distance": 1,
    }


def test_baseline_and_peak_overrides_extractors_return_only_their_sections():
    mod = _import_dta_page()

    assert mod._baseline_overrides_from_draft(None) == {}
    assert mod._baseline_overrides_from_draft({"smoothing": {}}) == {}
    baseline = mod._baseline_overrides_from_draft(
        {"baseline": {"method": "linear"}, "other": {}}
    )
    assert baseline == {"baseline": {"method": "linear"}}

    assert mod._peak_detection_overrides_from_draft(None) == {}
    assert mod._peak_detection_overrides_from_draft({"baseline": {}}) == {}
    peaks = mod._peak_detection_overrides_from_draft(
        {"peak_detection": {"prominence": 0.05, "distance": 5}}
    )
    assert peaks == {"peak_detection": {"prominence": 0.05, "distance": 5}}


def test_overrides_from_draft_unions_all_sections():
    mod = _import_dta_page()

    assert mod._overrides_from_draft(None) == {}
    assert mod._overrides_from_draft({"unrelated": {"x": 1}}) == {}

    draft = {
        "smoothing": {"method": "savgol", "window_length": 21, "polyorder": 3},
        "baseline": {"method": "linear"},
        "peak_detection": {"prominence": 0.02, "distance": 4},
        "junk": {"ignored": True},
    }
    combined = mod._overrides_from_draft(draft)
    assert combined == {
        "smoothing": {"method": "savgol", "window_length": 21, "polyorder": 3},
        "baseline": {"method": "linear"},
        "peak_detection": {"prominence": 0.02, "distance": 4},
    }
    # Returned dict must be an independent deep copy
    combined["smoothing"]["window_length"] = 99
    assert draft["smoothing"]["window_length"] == 21


def test_layout_includes_phase2a_baseline_and_peak_controls():
    mod = _import_dta_page()

    layout_str = str(mod.layout)
    for element_id in (
        "dta-baseline-card-title",
        "dta-baseline-method",
        "dta-baseline-lam",
        "dta-baseline-p",
        "dta-baseline-apply-btn",
        "dta-baseline-status",
        "dta-peak-card-title",
        "dta-peak-detect-exo",
        "dta-peak-detect-endo",
        "dta-peak-prominence",
        "dta-peak-distance",
        "dta-peak-apply-btn",
        "dta-peak-status",
    ):
        assert element_id in layout_str, f"Missing Phase 2a element: {element_id}"


def test_dta_analysis_run_honors_baseline_and_peak_overrides():
    """Baseline + peak_detection overrides must reach persisted processing for DTA."""
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

    run_response = client.post(
        "/analysis/run",
        json={
            "project_id": project_id,
            "dataset_key": dataset_key,
            "analysis_type": "DTA",
            "workflow_template_id": "dta.general",
            "processing_overrides": {
                "baseline": {"method": "linear"},
                "peak_detection": {
                    "detect_endothermic": True,
                    "detect_exothermic": True,
                    "prominence": 0.01,
                    "distance": 5,
                },
            },
        },
    )
    assert run_response.status_code == 200, run_response.text
    run_payload = run_response.json()
    assert run_payload["execution_status"] == "saved"
    result_id = run_payload["result_id"]

    detail = client.get(f"/workspace/{project_id}/results/{result_id}").json()
    processing = detail.get("processing") or {}
    baseline = processing.get("signal_pipeline", {}).get("baseline", {})
    peaks = processing.get("analysis_steps", {}).get("peak_detection", {})
    assert baseline.get("method") == "linear"
    assert peaks.get("prominence") == 0.01
    assert peaks.get("distance") == 5


def test_dta_api_client_forwards_baseline_and_peak_overrides(monkeypatch):
    """api_client.analysis_run must carry a multi-section processing_overrides payload."""
    import dash_app.api_client as api_client

    captured: dict = {}

    class _FakeResponse:
        status_code = 200

        def json(self):
            return {"execution_status": "saved", "result_id": "dta_multi"}

        def raise_for_status(self):
            return None

    class _FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def post(self, url, json=None):  # noqa: A002 - match httpx signature
            captured["url"] = url
            captured["json"] = json
            return _FakeResponse()

    monkeypatch.setattr(api_client, "_client", lambda: _FakeClient())
    monkeypatch.setattr(api_client, "_raise_with_detail", lambda _r: None)

    payload = {
        "smoothing": {"method": "savgol", "window_length": 15, "polyorder": 3},
        "baseline": {"method": "asls", "lam": 500000.0, "p": 0.02},
        "peak_detection": {
            "detect_endothermic": True,
            "detect_exothermic": False,
            "prominence": 0.03,
            "distance": 6,
        },
    }
    api_client.analysis_run(
        project_id="proj-2",
        dataset_key="ds-2",
        analysis_type="DTA",
        workflow_template_id="dta.general",
        processing_overrides=payload,
    )
    assert captured["json"]["processing_overrides"] == payload


# ---------------------------------------------------------------------------
# Phase 2b: literature compare panel + figure capture for Report Center
# ---------------------------------------------------------------------------


def test_layout_includes_phase2b_literature_and_figure_capture():
    mod = _import_dta_page()

    layout_str = str(mod.layout)
    for element_id in (
        "dta-literature-card-title",
        "dta-literature-hint",
        "dta-literature-max-claims",
        "dta-literature-persist",
        "dta-literature-compare-btn",
        "dta-literature-status",
        "dta-literature-output",
        "dta-figure-captured",
    ):
        assert element_id in layout_str, f"Missing Phase 2b element: {element_id}"


def test_dta_api_client_literature_compare_forwards_payload(monkeypatch):
    """api_client.literature_compare must POST to the per-result endpoint with options."""
    import dash_app.api_client as api_client

    captured: dict = {}

    class _FakeResponse:
        status_code = 200

        def json(self):
            return {
                "project_id": "proj-42",
                "result_id": "dta_1",
                "literature_context": {"count": 1},
                "literature_claims": [{"statement": "T_peak ~ 350 C", "source": "doi:1"}],
                "literature_comparisons": [],
                "citations": [],
            }

        def raise_for_status(self):
            return None

    class _FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def post(self, url, json=None):  # noqa: A002 - match httpx signature
            captured["url"] = url
            captured["json"] = json
            return _FakeResponse()

    monkeypatch.setattr(api_client, "_client", lambda: _FakeClient())
    monkeypatch.setattr(api_client, "_raise_with_detail", lambda _r: None)

    result = api_client.literature_compare(
        "proj-42",
        "dta_1",
        max_claims=5,
        persist=True,
        provider_ids=["openalex_like_provider"],
        filters={"min_year": 2000},
        user_documents=[{"title": "local note"}],
    )
    assert captured["url"] == "/workspace/proj-42/results/dta_1/literature/compare"
    assert captured["json"] == {
        "max_claims": 5,
        "persist": True,
        "provider_ids": ["openalex_like_provider"],
        "filters": {"min_year": 2000},
        "user_documents": [{"title": "local note"}],
    }
    assert result["literature_claims"][0]["statement"] == "T_peak ~ 350 C"


def test_dta_api_client_register_result_figure_forwards_base64(monkeypatch):
    """api_client.register_result_figure must POST base64-encoded PNG bytes."""
    import base64 as _b64

    import dash_app.api_client as api_client

    captured: dict = {}

    class _FakeResponse:
        status_code = 200

        def json(self):
            return {
                "project_id": "proj-7",
                "result_id": "dta_x",
                "figure_key": "DTA Analysis - ds-1",
                "figure_keys": ["DTA Analysis - ds-1"],
            }

        def raise_for_status(self):
            return None

    class _FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def post(self, url, json=None):  # noqa: A002 - match httpx signature
            captured["url"] = url
            captured["json"] = json
            return _FakeResponse()

    monkeypatch.setattr(api_client, "_client", lambda: _FakeClient())
    monkeypatch.setattr(api_client, "_raise_with_detail", lambda _r: None)

    png_bytes = b"\x89PNG\r\n\x1a\nFAKE"
    result = api_client.register_result_figure(
        "proj-7",
        "dta_x",
        png_bytes,
        label="DTA Analysis - ds-1",
        replace=True,
    )
    assert captured["url"] == "/workspace/proj-7/results/dta_x/figure"
    body = captured["json"]
    assert body["figure_label"] == "DTA Analysis - ds-1"
    assert body["replace"] is True
    assert _b64.b64decode(body["figure_png_base64"].encode("ascii")) == png_bytes
    assert result["figure_key"] == "DTA Analysis - ds-1"


def test_backend_register_figure_writes_state_and_artifacts():
    """POST /workspace/{pid}/results/{rid}/figure registers PNG + updates figure_keys."""
    import base64 as _b64

    from fastapi.testclient import TestClient
    from dash_app.sample_data import resolve_sample_request
    from dash_app.server import create_combined_app

    app = create_combined_app()
    client = TestClient(app)

    project_id = client.post("/workspace/new").json()["project_id"]
    sample_path, _ = resolve_sample_request("load-sample-dsc")
    payload = _b64.b64encode(sample_path.read_bytes()).decode("ascii")
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
    run = client.post(
        "/analysis/run",
        json={
            "project_id": project_id,
            "dataset_key": dataset_key,
            "analysis_type": "DTA",
            "workflow_template_id": "dta.general",
        },
    ).json()
    result_id = run["result_id"]
    assert result_id

    png = b"\x89PNG\r\n\x1a\nFIG-BYTES"
    register = client.post(
        f"/workspace/{project_id}/results/{result_id}/figure",
        json={
            "figure_png_base64": _b64.b64encode(png).decode("ascii"),
            "figure_label": f"DTA Analysis - {dataset_key}",
        },
    )
    assert register.status_code == 200, register.text
    body = register.json()
    assert body["figure_key"] == f"DTA Analysis - {dataset_key}"
    assert body["figure_keys"] == [f"DTA Analysis - {dataset_key}"]

    summary = client.get(f"/workspace/{project_id}").json()
    assert summary["summary"]["figure_count"] == 1

    # Re-register same label without replace → 409 conflict.
    conflict = client.post(
        f"/workspace/{project_id}/results/{result_id}/figure",
        json={
            "figure_png_base64": _b64.b64encode(png).decode("ascii"),
            "figure_label": f"DTA Analysis - {dataset_key}",
        },
    )
    assert conflict.status_code == 409, conflict.text

    # Re-register with replace=True → 200 and key still dedup'd.
    replace = client.post(
        f"/workspace/{project_id}/results/{result_id}/figure",
        json={
            "figure_png_base64": _b64.b64encode(b"NEW-BYTES").decode("ascii"),
            "figure_label": f"DTA Analysis - {dataset_key}",
            "replace": True,
        },
    )
    assert replace.status_code == 200, replace.text
    assert replace.json()["figure_keys"] == [f"DTA Analysis - {dataset_key}"]


def test_backend_register_figure_rejects_invalid_inputs():
    """Unknown result_id → 404; empty label → 400; bad base64 → 400."""
    import base64 as _b64

    from fastapi.testclient import TestClient
    from dash_app.sample_data import resolve_sample_request
    from dash_app.server import create_combined_app

    client = TestClient(create_combined_app())
    project_id = client.post("/workspace/new").json()["project_id"]

    unknown = client.post(
        f"/workspace/{project_id}/results/does-not-exist/figure",
        json={"figure_png_base64": "aGVsbG8=", "figure_label": "label"},
    )
    assert unknown.status_code == 404, unknown.text

    # Build a valid saved result to exercise 400 paths against a real rid.
    sample_path, _ = resolve_sample_request("load-sample-dsc")
    payload = _b64.b64encode(sample_path.read_bytes()).decode("ascii")
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
    run = client.post(
        "/analysis/run",
        json={
            "project_id": project_id,
            "dataset_key": dataset_key,
            "analysis_type": "DTA",
            "workflow_template_id": "dta.general",
        },
    ).json()
    result_id = run["result_id"]

    empty_label = client.post(
        f"/workspace/{project_id}/results/{result_id}/figure",
        json={"figure_png_base64": "aGVsbG8=", "figure_label": "   "},
    )
    assert empty_label.status_code == 400, empty_label.text

    bad_b64 = client.post(
        f"/workspace/{project_id}/results/{result_id}/figure",
        json={"figure_png_base64": "!!!not-base64!!!", "figure_label": "label"},
    )
    assert bad_b64.status_code == 400, bad_b64.text


def test_capture_dta_figure_posts_png_once_per_result(monkeypatch):
    """capture_dta_figure renders PNG via plotly.io.to_image and calls register_result_figure once."""
    mod = _import_dta_page()
    import dash_app.api_client as api_client

    detail_payload = {
        "result": {"dataset_key": "ds-xyz", "artifacts": {}},
        "summary": {"sample_name": "Synthetic DTA"},
        "rows": [{"direction": "exo", "peak_temperature": 150.0}],
    }
    dataset_payload = {"dataset": {"sample_name": "Synthetic DTA"}}
    curves_payload = {
        "temperature": [100.0, 150.0, 200.0, 250.0],
        "raw_signal": [0.0, 1.2, -0.3, 0.6],
        "smoothed": [0.1, 1.0, -0.1, 0.5],
        "baseline": [0.05, 0.05, 0.05, 0.05],
        "corrected": [0.05, 0.95, -0.15, 0.45],
    }

    register_calls: list[dict] = []

    monkeypatch.setattr(
        api_client,
        "workspace_result_detail",
        lambda *_a, **_k: detail_payload,
    )
    monkeypatch.setattr(
        api_client,
        "workspace_dataset_detail",
        lambda *_a, **_k: dataset_payload,
    )
    monkeypatch.setattr(
        api_client,
        "analysis_state_curves",
        lambda *_a, **_k: curves_payload,
    )
    monkeypatch.setattr(
        api_client,
        "register_result_figure",
        lambda pid, rid, png_bytes, *, label, replace=False: register_calls.append(
            {"pid": pid, "rid": rid, "bytes": bytes(png_bytes), "label": label, "replace": replace}
        )
        or {"figure_key": label, "figure_keys": [label]},
    )

    import plotly.io as pio

    monkeypatch.setattr(pio, "to_image", lambda *_a, **_k: b"FAKE-PNG")

    captured_first = mod.capture_dta_figure("dta_fake_id", "proj-1", {}, "light", "en")
    assert captured_first["dta_fake_id"]["status"] == "ok"
    assert captured_first["dta_fake_id"]["label"] == "DTA Analysis - ds-xyz"
    assert len(register_calls) == 1
    call = register_calls[0]
    assert call["pid"] == "proj-1"
    assert call["rid"] == "dta_fake_id"
    assert call["label"] == "DTA Analysis - ds-xyz"
    assert call["bytes"] == b"FAKE-PNG"
    assert call["replace"] is True

    import dash as _dash

    with pytest.raises(_dash.exceptions.PreventUpdate):
        mod.capture_dta_figure("dta_fake_id", "proj-1", captured_first, "light", "en")
    assert len(register_calls) == 1


def test_capture_dta_figure_degrades_when_kaleido_missing(monkeypatch):
    """If plotly.io.to_image raises, capture must record the failure without calling register."""
    mod = _import_dta_page()
    import dash_app.api_client as api_client

    monkeypatch.setattr(
        api_client,
        "workspace_result_detail",
        lambda *_a, **_k: {"result": {"dataset_key": "ds-q"}, "summary": {}, "rows": []},
    )
    monkeypatch.setattr(api_client, "workspace_dataset_detail", lambda *_a, **_k: {})
    monkeypatch.setattr(
        api_client,
        "analysis_state_curves",
        lambda *_a, **_k: {
            "temperature": [1.0, 2.0, 3.0],
            "raw_signal": [0.0, 1.0, 0.0],
            "smoothed": [],
            "baseline": [],
            "corrected": [0.0, 1.0, 0.0],
        },
    )

    register_calls: list[dict] = []
    monkeypatch.setattr(
        api_client,
        "register_result_figure",
        lambda *_a, **_k: register_calls.append(_k) or {},
    )

    import plotly.io as pio

    def _raise(*_a, **_k):
        raise RuntimeError("kaleido missing")

    monkeypatch.setattr(pio, "to_image", _raise)

    result = mod.capture_dta_figure("dta_q", "proj-1", {}, "light", "en")
    assert result["dta_q"]["status"] == "skipped"
    assert register_calls == []


def test_compare_dta_literature_renders_claims_and_citations(monkeypatch):
    """Compare click must call api_client.literature_compare and render claims + citations."""
    mod = _import_dta_page()
    import dash_app.api_client as api_client

    payload = {
        "literature_claims": [
            {"statement": "Onset around 350 C", "source": "doi:aaa"},
        ],
        "literature_comparisons": [
            {"summary": "Within 5 C of reference", "provider": "openalex_like_provider"},
        ],
        "citations": [{"title": "Ref Paper", "doi": "doi:aaa"}],
    }
    captured: dict = {}

    def _fake(project_id, result_id, *, max_claims, persist, **_extra):
        captured["args"] = (project_id, result_id, max_claims, persist)
        return payload

    monkeypatch.setattr(api_client, "literature_compare", _fake)

    children, status = mod.compare_dta_literature(
        1,
        "proj-1",
        "dta_fake",
        3,
        ["persist"],
        "en",
    )
    assert captured["args"] == ("proj-1", "dta_fake", 3, True)
    rendered = str(children)
    assert "Onset around 350 C" in rendered
    assert "Within 5 C of reference" in rendered
    assert "Ref Paper" in rendered
    status_text = str(status)
    assert "Literature comparison" in status_text


def test_compare_dta_literature_blocks_without_result_id():
    mod = _import_dta_page()

    import dash

    # No click yet — PreventUpdate
    with pytest.raises(dash.exceptions.PreventUpdate):
        mod.compare_dta_literature(0, "proj-1", None, 3, [], "en")

    # Clicked but no result id — warning alert returned in status slot
    _children, status = mod.compare_dta_literature(1, "proj-1", None, 3, [], "en")
    assert "Run a DTA analysis first" in str(status)


def test_toggle_literature_compare_button_gates_on_result_id():
    mod = _import_dta_page()

    assert mod.toggle_literature_compare_button(None) is True
    assert mod.toggle_literature_compare_button("") is True
    assert mod.toggle_literature_compare_button("dta_42") is False
