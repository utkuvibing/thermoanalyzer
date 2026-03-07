import io
import zipfile
from types import SimpleNamespace

import pandas as pd

from core.data_io import ThermalDataset
from core.dsc_processor import GlassTransition
from core.peak_analysis import ThermalPeak
from core.report_generator import generate_csv_summary, generate_docx_report
from core.result_serialization import serialize_dsc_result, serialize_kissinger_result, serialize_tga_result
from core.tga_processor import MassLossStep, TGAResult
from ui.export_page import _results_to_xlsx


def _make_dsc_result(thermal_dataset):
    peak = ThermalPeak(
        peak_index=10,
        peak_temperature=250.0,
        peak_signal=2.0,
        onset_temperature=245.0,
        endset_temperature=255.0,
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
    return serialize_dsc_result(
        "synthetic_dsc",
        thermal_dataset,
        [peak],
        glass_transitions=[tg],
        artifacts={"figure_keys": ["DSC Analysis - synthetic_dsc"]},
    )


def _make_tga_dataset(temperature_range, tga_signal):
    return ThermalDataset(
        data=pd.DataFrame({"temperature": temperature_range, "signal": tga_signal}),
        metadata={
            "sample_name": "SyntheticTGA",
            "sample_mass": 10.0,
            "heating_rate": 20.0,
            "instrument": "TestInstrument",
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
                midpoint_temperature=155.0,
                mass_loss_percent=12.0,
                mass_loss_mg=1.2,
                residual_percent=88.0,
                dtg_peak_temperature=155.0,
            )
        ],
        dtg_peaks=[],
        dtg_signal=tga_signal * 0.0,
        smoothed_signal=tga_signal,
        total_mass_loss_percent=12.0,
        residue_percent=88.0,
        metadata=dataset.metadata,
    )
    return serialize_tga_result(
        "synthetic_tga",
        dataset,
        result,
        artifacts={"figure_keys": ["TGA Analysis - synthetic_tga"]},
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


def test_generate_docx_report_separates_stable_and_experimental(thermal_dataset):
    dsc_result = _make_dsc_result(thermal_dataset)
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

    assert "Results" in workbook.sheet_names
    assert "Skipped" in workbook.sheet_names
    assert any(name.startswith("DSC_") for name in workbook.sheet_names)
    assert any(name.startswith("TGA_") for name in workbook.sheet_names)
