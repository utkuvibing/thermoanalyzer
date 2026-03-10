"""Rule-based mechanism heuristics for scientific reasoning narratives."""

from __future__ import annotations

from typing import Any


def _safe_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def tga_mechanism_signals(summary: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Infer high-level TGA decomposition behavior."""
    total_loss = _safe_float((summary or {}).get("total_mass_loss_percent"))
    residue = _safe_float((summary or {}).get("residue_percent"))
    step_count = (summary or {}).get("step_count")
    step_count = int(step_count) if isinstance(step_count, (int, float)) else None

    valid_rows = [row for row in (rows or []) if isinstance(row, dict)]
    ranked = sorted(
        valid_rows,
        key=lambda row: _safe_float(row.get("mass_loss_percent")) or float("-inf"),
        reverse=True,
    )
    lead_loss = _safe_float((ranked[0] if ranked else {}).get("mass_loss_percent"))
    second_loss = _safe_float((ranked[1] if len(ranked) > 1 else {}).get("mass_loss_percent"))

    dominant = bool(
        lead_loss is not None
        and second_loss is not None
        and second_loss > 0
        and lead_loss >= 1.5 * second_loss
    )
    if step_count is not None and step_count <= 1:
        dominant = True

    profile = "inconclusive"
    if total_loss is not None and residue is not None:
        if total_loss >= 90 and residue <= 5:
            profile = "near_complete_decomposition"
        elif residue >= 30:
            profile = "residue_forming"
        elif total_loss >= 70:
            profile = "substantial_partial_decomposition"
        else:
            profile = "limited_partial_decomposition"

    return {
        "profile": profile,
        "dominant_step": dominant,
        "step_count": step_count,
        "lead_mass_loss_percent": lead_loss,
        "second_mass_loss_percent": second_loss,
    }


def dsc_mechanism_signals(summary: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Infer high-level DSC event behavior."""
    summary = summary or {}
    rows = [row for row in (rows or []) if isinstance(row, dict)]
    peak_count = summary.get("peak_count")
    peak_count = int(peak_count) if isinstance(peak_count, (int, float)) else len(rows)

    has_tg = _safe_float(summary.get("tg_midpoint")) is not None
    peak_types = [str(row.get("peak_type") or "").lower() for row in rows]
    endotherm_count = sum(1 for value in peak_types if "endo" in value)
    exotherm_count = sum(1 for value in peak_types if "exo" in value)

    complexity = "simple" if peak_count <= 1 else "multistage"
    if peak_count >= 3:
        complexity = "complex"

    return {
        "peak_count": peak_count,
        "has_tg": has_tg,
        "complexity": complexity,
        "endotherm_count": endotherm_count,
        "exotherm_count": exotherm_count,
    }


def dta_mechanism_signals(summary: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Infer qualitative DTA event behavior."""
    summary = summary or {}
    rows = [row for row in (rows or []) if isinstance(row, dict)]
    peak_count = summary.get("peak_count")
    peak_count = int(peak_count) if isinstance(peak_count, (int, float)) else len(rows)
    return {
        "peak_count": peak_count,
        "event_richness": "multi-event" if peak_count >= 2 else "single-event",
    }


def kinetics_mechanism_signals(
    analysis_type: str,
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Infer kinetics behavior with trend and complexity hints."""
    normalized = (analysis_type or "").upper()
    rows = [row for row in (rows or []) if isinstance(row, dict)]
    ea_values = []
    alpha_values = []
    for row in rows:
        ea = _safe_float(row.get("activation_energy_kj_mol"))
        alpha = _safe_float(row.get("alpha"))
        if ea is not None:
            ea_values.append(ea)
        if alpha is not None:
            alpha_values.append(alpha)

    trend = "not_assessed"
    if len(ea_values) >= 2:
        delta = ea_values[-1] - ea_values[0]
        if abs(delta) <= 5:
            trend = "approximately_constant"
        elif delta > 5:
            trend = "increasing_with_conversion"
        else:
            trend = "decreasing_with_conversion"

    complexity = "single_step_like" if trend in {"approximately_constant", "not_assessed"} else "conversion_dependent"
    return {
        "method": normalized,
        "ea_count": len(ea_values),
        "ea_trend": trend,
        "complexity_hint": complexity,
        "has_conversion_profile": bool(alpha_values),
        "summary_activation_energy": _safe_float((summary or {}).get("activation_energy_kj_mol")),
    }


def deconvolution_mechanism_signals(summary: dict[str, Any], fit_quality: dict[str, Any]) -> dict[str, Any]:
    """Infer overlap/fit risk behavior for peak deconvolution."""
    peak_count = summary.get("peak_count")
    peak_count = int(peak_count) if isinstance(peak_count, (int, float)) else None
    r2 = _safe_float((fit_quality or {}).get("r_squared"))
    rmse = _safe_float((fit_quality or {}).get("rmse"))

    if peak_count is None:
        overlap = "unknown"
    elif peak_count >= 3:
        overlap = "high_overlap_likelihood"
    elif peak_count == 2:
        overlap = "moderate_overlap_likelihood"
    else:
        overlap = "low_overlap_likelihood"

    return {
        "peak_count": peak_count,
        "r_squared": r2,
        "rmse": rmse,
        "overlap_hint": overlap,
    }
