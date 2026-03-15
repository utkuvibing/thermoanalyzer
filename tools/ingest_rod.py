"""Normalize ROD spectral records into tooling-only reference-library packages."""

from __future__ import annotations

import argparse
import json
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
from tools.library_ingest.providers import normalize_rod_record, provider_metadata


def _read_ids(path: str | Path | None) -> list[str]:
    if not path:
        return []
    return [line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize ROD records into intermediate package_spec.json + entries.jsonl outputs.")
    parser.add_argument("--manifest", help="JSON/JSONL file containing ROD records with source_id and optional jcamp_path/jcamp_url/jcamp.")
    parser.add_argument("--source-id", action="append", default=[], help="ROD source id to fetch via the default JCAMP URL template.")
    parser.add_argument("--source-ids-file", help="Text file containing one ROD source id per line.")
    parser.add_argument("--analysis-type", default="RAMAN", help="Spectral modality recorded in emitted package specs.")
    parser.add_argument("--invert-signal", action="store_true", help="Invert spectral intensity before normalization.")
    parser.add_argument("--output-root", default=str(BUILD_ROOT), help="Normalized output root. Provider packages are written beneath this directory.")
    parser.add_argument("--generated-at", default=utcnow_iso(), help="ISO-8601 generation timestamp for emitted packages.")
    parser.add_argument("--provider-dataset-version", default=today_version_token(), help="Version token recorded in package_spec.json.")
    parser.add_argument("--chunk-size", type=int, default=1000, help="Maximum entries per emitted normalized package.")
    parser.add_argument("--resume", action="store_true", help="Resume from the persisted ingest job checkpoint for this provider/version.")
    parser.add_argument("--job-state-root", help="Override build/reference_library_jobs storage location.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    records: list[dict] = []
    if args.manifest:
        records.extend(read_json_records(args.manifest))
    records.extend({"source_id": source_id} for source_id in [*args.source_id, *_read_ids(args.source_ids_file)])
    if not records:
        raise SystemExit("Provide --manifest or at least one --source-id.")

    provider_id = "rod"
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
    ordered_records = sorted(records, key=lambda item: str(item.get("source_id") or item.get("id") or ""))
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
            analysis_type, entry = normalize_rod_record(
                record,
                generated_at=args.generated_at,
                provider_dataset_version=args.provider_dataset_version,
                default_analysis_type=args.analysis_type,
                invert_signal=bool(args.invert_signal),
            )
            emitter = emitter_for(analysis_type)
            emitted_ids = [package_id for package_id in emitter.append(entry) if package_id]
            if emitted_ids:
                state["emitted_package_ids"] = [*state.get("emitted_package_ids", []), *emitted_ids]
            state["processed_count"] = int(state.get("processed_count") or 0) + 1
            state["last_successful_ingest_at"] = utcnow_iso()
            state.setdefault("pending_entries_by_analysis_type", {})[analysis_type] = [dict(item) for item in emitter.buffer]
            state.setdefault("next_chunk_index_by_analysis_type", {})[analysis_type] = emitter.next_chunk_index
        except Exception as exc:
            state["failed_count"] = int(state.get("failed_count") or 0) + 1
            sampled = list(state.get("sampled_failures") or [])
            if len(sampled) < 20:
                sampled.append(
                    {
                        "cursor": index,
                        "source_id": str(record.get("source_id") or record.get("id") or ""),
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
