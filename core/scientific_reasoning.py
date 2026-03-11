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
    dataset_hint = str(
        metadata.get("file_name")
        or metadata.get("display_name")
        or metadata.get("sample_name")
        or summary.get("sample_name")
        or ""
    )
    signals = tga_mechanism_signals(summary, rows, metadata=metadata, dataset_key=dataset_hint)
    class_inference = signals.get("material_class_inference") or {}
    mass_balance = signals.get("mass_balance_assessment") or {}
    step_count = signals.get("step_count")
    if step_count is None:
        step_count = summary.get("step_count")
    event_structure_plausible = bool(step_count not in (None, "", 0))
    gaps = metadata_gaps(metadata, ["sample_mass", "heating_rate", "instrument", "atmosphere"])
    gates = claim_gate(
        len(gaps),
        fit_band,
        validation=validation,
        class_confidence=str(class_inference.get("confidence") or ""),
        mass_balance_status=str(mass_balance.get("status") or ""),
        segmentation_uncertain=bool(signals.get("possible_subdivision")),
        event_structure_plausible=event_structure_plausible,
    )

    claims: list[dict[str, Any]] = []
    evidence_map: dict[str, list[str]] = {}
    alternatives: list[str] = []

    total_loss = _safe_float(summary.get("total_mass_loss_percent"))
    residue = _safe_float(summary.get("residue_percent"))
    step_count_text = str(step_count) if step_count is not None else "not recorded"
    class_label = str(class_inference.get("material_class_label") or "unknown / unconstrained")
    class_confidence = str(class_inference.get("confidence") or "low")
    profile = str(signals.get("profile") or "inconclusive")
    balance_status = str(mass_balance.get("status") or "not_assessed")
    pathway = str(mass_balance.get("pathway") or "").strip()

    def _balance_sentence() -> str:
        material_class = str(class_inference.get("material_class") or "")
        if balance_status in {"strong_match", "plausible_match"}:
            if pathway:
                return f"Observed mass balance is consistent with near-complete {pathway}."
            if material_class == "hydrate_salt":
                return "Observed mass balance is consistent with near-complete dehydration to an expected anhydrous residue."
            if material_class == "carbonate_inorganic":
                return "Observed mass balance is consistent with near-complete decarbonation to a stable oxide-rich residue."
            if material_class == "hydroxide_to_oxide":
                return "Observed mass balance is consistent with dehydroxylation toward an expected oxide residue."
            if material_class == "oxalate_multistage_inorganic":
                return "Observed mass balance is consistent with a multistage oxalate gas-loss pathway to a stable final residue."
            if material_class == "generic_inorganic_salt_or_mineral":
                return "Observed mass balance is consistent with conversion to an expected stable solid residue under the recorded range."
            return "Mass-balance metrics are internally consistent with the dominant thermal transformation."
        if balance_status == "mismatch":
            return "Observed mass balance deviates from simple class-based pathways, so incomplete conversion or additional concurrent reactions remain plausible."
        if total_loss is not None and residue is not None and total_loss >= 85.0 and residue <= 15.0:
            return "Mass-balance metrics indicate extensive decomposition over the measured range."
        if total_loss is not None and residue is not None:
            return "Mass-balance metrics indicate partial conversion with retained solid residue, but the final solid identity remains unconstrained."
        return "Mass-balance interpretation remains limited by incomplete summary metrics."

    cid = "C1"
    if signals.get("possible_subdivision"):
        claim_text = (
            f"{step_count_text} DTG-resolved events were detected, and at least one minor or closely spaced event may represent "
            "subdivision of a broader transformation region rather than a fully independent mechanistic step."
        )
    elif signals.get("dominant_step"):
        claim_text = (
            f"{step_count_text} DTG-resolved events were detected, with one dominant primary event controlling most of the observed mass loss."
        )
    else:
        claim_text = f"{step_count_text} DTG-resolved events were detected across the measured range."
    evidence = []
    if step_count is not None:
        evidence.append(f"DTG-resolved event count: {step_count}.")
    if signals.get("lead_mass_loss_percent") is not None:
        evidence.append(f"Largest resolved event mass loss: {float(signals['lead_mass_loss_percent']):.2f}%.")
    if signals.get("lead_midpoint_temperature") is not None:
        evidence.append(f"Largest event midpoint temperature: {float(signals['lead_midpoint_temperature']):.1f} °C.")
    if signals.get("minor_event_count"):
        evidence.append(f"Minor event count below significance threshold: {int(signals['minor_event_count'])}.")
    if signals.get("adjacent_event_pair_count"):
        evidence.append(f"Closely spaced adjacent event pairs: {int(signals['adjacent_event_pair_count'])}.")
    claims.append(_claim(cid, "descriptive", claim_text, evidence))
    evidence_map[cid] = evidence

    if total_loss is not None and residue is not None and gates["allow_comparative"]:
        cid = "C2"
        text = _balance_sentence()
        evidence = [
            f"Total mass loss: {total_loss:.2f}%.",
            f"Final residue: {residue:.2f}%.",
            f"Inferred material class: {class_label} (confidence: {class_confidence}).",
        ]
        if pathway:
            evidence.append(f"Evaluated pathway: {pathway}.")
        if mass_balance.get("expected_loss_percent") is not None:
            evidence.append(f"Expected loss (pathway model): {float(mass_balance['expected_loss_percent']):.2f}%.")
        if mass_balance.get("expected_loss_range_percent"):
            low, high = mass_balance["expected_loss_range_percent"]
            evidence.append(f"Expected loss range (pathway model): {low:.2f}% to {high:.2f}%.")
        if mass_balance.get("delta_loss_percent") is not None:
            evidence.append(f"Loss mismatch versus pathway model: {float(mass_balance['delta_loss_percent']):+.2f} wt%.")
        claims.append(_claim(cid, "comparative", text, evidence))
        evidence_map[cid] = evidence

    if gates["allow_mechanistic"]:
        cid = "C3"
        if profile == "expected_stable_residue_conversion":
            if pathway:
                text = f"Combined class inference and mass-balance consistency support {pathway} as the dominant pathway."
            else:
                text = "Combined class inference and mass-balance consistency support conversion to an expected stable solid residue as the dominant pathway."
        elif signals.get("dominant_step"):
            text = "The DTG profile supports a dominant primary transformation region with weaker secondary contributions."
        else:
            text = "The DTG profile supports overlapping or sequential transformation regions rather than a single isolated pathway."
        evidence = [
            f"Profile classification: {profile}.",
            f"Material-class confidence: {class_confidence}.",
            f"Mass-balance consistency status: {balance_status}.",
        ]
        claims.append(_claim(cid, "mechanistic", text, evidence))
        evidence_map[cid] = evidence
    material_class = str(class_inference.get("material_class") or "")
    if material_class in {"hydrate_salt", "hydroxide_to_oxide"}:
        alternatives.extend(
            [
                "Apparent event multiplicity may reflect overlapping dehydration/dehydroxylation sub-steps through intermediate solid phases.",
                "Smoothing and segmentation settings can split one broad transformation region into multiple DTG-resolved events.",
                "Minor mass-balance mismatch can arise from baseline drift or retained bound water at run end.",
            ]
        )
    elif material_class == "carbonate_inorganic":
        alternatives.extend(
            [
                "A minor shoulder near the dominant high-temperature event may arise from segmentation of one broadened decarbonation region.",
                "Gas-release broadening and heat-transfer limits can shift apparent peak boundaries without changing core pathway chemistry.",
                "Small residual mismatch may reflect secondary carbonate stability or limited equilibration time.",
            ]
        )
    elif material_class == "oxalate_multistage_inorganic":
        alternatives.extend(
            [
                "Resolved events may combine overlapping dehydration and gas-evolution sub-steps rather than fully independent mechanisms.",
                "DTG peak splitting can increase apparent event count when neighboring transitions partially overlap.",
                "Intermediate carbonate formation can transiently alter apparent mass-balance partitioning.",
            ]
        )
    elif material_class == "polymer_or_organic":
        alternatives.extend(
            [
                "Apparent residue may include char stabilization rather than only unreacted material.",
                "Inorganic fillers or additives can increase retained residue without implying incomplete conversion of the organic fraction.",
                "Atmosphere sensitivity can shift overlap between volatilization and oxidative/decomposition pathways.",
            ]
        )
    elif material_class == "generic_inorganic_salt_or_mineral":
        alternatives.extend(
            [
                "Multiple DTG-resolved events may reflect subdivisions of one broad solid-state transformation sequence.",
                "Baseline drift and smoothing can redistribute event boundaries in low-slope regions.",
                "Without explicit phase identification, residue chemistry may differ from the simplest assumed pathway.",
            ]
        )
    else:
        alternatives.extend(
            [
                "Observed segmentation may partially reflect preprocessing thresholds rather than independent mechanisms.",
                "Unconstrained sample identity limits definitive assignment of residue chemistry.",
                "Overlapping transformations can mimic additional DTG-resolved events.",
            ]
        )

    if signals.get("possible_subdivision"):
        alternatives.insert(
            0,
            "At least one minor DTG event may represent subdivision of a broader transformation interval.",
        )

    uncertainty_items = []
    if gaps:
        uncertainty_items.append(f"Missing metadata: {', '.join(gaps)}.")
    uncertainty_items.append(fit_reason)
    uncertainty_items.append(f"Inferred material class: {class_label} (confidence: {class_confidence}).")
    if balance_status == "not_assessed":
        uncertainty_items.append("Stoichiometric mass-balance matching was not possible from the available formula/context information.")
    elif balance_status == "mismatch":
        uncertainty_items.append("Observed mass balance did not match simple class-based pathways within configured tolerance.")
    if signals.get("possible_subdivision"):
        uncertainty_items.append("DTG event segmentation suggests at least one potential event subdivision; mechanistic step count remains provisional.")
    if (validation or {}).get("warnings"):
        uncertainty_items.append("Validation warnings were reported and should temper interpretation confidence.")

    chemistry_supported = (
        class_confidence.lower() in {"high", "moderate"}
        and balance_status in {"strong_match", "plausible_match"}
    )
    overall = "high" if gates["allow_mechanistic"] else ("moderate" if gates["allow_comparative"] else "low")
    overall_label = ""
    if overall == "moderate" and chemistry_supported and gaps:
        overall_label = "medium, metadata-limited"
        uncertainty_items.append(
            "Overall confidence is medium, metadata-limited: strong class inference and mass-balance agreement are present, "
            "but interpretation is constrained by incomplete experimental metadata."
        )
    elif overall == "moderate" and gaps:
        overall_label = "medium, interpretation constrained by incomplete experimental metadata"

    return {
        "scientific_claims": claims,
        "evidence_map": evidence_map,
        "uncertainty_assessment": {
            "overall_confidence": overall,
            "overall_confidence_label": overall_label,
            "fit_assessment": fit_band,
            "metadata_gaps": gaps,
            "items": uncertainty_items,
            "class_inference": class_inference,
            "mass_balance_assessment": mass_balance,
        },
        "alternative_hypotheses": alternatives[:3],
        "next_experiments": recommend_next_experiments(
            "TGA",
            metadata_gaps=gaps,
            fit_band=fit_band,
            mechanism_hint=profile,
            material_class=material_class,
            mass_balance_status=balance_status,
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
