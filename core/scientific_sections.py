"""Scientific-context helpers for normalized analysis records."""

from __future__ import annotations

import copy
from typing import Any, Iterable


SCIENTIFIC_CONTEXT_KEYS = (
    "methodology",
    "equations",
    "numerical_interpretation",
    "fit_quality",
    "warnings",
    "limitations",
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

    return normalized


def build_scientific_context(
    *,
    methodology: dict[str, Any] | None = None,
    equations: list[dict[str, Any]] | None = None,
    numerical_interpretation: list[dict[str, Any]] | None = None,
    fit_quality: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    limitations: list[str] | None = None,
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
        }
    )


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
    for index, item in enumerate(context["numerical_interpretation"], start=1):
        label = item.get("metric") or f"Observation {index}"
        statement = item.get("statement") or "Not recorded"
        value = item.get("value")
        unit = item.get("unit")
        implication = item.get("implication")
        parts = [str(statement)]
        if value is not None:
            parts.append(f"value={value}")
        if unit:
            parts.append(f"unit={unit}")
        if implication:
            parts.append(f"implication={implication}")
        interpretation_payload[str(label)] = " | ".join(parts)
    if interpretation_payload:
        sections.append(("Numerical Interpretation", interpretation_payload))

    if context["fit_quality"]:
        sections.append(("Fit Quality", context["fit_quality"]))

    warning_limit_payload: dict[str, Any] = {}
    if context["warnings"]:
        warning_limit_payload["warnings"] = context["warnings"]
    if context["limitations"]:
        warning_limit_payload["limitations"] = context["limitations"]
    if warning_limit_payload:
        sections.append(("Warnings and Limitations", warning_limit_payload))

    return sections
