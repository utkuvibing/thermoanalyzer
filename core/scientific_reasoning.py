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
from core.xrd_display import xrd_candidate_display_name


def _safe_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
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


def _build_xrd_reasoning(
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
    metadata: dict[str, Any],
    fit_band: str,
    fit_reason: str,
    validation: dict[str, Any] | None,
) -> dict[str, Any]:
    top_row = rows[0] if rows else {}
    best_candidate = (
        summary.get("top_candidate_display_name_unicode")
        or summary.get("top_phase_display_name_unicode")
        or xrd_candidate_display_name(summary, target="unicode")
        or xrd_candidate_display_name(top_row, target="unicode")
        or top_row.get("candidate_name")
        or "the best-ranked candidate"
    )
    match_status = str(summary.get("match_status") or "no_match").lower()
    confidence_band = str(
        summary.get("top_candidate_confidence_band")
        or summary.get("confidence_band")
        or top_row.get("confidence_band")
        or "no_match"
    ).lower()
    candidate_count = _safe_int(summary.get("candidate_count"))
    if candidate_count is None:
        candidate_count = len(rows)
    top_score = _safe_float(summary.get("top_candidate_score"))
    if top_score is None:
        top_score = _safe_float(summary.get("top_phase_score"))
    shared_peak_count = _safe_int(summary.get("top_candidate_shared_peak_count"))
    if shared_peak_count is None:
        shared_peak_count = _safe_int((top_row.get("evidence") or {}).get("shared_peak_count"))
    coverage_ratio = _safe_float(summary.get("top_candidate_coverage_ratio"))
    if coverage_ratio is None:
        coverage_ratio = _safe_float((top_row.get("evidence") or {}).get("coverage_ratio"))
    weighted_overlap = _safe_float(summary.get("top_candidate_weighted_overlap_score"))
    if weighted_overlap is None:
        weighted_overlap = _safe_float((top_row.get("evidence") or {}).get("weighted_overlap_score"))
    mean_delta_position = _safe_float(summary.get("top_candidate_mean_delta_position"))
    if mean_delta_position is None:
        mean_delta_position = _safe_float((top_row.get("evidence") or {}).get("mean_delta_position"))
    unmatched_major_peak_count = _safe_int(summary.get("top_candidate_unmatched_major_peak_count"))
    if unmatched_major_peak_count is None:
        unmatched_major_peak_count = _safe_int((top_row.get("evidence") or {}).get("unmatched_major_peak_count"))
    provider_scope = [str(item) for item in (summary.get("library_provider_scope") or []) if str(item).strip()]
    provider_candidate_counts = {
        str(key): int(value)
        for key, value in dict(summary.get("xrd_provider_candidate_counts") or {}).items()
        if str(key).strip()
    }
    coverage_tier = str(summary.get("xrd_coverage_tier") or "").strip()
    coverage_warning = str(summary.get("xrd_coverage_warning_message") or "").strip()
    provenance_state = str(
        summary.get("xrd_provenance_state")
        or metadata.get("xrd_provenance_state")
        or ("complete" if metadata.get("xrd_wavelength_angstrom") not in (None, "") else "incomplete")
    ).strip().lower()
    provenance_warning = str(summary.get("xrd_provenance_warning") or metadata.get("xrd_provenance_warning") or "").strip()
    import_review_required = bool(metadata.get("import_review_required"))
    reason_below_threshold = str(summary.get("top_candidate_reason_below_threshold") or "").strip()
    validation_status = str((validation or {}).get("status") or "").lower()
    wavelength_missing = metadata.get("xrd_wavelength_angstrom") in (None, "")
    metadata_gaps_xrd = metadata_gaps(metadata, ["instrument"])
    if wavelength_missing:
        metadata_gaps_xrd.append("xrd wavelength")
    if metadata.get("xrd_axis_unit") in (None, ""):
        metadata_gaps_xrd.append("xrd axis unit")

    second_score = None
    if len(rows) > 1:
        second_score = _safe_float(rows[1].get("normalized_score"))
    score_gap = (top_score - second_score) if top_score is not None and second_score is not None else None
    sparse_shared_peaks = shared_peak_count is not None and shared_peak_count < 3
    low_coverage = coverage_ratio is not None and coverage_ratio < 0.5
    weak_overlap = weighted_overlap is not None and weighted_overlap < 0.45
    partial_support = bool(
        sparse_shared_peaks
        or low_coverage
        or weak_overlap
        or (unmatched_major_peak_count or 0) > 0
    )
    coverage_limited = bool(coverage_warning) or coverage_tier in {"seed_dev", "seed", "limited"}

    allow_comparative = (
        validation_status != "fail"
        and bool(rows)
        and fit_band in {"high", "moderate"}
    )
    allow_interpretive = (
        match_status == "matched"
        and confidence_band in {"high", "medium"}
        and validation_status == "pass"
        and top_score is not None
        and top_score >= 0.7
        and (shared_peak_count or 0) >= 3
        and (coverage_ratio or 0.0) >= 0.55
        and (weighted_overlap or 0.0) >= 0.6
        and (unmatched_major_peak_count or 0) == 0
        and provenance_state == "complete"
        and not import_review_required
    )

    claims: list[dict[str, Any]] = []
    evidence_map: dict[str, list[str]] = {}

    if match_status == "matched":
        descriptive_text = (
            f"Accepted qualitative phase screening retained {best_candidate} as the leading ranked candidate against the available XRD references."
        )
    elif rows:
        descriptive_text = (
            f"A best-ranked XRD candidate ({best_candidate}) was generated, but accepted match status remains no_match for qualitative screening."
        )
    else:
        descriptive_text = "No XRD candidate produced accepted qualitative screening support from the available reference corpus."
    evidence = [
        f"Accepted match status: {match_status}.",
        f"Ranked candidate count: {candidate_count}.",
    ]
    if top_score is not None:
        evidence.append(f"Best-ranked score: {top_score:.3f}.")
    if confidence_band:
        evidence.append(f"Confidence band: {confidence_band}.")
    if provider_scope:
        evidence.append(f"Provider scope: {', '.join(provider_scope)}.")
    claims.append(_claim("C1", "descriptive", descriptive_text, evidence))
    evidence_map["C1"] = evidence

    if allow_comparative and rows:
        if partial_support or match_status == "no_match":
            comparative_text = (
                f"Observed/reference overlap is strongest for {best_candidate}, but the support remains partial and does not justify definitive phase assignment."
            )
        else:
            comparative_text = (
                f"Observed/reference overlap is strongest for {best_candidate} relative to the other ranked candidates in the screened library set."
            )
        evidence = []
        if shared_peak_count is not None:
            evidence.append(f"Shared peaks with best-ranked candidate: {shared_peak_count}.")
        if coverage_ratio is not None:
            evidence.append(f"Reference coverage ratio: {coverage_ratio:.3f}.")
        if weighted_overlap is not None:
            evidence.append(f"Weighted overlap score: {weighted_overlap:.3f}.")
        if mean_delta_position is not None:
            evidence.append(f"Mean delta position: {mean_delta_position:.3f}.")
        if unmatched_major_peak_count is not None:
            evidence.append(f"Unmatched major reference peaks: {unmatched_major_peak_count}.")
        if score_gap is not None:
            evidence.append(f"Score gap to next ranked candidate: {score_gap:.3f}.")
        claims.append(_claim("C2", "comparative", comparative_text, evidence))
        evidence_map["C2"] = evidence

    if allow_interpretive:
        interpretive_text = (
            f"The screening pattern is most consistent with {best_candidate} as the leading reference-compatible phase candidate, and the evidence supports retaining this candidate for follow-up verification rather than definitive identification."
        )
        evidence = [
            f"Accepted match status: {match_status}.",
            f"Best-ranked score: {top_score:.3f}.",
            f"Shared peaks: {shared_peak_count}.",
            f"Coverage ratio: {coverage_ratio:.3f}.",
            f"Weighted overlap score: {weighted_overlap:.3f}.",
            f"Unmatched major reference peaks: {unmatched_major_peak_count}.",
        ]
        claims.append(_claim("C3", "mechanistic", interpretive_text, evidence))
        evidence_map["C3"] = evidence

    alternatives: list[str] = []
    if coverage_limited or len(provider_scope) <= 1:
        alternatives.append(
            "The available reference corpus may not yet contain the true phase, polymorph, or mixture component that generated the observed pattern."
        )
    if partial_support or (candidate_count and candidate_count > 1):
        alternatives.append(
            "A multiphase pattern could produce partial support for several candidates without yielding an accepted single-phase qualitative match."
        )
    if wavelength_missing or provenance_state != "complete" or (mean_delta_position is not None and mean_delta_position > 0.12):
        alternatives.append(
            "Peak-position mismatch may be amplified by wavelength provenance gaps, calibration drift, or other axis-position errors rather than only by incorrect reference identity."
        )
    else:
        alternatives.append(
            "Preferred orientation or intensity distortion could weaken apparent agreement with otherwise relevant reference patterns."
        )
    alternatives.append(
        "Peak-picking, smoothing, or tolerance settings may change how low-intensity peaks participate in the qualitative overlap score."
    )

    uncertainty_items = [fit_reason]
    if match_status == "no_match":
        uncertainty_items.append(
            "Accepted match status remained no_match; the best-ranked candidate did not satisfy the configured qualitative screening threshold."
        )
    elif confidence_band == "low":
        uncertainty_items.append(
            "The retained candidate is low confidence and should be treated as a follow-up target rather than a confirmed phase call."
        )
    if reason_below_threshold:
        uncertainty_items.append(f"Reason below threshold: {reason_below_threshold}.")
    if sparse_shared_peaks:
        uncertainty_items.append("Shared-peak support is sparse for the best-ranked candidate.")
    if low_coverage:
        uncertainty_items.append("Reference coverage is limited, so substantial portions of the candidate peak set remain unsupported.")
    if weak_overlap:
        uncertainty_items.append("Weighted overlap remains weak after intensity and penalty terms are applied.")
    if (unmatched_major_peak_count or 0) > 0:
        uncertainty_items.append("One or more major reference peaks remain unmatched, which weakens phase-specific confidence.")
    if coverage_warning:
        uncertainty_items.append(coverage_warning)
    if provider_candidate_counts:
        uncertainty_items.append(
            "Provider candidate breadth: "
            + ", ".join(f"{provider}={count}" for provider, count in provider_candidate_counts.items())
            + "."
        )
    if metadata_gaps_xrd:
        uncertainty_items.append(f"Missing metadata: {', '.join(metadata_gaps_xrd)}.")
    if provenance_warning:
        uncertainty_items.append(provenance_warning)
    if import_review_required:
        uncertainty_items.append("Import review is still required for the current XRD metadata or column mapping.")
    if validation_status == "warn":
        uncertainty_items.append("Validation warnings were reported and should temper interpretation confidence.")

    if allow_interpretive:
        overall_confidence = "moderate"
        overall_label = "moderate, qualitative screening support for follow-up verification"
    elif match_status == "matched" and confidence_band in {"medium", "high"} and not partial_support:
        overall_confidence = "moderate"
        overall_label = "moderate, qualitative phase-screening evidence"
    else:
        overall_confidence = "low"
        overall_label = "low, cautionary qualitative screening only"

    reasoning_state = (
        "accepted_screening"
        if allow_interpretive
        else "low_confidence"
        if match_status == "matched" and confidence_band == "low"
        else "no_match"
        if match_status == "no_match"
        else "partial_overlap"
    )

    return {
        "scientific_claims": claims,
        "evidence_map": evidence_map,
        "uncertainty_assessment": {
            "overall_confidence": overall_confidence,
            "overall_confidence_label": overall_label,
            "fit_assessment": fit_band,
            "metadata_gaps": metadata_gaps_xrd,
            "items": uncertainty_items,
            "coverage_tier": coverage_tier,
            "provider_scope": provider_scope,
            "provenance_state": provenance_state,
        },
        "alternative_hypotheses": alternatives[:4],
        "next_experiments": recommend_next_experiments(
            "XRD",
            metadata_gaps=metadata_gaps_xrd,
            fit_band=fit_band,
            mechanism_hint=reasoning_state,
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
    if analysis == "XRD":
        return _build_xrd_reasoning(summary, rows, metadata, band, fit_reason, validation)
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
