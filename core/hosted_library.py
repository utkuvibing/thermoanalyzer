"""Hosted cloud-library catalog helpers for server-side search and coverage."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

import numpy as np

LIBRARY_ENV_HOSTED_ROOT = "THERMOANALYZER_LIBRARY_HOSTED_ROOT"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HOSTED_ROOT = PROJECT_ROOT / "build" / "reference_library_hosted"
HOSTED_MANIFEST_FILE = "manifest.json"
HOSTED_SCHEMA_VERSION = 1
_FRESH_THRESHOLD = timedelta(days=14)
_AGING_THRESHOLD = timedelta(days=45)
_LOCAL_NORMALIZED_ROOT_NAMES = ("reference_library_ingest_live", "reference_library_ingest")
_SAMPLE_NORMALIZED_ROOT_NAMES = ("reference_library_ingest_cloud_dev",)
_XRD_SEED_COVERAGE_THRESHOLD = 12


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def resolve_hosted_root(root: str | Path | None = None) -> Path:
    configured = str(root or os.getenv(LIBRARY_ENV_HOSTED_ROOT, "")).strip()
    return Path(configured or DEFAULT_HOSTED_ROOT).resolve()


def _normalize_dataset_modality(payload: Mapping[str, Any]) -> str:
    return _normalize_modality(payload.get("modality") or payload.get("analysis_type"))


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _normalize_modality(value: Any) -> str:
    return str(value or "").strip().upper()


def _slug(value: Any, *, default: str = "item") -> str:
    text = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value or "").strip())
    token = "_".join(part for part in text.split("_") if part)
    return token or default


def normalize_provider_id(value: Any) -> str:
    token = _slug(value, default="")
    if token in {"materialsproject", "materials_project", "mp"}:
        return "materials_project"
    return token


def _freshness_state(*, published_at: str, reference_now: datetime | None = None) -> str:
    parsed = _parse_datetime(published_at)
    if parsed is None:
        return "unknown"
    now = reference_now or datetime.now(UTC)
    age = now - parsed
    if age <= _FRESH_THRESHOLD:
        return "fresh"
    if age <= _AGING_THRESHOLD:
        return "aging"
    return "stale"


def canonical_material_key(entry: Mapping[str, Any], *, modality: str = "") -> str:
    explicit = str(entry.get("canonical_material_key") or "").strip().lower()
    if explicit:
        return explicit
    candidates = [
        entry.get("material_key"),
        entry.get("formula"),
        entry.get("formula_pretty"),
        entry.get("phase_name"),
        entry.get("candidate_name"),
        entry.get("candidate_id"),
        entry.get("source_id"),
    ]
    if modality == "XRD":
        peaks = entry.get("peaks") or []
        if isinstance(peaks, list) and peaks:
            peak_token = "|".join(
                f"{float(item.get('d_spacing') or item.get('position') or 0.0):.4f}"
                for item in peaks[:8]
                if isinstance(item, Mapping)
            )
            if peak_token:
                candidates.insert(0, peak_token)
    token = " ".join(str(item or "").strip().lower() for item in candidates if str(item or "").strip())
    return _slug(token, default="unknown_material")


def spectral_signal_hash(axis: list[float], signal: list[float]) -> str:
    pairs = zip(axis, signal)
    payload = ";".join(f"{float(x):.4f}:{float(y):.6f}" for x, y in pairs)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def xrd_peak_hash(peaks: list[Mapping[str, Any]]) -> str:
    payload = ";".join(
        f"{float(item.get('d_spacing') or item.get('position') or 0.0):.5f}:{float(item.get('intensity') or 0.0):.5f}"
        for item in peaks
        if isinstance(item, Mapping)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _spectral_peak_summary(axis: np.ndarray, signal: np.ndarray, *, max_peaks: int = 12) -> tuple[np.ndarray, np.ndarray]:
    if axis.size == 0 or signal.size == 0 or axis.size != signal.size:
        return np.asarray([], dtype=float), np.asarray([], dtype=float)
    interior = signal[1:-1]
    if interior.size <= 0:
        ranking = np.argsort(signal)[-max_peaks:]
    else:
        peak_mask = (interior >= signal[:-2]) & (interior >= signal[2:])
        peak_indices = np.where(peak_mask)[0] + 1
        if peak_indices.size == 0:
            peak_indices = np.argsort(signal)[-max_peaks:]
        ranking = peak_indices[np.argsort(signal[peak_indices])[-max_peaks:]]
    ranking = np.asarray(sorted(set(int(index) for index in ranking.tolist())), dtype=int)
    if ranking.size > max_peaks:
        ranking = ranking[-max_peaks:]
    return axis[ranking].astype(float), signal[ranking].astype(float)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def _dataset_file_name(modality: str) -> str:
    return "signals.npz" if _normalize_modality(modality) in {"FTIR", "RAMAN"} else "peaks.npz"


def _count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def xrd_coverage_profile(
    *,
    total_candidate_count: Any,
    provider_rows: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    total_count = max(0, _coerce_int(total_candidate_count, 0))
    provider_payload = {
        str(provider_id): max(0, _coerce_int((row or {}).get("candidate_count"), 0))
        for provider_id, row in (provider_rows or {}).items()
        if str(provider_id).strip()
    }
    provider_count = len(provider_payload)
    if total_count <= 0:
        return {
            "coverage_tier": "empty",
            "coverage_warning_code": "xrd_hosted_coverage_empty",
            "coverage_warning_message": "No hosted XRD candidates are currently published.",
            "provider_candidate_counts": provider_payload,
            "seed_coverage_only": False,
        }
    if total_count <= _XRD_SEED_COVERAGE_THRESHOLD:
        return {
            "coverage_tier": "seed_dev",
            "coverage_warning_code": "xrd_seed_coverage_only",
            "coverage_warning_message": (
                f"XRD hosted coverage is still seed/dev sized ({total_count} candidates across "
                f"{provider_count} provider{'s' if provider_count != 1 else ''}). Cloud matching is online, "
                "but no-match outcomes can still reflect insufficient corpus depth."
            ),
            "provider_candidate_counts": provider_payload,
            "seed_coverage_only": True,
        }
    return {
        "coverage_tier": "expanded",
        "coverage_warning_code": "",
        "coverage_warning_message": "",
        "provider_candidate_counts": provider_payload,
        "seed_coverage_only": False,
    }


def write_hosted_dataset(
    *,
    output_dir: str | Path,
    dataset_metadata: Mapping[str, Any],
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    modality = _normalize_modality(dataset_metadata.get("modality") or dataset_metadata.get("analysis_type"))
    artifact_name = _dataset_file_name(modality)
    artifact_path = target_dir / artifact_name

    jsonl_rows: list[dict[str, Any]] = []
    arrays: dict[str, np.ndarray] = {}
    dedupe_keys: set[str] = set()
    for index, raw_entry in enumerate(entries, start=1):
        entry = dict(raw_entry)
        key = f"entry_{index:06d}"
        entry["canonical_material_key"] = canonical_material_key(entry, modality=modality)
        dedupe_keys.add(entry["canonical_material_key"])
        if modality in {"FTIR", "RAMAN"}:
            axis = np.asarray(entry.get("axis") or [], dtype=float)
            signal = np.asarray(entry.get("signal") or [], dtype=float)
            entry["signal_hash"] = str(entry.get("signal_hash") or spectral_signal_hash(axis.tolist(), signal.tolist()))
            peak_axis, peak_signal = _spectral_peak_summary(axis, signal)
            arrays[f"axis_{key}"] = axis
            arrays[f"signal_{key}"] = signal
            arrays[f"signal_norm_{key}"] = np.asarray([float(np.linalg.norm(signal))], dtype=float)
            arrays[f"peak_axis_{key}"] = peak_axis
            arrays[f"peak_signal_{key}"] = peak_signal
            entry["signal_key"] = key
            entry.pop("axis", None)
            entry.pop("signal", None)
        else:
            peaks = [dict(item) for item in (entry.get("peaks") or []) if isinstance(item, Mapping)]
            arrays[f"positions_{key}"] = np.asarray([float(item.get("position") or 0.0) for item in peaks], dtype=float)
            arrays[f"intensities_{key}"] = np.asarray([float(item.get("intensity") or 0.0) for item in peaks], dtype=float)
            d_spacings = [float(item.get("d_spacing")) for item in peaks if item.get("d_spacing") not in (None, "")]
            if d_spacings:
                arrays[f"d_spacings_{key}"] = np.asarray(d_spacings, dtype=float)
            entry["peak_hash"] = str(entry.get("peak_hash") or xrd_peak_hash(peaks))
            entry["peak_key"] = key
            entry.pop("peaks", None)
        jsonl_rows.append(entry)

    np.savez_compressed(artifact_path, **arrays)
    dataset_payload = {
        "dataset_id": str(dataset_metadata.get("dataset_id") or target_dir.name),
        "provider_id": normalize_provider_id(dataset_metadata.get("provider_id") or dataset_metadata.get("provider")),
        "provider": str(dataset_metadata.get("provider") or dataset_metadata.get("provider_id") or ""),
        "modality": modality,
        "dataset_version": str(dataset_metadata.get("dataset_version") or ""),
        "published_at": str(dataset_metadata.get("published_at") or utcnow_iso()),
        "generated_at": str(dataset_metadata.get("generated_at") or dataset_metadata.get("published_at") or utcnow_iso()),
        "last_successful_ingest_at": str(dataset_metadata.get("last_successful_ingest_at") or ""),
        "failed_ingest_count": _coerce_int(dataset_metadata.get("failed_ingest_count"), 0),
        "candidate_count": _coerce_int(dataset_metadata.get("candidate_count"), len(jsonl_rows)),
        "deduped_candidate_count": _coerce_int(dataset_metadata.get("deduped_candidate_count"), len(dedupe_keys)),
        "freshness_state": str(
            dataset_metadata.get("freshness_state")
            or _freshness_state(published_at=str(dataset_metadata.get("published_at") or ""))
        ),
        "provider_dataset_version": str(dataset_metadata.get("provider_dataset_version") or ""),
        "builder_version": str(dataset_metadata.get("builder_version") or ""),
        "normalized_schema_version": _coerce_int(dataset_metadata.get("normalized_schema_version"), 1),
        "source_url": str(dataset_metadata.get("source_url") or ""),
        "license_name": str(dataset_metadata.get("license_name") or ""),
        "license_text": str(dataset_metadata.get("license_text") or ""),
        "attribution": str(dataset_metadata.get("attribution") or ""),
        "priority": _coerce_int(dataset_metadata.get("priority"), 0),
        "entries_file": "entries.jsonl",
        "artifact_file": artifact_name,
    }
    _write_json(target_dir / "dataset.json", dataset_payload)
    _write_jsonl(target_dir / "entries.jsonl", jsonl_rows)
    return dataset_payload


def _manifest_etag(payload: Mapping[str, Any]) -> str:
    body = json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def build_hosted_manifest(*, generated_at: str, datasets: list[dict[str, Any]]) -> dict[str, Any]:
    provider_rows: dict[str, dict[str, Any]] = {}
    for dataset in datasets:
        if not dataset.get("active", True):
            continue
        provider_id = normalize_provider_id(dataset.get("provider_id") or dataset.get("provider"))
        payload = provider_rows.setdefault(
            provider_id,
            {
                "provider_id": provider_id,
                "name": str(dataset.get("provider") or provider_id),
                "modalities": [],
                "candidate_count": 0,
                "deduped_candidate_count": 0,
                "dataset_count": 0,
                "published_at": "",
            },
        )
        modality = _normalize_modality(dataset.get("modality"))
        if modality and modality not in payload["modalities"]:
            payload["modalities"].append(modality)
        payload["candidate_count"] += _coerce_int(dataset.get("candidate_count"), 0)
        payload["deduped_candidate_count"] += _coerce_int(dataset.get("deduped_candidate_count"), 0)
        payload["dataset_count"] += 1
        published_at = str(dataset.get("published_at") or "")
        if published_at and published_at > str(payload.get("published_at") or ""):
            payload["published_at"] = published_at

    manifest = {
        "schema_version": HOSTED_SCHEMA_VERSION,
        "generated_at": generated_at,
        "providers": sorted(provider_rows.values(), key=lambda item: str(item["provider_id"])),
        "datasets": sorted(
            datasets,
            key=lambda item: (
                _normalize_modality(item.get("modality")),
                normalize_provider_id(item.get("provider_id") or item.get("provider")),
                str(item.get("dataset_version") or ""),
            ),
        ),
    }
    manifest["etag"] = _manifest_etag(manifest)
    return manifest


class HostedLibraryCatalog:
    """Read hosted datasets and aggregate provider/coverage metadata."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = resolve_hosted_root(root)
        self._manifest_mtime: float | None = None
        self._manifest_cache: dict[str, Any] | None = None
        self._dataset_cache: dict[str, tuple[float, dict[str, Any], list[dict[str, Any]]]] = {}

    def invalidate(self) -> None:
        """Clear all cached manifest and dataset state so the next read picks up fresh data."""
        self._manifest_cache = None
        self._manifest_mtime = None
        self._dataset_cache = {}

    def refresh(self) -> dict[str, Any]:
        """Force a fresh manifest read and clear dataset caches."""
        self.invalidate()
        return self.manifest()

    @property
    def manifest_path(self) -> Path:
        return self.root / HOSTED_MANIFEST_FILE

    @property
    def configured(self) -> bool:
        return self.manifest_path.exists()

    def manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {
                "schema_version": HOSTED_SCHEMA_VERSION,
                "generated_at": "",
                "providers": [],
                "datasets": [],
                "etag": "",
            }
        mtime = self.manifest_path.stat().st_mtime
        if self._manifest_cache is not None and self._manifest_mtime == mtime:
            return dict(self._manifest_cache)
        payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            payload = {}
        payload.setdefault("providers", [])
        payload.setdefault("datasets", [])
        self._manifest_cache = payload
        self._manifest_mtime = mtime
        return dict(payload)

    def active_datasets(self, *, modality: str | None = None) -> list[dict[str, Any]]:
        token = _normalize_modality(modality) if modality else ""
        datasets: list[dict[str, Any]] = []
        for item in self.manifest().get("datasets") or []:
            if not isinstance(item, Mapping):
                continue
            dataset = dict(item)
            if not dataset.get("active", True):
                continue
            if token and _normalize_dataset_modality(dataset) != token:
                continue
            datasets.append(dataset)
        return datasets

    def _read_dataset_bundle(self, dataset: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        relative_path = Path(str(dataset.get("path") or ""))
        dataset_dir = self.root / relative_path
        dataset_json = dataset_dir / "dataset.json"
        entries_jsonl = dataset_dir / "entries.jsonl"
        artifact_file = dataset_dir / str(dataset.get("artifact_file") or _dataset_file_name(dataset.get("modality")))
        cache_key = str(dataset_dir).lower()
        cache_mtime = max(
            dataset_json.stat().st_mtime if dataset_json.exists() else 0.0,
            entries_jsonl.stat().st_mtime if entries_jsonl.exists() else 0.0,
            artifact_file.stat().st_mtime if artifact_file.exists() else 0.0,
        )
        cached = self._dataset_cache.get(cache_key)
        if cached is not None and cached[0] == cache_mtime:
            return dict(cached[1]), [dict(item) for item in cached[2]]

        dataset_payload = json.loads(dataset_json.read_text(encoding="utf-8")) if dataset_json.exists() else dict(dataset)
        if not isinstance(dataset_payload, dict):
            dataset_payload = dict(dataset)
        rows: list[dict[str, Any]] = []
        modality = _normalize_modality(dataset_payload.get("modality"))
        arrays = np.load(artifact_file, allow_pickle=False)
        try:
            for line in entries_jsonl.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                if not isinstance(row, dict):
                    continue
                base = {
                    **row,
                    "analysis_type": modality,
                    "provider": str(dataset_payload.get("provider") or ""),
                    "provider_id": normalize_provider_id(dataset_payload.get("provider_id") or dataset_payload.get("provider")),
                    "package_id": str(dataset_payload.get("dataset_id") or dataset.get("dataset_id") or ""),
                    "package_version": str(dataset_payload.get("dataset_version") or ""),
                    "hosted_dataset_version": str(dataset_payload.get("dataset_version") or ""),
                    "hosted_published_at": str(dataset_payload.get("published_at") or ""),
                    "provider_dataset_version": str(dataset_payload.get("provider_dataset_version") or ""),
                    "builder_version": str(dataset_payload.get("builder_version") or ""),
                    "normalized_schema_version": _coerce_int(dataset_payload.get("normalized_schema_version"), 1),
                    "priority": _coerce_int(row.get("priority"), _coerce_int(dataset_payload.get("priority"), 0)),
                    "source_url": str(row.get("source_url") or dataset_payload.get("source_url") or ""),
                    "published_at": str(row.get("published_at") or dataset_payload.get("published_at") or ""),
                    "generated_at": str(row.get("generated_at") or dataset_payload.get("generated_at") or ""),
                    "canonical_material_key": str(
                        row.get("canonical_material_key")
                        or canonical_material_key(row, modality=modality)
                    ),
                }
                if modality in {"FTIR", "RAMAN"}:
                    signal_key = str(row.get("signal_key") or "").strip()
                    if not signal_key:
                        continue
                    base["axis"] = arrays[f"axis_{signal_key}"].astype(float)
                    base["signal"] = arrays[f"signal_{signal_key}"].astype(float)
                else:
                    peak_key = str(row.get("peak_key") or "").strip()
                    if not peak_key:
                        continue
                    positions = arrays[f"positions_{peak_key}"].astype(float)
                    intensities = arrays[f"intensities_{peak_key}"].astype(float)
                    d_spacing_key = f"d_spacings_{peak_key}"
                    d_spacings = arrays[d_spacing_key].astype(float) if d_spacing_key in arrays else None
                    peaks = []
                    for idx, (position, intensity) in enumerate(zip(positions.tolist(), intensities.tolist(), strict=False)):
                        peak = {
                            "position": float(position),
                            "intensity": float(intensity),
                        }
                        if d_spacings is not None and idx < len(d_spacings):
                            peak["d_spacing"] = float(d_spacings[idx])
                        peaks.append(peak)
                    base["peaks"] = peaks
                    if d_spacings is not None:
                        base["d_spacing"] = [float(item) for item in d_spacings.tolist()]
                rows.append(base)
        finally:
            arrays.close()

        rows.sort(
            key=lambda item: (
                -_coerce_int(item.get("priority"), 0),
                str(item.get("provider") or ""),
                str(item.get("candidate_id") or ""),
            )
        )
        self._dataset_cache[cache_key] = (cache_mtime, dict(dataset_payload), [dict(item) for item in rows])
        return dict(dataset_payload), rows

    def load_entries(self, modality: str) -> list[dict[str, Any]]:
        token = _normalize_modality(modality)
        rows: list[dict[str, Any]] = []
        for dataset in self.active_datasets(modality=token):
            _payload, dataset_rows = self._read_dataset_bundle(dataset)
            rows.extend(dataset_rows)
        rows.sort(
            key=lambda item: (
                -_coerce_int(item.get("priority"), 0),
                str(item.get("provider") or ""),
                str(item.get("candidate_id") or ""),
            )
        )
        return rows

    def providers(self) -> list[dict[str, Any]]:
        rows: dict[str, dict[str, Any]] = {}
        for dataset in self.active_datasets():
            provider_id = normalize_provider_id(dataset.get("provider_id") or dataset.get("provider"))
            item = rows.setdefault(
                provider_id,
                {
                    "provider_id": provider_id,
                    "name": str(dataset.get("provider") or provider_id),
                    "analysis_types": [],
                    "dataset_versions": {},
                    "dataset_count": 0,
                    "candidate_count": 0,
                    "deduped_candidate_count": 0,
                    "published_at": "",
                    "last_successful_ingest_at": "",
                    "failed_ingest_count": 0,
                },
            )
            modality = _normalize_modality(dataset.get("modality"))
            if modality and modality not in item["analysis_types"]:
                item["analysis_types"].append(modality)
            item["dataset_versions"][modality] = str(dataset.get("dataset_version") or "")
            item["dataset_count"] += 1
            item["candidate_count"] += _coerce_int(dataset.get("candidate_count"), 0)
            item["deduped_candidate_count"] += _coerce_int(dataset.get("deduped_candidate_count"), 0)
            item["failed_ingest_count"] += _coerce_int(dataset.get("failed_ingest_count"), 0)
            published_at = str(dataset.get("published_at") or "")
            if published_at > str(item.get("published_at") or ""):
                item["published_at"] = published_at
            last_ingest = str(dataset.get("last_successful_ingest_at") or "")
            if last_ingest > str(item.get("last_successful_ingest_at") or ""):
                item["last_successful_ingest_at"] = last_ingest

        result = []
        for provider_id, item in sorted(rows.items()):
            result.append(
                {
                    **item,
                    "analysis_types": sorted(item["analysis_types"]),
                    "freshness_state": _freshness_state(published_at=str(item.get("published_at") or "")),
                }
            )
        return result

    def coverage(self) -> dict[str, Any]:
        coverage: dict[str, dict[str, Any]] = {}
        for modality in ("FTIR", "RAMAN", "XRD"):
            datasets = self.active_datasets(modality=modality)
            provider_rows: dict[str, dict[str, Any]] = {}
            dedupe_keys: set[str] = set()
            for dataset in datasets:
                provider_id = normalize_provider_id(dataset.get("provider_id") or dataset.get("provider"))
                provider_rows[provider_id] = {
                    "provider_id": provider_id,
                    "provider": str(dataset.get("provider") or provider_id),
                    "candidate_count": _coerce_int(dataset.get("candidate_count"), 0),
                    "deduped_candidate_count": _coerce_int(dataset.get("deduped_candidate_count"), 0),
                    "dataset_version": str(dataset.get("dataset_version") or ""),
                    "published_at": str(dataset.get("published_at") or ""),
                    "last_successful_ingest_at": str(dataset.get("last_successful_ingest_at") or ""),
                    "failed_ingest_count": _coerce_int(dataset.get("failed_ingest_count"), 0),
                    "freshness_state": str(dataset.get("freshness_state") or _freshness_state(published_at=str(dataset.get("published_at") or ""))),
                }
                _dataset_payload, dataset_rows = self._read_dataset_bundle(dataset)
                dedupe_keys.update(
                    str(item.get("canonical_material_key") or canonical_material_key(item, modality=modality))
                    for item in dataset_rows
                )
            published_values = [str(item.get("published_at") or "") for item in datasets if str(item.get("published_at") or "")]
            ingest_values = [
                str(item.get("last_successful_ingest_at") or "")
                for item in datasets
                if str(item.get("last_successful_ingest_at") or "")
            ]
            coverage[modality] = {
                "total_candidate_count": sum(_coerce_int(item.get("candidate_count"), 0) for item in datasets),
                "deduped_candidate_count": len(dedupe_keys),
                "published_at": max(published_values, default=""),
                "freshness_state": _freshness_state(published_at=max(published_values, default="")),
                "last_successful_ingest_at": max(ingest_values, default=""),
                "failed_ingest_count": sum(_coerce_int(item.get("failed_ingest_count"), 0) for item in datasets),
                "providers": provider_rows,
            }
            if modality == "XRD":
                coverage[modality].update(
                    xrd_coverage_profile(
                        total_candidate_count=coverage[modality]["total_candidate_count"],
                        provider_rows=provider_rows,
                    )
                )
        return coverage

    def live_provider_ids(self, *, modality: str | None = None) -> set[str]:
        return {
            normalize_provider_id(item.get("provider_id") or item.get("provider"))
            for item in self.active_datasets(modality=modality)
            if normalize_provider_id(item.get("provider_id") or item.get("provider"))
        }

    def live_provider_count(self, *, modality: str | None = None) -> int:
        return len(self.live_provider_ids(modality=modality))

    def missing_modalities(self, required_modalities: tuple[str, ...] = ("FTIR", "RAMAN", "XRD")) -> list[str]:
        missing: list[str] = []
        for modality in required_modalities:
            if self.live_provider_count(modality=modality) <= 0:
                missing.append(modality)
        return missing

    def availability_error(self, *, modality: str | None = None) -> str:
        token = _normalize_modality(modality) if modality else ""
        if not self.manifest_path.exists():
            return f"Cloud backend is reachable, but no hosted library manifest is published at {self.root}."
        if token and not self.active_datasets(modality=token):
            return f"Cloud backend is reachable, but no hosted {token} provider dataset is published at {self.root}."
        if not self.active_datasets():
            return f"Cloud backend is reachable, but the hosted library catalog at {self.root} has no active provider datasets."
        return ""


def _hosted_manifest_profile(hosted_root: Path) -> dict[str, Any]:
    """Read published manifest and summarize hosted health without loading dataset bundles."""
    manifest_path = hosted_root / HOSTED_MANIFEST_FILE
    if not manifest_path.exists():
        return {
            "coverage_tier": "empty",
            "xrd_entry_count": 0,
            "total_entry_count": 0,
            "package_count": 0,
            "provider_candidate_counts": {},
            "mtime": 0.0,
        }
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "coverage_tier": "empty",
            "xrd_entry_count": 0,
            "total_entry_count": 0,
            "package_count": 0,
            "provider_candidate_counts": {},
            "mtime": manifest_path.stat().st_mtime,
        }
    if not isinstance(payload, dict):
        return {
            "coverage_tier": "empty",
            "xrd_entry_count": 0,
            "total_entry_count": 0,
            "package_count": 0,
            "provider_candidate_counts": {},
            "mtime": manifest_path.stat().st_mtime,
        }
    total_xrd = 0
    total_entries = 0
    package_count = 0
    provider_rows: dict[str, dict[str, Any]] = {}
    for dataset in (payload.get("datasets") or []):
        if not isinstance(dataset, dict):
            continue
        if not dataset.get("active", True):
            continue
        package_count += 1
        total_entries += _coerce_int(dataset.get("candidate_count"), 0)
        if _normalize_dataset_modality(dataset) != "XRD":
            continue
        count = _coerce_int(dataset.get("candidate_count"), 0)
        total_xrd += count
        pid = normalize_provider_id(dataset.get("provider_id") or dataset.get("provider"))
        bucket = provider_rows.setdefault(pid, {"candidate_count": 0})
        bucket["candidate_count"] = _coerce_int(bucket.get("candidate_count"), 0) + count
    profile = xrd_coverage_profile(total_candidate_count=total_xrd, provider_rows=provider_rows)
    return {
        "coverage_tier": str(profile.get("coverage_tier") or "empty"),
        "xrd_entry_count": total_xrd,
        "total_entry_count": total_entries,
        "package_count": package_count,
        "provider_candidate_counts": dict(profile.get("provider_candidate_counts") or {}),
        "coverage_warning_code": str(profile.get("coverage_warning_code") or ""),
        "coverage_warning_message": str(profile.get("coverage_warning_message") or ""),
        "mtime": manifest_path.stat().st_mtime,
    }


def _normalized_root_candidates(*, hosted_root: Path, explicit_root: str | Path | None = None) -> list[Path]:
    candidates: list[Path] = []
    if explicit_root:
        candidates.append(Path(explicit_root).resolve())
    search_roots = [hosted_root.parent, PROJECT_ROOT / "build", PROJECT_ROOT / "sample_data"]
    for base_root in search_roots:
        root_names = _LOCAL_NORMALIZED_ROOT_NAMES
        if base_root == PROJECT_ROOT / "sample_data":
            root_names = _SAMPLE_NORMALIZED_ROOT_NAMES
        for name in root_names:
            candidates.append((base_root / name).resolve())
    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _candidate_origin_priority(*, candidate: Path, hosted_root: Path, explicit_root: str | Path | None = None) -> int:
    if explicit_root:
        explicit_path = Path(explicit_root).resolve()
        if candidate == explicit_path:
            return 4
    sample_root = (PROJECT_ROOT / "sample_data").resolve()
    build_root = (PROJECT_ROOT / "build").resolve()
    hosted_parent = hosted_root.parent.resolve()
    try:
        if hosted_parent != build_root and candidate.is_relative_to(hosted_parent):
            return 3
    except ValueError:
        pass
    try:
        if candidate.is_relative_to(sample_root):
            return 2
    except ValueError:
        pass
    return 1


def _normalized_root_score(root: Path) -> tuple[int, int, int, float]:
    if not root.exists():
        return (0, 0, 0, 0.0)
    spec_paths = [path for path in root.rglob("package_spec.json") if (path.parent / "entries.jsonl").exists()]
    if not spec_paths:
        return (0, 0, 0, 0.0)
    latest_mtime = 0.0
    total_entry_count = 0
    xrd_entry_count = 0
    for spec_path in spec_paths:
        latest_mtime = max(latest_mtime, spec_path.stat().st_mtime, (spec_path.parent / "entries.jsonl").stat().st_mtime)
        entry_count = _count_jsonl_rows(spec_path.parent / "entries.jsonl")
        total_entry_count += entry_count
        try:
            payload = json.loads(spec_path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        if _normalize_modality((payload or {}).get("analysis_type")) == "XRD":
            xrd_entry_count += entry_count
    return (xrd_entry_count, total_entry_count, len(spec_paths), latest_mtime)


def _normalized_root_profile(root: Path) -> dict[str, Any]:
    xrd_entry_count, total_entry_count, package_count, latest_mtime = _normalized_root_score(root)
    return {
        "xrd_entry_count": xrd_entry_count,
        "total_entry_count": total_entry_count,
        "package_count": package_count,
        "mtime": latest_mtime,
    }


def _score_tuple(payload: Mapping[str, Any]) -> tuple[int, int, int, float]:
    return (
        _coerce_int(payload.get("xrd_entry_count"), 0),
        _coerce_int(payload.get("total_entry_count"), 0),
        _coerce_int(payload.get("package_count"), 0),
        float(payload.get("mtime") or 0.0),
    )


def _is_richer_profile(candidate_profile: Mapping[str, Any], existing_profile: Mapping[str, Any]) -> bool:
    return _score_tuple(candidate_profile) > _score_tuple(existing_profile)


def discover_local_normalized_root(
    *,
    hosted_root: str | Path | None = None,
    explicit_root: str | Path | None = None,
) -> Path | None:
    target_root = resolve_hosted_root(hosted_root)
    if explicit_root:
        explicit_path = Path(explicit_root).resolve()
        if _normalized_root_score(explicit_path)[1] > 0:
            return explicit_path
    ranked = sorted(
        (
            (
                candidate,
                _candidate_origin_priority(candidate=candidate, hosted_root=target_root, explicit_root=explicit_root),
                _normalized_root_score(candidate),
            )
            for candidate in _normalized_root_candidates(hosted_root=target_root, explicit_root=explicit_root)
        ),
        key=lambda item: (item[1], item[2]),
        reverse=True,
    )
    for candidate, _origin_priority, score in ranked:
        if score[1] > 0:
            return candidate
    return None


def ensure_local_dev_hosted_catalog(
    *,
    hosted_root: str | Path | None = None,
    normalized_root: str | Path | None = None,
    job_state_root: str | Path | None = None,
    dev_mode: bool = False,
) -> dict[str, Any]:
    target_root = resolve_hosted_root(hosted_root)
    manifest_path = target_root / HOSTED_MANIFEST_FILE
    candidate_root = discover_local_normalized_root(hosted_root=target_root, explicit_root=normalized_root)
    candidate_profile = _normalized_root_profile(candidate_root) if candidate_root is not None else {
        "xrd_entry_count": 0,
        "total_entry_count": 0,
        "package_count": 0,
        "mtime": 0.0,
    }
    selected_source_root = str(candidate_root) if candidate_root is not None else ""

    if manifest_path.exists():
        existing_profile = _hosted_manifest_profile(target_root)
        existing_tier = str(existing_profile.get("coverage_tier") or "empty")
        existing_xrd_count = _coerce_int(existing_profile.get("xrd_entry_count"), 0)
        richer_source_available = candidate_root is not None and _is_richer_profile(candidate_profile, existing_profile)
        if existing_tier == "expanded" and not richer_source_available:
            return {
                "state": "already_present",
                "hosted_root": str(target_root),
                "source_root": selected_source_root,
                "previous_xrd_count": existing_xrd_count,
                "previous_total_count": _coerce_int(existing_profile.get("total_entry_count"), 0),
                "previous_package_count": _coerce_int(existing_profile.get("package_count"), 0),
                "previous_coverage_tier": existing_tier,
                "upgrade_reason": "existing_coverage_is_expanded",
                "selected_source_xrd_count": _coerce_int(candidate_profile.get("xrd_entry_count"), 0),
                "selected_source_total_count": _coerce_int(candidate_profile.get("total_entry_count"), 0),
                "selected_source_package_count": _coerce_int(candidate_profile.get("package_count"), 0),
            }
        if not dev_mode:
            return {
                "state": "already_present",
                "hosted_root": str(target_root),
                "source_root": selected_source_root,
                "previous_xrd_count": existing_xrd_count,
                "previous_total_count": _coerce_int(existing_profile.get("total_entry_count"), 0),
                "previous_package_count": _coerce_int(existing_profile.get("package_count"), 0),
                "previous_coverage_tier": existing_tier,
                "upgrade_reason": "dev_mode_disabled",
                "selected_source_xrd_count": _coerce_int(candidate_profile.get("xrd_entry_count"), 0),
                "selected_source_total_count": _coerce_int(candidate_profile.get("total_entry_count"), 0),
                "selected_source_package_count": _coerce_int(candidate_profile.get("package_count"), 0),
            }
        if candidate_root is None:
            return {
                "state": "already_present",
                "hosted_root": str(target_root),
                "source_root": "",
                "previous_xrd_count": existing_xrd_count,
                "previous_total_count": _coerce_int(existing_profile.get("total_entry_count"), 0),
                "previous_package_count": _coerce_int(existing_profile.get("package_count"), 0),
                "previous_coverage_tier": existing_tier,
                "upgrade_reason": "no_richer_normalized_root_found",
            }
        if not richer_source_available:
            return {
                "state": "already_present",
                "hosted_root": str(target_root),
                "source_root": selected_source_root,
                "previous_xrd_count": existing_xrd_count,
                "previous_total_count": _coerce_int(existing_profile.get("total_entry_count"), 0),
                "previous_package_count": _coerce_int(existing_profile.get("package_count"), 0),
                "previous_coverage_tier": existing_tier,
                "upgrade_reason": "candidate_not_richer",
                "selected_source_xrd_count": _coerce_int(candidate_profile.get("xrd_entry_count"), 0),
                "selected_source_total_count": _coerce_int(candidate_profile.get("total_entry_count"), 0),
                "selected_source_package_count": _coerce_int(candidate_profile.get("package_count"), 0),
            }
        try:
            from tools.publish_hosted_library import publish_hosted_library

            result = publish_hosted_library(
                normalized_root=candidate_root,
                output_root=target_root,
                job_state_root=job_state_root,
                clean=True,
            )
        except Exception as exc:
            return {
                "state": "upgrade_failed",
                "hosted_root": str(target_root),
                "source_root": selected_source_root,
                "previous_xrd_count": existing_xrd_count,
                "previous_total_count": _coerce_int(existing_profile.get("total_entry_count"), 0),
                "previous_package_count": _coerce_int(existing_profile.get("package_count"), 0),
                "previous_coverage_tier": existing_tier,
                "message": f"Hosted library upgrade failed: {exc}",
            }
        new_profile = _hosted_manifest_profile(target_root)
        new_tier = str(new_profile.get("coverage_tier") or "empty")
        new_xrd_count = _coerce_int(new_profile.get("xrd_entry_count"), 0)
        return {
            "state": "upgraded",
            "hosted_root": str(target_root),
            "source_root": selected_source_root,
            "previous_xrd_count": existing_xrd_count,
            "previous_total_count": _coerce_int(existing_profile.get("total_entry_count"), 0),
            "previous_package_count": _coerce_int(existing_profile.get("package_count"), 0),
            "previous_coverage_tier": existing_tier,
            "new_xrd_count": new_xrd_count,
            "new_total_count": _coerce_int(new_profile.get("total_entry_count"), 0),
            "new_package_count": _coerce_int(new_profile.get("package_count"), 0),
            "new_coverage_tier": new_tier,
            "upgrade_reason": (
                f"stale_{existing_tier}_upgraded_to_{new_tier}"
                if existing_tier in {"empty", "seed_dev"}
                else f"stale_manifest_republished_to_{new_tier}"
            ),
            "selected_source_xrd_count": _coerce_int(candidate_profile.get("xrd_entry_count"), 0),
            "selected_source_total_count": _coerce_int(candidate_profile.get("total_entry_count"), 0),
            "selected_source_package_count": _coerce_int(candidate_profile.get("package_count"), 0),
            **result,
        }

    if not dev_mode:
        return {
            "state": "disabled",
            "hosted_root": str(target_root),
        }
    source_root = discover_local_normalized_root(hosted_root=target_root, explicit_root=normalized_root)
    if source_root is None:
        return {
            "state": "missing_normalized_root",
            "hosted_root": str(target_root),
            "message": f"No normalized provider packages were found near {target_root}.",
        }
    source_profile = _normalized_root_profile(source_root)
    try:
        from tools.publish_hosted_library import publish_hosted_library

        result = publish_hosted_library(
            normalized_root=source_root,
            output_root=target_root,
            job_state_root=job_state_root,
            clean=False,
        )
    except Exception as exc:
        return {
            "state": "publish_failed",
            "hosted_root": str(target_root),
            "source_root": str(source_root),
            "message": f"Hosted library bootstrap failed: {exc}",
        }
    new_profile = _hosted_manifest_profile(target_root)
    new_tier = str(new_profile.get("coverage_tier") or "empty")
    new_xrd_count = _coerce_int(new_profile.get("xrd_entry_count"), 0)
    return {
        "state": "published",
        "hosted_root": str(target_root),
        "source_root": str(source_root),
        "new_xrd_count": new_xrd_count,
        "new_total_count": _coerce_int(new_profile.get("total_entry_count"), 0),
        "new_package_count": _coerce_int(new_profile.get("package_count"), 0),
        "new_coverage_tier": new_tier,
        "selected_source_xrd_count": _coerce_int(source_profile.get("xrd_entry_count"), 0),
        "selected_source_total_count": _coerce_int(source_profile.get("total_entry_count"), 0),
        "selected_source_package_count": _coerce_int(source_profile.get("package_count"), 0),
        **result,
    }
