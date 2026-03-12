from __future__ import annotations

import base64
import io
import zipfile

import pandas as pd
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.exports import build_export_preparation, generate_report_docx_artifact, generate_results_csv_artifact
from core.data_io import ThermalDataset
from core.processing_schema import ensure_processing_payload, update_processing_step
from core.result_serialization import serialize_spectral_result


def _headers() -> dict[str, str]:
    return {"X-TA-Token": "exports-token"}


def _as_b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _seed_workspace_with_result(
    client: TestClient,
    thermal_dataset,
    *,
    data_type: str = "DSC",
    analysis_type: str = "DSC",
    workflow_template_id: str | None = None,
) -> tuple[str, str]:
    created = client.post("/workspace/new", headers=_headers()).json()
    project_id = created["project_id"]

    csv_bytes = thermal_dataset.data.to_csv(index=False).encode("utf-8")
    imported = client.post(
        "/dataset/import",
        headers=_headers(),
        json={
            "project_id": project_id,
            "file_name": "export_seed.csv",
            "file_base64": _as_b64(csv_bytes),
            "data_type": data_type,
        },
    )
    assert imported.status_code == 200
    dataset_key = imported.json()["dataset"]["key"]

    run = client.post(
        "/analysis/run",
        headers=_headers(),
        json={
            "project_id": project_id,
            "dataset_key": dataset_key,
            "analysis_type": analysis_type,
            "workflow_template_id": workflow_template_id or f"{analysis_type.lower()}.general",
        },
    )
    assert run.status_code == 200
    result_id = run.json()["result_id"]
    assert result_id
    return project_id, result_id


def test_export_preparation_and_csv_generation(thermal_dataset):
    app = create_app(api_token="exports-token")
    client = TestClient(app)
    project_id, result_id = _seed_workspace_with_result(client, thermal_dataset)

    prep = client.get(f"/workspace/{project_id}/exports/preparation", headers=_headers())
    assert prep.status_code == 200
    prep_payload = prep.json()
    assert prep_payload["project_id"] == project_id
    assert "results_csv" in prep_payload["supported_outputs"]
    assert "report_docx" in prep_payload["supported_outputs"]
    assert len(prep_payload["exportable_results"]) == 1
    assert prep_payload["exportable_results"][0]["id"] == result_id

    csv_export = client.post(
        f"/workspace/{project_id}/exports/results-csv",
        headers=_headers(),
        json={"selected_result_ids": [result_id]},
    )
    assert csv_export.status_code == 200
    csv_payload = csv_export.json()
    assert csv_payload["output_type"] == "results_csv"
    assert csv_payload["included_result_ids"] == [result_id]
    assert csv_payload["file_name"].endswith(".csv")

    csv_text = base64.b64decode(csv_payload["artifact_base64"].encode("ascii")).decode("utf-8")
    assert "result_id,status,analysis_type" in csv_text
    assert result_id in csv_text


def test_export_docx_generation_returns_docx_bytes(thermal_dataset):
    app = create_app(api_token="exports-token")
    client = TestClient(app)
    project_id, result_id = _seed_workspace_with_result(client, thermal_dataset)

    docx_export = client.post(
        f"/workspace/{project_id}/exports/report-docx",
        headers=_headers(),
        json={"selected_result_ids": [result_id]},
    )
    assert docx_export.status_code == 200
    payload = docx_export.json()
    assert payload["output_type"] == "report_docx"
    assert payload["included_result_ids"] == [result_id]
    assert payload["file_name"].endswith(".docx")
    docx_bytes = base64.b64decode(payload["artifact_base64"].encode("ascii"))
    assert docx_bytes[:4] == b"PK\x03\x04"


def test_export_docx_generation_keeps_dta_in_stable_partition(thermal_dataset):
    app = create_app(api_token="exports-token")
    client = TestClient(app)
    project_id, result_id = _seed_workspace_with_result(
        client,
        thermal_dataset,
        data_type="DTA",
        analysis_type="DTA",
        workflow_template_id="dta.general",
    )

    docx_export = client.post(
        f"/workspace/{project_id}/exports/report-docx",
        headers=_headers(),
        json={"selected_result_ids": [result_id]},
    )
    assert docx_export.status_code == 200
    payload = docx_export.json()
    assert payload["included_result_ids"] == [result_id]
    docx_bytes = base64.b64decode(payload["artifact_base64"].encode("ascii"))

    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    assert "Stable Analyses" in xml
    assert "DTA - export_seed" in xml
    assert "outside the stable workflow guarantee" not in xml


def test_export_rejects_unknown_selected_result_id(thermal_dataset):
    app = create_app(api_token="exports-token")
    client = TestClient(app)
    project_id, _result_id = _seed_workspace_with_result(client, thermal_dataset)

    response = client.post(
        f"/workspace/{project_id}/exports/results-csv",
        headers=_headers(),
        json={"selected_result_ids": ["missing_result_id"]},
    )
    assert response.status_code == 400
    assert "Unknown selected_result_ids" in response.json()["detail"]


def _build_spectral_export_state() -> tuple[dict, str]:
    dataset_key = "ftir_export_seed"
    dataset = ThermalDataset(
        data=pd.DataFrame({"temperature": [650.0, 980.0, 1450.0], "signal": [0.08, 0.52, 0.18]}),
        metadata={
            "sample_name": "SyntheticFTIR",
            "sample_mass": 1.0,
            "heating_rate": 1.0,
            "instrument": "SpecBench",
            "vendor": "TestVendor",
            "display_name": "Synthetic FTIR Spectrum",
        },
        data_type="FTIR",
        units={"temperature": "cm^-1", "signal": "a.u."},
        original_columns={"temperature": "wavenumber", "signal": "intensity"},
        file_path="",
    )
    processing = ensure_processing_payload(analysis_type="FTIR", workflow_template="ftir.general")
    processing = update_processing_step(processing, "similarity_matching", {"metric": "cosine", "top_n": 3, "minimum_score": 0.45})
    spectral_record = serialize_spectral_result(
        dataset_key,
        dataset,
        analysis_type="FTIR",
        summary={
            "peak_count": 3,
            "match_status": "no_match",
            "candidate_count": 1,
            "top_match_id": None,
            "top_match_name": None,
            "top_match_score": 0.31,
            "confidence_band": "no_match",
            "caution_code": "spectral_no_match",
        },
        rows=[
            {
                "rank": 1,
                "candidate_id": "ftir_ref_unknown",
                "candidate_name": "Unknown",
                "normalized_score": 0.31,
                "confidence_band": "no_match",
                "evidence": {"shared_peak_count": 0, "peak_overlap_ratio": 0.0},
            }
        ],
        artifacts={"figure_keys": []},
        processing=processing,
        validation={"status": "warn", "issues": [], "warnings": ["FTIR produced no confident library match."]},
    )
    state = {
        "datasets": {dataset_key: dataset},
        "results": {spectral_record["id"]: spectral_record},
        "figures": {},
        "comparison_workspace": {
            "analysis_type": "FTIR",
            "selected_datasets": [dataset_key],
            "notes": "Spectral caution lane",
        },
    }
    return state, spectral_record["id"]


def test_export_preparation_includes_spectral_workspace_and_results():
    state, result_id = _build_spectral_export_state()
    prep = build_export_preparation(state)
    compare_workspace = prep["compare_workspace"]

    assert compare_workspace.analysis_type == "FTIR"
    assert compare_workspace.selected_datasets == ["ftir_export_seed"]
    assert len(prep["exportable_results"]) == 1
    assert prep["exportable_results"][0].id == result_id
    assert prep["exportable_results"][0].analysis_type == "FTIR"


def test_export_artifacts_preserve_spectral_caution_fields():
    state, result_id = _build_spectral_export_state()

    csv_artifact = generate_results_csv_artifact(state, selected_result_ids=[result_id])
    csv_text = base64.b64decode(csv_artifact["artifact_base64"].encode("ascii")).decode("utf-8")
    assert "spectral_no_match" in csv_text

    docx_artifact = generate_report_docx_artifact(state, selected_result_ids=[result_id])
    docx_bytes = base64.b64decode(docx_artifact["artifact_base64"].encode("ascii"))
    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    assert "FTIR - ftir_export_seed" in xml
    assert "Match Status" in xml
    assert "Caution Code" in xml
    assert "spectral_no_match" in xml
