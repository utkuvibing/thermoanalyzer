from __future__ import annotations

import base64
import io
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import create_app
from core.project_io import PROJECT_EXTENSION, load_project_archive, save_project_archive
from utils.license_manager import APP_VERSION


def _auth_headers() -> dict[str, str]:
    return {"X-TA-Token": "test-token"}


def _sample_session_state(thermal_dataset) -> dict:
    dataset = thermal_dataset.copy()
    dataset.metadata.setdefault("file_name", "synthetic_dsc.csv")
    return {
        "datasets": {"synthetic_dsc": dataset},
        "active_dataset": "synthetic_dsc",
        "results": {},
        "figures": {},
        "analysis_history": [{"action": "Data Loaded", "page": "Import"}],
        "branding": {"report_title": "ThermoAnalyzer Professional Report"},
        "comparison_workspace": {"analysis_type": "DSC", "selected_datasets": ["synthetic_dsc"]},
    }


def _project_file(path: str) -> str:
    return (Path(__file__).resolve().parents[1] / path).read_text(encoding="utf-8")


def test_health_and_version_endpoints():
    app = create_app(api_token="test-token")
    client = TestClient(app)

    health_response = client.get("/health")
    assert health_response.status_code == 200
    assert health_response.json()["status"] == "ok"

    version_response = client.get("/version", headers=_auth_headers())
    assert version_response.status_code == 200
    body = version_response.json()
    assert body["app_version"] == APP_VERSION
    assert body["project_extension"] == PROJECT_EXTENSION


def test_project_load_save_roundtrip_compatibility(thermal_dataset):
    app = create_app(api_token="test-token")
    client = TestClient(app)

    archive_bytes = save_project_archive(_sample_session_state(thermal_dataset))
    archive_b64 = base64.b64encode(archive_bytes).decode("ascii")

    load_response = client.post(
        "/project/load",
        json={"archive_base64": archive_b64},
        headers=_auth_headers(),
    )
    assert load_response.status_code == 200
    load_payload = load_response.json()
    assert load_payload["project_extension"] == PROJECT_EXTENSION
    assert load_payload["summary"]["dataset_count"] == 1
    assert load_payload["summary"]["active_dataset"] == "synthetic_dsc"

    project_id = load_payload["project_id"]
    save_response = client.post(
        "/project/save",
        json={"project_id": project_id},
        headers=_auth_headers(),
    )
    assert save_response.status_code == 200
    save_payload = save_response.json()
    assert save_payload["file_name"].endswith(PROJECT_EXTENSION)

    saved_archive_bytes = base64.b64decode(save_payload["archive_base64"].encode("ascii"))
    restored_state = load_project_archive(io.BytesIO(saved_archive_bytes))
    assert "synthetic_dsc" in restored_state["datasets"]
    assert restored_state["active_dataset"] == "synthetic_dsc"
    assert len(restored_state.get("analysis_history", [])) == 1


def test_project_load_rejects_invalid_base64():
    app = create_app(api_token="test-token")
    client = TestClient(app)

    response = client.post(
        "/project/load",
        json={"archive_base64": "not-valid-base64"},
        headers=_auth_headers(),
    )
    assert response.status_code == 400
    assert "base64" in response.json()["detail"]


def test_project_save_rejects_unknown_project_id():
    app = create_app(api_token="test-token")
    client = TestClient(app)

    response = client.post(
        "/project/save",
        json={"project_id": "missing-project"},
        headers=_auth_headers(),
    )
    assert response.status_code == 404
    assert "Unknown project_id" in response.json()["detail"]


def test_workspace_new_and_summary():
    app = create_app(api_token="test-token")
    client = TestClient(app)

    create_response = client.post("/workspace/new", headers=_auth_headers())
    assert create_response.status_code == 200
    payload = create_response.json()
    project_id = payload["project_id"]
    assert payload["summary"]["dataset_count"] == 0
    assert payload["summary"]["result_count"] == 0

    summary_response = client.get(f"/workspace/{project_id}", headers=_auth_headers())
    assert summary_response.status_code == 200
    summary = summary_response.json()["summary"]
    assert summary["dataset_count"] == 0
    assert summary["result_count"] == 0


def test_dataset_detail_rejects_unknown_dataset():
    app = create_app(api_token="test-token")
    client = TestClient(app)
    project_id = client.post("/workspace/new", headers=_auth_headers()).json()["project_id"]

    response = client.get(f"/workspace/{project_id}/datasets/missing", headers=_auth_headers())
    assert response.status_code == 404
    assert "Unknown dataset_key" in response.json()["detail"]


def test_streamlit_artifact_promotes_dta_to_primary_stable_navigation():
    app_source = _project_file("app.py")

    assert 'st.Page(dta_render, title=tx("DTA Analizi", "DTA Analysis"), icon="📊", url_path="dta")' in app_source
    assert 'DTA Analysis (Experimental)' not in app_source
    assert "Kinetik ve dekonvolüsyon modülleri önizleme anahtarı arkasında kalır" in app_source


def test_desktop_artifacts_expose_primary_dta_and_remove_preview_locked_dta():
    index_html = _project_file("desktop/electron/index.html")
    renderer_source = _project_file("desktop/electron/renderer.js")

    assert 'id="navDtaBtn"' in index_html
    assert 'id="view-dta"' in index_html
    assert 'id="navPreviewDtaBtn"' not in index_html

    assert 'setText("navDtaBtn", t("nav.dta"));' in renderer_source
    assert 'el("runDtaAnalysisBtn").addEventListener("click", () => onRunAnalysis("DTA"));' in renderer_source
    assert "DTA Analysis (Experimental)" not in renderer_source
