"""Uncertainty and confidence heuristics for scientific reasoning."""

from __future__ import annotations

from typing import Any


def _safe_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def metadata_gaps(metadata: dict[str, Any] | None, required_fields: list[str]) -> list[str]:
    """Return missing metadata fields in reader-facing language."""
    metadata = metadata or {}
    labels = {
        "sample_name": "sample name",
        "sample_mass": "sample mass",
        "heating_rate": "heating rate",
        "instrument": "instrument",
        "vendor": "vendor",
        "atmosphere": "atmosphere",
    }
    gaps: list[str] = []
    for field in required_fields:
        if metadata.get(field) in (None, "", [], {}):
            gaps.append(labels.get(field, field.replace("_", " ")))
    return gaps


def fit_quality_band(
    analysis_type: str,
    fit_quality: dict[str, Any] | None,
    validation: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Return qualitative fit confidence and rationale."""
    analysis = (analysis_type or "").upper()
    fit_quality = fit_quality or {}
    validation_status = ((validation or {}).get("status") or "").lower()
    r2 = _safe_float(fit_quality.get("r_squared"))
    mean_r2 = _safe_float(fit_quality.get("mean_r_squared"))

    score = mean_r2 if mean_r2 is not None else r2
    if score is None and analysis in {"TGA", "DSC", "DTA"}:
        band = "moderate"
        reason = "No formal fit statistic was reported; confidence is based on summary-level processing checks."
    elif score is None:
        band = "moderate"
        reason = "Fit statistics are incomplete."
    elif score >= 0.98:
        band = "high"
        reason = f"Fit statistics are strong (R^2 about {score:.3f})."
    elif score >= 0.93:
        band = "moderate"
        reason = f"Fit statistics are acceptable but not strong (R^2 about {score:.3f})."
    else:
        band = "low"
        reason = f"Fit statistics are weak (R^2 about {score:.3f})."

    if validation_status == "fail":
        return "low", f"{reason} Validation status is fail."
    if validation_status == "warn" and band == "high":
        return "moderate", f"{reason} Validation warnings were raised."
    if validation_status == "warn":
        return band, f"{reason} Validation warnings were raised."
    return band, reason


def claim_gate(
    metadata_gap_count: int,
    fit_band: str,
    validation: dict[str, Any] | None = None,
) -> dict[str, bool]:
    """Gate claim strength to avoid overclaiming."""
    validation_status = ((validation or {}).get("status") or "").lower()
    allow_comparative = fit_band in {"high", "moderate"} and validation_status != "fail"
    allow_mechanistic = (
        fit_band == "high"
        and metadata_gap_count <= 1
        and validation_status not in {"fail", "warn"}
    )
    return {
        "allow_comparative": allow_comparative,
        "allow_mechanistic": allow_mechanistic,
    }
