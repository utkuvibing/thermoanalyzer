from __future__ import annotations

import json
from pathlib import Path

from core.processing_schema import ensure_processing_payload
from core.result_serialization import serialize_dsc_result
from core.peak_analysis import ThermalPeak
from utils.diagnostics import (
    configure_diagnostics_logger,
    get_default_log_file,
    make_error_id,
    record_exception,
    serialize_support_snapshot,
)


def test_make_error_id_uses_stable_area_prefix():
    error_id = make_error_id("report")
    assert error_id.startswith("TA-REPORT-")


def test_default_log_file_uses_thermoanalyzer_home_when_set(monkeypatch, tmp_path):
    monkeypatch.setenv("THERMOANALYZER_HOME", str(tmp_path))
    assert get_default_log_file() == Path(tmp_path) / "support_logs" / "thermoanalyzer_support.log"


def test_serialize_support_snapshot_includes_recent_support_events_and_results(thermal_dataset, tmp_path):
    log_path = tmp_path / "diagnostics.log"
    configure_diagnostics_logger(log_path)

    session_state = {
        "datasets": {"synthetic_dsc": thermal_dataset},
        "results": {
            "dsc_synthetic_dsc": serialize_dsc_result(
                "synthetic_dsc",
                thermal_dataset,
                [
                    ThermalPeak(
                        peak_index=1,
                        peak_temperature=231.9,
                        peak_signal=2.0,
                        onset_temperature=228.0,
                        endset_temperature=236.0,
                        area=12.3,
                        fwhm=4.5,
                        peak_type="endotherm",
                        height=1.9,
                    )
                ],
                processing=ensure_processing_payload(
                    analysis_type="DSC",
                    workflow_template="dsc.general",
                    workflow_template_label="General DSC",
                ),
                provenance={"saved_at_utc": "2026-03-07T12:00:00+00:00"},
                validation={"status": "warn", "issues": [], "warnings": ["Calibration identifier is not recorded for this DSC dataset."]},
            )
        },
        "analysis_history": [{"event_id": "evt-1", "action": "Data Loaded"}],
        "support_events": [],
        "comparison_workspace": {"analysis_type": "DSC", "selected_datasets": ["synthetic_dsc"], "figure_key": None},
        "branding": {"report_title": "ThermoAnalyzer Professional Report", "company_name": "Acme"},
        "license_state": {"status": "development", "source": "local", "commercial_mode": False},
        "diagnostics_log_path": str(log_path),
    }

    try:
        raise ValueError("Synthetic export failure")
    except ValueError as exc:
        error_id = record_exception(
            session_state,
            area="export",
            action="result_exports",
            message="Preparing normalized result exports failed.",
            exception=exc,
        )

    snapshot_bytes = serialize_support_snapshot(session_state, app_version="2.0", log_file=log_path)
    snapshot = json.loads(snapshot_bytes.decode("utf-8"))

    assert snapshot["app_version"] == "2.0"
    assert snapshot["dataset_count"] == 1
    assert snapshot["valid_result_count"] == 1
    assert snapshot["support_events_tail"][-1]["error_id"] == error_id
    assert snapshot["results"][0]["workflow_template_id"] == "dsc.general"
    assert snapshot["diagnostics_log_tail"]
