"""Tests for Dash Compare Phase 2 (curve utils, batch API, layout source)."""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest

_ROOT = str(Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def test_axis_titles_spectral_and_xrd():
    from dash_app.compare_curve_utils import axis_titles

    assert "Wavenumber" in axis_titles("FTIR")[0]
    assert "Raman" in axis_titles("RAMAN")[0]
    assert "2theta" in axis_titles("XRD")[0].lower()


def test_pick_best_series_prefers_corrected_then_smoothed_then_raw():
    from dash_app.compare_curve_utils import pick_best_series

    x = [1.0, 2.0, 3.0]
    curves = {"temperature": x, "corrected": [0.1, 0.2, 0.3], "smoothed": [1.0, 2.0], "raw_signal": [5.0, 6.0, 7.0]}
    xs, ys, src = pick_best_series(curves)
    assert xs == x and ys == curves["corrected"] and src == "corrected"

    curves2 = {"temperature": x, "corrected": [], "smoothed": [1.0, 2.0, 3.0], "raw_signal": [5.0, 6.0, 7.0]}
    xs2, ys2, src2 = pick_best_series(curves2)
    assert ys2 == curves2["smoothed"] and src2 == "smoothed"

    curves3 = {"temperature": x, "corrected": [], "smoothed": [], "raw_signal": [5.0, 6.0, 7.0]}
    xs3, ys3, src3 = pick_best_series(curves3)
    assert ys3 == curves3["raw_signal"] and src3 == "raw"

    assert pick_best_series({"temperature": [], "raw_signal": []}) is None


def test_workspace_batch_run_persists_compare_workspace_combined_app():
    from fastapi.testclient import TestClient

    from dash_app.sample_data import resolve_sample_request
    from dash_app.server import create_combined_app

    app = create_combined_app()
    client = TestClient(app)

    ws = client.post("/workspace/new")
    assert ws.status_code == 200
    project_id = ws.json()["project_id"]

    sample_path, _ = resolve_sample_request("load-sample-dsc")
    assert sample_path is not None
    raw = sample_path.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")

    def _import(name: str) -> str:
        r = client.post(
            "/dataset/import",
            json={
                "project_id": project_id,
                "file_name": name,
                "file_base64": b64,
                "data_type": "DSC",
            },
        )
        assert r.status_code == 200
        return r.json()["dataset"]["key"]

    key_a = _import("compare_batch_a.csv")
    key_b = _import("compare_batch_b.csv")

    put = client.put(
        f"/workspace/{project_id}/compare",
        json={"analysis_type": "DSC", "selected_datasets": [key_a, key_b], "notes": "phase2"},
    )
    assert put.status_code == 200

    batch = client.post(
        f"/workspace/{project_id}/batch/run",
        json={"analysis_type": "DSC", "workflow_template_id": "dsc.general", "dataset_keys": [key_a, key_b]},
    )
    assert batch.status_code == 200
    payload = batch.json()
    assert payload["outcomes"]["saved"] == 2
    assert len(payload["batch_summary"]) == 2
    assert payload["workflow_template_id"] == "dsc.general"

    cmp = client.get(f"/workspace/{project_id}/compare").json()["compare_workspace"]
    assert cmp["analysis_type"] == "DSC"
    assert cmp["notes"] == "phase2"
    assert cmp.get("batch_last_feedback", {}).get("saved") == 2
    assert len(cmp.get("batch_summary") or []) == 2


def test_compare_page_source_contains_phase2_controls():
    """Avoid importing the page module (duplicate register_page vs Dash pages_folder)."""
    text = (Path(__file__).resolve().parent.parent / "dash_app" / "pages" / "compare.py").read_text(encoding="utf-8")
    for needle in ("compare-signal-mode", "compare-batch-template-select", "compare-batch-run-btn", "compare-batch-summary-panel"):
        assert needle in text


def test_two_dsc_runs_expose_analysis_state_for_best_overlay():
    """Combined-app: after saved DSC runs, analysis-state supports pick_best_series (Compare best mode)."""
    from fastapi.testclient import TestClient

    from dash_app.compare_curve_utils import pick_best_series
    from dash_app.sample_data import resolve_sample_request
    from dash_app.server import create_combined_app

    client = TestClient(create_combined_app())
    ws = client.post("/workspace/new")
    project_id = ws.json()["project_id"]
    sample_path, _ = resolve_sample_request("load-sample-dsc")
    b64 = base64.b64encode(sample_path.read_bytes()).decode("ascii")

    def _import(name: str) -> str:
        r = client.post(
            "/dataset/import",
            json={"project_id": project_id, "file_name": name, "file_base64": b64, "data_type": "DSC"},
        )
        assert r.status_code == 200
        return r.json()["dataset"]["key"]

    ka, kb = _import("overlay_a.csv"), _import("overlay_b.csv")
    for key in (ka, kb):
        run = client.post(
            "/analysis/run",
            json={"project_id": project_id, "dataset_key": key, "analysis_type": "DSC", "workflow_template_id": "dsc.general"},
        )
        assert run.status_code == 200
        assert run.json()["execution_status"] == "saved"

    for key in (ka, kb):
        curves = client.get(f"/workspace/{project_id}/analysis-state/DSC/{key}").json()
        picked = pick_best_series(curves)
        assert picked is not None, curves.keys()
        xs, ys, src = picked
        assert len(xs) == len(ys) > 0 and src in ("corrected", "smoothed", "raw")
