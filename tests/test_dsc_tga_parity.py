from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app


def _headers() -> dict[str, str]:
    return {"X-TA-Token": "parity-token"}


def _as_b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _new_project(client: TestClient) -> str:
    return client.post("/workspace/new", headers=_headers()).json()["project_id"]


def _import_dataset(client: TestClient, project_id: str, thermal_dataset, file_name: str, data_type: str) -> str:
    csv_bytes = thermal_dataset.data.to_csv(index=False).encode("utf-8")
    imported = client.post(
        "/dataset/import",
        headers=_headers(),
        json={
            "project_id": project_id,
            "file_name": file_name,
            "file_base64": _as_b64(csv_bytes),
            "data_type": data_type,
        },
    )
    assert imported.status_code == 200
    return imported.json()["dataset"]["key"]


def _run_single(client: TestClient, project_id: str, dataset_key: str, analysis_type: str, workflow_template_id: str) -> dict:
    response = client.post(
        "/analysis/run",
        headers=_headers(),
        json={
            "project_id": project_id,
            "dataset_key": dataset_key,
            "analysis_type": analysis_type,
            "workflow_template_id": workflow_template_id,
        },
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.parametrize(
    ("analysis_type", "workflow_template_id", "data_type", "result_prefix"),
    (
        ("DSC", "dsc.general", "DSC", "dsc_"),
        ("DTA", "dta.general", "DTA", "dta_"),
        ("TGA", "tga.general", "TGA", "tga_"),
    ),
)
def test_single_run_stable_parity_contract(
    thermal_dataset,
    analysis_type: str,
    workflow_template_id: str,
    data_type: str,
    result_prefix: str,
):
    app = create_app(api_token="parity-token")
    client = TestClient(app)
    project_id = _new_project(client)
    dataset_key = _import_dataset(client, project_id, thermal_dataset, f"single_{analysis_type.lower()}.csv", data_type)

    payload = _run_single(client, project_id, dataset_key, analysis_type, workflow_template_id)
    assert payload["analysis_type"] == analysis_type
    assert payload["execution_status"] == "saved"
    assert payload["failure_reason"] is None
    assert payload["result_id"].startswith(result_prefix)
    assert payload["validation"]["status"] in {"pass", "warn"}
    assert payload["provenance"]["saved_at_utc"]
    assert payload["provenance"]["calibration_state"] is not None
    assert payload["provenance"]["reference_state"] is not None

    result_detail = client.get(
        f"/workspace/{project_id}/results/{payload['result_id']}",
        headers=_headers(),
    )
    assert result_detail.status_code == 200
    detail = result_detail.json()
    assert detail["result"]["analysis_type"] == analysis_type
    assert detail["processing"]["workflow_template_id"] == workflow_template_id
    assert isinstance(detail["summary"], dict)
    assert isinstance(detail["rows_preview"], list)


@pytest.mark.parametrize(
    ("analysis_type", "workflow_template_id", "data_type"),
    (
        ("DSC", "dsc.general", "DSC"),
        ("DTA", "dta.general", "DTA"),
        ("TGA", "tga.general", "TGA"),
    ),
)
def test_batch_run_stable_parity_matches_single_run_summary(
    thermal_dataset,
    analysis_type: str,
    workflow_template_id: str,
    data_type: str,
):
    app = create_app(api_token="parity-token")
    client = TestClient(app)
    project_id = _new_project(client)

    first_key = _import_dataset(client, project_id, thermal_dataset, f"{analysis_type.lower()}_a.csv", data_type)
    second_key = _import_dataset(client, project_id, thermal_dataset, f"{analysis_type.lower()}_b.csv", data_type)
    single_payload = _run_single(client, project_id, first_key, analysis_type, workflow_template_id)

    selection = client.post(
        f"/workspace/{project_id}/compare/selection",
        headers=_headers(),
        json={"operation": "replace", "dataset_keys": [first_key, second_key]},
    )
    assert selection.status_code == 200

    batch_response = client.post(
        f"/workspace/{project_id}/batch/run",
        headers=_headers(),
        json={"analysis_type": analysis_type, "workflow_template_id": workflow_template_id},
    )
    assert batch_response.status_code == 200
    batch_payload = batch_response.json()

    assert batch_payload["analysis_type"] == analysis_type
    assert batch_payload["workflow_template_id"] == workflow_template_id
    assert batch_payload["outcomes"] == {"total": 2, "saved": 2, "blocked": 0, "failed": 0}
    assert len(batch_payload["batch_summary"]) == 2
    assert len(batch_payload["saved_result_ids"]) == 2

    rows_by_key = {row["dataset_key"]: row for row in batch_payload["batch_summary"]}
    first_row = rows_by_key[first_key]
    assert first_row["execution_status"] == "saved"
    assert first_row["workflow_template_id"] == workflow_template_id
    assert first_row["validation_status"] == single_payload["validation"]["status"]
    assert first_row["result_id"] in batch_payload["saved_result_ids"]

    assert batch_payload["compare_workspace"]["batch_run_id"] == batch_payload["batch_run_id"]
    assert batch_payload["compare_workspace"]["batch_template_id"] == workflow_template_id
    assert batch_payload["compare_workspace"]["batch_last_feedback"] == batch_payload["outcomes"]
