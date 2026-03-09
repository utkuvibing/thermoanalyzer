"""Workspace/compare context helpers for desktop usability endpoints."""

from __future__ import annotations

import copy
from datetime import datetime
from typing import Any

from backend.detail import normalize_compare_workspace
from backend.workspace import add_history_event, summarize_dataset, summarize_result
from core.result_serialization import split_valid_results


def _latest_result_summary(state: dict[str, Any]):
    valid_results, _issues = split_valid_results((state.get("results") or {}))
    if not valid_results:
        return None
    items = [summarize_result(record) for record in valid_results.values()]
    items.sort(key=lambda item: (item.saved_at_utc or "", item.id), reverse=True)
    return items[0]


def build_workspace_context(state: dict[str, Any], *, history_limit: int = 8) -> dict[str, Any]:
    datasets = (state.get("datasets") or {})
    active_dataset_key = state.get("active_dataset")
    active_dataset = summarize_dataset(active_dataset_key, datasets[active_dataset_key]) if active_dataset_key in datasets else None
    compare_workspace = normalize_compare_workspace(state)

    selected_dataset_summaries = []
    for dataset_key in compare_workspace.selected_datasets:
        dataset = datasets.get(dataset_key)
        if dataset is None:
            continue
        selected_dataset_summaries.append(summarize_dataset(dataset_key, dataset))

    history = state.get("analysis_history") or []
    return {
        "active_dataset_key": active_dataset_key,
        "active_dataset": active_dataset,
        "latest_result": _latest_result_summary(state),
        "compare_workspace": compare_workspace,
        "compare_selected_datasets": selected_dataset_summaries,
        "recent_history": copy.deepcopy(history[-history_limit:]),
    }


def set_active_dataset(state: dict[str, Any], dataset_key: str):
    key = str(dataset_key)
    datasets = (state.get("datasets") or {})
    dataset = datasets.get(key)
    if dataset is None:
        raise KeyError(f"Unknown dataset_key: {key}")

    previous = state.get("active_dataset")
    state["active_dataset"] = key
    if previous != key:
        add_history_event(
            state,
            action="Active Dataset Set",
            details=f"{previous or '-'} -> {key}",
            dataset_key=key,
        )
    return summarize_dataset(key, dataset)


def update_compare_selection(state: dict[str, Any], *, operation: str, dataset_keys: list[str] | None):
    token = str(operation or "").strip().lower()
    if token not in {"add", "remove", "replace", "clear"}:
        raise ValueError("operation must be one of: add, remove, replace, clear.")

    datasets = set((state.get("datasets") or {}).keys())
    workspace = state.setdefault("comparison_workspace", {})
    current = []
    for key in workspace.get("selected_datasets") or []:
        key = str(key)
        if key in datasets and key not in current:
            current.append(key)

    requested = []
    for key in dataset_keys or []:
        key = str(key)
        if key in datasets and key not in requested:
            requested.append(key)

    if token == "add":
        selected = current + [key for key in requested if key not in current]
    elif token == "remove":
        requested_set = set(requested)
        selected = [key for key in current if key not in requested_set]
    elif token == "replace":
        selected = requested
    else:  # clear
        selected = []

    workspace["selected_datasets"] = selected
    workspace["saved_at"] = datetime.now().isoformat(timespec="seconds")
    add_history_event(
        state,
        action="Compare Selection Updated",
        details=f"{token}: {', '.join(selected) if selected else 'none'}",
        dataset_key=state.get("active_dataset"),
    )
    return normalize_compare_workspace(state)
