"""Project archive save/load helpers for ThermoAnalyzer."""

from __future__ import annotations

import copy
import io
import json
import re
import zipfile
from datetime import datetime
from typing import Any, Mapping

import numpy as np
import pandas as pd

from core.data_io import ThermalDataset
from core.result_serialization import (
    glass_transition_from_dict,
    glass_transition_to_dict,
    mass_loss_step_from_dict,
    mass_loss_step_to_dict,
    split_valid_results,
    thermal_peak_from_dict,
    thermal_peak_to_dict,
)
from core.tga_processor import TGAResult


PROJECT_EXTENSION = ".thermozip"
APP_VERSION = "2.0"


def serialize_project(session_state: Mapping[str, Any], app_version: str = APP_VERSION) -> dict[str, Any]:
    """Serialize project state into manifest/results/history payloads."""
    datasets = session_state.get("datasets", {})
    results, _ = split_valid_results(session_state.get("results", {}))
    figures = session_state.get("figures", {}) or {}

    manifest = {
        "app_version": app_version,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "active_dataset": session_state.get("active_dataset"),
        "datasets": [],
        "analysis_states": {
            "dsc": {},
            "tga": {},
        },
        "figure_files": {},
        "branding": _serialize_branding(session_state.get("branding", {})),
        "comparison_workspace": copy.deepcopy(session_state.get("comparison_workspace", {})),
    }

    dataset_csv: dict[str, bytes] = {}
    for index, (dataset_key, dataset) in enumerate(datasets.items(), start=1):
        archive_path = f"datasets/{index:02d}_{_slugify(dataset_key)}.csv"
        dataset_csv[archive_path] = dataset.data.to_csv(index=False).encode("utf-8")
        manifest["datasets"].append(
            {
                "key": dataset_key,
                "archive_path": archive_path,
                "display_name": dataset.metadata.get("file_name", dataset_key),
                "data_type": dataset.data_type,
                "units": dataset.units,
                "original_columns": dataset.original_columns,
                "metadata": dataset.metadata,
                "file_path": dataset.file_path,
            }
        )

        dsc_state_key = f"dsc_state_{dataset_key}"
        if dsc_state_key in session_state:
            manifest["analysis_states"]["dsc"][dataset_key] = _serialize_dsc_state(
                session_state[dsc_state_key]
            )

        tga_state_key = f"tga_state_{dataset_key}"
        if tga_state_key in session_state:
            manifest["analysis_states"]["tga"][dataset_key] = _serialize_tga_state(
                session_state[tga_state_key]
            )

    figure_bytes: dict[str, bytes] = {}
    for index, (figure_key, png_bytes) in enumerate(figures.items(), start=1):
        archive_path = f"figures/{index:02d}_{_slugify(figure_key)}.png"
        manifest["figure_files"][figure_key] = archive_path
        figure_bytes[archive_path] = png_bytes

    branding_assets: dict[str, bytes] = {}
    branding = session_state.get("branding", {}) or {}
    logo_bytes = branding.get("logo_bytes")
    if logo_bytes:
        archive_path = "branding/logo.bin"
        manifest["branding"]["logo_file"] = archive_path
        branding_assets[archive_path] = logo_bytes

    return {
        "manifest": manifest,
        "results": results,
        "history": session_state.get("analysis_history", []),
        "datasets": dataset_csv,
        "figures": figure_bytes,
        "branding_assets": branding_assets,
    }


def deserialize_project(
    manifest: dict[str, Any],
    archive_members: dict[str, bytes],
    *,
    results_payload: dict[str, Any],
    history_payload: list[dict[str, Any]],
) -> dict[str, Any]:
    """Deserialize a project payload into session-state compatible data."""
    dataset_entries = manifest.get("datasets")
    if not isinstance(dataset_entries, list):
        raise ValueError("manifest.json is missing a valid 'datasets' list.")

    datasets: dict[str, ThermalDataset] = {}
    for entry in dataset_entries:
        if not isinstance(entry, dict):
            raise ValueError("manifest.json contains an invalid dataset entry.")
        dataset_key = entry.get("key")
        archive_path = entry.get("archive_path")
        if not dataset_key or not archive_path:
            raise ValueError("A dataset entry is missing 'key' or 'archive_path'.")
        if dataset_key in datasets:
            raise ValueError(f"Duplicate dataset key in project: {dataset_key}")
        if archive_path not in archive_members:
            raise ValueError(f"Missing dataset file in archive: {archive_path}")

        data = pd.read_csv(io.BytesIO(archive_members[archive_path]))
        datasets[dataset_key] = ThermalDataset(
            data=data,
            metadata=entry.get("metadata", {}),
            data_type=entry.get("data_type", "unknown"),
            units=entry.get("units", {}),
            original_columns=entry.get("original_columns", {}),
            file_path=entry.get("file_path", ""),
        )

    results, issues = split_valid_results(results_payload)
    if issues:
        raise ValueError("; ".join(issues))

    figures = {}
    for figure_key, archive_path in (manifest.get("figure_files") or {}).items():
        if archive_path not in archive_members:
            raise ValueError(f"Missing figure in archive: {archive_path}")
        figures[figure_key] = archive_members[archive_path]

    state: dict[str, Any] = {
        "datasets": datasets,
        "active_dataset": manifest.get("active_dataset"),
        "results": results,
        "figures": figures,
        "analysis_history": history_payload or [],
        "branding": _deserialize_branding(manifest, archive_members),
        "comparison_workspace": copy.deepcopy(manifest.get("comparison_workspace", {})),
    }

    analysis_states = manifest.get("analysis_states") or {}
    for dataset_key, payload in (analysis_states.get("dsc") or {}).items():
        state[f"dsc_state_{dataset_key}"] = _deserialize_dsc_state(payload)
    for dataset_key, payload in (analysis_states.get("tga") or {}).items():
        state[f"tga_state_{dataset_key}"] = _deserialize_tga_state(payload)

    return state


def save_project_archive(session_state: Mapping[str, Any], app_version: str = APP_VERSION) -> bytes:
    """Create a .thermozip archive from session state."""
    payload = serialize_project(session_state, app_version=app_version)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(payload["manifest"], indent=2, ensure_ascii=False))
        archive.writestr("results.json", json.dumps(payload["results"], indent=2, ensure_ascii=False))
        archive.writestr("history.json", json.dumps(payload["history"], indent=2, ensure_ascii=False))
        for archive_path, csv_bytes in payload["datasets"].items():
            archive.writestr(archive_path, csv_bytes)
        for archive_path, figure_bytes in payload["figures"].items():
            archive.writestr(archive_path, figure_bytes)
        for archive_path, raw_bytes in payload["branding_assets"].items():
            archive.writestr(archive_path, raw_bytes)
    return buffer.getvalue()


def load_project_archive(source: Any) -> dict[str, Any]:
    """Load a .thermozip archive and return session-state compatible data."""
    archive_bytes = _read_bytes(source)
    archive_members: dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(archive_bytes), "r") as archive:
        names = set(archive.namelist())
        required = {"manifest.json", "results.json", "history.json"}
        missing = sorted(required - names)
        if missing:
            raise ValueError(f"Project archive is missing required file(s): {', '.join(missing)}")

        for name in archive.namelist():
            archive_members[name] = archive.read(name)

    try:
        manifest = json.loads(archive_members["manifest.json"].decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"Could not parse manifest.json: {exc}") from exc

    try:
        results_payload = json.loads(archive_members["results.json"].decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"Could not parse results.json: {exc}") from exc

    try:
        history_payload = json.loads(archive_members["history.json"].decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"Could not parse history.json: {exc}") from exc

    if not isinstance(results_payload, dict):
        raise ValueError("results.json must contain an object.")
    if not isinstance(history_payload, list):
        raise ValueError("history.json must contain a list.")

    return deserialize_project(
        manifest,
        archive_members,
        results_payload=results_payload,
        history_payload=history_payload,
    )


def _serialize_dsc_state(state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "smoothed": _array_to_list(state.get("smoothed")),
        "baseline": _array_to_list(state.get("baseline")),
        "corrected": _array_to_list(state.get("corrected")),
        "peaks": [thermal_peak_to_dict(peak) for peak in state.get("peaks") or []],
        "glass_transitions": [
            glass_transition_to_dict(tg) for tg in state.get("glass_transitions") or []
        ],
    }


def _deserialize_dsc_state(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "smoothed": _list_to_array(payload.get("smoothed")),
        "baseline": _list_to_array(payload.get("baseline")),
        "corrected": _list_to_array(payload.get("corrected")),
        "peaks": [thermal_peak_from_dict(item) for item in payload.get("peaks", [])],
        "glass_transitions": [
            glass_transition_from_dict(item)
            for item in payload.get("glass_transitions", [])
        ],
        "processor": None,
    }


def _serialize_tga_state(state: Mapping[str, Any]) -> dict[str, Any]:
    result = state.get("tga_result")
    steps = []
    summary = {}
    if result is not None:
        steps = [mass_loss_step_to_dict(step) for step in result.steps]
        summary = {
            "total_mass_loss_percent": result.total_mass_loss_percent,
            "residue_percent": result.residue_percent,
        }
    return {
        "smoothed": _array_to_list(state.get("smoothed")),
        "dtg": _array_to_list(state.get("dtg")),
        "steps": steps,
        "summary": summary,
    }


def _deserialize_tga_state(payload: Mapping[str, Any]) -> dict[str, Any]:
    smoothed = _list_to_array(payload.get("smoothed"))
    dtg = _list_to_array(payload.get("dtg"))
    steps = [mass_loss_step_from_dict(item) for item in payload.get("steps", [])]
    summary = payload.get("summary") or {}
    tga_result = None
    if smoothed is not None and dtg is not None and summary:
        tga_result = TGAResult(
            steps=steps,
            dtg_peaks=[],
            dtg_signal=dtg,
            smoothed_signal=smoothed,
            total_mass_loss_percent=float(summary.get("total_mass_loss_percent", 0.0)),
            residue_percent=float(summary.get("residue_percent", 0.0)),
            metadata={},
        )
    return {
        "smoothed": smoothed,
        "dtg": dtg,
        "tga_result": tga_result,
    }


def _read_bytes(source: Any) -> bytes:
    if hasattr(source, "seek"):
        source.seek(0)
    if hasattr(source, "read"):
        raw = source.read()
        if isinstance(raw, str):
            return raw.encode("utf-8")
        return raw
    if isinstance(source, bytes):
        return source
    raise TypeError(f"Unsupported archive source type: {type(source)}")


def _array_to_list(value: Any) -> list[float] | None:
    if value is None:
        return None
    return np.asarray(value, dtype=float).tolist()


def _list_to_array(value: Any) -> np.ndarray | None:
    if value is None:
        return None
    return np.asarray(value, dtype=float)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return slug.strip("_") or "item"


def _serialize_branding(branding: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "report_title": branding.get("report_title", "ThermoAnalyzer Professional Report"),
        "company_name": branding.get("company_name", ""),
        "lab_name": branding.get("lab_name", ""),
        "analyst_name": branding.get("analyst_name", ""),
        "report_notes": branding.get("report_notes", ""),
        "logo_name": branding.get("logo_name", ""),
    }


def _deserialize_branding(manifest: Mapping[str, Any], archive_members: dict[str, bytes]) -> dict[str, Any]:
    branding = copy.deepcopy(manifest.get("branding", {}))
    logo_file = branding.pop("logo_file", None)
    if logo_file:
        if logo_file not in archive_members:
            raise ValueError(f"Missing branding asset in archive: {logo_file}")
        branding["logo_bytes"] = archive_members[logo_file]
    else:
        branding["logo_bytes"] = None
    branding.setdefault("logo_name", "")
    branding.setdefault("report_title", "ThermoAnalyzer Professional Report")
    branding.setdefault("company_name", "")
    branding.setdefault("lab_name", "")
    branding.setdefault("analyst_name", "")
    branding.setdefault("report_notes", "")
    return branding
