"""Follow-up experiment recommendations for analysis-specific reasoning."""

from __future__ import annotations

from typing import Any


def recommend_next_experiments(
    analysis_type: str,
    *,
    metadata_gaps: list[str] | None = None,
    fit_band: str | None = None,
    mechanism_hint: str | None = None,
) -> list[str]:
    """Return concise, analysis-specific follow-up recommendations."""
    analysis = (analysis_type or "").upper()
    metadata_gaps = metadata_gaps or []
    recommendations: list[str] = []

    if analysis == "TGA":
        recommendations.extend(
            [
                "Run replicate TGA scans under identical ramp and purge conditions to verify step reproducibility.",
                "Acquire at least two additional heating rates to test kinetic consistency of the observed mass-loss profile.",
                "Pair TGA with evolved-gas analysis (FTIR/MS) to distinguish decomposition from volatilization contributions.",
            ]
        )
    elif analysis == "DSC":
        recommendations.extend(
            [
                "Repeat DSC with second heating-cooling cycle to separate reversible transitions from history effects.",
                "Use modulated DSC or baseline-optimized rescans to refine overlapping Tg/Tm/Tc event assignments.",
            ]
        )
    elif analysis == "DTA":
        recommendations.extend(
            [
                "Confirm key DTA events with calibrated DSC/TGA runs for quantitative interpretation.",
                "Repeat DTA with inert and oxidative atmospheres to test atmosphere-sensitive event assignments.",
            ]
        )
    elif analysis in {"KISSINGER", "OZAWA-FLYNN-WALL", "FRIEDMAN"}:
        recommendations.extend(
            [
                "Expand heating-rate coverage and include replicates to improve kinetic parameter robustness.",
                "Compare Kissinger, OFW, and Friedman estimates on the same dataset to assess model consistency.",
            ]
        )
    elif analysis == "PEAK DECONVOLUTION":
        recommendations.extend(
            [
                "Re-fit with adjacent component counts (n-1 and n+1) and compare AIC/BIC to evaluate overfitting risk.",
                "Validate component assignments against orthogonal measurements or known reference transitions.",
            ]
        )

    if mechanism_hint in {"conversion_dependent", "residue_forming"}:
        recommendations.append(
            "Use complementary structural/chemical characterization (for example XRD/FTIR) before assigning mechanism."
        )
    if fit_band == "low":
        recommendations.insert(0, "Improve signal preprocessing and baseline treatment before drawing mechanistic conclusions.")
    if metadata_gaps:
        recommendations.insert(0, f"Record missing metadata in repeat runs: {', '.join(metadata_gaps)}.")

    seen: set[str] = set()
    deduped: list[str] = []
    for item in recommendations:
        key = item.casefold().strip()
        if key and key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped[:5]
