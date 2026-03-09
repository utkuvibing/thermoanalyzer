from __future__ import annotations

import base64

from fastapi.testclient import TestClient

from backend.app import create_app


def _headers() -> dict[str, str]:
    return {"X-TA-Token": "batch-token"}


def _as_b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


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


def test_batch_run_saves_results_for_compare_selected_datasets(thermal_dataset):
    app = create_app(api_token="batch-token")
    client = TestClient(app)
    project_id = client.post("/workspace/new", headers=_headers()).json()["project_id"]

    first = _import_dataset(client, project_id, thermal_dataset, "batch_a.csv", "DSC")
    second = _import_dataset(client, project_id, thermal_dataset, "batch_b.csv", "DSC")

    compare_set = client.post(
        f"/workspace/{project_id}/compare/selection",
        headers=_headers(),
        json={"operation": "replace", "dataset_keys": [first, second]},
    )
    assert compare_set.status_code == 200

    batch_run = client.post(
        f"/workspace/{project_id}/batch/run",
        headers=_headers(),
        json={"analysis_type": "DSC", "workflow_template_id": "dsc.general"},
    )
    assert batch_run.status_code == 200
    payload = batch_run.json()
    assert payload["analysis_type"] == "DSC"
    assert payload["outcomes"]["total"] == 2
    assert payload["outcomes"]["saved"] == 2
    assert payload["outcomes"]["blocked"] == 0
    assert payload["outcomes"]["failed"] == 0
    assert len(payload["saved_result_ids"]) == 2
    assert len(payload["batch_summary"]) == 2

    results = client.get(f"/workspace/{project_id}/results", headers=_headers())
    assert results.status_code == 200
    assert len(results.json()["results"]) == 2


def test_batch_run_blocks_incompatible_datasets_without_aborting(thermal_dataset):
    app = create_app(api_token="batch-token")
    client = TestClient(app)
    project_id = client.post("/workspace/new", headers=_headers()).json()["project_id"]

    dsc_key = _import_dataset(client, project_id, thermal_dataset, "batch_dsc.csv", "DSC")
    tga_key = _import_dataset(client, project_id, thermal_dataset, "batch_tga.csv", "TGA")

    compare_set = client.post(
        f"/workspace/{project_id}/compare/selection",
        headers=_headers(),
        json={"operation": "replace", "dataset_keys": [dsc_key, tga_key]},
    )
    assert compare_set.status_code == 200

    batch_run = client.post(
        f"/workspace/{project_id}/batch/run",
        headers=_headers(),
        json={"analysis_type": "DSC", "workflow_template_id": "dsc.general"},
    )
    assert batch_run.status_code == 200
    payload = batch_run.json()
    assert payload["outcomes"]["total"] == 2
    assert payload["outcomes"]["saved"] == 1
    assert payload["outcomes"]["blocked"] == 1
    assert payload["outcomes"]["failed"] == 0
    blocked = [row for row in payload["batch_summary"] if row["execution_status"] == "blocked"]
    assert blocked
    assert blocked[0]["dataset_key"] == tga_key


def test_batch_summary_persists_in_project_roundtrip(thermal_dataset):
    app = create_app(api_token="batch-token")
    client = TestClient(app)
    project_id = client.post("/workspace/new", headers=_headers()).json()["project_id"]

    first = _import_dataset(client, project_id, thermal_dataset, "persist_a.csv", "DSC")
    second = _import_dataset(client, project_id, thermal_dataset, "persist_b.csv", "DSC")
    client.post(
        f"/workspace/{project_id}/compare/selection",
        headers=_headers(),
        json={"operation": "replace", "dataset_keys": [first, second]},
    )

    batch_run = client.post(
        f"/workspace/{project_id}/batch/run",
        headers=_headers(),
        json={"analysis_type": "DSC", "workflow_template_id": "dsc.general"},
    )
    assert batch_run.status_code == 200
    run_payload = batch_run.json()
    assert run_payload["batch_run_id"]

    save_response = client.post(
        "/project/save",
        headers=_headers(),
        json={"project_id": project_id},
    )
    assert save_response.status_code == 200
    archive_base64 = save_response.json()["archive_base64"]

    load_response = client.post(
        "/project/load",
        headers=_headers(),
        json={"archive_base64": archive_base64},
    )
    assert load_response.status_code == 200
    loaded_project_id = load_response.json()["project_id"]

    compare_response = client.get(f"/workspace/{loaded_project_id}/compare", headers=_headers())
    assert compare_response.status_code == 200
    compare_payload = compare_response.json()["compare_workspace"]
    assert compare_payload["batch_run_id"] == run_payload["batch_run_id"]
    assert len(compare_payload["batch_summary"]) == 2
    assert len(compare_payload["batch_result_ids"]) == 2
