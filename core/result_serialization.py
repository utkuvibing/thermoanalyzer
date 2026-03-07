"""Serializable result helpers for ThermoAnalyzer analysis outputs."""

from __future__ import annotations

import copy
import math
from typing import Any, Iterable

from core.dsc_processor import GlassTransition
from core.peak_analysis import ThermalPeak
from core.tga_processor import MassLossStep, TGAResult


REQUIRED_RESULT_KEYS = {
    "id",
    "analysis_type",
    "status",
    "dataset_key",
    "metadata",
    "summary",
    "rows",
    "artifacts",
}

VALID_STATUSES = {"stable", "experimental"}


def _clean_scalar(value: Any) -> Any:
    """Convert numpy-like scalars and non-finite floats to JSON-safe values."""
    if hasattr(value, "item") and callable(value.item):
        try:
            value = value.item()
        except Exception:
            pass
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def make_result_record(
    *,
    result_id: str,
    analysis_type: str,
    status: str,
    dataset_key: str | None,
    metadata: dict[str, Any] | None = None,
    summary: dict[str, Any] | None = None,
    rows: list[dict[str, Any]] | None = None,
    artifacts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a normalized result record."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Unsupported result status: {status}")

    return {
        "id": result_id,
        "analysis_type": analysis_type,
        "status": status,
        "dataset_key": dataset_key,
        "metadata": copy.deepcopy(metadata or {}),
        "summary": copy.deepcopy(summary or {}),
        "rows": copy.deepcopy(rows or []),
        "artifacts": copy.deepcopy(artifacts or {}),
    }


def thermal_peak_to_dict(peak: ThermalPeak) -> dict[str, Any]:
    """Serialize a ThermalPeak."""
    payload = {
        "peak_index": peak.peak_index,
        "peak_temperature": peak.peak_temperature,
        "peak_signal": peak.peak_signal,
        "onset_temperature": peak.onset_temperature,
        "endset_temperature": peak.endset_temperature,
        "area": peak.area,
        "fwhm": peak.fwhm,
        "peak_type": peak.peak_type,
        "height": peak.height,
    }
    direction = getattr(peak, "direction", None)
    if direction is not None:
        payload["direction"] = direction
    return {key: _clean_scalar(value) for key, value in payload.items()}


def thermal_peak_from_dict(payload: dict[str, Any]) -> ThermalPeak:
    """Deserialize a ThermalPeak."""
    peak = ThermalPeak(
        peak_index=int(payload["peak_index"]),
        peak_temperature=float(payload["peak_temperature"]),
        peak_signal=float(payload["peak_signal"]),
        onset_temperature=_to_optional_float(payload.get("onset_temperature")),
        endset_temperature=_to_optional_float(payload.get("endset_temperature")),
        area=_to_optional_float(payload.get("area")),
        fwhm=_to_optional_float(payload.get("fwhm")),
        peak_type=str(payload.get("peak_type", "unknown")),
        height=_to_optional_float(payload.get("height")),
    )
    direction = payload.get("direction")
    if direction is not None:
        try:
            object.__setattr__(peak, "direction", direction)
        except Exception:
            pass
    return peak


def glass_transition_to_dict(tg: GlassTransition) -> dict[str, Any]:
    """Serialize a GlassTransition."""
    return {
        "tg_midpoint": _clean_scalar(tg.tg_midpoint),
        "tg_onset": _clean_scalar(tg.tg_onset),
        "tg_endset": _clean_scalar(tg.tg_endset),
        "delta_cp": _clean_scalar(tg.delta_cp),
    }


def glass_transition_from_dict(payload: dict[str, Any]) -> GlassTransition:
    """Deserialize a GlassTransition."""
    return GlassTransition(
        tg_midpoint=float(payload["tg_midpoint"]),
        tg_onset=float(payload["tg_onset"]),
        tg_endset=float(payload["tg_endset"]),
        delta_cp=float(payload["delta_cp"]),
    )


def mass_loss_step_to_dict(step: MassLossStep) -> dict[str, Any]:
    """Serialize a MassLossStep."""
    return {
        "onset_temperature": _clean_scalar(step.onset_temperature),
        "endset_temperature": _clean_scalar(step.endset_temperature),
        "midpoint_temperature": _clean_scalar(step.midpoint_temperature),
        "mass_loss_percent": _clean_scalar(step.mass_loss_percent),
        "mass_loss_mg": _clean_scalar(step.mass_loss_mg),
        "residual_percent": _clean_scalar(step.residual_percent),
        "dtg_peak_temperature": _clean_scalar(step.dtg_peak_temperature),
    }


def mass_loss_step_from_dict(payload: dict[str, Any]) -> MassLossStep:
    """Deserialize a MassLossStep."""
    return MassLossStep(
        onset_temperature=float(payload["onset_temperature"]),
        endset_temperature=float(payload["endset_temperature"]),
        midpoint_temperature=float(payload["midpoint_temperature"]),
        mass_loss_percent=float(payload["mass_loss_percent"]),
        mass_loss_mg=_to_optional_float(payload.get("mass_loss_mg")),
        residual_percent=_to_optional_float(payload.get("residual_percent")),
        dtg_peak_temperature=_to_optional_float(payload.get("dtg_peak_temperature")),
    )


def serialize_dsc_result(
    dataset_key: str,
    dataset,
    peaks: Iterable[ThermalPeak],
    glass_transitions: Iterable[GlassTransition] | None = None,
    artifacts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Serialize a stable DSC analysis record."""
    peaks = list(peaks)
    glass_transitions = list(glass_transitions or [])
    rows = [
        {
            "peak_type": peak.peak_type,
            "peak_temperature": _clean_scalar(peak.peak_temperature),
            "onset_temperature": _clean_scalar(peak.onset_temperature),
            "endset_temperature": _clean_scalar(peak.endset_temperature),
            "area": _clean_scalar(peak.area),
            "fwhm": _clean_scalar(peak.fwhm),
            "height": _clean_scalar(peak.height),
        }
        for peak in peaks
    ]
    summary = {
        "peak_count": len(peaks),
        "sample_name": dataset.metadata.get("sample_name"),
        "sample_mass": dataset.metadata.get("sample_mass"),
        "heating_rate": dataset.metadata.get("heating_rate"),
        "glass_transition_count": len(glass_transitions),
    }
    if glass_transitions:
        first_tg = glass_transitions[0]
        summary.update(
            {
                "tg_midpoint": _clean_scalar(first_tg.tg_midpoint),
                "tg_onset": _clean_scalar(first_tg.tg_onset),
                "tg_endset": _clean_scalar(first_tg.tg_endset),
                "delta_cp": _clean_scalar(first_tg.delta_cp),
            }
        )
    return make_result_record(
        result_id=f"dsc_{dataset_key}",
        analysis_type="DSC",
        status="stable",
        dataset_key=dataset_key,
        metadata=dataset.metadata,
        summary=summary,
        rows=rows,
        artifacts=artifacts,
    )


def serialize_tga_result(
    dataset_key: str,
    dataset,
    result: TGAResult,
    artifacts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Serialize a stable TGA analysis record."""
    rows = [
        {
            "onset_temperature": _clean_scalar(step.onset_temperature),
            "midpoint_temperature": _clean_scalar(step.midpoint_temperature),
            "endset_temperature": _clean_scalar(step.endset_temperature),
            "mass_loss_percent": _clean_scalar(step.mass_loss_percent),
            "mass_loss_mg": _clean_scalar(step.mass_loss_mg),
            "residual_percent": _clean_scalar(step.residual_percent),
        }
        for step in result.steps
    ]
    summary = {
        "step_count": len(result.steps),
        "total_mass_loss_percent": _clean_scalar(result.total_mass_loss_percent),
        "residue_percent": _clean_scalar(result.residue_percent),
        "sample_name": dataset.metadata.get("sample_name"),
        "sample_mass": dataset.metadata.get("sample_mass"),
        "heating_rate": dataset.metadata.get("heating_rate"),
    }
    return make_result_record(
        result_id=f"tga_{dataset_key}",
        analysis_type="TGA",
        status="stable",
        dataset_key=dataset_key,
        metadata=dataset.metadata,
        summary=summary,
        rows=rows,
        artifacts=artifacts,
    )


def serialize_dta_result(
    dataset_key: str,
    dataset,
    peaks: Iterable[ThermalPeak],
    artifacts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Serialize an experimental DTA analysis record."""
    peaks = list(peaks)
    rows = [
        {
            "peak_type": getattr(peak, "direction", peak.peak_type),
            "peak_temperature": _clean_scalar(peak.peak_temperature),
            "onset_temperature": _clean_scalar(peak.onset_temperature),
            "endset_temperature": _clean_scalar(peak.endset_temperature),
            "area": _clean_scalar(peak.area),
            "fwhm": _clean_scalar(peak.fwhm),
            "height": _clean_scalar(peak.height),
        }
        for peak in peaks
    ]
    summary = {"peak_count": len(peaks)}
    return make_result_record(
        result_id=f"dta_{dataset_key}",
        analysis_type="DTA",
        status="experimental",
        dataset_key=dataset_key,
        metadata=dataset.metadata,
        summary=summary,
        rows=rows,
        artifacts=artifacts,
    )


def serialize_kissinger_result(
    result,
    artifacts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Serialize an experimental Kissinger result."""
    summary = {
        "activation_energy_kj_mol": _clean_scalar(result.activation_energy),
        "r_squared": _clean_scalar(result.r_squared),
        "pre_exponential": _clean_scalar(result.pre_exponential),
    }
    return make_result_record(
        result_id="kissinger",
        analysis_type="Kissinger",
        status="experimental",
        dataset_key=None,
        metadata={},
        summary=summary,
        rows=[],
        artifacts=artifacts,
    )


def serialize_ofw_results(
    results: Iterable[Any],
    artifacts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Serialize experimental Ozawa-Flynn-Wall results."""
    rows = []
    results = list(results)
    for item in results:
        plot_data = item.plot_data or {}
        rows.append(
            {
                "alpha": _clean_scalar(plot_data.get("alpha")),
                "activation_energy_kj_mol": _clean_scalar(item.activation_energy),
                "r_squared": _clean_scalar(item.r_squared),
            }
        )
    summary = {"conversion_point_count": len(rows)}
    return make_result_record(
        result_id="ofw",
        analysis_type="Ozawa-Flynn-Wall",
        status="experimental",
        dataset_key=None,
        metadata={},
        summary=summary,
        rows=rows,
        artifacts=artifacts,
    )


def serialize_deconvolution_result(
    dataset_key: str,
    dataset,
    result: dict[str, Any],
    peak_shape: str,
    artifacts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Serialize an experimental peak deconvolution result."""
    params = result.get("params", {})
    rows = []
    n_peaks = len(result.get("components", []))
    for index in range(n_peaks):
        prefix = f"p{index + 1}_"
        row = {
            "peak": index + 1,
            "center": _clean_scalar(params.get(f"{prefix}center")),
            "amplitude": _clean_scalar(params.get(f"{prefix}amplitude")),
            "sigma": _clean_scalar(params.get(f"{prefix}sigma")),
        }
        fraction = params.get(f"{prefix}fraction")
        if fraction is not None:
            row["fraction"] = _clean_scalar(fraction)
        rows.append(row)

    summary = {
        "r_squared": _clean_scalar(result.get("r_squared")),
        "peak_shape": peak_shape,
        "peak_count": n_peaks,
    }
    return make_result_record(
        result_id=f"deconv_{dataset_key}",
        analysis_type="Peak Deconvolution",
        status="experimental",
        dataset_key=dataset_key,
        metadata=dataset.metadata,
        summary=summary,
        rows=rows,
        artifacts=artifacts,
    )


def validate_result_record(result_id: str, record: Any) -> list[str]:
    """Return validation issues for a normalized result record."""
    issues: list[str] = []
    if not isinstance(record, dict):
        return [f"{result_id}: result record is not a dict"]

    missing = sorted(REQUIRED_RESULT_KEYS - set(record))
    if missing:
        issues.append(f"{result_id}: missing keys {', '.join(missing)}")

    status = record.get("status")
    if status is not None and status not in VALID_STATUSES:
        issues.append(f"{result_id}: invalid status '{status}'")

    if "rows" in record and not isinstance(record.get("rows"), list):
        issues.append(f"{result_id}: rows must be a list")
    if "summary" in record and not isinstance(record.get("summary"), dict):
        issues.append(f"{result_id}: summary must be a dict")
    if "metadata" in record and not isinstance(record.get("metadata"), dict):
        issues.append(f"{result_id}: metadata must be a dict")
    if "artifacts" in record and not isinstance(record.get("artifacts"), dict):
        issues.append(f"{result_id}: artifacts must be a dict")

    return issues


def split_valid_results(results: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Separate valid normalized records from invalid ones."""
    valid: dict[str, dict[str, Any]] = {}
    issues: list[str] = []
    for result_id, record in (results or {}).items():
        record_issues = validate_result_record(result_id, record)
        if record_issues:
            issues.extend(record_issues)
            continue
        normalized = copy.deepcopy(record)
        normalized.setdefault("id", result_id)
        valid[result_id] = normalized
    return valid, issues


def partition_results_by_status(results: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return stable and experimental result lists."""
    stable = []
    experimental = []
    for record in results.values():
        if record.get("status") == "stable":
            stable.append(record)
        else:
            experimental.append(record)
    return stable, experimental


def flatten_result_records(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten normalized results for CSV export."""
    rows: list[dict[str, Any]] = []
    for record in results.values():
        base = {
            "result_id": record["id"],
            "status": record["status"],
            "analysis_type": record["analysis_type"],
            "dataset_key": record["dataset_key"],
        }
        for key, value in record.get("summary", {}).items():
            rows.append({**base, "section": "summary", "row_index": "", "field": key, "value": _clean_scalar(value)})
        for index, row in enumerate(record.get("rows", []), start=1):
            for key, value in row.items():
                rows.append({**base, "section": "row", "row_index": index, "field": key, "value": _clean_scalar(value)})
    return rows


def collect_figure_keys(results: dict[str, dict[str, Any]]) -> list[str]:
    """Collect referenced figure keys from result artifacts."""
    keys: list[str] = []
    for record in results.values():
        artifact_keys = record.get("artifacts", {}).get("figure_keys", [])
        if not isinstance(artifact_keys, list):
            continue
        for key in artifact_keys:
            if isinstance(key, str) and key not in keys:
                keys.append(key)
    return keys


def _to_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
