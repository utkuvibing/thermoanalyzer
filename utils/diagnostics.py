"""Structured logging and support-snapshot helpers."""

from __future__ import annotations

import json
import logging
import os
import traceback
import uuid
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from core.result_serialization import split_valid_results


LOGGER_NAME = "thermoanalyzer.diagnostics"
MAX_SUPPORT_EVENTS = 100
AREA_CODES = {
    "import": "IMPORT",
    "project_load": "PROJECT",
    "dsc_analysis": "DSC",
    "tga_analysis": "TGA",
    "export": "EXPORT",
    "report": "REPORT",
}


def get_default_log_dir() -> Path:
    """Return the default support-log directory for the current runtime."""
    root = os.getenv("THERMOANALYZER_HOME")
    if root:
        return Path(root) / "support_logs"
    return Path.cwd() / "support_logs"


def get_default_log_file() -> Path:
    """Return the default support-log file for the current runtime."""
    return get_default_log_dir() / "thermoanalyzer_support.log"


def configure_diagnostics_logger(log_file: str | Path | None = None) -> str:
    """Configure a rotating JSON-lines diagnostics logger once per process."""
    target = Path(log_file) if log_file else get_default_log_file()
    target.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not any(
        isinstance(handler, RotatingFileHandler) and Path(getattr(handler, "baseFilename", "")) == target
        for handler in logger.handlers
    ):
        handler = RotatingFileHandler(target, maxBytes=1_500_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

    return str(target)


def make_error_id(area: str) -> str:
    """Create a stable error identifier with a fixed area prefix."""
    code = AREA_CODES.get(area, "GENERAL")
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    suffix = uuid.uuid4().hex[:6].upper()
    return f"TA-{code}-{timestamp}-{suffix}"


def record_diagnostic_event(
    session_state: MutableMapping[str, Any] | None,
    *,
    area: str,
    action: str,
    status: str,
    message: str,
    context: Mapping[str, Any] | None = None,
    error_id: str | None = None,
    exception: BaseException | None = None,
) -> dict[str, Any]:
    """Record a structured diagnostics event and append it to the support timeline."""
    event = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "area": area,
        "action": action,
        "status": status,
        "message": message,
        "error_id": error_id,
        "context": dict(context or {}),
    }
    if exception is not None:
        event["exception_type"] = type(exception).__name__
        event["exception_message"] = str(exception)
        event["traceback"] = traceback.format_exc(limit=6)

    logger = logging.getLogger(LOGGER_NAME)
    line = json.dumps(event, ensure_ascii=False, sort_keys=True, default=str)
    if status == "error":
        logger.error(line)
    elif status == "warning":
        logger.warning(line)
    else:
        logger.info(line)

    if session_state is not None:
        events = session_state.setdefault("support_events", [])
        events.append(event)
        if len(events) > MAX_SUPPORT_EVENTS:
            del events[:-MAX_SUPPORT_EVENTS]
    return event


def record_exception(
    session_state: MutableMapping[str, Any] | None,
    *,
    area: str,
    action: str,
    message: str,
    context: Mapping[str, Any] | None = None,
    exception: BaseException,
) -> str:
    """Record an exception and return its stable error identifier."""
    error_id = make_error_id(area)
    record_diagnostic_event(
        session_state,
        area=area,
        action=action,
        status="error",
        message=message,
        context=context,
        error_id=error_id,
        exception=exception,
    )
    return error_id


def build_support_snapshot(
    session_state: Mapping[str, Any],
    *,
    app_version: str,
    log_file: str | Path | None = None,
) -> dict[str, Any]:
    """Build a support-friendly JSON snapshot without changing project archives."""
    datasets = session_state.get("datasets", {}) or {}
    valid_results, issues = split_valid_results(session_state.get("results", {}) or {})
    log_path = Path(log_file or session_state.get("diagnostics_log_path") or get_default_log_file())

    snapshot = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "app_version": app_version,
        "active_dataset": session_state.get("active_dataset"),
        "dataset_count": len(datasets),
        "valid_result_count": len(valid_results),
        "invalid_result_issues": issues,
        "datasets": [],
        "results": [],
        "analysis_history_tail": list((session_state.get("analysis_history") or [])[-25:]),
        "support_events_tail": list((session_state.get("support_events") or [])[-25:]),
        "comparison_workspace": {
            "analysis_type": (session_state.get("comparison_workspace") or {}).get("analysis_type"),
            "selected_datasets": list((session_state.get("comparison_workspace") or {}).get("selected_datasets") or []),
            "figure_key": (session_state.get("comparison_workspace") or {}).get("figure_key"),
        },
        "branding": {
            "report_title": (session_state.get("branding") or {}).get("report_title"),
            "company_name": (session_state.get("branding") or {}).get("company_name"),
            "lab_name": (session_state.get("branding") or {}).get("lab_name"),
            "analyst_name": (session_state.get("branding") or {}).get("analyst_name"),
        },
        "license_state": {
            "status": (session_state.get("license_state") or {}).get("status"),
            "source": (session_state.get("license_state") or {}).get("source"),
            "commercial_mode": (session_state.get("license_state") or {}).get("commercial_mode"),
        },
        "diagnostics_log_path": str(log_path),
        "diagnostics_log_tail": _tail_lines(log_path, line_count=40),
    }

    for dataset_key, dataset in datasets.items():
        snapshot["datasets"].append(
            {
                "key": dataset_key,
                "data_type": getattr(dataset, "data_type", "unknown"),
                "points": len(getattr(dataset, "data", [])),
                "sample_name": (getattr(dataset, "metadata", {}) or {}).get("sample_name"),
                "vendor": (getattr(dataset, "metadata", {}) or {}).get("vendor"),
                "instrument": (getattr(dataset, "metadata", {}) or {}).get("instrument"),
                "calibration_id": (getattr(dataset, "metadata", {}) or {}).get("calibration_id"),
                "calibration_status": (getattr(dataset, "metadata", {}) or {}).get("calibration_status"),
                "atmosphere": (getattr(dataset, "metadata", {}) or {}).get("atmosphere"),
                "atmosphere_status": (getattr(dataset, "metadata", {}) or {}).get("atmosphere_status"),
                "source_data_hash": (getattr(dataset, "metadata", {}) or {}).get("source_data_hash"),
            }
        )

    for record in valid_results.values():
        processing = record.get("processing") or {}
        method_context = processing.get("method_context") or {}
        provenance = record.get("provenance") or {}
        snapshot["results"].append(
            {
                "id": record["id"],
                "analysis_type": record["analysis_type"],
                "status": record["status"],
                "dataset_key": record.get("dataset_key"),
                "workflow_template": processing.get("workflow_template"),
                "workflow_template_id": processing.get("workflow_template_id"),
                "calibration_state": method_context.get("calibration_state") or provenance.get("calibration_state"),
                "reference_state": method_context.get("reference_state") or provenance.get("reference_state"),
                "reference_name": method_context.get("reference_name") or provenance.get("reference_name"),
                "saved_at_utc": provenance.get("saved_at_utc"),
                "validation_status": (record.get("validation") or {}).get("status"),
            }
        )

    return snapshot


def serialize_support_snapshot(
    session_state: Mapping[str, Any],
    *,
    app_version: str,
    log_file: str | Path | None = None,
) -> bytes:
    """Serialize a support snapshot to JSON bytes for download/attachment."""
    snapshot = build_support_snapshot(session_state, app_version=app_version, log_file=log_file)
    return json.dumps(snapshot, indent=2, ensure_ascii=False).encode("utf-8")


def _tail_lines(path: Path, *, line_count: int) -> list[str]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    return lines[-line_count:]
