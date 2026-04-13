"""Registry-backed analysis execution helpers for backend endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Mapping

from core.batch_runner import normalize_batch_summary_rows, summarize_batch_outcomes
from core.modalities import analysis_state_key, require_stable_modality
from core.processing_schema import get_workflow_templates


def _workflow_template_label(analysis_type: str, workflow_template_id: str) -> str:
    for entry in get_workflow_templates(analysis_type):
        if entry.get("id") == workflow_template_id:
            return str(entry.get("label") or workflow_template_id)
    return workflow_template_id


def _dataset_type(dataset: Any) -> str:
    return str(getattr(dataset, "data_type", "unknown") or "unknown").upper()


def _sample_name(dataset: Any, dataset_key: str) -> str:
    return (getattr(dataset, "metadata", {}) or {}).get("sample_name") or dataset_key


def _calibration_state(dataset: Any) -> str:
    return (getattr(dataset, "metadata", {}) or {}).get("calibration_status") or "unknown"


def _failed_batch_row(
    *,
    dataset_key: str,
    analysis_type: str,
    workflow_template_id: str,
    workflow_template_label: str,
    message: str,
    sample_name: str | None = None,
    calibration_state: str = "unknown",
) -> dict[str, Any]:
    return {
        "dataset_key": dataset_key,
        "analysis_type": analysis_type,
        "sample_name": sample_name or dataset_key,
        "workflow_template_id": workflow_template_id,
        "workflow_template": workflow_template_label,
        "execution_status": "failed",
        "validation_status": "not_run",
        "warning_count": 0,
        "issue_count": 1,
        "calibration_state": calibration_state,
        "reference_state": "not_run",
        "result_id": None,
        "failure_reason": message,
        "message": message,
        "error_id": "",
        "peak_count": 0,
        "match_status": "not_run",
        "top_match_id": None,
        "top_match_score": None,
        "confidence_band": "not_run",
    }


def _blocked_batch_row(
    *,
    dataset_key: str,
    analysis_type: str,
    workflow_template_id: str,
    workflow_template_label: str,
    sample_name: str,
    calibration_state: str,
    message: str,
) -> dict[str, Any]:
    return {
        "dataset_key": dataset_key,
        "analysis_type": analysis_type,
        "sample_name": sample_name,
        "workflow_template_id": workflow_template_id,
        "workflow_template": workflow_template_label,
        "execution_status": "blocked",
        "validation_status": "fail",
        "warning_count": 0,
        "issue_count": 1,
        "calibration_state": calibration_state,
        "reference_state": "not_run",
        "result_id": None,
        "failure_reason": message,
        "message": message,
        "error_id": "",
        "peak_count": 0,
        "match_status": "not_run",
        "top_match_id": None,
        "top_match_score": None,
        "confidence_band": "not_run",
    }


def _select_dataset_keys(
    state: Mapping[str, Any],
    requested_keys: list[str] | None,
) -> list[str]:
    compare_workspace = state.get("comparison_workspace", {}) or {}
    selected_from_workspace = list(compare_workspace.get("selected_datasets") or [])
    raw_keys = list(requested_keys) if requested_keys is not None else selected_from_workspace
    selected_keys: list[str] = []
    for key in raw_keys:
        token = str(key)
        if token and token not in selected_keys:
            selected_keys.append(token)
    return selected_keys


def run_single_analysis(
    *,
    state: dict[str, Any],
    dataset_key: str,
    analysis_type: str,
    workflow_template_id: str | None,
    app_version: str | None,
    run_id: str | None = None,
    unit_mode: str | None = None,
) -> dict[str, Any]:
    """Run one stable modality analysis against one dataset."""
    spec = require_stable_modality(analysis_type)
    dataset = (state.get("datasets") or {}).get(dataset_key)
    if dataset is None:
        raise KeyError(f"Unknown dataset_key: {dataset_key}")

    dataset_type = _dataset_type(dataset)
    if not spec.adapter.is_dataset_eligible(dataset_type):
        raise ValueError(
            f"Dataset '{dataset_key}' is not eligible for {spec.analysis_type} analysis."
        )

    resolved_template_id = workflow_template_id or spec.default_workflow_template_id
    resolved_template_label = _workflow_template_label(spec.analysis_type, resolved_template_id)
    state_key = analysis_state_key(spec.analysis_type, dataset_key)
    existing_state = state.get(state_key, {}) or {}
    execution_id = run_id or f"desktop_single_{uuid.uuid4().hex[:8]}"

    try:
        outcome = spec.adapter.run(
            dataset_key=dataset_key,
            dataset=dataset,
            workflow_template_id=resolved_template_id,
            existing_processing=existing_state.get("processing"),
            analysis_history=state.get("analysis_history", []),
            analyst_name=((state.get("branding") or {}).get("analyst_name") or ""),
            app_version=app_version,
            batch_run_id=execution_id,
            unit_mode=unit_mode,
        )
    except Exception as exc:  # pragma: no cover - covered by API-level tests
        message = str(exc)
        return {
            "analysis_type": spec.analysis_type,
            "workflow_template_id": resolved_template_id,
            "workflow_template_label": resolved_template_label,
            "execution_status": "failed",
            "result_id": None,
            "failure_reason": message,
            "validation": {"status": "error", "warnings": [], "issues": [message]},
            "provenance": {},
            "record": None,
            "state_key": state_key,
            "state_payload": None,
        }

    validation = dict(outcome.get("validation") or {})
    record = dict(outcome.get("record") or {})
    execution_status = str(outcome.get("status") or "failed")
    result_id = record.get("id")
    failure_reason = None
    if execution_status != "saved":
        failure_reason = (
            (outcome.get("summary_row") or {}).get("failure_reason")
            or "Analysis did not save a result."
        )

    return {
        "analysis_type": spec.analysis_type,
        "workflow_template_id": resolved_template_id,
        "workflow_template_label": resolved_template_label,
        "execution_status": execution_status,
        "result_id": result_id,
        "failure_reason": failure_reason,
        "validation": validation,
        "provenance": dict(record.get("provenance") or {}),
        "record": record or None,
        "state_key": state_key,
        "state_payload": outcome.get("state") or {},
    }


def run_batch_analysis(
    *,
    state: dict[str, Any],
    analysis_type: str,
    workflow_template_id: str | None,
    dataset_keys: list[str] | None,
    app_version: str | None,
) -> dict[str, Any]:
    """Run one stable modality batch against selected datasets."""
    spec = require_stable_modality(analysis_type)
    resolved_template_id = workflow_template_id or spec.default_workflow_template_id
    resolved_template_label = _workflow_template_label(spec.analysis_type, resolved_template_id)
    selected_dataset_keys = _select_dataset_keys(state, dataset_keys)
    if not selected_dataset_keys:
        raise ValueError("No datasets selected for batch run.")

    batch_run_id = (
        f"batch_{spec.analysis_type.lower()}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
    )
    datasets = state.get("datasets") or {}
    analysis_history = state.get("analysis_history", [])
    analyst_name = ((state.get("branding") or {}).get("analyst_name") or "")
    summary_rows: list[dict[str, Any]] = []
    saved_result_ids: list[str] = []

    for dataset_key in selected_dataset_keys:
        dataset = datasets.get(dataset_key)
        if dataset is None:
            summary_rows.append(
                _failed_batch_row(
                    dataset_key=dataset_key,
                    analysis_type=spec.analysis_type,
                    workflow_template_id=resolved_template_id,
                    workflow_template_label=resolved_template_label,
                    message="Dataset not found in workspace.",
                )
            )
            continue

        dataset_type = _dataset_type(dataset)
        if not spec.adapter.is_dataset_eligible(dataset_type):
            message = (
                f"Dataset '{dataset_key}' ({dataset_type}) is not compatible with "
                f"{spec.analysis_type} batch run."
            )
            summary_rows.append(
                _blocked_batch_row(
                    dataset_key=dataset_key,
                    analysis_type=spec.analysis_type,
                    workflow_template_id=resolved_template_id,
                    workflow_template_label=resolved_template_label,
                    sample_name=_sample_name(dataset, dataset_key),
                    calibration_state=_calibration_state(dataset),
                    message=message,
                )
            )
            continue

        state_key = analysis_state_key(spec.analysis_type, dataset_key)
        existing_state = state.get(state_key, {}) or {}
        try:
            outcome = spec.adapter.run(
                dataset_key=dataset_key,
                dataset=dataset,
                workflow_template_id=resolved_template_id,
                existing_processing=existing_state.get("processing"),
                analysis_history=analysis_history,
                analyst_name=analyst_name,
                app_version=app_version,
                batch_run_id=batch_run_id,
            )
            row = dict(outcome.get("summary_row") or {})
            summary_rows.append(row)
            record = dict(outcome.get("record") or {})
            if outcome.get("status") == "saved" and record.get("id"):
                result_id = str(record["id"])
                state.setdefault("results", {})[result_id] = record
                state[state_key] = outcome.get("state") or {}
                saved_result_ids.append(result_id)
        except Exception as exc:  # pragma: no cover - covered by API-level tests
            summary_rows.append(
                _failed_batch_row(
                    dataset_key=dataset_key,
                    analysis_type=spec.analysis_type,
                    workflow_template_id=resolved_template_id,
                    workflow_template_label=resolved_template_label,
                    sample_name=_sample_name(dataset, dataset_key),
                    calibration_state=_calibration_state(dataset),
                    message=str(exc),
                )
            )

    normalized_rows = normalize_batch_summary_rows(summary_rows)
    outcomes = summarize_batch_outcomes(normalized_rows)

    return {
        "analysis_type": spec.analysis_type,
        "workflow_template_id": resolved_template_id,
        "workflow_template_label": resolved_template_label,
        "batch_run_id": batch_run_id,
        "selected_dataset_keys": selected_dataset_keys,
        "batch_summary": normalized_rows,
        "outcomes": outcomes,
        "saved_result_ids": saved_result_ids,
    }
