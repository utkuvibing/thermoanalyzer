"""Publish normalized provider outputs into hosted cloud-library datasets."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.hosted_library import (
    build_hosted_manifest,
    canonical_material_key,
    discover_local_normalized_root,
    resolve_hosted_root,
    spectral_signal_hash,
    write_hosted_dataset,
    xrd_peak_hash,
)
from tools.library_ingest.common import (
    BUILD_ROOT,
    JOB_STATE_ROOT,
    load_ingest_job_state,
    normalized_package_dirs,
    read_package_entries,
    safe_slug,
)
from tools.library_ingest.providers import provider_metadata
from tools.library_ingest.schema import PackageSpec


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish hosted cloud-library datasets from normalized provider outputs."
    )
    parser.add_argument(
        "--normalized-root",
        default=str(BUILD_ROOT),
        help="Normalized provider package root containing package_spec.json + entries.jsonl outputs.",
    )
    parser.add_argument(
        "--output-root",
        default=None,
        help="Hosted output root. Defaults to THERMOANALYZER_LIBRARY_HOSTED_ROOT or build/reference_library_hosted.",
    )
    parser.add_argument(
        "--job-state-root",
        default=str(JOB_STATE_ROOT),
        help="Job-state root used to enrich publish metadata with ingest checkpoints.",
    )
    parser.add_argument("--provider", action="append", default=[], help="Optional provider id filter.")
    parser.add_argument("--analysis-type", action="append", default=[], help="Optional modality filter.")
    parser.add_argument("--clean", action="store_true", help="Remove the destination hosted root before publishing.")
    return parser.parse_args(argv)


def _load_package_spec(path: Path) -> PackageSpec:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        payload = {}
    return PackageSpec.from_dict(payload)


def _dedupe_entries(entries: list[dict[str, Any]], *, modality: str) -> list[dict[str, Any]]:
    ranked = sorted(
        (dict(item) for item in entries),
        key=lambda item: (
            -int(item.get("priority") or 0),
            str(item.get("candidate_id") or ""),
        ),
    )
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for entry in ranked:
        material_key = canonical_material_key(entry, modality=modality)
        entry["canonical_material_key"] = material_key
        if modality in {"FTIR", "RAMAN"}:
            signature = spectral_signal_hash(
                list(entry.get("axis") or []),
                list(entry.get("signal") or []),
            )
            entry["signal_hash"] = signature
        else:
            signature = xrd_peak_hash(list(entry.get("peaks") or []))
            entry["peak_hash"] = signature
        dedupe_key = (material_key, signature)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        deduped.append(entry)
    return deduped


def _group_normalized_packages(
    normalized_root: Path,
    *,
    provider_filter: set[str],
    modality_filter: set[str],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for package_dir in normalized_package_dirs(normalized_root):
        provider_id = safe_slug(package_dir.parent.name)
        spec = _load_package_spec(package_dir / "package_spec.json")
        modality = str(spec.analysis_type or "").upper()
        dataset_version = str(spec.provider_dataset_version or "").strip() or str(spec.version or "").strip()
        if provider_filter and provider_id not in provider_filter:
            continue
        if modality_filter and modality not in modality_filter:
            continue
        bucket = grouped.setdefault(
            (modality, provider_id, dataset_version),
            {
                "specs": [],
                "entries": [],
            },
        )
        bucket["specs"].append(spec)
        bucket["entries"].extend(read_package_entries(package_dir / "entries.jsonl"))
    return grouped


def _active_dataset_key(dataset: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(dataset.get("modality") or ""),
        str(dataset.get("provider_id") or ""),
        str(dataset.get("published_at") or ""),
    )


def _resolve_normalized_root(
    normalized_root: str | Path | None,
    *,
    output_root: str | Path | None = None,
) -> Path:
    discovered = discover_local_normalized_root(
        hosted_root=output_root,
        explicit_root=normalized_root,
    )
    if discovered is not None:
        return discovered
    return Path(normalized_root or BUILD_ROOT).resolve()


def publish_hosted_library(
    *,
    normalized_root: str | Path | None,
    output_root: str | Path | None = None,
    job_state_root: str | Path | None = None,
    provider_filters: list[str] | None = None,
    analysis_type_filters: list[str] | None = None,
    clean: bool = False,
) -> dict[str, Any]:
    normalized_root_path = _resolve_normalized_root(normalized_root, output_root=output_root)
    output_root_path = resolve_hosted_root(output_root)
    if clean:
        shutil.rmtree(output_root_path, ignore_errors=True)
    output_root_path.mkdir(parents=True, exist_ok=True)

    grouped = _group_normalized_packages(
        normalized_root_path,
        provider_filter={safe_slug(item) for item in (provider_filters or []) if str(item).strip()},
        modality_filter={str(item).strip().upper() for item in (analysis_type_filters or []) if str(item).strip()},
    )
    datasets: list[dict[str, Any]] = []
    publish_rows: list[dict[str, Any]] = []
    for (modality, provider_id, dataset_version), bucket in sorted(grouped.items()):
        specs: list[PackageSpec] = list(bucket["specs"])
        entries = list(bucket["entries"])
        if not specs or not entries:
            continue
        provider = provider_metadata(provider_id)
        deduped_entries = _dedupe_entries(entries, modality=modality)
        state_path, job_state = load_ingest_job_state(
            provider_id,
            dataset_version,
            job_state_root=job_state_root,
        )
        published_at = max((spec.published_at or spec.generated_at for spec in specs), default="")
        generated_at = max((spec.generated_at for spec in specs), default=published_at)
        dataset_dir = output_root_path / "datasets" / modality.lower() / provider_id / dataset_version
        dataset_id = f"{provider_id}_{modality.lower()}_{safe_slug(dataset_version, default='dataset')}"
        dataset_meta = write_hosted_dataset(
            output_dir=dataset_dir,
            dataset_metadata={
                "dataset_id": dataset_id,
                "provider_id": provider_id,
                "provider": specs[0].provider or str(provider.get("provider_name") or provider_id),
                "modality": modality,
                "dataset_version": dataset_version,
                "published_at": published_at,
                "generated_at": generated_at,
                "last_successful_ingest_at": str(job_state.get("last_successful_ingest_at") or generated_at),
                "failed_ingest_count": int(job_state.get("failed_count") or 0),
                "candidate_count": len(entries),
                "deduped_candidate_count": len(deduped_entries),
                "provider_dataset_version": dataset_version,
                "builder_version": specs[0].builder_version,
                "normalized_schema_version": specs[0].normalized_schema_version,
                "source_url": specs[0].source_url,
                "license_name": specs[0].license_name,
                "license_text": specs[0].license_text,
                "attribution": specs[0].attribution,
                "priority": max(int(spec.priority or 0) for spec in specs),
            },
            entries=deduped_entries,
        )
        dataset_row = {
            **dataset_meta,
            "path": str(dataset_dir.relative_to(output_root_path)).replace("\\", "/"),
            "active": False,
        }
        datasets.append(dataset_row)
        publish_rows.append(
            {
                "provider_id": provider_id,
                "modality": modality,
                "dataset_version": dataset_version,
                "candidate_count": dataset_meta["candidate_count"],
                "deduped_candidate_count": dataset_meta["deduped_candidate_count"],
                "failed_ingest_count": dataset_meta["failed_ingest_count"],
                "state_path": str(state_path),
            }
        )

    active_by_group: dict[tuple[str, str], dict[str, Any]] = {}
    for dataset in datasets:
        group_key = (str(dataset.get("modality") or ""), str(dataset.get("provider_id") or ""))
        current = active_by_group.get(group_key)
        if current is None or _active_dataset_key(dataset) >= _active_dataset_key(current):
            active_by_group[group_key] = dataset
    for dataset in datasets:
        group_key = (str(dataset.get("modality") or ""), str(dataset.get("provider_id") or ""))
        dataset["active"] = active_by_group.get(group_key) is dataset

    manifest = build_hosted_manifest(
        generated_at=max((str(item.get("generated_at") or "") for item in datasets), default=""),
        datasets=datasets,
    )
    (output_root_path / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return {
        "normalized_root": str(normalized_root_path),
        "output_root": str(output_root_path),
        "dataset_count": len(datasets),
        "active_dataset_count": sum(1 for item in datasets if item.get("active")),
        "datasets": publish_rows,
    }


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    result = publish_hosted_library(
        normalized_root=args.normalized_root,
        output_root=args.output_root,
        job_state_root=args.job_state_root,
        provider_filters=args.provider,
        analysis_type_filters=args.analysis_type,
        clean=args.clean,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
