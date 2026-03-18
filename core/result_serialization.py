"""Serializable result helpers for ThermoAnalyzer analysis outputs."""

from __future__ import annotations

import copy
import json
import math
from typing import Any, Iterable, Mapping

from core.dsc_processor import GlassTransition
from core.literature_models import (
    normalize_citations,
    normalize_literature_claims,
    normalize_literature_comparisons,
    normalize_literature_context,
)
from core.peak_analysis import ThermalPeak
from core.xrd_reference_dossier import (
    XRD_REFERENCE_DOSSIER_LIMIT,
    XRD_REFERENCE_PEAK_DISPLAY_LIMIT,
    build_xrd_reference_bundle,
    build_xrd_reference_dossiers,
)
from core.scientific_reasoning import build_scientific_reasoning
from core.scientific_sections import (
    build_equation,
    build_fit_quality,
    build_interpretation,
    build_limitations,
    build_scientific_context,
    normalize_scientific_context,
)
from core.tga_processor import MassLossStep, TGAResult
from core.xrd_display import (
    xrd_candidate_display_name,
    xrd_candidate_display_payload,
    xrd_candidate_display_variants,
)


REQUIRED_RESULT_KEYS = {
    "id",
    "analysis_type",
    "status",
    "dataset_key",
    "metadata",
    "summary",
    "rows",
    "artifacts",
}
OPTIONAL_RESULT_KEYS = {
    "processing",
    "provenance",
    "validation",
    "review",
    "scientific_context",
    "report_payload",
    "literature_context",
}
OPTIONAL_RESULT_LIST_KEYS = {
    "literature_claims",
    "literature_comparisons",
    "citations",
}

VALID_STATUSES = {"stable", "experimental"}


def _clean_scalar(value: Any) -> Any:
    """Convert numpy-like scalars and non-finite floats to JSON-safe values."""
    if hasattr(value, "item") and callable(value.item):
        try:
            value = value.item()
        except Exception:
            pass
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _normalize_xrd_report_payload(record: Mapping[str, Any]) -> dict[str, Any]:
    report_payload = copy.deepcopy(record.get("report_payload") or {})
    if str(record.get("analysis_type") or "").upper() != "XRD":
        return report_payload

    rows = [dict(item) for item in (record.get("rows") or []) if isinstance(item, Mapping)]
    summary = dict(record.get("summary") or {})
    report_payload["xrd_reference_dossier_limit"] = XRD_REFERENCE_DOSSIER_LIMIT
    report_payload["xrd_reference_peak_display_limit"] = XRD_REFERENCE_PEAK_DISPLAY_LIMIT
    report_payload["xrd_reference_dossiers"] = build_xrd_reference_dossiers(
        summary,
        rows,
        dossier_limit=XRD_REFERENCE_DOSSIER_LIMIT,
        peak_display_limit=XRD_REFERENCE_PEAK_DISPLAY_LIMIT,
    )
    return report_payload


def make_result_record(
    *,
    result_id: str,
    analysis_type: str,
    status: str,
    dataset_key: str | None,
    metadata: dict[str, Any] | None = None,
    summary: dict[str, Any] | None = None,
    rows: list[dict[str, Any]] | None = None,
    artifacts: dict[str, Any] | None = None,
    processing: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
    review: dict[str, Any] | None = None,
    scientific_context: dict[str, Any] | None = None,
    report_payload: dict[str, Any] | None = None,
    literature_context: dict[str, Any] | None = None,
    literature_claims: list[dict[str, Any]] | None = None,
    literature_comparisons: list[dict[str, Any]] | None = None,
    citations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create a normalized result record."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Unsupported result status: {status}")

    record = {
        "id": result_id,
        "analysis_type": analysis_type,
        "status": status,
        "dataset_key": dataset_key,
        "metadata": copy.deepcopy(metadata or {}),
        "summary": copy.deepcopy(summary or {}),
        "rows": copy.deepcopy(rows or []),
        "artifacts": copy.deepcopy(artifacts or {}),
        "processing": copy.deepcopy(processing or {}),
        "provenance": copy.deepcopy(provenance or {}),
        "validation": copy.deepcopy(validation or {}),
        "review": copy.deepcopy(review or {}),
        "scientific_context": normalize_scientific_context(scientific_context),
        "report_payload": copy.deepcopy(report_payload or {}),
        "literature_context": normalize_literature_context(literature_context),
        "literature_claims": normalize_literature_claims(literature_claims),
        "literature_comparisons": normalize_literature_comparisons(literature_comparisons),
        "citations": normalize_citations(citations),
    }
    record["report_payload"] = _normalize_xrd_report_payload(record)
    return record


def _validation_warnings(validation: dict[str, Any] | None) -> list[str]:
    warnings = []
    for item in (validation or {}).get("warnings") or []:
        if item in (None, ""):
            continue
        warnings.append(str(item))
    return warnings


def _attach_reasoning(
    *,
    base_context: dict[str, Any],
    analysis_type: str,
    summary: dict[str, Any] | None,
    rows: list[dict[str, Any]] | None,
    metadata: dict[str, Any] | None,
    fit_quality: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reasoning = build_scientific_reasoning(
        analysis_type=analysis_type,
        summary=summary or {},
        rows=rows or [],
        metadata=metadata or {},
        fit_quality=fit_quality or {},
        validation=validation or {},
    )
    merged = copy.deepcopy(base_context or {})
    merged.update(reasoning)
    return normalize_scientific_context(merged)


def _build_dsc_scientific_context(
    summary: dict[str, Any],
    *,
    rows: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
    processing: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    methodology = {
        "analysis_family": "Differential Scanning Calorimetry",
        "workflow_template": (processing or {}).get("workflow_template_label")
        or (processing or {}).get("workflow_template")
        or "General DSC",
        "signal_pipeline": (processing or {}).get("signal_pipeline") or {},
        "analysis_steps": (processing or {}).get("analysis_steps") or {},
    }
    equations = [
        build_equation(
            "Enthalpy Integration",
            "DeltaH = integral((signal - baseline) dT) / beta",
            notes="Area sign follows configured DSC sign convention.",
        )
    ]
    if summary.get("tg_midpoint") is not None:
        equations.append(
            build_equation(
                "Glass Transition Midpoint",
                "Tg(mid) from tangent-intersection between pre/post-transition baselines",
            )
        )
    interpretation = [
        build_interpretation(
            "Detected thermal events in DSC signal.",
            metric="peak_count",
            value=summary.get("peak_count"),
            unit="events",
        ),
    ]
    if summary.get("tg_midpoint") is not None:
        interpretation.append(
            build_interpretation(
                "Glass transition midpoint was resolved.",
                metric="tg_midpoint",
                value=summary.get("tg_midpoint"),
                unit="degC",
            )
        )
    limitations = [
        "Peak area and onset/endset are sensitive to baseline selection and smoothing strategy.",
        "Interpretation requires domain review when calibration/reference checks are not accepted.",
    ]
    warnings = _validation_warnings(validation)
    base_context = build_scientific_context(
        methodology=methodology,
        equations=equations,
        numerical_interpretation=interpretation,
        fit_quality=build_fit_quality({}),
        warnings=warnings,
        limitations=limitations,
    )
    return _attach_reasoning(
        base_context=base_context,
        analysis_type="DSC",
        summary=summary,
        rows=rows or [],
        metadata=metadata or {},
        fit_quality=(base_context or {}).get("fit_quality"),
        validation=validation,
    )


def _build_tga_scientific_context(
    summary: dict[str, Any],
    *,
    rows: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
    processing: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    methodology = {
        "analysis_family": "Thermogravimetric Analysis",
        "workflow_template": (processing or {}).get("workflow_template_label")
        or (processing or {}).get("workflow_template")
        or "General TGA",
        "signal_pipeline": (processing or {}).get("signal_pipeline") or {},
        "analysis_steps": (processing or {}).get("analysis_steps") or {},
    }
    equations = [
        build_equation(
            "Mass-Loss per Step",
            "mass_loss_percent = mass_onset - mass_endset",
            notes="Step bounds are estimated from DTG-derived onset/endset.",
        ),
        build_equation(
            "Total Mass Loss",
            "total_mass_loss_percent = smoothed_mass_start - smoothed_mass_end",
        ),
    ]
    interpretation = [
        build_interpretation(
            "Detected decomposition steps from DTG features.",
            metric="step_count",
            value=summary.get("step_count"),
            unit="steps",
        ),
        build_interpretation(
            "Overall mass loss across the run.",
            metric="total_mass_loss_percent",
            value=summary.get("total_mass_loss_percent"),
            unit="percent",
        ),
    ]
    limitations = [
        "Step boundaries are approximate and depend on smoothing and prominence thresholds.",
        "Absolute mass-loss conversion requires trusted initial-mass metadata.",
    ]
    warnings = _validation_warnings(validation)
    base_context = build_scientific_context(
        methodology=methodology,
        equations=equations,
        numerical_interpretation=interpretation,
        fit_quality=build_fit_quality({}),
        warnings=warnings,
        limitations=limitations,
    )
    return _attach_reasoning(
        base_context=base_context,
        analysis_type="TGA",
        summary=summary,
        rows=rows or [],
        metadata=metadata or {},
        fit_quality=(base_context or {}).get("fit_quality"),
        validation=validation,
    )


def _build_dta_scientific_context(
    summary: dict[str, Any],
    *,
    rows: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
    processing: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    methodology = {
        "analysis_family": "Differential Thermal Analysis",
        "workflow_template": (processing or {}).get("workflow_template_label")
        or (processing or {}).get("workflow_template")
        or "General DTA",
        "signal_pipeline": (processing or {}).get("signal_pipeline") or {},
        "analysis_steps": (processing or {}).get("analysis_steps") or {},
        "sign_convention": ((processing or {}).get("method_context") or {}).get("sign_convention_label")
        or (processing or {}).get("sign_convention")
        or "not recorded",
    }
    equations = [
        build_equation(
            "Event Area",
            "event_area = integral(deltaT - baseline dT)",
            notes="Qualitative unless instrument-specific calibration is available.",
        )
    ]
    interpretation = [
        build_interpretation(
            "Detected thermal events in DTA curve.",
            metric="peak_count",
            value=summary.get("peak_count"),
            unit="events",
            implication="Stable DTA workflow supports qualitative event screening.",
        )
    ]
    limitation_payload = build_limitations(
        limitations=[
            "Event-area values remain qualitative unless calibration and reference context are verified.",
            "Area-to-enthalpy mapping is instrument-dependent unless method-specific calibration is available.",
        ],
        warnings=_validation_warnings(validation),
    )
    base_context = build_scientific_context(
        methodology=methodology,
        equations=equations,
        numerical_interpretation=interpretation,
        fit_quality=build_fit_quality({}),
        warnings=limitation_payload["warnings"],
        limitations=limitation_payload["limitations"],
    )
    return _attach_reasoning(
        base_context=base_context,
        analysis_type="DTA",
        summary=summary,
        rows=rows or [],
        metadata=metadata or {},
        fit_quality=(base_context or {}).get("fit_quality"),
        validation=validation,
    )


def _build_spectral_scientific_context(
    summary: dict[str, Any],
    *,
    analysis_type: str,
    rows: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
    processing: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_type = str(analysis_type or "").upper() or "SPECTRAL"
    methodology = {
        "analysis_family": f"{normalized_type} Spectral Similarity",
        "workflow_template": (processing or {}).get("workflow_template_label")
        or (processing or {}).get("workflow_template")
        or f"General {normalized_type}",
        "signal_pipeline": (processing or {}).get("signal_pipeline") or {},
        "analysis_steps": (processing or {}).get("analysis_steps") or {},
        "matching_context": {
            "metric": ((processing or {}).get("method_context") or {}).get("matching_metric")
            or ((processing or {}).get("similarity_matching") or {}).get("metric"),
            "minimum_score": ((processing or {}).get("method_context") or {}).get("matching_minimum_score")
            or ((processing or {}).get("similarity_matching") or {}).get("minimum_score"),
            "top_n": ((processing or {}).get("method_context") or {}).get("matching_top_n")
            or ((processing or {}).get("similarity_matching") or {}).get("top_n"),
        },
        "library_context": {
            "sync_mode": ((processing or {}).get("method_context") or {}).get("library_sync_mode"),
            "cache_status": ((processing or {}).get("method_context") or {}).get("library_cache_status"),
            "access_mode": summary.get("library_access_mode")
            or ((processing or {}).get("method_context") or {}).get("library_access_mode"),
            "request_id": summary.get("library_request_id")
            or ((processing or {}).get("method_context") or {}).get("library_request_id"),
            "result_source": summary.get("library_result_source")
            or ((processing or {}).get("method_context") or {}).get("library_result_source"),
            "provider_scope": summary.get("library_provider_scope")
            or ((processing or {}).get("method_context") or {}).get("library_provider_scope")
            or [],
            "offline_limited_mode": summary.get("library_offline_limited_mode")
            if summary.get("library_offline_limited_mode") is not None
            else ((processing or {}).get("method_context") or {}).get("library_offline_limited_mode"),
            "reference_package_count": ((processing or {}).get("method_context") or {}).get(
                "library_reference_package_count"
            ),
            "reference_candidate_count": ((processing or {}).get("method_context") or {}).get(
                "library_reference_candidate_count"
            ),
            "provider": summary.get("library_provider"),
            "package": summary.get("library_package"),
            "version": summary.get("library_version"),
        },
    }
    equations = [
        build_equation(
            "Similarity Normalization",
            "normalized_score = clip((similarity + 1) / 2, 0, 1)",
            notes="Applies to cosine-based preranking and similarity reranking before confidence-band assignment.",
        )
    ]
    interpretation = [
        build_interpretation(
            "Ranked reference candidates were generated for this spectrum.",
            metric="candidate_count",
            value=summary.get("candidate_count"),
            unit="candidates",
        ),
        build_interpretation(
            "Top candidate confidence was normalized and banded.",
            metric="top_match_score",
            value=summary.get("top_match_score"),
            implication=f"match_status={summary.get('match_status')}",
        ),
    ]
    limitations = [
        "Similarity confidence depends on reference-library coverage and preprocessing assumptions.",
        "No-match outcomes are valid cautionary results and should not be interpreted as forced identification.",
    ]
    warnings = _validation_warnings(validation)
    caution_code = summary.get("caution_code")
    if caution_code:
        warnings.append(f"Caution: {caution_code}")
    base_context = build_scientific_context(
        methodology=methodology,
        equations=equations,
        numerical_interpretation=interpretation,
        fit_quality=build_fit_quality(
            {
                "confidence_band": summary.get("confidence_band"),
                "top_match_score": summary.get("top_match_score"),
            }
        ),
        warnings=warnings,
        limitations=limitations,
    )
    return _attach_reasoning(
        base_context=base_context,
        analysis_type=normalized_type,
        summary=summary,
        rows=rows or [],
        metadata=metadata or {},
        fit_quality=(base_context or {}).get("fit_quality"),
        validation=validation,
    )


def _build_xrd_scientific_context(
    summary: dict[str, Any],
    *,
    rows: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
    processing: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    methodology = {
        "analysis_family": "XRD Qualitative Phase Screening",
        "workflow_template": (processing or {}).get("workflow_template_label")
        or (processing or {}).get("workflow_template")
        or "General XRD",
        "signal_pipeline": (processing or {}).get("signal_pipeline") or {},
        "analysis_steps": (processing or {}).get("analysis_steps") or {},
        "library_context": {
            "sync_mode": ((processing or {}).get("method_context") or {}).get("library_sync_mode"),
            "cache_status": ((processing or {}).get("method_context") or {}).get("library_cache_status"),
            "access_mode": summary.get("library_access_mode")
            or ((processing or {}).get("method_context") or {}).get("library_access_mode"),
            "request_id": summary.get("library_request_id")
            or ((processing or {}).get("method_context") or {}).get("library_request_id"),
            "result_source": summary.get("library_result_source")
            or ((processing or {}).get("method_context") or {}).get("library_result_source"),
            "provider_scope": summary.get("library_provider_scope")
            or ((processing or {}).get("method_context") or {}).get("library_provider_scope")
            or [],
            "offline_limited_mode": summary.get("library_offline_limited_mode")
            if summary.get("library_offline_limited_mode") is not None
            else ((processing or {}).get("method_context") or {}).get("library_offline_limited_mode"),
            "reference_package_count": ((processing or {}).get("method_context") or {}).get(
                "library_reference_package_count"
            ),
            "reference_candidate_count": ((processing or {}).get("method_context") or {}).get(
                "library_reference_candidate_count"
            ),
            "provider": summary.get("library_provider"),
            "package": summary.get("library_package"),
            "version": summary.get("library_version"),
        },
        "matching_context": {
            "metric": ((processing or {}).get("method_context") or {}).get("xrd_match_metric"),
            "tolerance_deg": ((processing or {}).get("method_context") or {}).get("xrd_match_tolerance_deg"),
            "minimum_score": ((processing or {}).get("method_context") or {}).get("xrd_match_minimum_score"),
        },
    }
    equations = [
        build_equation(
            "Weighted Peak Overlap",
            "score = 0.5*coverage + wI*weighted_overlap + wD*delta_score - 0.15*major_unmatched_penalty",
            notes="Qualitative ranking only; not quantitative phase fraction.",
        )
    ]
    best_candidate_name = xrd_candidate_display_name(summary, target="unicode")
    best_candidate_score = summary.get("top_candidate_score")
    if best_candidate_score in (None, ""):
        best_candidate_score = summary.get("top_phase_score")
    interpretation = [
        build_interpretation(
            "Ranked candidate phases were generated from observed/reference peak overlap.",
            metric="candidate_count",
            value=summary.get("candidate_count"),
            unit="candidates",
        ),
        build_interpretation(
            "Best-ranked candidate evidence was retained separately from accepted match status.",
            metric="top_candidate_score",
            value=best_candidate_score,
            implication=(
                f"best_candidate={best_candidate_name or 'not_recorded'}; "
                f"accepted_match_status={summary.get('match_status')}"
            ),
        ),
    ]
    if summary.get("match_status") == "no_match" and summary.get("top_candidate_reason_below_threshold"):
        interpretation.append(
            build_interpretation(
                "The best-ranked candidate remained below the accepted qualitative phase-call threshold.",
                metric="top_candidate_reason_below_threshold",
                value=summary.get("top_candidate_reason_below_threshold"),
            )
        )
    limitations = [
        "Qualitative ranking is not a definitive identification or quantitative phase fraction.",
        "No-match and low-confidence outcomes remain valid cautionary results.",
    ]
    warnings = _validation_warnings(validation)
    caution_code = summary.get("caution_code")
    if caution_code:
        warnings.append(f"Caution: {caution_code}")
    caution_message = str(summary.get("caution_message") or "").strip()
    if caution_message:
        warnings.append(caution_message)
    fit_quality = build_fit_quality(
        {
            "confidence_band": summary.get("confidence_band"),
            "top_phase_score": summary.get("top_phase_score"),
            "top_candidate_score": best_candidate_score,
            "match_status": summary.get("match_status"),
            "top_candidate_reason_below_threshold": summary.get("top_candidate_reason_below_threshold"),
        }
    )
    base_context = build_scientific_context(
        methodology=methodology,
        equations=equations,
        numerical_interpretation=interpretation,
        fit_quality=fit_quality,
        warnings=warnings,
        limitations=limitations,
    )
    return _attach_reasoning(
        base_context=base_context,
        analysis_type="XRD",
        summary=summary,
        rows=rows or [],
        metadata=metadata or {},
        fit_quality=fit_quality,
        validation=validation,
    )


def _build_kissinger_scientific_context(result: Any, *, validation: dict[str, Any] | None = None) -> dict[str, Any]:
    equations = [
        build_equation(
            "Kissinger Linearization",
            "ln(beta / Tp^2) = -Ea / (R * Tp) + ln(A * R / Ea)",
            notes="Linear regression of ln(beta/Tp^2) vs 1/Tp.",
        )
    ]
    interpretation = [
        build_interpretation(
            "Estimated apparent activation energy from peak-temperature shift.",
            metric="activation_energy_kj_mol",
            value=_clean_scalar(getattr(result, "activation_energy", None)),
            unit="kJ/mol",
        ),
    ]
    fit_quality = build_fit_quality(
        {
            "r_squared": _clean_scalar(getattr(result, "r_squared", None)),
            "model": "linear_regression",
        }
    )
    base_context = build_scientific_context(
        methodology={"analysis_family": "Kinetic Analysis", "method": "Kissinger"},
        equations=equations,
        numerical_interpretation=interpretation,
        fit_quality=fit_quality,
        limitations=[
            "Assumes a dominant single-step process and representative peak temperatures.",
        ],
    )
    summary = {
        "activation_energy_kj_mol": _clean_scalar(getattr(result, "activation_energy", None)),
        "r_squared": _clean_scalar(getattr(result, "r_squared", None)),
    }
    rows = [
        {
            "activation_energy_kj_mol": _clean_scalar(getattr(result, "activation_energy", None)),
            "r_squared": _clean_scalar(getattr(result, "r_squared", None)),
        }
    ]
    return _attach_reasoning(
        base_context=base_context,
        analysis_type="Kissinger",
        summary=summary,
        rows=rows,
        metadata={},
        fit_quality=fit_quality,
        validation=validation,
    )


def _build_ofw_scientific_context(results: list[Any], *, validation: dict[str, Any] | None = None) -> dict[str, Any]:
    r2_values = [float(item.r_squared) for item in results if getattr(item, "r_squared", None) is not None]
    mean_r2 = sum(r2_values) / len(r2_values) if r2_values else None
    ea_values = [float(item.activation_energy) for item in results if getattr(item, "activation_energy", None) is not None]
    interpretation: list[dict[str, Any]] = [
        build_interpretation(
            "Computed activation-energy profile across conversion levels.",
            metric="conversion_point_count",
            value=len(results),
            unit="points",
        )
    ]
    if ea_values:
        interpretation.append(
            build_interpretation(
                "Observed OFW activation-energy range.",
                metric="activation_energy_range",
                value={"min": min(ea_values), "max": max(ea_values)},
                unit="kJ/mol",
            )
        )
    base_context = build_scientific_context(
        methodology={"analysis_family": "Kinetic Analysis", "method": "Ozawa-Flynn-Wall"},
        equations=[
            build_equation(
                "OFW Approximation",
                "log(beta) = -0.4567 * Ea / (R * T_alpha) + C",
                notes="Doyle approximation evaluated per conversion level alpha.",
            )
        ],
        numerical_interpretation=interpretation,
        fit_quality=build_fit_quality(
            {
                "mean_r_squared": _clean_scalar(mean_r2),
                "evaluated_levels": len(results),
            }
        ),
        limitations=[
            "Accuracy degrades near low/high conversion tails where interpolation is unstable.",
        ],
    )
    rows = []
    for item in results:
        plot_data = getattr(item, "plot_data", {}) or {}
        rows.append(
            {
                "alpha": _clean_scalar(plot_data.get("alpha")),
                "activation_energy_kj_mol": _clean_scalar(getattr(item, "activation_energy", None)),
                "r_squared": _clean_scalar(getattr(item, "r_squared", None)),
            }
        )
    summary = {"conversion_point_count": len(rows)}
    return _attach_reasoning(
        base_context=base_context,
        analysis_type="Ozawa-Flynn-Wall",
        summary=summary,
        rows=rows,
        metadata={},
        fit_quality=(base_context or {}).get("fit_quality"),
        validation=validation,
    )


def _build_friedman_scientific_context(results: list[Any], *, validation: dict[str, Any] | None = None) -> dict[str, Any]:
    r2_values = [float(item.r_squared) for item in results if getattr(item, "r_squared", None) is not None]
    mean_r2 = sum(r2_values) / len(r2_values) if r2_values else None
    base_context = build_scientific_context(
        methodology={"analysis_family": "Kinetic Analysis", "method": "Friedman"},
        equations=[
            build_equation(
                "Friedman Differential Form",
                "ln(dalpha/dt) = -Ea / (R * T_alpha) + ln(A * f(alpha))",
            )
        ],
        numerical_interpretation=[
            build_interpretation(
                "Computed activation-energy profile from differential conversion rates.",
                metric="conversion_point_count",
                value=len(results),
                unit="points",
            )
        ],
        fit_quality=build_fit_quality(
            {
                "mean_r_squared": _clean_scalar(mean_r2),
                "evaluated_levels": len(results),
            }
        ),
        limitations=[
            "Derivative-based method is sensitive to noise and smoothing choices.",
        ],
    )
    rows = []
    for item in results:
        plot_data = getattr(item, "plot_data", {}) or {}
        rows.append(
            {
                "alpha": _clean_scalar(plot_data.get("alpha")),
                "activation_energy_kj_mol": _clean_scalar(getattr(item, "activation_energy", None)),
                "r_squared": _clean_scalar(getattr(item, "r_squared", None)),
            }
        )
    summary = {"conversion_point_count": len(rows)}
    return _attach_reasoning(
        base_context=base_context,
        analysis_type="Friedman",
        summary=summary,
        rows=rows,
        metadata={},
        fit_quality=(base_context or {}).get("fit_quality"),
        validation=validation,
    )


def _build_deconvolution_scientific_context(
    result: dict[str, Any],
    peak_shape: str,
    n_peaks: int,
    *,
    metadata: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fit_quality = {
        "r_squared": _clean_scalar(result.get("r_squared")),
    }
    for key in ("rmse", "mae", "max_abs_residual", "reduced_chi_squared", "dof"):
        if key in (result.get("residual_stats") or {}):
            fit_quality[key] = _clean_scalar(result["residual_stats"].get(key))
    if "fit_quality" in result and isinstance(result["fit_quality"], dict):
        fit_quality.update({k: _clean_scalar(v) for k, v in result["fit_quality"].items()})

    interpretation = [
        build_interpretation(
            "Resolved overlapping peaks with a non-linear least-squares fit.",
            metric="peak_count",
            value=n_peaks,
            unit="components",
        )
    ]
    base_context = build_scientific_context(
        methodology={
            "analysis_family": "Peak Deconvolution",
            "fit_engine": "lmfit",
            "peak_shape": peak_shape,
            "initial_guesses": result.get("initial_guesses") or [],
        },
        equations=[
            build_equation(
                "Composite Peak Model",
                "y_hat(x) = sum_i component_i(x) + epsilon",
                notes=f"Component family: {peak_shape}",
            )
        ],
        numerical_interpretation=interpretation,
        fit_quality=build_fit_quality(fit_quality),
        limitations=[
            "Parameter identifiability may degrade for strongly overlapping peaks.",
            "Model-shape choice can bias component amplitudes and widths.",
        ],
    )
    summary = {
        "peak_shape": peak_shape,
        "peak_count": n_peaks,
        "r_squared": _clean_scalar(result.get("r_squared")),
    }
    return _attach_reasoning(
        base_context=base_context,
        analysis_type="Peak Deconvolution",
        summary=summary,
        rows=[],
        metadata=metadata or {},
        fit_quality=fit_quality,
        validation=validation or {},
    )


def thermal_peak_to_dict(peak: ThermalPeak) -> dict[str, Any]:
    """Serialize a ThermalPeak."""
    payload = {
        "peak_index": peak.peak_index,
        "peak_temperature": peak.peak_temperature,
        "peak_signal": peak.peak_signal,
        "onset_temperature": peak.onset_temperature,
        "endset_temperature": peak.endset_temperature,
        "area": peak.area,
        "fwhm": peak.fwhm,
        "peak_type": peak.peak_type,
        "height": peak.height,
    }
    direction = getattr(peak, "direction", None)
    if direction is not None:
        payload["direction"] = direction
    return {key: _clean_scalar(value) for key, value in payload.items()}


def thermal_peak_from_dict(payload: dict[str, Any]) -> ThermalPeak:
    """Deserialize a ThermalPeak."""
    peak = ThermalPeak(
        peak_index=int(payload["peak_index"]),
        peak_temperature=float(payload["peak_temperature"]),
        peak_signal=float(payload["peak_signal"]),
        onset_temperature=_to_optional_float(payload.get("onset_temperature")),
        endset_temperature=_to_optional_float(payload.get("endset_temperature")),
        area=_to_optional_float(payload.get("area")),
        fwhm=_to_optional_float(payload.get("fwhm")),
        peak_type=str(payload.get("peak_type", "unknown")),
        height=_to_optional_float(payload.get("height")),
    )
    direction = payload.get("direction")
    if direction is not None:
        try:
            object.__setattr__(peak, "direction", direction)
        except Exception:
            pass
    return peak


def glass_transition_to_dict(tg: GlassTransition) -> dict[str, Any]:
    """Serialize a GlassTransition."""
    return {
        "tg_midpoint": _clean_scalar(tg.tg_midpoint),
        "tg_onset": _clean_scalar(tg.tg_onset),
        "tg_endset": _clean_scalar(tg.tg_endset),
        "delta_cp": _clean_scalar(tg.delta_cp),
    }


def glass_transition_from_dict(payload: dict[str, Any]) -> GlassTransition:
    """Deserialize a GlassTransition."""
    return GlassTransition(
        tg_midpoint=float(payload["tg_midpoint"]),
        tg_onset=float(payload["tg_onset"]),
        tg_endset=float(payload["tg_endset"]),
        delta_cp=float(payload["delta_cp"]),
    )


def mass_loss_step_to_dict(step: MassLossStep) -> dict[str, Any]:
    """Serialize a MassLossStep."""
    return {
        "onset_temperature": _clean_scalar(step.onset_temperature),
        "endset_temperature": _clean_scalar(step.endset_temperature),
        "midpoint_temperature": _clean_scalar(step.midpoint_temperature),
        "mass_loss_percent": _clean_scalar(step.mass_loss_percent),
        "mass_loss_mg": _clean_scalar(step.mass_loss_mg),
        "residual_percent": _clean_scalar(step.residual_percent),
        "dtg_peak_temperature": _clean_scalar(step.dtg_peak_temperature),
    }


def mass_loss_step_from_dict(payload: dict[str, Any]) -> MassLossStep:
    """Deserialize a MassLossStep."""
    return MassLossStep(
        onset_temperature=float(payload["onset_temperature"]),
        endset_temperature=float(payload["endset_temperature"]),
        midpoint_temperature=float(payload["midpoint_temperature"]),
        mass_loss_percent=float(payload["mass_loss_percent"]),
        mass_loss_mg=_to_optional_float(payload.get("mass_loss_mg")),
        residual_percent=_to_optional_float(payload.get("residual_percent")),
        dtg_peak_temperature=_to_optional_float(payload.get("dtg_peak_temperature")),
    )


def serialize_dsc_result(
    dataset_key: str,
    dataset,
    peaks: Iterable[ThermalPeak],
    glass_transitions: Iterable[GlassTransition] | None = None,
    artifacts: dict[str, Any] | None = None,
    processing: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
    review: dict[str, Any] | None = None,
    scientific_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Serialize a stable DSC analysis record."""
    peaks = list(peaks)
    glass_transitions = list(glass_transitions or [])
    rows = [
        {
            "peak_type": peak.peak_type,
            "peak_temperature": _clean_scalar(peak.peak_temperature),
            "onset_temperature": _clean_scalar(peak.onset_temperature),
            "endset_temperature": _clean_scalar(peak.endset_temperature),
            "area": _clean_scalar(peak.area),
            "fwhm": _clean_scalar(peak.fwhm),
            "height": _clean_scalar(peak.height),
        }
        for peak in peaks
    ]
    summary = {
        "peak_count": len(peaks),
        "sample_name": dataset.metadata.get("sample_name"),
        "sample_mass": dataset.metadata.get("sample_mass"),
        "heating_rate": dataset.metadata.get("heating_rate"),
        "glass_transition_count": len(glass_transitions),
    }
    if glass_transitions:
        first_tg = glass_transitions[0]
        summary.update(
            {
                "tg_midpoint": _clean_scalar(first_tg.tg_midpoint),
                "tg_onset": _clean_scalar(first_tg.tg_onset),
                "tg_endset": _clean_scalar(first_tg.tg_endset),
                "delta_cp": _clean_scalar(first_tg.delta_cp),
            }
        )
    return make_result_record(
        result_id=f"dsc_{dataset_key}",
        analysis_type="DSC",
        status="stable",
        dataset_key=dataset_key,
        metadata=dataset.metadata,
        summary=summary,
        rows=rows,
        artifacts=artifacts,
        processing=processing,
        provenance=provenance,
        validation=validation,
        review=review,
        scientific_context=scientific_context
        or _build_dsc_scientific_context(
            summary,
            rows=rows,
            metadata=dataset.metadata,
            processing=processing,
            validation=validation,
        ),
    )


def serialize_tga_result(
    dataset_key: str,
    dataset,
    result: TGAResult,
    artifacts: dict[str, Any] | None = None,
    processing: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
    review: dict[str, Any] | None = None,
    scientific_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Serialize a stable TGA analysis record."""
    rows = [
        {
            "onset_temperature": _clean_scalar(step.onset_temperature),
            "midpoint_temperature": _clean_scalar(step.midpoint_temperature),
            "endset_temperature": _clean_scalar(step.endset_temperature),
            "mass_loss_percent": _clean_scalar(step.mass_loss_percent),
            "mass_loss_mg": _clean_scalar(step.mass_loss_mg),
            "residual_percent": _clean_scalar(step.residual_percent),
        }
        for step in result.steps
    ]
    summary = {
        "step_count": len(result.steps),
        "total_mass_loss_percent": _clean_scalar(result.total_mass_loss_percent),
        "residue_percent": _clean_scalar(result.residue_percent),
        "sample_name": dataset.metadata.get("sample_name"),
        "sample_mass": dataset.metadata.get("sample_mass"),
        "heating_rate": dataset.metadata.get("heating_rate"),
    }
    return make_result_record(
        result_id=f"tga_{dataset_key}",
        analysis_type="TGA",
        status="stable",
        dataset_key=dataset_key,
        metadata=dataset.metadata,
        summary=summary,
        rows=rows,
        artifacts=artifacts,
        processing=processing,
        provenance=provenance,
        validation=validation,
        review=review,
        scientific_context=scientific_context
        or _build_tga_scientific_context(
            summary,
            rows=rows,
            metadata=dataset.metadata,
            processing=processing,
            validation=validation,
        ),
    )


def serialize_dta_result(
    dataset_key: str,
    dataset,
    peaks: Iterable[ThermalPeak],
    status: str = "stable",
    artifacts: dict[str, Any] | None = None,
    processing: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
    review: dict[str, Any] | None = None,
    scientific_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Serialize a DTA analysis record."""
    peaks = list(peaks)
    rows = [
        {
            "peak_type": getattr(peak, "direction", peak.peak_type),
            "peak_temperature": _clean_scalar(peak.peak_temperature),
            "onset_temperature": _clean_scalar(peak.onset_temperature),
            "endset_temperature": _clean_scalar(peak.endset_temperature),
            "area": _clean_scalar(peak.area),
            "fwhm": _clean_scalar(peak.fwhm),
            "height": _clean_scalar(peak.height),
        }
        for peak in peaks
    ]
    summary = {
        "peak_count": len(peaks),
        "sample_name": dataset.metadata.get("sample_name"),
        "sample_mass": dataset.metadata.get("sample_mass"),
        "heating_rate": dataset.metadata.get("heating_rate"),
    }
    return make_result_record(
        result_id=f"dta_{dataset_key}",
        analysis_type="DTA",
        status=status,
        dataset_key=dataset_key,
        metadata=dataset.metadata,
        summary=summary,
        rows=rows,
        artifacts=artifacts,
        processing=processing,
        provenance=provenance,
        validation=validation,
        review=review,
        scientific_context=scientific_context
        or _build_dta_scientific_context(
            summary,
            rows=rows,
            metadata=dataset.metadata,
            processing=processing,
            validation=validation,
        ),
    )


def serialize_spectral_result(
    dataset_key: str,
    dataset,
    *,
    analysis_type: str,
    summary: Mapping[str, Any] | None = None,
    rows: Iterable[Mapping[str, Any]] | None = None,
    status: str = "stable",
    artifacts: dict[str, Any] | None = None,
    processing: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
    review: dict[str, Any] | None = None,
    scientific_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Serialize a stable FTIR/RAMAN spectral-similarity record."""
    normalized_type = str(analysis_type or "").upper()
    if normalized_type not in {"FTIR", "RAMAN"}:
        raise ValueError(f"Unsupported spectral analysis_type: {analysis_type}")

    normalized_rows: list[dict[str, Any]] = []
    for index, item in enumerate(rows or [], start=1):
        payload = dict(item or {})
        normalized_rows.append(
            {
                "rank": int(payload.get("rank") or index),
                "candidate_id": payload.get("candidate_id"),
                "candidate_name": payload.get("candidate_name"),
                "normalized_score": _clean_scalar(payload.get("normalized_score")),
                "confidence_band": payload.get("confidence_band"),
                "library_provider": payload.get("library_provider"),
                "library_package": payload.get("library_package"),
                "library_version": payload.get("library_version"),
                "evidence": copy.deepcopy(payload.get("evidence") or {}),
            }
        )

    normalized_summary = dict(summary or {})
    normalized_summary.setdefault("peak_count", 0)
    normalized_summary.setdefault("candidate_count", len(normalized_rows))
    normalized_summary.setdefault("match_status", "no_match")
    normalized_summary.setdefault("confidence_band", "no_match")
    normalized_summary.setdefault("top_match_score", 0.0)
    normalized_summary.setdefault("top_match_id", None)
    normalized_summary.setdefault("top_match_name", None)
    normalized_summary.setdefault("library_provider", None)
    normalized_summary.setdefault("library_package", None)
    normalized_summary.setdefault("library_version", None)
    normalized_summary.setdefault("library_sync_mode", None)
    normalized_summary.setdefault("library_cache_status", None)
    normalized_summary.setdefault("library_access_mode", None)
    normalized_summary.setdefault("library_request_id", None)
    normalized_summary.setdefault("library_result_source", None)
    normalized_summary.setdefault("library_provider_scope", [])
    normalized_summary.setdefault("library_offline_limited_mode", False)
    normalized_summary.setdefault("sample_name", dataset.metadata.get("sample_name"))
    normalized_summary.setdefault("sample_mass", dataset.metadata.get("sample_mass"))
    normalized_summary.setdefault("heating_rate", dataset.metadata.get("heating_rate"))
    if normalized_rows and not normalized_summary.get("library_provider"):
        normalized_summary["library_provider"] = normalized_rows[0].get("library_provider")
    if normalized_rows and not normalized_summary.get("library_package"):
        normalized_summary["library_package"] = normalized_rows[0].get("library_package")
    if normalized_rows and not normalized_summary.get("library_version"):
        normalized_summary["library_version"] = normalized_rows[0].get("library_version")
    if normalized_summary.get("library_sync_mode") in (None, ""):
        normalized_summary["library_sync_mode"] = ((processing or {}).get("method_context") or {}).get(
            "library_sync_mode"
        )
    if normalized_summary.get("library_cache_status") in (None, ""):
        normalized_summary["library_cache_status"] = ((processing or {}).get("method_context") or {}).get(
            "library_cache_status"
        )
    if normalized_summary.get("library_access_mode") in (None, ""):
        normalized_summary["library_access_mode"] = ((processing or {}).get("method_context") or {}).get(
            "library_access_mode"
        )
    if normalized_summary.get("library_request_id") in (None, ""):
        normalized_summary["library_request_id"] = ((processing or {}).get("method_context") or {}).get(
            "library_request_id"
        )
    if normalized_summary.get("library_result_source") in (None, ""):
        normalized_summary["library_result_source"] = ((processing or {}).get("method_context") or {}).get(
            "library_result_source"
        )
    if not normalized_summary.get("library_provider_scope"):
        normalized_summary["library_provider_scope"] = list(
            ((processing or {}).get("method_context") or {}).get("library_provider_scope")
            or []
        )
    if normalized_summary.get("library_offline_limited_mode") in (None, ""):
        normalized_summary["library_offline_limited_mode"] = bool(
            ((processing or {}).get("method_context") or {}).get("library_offline_limited_mode")
        )
    normalized_summary["top_match_score"] = _clean_scalar(normalized_summary.get("top_match_score"))

    match_status = str(normalized_summary.get("match_status") or "").lower()
    confidence_band = str(normalized_summary.get("confidence_band") or "").lower()
    caution_payload = {}
    if match_status == "no_match":
        caution_payload = {
            "code": str(normalized_summary.get("caution_code") or "spectral_no_match"),
            "message": str(
                normalized_summary.get("caution_message")
                or "No reference candidate met the minimum similarity threshold."
            ),
            "top_match_score": _clean_scalar(normalized_summary.get("top_match_score")),
        }
    elif match_status == "matched" and confidence_band == "low":
        caution_payload = {
            "code": str(normalized_summary.get("caution_code") or "spectral_low_confidence"),
            "message": str(
                normalized_summary.get("caution_message")
                or "Top candidate confidence is low; review spectral evidence before definitive interpretation."
            ),
            "top_match_score": _clean_scalar(normalized_summary.get("top_match_score")),
        }

    if caution_payload:
        normalized_summary["caution_code"] = caution_payload["code"]
        normalized_summary["caution_message"] = caution_payload["message"]
    else:
        normalized_summary.setdefault("caution_code", "")
        normalized_summary.setdefault("caution_message", "")

    review_payload = copy.deepcopy(review or {})
    if caution_payload:
        review_payload["caution"] = caution_payload
    elif "caution" not in review_payload:
        review_payload["caution"] = {}

    return make_result_record(
        result_id=f"{normalized_type.lower()}_{dataset_key}",
        analysis_type=normalized_type,
        status=status,
        dataset_key=dataset_key,
        metadata=dataset.metadata,
        summary=normalized_summary,
        rows=normalized_rows,
        artifacts=artifacts,
        processing=processing,
        provenance=provenance,
        validation=validation,
        review=review_payload,
        scientific_context=scientific_context
        or _build_spectral_scientific_context(
            normalized_summary,
            analysis_type=normalized_type,
            rows=normalized_rows,
            metadata=dataset.metadata,
            processing=processing,
            validation=validation,
        ),
    )


def serialize_xrd_result(
    dataset_key: str,
    dataset,
    *,
    summary: Mapping[str, Any] | None = None,
    rows: Iterable[Mapping[str, Any]] | None = None,
    status: str = "stable",
    artifacts: dict[str, Any] | None = None,
    processing: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
    review: dict[str, Any] | None = None,
    scientific_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Serialize a stable XRD qualitative phase-candidate record."""
    normalized_rows: list[dict[str, Any]] = []
    for index, item in enumerate(rows or [], start=1):
        payload = dict(item or {})
        display_payload = xrd_candidate_display_payload(payload)
        reference_bundle = build_xrd_reference_bundle(payload)
        normalized_rows.append(
            {
                "rank": int(payload.get("rank") or index),
                "candidate_id": payload.get("candidate_id"),
                "candidate_name": payload.get("candidate_name"),
                "display_name": payload.get("display_name") or display_payload.get("display_name"),
                "display_name_unicode": payload.get("display_name_unicode") or reference_bundle.get("display_name_unicode"),
                "phase_name": payload.get("phase_name") or display_payload.get("phase_name"),
                "formula_pretty": payload.get("formula_pretty") or display_payload.get("formula_pretty"),
                "formula": payload.get("formula") or display_payload.get("formula"),
                "formula_unicode": payload.get("formula_unicode") or reference_bundle.get("formula_unicode"),
                "source_id": payload.get("source_id") or display_payload.get("source_id"),
                "normalized_score": _clean_scalar(payload.get("normalized_score")),
                "confidence_band": payload.get("confidence_band"),
                "library_provider": payload.get("library_provider"),
                "library_package": payload.get("library_package"),
                "library_version": payload.get("library_version"),
                "reference_metadata": copy.deepcopy(reference_bundle.get("reference_metadata") or {}),
                "reference_peaks": copy.deepcopy(reference_bundle.get("reference_peaks") or []),
                "structure_payload": copy.deepcopy(reference_bundle.get("structure_payload") or {}),
                "source_assets": copy.deepcopy(reference_bundle.get("source_assets") or []),
                "evidence": copy.deepcopy(payload.get("evidence") or {}),
            }
        )

    normalized_summary = dict(summary or {})
    top_row = normalized_rows[0] if normalized_rows else None
    top_evidence = dict((top_row or {}).get("evidence") or {})
    normalized_summary.setdefault("peak_count", 0)
    normalized_summary.setdefault("candidate_count", len(normalized_rows))
    normalized_summary.setdefault("match_status", "no_match")
    normalized_summary.setdefault("confidence_band", "no_match")
    normalized_summary.setdefault("top_phase_id", None)
    normalized_summary.setdefault("top_phase", None)
    normalized_summary.setdefault("top_phase_score", 0.0)
    normalized_summary.setdefault("top_match_id", normalized_summary.get("top_phase_id"))
    normalized_summary.setdefault("top_match_name", normalized_summary.get("top_phase"))
    normalized_summary.setdefault("top_match_score", normalized_summary.get("top_phase_score"))
    normalized_summary.setdefault("library_provider", None)
    normalized_summary.setdefault("library_package", None)
    normalized_summary.setdefault("library_version", None)
    normalized_summary.setdefault("library_sync_mode", None)
    normalized_summary.setdefault("library_cache_status", None)
    normalized_summary.setdefault("library_access_mode", None)
    normalized_summary.setdefault("library_request_id", None)
    normalized_summary.setdefault("library_result_source", None)
    normalized_summary.setdefault("library_provider_scope", [])
    normalized_summary.setdefault("library_offline_limited_mode", False)
    normalized_summary.setdefault("sample_name", dataset.metadata.get("sample_name"))
    normalized_summary.setdefault("sample_mass", dataset.metadata.get("sample_mass"))
    normalized_summary.setdefault("heating_rate", dataset.metadata.get("heating_rate"))
    normalized_summary.setdefault("top_candidate_id", (top_row or {}).get("candidate_id"))
    normalized_summary.setdefault("top_candidate_name", (top_row or {}).get("candidate_name"))
    normalized_summary.setdefault("top_candidate_phase_name", (top_row or {}).get("phase_name"))
    normalized_summary.setdefault("top_candidate_formula_pretty", (top_row or {}).get("formula_pretty"))
    normalized_summary.setdefault("top_candidate_formula", (top_row or {}).get("formula"))
    normalized_summary.setdefault("top_candidate_source_id", (top_row or {}).get("source_id"))
    normalized_summary.setdefault("top_candidate_score", (top_row or {}).get("normalized_score"))
    normalized_summary.setdefault("top_candidate_confidence_band", (top_row or {}).get("confidence_band"))
    normalized_summary.setdefault("top_candidate_provider", (top_row or {}).get("library_provider"))
    normalized_summary.setdefault("top_candidate_package", (top_row or {}).get("library_package"))
    normalized_summary.setdefault("top_candidate_version", (top_row or {}).get("library_version"))
    normalized_summary.setdefault("top_candidate_shared_peak_count", top_evidence.get("shared_peak_count"))
    normalized_summary.setdefault("top_candidate_weighted_overlap_score", top_evidence.get("weighted_overlap_score"))
    normalized_summary.setdefault("top_candidate_coverage_ratio", top_evidence.get("coverage_ratio"))
    normalized_summary.setdefault("top_candidate_mean_delta_position", top_evidence.get("mean_delta_position"))
    normalized_summary.setdefault("top_candidate_unmatched_major_peak_count", top_evidence.get("unmatched_major_peak_count"))
    normalized_summary.setdefault("top_candidate_reason_below_threshold", "")
    top_display = xrd_candidate_display_payload(normalized_summary, top_row)
    top_display_variants = xrd_candidate_display_variants(normalized_summary, top_row)
    normalized_summary.setdefault("top_candidate_display_name", top_display.get("display_name"))
    normalized_summary.setdefault("top_phase_display_name", top_display.get("display_name"))
    normalized_summary.setdefault("top_candidate_display_name_unicode", top_display_variants.get("unicode_display_name"))
    normalized_summary.setdefault("top_phase_display_name_unicode", top_display_variants.get("unicode_display_name"))
    if normalized_rows and not normalized_summary.get("library_provider"):
        normalized_summary["library_provider"] = normalized_rows[0].get("library_provider")
    if normalized_rows and not normalized_summary.get("library_package"):
        normalized_summary["library_package"] = normalized_rows[0].get("library_package")
    if normalized_rows and not normalized_summary.get("library_version"):
        normalized_summary["library_version"] = normalized_rows[0].get("library_version")
    if normalized_summary.get("library_sync_mode") in (None, ""):
        normalized_summary["library_sync_mode"] = ((processing or {}).get("method_context") or {}).get(
            "library_sync_mode"
        )
    if normalized_summary.get("library_cache_status") in (None, ""):
        normalized_summary["library_cache_status"] = ((processing or {}).get("method_context") or {}).get(
            "library_cache_status"
        )
    if normalized_summary.get("library_access_mode") in (None, ""):
        normalized_summary["library_access_mode"] = ((processing or {}).get("method_context") or {}).get(
            "library_access_mode"
        )
    if normalized_summary.get("library_request_id") in (None, ""):
        normalized_summary["library_request_id"] = ((processing or {}).get("method_context") or {}).get(
            "library_request_id"
        )
    if normalized_summary.get("library_result_source") in (None, ""):
        normalized_summary["library_result_source"] = ((processing or {}).get("method_context") or {}).get(
            "library_result_source"
        )
    if not normalized_summary.get("library_provider_scope"):
        normalized_summary["library_provider_scope"] = list(
            ((processing or {}).get("method_context") or {}).get("library_provider_scope")
            or []
        )
    if normalized_summary.get("library_offline_limited_mode") in (None, ""):
        normalized_summary["library_offline_limited_mode"] = bool(
            ((processing or {}).get("method_context") or {}).get("library_offline_limited_mode")
        )
    normalized_summary["top_phase_score"] = _clean_scalar(normalized_summary.get("top_phase_score"))
    normalized_summary["top_match_score"] = _clean_scalar(normalized_summary.get("top_match_score"))
    normalized_summary["top_candidate_score"] = _clean_scalar(normalized_summary.get("top_candidate_score"))
    normalized_summary["top_candidate_weighted_overlap_score"] = _clean_scalar(
        normalized_summary.get("top_candidate_weighted_overlap_score")
    )
    normalized_summary["top_candidate_coverage_ratio"] = _clean_scalar(normalized_summary.get("top_candidate_coverage_ratio"))
    normalized_summary["top_candidate_mean_delta_position"] = _clean_scalar(
        normalized_summary.get("top_candidate_mean_delta_position")
    )

    match_status = str(normalized_summary.get("match_status") or "").lower()
    confidence_band = str(normalized_summary.get("confidence_band") or "").lower()
    if match_status == "no_match" and top_row and not str(normalized_summary.get("top_candidate_reason_below_threshold") or "").strip():
        reasons: list[str] = []
        top_candidate_score = normalized_summary.get("top_candidate_score")
        minimum_score = _clean_scalar(((processing or {}).get("method_context") or {}).get("xrd_match_minimum_score"))
        try:
            parsed_score = float(top_candidate_score) if top_candidate_score not in (None, "") else None
        except (TypeError, ValueError):
            parsed_score = None
        try:
            parsed_minimum = float(minimum_score) if minimum_score not in (None, "") else None
        except (TypeError, ValueError):
            parsed_minimum = None
        try:
            unmatched_major = int(normalized_summary.get("top_candidate_unmatched_major_peak_count") or 0)
        except (TypeError, ValueError):
            unmatched_major = 0
        try:
            shared_peak_count = int(normalized_summary.get("top_candidate_shared_peak_count") or 0)
        except (TypeError, ValueError):
            shared_peak_count = 0
        try:
            coverage_ratio = float(normalized_summary.get("top_candidate_coverage_ratio"))
        except (TypeError, ValueError):
            coverage_ratio = None
        try:
            weighted_overlap = float(normalized_summary.get("top_candidate_weighted_overlap_score"))
        except (TypeError, ValueError):
            weighted_overlap = None

        if parsed_score is not None and parsed_minimum is not None and parsed_score < parsed_minimum:
            reasons.append("below minimum score threshold")
        if unmatched_major > 0:
            reasons.append("unmatched major reference peaks")
        if coverage_ratio is not None and coverage_ratio < 0.5:
            reasons.append("limited reference coverage")
        if shared_peak_count <= 0:
            reasons.append("insufficient shared peaks")
        elif weighted_overlap is not None and weighted_overlap < 0.35:
            reasons.append("weak overlap after penalty")
        if ((dataset.metadata or {}).get("xrd_axis_role") or "").strip().lower() in {"two_theta", ""} and (
            (dataset.metadata or {}).get("xrd_wavelength_angstrom") in (None, "")
        ):
            reasons.append("wavelength metadata missing")
        if bool((dataset.metadata or {}).get("import_review_required")):
            reasons.append("import review required")
        if not reasons:
            reasons.append("candidate exists but evidence remains insufficient for accepted qualitative match")
        normalized_summary["top_candidate_reason_below_threshold"] = "; ".join(reasons[:3])

    caution_payload = {}
    if match_status == "no_match":
        caution_payload = {
            "code": str(normalized_summary.get("caution_code") or "xrd_no_match"),
            "message": str(
                normalized_summary.get("caution_message")
                or "No reference phase candidate met the minimum qualitative matching threshold."
            ),
            "top_phase_score": _clean_scalar(normalized_summary.get("top_phase_score")),
            "top_candidate_name": normalized_summary.get("top_candidate_name"),
            "top_candidate_display_name": normalized_summary.get("top_candidate_display_name"),
            "top_candidate_score": _clean_scalar(normalized_summary.get("top_candidate_score")),
            "top_candidate_reason_below_threshold": normalized_summary.get("top_candidate_reason_below_threshold"),
        }
    elif match_status == "matched" and confidence_band == "low":
        caution_payload = {
            "code": str(normalized_summary.get("caution_code") or "xrd_low_confidence"),
            "message": str(
                normalized_summary.get("caution_message")
                or "Top XRD candidate is low confidence; review evidence before interpretation."
            ),
            "top_phase_score": _clean_scalar(normalized_summary.get("top_phase_score")),
            "top_candidate_name": normalized_summary.get("top_candidate_name"),
            "top_candidate_display_name": normalized_summary.get("top_candidate_display_name"),
            "top_candidate_score": _clean_scalar(normalized_summary.get("top_candidate_score")),
        }

    if caution_payload:
        normalized_summary["caution_code"] = caution_payload["code"]
        normalized_summary["caution_message"] = caution_payload["message"]
    else:
        normalized_summary.setdefault("caution_code", "")
        normalized_summary.setdefault("caution_message", "")

    review_payload = copy.deepcopy(review or {})
    if caution_payload:
        review_payload["caution"] = caution_payload
    elif "caution" not in review_payload:
        review_payload["caution"] = {}

    report_payload = {
        "xrd_reference_dossier_limit": XRD_REFERENCE_DOSSIER_LIMIT,
        "xrd_reference_peak_display_limit": XRD_REFERENCE_PEAK_DISPLAY_LIMIT,
        "xrd_reference_dossiers": build_xrd_reference_dossiers(
            normalized_summary,
            normalized_rows,
            dossier_limit=XRD_REFERENCE_DOSSIER_LIMIT,
            peak_display_limit=XRD_REFERENCE_PEAK_DISPLAY_LIMIT,
        ),
    }

    return make_result_record(
        result_id=f"xrd_{dataset_key}",
        analysis_type="XRD",
        status=status,
        dataset_key=dataset_key,
        metadata=dataset.metadata,
        summary=normalized_summary,
        rows=normalized_rows,
        artifacts=artifacts,
        processing=processing,
        provenance=provenance,
        validation=validation,
        review=review_payload,
        scientific_context=scientific_context
        or _build_xrd_scientific_context(
            normalized_summary,
            rows=normalized_rows,
            metadata=dataset.metadata,
            processing=processing,
            validation=validation,
        ),
        report_payload=report_payload,
    )


def serialize_kissinger_result(
    result,
    artifacts: dict[str, Any] | None = None,
    processing: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
    review: dict[str, Any] | None = None,
    scientific_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Serialize an experimental Kissinger result."""
    summary = {
        "activation_energy_kj_mol": _clean_scalar(result.activation_energy),
        "r_squared": _clean_scalar(result.r_squared),
        "pre_exponential": _clean_scalar(result.pre_exponential),
    }
    return make_result_record(
        result_id="kissinger",
        analysis_type="Kissinger",
        status="experimental",
        dataset_key=None,
        metadata={},
        summary=summary,
        rows=[],
        artifacts=artifacts,
        processing=processing,
        provenance=provenance,
        validation=validation,
        review=review,
        scientific_context=scientific_context or _build_kissinger_scientific_context(result, validation=validation),
    )


def serialize_ofw_results(
    results: Iterable[Any],
    artifacts: dict[str, Any] | None = None,
    processing: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
    review: dict[str, Any] | None = None,
    scientific_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Serialize experimental Ozawa-Flynn-Wall results."""
    rows = []
    results = list(results)
    for item in results:
        plot_data = item.plot_data or {}
        rows.append(
            {
                "alpha": _clean_scalar(plot_data.get("alpha")),
                "activation_energy_kj_mol": _clean_scalar(item.activation_energy),
                "r_squared": _clean_scalar(item.r_squared),
            }
        )
    summary = {"conversion_point_count": len(rows)}
    return make_result_record(
        result_id="ofw",
        analysis_type="Ozawa-Flynn-Wall",
        status="experimental",
        dataset_key=None,
        metadata={},
        summary=summary,
        rows=rows,
        artifacts=artifacts,
        processing=processing,
        provenance=provenance,
        validation=validation,
        review=review,
        scientific_context=scientific_context or _build_ofw_scientific_context(results, validation=validation),
    )


def serialize_friedman_results(
    results: Iterable[Any],
    artifacts: dict[str, Any] | None = None,
    processing: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
    review: dict[str, Any] | None = None,
    scientific_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Serialize experimental Friedman results."""
    rows = []
    results = list(results)
    for item in results:
        plot_data = item.plot_data or {}
        rows.append(
            {
                "alpha": _clean_scalar(plot_data.get("alpha")),
                "activation_energy_kj_mol": _clean_scalar(item.activation_energy),
                "pre_exponential": _clean_scalar(item.pre_exponential),
                "r_squared": _clean_scalar(item.r_squared),
            }
        )
    summary = {"conversion_point_count": len(rows)}
    return make_result_record(
        result_id="friedman",
        analysis_type="Friedman",
        status="experimental",
        dataset_key=None,
        metadata={},
        summary=summary,
        rows=rows,
        artifacts=artifacts,
        processing=processing,
        provenance=provenance,
        validation=validation,
        review=review,
        scientific_context=scientific_context or _build_friedman_scientific_context(results, validation=validation),
    )


def serialize_deconvolution_result(
    dataset_key: str,
    dataset,
    result: dict[str, Any],
    peak_shape: str,
    artifacts: dict[str, Any] | None = None,
    processing: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
    review: dict[str, Any] | None = None,
    scientific_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Serialize an experimental peak deconvolution result."""
    params = result.get("params", {})
    rows = []
    n_peaks = len(result.get("components", []))
    for index in range(n_peaks):
        prefix = f"p{index + 1}_"
        row = {
            "peak": index + 1,
            "center": _clean_scalar(params.get(f"{prefix}center")),
            "amplitude": _clean_scalar(params.get(f"{prefix}amplitude")),
            "sigma": _clean_scalar(params.get(f"{prefix}sigma")),
        }
        fraction = params.get(f"{prefix}fraction")
        if fraction is not None:
            row["fraction"] = _clean_scalar(fraction)
        rows.append(row)

    summary = {
        "r_squared": _clean_scalar(result.get("r_squared")),
        "peak_shape": peak_shape,
        "peak_count": n_peaks,
    }
    return make_result_record(
        result_id=f"deconv_{dataset_key}",
        analysis_type="Peak Deconvolution",
        status="experimental",
        dataset_key=dataset_key,
        metadata=dataset.metadata,
        summary=summary,
        rows=rows,
        artifacts=artifacts,
        processing=processing,
        provenance=provenance,
        validation=validation,
        review=review,
        scientific_context=scientific_context
        or _build_deconvolution_scientific_context(
            result,
            peak_shape,
            n_peaks,
            metadata=dataset.metadata,
            validation=validation,
        ),
    )


def validate_result_record(result_id: str, record: Any) -> list[str]:
    """Return validation issues for a normalized result record."""
    issues: list[str] = []
    if not isinstance(record, dict):
        return [f"{result_id}: result record is not a dict"]

    missing = sorted(REQUIRED_RESULT_KEYS - set(record))
    if missing:
        issues.append(f"{result_id}: missing keys {', '.join(missing)}")

    status = record.get("status")
    if status is not None and status not in VALID_STATUSES:
        issues.append(f"{result_id}: invalid status '{status}'")

    if "rows" in record and not isinstance(record.get("rows"), list):
        issues.append(f"{result_id}: rows must be a list")
    if "summary" in record and not isinstance(record.get("summary"), dict):
        issues.append(f"{result_id}: summary must be a dict")
    if "metadata" in record and not isinstance(record.get("metadata"), dict):
        issues.append(f"{result_id}: metadata must be a dict")
    if "artifacts" in record and not isinstance(record.get("artifacts"), dict):
        issues.append(f"{result_id}: artifacts must be a dict")
    for optional_key in OPTIONAL_RESULT_KEYS:
        if optional_key in record and not isinstance(record.get(optional_key), dict):
            issues.append(f"{result_id}: {optional_key} must be a dict")
    for optional_key in OPTIONAL_RESULT_LIST_KEYS:
        if optional_key in record and not isinstance(record.get(optional_key), list):
            issues.append(f"{result_id}: {optional_key} must be a list")

    return issues


def split_valid_results(results: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Separate valid normalized records from invalid ones."""
    valid: dict[str, dict[str, Any]] = {}
    issues: list[str] = []
    for result_id, record in (results or {}).items():
        record_issues = validate_result_record(result_id, record)
        if record_issues:
            issues.extend(record_issues)
            continue
        normalized = copy.deepcopy(record)
        normalized.setdefault("id", result_id)
        normalized.setdefault("processing", {})
        normalized.setdefault("provenance", {})
        normalized.setdefault("validation", {})
        normalized.setdefault("review", {})
        normalized.setdefault("report_payload", {})
        normalized.setdefault("literature_context", {})
        normalized.setdefault("literature_claims", [])
        normalized.setdefault("literature_comparisons", [])
        normalized.setdefault("citations", [])
        normalized["report_payload"] = _normalize_xrd_report_payload(normalized)
        normalized["scientific_context"] = normalize_scientific_context(
            normalized.get("scientific_context")
        )
        normalized["literature_context"] = normalize_literature_context(
            normalized.get("literature_context")
        )
        normalized["literature_claims"] = normalize_literature_claims(
            normalized.get("literature_claims")
        )
        normalized["literature_comparisons"] = normalize_literature_comparisons(
            normalized.get("literature_comparisons")
        )
        normalized["citations"] = normalize_citations(
            normalized.get("citations")
        )
        valid[result_id] = normalized
    return valid, issues


def _flat_value(value: Any) -> Any:
    value = _clean_scalar(value)
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return value


def partition_results_by_status(results: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return stable and experimental result lists."""
    stable = []
    experimental = []
    for record in results.values():
        if record.get("status") == "stable":
            stable.append(record)
        else:
            experimental.append(record)
    return stable, experimental


def flatten_result_records(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten normalized results for CSV export."""
    rows: list[dict[str, Any]] = []
    for record in results.values():
        base = {
            "result_id": record["id"],
            "status": record["status"],
            "analysis_type": record["analysis_type"],
            "dataset_key": record["dataset_key"],
        }
        for key, value in record.get("metadata", {}).items():
            rows.append({**base, "section": "metadata", "row_index": "", "field": key, "value": _flat_value(value)})
        for key, value in record.get("summary", {}).items():
            rows.append({**base, "section": "summary", "row_index": "", "field": key, "value": _flat_value(value)})
        for section_name in (
            "processing",
            "provenance",
            "validation",
            "review",
            "scientific_context",
            "report_payload",
            "literature_context",
        ):
            for key, value in record.get(section_name, {}).items():
                rows.append({**base, "section": section_name, "row_index": "", "field": key, "value": _flat_value(value)})
        for section_name in ("literature_claims", "literature_comparisons", "citations"):
            for index, item in enumerate(record.get(section_name, []), start=1):
                if isinstance(item, Mapping):
                    for key, value in item.items():
                        rows.append(
                            {
                                **base,
                                "section": section_name,
                                "row_index": index,
                                "field": key,
                                "value": _flat_value(value),
                            }
                        )
                else:
                    rows.append(
                        {
                            **base,
                            "section": section_name,
                            "row_index": index,
                            "field": "value",
                            "value": _flat_value(item),
                        }
                    )
        for index, row in enumerate(record.get("rows", []), start=1):
            for key, value in row.items():
                rows.append({**base, "section": "row", "row_index": index, "field": key, "value": _flat_value(value)})
    return rows


def collect_figure_keys(results: dict[str, dict[str, Any]]) -> list[str]:
    """Collect referenced figure keys from result artifacts."""
    keys: list[str] = []
    for record in results.values():
        artifacts = record.get("artifacts", {}) or {}
        primary_key = artifacts.get("report_figure_key")
        if isinstance(primary_key, str) and primary_key:
            if primary_key not in keys:
                keys.append(primary_key)
            # Primary report figure takes precedence; do not auto-include other record snapshots.
            continue
        artifact_keys = artifacts.get("figure_keys", [])
        if not isinstance(artifact_keys, list):
            continue
        for key in artifact_keys:
            if isinstance(key, str) and key not in keys:
                keys.append(key)
    return keys


def _to_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
