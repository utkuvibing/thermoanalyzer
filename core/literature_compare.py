"""Literature comparison engine for legal-safe, citation-backed result review."""

from __future__ import annotations

import copy
import uuid
from typing import Any, Mapping

from core.citation_formatter import build_citation_entry
from core.literature_claims import build_claim_queries, extract_literature_claims
from core.literature_models import (
    LiteratureComparison,
    LiteratureContext,
    normalize_citations,
    normalize_literature_comparisons,
    normalize_literature_context,
    normalize_literature_sources,
)
from core.literature_provider import FixtureLiteratureProvider, LiteratureProvider


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
CONTRADICT_PHRASES = ("contradicts", "inconsistent", "not consistent", "alternative phase")


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _clean_int(value: Any) -> int | None:
    try:
        return int(value)
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
        for item in (
            _as_list(document.get("keywords"))
            + _as_list(provenance.get("keywords"))
        )
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
        for item in (
            _as_list(document.get("modalities"))
            + _as_list(provenance.get("modalities"))
        )
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
                        "source_license_note": "user_provided_document",
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


def _fetch_accessible_text(
    source: Mapping[str, Any],
    *,
    provider: LiteratureProvider,
) -> dict[str, Any] | None:
    access_class = _clean_text(source.get("access_class")).lower()
    if access_class == "restricted_external":
        return None
    if access_class == "user_provided_document":
        text = _clean_text(source.get("oa_full_text") or source.get("abstract_text"))
        if not text:
            return None
        return {
            "source_id": source.get("source_id"),
            "text": text,
            "field": "user_provided_document",
            "access_class": access_class,
        }
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
    evidence = _brief_evidence(text)
    return {
        "source_id": source.get("source_id"),
        "label": label,
        "score": overlap + {"supports": 6, "partially_supports": 4, "contradicts": 5, "related_but_inconclusive": 1}[label],
        "evidence": evidence,
        "access_field": accessible.get("field") or "abstract_text",
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
    comparison_run_id = f"litcmp_{uuid.uuid4().hex[:12]}"
    claims = extract_literature_claims(record, max_claims=max(1, int(max_claims or 1)))
    active_provider = provider or FixtureLiteratureProvider()
    scope = provider_scope or [getattr(active_provider, "provider_id", "fixture_provider")]
    normalized_user_documents = _normalize_user_document_sources(user_documents)

    all_queries: list[str] = []
    comparisons: list[dict[str, Any]] = []
    citations_by_source_id: dict[str, dict[str, Any]] = {}
    restricted_content_used = False

    for claim in claims:
        search_results: dict[str, dict[str, Any]] = {
            str(source.get("source_id") or ""): copy.deepcopy(source)
            for source in normalized_user_documents
            if str(source.get("source_id") or "")
        }
        claim_filters = _search_filters_for_claim(claim, filters)
        for query in build_claim_queries(claim):
            all_queries.append(query)
            for candidate in active_provider.search(query, filters=claim_filters):
                source_id = str(candidate.get("source_id") or "")
                if source_id and source_id not in search_results:
                    search_results[source_id] = copy.deepcopy(candidate)

        evaluations: list[dict[str, Any]] = []
        for source in search_results.values():
            accessible = _fetch_accessible_text(source, provider=active_provider)
            if accessible is None:
                if str(source.get("access_class") or "").lower() == "restricted_external":
                    restricted_content_used = restricted_content_used or False
                continue
            evaluations.append(_evaluate_source(claim, source, accessible))

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
                source = search_results.get(str(source_eval["source_id"]))
                if source is None:
                    continue
                source_id = str(source.get("source_id") or "")
                if source_id not in citations_by_source_id:
                    citation_id = f"ref{len(citations_by_source_id) + 1}"
                    citations_by_source_id[source_id] = build_citation_entry(source, citation_id=citation_id)
                citation_ids.append(citations_by_source_id[source_id]["citation_id"])
                evidence_used.append(source_eval["evidence"])

            comparisons.append(
                LiteratureComparison(
                    claim_id=str(claim.get("claim_id") or ""),
                    retrieved_sources=sorted(search_results),
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
                    retrieved_sources=sorted(search_results),
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
        provider_scope=scope,
        query_count=len(all_queries),
        restricted_content_used=restricted_content_used,
    ).to_dict()

    citations = sorted(citations_by_source_id.values(), key=lambda item: item["citation_id"])
    return {
        "literature_context": normalize_literature_context(context),
        "literature_claims": claims,
        "literature_comparisons": normalize_literature_comparisons(comparisons),
        "citations": normalize_citations(citations),
    }


def attach_literature_package(record: Mapping[str, Any], package: Mapping[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(dict(record))
    updated["literature_context"] = normalize_literature_context(package.get("literature_context"))
    updated["literature_claims"] = list(package.get("literature_claims") or extract_literature_claims(updated))
    updated["literature_comparisons"] = list(package.get("literature_comparisons") or [])
    updated["citations"] = list(package.get("citations") or [])
    return updated
