from __future__ import annotations

import pandas as pd

from core.data_io import ThermalDataset
from core.peak_analysis import ThermalPeak
from core.processing_schema import ensure_processing_payload, update_method_context, update_processing_step
from core.result_serialization import (
    flatten_result_records,
    make_result_record,
    serialize_dta_result,
    serialize_spectral_result,
    serialize_xrd_result,
    split_valid_results,
    validate_result_record,
)


def _base_record():
    return make_result_record(
        result_id="demo_result",
        analysis_type="DSC",
        status="stable",
        dataset_key="demo_dataset",
        metadata={"sample_name": "Demo"},
        summary={"peak_count": 1},
        rows=[{"peak_temperature": 123.4}],
    )


def _dta_dataset() -> ThermalDataset:
    return ThermalDataset(
        data=pd.DataFrame({"temperature": [30.0, 50.0, 70.0], "signal": [0.2, 0.5, 0.1]}),
        metadata={
            "sample_name": "SyntheticDTA",
            "sample_mass": 5.0,
            "heating_rate": 10.0,
            "instrument": "TestInstrument",
            "vendor": "TestVendor",
            "display_name": "Synthetic DTA Run",
        },
        data_type="DTA",
        units={"temperature": "degC", "signal": "uV"},
        original_columns={"temperature": "temperature", "signal": "signal"},
        file_path="",
    )


def _dta_peak() -> ThermalPeak:
    return ThermalPeak(
        peak_index=1,
        peak_temperature=50.0,
        peak_signal=0.5,
        onset_temperature=45.0,
        endset_temperature=55.0,
        area=1.2,
        fwhm=3.0,
        peak_type="exo",
        height=0.4,
    )


def _spectral_dataset(analysis_type: str) -> ThermalDataset:
    return ThermalDataset(
        data=pd.DataFrame({"temperature": [600.0, 900.0, 1200.0], "signal": [0.1, 0.7, 0.25]}),
        metadata={
            "sample_name": f"Synthetic{analysis_type.upper()}",
            "sample_mass": 1.0,
            "heating_rate": 1.0,
            "instrument": "SpecBench",
            "vendor": "TestVendor",
            "display_name": f"Synthetic {analysis_type.upper()} Spectrum",
        },
        data_type=analysis_type.upper(),
        units={"temperature": "cm^-1", "signal": "a.u." if analysis_type.upper() == "FTIR" else "counts"},
        original_columns={"temperature": "wavenumber", "signal": "intensity"},
        file_path="",
    )


def _xrd_dataset() -> ThermalDataset:
    return ThermalDataset(
        data=pd.DataFrame({"temperature": [18.4, 33.2, 47.8, 63.5], "signal": [120.0, 240.0, 190.0, 130.0]}),
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
        },
        data_type="XRD",
        units={"temperature": "degree_2theta", "signal": "counts"},
        original_columns={"temperature": "two_theta", "signal": "intensity"},
        file_path="",
    )


def test_serialize_dta_result_stable_status_and_context_wording():
    dataset = _dta_dataset()
    processing = ensure_processing_payload(analysis_type="DTA", workflow_template="dta.general")
    processing = update_processing_step(processing, "peak_detection", {"method": "thermal_peaks", "prominence": 0.1})

    record = serialize_dta_result(
        "synthetic_dta",
        dataset,
        [_dta_peak()],
        processing=processing,
        validation={"status": "pass", "issues": [], "warnings": []},
    )

    assert record["status"] == "stable"
    assert record["summary"]["sample_name"] == "SyntheticDTA"
    assert record["summary"]["sample_mass"] == 5.0
    assert record["summary"]["heating_rate"] == 10.0
    assert record["scientific_context"]["methodology"]["workflow_template"] == "General DTA"
    limitations = " ".join(record["scientific_context"]["limitations"]).lower()
    assert "outside stable reporting guarantees" not in limitations
    assert "dta module is experimental" not in limitations


def test_serialize_dta_result_status_override_keeps_non_stable_path():
    dataset = _dta_dataset()

    record = serialize_dta_result(
        "synthetic_dta",
        dataset,
        [_dta_peak()],
        status="experimental",
        validation={"status": "warn", "issues": [], "warnings": ["review sign convention"]},
    )

    assert record["status"] == "experimental"
    assert record["analysis_type"] == "DTA"
    assert record["scientific_context"]["warnings"]


def test_validate_result_record_accepts_scientific_context_dict():
    record = _base_record()
    record["scientific_context"] = {
        "methodology": {"method": "demo"},
        "equations": [{"name": "E1", "formula": "y=x"}],
    }

    issues = validate_result_record("demo_result", record)

    assert issues == []


def test_validate_result_record_rejects_non_dict_scientific_context():
    record = _base_record()
    record["scientific_context"] = ["not", "a", "dict"]

    issues = validate_result_record("demo_result", record)

    assert any("scientific_context must be a dict" in issue for issue in issues)


def test_split_valid_results_backfills_scientific_context():
    record = _base_record()
    record.pop("scientific_context", None)

    valid, issues = split_valid_results({"demo_result": record})

    assert issues == []
    assert "demo_result" in valid
    assert valid["demo_result"]["scientific_context"] == {
        "methodology": {},
        "equations": [],
        "numerical_interpretation": [],
        "fit_quality": {},
        "warnings": [],
        "limitations": [],
        "scientific_claims": [],
        "evidence_map": {},
        "uncertainty_assessment": {},
        "alternative_hypotheses": [],
        "next_experiments": [],
    }


def test_flatten_result_records_emits_scientific_context_section():
    record = _base_record()
    record["scientific_context"] = {
        "methodology": {"workflow_template": "General DSC"},
        "equations": [{"name": "Energy", "formula": "DeltaH=int(q dT)"}],
    }

    flat_rows = flatten_result_records({"demo_result": record})

    assert any(row["section"] == "scientific_context" and row["field"] == "methodology" for row in flat_rows)
    assert any(row["section"] == "scientific_context" and row["field"] == "equations" for row in flat_rows)


def test_serialize_ftir_result_persists_no_match_caution_and_evidence():
    dataset = _spectral_dataset("FTIR")
    processing = ensure_processing_payload(analysis_type="FTIR", workflow_template="ftir.general")
    processing = update_processing_step(processing, "similarity_matching", {"metric": "cosine", "top_n": 3, "minimum_score": 0.45})

    record = serialize_spectral_result(
        "synthetic_ftir",
        dataset,
        analysis_type="FTIR",
        summary={
            "peak_count": 3,
            "match_status": "no_match",
            "candidate_count": 1,
            "top_match_id": None,
            "top_match_name": None,
            "top_match_score": 0.31,
            "confidence_band": "no_match",
            "caution_code": "spectral_no_match",
            "library_provider": "OpenSpecy",
            "library_package": "openspecy_ftir_core",
            "library_version": "2026.03-core",
            "library_sync_mode": "online_sync",
            "library_cache_status": "warm",
            "library_access_mode": "cloud_full_access",
            "library_request_id": "libreq_ftir_001",
            "library_result_source": "cloud_search",
            "library_provider_scope": ["openspecy"],
            "library_offline_limited_mode": False,
        },
        rows=[
            {
                "rank": 1,
                "candidate_id": "ftir_ref_a",
                "candidate_name": "FTIR Ref A",
                "normalized_score": 0.31,
                "confidence_band": "no_match",
                "library_provider": "OpenSpecy",
                "library_package": "openspecy_ftir_core",
                "library_version": "2026.03-core",
                "evidence": {"shared_peak_count": 0, "peak_overlap_ratio": 0.0},
            }
        ],
        processing=processing,
        validation={"status": "warn", "issues": [], "warnings": ["FTIR produced no confident match."]},
    )

    assert record["id"] == "ftir_synthetic_ftir"
    assert record["analysis_type"] == "FTIR"
    assert record["summary"]["match_status"] == "no_match"
    assert record["summary"]["caution_code"] == "spectral_no_match"
    assert record["summary"]["library_package"] == "openspecy_ftir_core"
    assert record["summary"]["library_access_mode"] == "cloud_full_access"
    assert record["summary"]["library_request_id"] == "libreq_ftir_001"
    assert record["summary"]["library_result_source"] == "cloud_search"
    assert record["review"]["caution"]["code"] == "spectral_no_match"
    assert record["rows"][0]["library_provider"] == "OpenSpecy"
    assert record["rows"][0]["evidence"]["shared_peak_count"] == 0
    assert record["scientific_context"]["methodology"]["library_context"]["package"] == "openspecy_ftir_core"
    assert record["scientific_context"]["methodology"]["library_context"]["request_id"] == "libreq_ftir_001"
    assert record["scientific_context"]["fit_quality"]["confidence_band"] == "no_match"
    assert any("no-match outcomes are valid cautionary results" in item.lower() for item in record["scientific_context"]["limitations"])


def test_serialize_raman_result_adds_low_confidence_caution():
    dataset = _spectral_dataset("RAMAN")
    processing = ensure_processing_payload(analysis_type="RAMAN", workflow_template="raman.general")
    processing = update_processing_step(processing, "similarity_matching", {"metric": "cosine", "top_n": 3, "minimum_score": 0.45})

    record = serialize_spectral_result(
        "synthetic_raman",
        dataset,
        analysis_type="RAMAN",
        summary={
            "peak_count": 3,
            "match_status": "matched",
            "candidate_count": 1,
            "top_match_id": "raman_ref_a",
            "top_match_name": "Raman Ref A",
            "top_match_score": 0.61,
            "confidence_band": "low",
        },
        rows=[
            {
                "rank": 1,
                "candidate_id": "raman_ref_a",
                "candidate_name": "Raman Ref A",
                "normalized_score": 0.61,
                "confidence_band": "low",
                "evidence": {"shared_peak_count": 2, "peak_overlap_ratio": 0.4},
            }
        ],
        processing=processing,
        validation={"status": "warn", "issues": [], "warnings": ["Low-confidence Raman match."]},
    )

    assert record["id"] == "raman_synthetic_raman"
    assert record["analysis_type"] == "RAMAN"
    assert record["summary"]["match_status"] == "matched"
    assert record["summary"]["caution_code"] == "spectral_low_confidence"
    assert record["review"]["caution"]["code"] == "spectral_low_confidence"
    assert record["rows"][0]["evidence"]["shared_peak_count"] == 2


def test_serialize_xrd_result_keeps_candidate_evidence_and_confidence_band_fields():
    dataset = _xrd_dataset()
    processing = ensure_processing_payload(analysis_type="XRD", workflow_template="xrd.general")
    processing = update_method_context(
        processing,
        {
            "xrd_match_metric": "peak_overlap_weighted",
            "xrd_match_tolerance_deg": 0.28,
            "xrd_match_minimum_score": 0.42,
        },
        analysis_type="XRD",
    )

    record = serialize_xrd_result(
        "synthetic_xrd",
        dataset,
        summary={
            "peak_count": 4,
            "match_status": "matched",
            "candidate_count": 2,
            "top_phase_id": "xrd_phase_alpha",
            "top_phase": "Phase Alpha",
            "top_phase_score": 0.79,
            "confidence_band": "medium",
            "library_provider": "COD",
            "library_package": "cod_xrd_core",
            "library_version": "2026.03-core",
            "library_access_mode": "cloud_full_access",
            "library_request_id": "libreq_xrd_001",
            "library_result_source": "cloud_search",
            "library_provider_scope": ["cod", "materials_project"],
            "library_offline_limited_mode": False,
        },
        rows=[
            {
                "rank": 1,
                "candidate_id": "xrd_phase_alpha",
                "candidate_name": "Phase Alpha",
                "normalized_score": 0.79,
                "confidence_band": "medium",
                "library_provider": "COD",
                "library_package": "cod_xrd_core",
                "library_version": "2026.03-core",
                "evidence": {
                    "shared_peak_count": 4,
                    "weighted_overlap_score": 0.83,
                    "mean_delta_position": 0.09,
                    "unmatched_major_peak_count": 0,
                    "tolerance_deg": 0.28,
                    "matched_peak_pairs": [{"observed_index": 0, "reference_index": 0, "delta_position": 0.09}],
                    "unmatched_observed_peaks": [],
                    "unmatched_reference_peaks": [],
                },
            }
        ],
        processing=processing,
        validation={"status": "pass", "issues": [], "warnings": []},
    )

    assert record["id"] == "xrd_synthetic_xrd"
    assert record["analysis_type"] == "XRD"
    assert record["summary"]["top_phase_id"] == "xrd_phase_alpha"
    assert record["summary"]["top_match_id"] == "xrd_phase_alpha"
    assert record["summary"]["top_candidate_id"] == "xrd_phase_alpha"
    assert record["summary"]["top_candidate_name"] == "Phase Alpha"
    assert record["summary"]["top_candidate_score"] == 0.79
    assert record["summary"]["confidence_band"] == "medium"
    assert record["summary"]["library_provider"] == "COD"
    assert record["summary"]["library_access_mode"] == "cloud_full_access"
    assert record["summary"]["library_request_id"] == "libreq_xrd_001"
    assert record["summary"]["library_result_source"] == "cloud_search"
    assert record["rows"][0]["library_package"] == "cod_xrd_core"
    assert record["rows"][0]["evidence"]["weighted_overlap_score"] == 0.83
    assert record["rows"][0]["evidence"]["matched_peak_pairs"][0]["observed_index"] == 0
    assert record["review"]["caution"] == {}
    assert record["scientific_context"]["methodology"]["library_context"]["provider"] == "COD"
    assert record["scientific_context"]["methodology"]["library_context"]["request_id"] == "libreq_xrd_001"
    assert record["scientific_context"]["fit_quality"]["confidence_band"] == "medium"


def test_serialize_xrd_result_adds_no_match_caution_semantics():
    dataset = _xrd_dataset()
    processing = ensure_processing_payload(analysis_type="XRD", workflow_template="xrd.general")

    record = serialize_xrd_result(
        "synthetic_xrd",
        dataset,
        summary={
            "peak_count": 4,
            "match_status": "no_match",
            "candidate_count": 1,
            "top_phase_id": None,
            "top_phase": None,
            "top_phase_score": 0.33,
            "confidence_band": "no_match",
        },
        rows=[
            {
                "rank": 1,
                "candidate_id": "xrd_phase_alpha",
                "candidate_name": "Phase Alpha",
                "normalized_score": 0.33,
                "confidence_band": "no_match",
                "evidence": {
                    "shared_peak_count": 0,
                    "weighted_overlap_score": 0.12,
                    "mean_delta_position": None,
                    "unmatched_major_peak_count": 3,
                    "tolerance_deg": 0.28,
                },
            }
        ],
        processing=processing,
        validation={"status": "warn", "issues": [], "warnings": ["XRD no-match caution."]},
    )

    assert record["summary"]["match_status"] == "no_match"
    assert record["summary"]["caution_code"] == "xrd_no_match"
    assert record["summary"]["top_candidate_id"] == "xrd_phase_alpha"
    assert record["summary"]["top_candidate_name"] == "Phase Alpha"
    assert record["summary"]["top_candidate_score"] == 0.33
    assert record["summary"]["top_candidate_weighted_overlap_score"] == 0.12
    assert record["summary"]["top_candidate_reason_below_threshold"]
    assert record["review"]["caution"]["code"] == "xrd_no_match"
    assert record["review"]["caution"]["top_candidate_name"] == "Phase Alpha"
    assert any("no-match" in item.lower() for item in record["scientific_context"]["limitations"])
    assert record["scientific_context"]["fit_quality"]["top_candidate_score"] == 0.33
