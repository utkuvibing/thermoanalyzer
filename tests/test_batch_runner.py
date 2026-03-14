from __future__ import annotations

import io
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from core.batch_runner import (
    _match_xrd_reference_peaks,
    execute_batch_template,
    filter_batch_summary_rows,
    normalize_batch_summary_rows,
    summarize_batch_outcomes,
)
from core.data_io import ThermalDataset, read_thermal_data
from core.processing_schema import set_tga_unit_mode
from core.reference_library import build_reference_library_package, get_reference_library_manager


def _manifest_etag(payload: dict) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _make_tga_dataset(temperature_range, tga_signal, *, signal_unit="%"):
    return ThermalDataset(
        data=pd.DataFrame({"temperature": temperature_range, "signal": tga_signal}),
        metadata={
            "sample_name": "SyntheticTGA",
            "sample_mass": 10.0,
            "heating_rate": 20.0,
            "instrument": "TestInstrument",
            "vendor": "TestVendor",
            "display_name": "Synthetic TGA Run",
            "atmosphere": "Nitrogen",
            "atmosphere_status": "verified",
            "source_data_hash": "synthetic-tga-hash",
        },
        data_type="TGA",
        units={"temperature": "degC", "signal": signal_unit},
        original_columns={"temperature": "temperature", "signal": "signal"},
        file_path="",
    )


def _make_dta_dataset(thermal_dataset):
    dataset = thermal_dataset.copy()
    dataset.data_type = "DTA"
    dataset.units["signal"] = "uV"
    dataset.metadata.update(
        {
            "sample_name": "SyntheticDTA",
            "display_name": "Synthetic DTA Run",
            "vendor": "TestVendor",
            "instrument": "TestInstrument",
        }
    )
    return dataset


def _gaussian(axis, center, width, amplitude):
    return amplitude * np.exp(-0.5 * ((axis - center) / width) ** 2)


def _two_theta_from_d_spacing(d_spacing: float, wavelength_angstrom: float) -> float:
    return float(np.degrees(2.0 * np.arcsin(wavelength_angstrom / (2.0 * d_spacing))))


def _make_spectral_dataset(*, analysis_type: str, include_reference_library: bool = True, no_match: bool = False):
    axis = np.linspace(450.0, 1800.0, 420)
    if analysis_type.upper() == "FTIR":
        base = (
            _gaussian(axis, 720.0, 22.0, 0.9)
            + _gaussian(axis, 1115.0, 28.0, 1.3)
            + _gaussian(axis, 1510.0, 24.0, 0.8)
        )
        signal_unit = "a.u."
    else:
        base = (
            _gaussian(axis, 620.0, 18.0, 1.1)
            + _gaussian(axis, 1003.0, 15.0, 1.4)
            + _gaussian(axis, 1585.0, 20.0, 0.95)
        )
        signal_unit = "counts"

    signal = base + 0.02 * np.sin(axis / 45.0)
    metadata = {
        "sample_name": f"Synthetic{analysis_type.upper()}",
        "sample_mass": 1.0,
        "heating_rate": 1.0,
        "instrument": "SpecBench",
        "vendor": "TestVendor",
        "display_name": f"Synthetic {analysis_type.upper()} Spectrum",
        "source_data_hash": f"synthetic-{analysis_type.lower()}-hash",
    }
    if include_reference_library:
        if no_match:
            ref_signal = np.zeros_like(signal)
            metadata["spectral_reference_library"] = [
                {
                    "id": f"{analysis_type.lower()}_mismatch",
                    "name": "Intentional Mismatch",
                    "axis": axis.tolist(),
                    "signal": ref_signal.tolist(),
                }
            ]
        else:
            metadata["spectral_reference_library"] = [
                {
                    "id": f"{analysis_type.lower()}_polymer_a",
                    "name": "Polymer A",
                    "axis": axis.tolist(),
                    "signal": (signal * 0.98 + 0.01).tolist(),
                },
                {
                    "id": f"{analysis_type.lower()}_polymer_b",
                    "name": "Polymer B",
                    "axis": axis.tolist(),
                    "signal": np.roll(signal, 14).tolist(),
                },
            ]

    return ThermalDataset(
        data=pd.DataFrame({"temperature": axis, "signal": signal}),
        metadata=metadata,
        data_type=analysis_type.upper(),
        units={"temperature": "cm^-1", "signal": signal_unit},
        original_columns={"temperature": "wavenumber", "signal": "intensity"},
        file_path="",
    )


def _make_xrd_dataset(*, include_reference_library: bool = True, no_match: bool = False):
    axis = np.linspace(8.0, 88.0, 700)
    baseline = 18.0 + 0.03 * axis
    signal = (
        baseline
        + _gaussian(axis, 18.4, 0.25, 95.0)
        + _gaussian(axis, 33.2, 0.35, 160.0)
        + _gaussian(axis, 47.8, 0.45, 130.0)
        + _gaussian(axis, 63.5, 0.4, 84.0)
        + 0.8 * np.sin(axis / 4.0)
    )
    metadata = {
        "sample_name": "SyntheticXRD",
        "sample_mass": 1.0,
        "heating_rate": 1.0,
        "instrument": "XRDBench",
        "vendor": "TestVendor",
        "display_name": "Synthetic XRD Pattern",
        "source_data_hash": "synthetic-xrd-hash",
        "xrd_axis_role": "two_theta",
        "xrd_axis_unit": "degree_2theta",
        "xrd_wavelength_angstrom": 1.5406,
    }
    if include_reference_library:
        if no_match:
            metadata["xrd_reference_library"] = [
                {
                    "id": "xrd_phase_mismatch_a",
                    "name": "Mismatch A",
                    "peaks": [
                        {"position": 11.2, "intensity": 1.0},
                        {"position": 25.8, "intensity": 0.7},
                        {"position": 42.1, "intensity": 0.9},
                        {"position": 78.6, "intensity": 0.65},
                    ],
                }
            ]
        else:
            metadata["xrd_reference_library"] = [
                {
                    "id": "xrd_phase_alpha",
                    "name": "Phase Alpha",
                    "peaks": [
                        {"position": 18.37, "intensity": 0.62},
                        {"position": 33.18, "intensity": 1.0},
                        {"position": 47.76, "intensity": 0.84},
                        {"position": 63.52, "intensity": 0.51},
                        {"position": 72.05, "intensity": 0.22},
                    ],
                },
                {
                    "id": "xrd_phase_beta",
                    "name": "Phase Beta",
                    "peaks": [
                        {"position": 21.85, "intensity": 0.63},
                        {"position": 35.75, "intensity": 0.95},
                        {"position": 52.45, "intensity": 0.88},
                        {"position": 66.25, "intensity": 0.55},
                    ],
                },
            ]

    return ThermalDataset(
        data=pd.DataFrame({"temperature": axis, "signal": signal}),
        metadata=metadata,
        data_type="XRD",
        units={"temperature": "degree_2theta", "signal": "counts"},
        original_columns={"temperature": "two_theta", "signal": "intensity"},
        file_path="",
    )


def test_execute_dsc_batch_template_saves_normalized_record(thermal_dataset):
    dataset = thermal_dataset.copy()
    dataset.metadata.update(
        {
            "vendor": "TestVendor",
            "display_name": "Synthetic DSC Run",
            "calibration_id": "DSC-CAL-01",
            "calibration_status": "verified",
        }
    )

    outcome = execute_batch_template(
        dataset_key="synthetic_dsc",
        dataset=dataset,
        analysis_type="DSC",
        workflow_template_id="dsc.polymer_tg",
        analysis_history=[{"event_id": "evt-batch-start"}],
        analyst_name="Ada",
        app_version="2.0",
        batch_run_id="batch_dsc_demo",
    )

    assert outcome["status"] == "saved"
    assert outcome["record"]["id"] == "dsc_synthetic_dsc"
    assert outcome["record"]["processing"]["workflow_template_id"] == "dsc.polymer_tg"
    assert outcome["record"]["processing"]["workflow_template_version"] == 1
    assert outcome["record"]["processing"]["method_context"]["batch_run_id"] == "batch_dsc_demo"
    assert outcome["record"]["provenance"]["batch_run_id"] == "batch_dsc_demo"
    assert outcome["record"]["review"]["batch_runner"] == "compare_workspace"
    assert outcome["validation"]["status"] in {"pass", "warn"}
    assert outcome["state"]["processing"]["workflow_template"] == "Polymer Tg"
    assert outcome["state"]["peaks"]
    assert outcome["summary_row"]["execution_status"] == "saved"


def test_execute_tga_batch_template_saves_normalized_record(temperature_range, tga_signal):
    dataset = _make_tga_dataset(temperature_range, tga_signal)

    outcome = execute_batch_template(
        dataset_key="synthetic_tga",
        dataset=dataset,
        analysis_type="TGA",
        workflow_template_id="tga.single_step_decomposition",
        analysis_history=[{"event_id": "evt-batch-start"}],
        analyst_name="Ada",
        app_version="2.0",
        batch_run_id="batch_tga_demo",
    )

    assert outcome["status"] == "saved"
    assert outcome["record"]["id"] == "tga_synthetic_tga"
    assert outcome["record"]["processing"]["workflow_template_id"] == "tga.single_step_decomposition"
    assert outcome["record"]["processing"]["workflow_template_version"] == 1
    assert outcome["record"]["processing"]["method_context"]["batch_run_id"] == "batch_tga_demo"
    assert outcome["record"]["processing"]["method_context"]["tga_unit_mode_declared"] == "auto"
    assert outcome["record"]["processing"]["method_context"]["tga_unit_mode_resolved"] == "percent"
    assert outcome["record"]["processing"]["method_context"]["tga_unit_auto_inference_used"] is True
    assert outcome["record"]["provenance"]["batch_run_id"] == "batch_tga_demo"
    assert outcome["state"]["tga_result"] is not None
    assert outcome["summary_row"]["step_count"] >= 1
    assert outcome["summary_row"]["execution_status"] == "saved"


def test_execute_dta_batch_template_saves_normalized_record_with_general_default(thermal_dataset):
    dataset = _make_dta_dataset(thermal_dataset)

    outcome = execute_batch_template(
        dataset_key="synthetic_dta",
        dataset=dataset,
        analysis_type="DTA",
        workflow_template_id="dta.general",
        analysis_history=[{"event_id": "evt-batch-start"}],
        analyst_name="Ada",
        app_version="2.0",
        batch_run_id="batch_dta_demo",
    )

    assert outcome["status"] == "saved"
    assert outcome["record"]["id"] == "dta_synthetic_dta"
    assert outcome["record"]["processing"]["workflow_template_id"] == "dta.general"
    assert outcome["record"]["processing"]["method_context"]["batch_run_id"] == "batch_dta_demo"
    assert outcome["record"]["provenance"]["batch_run_id"] == "batch_dta_demo"
    assert outcome["record"]["review"]["batch_runner"] == "compare_workspace"
    assert outcome["validation"]["status"] in {"pass", "warn"}
    assert outcome["state"]["processing"]["workflow_template"] == "General DTA"
    assert outcome["summary_row"]["execution_status"] == "saved"


def test_execute_dta_batch_template_honors_thermal_events_override(thermal_dataset):
    dataset = _make_dta_dataset(thermal_dataset)

    outcome = execute_batch_template(
        dataset_key="synthetic_dta",
        dataset=dataset,
        analysis_type="DTA",
        workflow_template_id="dta.thermal_events",
        batch_run_id="batch_dta_events",
    )

    assert outcome["status"] == "saved"
    assert outcome["analysis_type"] == "DTA"
    assert outcome["record"]["processing"]["workflow_template_id"] == "dta.thermal_events"
    assert outcome["record"]["processing"]["workflow_template"] == "Thermal Event Screening"
    assert outcome["summary_row"]["workflow_template_id"] == "dta.thermal_events"


def test_execute_ftir_batch_template_returns_ranked_similarity_matches():
    dataset = _make_spectral_dataset(analysis_type="FTIR")

    outcome = execute_batch_template(
        dataset_key="synthetic_ftir",
        dataset=dataset,
        analysis_type="FTIR",
        workflow_template_id="ftir.general",
        batch_run_id="batch_ftir_demo",
    )

    assert outcome["status"] == "saved"
    assert outcome["record"]["id"] == "ftir_synthetic_ftir"
    assert outcome["record"]["summary"]["match_status"] == "matched"
    assert outcome["record"]["summary"]["top_match_id"] == "ftir_polymer_a"
    assert outcome["record"]["summary"]["confidence_band"] in {"high", "medium", "low"}
    assert outcome["record"]["summary"]["library_result_source"] == "dataset_embedded"
    assert outcome["record"]["summary"]["library_access_mode"] in {"not_configured", "limited_cached_fallback"}
    assert outcome["record"]["summary"]["library_offline_limited_mode"] is True
    assert outcome["record"]["rows"][0]["normalized_score"] >= outcome["record"]["rows"][-1]["normalized_score"]
    assert outcome["record"]["rows"][0]["evidence"]["shared_peak_count"] >= 1
    assert outcome["summary_row"]["match_status"] == "matched"


def test_execute_raman_batch_template_handles_no_match_without_failing():
    dataset = _make_spectral_dataset(analysis_type="RAMAN", no_match=True)

    outcome = execute_batch_template(
        dataset_key="synthetic_raman",
        dataset=dataset,
        analysis_type="RAMAN",
        workflow_template_id="raman.general",
        batch_run_id="batch_raman_demo",
    )

    assert outcome["status"] == "saved"
    assert outcome["record"]["id"] == "raman_synthetic_raman"
    assert outcome["record"]["summary"]["match_status"] == "no_match"
    assert outcome["record"]["summary"]["caution_code"] == "spectral_no_match"
    assert outcome["record"]["review"]["caution"]["code"] == "spectral_no_match"
    assert outcome["summary_row"]["execution_status"] == "saved"
    assert outcome["summary_row"]["match_status"] == "no_match"


def test_execute_ftir_batch_template_similarity_is_deterministic():
    dataset = _make_spectral_dataset(analysis_type="FTIR")

    first = execute_batch_template(
        dataset_key="synthetic_ftir",
        dataset=dataset,
        analysis_type="FTIR",
        workflow_template_id="ftir.general",
        batch_run_id="batch_ftir_first",
    )
    second = execute_batch_template(
        dataset_key="synthetic_ftir",
        dataset=dataset,
        analysis_type="FTIR",
        workflow_template_id="ftir.general",
        batch_run_id="batch_ftir_second",
    )

    first_processing = dict(first["record"]["processing"])
    second_processing = dict(second["record"]["processing"])
    first_context = dict(first_processing["method_context"])
    second_context = dict(second_processing["method_context"])
    first_context.pop("batch_run_id", None)
    second_context.pop("batch_run_id", None)
    first_processing["method_context"] = first_context
    second_processing["method_context"] = second_context

    assert first["status"] == second["status"] == "saved"
    assert first_processing == second_processing
    assert first["record"]["summary"] == second["record"]["summary"]
    assert first["record"]["rows"] == second["record"]["rows"]


def test_execute_xrd_batch_template_returns_ranked_candidate_match_with_confidence_context():
    dataset = _make_xrd_dataset()

    outcome = execute_batch_template(
        dataset_key="synthetic_xrd",
        dataset=dataset,
        analysis_type="XRD",
        workflow_template_id="xrd.general",
        batch_run_id="batch_xrd_demo",
    )

    assert outcome["status"] == "saved"
    assert outcome["record"]["id"] == "xrd_synthetic_xrd"
    assert outcome["record"]["processing"]["workflow_template_id"] == "xrd.general"
    assert outcome["record"]["processing"]["method_context"]["xrd_peak_detection_method"] == "scipy_find_peaks"
    assert outcome["record"]["processing"]["method_context"]["xrd_peak_ranking"] == "prominence_desc_then_position_asc"
    assert outcome["record"]["summary"]["peak_count"] >= 3
    assert outcome["record"]["summary"]["match_status"] == "matched"
    assert outcome["record"]["summary"]["top_phase_id"] == "xrd_phase_alpha"
    assert outcome["record"]["summary"]["top_candidate_id"] == "xrd_phase_alpha"
    assert outcome["record"]["summary"]["top_candidate_name"] == "Phase Alpha"
    assert outcome["record"]["summary"]["top_candidate_score"] == outcome["record"]["summary"]["top_phase_score"]
    assert outcome["record"]["summary"]["library_result_source"] == "dataset_embedded"
    assert outcome["record"]["summary"]["library_offline_limited_mode"] is True
    assert outcome["record"]["summary"]["confidence_band"] in {"high", "medium", "low"}
    assert outcome["summary_row"]["peak_count"] == outcome["record"]["summary"]["peak_count"]
    assert outcome["summary_row"]["execution_status"] == "saved"

    rows = list(outcome["record"]["rows"])
    ranks = [row["rank"] for row in rows]
    assert ranks == sorted(ranks)
    scores = [row["normalized_score"] for row in rows]
    assert scores == sorted(scores, reverse=True)
    assert rows[0]["evidence"]["shared_peak_count"] >= 3
    assert rows[0]["evidence"]["mean_delta_position"] is not None
    assert "unmatched_major_peak_positions" in rows[0]["evidence"]
    assert "matched_peak_pairs" in rows[0]["evidence"]
    assert "unmatched_observed_peaks" in rows[0]["evidence"]
    assert "unmatched_reference_peaks" in rows[0]["evidence"]
    assert rows[0]["evidence"]["matched_peak_pairs"][0]["observed_index"] >= 0
    assert rows[0]["evidence"]["matched_peak_pairs"][0]["reference_index"] >= 0


def test_execute_ftir_batch_template_prefers_cloud_search_when_configured(monkeypatch):
    dataset = _make_spectral_dataset(analysis_type="FTIR")

    class _StubCloudClient:
        configured = True
        last_error = ""

        def search(self, *, analysis_type, payload):
            assert analysis_type == "FTIR"
            return {
                "request_id": "cloud_req_123",
                "analysis_type": "FTIR",
                "match_status": "matched",
                "candidate_count": 1,
                "rows": [
                    {
                        "rank": 1,
                        "candidate_id": "cloud_ref_ftir_1",
                        "candidate_name": "Cloud FTIR Ref",
                        "normalized_score": 0.91,
                        "confidence_band": "high",
                        "library_provider": "openspecy",
                        "library_package": "openspecy_ftir_cloud",
                        "library_version": "2026.03",
                        "evidence": {"shared_peak_count": 4, "peak_overlap_ratio": 0.66},
                    }
                ],
                "caution_code": "",
                "caution_message": "",
                "library_provider": "openspecy",
                "library_package": "openspecy_ftir_cloud",
                "library_version": "2026.03",
                "library_access_mode": "cloud_full_access",
                "library_result_source": "cloud_search",
                "library_provider_scope": ["openspecy"],
                "library_offline_limited_mode": False,
            }

    monkeypatch.setattr("core.batch_runner.get_library_cloud_client", lambda: _StubCloudClient())

    outcome = execute_batch_template(
        dataset_key="synthetic_ftir",
        dataset=dataset,
        analysis_type="FTIR",
        workflow_template_id="ftir.general",
        batch_run_id="batch_ftir_cloud_demo",
    )

    assert outcome["status"] == "saved"
    assert outcome["record"]["summary"]["library_result_source"] == "cloud_search"
    assert outcome["record"]["summary"]["library_access_mode"] == "cloud_full_access"
    assert outcome["record"]["summary"]["library_request_id"] == "cloud_req_123"
    assert outcome["record"]["summary"]["top_match_id"] == "cloud_ref_ftir_1"
    assert outcome["record"]["rows"][0]["library_provider"] == "openspecy"


def test_execute_xrd_batch_template_uses_reference_d_spacing_for_non_cu_wavelength():
    reference_d_spacings = [4.828, 2.698, 1.902, 1.466]
    dataset_wavelength = 1.002
    axis = np.linspace(8.0, 70.0, 700)
    signal = 18.0 + 0.025 * axis
    amplitudes = [95.0, 160.0, 130.0, 84.0]
    for d_spacing, amplitude in zip(reference_d_spacings, amplitudes):
        signal += _gaussian(axis, _two_theta_from_d_spacing(d_spacing, dataset_wavelength), 0.28, amplitude)

    dataset = ThermalDataset(
        data=pd.DataFrame({"temperature": axis, "signal": signal}),
        metadata={
            "sample_name": "ShiftedXRD",
            "display_name": "Shifted XRD Pattern",
            "source_data_hash": "shifted-xrd-hash",
            "xrd_axis_role": "two_theta",
            "xrd_axis_unit": "degree_2theta",
            "xrd_wavelength_angstrom": dataset_wavelength,
            "xrd_reference_library": [
                {
                    "id": "xrd_phase_alpha_shifted",
                    "name": "Phase Alpha Shifted",
                    "peaks": [
                        {
                            "position": _two_theta_from_d_spacing(d_spacing, 1.5406),
                            "d_spacing": d_spacing,
                            "intensity": intensity,
                        }
                        for d_spacing, intensity in zip(reference_d_spacings, [0.62, 1.0, 0.84, 0.51])
                    ],
                },
                {
                    "id": "xrd_phase_beta_shifted",
                    "name": "Phase Beta Shifted",
                    "peaks": [
                        {
                            "position": _two_theta_from_d_spacing(d_spacing, 1.5406),
                            "d_spacing": d_spacing,
                            "intensity": intensity,
                        }
                        for d_spacing, intensity in zip([3.97, 2.51, 1.74, 1.41], [0.63, 0.95, 0.88, 0.55])
                    ],
                },
            ],
        },
        data_type="XRD",
        units={"temperature": "degree_2theta", "signal": "counts"},
        original_columns={"temperature": "two_theta", "signal": "intensity"},
        file_path="",
    )

    outcome = execute_batch_template(
        dataset_key="shifted_xrd",
        dataset=dataset,
        analysis_type="XRD",
        workflow_template_id="xrd.general",
        batch_run_id="batch_xrd_shifted",
    )

    assert outcome["status"] == "saved"
    assert outcome["record"]["summary"]["match_status"] == "matched"
    assert outcome["record"]["summary"]["top_phase_id"] == "xrd_phase_alpha_shifted"
    assert outcome["record"]["summary"]["match_coordinate_space"] == "two_theta"
    assert outcome["record"]["rows"][0]["evidence"]["comparison_space"] == "two_theta"


def test_execute_xrd_batch_template_is_deterministic_for_candidate_match_and_peak_limit_override():
    dataset = _make_xrd_dataset()
    existing_processing = {
        "analysis_type": "XRD",
        "workflow_template_id": "xrd.general",
        "analysis_steps": {
            "peak_detection": {"prominence": 0.14, "distance": 9, "width": 3, "max_peaks": 3},
        },
        "method_context": {
            "xrd_match_top_n": 2,
        },
    }

    first = execute_batch_template(
        dataset_key="synthetic_xrd",
        dataset=dataset,
        analysis_type="XRD",
        workflow_template_id="xrd.general",
        existing_processing=existing_processing,
        batch_run_id="batch_xrd_first",
    )
    second = execute_batch_template(
        dataset_key="synthetic_xrd",
        dataset=dataset,
        analysis_type="XRD",
        workflow_template_id="xrd.general",
        existing_processing=existing_processing,
        batch_run_id="batch_xrd_second",
    )

    first_processing = dict(first["record"]["processing"])
    second_processing = dict(second["record"]["processing"])
    first_context = dict(first_processing["method_context"])
    second_context = dict(second_processing["method_context"])
    first_context.pop("batch_run_id", None)
    second_context.pop("batch_run_id", None)
    first_processing["method_context"] = first_context
    second_processing["method_context"] = second_context

    assert first["status"] == second["status"] == "saved"
    assert first_processing == second_processing
    assert first["record"]["summary"] == second["record"]["summary"]
    assert first["record"]["rows"] == second["record"]["rows"]
    assert first["record"]["summary"]["peak_count"] <= 3
    assert first["record"]["summary"]["candidate_count"] <= 2


def test_execute_xrd_batch_template_keeps_no_match_as_cautionary_saved_output():
    dataset = _make_xrd_dataset(no_match=True)

    outcome = execute_batch_template(
        dataset_key="synthetic_xrd",
        dataset=dataset,
        analysis_type="XRD",
        workflow_template_id="xrd.general",
        batch_run_id="batch_xrd_no_match",
    )

    assert outcome["status"] == "saved"
    assert outcome["record"]["summary"]["match_status"] == "no_match"
    assert outcome["record"]["summary"]["confidence_band"] == "no_match"
    assert outcome["record"]["summary"]["caution_code"] == "xrd_no_match"
    assert outcome["record"]["summary"]["top_candidate_id"] == "xrd_phase_mismatch_a"
    assert outcome["record"]["summary"]["top_candidate_name"] == "Mismatch A"
    assert outcome["record"]["summary"]["top_candidate_score"] is not None
    assert outcome["record"]["summary"]["top_candidate_reason_below_threshold"]
    assert outcome["record"]["summary"]["top_candidate_unmatched_major_peak_count"] >= 0
    assert "matched_peak_pairs" in outcome["record"]["rows"][0]["evidence"]
    assert "unmatched_observed_peaks" in outcome["record"]["rows"][0]["evidence"]
    assert "unmatched_reference_peaks" in outcome["record"]["rows"][0]["evidence"]
    assert "screening result" in outcome["record"]["summary"]["caution_message"].lower()
    assert outcome["record"]["review"]["caution"]["code"] == "xrd_no_match"
    assert outcome["record"]["review"]["caution"]["top_candidate_name"] == "Mismatch A"
    assert outcome["summary_row"]["match_status"] == "no_match"


def test_execute_batch_template_uses_installed_global_reference_libraries(monkeypatch):
    mirror_root = Path(__file__).resolve().parents[1] / "sample_data" / "reference_library_mirror"
    monkeypatch.setenv("THERMOANALYZER_LIBRARY_MIRROR_ROOT", str(mirror_root))
    manager = get_reference_library_manager()
    manager.sync(force=True, package_ids=["openspecy_ftir_core", "cod_xrd_core"])

    spectral_dataset = _make_spectral_dataset(analysis_type="FTIR", include_reference_library=False)
    spectral_outcome = execute_batch_template(
        dataset_key="synthetic_ftir_global",
        dataset=spectral_dataset,
        analysis_type="FTIR",
        workflow_template_id="ftir.general",
        batch_run_id="batch_ftir_global",
    )

    assert spectral_outcome["status"] == "saved"
    assert spectral_outcome["record"]["summary"]["library_package"] == "openspecy_ftir_core"
    assert spectral_outcome["record"]["summary"]["library_provider"] == "OpenSpecy"
    assert spectral_outcome["record"]["summary"]["library_cache_status"] == "warm"
    assert spectral_outcome["record"]["rows"][0]["library_package"] == "openspecy_ftir_core"

    xrd_dataset = _make_xrd_dataset(include_reference_library=False)
    xrd_outcome = execute_batch_template(
        dataset_key="synthetic_xrd_global",
        dataset=xrd_dataset,
        analysis_type="XRD",
        workflow_template_id="xrd.general",
        batch_run_id="batch_xrd_global",
    )

    assert xrd_outcome["status"] == "saved"
    assert xrd_outcome["record"]["summary"]["library_package"] == "cod_xrd_core"
    assert xrd_outcome["record"]["summary"]["library_provider"] == "COD"
    assert xrd_outcome["record"]["summary"]["library_cache_status"] == "warm"
    assert xrd_outcome["record"]["summary"]["top_candidate_package"] == "cod_xrd_core"
    assert xrd_outcome["record"]["rows"][0]["library_package"] == "cod_xrd_core"


def test_execute_batch_template_blocks_failed_validation(thermal_dataset):
    dataset = thermal_dataset.copy()
    dataset.data.loc[10, "temperature"] = dataset.data.loc[9, "temperature"]

    outcome = execute_batch_template(
        dataset_key="broken_dsc",
        dataset=dataset,
        analysis_type="DSC",
        workflow_template_id="dsc.general",
        batch_run_id="batch_broken_demo",
    )

    assert outcome["status"] == "blocked"
    assert outcome["record"] is None
    assert outcome["state"] is None
    assert outcome["validation"]["status"] == "fail"
    assert "strictly increasing" in " ".join(outcome["validation"]["issues"])
    assert outcome["summary_row"]["execution_status"] == "blocked"


def test_batch_summary_helpers_normalize_legacy_error_rows():
    rows = [
        {"dataset_key": "run_a", "execution_status": "saved"},
        {"dataset_key": "run_b", "execution_status": "blocked", "failure_reason": "Validation blocked", "error_id": "TA-DSC-1"},
        {"dataset_key": "run_c", "execution_status": "error", "message": "Processor exploded", "error_id": "TA-DSC-2"},
    ]

    normalized = normalize_batch_summary_rows(rows)
    totals = summarize_batch_outcomes(rows)
    failed_only = filter_batch_summary_rows(rows, execution_status="failed")

    assert [row["execution_status"] for row in normalized] == ["saved", "blocked", "failed"]
    assert normalized[2]["failure_reason"] == "Processor exploded"
    assert totals == {"total": 3, "saved": 1, "blocked": 1, "failed": 1}
    assert [row["dataset_key"] for row in failed_only] == ["run_c"]


def test_execute_dsc_batch_template_is_deterministic_for_same_input_and_template(thermal_dataset):
    dataset = thermal_dataset.copy()
    dataset.metadata.update(
        {
            "vendor": "TestVendor",
            "display_name": "Synthetic DSC Run",
            "calibration_id": "DSC-CAL-01",
            "calibration_status": "verified",
        }
    )

    first = execute_batch_template(
        dataset_key="synthetic_dsc",
        dataset=dataset,
        analysis_type="DSC",
        workflow_template_id="dsc.polymer_tg",
        batch_run_id="batch_dsc_first",
    )
    second = execute_batch_template(
        dataset_key="synthetic_dsc",
        dataset=dataset,
        analysis_type="DSC",
        workflow_template_id="dsc.polymer_tg",
        batch_run_id="batch_dsc_second",
    )

    first_processing = dict(first["record"]["processing"])
    second_processing = dict(second["record"]["processing"])
    first_context = dict(first_processing["method_context"])
    second_context = dict(second_processing["method_context"])
    first_context.pop("batch_run_id", None)
    second_context.pop("batch_run_id", None)
    first_processing["method_context"] = first_context
    second_processing["method_context"] = second_context

    assert first["status"] == second["status"] == "saved"
    assert first_processing == second_processing
    assert first["record"]["summary"] == second["record"]["summary"]
    assert first["record"]["rows"] == second["record"]["rows"]
    np.testing.assert_allclose(first["state"]["corrected"], second["state"]["corrected"])


def test_execute_tga_batch_template_is_deterministic_for_same_input_and_template(temperature_range, tga_signal):
    dataset = _make_tga_dataset(temperature_range, tga_signal)

    first = execute_batch_template(
        dataset_key="synthetic_tga",
        dataset=dataset,
        analysis_type="TGA",
        workflow_template_id="tga.single_step_decomposition",
        batch_run_id="batch_tga_first",
    )
    second = execute_batch_template(
        dataset_key="synthetic_tga",
        dataset=dataset,
        analysis_type="TGA",
        workflow_template_id="tga.single_step_decomposition",
        batch_run_id="batch_tga_second",
    )

    first_processing = dict(first["record"]["processing"])
    second_processing = dict(second["record"]["processing"])
    first_context = dict(first_processing["method_context"])
    second_context = dict(second_processing["method_context"])
    first_context.pop("batch_run_id", None)
    second_context.pop("batch_run_id", None)
    first_processing["method_context"] = first_context
    second_processing["method_context"] = second_context

    assert first["status"] == second["status"] == "saved"
    assert first_processing == second_processing
    assert first["record"]["summary"] == second["record"]["summary"]
    assert first["record"]["rows"] == second["record"]["rows"]
    np.testing.assert_allclose(first["state"]["smoothed"], second["state"]["smoothed"])


def test_execute_tga_batch_template_preserves_explicit_absolute_mass_mode(temperature_range, tga_percent_signal):
    dataset = _make_tga_dataset(temperature_range, tga_percent_signal, signal_unit="")
    dataset.metadata["sample_mass"] = 100.0
    existing_processing = set_tga_unit_mode(
        {"workflow_template_id": "tga.general", "workflow_template": "General TGA"},
        "absolute_mass",
    )

    outcome = execute_batch_template(
        dataset_key="explicit_mass_tga",
        dataset=dataset,
        analysis_type="TGA",
        workflow_template_id="tga.general",
        existing_processing=existing_processing,
        batch_run_id="batch_explicit_mass_tga",
    )

    method_context = outcome["record"]["processing"]["method_context"]
    assert outcome["status"] == "saved"
    assert method_context["tga_unit_mode_declared"] == "absolute_mass"
    assert method_context["tga_unit_mode_resolved"] == "absolute_mass"
    assert method_context["tga_unit_auto_inference_used"] is False
    assert method_context["tga_unit_reference_source"] == "initial_mass_mg"
