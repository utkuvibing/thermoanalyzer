"""Normalized literature-domain models for legal-safe comparison workflows."""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


ALLOWED_ACCESS_CLASSES = {
    "metadata_only",
    "abstract_only",
    "open_access_full_text",
    "user_provided_document",
    "restricted_external",
}

ALLOWED_SUPPORT_LABELS = {
    "supports",
    "partially_supports",
    "contradicts",
    "related_but_inconclusive",
}

ALLOWED_CONFIDENCE_LABELS = {"low", "moderate", "high"}
ALLOWED_VALIDATION_POSTURES = {
    "contextual_only",
    "related_support",
    "alternative_interpretation",
    "non_validating",
}


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _copy_mapping(value: Any) -> dict[str, Any]:
    return copy.deepcopy(value) if isinstance(value, Mapping) else {}


def _to_str_list(value: Any) -> list[str]:
    if value in (None, "", [], (), {}):
        return []
    if isinstance(value, str):
        cleaned = _clean_text(value)
        return [cleaned] if cleaned else []
    if isinstance(value, (list, tuple, set)):
        output: list[str] = []
        for item in value:
            cleaned = _clean_text(item)
            if cleaned:
                output.append(cleaned)
        return output
    cleaned = _clean_text(value)
    return [cleaned] if cleaned else []


def _normalize_access_class(value: Any) -> str:
    token = _clean_text(value).lower() or "metadata_only"
    if token not in ALLOWED_ACCESS_CLASSES:
        return "metadata_only"
    return token


def _normalize_confidence(value: Any, *, default: str = "low") -> str:
    token = _clean_text(value).lower() or default
    if token not in ALLOWED_CONFIDENCE_LABELS:
        return default
    return token


def _normalize_support_label(value: Any) -> str:
    token = _clean_text(value).lower() or "related_but_inconclusive"
    if token not in ALLOWED_SUPPORT_LABELS:
        return "related_but_inconclusive"
    return token


def _normalize_validation_posture(value: Any) -> str:
    token = _clean_text(value).lower() or "non_validating"
    if token not in ALLOWED_VALIDATION_POSTURES:
        return "non_validating"
    return token


@dataclass(slots=True)
class LiteratureClaim:
    claim_id: str
    claim_text: str
    claim_type: str
    modality: str
    strength: str
    evidence_snapshot: dict[str, Any] = field(default_factory=dict)
    uncertainty_notes: list[str] = field(default_factory=list)
    suggested_query_terms: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["claim_id"] = _clean_text(payload.get("claim_id")) or "C1"
        payload["claim_text"] = _clean_text(payload.get("claim_text"))
        payload["claim_type"] = _clean_text(payload.get("claim_type")) or "interpretation"
        payload["modality"] = _clean_text(payload.get("modality")).upper() or "UNKNOWN"
        payload["strength"] = _normalize_confidence(payload.get("strength"), default="low")
        payload["evidence_snapshot"] = _copy_mapping(payload.get("evidence_snapshot"))
        payload["uncertainty_notes"] = _to_str_list(payload.get("uncertainty_notes"))
        payload["suggested_query_terms"] = _to_str_list(payload.get("suggested_query_terms"))
        return payload


@dataclass(slots=True)
class LiteratureSource:
    source_id: str
    title: str
    authors: list[str] = field(default_factory=list)
    journal: str = ""
    year: int | None = None
    doi: str = ""
    url: str = ""
    access_class: str = "metadata_only"
    available_fields: list[str] = field(default_factory=list)
    abstract_text: str = ""
    oa_full_text: str = ""
    source_license_note: str = ""
    citation_text: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source_id"] = _clean_text(payload.get("source_id"))
        payload["title"] = _clean_text(payload.get("title"))
        payload["authors"] = _to_str_list(payload.get("authors"))
        payload["journal"] = _clean_text(payload.get("journal"))
        payload["doi"] = _clean_text(payload.get("doi"))
        payload["url"] = _clean_text(payload.get("url"))
        payload["access_class"] = _normalize_access_class(payload.get("access_class"))
        payload["available_fields"] = _to_str_list(payload.get("available_fields"))
        payload["abstract_text"] = _clean_text(payload.get("abstract_text"))
        payload["oa_full_text"] = _clean_text(payload.get("oa_full_text"))
        payload["source_license_note"] = _clean_text(payload.get("source_license_note"))
        payload["citation_text"] = _clean_text(payload.get("citation_text"))
        payload["provenance"] = _copy_mapping(payload.get("provenance"))
        return payload


@dataclass(slots=True)
class LiteratureComparison:
    claim_id: str
    claim_text: str = ""
    candidate_name: str = ""
    candidate_formula: str = ""
    paper_title: str = ""
    paper_year: int | None = None
    paper_journal: str = ""
    paper_doi: str = ""
    paper_url: str = ""
    provider_id: str = ""
    access_class: str = "metadata_only"
    comparison_note: str = ""
    validation_posture: str = "non_validating"
    query_text: str = ""
    match_status_snapshot: str = ""
    confidence_band_snapshot: str = ""
    retrieved_sources: list[str] = field(default_factory=list)
    support_label: str = "related_but_inconclusive"
    rationale: str = ""
    evidence_used: list[str] = field(default_factory=list)
    citation_ids: list[str] = field(default_factory=list)
    confidence: str = "low"
    sources_considered: int = 0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["claim_id"] = _clean_text(payload.get("claim_id")) or "C1"
        payload["claim_text"] = _clean_text(payload.get("claim_text"))
        payload["candidate_name"] = _clean_text(payload.get("candidate_name"))
        payload["candidate_formula"] = _clean_text(payload.get("candidate_formula"))
        payload["paper_title"] = _clean_text(payload.get("paper_title"))
        payload["paper_journal"] = _clean_text(payload.get("paper_journal"))
        payload["paper_doi"] = _clean_text(payload.get("paper_doi"))
        payload["paper_url"] = _clean_text(payload.get("paper_url"))
        payload["provider_id"] = _clean_text(payload.get("provider_id"))
        payload["access_class"] = _normalize_access_class(payload.get("access_class"))
        payload["comparison_note"] = _clean_text(payload.get("comparison_note"))
        payload["validation_posture"] = _normalize_validation_posture(payload.get("validation_posture"))
        payload["query_text"] = _clean_text(payload.get("query_text"))
        payload["match_status_snapshot"] = _clean_text(payload.get("match_status_snapshot")).lower()
        payload["confidence_band_snapshot"] = _clean_text(payload.get("confidence_band_snapshot")).lower()
        payload["retrieved_sources"] = _to_str_list(payload.get("retrieved_sources"))
        payload["support_label"] = _normalize_support_label(payload.get("support_label"))
        payload["rationale"] = _clean_text(payload.get("rationale"))
        payload["evidence_used"] = _to_str_list(payload.get("evidence_used"))
        payload["citation_ids"] = _to_str_list(payload.get("citation_ids"))
        payload["confidence"] = _normalize_confidence(payload.get("confidence"), default="low")
        try:
            payload["paper_year"] = int(payload.get("paper_year")) if payload.get("paper_year") not in (None, "") else None
        except (TypeError, ValueError):
            payload["paper_year"] = None
        try:
            payload["sources_considered"] = int(payload.get("sources_considered") or 0)
        except (TypeError, ValueError):
            payload["sources_considered"] = 0
        return payload


@dataclass(slots=True)
class CitationEntry:
    citation_id: str
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    journal: str = ""
    doi: str = ""
    url: str = ""
    access_class: str = "metadata_only"
    citation_text: str = ""
    source_license_note: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["citation_id"] = _clean_text(payload.get("citation_id"))
        payload["title"] = _clean_text(payload.get("title"))
        payload["authors"] = _to_str_list(payload.get("authors"))
        payload["journal"] = _clean_text(payload.get("journal"))
        payload["doi"] = _clean_text(payload.get("doi"))
        payload["url"] = _clean_text(payload.get("url"))
        payload["access_class"] = _normalize_access_class(payload.get("access_class"))
        payload["citation_text"] = _clean_text(payload.get("citation_text"))
        payload["source_license_note"] = _clean_text(payload.get("source_license_note"))
        payload["provenance"] = _copy_mapping(payload.get("provenance"))
        return payload


@dataclass(slots=True)
class LiteratureContext:
    mode: str = "metadata_abstract_oa_only"
    comparison_run_id: str = ""
    provider_scope: list[str] = field(default_factory=list)
    result_id: str = ""
    analysis_type: str = ""
    provider_request_ids: list[str] = field(default_factory=list)
    provider_result_source: str = ""
    query_count: int = 0
    source_count: int = 0
    citation_count: int = 0
    accessible_source_count: int = 0
    restricted_source_count: int = 0
    metadata_only_evidence: bool = False
    restricted_content_used: bool = False
    generated_at_utc: str = ""
    query_text: str = ""
    candidate_name: str = ""
    candidate_formula: str = ""
    candidate_id: str = ""
    candidate_display_name: str = ""
    match_status_snapshot: str = ""
    confidence_band_snapshot: str = ""
    top_candidate_score_snapshot: float | None = None
    shared_peak_count_snapshot: int | None = None
    coverage_ratio_snapshot: float | None = None
    weighted_overlap_score_snapshot: float | None = None
    candidate_provider_snapshot: str = ""
    candidate_result_source_snapshot: str = ""
    real_literature_available: bool = False
    fixture_fallback_used: bool = False
    query_rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mode"] = _clean_text(payload.get("mode")) or "metadata_abstract_oa_only"
        payload["comparison_run_id"] = _clean_text(payload.get("comparison_run_id"))
        payload["provider_scope"] = _to_str_list(payload.get("provider_scope"))
        payload["result_id"] = _clean_text(payload.get("result_id"))
        payload["analysis_type"] = _clean_text(payload.get("analysis_type")).upper()
        payload["provider_request_ids"] = _to_str_list(payload.get("provider_request_ids"))
        payload["provider_result_source"] = _clean_text(payload.get("provider_result_source"))
        try:
            payload["query_count"] = int(payload.get("query_count") or 0)
        except (TypeError, ValueError):
            payload["query_count"] = 0
        for key in ("source_count", "citation_count", "accessible_source_count", "restricted_source_count"):
            try:
                payload[key] = int(payload.get(key) or 0)
            except (TypeError, ValueError):
                payload[key] = 0
        payload["metadata_only_evidence"] = bool(payload.get("metadata_only_evidence"))
        payload["restricted_content_used"] = bool(payload.get("restricted_content_used"))
        payload["generated_at_utc"] = _clean_text(payload.get("generated_at_utc"))
        payload["query_text"] = _clean_text(payload.get("query_text"))
        payload["candidate_name"] = _clean_text(payload.get("candidate_name"))
        payload["candidate_formula"] = _clean_text(payload.get("candidate_formula"))
        payload["candidate_id"] = _clean_text(payload.get("candidate_id"))
        payload["candidate_display_name"] = _clean_text(payload.get("candidate_display_name"))
        payload["match_status_snapshot"] = _clean_text(payload.get("match_status_snapshot")).lower()
        payload["confidence_band_snapshot"] = _clean_text(payload.get("confidence_band_snapshot")).lower()
        for key in ("top_candidate_score_snapshot", "coverage_ratio_snapshot", "weighted_overlap_score_snapshot"):
            try:
                payload[key] = float(payload.get(key)) if payload.get(key) not in (None, "") else None
            except (TypeError, ValueError):
                payload[key] = None
        try:
            payload["shared_peak_count_snapshot"] = (
                int(payload.get("shared_peak_count_snapshot"))
                if payload.get("shared_peak_count_snapshot") not in (None, "")
                else None
            )
        except (TypeError, ValueError):
            payload["shared_peak_count_snapshot"] = None
        payload["candidate_provider_snapshot"] = _clean_text(payload.get("candidate_provider_snapshot"))
        payload["candidate_result_source_snapshot"] = _clean_text(payload.get("candidate_result_source_snapshot"))
        payload["real_literature_available"] = bool(payload.get("real_literature_available"))
        payload["fixture_fallback_used"] = bool(payload.get("fixture_fallback_used"))
        payload["query_rationale"] = _clean_text(payload.get("query_rationale"))
        return payload


def normalize_literature_context(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, Mapping) else {}
    if not source:
        return {}
    return LiteratureContext(
        mode=source.get("mode", "metadata_abstract_oa_only"),
        comparison_run_id=source.get("comparison_run_id", ""),
        provider_scope=source.get("provider_scope", []),
        result_id=source.get("result_id", ""),
        analysis_type=source.get("analysis_type", ""),
        provider_request_ids=source.get("provider_request_ids", []),
        provider_result_source=source.get("provider_result_source", ""),
        query_count=source.get("query_count", 0),
        source_count=source.get("source_count", 0),
        citation_count=source.get("citation_count", 0),
        accessible_source_count=source.get("accessible_source_count", 0),
        restricted_source_count=source.get("restricted_source_count", 0),
        metadata_only_evidence=source.get("metadata_only_evidence", False),
        restricted_content_used=source.get("restricted_content_used", False),
        generated_at_utc=source.get("generated_at_utc", ""),
        query_text=source.get("query_text", ""),
        candidate_name=source.get("candidate_name", ""),
        candidate_formula=source.get("candidate_formula", ""),
        candidate_id=source.get("candidate_id", ""),
        candidate_display_name=source.get("candidate_display_name", ""),
        match_status_snapshot=source.get("match_status_snapshot", ""),
        confidence_band_snapshot=source.get("confidence_band_snapshot", ""),
        top_candidate_score_snapshot=source.get("top_candidate_score_snapshot"),
        shared_peak_count_snapshot=source.get("shared_peak_count_snapshot"),
        coverage_ratio_snapshot=source.get("coverage_ratio_snapshot"),
        weighted_overlap_score_snapshot=source.get("weighted_overlap_score_snapshot"),
        candidate_provider_snapshot=source.get("candidate_provider_snapshot", ""),
        candidate_result_source_snapshot=source.get("candidate_result_source_snapshot", ""),
        real_literature_available=source.get("real_literature_available", False),
        fixture_fallback_used=source.get("fixture_fallback_used", False),
        query_rationale=source.get("query_rationale", ""),
    ).to_dict()


def normalize_literature_claims(value: Any) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, item in enumerate(value or [], start=1):
        source = item if isinstance(item, Mapping) else {"claim_text": item}
        output.append(
            LiteratureClaim(
                claim_id=source.get("claim_id") or source.get("id") or f"C{index}",
                claim_text=source.get("claim_text") or source.get("claim") or "",
                claim_type=source.get("claim_type") or "interpretation",
                modality=source.get("modality") or "UNKNOWN",
                strength=source.get("strength") or "low",
                evidence_snapshot=_copy_mapping(source.get("evidence_snapshot")),
                uncertainty_notes=_to_str_list(source.get("uncertainty_notes")),
                suggested_query_terms=_to_str_list(source.get("suggested_query_terms")),
            ).to_dict()
        )
    return output


def normalize_literature_sources(value: Any) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for item in value or []:
        if not isinstance(item, Mapping):
            continue
        output.append(
            LiteratureSource(
                source_id=item.get("source_id") or "",
                title=item.get("title") or "",
                authors=_to_str_list(item.get("authors")),
                journal=item.get("journal") or "",
                year=item.get("year"),
                doi=item.get("doi") or "",
                url=item.get("url") or "",
                access_class=item.get("access_class") or "metadata_only",
                available_fields=_to_str_list(item.get("available_fields")),
                abstract_text=item.get("abstract_text") or "",
                oa_full_text=item.get("oa_full_text") or "",
                source_license_note=item.get("source_license_note") or "",
                citation_text=item.get("citation_text") or "",
                provenance=_copy_mapping(item.get("provenance")),
            ).to_dict()
        )
    return output


def normalize_literature_comparisons(value: Any) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, item in enumerate(value or [], start=1):
        source = item if isinstance(item, Mapping) else {"claim_id": f"C{index}", "rationale": item}
        output.append(
            LiteratureComparison(
                claim_id=source.get("claim_id") or f"C{index}",
                claim_text=source.get("claim_text") or "",
                candidate_name=source.get("candidate_name") or "",
                candidate_formula=source.get("candidate_formula") or "",
                paper_title=source.get("paper_title") or "",
                paper_year=source.get("paper_year"),
                paper_journal=source.get("paper_journal") or "",
                paper_doi=source.get("paper_doi") or "",
                paper_url=source.get("paper_url") or "",
                provider_id=source.get("provider_id") or "",
                access_class=source.get("access_class") or "metadata_only",
                comparison_note=source.get("comparison_note") or "",
                validation_posture=source.get("validation_posture") or "non_validating",
                query_text=source.get("query_text") or "",
                match_status_snapshot=source.get("match_status_snapshot") or "",
                confidence_band_snapshot=source.get("confidence_band_snapshot") or "",
                retrieved_sources=_to_str_list(source.get("retrieved_sources")),
                support_label=source.get("support_label") or "related_but_inconclusive",
                rationale=source.get("rationale") or "",
                evidence_used=_to_str_list(source.get("evidence_used")),
                citation_ids=_to_str_list(source.get("citation_ids")),
                confidence=source.get("confidence") or "low",
                sources_considered=source.get("sources_considered") or 0,
            ).to_dict()
        )
    return output


def normalize_citations(value: Any) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, item in enumerate(value or [], start=1):
        source = item if isinstance(item, Mapping) else {"citation_text": item}
        output.append(
            CitationEntry(
                citation_id=source.get("citation_id") or f"ref{index}",
                title=source.get("title") or "",
                authors=_to_str_list(source.get("authors")),
                year=source.get("year"),
                journal=source.get("journal") or "",
                doi=source.get("doi") or "",
                url=source.get("url") or "",
                access_class=source.get("access_class") or "metadata_only",
                citation_text=source.get("citation_text") or "",
                source_license_note=source.get("source_license_note") or "",
                provenance=_copy_mapping(source.get("provenance")),
            ).to_dict()
        )
    return output
