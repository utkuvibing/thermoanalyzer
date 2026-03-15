"""Global reference library cache, mirror sync, and provider loading."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import tempfile
import zipfile
from urllib.parse import unquote, urlparse
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping

import httpx
import numpy as np

from utils.license_manager import encode_license_key, get_storage_dir


DEFAULT_BACKGROUND_REFRESH_HOURS = 24
DEFAULT_PRIORITY = 0
MANIFEST_FILE = "manifest.json"
SYNC_STATE_FILE = "sync_state.json"
LIBRARY_ENV_FEED_URL = "THERMOANALYZER_LIBRARY_FEED_URL"
LIBRARY_ENV_MIRROR_ROOT = "THERMOANALYZER_LIBRARY_MIRROR_ROOT"
LIBRARY_ENV_CLOUD_URL = "THERMOANALYZER_LIBRARY_CLOUD_URL"
LIBRARY_ENV_CLOUD_ENABLED = "THERMOANALYZER_LIBRARY_CLOUD_ENABLED"
LIBRARY_ENV_ALLOW_FULL_PROVIDER_SYNC = "THERMOANALYZER_LIBRARY_ALLOW_FULL_PROVIDER_SYNC"
LIBRARY_HEADER = "X-TA-License"
LIBRARY_API_PREFIX = "/v1/library"
DELIVERY_TIER_LIMITED_FALLBACK = "limited_fallback"
DELIVERY_TIER_FULL_PROVIDER = "full_provider"
LIBRARY_MODE_CLOUD_FULL_ACCESS = "cloud_full_access"
LIBRARY_MODE_LIMITED_CACHED_FALLBACK = "limited_cached_fallback"
LIBRARY_MODE_NOT_CONFIGURED = "not_configured"


@dataclass(frozen=True)
class LibraryProvider:
    provider_id: str
    name: str
    modalities: tuple[str, ...] = ()
    source_url: str = ""
    license_name: str = ""
    license_text: str = ""
    attribution: str = ""


@dataclass(frozen=True)
class LibraryPackage:
    package_id: str
    analysis_type: str
    provider: str
    version: str
    archive_name: str
    sha256: str
    entry_count: int
    source_url: str = ""
    license_name: str = ""
    license_text: str = ""
    attribution: str = ""
    priority: int = DEFAULT_PRIORITY
    published_at: str = ""
    generated_at: str = ""
    provider_dataset_version: str = ""
    builder_version: str = ""
    normalized_schema_version: int = 1
    delivery_tier: str = DELIVERY_TIER_LIMITED_FALLBACK


@dataclass(frozen=True)
class InstalledLibrary:
    package_id: str
    analysis_type: str
    provider: str
    version: str
    archive_path: str
    extract_path: str
    entry_count: int
    installed_at: str = ""
    source_url: str = ""
    license_name: str = ""
    license_text: str = ""
    attribution: str = ""
    priority: int = DEFAULT_PRIORITY
    update_available: bool = False
    published_at: str = ""
    generated_at: str = ""
    provider_dataset_version: str = ""
    builder_version: str = ""
    normalized_schema_version: int = 1
    delivery_tier: str = DELIVERY_TIER_LIMITED_FALLBACK


@dataclass(frozen=True)
class LibraryManifest:
    schema_version: int
    generated_at: str
    providers: tuple[LibraryProvider, ...]
    packages: tuple[LibraryPackage, ...]
    etag: str = ""


@dataclass
class LibrarySyncState:
    manifest_etag: str = ""
    manifest_checked_at: str = ""
    last_sync_at: str = ""
    sync_mode: str = "not_synced"
    cache_status: str = "cold"
    last_error: str = ""
    feed_source: str = ""
    installed_packages: dict[str, dict[str, Any]] = field(default_factory=dict)
    cloud_access_enabled: bool = False
    cloud_provider_count: int = 0
    last_cloud_lookup_at: str = ""
    last_cloud_error: str = ""


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def get_library_root() -> Path:
    return get_storage_dir() / "libraries"


def configured_library_feed_source() -> str | None:
    feed_url = os.getenv(LIBRARY_ENV_FEED_URL, "").strip()
    if feed_url:
        return feed_url.rstrip("/")

    mirror_root = os.getenv(LIBRARY_ENV_MIRROR_ROOT, "").strip()
    if mirror_root:
        return Path(mirror_root).resolve().as_uri()
    return None


def _json_read(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _json_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _sha256_bytes(raw_bytes: bytes) -> str:
    return hashlib.sha256(raw_bytes).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_analysis_type(value: Any) -> str:
    token = str(value or "").strip().upper()
    return token or "UNKNOWN"


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _truthy(value: Any) -> bool:
    token = str(value or "").strip().lower()
    return token in {"1", "true", "yes", "on"}


def _to_serializable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _to_serializable(item) for key, item in value.items()}
    if isinstance(value, np.ndarray):
        return [_to_serializable(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (list, tuple, set)):
        return [_to_serializable(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return value


def _extract_xrd_d_spacing_array(item: Mapping[str, Any], peaks: list[Mapping[str, Any]]) -> np.ndarray | None:
    raw_values = (
        item.get("d_spacing")
        or item.get("d_spacings")
        or item.get("peak_d_spacing")
        or item.get("peak_d_spacings")
    )
    if raw_values is not None and not (isinstance(raw_values, str) and raw_values == ""):
        try:
            values = np.asarray(raw_values, dtype=float)
        except (TypeError, ValueError):
            values = None
        if values is not None and values.ndim == 1 and values.size == len(peaks):
            return values.astype(float, copy=False)

    peak_values: list[float] = []
    for peak in peaks:
        if not isinstance(peak, Mapping):
            return None
        raw_value = peak.get("d_spacing") or peak.get("d")
        if raw_value in (None, ""):
            return None
        try:
            peak_values.append(float(raw_value))
        except (TypeError, ValueError):
            return None
    return np.asarray(peak_values, dtype=float) if peak_values else None


def _package_from_mapping(payload: Mapping[str, Any]) -> LibraryPackage:
    return LibraryPackage(
        package_id=str(payload.get("package_id") or payload.get("id") or "").strip(),
        analysis_type=_normalize_analysis_type(payload.get("analysis_type")),
        provider=str(payload.get("provider") or "").strip(),
        version=str(payload.get("version") or "").strip(),
        archive_name=str(payload.get("archive_name") or payload.get("file_name") or "").strip(),
        sha256=str(payload.get("sha256") or "").strip().lower(),
        entry_count=_coerce_int(payload.get("entry_count"), 0),
        source_url=str(payload.get("source_url") or "").strip(),
        license_name=str(payload.get("license_name") or payload.get("license") or "").strip(),
        license_text=str(payload.get("license_text") or "").strip(),
        attribution=str(payload.get("attribution") or "").strip(),
        priority=_coerce_int(payload.get("priority"), DEFAULT_PRIORITY),
        published_at=str(payload.get("published_at") or "").strip(),
        generated_at=str(payload.get("generated_at") or "").strip(),
        provider_dataset_version=str(payload.get("provider_dataset_version") or "").strip(),
        builder_version=str(payload.get("builder_version") or "").strip(),
        normalized_schema_version=_coerce_int(payload.get("normalized_schema_version"), 1),
        delivery_tier=str(payload.get("delivery_tier") or DELIVERY_TIER_LIMITED_FALLBACK).strip() or DELIVERY_TIER_LIMITED_FALLBACK,
    )


def _installed_from_mapping(payload: Mapping[str, Any]) -> InstalledLibrary:
    return InstalledLibrary(
        package_id=str(payload.get("package_id") or "").strip(),
        analysis_type=_normalize_analysis_type(payload.get("analysis_type")),
        provider=str(payload.get("provider") or "").strip(),
        version=str(payload.get("version") or "").strip(),
        archive_path=str(payload.get("archive_path") or "").strip(),
        extract_path=str(payload.get("extract_path") or "").strip(),
        entry_count=_coerce_int(payload.get("entry_count"), 0),
        installed_at=str(payload.get("installed_at") or "").strip(),
        source_url=str(payload.get("source_url") or "").strip(),
        license_name=str(payload.get("license_name") or "").strip(),
        license_text=str(payload.get("license_text") or "").strip(),
        attribution=str(payload.get("attribution") or "").strip(),
        priority=_coerce_int(payload.get("priority"), DEFAULT_PRIORITY),
        update_available=bool(payload.get("update_available")),
        published_at=str(payload.get("published_at") or "").strip(),
        generated_at=str(payload.get("generated_at") or "").strip(),
        provider_dataset_version=str(payload.get("provider_dataset_version") or "").strip(),
        builder_version=str(payload.get("builder_version") or "").strip(),
        normalized_schema_version=_coerce_int(payload.get("normalized_schema_version"), 1),
        delivery_tier=str(payload.get("delivery_tier") or DELIVERY_TIER_LIMITED_FALLBACK).strip() or DELIVERY_TIER_LIMITED_FALLBACK,
    )


def _provider_from_mapping(payload: Mapping[str, Any]) -> LibraryProvider:
    provider_id = str(payload.get("provider_id") or payload.get("id") or payload.get("name") or "").strip()
    return LibraryProvider(
        provider_id=provider_id,
        name=str(payload.get("name") or provider_id).strip(),
        modalities=tuple(_normalize_analysis_type(item) for item in (payload.get("modalities") or [])),
        source_url=str(payload.get("source_url") or "").strip(),
        license_name=str(payload.get("license_name") or payload.get("license") or "").strip(),
        license_text=str(payload.get("license_text") or "").strip(),
        attribution=str(payload.get("attribution") or "").strip(),
    )


def _parse_manifest(payload: Mapping[str, Any], *, etag: str = "") -> LibraryManifest:
    providers = tuple(_provider_from_mapping(item) for item in (payload.get("providers") or []))
    packages = tuple(_package_from_mapping(item) for item in (payload.get("packages") or []))
    return LibraryManifest(
        schema_version=_coerce_int(payload.get("schema_version"), 1),
        generated_at=str(payload.get("generated_at") or ""),
        providers=providers,
        packages=packages,
        etag=etag or str(payload.get("etag") or ""),
    )


def _license_header_value(license_state: Mapping[str, Any] | None) -> str | None:
    payload = (license_state or {}).get("license")
    if not isinstance(payload, Mapping):
        return None
    try:
        return encode_license_key(dict(payload))
    except Exception:
        return None


class MirrorClient:
    """Fetch manifest and package bytes from a curated mirror."""

    def __init__(self, source: str | None = None) -> None:
        self.source = (source or configured_library_feed_source() or "").strip()

    @property
    def configured(self) -> bool:
        return bool(self.source)

    def _headers(self, license_state: Mapping[str, Any] | None) -> dict[str, str]:
        encoded = _license_header_value(license_state)
        if not encoded:
            return {}
        return {LIBRARY_HEADER: encoded}

    def _is_file_source(self) -> bool:
        return self.source.startswith("file://")

    def _root_path(self) -> Path:
        if self._is_file_source():
            parsed = urlparse(self.source)
            path = unquote(parsed.path or "")
            if os.name == "nt" and len(path) >= 3 and path[0] == "/" and path[2] == ":":
                path = path[1:]
            return Path(path)
        return Path(self.source)

    def _manifest_url(self) -> str:
        base = self.source.rstrip("/")
        if base.endswith(LIBRARY_API_PREFIX):
            return f"{base}/manifest"
        return f"{base}{LIBRARY_API_PREFIX}/manifest"

    def _package_url(self, package_id: str) -> str:
        base = self.source.rstrip("/")
        if base.endswith(LIBRARY_API_PREFIX):
            return f"{base}/packages/{package_id}"
        return f"{base}{LIBRARY_API_PREFIX}/packages/{package_id}"

    def fetch_manifest(
        self,
        *,
        etag: str | None = None,
        license_state: Mapping[str, Any] | None = None,
        timeout: float = 20.0,
    ) -> tuple[int, bytes | None, str]:
        if not self.configured:
            raise ValueError("Library feed source is not configured.")

        if self._is_file_source() or ("://" not in self.source and Path(self.source).exists()):
            manifest_path = self._root_path() / MANIFEST_FILE
            raw = manifest_path.read_bytes()
            manifest_etag = _sha256_bytes(raw)
            if etag and etag == manifest_etag:
                return 304, None, manifest_etag
            return 200, raw, manifest_etag

        headers = self._headers(license_state)
        if etag:
            headers["If-None-Match"] = etag
        response = httpx.get(self._manifest_url(), headers=headers, timeout=timeout)
        if response.status_code == 304:
            return 304, None, response.headers.get("ETag", etag or "")
        response.raise_for_status()
        return response.status_code, response.content, response.headers.get("ETag", _sha256_bytes(response.content))

    def fetch_package(
        self,
        package: LibraryPackage,
        *,
        license_state: Mapping[str, Any] | None = None,
        timeout: float = 60.0,
    ) -> bytes:
        if not self.configured:
            raise ValueError("Library feed source is not configured.")

        if self._is_file_source() or ("://" not in self.source and Path(self.source).exists()):
            return (self._root_path() / "packages" / package.archive_name).read_bytes()

        response = httpx.get(
            self._package_url(package.package_id),
            headers=self._headers(license_state),
            timeout=timeout,
        )
        response.raise_for_status()
        return response.content


class ReferenceLibraryManager:
    """Manage installed reference-library packages and curated mirror sync."""

    def __init__(self, *, root: Path | None = None, feed_source: str | None = None) -> None:
        self.root = Path(root or get_library_root())
        self.feed_source = (feed_source or configured_library_feed_source() or "").strip()
        self.client = MirrorClient(self.feed_source)
        self.root.mkdir(parents=True, exist_ok=True)
        self._packages_root().mkdir(parents=True, exist_ok=True)
        self._installed_root().mkdir(parents=True, exist_ok=True)

    def _manifest_path(self) -> Path:
        return self.root / MANIFEST_FILE

    def _sync_state_path(self) -> Path:
        return self.root / SYNC_STATE_FILE

    def _packages_root(self) -> Path:
        return self.root / "packages"

    def _installed_root(self) -> Path:
        return self.root / "installed"

    def load_sync_state(self) -> LibrarySyncState:
        payload = _json_read(self._sync_state_path(), {})
        state = LibrarySyncState()
        if isinstance(payload, Mapping):
            state.manifest_etag = str(payload.get("manifest_etag") or "")
            state.manifest_checked_at = str(payload.get("manifest_checked_at") or "")
            state.last_sync_at = str(payload.get("last_sync_at") or "")
            state.sync_mode = str(payload.get("sync_mode") or "not_synced")
            state.cache_status = str(payload.get("cache_status") or "cold")
            state.last_error = str(payload.get("last_error") or "")
            state.feed_source = str(payload.get("feed_source") or self.feed_source)
            state.installed_packages = dict(payload.get("installed_packages") or {})
            state.cloud_access_enabled = bool(payload.get("cloud_access_enabled"))
            state.cloud_provider_count = _coerce_int(payload.get("cloud_provider_count"), 0)
            state.last_cloud_lookup_at = str(payload.get("last_cloud_lookup_at") or "")
            state.last_cloud_error = str(payload.get("last_cloud_error") or "")
        return state

    def save_sync_state(self, state: LibrarySyncState) -> None:
        _json_write(self._sync_state_path(), asdict(state))

    def load_manifest(self) -> LibraryManifest | None:
        payload = _json_read(self._manifest_path(), {})
        if not isinstance(payload, Mapping) or not payload:
            return None
        return _parse_manifest(payload, etag=str(payload.get("etag") or ""))

    def save_manifest(self, manifest: LibraryManifest) -> None:
        payload = {
            "schema_version": manifest.schema_version,
            "generated_at": manifest.generated_at,
            "etag": manifest.etag,
            "providers": [asdict(item) for item in manifest.providers],
            "packages": [asdict(item) for item in manifest.packages],
        }
        _json_write(self._manifest_path(), payload)

    def needs_manifest_refresh(self, *, hours: int = DEFAULT_BACKGROUND_REFRESH_HOURS) -> bool:
        state = self.load_sync_state()
        if not state.manifest_checked_at:
            return True
        try:
            checked_at = datetime.fromisoformat(state.manifest_checked_at.replace("Z", "+00:00"))
        except ValueError:
            return True
        return checked_at + timedelta(hours=hours) <= datetime.now(UTC)

    def check_manifest(self, *, license_state: Mapping[str, Any] | None = None, force: bool = False) -> dict[str, Any]:
        state = self.load_sync_state()
        if not self.client.configured:
            state.cache_status = self._cache_status(state)
            state.sync_mode = "cached_read_only" if state.cache_status == "warm" else "not_synced"
            state.last_error = "Library feed source is not configured."
            self.save_sync_state(state)
            return self.status()
        if not force and not self.needs_manifest_refresh():
            return self.status()

        try:
            status_code, raw, etag = self.client.fetch_manifest(
                etag=state.manifest_etag or None,
                license_state=license_state,
            )
        except Exception as exc:
            state.manifest_checked_at = utcnow_iso()
            state.cache_status = self._cache_status(state)
            state.sync_mode = "cached_read_only" if state.cache_status == "warm" else "not_synced"
            state.last_error = str(exc)
            state.feed_source = self.feed_source
            self.save_sync_state(state)
            raise
        state.manifest_checked_at = utcnow_iso()
        state.feed_source = self.feed_source
        if status_code == 304:
            state.sync_mode = "cached_read_only" if self._cache_status(state) == "warm" else state.sync_mode
            state.cache_status = self._cache_status(state)
            state.last_error = ""
            self.save_sync_state(state)
            return self.status()

        if raw is None:
            raise ValueError("Manifest fetch returned no content.")

        payload = json.loads(raw.decode("utf-8"))
        manifest = _parse_manifest(payload, etag=etag or _sha256_bytes(raw))
        self.save_manifest(manifest)
        state.manifest_etag = manifest.etag
        state.cache_status = self._cache_status(state)
        state.last_error = ""
        self.save_sync_state(state)
        return self.status()

    def _cache_status(self, state: LibrarySyncState | None = None) -> str:
        state = state or self.load_sync_state()
        return "warm" if bool(state.installed_packages) else "cold"

    def _cloud_access_enabled(self, state: LibrarySyncState | None = None) -> bool:
        state = state or self.load_sync_state()
        cloud_root = str(os.getenv(LIBRARY_ENV_CLOUD_URL, "")).strip()
        if not cloud_root:
            return False
        enabled_override = os.getenv(LIBRARY_ENV_CLOUD_ENABLED, "")
        if enabled_override != "" and not _truthy(enabled_override):
            return False
        return bool(state.cloud_access_enabled) and max(0, int(state.cloud_provider_count or 0)) > 0

    def _allow_full_provider_sync(self) -> bool:
        return _truthy(os.getenv(LIBRARY_ENV_ALLOW_FULL_PROVIDER_SYNC, ""))

    def _installed_mapping(self) -> dict[str, InstalledLibrary]:
        state = self.load_sync_state()
        installed: dict[str, InstalledLibrary] = {}
        for package_id, payload in state.installed_packages.items():
            try:
                installed[str(package_id)] = _installed_from_mapping(payload)
            except Exception:
                continue
        return installed

    def installed_packages(self) -> list[InstalledLibrary]:
        manifest = self.load_manifest()
        available = {item.package_id: item for item in (manifest.packages if manifest else ())}
        items: list[InstalledLibrary] = []
        for installed in self._installed_mapping().values():
            available_package = available.get(installed.package_id)
            items.append(
                InstalledLibrary(
                    **{
                        **asdict(installed),
                        "update_available": bool(
                            available_package is not None and available_package.version != installed.version
                        ),
                    }
                )
            )
        items.sort(key=lambda item: (-item.priority, item.analysis_type, item.provider, item.package_id))
        return items

    def catalog(self) -> list[dict[str, Any]]:
        manifest = self.load_manifest()
        installed = {item.package_id: item for item in self.installed_packages()}
        catalog_rows: list[dict[str, Any]] = []
        for package in (manifest.packages if manifest else ()):
            active = installed.get(package.package_id)
            catalog_rows.append(
                {
                    "package_id": package.package_id,
                    "analysis_type": package.analysis_type,
                    "provider": package.provider,
                    "version": package.version,
                    "entry_count": package.entry_count,
                    "source_url": package.source_url,
                    "license_name": package.license_name,
                    "license_text": package.license_text,
                    "attribution": package.attribution,
                    "priority": package.priority,
                    "published_at": package.published_at,
                    "generated_at": package.generated_at,
                    "provider_dataset_version": package.provider_dataset_version,
                    "builder_version": package.builder_version,
                    "normalized_schema_version": package.normalized_schema_version,
                    "delivery_tier": package.delivery_tier,
                    "installed": active is not None,
                    "installed_version": active.version if active else None,
                    "update_available": active.update_available if active else False,
                }
            )
        return catalog_rows

    def status(self) -> dict[str, Any]:
        state = self.load_sync_state()
        installed = self.installed_packages()
        manifest = self.load_manifest()
        fallback_packages = [
            item
            for item in installed
            if str(item.delivery_tier or DELIVERY_TIER_LIMITED_FALLBACK) != DELIVERY_TIER_FULL_PROVIDER
        ]
        cloud_access_enabled = self._cloud_access_enabled(state)
        cloud_provider_count = max(0, int(state.cloud_provider_count or 0)) if cloud_access_enabled else 0
        if cloud_access_enabled and cloud_provider_count > 0:
            library_mode = LIBRARY_MODE_CLOUD_FULL_ACCESS
        elif fallback_packages:
            library_mode = LIBRARY_MODE_LIMITED_CACHED_FALLBACK
        else:
            library_mode = LIBRARY_MODE_NOT_CONFIGURED
        return {
            "feed_configured": self.client.configured,
            "feed_source": state.feed_source or self.feed_source,
            "manifest_checked_at": state.manifest_checked_at,
            "last_sync_at": state.last_sync_at,
            "sync_mode": state.sync_mode or "not_synced",
            "cache_status": self._cache_status(state),
            "installed_package_count": len(installed),
            "installed_entry_count": sum(item.entry_count for item in installed),
            "update_available_count": sum(1 for item in installed if item.update_available),
            "available_package_count": len(manifest.packages) if manifest else 0,
            "available_provider_count": len(manifest.providers) if manifest else 0,
            "manifest_generated_at": manifest.generated_at if manifest else "",
            "manifest_etag": state.manifest_etag,
            "last_error": state.last_error,
            "sync_due": self.needs_manifest_refresh() if self.client.configured else False,
            "library_mode": library_mode,
            "cloud_url": str(os.getenv(LIBRARY_ENV_CLOUD_URL, "")).strip(),
            "cloud_enabled_by_env": bool(str(os.getenv(LIBRARY_ENV_CLOUD_URL, "")).strip())
            and (str(os.getenv(LIBRARY_ENV_CLOUD_ENABLED, "")).strip() == "" or _truthy(os.getenv(LIBRARY_ENV_CLOUD_ENABLED, ""))),
            "cloud_access_enabled": cloud_access_enabled,
            "cloud_provider_count": cloud_provider_count,
            "fallback_package_count": len(fallback_packages),
            "fallback_entry_count": sum(item.entry_count for item in fallback_packages),
            "last_cloud_lookup_at": state.last_cloud_lookup_at or None,
            "last_cloud_error": state.last_cloud_error,
        }

    def sync(
        self,
        *,
        license_state: Mapping[str, Any] | None = None,
        package_ids: Iterable[str] | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        self.check_manifest(license_state=license_state, force=force)
        state = self.load_sync_state()
        manifest = self.load_manifest()
        if manifest is None:
            return self.status()

        selected = {str(item) for item in (package_ids or []) if str(item).strip()}
        all_target_packages = [
            package for package in manifest.packages if not selected or package.package_id in selected
        ]
        blocked_packages: list[str] = []
        if self._allow_full_provider_sync():
            target_packages = list(all_target_packages)
        else:
            target_packages = []
            for package in all_target_packages:
                if str(package.delivery_tier or DELIVERY_TIER_LIMITED_FALLBACK) == DELIVERY_TIER_FULL_PROVIDER:
                    blocked_packages.append(package.package_id)
                    continue
                target_packages.append(package)
        installed = state.installed_packages

        for package in target_packages:
            existing = installed.get(package.package_id) or {}
            if not force and existing.get("version") == package.version:
                continue
            try:
                raw = self.client.fetch_package(package, license_state=license_state)
            except Exception as exc:
                state.sync_mode = "cached_read_only" if self._cache_status(state) == "warm" else "not_synced"
                state.cache_status = self._cache_status(state)
                state.last_error = str(exc)
                state.feed_source = self.feed_source
                self.save_sync_state(state)
                raise
            actual_hash = _sha256_bytes(raw)
            if actual_hash != package.sha256:
                raise ValueError(
                    f"Package '{package.package_id}' hash mismatch: expected {package.sha256}, got {actual_hash}."
                )
            archive_path, extract_path = self._install_package(package, raw)
            installed[package.package_id] = {
                "package_id": package.package_id,
                "analysis_type": package.analysis_type,
                "provider": package.provider,
                "version": package.version,
                "archive_path": str(archive_path),
                "extract_path": str(extract_path),
                "entry_count": package.entry_count,
                "installed_at": utcnow_iso(),
                "source_url": package.source_url,
                "license_name": package.license_name,
                "license_text": package.license_text,
                "attribution": package.attribution,
                "priority": package.priority,
                "update_available": False,
                "published_at": package.published_at,
                "generated_at": package.generated_at,
                "provider_dataset_version": package.provider_dataset_version,
                "builder_version": package.builder_version,
                "normalized_schema_version": package.normalized_schema_version,
                "delivery_tier": package.delivery_tier,
            }

        state.installed_packages = installed
        state.last_sync_at = utcnow_iso()
        state.sync_mode = "online_sync"
        state.cache_status = self._cache_status(state)
        state.feed_source = self.feed_source
        if blocked_packages:
            state.last_error = (
                "Some packages were skipped by delivery-tier policy: "
                + ", ".join(sorted(blocked_packages))
            )
        else:
            state.last_error = ""
        self.save_sync_state(state)
        return self.status()

    def record_cloud_lookup(
        self,
        *,
        success: bool,
        provider_count: int | None = None,
        error: str = "",
    ) -> None:
        state = self.load_sync_state()
        cloud_root = str(os.getenv(LIBRARY_ENV_CLOUD_URL, "")).strip()
        enabled_override = os.getenv(LIBRARY_ENV_CLOUD_ENABLED, "")
        cloud_configured = bool(cloud_root) and (enabled_override == "" or _truthy(enabled_override))
        effective_provider_count = max(0, int(provider_count)) if provider_count is not None else None
        zero_provider_lookup = bool(success and effective_provider_count is not None and effective_provider_count <= 0)
        missing_provider_lookup = bool(success and effective_provider_count is None)
        cloud_success = bool(success and cloud_configured and effective_provider_count is not None and effective_provider_count > 0)
        state.cloud_access_enabled = cloud_success
        state.last_cloud_lookup_at = utcnow_iso()
        if effective_provider_count is not None:
            state.cloud_provider_count = effective_provider_count if cloud_success else 0
        if cloud_success:
            state.last_cloud_error = ""
        else:
            state.cloud_provider_count = 0
            if zero_provider_lookup:
                state.last_cloud_error = str(error or "Cloud coverage lookup returned zero providers.").strip()
            elif missing_provider_lookup:
                state.last_cloud_error = str(error or "Cloud coverage lookup did not report provider count.").strip()
            else:
                state.last_cloud_error = str(error or "").strip()
        self.save_sync_state(state)

    def _install_package(self, package: LibraryPackage, raw: bytes) -> tuple[Path, Path]:
        archive_path = self._packages_root() / package.archive_name
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        archive_path.write_bytes(raw)

        extract_dir = self._installed_root() / package.package_id / package.version
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        extract_dir.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="ta_lib_", dir=str(self.root)) as tmp_dir:
            temp_extract = Path(tmp_dir) / "extract"
            temp_extract.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(io.BytesIO(raw), "r") as archive:
                archive.extractall(temp_extract)
            shutil.move(str(temp_extract), str(extract_dir))
        return archive_path, extract_dir

    def count_installed_candidates(self, analysis_type: str) -> int:
        token = _normalize_analysis_type(analysis_type)
        return sum(item.entry_count for item in self.installed_packages() if item.analysis_type == token)

    def library_context(self, analysis_type: str) -> dict[str, Any]:
        token = _normalize_analysis_type(analysis_type)
        installed = [item for item in self.installed_packages() if item.analysis_type == token]
        status = self.status()
        return {
            "analysis_type": token,
            "reference_package_count": len(installed),
            "reference_candidate_count": sum(item.entry_count for item in installed),
            "library_sync_mode": status["sync_mode"],
            "library_cache_status": status["cache_status"],
            "library_providers": [item.provider for item in installed],
            "library_packages": [item.package_id for item in installed],
            "library_mode": status.get("library_mode", LIBRARY_MODE_NOT_CONFIGURED),
            "cloud_url": str(status.get("cloud_url") or "").strip(),
            "cloud_enabled_by_env": bool(status.get("cloud_enabled_by_env")),
            "cloud_access_enabled": bool(status.get("cloud_access_enabled")),
            "cloud_provider_count": _coerce_int(status.get("cloud_provider_count"), 0),
            "fallback_package_count": _coerce_int(status.get("fallback_package_count"), 0),
            "fallback_entry_count": _coerce_int(status.get("fallback_entry_count"), 0),
            "last_cloud_lookup_at": status.get("last_cloud_lookup_at"),
            "last_cloud_error": status.get("last_cloud_error") or "",
        }

    def _entry_base(
        self,
        *,
        entry: Mapping[str, Any],
        package: InstalledLibrary,
        token: str,
        package_payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        base = dict(entry)
        package_additive = {
            str(key): value
            for key, value in package_payload.items()
            if str(key) not in {
                "package_id",
                "analysis_type",
                "provider",
                "version",
                "source_url",
                "license_name",
                "license_text",
                "attribution",
                "priority",
                "published_at",
                "generated_at",
                "provider_dataset_version",
                "builder_version",
                "normalized_schema_version",
                "entry_count",
                "archive_name",
                "sha256",
            }
        }
        if package_additive:
            base.setdefault("package_metadata", dict(package_additive))
            for key, value in package_additive.items():
                base.setdefault(key, value)
        base["candidate_id"] = str(entry.get("candidate_id") or entry.get("id") or "").strip()
        base["candidate_name"] = str(entry.get("candidate_name") or entry.get("name") or "").strip()
        base["analysis_type"] = token
        base["provider"] = package.provider
        base["package_id"] = package.package_id
        base["package_version"] = package.version
        base["license_name"] = package.license_name
        base["source_url"] = str(entry.get("source_url") or package.source_url).strip()
        base["attribution"] = str(entry.get("attribution") or package.attribution).strip()
        base["priority"] = _coerce_int(entry.get("priority"), package.priority)
        base["published_at"] = str(entry.get("published_at") or package.published_at or package_payload.get("published_at") or "").strip()
        base["generated_at"] = str(entry.get("generated_at") or package.generated_at or package_payload.get("generated_at") or "").strip()
        base["provider_dataset_version"] = str(
            entry.get("provider_dataset_version")
            or package.provider_dataset_version
            or package_payload.get("provider_dataset_version")
            or ""
        ).strip()
        base["builder_version"] = str(entry.get("builder_version") or package.builder_version or package_payload.get("builder_version") or "").strip()
        base["normalized_schema_version"] = _coerce_int(
            entry.get("normalized_schema_version")
            or package.normalized_schema_version
            or package_payload.get("normalized_schema_version"),
            1,
        )
        base["delivery_tier"] = str(entry.get("delivery_tier") or package.delivery_tier).strip() or DELIVERY_TIER_LIMITED_FALLBACK
        return base

    def load_entries(self, analysis_type: str) -> list[dict[str, Any]]:
        token = _normalize_analysis_type(analysis_type)
        entries: list[dict[str, Any]] = []
        for package in self.installed_packages():
            if package.analysis_type != token:
                continue
            extract_path = Path(package.extract_path)
            package_meta_path = extract_path / "package.json"
            entries_path = extract_path / "entries.jsonl"
            if not package_meta_path.exists() or not entries_path.exists():
                continue

            payload = json.loads(package_meta_path.read_text(encoding="utf-8"))
            if not isinstance(payload, Mapping):
                payload = {}
            array_file = extract_path / ("signals.npz" if token in {"FTIR", "RAMAN"} else "peaks.npz")
            if not array_file.exists():
                continue
            with np.load(array_file, allow_pickle=False) as arrays:
                for line in entries_path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    entry = json.loads(line)
                    base = self._entry_base(entry=entry, package=package, token=token, package_payload=payload)
                    if token in {"FTIR", "RAMAN"}:
                        signal_key = str(entry.get("signal_key") or "").strip()
                        if not signal_key:
                            continue
                        axis = arrays[f"axis_{signal_key}"].astype(float)
                        signal = arrays[f"signal_{signal_key}"].astype(float)
                        entries.append({**base, "axis": axis, "signal": signal})
                    else:
                        peak_key = str(entry.get("peak_key") or "").strip()
                        if not peak_key:
                            continue
                        positions = arrays[f"positions_{peak_key}"].astype(float)
                        intensities = arrays[f"intensities_{peak_key}"].astype(float)
                        d_spacing_key = f"d_spacings_{peak_key}"
                        d_spacings = arrays[d_spacing_key].astype(float) if d_spacing_key in arrays else None
                        peaks = [
                            {
                                "position": float(position),
                                "intensity": float(intensity),
                                **(
                                    {"d_spacing": float(d_spacings[index])}
                                    if d_spacings is not None and index < len(d_spacings)
                                    else {}
                                ),
                            }
                            for index, (position, intensity) in enumerate(zip(positions.tolist(), intensities.tolist()))
                        ]
                        resolved_entry = {**base, "peaks": peaks}
                        if d_spacings is not None:
                            resolved_entry.setdefault("d_spacing", [float(item) for item in d_spacings.tolist()])
                        entries.append(resolved_entry)
        entries.sort(
            key=lambda item: (
                -_coerce_int(item.get("priority"), DEFAULT_PRIORITY),
                item.get("provider") or "",
                item.get("candidate_id") or "",
            )
        )
        return entries


def get_reference_library_manager() -> ReferenceLibraryManager:
    return ReferenceLibraryManager()


def maybe_refresh_library_manifest(license_state: Mapping[str, Any] | None, *, hours: int = DEFAULT_BACKGROUND_REFRESH_HOURS) -> dict[str, Any]:
    manager = get_reference_library_manager()
    if not manager.client.configured:
        return manager.status()
    if not manager.needs_manifest_refresh(hours=hours):
        return manager.status()
    try:
        return manager.check_manifest(license_state=license_state, force=True)
    except Exception:
        state = manager.load_sync_state()
        state.sync_mode = "cached_read_only" if manager._cache_status(state) == "warm" else "not_synced"
        state.cache_status = manager._cache_status(state)
        state.last_error = "Manifest refresh failed; using cached library state."
        manager.save_sync_state(state)
        return manager.status()


def build_reference_library_package(
    *,
    output_path: Path,
    package_metadata: Mapping[str, Any],
    entries: Iterable[Mapping[str, Any]],
) -> str:
    """Create a package archive and return its sha256 hash."""
    token = _normalize_analysis_type(package_metadata.get("analysis_type"))
    temp_dir = Path(tempfile.mkdtemp(prefix="ta_lib_build_"))
    try:
        temp_extract = temp_dir / "extract"
        temp_extract.mkdir(parents=True, exist_ok=True)
        package_json = _to_serializable(dict(package_metadata))
        package_json["analysis_type"] = token
        (temp_extract / "package.json").write_text(
            json.dumps(package_json, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        lines: list[str] = []
        if token in {"FTIR", "RAMAN"}:
            axis_map: dict[str, np.ndarray] = {}
            signal_map: dict[str, np.ndarray] = {}
            for index, item in enumerate(entries, start=1):
                key = f"ref_{index:04d}"
                axis = np.asarray(item.get("axis") or [], dtype=float)
                signal = np.asarray(item.get("signal") or [], dtype=float)
                axis_map[f"axis_{key}"] = axis
                signal_map[f"signal_{key}"] = signal
                payload = _to_serializable(dict(item))
                payload["signal_key"] = key
                payload.pop("axis", None)
                payload.pop("signal", None)
                lines.append(json.dumps(payload, ensure_ascii=False))
            np.savez_compressed(temp_extract / "signals.npz", **axis_map, **signal_map)
        else:
            position_map: dict[str, np.ndarray] = {}
            intensity_map: dict[str, np.ndarray] = {}
            d_spacing_map: dict[str, np.ndarray] = {}
            for index, item in enumerate(entries, start=1):
                key = f"ref_{index:04d}"
                peaks = list(item.get("peaks") or [])
                position_map[f"positions_{key}"] = np.asarray([peak["position"] for peak in peaks], dtype=float)
                intensity_map[f"intensities_{key}"] = np.asarray([peak["intensity"] for peak in peaks], dtype=float)
                d_spacings = _extract_xrd_d_spacing_array(item, peaks)
                if d_spacings is not None and d_spacings.size:
                    d_spacing_map[f"d_spacings_{key}"] = np.asarray(d_spacings, dtype=float)
                payload = _to_serializable(dict(item))
                payload["peak_key"] = key
                if d_spacings is not None and d_spacings.size:
                    payload["d_spacing"] = [float(value) for value in d_spacings.tolist()]
                payload.pop("peaks", None)
                lines.append(json.dumps(payload, ensure_ascii=False))
            np.savez_compressed(temp_extract / "peaks.npz", **position_map, **intensity_map, **d_spacing_map)

        (temp_extract / "entries.jsonl").write_text("\n".join(lines), encoding="utf-8")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in ("package.json", "entries.jsonl", "signals.npz", "peaks.npz"):
                source = temp_extract / name
                if source.exists():
                    archive.write(source, arcname=name)
        return _sha256_file(output_path)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
