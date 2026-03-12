"""Detail payload helpers for dataset/result/compare backend endpoints."""

from __future__ import annotations

import copy
from datetime import datetime
from typing import Any

import pandas as pd

from backend.models import CompareWorkspacePayload
from backend.workspace import summarize_dataset, summarize_result
from core.modalities import get_modality, stable_analysis_types
from core.result_serialization import split_valid_results
from core.validation import validate_thermal_dataset


def _records_preview(frame: pd.DataFrame, *, limit: int = 20) -> list[dict[str, Any]]:
    preview = frame.head(limit).copy()
    preview = preview.where(pd.notna(preview), None)
    return preview.to_dict(orient="records")


def _dataset_matches_analysis(dataset: Any, analysis_type: str) -> bool:
    modality = get_modality(analysis_type)
    if modality is None:
        return False
    dataset_type = str(getattr(dataset, "data_type", "UNKNOWN") or "UNKNOWN")
    return modality.adapter.is_dataset_eligible(dataset_type)


def _filter_selected_datasets(state: dict[str, Any], *, analysis_type: str, selected_datasets: list[str]) -> list[str]:
    datasets = state.get("datasets", {}) or {}
    filtered: list[str] = []
    for item in selected_datasets:
        key = str(item)
        dataset = datasets.get(key)
        if dataset is None:
            continue
        if not _dataset_matches_analysis(dataset, analysis_type):
            continue
        if key not in filtered:
            filtered.append(key)
    return filtered


def build_dataset_detail(state: dict[str, Any], dataset_key: str) -> dict[str, Any]:
    datasets = state.get("datasets", {}) or {}
    dataset = datasets.get(dataset_key)
    if dataset is None:
        raise KeyError(f"Unknown dataset_key: {dataset_key}")

    validation = validate_thermal_dataset(dataset, analysis_type=getattr(dataset, "data_type", "unknown"))
    compare_workspace = normalize_compare_workspace(state)
    selected_datasets = compare_workspace.selected_datasets

    return {
        "dataset": summarize_dataset(dataset_key, dataset),
        "validation": validation,
        "metadata": copy.deepcopy(getattr(dataset, "metadata", {}) or {}),
        "units": copy.deepcopy(getattr(dataset, "units", {}) or {}),
        "original_columns": copy.deepcopy(getattr(dataset, "original_columns", {}) or {}),
        "data_preview": _records_preview(getattr(dataset, "data")),
        "compare_selected": dataset_key in selected_datasets,
    }


def build_result_detail(state: dict[str, Any], result_id: str) -> dict[str, Any]:
    results = state.get("results", {}) or {}
    valid_results, issues = split_valid_results(results)
    record = valid_results.get(result_id)
    if record is None:
        if result_id in results:
            issue_text = "; ".join([issue for issue in issues if issue.startswith(f"{result_id}:")]) or "invalid result record"
            raise ValueError(f"Result '{result_id}' is present but invalid: {issue_text}")
        raise KeyError(f"Unknown result_id: {result_id}")

    rows = record.get("rows") or []
    frame = pd.DataFrame(rows) if rows else pd.DataFrame()
    return {
        "result": summarize_result(record),
        "summary": copy.deepcopy(record.get("summary") or {}),
        "processing": copy.deepcopy(record.get("processing") or {}),
        "provenance": copy.deepcopy(record.get("provenance") or {}),
        "validation": copy.deepcopy(record.get("validation") or {}),
        "review": copy.deepcopy(record.get("review") or {}),
        "rows_preview": _records_preview(frame) if not frame.empty else [],
        "row_count": len(rows),
    }


def normalize_compare_workspace(state: dict[str, Any]) -> CompareWorkspacePayload:
    raw = state.get("comparison_workspace", {}) or {}
    stable_types = stable_analysis_types()
    default_type = stable_types[0] if stable_types else "DSC"
    analysis_type = str(raw.get("analysis_type") or default_type).upper()
    if analysis_type not in stable_types:
        analysis_type = default_type
    selected_datasets = _filter_selected_datasets(
        state,
        analysis_type=analysis_type,
        selected_datasets=list(raw.get("selected_datasets") or []),
    )
    return CompareWorkspacePayload(
        analysis_type=analysis_type,
        selected_datasets=selected_datasets,
        notes=str(raw.get("notes") or ""),
        figure_key=raw.get("figure_key"),
        saved_at=raw.get("saved_at"),
        batch_run_id=raw.get("batch_run_id"),
        batch_template_id=raw.get("batch_template_id"),
        batch_template_label=raw.get("batch_template_label"),
        batch_completed_at=raw.get("batch_completed_at"),
        batch_summary=list(raw.get("batch_summary") or []),
        batch_result_ids=list(raw.get("batch_result_ids") or []),
        batch_last_feedback=dict(raw.get("batch_last_feedback") or {}),
    )


def update_compare_workspace(
    state: dict[str, Any],
    *,
    analysis_type: str | None,
    selected_datasets: list[str] | None,
    notes: str | None,
) -> CompareWorkspacePayload:
    workspace = state.setdefault("comparison_workspace", {})
    stable_types = stable_analysis_types()
    default_type = stable_types[0] if stable_types else "DSC"
    existing_analysis = str(workspace.get("analysis_type") or default_type).upper()
    if existing_analysis not in stable_types:
        existing_analysis = default_type
    normalized_analysis = existing_analysis

    if analysis_type is not None:
        token = str(analysis_type or "").upper()
        if token not in stable_types:
            raise ValueError(f"analysis_type must be one of: {', '.join(stable_types)}.")
        normalized_analysis = token
    workspace["analysis_type"] = normalized_analysis

    if selected_datasets is not None:
        workspace["selected_datasets"] = _filter_selected_datasets(
            state,
            analysis_type=normalized_analysis,
            selected_datasets=selected_datasets,
        )
    elif analysis_type is not None:
        workspace["selected_datasets"] = _filter_selected_datasets(
            state,
            analysis_type=normalized_analysis,
            selected_datasets=list(workspace.get("selected_datasets") or []),
        )

    if notes is not None:
        workspace["notes"] = str(notes)

    workspace["saved_at"] = datetime.now().isoformat(timespec="seconds")
    payload = normalize_compare_workspace(state)
    if hasattr(payload, "model_dump"):
        workspace.update(payload.model_dump())
    else:  # pragma: no cover - pydantic v1 compatibility
        workspace.update(payload.dict())
    return payload
