"""Scientific-context helpers for normalized analysis records."""

from __future__ import annotations

import copy
import unicodedata
from typing import Any, Iterable

from core.mechanism_rules import tga_mechanism_signals


SCIENTIFIC_CONTEXT_KEYS = (
    "methodology",
    "equations",
    "numerical_interpretation",
    "fit_quality",
    "warnings",
    "limitations",
    "scientific_claims",
    "evidence_map",
    "uncertainty_assessment",
    "alternative_hypotheses",
    "next_experiments",
)

_DATA_COMPLETENESS_HINTS = (
    "missing",
    "not recorded",
    "not available",
    "unavailable",
    "unknown",
    "incomplete",
    "not provided",
    "not supplied",
    "import",
)


def _copy_mapping(value: Any) -> dict[str, Any]:
    return copy.deepcopy(value) if isinstance(value, dict) else {}


def _to_str_list(values: Any) -> list[str]:
    if values in (None, "", [], (), {}):
        return []
    if isinstance(values, str):
        return [values]
    if isinstance(values, Iterable):
        output: list[str] = []
        for item in values:
            if item in (None, ""):
                continue
            output.append(str(item))
        return output
    return [str(values)]


def _to_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    output: dict[str, Any] = {}
    for key, item in value.items():
        if key in (None, ""):
            continue
        output[str(key)] = copy.deepcopy(item)
    return output


def _clean_text(value: Any) -> str:
    text = str(value).strip()
    if not text:
        return ""
    return " ".join(text.split())


def normalize_report_text(value: Any) -> str:
    """Normalize report text for Unicode-safe rendering."""
    return unicodedata.normalize("NFC", _clean_text(value))


def _dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in values:
        normalized = _clean_text(item)
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped


def _humanize_metric(metric: str | None) -> str:
    if not metric:
        return ""
    words = str(metric).replace("_", " ").split()
    return " ".join(word.capitalize() for word in words)


def _value_with_unit(value: Any, unit: str | None) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, dict):
        parts = []
        for key, raw in value.items():
            parts.append(f"{_humanize_metric(str(key))} {raw}")
        payload = ", ".join(parts)
    else:
        payload = str(value)
    if unit:
        payload = f"{payload} {unit}"
    return payload


def _sentence(text: str) -> str:
    cleaned = normalize_report_text(text)
    if not cleaned:
        return ""
    if cleaned[-1] in ".!?":
        return cleaned
    return f"{cleaned}."


def _sentence_list(values: Iterable[str]) -> list[str]:
    return [_sentence(value) for value in values if _sentence(value)]


def _safe_float(value: Any) -> float | None:
    try:
        if value in (None, "", [], {}):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _metadata_warning_summary(data_warnings: list[str]) -> tuple[str | None, list[str]]:
    fields = []
    patterns = (
        ("sample mass", "sample mass"),
        ("heating rate", "heating rate"),
        ("instrument", "instrument"),
        ("atmosphere", "atmosphere"),
        ("vendor", "vendor"),
    )
    remaining = []
    for warning in data_warnings:
        lower = warning.casefold()
        matched = False
        for token, label in patterns:
            if token in lower:
                if label not in fields:
                    fields.append(label)
                matched = True
        if not matched:
            remaining.append(warning)
    if not fields:
        return None, data_warnings
    if len(fields) == 1:
        summary = f"Key metadata were not recorded, including {fields[0]}."
    elif len(fields) == 2:
        summary = f"Key metadata were not recorded, including {fields[0]} and {fields[1]}."
    else:
        summary = f"Key metadata were not recorded, including {', '.join(fields[:-1])}, and {fields[-1]}."
    return summary, remaining


def build_equation(
    name: str,
    formula: str,
    *,
    variables: dict[str, str] | None = None,
    assumptions: list[str] | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Build a report-ready equation payload."""
    payload: dict[str, Any] = {
        "name": str(name),
        "formula": str(formula),
    }
    if variables:
        payload["variables"] = _copy_mapping(variables)
    if assumptions:
        payload["assumptions"] = _to_str_list(assumptions)
    if notes:
        payload["notes"] = str(notes)
    return payload


def build_interpretation(
    statement: str,
    *,
    metric: str | None = None,
    value: Any = None,
    unit: str | None = None,
    implication: str | None = None,
) -> dict[str, Any]:
    """Build a numerical-interpretation entry."""
    payload: dict[str, Any] = {"statement": str(statement)}
    if metric:
        payload["metric"] = str(metric)
    if value is not None:
        payload["value"] = value
    if unit:
        payload["unit"] = str(unit)
    if implication:
        payload["implication"] = str(implication)
    return payload


def build_fit_quality(
    metrics: dict[str, Any] | None = None,
    *,
    narrative: str | None = None,
) -> dict[str, Any]:
    """Build fit-quality payload."""
    payload = _copy_mapping(metrics)
    if narrative:
        payload["narrative"] = str(narrative)
    return payload


def build_limitations(
    *,
    limitations: list[str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, list[str]]:
    """Build warnings/limitations payload."""
    return {
        "limitations": _to_str_list(limitations),
        "warnings": _to_str_list(warnings),
    }


def normalize_scientific_context(scientific_context: dict[str, Any] | None) -> dict[str, Any]:
    """Return a normalized scientific-context mapping."""
    context = _copy_mapping(scientific_context)

    normalized: dict[str, Any] = {
        "methodology": _copy_mapping(context.get("methodology")),
        "equations": [],
        "numerical_interpretation": [],
        "fit_quality": _copy_mapping(context.get("fit_quality")),
        "warnings": _to_str_list(context.get("warnings")),
        "limitations": _to_str_list(context.get("limitations")),
        "scientific_claims": [],
        "evidence_map": _to_mapping(context.get("evidence_map")),
        "uncertainty_assessment": _copy_mapping(context.get("uncertainty_assessment")),
        "alternative_hypotheses": _to_str_list(context.get("alternative_hypotheses")),
        "next_experiments": _to_str_list(context.get("next_experiments")),
    }

    for item in context.get("equations") or []:
        if isinstance(item, dict):
            normalized["equations"].append(copy.deepcopy(item))
        elif item not in (None, ""):
            normalized["equations"].append({"formula": str(item)})

    for item in context.get("numerical_interpretation") or []:
        if isinstance(item, dict):
            normalized["numerical_interpretation"].append(copy.deepcopy(item))
        elif item not in (None, ""):
            normalized["numerical_interpretation"].append({"statement": str(item)})

    for item in context.get("scientific_claims") or []:
        if isinstance(item, dict):
            normalized["scientific_claims"].append(copy.deepcopy(item))
        elif item not in (None, ""):
            normalized["scientific_claims"].append({"strength": "descriptive", "claim": str(item)})

    return normalized


def build_scientific_context(
    *,
    methodology: dict[str, Any] | None = None,
    equations: list[dict[str, Any]] | None = None,
    numerical_interpretation: list[dict[str, Any]] | None = None,
    fit_quality: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    limitations: list[str] | None = None,
    scientific_claims: list[dict[str, Any]] | None = None,
    evidence_map: dict[str, Any] | None = None,
    uncertainty_assessment: dict[str, Any] | None = None,
    alternative_hypotheses: list[str] | None = None,
    next_experiments: list[str] | None = None,
) -> dict[str, Any]:
    """Build and normalize a scientific-context payload."""
    return normalize_scientific_context(
        {
            "methodology": methodology or {},
            "equations": equations or [],
            "numerical_interpretation": numerical_interpretation or [],
            "fit_quality": fit_quality or {},
            "warnings": warnings or [],
            "limitations": limitations or [],
            "scientific_claims": scientific_claims or [],
            "evidence_map": evidence_map or {},
            "uncertainty_assessment": uncertainty_assessment or {},
            "alternative_hypotheses": alternative_hypotheses or [],
            "next_experiments": next_experiments or [],
        }
    )


def build_scientific_interpretation_lines(
    scientific_context: dict[str, Any] | None,
    *,
    max_items: int = 6,
) -> list[str]:
    """Return reader-facing interpretation sentences from normalized context."""
    context = normalize_scientific_context(scientific_context)
    output: list[str] = []
    for item in context["numerical_interpretation"]:
        statement = _sentence(item.get("statement") or "Observation recorded")
        metric = _humanize_metric(item.get("metric"))
        value = _value_with_unit(item.get("value"), item.get("unit"))
        implication = _sentence(item.get("implication") or "")

        if metric and value:
            sentence = f"{statement} Reported {metric.lower()} was {value}."
        elif value:
            sentence = f"{statement} Observed value: {value}."
        else:
            sentence = statement

        if implication:
            sentence = f"{sentence} {implication}"

        output.append(" ".join(sentence.split()))
        if len(output) >= max_items:
            break
    return output


def condense_warning_limitations(
    scientific_context: dict[str, Any] | None,
    *,
    validation: dict[str, Any] | None = None,
    max_data_warnings: int = 3,
    max_method_limits: int = 2,
) -> dict[str, list[str]]:
    """Group warnings into concise, deduplicated reader-facing categories."""
    context = normalize_scientific_context(scientific_context)
    validation_warnings = _to_str_list((validation or {}).get("warnings"))
    raw_warnings = _dedupe_preserve_order(context["warnings"] + validation_warnings)
    raw_limits = _dedupe_preserve_order(context["limitations"])

    data_warnings: list[str] = []
    method_limits: list[str] = []
    for item in raw_warnings:
        lower = item.casefold()
        if any(token in lower for token in _DATA_COMPLETENESS_HINTS):
            data_warnings.append(_sentence(item))
        else:
            method_limits.append(_sentence(item))
    for item in raw_limits:
        method_limits.append(_sentence(item))

    metadata_summary, remaining_data = _metadata_warning_summary(data_warnings)
    data_output = []
    if metadata_summary:
        data_output.append(metadata_summary)
    data_output.extend(remaining_data)

    return {
        "data_completeness_warnings": _dedupe_preserve_order(_sentence_list(data_output))[:max_data_warnings],
        "methodological_limitations": _dedupe_preserve_order(_sentence_list(method_limits))[:max_method_limits],
    }


def build_tga_scientific_narrative(
    *,
    summary: dict[str, Any] | None,
    rows: list[dict[str, Any]] | None,
    metadata: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
) -> list[str]:
    """Return domain-aware narrative statements for TGA interpretation."""
    summary = summary or {}
    rows = [row for row in (rows or []) if isinstance(row, dict)]
    metadata = metadata or {}
    validation = validation or {}

    signals = tga_mechanism_signals(
        summary,
        rows,
        metadata=metadata,
        dataset_key=str(metadata.get("file_name") or metadata.get("display_name") or metadata.get("sample_name") or ""),
    )
    class_inference = signals.get("material_class_inference") or {}
    mass_balance = signals.get("mass_balance_assessment") or {}
    class_label = class_inference.get("material_class_label") or "unknown / unconstrained"
    class_confidence = class_inference.get("confidence") or "low"

    step_count = signals.get("dtg_resolved_event_count") or summary.get("step_count")
    lead_midpoint = signals.get("lead_midpoint_temperature")
    lines: list[str] = []
    if step_count in (None, "", 0):
        lines.append(_sentence("The thermogram could not resolve DTG-based event structure from the available payload."))
    elif signals.get("possible_subdivision"):
        lines.append(
            _sentence(
                f"{step_count} DTG-resolved events were detected; at least one minor or closely spaced event may represent subdivision of a broader transformation region rather than an independent mechanistic step"
            )
        )
    elif signals.get("dominant_step"):
        if lead_midpoint is not None:
            lines.append(
                _sentence(
                    f"The thermogram indicates a dominant primary mass-loss event centered near {float(lead_midpoint):.0f} °C, with weaker secondary contributions"
                )
            )
        else:
            lines.append(_sentence("The thermogram indicates a dominant primary mass-loss event with weaker secondary contributions"))
    else:
        lines.append(_sentence(f"The thermogram indicates {step_count} DTG-resolved events with comparable contributions across the measured range"))

    loss_value = _safe_float(summary.get("total_mass_loss_percent"))
    residue_value = _safe_float(summary.get("residue_percent"))
    balance_status = str(mass_balance.get("status") or "not_assessed")
    pathway = str(mass_balance.get("pathway") or "").strip()
    material_class = str(class_inference.get("material_class") or "")
    if loss_value is not None and residue_value is not None:
        if balance_status in {"strong_match", "plausible_match"} and pathway:
            line = (
                f"The total mass loss (~{loss_value:.1f}%) and final residue (~{residue_value:.1f}%) are consistent with near-complete {pathway}"
            )
        elif balance_status in {"strong_match", "plausible_match"} and material_class == "hydrate_salt":
            line = (
                f"The total mass loss (~{loss_value:.1f}%) and final residue (~{residue_value:.1f}%) are consistent with near-complete dehydration to an expected anhydrous residue"
            )
        elif balance_status in {"strong_match", "plausible_match"} and material_class == "carbonate_inorganic":
            line = (
                f"The total mass loss (~{loss_value:.1f}%) and final residue (~{residue_value:.1f}%) are consistent with near-complete decarbonation to a stable oxide-rich residue"
            )
        elif balance_status in {"strong_match", "plausible_match"} and material_class in {"hydroxide_to_oxide", "oxalate_multistage_inorganic", "generic_inorganic_salt_or_mineral"}:
            line = (
                f"The total mass loss (~{loss_value:.1f}%) and final residue (~{residue_value:.1f}%) are consistent with conversion to an expected stable solid residue pathway"
            )
        elif loss_value >= 90 and residue_value <= 10:
            line = (
                f"The total mass loss (~{loss_value:.1f}%) and final residue (~{residue_value:.1f}%) are consistent with extensive decomposition across the measured range"
            )
        else:
            line = (
                f"The total mass loss (~{loss_value:.1f}%) and final residue (~{residue_value:.1f}%) indicate partial conversion within the measured range; residue alone should not be treated as evidence of incomplete reaction without class-specific chemistry"
            )
        lines.append(_sentence(line))

    lines.append(_sentence(f"Material-class inference is {class_label} (confidence: {class_confidence})"))
    if balance_status == "mismatch":
        lines.append(_sentence("Stoichiometric mass-balance matching deviated from simple class-based pathways, so mechanistic conclusions remain conservative"))
    elif balance_status == "not_assessed":
        lines.append(_sentence("Stoichiometric mass-balance matching could not be established from available formula/context clues"))

    missing_fields = []
    for key, label in (
        ("sample_mass", "sample mass"),
        ("heating_rate", "heating rate"),
        ("atmosphere", "atmosphere"),
        ("instrument", "instrument"),
    ):
        if not metadata.get(key):
            missing_fields.append(label)
    if missing_fields:
        if len(missing_fields) == 1:
            caveat = f"Because {missing_fields[0]} was not recorded, this interpretation should be treated as condition-limited rather than fully definitive."
        else:
            caveat = f"Because {', '.join(missing_fields[:-1])}, and {missing_fields[-1]} were not recorded, this interpretation should be treated as condition-limited rather than fully definitive."
        lines.append(_sentence(caveat))
    elif (validation.get("status") or "").lower() == "warn":
        lines.append(_sentence("Validation warnings were present, so this interpretation should be treated as moderate-confidence"))

    return [normalize_report_text(line) for line in lines if line]


def scientific_context_to_report_sections(scientific_context: dict[str, Any] | None) -> list[tuple[str, dict[str, Any]]]:
    """Convert scientific context into DOCX table sections."""
    context = normalize_scientific_context(scientific_context)
    sections: list[tuple[str, dict[str, Any]]] = []

    if context["methodology"]:
        sections.append(("Methodology", context["methodology"]))

    equations_payload: dict[str, Any] = {}
    for index, equation in enumerate(context["equations"], start=1):
        label = equation.get("name") or f"Equation {index}"
        formula = equation.get("formula") or "Not recorded"
        assumptions = equation.get("assumptions") or []
        notes = equation.get("notes")
        line = str(formula)
        if assumptions:
            line = f"{line} | assumptions: {'; '.join(str(item) for item in assumptions)}"
        if notes:
            line = f"{line} | notes: {notes}"
        equations_payload[str(label)] = line
    if equations_payload:
        sections.append(("Equations and Formulation", equations_payload))

    interpretation_payload: dict[str, Any] = {}
    for index, line in enumerate(build_scientific_interpretation_lines(context), start=1):
        interpretation_payload[f"Observation {index}"] = line
    if interpretation_payload:
        sections.append(("Scientific Interpretation", interpretation_payload))

    claim_payload: dict[str, Any] = {}
    for item in context.get("scientific_claims") or []:
        if not isinstance(item, dict):
            continue
        claim_text = normalize_report_text(item.get("claim") or item.get("statement") or "")
        if not claim_text:
            continue
        claim_id = item.get("id")
        strength = normalize_report_text(item.get("strength") or "descriptive").lower()
        strength_label = strength.capitalize()
        label = f"{claim_id} ({strength_label})" if claim_id else f"Claim {len(claim_payload) + 1} ({strength_label})"
        claim_payload[label] = claim_text
    if claim_payload:
        sections.append(("Primary Scientific Interpretation", claim_payload))

    evidence_payload: dict[str, Any] = {}
    evidence_map = context.get("evidence_map") or {}
    if isinstance(evidence_map, dict):
        for key, value in evidence_map.items():
            if isinstance(value, list):
                text = "; ".join(normalize_report_text(item) for item in value if normalize_report_text(item))
            else:
                text = normalize_report_text(value)
            if text:
                evidence_payload[normalize_report_text(key)] = text
    for item in context.get("scientific_claims") or []:
        if not isinstance(item, dict):
            continue
        claim_id = normalize_report_text(item.get("id") or "")
        evidence = item.get("evidence")
        if not claim_id or claim_id in evidence_payload:
            continue
        if isinstance(evidence, list):
            text = "; ".join(normalize_report_text(entry) for entry in evidence if normalize_report_text(entry))
            if text:
                evidence_payload[claim_id] = text
    if evidence_payload:
        sections.append(("Evidence Supporting This Interpretation", evidence_payload))

    alternatives_payload = {
        f"Alternative {idx}": normalize_report_text(item)
        for idx, item in enumerate(context.get("alternative_hypotheses") or [], start=1)
        if normalize_report_text(item)
    }
    if alternatives_payload:
        sections.append(("Alternative Explanations", alternatives_payload))

    uncertainty_payload: dict[str, Any] = {}
    uncertainty = context.get("uncertainty_assessment") or {}
    if isinstance(uncertainty, dict):
        overall = uncertainty.get("overall_confidence")
        overall_label = uncertainty.get("overall_confidence_label")
        fit_assessment = uncertainty.get("fit_assessment")
        if overall_label:
            uncertainty_payload["Overall Confidence"] = normalize_report_text(overall_label)
        elif overall:
            uncertainty_payload["Overall Confidence"] = normalize_report_text(overall)
        if fit_assessment:
            uncertainty_payload["Fit Assessment"] = normalize_report_text(fit_assessment)
        gaps = _to_str_list(uncertainty.get("metadata_gaps"))
        if gaps:
            uncertainty_payload["Metadata Gaps"] = "; ".join(normalize_report_text(item) for item in gaps if normalize_report_text(item))
        items = _to_str_list(uncertainty.get("items"))
        if items:
            uncertainty_payload["Uncertainty Notes"] = "; ".join(normalize_report_text(item) for item in items if normalize_report_text(item))

    grouped = condense_warning_limitations(context)
    if grouped.get("data_completeness_warnings"):
        uncertainty_payload["Data Completeness Warnings"] = "; ".join(grouped["data_completeness_warnings"])
    if grouped.get("methodological_limitations"):
        uncertainty_payload["Methodological Limitations"] = "; ".join(grouped["methodological_limitations"])
    if uncertainty_payload:
        sections.append(("Uncertainty and Methodological Limits", uncertainty_payload))

    next_exp_payload = {
        f"Experiment {idx}": normalize_report_text(item)
        for idx, item in enumerate(context.get("next_experiments") or [], start=1)
        if normalize_report_text(item)
    }
    if next_exp_payload:
        sections.append(("Recommended Follow-Up Experiments", next_exp_payload))

    if context["fit_quality"]:
        sections.append(("Fit Quality", context["fit_quality"]))

    warning_limit_payload = condense_warning_limitations(context)
    grouped_payload: dict[str, Any] = {}
    if warning_limit_payload["data_completeness_warnings"]:
        grouped_payload["Data Completeness Warnings"] = warning_limit_payload["data_completeness_warnings"]
    if warning_limit_payload["methodological_limitations"]:
        grouped_payload["Methodological Limitations"] = warning_limit_payload["methodological_limitations"]
    if grouped_payload:
        sections.append(("Warnings and Limitations", grouped_payload))

    return sections
