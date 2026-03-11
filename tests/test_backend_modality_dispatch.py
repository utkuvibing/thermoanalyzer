from __future__ import annotations

import base64

from fastapi.testclient import TestClient

from backend.app import create_app


def _headers() -> dict[str, str]:
    return {"X-TA-Token": "dispatch-token"}


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


def test_analysis_run_dispatches_stable_type_case_insensitively(thermal_dataset):
    app = create_app(api_token="dispatch-token")
    client = TestClient(app)
    project_id = _new_project(client)
    dataset_key = _import_dataset(client, project_id, thermal_dataset, "dispatch_dsc.csv", "DSC")

    response = client.post(
        "/analysis/run",
        headers=_headers(),
        json={
            "project_id": project_id,
            "dataset_key": dataset_key,
            "analysis_type": "dsc",
            "workflow_template_id": "dsc.general",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["analysis_type"] == "DSC"
    assert payload["execution_status"] == "saved"
    assert payload["result_id"]


def test_analysis_run_rejects_unknown_analysis_type_with_explicit_stable_set(thermal_dataset):
    app = create_app(api_token="dispatch-token")
    client = TestClient(app)
    project_id = _new_project(client)
    dataset_key = _import_dataset(client, project_id, thermal_dataset, "dispatch_dsc.csv", "DSC")

    response = client.post(
        "/analysis/run",
        headers=_headers(),
        json={
            "project_id": project_id,
            "dataset_key": dataset_key,
            "analysis_type": "XRD",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "analysis_type must be one of: DSC, DTA, TGA."


def test_analysis_run_rejects_ineligible_dataset_with_explicit_error(thermal_dataset):
    app = create_app(api_token="dispatch-token")
    client = TestClient(app)
    project_id = _new_project(client)
    dataset_key = _import_dataset(client, project_id, thermal_dataset, "dispatch_tga.csv", "TGA")

    response = client.post(
        "/analysis/run",
        headers=_headers(),
        json={
            "project_id": project_id,
            "dataset_key": dataset_key,
            "analysis_type": "DSC",
        },
    )
    assert response.status_code == 400
    assert f"Dataset '{dataset_key}' is not eligible for DSC analysis." in response.json()["detail"]


def test_batch_run_rejects_unknown_analysis_type_with_explicit_stable_set():
    app = create_app(api_token="dispatch-token")
    client = TestClient(app)
    project_id = _new_project(client)

    response = client.post(
        f"/workspace/{project_id}/batch/run",
        headers=_headers(),
        json={"analysis_type": "XRF"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "analysis_type must be one of: DSC, DTA, TGA."


def test_batch_run_dispatches_tga_through_registry_path(thermal_dataset):
    app = create_app(api_token="dispatch-token")
    client = TestClient(app)
    project_id = _new_project(client)
    dataset_key = _import_dataset(client, project_id, thermal_dataset, "dispatch_tga.csv", "TGA")

    set_selection = client.post(
        f"/workspace/{project_id}/compare/selection",
        headers=_headers(),
        json={"operation": "replace", "dataset_keys": [dataset_key]},
    )
    assert set_selection.status_code == 200

    response = client.post(
        f"/workspace/{project_id}/batch/run",
        headers=_headers(),
        json={"analysis_type": "tga", "workflow_template_id": "tga.general"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["analysis_type"] == "TGA"
    assert payload["outcomes"]["saved"] == 1
    assert payload["outcomes"]["blocked"] == 0
    assert payload["outcomes"]["failed"] == 0


def test_compare_workspace_validation_uses_registry_set(monkeypatch):
    app = create_app(api_token="dispatch-token")
    client = TestClient(app)
    project_id = _new_project(client)

    monkeypatch.setattr("backend.detail.stable_analysis_types", lambda: ("DSC", "TGA", "DTA"))
    response = client.put(
        f"/workspace/{project_id}/compare",
        headers=_headers(),
        json={"analysis_type": "DTA"},
    )

    assert response.status_code == 200
    assert response.json()["compare_workspace"]["analysis_type"] == "DTA"
