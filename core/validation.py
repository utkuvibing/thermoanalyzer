"""Dataset validation helpers for stable thermal-analysis workflows."""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd

from core.processing_schema import ensure_processing_payload
from core.provenance import classify_calibration_state, classify_reference_acceptance
from core.reference_library import get_reference_library_manager
from core.tga_processor import resolve_tga_unit_interpretation


SUPPORTED_ANALYSIS_TYPES = {"DSC", "TGA", "DTA", "FTIR", "RAMAN", "XRD", "UNKNOWN", "unknown"}
_THERMAL_ANALYSIS_TYPES = {"DSC", "TGA", "DTA"}
_SPECTRAL_ANALYSIS_TYPES = {"FTIR", "RAMAN"}
TEMPERATURE_MIN_C = -200.0
TEMPERATURE_MAX_C = 2000.0
TEMPERATURE_UNITS = {"°C", "degC", "K"}
XRD_AXIS_UNITS = {"degree_2theta", "deg", "2theta", "angstrom", "1/angstrom"}
SIGNAL_UNITS_BY_TYPE = {
    "DSC": {"mW", "mW/mg", "W/g"},
    "TGA": {"%", "mg"},
    "DTA": {"uV", "µV", "mV", "a.u."},
    "FTIR": {"a.u.", "absorbance", "%T", "transmittance"},
    "RAMAN": {"counts", "cps", "a.u.", "intensity"},
    "XRD": {"counts", "cps", "a.u.", "intensity"},
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
_SPECTRAL_TEMPLATE_IDS = {
    "FTIR": {"ftir.general", "ftir.functional_groups"},
    "RAMAN": {"raman.general", "raman.polymorph_screening"},
}
_SPECTRAL_METRICS = {"cosine", "pearson", "cosine_prerank_then_pearson_peak_overlap"}
_XRD_TEMPLATE_IDS = {"xrd.general", "xrd.phase_screening"}
_XRD_MATCH_STATUSES = {"matched", "no_match", "not_run"}
_XRD_CONFIDENCE_BANDS = {"high", "medium", "low", "no_match", "not_run"}
_XRD_REQUIRED_EVIDENCE_FIELDS = (
    "shared_peak_count",
    "weighted_overlap_score",
    "mean_delta_position",
    "unmatched_major_peak_count",
    "tolerance_deg",
)


def _global_reference_candidate_count(analysis_type: str) -> int:
    try:
        return int(get_reference_library_manager().count_installed_candidates(analysis_type))
    except Exception:
        return 0


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


def _check_dataset_axis(
    *,
    temperature: pd.Series,
    analysis_type: str,
    checks: dict[str, Any],
    issues: list[str],
) -> None:
    if temperature.isna().any():
        if analysis_type in _SPECTRAL_ANALYSIS_TYPES or analysis_type == "XRD":
            issues.append("Axis column contains non-numeric or missing values.")
        else:
            issues.append("Temperature column contains non-numeric or missing values.")
        return

    diffs = temperature.diff().dropna()
    axis_min = float(temperature.min())
    axis_max = float(temperature.max())
    checks["temperature_min"] = axis_min
    checks["temperature_max"] = axis_max

    increasing = bool(not diffs.empty and (diffs > 0).all())
    decreasing = bool(not diffs.empty and (diffs < 0).all())
    if diffs.empty:
        checks["axis_direction"] = "single_point"
        return

    if analysis_type in _SPECTRAL_ANALYSIS_TYPES:
        checks["axis_direction"] = "increasing" if increasing else "decreasing" if decreasing else "mixed"
        if not increasing and not decreasing:
            issues.append(f"{analysis_type} spectral axis must be strictly monotonic.")
        return

    checks["axis_direction"] = "increasing" if increasing else "mixed"
    if not increasing:
        if analysis_type == "XRD":
            issues.append("XRD axis must be strictly increasing.")
        else:
            issues.append("Temperature column must be strictly increasing.")

    if analysis_type in _THERMAL_ANALYSIS_TYPES or analysis_type in {"UNKNOWN", "unknown"}:
        if axis_min < TEMPERATURE_MIN_C or axis_max > TEMPERATURE_MAX_C:
            issues.append(
                f"Temperature range {axis_min:.1f} to {axis_max:.1f} is outside the supported thermal-analysis bounds."
            )


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


def _check_spectral_workflow(
    *,
    analysis_type: str,
    metadata: dict[str, Any],
    processing: dict[str, Any] | None,
    checks: dict[str, Any],
    issues: list[str],
    warnings: list[str],
) -> None:
    if not processing:
        checks["workflow_template_id"] = "not recorded"
        checks["workflow_template_label"] = "not recorded"
        checks["workflow_template_version"] = "not recorded"
        checks["normalization_context"] = "not recorded"
        checks["peak_detection_context"] = "not recorded"
        checks["similarity_matching_context"] = "not recorded"
        checks["reference_candidate_count"] = 0
        checks["caution_state"] = "processing_context_missing"
        issues.append(f"{analysis_type} processing context is required for stable spectral reporting.")
        return

    template_id = str(processing.get("workflow_template_id") or "").strip().lower()
    checks["workflow_template_id"] = template_id or "not recorded"
    checks["workflow_template_label"] = processing.get("workflow_template_label") or processing.get("workflow_template") or "not recorded"
    checks["workflow_template_version"] = processing.get("workflow_template_version") or "not recorded"
    if not template_id:
        issues.append(f"{analysis_type} workflow template id is required for stable reporting.")
    elif template_id not in _SPECTRAL_TEMPLATE_IDS.get(analysis_type, set()):
        issues.append(f"{analysis_type} workflow template '{template_id}' is not supported for stable reporting.")

    normalization = _processing_section(processing, "normalization")
    peak_detection = _processing_section(processing, "peak_detection")
    similarity_matching = _processing_section(processing, "similarity_matching")
    checks["normalization_context"] = "recorded" if normalization else "not recorded"
    checks["peak_detection_context"] = "recorded" if peak_detection else "not recorded"
    checks["similarity_matching_context"] = "recorded" if similarity_matching else "not recorded"
    if not normalization:
        warnings.append(f"{analysis_type} normalization settings are not recorded; similarity confidence may be unstable.")
    if not peak_detection:
        warnings.append(f"{analysis_type} peak-detection settings are not recorded; evidence traceability is reduced.")
    if not similarity_matching:
        issues.append(f"{analysis_type} similarity-matching settings are required for stable ranked output.")
        return

    metric = str(similarity_matching.get("metric") or "").strip().lower()
    checks["matching_metric"] = metric or "not recorded"
    if not metric:
        warnings.append(f"{analysis_type} similarity metric is not recorded.")
    elif metric not in _SPECTRAL_METRICS:
        issues.append(f"{analysis_type} similarity metric '{metric}' is not supported.")

    top_n = similarity_matching.get("top_n")
    checks["matching_top_n"] = top_n if top_n not in (None, "") else "not recorded"
    if top_n not in (None, ""):
        try:
            if int(top_n) < 1:
                issues.append(f"{analysis_type} similarity top_n must be at least 1.")
        except (TypeError, ValueError):
            issues.append(f"{analysis_type} similarity top_n must be numeric.")

    minimum_score = similarity_matching.get("minimum_score")
    checks["matching_minimum_score"] = minimum_score if minimum_score not in (None, "") else "not recorded"
    if minimum_score not in (None, ""):
        try:
            token = float(minimum_score)
        except (TypeError, ValueError):
            issues.append(f"{analysis_type} similarity minimum_score must be numeric.")
        else:
            if token < 0.0 or token > 1.0:
                issues.append(f"{analysis_type} similarity minimum_score must be within [0, 1].")

    method_context = processing.get("method_context") or {}
    checks["library_sync_mode"] = method_context.get("library_sync_mode") or "not recorded"
    checks["library_cache_status"] = method_context.get("library_cache_status") or "not recorded"
    reference_candidate_count = method_context.get("reference_candidate_count")
    if reference_candidate_count in (None, ""):
        reference_candidate_count = len(metadata.get("spectral_reference_library") or []) + _global_reference_candidate_count(
            analysis_type
        )
    try:
        reference_candidate_count = int(reference_candidate_count or 0)
    except (TypeError, ValueError):
        reference_candidate_count = 0
    checks["reference_candidate_count"] = reference_candidate_count

    if reference_candidate_count <= 0:
        checks["caution_state"] = "reference_library_missing"
        warnings.append(
            f"{analysis_type} reference library is empty; no-match outcomes should be treated as cautionary rather than conclusive."
        )
    else:
        checks["caution_state"] = "reference_library_available"


def _check_xrd_workflow(
    *,
    metadata: dict[str, Any],
    processing: dict[str, Any] | None,
    checks: dict[str, Any],
    issues: list[str],
    warnings: list[str],
) -> None:
    if not processing:
        checks["workflow_template_id"] = "not recorded"
        checks["workflow_template_label"] = "not recorded"
        checks["workflow_template_version"] = "not recorded"
        checks["axis_normalization_context"] = "not recorded"
        checks["smoothing_context"] = "not recorded"
        checks["baseline_context"] = "not recorded"
        checks["peak_detection_context"] = "not recorded"
        checks["xrd_processing_context_status"] = "missing"
        issues.append("XRD processing context is required for stable reporting.")
        return

    template_id = str(processing.get("workflow_template_id") or "").strip().lower()
    checks["workflow_template_id"] = template_id or "not recorded"
    checks["workflow_template_label"] = processing.get("workflow_template_label") or processing.get("workflow_template") or "not recorded"
    checks["workflow_template_version"] = processing.get("workflow_template_version") or "not recorded"
    if not template_id:
        issues.append("XRD workflow template id is required for stable reporting.")
    elif template_id not in _XRD_TEMPLATE_IDS:
        issues.append(f"XRD workflow template '{template_id}' is not supported for stable reporting.")

    axis_normalization = _processing_section(processing, "axis_normalization")
    smoothing = _processing_section(processing, "smoothing")
    baseline = _processing_section(processing, "baseline")
    peak_detection = _processing_section(processing, "peak_detection")
    checks["axis_normalization_context"] = "recorded" if axis_normalization else "not recorded"
    checks["smoothing_context"] = "recorded" if smoothing else "not recorded"
    checks["baseline_context"] = "recorded" if baseline else "not recorded"
    checks["peak_detection_context"] = "recorded" if peak_detection else "not recorded"
    checks["xrd_processing_context_status"] = "recorded" if peak_detection else "peak_detection_missing"
    if not axis_normalization:
        warnings.append("XRD axis-normalization settings are not recorded; preprocessing traceability is reduced.")
    if not smoothing:
        warnings.append("XRD smoothing settings are not recorded; peak reproducibility may be unstable.")
    if not baseline:
        warnings.append("XRD baseline/background settings are not recorded; corrected intensities may not be reproducible.")
    if not peak_detection:
        issues.append("XRD peak-detection settings are required for stable reporting.")
        return

    peak_controls = {
        "prominence": peak_detection.get("prominence"),
        "distance": peak_detection.get("distance"),
        "width": peak_detection.get("width"),
        "max_peaks": peak_detection.get("max_peaks"),
    }
    checks["xrd_peak_prominence"] = peak_controls["prominence"] if peak_controls["prominence"] not in (None, "") else "not recorded"
    checks["xrd_peak_distance"] = peak_controls["distance"] if peak_controls["distance"] not in (None, "") else "not recorded"
    checks["xrd_peak_width"] = peak_controls["width"] if peak_controls["width"] not in (None, "") else "not recorded"
    checks["xrd_peak_max_peaks"] = peak_controls["max_peaks"] if peak_controls["max_peaks"] not in (None, "") else "not recorded"

    for key in ("prominence", "distance", "width"):
        value = peak_controls[key]
        if value in (None, ""):
            issues.append(f"XRD peak-detection '{key}' is required for stable reporting.")
            continue
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            issues.append(f"XRD peak-detection '{key}' must be numeric.")
            continue
        if parsed <= 0.0:
            issues.append(f"XRD peak-detection '{key}' must be greater than zero.")

    max_peaks = peak_controls["max_peaks"]
    if max_peaks not in (None, ""):
        try:
            if int(max_peaks) < 1:
                issues.append("XRD peak-detection 'max_peaks' must be at least 1.")
        except (TypeError, ValueError):
            issues.append("XRD peak-detection 'max_peaks' must be numeric.")

    method_context = processing.get("method_context") or {}
    axis_role = method_context.get("xrd_axis_role") or metadata.get("xrd_axis_role")
    axis_unit = method_context.get("xrd_axis_unit") or metadata.get("xrd_axis_unit")
    wavelength = method_context.get("xrd_wavelength_angstrom")
    if wavelength in (None, ""):
        wavelength = metadata.get("xrd_wavelength_angstrom")
    axis_mapping_review_required = bool(
        method_context.get("xrd_axis_mapping_review_required")
        if method_context.get("xrd_axis_mapping_review_required") is not None
        else metadata.get("xrd_axis_mapping_review_required")
    )
    stable_matching_blocked = bool(
        method_context.get("xrd_stable_matching_blocked")
        if method_context.get("xrd_stable_matching_blocked") is not None
        else metadata.get("xrd_stable_matching_blocked")
    )
    provenance_state = str(
        method_context.get("xrd_provenance_state")
        or metadata.get("xrd_provenance_state")
        or ("complete" if wavelength not in (None, "") else "incomplete")
    ).strip()
    provenance_warning = str(
        method_context.get("xrd_provenance_warning")
        or metadata.get("xrd_provenance_warning")
        or ""
    ).strip()
    peak_count = method_context.get("xrd_peak_count")
    match_metric = str(method_context.get("xrd_match_metric") or "").strip().lower()
    match_tolerance = method_context.get("xrd_match_tolerance_deg")
    match_top_n = method_context.get("xrd_match_top_n")
    match_minimum_score = method_context.get("xrd_match_minimum_score")
    reference_candidate_count = method_context.get("xrd_reference_candidate_count")
    coverage_tier = str(method_context.get("xrd_coverage_tier") or "").strip()
    coverage_warning = str(method_context.get("xrd_coverage_warning_message") or "").strip()
    provider_candidate_counts = method_context.get("xrd_provider_candidate_counts") or {}
    checks["xrd_axis_role"] = axis_role or "not recorded"
    checks["xrd_axis_unit"] = axis_unit or "not recorded"
    checks["xrd_wavelength_angstrom"] = wavelength if wavelength not in (None, "") else "not recorded"
    checks["xrd_axis_mapping_review_required"] = axis_mapping_review_required
    checks["xrd_stable_matching_blocked"] = stable_matching_blocked
    checks["xrd_provenance_state"] = provenance_state or "not recorded"
    checks["xrd_provenance_warning"] = provenance_warning or "not recorded"
    checks["xrd_peak_count"] = peak_count if peak_count not in (None, "") else "not recorded"
    checks["xrd_match_metric"] = match_metric or "not recorded"
    checks["xrd_match_tolerance_deg"] = match_tolerance if match_tolerance not in (None, "") else "not recorded"
    checks["xrd_match_top_n"] = match_top_n if match_top_n not in (None, "") else "not recorded"
    checks["xrd_match_minimum_score"] = (
        match_minimum_score if match_minimum_score not in (None, "") else "not recorded"
    )
    checks["library_sync_mode"] = method_context.get("library_sync_mode") or "not recorded"
    checks["library_cache_status"] = method_context.get("library_cache_status") or "not recorded"
    checks["xrd_coverage_tier"] = coverage_tier or "not recorded"
    checks["xrd_provider_candidate_counts"] = provider_candidate_counts or {}
    checks["xrd_reference_candidate_count"] = (
        reference_candidate_count if reference_candidate_count not in (None, "") else "not recorded"
    )
    if axis_mapping_review_required or stable_matching_blocked:
        issues.append(
            "XRD axis mapping requires explicit 2theta/angle confirmation before stable qualitative matching."
        )
    if not axis_role:
        warnings.append("XRD axis role is not recorded in processing context.")
    if not axis_unit:
        warnings.append("XRD axis unit is not recorded in processing context.")
    if wavelength in (None, ""):
        warnings.append(
            "XRD wavelength is not recorded; set xrd_wavelength_angstrom for deterministic qualitative matching provenance."
        )
    if provenance_state.lower() != "complete" and provenance_warning:
        warnings.append(provenance_warning)
    if coverage_tier == "seed_dev":
        warnings.append(
            coverage_warning
            or "XRD hosted coverage is still seed/dev sized; no-match outcomes may reflect insufficient corpus depth."
        )
    if peak_count not in (None, ""):
        try:
            if int(peak_count) <= 0:
                warnings.append("XRD peak extraction detected no peaks; review preprocessing controls before interpretation.")
        except (TypeError, ValueError):
            warnings.append("XRD peak-count context is not numeric; review processing metadata.")

    if not match_metric:
        issues.append("XRD matching metric context is required for stable reporting.")
    if match_tolerance in (None, ""):
        issues.append("XRD matching tolerance context is required for stable reporting.")
    else:
        parsed_tolerance = _coerce_float(match_tolerance)
        if parsed_tolerance is None or parsed_tolerance <= 0.0:
            issues.append("XRD matching tolerance must be numeric and greater than zero.")

    if match_top_n in (None, ""):
        issues.append("XRD matching top_n context is required for stable reporting.")
    else:
        try:
            if int(match_top_n) < 1:
                issues.append("XRD matching top_n must be at least 1.")
        except (TypeError, ValueError):
            issues.append("XRD matching top_n must be numeric.")

    if match_minimum_score in (None, ""):
        issues.append("XRD matching minimum_score context is required for stable reporting.")
    else:
        parsed_minimum = _coerce_float(match_minimum_score)
        if parsed_minimum is None:
            issues.append("XRD matching minimum_score must be numeric.")
        elif parsed_minimum < 0.0 or parsed_minimum > 1.0:
            issues.append("XRD matching minimum_score must be within [0, 1].")

    if reference_candidate_count in (None, ""):
        reference_count = (
            len(metadata.get("xrd_reference_library") or metadata.get("reference_library") or [])
            + _global_reference_candidate_count("XRD")
        )
    else:
        try:
            reference_count = int(reference_candidate_count)
        except (TypeError, ValueError):
            reference_count = 0
            warnings.append("XRD reference-candidate count is not numeric; verify matching context.")
    checks["xrd_reference_candidate_count"] = reference_count
    if reference_count <= 0:
        warnings.append(
            "XRD reference library is empty; no-match outcomes should be treated as cautionary rather than conclusive."
        )


def enrich_spectral_result_validation(
    validation: dict[str, Any] | None,
    *,
    analysis_type: str,
    summary: Mapping[str, Any] | None,
    rows: list[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Attach FTIR/Raman result-level caution semantics to a validation payload."""
    normalized_type = str(analysis_type or "").upper()
    payload = dict(validation or {})
    issues = [str(item) for item in (payload.get("issues") or []) if item]
    warnings = [str(item) for item in (payload.get("warnings") or []) if item]
    checks = dict(payload.get("checks") or {})
    summary = dict(summary or {})
    rows = [dict(item) for item in (rows or []) if isinstance(item, Mapping)]

    match_status = str(summary.get("match_status") or "").strip().lower() or "not_recorded"
    confidence_band = str(summary.get("confidence_band") or "").strip().lower() or "not_recorded"
    caution_code = str(summary.get("caution_code") or "").strip()
    top_match_id = summary.get("top_match_id")
    top_match_score = summary.get("top_match_score")

    checks["match_status"] = match_status
    checks["confidence_band"] = confidence_band
    checks["top_match_id"] = top_match_id if top_match_id not in (None, "") else "not_recorded"
    checks["candidate_count"] = summary.get("candidate_count", len(rows))
    checks["top_match_score"] = top_match_score if top_match_score not in (None, "") else "not_recorded"
    checks["caution_code"] = caution_code or "not_recorded"

    if match_status == "matched":
        checks["caution_state_output"] = "clear"
        if top_match_id in (None, ""):
            issues.append(f"{normalized_type} matched outputs must include top_match_id.")
        if confidence_band in {"no_match", "not_recorded"}:
            issues.append(f"{normalized_type} matched outputs must include a confidence band.")
    elif match_status == "no_match":
        checks["caution_state_output"] = "no_match"
        message = (
            f"{normalized_type} produced no confident library match; treat this as a cautionary outcome."
        )
        if message not in warnings:
            warnings.append(message)
        if not caution_code:
            warnings.append(f"{normalized_type} no-match output is missing caution_code metadata.")
    else:
        checks["caution_state_output"] = "review"
        warnings.append(f"{normalized_type} match_status is not recorded; report caution semantics may be incomplete.")

    if confidence_band == "low" and match_status == "matched":
        checks["caution_state_output"] = "low_confidence"
        message = (
            f"{normalized_type} top match is low confidence; review evidence before interpretation."
        )
        if message not in warnings:
            warnings.append(message)
        if not caution_code:
            warnings.append(f"{normalized_type} low-confidence output is missing caution_code metadata.")

    if top_match_score not in (None, ""):
        try:
            score = float(top_match_score)
        except (TypeError, ValueError):
            issues.append(f"{normalized_type} top_match_score must be numeric.")
        else:
            if score < 0.0 or score > 1.0:
                issues.append(f"{normalized_type} top_match_score must be within [0, 1].")

    top_row = rows[0] if rows else {}
    evidence = top_row.get("evidence") if isinstance(top_row, dict) else None
    if match_status == "matched":
        if not isinstance(evidence, Mapping) or not evidence:
            warnings.append(f"{normalized_type} matched output is missing evidence payload for the top candidate.")
            checks["top_match_evidence"] = "missing"
        else:
            checks["top_match_evidence"] = "recorded"
            shared_peak_count = evidence.get("shared_peak_count")
            checks["top_match_shared_peak_count"] = (
                shared_peak_count if shared_peak_count not in (None, "") else "not_recorded"
            )
    else:
        checks["top_match_evidence"] = "not_required"

    dedup_warnings: list[str] = []
    for item in warnings:
        if item not in dedup_warnings:
            dedup_warnings.append(item)

    payload["checks"] = checks
    payload["issues"] = issues
    payload["warnings"] = dedup_warnings
    payload["status"] = _validation_status(issues=issues, warnings=dedup_warnings)
    return payload


def enrich_xrd_result_validation(
    validation: dict[str, Any] | None,
    *,
    summary: Mapping[str, Any] | None,
    rows: list[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Attach XRD result-level candidate schema and caution semantics to a validation payload."""
    payload = dict(validation or {})
    issues = [str(item) for item in (payload.get("issues") or []) if item]
    warnings = [str(item) for item in (payload.get("warnings") or []) if item]
    checks = dict(payload.get("checks") or {})
    summary = dict(summary or {})
    rows = [dict(item) for item in (rows or []) if isinstance(item, Mapping)]

    match_status = str(summary.get("match_status") or "").strip().lower() or "not_recorded"
    confidence_band = str(summary.get("confidence_band") or "").strip().lower() or "not_recorded"
    top_phase_id = summary.get("top_phase_id")
    if top_phase_id in (None, ""):
        top_phase_id = summary.get("top_match_id")
    top_phase_score = summary.get("top_phase_score")
    if top_phase_score in (None, ""):
        top_phase_score = summary.get("top_match_score")
    caution_code = str(summary.get("caution_code") or "").strip()
    candidate_count = summary.get("candidate_count", len(rows))
    try:
        candidate_count = int(candidate_count)
    except (TypeError, ValueError):
        issues.append("XRD candidate_count must be numeric.")
        candidate_count = len(rows)

    checks["match_status"] = match_status
    checks["confidence_band"] = confidence_band
    checks["candidate_count"] = candidate_count
    checks["top_phase_id"] = top_phase_id if top_phase_id not in (None, "") else "not_recorded"
    checks["top_phase_score"] = top_phase_score if top_phase_score not in (None, "") else "not_recorded"
    checks["caution_code"] = caution_code or "not_recorded"
    checks["xrd_coverage_tier"] = summary.get("xrd_coverage_tier") or "not_recorded"
    checks["xrd_provider_candidate_counts"] = summary.get("xrd_provider_candidate_counts") or {}
    checks["xrd_provenance_state"] = summary.get("xrd_provenance_state") or "not_recorded"

    if match_status not in _XRD_MATCH_STATUSES:
        issues.append("XRD match_status must be one of 'matched', 'no_match', or 'not_run'.")
        checks["caution_state_output"] = "invalid"
    elif match_status == "matched":
        checks["caution_state_output"] = "clear"
        if top_phase_id in (None, ""):
            issues.append("XRD matched outputs must include top_phase_id.")
        if confidence_band not in {"high", "medium", "low"}:
            issues.append("XRD matched outputs must include confidence_band high/medium/low.")
    elif match_status == "no_match":
        checks["caution_state_output"] = "no_match"
        if confidence_band != "no_match":
            issues.append("XRD no_match outputs must use confidence_band='no_match'.")
        message = "XRD produced no confident phase candidate; treat this as a cautionary stable outcome."
        if message not in warnings:
            warnings.append(message)
        if not caution_code:
            warnings.append("XRD no-match output is missing caution_code metadata.")
    else:
        checks["caution_state_output"] = "not_run"
        if confidence_band != "not_run":
            issues.append("XRD not_run outputs must use confidence_band='not_run'.")
        message = "XRD phase matching was not run because no reference library candidates were available."
        if message not in warnings:
            warnings.append(message)

    if confidence_band not in _XRD_CONFIDENCE_BANDS:
        issues.append("XRD confidence_band must be one of high/medium/low/no_match/not_run.")

    if confidence_band == "low" and match_status == "matched":
        checks["caution_state_output"] = "low_confidence"
        warnings.append("XRD top candidate is low confidence; review evidence before interpretation.")
        if not caution_code:
            warnings.append("XRD low-confidence output is missing caution_code metadata.")

    coverage_tier = str(summary.get("xrd_coverage_tier") or "").strip().lower()
    if coverage_tier == "seed_dev":
        warnings.append(
            str(summary.get("xrd_coverage_warning_message") or "").strip()
            or "XRD hosted coverage is still seed/dev sized; no-match outcomes may reflect insufficient corpus depth."
        )
    provenance_state = str(summary.get("xrd_provenance_state") or "").strip().lower()
    if provenance_state == "incomplete":
        warnings.append(
            str(summary.get("xrd_provenance_warning") or "").strip()
            or "XRD wavelength is not recorded; qualitative phase matching provenance remains incomplete."
        )

    if top_phase_score not in (None, ""):
        parsed_score = _coerce_float(top_phase_score)
        if parsed_score is None:
            issues.append("XRD top_phase_score must be numeric.")
        elif parsed_score < 0.0 or parsed_score > 1.0:
            issues.append("XRD top_phase_score must be within [0, 1].")

    if candidate_count != len(rows):
        warnings.append("XRD candidate_count does not match row count; verify serialization consistency.")

    if match_status == "matched" and not rows:
        issues.append("XRD matched outputs must include at least one candidate row.")

    for index, row in enumerate(rows, start=1):
        row_confidence = str(row.get("confidence_band") or "").strip().lower() or "not_recorded"
        if row_confidence not in _XRD_CONFIDENCE_BANDS:
            issues.append(f"XRD candidate row {index} has invalid confidence_band.")
        evidence = row.get("evidence")
        if not isinstance(evidence, Mapping):
            issues.append(f"XRD candidate row {index} must include evidence payload.")
            continue
        for field in _XRD_REQUIRED_EVIDENCE_FIELDS:
            if field not in evidence:
                issues.append(f"XRD candidate row {index} evidence is missing '{field}'.")
        shared_peak_count = evidence.get("shared_peak_count")
        if shared_peak_count not in (None, ""):
            try:
                if int(shared_peak_count) < 0:
                    issues.append(f"XRD candidate row {index} shared_peak_count must be >= 0.")
            except (TypeError, ValueError):
                issues.append(f"XRD candidate row {index} shared_peak_count must be numeric.")

        overlap_score = evidence.get("weighted_overlap_score")
        if overlap_score not in (None, ""):
            parsed_overlap = _coerce_float(overlap_score)
            if parsed_overlap is None:
                issues.append(f"XRD candidate row {index} weighted_overlap_score must be numeric.")
            elif parsed_overlap < 0.0 or parsed_overlap > 1.0:
                issues.append(f"XRD candidate row {index} weighted_overlap_score must be within [0, 1].")

        mean_delta = evidence.get("mean_delta_position")
        if mean_delta not in (None, "") and _coerce_float(mean_delta) is None:
            issues.append(f"XRD candidate row {index} mean_delta_position must be numeric or null.")

        unmatched_major = evidence.get("unmatched_major_peak_count")
        if unmatched_major not in (None, ""):
            try:
                if int(unmatched_major) < 0:
                    issues.append(f"XRD candidate row {index} unmatched_major_peak_count must be >= 0.")
            except (TypeError, ValueError):
                issues.append(f"XRD candidate row {index} unmatched_major_peak_count must be numeric.")

        tolerance = evidence.get("tolerance_deg")
        parsed_tolerance = _coerce_float(tolerance)
        if parsed_tolerance is None or parsed_tolerance <= 0.0:
            issues.append(f"XRD candidate row {index} tolerance_deg must be numeric and > 0.")

    dedup_warnings: list[str] = []
    for item in warnings:
        if item not in dedup_warnings:
            dedup_warnings.append(item)

    payload["checks"] = checks
    payload["issues"] = issues
    payload["warnings"] = dedup_warnings
    payload["status"] = _validation_status(issues=issues, warnings=dedup_warnings)
    return payload


def validate_thermal_dataset(
    dataset,
    *,
    analysis_type: str | None = None,
    require_sample_mass: bool = False,
    require_heating_rate: bool = False,
    processing: dict[str, Any] | None = None,
    enforce_workflow_context: bool = True,
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
    normalized_analysis_type = (analysis_type or dataset_type or "unknown").upper()

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
    _check_dataset_axis(
        temperature=temperature,
        analysis_type=normalized_analysis_type,
        checks=checks,
        issues=issues,
    )

    if signal.isna().all():
        issues.append("Signal column contains no usable numeric values.")
    elif signal.isna().any():
        warnings.append("Signal column contains missing values; affected rows were dropped during import.")
    checks["data_points"] = int(len(data))

    if normalized_analysis_type not in SUPPORTED_ANALYSIS_TYPES:
        warnings.append(f"Dataset type '{normalized_analysis_type}' is not part of the stable workflow.")
    normalized_processing = None
    if processing:
        source_processing_type = (processing.get("analysis_type") or "").upper()
        normalized_processing = ensure_processing_payload(processing, analysis_type=normalized_analysis_type)
        if source_processing_type:
            normalized_processing["source_analysis_type"] = source_processing_type

    temperature_unit = units.get("temperature")
    if normalized_analysis_type == "XRD":
        if temperature_unit and str(temperature_unit) not in XRD_AXIS_UNITS:
            warnings.append(f"XRD axis unit '{temperature_unit}' is unusual; verify axis normalization before analysis.")
    elif temperature_unit and temperature_unit not in TEMPERATURE_UNITS:
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
        elif normalized_analysis_type in _THERMAL_ANALYSIS_TYPES:
            warnings.append("Sample mass is not recorded; mass-normalized workflows may be limited.")
    elif sample_mass <= 0:
        issues.append("Sample mass must be positive.")

    heating_rate = _coerce_float(metadata.get("heating_rate"))
    checks["heating_rate"] = heating_rate
    if heating_rate is None:
        if require_heating_rate:
            issues.append("Heating rate is required for this workflow.")
        elif normalized_analysis_type in _THERMAL_ANALYSIS_TYPES:
            warnings.append("Heating rate is not recorded; kinetic and comparison workflows may be limited.")
    elif heating_rate <= 0:
        issues.append("Heating rate must be positive.")

    if not enforce_workflow_context:
        return {
            "status": _validation_status(issues=issues, warnings=warnings),
            "issues": issues,
            "warnings": warnings,
            "checks": checks,
            "required_metadata": list(RECOMMENDED_METADATA_FIELDS),
            "optional_metadata": list(OPTIONAL_METADATA_FIELDS),
        }

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
    elif normalized_analysis_type in _SPECTRAL_ANALYSIS_TYPES:
        _check_spectral_workflow(
            analysis_type=normalized_analysis_type,
            metadata=metadata,
            processing=normalized_processing,
            checks=checks,
            issues=issues,
            warnings=warnings,
        )
    elif normalized_analysis_type == "XRD":
        _check_xrd_workflow(
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
