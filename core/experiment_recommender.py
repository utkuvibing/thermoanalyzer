"""Follow-up experiment recommendations for analysis-specific reasoning."""

from __future__ import annotations

from typing import Any


def _recommendation_concept(text: str) -> str:
    lowered = str(text or "").lower()
    if "missing metadata" in lowered or "record missing metadata" in lowered:
        return "metadata_completion"
    if "baseline" in lowered or "signal preprocessing" in lowered:
        return "signal_quality"
    if "sample mass calibration" in lowered or "mass-balance mismatch" in lowered:
        return "mass_balance_recheck"
    if "xrd" in lowered or "raman" in lowered or "phase" in lowered:
        return "phase_confirmation"
    if "isothermal hold" in lowered or "controlled reheating" in lowered:
        return "thermal_hold"
    if "dsc" in lowered or "sta" in lowered:
        return "coupled_dsc_sta"
    if "controlled atmosphere" in lowered or "heating rates" in lowered or "heating-rate" in lowered:
        return "atmosphere_rate_repeat"
    if "co2" in lowered:
        return "co2_confirmation"
    if "evolved-gas" in lowered or "ftir/ms" in lowered:
        return "gas_speciation"
    if "replicate tga" in lowered:
        return "replicate_runs"
    return lowered.casefold().strip()


def recommend_next_experiments(
    analysis_type: str,
    *,
    metadata_gaps: list[str] | None = None,
    fit_band: str | None = None,
    mechanism_hint: str | None = None,
    material_class: str | None = None,
    mass_balance_status: str | None = None,
) -> list[str]:
    """Return concise, analysis-specific follow-up recommendations."""
    analysis = (analysis_type or "").upper()
    metadata_gaps = metadata_gaps or []
    recommendations: list[str] = []

    if analysis == "TGA":
        if material_class == "hydrate_salt":
            recommendations.extend(
                [
                    "Use before/after XRD to verify conversion from hydrate to the expected anhydrous phase.",
                    "Run controlled reheating or an isothermal hold through the primary dehydration region to confirm step completion.",
                    "Pair TGA with DSC (or STA) over the dehydration window to confirm event boundaries and heat-flow coupling.",
                ]
            )
        elif material_class == "carbonate_inorganic":
            recommendations.extend(
                [
                    "Use post-run residue phase analysis (XRD/Raman) to verify oxide formation after decarbonation.",
                    "Repeat TGA under controlled atmosphere and at additional heating rates to test pathway robustness.",
                    "Add targeted gas-evolution confirmation for CO2 release near the dominant decarbonation region.",
                ]
            )
        elif material_class == "hydroxide_to_oxide":
            recommendations.extend(
                [
                    "Use before/after XRD to verify conversion from hydroxide to the expected oxide phase.",
                    "Run controlled reheating or isothermal holds across the dominant dehydroxylation region to confirm completion.",
                    "Pair TGA with DSC (or STA) to refine boundaries of overlapping dehydration/dehydroxylation events.",
                ]
            )
        elif material_class == "oxalate_multistage_inorganic":
            recommendations.extend(
                [
                    "Combine TGA with evolved-gas speciation to resolve CO versus CO2 release across oxalate decomposition stages.",
                    "Use residue-phase characterization (XRD/Raman) after staged cut-off temperatures to map intermediate solids.",
                    "Repeat at additional heating rates to confirm multistage pathway stability and step partitioning.",
                ]
            )
        else:
            recommendations.extend(
                [
                    "Run replicate TGA scans under identical ramp and purge conditions to verify step reproducibility.",
                    "Acquire at least two additional heating rates to test kinetic consistency of the observed mass-loss profile.",
                    "Pair TGA with evolved-gas analysis (FTIR/MS) to resolve competing gas-release pathways.",
                ]
            )

        if material_class in {"hydrate_salt", "hydroxide_to_oxide"}:
            recommendations.append(
                "Use XRD (before/after heating) to verify dehydration/dehydroxylation product phases and confirm stable-residue assignment."
            )
        elif material_class == "carbonate_inorganic":
            recommendations.append(
                "Use post-run phase analysis (XRD/Raman) to verify decarbonation products and confirm oxide-residue formation."
            )
        elif material_class == "oxalate_multistage_inorganic":
            recommendations.append(
                "Combine TGA with evolved-gas speciation to resolve CO versus CO2 release across oxalate decomposition stages."
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

    if mechanism_hint in {"conversion_dependent", "residue_forming"} and material_class not in {"hydrate_salt", "carbonate_inorganic", "hydroxide_to_oxide", "oxalate_multistage_inorganic"}:
        recommendations.append(
            "Use complementary structural/chemical characterization (for example XRD/FTIR) before assigning mechanism."
        )
    if mechanism_hint in {"expected_stable_residue_conversion"}:
        recommendations.append(
            "Validate final solid identity with post-TGA phase characterization to distinguish expected conversion products from residual reactant."
        )
    if mass_balance_status == "mismatch":
        recommendations.append(
            "Recheck baseline correction and sample mass calibration, then repeat TGA to test whether mass-balance mismatch persists."
        )
    if fit_band == "low":
        recommendations.insert(0, "Improve signal preprocessing and baseline treatment before drawing mechanistic conclusions.")
    if metadata_gaps:
        recommendations.insert(0, f"Record missing metadata in repeat runs: {', '.join(metadata_gaps)}.")

    seen: set[str] = set()
    deduped: list[str] = []
    for item in recommendations:
        key = _recommendation_concept(item)
        if key and key not in seen:
            seen.add(key)
            deduped.append(item)

    max_items = 3 if analysis == "TGA" else 4
    return deduped[:max_items]
