"""Literature comparison engine for legal-safe, citation-backed result review."""

from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

from core.citation_formatter import build_citation_entry
from core.literature_claims import build_claim_queries, extract_literature_claims
from core.literature_models import (
    LiteratureClaim,
    LiteratureComparison,
    LiteratureContext,
    normalize_citations,
    normalize_literature_claims,
    normalize_literature_comparisons,
    normalize_literature_context,
    normalize_literature_sources,
)
from core.literature_provider import FixtureLiteratureProvider, LiteratureProvider
from core.literature_provider import citation_identity_key, merge_literature_candidates
from core.xrd_literature_query_builder import build_xrd_literature_query


HINT_TO_LABEL = {
    "support": "supports",
    "supports": "supports",
    "partial": "partially_supports",
    "partially_supports": "partially_supports",
    "contradict": "contradicts",
    "contradicts": "contradicts",
    "related": "related_but_inconclusive",
    "related_but_inconclusive": "related_but_inconclusive",
}
SUPPORT_PHRASES = ("supports", "consistent with", "agreement", "aligned with")
PARTIAL_PHRASES = ("partial", "tentative", "limited support", "follow-up verification")
CONTRADICT_PHRASES = ("contradicts", "inconsistent", "not consistent", "alternative phase", "secondary phase")
REAL_BIBLIOGRAPHIC_PROVIDERS = {"metadata_api_provider", "openalex_like_provider"}


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _clean_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_list(value: Any) -> list[Any]:
    if value in (None, "", [], (), {}):
        return []
    if isinstance(value, str):
        cleaned = _clean_text(value)
        return [cleaned] if cleaned else []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _tokenize(value: str) -> list[str]:
    cleaned = "".join(ch if ch.isalnum() else " " for ch in str(value or "").lower())
    return [token for token in cleaned.split() if len(token) >= 3]


def _brief_evidence(text: str, *, max_chars: int = 180) -> str:
    sentence = _clean_text(text).split(".")[0].strip()
    if not sentence:
        sentence = _clean_text(text)
    if len(sentence) <= max_chars:
        return sentence
    return f"{sentence[: max_chars - 1].rstrip()}…"


def _first_non_empty(mapping: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        cleaned = _clean_text(mapping.get(key))
        if cleaned:
            return cleaned
    return ""


def _user_document_provenance(document: Mapping[str, Any], *, index: int) -> dict[str, Any]:
    provenance = dict(document.get("provenance") or {}) if isinstance(document.get("provenance"), Mapping) else {}
    normalized: dict[str, Any] = {
        "provider_id": "user_documents",
        "result_source": "user_provided_document",
        "document_index": index,
    }
    comparison_hint = _clean_text(document.get("comparison_hint") or provenance.get("comparison_hint")).lower()
    if comparison_hint:
        normalized["comparison_hint"] = comparison_hint
    keywords = [
        _clean_text(item)
        for item in (_as_list(document.get("keywords")) + _as_list(provenance.get("keywords")))
        if _clean_text(item)
    ]
    if keywords:
        deduped_keywords: list[str] = []
        for item in keywords:
            if item not in deduped_keywords:
                deduped_keywords.append(item)
        normalized["keywords"] = deduped_keywords[:12]
    modalities = [
        _clean_text(item).upper()
        for item in (_as_list(document.get("modalities")) + _as_list(provenance.get("modalities")))
        if _clean_text(item)
    ]
    if modalities:
        deduped_modalities: list[str] = []
        for item in modalities:
            if item not in deduped_modalities:
                deduped_modalities.append(item)
        normalized["modalities"] = deduped_modalities
    for key in ("document_id", "document_type", "file_name", "source_url", "url"):
        value = _clean_text(document.get(key) or provenance.get(key))
        if value:
            normalized[key] = value
    return normalized


def _normalize_user_document_sources(user_documents: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized_sources: list[dict[str, Any]] = []
    for index, item in enumerate(user_documents or [], start=1):
        if not isinstance(item, Mapping):
            continue
        source_id = _first_non_empty(item, "source_id", "document_id", "id") or f"user_document_{index}"
        title = _first_non_empty(item, "title", "document_title", "name", "file_name") or f"User document {index}"
        accessible_text = _first_non_empty(
            item,
            "text",
            "content",
            "body",
            "document_text",
            "accessible_text",
            "oa_full_text",
            "abstract_text",
            "excerpt",
            "summary",
        )
        normalized_sources.extend(
            normalize_literature_sources(
                [
                    {
                        "source_id": source_id,
                        "title": title,
                        "authors": _as_list(item.get("authors")),
                        "journal": _first_non_empty(item, "journal", "publisher", "source"),
                        "year": _clean_int(item.get("year")),
                        "doi": _first_non_empty(item, "doi"),
                        "url": _first_non_empty(item, "url", "source_url"),
                        "access_class": "user_provided_document",
                        "available_fields": ["metadata", "user_provided_document"],
                        "abstract_text": "",
                        "oa_full_text": accessible_text,
                        "source_license_note": _first_non_empty(item, "source_license_note") or "user_provided_document",
                        "citation_text": _first_non_empty(item, "citation_text"),
                        "provenance": _user_document_provenance(item, index=index),
                    }
                ]
            )
        )
    return normalized_sources


def _search_filters_for_claim(claim: Mapping[str, Any], filters: Mapping[str, Any] | None) -> dict[str, Any]:
    search_filters = copy.deepcopy(dict(filters or {}))
    requested_modalities = [
        _clean_text(item).upper()
        for item in _as_list(search_filters.get("modalities"))
        if _clean_text(item)
    ]
    modality = _clean_text(claim.get("modality")).upper()
    if modality and modality not in requested_modalities:
        requested_modalities.insert(0, modality)
    if requested_modalities:
        search_filters["modalities"] = requested_modalities
    search_filters.setdefault("top_k", 5)
    return search_filters


def _fetch_accessible_text(source: Mapping[str, Any], *, provider: LiteratureProvider) -> dict[str, Any] | None:
    access_class = _clean_text(source.get("access_class")).lower()
    if access_class == "restricted_external":
        return None
    if access_class == "user_provided_document":
        text = _clean_text(source.get("oa_full_text") or source.get("abstract_text"))
        if not text:
            return None
        return {"source_id": source.get("source_id"), "text": text, "field": "user_provided_document", "access_class": access_class}
    return provider.fetch_accessible_text(dict(source))


def _source_overlap(claim: Mapping[str, Any], source: Mapping[str, Any], text: str) -> int:
    tokens = {token for token in _tokenize(" ".join(claim.get("suggested_query_terms") or []))}
    if not tokens:
        tokens = set(_tokenize(str(claim.get("claim_text") or "")))
    searchable = " ".join([str(source.get("title") or ""), text]).lower()
    return sum(1 for token in tokens if token in searchable)


def _fallback_label(*, overlap: int, text: str) -> str:
    lowered = text.lower()
    if any(phrase in lowered for phrase in CONTRADICT_PHRASES) and overlap >= 1:
        return "contradicts"
    if any(phrase in lowered for phrase in PARTIAL_PHRASES) and overlap >= 1:
        return "partially_supports"
    if any(phrase in lowered for phrase in SUPPORT_PHRASES) and overlap >= 2:
        return "supports"
    return "related_but_inconclusive"


def _confidence_for_label(label: str, *, access_field: str, citation_count: int) -> str:
    if label == "supports" and access_field in {"oa_full_text", "user_provided_document"} and citation_count >= 2:
        return "high"
    if label in {"supports", "partially_supports", "contradicts"}:
        return "moderate"
    return "low"


def _rationale_for_label(label: str, *, access_field: str) -> str:
    access_note = (
        "Reasoning used open-access or user-provided full text."
        if access_field in {"oa_full_text", "user_provided_document"}
        else "Reasoning was limited to abstract-level accessible text."
    )
    if label == "supports":
        return f"Accessible literature supports the claim in a cautionary, non-definitive way. {access_note}"
    if label == "partially_supports":
        return f"Accessible literature is partly consistent with the claim, but evidence is limited or mixed. {access_note}"
    if label == "contradicts":
        return f"Accessible literature points toward an alternative interpretation and does not support the current claim. {access_note}"
    return (
        "Accessible literature remains related but inconclusive for this claim; additional confirmatory experiments may be required. "
        f"{access_note}"
    )


def _evaluate_source(claim: Mapping[str, Any], source: Mapping[str, Any], accessible: Mapping[str, Any]) -> dict[str, Any]:
    text = _clean_text(accessible.get("text"))
    overlap = _source_overlap(claim, source, text)
    hint = _clean_text((source.get("provenance") or {}).get("comparison_hint")).lower()
    label = HINT_TO_LABEL.get(hint) if hint and overlap >= 1 else None
    if not label:
        label = _fallback_label(overlap=overlap, text=text)
    return {
        "source_id": source.get("source_id"),
        "label": label,
        "score": overlap + {"supports": 6, "partially_supports": 4, "contradicts": 5, "related_but_inconclusive": 1}[label],
        "evidence": _brief_evidence(text),
        "access_field": accessible.get("field") or "abstract_text",
    }


def _search_result_identity(source: Mapping[str, Any]) -> str:
    identity = citation_identity_key(source)
    if identity.startswith("provider_source:"):
        provider_id = _clean_text((source.get("provenance") or {}).get("provider_id")).lower()
        source_id = _clean_text(source.get("source_id")).lower()
        return f"provider_source:{provider_id}|{source_id}"
    return identity


def _provider_request_ids(provider: LiteratureProvider) -> list[str]:
    request_ids = [_clean_text(item) for item in getattr(provider, "last_request_ids", []) if _clean_text(item)]
    if request_ids:
        return request_ids
    request_id = _clean_text(getattr(provider, "last_request_id", ""))
    return [request_id] if request_id else []


def _provider_result_source(provider: LiteratureProvider, *, provider_scope: list[str]) -> str:
    if len(provider_scope) > 1:
        return "multi_provider_search"
    token = _clean_text(getattr(provider, "provider_result_source", ""))
    return token or "metadata_abstract_oa_only"


def _compare_generic_result_to_literature(
    record: Mapping[str, Any],
    *,
    provider: LiteratureProvider,
    provider_scope: list[str],
    max_claims: int,
    filters: Mapping[str, Any] | None,
    user_documents: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    comparison_run_id = f"litcmp_{uuid.uuid4().hex[:12]}"
    claims = extract_literature_claims(record, max_claims=max(1, int(max_claims or 1)))
    normalized_user_documents = _normalize_user_document_sources(user_documents)

    query_count = 0
    comparisons: list[dict[str, Any]] = []
    citations_by_identity: dict[str, dict[str, Any]] = {}
    provider_request_ids: list[str] = []
    all_sources_seen: dict[str, dict[str, Any]] = {
        _search_result_identity(source): copy.deepcopy(source)
        for source in normalized_user_documents
        if _search_result_identity(source)
    }
    provider_result_sources = {
        _clean_text((source.get("provenance") or {}).get("result_source"))
        for source in normalized_user_documents
        if _clean_text((source.get("provenance") or {}).get("result_source"))
    }
    accessible_source_ids: set[str] = set()
    restricted_source_ids: set[str] = set()
    used_access_fields: set[str] = set()

    for claim in claims:
        search_results: dict[str, dict[str, Any]] = {
            _search_result_identity(source): copy.deepcopy(source)
            for source in normalized_user_documents
            if _search_result_identity(source)
        }
        claim_filters = _search_filters_for_claim(claim, filters)
        for query in build_claim_queries(claim):
            for candidate in provider.search(query, filters=claim_filters):
                source_key = _search_result_identity(candidate)
                if not source_key:
                    continue
                if source_key in search_results:
                    search_results[source_key] = merge_literature_candidates(search_results[source_key], candidate)
                else:
                    search_results[source_key] = copy.deepcopy(candidate)
                if source_key in all_sources_seen:
                    all_sources_seen[source_key] = merge_literature_candidates(all_sources_seen[source_key], candidate)
                else:
                    all_sources_seen[source_key] = copy.deepcopy(candidate)
                result_source = _clean_text((candidate.get("provenance") or {}).get("result_source"))
                if result_source:
                    provider_result_sources.add(result_source)
            request_ids_for_query = _provider_request_ids(provider)
            query_count += max(1, len(request_ids_for_query))
            for request_id in request_ids_for_query:
                if request_id and request_id not in provider_request_ids:
                    provider_request_ids.append(request_id)

        evaluations: list[dict[str, Any]] = []
        for source in search_results.values():
            source_key = _search_result_identity(source)
            accessible = _fetch_accessible_text(source, provider=provider)
            if accessible is None:
                if str(source.get("access_class") or "").lower() == "restricted_external":
                    restricted_source_ids.add(source_key)
                continue
            accessible_source_ids.add(source_key)
            used_access_fields.add(_clean_text(accessible.get("field")).lower())
            evaluation = _evaluate_source(claim, source, accessible)
            evaluation["source_identity"] = source_key
            evaluations.append(evaluation)

        if evaluations:
            evaluations.sort(key=lambda item: (-item["score"], str(item.get("source_id") or "")))
            labels = {item["label"] for item in evaluations}
            best = evaluations[0]
            label = best["label"]
            if "supports" in labels and "contradicts" in labels and label == "supports":
                label = "partially_supports"
            citation_sources = [item for item in evaluations if item["label"] == best["label"]][:2]
            if label == "partially_supports" and best["label"] != "partially_supports":
                citation_sources = evaluations[:2]

            citation_ids: list[str] = []
            evidence_used: list[str] = []
            access_field = best["access_field"]
            for source_eval in citation_sources:
                source = search_results.get(str(source_eval["source_identity"] or ""))
                if source is None:
                    continue
                citation_key = citation_identity_key(source)
                if citation_key not in citations_by_identity:
                    citation_id = f"ref{len(citations_by_identity) + 1}"
                    citations_by_identity[citation_key] = build_citation_entry(source, citation_id=citation_id)
                citation_ids.append(citations_by_identity[citation_key]["citation_id"])
                evidence_used.append(source_eval["evidence"])

            comparisons.append(
                LiteratureComparison(
                    claim_id=str(claim.get("claim_id") or ""),
                    claim_text=str(claim.get("claim_text") or ""),
                    retrieved_sources=sorted(
                        _clean_text(item.get("source_id"))
                        for item in search_results.values()
                        if _clean_text(item.get("source_id"))
                    ),
                    support_label=label,
                    rationale=_rationale_for_label(label, access_field=access_field),
                    evidence_used=evidence_used,
                    citation_ids=citation_ids,
                    confidence=_confidence_for_label(label, access_field=access_field, citation_count=len(citation_ids)),
                    sources_considered=len(search_results),
                ).to_dict()
            )
        else:
            comparisons.append(
                LiteratureComparison(
                    claim_id=str(claim.get("claim_id") or ""),
                    claim_text=str(claim.get("claim_text") or ""),
                    retrieved_sources=sorted(
                        _clean_text(item.get("source_id"))
                        for item in search_results.values()
                        if _clean_text(item.get("source_id"))
                    ),
                    support_label="related_but_inconclusive",
                    rationale=(
                        "Insufficient literature evidence was available from metadata, abstracts, open-access text, "
                        "or user-provided documents. Closed-access full text was not used."
                    ),
                    evidence_used=[],
                    citation_ids=[],
                    confidence="low",
                    sources_considered=len(search_results),
                ).to_dict()
            )

    context = LiteratureContext(
        mode="metadata_abstract_oa_only",
        comparison_run_id=comparison_run_id,
        provider_scope=provider_scope,
        result_id=_clean_text(record.get("id")),
        analysis_type=_clean_text(record.get("analysis_type")).upper(),
        provider_request_ids=provider_request_ids,
        provider_result_source=(
            "multi_provider_search"
            if len(provider_scope) > 1
            else (sorted(provider_result_sources)[0] if len(provider_result_sources) == 1 else _provider_result_source(provider, provider_scope=provider_scope))
        ),
        query_count=query_count,
        source_count=len(all_sources_seen),
        citation_count=len(citations_by_identity),
        accessible_source_count=len(accessible_source_ids),
        restricted_source_count=len(restricted_source_ids),
        metadata_only_evidence=bool(accessible_source_ids) and not (used_access_fields & {"oa_full_text", "user_provided_document"}),
        restricted_content_used=False,
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
    ).to_dict()

    citations = sorted(citations_by_identity.values(), key=lambda item: item["citation_id"])
    return {
        "literature_context": normalize_literature_context(context),
        "literature_claims": claims,
        "literature_comparisons": normalize_literature_comparisons(comparisons),
        "citations": normalize_citations(citations),
    }


def _xrd_candidate_claims(
    record: Mapping[str, Any],
    query_payload: Mapping[str, Any],
    *,
    max_claims: int,
) -> list[dict[str, Any]]:
    summary = dict(record.get("summary") or {})
    candidate = _clean_text(query_payload.get("candidate_display_name") or query_payload.get("candidate_name")) or "the top-ranked candidate"
    match_status = _clean_text(summary.get("match_status")).lower() or "no_match"
    confidence_band = _clean_text(summary.get("confidence_band")).lower() or "no_match"
    warning_reason = _clean_text(summary.get("top_candidate_reason_below_threshold"))

    claims: list[dict[str, Any]] = []
    if match_status == "no_match":
        claims.append(
            LiteratureClaim(
                claim_id="C1",
                claim_text=f"The current XRD result remains a no_match screening outcome; literature can only provide context around the top-ranked candidate {candidate}.",
                claim_type="cautionary_interpretation",
                modality="XRD",
                strength="low",
                evidence_snapshot=dict(query_payload.get("evidence_snapshot") or {}),
                uncertainty_notes=[warning_reason] if warning_reason else [],
                suggested_query_terms=[_clean_text(query_payload.get("candidate_name")), _clean_text(query_payload.get("candidate_formula")), "XRD"],
            ).to_dict()
        )
    else:
        claims.append(
            LiteratureClaim(
                claim_id="C1",
                claim_text=f"The top-ranked XRD candidate is {candidate}, but the result remains qualitative and requires cautious interpretation.",
                claim_type="interpretation",
                modality="XRD",
                strength="low" if confidence_band == "low" else "moderate",
                evidence_snapshot=dict(query_payload.get("evidence_snapshot") or {}),
                uncertainty_notes=[warning_reason] if warning_reason else [],
                suggested_query_terms=[_clean_text(query_payload.get("candidate_name")), _clean_text(query_payload.get("candidate_formula")), "XRD"],
            ).to_dict()
        )
    if max_claims > 1 and warning_reason:
        claims.append(
            LiteratureClaim(
                claim_id="C2",
                claim_text=f"The current XRD evidence for {candidate} remains below a definitive phase-validation threshold.",
                claim_type="cautionary_interpretation",
                modality="XRD",
                strength="low",
                evidence_snapshot=dict(query_payload.get("evidence_snapshot") or {}),
                uncertainty_notes=[warning_reason],
                suggested_query_terms=[_clean_text(query_payload.get("candidate_name")), _clean_text(query_payload.get("candidate_formula")), "powder diffraction"],
            ).to_dict()
        )
    return normalize_literature_claims(claims[: max(1, int(max_claims or 1))])


def _xrd_candidate_tokens(query_payload: Mapping[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for value in (
        query_payload.get("candidate_display_name"),
        query_payload.get("candidate_name"),
        query_payload.get("candidate_formula"),
        query_payload.get("candidate_id"),
    ):
        cleaned = _clean_text(value)
        if not cleaned:
            continue
        tokens.add(cleaned.lower())
        tokens.update(_tokenize(cleaned))
    return {token for token in tokens if token}


def _xrd_source_text(source: Mapping[str, Any], accessible: Mapping[str, Any] | None) -> str:
    parts = [
        _clean_text(source.get("title")),
        _clean_text(source.get("journal")),
        _clean_text(source.get("abstract_text")),
        _clean_text(source.get("oa_full_text")),
        _clean_text((source.get("provenance") or {}).get("comparison_hint")),
    ]
    if accessible is not None:
        parts.append(_clean_text(accessible.get("text")))
    return " ".join(part for part in parts if part).strip()


def _xrd_candidate_overlap(source_text: str, candidate_tokens: set[str]) -> int:
    lowered = source_text.lower()
    return sum(1 for token in candidate_tokens if token and token in lowered)


def _xrd_validation_posture(
    *,
    match_status: str,
    confidence_band: str,
    access_class: str,
    overlap: int,
    source_text: str,
    hint: str,
) -> str:
    lowered = source_text.lower()
    if match_status == "no_match":
        return "contextual_only"
    if hint in {"contradicts", "contradict"} or any(phrase in lowered for phrase in CONTRADICT_PHRASES):
        return "alternative_interpretation"
    if overlap >= 2 and confidence_band not in {"low", "no_match", "not_run"} and access_class in {"open_access_full_text", "user_provided_document", "abstract_only"}:
        return "related_support"
    return "non_validating"


def _xrd_support_label_for_posture(posture: str) -> str:
    if posture == "related_support":
        return "partially_supports"
    if posture == "alternative_interpretation":
        return "contradicts"
    return "related_but_inconclusive"


def _xrd_comparison_confidence(posture: str, access_class: str, overlap: int) -> str:
    if posture == "related_support" and access_class in {"open_access_full_text", "user_provided_document"} and overlap >= 2:
        return "moderate"
    if posture == "alternative_interpretation" and overlap >= 1:
        return "moderate"
    return "low"


def _xrd_comparison_note(*, candidate: str, match_status: str, confidence_band: str, posture: str) -> str:
    if match_status == "no_match":
        return (
            f"This paper discusses XRD characterization of {candidate}. The current result remains a no_match screening outcome and the paper does not validate a phase call for the present sample."
        )
    if posture == "alternative_interpretation":
        return (
            "This source is related to the candidate context, but it does not provide validating support for the current pattern and may indicate an alternative interpretation."
        )
    if posture == "related_support" and confidence_band not in {"low", "no_match"}:
        return (
            f"This paper discusses XRD characterization of {candidate}. It is relevant to the top-ranked candidate, but the present result should still be interpreted within qualitative phase-screening limits."
        )
    return "This source is relevant to the top-ranked candidate, but the current XRD evidence remains limited and non-validating."


def _is_fixture_source(source: Mapping[str, Any]) -> bool:
    provenance = dict(source.get("provenance") or {})
    provider_id = _clean_text(provenance.get("provider_id")).lower()
    result_source = _clean_text(provenance.get("result_source")).lower()
    return provider_id == "fixture_provider" or result_source == "fixture_search"


def _compare_xrd_candidate_to_literature(
    record: Mapping[str, Any],
    *,
    provider: LiteratureProvider,
    provider_scope: list[str],
    max_claims: int,
    filters: Mapping[str, Any] | None,
    user_documents: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    comparison_run_id = f"litcmp_{uuid.uuid4().hex[:12]}"
    query_payload = build_xrd_literature_query(record)
    claims = _xrd_candidate_claims(record, query_payload, max_claims=max_claims)
    summary = dict(record.get("summary") or {})
    normalized_user_documents = _normalize_user_document_sources(user_documents)

    search_results: dict[str, dict[str, Any]] = {
        _search_result_identity(source): copy.deepcopy(source)
        for source in normalized_user_documents
        if _search_result_identity(source)
    }
    provider_request_ids: list[str] = []
    provider_result_sources = {
        _clean_text((source.get("provenance") or {}).get("result_source"))
        for source in normalized_user_documents
        if _clean_text((source.get("provenance") or {}).get("result_source"))
    }
    search_filters = copy.deepcopy(dict(filters or {}))
    modalities = [_clean_text(item).upper() for item in _as_list(search_filters.get("modalities")) if _clean_text(item)]
    if "XRD" not in modalities:
        modalities.insert(0, "XRD")
    search_filters["modalities"] = modalities
    search_filters.setdefault("analysis_type", "XRD")
    search_filters.setdefault("top_k", 5)

    query_text = _clean_text(query_payload.get("query_text"))
    if query_text:
        for candidate in provider.search(query_text, filters=search_filters):
            source_key = _search_result_identity(candidate)
            if not source_key:
                continue
            if source_key in search_results:
                search_results[source_key] = merge_literature_candidates(search_results[source_key], candidate)
            else:
                search_results[source_key] = copy.deepcopy(candidate)
            result_source = _clean_text((candidate.get("provenance") or {}).get("result_source"))
            if result_source:
                provider_result_sources.add(result_source)
        for request_id in _provider_request_ids(provider):
            if request_id and request_id not in provider_request_ids:
                provider_request_ids.append(request_id)

    citations_by_identity: dict[str, dict[str, Any]] = {}
    comparisons_with_rank: list[tuple[int, dict[str, Any]]] = []
    accessible_source_ids: set[str] = set()
    restricted_source_ids: set[str] = set()
    used_access_fields: set[str] = set()
    candidate_tokens = _xrd_candidate_tokens(query_payload)
    match_status = _clean_text(summary.get("match_status")).lower() or "no_match"
    confidence_band = _clean_text(summary.get("confidence_band")).lower() or "no_match"
    candidate_display = _clean_text(query_payload.get("candidate_display_name") or query_payload.get("candidate_name")) or "the top-ranked candidate"
    real_literature_available = False

    for source in search_results.values():
        source_identity = _search_result_identity(source)
        access_class = _clean_text(source.get("access_class")).lower() or "metadata_only"
        accessible = _fetch_accessible_text(source, provider=provider)
        if accessible is None:
            if access_class == "restricted_external":
                restricted_source_ids.add(source_identity)
            evidence_used: list[str] = []
        else:
            accessible_source_ids.add(source_identity)
            field = _clean_text(accessible.get("field")).lower() or "abstract_text"
            used_access_fields.add(field)
            evidence_used = [_brief_evidence(_clean_text(accessible.get("text")))] if _clean_text(accessible.get("text")) else []

        source_text = _xrd_source_text(source, accessible)
        overlap = _xrd_candidate_overlap(source_text, candidate_tokens)
        hint = _clean_text((source.get("provenance") or {}).get("comparison_hint")).lower()
        posture = _xrd_validation_posture(
            match_status=match_status,
            confidence_band=confidence_band,
            access_class=access_class,
            overlap=overlap,
            source_text=source_text,
            hint=hint,
        )
        note = _xrd_comparison_note(candidate=candidate_display, match_status=match_status, confidence_band=confidence_band, posture=posture)
        citation_key = citation_identity_key(source)
        if citation_key not in citations_by_identity:
            citations_by_identity[citation_key] = build_citation_entry(source, citation_id=f"ref{len(citations_by_identity) + 1}")
        citation = citations_by_identity[citation_key]
        provider_id = _clean_text((source.get("provenance") or {}).get("provider_id"))
        if provider_id in REAL_BIBLIOGRAPHIC_PROVIDERS:
            real_literature_available = True

        comparison = LiteratureComparison(
            claim_id=str(claims[0]["claim_id"]) if claims else "C1",
            claim_text=str(claims[0]["claim_text"]) if claims else "",
            candidate_name=_clean_text(query_payload.get("candidate_name")),
            candidate_formula=_clean_text(query_payload.get("candidate_formula")),
            paper_title=_clean_text(source.get("title")),
            paper_year=source.get("year"),
            paper_journal=_clean_text(source.get("journal")),
            paper_doi=_clean_text(source.get("doi")),
            paper_url=_clean_text(source.get("url")),
            provider_id=provider_id,
            access_class=access_class,
            comparison_note=note,
            validation_posture=posture,
            query_text=query_text,
            match_status_snapshot=match_status,
            confidence_band_snapshot=confidence_band,
            retrieved_sources=[_clean_text(source.get("source_id"))] if _clean_text(source.get("source_id")) else [],
            support_label=_xrd_support_label_for_posture(posture),
            rationale=note,
            evidence_used=evidence_used,
            citation_ids=[citation["citation_id"]],
            confidence=_xrd_comparison_confidence(posture, access_class, overlap),
            sources_considered=len(search_results),
        ).to_dict()
        score = overlap + (6 if posture == "related_support" else 4 if posture == "alternative_interpretation" else 2 if posture == "contextual_only" else 1)
        comparisons_with_rank.append((score, comparison))

    comparisons_with_rank.sort(key=lambda item: (-item[0], -(item[1].get("paper_year") or 0), str(item[1].get("paper_title") or "")))
    comparisons = [item for _score, item in comparisons_with_rank]

    context = LiteratureContext(
        mode="metadata_abstract_oa_only",
        comparison_run_id=comparison_run_id,
        provider_scope=provider_scope,
        result_id=_clean_text(record.get("id")),
        analysis_type="XRD",
        provider_request_ids=provider_request_ids,
        provider_result_source=(
            "multi_provider_search"
            if len(provider_scope) > 1
            else (sorted(provider_result_sources)[0] if len(provider_result_sources) == 1 else _provider_result_source(provider, provider_scope=provider_scope))
        ),
        query_count=1 if query_text else 0,
        source_count=len(search_results),
        citation_count=len(citations_by_identity),
        accessible_source_count=len(accessible_source_ids),
        restricted_source_count=len(restricted_source_ids),
        metadata_only_evidence=bool(search_results) and not (used_access_fields & {"oa_full_text", "user_provided_document"}),
        restricted_content_used=False,
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
        query_text=query_text,
        candidate_name=_clean_text(query_payload.get("candidate_name")),
        candidate_formula=_clean_text(query_payload.get("candidate_formula")),
        candidate_id=_clean_text(query_payload.get("candidate_id")),
        candidate_display_name=_clean_text(query_payload.get("candidate_display_name")),
        match_status_snapshot=match_status,
        confidence_band_snapshot=confidence_band,
        top_candidate_score_snapshot=_clean_float(summary.get("top_candidate_score")),
        shared_peak_count_snapshot=_clean_int(summary.get("top_candidate_shared_peak_count")),
        coverage_ratio_snapshot=_clean_float(summary.get("top_candidate_coverage_ratio")),
        weighted_overlap_score_snapshot=_clean_float(summary.get("top_candidate_weighted_overlap_score")),
        candidate_provider_snapshot=_clean_text(summary.get("top_candidate_provider")),
        candidate_result_source_snapshot=_clean_text(summary.get("library_result_source")),
        real_literature_available=real_literature_available,
        fixture_fallback_used=bool(search_filters.get("allow_fixture_fallback")) and not real_literature_available and any(
            _is_fixture_source(source) for source in search_results.values()
        ),
        query_rationale=_clean_text(query_payload.get("query_rationale")),
    ).to_dict()

    citations = sorted(citations_by_identity.values(), key=lambda item: item["citation_id"])
    return {
        "literature_context": normalize_literature_context(context),
        "literature_claims": claims,
        "literature_comparisons": normalize_literature_comparisons(comparisons),
        "citations": normalize_citations(citations),
    }


def compare_result_to_literature(
    record: Mapping[str, Any],
    *,
    provider: LiteratureProvider | None = None,
    provider_scope: list[str] | None = None,
    max_claims: int = 3,
    filters: Mapping[str, Any] | None = None,
    user_documents: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    active_provider = provider or FixtureLiteratureProvider()
    scope = provider_scope or [getattr(active_provider, "provider_id", "fixture_provider")]
    if _clean_text(record.get("analysis_type")).upper() == "XRD":
        return _compare_xrd_candidate_to_literature(
            record,
            provider=active_provider,
            provider_scope=scope,
            max_claims=max_claims,
            filters=filters,
            user_documents=user_documents,
        )
    return _compare_generic_result_to_literature(
        record,
        provider=active_provider,
        provider_scope=scope,
        max_claims=max_claims,
        filters=filters,
        user_documents=user_documents,
    )


def attach_literature_package(record: Mapping[str, Any], package: Mapping[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(dict(record))
    updated["literature_context"] = normalize_literature_context(package.get("literature_context"))
    updated["literature_claims"] = list(package.get("literature_claims") or extract_literature_claims(updated))
    updated["literature_comparisons"] = list(package.get("literature_comparisons") or [])
    updated["citations"] = list(package.get("citations") or [])
    return updated
