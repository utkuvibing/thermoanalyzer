from __future__ import annotations

import base64
import io
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi.testclient import TestClient

from backend.app import create_app
from core.hosted_library import build_hosted_manifest, write_hosted_dataset
from core.library_cloud_client import ManagedLibraryCloudClient
from core.project_io import PROJECT_EXTENSION, load_project_archive, save_project_archive
from core.reference_library import get_reference_library_manager
from tools.library_ingest.common import write_normalized_package
from tools.library_ingest.schema import PackageSpec, normalized_spectral_entry, normalized_xrd_entry
from utils.license_manager import APP_VERSION, create_signed_license, encode_license_key


def _auth_headers() -> dict[str, str]:
    return {"X-TA-Token": "test-token"}


def _as_b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


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


def _cloud_license_header() -> dict[str, str]:
    payload = create_signed_license(
        customer_name="Cloud Test User",
        company_name="Cloud QA",
        sku="TRIAL",
        seat_count=1,
        issued_at=datetime.fromisoformat("2026-03-14T00:00:00+00:00"),
        expires_at=datetime.fromisoformat("2026-04-14T00:00:00+00:00"),
        allowed_major_version=2,
        machine_fingerprint="cloud-test-client",
    )
    return {"X-TA-License": encode_license_key(payload)}


def _cloud_bearer_header(client: TestClient) -> dict[str, str]:
    auth_response = client.post("/v1/library/auth/token", headers=_cloud_license_header())
    assert auth_response.status_code == 200
    auth_payload = auth_response.json()
    assert auth_payload["token_type"] == "bearer"
    assert auth_payload["request_id"]
    return {"Authorization": f"Bearer {auth_payload['access_token']}"}


def _run_cloud_smoke_chain(client: TestClient, bearer: dict[str, str]) -> None:
    providers_response = client.get("/v1/library/providers", headers=bearer)
    assert providers_response.status_code == 200
    providers_payload = providers_response.json()
    assert providers_payload["library_access_mode"] == "cloud_full_access"
    assert providers_payload["request_id"]
    assert isinstance(providers_payload["providers"], list)
    assert any(item["provider_id"] == "openspecy" for item in providers_payload["providers"])

    coverage_response = client.get("/v1/library/coverage", headers=bearer)
    assert coverage_response.status_code == 200
    coverage_payload = coverage_response.json()
    assert coverage_payload["library_access_mode"] == "cloud_full_access"
    assert coverage_payload["request_id"]
    assert isinstance(coverage_payload["coverage"], dict)
    for modality in ("FTIR", "RAMAN", "XRD"):
        assert coverage_payload["coverage"][modality]["total_candidate_count"] >= 1
        assert "providers" in coverage_payload["coverage"][modality]
    assert coverage_payload["coverage"]["XRD"]["providers"]["cod"]["dataset_version"] == "2026.03.fixture"
    assert coverage_payload["coverage"]["XRD"]["coverage_tier"] == "seed_dev"
    assert coverage_payload["coverage"]["XRD"]["coverage_warning_code"] == "xrd_seed_coverage_only"

    ftir_response = client.post(
        "/v1/library/search/ftir",
        headers=bearer,
        json={
            "axis": [600.0, 900.0, 1200.0, 1500.0],
            "signal": [0.1, 0.4, 0.2, 0.3],
            "top_n": 3,
            "minimum_score": 0.45,
        },
    )
    assert ftir_response.status_code == 200
    ftir_payload = ftir_response.json()
    assert ftir_payload["analysis_type"] == "FTIR"
    assert ftir_payload["library_access_mode"] == "cloud_full_access"
    assert ftir_payload["library_result_source"] == "cloud_search"
    assert ftir_payload["request_id"]
    assert ftir_payload["summary"]["active_dataset_version"] == "2026.03.fixture"
    assert ftir_payload["rows"][0]["evidence"]["hosted_dataset_version"] == "2026.03.fixture"

    raman_response = client.post(
        "/v1/library/search/raman",
        headers=bearer,
        json={
            "axis": [450.0, 700.0, 1000.0, 1350.0],
            "signal": [0.11, 0.35, 0.5, 0.27],
            "top_n": 3,
            "minimum_score": 0.45,
        },
    )
    assert raman_response.status_code == 200
    raman_payload = raman_response.json()
    assert raman_payload["analysis_type"] == "RAMAN"
    assert raman_payload["library_access_mode"] == "cloud_full_access"
    assert raman_payload["library_result_source"] == "cloud_search"
    assert raman_payload["request_id"]
    assert raman_payload["summary"]["active_dataset_version"] == "2026.03.fixture"
    assert raman_payload["rows"][0]["evidence"]["hosted_dataset_version"] == "2026.03.fixture"
    assert "provider_alternates" in raman_payload["rows"][0]["evidence"]

    xrd_response = client.post(
        "/v1/library/search/xrd",
        headers=bearer,
        json={
            "observed_peaks": [
                {"position": 18.4, "intensity": 0.72},
                {"position": 33.2, "intensity": 1.0},
                {"position": 47.8, "intensity": 0.85},
            ],
            "xrd_axis_role": "two_theta",
            "xrd_axis_unit": "degree_2theta",
            "xrd_wavelength_angstrom": 1.5406,
        },
    )
    assert xrd_response.status_code == 200
    xrd_payload = xrd_response.json()
    assert xrd_payload["analysis_type"] == "XRD"
    assert "match_status" in xrd_payload
    assert xrd_payload["library_access_mode"] == "cloud_full_access"
    assert xrd_payload["library_result_source"] == "cloud_search"
    assert xrd_payload["request_id"]
    assert xrd_payload["summary"]["active_dataset_version"] == "2026.03.fixture"
    assert xrd_payload["summary"]["reference_candidate_count"] == 2
    assert xrd_payload["summary"]["xrd_provider_candidate_counts"] == {"cod": 1, "materials_project": 1}
    assert xrd_payload["summary"]["xrd_coverage_tier"] == "seed_dev"
    assert xrd_payload["rows"][0]["evidence"]["hosted_dataset_version"] == "2026.03.fixture"


def _route_runtime_cloud_client(monkeypatch, api_client: TestClient) -> None:
    def _path(url: str) -> str:
        parsed = urlparse(url)
        return parsed.path or "/"

    def _post(url: str, *, headers=None, timeout=None):
        return api_client.post(_path(url), headers=headers)

    def _request(method: str, url: str, *, json=None, headers=None, timeout=None):
        return api_client.request(method, _path(url), headers=headers, json=json)

    monkeypatch.setattr("core.library_cloud_client.httpx.post", _post)
    monkeypatch.setattr("core.library_cloud_client.httpx.request", _request)
    monkeypatch.setattr("core.library_cloud_client.httpx.get", lambda url, *, timeout=None: api_client.get(_path(url)))


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _wait_for_backend_health(base_url: str, *, timeout_seconds: float = 20.0) -> dict[str, object]:
    deadline = time.time() + float(timeout_seconds)
    last_error = ""
    while time.time() < deadline:
        try:
            response = httpx.get(f"{base_url}/health", timeout=1.5)
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict):
                return payload
            last_error = f"Non-object /health payload: {payload!r}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(0.2)
    raise AssertionError(f"Backend did not become healthy at {base_url}: {last_error}")


def _write_hosted_root(root: Path) -> None:
    datasets = []
    datasets.append(
        {
            **write_hosted_dataset(
                output_dir=root / "datasets" / "ftir" / "openspecy" / "2026.03.fixture",
                dataset_metadata={
                    "dataset_id": "openspecy_ftir_2026_03_fixture",
                    "provider_id": "openspecy",
                    "provider": "OpenSpecy",
                    "modality": "FTIR",
                    "dataset_version": "2026.03.fixture",
                    "published_at": "2026-03-14T00:00:00Z",
                    "generated_at": "2026-03-14T00:00:00Z",
                    "last_successful_ingest_at": "2026-03-14T00:00:00Z",
                    "failed_ingest_count": 0,
                    "candidate_count": 2,
                    "deduped_candidate_count": 2,
                    "provider_dataset_version": "2026.03.fixture",
                    "builder_version": "b1",
                    "normalized_schema_version": 1,
                },
                entries=[
                    {
                        "candidate_id": "openspecy_ftir_polymer_a",
                        "candidate_name": "Polymer A",
                        "axis": [600.0, 900.0, 1200.0, 1500.0],
                        "signal": [0.1, 0.4, 0.2, 0.3],
                        "canonical_material_key": "polymer_a",
                    },
                    {
                        "candidate_id": "openspecy_ftir_polymer_b",
                        "candidate_name": "Polymer B",
                        "axis": [600.0, 900.0, 1200.0, 1500.0],
                        "signal": [0.1, 0.3, 0.22, 0.35],
                        "canonical_material_key": "polymer_b",
                    },
                ],
            ),
            "path": "datasets/ftir/openspecy/2026.03.fixture",
            "active": True,
        }
    )
    datasets.append(
        {
            **write_hosted_dataset(
                output_dir=root / "datasets" / "raman" / "openspecy" / "2026.03.fixture",
                dataset_metadata={
                    "dataset_id": "openspecy_raman_2026_03_fixture",
                    "provider_id": "openspecy",
                    "provider": "OpenSpecy",
                    "modality": "RAMAN",
                    "dataset_version": "2026.03.fixture",
                    "published_at": "2026-03-14T00:00:00Z",
                    "generated_at": "2026-03-14T00:00:00Z",
                    "last_successful_ingest_at": "2026-03-14T00:00:00Z",
                    "failed_ingest_count": 0,
                    "candidate_count": 1,
                    "deduped_candidate_count": 1,
                    "provider_dataset_version": "2026.03.fixture",
                    "builder_version": "b1",
                    "normalized_schema_version": 1,
                },
                entries=[
                    {
                        "candidate_id": "openspecy_raman_graphite",
                        "candidate_name": "Graphite",
                        "axis": [450.0, 700.0, 1000.0, 1350.0],
                        "signal": [0.11, 0.35, 0.5, 0.27],
                        "canonical_material_key": "graphite",
                    }
                ],
            ),
            "path": "datasets/raman/openspecy/2026.03.fixture",
            "active": True,
        }
    )
    datasets.append(
        {
            **write_hosted_dataset(
                output_dir=root / "datasets" / "raman" / "rod" / "2026.03.fixture",
                dataset_metadata={
                    "dataset_id": "rod_raman_2026_03_fixture",
                    "provider_id": "rod",
                    "provider": "ROD",
                    "modality": "RAMAN",
                    "dataset_version": "2026.03.fixture",
                    "published_at": "2026-03-14T00:00:00Z",
                    "generated_at": "2026-03-14T00:00:00Z",
                    "last_successful_ingest_at": "2026-03-14T00:00:00Z",
                    "failed_ingest_count": 0,
                    "candidate_count": 1,
                    "deduped_candidate_count": 1,
                    "provider_dataset_version": "2026.03.fixture",
                    "builder_version": "b1",
                    "normalized_schema_version": 1,
                },
                entries=[
                    {
                        "candidate_id": "rod_graphite_2001",
                        "candidate_name": "Graphite",
                        "axis": [450.0, 700.0, 1000.0, 1350.0],
                        "signal": [0.11, 0.35, 0.49, 0.27],
                        "canonical_material_key": "graphite",
                    }
                ],
            ),
            "path": "datasets/raman/rod/2026.03.fixture",
            "active": True,
        }
    )
    datasets.append(
        {
            **write_hosted_dataset(
                output_dir=root / "datasets" / "xrd" / "cod" / "2026.03.fixture",
                dataset_metadata={
                    "dataset_id": "cod_xrd_2026_03_fixture",
                    "provider_id": "cod",
                    "provider": "COD",
                    "modality": "XRD",
                    "dataset_version": "2026.03.fixture",
                    "published_at": "2026-03-14T00:00:00Z",
                    "generated_at": "2026-03-14T00:00:00Z",
                    "last_successful_ingest_at": "2026-03-14T00:00:00Z",
                    "failed_ingest_count": 0,
                    "candidate_count": 1,
                    "deduped_candidate_count": 1,
                    "provider_dataset_version": "2026.03.fixture",
                    "builder_version": "b1",
                    "normalized_schema_version": 1,
                },
                entries=[
                    {
                        "candidate_id": "cod_phase_alpha",
                        "candidate_name": "Phase Alpha",
                        "canonical_material_key": "phase_alpha",
                        "peaks": [
                            {"position": 18.4, "intensity": 0.72, "d_spacing": 4.82},
                            {"position": 33.2, "intensity": 1.0, "d_spacing": 2.70},
                            {"position": 47.8, "intensity": 0.85, "d_spacing": 1.90},
                        ],
                    }
                ],
            ),
            "path": "datasets/xrd/cod/2026.03.fixture",
            "active": True,
        }
    )
    datasets.append(
        {
            **write_hosted_dataset(
                output_dir=root / "datasets" / "xrd" / "materials_project" / "2026.03.fixture",
                dataset_metadata={
                    "dataset_id": "materials_project_xrd_2026_03_fixture",
                    "provider_id": "materials_project",
                    "provider": "Materials Project",
                    "modality": "XRD",
                    "dataset_version": "2026.03.fixture",
                    "published_at": "2026-03-14T00:00:00Z",
                    "generated_at": "2026-03-14T00:00:00Z",
                    "last_successful_ingest_at": "2026-03-14T00:00:00Z",
                    "failed_ingest_count": 0,
                    "candidate_count": 1,
                    "deduped_candidate_count": 1,
                    "provider_dataset_version": "2026.03.fixture",
                    "builder_version": "b1",
                    "normalized_schema_version": 1,
                },
                entries=[
                    {
                        "candidate_id": "materials_project_phase_beta",
                        "candidate_name": "Phase Beta",
                        "canonical_material_key": "phase_beta",
                        "peaks": [
                            {"position": 22.1, "intensity": 0.55, "d_spacing": 4.01},
                            {"position": 36.0, "intensity": 1.0, "d_spacing": 2.49},
                            {"position": 41.5, "intensity": 0.72, "d_spacing": 2.17},
                        ],
                    }
                ],
            ),
            "path": "datasets/xrd/materials_project/2026.03.fixture",
            "active": True,
        }
    )
    manifest = build_hosted_manifest(generated_at="2026-03-14T00:00:00Z", datasets=datasets)
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _write_seed_xrd_manifest(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-03-14T00:00:00Z",
                "providers": [],
                "datasets": [
                    {
                        "dataset_id": "cod_xrd_seed",
                        "provider_id": "cod",
                        "provider": "COD",
                        "modality": "XRD",
                        "dataset_version": "2026.03.seed",
                        "candidate_count": 4,
                        "deduped_candidate_count": 4,
                        "published_at": "2026-03-14T00:00:00Z",
                        "active": True,
                    },
                    {
                        "dataset_id": "materials_project_xrd_seed",
                        "provider_id": "materials_project",
                        "provider": "Materials Project",
                        "modality": "XRD",
                        "dataset_version": "2026.03.seed",
                        "candidate_count": 2,
                        "deduped_candidate_count": 2,
                        "published_at": "2026-03-14T00:00:00Z",
                        "active": True,
                    },
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _package_spec(*, package_id: str, analysis_type: str, provider: str) -> PackageSpec:
    return PackageSpec(
        package_id=package_id,
        analysis_type=analysis_type,
        provider=provider,
        version="2026.03.fixture-b1",
        source_url=f"https://example.invalid/{provider}",
        license_name="Fixture License",
        license_text="Fixture License Text",
        attribution=f"{provider} fixture",
        priority=1,
        published_at="2026-03-14T00:00:00Z",
        generated_at="2026-03-14T00:00:00Z",
        provider_dataset_version="2026.03.fixture",
        builder_version="b1",
        normalized_schema_version=1,
    )


def _write_normalized_root(root: Path) -> None:
    write_normalized_package(
        root / "openspecy" / "openspecy_ftir_0001",
        _package_spec(package_id="openspecy_ftir_0001", analysis_type="FTIR", provider="OpenSpecy"),
        [
            normalized_spectral_entry(
                candidate_id="openspecy_ftir_polymer_a",
                candidate_name="Polymer A",
                provider="OpenSpecy",
                source_id="ftir-001",
                source_url="https://example.invalid/openspecy/ftir-001",
                axis=[600.0, 900.0, 1200.0, 1500.0],
                signal=[0.1, 0.4, 0.2, 0.3],
                generated_at="2026-03-14T00:00:00Z",
                provider_dataset_version="2026.03.fixture",
                builder_version="b1",
                normalized_schema_version=1,
            )
        ],
    )
    write_normalized_package(
        root / "openspecy" / "openspecy_raman_0001",
        _package_spec(package_id="openspecy_raman_0001", analysis_type="RAMAN", provider="OpenSpecy"),
        [
            normalized_spectral_entry(
                candidate_id="openspecy_raman_graphite",
                candidate_name="Graphite",
                provider="OpenSpecy",
                source_id="raman-001",
                source_url="https://example.invalid/openspecy/raman-001",
                axis=[450.0, 700.0, 1000.0, 1350.0],
                signal=[0.11, 0.35, 0.5, 0.27],
                generated_at="2026-03-14T00:00:00Z",
                provider_dataset_version="2026.03.fixture",
                builder_version="b1",
                normalized_schema_version=1,
            )
        ],
    )
    write_normalized_package(
        root / "rod" / "rod_raman_0001",
        _package_spec(package_id="rod_raman_0001", analysis_type="RAMAN", provider="ROD"),
        [
            normalized_spectral_entry(
                candidate_id="rod_graphite_2001",
                candidate_name="Graphite",
                provider="ROD",
                source_id="rod-2001",
                source_url="https://example.invalid/rod/2001",
                axis=[450.0, 700.0, 1000.0, 1350.0],
                signal=[0.11, 0.35, 0.49, 0.27],
                generated_at="2026-03-14T00:00:00Z",
                provider_dataset_version="2026.03.fixture",
                builder_version="b1",
                normalized_schema_version=1,
            )
        ],
    )
    write_normalized_package(
        root / "cod" / "cod_xrd_0001",
        _package_spec(package_id="cod_xrd_0001", analysis_type="XRD", provider="COD"),
        [
            normalized_xrd_entry(
                candidate_id="cod_phase_alpha",
                candidate_name="Phase Alpha",
                provider="COD",
                source_id="cod-1001",
                source_url="https://example.invalid/cod/1001",
                peaks=[
                    {"position": 18.4, "intensity": 0.72, "d_spacing": 4.82},
                    {"position": 33.2, "intensity": 1.0, "d_spacing": 2.70},
                    {"position": 47.8, "intensity": 0.85, "d_spacing": 1.90},
                ],
                generated_at="2026-03-14T00:00:00Z",
                provider_dataset_version="2026.03.fixture",
                builder_version="b1",
                normalized_schema_version=1,
            )
        ],
    )
    write_normalized_package(
        root / "materials_project" / "materials_project_xrd_0001",
        _package_spec(package_id="materials_project_xrd_0001", analysis_type="XRD", provider="Materials Project"),
        [
            normalized_xrd_entry(
                candidate_id="materials_project_phase_beta",
                candidate_name="Phase Beta",
                provider="Materials Project",
                source_id="mp-149",
                source_url="https://example.invalid/materials-project/mp-149",
                peaks=[
                    {"position": 22.1, "intensity": 0.55, "d_spacing": 4.01},
                    {"position": 36.0, "intensity": 1.0, "d_spacing": 2.49},
                    {"position": 41.5, "intensity": 0.72, "d_spacing": 2.17},
                ],
                generated_at="2026-03-14T00:00:00Z",
                provider_dataset_version="2026.03.fixture",
                builder_version="b1",
                normalized_schema_version=1,
            )
        ],
    )


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


def test_cloud_library_auth_and_search_endpoints(tmp_path, monkeypatch):
    hosted_root = tmp_path / "reference_library_hosted"
    _write_hosted_root(hosted_root)
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_HOSTED_ROOT", str(hosted_root))
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_DEV_CLOUD_AUTH", "false")
    app = create_app(api_token="test-token")
    client = TestClient(app)
    bearer = _cloud_bearer_header(client)
    _run_cloud_smoke_chain(client, bearer)


def test_cloud_library_search_requires_bearer_token():
    app = create_app(api_token="test-token")
    client = TestClient(app)

    response = client.post(
        "/v1/library/search/raman",
        json={"axis": [500.0, 900.0, 1200.0], "signal": [0.1, 0.3, 0.2]},
    )
    assert response.status_code == 401


def test_library_status_reports_limited_fallback_when_cloud_url_missing(tmp_path, monkeypatch):
    home_root = tmp_path / "home"
    mirror_root = Path(__file__).resolve().parents[1] / "sample_data" / "reference_library_mirror"
    monkeypatch.setenv("THERMOANALYZER_HOME", str(home_root))
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_MIRROR_ROOT", str(mirror_root))
    monkeypatch.delenv("THERMOANALYZER_LIBRARY_CLOUD_URL", raising=False)
    monkeypatch.delenv("THERMOANALYZER_LIBRARY_CLOUD_ENABLED", raising=False)

    client = TestClient(create_app(api_token="test-token"))
    sync_response = client.post("/library/sync", headers=_auth_headers(), json={"force": True})
    assert sync_response.status_code == 200

    status_response = client.get("/library/status", headers=_auth_headers())
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["library_mode"] == "limited_cached_fallback"
    assert status_payload["cloud_access_enabled"] is False
    assert status_payload["fallback_package_count"] >= 1
    assert status_payload["fallback_entry_count"] >= 1


def test_library_status_reports_cloud_full_access_after_successful_cloud_calls(tmp_path, monkeypatch):
    home_root = tmp_path / "home"
    mirror_root = Path(__file__).resolve().parents[1] / "sample_data" / "reference_library_mirror"
    hosted_root = tmp_path / "reference_library_hosted"
    _write_hosted_root(hosted_root)
    monkeypatch.setenv("THERMOANALYZER_HOME", str(home_root))
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_MIRROR_ROOT", str(mirror_root))
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_CLOUD_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_CLOUD_ENABLED", "true")
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_ALLOW_FULL_PROVIDER_SYNC", "false")
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_HOSTED_ROOT", str(hosted_root))
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_DEV_CLOUD_AUTH", "false")

    client = TestClient(create_app(api_token="test-token"))
    sync_response = client.post("/library/sync", headers=_auth_headers(), json={"force": True})
    assert sync_response.status_code == 200

    bearer = _cloud_bearer_header(client)
    _run_cloud_smoke_chain(client, bearer)

    status_response = client.get("/library/status", headers=_auth_headers())
    assert status_response.status_code == 200
    status_payload = status_response.json()
    for key in (
        "library_mode",
        "cloud_access_enabled",
        "cloud_provider_count",
        "fallback_package_count",
        "fallback_entry_count",
        "last_cloud_lookup_at",
        "last_cloud_error",
    ):
        assert key in status_payload
    assert status_payload["library_mode"] == "cloud_full_access"
    assert status_payload["cloud_access_enabled"] is True
    assert status_payload["cloud_provider_count"] >= 1
    assert status_payload["fallback_package_count"] >= 1
    assert status_payload["fallback_entry_count"] >= 1
    assert status_payload["last_cloud_lookup_at"]
    assert status_payload["last_cloud_error"] in {"", None}


def test_library_status_stays_limited_when_hosted_catalog_is_empty(tmp_path, monkeypatch):
    home_root = tmp_path / "home"
    mirror_root = Path(__file__).resolve().parents[1] / "sample_data" / "reference_library_mirror"
    hosted_root = tmp_path / "reference_library_hosted"
    hosted_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("THERMOANALYZER_HOME", str(home_root))
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_MIRROR_ROOT", str(mirror_root))
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_CLOUD_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_CLOUD_ENABLED", "true")
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_HOSTED_ROOT", str(hosted_root))
    monkeypatch.delenv("THERMOANALYZER_LIBRARY_DEV_CLOUD_AUTH", raising=False)

    client = TestClient(create_app(api_token="test-token"))
    sync_response = client.post("/library/sync", headers=_auth_headers(), json={"force": True})
    assert sync_response.status_code == 200

    bearer = _cloud_bearer_header(client)
    coverage_response = client.get("/v1/library/coverage", headers=bearer)
    assert coverage_response.status_code == 200
    coverage_payload = coverage_response.json()
    assert coverage_payload["library_access_mode"] == "limited_cached_fallback"
    assert coverage_payload["coverage"]["XRD"]["providers"] == {}

    status_response = client.get("/library/status", headers=_auth_headers())
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["library_mode"] == "limited_cached_fallback"
    assert status_payload["cloud_access_enabled"] is False
    assert status_payload["cloud_provider_count"] == 0
    assert "hosted" in str(status_payload["last_cloud_error"]).lower()


def test_local_dev_bootstraps_hosted_catalog_from_live_ingest_sibling(tmp_path, monkeypatch):
    home_root = tmp_path / "home"
    mirror_root = Path(__file__).resolve().parents[1] / "sample_data" / "reference_library_mirror"
    hosted_root = tmp_path / "reference_library_hosted"
    normalized_live_root = tmp_path / "reference_library_ingest_live"
    _write_normalized_root(normalized_live_root)
    monkeypatch.setenv("THERMOANALYZER_HOME", str(home_root))
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_MIRROR_ROOT", str(mirror_root))
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_CLOUD_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_CLOUD_ENABLED", "true")
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_HOSTED_ROOT", str(hosted_root))
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_DEV_CLOUD_AUTH", "1")

    client = TestClient(create_app(api_token="test-token"))
    assert (hosted_root / "manifest.json").exists()

    bearer = _cloud_bearer_header(client)
    coverage_response = client.get("/v1/library/coverage", headers=bearer)
    assert coverage_response.status_code == 200
    coverage_payload = coverage_response.json()
    assert coverage_payload["library_access_mode"] == "cloud_full_access"
    assert "cod" in coverage_payload["coverage"]["XRD"]["providers"]

    xrd_response = client.post(
        "/v1/library/search/xrd",
        headers=bearer,
        json={
            "observed_peaks": [
                {"position": 18.4, "intensity": 0.72},
                {"position": 33.2, "intensity": 1.0},
                {"position": 47.8, "intensity": 0.85},
            ],
            "xrd_axis_role": "two_theta",
            "xrd_axis_unit": "degree_2theta",
            "xrd_wavelength_angstrom": 1.5406,
        },
    )
    assert xrd_response.status_code == 200
    xrd_payload = xrd_response.json()
    assert xrd_payload["library_result_source"] == "cloud_search"
    assert xrd_payload["caution_code"] != "xrd_reference_library_unavailable"

    status_response = client.get("/library/status", headers=_auth_headers())
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["library_mode"] == "cloud_full_access"
    assert status_payload["cloud_access_enabled"] is True
    assert status_payload["cloud_provider_count"] >= 1


def test_local_dev_bootstrap_prefers_expanded_sample_data_xrd_corpus(tmp_path, monkeypatch):
    home_root = tmp_path / "home"
    mirror_root = Path(__file__).resolve().parents[1] / "sample_data" / "reference_library_mirror"
    hosted_root = tmp_path / "reference_library_hosted"
    monkeypatch.setenv("THERMOANALYZER_HOME", str(home_root))
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_MIRROR_ROOT", str(mirror_root))
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_CLOUD_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_CLOUD_ENABLED", "true")
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_HOSTED_ROOT", str(hosted_root))
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_DEV_CLOUD_AUTH", "1")

    app = create_app(api_token="test-token")
    client = TestClient(app)
    bootstrap_status = dict(app.state.cloud_library_bootstrap_status or {})
    assert "sample_data" in str(bootstrap_status.get("source_root") or "").lower()

    bearer = _cloud_bearer_header(client)
    coverage_response = client.get("/v1/library/coverage", headers=bearer)
    assert coverage_response.status_code == 200
    coverage_payload = coverage_response.json()
    assert coverage_payload["coverage"]["XRD"]["total_candidate_count"] == 29
    assert coverage_payload["coverage"]["XRD"]["providers"]["cod"]["candidate_count"] == 27
    assert coverage_payload["coverage"]["XRD"]["coverage_tier"] == "expanded"
    assert coverage_payload["coverage"]["XRD"]["coverage_warning_code"] == ""

    xrd_response = client.post(
        "/v1/library/search/xrd",
        headers=bearer,
        json={
            "observed_peaks": [
                {"position": 11.22, "intensity": 0.32},
                {"position": 18.38, "intensity": 1.0},
                {"position": 23.65, "intensity": 0.41},
            ],
            "xrd_axis_role": "two_theta",
            "xrd_axis_unit": "degree_2theta",
            "xrd_wavelength_angstrom": 1.5406,
        },
    )
    assert xrd_response.status_code == 200
    xrd_payload = xrd_response.json()
    assert xrd_payload["library_result_source"] == "cloud_search"
    assert xrd_payload["summary"]["reference_candidate_count"] == 29
    assert xrd_payload["summary"]["xrd_coverage_tier"] == "expanded"


def test_local_dev_bootstrap_upgrades_stale_seed_manifest_to_expanded_runtime(tmp_path, monkeypatch):
    home_root = tmp_path / "home"
    mirror_root = Path(__file__).resolve().parents[1] / "sample_data" / "reference_library_mirror"
    hosted_root = tmp_path / "reference_library_hosted"
    _write_seed_xrd_manifest(hosted_root)
    monkeypatch.setenv("THERMOANALYZER_HOME", str(home_root))
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_MIRROR_ROOT", str(mirror_root))
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_CLOUD_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_CLOUD_ENABLED", "true")
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_HOSTED_ROOT", str(hosted_root))
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_DEV_CLOUD_AUTH", "1")

    app = create_app(api_token="test-token")
    client = TestClient(app)
    bootstrap_status = dict(app.state.cloud_library_bootstrap_status or {})
    assert bootstrap_status["state"] == "upgraded"
    assert "stale_seed_dev_upgraded_to_expanded" in str(bootstrap_status.get("upgrade_reason") or "")
    assert bootstrap_status["previous_xrd_count"] == 6
    assert bootstrap_status["active_xrd_count"] == 29
    assert bootstrap_status["active_coverage_tier"] == "expanded"

    bearer = _cloud_bearer_header(client)
    coverage_response = client.get("/v1/library/coverage", headers=bearer)
    assert coverage_response.status_code == 200
    xrd_coverage = coverage_response.json()["coverage"]["XRD"]
    assert xrd_coverage["total_candidate_count"] == 29
    assert xrd_coverage["provider_candidate_counts"] == {"cod": 27, "materials_project": 2}
    assert xrd_coverage["coverage_tier"] == "expanded"
    assert xrd_coverage["coverage_warning_code"] == ""

    xrd_response = client.post(
        "/v1/library/search/xrd",
        headers=bearer,
        json={
            "observed_peaks": [
                {"position": 11.22, "intensity": 0.32},
                {"position": 18.38, "intensity": 1.0},
                {"position": 23.65, "intensity": 0.41},
            ],
            "xrd_axis_role": "two_theta",
            "xrd_axis_unit": "degree_2theta",
            "xrd_wavelength_angstrom": 1.5406,
        },
    )
    assert xrd_response.status_code == 200
    xrd_payload = xrd_response.json()
    assert xrd_payload["library_result_source"] == "cloud_search"
    assert xrd_payload["summary"]["reference_candidate_count"] == 29
    assert xrd_payload["summary"]["xrd_coverage_tier"] == "expanded"


def test_runtime_cloud_client_stays_strict_without_dev_override(tmp_path, monkeypatch):
    home_root = tmp_path / "home"
    mirror_root = Path(__file__).resolve().parents[1] / "sample_data" / "reference_library_mirror"
    monkeypatch.setenv("THERMOANALYZER_HOME", str(home_root))
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_MIRROR_ROOT", str(mirror_root))
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_CLOUD_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_CLOUD_ENABLED", "true")
    monkeypatch.delenv("THERMOANALYZER_LIBRARY_DEV_CLOUD_AUTH", raising=False)
    monkeypatch.delenv("THERMOANALYZER_COMMERCIAL_MODE", raising=False)

    client = TestClient(create_app(api_token="test-token"))
    sync_response = client.post("/library/sync", headers=_auth_headers(), json={"force": True})
    assert sync_response.status_code == 200

    auth_attempts: list[str] = []

    def _unexpected_post(url: str, *, headers=None, timeout=None):
        auth_attempts.append(url)
        raise AssertionError("Cloud auth/token should not be called without dev override.")

    monkeypatch.setattr("core.library_cloud_client.httpx.post", _unexpected_post)

    cloud_client = ManagedLibraryCloudClient(base_url="http://127.0.0.1:8000")
    assert cloud_client.coverage() is None
    assert auth_attempts == []
    assert "Cloud library access requires trial or activated license status." in cloud_client.last_error
    assert "THERMOANALYZER_LIBRARY_DEV_CLOUD_AUTH=1" in cloud_client.last_error

    manager = get_reference_library_manager()
    manager.record_cloud_lookup(success=False, error=cloud_client.last_error)

    status_response = client.get("/library/status", headers=_auth_headers())
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["library_mode"] == "limited_cached_fallback"
    assert status_payload["cloud_access_enabled"] is False
    assert "trial or activated license status" in str(status_payload["last_cloud_error"])


def test_runtime_cloud_client_reports_connection_refused_precisely(monkeypatch):
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_CLOUD_URL", base_url)
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_CLOUD_ENABLED", "true")
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_DEV_CLOUD_AUTH", "1")

    cloud_client = ManagedLibraryCloudClient(base_url=base_url, timeout_seconds=1.0)
    probe = cloud_client.health_probe()
    assert probe["state"] == "connection_refused"
    assert probe["message"] == f"Cloud backend is not reachable at {base_url}"

    assert cloud_client.coverage() is None
    assert cloud_client.last_error == f"Cloud backend is not reachable at {base_url}"
    assert cloud_client.last_error_kind == "connection_refused"


def test_runtime_cloud_client_dev_override_enables_real_cloud_full_access(tmp_path, monkeypatch):
    home_root = tmp_path / "home"
    mirror_root = Path(__file__).resolve().parents[1] / "sample_data" / "reference_library_mirror"
    hosted_root = tmp_path / "reference_library_hosted"
    _write_hosted_root(hosted_root)
    monkeypatch.setenv("THERMOANALYZER_HOME", str(home_root))
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_MIRROR_ROOT", str(mirror_root))
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_HOSTED_ROOT", str(hosted_root))
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_CLOUD_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_CLOUD_ENABLED", "true")
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_DEV_CLOUD_AUTH", "1")
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_ALLOW_FULL_PROVIDER_SYNC", "false")
    monkeypatch.delenv("THERMOANALYZER_COMMERCIAL_MODE", raising=False)

    client = TestClient(create_app(api_token="test-token"))
    sync_response = client.post("/library/sync", headers=_auth_headers(), json={"force": True})
    assert sync_response.status_code == 200

    _route_runtime_cloud_client(monkeypatch, client)
    cloud_client = ManagedLibraryCloudClient(base_url="http://127.0.0.1:8000")

    providers_payload = cloud_client.providers()
    assert providers_payload is not None
    assert providers_payload["library_access_mode"] == "cloud_full_access"

    coverage_payload = cloud_client.coverage()
    assert coverage_payload is not None
    assert coverage_payload["library_access_mode"] == "cloud_full_access"
    assert "2026." in coverage_payload["coverage"]["XRD"]["providers"]["cod"]["dataset_version"]
    assert coverage_payload["coverage"]["XRD"]["coverage_tier"] == "expanded"

    ftir_payload = cloud_client.search(
        analysis_type="FTIR",
        payload={
            "axis": [600.0, 900.0, 1200.0, 1500.0],
            "signal": [0.1, 0.4, 0.2, 0.3],
            "top_n": 3,
            "minimum_score": 0.45,
        },
    )
    assert ftir_payload is not None
    assert ftir_payload["library_result_source"] == "cloud_search"

    raman_payload = cloud_client.search(
        analysis_type="RAMAN",
        payload={
            "axis": [450.0, 700.0, 1000.0, 1350.0],
            "signal": [0.11, 0.35, 0.5, 0.27],
            "top_n": 3,
            "minimum_score": 0.45,
        },
    )
    assert raman_payload is not None
    assert raman_payload["library_result_source"] == "cloud_search"

    xrd_payload = cloud_client.search(
        analysis_type="XRD",
        payload={
            "observed_peaks": [
                {"position": 18.4, "intensity": 0.72},
                {"position": 33.2, "intensity": 1.0},
                {"position": 47.8, "intensity": 0.85},
            ],
            "xrd_axis_role": "two_theta",
            "xrd_axis_unit": "degree_2theta",
            "xrd_wavelength_angstrom": 1.5406,
        },
    )
    assert xrd_payload is not None
    assert xrd_payload["library_result_source"] == "cloud_search"

    assert cloud_client.dev_auth_override_used is True
    assert cloud_client.last_error == ""

    status_response = client.get("/library/status", headers=_auth_headers())
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["library_mode"] == "cloud_full_access"
    assert status_payload["cloud_access_enabled"] is True
    assert status_payload["cloud_provider_count"] >= 1
    assert status_payload["last_cloud_error"] in {"", None}


def test_backend_main_starts_and_runtime_client_reaches_cloud_chain(tmp_path, monkeypatch):
    home_root = tmp_path / "home"
    hosted_root = tmp_path / "reference_library_hosted"
    mirror_root = Path(__file__).resolve().parents[1] / "sample_data" / "reference_library_mirror"
    _write_hosted_root(hosted_root)
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"

    monkeypatch.setenv("THERMOANALYZER_HOME", str(home_root))
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_MIRROR_ROOT", str(mirror_root))
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_HOSTED_ROOT", str(hosted_root))
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_CLOUD_URL", base_url)
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_CLOUD_ENABLED", "true")
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_DEV_CLOUD_AUTH", "1")

    env = os.environ.copy()
    repo_root = Path(__file__).resolve().parents[1]
    process = subprocess.Popen(
        [sys.executable, "-m", "backend.main", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(repo_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    output = ""
    try:
        health_payload = _wait_for_backend_health(base_url)
        assert health_payload["status"] == "ok"

        auth_response = httpx.post(
            f"{base_url}/v1/library/auth/token",
            headers=_cloud_license_header(),
            timeout=5.0,
        )
        assert auth_response.status_code == 200

        cloud_client = ManagedLibraryCloudClient(base_url=base_url, timeout_seconds=5.0)
        providers_payload = cloud_client.providers()
        assert providers_payload is not None
        assert providers_payload["library_access_mode"] == "cloud_full_access"

        coverage_payload = cloud_client.coverage()
        assert coverage_payload is not None
        assert coverage_payload["library_access_mode"] == "cloud_full_access"
        assert coverage_payload["coverage"]["FTIR"]["total_candidate_count"] >= 1
    finally:
        process.terminate()
        try:
            output, _ = process.communicate(timeout=10.0)
        except subprocess.TimeoutExpired:
            process.kill()
            output, _ = process.communicate(timeout=10.0)

    assert f"ThermoAnalyzer backend starting on {base_url}" in output
    assert f"ThermoAnalyzer backend listening on {base_url}" in output


def test_runtime_cloud_client_production_error_remains_strict_without_dev_hint(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMOANALYZER_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("THERMOANALYZER_COMMERCIAL_MODE", "1")
    monkeypatch.delenv("THERMOANALYZER_LIBRARY_DEV_CLOUD_AUTH", raising=False)

    auth_attempts: list[str] = []

    def _unexpected_post(url: str, *, headers=None, timeout=None):
        auth_attempts.append(url)
        raise AssertionError("Production strict mode should not call cloud auth/token.")

    monkeypatch.setattr("core.library_cloud_client.httpx.post", _unexpected_post)

    cloud_client = ManagedLibraryCloudClient(base_url="https://cloud.thermoanalyzer.example")
    assert cloud_client._acquire_token() is None
    assert auth_attempts == []
    assert cloud_client.last_error == "Cloud library access requires trial or activated license status."


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


def test_streamlit_artifact_exposes_ftir_and_raman_in_primary_navigation():
    app_source = _project_file("app.py")

    assert 'st.Page(ftir_render, title=t("nav.ftir"), icon="🧬", url_path="ftir")' in app_source
    assert 'st.Page(raman_render, title=t("nav.raman"), icon="🔦", url_path="raman")' in app_source


def test_streamlit_artifact_exposes_global_library_management_page():
    app_source = _project_file("app.py")

    assert 'from ui.library_page import render as library_render' in app_source
    assert 'st.Page(library_render, title=tx("Kütüphane", "Library"), icon="🗃️", url_path="library")' in app_source


def test_desktop_artifacts_expose_primary_dta_and_remove_preview_locked_dta():
    index_html = _project_file("desktop/electron/index.html")
    renderer_source = _project_file("desktop/electron/renderer.js")

    assert 'id="navDtaBtn"' in index_html
    assert 'id="view-dta"' in index_html
    assert 'id="navPreviewDtaBtn"' not in index_html

    assert 'setText("navDtaBtn", t("nav.dta"));' in renderer_source
    assert 'el("runDtaAnalysisBtn").addEventListener("click", () => onRunAnalysis("DTA"));' in renderer_source
    assert "DTA Analysis (Experimental)" not in renderer_source


def test_dataset_import_accepts_ftir_with_warning_based_validation_summary():
    app = create_app(api_token="test-token")
    client = TestClient(app)
    project_id = client.post("/workspace/new", headers=_auth_headers()).json()["project_id"]
    csv_bytes = (
        "Wavenumber (cm-1),Absorbance\n"
        "4000,0.10\n"
        "3500,0.22\n"
        "3000,0.15\n"
    ).encode("utf-8")

    response = client.post(
        "/dataset/import",
        headers=_auth_headers(),
        json={
            "project_id": project_id,
            "file_name": "ftir_sample.csv",
            "file_base64": _as_b64(csv_bytes),
            "data_type": "FTIR",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset"]["data_type"] == "FTIR"
    assert payload["validation"]["status"] in {"pass", "warn"}

def test_dataset_import_accepts_xrd_with_contract_metadata():
    app = create_app(api_token="test-token")
    client = TestClient(app)
    project_id = client.post("/workspace/new", headers=_auth_headers()).json()["project_id"]
    xy_bytes = (
        "# wavelength 1.5406\n"
        "2theta intensity\n"
        "10.0 100\n"
        "10.4 130\n"
        "10.8 115\n"
    ).encode("utf-8")

    response = client.post(
        "/dataset/import",
        headers=_auth_headers(),
        json={
            "project_id": project_id,
            "file_name": "sample_pattern.xy",
            "file_base64": _as_b64(xy_bytes),
            "data_type": "XRD",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset"]["data_type"] == "XRD"
    assert payload["validation"]["status"] in {"pass", "warn"}

    dataset_key = payload["dataset"]["key"]
    detail = client.get(f"/workspace/{project_id}/datasets/{dataset_key}", headers=_auth_headers())
    assert detail.status_code == 200
    metadata = detail.json()["metadata"]
    assert metadata["import_format"] == "xrd_xy_dat"
    assert metadata["xrd_axis_role"] == "two_theta"
    assert metadata["xrd_axis_unit"] == "degree_2theta"
    assert metadata["xrd_wavelength_angstrom"] == 1.5406

