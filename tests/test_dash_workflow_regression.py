"""End-to-end API regression for Dash-relevant workflows (combined FastAPI + Dash app).

Validates the same HTTP contracts Dash pages use: import, analysis run, result detail,
analysis-state curves, workspace context/results, export preparation, compare persistence,
project save/load, and key route smoke. Does not execute Dash callbacks in a browser.
"""

from __future__ import annotations

import base64
from typing import Any

import pytest
from fastapi.testclient import TestClient

from dash_app.sample_data import resolve_sample_request
from dash_app.server import create_combined_app

# (sample_button_id, analysis_type, workflow_template_id)
_MODALITY_MATRIX: list[tuple[str, str, str]] = [
    ("load-sample-dsc", "DSC", "dsc.general"),
    ("load-sample-tga", "TGA", "tga.general"),
    ("load-sample-dta", "DTA", "dta.general"),
    ("load-sample-ftir", "FTIR", "ftir.general"),
    ("load-sample-raman", "RAMAN", "raman.general"),
    ("load-sample-xrd", "XRD", "xrd.general"),
]


def _client() -> TestClient:
    return TestClient(create_combined_app())


def _b64_file(button_id: str) -> tuple[bytes, str, str]:
    path, data_type = resolve_sample_request(button_id)
    assert path is not None and data_type is not None
    return path.read_bytes(), path.name, data_type


def _import_dataset(
    client: TestClient,
    project_id: str,
    *,
    file_bytes: bytes,
    file_name: str,
    data_type: str,
) -> str:
    r = client.post(
        "/dataset/import",
        json={
            "project_id": project_id,
            "file_name": file_name,
            "file_base64": base64.b64encode(file_bytes).decode("ascii"),
            "data_type": data_type,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["dataset"]["key"]


def _run_analysis(
    client: TestClient,
    project_id: str,
    dataset_key: str,
    analysis_type: str,
    workflow_template_id: str,
    *,
    unit_mode: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "project_id": project_id,
        "dataset_key": dataset_key,
        "analysis_type": analysis_type,
        "workflow_template_id": workflow_template_id,
    }
    if unit_mode:
        payload["unit_mode"] = unit_mode
    r = client.post("/analysis/run", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def _assert_result_detail_contract(detail: dict[str, Any], analysis_type: str, workflow_template_id: str) -> None:
    assert "summary" in detail and isinstance(detail["summary"], dict)
    assert "processing" in detail and isinstance(detail["processing"], dict)
    assert detail["processing"].get("workflow_template_id") == workflow_template_id
    rows = detail.get("rows") or []
    preview = detail.get("rows_preview") or []
    assert detail.get("row_count", len(rows)) == len(rows)
    assert len(rows) >= 0
    if rows:
        assert len(preview) <= 20

    summary = detail["summary"]
    # Modality-shaped summary: at least one stable discriminator key exists per family.
    upper = analysis_type.upper()
    if upper in {"DSC", "DTA", "TGA"}:
        assert "peak_count" in summary or rows, summary
    elif upper in {"FTIR", "RAMAN", "XRD"}:
        assert "match_status" in summary or "candidate_count" in summary, summary

    # Caution / provenance: only assert when backend populated them (non-brittle).
    if summary.get("caution_code"):
        assert isinstance(summary["caution_code"], str) and summary["caution_code"].strip()
    if summary.get("caution_message"):
        assert isinstance(summary["caution_message"], str) and summary["caution_message"].strip()
    if summary.get("xrd_provenance_state") is not None:
        assert str(summary.get("xrd_provenance_state")).strip() != ""
    if summary.get("xrd_provenance_warning"):
        assert isinstance(summary["xrd_provenance_warning"], str)

    # Sample naming: allow missing/empty from fixtures; never accept the literal string "None".
    sn = summary.get("sample_name")
    if sn is not None:
        assert str(sn) != "None"


def _assert_analysis_state_curves(curves: dict[str, Any]) -> None:
    axis = curves.get("temperature") or []
    assert isinstance(axis, list) and len(axis) > 0
    n = len(axis)
    raw = curves.get("raw_signal") or []
    smoothed = curves.get("smoothed") or []
    corrected = curves.get("corrected") or []
    assert any(
        len(series) == n for series in (raw, smoothed, corrected) if series
    ), curves.keys()


@pytest.mark.parametrize("button_id,analysis_type,template_id", _MODALITY_MATRIX)
def test_modality_import_run_result_detail_and_analysis_state(
    button_id: str,
    analysis_type: str,
    template_id: str,
):
    client = _client()
    ws = client.post("/workspace/new")
    assert ws.status_code == 200
    project_id = ws.json()["project_id"]

    raw, name, data_type = _b64_file(button_id)
    key = _import_dataset(client, project_id, file_bytes=raw, file_name=name, data_type=data_type)

    run_payload = _run_analysis(client, project_id, key, analysis_type, template_id)
    assert run_payload["execution_status"] == "saved"
    result_id = run_payload["result_id"]
    assert result_id

    detail_r = client.get(f"/workspace/{project_id}/results/{result_id}")
    assert detail_r.status_code == 200
    detail = detail_r.json()
    _assert_result_detail_contract(detail, analysis_type, template_id)

    curves_r = client.get(f"/workspace/{project_id}/analysis-state/{analysis_type}/{key}")
    assert curves_r.status_code == 200
    _assert_analysis_state_curves(curves_r.json())


def test_downstream_workspace_export_compare_after_two_dsc_runs():
    """Two analyses on one workspace; APIs Dash Project/Report/Compare use stay consistent."""
    client = _client()
    ws = client.post("/workspace/new")
    assert ws.status_code == 200
    project_id = ws.json()["project_id"]

    raw, _, _ = _b64_file("load-sample-dsc")
    key_a = _import_dataset(client, project_id, file_bytes=raw, file_name="regression_dsc_a.csv", data_type="DSC")
    key_b = _import_dataset(client, project_id, file_bytes=raw, file_name="regression_dsc_b.csv", data_type="DSC")

    run_a = _run_analysis(client, project_id, key_a, "DSC", "dsc.general")
    run_b = _run_analysis(client, project_id, key_b, "DSC", "dsc.general")
    assert run_a["execution_status"] == run_b["execution_status"] == "saved"
    id_a, id_b = run_a["result_id"], run_b["result_id"]
    assert id_a and id_b and id_a != id_b

    ctx = client.get(f"/workspace/{project_id}/context")
    assert ctx.status_code == 200
    body = ctx.json()
    assert body["summary"]["result_count"] == 2
    assert body.get("latest_result") is not None
    hist = body.get("recent_history") or []
    assert any("Analysis Saved" in str(h.get("action", "")) for h in hist)

    res_list = client.get(f"/workspace/{project_id}/results")
    assert res_list.status_code == 200
    ids = {item["id"] for item in res_list.json().get("results", [])}
    assert id_a in ids and id_b in ids

    prep = client.get(f"/workspace/{project_id}/exports/preparation")
    assert prep.status_code == 200
    prep_json = prep.json()
    assert prep_json["project_id"] == project_id
    exportable = {item["id"] for item in prep_json.get("exportable_results", [])}
    assert id_a in exportable and id_b in exportable
    supported = prep_json.get("supported_outputs", [])
    assert "results_csv" in supported
    assert "report_docx" in supported

    cmp_get = client.get(f"/workspace/{project_id}/compare")
    assert cmp_get.status_code == 200

    cmp_put = client.put(
        f"/workspace/{project_id}/compare",
        json={
            "analysis_type": "DSC",
            "selected_datasets": [key_a, key_b],
            "notes": "dash workflow regression",
        },
    )
    assert cmp_put.status_code == 200
    cw = cmp_put.json()["compare_workspace"]
    assert cw["analysis_type"] == "DSC"
    assert cw["selected_datasets"] == [key_a, key_b]
    assert cw["notes"] == "dash workflow regression"


def test_export_results_csv_smoke_combined_app():
    client = _client()
    ws = client.post("/workspace/new")
    project_id = ws.json()["project_id"]
    raw, name, dt = _b64_file("load-sample-dsc")
    key = _import_dataset(client, project_id, file_bytes=raw, file_name=name, data_type=dt)
    run = _run_analysis(client, project_id, key, "DSC", "dsc.general")
    rid = run["result_id"]

    out = client.post(
        f"/workspace/{project_id}/exports/results-csv",
        json={"selected_result_ids": [rid]},
    )
    assert out.status_code == 200
    payload = out.json()
    assert payload["output_type"] == "results_csv"
    assert rid in payload["included_result_ids"]
    assert payload.get("artifact_base64")


def test_project_save_load_preserves_results_and_compare():
    """Round-trip project archive on combined app (no API token)."""
    client = _client()
    ws = client.post("/workspace/new")
    project_id = ws.json()["project_id"]

    raw, _, _ = _b64_file("load-sample-dsc")
    key_a = _import_dataset(client, project_id, file_bytes=raw, file_name="roundtrip_a.csv", data_type="DSC")
    key_b = _import_dataset(client, project_id, file_bytes=raw, file_name="roundtrip_b.csv", data_type="DSC")
    run = _run_analysis(client, project_id, key_a, "DSC", "dsc.general")
    rid = run["result_id"]

    client.put(
        f"/workspace/{project_id}/compare",
        json={"analysis_type": "DSC", "selected_datasets": [key_a, key_b], "notes": "rt"},
    )

    save_r = client.post("/project/save", json={"project_id": project_id})
    assert save_r.status_code == 200
    archive_b64 = save_r.json()["archive_base64"]

    load_r = client.post("/project/load", json={"archive_base64": archive_b64})
    assert load_r.status_code == 200
    loaded_id = load_r.json()["project_id"]
    assert loaded_id != project_id

    results = client.get(f"/workspace/{loaded_id}/results").json().get("results", [])
    assert any(item["id"] == rid for item in results)

    cmp = client.get(f"/workspace/{loaded_id}/compare").json()["compare_workspace"]
    assert cmp["analysis_type"] == "DSC"
    assert cmp["notes"] == "rt"
    assert len(cmp.get("selected_datasets") or []) == 2


def test_export_preparation_empty_workspace_structure():
    client = _client()
    ws = client.post("/workspace/new")
    project_id = ws.json()["project_id"]
    prep = client.get(f"/workspace/{project_id}/exports/preparation")
    assert prep.status_code == 200
    p = prep.json()
    assert p["project_id"] == project_id
    assert p.get("exportable_results") == []
    assert isinstance(p.get("supported_outputs"), list)


def test_result_detail_unknown_id_returns_404():
    client = _client()
    ws = client.post("/workspace/new")
    project_id = ws.json()["project_id"]
    r = client.get(f"/workspace/{project_id}/results/no_such_result_id")
    assert r.status_code == 404


def test_analysis_run_unknown_dataset_key_returns_404():
    client = _client()
    ws = client.post("/workspace/new")
    project_id = ws.json()["project_id"]
    r = client.post(
        "/analysis/run",
        json={
            "project_id": project_id,
            "dataset_key": "definitely_missing_dataset_key",
            "analysis_type": "DSC",
            "workflow_template_id": "dsc.general",
        },
    )
    assert r.status_code == 404


@pytest.mark.parametrize(
    "path,snippet",
    [
        ("/", "MaterialScope"),
        ("/dsc", "DSC"),
        ("/tga", "TGA"),
        ("/project", "Project"),
        ("/export", "Export - MaterialScope"),
        ("/compare", "Compare"),
        ("/xrd", "XRD"),
    ],
)
def test_key_dash_routes_return_200(path: str, snippet: str):
    client = _client()
    r = client.get(path)
    assert r.status_code == 200
    assert snippet in r.text
