from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.library_feed import create_library_feed_app
from core.reference_library import ReferenceLibraryManager, build_reference_library_package
from utils.license_manager import APP_VERSION, create_signed_license, encode_license_key


def _manifest_etag(payload: dict) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _write_mirror(root: Path, *, bad_hash: bool = False, delivery_tier: str = "limited_fallback") -> dict:
    packages_root = root / "packages"
    packages_root.mkdir(parents=True, exist_ok=True)

    archive_name = "openspecy_ftir_core-2026.03-test.zip"
    archive_path = packages_root / archive_name
    sha256 = build_reference_library_package(
        output_path=archive_path,
        package_metadata={
            "package_id": "openspecy_ftir_core",
            "analysis_type": "FTIR",
            "provider": "OpenSpecy",
            "version": "2026.03-test",
            "source_url": "https://example.invalid/openspecy",
            "license_name": "CC-BY-4.0",
            "license_text": "Attribution required.",
            "attribution": "Synthetic OpenSpecy-compatible FTIR seed.",
            "priority": 100,
            "published_at": "2026-03-14T00:00:00Z",
            "generated_at": "2026-03-14T00:00:00Z",
            "provider_dataset_version": "2026.03.14",
            "builder_version": "b1",
            "normalized_schema_version": 1,
            "delivery_tier": delivery_tier,
        },
        entries=[
            {
                "candidate_id": "ftir_polymer_a",
                "candidate_name": "Polymer A",
                "axis": [500.0, 1000.0, 1500.0],
                "signal": [0.25, 1.0, 0.45],
            },
            {
                "candidate_id": "ftir_polymer_b",
                "candidate_name": "Polymer B",
                "axis": [500.0, 1000.0, 1500.0],
                "signal": [0.2, 0.85, 0.6],
            },
        ],
    )

    manifest = {
        "schema_version": 1,
        "generated_at": "2026-03-14T00:00:00Z",
        "providers": [
            {
                "provider_id": "openspecy",
                "name": "OpenSpecy",
                "modalities": ["FTIR"],
                "source_url": "https://example.invalid/openspecy",
                "license_name": "CC-BY-4.0",
                "license_text": "Attribution required.",
                "attribution": "Synthetic OpenSpecy-compatible FTIR seed.",
            }
        ],
        "packages": [
            {
                "package_id": "openspecy_ftir_core",
                "analysis_type": "FTIR",
                "provider": "OpenSpecy",
                "version": "2026.03-test",
                "archive_name": archive_name,
                "sha256": "0" * 64 if bad_hash else sha256,
                "entry_count": 2,
                "source_url": "https://example.invalid/openspecy",
                "license_name": "CC-BY-4.0",
                "license_text": "Attribution required.",
                "attribution": "Synthetic OpenSpecy-compatible FTIR seed.",
                "priority": 100,
                "published_at": "2026-03-14T00:00:00Z",
                "generated_at": "2026-03-14T00:00:00Z",
                "provider_dataset_version": "2026.03.14",
                "builder_version": "b1",
                "normalized_schema_version": 1,
                "delivery_tier": delivery_tier,
            }
        ],
    }
    manifest["etag"] = _manifest_etag(manifest)
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _write_xrd_mirror(root: Path) -> dict:
    packages_root = root / "packages"
    packages_root.mkdir(parents=True, exist_ok=True)

    archive_name = "cod_xrd_core-2026.03-test.zip"
    archive_path = packages_root / archive_name
    sha256 = build_reference_library_package(
        output_path=archive_path,
        package_metadata={
            "package_id": "cod_xrd_core",
            "analysis_type": "XRD",
            "provider": "COD",
            "version": "2026.03-test",
            "source_url": "https://example.invalid/cod",
            "license_name": "CC0-1.0",
            "attribution": "Synthetic COD-compatible XRD seed.",
            "priority": 100,
            "published_at": "2026-03-14T00:00:00Z",
            "generated_at": "2026-03-13T21:45:00Z",
            "provider_dataset_version": "2026.03-curated",
            "builder_version": "m003-test",
            "normalized_schema_version": 2,
            "curation_note": "Preserve additive metadata during package load.",
        },
        entries=[
            {
                "candidate_id": "xrd_phase_alpha",
                "candidate_name": "Phase Alpha",
                "phase_family": "oxide",
                "aliases": ["alpha-main", "alpha-ref"],
                "peaks": [
                    {"position": 18.37, "intensity": 0.62, "d_spacing": 4.828},
                    {"position": 33.18, "intensity": 1.0, "d_spacing": 2.698},
                    {"position": 47.76, "intensity": 0.84, "d_spacing": 1.902},
                ],
            }
        ],
    )

    manifest = {
        "schema_version": 1,
        "generated_at": "2026-03-14T00:00:00Z",
        "providers": [
            {
                "provider_id": "cod",
                "name": "COD",
                "modalities": ["XRD"],
                "source_url": "https://example.invalid/cod",
                "license_name": "CC0-1.0",
                "attribution": "Synthetic COD-compatible XRD seed.",
            }
        ],
        "packages": [
            {
                "package_id": "cod_xrd_core",
                "analysis_type": "XRD",
                "provider": "COD",
                "version": "2026.03-test",
                "archive_name": archive_name,
                "sha256": sha256,
                "entry_count": 1,
                "source_url": "https://example.invalid/cod",
                "license_name": "CC0-1.0",
                "attribution": "Synthetic COD-compatible XRD seed.",
                "priority": 100,
                "published_at": "2026-03-14T00:00:00Z",
                "generated_at": "2026-03-13T21:45:00Z",
                "provider_dataset_version": "2026.03-curated",
                "builder_version": "m003-test",
                "normalized_schema_version": 2,
            }
        ],
    }
    manifest["etag"] = _manifest_etag(manifest)
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _auth_headers() -> dict[str, str]:
    return {"X-TA-Token": "test-token"}


def _license_header(*, sku: str, expires_at: datetime) -> str:
    payload = create_signed_license(
        customer_name="Test User",
        company_name="QA Lab",
        sku=sku,
        seat_count=1,
        issued_at=datetime(2026, 3, 14, tzinfo=UTC),
        expires_at=expires_at,
        allowed_major_version=2,
        machine_fingerprint="different-machine-ok-for-feed",
    )
    return encode_license_key(payload)


def test_reference_library_manager_syncs_catalog_from_file_mirror(tmp_path, monkeypatch):
    home_root = tmp_path / "home"
    mirror_root = tmp_path / "mirror"
    _write_mirror(mirror_root)
    monkeypatch.setenv("THERMOANALYZER_HOME", str(home_root))

    manager = ReferenceLibraryManager(feed_source=mirror_root.as_uri())

    initial = manager.status()
    assert initial["cache_status"] == "cold"
    assert initial["available_package_count"] == 0

    checked = manager.check_manifest(force=True)
    assert checked["available_package_count"] == 1
    assert checked["available_provider_count"] == 1
    assert checked["manifest_generated_at"] == "2026-03-14T00:00:00Z"

    synced = manager.sync(force=True)
    assert synced["sync_mode"] == "online_sync"
    assert synced["cache_status"] == "warm"
    assert synced["installed_package_count"] == 1
    assert synced["installed_entry_count"] == 2

    catalog = manager.catalog()
    assert len(catalog) == 1
    assert catalog[0]["installed"] is True
    assert catalog[0]["license_name"] == "CC-BY-4.0"

    entries = manager.load_entries("FTIR")
    assert len(entries) == 2
    assert entries[0]["package_id"] == "openspecy_ftir_core"


def test_reference_library_manager_reports_not_configured_without_feed_source(monkeypatch):
    monkeypatch.delenv("THERMOANALYZER_LIBRARY_FEED_URL", raising=False)
    monkeypatch.delenv("THERMOANALYZER_LIBRARY_MIRROR_ROOT", raising=False)

    manager = ReferenceLibraryManager()

    status = manager.check_manifest(force=True)
    assert status["feed_configured"] is False
    assert status["sync_mode"] == "not_synced"
    assert "not configured" in status["last_error"].lower()


def test_reference_library_manager_preserves_additive_xrd_metadata_and_d_spacing(tmp_path, monkeypatch):
    home_root = tmp_path / "home"
    mirror_root = tmp_path / "mirror"
    _write_xrd_mirror(mirror_root)
    monkeypatch.setenv("THERMOANALYZER_HOME", str(home_root))

    manager = ReferenceLibraryManager(feed_source=mirror_root.as_uri())
    manager.sync(force=True)

    entries = manager.load_entries("XRD")
    assert len(entries) == 1
    assert entries[0]["candidate_id"] == "xrd_phase_alpha"
    assert entries[0]["phase_family"] == "oxide"
    assert entries[0]["aliases"] == ["alpha-main", "alpha-ref"]
    assert entries[0]["package_metadata"]["curation_note"] == "Preserve additive metadata during package load."
    assert entries[0]["builder_version"] == "m003-test"
    assert entries[0]["provider_dataset_version"] == "2026.03-curated"
    assert entries[0]["normalized_schema_version"] == 2
    assert entries[0]["peaks"][0]["d_spacing"] == 4.828
    assert entries[0]["d_spacing"] == [4.828, 2.698, 1.902]
    assert entries[0]["generated_at"] == "2026-03-13T21:45:00Z"


def test_reference_library_manager_requires_explicit_feed_configuration(tmp_path, monkeypatch):
    home_root = tmp_path / "home"
    monkeypatch.setenv("THERMOANALYZER_HOME", str(home_root))
    monkeypatch.delenv("THERMOANALYZER_LIBRARY_FEED_URL", raising=False)
    monkeypatch.delenv("THERMOANALYZER_LIBRARY_MIRROR_ROOT", raising=False)

    manager = ReferenceLibraryManager(root=home_root / "libraries")
    status = manager.status()

    assert status["feed_configured"] is False
    assert status["sync_mode"] == "not_synced"
    assert status["library_mode"] == "not_configured"
    assert "not configured" in status["last_error"].lower() or status["last_error"] == ""


def test_reference_library_manager_falls_back_to_cached_read_only_when_feed_disappears(tmp_path, monkeypatch):
    home_root = tmp_path / "home"
    mirror_root = tmp_path / "mirror"
    _write_mirror(mirror_root)
    monkeypatch.setenv("THERMOANALYZER_HOME", str(home_root))

    online_manager = ReferenceLibraryManager(root=home_root / "libraries", feed_source=mirror_root.as_uri())
    online_manager.sync(force=True)

    missing_feed = (tmp_path / "missing-mirror").as_uri()
    offline_manager = ReferenceLibraryManager(root=home_root / "libraries", feed_source=missing_feed)
    try:
        offline_manager.check_manifest(force=True)
    except Exception:
        pass

    status = offline_manager.status()
    assert status["cache_status"] == "warm"
    assert status["sync_mode"] == "cached_read_only"
    assert offline_manager.count_installed_candidates("FTIR") == 2


def test_reference_library_manager_rejects_sha256_mismatch(tmp_path, monkeypatch):
    home_root = tmp_path / "home"
    mirror_root = tmp_path / "mirror"
    _write_mirror(mirror_root, bad_hash=True)
    monkeypatch.setenv("THERMOANALYZER_HOME", str(home_root))

    manager = ReferenceLibraryManager(feed_source=mirror_root.as_uri())

    try:
        manager.sync(force=True)
    except ValueError as exc:
        assert "hash mismatch" in str(exc)
    else:
        raise AssertionError("Expected sync() to reject a bad sha256 hash.")


def test_reference_library_manager_blocks_full_provider_packages_by_default(tmp_path, monkeypatch):
    home_root = tmp_path / "home"
    mirror_root = tmp_path / "mirror"
    _write_mirror(mirror_root, delivery_tier="full_provider")
    monkeypatch.setenv("THERMOANALYZER_HOME", str(home_root))
    monkeypatch.delenv("THERMOANALYZER_LIBRARY_ALLOW_FULL_PROVIDER_SYNC", raising=False)

    manager = ReferenceLibraryManager(feed_source=mirror_root.as_uri())
    status = manager.sync(force=True)

    assert status["installed_package_count"] == 0
    assert "delivery-tier policy" in str(status["last_error"]).lower()
    catalog = manager.catalog()
    assert catalog[0]["delivery_tier"] == "full_provider"


def test_reference_library_manager_allows_full_provider_packages_with_dev_override(tmp_path, monkeypatch):
    home_root = tmp_path / "home"
    mirror_root = tmp_path / "mirror"
    _write_mirror(mirror_root, delivery_tier="full_provider")
    monkeypatch.setenv("THERMOANALYZER_HOME", str(home_root))
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_ALLOW_FULL_PROVIDER_SYNC", "1")

    manager = ReferenceLibraryManager(feed_source=mirror_root.as_uri())
    status = manager.sync(force=True)

    assert status["installed_package_count"] == 1
    assert status["cache_status"] == "warm"


def test_reference_library_manager_degrades_to_limited_fallback_after_cloud_failure(tmp_path, monkeypatch):
    home_root = tmp_path / "home"
    mirror_root = tmp_path / "mirror"
    _write_mirror(mirror_root)
    monkeypatch.setenv("THERMOANALYZER_HOME", str(home_root))
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_CLOUD_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_CLOUD_ENABLED", "true")

    manager = ReferenceLibraryManager(feed_source=mirror_root.as_uri())
    manager.sync(force=True)
    manager.record_cloud_lookup(success=True, provider_count=2)

    assert manager.status()["library_mode"] == "cloud_full_access"

    manager.record_cloud_lookup(success=False, error="cloud unreachable")
    status = manager.status()
    assert status["library_mode"] == "limited_cached_fallback"
    assert status["cloud_access_enabled"] is False
    assert status["last_cloud_error"] == "cloud unreachable"


def test_library_feed_enforces_license_statuses(tmp_path):
    mirror_root = tmp_path / "mirror"
    manifest = _write_mirror(mirror_root)
    app = create_library_feed_app(mirror_root=mirror_root)
    client = TestClient(app)

    trial_header = {"X-TA-License": _license_header(sku="TRIAL", expires_at=datetime(2026, 3, 28, tzinfo=UTC))}
    activated_header = {"X-TA-License": _license_header(sku="PRO", expires_at=datetime(2026, 6, 1, tzinfo=UTC))}
    expired_header = {"X-TA-License": _license_header(sku="PRO", expires_at=datetime(2026, 3, 1, tzinfo=UTC))}

    manifest_response = client.get("/v1/library/manifest", headers=trial_header)
    assert manifest_response.status_code == 200
    assert manifest_response.headers["etag"] == manifest["etag"]

    package_response = client.get("/v1/library/packages/openspecy_ftir_core", headers=activated_header)
    assert package_response.status_code == 200
    assert package_response.headers["content-disposition"].endswith('"openspecy_ftir_core-2026.03-test.zip"')

    expired_response = client.get("/v1/library/manifest", headers=expired_header)
    assert expired_response.status_code == 403

    missing_response = client.get("/v1/library/manifest")
    assert missing_response.status_code == 401


def test_backend_library_routes_surface_status_catalog_and_sync(tmp_path, monkeypatch):
    home_root = tmp_path / "home"
    mirror_root = tmp_path / "mirror"
    _write_mirror(mirror_root)
    monkeypatch.setenv("THERMOANALYZER_HOME", str(home_root))
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_MIRROR_ROOT", str(mirror_root))

    app = create_app(api_token="test-token")
    client = TestClient(app)

    status_response = client.get("/library/status", headers=_auth_headers())
    assert status_response.status_code == 200
    assert status_response.json()["cache_status"] == "cold"
    assert status_response.json()["manifest_generated_at"] == "2026-03-14T00:00:00Z"

    sync_response = client.post("/library/sync", headers=_auth_headers(), json={"force": True})
    assert sync_response.status_code == 200
    sync_payload = sync_response.json()["status"]
    assert sync_payload["sync_mode"] == "online_sync"
    assert sync_payload["installed_package_count"] == 1

    catalog_response = client.get("/library/catalog", headers=_auth_headers())
    assert catalog_response.status_code == 200
    catalog_payload = catalog_response.json()
    assert catalog_payload["status"]["installed_package_count"] == 1
    assert catalog_payload["libraries"][0]["package_id"] == "openspecy_ftir_core"
    assert catalog_payload["libraries"][0]["installed"] is True
    assert catalog_payload["libraries"][0]["published_at"] == "2026-03-14T00:00:00Z"


def test_backend_library_routes_require_auth_token(tmp_path, monkeypatch):
    home_root = tmp_path / "home"
    mirror_root = tmp_path / "mirror"
    _write_mirror(mirror_root)
    monkeypatch.setenv("THERMOANALYZER_HOME", str(home_root))
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_MIRROR_ROOT", str(mirror_root))

    client = TestClient(create_app(api_token="test-token"))
    response = client.get("/library/status")
    assert response.status_code == 401
    assert "token" in response.json()["detail"].lower()
