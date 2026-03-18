from __future__ import annotations

import io

import numpy as np
import pandas as pd

from core.data_io import ThermalDataset, read_thermal_data
from core.processing_schema import ensure_processing_payload, set_tga_unit_mode, update_method_context, update_processing_step
from core.provenance import build_calibration_reference_context, classify_calibration_state
from core.validation import enrich_spectral_result_validation, enrich_xrd_result_validation, validate_thermal_dataset
from ui.home import _validate_import_stage
from utils.validators import validate_thermal_dataset as legacy_validate_thermal_dataset


def _make_dta_dataset(thermal_dataset):
    dataset = thermal_dataset.copy()
    dataset.data_type = "DTA"
    dataset.units["signal"] = "uV"
    dataset.metadata.update(
        {
            "sample_name": "SyntheticDTA",
            "sample_mass": 5.0,
            "heating_rate": 10.0,
            "instrument": "TestInstrument",
            "vendor": "TestVendor",
            "display_name": "Synthetic DTA Run",
        }
    )
    return dataset


def _make_xrd_dataset():
    axis = np.linspace(8.0, 88.0, 600)
    signal = (
        16.0
        + 0.03 * axis
        + 90.0 * np.exp(-0.5 * ((axis - 18.4) / 0.28) ** 2)
        + 140.0 * np.exp(-0.5 * ((axis - 35.3) / 0.36) ** 2)
        + 110.0 * np.exp(-0.5 * ((axis - 49.8) / 0.32) ** 2)
        + 70.0 * np.exp(-0.5 * ((axis - 64.1) / 0.44) ** 2)
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
            "xrd_axis_role": "two_theta",
            "xrd_axis_unit": "degree_2theta",
            "xrd_wavelength_angstrom": 1.5406,
            "import_confidence": "high",
            "import_review_required": False,
            "import_warnings": [],
        },
        data_type="XRD",
        units={"temperature": "degree_2theta", "signal": "counts"},
        original_columns={"temperature": "two_theta", "signal": "intensity"},
        file_path="",
    )


def _make_spectral_dataset(*, analysis_type: str, axis_values: list[float], signal_values: list[float]):
    metadata = {
        "sample_name": f"Synthetic{analysis_type}",
        "sample_mass": 1.0,
        "heating_rate": 1.0,
        "instrument": "SpectralBench",
        "vendor": "TestVendor",
        "display_name": f"Synthetic {analysis_type} Spectrum",
        "import_confidence": "high",
        "import_review_required": False,
        "import_warnings": [],
        "inferred_analysis_type": analysis_type,
    }
    unit = "cm^-1"
    signal_unit = "absorbance" if analysis_type == "FTIR" else "counts"
    return ThermalDataset(
        data=pd.DataFrame({"temperature": axis_values, "signal": signal_values}),
        metadata=metadata,
        data_type=analysis_type,
        units={"temperature": unit, "signal": signal_unit},
        original_columns={"temperature": "axis", "signal": "signal"},
        file_path="",
    )


def test_validate_thermal_dataset_passes_for_synthetic_fixture(thermal_dataset):
    summary = validate_thermal_dataset(thermal_dataset, analysis_type="DSC")
    assert summary["status"] in {"pass", "warn"}
    assert not summary["issues"]
    assert summary["checks"]["data_points"] == len(thermal_dataset.data)


def test_validate_thermal_dataset_fails_for_non_monotonic_temperature(thermal_dataset):
    broken = thermal_dataset.copy()
    broken.data.loc[10, "temperature"] = broken.data.loc[9, "temperature"]

    summary = validate_thermal_dataset(broken, analysis_type="DSC")

    assert summary["status"] == "fail"
    assert any("strictly increasing" in issue for issue in summary["issues"])


def test_read_thermal_data_populates_source_data_hash():
    dataset = read_thermal_data(
        io.StringIO("Temperature,HeatFlow\n30.0,0.0\n50.0,0.5\n70.0,0.1\n")
    )
    assert dataset.metadata["source_data_hash"]
    assert len(dataset.metadata["source_data_hash"]) == 64


def test_validate_thermal_dataset_warns_when_required_metadata_missing():
    dataset = read_thermal_data(io.StringIO("Temperature,Weight\n30.0,100.0\n50.0,95.0\n70.0,90.0\n"))
    summary = validate_thermal_dataset(dataset, analysis_type="TGA")

    assert summary["status"] == "warn"
    assert any("Recommended metadata missing" in warning for warning in summary["warnings"])


def test_validate_thermal_dataset_surfaces_import_review_context():
    dataset = read_thermal_data(io.StringIO("Temperature,Weight\n30.0,100.0\n50.0,95.0\n70.0,90.0\n"))

    summary = validate_thermal_dataset(dataset, analysis_type="TGA")

    assert summary["checks"]["import_confidence"] == "review"
    assert summary["checks"]["import_review_required"] is True
    assert summary["checks"]["inferred_analysis_type"] == "TGA"
    assert summary["checks"]["inferred_signal_unit"] == "a.u."
    assert any("Import heuristics require review" in warning for warning in summary["warnings"])


def test_ensure_processing_payload_backfills_legacy_workflow_template_label():
    processing = ensure_processing_payload({"workflow_template": "Polymer Tg"}, analysis_type="DSC")

    assert processing["workflow_template"] == "Polymer Tg"
    assert processing["workflow_template_id"] == "dsc.polymer_tg"
    assert processing["workflow_template_label"] == "Polymer Tg"
    assert processing["workflow_template_version"] == 1


def test_validate_dsc_processing_records_calibration_and_sign_convention(thermal_dataset):
    dataset = thermal_dataset.copy()
    dataset.metadata.update(
        {
            "vendor": "TestVendor",
            "display_name": "Synthetic DSC Run",
            "calibration_id": "DSC-CAL-01",
            "calibration_status": "verified",
        }
    )
    processing = ensure_processing_payload(
        analysis_type="DSC",
        workflow_template="dsc.polymer_tg",
        workflow_template_label="Polymer Tg",
    )
    processing = update_processing_step(processing, "baseline", {"method": "asls"})
    processing = update_processing_step(processing, "peak_detection", {"direction": "both", "peak_count": 1})

    summary = validate_thermal_dataset(dataset, analysis_type="DSC", processing=processing)

    assert summary["status"] == "pass"
    assert summary["checks"]["workflow_template_id"] == "dsc.polymer_tg"
    assert summary["checks"]["workflow_template_version"] == 1
    assert summary["checks"]["calibration_state"] == "calibrated"
    assert summary["checks"]["calibration_acceptance"] == "accepted"
    assert summary["checks"]["calibration_status"] == "verified"
    assert summary["checks"]["sign_convention"] == "Endotherm up / Exotherm down"
    assert summary["checks"]["reference_state"] == "not recorded"
    assert summary["checks"]["reference_acceptance"] == "review"
    assert summary["checks"]["peak_detection_context"] == "recorded"


def test_validate_dsc_processing_blocks_failed_calibration(thermal_dataset):
    dataset = thermal_dataset.copy()
    dataset.metadata.update(
        {
            "vendor": "TestVendor",
            "display_name": "Synthetic DSC Run",
            "calibration_id": "DSC-CAL-EXPIRED",
            "calibration_status": "expired",
        }
    )
    processing = ensure_processing_payload(
        analysis_type="DSC",
        workflow_template="dsc.general",
        workflow_template_label="General DSC",
    )

    summary = validate_thermal_dataset(dataset, analysis_type="DSC", processing=processing)

    assert summary["status"] == "fail"
    assert summary["checks"]["calibration_state"] == "calibration_not_current"
    assert any("not currently verified" in issue for issue in summary["issues"])


def test_validate_dta_processing_passes_with_stable_method_context(thermal_dataset):
    dataset = _make_dta_dataset(thermal_dataset)
    processing = ensure_processing_payload(
        analysis_type="DTA",
        workflow_template="dta.general",
        workflow_template_label="General DTA",
    )
    processing = update_processing_step(
        processing,
        "peak_detection",
        {"method": "thermal_peaks", "prominence": 0.1},
    )
    processing = update_method_context(
        processing,
        {"reference_state": "reference_checked"},
        analysis_type="DTA",
    )

    summary = validate_thermal_dataset(dataset, analysis_type="DTA", processing=processing)

    assert summary["status"] == "pass"
    assert not summary["issues"]
    assert not summary["warnings"]
    assert summary["checks"]["workflow_template_id"] == "dta.general"
    assert summary["checks"]["sign_convention"] == "Exotherm up / Endotherm down"
    assert summary["checks"]["peak_detection_context"] == "recorded"
    assert summary["checks"]["reference_acceptance"] == "accepted"


def test_validate_dta_processing_warns_when_sign_convention_and_peak_context_missing(thermal_dataset):
    dataset = _make_dta_dataset(thermal_dataset)
    processing = ensure_processing_payload(analysis_type="DTA", workflow_template="dta.general")
    processing = update_method_context(
        processing,
        {"sign_convention_label": "", "sign_convention_id": ""},
        analysis_type="DTA",
    )

    summary = validate_thermal_dataset(dataset, analysis_type="DTA", processing=processing)

    assert summary["status"] == "warn"
    assert summary["issues"] == []
    assert any("sign convention is not recorded" in warning.lower() for warning in summary["warnings"])
    assert any("peak-detection settings" in warning.lower() for warning in summary["warnings"])
    assert summary["checks"]["peak_detection_context"] == "not recorded"


def test_validate_dta_processing_fails_when_method_context_is_not_dta(thermal_dataset):
    dataset = _make_dta_dataset(thermal_dataset)
    processing = ensure_processing_payload(analysis_type="DSC", workflow_template="dsc.general")

    summary = validate_thermal_dataset(dataset, analysis_type="DTA", processing=processing)

    assert summary["status"] == "fail"
    assert any("analysis_type does not match dta" in issue.lower() for issue in summary["issues"])
    assert any("not supported for stable reporting" in issue.lower() for issue in summary["issues"])


def test_validate_dta_processing_fails_when_template_requires_reference_without_acceptance(thermal_dataset):
    dataset = _make_dta_dataset(thermal_dataset)
    processing = ensure_processing_payload(analysis_type="DTA", workflow_template="dta.thermal_events")
    processing = update_method_context(
        processing,
        {"reference_required": True, "reference_state": "not_recorded"},
        analysis_type="DTA",
    )

    summary = validate_thermal_dataset(dataset, analysis_type="DTA", processing=processing)

    assert summary["status"] == "fail"
    assert any("requires a verified reference state" in issue.lower() for issue in summary["issues"])
    assert summary["checks"]["reference_required"] is True
    assert summary["checks"]["reference_acceptance"] == "review"


def test_validate_xrd_processing_passes_with_peak_controls_and_context():
    dataset = _make_xrd_dataset()
    processing = ensure_processing_payload(
        analysis_type="XRD",
        workflow_template="xrd.general",
        workflow_template_label="General XRD",
    )
    processing = update_processing_step(
        processing,
        "axis_normalization",
        {"sort_axis": True, "deduplicate": "first", "axis_min": 8.0, "axis_max": 88.0},
        analysis_type="XRD",
    )
    processing = update_processing_step(
        processing,
        "smoothing",
        {"method": "savgol", "window_length": 11, "polyorder": 3},
        analysis_type="XRD",
    )
    processing = update_processing_step(
        processing,
        "baseline",
        {"method": "rolling_minimum", "window_length": 31},
        analysis_type="XRD",
    )
    processing = update_processing_step(
        processing,
        "peak_detection",
        {"method": "scipy_find_peaks", "prominence": 0.08, "distance": 6, "width": 2, "max_peaks": 12},
        analysis_type="XRD",
    )
    processing = update_method_context(
        processing,
        {
            "xrd_peak_count": 4,
            "xrd_reference_candidate_count": 3,
            "xrd_match_metric": "peak_overlap_weighted",
            "xrd_match_tolerance_deg": 0.28,
            "xrd_match_top_n": 5,
            "xrd_match_minimum_score": 0.42,
        },
        analysis_type="XRD",
    )

    summary = validate_thermal_dataset(dataset, analysis_type="XRD", processing=processing)

    assert summary["status"] == "pass"
    assert summary["issues"] == []
    assert summary["warnings"] == []
    assert summary["checks"]["workflow_template_id"] == "xrd.general"
    assert summary["checks"]["peak_detection_context"] == "recorded"
    assert summary["checks"]["xrd_peak_prominence"] == 0.08
    assert summary["checks"]["xrd_peak_distance"] == 6
    assert summary["checks"]["xrd_peak_width"] == 2


def test_validate_xrd_processing_fails_when_peak_controls_missing():
    dataset = _make_xrd_dataset()
    processing = ensure_processing_payload(
        analysis_type="XRD",
        workflow_template="xrd.general",
        workflow_template_label="General XRD",
    )
    processing = update_processing_step(
        processing,
        "peak_detection",
        {"method": "scipy_find_peaks", "prominence": "", "distance": "", "width": ""},
        analysis_type="XRD",
    )

    summary = validate_thermal_dataset(dataset, analysis_type="XRD", processing=processing)

    assert summary["status"] == "fail"
    assert any("peak-detection 'prominence' is required" in issue.lower() for issue in summary["issues"])
    assert any("peak-detection 'distance' is required" in issue.lower() for issue in summary["issues"])
    assert any("peak-detection 'width' is required" in issue.lower() for issue in summary["issues"])


def test_validate_ftir_allows_descending_wavenumber_axis_outside_thermal_bounds():
    dataset = _make_spectral_dataset(
        analysis_type="FTIR",
        axis_values=[3999.8, 3200.0, 1800.0, 900.0, 500.0],
        signal_values=[0.02, 0.08, 0.31, 0.22, 0.12],
    )
    processing = ensure_processing_payload(
        analysis_type="FTIR",
        workflow_template="ftir.general",
        workflow_template_label="General FTIR",
    )
    processing = update_processing_step(processing, "normalization", {"method": "vector"}, analysis_type="FTIR")
    processing = update_processing_step(
        processing,
        "peak_detection",
        {"prominence": 0.05, "min_distance": 6, "max_peaks": 12},
        analysis_type="FTIR",
    )
    processing = update_processing_step(
        processing,
        "similarity_matching",
        {"metric": "cosine", "top_n": 3, "minimum_score": 0.45},
        analysis_type="FTIR",
    )

    summary = validate_thermal_dataset(dataset, analysis_type="FTIR", processing=processing)

    assert summary["status"] in {"pass", "warn"}
    assert not any("strictly increasing" in issue.lower() for issue in summary["issues"])
    assert not any("thermal-analysis bounds" in issue.lower() for issue in summary["issues"])


def test_validate_raman_allows_wide_monotonic_shift_axis_outside_thermal_bounds():
    dataset = _make_spectral_dataset(
        analysis_type="RAMAN",
        axis_values=[50.4, 300.0, 800.0, 1600.0, 3400.2],
        signal_values=[12.0, 25.0, 55.0, 32.0, 18.0],
    )
    processing = ensure_processing_payload(
        analysis_type="RAMAN",
        workflow_template="raman.general",
        workflow_template_label="General Raman",
    )
    processing = update_processing_step(processing, "normalization", {"method": "snv"}, analysis_type="RAMAN")
    processing = update_processing_step(
        processing,
        "peak_detection",
        {"prominence": 0.04, "min_distance": 5, "max_peaks": 14},
        analysis_type="RAMAN",
    )
    processing = update_processing_step(
        processing,
        "similarity_matching",
        {"metric": "cosine", "top_n": 3, "minimum_score": 0.45},
        analysis_type="RAMAN",
    )

    summary = validate_thermal_dataset(dataset, analysis_type="RAMAN", processing=processing)

    assert summary["status"] in {"pass", "warn"}
    assert not any("strictly increasing" in issue.lower() for issue in summary["issues"])
    assert not any("thermal-analysis bounds" in issue.lower() for issue in summary["issues"])


def test_validate_import_stage_uses_detected_spectral_modality():
    dataset = _make_spectral_dataset(
        analysis_type="FTIR",
        axis_values=[3999.8, 3200.0, 1800.0, 900.0, 500.0],
        signal_values=[0.02, 0.08, 0.31, 0.22, 0.12],
    )

    summary = _validate_import_stage(dataset)

    assert summary["status"] in {"pass", "warn"}
    assert not any("thermal-analysis bounds" in issue.lower() for issue in summary["issues"])


def test_validate_xrd_processing_warns_when_wavelength_context_is_missing():
    dataset = _make_xrd_dataset()
    dataset.metadata["xrd_wavelength_angstrom"] = None
    dataset.metadata["xrd_provenance_state"] = "incomplete"
    dataset.metadata["xrd_provenance_warning"] = "XRD wavelength is not recorded; qualitative phase matching provenance remains incomplete."
    processing = ensure_processing_payload(
        analysis_type="XRD",
        workflow_template="xrd.general",
        workflow_template_label="General XRD",
    )
    processing = update_processing_step(
        processing,
        "peak_detection",
        {"method": "scipy_find_peaks", "prominence": 0.09, "distance": 7, "width": 3, "max_peaks": 10},
        analysis_type="XRD",
    )
    processing = update_method_context(
        processing,
        {
            "xrd_wavelength_angstrom": None,
            "xrd_reference_candidate_count": 2,
            "xrd_match_metric": "peak_overlap_weighted",
            "xrd_match_tolerance_deg": 0.28,
            "xrd_match_top_n": 5,
            "xrd_match_minimum_score": 0.42,
        },
        analysis_type="XRD",
    )

    summary = validate_thermal_dataset(dataset, analysis_type="XRD", processing=processing)

    assert summary["status"] == "warn"
    assert summary["issues"] == []
    assert any("xrd wavelength is not recorded" in warning.lower() for warning in summary["warnings"])
    assert summary["checks"]["xrd_provenance_state"] == "incomplete"


def test_validate_xrd_processing_fails_when_axis_mapping_requires_review():
    dataset = _make_xrd_dataset()
    dataset.metadata["xrd_axis_mapping_review_required"] = True
    dataset.metadata["xrd_stable_matching_blocked"] = True
    processing = ensure_processing_payload(
        analysis_type="XRD",
        workflow_template="xrd.general",
        workflow_template_label="General XRD",
    )
    processing = update_processing_step(
        processing,
        "peak_detection",
        {"method": "scipy_find_peaks", "prominence": 0.09, "distance": 7, "width": 3, "max_peaks": 10},
        analysis_type="XRD",
    )
    processing = update_method_context(
        processing,
        {
            "xrd_reference_candidate_count": 12,
            "xrd_match_metric": "peak_overlap_weighted",
            "xrd_match_tolerance_deg": 0.28,
            "xrd_match_top_n": 5,
            "xrd_match_minimum_score": 0.42,
        },
        analysis_type="XRD",
    )

    summary = validate_thermal_dataset(dataset, analysis_type="XRD", processing=processing)

    assert summary["status"] == "fail"
    assert any("2theta/angle confirmation" in issue.lower() for issue in summary["issues"])


def test_validate_tga_processing_checks_unit_plausibility_and_step_context():
    dataset = read_thermal_data(io.StringIO("Temperature,Weight\n30.0,130.0\n50.0,125.0\n70.0,118.0\n"))
    dataset.units["signal"] = "%"
    dataset.metadata.update(
        {
            "sample_name": "SyntheticTGA",
            "sample_mass": 10.0,
            "heating_rate": 20.0,
            "instrument": "TestInstrument",
            "vendor": "TestVendor",
            "display_name": "Synthetic TGA Run",
            "atmosphere": "Nitrogen",
            "atmosphere_status": "verified",
        }
    )
    processing = ensure_processing_payload(
        analysis_type="TGA",
        workflow_template="tga.single_step_decomposition",
        workflow_template_label="Single-Step Decomposition",
    )
    processing = update_processing_step(
        processing,
        "step_detection",
        {"method": "savgol", "prominence": 0.1, "min_mass_loss": 0.5},
    )

    summary = validate_thermal_dataset(dataset, analysis_type="TGA", processing=processing)

    assert summary["status"] == "warn"
    assert summary["checks"]["workflow_template_id"] == "tga.single_step_decomposition"
    assert summary["checks"]["workflow_template_version"] == 1
    assert summary["checks"]["tga_unit_mode_declared"] == "auto"
    assert summary["checks"]["tga_unit_mode_resolved"] == "percent"
    assert summary["checks"]["tga_unit_auto_inference_used"] is True
    assert summary["checks"]["tga_unit_interpretation_status"] == "accepted"
    assert summary["checks"]["atmosphere_status"] == "verified"
    assert summary["checks"]["calibration_state"] == "missing_calibration"
    assert summary["checks"]["calibration_acceptance"] == "missing"
    assert summary["checks"]["step_analysis_context"] == "recorded"
    assert summary["checks"]["reference_state"] == "not recorded"
    assert summary["checks"]["reference_acceptance"] == "review"
    assert summary["checks"]["unit_plausibility"] == "review"
    assert any("plausible mass-percent range" in warning for warning in summary["warnings"])


def test_validate_tga_auto_mode_on_ambiguous_low_range_warns_for_review():
    dataset = read_thermal_data(io.StringIO("Temperature,Weight\n30.0,100.0\n50.0,95.0\n70.0,90.0\n"))
    dataset.metadata.update(
        {
            "sample_name": "AmbiguousLowRangeTGA",
            "sample_mass": 10.0,
            "heating_rate": 20.0,
            "instrument": "TestInstrument",
            "vendor": "TestVendor",
            "display_name": "Ambiguous TGA Run",
            "atmosphere": "Nitrogen",
            "atmosphere_status": "verified",
        }
    )
    processing = ensure_processing_payload(analysis_type="TGA", workflow_template="tga.general")

    summary = validate_thermal_dataset(dataset, analysis_type="TGA", processing=processing)

    assert summary["status"] == "warn"
    assert summary["checks"]["tga_unit_mode_declared"] == "auto"
    assert summary["checks"]["tga_unit_mode_resolved"] == "percent"
    assert summary["checks"]["tga_unit_auto_inference_used"] is True
    assert summary["checks"]["tga_unit_interpretation_status"] == "review"
    assert summary["checks"]["unit_plausibility"] == "review"
    assert any("defaulted to percent" in warning for warning in summary["warnings"])


def test_validate_tga_explicit_absolute_mass_mode_overrides_low_range_ambiguity():
    dataset = read_thermal_data(io.StringIO("Temperature,Weight\n30.0,100.0\n50.0,95.0\n70.0,90.0\n"))
    dataset.metadata.update(
        {
            "sample_name": "ExplicitMassModeTGA",
            "sample_mass": 100.0,
            "heating_rate": 20.0,
            "instrument": "TestInstrument",
            "vendor": "TestVendor",
            "display_name": "Explicit Mass TGA Run",
            "atmosphere": "Nitrogen",
            "atmosphere_status": "verified",
        }
    )
    processing = ensure_processing_payload(analysis_type="TGA", workflow_template="tga.general")
    processing = set_tga_unit_mode(processing, "absolute_mass")
    dataset.units["signal"] = ""

    summary = validate_thermal_dataset(dataset, analysis_type="TGA", processing=processing)

    assert summary["checks"]["tga_unit_mode_declared"] == "absolute_mass"
    assert summary["checks"]["tga_unit_mode_resolved"] == "absolute_mass"
    assert summary["checks"]["tga_unit_auto_inference_used"] is False
    assert summary["checks"]["tga_unit_interpretation_status"] == "accepted"
    assert summary["checks"]["unit_plausibility"] == "pass"


def test_tga_reference_lookup_does_not_fall_back_to_dsc_standards():
    dataset = read_thermal_data(io.StringIO("Temperature,Weight\n30.0,100.0\n50.0,95.0\n70.0,90.0\n"))
    dataset.metadata.update(
        {
            "sample_name": "SyntheticTGA",
            "sample_mass": 10.0,
            "heating_rate": 20.0,
            "instrument": "TestInstrument",
        }
    )

    context = build_calibration_reference_context(
        dataset=dataset,
        analysis_type="TGA",
        reference_temperature_c=155.0,
    )

    assert context["reference_state"] == "reference_out_of_window"
    assert context["reference_checked"] is False
    assert context["reference_acceptance"] == "review"
    assert "reference_name" not in context


def test_classify_calibration_state_distinguishes_all_supported_states():
    assert classify_calibration_state(calibration_id="CAL-01", calibration_status="verified") == {
        "calibration_state": "calibrated",
        "calibration_acceptance": "accepted",
        "calibration_id": "CAL-01",
        "calibration_status": "verified",
    }
    assert classify_calibration_state(calibration_id="", calibration_status=None)["calibration_state"] == "missing_calibration"
    assert classify_calibration_state(calibration_id="CAL-02", calibration_status="expired")["calibration_state"] == "calibration_not_current"
    assert classify_calibration_state(calibration_id="CAL-03", calibration_status="pending_review")["calibration_state"] == "unknown_calibration_state"


def test_legacy_validator_wraps_structured_validation_for_current_dataset(thermal_dataset):
    is_valid, message = legacy_validate_thermal_dataset(thermal_dataset)

    assert is_valid is True
    assert "Validation passed" in message or "All checks passed" in message


def test_legacy_validator_surfaces_structured_failures(thermal_dataset):
    broken = thermal_dataset.copy()
    broken.data.loc[10, "temperature"] = broken.data.loc[9, "temperature"]

    is_valid, message = legacy_validate_thermal_dataset(broken)

    assert is_valid is False
    assert "strictly increasing" in message


def test_enrich_ftir_result_validation_adds_no_match_caution_semantics():
    validation = {"status": "pass", "issues": [], "warnings": [], "checks": {}}
    summary = {
        "match_status": "no_match",
        "candidate_count": 1,
        "top_match_score": 0.31,
        "confidence_band": "no_match",
        "caution_code": "spectral_no_match",
    }
    rows = [
        {
            "rank": 1,
            "candidate_id": "ftir_ref_a",
            "normalized_score": 0.31,
            "confidence_band": "no_match",
            "evidence": {"shared_peak_count": 0},
        }
    ]

    enriched = enrich_spectral_result_validation(
        validation,
        analysis_type="FTIR",
        summary=summary,
        rows=rows,
    )

    assert enriched["status"] == "warn"
    assert enriched["issues"] == []
    assert enriched["checks"]["match_status"] == "no_match"
    assert enriched["checks"]["confidence_band"] == "no_match"
    assert enriched["checks"]["caution_code"] == "spectral_no_match"
    assert enriched["checks"]["caution_state_output"] == "no_match"
    assert any("cautionary outcome" in item.lower() for item in enriched["warnings"])


def test_enrich_raman_result_validation_requires_evidence_for_matched_output():
    validation = {"status": "pass", "issues": [], "warnings": [], "checks": {}}
    summary = {
        "match_status": "matched",
        "candidate_count": 1,
        "top_match_id": "raman_ref_a",
        "top_match_score": 0.73,
        "confidence_band": "medium",
    }
    rows = [
        {
            "rank": 1,
            "candidate_id": "raman_ref_a",
            "normalized_score": 0.73,
            "confidence_band": "medium",
        }
    ]

    enriched = enrich_spectral_result_validation(
        validation,
        analysis_type="RAMAN",
        summary=summary,
        rows=rows,
    )

    assert enriched["status"] == "warn"
    assert enriched["issues"] == []
    assert enriched["checks"]["match_status"] == "matched"
    assert enriched["checks"]["caution_state_output"] == "clear"
    assert enriched["checks"]["top_match_evidence"] == "missing"
    assert any("missing evidence payload" in item.lower() for item in enriched["warnings"])


def test_enrich_xrd_match_validation_accepts_no_match_as_cautionary_output():
    validation = {"status": "pass", "issues": [], "warnings": [], "checks": {}}
    summary = {
        "match_status": "no_match",
        "candidate_count": 1,
        "top_phase_score": 0.31,
        "confidence_band": "no_match",
        "caution_code": "xrd_no_match",
    }
    rows = [
        {
            "rank": 1,
            "candidate_id": "xrd_phase_alpha",
            "normalized_score": 0.31,
            "confidence_band": "no_match",
            "evidence": {
                "shared_peak_count": 0,
                "weighted_overlap_score": 0.11,
                "mean_delta_position": None,
                "unmatched_major_peak_count": 3,
                "tolerance_deg": 0.28,
            },
        }
    ]

    enriched = enrich_xrd_result_validation(
        validation,
        summary=summary,
        rows=rows,
    )

    assert enriched["status"] == "warn"
    assert enriched["issues"] == []
    assert enriched["checks"]["match_status"] == "no_match"
    assert enriched["checks"]["confidence_band"] == "no_match"
    assert enriched["checks"]["caution_state_output"] == "no_match"
    assert any("cautionary stable outcome" in item.lower() for item in enriched["warnings"])


def test_enrich_xrd_match_validation_fails_when_matched_output_is_missing_evidence():
    validation = {"status": "pass", "issues": [], "warnings": [], "checks": {}}
    summary = {
        "match_status": "matched",
        "candidate_count": 1,
        "top_phase_id": "xrd_phase_alpha",
        "top_phase_score": 0.73,
        "confidence_band": "medium",
    }
    rows = [
        {
            "rank": 1,
            "candidate_id": "xrd_phase_alpha",
            "normalized_score": 0.73,
            "confidence_band": "medium",
            "evidence": {
                "shared_peak_count": 3,
                "weighted_overlap_score": 0.82,
                "mean_delta_position": 0.11,
                "tolerance_deg": 0.28,
            },
        }
    ]

    enriched = enrich_xrd_result_validation(
        validation,
        summary=summary,
        rows=rows,
    )

    assert enriched["status"] == "fail"
    assert any("missing 'unmatched_major_peak_count'" in item.lower() for item in enriched["issues"])
    assert enriched["checks"]["match_status"] == "matched"
    assert enriched["checks"]["top_phase_id"] == "xrd_phase_alpha"


def test_enrich_xrd_confidence_validation_warns_on_low_confidence_matched_output():
    validation = {"status": "pass", "issues": [], "warnings": [], "checks": {}}
    summary = {
        "match_status": "matched",
        "candidate_count": 1,
        "top_phase_id": "xrd_phase_alpha",
        "top_phase_score": 0.57,
        "confidence_band": "low",
        "caution_code": "xrd_low_confidence",
    }
    rows = [
        {
            "rank": 1,
            "candidate_id": "xrd_phase_alpha",
            "normalized_score": 0.57,
            "confidence_band": "low",
            "evidence": {
                "shared_peak_count": 2,
                "weighted_overlap_score": 0.49,
                "mean_delta_position": 0.19,
                "unmatched_major_peak_count": 1,
                "tolerance_deg": 0.28,
            },
        }
    ]

    enriched = enrich_xrd_result_validation(
        validation,
        summary=summary,
        rows=rows,
    )

    assert enriched["status"] == "warn"
    assert enriched["issues"] == []
    assert enriched["checks"]["caution_state_output"] == "low_confidence"
    assert any("low confidence" in item.lower() for item in enriched["warnings"])
