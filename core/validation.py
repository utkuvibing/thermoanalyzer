"""Dataset validation helpers for stable thermal-analysis workflows."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from core.processing_schema import ensure_processing_payload
from core.provenance import classify_calibration_state, classify_reference_acceptance
from core.tga_processor import resolve_tga_unit_interpretation


SUPPORTED_ANALYSIS_TYPES = {"DSC", "TGA", "DTA", "UNKNOWN", "unknown"}
TEMPERATURE_MIN_C = -200.0
TEMPERATURE_MAX_C = 2000.0
TEMPERATURE_UNITS = {"°C", "degC", "K"}
SIGNAL_UNITS_BY_TYPE = {
    "DSC": {"mW", "mW/mg", "W/g"},
    "TGA": {"%", "mg"},
    "DTA": {"uV", "µV", "mV", "a.u."},
}
RECOMMENDED_METADATA_FIELDS = (
    "sample_name",
    "sample_mass",
    "heating_rate",
    "instrument",
    "vendor",
    "display_name",
)
OPTIONAL_METADATA_FIELDS = (
    "atmosphere",
    "atmosphere_status",
    "operator",
    "calibration_id",
    "calibration_status",
    "method_template_id",
    "source_data_hash",
)
ACCEPTED_ATMOSPHERE_STATUSES = {"verified", "recorded", "controlled", "current", "ok"}
BLOCKING_ATMOSPHERE_STATUSES = {"failed", "unstable", "unknown", "unverified", "invalid"}
TGA_PERCENT_MIN = -5.0
TGA_PERCENT_MAX = 120.0
_TGA_PERCENT_SIGNAL_UNITS = {"%"}
_TGA_ABSOLUTE_SIGNAL_UNITS = {"mg", "g"}
DTA_STABLE_TEMPLATE_IDS = {"dta.general", "dta.thermal_events"}
_DTA_EXPECTED_SIGN_CONVENTIONS = {
    "exotherm up / endotherm down",
    "exo_up_endo_down",
    "dta.exotherm_up",
}


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(result):
        return None
    return result


def _validation_status(*, issues: list[str], warnings: list[str]) -> str:
    if issues:
        return "fail"
    if warnings:
        return "warn"
    return "pass"


def _normalize_status_token(value: Any) -> str | None:
    if value in (None, ""):
        return None
    token = str(value).strip().lower()
    return token or None


def _processing_section(processing: dict[str, Any] | None, key: str) -> dict[str, Any]:
    processing = processing or {}
    nested = processing.get("signal_pipeline") or {}
    if key in nested and isinstance(nested[key], dict):
        return nested[key]

    nested = processing.get("analysis_steps") or {}
    if key in nested and isinstance(nested[key], dict):
        return nested[key]

    value = processing.get(key)
    return value if isinstance(value, dict) else {}


def _check_import_context(
    *,
    metadata: dict[str, Any],
    checks: dict[str, Any],
    warnings: list[str],
) -> None:
    import_confidence = metadata.get("import_confidence") or "not recorded"
    import_review_required = bool(metadata.get("import_review_required"))
    import_warnings = [str(item) for item in (metadata.get("import_warnings") or []) if item]
    checks["import_confidence"] = import_confidence
    checks["import_review_required"] = import_review_required
    checks["inferred_analysis_type"] = metadata.get("inferred_analysis_type") or "not recorded"
    checks["inferred_signal_unit"] = metadata.get("inferred_signal_unit") or "not recorded"
    checks["inferred_vendor"] = metadata.get("inferred_vendor") or "not recorded"
    checks["vendor_detection_confidence"] = metadata.get("vendor_detection_confidence") or "not recorded"

    if import_confidence == "review":
        warnings.append("Import heuristics require review before stable interpretation.")
    elif import_confidence == "medium":
        warnings.append("Import heuristics were partially inferred; verify columns, units, and analysis type.")

    for warning in import_warnings:
        warnings.append(f"Import review: {warning}")


def _check_dsc_workflow(
    *,
    metadata: dict[str, Any],
    processing: dict[str, Any] | None,
    checks: dict[str, Any],
    issues: list[str],
    warnings: list[str],
) -> None:
    calibration_context = classify_calibration_state(metadata=metadata)
    calibration_id = calibration_context["calibration_id"]
    calibration_status = calibration_context["calibration_status"]
    calibration_state = calibration_context["calibration_state"]
    checks["calibration_id"] = calibration_id or "not recorded"
    checks["calibration_status"] = calibration_status or "not recorded"
    checks["calibration_state"] = calibration_state
    checks["calibration_acceptance"] = calibration_context["calibration_acceptance"]

    if not calibration_id:
        warnings.append("Calibration identifier is not recorded for this DSC dataset.")

    calibration_token = _normalize_status_token(calibration_status)
    if calibration_token is None:
        warnings.append("Calibration status is not recorded for this DSC dataset.")
    elif calibration_state == "calibration_not_current":
        issues.append("Calibration status indicates the DSC workflow is not currently verified.")
    elif calibration_state == "unknown_calibration_state":
        warnings.append(f"Calibration status '{calibration_status}' should be reviewed before stable reporting.")

    if not processing:
        return

    checks["workflow_template_id"] = processing.get("workflow_template_id") or "not recorded"
    checks["workflow_template_label"] = processing.get("workflow_template_label") or processing.get("workflow_template") or "not recorded"

    method_context = processing.get("method_context") or {}
    sign_convention = method_context.get("sign_convention_label") or processing.get("sign_convention")
    checks["sign_convention"] = sign_convention or "not recorded"
    checks["reference_state"] = method_context.get("reference_state") or "not recorded"
    checks["reference_acceptance"] = classify_reference_acceptance(checks["reference_state"])
    checks["reference_name"] = method_context.get("reference_name") or "not recorded"
    checks["workflow_template_version"] = processing.get("workflow_template_version") or "not recorded"
    if not sign_convention:
        warnings.append("DSC sign convention is not recorded in the saved method context.")

    baseline = _processing_section(processing, "baseline")
    baseline_method = baseline.get("method")
    checks["baseline_method"] = baseline_method or "not recorded"
    if not baseline_method:
        warnings.append("Baseline method is not recorded for this DSC result.")

    glass_transition = _processing_section(processing, "glass_transition")
    peak_detection = _processing_section(processing, "peak_detection")
    checks["glass_transition_context"] = "recorded" if glass_transition else "not recorded"
    checks["peak_detection_context"] = "recorded" if peak_detection else "not recorded"
    if not glass_transition and not peak_detection:
        warnings.append("DSC method context does not record Tg or peak-analysis settings.")


def _check_tga_workflow(
    *,
    metadata: dict[str, Any],
    processing: dict[str, Any] | None,
    signal: pd.Series,
    signal_unit: str | None,
    sample_mass: float | None,
    checks: dict[str, Any],
    issues: list[str],
    warnings: list[str],
) -> None:
    signal_min = float(signal.min())
    signal_max = float(signal.max())
    checks["signal_min"] = signal_min
    checks["signal_max"] = signal_max
    method_context = (processing or {}).get("method_context") or {}
    declared_unit_mode = method_context.get("tga_unit_mode_declared") or "auto"
    unit_context = resolve_tga_unit_interpretation(
        signal.to_numpy(dtype=float),
        unit_mode=declared_unit_mode,
        signal_unit=signal_unit,
        initial_mass_mg=sample_mass,
    )
    resolved_unit_mode = str(unit_context["resolved_unit_mode"])
    checks["tga_unit_mode"] = resolved_unit_mode
    checks["tga_unit_mode_declared"] = unit_context["declared_unit_mode"]
    checks["tga_unit_mode_resolved"] = resolved_unit_mode
    checks["tga_unit_auto_inference_used"] = bool(unit_context["auto_inference_used"])
    checks["tga_unit_inference_basis"] = unit_context["unit_inference_basis"]
    checks["tga_unit_interpretation_status"] = unit_context["unit_interpretation_status"]
    checks["tga_unit_reference_source"] = unit_context["unit_reference_source"]
    checks["tga_unit_reference_value"] = unit_context["unit_reference_value"]

    if signal_unit in _TGA_PERCENT_SIGNAL_UNITS:
        if resolved_unit_mode != "percent":
            warnings.append("TGA signal unit is recorded as % but the workflow resolved the unit mode as absolute mass.")
            checks["unit_plausibility"] = "review"
        elif signal_min < TGA_PERCENT_MIN or signal_max > TGA_PERCENT_MAX:
            warnings.append("TGA signal is labeled as % but falls outside a plausible mass-percent range.")
            checks["unit_plausibility"] = "review"
        else:
            checks["unit_plausibility"] = "pass"
    elif signal_unit in _TGA_ABSOLUTE_SIGNAL_UNITS:
        if resolved_unit_mode != "absolute_mass":
            warnings.append("TGA signal unit is recorded as absolute mass but the workflow resolved the unit mode as percent.")
            checks["unit_plausibility"] = "review"
        else:
            checks["unit_plausibility"] = "pass"
        if sample_mass is None:
            warnings.append("Absolute-mass TGA data is recorded but sample mass is not recorded.")
    elif signal_unit:
        checks["unit_plausibility"] = "review"
        warnings.append(f"Signal unit '{signal_unit}' should be reviewed before stable TGA reporting.")
    else:
        if declared_unit_mode != "auto":
            if resolved_unit_mode == "percent" and (signal_min < TGA_PERCENT_MIN or signal_max > TGA_PERCENT_MAX):
                checks["unit_plausibility"] = "review"
                warnings.append("Explicit percent-mode TGA signal falls outside a plausible mass-percent range.")
            else:
                checks["unit_plausibility"] = "pass"
        else:
            checks["unit_plausibility"] = "review" if unit_context["unit_interpretation_status"] == "review" else "not_recorded"
        warnings.append("Signal unit is not recorded for this TGA dataset.")

    if unit_context["unit_interpretation_status"] == "review" and unit_context["unit_review_reason"]:
        warnings.append(str(unit_context["unit_review_reason"]))
    if resolved_unit_mode == "absolute_mass" and unit_context["unit_reference_source"] == "first_signal_value":
        warnings.append("Absolute-mass TGA was converted to percent using the first signal value as the 100% reference.")

    atmosphere = metadata.get("atmosphere")
    atmosphere_status = metadata.get("atmosphere_status")
    calibration_context = classify_calibration_state(metadata=metadata)
    calibration_id = calibration_context["calibration_id"]
    calibration_status = calibration_context["calibration_status"]
    checks["atmosphere"] = atmosphere or "not recorded"
    checks["atmosphere_status"] = atmosphere_status or "not recorded"
    checks["calibration_id"] = calibration_id or "not recorded"
    checks["calibration_status"] = calibration_status or "not recorded"
    checks["calibration_state"] = calibration_context["calibration_state"]
    checks["calibration_acceptance"] = calibration_context["calibration_acceptance"]

    if not atmosphere:
        warnings.append("Atmosphere is not recorded for this TGA dataset.")

    atmosphere_token = _normalize_status_token(atmosphere_status)
    if atmosphere_token is None:
        warnings.append("Atmosphere status is not recorded for this TGA dataset.")
    elif atmosphere_token in BLOCKING_ATMOSPHERE_STATUSES:
        issues.append("Atmosphere status indicates the TGA run conditions were not verified.")
    elif atmosphere_token not in ACCEPTED_ATMOSPHERE_STATUSES:
        warnings.append(f"Atmosphere status '{atmosphere_status}' should be reviewed before stable reporting.")

    if not processing:
        return

    checks["workflow_template_id"] = processing.get("workflow_template_id") or "not recorded"
    checks["workflow_template_label"] = processing.get("workflow_template_label") or processing.get("workflow_template") or "not recorded"
    checks["workflow_template_version"] = processing.get("workflow_template_version") or "not recorded"

    step_detection = _processing_section(processing, "step_detection")
    method_context = processing.get("method_context") or {}
    checks["step_analysis_context"] = "recorded" if step_detection else "not recorded"
    checks["step_detection_method"] = step_detection.get("method") or "not recorded"
    checks["reference_state"] = method_context.get("reference_state") or "not recorded"
    checks["reference_acceptance"] = classify_reference_acceptance(checks["reference_state"])
    checks["reference_name"] = method_context.get("reference_name") or "not recorded"
    if not step_detection:
        warnings.append("TGA method context does not record step-analysis settings.")


def _check_dta_workflow(
    *,
    metadata: dict[str, Any],
    processing: dict[str, Any] | None,
    checks: dict[str, Any],
    issues: list[str],
    warnings: list[str],
) -> None:
    if not processing:
        checks["processing_analysis_type"] = "not recorded"
        checks["workflow_template_id"] = "not recorded"
        checks["workflow_template_label"] = "not recorded"
        checks["workflow_template_version"] = "not recorded"
        checks["sign_convention"] = "not recorded"
        checks["peak_detection_context"] = "not recorded"
        checks["reference_state"] = "not recorded"
        checks["reference_acceptance"] = "review"
        checks["reference_required"] = False
        checks["calibration_state"] = "not recorded"
        checks["calibration_acceptance"] = "review"
        checks["calibration_required"] = False
        warnings.append("DTA processing context is not yet recorded; run-level checks will enforce stable template requirements.")
        return

    template_id = str(processing.get("workflow_template_id") or "").strip()
    template_label = processing.get("workflow_template_label") or processing.get("workflow_template")
    template_version = processing.get("workflow_template_version") or "not recorded"
    checks["workflow_template_id"] = template_id or "not recorded"
    checks["workflow_template_label"] = template_label or "not recorded"
    checks["workflow_template_version"] = template_version

    source_processing_type = (processing.get("source_analysis_type") or "").upper()
    processing_type = (processing.get("analysis_type") or "").upper()
    checks["processing_analysis_type"] = source_processing_type or processing_type or "not recorded"
    if source_processing_type and source_processing_type != "DTA":
        issues.append("Processing context analysis_type does not match DTA workflow.")
    elif processing_type and processing_type != "DTA":
        issues.append("Processing context analysis_type does not match DTA workflow.")

    if not template_id:
        issues.append("DTA workflow template id is required for stable validation.")
    elif template_id.lower() not in DTA_STABLE_TEMPLATE_IDS:
        issues.append(f"DTA workflow template '{template_id}' is not supported for stable reporting.")

    method_context = processing.get("method_context") or {}
    sign_convention = method_context.get("sign_convention_label") or processing.get("sign_convention")
    checks["sign_convention"] = sign_convention or "not recorded"
    sign_token = _normalize_status_token(sign_convention)
    if sign_token is None:
        warnings.append("DTA sign convention is not recorded in the saved method context.")
    elif sign_token not in _DTA_EXPECTED_SIGN_CONVENTIONS:
        issues.append("DTA sign convention does not match the expected stable method context.")

    peak_detection = _processing_section(processing, "peak_detection")
    checks["peak_detection_context"] = "recorded" if peak_detection else "not recorded"
    if not peak_detection:
        warnings.append("DTA method context does not record peak-detection settings.")

    reference_state = method_context.get("reference_state") or "not recorded"
    reference_acceptance = classify_reference_acceptance(reference_state)
    checks["reference_state"] = reference_state
    checks["reference_acceptance"] = reference_acceptance
    reference_required = bool(method_context.get("reference_required"))
    checks["reference_required"] = reference_required
    if reference_state == "not recorded":
        warnings.append("Reference-state context is not recorded for this DTA result.")
    if reference_required and reference_acceptance != "accepted":
        issues.append("DTA method context requires a verified reference state before stable reporting.")

    calibration_context = classify_calibration_state(metadata=metadata)
    checks["calibration_state"] = calibration_context["calibration_state"]
    checks["calibration_acceptance"] = calibration_context["calibration_acceptance"]
    calibration_required = bool(method_context.get("calibration_required"))
    checks["calibration_required"] = calibration_required
    if calibration_required and calibration_context["calibration_acceptance"] != "accepted":
        issues.append("DTA method context requires verified calibration before stable reporting.")


def validate_thermal_dataset(
    dataset,
    *,
    analysis_type: str | None = None,
    require_sample_mass: bool = False,
    require_heating_rate: bool = False,
    processing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a structured validation summary for a ThermalDataset-like object."""
    issues: list[str] = []
    warnings: list[str] = []
    checks: dict[str, Any] = {}

    if dataset is None:
        return {
            "status": "fail",
            "issues": ["Dataset is missing."],
            "warnings": [],
            "checks": {},
            "required_metadata": list(RECOMMENDED_METADATA_FIELDS),
            "optional_metadata": list(OPTIONAL_METADATA_FIELDS),
        }

    data = getattr(dataset, "data", None)
    metadata = getattr(dataset, "metadata", {}) or {}
    units = getattr(dataset, "units", {}) or {}
    dataset_type = getattr(dataset, "data_type", "unknown")

    checks["dataset_type"] = dataset_type

    if data is None or not isinstance(data, pd.DataFrame) or data.empty:
        issues.append("Dataset does not contain a non-empty DataFrame.")
        return {
            "status": "fail",
            "issues": issues,
            "warnings": warnings,
            "checks": checks,
            "required_metadata": list(RECOMMENDED_METADATA_FIELDS),
            "optional_metadata": list(OPTIONAL_METADATA_FIELDS),
        }

    missing_columns = [col for col in ("temperature", "signal") if col not in data.columns]
    if missing_columns:
        issues.append(f"Missing required standardized column(s): {', '.join(missing_columns)}.")
        return {
            "status": "fail",
            "issues": issues,
            "warnings": warnings,
            "checks": checks,
            "required_metadata": list(RECOMMENDED_METADATA_FIELDS),
            "optional_metadata": list(OPTIONAL_METADATA_FIELDS),
        }

    temperature = pd.to_numeric(data["temperature"], errors="coerce")
    signal = pd.to_numeric(data["signal"], errors="coerce")

    if temperature.isna().any():
        issues.append("Temperature column contains non-numeric or missing values.")
    else:
        diffs = temperature.diff().dropna()
        if (diffs <= 0).any():
            issues.append("Temperature column must be strictly increasing.")
        temp_min = float(temperature.min())
        temp_max = float(temperature.max())
        checks["temperature_min"] = temp_min
        checks["temperature_max"] = temp_max
        if temp_min < TEMPERATURE_MIN_C or temp_max > TEMPERATURE_MAX_C:
            issues.append(
                f"Temperature range {temp_min:.1f} to {temp_max:.1f} is outside the supported thermal-analysis bounds."
            )

    if signal.isna().all():
        issues.append("Signal column contains no usable numeric values.")
    elif signal.isna().any():
        warnings.append("Signal column contains missing values; affected rows were dropped during import.")
    checks["data_points"] = int(len(data))

    normalized_analysis_type = (analysis_type or dataset_type or "unknown").upper()
    if normalized_analysis_type not in SUPPORTED_ANALYSIS_TYPES:
        warnings.append(f"Dataset type '{normalized_analysis_type}' is not part of the stable workflow.")
    normalized_processing = None
    if processing:
        source_processing_type = (processing.get("analysis_type") or "").upper()
        normalized_processing = ensure_processing_payload(processing, analysis_type=normalized_analysis_type)
        if source_processing_type:
            normalized_processing["source_analysis_type"] = source_processing_type

    temperature_unit = units.get("temperature")
    if temperature_unit and temperature_unit not in TEMPERATURE_UNITS:
        warnings.append(f"Temperature unit '{temperature_unit}' is unusual; verify unit conversion before analysis.")
    checks["temperature_unit"] = temperature_unit or "unspecified"

    signal_unit = units.get("signal")
    recommended_signal_units = SIGNAL_UNITS_BY_TYPE.get(normalized_analysis_type, set())
    if signal_unit and recommended_signal_units and signal_unit not in recommended_signal_units:
        warnings.append(
            f"Signal unit '{signal_unit}' is unusual for {normalized_analysis_type}; verify instrument/export settings."
        )
    checks["signal_unit"] = signal_unit or "unspecified"

    _check_import_context(metadata=metadata, checks=checks, warnings=warnings)

    missing_metadata = [field for field in RECOMMENDED_METADATA_FIELDS if not metadata.get(field)]
    if missing_metadata:
        warnings.append(f"Recommended metadata missing: {', '.join(missing_metadata)}.")
    checks["missing_metadata"] = missing_metadata

    sample_mass = _coerce_float(metadata.get("sample_mass"))
    checks["sample_mass"] = sample_mass
    if sample_mass is None:
        if require_sample_mass:
            issues.append("Sample mass is required for this workflow.")
        else:
            warnings.append("Sample mass is not recorded; mass-normalized workflows may be limited.")
    elif sample_mass <= 0:
        issues.append("Sample mass must be positive.")

    heating_rate = _coerce_float(metadata.get("heating_rate"))
    checks["heating_rate"] = heating_rate
    if heating_rate is None:
        if require_heating_rate:
            issues.append("Heating rate is required for this workflow.")
        else:
            warnings.append("Heating rate is not recorded; kinetic and comparison workflows may be limited.")
    elif heating_rate <= 0:
        issues.append("Heating rate must be positive.")

    if normalized_analysis_type == "DSC":
        _check_dsc_workflow(
            metadata=metadata,
            processing=normalized_processing,
            checks=checks,
            issues=issues,
            warnings=warnings,
        )
    elif normalized_analysis_type == "TGA":
        _check_tga_workflow(
            metadata=metadata,
            processing=normalized_processing,
            signal=signal,
            signal_unit=signal_unit,
            sample_mass=sample_mass,
            checks=checks,
            issues=issues,
            warnings=warnings,
        )
    elif normalized_analysis_type == "DTA":
        _check_dta_workflow(
            metadata=metadata,
            processing=normalized_processing,
            checks=checks,
            issues=issues,
            warnings=warnings,
        )

    return {
        "status": _validation_status(issues=issues, warnings=warnings),
        "issues": issues,
        "warnings": warnings,
        "checks": checks,
        "required_metadata": list(RECOMMENDED_METADATA_FIELDS),
        "optional_metadata": list(OPTIONAL_METADATA_FIELDS),
    }
