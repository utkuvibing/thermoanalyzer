import io

import numpy as np
import pandas as pd

from core.dsc_processor import GlassTransition
from core.peak_analysis import ThermalPeak
from core.data_io import ThermalDataset
from core.report_generator import generate_dsc_pdf_report
from ui.export_page import _dsc_result_to_xlsx


def _sample_dsc_result():
    peak = ThermalPeak(
        peak_index=10,
        peak_temperature=151.2,
        peak_signal=0.8,
        onset_temperature=145.0,
        endset_temperature=160.0,
        area=12.5,
        peak_type="endotherm",
    )
    tg = GlassTransition(
        tg_midpoint=79.5,
        tg_onset=75.2,
        tg_endset=83.4,
        delta_cp=0.1,
    )
    return {
        "analysis_type": "DSC",
        "dataset_key": "sample",
        "peaks": [peak],
        "glass_transitions": [tg],
        "baseline": np.array([0.01, 0.02, 0.03]),
        "corrected": np.array([0.1, 0.2, 0.3]),
    }


def _sample_dataset():
    return ThermalDataset(
        data=pd.DataFrame(
            {
                "temperature": np.array([50.0, 100.0, 150.0]),
                "signal": np.array([0.11, 0.32, 0.21]),
            }
        ),
        metadata={},
        data_type="DSC",
        units={"temperature": "°C", "signal": "mW/mg"},
        original_columns={"temperature": "temperature", "signal": "signal"},
        file_path="",
    )


def test_generate_dsc_pdf_report_returns_pdf_bytes():
    pdf_bytes = generate_dsc_pdf_report(_sample_dsc_result(), figures=None)
    assert pdf_bytes.startswith(b"%PDF")


def test_dsc_result_to_xlsx_creates_required_sheets():
    buf = io.BytesIO()
    _dsc_result_to_xlsx(_sample_dsc_result(), _sample_dataset(), buf)
    buf.seek(0)

    workbook = pd.ExcelFile(buf)
    assert workbook.sheet_names == ["Summary", "Raw Data", "Baseline", "Corrected", "Peaks"]
