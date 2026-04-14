from __future__ import annotations

import pandas as pd

from core.data_io import ThermalDataset
from core.peak_analysis import ThermalPeak
from core.processing_schema import ensure_processing_payload, update_method_context, update_processing_step
from core.result_serialization import (
    collect_figure_keys,
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
    assert record["summary"]["display_name"] == "Synthetic DTA Run"
    assert record["summary"]["sample_mass"] == 5.0
    assert record["summary"]["heating_rate"] == 10.0
    assert record["summary"]["exotherm_count"] == 1
    assert record["summary"]["endotherm_count"] == 0
    assert record["rows"][0]["direction"] == "exo"
    assert record["rows"][0]["peak_type"] == "exo"
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
    record.pop("report_payload", None)

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
    assert valid["demo_result"]["report_payload"] == {}


def test_flatten_result_records_emits_scientific_context_section():
    record = _base_record()
    record["scientific_context"] = {
        "methodology": {"workflow_template": "General DSC"},
        "equations": [{"name": "Energy", "formula": "DeltaH=int(q dT)"}],
    }
    record["report_payload"] = {"appendix_note": "demo"}

    flat_rows = flatten_result_records({"demo_result": record})

    assert any(row["section"] == "scientific_context" and row["field"] == "methodology" for row in flat_rows)
    assert any(row["section"] == "scientific_context" and row["field"] == "equations" for row in flat_rows)
    assert any(row["section"] == "report_payload" and row["field"] == "appendix_note" for row in flat_rows)


def test_split_valid_results_backfills_extended_literature_context_fields():
    record = _base_record()
    record["literature_context"] = {
        "mode": "metadata_abstract_oa_only",
        "comparison_run_id": "litcmp_demo_001",
        "provider_scope": ["fixture_provider"],
        "query_count": 2,
        "restricted_content_used": False,
    }

    valid, issues = split_valid_results({"demo_result": record})

    assert issues == []
    context = valid["demo_result"]["literature_context"]
    assert context["comparison_run_id"] == "litcmp_demo_001"
    assert context["provider_scope"] == ["fixture_provider"]
    assert context["provider_request_ids"] == []
    assert context["provider_result_source"] == ""
    assert context["source_count"] == 0
    assert context["citation_count"] == 0
    assert context["accessible_source_count"] == 0
    assert context["restricted_source_count"] == 0
    assert context["metadata_only_evidence"] is False
    assert context["generated_at_utc"] == ""


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
    claim_text = " ".join(item.get("claim", "") for item in record["scientific_context"]["scientific_claims"])
    assert "not specialized for this analysis type yet" not in claim_text.lower()
    assert record["scientific_context"]["scientific_claims"]
    assert record["scientific_context"]["evidence_map"]
    assert record["scientific_context"]["uncertainty_assessment"]["items"]
    assert record["scientific_context"]["alternative_hypotheses"]
    assert record["scientific_context"]["next_experiments"]
    assert "qualitative phase screening" in claim_text.lower() or "xrd" in claim_text.lower()


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
    assert "screening only" in record["report_payload"]["xrd_reference_dossiers"][0]["match_evidence"]["caution_note"].lower()
    assert any("no-match" in item.lower() for item in record["scientific_context"]["limitations"])
    assert record["scientific_context"]["fit_quality"]["top_candidate_score"] == 0.33
    claim_text = " ".join(item.get("claim", "") for item in record["scientific_context"]["scientific_claims"]).lower()
    assert "generic" not in claim_text
    assert "no_match" in claim_text
    assert "definitive identification" not in claim_text


def test_serialize_xrd_result_adds_humanized_display_fields_without_losing_raw_ids():
    dataset = _xrd_dataset()
    processing = ensure_processing_payload(analysis_type="XRD", workflow_template="xrd.general")

    record = serialize_xrd_result(
        "synthetic_xrd",
        dataset,
        summary={
            "peak_count": 4,
            "match_status": "matched",
            "candidate_count": 1,
            "top_phase_id": "cod_1000026",
            "top_phase": "COD 1000026",
            "top_phase_score": 0.91,
            "confidence_band": "high",
            "library_provider": "COD",
        },
        rows=[
            {
                "rank": 1,
                "candidate_id": "cod_1000026",
                "candidate_name": "COD 1000026",
                "formula": "MgB2",
                "source_id": "1000026",
                "normalized_score": 0.91,
                "confidence_band": "high",
                "library_provider": "COD",
                "evidence": {
                    "shared_peak_count": 4,
                    "weighted_overlap_score": 0.91,
                    "mean_delta_position": 0.04,
                    "unmatched_major_peak_count": 0,
                    "tolerance_deg": 0.28,
                },
            }
        ],
        processing=processing,
        validation={"status": "pass", "issues": [], "warnings": []},
    )

    assert record["summary"]["top_candidate_name"] == "COD 1000026"
    assert record["summary"]["top_candidate_display_name"] == "MgB2"
    assert record["summary"]["top_candidate_display_name_unicode"] == "MgB₂"
    assert record["summary"]["top_phase_display_name"] == "MgB2"
    assert record["summary"]["top_phase_display_name_unicode"] == "MgB₂"
    assert record["rows"][0]["display_name"] == "MgB2"
    assert record["rows"][0]["source_id"] == "1000026"


def test_serialize_xrd_result_builds_reference_dossiers_with_truncated_peaks_and_preserves_raw_fields():
    dataset = _xrd_dataset()
    processing = ensure_processing_payload(analysis_type="XRD", workflow_template="xrd.general")

    peaks = [
        {
            "peak_number": idx + 1,
            "position": 10.0 + (idx * 1.1),
            "d_spacing": 4.0 - (idx * 0.05),
            "intensity": float(100 - idx),
        }
        for idx in range(25)
    ]
    rows = [
        {
            "rank": 1,
            "candidate_id": "cod_1000026",
            "candidate_name": "COD 1000026",
            "formula": "MgB2",
            "source_id": "1000026",
            "normalized_score": 0.91,
            "confidence_band": "high",
            "library_provider": "COD",
            "library_package": "cod_xrd_core",
            "library_version": "2026.03-core",
            "reference_metadata": {
                "provider_dataset_version": "2026.03",
                "hosted_dataset_version": "2026.03.fixture",
                "source_url": "https://example.test/cod/1000026",
                "provider_url": "https://provider.example.test/cod/1000026",
                "space_group": "P6/mmm",
                "symmetry": "hexagonal",
                "attribution": "COD reference dataset",
            },
            "reference_peaks": peaks,
            "source_assets": [
                {"kind": "source_url", "label": "Source Reference", "url": "https://example.test/cod/1000026", "available": True},
                {"kind": "source_url", "label": "Provider Reference", "url": "https://provider.example.test/cod/1000026", "available": True},
            ],
            "evidence": {
                "shared_peak_count": 6,
                "weighted_overlap_score": 0.91,
                "coverage_ratio": 0.81,
                "mean_delta_position": 0.03,
                "unmatched_major_peak_count": 0,
                "matched_peak_pairs": [{"observed_index": idx, "reference_index": idx} for idx in range(3)],
                "unmatched_observed_peaks": [],
                "unmatched_reference_peaks": [{"reference_index": 20, "is_major": True}],
            },
        },
        *[
            {
                "rank": idx,
                "candidate_id": f"xrd_phase_{idx}",
                "candidate_name": f"Phase {idx}",
                "normalized_score": 0.6 - (idx * 0.05),
                "confidence_band": "medium",
                "library_provider": "COD",
                "evidence": {"shared_peak_count": 2, "coverage_ratio": 0.2},
            }
            for idx in range(2, 5)
        ],
    ]

    record = serialize_xrd_result(
        "synthetic_xrd_dossier",
        dataset,
        summary={
            "peak_count": 4,
            "match_status": "matched",
            "candidate_count": 4,
            "top_phase_id": "cod_1000026",
            "top_phase": "COD 1000026",
            "top_phase_score": 0.91,
            "confidence_band": "high",
            "library_request_id": "libreq_xrd_dossier_001",
        },
        rows=rows,
        processing=processing,
        validation={"status": "pass", "issues": [], "warnings": []},
    )

    assert record["rows"][0]["candidate_name"] == "COD 1000026"
    assert record["rows"][0]["source_id"] == "1000026"
    assert record["report_payload"]["xrd_reference_dossier_limit"] == 3
    assert record["report_payload"]["xrd_reference_peak_display_limit"] == 20
    assert len(record["report_payload"]["xrd_reference_dossiers"]) == 3
    first_dossier = record["report_payload"]["xrd_reference_dossiers"][0]
    assert first_dossier["candidate_overview"]["display_name_unicode"] == "MgB₂"
    assert first_dossier["candidate_overview"]["formula_unicode"] == "MgB₂"
    assert first_dossier["provenance"]["raw_label"] == "COD 1000026"
    assert first_dossier["provenance"]["candidate_id"] == "cod_1000026"
    assert first_dossier["reference_metadata"]["source_url"] == "https://example.test/cod/1000026"
    assert first_dossier["reference_metadata"]["provider_url"] == "https://provider.example.test/cod/1000026"
    assert first_dossier["reference_peaks"]["displayed_peak_count"] == 20
    assert first_dossier["reference_peaks"]["total_peak_count"] == 25
    assert first_dossier["reference_peaks"]["truncated_count"] == 5
    assert first_dossier["structure_payload"]["provider_url"] == "https://provider.example.test/cod/1000026"
    assert first_dossier["source_assets"][1]["label"] == "Provider Reference"


def test_split_valid_results_rebuilds_stale_xrd_reference_dossiers_from_rows():
    dataset = _xrd_dataset()
    processing = ensure_processing_payload(analysis_type="XRD", workflow_template="xrd.general")
    peaks = [
        {
            "peak_number": idx + 1,
            "position": 10.0 + (idx * 1.1),
            "d_spacing": 4.0 - (idx * 0.05),
            "intensity": float(100 - idx),
        }
        for idx in range(25)
    ]
    record = serialize_xrd_result(
        "synthetic_xrd_stale_dossier",
        dataset,
        summary={
            "peak_count": 4,
            "match_status": "matched",
            "candidate_count": 1,
            "top_phase_id": "cod_1000026",
            "top_phase": "COD 1000026",
            "top_phase_score": 0.91,
            "confidence_band": "high",
            "library_request_id": "libreq_xrd_stale_001",
        },
        rows=[
            {
                "rank": 1,
                "candidate_id": "cod_1000026",
                "candidate_name": "COD 1000026",
                "formula": "MgB2",
                "source_id": "1000026",
                "normalized_score": 0.91,
                "confidence_band": "high",
                "library_provider": "COD",
                "library_package": "cod_xrd_core",
                "library_version": "2026.03-core",
                "reference_metadata": {
                    "source_url": "https://example.test/cod/1000026",
                    "provider_url": "https://provider.example.test/cod/1000026",
                    "space_group": "P6/mmm",
                    "symmetry": "hexagonal",
                },
                "reference_peaks": peaks,
                "source_assets": [
                    {
                        "kind": "source_url",
                        "label": "Source Reference",
                        "url": "https://example.test/cod/1000026",
                        "available": True,
                    },
                    {
                        "kind": "source_url",
                        "label": "Provider Reference",
                        "url": "https://provider.example.test/cod/1000026",
                        "available": True,
                    },
                ],
                "evidence": {
                    "shared_peak_count": 6,
                    "weighted_overlap_score": 0.91,
                    "coverage_ratio": 0.81,
                    "mean_delta_position": 0.03,
                    "unmatched_major_peak_count": 0,
                    "matched_peak_pairs": [{"observed_index": idx, "reference_index": idx} for idx in range(3)],
                    "unmatched_reference_peaks": [{"reference_index": 20, "is_major": True}],
                },
            }
        ],
        processing=processing,
        validation={"status": "pass", "issues": [], "warnings": []},
    )
    record["report_payload"] = {
        "xrd_reference_dossier_limit": 3,
        "xrd_reference_peak_display_limit": 20,
        "xrd_reference_dossiers": [
            {
                "rank": 1,
                "candidate_overview": {"display_name_unicode": "MgB₂"},
                "reference_peaks": {
                    "display_rows": [],
                    "displayed_peak_count": 0,
                    "total_peak_count": 0,
                    "truncated_count": 0,
                    "selection_policy": "matched_and_major_then_fill_to_top_20_by_intensity",
                },
                "reference_metadata": {"source_url": None, "provider_url": None},
                "structure_payload": {
                    "availability": "none",
                    "source_asset_count": 0,
                    "rendered_asset_count": 0,
                },
                "source_assets": [],
            }
        ],
    }

    valid, issues = split_valid_results({record["id"]: record})

    assert issues == []
    dossier = valid[record["id"]]["report_payload"]["xrd_reference_dossiers"][0]
    assert dossier["reference_peaks"]["displayed_peak_count"] == 20
    assert dossier["reference_peaks"]["total_peak_count"] == 25
    assert dossier["reference_peaks"]["truncated_count"] == 5
    assert dossier["reference_metadata"]["source_url"] == "https://example.test/cod/1000026"
    assert dossier["reference_metadata"]["provider_url"] == "https://provider.example.test/cod/1000026"
    assert len(dossier["source_assets"]) == 2
    assert dossier["structure_payload"]["source_asset_count"] == 2


def test_serialize_xrd_result_gates_stronger_scientific_claims_on_strong_evidence():
    dataset = _xrd_dataset()
    processing = ensure_processing_payload(analysis_type="XRD", workflow_template="xrd.general")

    record = serialize_xrd_result(
        "synthetic_xrd_strong_reasoning",
        dataset,
        summary={
            "peak_count": 4,
            "match_status": "matched",
            "candidate_count": 2,
            "top_phase_id": "cod_1000026",
            "top_phase": "COD 1000026",
            "top_phase_score": 0.93,
            "confidence_band": "high",
            "top_candidate_shared_peak_count": 5,
            "top_candidate_coverage_ratio": 0.82,
            "top_candidate_weighted_overlap_score": 0.88,
            "top_candidate_mean_delta_position": 0.03,
            "top_candidate_unmatched_major_peak_count": 0,
        },
        rows=[
            {
                "rank": 1,
                "candidate_id": "cod_1000026",
                "candidate_name": "COD 1000026",
                "formula": "MgB2",
                "source_id": "1000026",
                "normalized_score": 0.93,
                "confidence_band": "high",
                "library_provider": "COD",
                "evidence": {
                    "shared_peak_count": 5,
                    "coverage_ratio": 0.82,
                    "weighted_overlap_score": 0.88,
                    "mean_delta_position": 0.03,
                    "unmatched_major_peak_count": 0,
                },
            },
            {
                "rank": 2,
                "candidate_id": "xrd_phase_beta",
                "candidate_name": "Phase Beta",
                "normalized_score": 0.51,
                "confidence_band": "medium",
                "evidence": {"shared_peak_count": 2, "coverage_ratio": 0.31},
            },
        ],
        processing=processing,
        validation={"status": "pass", "issues": [], "warnings": []},
    )

    mechanistic_claims = [
        item for item in record["scientific_context"]["scientific_claims"]
        if str(item.get("strength") or "").lower() == "mechanistic"
    ]

    assert mechanistic_claims
    assert "follow-up verification" in mechanistic_claims[0]["claim"].lower()
    assert "confirmed" not in mechanistic_claims[0]["claim"].lower()


def test_collect_figure_keys_prefers_primary_report_figure_when_present():
    results = {
        "xrd_demo": {
            "id": "xrd_demo",
            "analysis_type": "XRD",
            "status": "stable",
            "dataset_key": "synthetic_xrd",
            "metadata": {},
            "summary": {},
            "rows": [],
            "artifacts": {
                "report_figure_key": "XRD Snapshot - synthetic_xrd - primary",
                "figure_keys": [
                    "XRD Snapshot - synthetic_xrd - old_1",
                    "XRD Snapshot - synthetic_xrd - old_2",
                ],
            },
        }
    }

    figure_keys = collect_figure_keys(results)

    assert figure_keys == ["XRD Snapshot - synthetic_xrd - primary"]
