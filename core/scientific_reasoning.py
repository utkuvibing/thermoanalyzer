"""Academic-style scientific reasoning payload builders."""

from __future__ import annotations

from typing import Any

from core.experiment_recommender import recommend_next_experiments
from core.mechanism_rules import (
    deconvolution_mechanism_signals,
    dsc_mechanism_signals,
    dta_mechanism_signals,
    kinetics_mechanism_signals,
    tga_mechanism_signals,
)
from core.uncertainty_rules import claim_gate, fit_quality_band, metadata_gaps


def _safe_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _claim(
    claim_id: str,
    strength: str,
    text: str,
    evidence: list[str],
) -> dict[str, Any]:
    return {
        "id": claim_id,
        "strength": strength,
        "claim": text,
        "evidence": evidence,
    }


def _build_tga_reasoning(
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
    metadata: dict[str, Any],
    fit_band: str,
    fit_reason: str,
    validation: dict[str, Any] | None,
) -> dict[str, Any]:
    signals = tga_mechanism_signals(summary, rows)
    gaps = metadata_gaps(metadata, ["sample_mass", "heating_rate", "instrument", "atmosphere"])
    gates = claim_gate(len(gaps), fit_band, validation=validation)

    claims: list[dict[str, Any]] = []
    evidence_map: dict[str, list[str]] = {}
    alternatives: list[str] = []

    total_loss = _safe_float(summary.get("total_mass_loss_percent"))
    residue = _safe_float(summary.get("residue_percent"))
    step_count = signals.get("step_count")

    cid = "C1"
    claim_text = "The thermogram shows single-step-dominant decomposition behavior." if signals.get("dominant_step") else "The thermogram shows multi-step decomposition behavior."
    evidence = []
    if step_count is not None:
        evidence.append(f"Resolved decomposition step count: {step_count}.")
    if signals.get("lead_mass_loss_percent") is not None:
        evidence.append(f"Largest resolved step mass loss: {float(signals['lead_mass_loss_percent']):.2f}%.")
    claims.append(_claim(cid, "descriptive", claim_text, evidence))
    evidence_map[cid] = evidence

    if total_loss is not None and residue is not None and gates["allow_comparative"]:
        cid = "C2"
        if total_loss >= 90 and residue <= 5:
            text = "Mass-balance metrics are consistent with near-complete decomposition over the measured range."
        elif residue >= 30:
            text = "Mass-balance metrics indicate residue-forming and only partial decomposition behavior."
        else:
            text = "Mass-balance metrics indicate substantial but incomplete decomposition."
        evidence = [
            f"Total mass loss: {total_loss:.2f}%.",
            f"Final residue: {residue:.2f}%.",
        ]
        claims.append(_claim(cid, "comparative", text, evidence))
        evidence_map[cid] = evidence

    if gates["allow_mechanistic"]:
        cid = "C3"
        text = "The decomposition pattern is mechanistically consistent with a dominant primary pathway followed by secondary transformations." if signals.get("dominant_step") else "The decomposition pattern is mechanistically consistent with overlapping or sequential pathways."
        evidence = [
            f"Dominant-step flag: {'yes' if signals.get('dominant_step') else 'no'}.",
            f"Profile classification: {signals.get('profile')}.",
        ]
        claims.append(_claim(cid, "mechanistic", text, evidence))
        evidence_map[cid] = evidence
    else:
        alternatives.append("Observed mass-loss segmentation may reflect preprocessing thresholds rather than distinct mechanistic stages.")

    if residue is not None and residue >= 20:
        alternatives.append("A portion of the apparent residue may represent inert fillers or char stabilization rather than incomplete reaction alone.")
    else:
        alternatives.append("A near-zero final residue may also include volatilization of non-reactive components.")

    uncertainty_items = []
    if gaps:
        uncertainty_items.append(f"Missing metadata: {', '.join(gaps)}.")
    uncertainty_items.append(fit_reason)
    if (validation or {}).get("warnings"):
        uncertainty_items.append("Validation warnings were reported and should temper interpretation confidence.")

    return {
        "scientific_claims": claims,
        "evidence_map": evidence_map,
        "uncertainty_assessment": {
            "overall_confidence": "high" if gates["allow_mechanistic"] else ("moderate" if gates["allow_comparative"] else "low"),
            "fit_assessment": fit_band,
            "metadata_gaps": gaps,
            "items": uncertainty_items,
        },
        "alternative_hypotheses": alternatives[:3],
        "next_experiments": recommend_next_experiments(
            "TGA",
            metadata_gaps=gaps,
            fit_band=fit_band,
            mechanism_hint=str(signals.get("profile")),
        ),
    }


def _build_dsc_reasoning(
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
    metadata: dict[str, Any],
    fit_band: str,
    fit_reason: str,
    validation: dict[str, Any] | None,
) -> dict[str, Any]:
    signals = dsc_mechanism_signals(summary, rows)
    gaps = metadata_gaps(metadata, ["sample_mass", "heating_rate", "instrument"])
    gates = claim_gate(len(gaps), fit_band, validation=validation)

    claims: list[dict[str, Any]] = []
    evidence_map: dict[str, list[str]] = {}
    alternatives: list[str] = []

    cid = "C1"
    desc = "The DSC profile contains a simple thermal-event structure." if signals["complexity"] == "simple" else "The DSC profile contains multiple thermal events."
    evidence = [f"Detected peak count: {signals['peak_count']}."]
    if signals["has_tg"]:
        tg = _safe_float(summary.get("tg_midpoint"))
        if tg is not None:
            evidence.append(f"Resolved Tg midpoint: {tg:.2f} °C.")
    claims.append(_claim(cid, "descriptive", desc, evidence))
    evidence_map[cid] = evidence

    if signals["has_tg"] and gates["allow_comparative"]:
        cid = "C2"
        tg = _safe_float(summary.get("tg_midpoint"))
        if tg is not None:
            claims.append(
                _claim(
                    cid,
                    "comparative",
                    "The detected Tg is consistent with a matrix-dominated transition in the measured temperature window.",
                    [f"Tg midpoint: {tg:.2f} °C.", f"Event complexity class: {signals['complexity']}."],
                )
            )
            evidence_map[cid] = [f"Tg midpoint: {tg:.2f} °C.", f"Event complexity class: {signals['complexity']}."]

    if gates["allow_mechanistic"] and signals["peak_count"] >= 2:
        cid = "C3"
        claims.append(
            _claim(
                cid,
                "mechanistic",
                "The combination of transition and peak structure suggests overlapping physical transition and thermal reaction contributions.",
                [f"Endothermic events: {signals['endotherm_count']}.", f"Exothermic events: {signals['exotherm_count']}."],
            )
        )
        evidence_map[cid] = [f"Endothermic events: {signals['endotherm_count']}.", f"Exothermic events: {signals['exotherm_count']}."]
    else:
        alternatives.append("Observed event splitting may originate from baseline/smoothing settings rather than distinct physicochemical transitions.")

    alternatives.append("Thermal history and sample heterogeneity can shift Tg and apparent peak structure without changing chemistry.")
    uncertainty_items = [fit_reason]
    if gaps:
        uncertainty_items.append(f"Missing metadata: {', '.join(gaps)}.")

    return {
        "scientific_claims": claims,
        "evidence_map": evidence_map,
        "uncertainty_assessment": {
            "overall_confidence": "high" if gates["allow_mechanistic"] else ("moderate" if gates["allow_comparative"] else "low"),
            "fit_assessment": fit_band,
            "metadata_gaps": gaps,
            "items": uncertainty_items,
        },
        "alternative_hypotheses": alternatives[:3],
        "next_experiments": recommend_next_experiments(
            "DSC",
            metadata_gaps=gaps,
            fit_band=fit_band,
            mechanism_hint=signals["complexity"],
        ),
    }


def _build_dta_reasoning(
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
    metadata: dict[str, Any],
    fit_band: str,
    fit_reason: str,
    validation: dict[str, Any] | None,
) -> dict[str, Any]:
    signals = dta_mechanism_signals(summary, rows)
    gaps = metadata_gaps(metadata, ["sample_mass", "heating_rate", "instrument", "atmosphere"])
    gates = claim_gate(len(gaps), fit_band, validation=validation)

    claims = [
        _claim(
            "C1",
            "descriptive",
            "DTA identified qualitative thermal-event structure in the current run.",
            [f"Detected event count: {signals['peak_count']}.", "DTA amplitudes are interpreted qualitatively in this workflow."],
        )
    ]
    evidence_map = {"C1": claims[0]["evidence"]}
    if gates["allow_comparative"]:
        claims.append(
            _claim(
                "C2",
                "comparative",
                "Event richness suggests more than one thermally distinct process may be present.",
                [f"Event-richness class: {signals['event_richness']}."],
            )
        )
        evidence_map["C2"] = claims[-1]["evidence"]

    alternatives = [
        "Apparent DTA events may be influenced by baseline drift or reference mismatch.",
        "Without calibration transfer, event area differences should not be treated as quantitative enthalpy differences.",
    ]
    uncertainty_items = [
        fit_reason,
        "DTA interpretation remains qualitative unless instrument-specific calibration is established.",
    ]
    if gaps:
        uncertainty_items.append(f"Missing metadata: {', '.join(gaps)}.")

    return {
        "scientific_claims": claims,
        "evidence_map": evidence_map,
        "uncertainty_assessment": {
            "overall_confidence": "moderate" if gates["allow_comparative"] else "low",
            "fit_assessment": fit_band,
            "metadata_gaps": gaps,
            "items": uncertainty_items,
        },
        "alternative_hypotheses": alternatives[:3],
        "next_experiments": recommend_next_experiments(
            "DTA",
            metadata_gaps=gaps,
            fit_band=fit_band,
            mechanism_hint=signals["event_richness"],
        ),
    }


def _build_kinetics_reasoning(
    analysis_type: str,
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
    metadata: dict[str, Any],
    fit_band: str,
    fit_reason: str,
    validation: dict[str, Any] | None,
) -> dict[str, Any]:
    signals = kinetics_mechanism_signals(analysis_type, summary, rows)
    gaps = metadata_gaps(metadata, ["heating_rate"])
    gates = claim_gate(len(gaps), fit_band, validation=validation)

    claims = []
    evidence_map: dict[str, list[str]] = {}

    claims.append(
        _claim(
            "C1",
            "descriptive",
            f"{analysis_type} produced an activation-energy estimate/profile for the analyzed conversion window.",
            [
                f"Activation-energy points: {signals['ea_count']}.",
                f"Trend class: {signals['ea_trend']}.",
            ],
        )
    )
    evidence_map["C1"] = claims[-1]["evidence"]

    if gates["allow_comparative"]:
        claims.append(
            _claim(
                "C2",
                "comparative",
                "The Ea(alpha) behavior indicates whether a single apparent regime or conversion-dependent kinetics is more plausible.",
                [f"Complexity hint: {signals['complexity_hint']}."],
            )
        )
        evidence_map["C2"] = claims[-1]["evidence"]

    if gates["allow_mechanistic"] and signals["complexity_hint"] == "conversion_dependent":
        claims.append(
            _claim(
                "C3",
                "mechanistic",
                "Conversion-dependent Ea trends suggest multi-step or changing-rate-control mechanisms rather than one dominant elementary step.",
                [f"Ea(alpha) trend: {signals['ea_trend']}."],
            )
        )
        evidence_map["C3"] = claims[-1]["evidence"]

    alternatives = [
        "Observed Ea(alpha) drift may be amplified by conversion interpolation and derivative noise.",
        "Cross-method agreement (Kissinger/OFW/Friedman) cannot be fully established from a single-method payload.",
    ]
    uncertainty_items = [fit_reason]
    if gaps:
        uncertainty_items.append(f"Missing metadata: {', '.join(gaps)}.")
    if not gates["allow_mechanistic"]:
        uncertainty_items.append("Mechanistic claims were intentionally constrained by confidence gating.")

    return {
        "scientific_claims": claims,
        "evidence_map": evidence_map,
        "uncertainty_assessment": {
            "overall_confidence": "high" if gates["allow_mechanistic"] else ("moderate" if gates["allow_comparative"] else "low"),
            "fit_assessment": fit_band,
            "metadata_gaps": gaps,
            "items": uncertainty_items,
        },
        "alternative_hypotheses": alternatives[:3],
        "next_experiments": recommend_next_experiments(
            analysis_type,
            metadata_gaps=gaps,
            fit_band=fit_band,
            mechanism_hint=signals["complexity_hint"],
        ),
    }


def _build_deconvolution_reasoning(
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
    metadata: dict[str, Any],
    fit_quality: dict[str, Any],
    fit_band: str,
    fit_reason: str,
    validation: dict[str, Any] | None,
) -> dict[str, Any]:
    del rows, metadata
    signals = deconvolution_mechanism_signals(summary, fit_quality)
    gates = claim_gate(0, fit_band, validation=validation)

    claims = [
        _claim(
            "C1",
            "descriptive",
            "Peak deconvolution resolved overlapping signal components in the analyzed window.",
            [
                f"Resolved component count: {signals['peak_count'] if signals['peak_count'] is not None else 'not recorded'}.",
                f"R^2: {signals['r_squared'] if signals['r_squared'] is not None else 'not recorded'}.",
            ],
        )
    ]
    evidence_map = {"C1": claims[0]["evidence"]}

    if gates["allow_comparative"]:
        claims.append(
            _claim(
                "C2",
                "comparative",
                "The fitted component structure is internally consistent with overlapping-event behavior.",
                [f"Overlap hint: {signals['overlap_hint']}."],
            )
        )
        evidence_map["C2"] = claims[-1]["evidence"]

    if gates["allow_mechanistic"] and signals["overlap_hint"] == "high_overlap_likelihood":
        claims.append(
            _claim(
                "C3",
                "mechanistic",
                "The pattern supports a multi-event process rather than a single isolated transition.",
                [f"Component count: {signals['peak_count']}.", f"R^2: {signals['r_squared']}."],
            )
        )
        evidence_map["C3"] = claims[-1]["evidence"]

    alternatives = [
        "Similar goodness-of-fit can sometimes be achieved with fewer components, indicating potential overfitting.",
        "Component parameters may not be uniquely identifiable under strong peak overlap.",
    ]
    uncertainty_items = [fit_reason]
    if not gates["allow_mechanistic"]:
        uncertainty_items.append("Mechanistic claims were constrained because fit confidence was not high enough.")

    return {
        "scientific_claims": claims,
        "evidence_map": evidence_map,
        "uncertainty_assessment": {
            "overall_confidence": "high" if gates["allow_mechanistic"] else ("moderate" if gates["allow_comparative"] else "low"),
            "fit_assessment": fit_band,
            "metadata_gaps": [],
            "items": uncertainty_items,
        },
        "alternative_hypotheses": alternatives[:3],
        "next_experiments": recommend_next_experiments(
            "Peak Deconvolution",
            fit_band=fit_band,
            mechanism_hint=str(signals["overlap_hint"]),
        ),
    }


def build_scientific_reasoning(
    *,
    analysis_type: str,
    summary: dict[str, Any] | None = None,
    rows: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
    fit_quality: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build structured scientific reasoning blocks for a normalized analysis record."""
    summary = summary or {}
    rows = rows or []
    metadata = metadata or {}
    fit_quality = fit_quality or {}

    analysis = (analysis_type or "").upper()
    band, fit_reason = fit_quality_band(analysis, fit_quality, validation=validation)

    if analysis == "TGA":
        return _build_tga_reasoning(summary, rows, metadata, band, fit_reason, validation)
    if analysis == "DSC":
        return _build_dsc_reasoning(summary, rows, metadata, band, fit_reason, validation)
    if analysis == "DTA":
        return _build_dta_reasoning(summary, rows, metadata, band, fit_reason, validation)
    if analysis in {"KISSINGER", "OZAWA-FLYNN-WALL", "FRIEDMAN"}:
        return _build_kinetics_reasoning(analysis, summary, rows, metadata, band, fit_reason, validation)
    if analysis == "PEAK DECONVOLUTION":
        return _build_deconvolution_reasoning(summary, rows, metadata, fit_quality, band, fit_reason, validation)

    return {
        "scientific_claims": [
            _claim(
                "C1",
                "descriptive",
                "Scientific reasoning is not specialized for this analysis type yet.",
                ["No analysis-specific mechanism rules were available."],
            )
        ],
        "evidence_map": {"C1": ["No analysis-specific mechanism rules were available."]},
        "uncertainty_assessment": {
            "overall_confidence": "low",
            "fit_assessment": band,
            "metadata_gaps": [],
            "items": [fit_reason],
        },
        "alternative_hypotheses": ["Result interpretation remains provisional pending domain-specific reasoning rules."],
        "next_experiments": recommend_next_experiments(analysis, fit_band=band),
    }
