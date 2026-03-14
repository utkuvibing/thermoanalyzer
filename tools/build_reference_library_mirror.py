"""Build a curated reference-library mirror from normalized source specs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.reference_library import build_reference_library_package


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build ThermoAnalyzer reference-library mirror packages.")
    parser.add_argument(
        "--source",
        default=str(Path("sample_data") / "reference_library_seed.json"),
        help="Path to the normalized seed/source JSON file.",
    )
    parser.add_argument(
        "--output",
        default=str(Path("sample_data") / "reference_library_mirror"),
        help="Destination directory for the generated mirror.",
    )
    return parser.parse_args()


def _manifest_etag(payload: dict) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def main() -> None:
    args = _parse_args()
    source_path = Path(args.source).resolve()
    output_root = Path(args.output).resolve()
    seed = json.loads(source_path.read_text(encoding="utf-8"))

    output_root.mkdir(parents=True, exist_ok=True)
    packages_root = output_root / "packages"
    packages_root.mkdir(parents=True, exist_ok=True)

    provider_rows: dict[str, dict] = {}
    manifest_packages: list[dict] = []
    for package in seed.get("packages") or []:
        package_id = str(package.get("package_id") or "").strip()
        version = str(package.get("version") or "").strip()
        archive_name = f"{package_id}-{version}.zip"
        archive_path = packages_root / archive_name
        sha256 = build_reference_library_package(
            output_path=archive_path,
            package_metadata={
                "package_id": package_id,
                "analysis_type": package.get("analysis_type"),
                "provider": package.get("provider"),
                "version": version,
                "source_url": package.get("source_url") or "",
                "license_name": package.get("license_name") or "",
                "license_text": package.get("license_text") or "",
                "attribution": package.get("attribution") or "",
                "priority": package.get("priority") or 0,
                "published_at": package.get("published_at") or seed.get("generated_at") or "",
            },
            entries=package.get("entries") or [],
        )
        provider_name = str(package.get("provider") or "").strip()
        provider_key = provider_name.lower().replace(" ", "_")
        provider = provider_rows.setdefault(
            provider_key,
            {
                "provider_id": provider_key,
                "name": provider_name,
                "modalities": [],
                "source_url": package.get("source_url") or "",
                "license_name": package.get("license_name") or "",
                "license_text": package.get("license_text") or "",
                "attribution": package.get("attribution") or "",
            },
        )
        analysis_type = str(package.get("analysis_type") or "").upper()
        if analysis_type and analysis_type not in provider["modalities"]:
            provider["modalities"].append(analysis_type)
        manifest_packages.append(
            {
                "package_id": package_id,
                "analysis_type": package.get("analysis_type"),
                "provider": package.get("provider"),
                "version": version,
                "archive_name": archive_name,
                "sha256": sha256,
                "entry_count": len(package.get("entries") or []),
                "source_url": package.get("source_url") or "",
                "license_name": package.get("license_name") or "",
                "license_text": package.get("license_text") or "",
                "attribution": package.get("attribution") or "",
                "priority": package.get("priority") or 0,
                "published_at": package.get("published_at") or seed.get("generated_at") or "",
            }
        )

    manifest = {
        "schema_version": 1,
        "generated_at": seed.get("generated_at"),
        "providers": sorted(provider_rows.values(), key=lambda item: item["name"].lower()),
        "packages": manifest_packages,
    }
    manifest["etag"] = _manifest_etag(manifest)
    (output_root / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
