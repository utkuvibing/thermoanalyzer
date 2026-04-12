from __future__ import annotations

import base64
import io
import zipfile

from fastapi.testclient import TestClient

from backend.app import create_app
from core.project_io import load_project_archive


def _headers() -> dict[str, str]:
    return {"X-TA-Token": "workflow-token"}


def _to_base64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def test_workspace_import_run_analysis_and_save_roundtrip(thermal_dataset):
    app = create_app(api_token="workflow-token")
    client = TestClient(app)

    create_response = client.post("/workspace/new", headers=_headers())
    assert create_response.status_code == 200
    project_id = create_response.json()["project_id"]

    csv_bytes = thermal_dataset.data.to_csv(index=False).encode("utf-8")
    import_response = client.post(
        "/dataset/import",
        headers=_headers(),
        json={
            "project_id": project_id,
            "file_name": "synthetic_dsc.csv",
            "file_base64": _to_base64(csv_bytes),
            "data_type": "DSC",
        },
    )
    assert import_response.status_code == 200
    imported = import_response.json()
    dataset_key = imported["dataset"]["key"]
    assert imported["summary"]["dataset_count"] == 1
    assert imported["dataset"]["data_type"] == "DSC"

    datasets_response = client.get(f"/workspace/{project_id}/datasets", headers=_headers())
    assert datasets_response.status_code == 200
    datasets = datasets_response.json()["datasets"]
    assert len(datasets) == 1
    assert datasets[0]["key"] == dataset_key

    run_response = client.post(
        "/analysis/run",
        headers=_headers(),
        json={
            "project_id": project_id,
            "dataset_key": dataset_key,
            "analysis_type": "DSC",
            "workflow_template_id": "dsc.general",
        },
    )
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["execution_status"] == "saved"
    assert run_payload["result_id"].startswith("dsc_")

    results_response = client.get(f"/workspace/{project_id}/results", headers=_headers())
    assert results_response.status_code == 200
    results = results_response.json()["results"]
    assert len(results) == 1
    assert results[0]["id"] == run_payload["result_id"]
    assert results[0]["analysis_type"] == "DSC"

    result_detail_response = client.get(
        f"/workspace/{project_id}/results/{run_payload['result_id']}",
        headers=_headers(),
    )
    assert result_detail_response.status_code == 200
    result_detail = result_detail_response.json()
    assert result_detail["result"]["id"] == run_payload["result_id"]
    assert "processing" in result_detail
    assert "validation" in result_detail
    assert "provenance" in result_detail

    export_prep_response = client.get(f"/workspace/{project_id}/exports/preparation", headers=_headers())
    assert export_prep_response.status_code == 200
    export_prep = export_prep_response.json()
    assert any(item["id"] == run_payload["result_id"] for item in export_prep["exportable_results"])

    export_csv_response = client.post(
        f"/workspace/{project_id}/exports/results-csv",
        headers=_headers(),
        json={"selected_result_ids": [run_payload["result_id"]]},
    )
    assert export_csv_response.status_code == 200
    export_csv = export_csv_response.json()
    export_csv_text = base64.b64decode(export_csv["artifact_base64"].encode("ascii")).decode("utf-8")
    assert run_payload["result_id"] in export_csv_text

    save_response = client.post(
        "/project/save",
        headers=_headers(),
        json={"project_id": project_id},
    )
    assert save_response.status_code == 200
    archive_base64 = save_response.json()["archive_base64"]
    restored = load_project_archive(io.BytesIO(base64.b64decode(archive_base64.encode("ascii"))))
    assert dataset_key in restored["datasets"]
    assert run_payload["result_id"] in restored["results"]


def test_workspace_import_run_dta_analysis_roundtrip(thermal_dataset):
    app = create_app(api_token="workflow-token")
    client = TestClient(app)

    create_response = client.post("/workspace/new", headers=_headers())
    assert create_response.status_code == 200
    project_id = create_response.json()["project_id"]

    csv_bytes = thermal_dataset.data.to_csv(index=False).encode("utf-8")
    import_response = client.post(
        "/dataset/import",
        headers=_headers(),
        json={
            "project_id": project_id,
            "file_name": "synthetic_dta.csv",
            "file_base64": _to_base64(csv_bytes),
            "data_type": "DTA",
        },
    )
    assert import_response.status_code == 200
    dataset_key = import_response.json()["dataset"]["key"]

    run_response = client.post(
        "/analysis/run",
        headers=_headers(),
        json={
            "project_id": project_id,
            "dataset_key": dataset_key,
            "analysis_type": "DTA",
            "workflow_template_id": "dta.general",
        },
    )
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["analysis_type"] == "DTA"
    assert run_payload["execution_status"] == "saved"
    assert run_payload["result_id"].startswith("dta_")

    results_response = client.get(f"/workspace/{project_id}/results", headers=_headers())
    assert results_response.status_code == 200
    results = results_response.json()["results"]
    assert len(results) == 1
    assert results[0]["analysis_type"] == "DTA"


def test_workspace_compare_batch_run_with_dta_stable_template(thermal_dataset):
    app = create_app(api_token="workflow-token")
    client = TestClient(app)

    create_response = client.post("/workspace/new", headers=_headers())
    assert create_response.status_code == 200
    project_id = create_response.json()["project_id"]

    csv_bytes = thermal_dataset.data.to_csv(index=False).encode("utf-8")
    imported_a = client.post(
        "/dataset/import",
        headers=_headers(),
        json={
            "project_id": project_id,
            "file_name": "batch_dta_a.csv",
            "file_base64": _to_base64(csv_bytes),
            "data_type": "DTA",
        },
    )
    imported_b = client.post(
        "/dataset/import",
        headers=_headers(),
        json={
            "project_id": project_id,
            "file_name": "batch_dta_b.csv",
            "file_base64": _to_base64(csv_bytes),
            "data_type": "DTA",
        },
    )
    assert imported_a.status_code == 200
    assert imported_b.status_code == 200
    dataset_a = imported_a.json()["dataset"]["key"]
    dataset_b = imported_b.json()["dataset"]["key"]

    selection_response = client.post(
        f"/workspace/{project_id}/compare/selection",
        headers=_headers(),
        json={"operation": "replace", "dataset_keys": [dataset_a, dataset_b]},
    )
    assert selection_response.status_code == 200

    batch_response = client.post(
        f"/workspace/{project_id}/batch/run",
        headers=_headers(),
        json={"analysis_type": "DTA", "workflow_template_id": "dta.general"},
    )
    assert batch_response.status_code == 200
    batch_payload = batch_response.json()
    assert batch_payload["analysis_type"] == "DTA"
    assert batch_payload["workflow_template_id"] == "dta.general"
    assert batch_payload["outcomes"] == {"total": 2, "saved": 2, "blocked": 0, "failed": 0}
    assert len(batch_payload["batch_summary"]) == 2
    assert {row["analysis_type"] for row in batch_payload["batch_summary"]} == {"DTA"}


def test_workspace_compare_spectral_lane_filters_incompatible_dataset_selection(thermal_dataset):
    app = create_app(api_token="workflow-token")
    client = TestClient(app)

    create_response = client.post("/workspace/new", headers=_headers())
    assert create_response.status_code == 200
    project_id = create_response.json()["project_id"]

    csv_bytes = thermal_dataset.data.to_csv(index=False).encode("utf-8")
    imported_ftir = client.post(
        "/dataset/import",
        headers=_headers(),
        json={
            "project_id": project_id,
            "file_name": "spectral_ftir.csv",
            "file_base64": _to_base64(csv_bytes),
            "data_type": "FTIR",
        },
    )
    imported_raman = client.post(
        "/dataset/import",
        headers=_headers(),
        json={
            "project_id": project_id,
            "file_name": "spectral_raman.csv",
            "file_base64": _to_base64(csv_bytes),
            "data_type": "RAMAN",
        },
    )
    assert imported_ftir.status_code == 200
    assert imported_raman.status_code == 200
    ftir_key = imported_ftir.json()["dataset"]["key"]
    raman_key = imported_raman.json()["dataset"]["key"]

    ftir_workspace = client.put(
        f"/workspace/{project_id}/compare",
        headers=_headers(),
        json={
            "analysis_type": "FTIR",
            "selected_datasets": [ftir_key, raman_key],
        },
    )
    assert ftir_workspace.status_code == 200
    payload = ftir_workspace.json()["compare_workspace"]
    assert payload["analysis_type"] == "FTIR"
    assert payload["selected_datasets"] == [ftir_key]

    raman_workspace = client.put(
        f"/workspace/{project_id}/compare",
        headers=_headers(),
        json={"analysis_type": "RAMAN"},
    )
    assert raman_workspace.status_code == 200
    assert raman_workspace.json()["compare_workspace"]["selected_datasets"] == []


def test_workspace_compare_xrd_lane_filters_incompatible_dataset_selection(thermal_dataset):
    app = create_app(api_token="workflow-token")
    client = TestClient(app)

    create_response = client.post("/workspace/new", headers=_headers())
    assert create_response.status_code == 200
    project_id = create_response.json()["project_id"]

    csv_bytes = thermal_dataset.data.to_csv(index=False).encode("utf-8")
    imported_xrd = client.post(
        "/dataset/import",
        headers=_headers(),
        json={
            "project_id": project_id,
            "file_name": "xrd_compare.csv",
            "file_base64": _to_base64(csv_bytes),
            "data_type": "XRD",
        },
    )
    imported_ftir = client.post(
        "/dataset/import",
        headers=_headers(),
        json={
            "project_id": project_id,
            "file_name": "ftir_compare.csv",
            "file_base64": _to_base64(csv_bytes),
            "data_type": "FTIR",
        },
    )
    assert imported_xrd.status_code == 200
    assert imported_ftir.status_code == 200
    xrd_key = imported_xrd.json()["dataset"]["key"]
    ftir_key = imported_ftir.json()["dataset"]["key"]

    xrd_workspace = client.put(
        f"/workspace/{project_id}/compare",
        headers=_headers(),
        json={
            "analysis_type": "XRD",
            "selected_datasets": [xrd_key, ftir_key],
        },
    )
    assert xrd_workspace.status_code == 200
    payload = xrd_workspace.json()["compare_workspace"]
    assert payload["analysis_type"] == "XRD"
    assert payload["selected_datasets"] == [xrd_key]


def test_stable_compare_batch_report_and_project_roundtrip_smoke(thermal_dataset):
    app = create_app(api_token="workflow-token")
    client = TestClient(app)

    create_response = client.post("/workspace/new", headers=_headers())
    assert create_response.status_code == 200
    project_id = create_response.json()["project_id"]

    first_csv = thermal_dataset.data.to_csv(index=False).encode("utf-8")
    first_import = client.post(
        "/dataset/import",
        headers=_headers(),
        json={
            "project_id": project_id,
            "file_name": "stable_smoke_a.csv",
            "file_base64": _to_base64(first_csv),
            "data_type": "DSC",
        },
    )
    assert first_import.status_code == 200
    first_key = first_import.json()["dataset"]["key"]

    second_dataset = thermal_dataset.copy()
    second_dataset.data["signal"] = second_dataset.data["signal"] * 1.015
    second_csv = second_dataset.data.to_csv(index=False).encode("utf-8")
    second_import = client.post(
        "/dataset/import",
        headers=_headers(),
        json={
            "project_id": project_id,
            "file_name": "stable_smoke_b.csv",
            "file_base64": _to_base64(second_csv),
            "data_type": "DSC",
        },
    )
    assert second_import.status_code == 200
    second_key = second_import.json()["dataset"]["key"]

    replace_selection = client.post(
        f"/workspace/{project_id}/compare/selection",
        headers=_headers(),
        json={"operation": "replace", "dataset_keys": [first_key, second_key]},
    )
    assert replace_selection.status_code == 200
    assert replace_selection.json()["compare_workspace"]["selected_datasets"] == [first_key, second_key]

    compare_config = client.put(
        f"/workspace/{project_id}/compare",
        headers=_headers(),
        json={
            "analysis_type": "DSC",
            "selected_datasets": [first_key, second_key],
            "notes": "Stable smoke workflow",
        },
    )
    assert compare_config.status_code == 200
    compare_payload = compare_config.json()["compare_workspace"]
    assert compare_payload["analysis_type"] == "DSC"
    assert compare_payload["notes"] == "Stable smoke workflow"

    batch_response = client.post(
        f"/workspace/{project_id}/batch/run",
        headers=_headers(),
        json={"analysis_type": "DSC", "workflow_template_id": "dsc.general"},
    )
    assert batch_response.status_code == 200
    batch_payload = batch_response.json()
    assert batch_payload["outcomes"] == {"total": 2, "saved": 2, "blocked": 0, "failed": 0}
    result_ids = list(batch_payload["saved_result_ids"])
    assert len(result_ids) == 2
    assert batch_payload["batch_run_id"]

    export_prep_response = client.get(f"/workspace/{project_id}/exports/preparation", headers=_headers())
    assert export_prep_response.status_code == 200
    export_prep = export_prep_response.json()
    assert export_prep["compare_workspace"]["analysis_type"] == "DSC"
    assert export_prep["compare_workspace"]["selected_datasets"] == [first_key, second_key]
    assert export_prep["compare_workspace"]["notes"] == "Stable smoke workflow"
    assert {item["id"] for item in export_prep["exportable_results"]} == set(result_ids)

    report_response = client.post(
        f"/workspace/{project_id}/exports/report-docx",
        headers=_headers(),
        json={"selected_result_ids": result_ids},
    )
    assert report_response.status_code == 200
    report_payload = report_response.json()
    assert set(report_payload["included_result_ids"]) == set(result_ids)
    report_docx = base64.b64decode(report_payload["artifact_base64"].encode("ascii"))
    with zipfile.ZipFile(io.BytesIO(report_docx), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
    assert "Stable Analyses" in xml
    assert "Experimental Analyses" not in xml
    assert "stable_smoke_a" in xml
    assert "stable_smoke_b" in xml

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

    loaded_compare_response = client.get(f"/workspace/{loaded_project_id}/compare", headers=_headers())
    assert loaded_compare_response.status_code == 200
    loaded_compare = loaded_compare_response.json()["compare_workspace"]
    assert loaded_compare["analysis_type"] == "DSC"
    assert loaded_compare["selected_datasets"] == [first_key, second_key]
    assert loaded_compare["notes"] == "Stable smoke workflow"
    assert loaded_compare["batch_run_id"] == batch_payload["batch_run_id"]
    assert set(loaded_compare["batch_result_ids"]) == set(result_ids)
    assert len(loaded_compare["batch_summary"]) == 2

    loaded_results_response = client.get(f"/workspace/{loaded_project_id}/results", headers=_headers())
    assert loaded_results_response.status_code == 200
    loaded_results = loaded_results_response.json()["results"]
    assert {item["id"] for item in loaded_results} == set(result_ids)
