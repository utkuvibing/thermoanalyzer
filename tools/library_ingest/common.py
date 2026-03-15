"""Shared helpers for provider ingest tooling."""

from __future__ import annotations

import csv
import gzip
import io
import json
import math
import re
import shutil
import tarfile
import tempfile
import zipfile
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import numpy as np

from .schema import PackageSpec

BUILD_ROOT = Path("build") / "reference_library_ingest"
JOB_STATE_ROOT = Path("build") / "reference_library_jobs"
BUILDER_VERSION = "b1"
NORMALIZED_SCHEMA_VERSION = 1
PROVIDER_SOURCE_FILE = Path(__file__).with_name("provider_sources.json")
USER_AGENT = "ThermoAnalyzer-Ingest/1"


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def today_version_token() -> str:
    return datetime.now(UTC).strftime("%Y.%m.%d")


def build_version(provider_dataset_version: str | None, *, generated_at: str) -> str:
    dataset_version = str(provider_dataset_version or "").strip() or today_version_token()
    return f"{dataset_version}-{BUILDER_VERSION}"


def load_provider_sources() -> dict[str, Any]:
    return json.loads(PROVIDER_SOURCE_FILE.read_text(encoding="utf-8"))


def resolve_output_root(output_root: str | Path | None) -> Path:
    return Path(output_root or BUILD_ROOT).resolve()


def resolve_job_state_root(job_state_root: str | Path | None) -> Path:
    return Path(job_state_root or JOB_STATE_ROOT).resolve()


def ensure_dir(path: str | Path) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def read_json(path: str | Path, default: Any) -> Any:
    source = Path(path)
    if not source.exists():
        return default
    return json.loads(source.read_text(encoding="utf-8"))


def write_json(path: str | Path, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_jsonl(path: str | Path, rows: Iterable[dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def safe_slug(value: str, *, default: str = "item") -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    return slug or default


def ingest_job_state_path(
    provider_id: str,
    provider_dataset_version: str,
    *,
    job_state_root: str | Path | None = None,
) -> Path:
    root = resolve_job_state_root(job_state_root)
    return root / safe_slug(provider_id) / f"{safe_slug(provider_dataset_version, default='dataset')}.json"


def default_ingest_job_state(provider_id: str, provider_dataset_version: str) -> dict[str, Any]:
    return {
        "provider_id": safe_slug(provider_id),
        "provider_dataset_version": str(provider_dataset_version),
        "cursor": 0,
        "processed_count": 0,
        "failed_count": 0,
        "last_successful_ingest_at": "",
        "sampled_failures": [],
        "next_chunk_index_by_analysis_type": {},
        "pending_entries_by_analysis_type": {},
        "emitted_package_ids": [],
        "completed": False,
        "completed_at": "",
    }


def load_ingest_job_state(
    provider_id: str,
    provider_dataset_version: str,
    *,
    job_state_root: str | Path | None = None,
) -> tuple[Path, dict[str, Any]]:
    path = ingest_job_state_path(
        provider_id,
        provider_dataset_version,
        job_state_root=job_state_root,
    )
    state = read_json(path, default_ingest_job_state(provider_id, provider_dataset_version))
    if not isinstance(state, dict):
        state = default_ingest_job_state(provider_id, provider_dataset_version)
    state.setdefault("provider_id", safe_slug(provider_id))
    state.setdefault("provider_dataset_version", str(provider_dataset_version))
    state.setdefault("cursor", 0)
    state.setdefault("processed_count", 0)
    state.setdefault("failed_count", 0)
    state.setdefault("last_successful_ingest_at", "")
    state.setdefault("sampled_failures", [])
    state.setdefault("next_chunk_index_by_analysis_type", {})
    state.setdefault("pending_entries_by_analysis_type", {})
    state.setdefault("emitted_package_ids", [])
    state.setdefault("completed", False)
    state.setdefault("completed_at", "")
    return path, state


def save_ingest_job_state(path: str | Path, state: dict[str, Any]) -> None:
    write_json(path, state)


def iter_jsonl(path: str | Path) -> Iterator[dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        return iter(())
    def _rows() -> Iterator[dict[str, Any]]:
        for line in source.read_text(encoding="utf-8").splitlines():
            if line.strip():
                yield json.loads(line)
    return _rows()


def read_json_records(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if source.suffix.lower() == ".jsonl":
        return list(iter_jsonl(source))
    payload = read_json(source, [])
    if isinstance(payload, dict):
        rows = payload.get("items") or payload.get("records") or payload.get("documents") or payload.get("data") or []
        return [dict(row) for row in rows if isinstance(row, dict)]
    if isinstance(payload, list):
        return [dict(row) for row in payload if isinstance(row, dict)]
    raise ValueError(f"Unsupported record payload in {source}")


def sorted_entries(entries: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        entries,
        key=lambda item: (
            str(item.get("provider") or ""),
            str(item.get("source_id") or ""),
            str(item.get("candidate_id") or ""),
        ),
    )


def provider_output_root(output_root: str | Path, provider_id: str) -> Path:
    return ensure_dir(Path(output_root) / safe_slug(provider_id))


def normalized_package_dirs(root: str | Path) -> list[Path]:
    source_root = Path(root)
    if not source_root.exists():
        return []
    package_dirs: list[Path] = []
    for spec_path in source_root.rglob("package_spec.json"):
        package_dir = spec_path.parent
        if (package_dir / "entries.jsonl").exists():
            package_dirs.append(package_dir)
    package_dirs.sort(key=lambda item: str(item).lower())
    return package_dirs


def load_package_spec(path: str | Path) -> PackageSpec:
    return PackageSpec.from_dict(read_json(path, {}))


def read_package_entries(path: str | Path) -> list[dict[str, Any]]:
    return sorted_entries(iter_jsonl(path))


def iter_normalized_packages(root: str | Path) -> Iterator[tuple[PackageSpec, list[dict[str, Any]]]]:
    for package_dir in normalized_package_dirs(root):
        yield load_package_spec(package_dir / "package_spec.json"), read_package_entries(package_dir / "entries.jsonl")


def write_normalized_package(package_dir: str | Path, spec: PackageSpec, entries: Iterable[dict[str, Any]]) -> None:
    target_dir = ensure_dir(package_dir)
    ordered_entries = sorted_entries(entries)
    write_json(target_dir / "package_spec.json", spec.to_dict())
    write_jsonl(target_dir / "entries.jsonl", ordered_entries)


def http_client() -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(60.0, connect=30.0), headers={"User-Agent": USER_AGENT}, follow_redirects=True)


def download_bytes(url: str) -> bytes:
    with http_client() as client:
        response = client.get(url)
        response.raise_for_status()
        return response.content


def download_text(url: str) -> str:
    return download_bytes(url).decode("utf-8", errors="ignore")


def extract_archive_to_temp(path_or_url: str | Path) -> Path:
    source = str(path_or_url)
    if source.startswith("http://") or source.startswith("https://"):
        raw = download_bytes(source)
        temp_dir = Path(tempfile.mkdtemp(prefix="ta_provider_extract_"))
        archive_path = temp_dir / "archive.bin"
        archive_path.write_bytes(raw)
        return _extract_archive(archive_path, temp_dir / "extracted")
    source_path = Path(source).resolve()
    if source_path.is_dir():
        return source_path
    temp_dir = Path(tempfile.mkdtemp(prefix="ta_provider_extract_"))
    return _extract_archive(source_path, temp_dir / "extracted")


def _extract_archive(archive_path: Path, target_dir: Path) -> Path:
    ensure_dir(target_dir)
    lower = archive_path.name.lower()
    if lower.endswith(".zip"):
        with zipfile.ZipFile(archive_path, "r") as archive:
            archive.extractall(target_dir)
        return target_dir
    if lower.endswith((".tar.gz", ".tgz", ".tar")):
        with tarfile.open(archive_path, "r:*") as archive:
            archive.extractall(target_dir)
        return target_dir
    raise ValueError(f"Unsupported archive format: {archive_path}")


def remove_temp_dir(path: str | Path | None) -> None:
    if path:
        shutil.rmtree(Path(path), ignore_errors=True)


def coerce_float_array(values: Iterable[Any]) -> np.ndarray:
    return np.asarray(list(values), dtype=float)


def canonicalize_axis_signal(
    axis: Iterable[Any],
    signal: Iterable[Any],
    *,
    invert: bool = False,
    shift_to_zero: bool = True,
) -> tuple[list[float], list[float]]:
    axis_arr = np.asarray(list(axis), dtype=float)
    signal_arr = np.asarray(list(signal), dtype=float)
    if axis_arr.size == 0 or signal_arr.size == 0 or axis_arr.size != signal_arr.size:
        return [], []
    mask = np.isfinite(axis_arr) & np.isfinite(signal_arr)
    axis_arr = axis_arr[mask]
    signal_arr = signal_arr[mask]
    if axis_arr.size == 0:
        return [], []
    order = np.argsort(axis_arr)
    axis_arr = axis_arr[order]
    signal_arr = signal_arr[order]
    unique_axis, unique_idx = np.unique(axis_arr, return_index=True)
    axis_arr = unique_axis
    signal_arr = signal_arr[unique_idx]
    if shift_to_zero:
        signal_arr = signal_arr - float(np.nanmin(signal_arr))
    max_value = float(np.nanmax(signal_arr)) if signal_arr.size else 0.0
    if max_value > 0.0:
        signal_arr = signal_arr / max_value
    if invert:
        signal_arr = 1.0 - signal_arr
        signal_arr = signal_arr - float(np.nanmin(signal_arr))
        max_value = float(np.nanmax(signal_arr)) if signal_arr.size else 0.0
        if max_value > 0.0:
            signal_arr = signal_arr / max_value
    return axis_arr.astype(float).tolist(), signal_arr.astype(float).tolist()


def parse_jcamp_xy(text: str) -> tuple[dict[str, str], list[float], list[float]]:
    metadata: dict[str, str] = {}
    axis: list[float] = []
    signal: list[float] = []
    reading_xy = False
    tokens: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("##"):
            reading_xy = False
            if "=" in line:
                key, value = line[2:].split("=", 1)
                metadata[key.strip().upper()] = value.strip()
            if line.upper().startswith("##XYPOINTS"):
                reading_xy = True
            continue
        if not reading_xy:
            continue
        tokens.extend(line.replace(",", " ").split())
    for index in range(0, len(tokens) - 1, 2):
        try:
            axis.append(float(tokens[index]))
            signal.append(float(tokens[index + 1]))
        except ValueError:
            continue
    return metadata, axis, signal


def read_csv_text(text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


class ChunkedPackageEmitter:
    def __init__(
        self,
        *,
        output_root: Path,
        package_prefix: str,
        analysis_type: str,
        provider_name: str,
        source_url: str,
        license_name: str,
        license_text: str,
        attribution: str,
        priority: int,
        generated_at: str,
        provider_dataset_version: str,
        chunk_size: int,
        next_chunk_index: int = 1,
        initial_buffer: list[dict[str, Any]] | None = None,
    ) -> None:
        self.output_root = ensure_dir(output_root)
        self.package_prefix = package_prefix
        self.analysis_type = analysis_type
        self.provider_name = provider_name
        self.source_url = source_url
        self.license_name = license_name
        self.license_text = license_text
        self.attribution = attribution
        self.priority = int(priority)
        self.generated_at = generated_at
        self.provider_dataset_version = provider_dataset_version
        self.chunk_size = max(int(chunk_size), 1)
        self.next_chunk_index = max(int(next_chunk_index), 1)
        self.buffer: list[dict[str, Any]] = [dict(item) for item in (initial_buffer or [])]
        self.emitted_package_ids: list[str] = []
        self.version = build_version(provider_dataset_version, generated_at=generated_at)

    def append(self, entry: dict[str, Any]) -> list[str]:
        self.buffer.append(entry)
        if len(self.buffer) < self.chunk_size:
            return []
        return [self.flush()]

    def flush(self) -> str:
        if not self.buffer:
            return ""
        package_id = f"{self.package_prefix}_{self.next_chunk_index:04d}"
        package_dir = ensure_dir(self.output_root / package_id)
        spec = PackageSpec(
            package_id=package_id,
            analysis_type=self.analysis_type,
            provider=self.provider_name,
            version=self.version,
            source_url=self.source_url,
            license_name=self.license_name,
            license_text=self.license_text,
            attribution=self.attribution,
            priority=self.priority,
            published_at=self.generated_at,
            generated_at=self.generated_at,
            provider_dataset_version=self.provider_dataset_version,
            builder_version=BUILDER_VERSION,
            normalized_schema_version=NORMALIZED_SCHEMA_VERSION,
        )
        write_json(package_dir / "package_spec.json", spec.to_dict())
        write_jsonl(package_dir / "entries.jsonl", sorted_entries(self.buffer))
        self.emitted_package_ids.append(package_id)
        self.buffer = []
        self.next_chunk_index += 1
        return package_id

    def close(self) -> list[str]:
        emitted: list[str] = []
        if self.buffer:
            package_id = self.flush()
            if package_id:
                emitted.append(package_id)
        return emitted


def bragg_two_theta_from_d_spacing(d_spacing: float, wavelength_angstrom: float) -> float | None:
    if d_spacing <= 0.0 or wavelength_angstrom <= 0.0:
        return None
    ratio = wavelength_angstrom / (2.0 * d_spacing)
    if ratio <= 0.0 or ratio >= 1.0:
        return None
    theta = math.asin(ratio)
    return math.degrees(2.0 * theta)


def d_spacing_from_two_theta(two_theta: float, wavelength_angstrom: float) -> float | None:
    if two_theta <= 0.0 or wavelength_angstrom <= 0.0:
        return None
    theta = math.radians(two_theta / 2.0)
    denominator = 2.0 * math.sin(theta)
    if denominator <= 0.0:
        return None
    return wavelength_angstrom / denominator


def normalize_xrd_peaks(raw_peaks: Iterable[dict[str, Any]]) -> list[dict[str, float]]:
    peaks: list[dict[str, float]] = []
    for item in raw_peaks:
        try:
            position = float(item["position"])
            intensity = float(item["intensity"])
            d_spacing = float(item["d_spacing"])
        except (KeyError, TypeError, ValueError):
            continue
        if intensity <= 0.0:
            continue
        peaks.append({
            "position": round(position, 6),
            "intensity": round(intensity, 6),
            "d_spacing": round(d_spacing, 8),
        })
    peaks.sort(key=lambda entry: float(entry["d_spacing"]))
    return peaks


def gzip_decompress_if_needed(raw: bytes) -> bytes:
    if raw[:2] == b"\x1f\x8b":
        return gzip.decompress(raw)
    return raw
