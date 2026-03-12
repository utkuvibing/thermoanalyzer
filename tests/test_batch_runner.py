from __future__ import annotations

import io

import numpy as np
import pandas as pd

from core.batch_runner import execute_batch_template, filter_batch_summary_rows, normalize_batch_summary_rows, summarize_batch_outcomes
from core.data_io import ThermalDataset, read_thermal_data
from core.processing_schema import set_tga_unit_mode


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


def _make_xrd_dataset():
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
    return ThermalDataset(
        data=pd.DataFrame({"temperature": axis, "signal": signal}),
        metadata={
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
        },
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


def test_execute_xrd_batch_template_detects_ranked_peaks_with_processing_context():
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
    assert outcome["record"]["summary"]["match_status"] == "not_run"
    assert outcome["summary_row"]["peak_count"] == outcome["record"]["summary"]["peak_count"]
    assert outcome["summary_row"]["execution_status"] == "saved"

    rows = list(outcome["record"]["rows"])
    ranks = [row["rank"] for row in rows]
    assert ranks == sorted(ranks)
    prominence_pairs = [(row["prominence"], row["position"]) for row in rows]
    assert prominence_pairs == sorted(prominence_pairs, key=lambda item: (-item[0], item[1]))


def test_execute_xrd_batch_template_is_deterministic_and_honors_peak_limit_override():
    dataset = _make_xrd_dataset()
    existing_processing = {
        "analysis_type": "XRD",
        "workflow_template_id": "xrd.general",
        "analysis_steps": {
            "peak_detection": {"prominence": 0.14, "distance": 9, "width": 3, "max_peaks": 3},
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
