"""Normalize Materials Project structures into tooling-only reference-library packages."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.library_ingest.common import (
    BUILD_ROOT,
    ChunkedPackageEmitter,
    default_ingest_job_state,
    load_ingest_job_state,
    provider_output_root,
    read_json_records,
    save_ingest_job_state,
    today_version_token,
    utcnow_iso,
)
from tools.library_ingest.providers import (
    XRDPatternOptions,
    fetch_materials_project_records,
    normalize_materials_project_record,
    provider_metadata,
)


def _read_ids(path: str | Path | None) -> list[str]:
    if not path:
        return []
    return [line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize Materials Project structures into intermediate package_spec.json + entries.jsonl outputs.")
    parser.add_argument("--input-json", help="Recorded Materials Project JSON fixture with material_id plus structure or structure_cif fields.")
    parser.add_argument("--material-id", action="append", default=[], help="Materials Project material id to fetch live via the mp-api client.")
    parser.add_argument("--material-ids-file", help="Text file containing one Materials Project material id per line.")
    parser.add_argument("--api-key", help="Materials Project API key. Falls back to MP_API_KEY if omitted.")
    parser.add_argument("--output-root", default=str(BUILD_ROOT), help="Normalized output root. Provider packages are written beneath this directory.")
    parser.add_argument("--generated-at", default=utcnow_iso(), help="ISO-8601 generation timestamp for emitted packages.")
    parser.add_argument("--provider-dataset-version", default=today_version_token(), help="Version token recorded in package_spec.json.")
    parser.add_argument("--chunk-size", type=int, default=500, help="Maximum entries per emitted normalized package.")
    parser.add_argument("--resume", action="store_true", help="Resume from the persisted ingest job checkpoint for this provider/version.")
    parser.add_argument("--job-state-root", help="Override build/reference_library_jobs storage location.")
    parser.add_argument("--wavelength-angstrom", type=float, default=1.5406, help="X-ray wavelength used to calculate powder patterns.")
    parser.add_argument("--two-theta-min", type=float, default=5.0, help="Lower two-theta bound for emitted peaks.")
    parser.add_argument("--two-theta-max", type=float, default=90.0, help="Upper two-theta bound for emitted peaks.")
    parser.add_argument("--min-relative-intensity", type=float, default=0.01, help="Discard peaks below this normalized intensity threshold.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    records: list[dict] = []
    if args.input_json:
        records.extend(read_json_records(args.input_json))

    requested_ids = [*args.material_id, *_read_ids(args.material_ids_file)]
    api_key = (args.api_key or os.getenv("MP_API_KEY") or "").strip()
    if requested_ids:
        if not api_key:
            raise SystemExit("Materials Project live ingest requires --api-key or MP_API_KEY.")
        records.extend(fetch_materials_project_records(api_key=api_key, material_ids=requested_ids))

    if not records:
        raise SystemExit("Provide --input-json or at least one --material-id.")

    options = XRDPatternOptions(
        wavelength_angstrom=float(args.wavelength_angstrom),
        two_theta_min=float(args.two_theta_min),
        two_theta_max=float(args.two_theta_max),
        min_relative_intensity=float(args.min_relative_intensity),
    )
    provider_id = "materials_project"
    provider = provider_metadata(provider_id)
    provider_root = provider_output_root(args.output_root, provider_id)
    state_path, state = load_ingest_job_state(
        provider_id,
        args.provider_dataset_version,
        job_state_root=args.job_state_root,
    )
    if not args.resume:
        shutil.rmtree(provider_root, ignore_errors=True)
        state = default_ingest_job_state(provider_id, args.provider_dataset_version)
    ordered_records = sorted(records, key=lambda item: str(item.get("material_id") or item.get("source_id") or item.get("id") or ""))
    emitters: dict[str, ChunkedPackageEmitter] = {}

    def emitter_for(analysis_type: str) -> ChunkedPackageEmitter:
        token = str(analysis_type or "").upper()
        emitter = emitters.get(token)
        if emitter is None:
            emitter = ChunkedPackageEmitter(
                output_root=provider_root,
                package_prefix=f"{provider_id}_{token.lower()}",
                analysis_type=token,
                provider_name=str(provider.get("provider_name") or provider_id),
                source_url=str(provider.get("source_url") or ""),
                license_name=str(provider.get("license_name") or ""),
                license_text=str(provider.get("license_text") or ""),
                attribution=str(provider.get("attribution") or ""),
                priority=int(provider.get("priority") or 0),
                generated_at=args.generated_at,
                provider_dataset_version=args.provider_dataset_version,
                chunk_size=int(args.chunk_size),
                next_chunk_index=int((state.get("next_chunk_index_by_analysis_type") or {}).get(token) or 1),
                initial_buffer=list((state.get("pending_entries_by_analysis_type") or {}).get(token) or []),
            )
            emitters[token] = emitter
        return emitter

    for index in range(int(state.get("cursor") or 0), len(ordered_records)):
        record = ordered_records[index]
        try:
            entry = normalize_materials_project_record(
                record,
                generated_at=args.generated_at,
                provider_dataset_version=args.provider_dataset_version,
                options=options,
            )
            emitter = emitter_for("XRD")
            emitted_ids = [package_id for package_id in emitter.append(entry) if package_id]
            if emitted_ids:
                state["emitted_package_ids"] = [*state.get("emitted_package_ids", []), *emitted_ids]
            state["processed_count"] = int(state.get("processed_count") or 0) + 1
            state["last_successful_ingest_at"] = utcnow_iso()
            state.setdefault("pending_entries_by_analysis_type", {})["XRD"] = [dict(item) for item in emitter.buffer]
            state.setdefault("next_chunk_index_by_analysis_type", {})["XRD"] = emitter.next_chunk_index
        except Exception as exc:
            state["failed_count"] = int(state.get("failed_count") or 0) + 1
            sampled = list(state.get("sampled_failures") or [])
            if len(sampled) < 20:
                sampled.append(
                    {
                        "cursor": index,
                        "source_id": str(record.get("material_id") or record.get("source_id") or record.get("id") or ""),
                        "message": str(exc),
                    }
                )
            state["sampled_failures"] = sampled
        finally:
            state["cursor"] = index + 1
            save_ingest_job_state(state_path, state)

    for analysis_type, emitter in emitters.items():
        emitted_ids = [package_id for package_id in emitter.close() if package_id]
        if emitted_ids:
            state["emitted_package_ids"] = [*state.get("emitted_package_ids", []), *emitted_ids]
        state.setdefault("pending_entries_by_analysis_type", {})[analysis_type] = [dict(item) for item in emitter.buffer]
        state.setdefault("next_chunk_index_by_analysis_type", {})[analysis_type] = emitter.next_chunk_index

    state["completed"] = True
    state["completed_at"] = utcnow_iso()
    save_ingest_job_state(state_path, state)
    print(
        json.dumps(
            {
                "provider": provider_id,
                "package_ids": state.get("emitted_package_ids", []),
                "processed_count": int(state.get("processed_count") or 0),
                "failed_count": int(state.get("failed_count") or 0),
                "state_path": str(state_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
