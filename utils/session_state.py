"""Shared Streamlit session-state helpers."""

from __future__ import annotations

import copy

import streamlit as st


SESSION_DEFAULTS = {
    "ui_language": "tr",
    "datasets": {},
    "active_dataset": None,
    "results": {},
    "figures": {},
    "analysis_history": [],
    "support_events": [],
    "diagnostics_log_path": "",
    "branding": {
        "report_title": "ThermoAnalyzer Professional Report",
        "company_name": "",
        "lab_name": "",
        "analyst_name": "",
        "report_notes": "",
        "logo_bytes": None,
        "logo_name": "",
    },
    "comparison_workspace": {
        "analysis_type": "DSC",
        "selected_datasets": [],
        "notes": "",
        "figure_key": None,
        "saved_at": None,
    },
}

EPHEMERAL_KEYS = {
    "kissinger_result",
    "ofw_results",
    "friedman_results",
    "deconv_result",
    "project_archive_bytes",
    "project_archive_ready",
    "prepared_data_exports",
    "prepared_results_csv",
    "prepared_results_xlsx",
    "prepared_report_docx",
    "prepared_report_pdf",
    "prepared_support_snapshot",
}

ANALYSIS_PREFIXES = ("dsc_state_", "tga_state_", "dta_state_")
ANALYSIS_HISTORY_LIMIT = 20


def ensure_session_state() -> None:
    """Initialize shared session-state keys."""
    for key, default in SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = copy.deepcopy(default)


def clear_project_state() -> None:
    """Clear all project-related session-state entries."""
    keys = list(st.session_state.keys())
    for key in keys:
        if key in SESSION_DEFAULTS or key in EPHEMERAL_KEYS or key.startswith(ANALYSIS_PREFIXES):
            del st.session_state[key]
    ensure_session_state()


def replace_project_state(project_state: dict) -> None:
    """Replace current project state with a loaded project."""
    clear_project_state()
    for key, value in project_state.items():
        st.session_state[key] = value
    ensure_session_state()


def init_analysis_state_history(state: dict) -> None:
    """Ensure per-analysis undo/redo stacks exist."""
    state.setdefault("_undo_stack", [])
    state.setdefault("_redo_stack", [])
    state.setdefault("_render_revision", 0)


def make_analysis_state_snapshot(state: dict, tracked_keys: tuple[str, ...] | list[str]) -> dict:
    """Capture a deep-copied snapshot of tracked analysis fields."""
    return {key: copy.deepcopy(state.get(key)) for key in tracked_keys}


def restore_analysis_state(state: dict, snapshot: dict, default_state: dict) -> None:
    """Restore tracked analysis fields from a snapshot."""
    for key, value in default_state.items():
        state[key] = copy.deepcopy(value)
    for key, value in snapshot.items():
        state[key] = copy.deepcopy(value)


def push_analysis_undo_snapshot(
    state: dict,
    tracked_keys: tuple[str, ...] | list[str],
    *,
    limit: int = ANALYSIS_HISTORY_LIMIT,
) -> bool:
    """Push the current tracked state into the undo stack and clear redo."""
    init_analysis_state_history(state)
    snapshot = make_analysis_state_snapshot(state, tracked_keys)
    if state["_undo_stack"] and analysis_state_snapshots_equal(state["_undo_stack"][-1], snapshot):
        state["_redo_stack"] = []
        return False
    state["_undo_stack"].append(snapshot)
    if len(state["_undo_stack"]) > limit:
        state["_undo_stack"] = state["_undo_stack"][-limit:]
    state["_redo_stack"] = []
    return True


def reset_analysis_state(
    state: dict,
    default_state: dict,
    *,
    limit: int = ANALYSIS_HISTORY_LIMIT,
) -> bool:
    """Reset tracked analysis fields to their defaults."""
    tracked_keys = tuple(default_state.keys())
    current = make_analysis_state_snapshot(state, tracked_keys)
    if analysis_state_snapshots_equal(current, default_state):
        return False
    init_analysis_state_history(state)
    state["_undo_stack"].append(current)
    if len(state["_undo_stack"]) > limit:
        state["_undo_stack"] = state["_undo_stack"][-limit:]
    state["_redo_stack"] = []
    restore_analysis_state(state, default_state, default_state)
    return True


def undo_analysis_state(state: dict, default_state: dict) -> bool:
    """Restore the previous tracked analysis snapshot if available."""
    init_analysis_state_history(state)
    if not state["_undo_stack"]:
        return False
    tracked_keys = tuple(default_state.keys())
    current = make_analysis_state_snapshot(state, tracked_keys)
    target = state["_undo_stack"].pop()
    state["_redo_stack"].append(current)
    restore_analysis_state(state, target, default_state)
    return True


def redo_analysis_state(state: dict, default_state: dict) -> bool:
    """Reapply the next tracked analysis snapshot if available."""
    init_analysis_state_history(state)
    if not state["_redo_stack"]:
        return False
    tracked_keys = tuple(default_state.keys())
    current = make_analysis_state_snapshot(state, tracked_keys)
    target = state["_redo_stack"].pop()
    state["_undo_stack"].append(current)
    restore_analysis_state(state, target, default_state)
    return True


def advance_analysis_render_revision(state: dict) -> int:
    """Force plot widgets to remount on the next render."""
    init_analysis_state_history(state)
    state["_render_revision"] = int(state.get("_render_revision", 0)) + 1
    return state["_render_revision"]


def analysis_state_snapshots_equal(left, right) -> bool:
    """Recursively compare analysis snapshots, including numpy arrays."""
    if left is right:
        return True
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        if left.keys() != right.keys():
            return False
        return all(analysis_state_snapshots_equal(left[key], right[key]) for key in left)
    if isinstance(left, (list, tuple)):
        if len(left) != len(right):
            return False
        return all(analysis_state_snapshots_equal(a, b) for a, b in zip(left, right))
    if hasattr(left, "shape") and hasattr(right, "shape"):
        try:
            import numpy as np

            return np.array_equal(left, right, equal_nan=True)
        except Exception:
            return False
    return left == right
