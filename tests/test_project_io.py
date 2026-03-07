import io
import json
import zipfile

import numpy as np
import pandas as pd
import pytest

from core.data_io import ThermalDataset
from core.dsc_processor import GlassTransition
from core.peak_analysis import ThermalPeak
from core.project_io import load_project_archive, save_project_archive
from core.result_serialization import serialize_dsc_result, serialize_tga_result
from core.tga_processor import MassLossStep, TGAResult


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


def _make_peak():
    return ThermalPeak(
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


def _make_tg():
    return GlassTransition(
        tg_midpoint=120.0,
        tg_onset=115.0,
        tg_endset=125.0,
        delta_cp=0.12,
    )


def _make_tga_result(dataset, tga_signal):
    return TGAResult(
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
        dtg_signal=np.zeros_like(tga_signal),
        smoothed_signal=tga_signal,
        total_mass_loss_percent=12.0,
        residue_percent=88.0,
        metadata=dataset.metadata,
    )


def test_project_archive_round_trip_restores_stable_state(thermal_dataset, temperature_range, tga_signal):
    tga_dataset = _make_tga_dataset(temperature_range, tga_signal)
    peak = _make_peak()
    tg = _make_tg()
    tga_result = _make_tga_result(tga_dataset, tga_signal)

    dsc_record = serialize_dsc_result(
        "synthetic_dsc",
        thermal_dataset,
        [peak],
        glass_transitions=[tg],
        artifacts={"figure_keys": ["DSC Analysis - synthetic_dsc"]},
    )
    tga_record = serialize_tga_result(
        "synthetic_tga",
        tga_dataset,
        tga_result,
        artifacts={"figure_keys": ["TGA Analysis - synthetic_tga"]},
    )

    session_state = {
        "datasets": {
            "synthetic_dsc": thermal_dataset,
            "synthetic_tga": tga_dataset,
        },
        "active_dataset": "synthetic_tga",
        "results": {
            dsc_record["id"]: dsc_record,
            tga_record["id"]: tga_record,
        },
        "figures": {
            "DSC Analysis - synthetic_dsc": b"fake-dsc-png",
            "TGA Analysis - synthetic_tga": b"fake-tga-png",
            "Comparison Workspace - DSC": b"fake-compare-png",
        },
        "analysis_history": [
            {"step_number": 1, "timestamp": "10:00:00", "action": "Data Loaded", "details": "demo", "page": "Import Data"}
        ],
        "branding": {
            "report_title": "Acme Thermal Report",
            "company_name": "Acme Lab",
            "lab_name": "Polymer Lab",
            "analyst_name": "Ada",
            "report_notes": "Release batch passes overlay check.",
            "logo_bytes": b"fake-logo",
            "logo_name": "logo.png",
        },
        "comparison_workspace": {
            "analysis_type": "DSC",
            "selected_datasets": ["synthetic_dsc", "synthetic_tga"],
            "notes": "Synthetic comparison notes",
            "figure_key": "Comparison Workspace - DSC",
            "saved_at": "2026-03-07T10:05:00",
        },
        "dsc_state_synthetic_dsc": {
            "smoothed": thermal_dataset.data["signal"].values,
            "baseline": np.zeros(len(thermal_dataset.data)),
            "corrected": thermal_dataset.data["signal"].values,
            "peaks": [peak],
            "glass_transitions": [tg],
            "processor": None,
        },
        "tga_state_synthetic_tga": {
            "smoothed": tga_signal,
            "dtg": np.zeros_like(tga_signal),
            "tga_result": tga_result,
        },
    }

    archive_bytes = save_project_archive(session_state)
    restored = load_project_archive(io.BytesIO(archive_bytes))

    assert set(restored["datasets"].keys()) == {"synthetic_dsc", "synthetic_tga"}
    assert restored["active_dataset"] == "synthetic_tga"
    assert set(restored["results"].keys()) == {"dsc_synthetic_dsc", "tga_synthetic_tga"}
    assert restored["figures"]["DSC Analysis - synthetic_dsc"] == b"fake-dsc-png"
    assert restored["figures"]["Comparison Workspace - DSC"] == b"fake-compare-png"
    assert len(restored["analysis_history"]) == 1
    assert restored["branding"]["company_name"] == "Acme Lab"
    assert restored["branding"]["logo_bytes"] == b"fake-logo"
    assert restored["comparison_workspace"]["notes"] == "Synthetic comparison notes"
    assert restored["dsc_state_synthetic_dsc"]["peaks"][0].peak_temperature == pytest.approx(250.0)
    assert restored["dsc_state_synthetic_dsc"]["glass_transitions"][0].tg_midpoint == pytest.approx(120.0)
    assert restored["tga_state_synthetic_tga"]["tga_result"] is not None
    assert restored["tga_state_synthetic_tga"]["tga_result"].steps[0].mass_loss_percent == pytest.approx(12.0)


def test_load_project_archive_missing_manifest_raises():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("results.json", json.dumps({}))
        archive.writestr("history.json", json.dumps([]))
    buffer.seek(0)

    with pytest.raises(ValueError, match="manifest.json"):
        load_project_archive(buffer)


def test_load_project_archive_duplicate_dataset_key_raises():
    manifest = {
        "app_version": "1.1",
        "created_at": "2026-03-07T12:00:00",
        "updated_at": "2026-03-07T12:00:00",
        "active_dataset": None,
        "datasets": [
            {
                "key": "duplicate",
                "archive_path": "datasets/a.csv",
                "display_name": "duplicate",
                "data_type": "DSC",
                "units": {"temperature": "degC", "signal": "mW/mg"},
                "original_columns": {"temperature": "temperature", "signal": "signal"},
                "metadata": {},
                "file_path": "",
            },
            {
                "key": "duplicate",
                "archive_path": "datasets/b.csv",
                "display_name": "duplicate",
                "data_type": "DSC",
                "units": {"temperature": "degC", "signal": "mW/mg"},
                "original_columns": {"temperature": "temperature", "signal": "signal"},
                "metadata": {},
                "file_path": "",
            },
        ],
        "analysis_states": {"dsc": {}, "tga": {}},
        "figure_files": {},
    }

    csv_bytes = pd.DataFrame({"temperature": [1, 2], "signal": [3, 4]}).to_csv(index=False).encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("results.json", json.dumps({}))
        archive.writestr("history.json", json.dumps([]))
        archive.writestr("datasets/a.csv", csv_bytes)
        archive.writestr("datasets/b.csv", csv_bytes)
    buffer.seek(0)

    with pytest.raises(ValueError, match="Duplicate dataset key"):
        load_project_archive(buffer)
