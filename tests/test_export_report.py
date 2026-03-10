import io
import zipfile
from types import SimpleNamespace

import pandas as pd

from core.data_io import ThermalDataset
from core.dsc_processor import GlassTransition
from core.peak_analysis import ThermalPeak
from core.processing_schema import ensure_processing_payload, update_method_context, update_processing_step
from core.provenance import build_calibration_reference_context
from core.report_generator import generate_csv_summary, generate_docx_report
from core.result_serialization import serialize_dsc_result, serialize_kissinger_result, serialize_tga_result
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
    assert "Stable Analyses" in xml
    assert "Experimental Analyses" in xml
    assert "Skipped Records" in xml
    assert "Analyst Notes" in xml
    assert "Compare Workspace" in xml
    assert "Kissinger" in xml
    assert "Methodology" in xml
    assert "Equations and Formulation" in xml
    assert "Numerical Interpretation" in xml
    assert "Fit Quality" in xml
    assert "Warnings and Limitations" in xml
    assert "Calibration State" in xml
    assert "missing_calibration" in xml
    assert "Atmosphere Status" in xml
    assert "Reference State" in xml
    assert "reference_checked" in xml
    assert "Single-Step Decomposition" in xml
    assert "CaC₂O₄·H₂O  Step 1" in xml


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
