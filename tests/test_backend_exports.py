from __future__ import annotations

import base64

from fastapi.testclient import TestClient

from backend.app import create_app


def _headers() -> dict[str, str]:
    return {"X-TA-Token": "exports-token"}


def _as_b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _seed_workspace_with_result(client: TestClient, thermal_dataset) -> tuple[str, str]:
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
            "data_type": "DSC",
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
            "analysis_type": "DSC",
            "workflow_template_id": "dsc.general",
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
