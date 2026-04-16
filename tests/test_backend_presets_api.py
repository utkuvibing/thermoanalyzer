"""Tests for the `/presets/{analysis_type}` FastAPI routes (Phase 3b).

These tests isolate the preset SQLite store from the real user storage dir by
pointing ``MATERIALSCOPE_HOME`` at a pytest ``tmp_path``. They cover the full
CRUD happy path plus the three explicit error paths the Dash-side UI relies on
(`PresetLimitError` -> 409, `PresetStoreError` -> 400, missing preset -> 404).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from core.preset_store import MAX_PRESETS_PER_ANALYSIS


TOKEN = "phase3b-token"
HEADERS = {"X-TA-Token": TOKEN}


def _dta_processing_payload(template: str = "dta.general") -> dict:
    """Minimal processing payload the preset store will accept for DTA."""
    return {
        "smoothing": {"method": "savgol", "window_length": 11, "polyorder": 3},
        "baseline": {"method": "asls", "lam": 1e7, "p": 0.001},
        "peak_detection": {"min_prominence": 0.01, "min_distance_c": 5.0},
    }


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("MATERIALSCOPE_HOME", str(tmp_path))
    app = create_app(api_token=TOKEN)
    return TestClient(app)


def test_presets_list_returns_empty_envelope_for_fresh_storage(client: TestClient) -> None:
    response = client.get("/presets/DTA", headers=HEADERS)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["analysis_type"] == "DTA"
    assert body["count"] == 0
    assert body["max_count"] == MAX_PRESETS_PER_ANALYSIS
    assert body["presets"] == []


def test_presets_save_and_list_roundtrip(client: TestClient) -> None:
    save_response = client.post(
        "/presets/DTA",
        headers=HEADERS,
        json={
            "preset_name": "dta-baseline-slow",
            "workflow_template_id": "dta.general",
            "processing": _dta_processing_payload(),
        },
    )
    assert save_response.status_code == 200, save_response.text
    save_body = save_response.json()
    assert save_body["analysis_type"] == "DTA"
    assert save_body["preset_name"] == "dta-baseline-slow"
    assert save_body["workflow_template_id"] == "dta.general"
    assert save_body["updated_at"]

    list_response = client.get("/presets/DTA", headers=HEADERS)
    assert list_response.status_code == 200
    list_body = list_response.json()
    assert list_body["count"] == 1
    names = [item["preset_name"] for item in list_body["presets"]]
    assert names == ["dta-baseline-slow"]
    assert list_body["presets"][0]["workflow_template_id"] == "dta.general"


def test_presets_save_upserts_same_name_without_consuming_slot(client: TestClient) -> None:
    for index in range(MAX_PRESETS_PER_ANALYSIS):
        ok = client.post(
            "/presets/DTA",
            headers=HEADERS,
            json={
                "preset_name": f"dta-{index}",
                "workflow_template_id": "dta.general",
                "processing": _dta_processing_payload(),
            },
        )
        assert ok.status_code == 200

    upsert = client.post(
        "/presets/DTA",
        headers=HEADERS,
        json={
            "preset_name": "dta-0",
            "workflow_template_id": "dta.thermal_events",
            "processing": _dta_processing_payload("dta.thermal_events"),
        },
    )
    assert upsert.status_code == 200, upsert.text
    assert upsert.json()["workflow_template_id"] == "dta.thermal_events"

    count = client.get("/presets/DTA", headers=HEADERS).json()["count"]
    assert count == MAX_PRESETS_PER_ANALYSIS


def test_presets_save_rejects_overflow_with_409(client: TestClient) -> None:
    for index in range(MAX_PRESETS_PER_ANALYSIS):
        client.post(
            "/presets/DTA",
            headers=HEADERS,
            json={
                "preset_name": f"dta-{index}",
                "workflow_template_id": "dta.general",
                "processing": _dta_processing_payload(),
            },
        )

    overflow = client.post(
        "/presets/DTA",
        headers=HEADERS,
        json={
            "preset_name": "dta-overflow",
            "workflow_template_id": "dta.general",
            "processing": _dta_processing_payload(),
        },
    )
    assert overflow.status_code == 409, overflow.text
    assert "limit" in overflow.json()["detail"].lower()


def test_presets_save_rejects_empty_name_with_400(client: TestClient) -> None:
    response = client.post(
        "/presets/DTA",
        headers=HEADERS,
        json={
            "preset_name": "   ",
            "workflow_template_id": "dta.general",
            "processing": _dta_processing_payload(),
        },
    )
    assert response.status_code == 400, response.text
    assert "name" in response.json()["detail"].lower()


def test_presets_load_returns_404_for_unknown_name(client: TestClient) -> None:
    response = client.get("/presets/DTA/does-not-exist", headers=HEADERS)
    assert response.status_code == 404
    assert "does-not-exist" in response.json()["detail"]


def test_presets_load_returns_normalized_payload(client: TestClient) -> None:
    client.post(
        "/presets/DTA",
        headers=HEADERS,
        json={
            "preset_name": "dta-loadable",
            "workflow_template_id": "dta.general",
            "processing": _dta_processing_payload(),
        },
    )
    response = client.get("/presets/DTA/dta-loadable", headers=HEADERS)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["preset_name"] == "dta-loadable"
    assert body["workflow_template_id"] == "dta.general"
    processing = body["processing"]
    assert processing["workflow_template_id"] == "dta.general"
    assert processing["smoothing"]["method"] == "savgol"
    assert processing["baseline"]["method"] == "asls"


def test_presets_delete_then_idempotent_404(client: TestClient) -> None:
    client.post(
        "/presets/DTA",
        headers=HEADERS,
        json={
            "preset_name": "dta-delete-me",
            "workflow_template_id": "dta.general",
            "processing": _dta_processing_payload(),
        },
    )
    first = client.delete("/presets/DTA/dta-delete-me", headers=HEADERS)
    assert first.status_code == 200, first.text
    assert first.json() == {
        "analysis_type": "DTA",
        "preset_name": "dta-delete-me",
        "deleted": True,
    }

    second = client.delete("/presets/DTA/dta-delete-me", headers=HEADERS)
    assert second.status_code == 404


def test_presets_routes_require_api_token(client: TestClient) -> None:
    unauth = client.get("/presets/DTA")
    assert unauth.status_code == 401

    bad_token = client.post(
        "/presets/DTA",
        headers={"X-TA-Token": "wrong"},
        json={
            "preset_name": "dta-anything",
            "workflow_template_id": "dta.general",
            "processing": _dta_processing_payload(),
        },
    )
    assert bad_token.status_code == 401


def test_presets_unsupported_analysis_type_returns_400(client: TestClient) -> None:
    response = client.get("/presets/FOO", headers=HEADERS)
    assert response.status_code == 400
    assert "analysis type" in response.json()["detail"].lower()
