"""Deterministic XRD candidate-centered literature query builder."""

from __future__ import annotations

import copy
from typing import Any, Mapping


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _clean_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_int(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _top_row(record: Mapping[str, Any]) -> dict[str, Any]:
    rows = record.get("rows") or []
    for item in rows:
        if isinstance(item, Mapping):
            return dict(item)
    return {}


def _is_weak_candidate_label(value: str) -> bool:
    token = _clean_text(value)
    if not token:
        return True
    lowered = token.lower()
    return lowered in {"unknown", "n/a", "not recorded", "candidate", "phase"} or len(token) < 3


def _candidate_label(summary: Mapping[str, Any]) -> str:
    for key in (
        "top_candidate_display_name_unicode",
        "top_candidate_name",
        "top_candidate_formula",
        "top_candidate_id",
    ):
        value = _clean_text(summary.get(key))
        if value and not _is_weak_candidate_label(value):
            return value
    return ""


def _query_text(candidate_label: str, formula: str) -> str:
    if candidate_label:
        base = f"\"{candidate_label}\" XRD powder diffraction phase identification crystal structure"
        if formula and formula.casefold() != candidate_label.casefold():
            return f"{base} {formula}".strip()
        return base
    if formula:
        return f"\"{formula}\" XRD powder diffraction phase identification crystal structure"
    return "XRD phase identification diffraction pattern"


def _query_rationale(
    *,
    candidate_label: str,
    formula: str,
    match_status: str,
    shared_peaks: int | None,
) -> str:
    if candidate_label:
        rationale = f"The literature search is centered on the top-ranked XRD candidate '{candidate_label}'."
    elif formula:
        rationale = (
            "The top-ranked XRD candidate label was weak or unavailable, so the literature search falls back to the candidate formula."
        )
    else:
        rationale = (
            "The result did not expose a strong candidate identifier, so the literature search falls back to generic XRD phase-identification terms."
        )

    if match_status == "no_match":
        rationale += " The accepted match status remains no_match, so literature can only provide candidate-level context."
    elif shared_peaks is not None:
        rationale += f" The current result reports about {shared_peaks} shared peaks for the top-ranked candidate."
    return rationale


def build_xrd_literature_query(record: Mapping[str, Any]) -> dict[str, Any]:
    summary = dict(record.get("summary") or {})
    top_row = _top_row(record)
    top_evidence = dict(top_row.get("evidence") or {}) if isinstance(top_row.get("evidence"), Mapping) else {}

    candidate_label = _candidate_label(summary)
    formula = _clean_text(summary.get("top_candidate_formula"))
    match_status = _clean_text(summary.get("match_status")).lower() or "no_match"
    confidence_band = _clean_text(summary.get("confidence_band")).lower() or "no_match"
    shared_peaks = _clean_int(summary.get("top_candidate_shared_peak_count"))

    evidence_snapshot = {
        "top_candidate_name": _clean_text(summary.get("top_candidate_name")),
        "top_candidate_display_name": _clean_text(summary.get("top_candidate_display_name_unicode") or summary.get("top_candidate_display_name")),
        "top_candidate_formula": formula,
        "top_candidate_id": _clean_text(summary.get("top_candidate_id")),
        "match_status": match_status,
        "confidence_band": confidence_band,
        "top_candidate_score": _clean_float(summary.get("top_candidate_score")),
        "shared_peak_count": shared_peaks,
        "coverage_ratio": _clean_float(summary.get("top_candidate_coverage_ratio")),
        "weighted_overlap_score": _clean_float(summary.get("top_candidate_weighted_overlap_score")),
        "candidate_provider": _clean_text(summary.get("top_candidate_provider")),
        "candidate_result_source": _clean_text(summary.get("library_result_source")),
        "library_provider_scope": copy.deepcopy(summary.get("library_provider_scope") or []),
        "row_evidence": copy.deepcopy(top_evidence),
    }

    return {
        "query_text": _query_text(candidate_label, formula),
        "candidate_name": _clean_text(summary.get("top_candidate_name")) or candidate_label or formula,
        "candidate_formula": formula,
        "candidate_id": _clean_text(summary.get("top_candidate_id")),
        "candidate_display_name": _clean_text(summary.get("top_candidate_display_name_unicode") or summary.get("top_candidate_display_name") or candidate_label),
        "query_rationale": _query_rationale(
            candidate_label=candidate_label,
            formula=formula,
            match_status=match_status,
            shared_peaks=shared_peaks,
        ),
        "match_status_snapshot": match_status,
        "confidence_band_snapshot": confidence_band,
        "evidence_snapshot": evidence_snapshot,
    }
