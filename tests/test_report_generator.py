from __future__ import annotations

import copy
import csv
import io
import os
from pathlib import Path
import zipfile
from types import SimpleNamespace

import pandas as pd
import pytest

from core import report_generator
from core.data_io import ThermalDataset
from core.dsc_processor import GlassTransition
from core.peak_analysis import ThermalPeak
from core.processing_schema import (
    ensure_processing_payload,
    update_method_context,
    update_processing_step,
    update_tga_unit_context,
)
from core.provenance import build_calibration_reference_context
from core.report_generator import generate_csv_summary, generate_docx_report
from core.result_serialization import (
    serialize_dta_result,
    serialize_dsc_result,
    serialize_friedman_results,
    serialize_kissinger_result,
    serialize_ofw_results,
    serialize_spectral_result,
    serialize_tga_result,
    serialize_xrd_result,
)
from core.tga_processor import TGAProcessor, resolve_tga_unit_interpretation
from core.validation import validate_thermal_dataset


def _make_peak() -> ThermalPeak:
    return ThermalPeak(
        peak_index=10,
        peak_temperature=231.9,
        peak_signal=2.0,
        onset_temperature=228.0,
        endset_temperature=236.0,
        area=12.3,
        fwhm=4.5,
        peak_type="endotherm",
        height=1.9,
    )


def _make_tg() -> GlassTransition:
    return GlassTransition(
        tg_midpoint=120.0,
        tg_onset=115.0,
        tg_endset=125.0,
        delta_cp=0.12,
    )


def _make_kissinger():
    return serialize_kissinger_result(
        SimpleNamespace(
            activation_energy=123.4,
            r_squared=0.998,
            pre_exponential=12.0,
            plot_data={},
        ),
        processing={"method": "Kissinger"},
        provenance={"saved_at_utc": "2026-03-07T12:00:00+00:00"},
        validation={"status": "pass", "issues": [], "warnings": []},
        review={"commercial_scope": "preview_kinetics"},
    )


def _make_ofw():
    rows = [
        SimpleNamespace(activation_energy=110.0, r_squared=0.99, plot_data={"alpha": 0.2}),
        SimpleNamespace(activation_energy=112.0, r_squared=0.98, plot_data={"alpha": 0.4}),
    ]
    return serialize_ofw_results(rows, processing={"method": "Ozawa-Flynn-Wall"})


def _make_friedman():
    rows = [
        SimpleNamespace(activation_energy=118.0, pre_exponential=27.0, r_squared=0.995, plot_data={"alpha": 0.2}),
        SimpleNamespace(activation_energy=121.0, pre_exponential=28.0, r_squared=0.985, plot_data={"alpha": 0.4}),
    ]
    return serialize_friedman_results(rows, processing={"method": "Friedman"})


def _make_dsc_record(thermal_dataset):
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
    processing = update_processing_step(
        processing,
        "smoothing",
        {"method": "savgol", "window_length": 11, "polyorder": 3},
    )
    processing = update_processing_step(
        processing,
        "baseline",
        {"method": "asls"},
    )
    processing = update_processing_step(
        processing,
        "glass_transition",
        {"region": [90.0, 150.0], "event_count": 1},
    )
    processing = update_processing_step(
        processing,
        "peak_detection",
        {"direction": "both", "peak_count": 1},
    )
    calibration_context = build_calibration_reference_context(
        dataset=dataset,
        analysis_type="DSC",
        reference_temperature_c=_make_peak().peak_temperature,
    )
    processing = update_method_context(processing, calibration_context, analysis_type="DSC")
    validation = validate_thermal_dataset(dataset, analysis_type="DSC", processing=processing)

    return serialize_dsc_result(
        "synthetic_dsc",
        dataset,
        [_make_peak()],
        glass_transitions=[_make_tg()],
        artifacts={"figure_keys": ["DSC Analysis - synthetic_dsc"]},
        processing=processing,
        provenance={
            "saved_at_utc": "2026-03-07T12:00:00+00:00",
            "source_data_hash": dataset.metadata.get("source_data_hash", "abc"),
            "app_version": "2.0",
            "recent_event_ids": ["evt-import", "evt-dsc-save"],
            "calibration_state": calibration_context["calibration_state"],
            "reference_state": calibration_context["reference_state"],
            "reference_name": calibration_context.get("reference_name"),
            "reference_delta_c": calibration_context.get("reference_delta_c"),
        },
        validation=validation,
        review={"commercial_scope": "stable_dsc"},
    )


def _make_tga_record(temperature_range, tga_percent_signal):
    dataset = ThermalDataset(
        data=pd.DataFrame({"temperature": temperature_range, "signal": tga_percent_signal}),
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
        units={"temperature": "degC", "signal": ""},
        original_columns={"temperature": "temperature", "signal": "signal"},
        file_path="",
    )
    processing = ensure_processing_payload(
        analysis_type="TGA",
        workflow_template="tga.single_step_decomposition",
        workflow_template_label="Single-Step Decomposition",
    )
    processing = update_processing_step(
        processing,
        "smoothing",
        {"method": "savgol", "window_length": 11, "polyorder": 3},
    )
    processing = update_processing_step(
        processing,
        "step_detection",
        {"method": "dtg_peaks", "prominence": 0.1, "min_mass_loss": 0.5},
    )
    unit_context = resolve_tga_unit_interpretation(
        tga_percent_signal,
        unit_mode="auto",
        signal_unit="",
        initial_mass_mg=dataset.metadata["sample_mass"],
    )
    processing = update_tga_unit_context(processing, unit_context)
    result = TGAProcessor(
        temperature_range,
        tga_percent_signal,
        initial_mass_mg=dataset.metadata["sample_mass"],
        unit_mode=str(unit_context["resolved_unit_mode"]),
    ).process()
    calibration_context = build_calibration_reference_context(
        dataset=dataset,
        analysis_type="TGA",
        reference_temperature_c=result.steps[0].midpoint_temperature if result.steps else None,
    )
    processing = update_method_context(processing, calibration_context, analysis_type="TGA")
    validation = validate_thermal_dataset(dataset, analysis_type="TGA", processing=processing)

    record = serialize_tga_result(
        "synthetic_tga",
        dataset,
        result,
        artifacts={},
        processing=processing,
        provenance={
            "saved_at_utc": "2026-03-07T12:00:00+00:00",
            "source_data_hash": dataset.metadata["source_data_hash"],
            "app_version": "2.0",
            "tga_unit_mode_declared": unit_context["declared_unit_mode"],
            "tga_unit_mode_resolved": unit_context["resolved_unit_mode"],
            "tga_unit_auto_inference_used": unit_context["auto_inference_used"],
        },
        validation=validation,
        review={"commercial_scope": "stable_tga"},
    )
    return record, dataset


def _make_dta_record(thermal_dataset):
    dataset = thermal_dataset.copy()
    dataset.data_type = "DTA"
    dataset.units["signal"] = "uV"
    dataset.metadata.update(
        {
            "sample_name": "SyntheticDTA",
            "display_name": "Synthetic DTA Run",
            "vendor": "TestVendor",
        }
    )
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
    validation = validate_thermal_dataset(dataset, analysis_type="DTA", processing=processing)
    peak = _make_peak()
    try:
        object.__setattr__(peak, "direction", "exo")
    except Exception:
        pass

    return serialize_dta_result(
        "synthetic_dta",
        dataset,
        [peak],
        artifacts={"figure_keys": ["DTA Analysis - synthetic_dta"]},
        processing=processing,
        provenance={"saved_at_utc": "2026-03-07T12:10:00+00:00", "app_version": "2.0"},
        validation=validation,
        review={"commercial_scope": "stable_dta"},
    ), dataset


def _make_ftir_no_match_record():
    dataset = ThermalDataset(
        data=pd.DataFrame({"temperature": [650.0, 980.0, 1450.0], "signal": [0.08, 0.52, 0.18]}),
        metadata={
            "sample_name": "SyntheticFTIR",
            "sample_mass": 1.0,
            "heating_rate": 1.0,
            "instrument": "SpecBench",
            "vendor": "TestVendor",
            "display_name": "Synthetic FTIR Spectrum",
        },
        data_type="FTIR",
        units={"temperature": "cm^-1", "signal": "a.u."},
        original_columns={"temperature": "wavenumber", "signal": "intensity"},
        file_path="",
    )
    processing = ensure_processing_payload(
        analysis_type="FTIR",
        workflow_template="ftir.general",
        workflow_template_label="General FTIR",
    )
    processing = update_processing_step(processing, "normalization", {"method": "vector"})
    processing = update_processing_step(processing, "peak_detection", {"prominence": 0.05, "min_distance": 6})
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
            "top_match_score": 0.33,
            "confidence_band": "no_match",
            "caution_code": "spectral_no_match",
            "library_access_mode": "cloud_full_access",
            "library_request_id": "libreq_report_ftir_001",
            "library_result_source": "cloud_search",
            "library_provider_scope": ["openspecy"],
            "library_offline_limited_mode": False,
        },
        rows=[
            {
                "rank": 1,
                "candidate_id": "ftir_ref_unknown",
                "candidate_name": "Unknown",
                "normalized_score": 0.33,
                "confidence_band": "no_match",
                "evidence": {"shared_peak_count": 0, "peak_overlap_ratio": 0.0},
            }
        ],
        artifacts={"figure_keys": ["FTIR Analysis - synthetic_ftir"]},
        processing=processing,
        provenance={"saved_at_utc": "2026-03-12T02:00:00+00:00", "app_version": "2.0"},
        validation={
            "status": "warn",
            "issues": [],
            "warnings": ["FTIR produced no confident library match; treat this as cautionary."],
            "checks": {"caution_state_output": "no_match"},
        },
        review={"commercial_scope": "stable_ftir", "batch_runner": "compare_workspace"},
    )
    return record, dataset


def _make_xrd_no_match_record():
    dataset = ThermalDataset(
        data=pd.DataFrame({"temperature": [18.2, 27.5, 36.1, 44.8], "signal": [130.0, 290.0, 175.0, 120.0]}),
        metadata={
            "sample_name": "SyntheticXRD",
            "sample_mass": 1.0,
            "instrument": "XRDBench",
            "vendor": "TestVendor",
            "display_name": "Synthetic XRD Pattern",
            "xrd_axis_role": "two_theta",
            "xrd_axis_unit": "degree_2theta",
        },
        data_type="XRD",
        units={"temperature": "degree_2theta", "signal": "counts"},
        original_columns={"temperature": "two_theta", "signal": "intensity"},
        file_path="",
    )
    processing = ensure_processing_payload(
        analysis_type="XRD",
        workflow_template="xrd.general",
        workflow_template_label="General XRD",
    )
    processing = update_processing_step(processing, "axis_normalization", {"axis_min": 10.0, "axis_max": 80.0})
    processing = update_processing_step(processing, "peak_detection", {"method": "scipy_find_peaks", "prominence": 0.08, "distance": 6})
    processing = update_method_context(
        processing,
        {
            "xrd_match_metric": "peak_overlap_weighted",
            "xrd_match_tolerance_deg": 0.28,
            "xrd_match_minimum_score": 0.42,
            "xrd_match_top_n": 5,
        },
        analysis_type="XRD",
    )

    record = serialize_xrd_result(
        "synthetic_xrd",
        dataset,
        summary={
            "peak_count": 4,
            "match_status": "no_match",
            "candidate_count": 1,
            "reference_candidate_count": 6,
            "top_phase_id": None,
            "top_phase": None,
            "top_phase_score": 0.33,
            "confidence_band": "no_match",
            "caution_code": "xrd_no_match",
            "caution_message": (
                "No candidate exceeded threshold; qualitative caution required. "
                "Hosted coverage note: XRD hosted coverage is still seed/dev sized."
            ),
            "library_access_mode": "cloud_full_access",
            "library_request_id": "libreq_report_xrd_001",
            "library_result_source": "cloud_search",
            "library_provider_scope": ["cod", "materials_project"],
            "library_offline_limited_mode": False,
            "xrd_provider_candidate_counts": {"cod": 4, "materials_project": 2},
            "xrd_coverage_tier": "seed_dev",
            "xrd_coverage_warning_message": (
                "XRD hosted coverage is still seed/dev sized (6 candidates across 2 providers). "
                "Cloud matching is online, but no-match outcomes can still reflect insufficient corpus depth."
            ),
            "xrd_provenance_state": "incomplete",
            "xrd_provenance_warning": (
                "XRD wavelength is not recorded; qualitative phase matching provenance remains incomplete."
            ),
            "top_candidate_weighted_overlap_score": 0.11,
            "top_candidate_coverage_ratio": 0.08,
            "top_candidate_unmatched_major_peak_count": 3,
        },
        rows=[
            {
                "rank": 1,
                "candidate_id": "xrd_phase_alpha",
                "candidate_name": "Phase Alpha",
                "source_id": "alpha-001",
                "normalized_score": 0.33,
                "confidence_band": "no_match",
                "library_provider": "COD",
                "library_package": "cod_xrd_core",
                "library_version": "2026.03-core",
                "reference_metadata": {
                    "source_url": "https://example.test/xrd/alpha-001",
                    "provider_url": "https://provider.example.test/cod/alpha-001",
                    "provider_dataset_version": "2026.03",
                    "hosted_dataset_version": "2026.03.fixture",
                    "space_group": "P6/mmm",
                    "symmetry": "hexagonal",
                    "attribution": "Hosted XRD seed dataset",
                },
                "reference_peaks": [
                    {"peak_number": idx + 1, "position": 18.0 + (idx * 0.42), "d_spacing": 4.8 - (idx * 0.05), "intensity": 100 - idx}
                    for idx in range(25)
                ],
                "source_assets": [
                    {"kind": "source_url", "label": "Source Reference", "url": "https://example.test/xrd/alpha-001", "available": True},
                    {"kind": "source_url", "label": "Provider Reference", "url": "https://provider.example.test/cod/alpha-001", "available": True},
                ],
                "evidence": {
                    "shared_peak_count": 0,
                    "weighted_overlap_score": 0.11,
                    "mean_delta_position": None,
                    "unmatched_major_peak_count": 3,
                    "tolerance_deg": 0.28,
                    "matched_peak_pairs": [{"observed_index": 0, "reference_index": 0}],
                },
            }
        ],
        artifacts={"figure_keys": ["XRD Analysis - synthetic_xrd"]},
        processing=processing,
        provenance={"saved_at_utc": "2026-03-12T02:00:00+00:00", "app_version": "2.0"},
        validation={
            "status": "warn",
            "issues": [],
            "warnings": ["XRD no-match output is cautionary."],
            "checks": {"caution_state_output": "no_match"},
        },
        review={"commercial_scope": "stable_xrd", "batch_runner": "compare_workspace"},
    )
    return record, dataset


def test_generate_docx_report_returns_docx_bytes(thermal_dataset):
    docx_bytes = generate_docx_report(results={}, datasets={"synthetic_dsc": thermal_dataset})
    assert isinstance(docx_bytes, bytes)
    assert docx_bytes[:4] == b"PK\x03\x04"


def test_generate_docx_report_renders_method_validation_and_provenance_sections(thermal_dataset, temperature_range, tga_percent_signal):
    dsc_record = _make_dsc_record(thermal_dataset)
    tga_record, tga_dataset = _make_tga_record(temperature_range, tga_percent_signal)
    kissinger_record = _make_kissinger()

    docx_bytes = generate_docx_report(
        results={
            dsc_record["id"]: dsc_record,
            tga_record["id"]: tga_record,
            kissinger_record["id"]: kissinger_record,
        },
        datasets={"synthetic_dsc": thermal_dataset, "synthetic_tga": tga_dataset},
        branding={"report_notes": "Batch remains within envelope."},
        comparison_workspace={
            "analysis_type": "DSC",
            "selected_datasets": ["synthetic_dsc"],
            "notes": "Overlay saved for review.",
            "figure_key": "Comparison Workspace - DSC",
            "batch_run_id": "batch_dsc_20260307_demo",
            "batch_template_id": "dsc.polymer_tg",
            "batch_template_label": "Polymer Tg",
            "batch_completed_at": "2026-03-07T13:00:00",
            "batch_summary": [
                {
                    "dataset_key": "synthetic_dsc",
                    "sample_name": "SyntheticDSC",
                    "workflow_template": "Polymer Tg",
                    "execution_status": "saved",
                    "validation_status": "pass",
                    "calibration_state": "calibrated",
                    "reference_state": "reference_checked",
                    "result_id": "dsc_synthetic_dsc",
                    "error_id": "",
                    "failure_reason": "",
                },
                {
                    "dataset_key": "blocked_dsc",
                    "sample_name": "Blocked DSC",
                    "workflow_template": "Polymer Tg",
                    "execution_status": "blocked",
                    "validation_status": "fail",
                    "calibration_state": "missing_calibration",
                    "reference_state": "not_recorded",
                    "result_id": "",
                    "error_id": "TA-DSC-20260307123400-AAAAAA",
                    "failure_reason": "Dataset blocked by validation.",
                },
                {
                    "dataset_key": "failed_dsc",
                    "sample_name": "Failed DSC",
                    "workflow_template": "Polymer Tg",
                    "execution_status": "failed",
                    "validation_status": "not_run",
                    "calibration_state": "unknown",
                    "reference_state": "not_run",
                    "result_id": "",
                    "error_id": "TA-DSC-20260307123400-BBBBBB",
                    "failure_reason": "Processor exploded.",
                }
            ],
        },
    )

    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    assert "Executive Summary" in xml
    assert xml.index("Executive Summary") < xml.index("Experimental Conditions")
    assert "This report summarizes" in xml
    assert "Comparison Overview" in xml
    assert "Comparison Interpretation" in xml
    assert "Methodology" in xml
    assert "Equations and Formulation" in xml
    assert "Scientific Interpretation" in xml
    assert "Numerical Interpretation" not in xml
    assert "Fit Quality" in xml
    assert "Warnings and Limitations" in xml
    assert "Data Completeness Warnings" in xml
    assert "Methodological Limitations" in xml
    assert "Sign Convention" in xml
    assert "Reference Check" in xml
    assert "Tin (Sn)" in xml
    assert "Major Decomposition Events" in xml
    assert "Full Raw Data Table" in xml
    assert "Final Conclusion" in xml
    assert "Appendix A" in xml
    assert "Batch remains within envelope." in xml

    appendix_index = xml.index("Appendix A")
    assert xml.index("Source Data Hash") > appendix_index
    assert xml.index("Batch Run ID") > appendix_index
    assert xml.index("Full Raw Data Table") > appendix_index
    if "Dataset Key" in xml:
        assert xml.index("Dataset Key") > appendix_index
    if "Import Confidence" in xml:
        assert xml.index("Import Confidence") > appendix_index


def test_generate_docx_report_renders_tga_comparison_interpretation(temperature_range, tga_percent_signal):
    first_record, first_dataset = _make_tga_record(temperature_range, tga_percent_signal)
    second_dataset = copy.deepcopy(first_dataset)
    second_dataset.metadata["display_name"] = "Pending Metrics Run"
    second_dataset.metadata["atmosphere"] = ""

    docx_bytes = generate_docx_report(
        results={first_record["id"]: first_record},
        datasets={"synthetic_tga": first_dataset, "synthetic_tga_b": second_dataset},
        comparison_workspace={
            "analysis_type": "TGA",
            "selected_datasets": ["synthetic_tga", "synthetic_tga_b"],
            "figure_key": "Comparison Workspace - TGA",
        },
    )

    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    assert "Comparison Overview" in xml
    assert "Comparison Interpretation" in xml
    assert "only Synthetic TGA Run produced reportable TGA summary metrics" in xml
    assert "total mass loss" in xml
    assert "Excluded from metric comparison" in xml
    assert "partial rather than comprehensive" in xml


def test_generate_docx_report_suppresses_empty_experimental_section(thermal_dataset):
    dsc_record = _make_dsc_record(thermal_dataset)
    docx_bytes = generate_docx_report(
        results={dsc_record["id"]: dsc_record},
        datasets={"synthetic_dsc": thermal_dataset},
    )

    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    assert "Experimental Analyses" not in xml
    assert "No experimental analysis results available." not in xml


def test_generate_docx_report_places_stable_dta_in_stable_section(thermal_dataset):
    dta_record, dta_dataset = _make_dta_record(thermal_dataset)
    docx_bytes = generate_docx_report(
        results={dta_record["id"]: dta_record},
        datasets={"synthetic_dta": dta_dataset},
    )

    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    assert "Stable Analyses" in xml
    assert "DTA - synthetic_dta" in xml
    assert "outside the stable workflow guarantee" not in xml
    assert "DTA module is experimental and outside stable reporting guarantees." not in xml


def test_generate_docx_report_renders_ftir_no_match_caution_fields():
    ftir_record, ftir_dataset = _make_ftir_no_match_record()
    docx_bytes = generate_docx_report(
        results={ftir_record["id"]: ftir_record},
        datasets={"synthetic_ftir": ftir_dataset},
    )

    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    assert "FTIR - synthetic_ftir" in xml
    assert "Match Status" in xml
    assert "no_match" in xml
    assert "Caution Code" in xml
    assert "spectral_no_match" in xml
    assert "Confidence Band" in xml
    assert "Library Result Source" in xml
    assert "cloud_search" in xml


def test_generate_docx_report_renders_ftir_literature_sections():
    ftir_record, ftir_dataset = _make_ftir_no_match_record()
    ftir_record["literature_context"] = {
        "analysis_type": "FTIR",
        "provider_scope": ["openalex_like_provider"],
        "provider_request_ids": ["openalex_req_ftir_001"],
        "query_text": "\"cellulose\" FTIR band assignment qualitative interpretation",
        "query_rationale": "The FTIR literature search is centered on the leading band-pattern interpretation.",
        "real_literature_available": True,
        "restricted_content_used": False,
    }
    ftir_record["literature_claims"] = [
        {
            "claim_id": "C1",
            "claim_text": "The FTIR result suggests a cellulose-like band pattern that remains qualitative.",
        }
    ]
    ftir_record["literature_comparisons"] = [
        {
            "claim_id": "C1",
            "claim_text": "The FTIR result suggests a cellulose-like band pattern that remains qualitative.",
            "support_label": "related_but_inconclusive",
            "confidence": "low",
            "rationale": "Accessible literature discusses a similar FTIR band pattern, but the assignment remains non-confirmatory.",
            "citation_ids": ["ref_ftir_001"],
        }
    ]
    ftir_record["citations"] = [
        {
            "citation_id": "ref_ftir_001",
            "title": "Cellulose FTIR band assignments",
            "authors": ["A. Author"],
            "journal": "Journal of Spectroscopy",
            "year": 2024,
            "doi": "10.1000/ftir-cellulose",
            "url": "https://doi.org/10.1000/ftir-cellulose",
            "access_class": "open_access_full_text",
            "available_fields": ["metadata", "abstract", "oa_full_text"],
            "source_license_note": "open_access",
            "provenance": {
                "provider_id": "openalex_like_provider",
                "request_id": "openalex_req_ftir_001",
                "result_source": "openalex_api",
                "provider_scope": ["openalex_like_provider"],
                "provider_request_ids": ["openalex_req_ftir_001"],
            },
        }
    ]

    docx_bytes = generate_docx_report(
        results={ftir_record["id"]: ftir_record},
        datasets={"synthetic_ftir": ftir_dataset},
    )

    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    assert "Literature Comparison" in xml
    assert "Supporting References" in xml
    assert "Cellulose FTIR band assignments" in xml
    assert "Recommended Follow-Up Literature Checks" in xml


def test_generate_docx_report_renders_xrd_no_match_caution_fields():
    xrd_record, xrd_dataset = _make_xrd_no_match_record()
    docx_bytes = generate_docx_report(
        results={xrd_record["id"]: xrd_record},
        datasets={"synthetic_xrd": xrd_dataset},
    )

    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    assert "XRD - synthetic_xrd" in xml
    assert "Accepted Match Status" in xml
    assert "no_match" in xml
    assert "Best Candidate" in xml
    assert "Phase Alpha" in xml
    assert "Best Candidate Score" in xml
    assert "Shared Peaks" in xml
    assert "Weighted Overlap Score" in xml
    assert "Caution Code" in xml
    assert "xrd_no_match" in xml
    assert "Library Result Source" in xml
    assert "cloud_search" in xml
    assert "Library Access Mode" in xml
    assert "cloud_full_access" in xml
    assert "Match Metric" in xml
    assert "Provider Candidate Counts" in xml
    assert "cod=4.0000" in xml
    assert "materials_project=2.0000" in xml
    assert "Xrd Coverage Tier" in xml
    assert "seed_dev" in xml
    assert "Xrd Coverage Warning" in xml
    assert "seed/dev sized" in xml
    assert "Xrd Provenance State" in xml
    assert "incomplete" in xml
    assert "Xrd Provenance Warning" in xml
    assert "qualitative phase matching provenance remains incomplete" in xml
    assert "qualitative caution" in xml


def test_record_key_results_uses_humanized_xrd_display_name():
    payload = report_generator._record_key_results(
        {
            "analysis_type": "XRD",
            "summary": {
                "match_status": "matched",
                "top_phase": "COD 1000026",
                "top_phase_id": "cod_1000026",
                "top_candidate_name": "COD 1000026",
                "top_candidate_id": "cod_1000026",
                "top_candidate_formula": "MgB2",
                "top_candidate_source_id": "1000026",
                "top_candidate_provider": "COD",
                "top_candidate_score": 0.91,
            },
        }
    )

    assert payload["Best Candidate"] == "MgB₂"


def test_generate_docx_report_keeps_xrd_library_dump_out_of_main_body():
    xrd_record, xrd_dataset = _make_xrd_no_match_record()
    docx_bytes = generate_docx_report(
        results={xrd_record["id"]: xrd_record},
        datasets={"synthetic_xrd": xrd_dataset},
    )

    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    appendix_index = xml.index("Appendix A")
    main_xml = xml[:appendix_index]
    appendix_xml = xml[appendix_index:]

    assert "Best Candidate" in main_xml
    assert "Confidence Band" in main_xml
    assert "Shared Peaks" in main_xml
    assert "Coverage Ratio" in main_xml
    assert "Library Result Source" not in main_xml
    assert "Library Access Mode" not in main_xml
    assert "Provider Candidate Counts" not in main_xml
    assert "Xrd Coverage Tier" not in main_xml
    assert "Xrd Provenance State" not in main_xml
    assert "Library Result Source" in appendix_xml
    assert "Library Access Mode" in appendix_xml
    assert "Provider Candidate Counts" in appendix_xml
    assert "Xrd Coverage Tier" in appendix_xml
    assert "Xrd Provenance State" in appendix_xml


def test_generate_docx_report_uses_xrd_candidate_summary_table_and_keeps_evidence_detail_in_appendix():
    xrd_record, xrd_dataset = _make_xrd_no_match_record()
    xrd_record["rows"][0]["evidence"] = {
        "shared_peak_count": 7,
        "weighted_overlap_score": 0.31,
        "coverage_ratio": 0.22,
        "mean_delta_position": 0.14,
        "unmatched_major_peak_count": 3,
        "matched_peak_pairs": [{"observed_index": idx, "reference_index": idx} for idx in range(12)],
        "unmatched_observed_peaks": [{"observed_index": idx} for idx in range(5)],
        "unmatched_reference_peaks": [{"reference_index": idx} for idx in range(4)],
    }
    docx_bytes = generate_docx_report(
        results={xrd_record["id"]: xrd_record},
        datasets={"synthetic_xrd": xrd_dataset},
    )

    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    appendix_index = xml.index("Appendix A")
    main_xml = xml[:appendix_index]
    appendix_xml = xml[appendix_index:]

    assert "Top Candidates" in main_xml
    assert "matched_peak_pairs" not in main_xml
    assert "Candidate Evidence Summary" in appendix_xml
    assert "Full Raw Data Table" in appendix_xml
    assert "matched_peak_pairs=12" in appendix_xml


def test_generate_docx_report_uses_scientific_xrd_candidate_names():
    dataset = ThermalDataset(
        data=pd.DataFrame({"temperature": [18.2, 27.5, 36.1], "signal": [130.0, 290.0, 175.0]}),
        metadata={
            "sample_name": "SyntheticXRD",
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
    processing = ensure_processing_payload(
        analysis_type="XRD",
        workflow_template="xrd.general",
        workflow_template_label="General XRD",
    )
    processing = update_method_context(
        processing,
        {
            "xrd_match_metric": "peak_overlap_weighted",
            "xrd_match_tolerance_deg": 0.28,
            "xrd_match_minimum_score": 0.42,
            "xrd_match_top_n": 5,
        },
        analysis_type="XRD",
    )
    record = serialize_xrd_result(
        "synthetic_xrd_formula",
        dataset,
        summary={
            "peak_count": 3,
            "match_status": "matched",
            "candidate_count": 1,
            "top_phase": "COD 1000026",
            "top_phase_id": "cod_1000026",
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
                "library_package": "cod_xrd_core",
                "library_version": "2026.03-core",
                "reference_metadata": {
                    "source_url": "https://example.test/cod/1000026",
                    "provider_url": "https://provider.example.test/cod/1000026",
                    "provider_dataset_version": "2026.03",
                    "space_group": "P6/mmm",
                    "symmetry": "hexagonal",
                    "attribution": "COD reference dataset",
                },
                "reference_peaks": [
                    {"peak_number": idx + 1, "position": 27.5 + (idx * 0.37), "d_spacing": 3.24 - (idx * 0.04), "intensity": 100.0 - idx}
                    for idx in range(25)
                ],
                "source_assets": [
                    {"kind": "source_url", "label": "Source Reference", "url": "https://example.test/cod/1000026", "available": True},
                    {"kind": "source_url", "label": "Provider Reference", "url": "https://provider.example.test/cod/1000026", "available": True},
                ],
                "evidence": {
                    "shared_peak_count": 3,
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

    docx_bytes = generate_docx_report(
        results={record["id"]: record},
        datasets={"synthetic_xrd_formula": dataset},
    )

    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    assert "MgB₂" in xml
    assert "Candidate Reference Dossier" in xml
    assert "Rank #1" in xml
    assert "https://example.test/cod/1000026" in xml
    assert "https://provider.example.test/cod/1000026" in xml
    assert "Linked Source and Provider Assets" in xml
    assert "Showing 20 of 25 reference peaks" in xml
    assert "Remaining peaks omitted from visible table by display policy" in xml


def test_generate_docx_report_adds_xrd_reference_dossier_sections_with_caution_safe_wording():
    xrd_record, xrd_dataset = _make_xrd_no_match_record()

    docx_bytes = generate_docx_report(
        results={xrd_record["id"]: xrd_record},
        datasets={"synthetic_xrd": xrd_dataset},
    )

    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    appendix_index = xml.index("Appendix A")
    appendix_xml = xml[appendix_index:]

    assert "Candidate Reference Dossier" in appendix_xml
    assert "Rank #1" in appendix_xml
    assert "Candidate Overview" in appendix_xml
    assert "Match Evidence Summary" in appendix_xml
    assert "Reference Metadata" in appendix_xml
    assert "Reference Peaks" in appendix_xml
    assert "Structure / Visual Evidence" in appendix_xml
    assert "Provenance / Attribution" in appendix_xml
    assert "alpha-001" in appendix_xml
    assert "https://example.test/xrd/alpha-001" in appendix_xml
    assert "https://provider.example.test/cod/alpha-001" in appendix_xml
    assert "Linked Source and Provider Assets" in appendix_xml
    assert "Showing 20 of 25 reference peaks" in appendix_xml
    assert "Remaining peaks omitted from visible table by display policy" in appendix_xml
    assert "P6/mmm" in appendix_xml
    assert "hexagonal" in appendix_xml
    assert "screening only" in appendix_xml.lower()
    assert "Structure metadata and traceable source links are provided for follow-up review." in appendix_xml


def test_generate_docx_report_renders_xrd_domain_specific_scientific_reasoning_sections():
    xrd_record, xrd_dataset = _make_xrd_no_match_record()

    docx_bytes = generate_docx_report(
        results={xrd_record["id"]: xrd_record},
        datasets={"synthetic_xrd": xrd_dataset},
    )

    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    assert "Primary Scientific Interpretation" in xml
    assert "Evidence Supporting This Interpretation" in xml
    assert "Alternative Explanations" in xml
    assert "Uncertainty and Methodological Limits" in xml
    assert "Recommended Follow-Up Experiments" in xml
    assert "best-ranked XRD candidate" in xml or "qualitative phase screening" in xml
    assert "Scientific reasoning is not specialized for this analysis type yet." not in xml


def test_generate_docx_report_hides_operational_fields_from_experimental_conditions(thermal_dataset):
    dataset = thermal_dataset.copy()
    dataset.metadata["import_confidence"] = "high"
    dataset.metadata.pop("instrument", None)
    docx_bytes = generate_docx_report(results={}, datasets={"synthetic_dsc": dataset})

    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    assert "Experimental Conditions" in xml
    assert "Dataset Key" not in xml
    assert "Import Confidence" not in xml
    assert "Not recorded" in xml


def test_generate_docx_report_condenses_and_deduplicates_warnings(thermal_dataset):
    record = _make_dsc_record(thermal_dataset)
    record["scientific_context"]["warnings"] = [
        "Atmosphere is not recorded for this dataset.",
        "Atmosphere is not recorded for this dataset.",
    ]
    record["scientific_context"]["limitations"] = [
        "Interpretation requires independent method validation.",
        "Interpretation requires independent method validation.",
    ]
    record["validation"]["warnings"] = []

    docx_bytes = generate_docx_report(
        results={record["id"]: record},
        datasets={"synthetic_dsc": thermal_dataset},
    )

    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    assert "Data Completeness Warnings" in xml
    assert "Methodological Limitations" in xml
    appendix_index = xml.index("Appendix A")
    main_xml = xml[:appendix_index]
    assert "Atmosphere is not recorded for this dataset." not in main_xml
    assert "Key metadata were not recorded" in main_xml
    assert 1 <= main_xml.count("Interpretation requires independent method validation.") <= 2


def test_generate_docx_report_renders_tga_scientific_prose_not_metric_label_pattern(temperature_range, tga_percent_signal):
    tga_record, tga_dataset = _make_tga_record(temperature_range, tga_percent_signal)
    docx_bytes = generate_docx_report(
        results={tga_record["id"]: tga_record},
        datasets={"synthetic_tga": tga_dataset},
    )

    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    assert "dominant primary mass-loss event" in xml or "multiple decomposition events" in xml
    assert "Step Count:" not in xml


def test_generate_docx_report_preserves_turkish_labels(temperature_range, tga_percent_signal):
    tga_record, tga_dataset = _make_tga_record(temperature_range, tga_percent_signal)
    tga_record["processing"]["workflow_template_label"] = "Çok Adımlı Ayrışma"

    docx_bytes = generate_docx_report(
        results={tga_record["id"]: tga_record},
        datasets={"synthetic_tga": tga_dataset},
    )

    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    assert "Çok Adımlı Ayrışma" in xml
    assert "□" not in xml


def test_generate_docx_report_renders_academic_reasoning_sections(temperature_range, tga_percent_signal):
    tga_record, tga_dataset = _make_tga_record(temperature_range, tga_percent_signal)

    docx_bytes = generate_docx_report(
        results={tga_record["id"]: tga_record},
        datasets={"synthetic_tga": tga_dataset},
    )

    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    assert "Primary Scientific Interpretation" in xml
    assert "Evidence Supporting This Interpretation" in xml
    assert "Alternative Explanations" in xml
    assert "Uncertainty and Methodological Limits" in xml
    assert "Recommended Follow-Up Experiments" in xml


def test_generate_csv_summary_uses_normalized_flat_contract(thermal_dataset):
    dsc_record = _make_dsc_record(thermal_dataset)
    csv_str = generate_csv_summary({dsc_record["id"]: dsc_record})

    reader = csv.DictReader(io.StringIO(csv_str))
    rows = list(reader)

    assert reader.fieldnames == [
        "result_id",
        "status",
        "analysis_type",
        "dataset_key",
        "section",
        "row_index",
        "field",
        "value",
    ]
    assert any(row["section"] == "summary" and row["field"] == "peak_count" for row in rows)
    assert any(row["section"] == "processing" and row["field"] == "workflow_template" for row in rows)
    assert any(row["section"] == "processing" and row["field"] == "workflow_template_id" for row in rows)
    assert any(row["section"] == "processing" and row["field"] == "workflow_template_label" for row in rows)
    assert any(row["section"] == "processing" and row["field"] == "schema_version" for row in rows)
    assert any(row["section"] == "processing" and row["field"] == "signal_pipeline" for row in rows)
    assert any(row["section"] == "processing" and row["field"] == "analysis_steps" for row in rows)
    assert any(row["section"] == "processing" and row["field"] == "sign_convention" for row in rows)
    assert any(row["section"] == "processing" and row["field"] == "method_context" for row in rows)
    assert any(row["section"] == "scientific_context" and row["field"] == "methodology" for row in rows)
    assert any(row["section"] == "scientific_context" and row["field"] == "equations" for row in rows)
    assert any(row["section"] == "provenance" and row["field"] == "app_version" for row in rows)
    assert any(row["section"] == "provenance" and row["field"] == "calibration_state" for row in rows)
    assert any(row["section"] == "provenance" and row["field"] == "reference_state" for row in rows)
    assert any(row["section"] == "validation" and row["field"] == "status" for row in rows)
    assert any(row["section"] == "row" and row["field"] == "peak_temperature" for row in rows)


def test_generate_csv_summary_handles_multiple_normalized_record_types(thermal_dataset):
    dsc_record = _make_dsc_record(thermal_dataset)
    kissinger_record = _make_kissinger()
    ofw_record = _make_ofw()
    friedman_record = _make_friedman()

    csv_str = generate_csv_summary(
        {
            dsc_record["id"]: dsc_record,
            kissinger_record["id"]: kissinger_record,
            ofw_record["id"]: ofw_record,
            friedman_record["id"]: friedman_record,
        }
    )
    rows = list(csv.DictReader(io.StringIO(csv_str)))

    analysis_types = {row["analysis_type"] for row in rows}
    assert {"DSC", "Kissinger", "Ozawa-Flynn-Wall", "Friedman"} <= analysis_types


def test_generate_csv_summary_writes_to_targets(thermal_dataset):
    dsc_record = _make_dsc_record(thermal_dataset)

    buf = io.StringIO()
    csv_str = generate_csv_summary({dsc_record["id"]: dsc_record}, buf)
    assert buf.tell() == 0
    assert csv_str == buf.read()

    out_dir = Path(".test-output")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "normalized_results.csv"
    csv_str = generate_csv_summary({dsc_record["id"]: dsc_record}, str(out_path))
    assert os.path.exists(out_path)
    with open(out_path, newline="", encoding="utf-8") as fh:
        assert fh.read() == csv_str
    out_path.unlink(missing_ok=True)


def test_generate_docx_report_writes_to_buffer_and_path(thermal_dataset):
    dsc_record = _make_dsc_record(thermal_dataset)

    buf = io.BytesIO()
    docx_bytes = generate_docx_report(
        results={dsc_record["id"]: dsc_record},
        datasets={"synthetic_dsc": thermal_dataset},
        file_path_or_buffer=buf,
    )
    assert buf.tell() == 0
    assert buf.getvalue() == docx_bytes

    out_dir = Path(".test-output")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "normalized_report.docx"
    docx_bytes = generate_docx_report(
        results={dsc_record["id"]: dsc_record},
        datasets={"synthetic_dsc": thermal_dataset},
        file_path_or_buffer=str(out_path),
    )
    assert os.path.exists(out_path)
    with open(out_path, "rb") as fh:
        assert fh.read() == docx_bytes
    out_path.unlink(missing_ok=True)


def test_generate_docx_report_skips_invalid_records_but_keeps_valid_ones(thermal_dataset):
    dsc_record = _make_dsc_record(thermal_dataset)
    docx_bytes = generate_docx_report(
        results={
            dsc_record["id"]: dsc_record,
            "broken": {"analysis_type": "DSC"},
        },
        datasets={"synthetic_dsc": thermal_dataset},
    )

    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    assert "Skipped Records" in xml
    assert "dsc_synthetic_dsc" not in xml  # title uses analysis type + dataset key
    assert "DSC - synthetic_dsc" in xml


def test_generate_csv_summary_skips_invalid_records_without_restoring_legacy_contract(thermal_dataset):
    dsc_record = _make_dsc_record(thermal_dataset)
    csv_str = generate_csv_summary(
        {
            dsc_record["id"]: dsc_record,
            "legacy_raw": SimpleNamespace(activation_energy=123.4),
        }
    )

    rows = list(csv.DictReader(io.StringIO(csv_str)))

    assert rows
    assert all(row["result_id"] == dsc_record["id"] for row in rows)
