"""Helpers for stable DSC/TGA processing payloads."""

from __future__ import annotations

import copy
import re
from typing import Any


PROCESSING_SCHEMA_VERSION = 1

_SIGNAL_PIPELINE_SECTIONS = {
    "DSC": ("smoothing", "baseline"),
    "TGA": ("smoothing",),
    "DTA": ("smoothing", "baseline"),
    "KISSINGER": (),
    "OZAWA-FLYNN-WALL": (),
    "FRIEDMAN": (),
    "PEAK DECONVOLUTION": (),
}
_ANALYSIS_STEP_SECTIONS = {
    "DSC": ("glass_transition", "peak_detection"),
    "TGA": ("step_detection",),
    "DTA": ("peak_detection",),
    "KISSINGER": ("kinetic_regression",),
    "OZAWA-FLYNN-WALL": ("isoconversional_analysis",),
    "FRIEDMAN": ("isoconversional_analysis",),
    "PEAK DECONVOLUTION": ("peak_fitting",),
}
_DEFAULT_WORKFLOW_TEMPLATE = {
    "DSC": "General DSC",
    "TGA": "General TGA",
    "DTA": "General DTA",
    "KISSINGER": "Kissinger Kinetics",
    "OZAWA-FLYNN-WALL": "OFW Isoconversional",
    "FRIEDMAN": "Friedman Isoconversional",
    "PEAK DECONVOLUTION": "General Peak Deconvolution",
}
_WORKFLOW_TEMPLATES = {
    "DSC": (
        {"id": "dsc.general", "label": "General DSC", "version": 1},
        {"id": "dsc.polymer_tg", "label": "Polymer Tg", "version": 1},
        {"id": "dsc.polymer_melting_crystallization", "label": "Polymer Melting/Crystallization", "version": 1},
    ),
    "TGA": (
        {"id": "tga.general", "label": "General TGA", "version": 1},
        {"id": "tga.single_step_decomposition", "label": "Single-Step Decomposition", "version": 1},
        {"id": "tga.multi_step_decomposition", "label": "Multi-Step Decomposition", "version": 1},
    ),
    "DTA": (
        {"id": "dta.general", "label": "General DTA", "version": 1},
        {"id": "dta.thermal_events", "label": "Thermal Event Screening", "version": 1},
    ),
    "KISSINGER": (
        {"id": "kinetics.kissinger_general", "label": "Kissinger Kinetics", "version": 1},
    ),
    "OZAWA-FLYNN-WALL": (
        {"id": "kinetics.ofw_general", "label": "OFW Isoconversional", "version": 1},
    ),
    "FRIEDMAN": (
        {"id": "kinetics.friedman_general", "label": "Friedman Isoconversional", "version": 1},
    ),
    "PEAK DECONVOLUTION": (
        {"id": "deconvolution.general", "label": "General Peak Deconvolution", "version": 1},
        {"id": "deconvolution.overlap_resolution", "label": "Overlap Resolution", "version": 1},
    ),
}
_TGA_UNIT_MODES = (
    {"id": "auto", "label": "Auto"},
    {"id": "percent", "label": "Percent"},
    {"id": "absolute_mass", "label": "Absolute Mass"},
)
_TGA_METHOD_CONTEXT_ALIASES = (
    "tga_unit_mode_declared",
    "tga_unit_mode_label",
    "tga_unit_mode_resolved",
    "tga_unit_mode_resolved_label",
    "tga_unit_auto_inference_used",
    "tga_unit_inference_basis",
    "tga_unit_interpretation_status",
    "tga_unit_review_reason",
    "tga_unit_reference_source",
    "tga_unit_reference_value",
    "tga_signal_unit_recorded",
)
_METHOD_CONTEXT_DEFAULTS = {
    "DSC": {
        "sign_convention_id": "dsc.endotherm_up",
        "sign_convention_label": "Endotherm up / Exotherm down",
    },
    "TGA": {
        "step_analysis_basis": "DTG-derived onset, midpoint, and endset estimation",
        "tga_unit_mode_declared": "auto",
        "tga_unit_mode_label": "Auto",
    },
    "DTA": {
        "sign_convention_id": "dta.exotherm_up",
        "sign_convention_label": "Exotherm up / Endotherm down",
    },
    "KISSINGER": {
        "kinetic_family": "model_fitting",
        "formulation": "kissinger",
        "temperature_scale": "kelvin",
    },
    "OZAWA-FLYNN-WALL": {
        "kinetic_family": "isoconversional",
        "formulation": "ozawa_flynn_wall",
        "temperature_scale": "kelvin",
    },
    "FRIEDMAN": {
        "kinetic_family": "isoconversional",
        "formulation": "friedman",
        "temperature_scale": "kelvin",
    },
    "PEAK DECONVOLUTION": {
        "fit_engine": "lmfit",
        "objective_function": "least_squares",
    },
}


def _normalize_analysis_type(analysis_type: str | None) -> str:
    return (analysis_type or "UNKNOWN").upper()


def _copy_mapping(payload: Any) -> dict[str, Any]:
    return copy.deepcopy(payload) if isinstance(payload, dict) else {}


def _slugify(value: Any) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower())
    return text.strip("_") or "template"


def get_workflow_templates(analysis_type: str | None) -> list[dict[str, Any]]:
    """Return a copy of the stable workflow template catalog for an analysis type."""
    normalized_type = _normalize_analysis_type(analysis_type)
    return [copy.deepcopy(entry) for entry in _WORKFLOW_TEMPLATES.get(normalized_type, ())]


def get_tga_unit_modes() -> list[dict[str, str]]:
    """Return the stable TGA unit-mode catalog."""
    return [copy.deepcopy(entry) for entry in _TGA_UNIT_MODES]


def _fallback_template_entry(analysis_type: str, raw_value: Any, version: int | None = None) -> dict[str, Any]:
    normalized_type = _normalize_analysis_type(analysis_type)
    label = str(raw_value or _DEFAULT_WORKFLOW_TEMPLATE.get(normalized_type, f"General {normalized_type}"))
    return {
        "id": f"{normalized_type.lower()}.custom.{_slugify(label)}",
        "label": label,
        "version": int(version or 1),
    }


def _resolve_workflow_template(
    analysis_type: str,
    *,
    workflow_template: Any = None,
    workflow_template_label: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = payload or {}
    catalog = get_workflow_templates(analysis_type)
    template_inputs = [
        workflow_template,
        payload.get("workflow_template_id"),
        payload.get("workflow_template_label"),
        payload.get("workflow_template"),
    ]

    normalized_inputs = {str(item).strip().lower() for item in template_inputs if item not in (None, "")}
    for entry in catalog:
        if entry["id"].lower() in normalized_inputs or entry["label"].lower() in normalized_inputs:
            resolved = copy.deepcopy(entry)
            if workflow_template_label:
                resolved["label"] = workflow_template_label
            elif payload.get("workflow_template_label"):
                resolved["label"] = str(payload["workflow_template_label"])
            elif payload.get("workflow_template") and str(payload["workflow_template"]).strip().lower() == entry["id"].lower():
                resolved["label"] = entry["label"]
            return resolved

    raw_value = workflow_template or payload.get("workflow_template_label") or payload.get("workflow_template")
    resolved = _fallback_template_entry(
        analysis_type,
        raw_value,
        version=payload.get("workflow_template_version"),
    )
    if workflow_template_label:
        resolved["label"] = workflow_template_label
    return resolved


def _extract_group(
    payload: dict[str, Any],
    group_key: str,
    section_names: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    nested = _copy_mapping(payload.get(group_key))
    group: dict[str, dict[str, Any]] = {}

    for section_name in section_names:
        if isinstance(nested.get(section_name), dict):
            group[section_name] = copy.deepcopy(nested[section_name])
        elif isinstance(payload.get(section_name), dict):
            group[section_name] = copy.deepcopy(payload[section_name])

    return group


def ensure_processing_payload(
    payload: dict[str, Any] | None = None,
    *,
    analysis_type: str,
    workflow_template: str | None = None,
    workflow_template_label: str | None = None,
) -> dict[str, Any]:
    """Return the standardized processing payload while preserving legacy aliases."""
    normalized_type = _normalize_analysis_type(analysis_type)
    payload = _copy_mapping(payload)
    template_entry = _resolve_workflow_template(
        normalized_type,
        workflow_template=workflow_template,
        workflow_template_label=workflow_template_label,
        payload=payload,
    )

    signal_sections = _extract_group(
        payload,
        "signal_pipeline",
        _SIGNAL_PIPELINE_SECTIONS.get(normalized_type, ()),
    )
    analysis_sections = _extract_group(
        payload,
        "analysis_steps",
        _ANALYSIS_STEP_SECTIONS.get(normalized_type, ()),
    )
    method_context = copy.deepcopy(_METHOD_CONTEXT_DEFAULTS.get(normalized_type, {}))
    method_context.update(_copy_mapping(payload.get("method_context")))
    if normalized_type == "TGA":
        for key in _TGA_METHOD_CONTEXT_ALIASES:
            if payload.get(key) not in (None, "") and key not in method_context:
                method_context[key] = copy.deepcopy(payload[key])

    normalized = {
        "schema_version": PROCESSING_SCHEMA_VERSION,
        "analysis_type": normalized_type,
        "workflow_template_id": template_entry["id"],
        "workflow_template_label": template_entry["label"],
        "workflow_template": template_entry["label"],
        "workflow_template_version": int(template_entry.get("version", payload.get("workflow_template_version") or 1)),
        "signal_pipeline": signal_sections,
        "analysis_steps": analysis_sections,
        "method_context": method_context,
    }

    for key, value in signal_sections.items():
        normalized[key] = copy.deepcopy(value)
    for key, value in analysis_sections.items():
        normalized[key] = copy.deepcopy(value)
    if method_context:
        if method_context.get("sign_convention_label"):
            normalized["sign_convention"] = method_context["sign_convention_label"]
        if method_context.get("step_analysis_basis"):
            normalized["step_analysis_basis"] = method_context["step_analysis_basis"]
        if normalized_type == "TGA":
            for key in _TGA_METHOD_CONTEXT_ALIASES:
                if key in method_context:
                    normalized[key] = copy.deepcopy(method_context[key])

    return normalized


def set_workflow_template(
    payload: dict[str, Any] | None,
    workflow_template: str,
    *,
    analysis_type: str | None = None,
    workflow_template_label: str | None = None,
) -> dict[str, Any]:
    """Update the workflow template while preserving standardized sections."""
    resolved_type = analysis_type or (payload or {}).get("analysis_type") or "UNKNOWN"
    return ensure_processing_payload(
        payload,
        analysis_type=resolved_type,
        workflow_template=workflow_template,
        workflow_template_label=workflow_template_label,
    )


def update_method_context(
    payload: dict[str, Any] | None,
    values: dict[str, Any] | None,
    *,
    analysis_type: str | None = None,
) -> dict[str, Any]:
    """Update the standardized method-context block."""
    resolved_type = analysis_type or (payload or {}).get("analysis_type") or "UNKNOWN"
    normalized = ensure_processing_payload(payload, analysis_type=resolved_type)
    method_context = normalized.get("method_context", {})
    method_context.update(_copy_mapping(values))
    normalized["method_context"] = method_context
    if method_context.get("sign_convention_label"):
        normalized["sign_convention"] = method_context["sign_convention_label"]
    if method_context.get("step_analysis_basis"):
        normalized["step_analysis_basis"] = method_context["step_analysis_basis"]
    if normalized["analysis_type"] == "TGA":
        for key in _TGA_METHOD_CONTEXT_ALIASES:
            if key in method_context:
                normalized[key] = copy.deepcopy(method_context[key])
            else:
                normalized.pop(key, None)
    return normalized


def update_processing_step(
    payload: dict[str, Any] | None,
    section_name: str,
    values: dict[str, Any] | None,
    *,
    analysis_type: str | None = None,
) -> dict[str, Any]:
    """Write a processing step into the correct standardized section and alias."""
    resolved_type = analysis_type or (payload or {}).get("analysis_type") or "UNKNOWN"
    normalized = ensure_processing_payload(payload, analysis_type=resolved_type)
    normalized_type = normalized["analysis_type"]
    values = _copy_mapping(values)

    if section_name in _SIGNAL_PIPELINE_SECTIONS.get(normalized_type, ()):
        normalized["signal_pipeline"][section_name] = copy.deepcopy(values)
    elif section_name in _ANALYSIS_STEP_SECTIONS.get(normalized_type, ()):
        normalized["analysis_steps"][section_name] = copy.deepcopy(values)
    else:
        raise ValueError(f"Unsupported processing section '{section_name}' for {normalized_type}")

    normalized[section_name] = copy.deepcopy(values)
    return normalized


def set_tga_unit_mode(
    payload: dict[str, Any] | None,
    unit_mode: str,
    *,
    unit_mode_label: str | None = None,
) -> dict[str, Any]:
    """Persist the declared TGA unit mode in the method-context block."""
    normalized_mode = str(unit_mode or "auto").strip().lower()
    for entry in _TGA_UNIT_MODES:
        if entry["id"] == normalized_mode:
            label = unit_mode_label or entry["label"]
            break
    else:
        normalized_mode = "auto"
        label = unit_mode_label or "Auto"

    return update_method_context(
        payload,
        {
            "tga_unit_mode_declared": normalized_mode,
            "tga_unit_mode_label": label,
        },
        analysis_type="TGA",
    )


def update_tga_unit_context(payload: dict[str, Any] | None, unit_context: dict[str, Any] | None) -> dict[str, Any]:
    """Persist resolved TGA unit interpretation context additively."""
    unit_context = _copy_mapping(unit_context)
    declared = str(unit_context.get("declared_unit_mode") or "auto")
    resolved = str(unit_context.get("resolved_unit_mode") or "not_recorded")
    labels = {entry["id"]: entry["label"] for entry in _TGA_UNIT_MODES}
    return update_method_context(
        payload,
        {
            "tga_unit_mode_declared": declared,
            "tga_unit_mode_label": labels.get(declared, declared.replace("_", " ").title()),
            "tga_unit_mode_resolved": resolved,
            "tga_unit_mode_resolved_label": labels.get(resolved, resolved.replace("_", " ").title()),
            "tga_unit_auto_inference_used": bool(unit_context.get("auto_inference_used")),
            "tga_unit_inference_basis": unit_context.get("unit_inference_basis") or "not_recorded",
            "tga_unit_interpretation_status": unit_context.get("unit_interpretation_status") or "not_recorded",
            "tga_unit_review_reason": unit_context.get("unit_review_reason") or "",
            "tga_unit_reference_source": unit_context.get("unit_reference_source") or "not_recorded",
            "tga_unit_reference_value": unit_context.get("unit_reference_value"),
            "tga_signal_unit_recorded": unit_context.get("signal_unit") or "",
        },
        analysis_type="TGA",
    )
