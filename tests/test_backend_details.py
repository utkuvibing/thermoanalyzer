from __future__ import annotations

import base64

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.store import ProjectStore
from core.modalities import stable_analysis_types
from core.result_serialization import make_result_record
from backend.workspace import normalize_workspace_state


def _headers() -> dict[str, str]:
    return {"X-TA-Token": "details-token"}


def _as_b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _import_dataset(client: TestClient, project_id: str, thermal_dataset, *, file_name: str, data_type: str) -> str:
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


def _seed_workspace_with_dsc_result(client: TestClient, thermal_dataset) -> tuple[str, str, str]:
    created = client.post("/workspace/new", headers=_headers()).json()
    project_id = created["project_id"]
    dataset_key = _import_dataset(client, project_id, thermal_dataset, file_name="seed_dsc.csv", data_type="DSC")

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
    return project_id, dataset_key, result_id


def test_dataset_and_result_detail_endpoints(thermal_dataset):
    app = create_app(api_token="details-token")
    client = TestClient(app)
    project_id, dataset_key, result_id = _seed_workspace_with_dsc_result(client, thermal_dataset)

    ds_detail = client.get(f"/workspace/{project_id}/datasets/{dataset_key}", headers=_headers())
    assert ds_detail.status_code == 200
    ds_body = ds_detail.json()
    assert ds_body["dataset"]["key"] == dataset_key
    assert "validation" in ds_body
    assert "metadata" in ds_body
    assert isinstance(ds_body["data_preview"], list)

    result_detail = client.get(f"/workspace/{project_id}/results/{result_id}", headers=_headers())
    assert result_detail.status_code == 200
    result_body = result_detail.json()
    assert result_body["result"]["id"] == result_id
    assert result_body["result"]["analysis_type"] == "DSC"
    assert "processing" in result_body
    assert "provenance" in result_body
    assert "validation" in result_body
    assert result_body["row_count"] >= 0


def test_compare_workspace_read_write(thermal_dataset):
    app = create_app(api_token="details-token")
    client = TestClient(app)
    project_id, dataset_key, _result_id = _seed_workspace_with_dsc_result(client, thermal_dataset)

    compare_get = client.get(f"/workspace/{project_id}/compare", headers=_headers())
    assert compare_get.status_code == 200
    assert compare_get.json()["compare_workspace"]["analysis_type"] in set(stable_analysis_types())

    compare_put = client.put(
        f"/workspace/{project_id}/compare",
        headers=_headers(),
        json={
            "analysis_type": "DSC",
            "selected_datasets": [dataset_key],
            "notes": "Desktop compare smoke",
        },
    )
    assert compare_put.status_code == 200
    payload = compare_put.json()["compare_workspace"]
    assert payload["analysis_type"] == "DSC"
    assert payload["selected_datasets"] == [dataset_key]
    assert payload["notes"] == "Desktop compare smoke"


def test_compare_workspace_accepts_spectral_analysis_types():
    app = create_app(api_token="details-token")
    client = TestClient(app)
    project_id = client.post("/workspace/new", headers=_headers()).json()["project_id"]

    for analysis_type in ("FTIR", "RAMAN"):
        compare_put = client.put(
            f"/workspace/{project_id}/compare",
            headers=_headers(),
            json={"analysis_type": analysis_type, "selected_datasets": [], "notes": f"{analysis_type} lane"},
        )
        assert compare_put.status_code == 200
        payload = compare_put.json()["compare_workspace"]
        assert payload["analysis_type"] == analysis_type
        assert payload["selected_datasets"] == []


def test_compare_workspace_accepts_xrd_analysis_type():
    app = create_app(api_token="details-token")
    client = TestClient(app)
    project_id = client.post("/workspace/new", headers=_headers()).json()["project_id"]

    compare_put = client.put(
        f"/workspace/{project_id}/compare",
        headers=_headers(),
        json={"analysis_type": "XRD", "selected_datasets": [], "notes": "XRD lane"},
    )
    assert compare_put.status_code == 200
    payload = compare_put.json()["compare_workspace"]
    assert payload["analysis_type"] == "XRD"
    assert payload["selected_datasets"] == []


def test_compare_workspace_xrd_lane_filters_incompatible_datasets(thermal_dataset):
    app = create_app(api_token="details-token")
    client = TestClient(app)
    project_id = client.post("/workspace/new", headers=_headers()).json()["project_id"]

    xrd_key = _import_dataset(client, project_id, thermal_dataset, file_name="xrd_lane.csv", data_type="XRD")
    ftir_key = _import_dataset(client, project_id, thermal_dataset, file_name="ftir_lane.csv", data_type="FTIR")

    compare_put = client.put(
        f"/workspace/{project_id}/compare",
        headers=_headers(),
        json={"analysis_type": "XRD", "selected_datasets": [xrd_key, ftir_key]},
    )
    assert compare_put.status_code == 200
    payload = compare_put.json()["compare_workspace"]
    assert payload["analysis_type"] == "XRD"
    assert payload["selected_datasets"] == [xrd_key]


def test_compare_workspace_rejects_invalid_analysis_type():
    app = create_app(api_token="details-token")
    client = TestClient(app)
    project_id = client.post("/workspace/new", headers=_headers()).json()["project_id"]

    response = client.put(
        f"/workspace/{project_id}/compare",
        headers=_headers(),
        json={"analysis_type": "INVALID"},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "analysis_type must be one of:" in detail
    for token in stable_analysis_types():
        assert token in detail


def test_result_literature_compare_endpoint_persists_payload():
    store = ProjectStore()
    record = make_result_record(
        result_id="xrd_demo",
        analysis_type="XRD",
        status="stable",
        dataset_key="xrd_demo",
        metadata={"sample_name": "Phase Alpha Sample"},
        summary={"top_candidate_name": "Phase Alpha", "match_status": "matched"},
        rows=[{"rank": 1, "candidate_name": "Phase Alpha", "normalized_score": 0.82}],
        scientific_context={
            "scientific_claims": [
                {
                    "id": "C1",
                    "strength": "mechanistic",
                    "claim": "Phase Alpha remains a qualitative XRD follow-up candidate rather than a confirmed phase call.",
                    "evidence": ["Shared peaks remain consistent with the retained candidate."],
                }
            ],
            "uncertainty_assessment": {"overall_confidence": "moderate", "items": ["Interpretation remains qualitative."]},
        },
        validation={"status": "pass", "warnings": [], "issues": []},
    )
    project_id = store.put(normalize_workspace_state({"results": {record["id"]: record}}))
    client = TestClient(create_app(api_token="details-token", store=store))

    response = client.post(
        f"/workspace/{project_id}/results/{record['id']}/literature/compare",
        headers=_headers(),
        json={"persist": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_id"] == record["id"]
    assert payload["literature_context"]["mode"] == "metadata_abstract_oa_only"
    assert payload["literature_claims"]
    assert "support_label" in payload["literature_comparisons"][0]
    assert payload["detail"]["project_id"] == project_id
    assert payload["detail"]["result"]["id"] == record["id"]
    assert payload["detail"]["literature_context"]["mode"] == "metadata_abstract_oa_only"

    detail = client.get(f"/workspace/{project_id}/results/{record['id']}", headers=_headers())
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["literature_context"]["mode"] == "metadata_abstract_oa_only"
    assert detail_payload["literature_claims"]
