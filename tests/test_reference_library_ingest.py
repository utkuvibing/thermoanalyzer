from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.hosted_library import HostedLibraryCatalog, ensure_local_dev_hosted_catalog
from tools.build_reference_library_mirror import main as build_mirror_main
from tools.ingest_cod import main as ingest_cod_main
from tools.ingest_materials_project import main as ingest_materials_project_main
from tools.ingest_openspecy import main as ingest_openspecy_main
from tools.ingest_rod import main as ingest_rod_main
from tools.publish_hosted_library import main as publish_hosted_main
from tools.library_ingest.providers import normalize_openspecy_record

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "reference_library_ingest"
GENERATED_AT = "2026-03-14T00:00:00Z"
DATASET_VERSION = "2026.03.fixture"


def _write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.mark.usefixtures("tmp_path")
def test_cod_ingest_normalizes_cif_records(tmp_path):
    pytest.importorskip("pymatgen")
    manifest_path = _write_json(
        tmp_path / "cod_records.json",
        [
            {
                "source_id": "1002",
                "candidate_name": "Sodium Chloride",
                "formula": "NaCl",
                "cif_path": str(FIXTURE_ROOT / "cod" / "cod_nacl.cif"),
            },
            {
                "source_id": "1001",
                "candidate_name": "Silicon",
                "formula": "Si",
                "cif_path": str(FIXTURE_ROOT / "cod" / "cod_si.cif"),
            },
        ],
    )
    output_root = tmp_path / "reference_library_ingest"

    ingest_cod_main(
        [
            "--manifest",
            str(manifest_path),
            "--output-root",
            str(output_root),
            "--generated-at",
            GENERATED_AT,
            "--provider-dataset-version",
            DATASET_VERSION,
            "--chunk-size",
            "1",
        ]
    )

    provider_root = output_root / "cod"
    package_dirs = sorted(path for path in provider_root.iterdir() if path.is_dir())
    assert [path.name for path in package_dirs] == ["cod_xrd_0001", "cod_xrd_0002"]

    spec = _read_json(package_dirs[0] / "package_spec.json")
    assert spec["analysis_type"] == "XRD"
    assert spec["provider"] == "COD"
    assert spec["version"] == f"{DATASET_VERSION}-b1"

    rows = _read_jsonl(package_dirs[0] / "entries.jsonl")
    assert len(rows) == 1
    assert rows[0]["source_id"] == "1001"
    assert rows[0]["candidate_name"] == "Silicon"
    assert rows[0]["peaks"]
    assert all("d_spacing" in peak for peak in rows[0]["peaks"])


@pytest.mark.usefixtures("tmp_path")
def test_materials_project_ingest_normalizes_fixture_records(tmp_path):
    pytest.importorskip("pymatgen")
    fixture_path = _write_json(
        tmp_path / "materials_project_records.json",
        [
            {
                "material_id": "mp-22862",
                "formula_pretty": "NaCl",
                "structure_cif_path": str(FIXTURE_ROOT / "materials_project" / "mp_22862_nacl.cif"),
                "last_updated": "2026-03-10T00:00:00Z",
            },
            {
                "material_id": "mp-149",
                "formula_pretty": "Si",
                "structure_cif_path": str(FIXTURE_ROOT / "materials_project" / "mp_149_si.cif"),
                "last_updated": "2026-03-11T00:00:00Z",
            },
        ],
    )
    output_root = tmp_path / "reference_library_ingest"

    ingest_materials_project_main(
        [
            "--input-json",
            str(fixture_path),
            "--output-root",
            str(output_root),
            "--generated-at",
            GENERATED_AT,
            "--provider-dataset-version",
            DATASET_VERSION,
            "--chunk-size",
            "1",
        ]
    )

    provider_root = output_root / "materials_project"
    package_dirs = sorted(path for path in provider_root.iterdir() if path.is_dir())
    assert [path.name for path in package_dirs] == ["materials_project_xrd_0001", "materials_project_xrd_0002"]

    rows = _read_jsonl(package_dirs[0] / "entries.jsonl")
    assert len(rows) == 1
    assert rows[0]["source_id"] == "mp-149"
    assert rows[0]["candidate_id"] == "materials_project_mp_149"
    assert rows[0]["formula"] == "Si"
    assert rows[0]["source_url"].endswith("/materials/mp-149")


def test_openspecy_ingest_splits_modalities_and_normalizes_signals(tmp_path):
    output_root = tmp_path / "reference_library_ingest"

    ingest_openspecy_main(
        [
            "--input-json",
            str(FIXTURE_ROOT / "openspecy" / "records.json"),
            "--output-root",
            str(output_root),
            "--generated-at",
            GENERATED_AT,
            "--provider-dataset-version",
            DATASET_VERSION,
            "--chunk-size",
            "2",
        ]
    )

    provider_root = output_root / "openspecy"
    package_dirs = sorted(path for path in provider_root.iterdir() if path.is_dir())
    assert [path.name for path in package_dirs] == ["openspecy_ftir_0001", "openspecy_raman_0001"]

    ftir_rows = _read_jsonl(provider_root / "openspecy_ftir_0001" / "entries.jsonl")
    assert [row["source_id"] for row in ftir_rows] == ["ftir-001", "ftir-002"]
    assert ftir_rows[0]["axis"] == sorted(ftir_rows[0]["axis"])
    assert min(ftir_rows[0]["signal"]) == 0.0
    assert max(ftir_rows[0]["signal"]) == 1.0

    raman_rows = _read_jsonl(provider_root / "openspecy_raman_0001" / "entries.jsonl")
    assert len(raman_rows) == 1
    assert raman_rows[0]["candidate_name"] == "Graphite"


def test_rod_ingest_normalizes_jcamp_fixture(tmp_path):
    manifest_path = _write_json(
        tmp_path / "rod_records.json",
        [
            {
                "source_id": "2001",
                "candidate_name": "Calcite",
                "jcamp_path": str(FIXTURE_ROOT / "rod" / "calcite_2001.jdx"),
            }
        ],
    )
    output_root = tmp_path / "reference_library_ingest"

    ingest_rod_main(
        [
            "--manifest",
            str(manifest_path),
            "--output-root",
            str(output_root),
            "--generated-at",
            GENERATED_AT,
            "--provider-dataset-version",
            DATASET_VERSION,
        ]
    )

    package_dir = output_root / "rod" / "rod_raman_0001"
    spec = _read_json(package_dir / "package_spec.json")
    rows = _read_jsonl(package_dir / "entries.jsonl")

    assert spec["analysis_type"] == "RAMAN"
    assert rows[0]["candidate_name"] == "Calcite"
    assert rows[0]["axis"] == [100.0, 200.0, 300.0, 400.0, 500.0]
    assert rows[0]["signal"][2] == 1.0
    assert rows[0]["source_url"].endswith("2001.rod")


@pytest.mark.usefixtures("tmp_path")
def test_mirror_builder_consumes_normalized_root_before_legacy_source(tmp_path):
    pytest.importorskip("pymatgen")
    normalized_root = tmp_path / "reference_library_ingest"

    ingest_cod_main(
        [
            "--manifest",
            str(
                _write_json(
                    tmp_path / "cod_records.json",
                    [
                        {
                            "source_id": "1001",
                            "candidate_name": "Silicon",
                            "cif_path": str(FIXTURE_ROOT / "cod" / "cod_si.cif"),
                        },
                        {
                            "source_id": "1002",
                            "candidate_name": "Sodium Chloride",
                            "cif_path": str(FIXTURE_ROOT / "cod" / "cod_nacl.cif"),
                        },
                    ],
                )
            ),
            "--output-root",
            str(normalized_root),
            "--generated-at",
            GENERATED_AT,
            "--provider-dataset-version",
            DATASET_VERSION,
            "--chunk-size",
            "1",
        ]
    )
    ingest_materials_project_main(
        [
            "--input-json",
            str(
                _write_json(
                    tmp_path / "mp_records.json",
                    [
                        {
                            "material_id": "mp-149",
                            "formula_pretty": "Si",
                            "structure_cif_path": str(FIXTURE_ROOT / "materials_project" / "mp_149_si.cif"),
                        },
                        {
                            "material_id": "mp-22862",
                            "formula_pretty": "NaCl",
                            "structure_cif_path": str(FIXTURE_ROOT / "materials_project" / "mp_22862_nacl.cif"),
                        },
                    ],
                )
            ),
            "--output-root",
            str(normalized_root),
            "--generated-at",
            GENERATED_AT,
            "--provider-dataset-version",
            DATASET_VERSION,
            "--chunk-size",
            "1",
        ]
    )
    ingest_openspecy_main(
        [
            "--input-json",
            str(FIXTURE_ROOT / "openspecy" / "records.json"),
            "--output-root",
            str(normalized_root),
            "--generated-at",
            GENERATED_AT,
            "--provider-dataset-version",
            DATASET_VERSION,
            "--chunk-size",
            "2",
        ]
    )
    ingest_rod_main(
        [
            "--manifest",
            str(
                _write_json(
                    tmp_path / "rod_records.json",
                    [
                        {
                            "source_id": "2001",
                            "candidate_name": "Calcite",
                            "jcamp_path": str(FIXTURE_ROOT / "rod" / "calcite_2001.jdx"),
                        }
                    ],
                )
            ),
            "--output-root",
            str(normalized_root),
            "--generated-at",
            GENERATED_AT,
            "--provider-dataset-version",
            DATASET_VERSION,
        ]
    )

    mirror_root = tmp_path / "mirror"
    build_mirror_main(
        [
            "--normalized-root",
            str(normalized_root),
            "--source",
            str(FIXTURE_ROOT / "legacy_seed.json"),
            "--output",
            str(mirror_root),
        ]
    )

    manifest = _read_json(mirror_root / "manifest.json")
    assert {provider["name"] for provider in manifest["providers"]} == {"COD", "Materials Project", "OpenSpecy", "ROD"}
    assert len(manifest["packages"]) == 7
    assert {package["package_id"] for package in manifest["packages"]} >= {
        "cod_xrd_0001",
        "materials_project_xrd_0001",
        "openspecy_ftir_0001",
        "openspecy_raman_0001",
        "rod_raman_0001",
    }
    assert all((mirror_root / "packages" / package["archive_name"]).exists() for package in manifest["packages"])
    assert "legacy_ftir_fixture" not in {package["package_id"] for package in manifest["packages"]}


def test_mirror_builder_falls_back_to_legacy_seed_when_normalized_root_is_empty(tmp_path):
    mirror_root = tmp_path / "mirror"
    build_mirror_main(
        [
            "--normalized-root",
            str(tmp_path / "missing-normalized-root"),
            "--source",
            str(FIXTURE_ROOT / "legacy_seed.json"),
            "--output",
            str(mirror_root),
        ]
    )

    manifest = _read_json(mirror_root / "manifest.json")
    assert [package["package_id"] for package in manifest["packages"]] == ["legacy_ftir_fixture"]
    assert (mirror_root / "packages" / "legacy_ftir_fixture-2026.03.fixture.zip").exists()


def test_openspecy_ingest_resume_uses_job_state_pending_buffer(tmp_path):
    output_root = tmp_path / "reference_library_ingest"
    state_root = tmp_path / "reference_library_jobs"
    records = _read_json(FIXTURE_ROOT / "openspecy" / "records.json")
    _, first_entry = normalize_openspecy_record(
        records[0],
        generated_at=GENERATED_AT,
        provider_dataset_version=DATASET_VERSION,
    )
    state_path = state_root / "openspecy" / f"{DATASET_VERSION.replace('.', '_')}.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "provider_id": "openspecy",
                "provider_dataset_version": DATASET_VERSION,
                "cursor": 1,
                "processed_count": 1,
                "failed_count": 0,
                "last_successful_ingest_at": GENERATED_AT,
                "sampled_failures": [],
                "next_chunk_index_by_analysis_type": {"FTIR": 1},
                "pending_entries_by_analysis_type": {"FTIR": [first_entry]},
                "emitted_package_ids": [],
                "completed": False,
                "completed_at": "",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    ingest_openspecy_main(
        [
            "--input-json",
            str(FIXTURE_ROOT / "openspecy" / "records.json"),
            "--output-root",
            str(output_root),
            "--generated-at",
            GENERATED_AT,
            "--provider-dataset-version",
            DATASET_VERSION,
            "--chunk-size",
            "2",
            "--resume",
            "--job-state-root",
            str(state_root),
        ]
    )

    ftir_rows = _read_jsonl(output_root / "openspecy" / "openspecy_ftir_0001" / "entries.jsonl")
    assert [row["source_id"] for row in ftir_rows] == ["ftir-001", "ftir-002"]
    state = _read_json(state_path)
    assert state["processed_count"] == 3
    assert state["pending_entries_by_analysis_type"]["FTIR"] == []
    assert state["completed"] is True


@pytest.mark.usefixtures("tmp_path")
def test_publish_hosted_library_builds_hosted_manifest_and_coverage(tmp_path):
    pytest.importorskip("pymatgen")
    normalized_root = tmp_path / "reference_library_ingest"
    job_state_root = tmp_path / "reference_library_jobs"

    ingest_cod_main(
        [
            "--manifest",
            str(
                _write_json(
                    tmp_path / "cod_records.json",
                    [
                        {
                            "source_id": "1001",
                            "candidate_name": "Silicon",
                            "cif_path": str(FIXTURE_ROOT / "cod" / "cod_si.cif"),
                        },
                        {
                            "source_id": "1002",
                            "candidate_name": "Sodium Chloride",
                            "cif_path": str(FIXTURE_ROOT / "cod" / "cod_nacl.cif"),
                        },
                    ],
                )
            ),
            "--output-root",
            str(normalized_root),
            "--generated-at",
            GENERATED_AT,
            "--provider-dataset-version",
            DATASET_VERSION,
            "--job-state-root",
            str(job_state_root),
        ]
    )
    ingest_materials_project_main(
        [
            "--input-json",
            str(
                _write_json(
                    tmp_path / "mp_records.json",
                    [
                        {
                            "material_id": "mp-149",
                            "formula_pretty": "Si",
                            "structure_cif_path": str(FIXTURE_ROOT / "materials_project" / "mp_149_si.cif"),
                        },
                        {
                            "material_id": "mp-22862",
                            "formula_pretty": "NaCl",
                            "structure_cif_path": str(FIXTURE_ROOT / "materials_project" / "mp_22862_nacl.cif"),
                        },
                    ],
                )
            ),
            "--output-root",
            str(normalized_root),
            "--generated-at",
            GENERATED_AT,
            "--provider-dataset-version",
            DATASET_VERSION,
            "--job-state-root",
            str(job_state_root),
        ]
    )
    ingest_openspecy_main(
        [
            "--input-json",
            str(FIXTURE_ROOT / "openspecy" / "records.json"),
            "--output-root",
            str(normalized_root),
            "--generated-at",
            GENERATED_AT,
            "--provider-dataset-version",
            DATASET_VERSION,
            "--job-state-root",
            str(job_state_root),
        ]
    )
    ingest_rod_main(
        [
            "--manifest",
            str(
                _write_json(
                    tmp_path / "rod_records.json",
                    [
                        {
                            "source_id": "2001",
                            "candidate_name": "Calcite",
                            "jcamp_path": str(FIXTURE_ROOT / "rod" / "calcite_2001.jdx"),
                        }
                    ],
                )
            ),
            "--output-root",
            str(normalized_root),
            "--generated-at",
            GENERATED_AT,
            "--provider-dataset-version",
            DATASET_VERSION,
            "--job-state-root",
            str(job_state_root),
        ]
    )

    hosted_root = tmp_path / "reference_library_hosted"
    publish_hosted_main(
        [
            "--normalized-root",
            str(normalized_root),
            "--output-root",
            str(hosted_root),
            "--job-state-root",
            str(job_state_root),
        ]
    )

    manifest = _read_json(hosted_root / "manifest.json")
    assert len(manifest["datasets"]) == 5
    assert sum(1 for item in manifest["datasets"] if item["active"]) == 5
    catalog = HostedLibraryCatalog(hosted_root)
    coverage = catalog.coverage()
    assert coverage["FTIR"]["total_candidate_count"] == 2
    assert coverage["FTIR"]["providers"]["openspecy"]["dataset_version"] == DATASET_VERSION
    assert coverage["RAMAN"]["total_candidate_count"] == 2
    assert set(coverage["RAMAN"]["providers"]) == {"openspecy", "rod"}
    assert coverage["XRD"]["total_candidate_count"] == 4
    assert set(coverage["XRD"]["providers"]) == {"cod", "materials_project"}
    assert coverage["XRD"]["coverage_tier"] == "seed_dev"
    assert coverage["XRD"]["coverage_warning_code"] == "xrd_seed_coverage_only"
    raman_entries = catalog.load_entries("RAMAN")
    assert raman_entries[0]["package_version"] == DATASET_VERSION
    assert raman_entries[0]["provider_dataset_version"] == DATASET_VERSION
    assert raman_entries[0]["canonical_material_key"]


def test_publish_hosted_library_uses_expanded_local_dev_xrd_corpus(tmp_path):
    normalized_root = Path(__file__).resolve().parents[1] / "sample_data" / "reference_library_ingest_cloud_dev"
    hosted_root = tmp_path / "reference_library_hosted"

    publish_hosted_main(
        [
            "--normalized-root",
            str(normalized_root),
            "--output-root",
            str(hosted_root),
        ]
    )

    coverage = HostedLibraryCatalog(hosted_root).coverage()
    assert coverage["XRD"]["total_candidate_count"] == 29
    assert coverage["XRD"]["providers"]["cod"]["candidate_count"] == 27
    assert coverage["XRD"]["providers"]["materials_project"]["candidate_count"] == 2
    assert coverage["XRD"]["coverage_tier"] == "expanded"
    assert coverage["XRD"]["coverage_warning_code"] == ""


def test_publish_hosted_library_defaults_to_expanded_local_dev_xrd_corpus(tmp_path):
    hosted_root = tmp_path / "reference_library_hosted"

    publish_hosted_main(
        [
            "--output-root",
            str(hosted_root),
        ]
    )

    coverage = HostedLibraryCatalog(hosted_root).coverage()
    assert coverage["XRD"]["total_candidate_count"] == 29
    assert coverage["XRD"]["providers"]["cod"]["candidate_count"] == 27
    assert coverage["XRD"]["providers"]["materials_project"]["candidate_count"] == 2
    assert coverage["XRD"]["coverage_tier"] == "expanded"
    assert coverage["XRD"]["coverage_warning_code"] == ""


def test_ensure_local_dev_upgrades_stale_seed_manifest_to_expanded(tmp_path):
    """When a seed-sized hosted manifest exists but a richer normalized root is
    available, ensure_local_dev_hosted_catalog should detect the upgrade
    opportunity and republish with the expanded corpus."""
    normalized_root = Path(__file__).resolve().parents[1] / "sample_data" / "reference_library_ingest_cloud_dev"
    hosted_root = tmp_path / "reference_library_hosted"
    hosted_root.mkdir(parents=True, exist_ok=True)

    # Create a minimal seed manifest with only 6 XRD entries
    seed_manifest = {
        "version": "1.0",
        "datasets": [
            {
                "dataset_id": "xrd_cod_seed",
                "modality": "XRD",
                "provider_id": "cod",
                "candidate_count": 4,
                "active": True,
            },
            {
                "dataset_id": "xrd_mp_seed",
                "modality": "XRD",
                "provider_id": "materials_project",
                "candidate_count": 2,
                "active": True,
            },
        ],
    }
    (hosted_root / "manifest.json").write_text(
        json.dumps(seed_manifest, indent=2), encoding="utf-8"
    )

    result = ensure_local_dev_hosted_catalog(
        hosted_root=hosted_root,
        normalized_root=normalized_root,
        dev_mode=True,
    )

    assert result["state"] == "upgraded"
    assert result["previous_coverage_tier"] == "seed_dev"
    assert result["previous_xrd_count"] == 6
    assert result["new_coverage_tier"] == "expanded"
    assert result["new_xrd_count"] == 29
    assert "stale_" in result.get("upgrade_reason", "")

    coverage = HostedLibraryCatalog(hosted_root).coverage()
    assert coverage["XRD"]["total_candidate_count"] == 29
    assert coverage["XRD"]["coverage_tier"] == "expanded"


def test_hosted_catalog_refresh_reloads_expanded_xrd_corpus_after_republish(tmp_path):
    seed_root = Path(__file__).resolve().parents[1] / "build" / "reference_library_ingest_live"
    expanded_root = Path(__file__).resolve().parents[1] / "sample_data" / "reference_library_ingest_cloud_dev"
    hosted_root = tmp_path / "reference_library_hosted"

    publish_hosted_main(
        [
            "--normalized-root",
            str(seed_root),
            "--output-root",
            str(hosted_root),
            "--clean",
        ]
    )
    catalog = HostedLibraryCatalog(hosted_root)
    assert catalog.coverage()["XRD"]["total_candidate_count"] == 6
    assert catalog.coverage()["XRD"]["coverage_tier"] == "seed_dev"

    publish_hosted_main(
        [
            "--normalized-root",
            str(expanded_root),
            "--output-root",
            str(hosted_root),
            "--clean",
        ]
    )

    refreshed_manifest = catalog.refresh()
    assert refreshed_manifest["datasets"]
    refreshed_coverage = catalog.coverage()["XRD"]
    assert refreshed_coverage["total_candidate_count"] == 29
    assert refreshed_coverage["providers"]["cod"]["candidate_count"] == 27
    assert refreshed_coverage["providers"]["materials_project"]["candidate_count"] == 2
    assert refreshed_coverage["coverage_tier"] == "expanded"
