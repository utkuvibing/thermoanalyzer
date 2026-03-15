import io
import zipfile
from types import SimpleNamespace

import pandas as pd
import pytest

from core.data_io import ThermalDataset
from core.dsc_processor import GlassTransition
from core.peak_analysis import ThermalPeak
from core.processing_schema import ensure_processing_payload, update_method_context, update_processing_step
from core.provenance import build_calibration_reference_context
from core.report_generator import (
    _build_comparison_payload,
    _build_final_conclusion_paragraph,
    _build_pdf_abstract_layout,
    _build_experimental_prose_block,
    _build_pdf_matrix_table,
    _record_appendix_sections,
    _choose_portrait_or_landscape_table_layout,
    _insert_soft_breaks,
    _paper_display_label,
    _figures_for_record,
    _record_full_rows,
    select_comparison_figures,
    _pdf_render_sections,
    generate_csv_summary,
    generate_docx_report,
    generate_pdf_report,
)
from core.result_serialization import serialize_dsc_result, serialize_kissinger_result, serialize_spectral_result, serialize_tga_result, serialize_xrd_result
from core.tga_processor import MassLossStep, TGAResult
from core.validation import validate_thermal_dataset
from ui.export_page import _batch_summary_preview_frame, _results_to_xlsx


def _make_dsc_result(thermal_dataset):
    dataset = thermal_dataset.copy()
    dataset.metadata.update(
        {
            "vendor": "TestVendor",
            "display_name": "Synthetic DSC Run",
            "calibration_id": "DSC-CAL-01",
            "calibration_status": "verified",
        }
    )
    peak = ThermalPeak(
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
    tg = GlassTransition(
        tg_midpoint=120.0,
        tg_onset=115.0,
        tg_endset=125.0,
        delta_cp=0.12,
    )
    processing = ensure_processing_payload(
        analysis_type="DSC",
        workflow_template="dsc.polymer_tg",
        workflow_template_label="Polymer Tg",
    )
    processing = update_processing_step(processing, "smoothing", {"method": "savgol", "window_length": 11, "polyorder": 3})
    processing = update_processing_step(processing, "baseline", {"method": "asls"})
    processing = update_processing_step(processing, "peak_detection", {"direction": "both", "peak_count": 1})
    calibration_context = build_calibration_reference_context(
        dataset=dataset,
        analysis_type="DSC",
        reference_temperature_c=peak.peak_temperature,
    )
    processing = update_method_context(processing, calibration_context, analysis_type="DSC")
    validation = validate_thermal_dataset(dataset, analysis_type="DSC", processing=processing)
    return serialize_dsc_result(
        "synthetic_dsc",
        dataset,
        [peak],
        glass_transitions=[tg],
        artifacts={"figure_keys": ["DSC Analysis - synthetic_dsc"]},
        processing=processing,
        provenance={
            "saved_at_utc": "2026-03-07T10:00:00+00:00",
            "app_version": "2.0",
            "calibration_state": calibration_context["calibration_state"],
            "reference_state": calibration_context["reference_state"],
            "reference_name": calibration_context.get("reference_name"),
        },
        validation=validation,
    )


def _make_tga_dataset(temperature_range, tga_signal):
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
        },
        data_type="TGA",
        units={"temperature": "degC", "signal": "%"},
        original_columns={"temperature": "temperature", "signal": "signal"},
        file_path="",
    )


def _make_tga_result(temperature_range, tga_signal):
    dataset = _make_tga_dataset(temperature_range, tga_signal)
    result = TGAResult(
        steps=[
            MassLossStep(
                onset_temperature=140.0,
                endset_temperature=180.0,
                midpoint_temperature=200.0,
                mass_loss_percent=12.0,
                mass_loss_mg=1.2,
                residual_percent=88.0,
                dtg_peak_temperature=200.0,
            )
        ],
        dtg_peaks=[],
        dtg_signal=tga_signal * 0.0,
        smoothed_signal=tga_signal,
        total_mass_loss_percent=12.0,
        residue_percent=88.0,
        metadata=dataset.metadata,
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
    calibration_context = build_calibration_reference_context(
        dataset=dataset,
        analysis_type="TGA",
        reference_temperature_c=result.steps[0].midpoint_temperature,
    )
    processing = update_method_context(processing, calibration_context, analysis_type="TGA")
    validation = validate_thermal_dataset(dataset, analysis_type="TGA", processing=processing)
    return serialize_tga_result(
        "synthetic_tga",
        dataset,
        result,
        artifacts={"figure_keys": ["TGA Analysis - synthetic_tga"]},
        processing=processing,
        provenance={
            "saved_at_utc": "2026-03-07T10:01:00+00:00",
            "app_version": "2.0",
            "calibration_state": calibration_context["calibration_state"],
            "reference_state": calibration_context["reference_state"],
            "reference_name": calibration_context.get("reference_name"),
        },
        validation=validation,
    )


def _make_ftir_no_match_result():
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
    validation = validate_thermal_dataset(dataset, analysis_type="FTIR", processing=processing)
    return serialize_spectral_result(
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
            "library_request_id": "libreq_export_ftir_001",
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
        validation=validation,
    )


def _make_xrd_no_match_result():
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
        },
        analysis_type="XRD",
    )
    validation = validate_thermal_dataset(dataset, analysis_type="XRD", processing=processing)
    return serialize_xrd_result(
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
            "caution_code": "xrd_no_match",
            "caution_message": "No candidate exceeded threshold; qualitative caution required.",
            "library_access_mode": "limited_cached_fallback",
            "library_request_id": "libreq_export_xrd_001",
            "library_result_source": "limited_fallback_cache",
            "library_provider_scope": ["cod"],
            "library_offline_limited_mode": True,
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
                    "weighted_overlap_score": 0.11,
                    "mean_delta_position": None,
                    "unmatched_major_peak_count": 3,
                    "tolerance_deg": 0.28,
                },
            }
        ],
        artifacts={"figure_keys": ["XRD Analysis - synthetic_xrd"]},
        processing=processing,
        provenance={"saved_at_utc": "2026-03-12T02:00:00+00:00", "app_version": "2.0"},
        validation=validation,
    )


def test_generate_csv_summary_with_normalized_records(thermal_dataset):
    dsc_result = _make_dsc_result(thermal_dataset)
    kissinger_result = serialize_kissinger_result(
        SimpleNamespace(
            activation_energy=123.4,
            r_squared=0.998,
            pre_exponential=12.0,
            plot_data={},
        )
    )

    csv_text = generate_csv_summary(
        {
            dsc_result["id"]: dsc_result,
            kissinger_result["id"]: kissinger_result,
        }
    )

    assert "result_id,status,analysis_type" in csv_text
    assert "dsc_synthetic_dsc" in csv_text
    assert "kissinger" in csv_text
    assert "processing" in csv_text
    assert "scientific_context" in csv_text
    assert "provenance" in csv_text
    assert "schema_version" in csv_text
    assert "workflow_template_id" in csv_text


def test_generate_docx_report_separates_stable_and_experimental(thermal_dataset):
    dsc_result = _make_dsc_result(thermal_dataset)
    tga_result = _make_tga_result(thermal_dataset.data["temperature"].values, thermal_dataset.data["signal"].values * 0 + 100)
    kissinger_result = serialize_kissinger_result(
        SimpleNamespace(
            activation_energy=123.4,
            r_squared=0.998,
            pre_exponential=12.0,
            plot_data={},
        )
    )
    invalid_record = {"analysis_type": "DSC"}

    docx_bytes = generate_docx_report(
        {
            dsc_result["id"]: dsc_result,
            tga_result["id"]: tga_result,
            kissinger_result["id"]: kissinger_result,
            "broken": invalid_record,
        },
        datasets={"synthetic_dsc": thermal_dataset},
        branding={
            "report_title": "Acme Customer Report",
            "company_name": "Acme Lab",
            "lab_name": "Polymer Lab",
            "analyst_name": "Ada",
            "report_notes": "Batch remains within thermal envelope.",
        },
        comparison_workspace={
            "analysis_type": "DSC",
            "selected_datasets": ["synthetic_dsc"],
            "notes": "Comparison workspace notes",
            "figure_key": "Comparison Workspace - DSC",
        },
        license_state={"status": "activated", "license": {"sku": "PROFESSIONAL"}},
    )

    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    assert "Acme Customer Report" in xml
    assert "Executive Summary" in xml
    assert "This report summarizes" in xml
    assert "Stable Analyses" in xml
    assert "Experimental Analyses" in xml
    assert "Skipped Records" in xml
    assert "Analyst Notes" in xml
    assert "Comparison Overview" in xml
    assert "Comparison Interpretation" in xml
    assert "Kissinger" in xml
    assert "Methodology" in xml
    assert "Equations and Formulation" in xml
    assert "Scientific Interpretation" in xml
    assert "Numerical Interpretation" not in xml
    assert "Fit Quality" in xml
    assert "Warnings and Limitations" in xml
    assert "Methodological Limitations" in xml
    assert "Final Conclusion" in xml
    assert "Appendix A" in xml
    assert "Single-Step Decomposition" in xml
    assert "Major Decomposition Events" in xml
    assert "Full Raw Data Table" in xml


def test_generate_docx_report_renders_ftir_caution_semantics():
    ftir_result = _make_ftir_no_match_result()
    docx_bytes = generate_docx_report(
        {ftir_result["id"]: ftir_result},
        datasets={"synthetic_ftir": ThermalDataset(
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
        )},
    )
    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    assert "FTIR - synthetic_ftir" in xml
    assert "Match Status" in xml
    assert "no_match" in xml
    assert "Caution Code" in xml
    assert "spectral_no_match" in xml
    assert "Library Result Source" in xml
    assert "cloud_search" in xml


def test_generate_docx_report_renders_xrd_caution_semantics():
    xrd_result = _make_xrd_no_match_result()
    docx_bytes = generate_docx_report(
        {xrd_result["id"]: xrd_result},
        datasets={"synthetic_xrd": ThermalDataset(
            data=pd.DataFrame({"temperature": [18.2, 27.5, 36.1, 44.8], "signal": [130.0, 290.0, 175.0, 120.0]}),
            metadata={
                "sample_name": "SyntheticXRD",
                "sample_mass": 1.0,
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
        )},
    )
    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    assert "XRD - synthetic_xrd" in xml
    assert "Accepted Match Status" in xml
    assert "no_match" in xml
    assert "Best Candidate Name" in xml
    assert "Phase Alpha" in xml
    assert "Best Candidate Score" in xml
    assert "Shared Peaks" in xml
    assert "Weighted Overlap Score" in xml
    assert "Caution Code" in xml
    assert "xrd_no_match" in xml
    assert "Library Result Source" in xml
    assert "limited_fallback_cache" in xml
    assert "Library Access Mode" in xml
    assert "limited_cached_fallback" in xml
    assert "Phase Matching Metric" in xml


def test_results_to_xlsx_writes_summary_and_detail_sheets(thermal_dataset, temperature_range, tga_signal):
    dsc_result = _make_dsc_result(thermal_dataset)
    tga_result = _make_tga_result(temperature_range, tga_signal)

    buffer = io.BytesIO()
    _results_to_xlsx(
        {
            dsc_result["id"]: dsc_result,
            tga_result["id"]: tga_result,
        },
        ["broken record"],
        buffer,
    )
    buffer.seek(0)
    workbook = pd.ExcelFile(buffer)
    results_df = workbook.parse("Results")

    assert "Results" in workbook.sheet_names
    assert "Skipped" in workbook.sheet_names
    assert any(name.startswith("DSC_") for name in workbook.sheet_names)
    assert any(name.startswith("TGA_") for name in workbook.sheet_names)
    assert {"workflow_template", "validation_status", "saved_at_utc"} <= set(results_df.columns)
    dsc_row = results_df.loc[results_df["result_id"] == "dsc_synthetic_dsc"].iloc[0]
    assert dsc_row["workflow_template"] == "Polymer Tg"
    assert dsc_row["validation_status"] == "pass"
    assert dsc_row["saved_at_utc"] == "2026-03-07T10:00:00+00:00"


def test_batch_summary_preview_frame_exposes_failure_reason_and_error_id():
    frame = _batch_summary_preview_frame(
        [
            {
                "dataset_key": "run_a",
                "sample_name": "Run A",
                "workflow_template": "Polymer Tg",
                "execution_status": "failed",
                "validation_status": "not_run",
                "result_id": "",
                "error_id": "TA-DSC-20260307123400-CCCCCC",
                "failure_reason": "Processor exploded.",
            }
        ],
        "en",
    )

    assert list(frame.columns) == ["Run", "Sample", "Template", "Execution", "Validation", "Result ID", "Error ID", "Reason"]
    assert frame.iloc[0]["Execution"] == "failed"
    assert frame.iloc[0]["Error ID"] == "TA-DSC-20260307123400-CCCCCC"
    assert frame.iloc[0]["Reason"] == "Processor exploded."


def test_pdf_abstract_layout_uses_narrative_and_bullets_without_table_rows(thermal_dataset):
    dsc_result = _make_dsc_result(thermal_dataset)
    tga_result = _make_tga_result(
        thermal_dataset.data["temperature"].values,
        thermal_dataset.data["signal"].values * 0 + 100,
    )

    abstract, bullets = _build_pdf_abstract_layout(
        [dsc_result, tga_result],
        {"synthetic_dsc": thermal_dataset},
    )

    assert "scientific synthesis" in abstract
    assert bullets
    assert isinstance(bullets[0], str)
    assert len(bullets) <= 3


def test_pdf_soft_break_insertion_wraps_long_hash_tokens():
    wrapped = _insert_soft_breaks("a" * 80, chunk=16)
    assert "\u200b" in wrapped


def test_pdf_soft_break_insertion_truncates_when_max_chars_is_set():
    wrapped = _insert_soft_breaks("b" * 200, chunk=8, max_chars=60)
    assert len(wrapped) <= 80
    assert wrapped.endswith("…")


def test_pdf_layout_selector_uses_landscape_for_wide_appendix_tables():
    headers = ["Run", "Sample", "Template", "Execution", "Validation", "Calibration", "Reference", "Result ID", "Error ID", "Reason"]
    rows = [["x" * 48 for _ in headers]]
    layout = _choose_portrait_or_landscape_table_layout(headers, rows, portrait_width=420.0)
    assert layout == "landscape"


def test_pdf_matrix_builder_respects_available_width_budget():
    pytest.importorskip("reportlab")
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet

    styles = getSampleStyleSheet()
    table = _build_pdf_matrix_table(
        headers=["Dataset", "Analysis Type", "Key Findings"],
        rows=[["Synthetic Run", "TGA", "Long summary " * 12]],
        available_width=360.0,
        paragraph_style=styles["Normal"],
        header_style=styles["Normal"],
        colors=colors,
        font_name=None,
        compact=False,
    )

    assert sum(float(width) for width in table._colWidths) <= 360.001


def test_pdf_render_sections_suppresses_redundant_scientific_interpretation():
    record = {
        "analysis_type": "DSC",
        "scientific_context": {
            "methodology": {"analysis_family": "Differential Scanning Calorimetry"},
            "equations": [],
            "numerical_interpretation": [{"statement": "Legacy line"}],
            "scientific_claims": [{"id": "C1", "strength": "descriptive", "claim": "Primary line"}],
            "evidence_map": {"C1": ["Evidence"]},
            "uncertainty_assessment": {"overall_confidence": "moderate"},
            "alternative_hypotheses": ["Alt"],
            "next_experiments": ["Follow-up"],
        },
        "processing": {},
        "validation": {},
        "summary": {"peak_count": 1},
        "rows": [],
        "metadata": {},
    }

    titles = [title for title, _ in _pdf_render_sections(record)]
    assert "Primary Scientific Interpretation" in titles
    assert "Scientific Interpretation" not in titles
    assert "Methodology" not in titles
    assert "Equations and Formulation" not in titles


def test_experimental_block_uses_compact_prose_not_key_value_layout(thermal_dataset):
    prose = _build_experimental_prose_block("synthetic_dsc", thermal_dataset, {"synthetic_dsc": thermal_dataset})
    assert "Instrument:" in prose
    assert "Heating rate:" in prose
    assert "Atmosphere:" in prose
    assert "Metadata completeness" in prose


def test_appendix_retains_technical_method_tables():
    record = {
        "analysis_type": "TGA",
        "processing": {
            "workflow_template": "tga.general",
            "analysis_type": "TGA",
            "method_context": {"tga_unit_mode_label": "Percent"},
        },
        "validation": {"status": "pass", "issues": [], "warnings": []},
        "provenance": {"source_data_hash": "abc123", "saved_at_utc": "2026-03-07T10:00:00+00:00"},
        "review": {"commercial_scope": "stable_tga"},
        "scientific_context": {"warnings": ["x"], "limitations": ["y"]},
        "metadata": {"delimiter": ",", "header_row": 1},
    }
    sections = _record_appendix_sections(record)
    titles = [title for title, _ in sections]
    assert "Method Context" in titles
    assert "Provenance" in titles


def test_paper_display_label_prefers_user_friendly_mapping():
    datasets = {
        "run1": SimpleNamespace(metadata={"file_name": "tga_polymers_comparison.xlsx", "display_name": ""}),
    }
    assert _paper_display_label("run1", datasets) == "PMMA sample"


def test_paper_display_label_maps_caco3_and_avoids_raw_filename_heading():
    record = {
        "summary": {"sample_name": "tga_CaCO3_decomposition.csv"},
        "metadata": {"file_name": "tga_CaCO3_decomposition.csv"},
        "dataset_key": "tga_CaCO3_decomposition.csv",
    }
    label = _paper_display_label("tga_CaCO3_decomposition.csv", {}, record=record)
    assert label == "CaCO3 sample"
    assert ".csv" not in label


def test_final_conclusion_explicitly_contrasts_two_tga_behaviors():
    conclusion = _build_final_conclusion_paragraph(
        [
            {
                "analysis_type": "TGA",
                "status": "stable",
                "dataset_key": "run_low_residue",
                "summary": {
                    "sample_name": "Low-Residue Sample",
                    "step_count": 2,
                    "total_mass_loss_percent": 98.1,
                    "residue_percent": 1.9,
                },
            },
            {
                "analysis_type": "TGA",
                "status": "stable",
                "dataset_key": "run_high_residue",
                "summary": {
                    "sample_name": "High-Residue Sample",
                    "step_count": 4,
                    "total_mass_loss_percent": 63.5,
                    "residue_percent": 36.2,
                },
            },
        ],
        comparison_payload=None,
    )

    assert "near-complete decomposition with minimal residue" in conclusion
    assert "residue retention" in conclusion or "residue-forming behavior" in conclusion
    assert "Low-Residue Sample" in conclusion
    assert "High-Residue Sample" in conclusion
    assert "metadata limitations reduce mechanistic certainty" in conclusion.lower()


def test_final_conclusion_does_not_overclaim_caco3_as_near_complete():
    conclusion = _build_final_conclusion_paragraph(
        [
            {
                "analysis_type": "TGA",
                "status": "stable",
                "dataset_key": "tga_CaCO3_decomposition.csv",
                "summary": {
                    "sample_name": "tga_CaCO3_decomposition.csv",
                    "step_count": 2,
                    "total_mass_loss_percent": 44.0,
                    "residue_percent": 56.1,
                },
            }
        ],
        comparison_payload=None,
    )

    assert "near-complete decomposition with minimal residue" not in conclusion
    assert "decarbonation of caco3 to cao" in conclusion.lower()


def test_final_conclusion_uses_formula_specific_hydrate_product_when_available():
    conclusion = _build_final_conclusion_paragraph(
        [
            {
                "analysis_type": "TGA",
                "status": "stable",
                "dataset_key": "tga_CuSO4_5H2O_dehydration.csv",
                "summary": {
                    "sample_name": "CuSO4·5H2O",
                    "step_count": 4,
                    "total_mass_loss_percent": 36.06,
                    "residue_percent": 63.99,
                },
                "rows": [
                    {"midpoint_temperature": 118.0, "mass_loss_percent": 14.5},
                    {"midpoint_temperature": 172.0, "mass_loss_percent": 11.2},
                    {"midpoint_temperature": 223.0, "mass_loss_percent": 8.1},
                    {"midpoint_temperature": 318.0, "mass_loss_percent": 2.3},
                ],
                "metadata": {"file_name": "tga_CuSO4_5H2O_dehydration.csv"},
            }
        ],
        comparison_payload=None,
    )

    lowered = conclusion.lower()
    assert "dehydration of cuso4" in lowered
    assert "anhydrous cuso4" in lowered


def test_figures_for_record_excludes_comparison_workspace_figures_from_dataset_section():
    record = {
        "analysis_type": "TGA",
        "dataset_key": "run_a",
        "artifacts": {"figure_keys": ["Comparison Workspace - TGA"]},
    }
    figures = {
        "Comparison Workspace - TGA": b"cmp",
        "TGA Analysis - run_a": b"sample",
    }
    matched = _figures_for_record(record, figures, used=set())

    assert matched
    assert all("comparison workspace" not in caption.lower() for caption, _ in matched)
    assert any("run_a" in caption.lower() for caption, _ in matched)


def test_figures_for_record_excludes_other_sample_figure_from_dataset_section():
    record = {
        "analysis_type": "TGA",
        "dataset_key": "run_a",
        "metadata": {"sample_name": "Run A"},
        "artifacts": {"figure_keys": ["TGA Analysis - run_b"]},
    }
    figures = {
        "TGA Analysis - run_b": b"other",
        "TGA Analysis - run_a": b"correct",
    }
    matched = _figures_for_record(record, figures, used=set())

    captions = [caption for caption, _ in matched]
    assert "TGA Analysis - run_a" in captions
    assert "TGA Analysis - run_b" not in captions


def test_figures_for_record_uses_sample_artifact_key_when_caption_is_generic():
    record = {
        "analysis_type": "TGA",
        "dataset_key": "run_a",
        "metadata": {"sample_name": "Run A"},
        "artifacts": {"figure_keys": ["Thermogram Figure"]},
    }
    figures = {
        "Thermogram Figure": b"sample",
        "Comparison Workspace - TGA": b"cmp",
    }
    matched = _figures_for_record(record, figures, used=set())

    assert matched == [("Thermogram Figure", b"sample")]


def test_figures_for_record_prefers_primary_report_figure_key():
    record = {
        "analysis_type": "XRD",
        "dataset_key": "synthetic_xrd",
        "artifacts": {
            "report_figure_key": "XRD Snapshot - synthetic_xrd - primary",
            "figure_keys": ["XRD Snapshot - synthetic_xrd - backup"],
        },
    }
    figures = {
        "XRD Snapshot - synthetic_xrd - primary": b"primary-bytes",
        "XRD Snapshot - synthetic_xrd - backup": b"backup-bytes",
    }

    matched = _figures_for_record(record, figures, used=set())

    assert matched == [("XRD Snapshot - synthetic_xrd - primary", b"primary-bytes")]


def test_record_full_rows_compacts_xrd_evidence_for_table_safety():
    record = {
        "analysis_type": "XRD",
        "rows": [
            {
                "rank": 1,
                "candidate_id": "xrd_phase_alpha",
                "normalized_score": 0.44,
                "evidence": {
                    "shared_peak_count": 7,
                    "weighted_overlap_score": 0.31,
                    "coverage_ratio": 0.22,
                    "mean_delta_position": 0.14,
                    "unmatched_major_peak_count": 3,
                    "matched_peak_pairs": [{"observed_index": idx, "reference_index": idx} for idx in range(120)],
                    "unmatched_observed_peaks": [{"observed_index": idx} for idx in range(80)],
                    "unmatched_reference_peaks": [{"reference_index": idx} for idx in range(60)],
                },
            }
        ],
    }

    payload = _record_full_rows(record)

    assert payload is not None
    headers, rows = payload
    evidence_index = headers.index("evidence")
    evidence_cell = rows[0][evidence_index]
    assert "shared_peak_count" in evidence_cell
    assert "matched_peak_pairs=120" in evidence_cell
    assert len(evidence_cell) <= 320


def test_figures_for_record_uses_non_conflicting_generic_when_no_direct_match():
    record = {
        "analysis_type": "TGA",
        "dataset_key": "run_a",
        "metadata": {"sample_name": "Run A"},
        "artifacts": {"figure_keys": []},
    }
    figures = {
        "Thermogram Figure": b"sample",
        "Comparison Workspace - TGA": b"cmp",
    }
    matched = _figures_for_record(record, figures, used=set())

    assert matched == [("Thermogram Figure", b"sample")]


def test_generate_docx_report_renders_non_conflicting_sample_figure_in_dataset_section(temperature_range, tga_signal):
    tga_result = _make_tga_result(temperature_range, tga_signal)
    tga_result["artifacts"] = {"figure_keys": []}
    dataset = _make_tga_dataset(temperature_range, tga_signal)
    docx_bytes = generate_docx_report(
        {tga_result["id"]: tga_result},
        datasets={"synthetic_tga": dataset},
        figures={"Thermogram Figure": b"not-a-real-png"},
    )

    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    assert "Figure 1: Thermogram Figure" in xml


def test_select_comparison_figures_returns_only_comparison_captions():
    figures = {
        "Comparison Workspace - TGA": b"cmp",
        "TGA Analysis - run_a": b"a",
        "TGA Analysis - run_b": b"b",
    }
    selected = select_comparison_figures(
        figures,
        used=set(),
        comparison_workspace={"figure_key": "Comparison Workspace - TGA"},
    )

    assert selected == [("Comparison Workspace - TGA", b"cmp")]


def test_tga_comparison_payload_uses_display_labels_and_chemistry_aware_wording():
    datasets = {
        "hydrate": SimpleNamespace(
            metadata={
                "file_name": "tga_CuSO4_5H2O_dehydration.csv",
                "sample_name": "CuSO4·5H2O",
                "heating_rate": 10.0,
                "atmosphere": "N2",
            }
        ),
        "carbonate": SimpleNamespace(
            metadata={
                "file_name": "tga_CaCO3_decomposition.csv",
                "sample_name": "CaCO3",
                "heating_rate": 10.0,
                "atmosphere": "N2",
            }
        ),
    }
    records = [
        {
            "analysis_type": "TGA",
            "status": "stable",
            "dataset_key": "hydrate",
            "summary": {
                "sample_name": "CuSO4·5H2O",
                "step_count": 4,
                "total_mass_loss_percent": 36.1,
                "residue_percent": 63.9,
            },
            "rows": [
                {"midpoint_temperature": 118.0, "mass_loss_percent": 14.5},
                {"midpoint_temperature": 172.0, "mass_loss_percent": 11.2},
                {"midpoint_temperature": 223.0, "mass_loss_percent": 8.1},
                {"midpoint_temperature": 318.0, "mass_loss_percent": 2.3},
            ],
            "metadata": datasets["hydrate"].metadata,
        },
        {
            "analysis_type": "TGA",
            "status": "stable",
            "dataset_key": "carbonate",
            "summary": {
                "sample_name": "CaCO3",
                "step_count": 2,
                "total_mass_loss_percent": 44.0,
                "residue_percent": 56.1,
            },
            "rows": [
                {"midpoint_temperature": 312.0, "mass_loss_percent": 2.4},
                {"midpoint_temperature": 720.0, "mass_loss_percent": 41.5},
            ],
            "metadata": datasets["carbonate"].metadata,
        },
    ]

    payload = _build_comparison_payload(
        {
            "analysis_type": "TGA",
            "selected_datasets": ["hydrate", "carbonate"],
            "figure_key": "Comparison Workspace - TGA",
        },
        datasets,
        records,
    )

    assert payload is not None
    assert payload["metric_rows"]
    labels = [row[0] for row in payload["metric_rows"]]
    assert "CuSO4·5H2O sample" in labels
    assert "CaCO3 sample" in labels
    assert all(".csv" not in label for label in labels)
    interpretation = payload["interpretation"].lower()
    assert "expected final solid products" in interpretation
    assert "higher residue may reflect retention of a stable inorganic end-product" in interpretation
    assert "different transformation pathways" in interpretation
    assert "dehydration" in interpretation
    assert "decarbonation" in interpretation
    assert "anhydrous cuso4" in interpretation
    assert "cao" in interpretation


def test_generate_pdf_report_uses_paper_structure_and_hides_executive_summary(thermal_dataset):
    pytest.importorskip("reportlab")
    dsc_result = _make_dsc_result(thermal_dataset)
    tga_result = _make_tga_result(
        thermal_dataset.data["temperature"].values,
        thermal_dataset.data["signal"].values * 0 + 100,
    )
    pdf_bytes = generate_pdf_report(
        results={dsc_result["id"]: dsc_result, tga_result["id"]: tga_result},
        datasets={"synthetic_dsc": thermal_dataset},
    )

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000
