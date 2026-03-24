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
from core.thermal_literature_query_builder import (
    build_dsc_literature_query,
    build_dta_literature_query,
    build_thermal_query_presentation,
    build_tga_literature_query,
)
from core.xrd_literature_query_builder import build_xrd_literature_query, build_xrd_query_presentation


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
THERMAL_GENERIC_NEIGHBOR_TERMS = {
    "cement",
    "clinker",
    "clay",
    "ceramic",
    "ceramics",
    "silicate",
    "concrete",
    "mortar",
    "geopolymer",
    "carbonation",
    "calcined clay",
    "alkali activated",
}
THERMAL_TGA_DIRECT_ENTITY_TERMS = {
    "caco3",
    "calcium carbonate",
    "calcite",
}
THERMAL_TGA_DIRECT_PROCESS_TERMS = {
    "thermal decomposition",
    "decomposition",
    "decarbonation",
    "calcination",
    "cao",
    "co2 release",
    "co2 evolution",
}
THERMAL_TGA_DIRECT_MODALITY_TERMS = {
    "tga",
    "thermogravimetric",
    "thermogravimetric analysis",
    "mass loss",
    "residue",
}


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


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for item in values:
        cleaned = _clean_text(item)
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        output.append(cleaned)
    return output


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
    accessible = provider.fetch_accessible_text(dict(source))
    if accessible is not None and _clean_text(accessible.get("text")):
        return accessible
    fallback_oa = _clean_text(source.get("oa_full_text"))
    if fallback_oa and access_class == "open_access_full_text":
        return {"source_id": source.get("source_id"), "text": fallback_oa, "field": "oa_full_text", "access_class": access_class}
    fallback_abstract = _clean_text(source.get("abstract_text"))
    if fallback_abstract and access_class in {"abstract_only", "metadata_only", "open_access_full_text"}:
        return {
            "source_id": source.get("source_id"),
            "text": fallback_abstract,
            "field": "abstract_text",
            "access_class": "abstract_only" if access_class == "metadata_only" else access_class,
        }
    return None


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


def _provider_query_status(provider: LiteratureProvider) -> str:
    return _clean_text(getattr(provider, "last_query_status", "")).lower()


def _provider_error_message(provider: LiteratureProvider) -> str:
    return _clean_text(getattr(provider, "last_error_message", ""))


def _thermal_query_payload(record: Mapping[str, Any]) -> dict[str, Any]:
    analysis_type = _clean_text(record.get("analysis_type")).upper()
    if analysis_type == "DSC":
        return build_dsc_literature_query(record)
    if analysis_type == "DTA":
        return build_dta_literature_query(record)
    if analysis_type == "TGA":
        return build_tga_literature_query(record)
    raise ValueError(f"Unsupported thermal analysis_type: {analysis_type}")


def _thermal_search_queries(query_payload: Mapping[str, Any]) -> list[str]:
    queries: list[str] = []
    for value in [_clean_text(query_payload.get("query_text"))] + [_clean_text(item) for item in _as_list(query_payload.get("fallback_queries"))]:
        if value and value not in queries:
            queries.append(value)
        if len(queries) >= 5:
            break
    return queries


def _phrase_overlap_count(text: str, phrases: list[str]) -> int:
    lowered = text.lower()
    return sum(1 for phrase in phrases if phrase and phrase.lower() in lowered)


def _thermal_subject_tokens(query_payload: Mapping[str, Any], record: Mapping[str, Any]) -> set[str]:
    tokens: set[str] = set()
    summary = dict(record.get("summary") or {})
    metadata = dict(record.get("metadata") or {})
    values = [
        query_payload.get("query_display_title"),
        summary.get("sample_name"),
        metadata.get("sample_name"),
        metadata.get("display_name"),
    ]
    evidence_snapshot = dict(query_payload.get("evidence_snapshot") or {})
    for key in ("peak_type", "event_direction", "sample_name"):
        values.append(evidence_snapshot.get(key))
    values.extend(_as_list(evidence_snapshot.get("subject_aliases")))
    values.extend(_as_list(evidence_snapshot.get("subject_formulas")))
    for value in values:
        cleaned = _clean_text(value)
        if not cleaned:
            continue
        tokens.add(cleaned.lower())
        tokens.update(_tokenize(cleaned))
    return {token for token in tokens if token}


def _thermal_source_text(source: Mapping[str, Any], accessible: Mapping[str, Any] | None) -> str:
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


def _thermal_subject_overlap(source_text: str, subject_tokens: set[str]) -> int:
    lowered = source_text.lower()
    return sum(1 for token in subject_tokens if token and token in lowered)


def _thermal_precision_signals(query_payload: Mapping[str, Any], analysis_type: str) -> dict[str, list[str]]:
    evidence_snapshot = dict(query_payload.get("evidence_snapshot") or {})
    entity_terms = _dedupe(
        [_clean_text(query_payload.get("query_display_title"))]
        + [_clean_text(item) for item in _as_list(evidence_snapshot.get("subject_aliases"))]
        + [_clean_text(item) for item in _as_list(evidence_snapshot.get("subject_formulas"))]
        + [_clean_text(evidence_snapshot.get("sample_name"))]
    )
    process_terms = _dedupe(
        [_clean_text(item) for item in _as_list(evidence_snapshot.get("process_terms"))]
        + ["decomposition"]
        + (["glass transition", "calorimetry"] if analysis_type == "DSC" else [])
        + (["differential thermal analysis", "thermal event"] if analysis_type == "DTA" else [])
        + (["thermogravimetric analysis", "mass loss", "residue", "tga"] if analysis_type == "TGA" else [])
    )
    modality_terms = {
        "DSC": ["dsc", "differential scanning calorimetry", "calorimetry"],
        "DTA": ["dta", "differential thermal analysis", "thermal event"],
        "TGA": ["tga", "thermogravimetric", "thermogravimetric analysis", "mass loss", "residue"],
    }.get(analysis_type, [])
    temperature_terms = []
    midpoint = _clean_float(evidence_snapshot.get("midpoint_temperature") or evidence_snapshot.get("peak_temperature") or evidence_snapshot.get("tg_midpoint"))
    if midpoint is not None:
        temperature_terms.append(str(int(round(midpoint))))
    temperature_band = _clean_text(evidence_snapshot.get("temperature_band_query"))
    if temperature_band:
        temperature_terms.extend([token for token in temperature_band.split() if token.isdigit()])
    return {
        "entity_terms": entity_terms,
        "process_terms": process_terms,
        "modality_terms": modality_terms,
        "temperature_terms": temperature_terms,
    }


def _thermal_relevance_score(
    *,
    source_text: str,
    access_class: str,
    query_payload: Mapping[str, Any],
    analysis_type: str,
    overlap: int,
) -> tuple[int, bool]:
    signals = _thermal_precision_signals(query_payload, analysis_type)
    entity_hits = _phrase_overlap_count(source_text, signals["entity_terms"])
    process_hits = _phrase_overlap_count(source_text, signals["process_terms"])
    modality_hits = _phrase_overlap_count(source_text, signals["modality_terms"])
    temperature_hits = _phrase_overlap_count(source_text, signals["temperature_terms"])
    generic_neighbor_hits = _phrase_overlap_count(source_text, list(THERMAL_GENERIC_NEIGHBOR_TERMS))
    direct_entity_hits = 0
    direct_process_hits = 0
    direct_modality_hits = 0
    if analysis_type == "TGA":
        direct_entity_hits = _phrase_overlap_count(source_text, list(THERMAL_TGA_DIRECT_ENTITY_TERMS))
        direct_process_hits = _phrase_overlap_count(source_text, list(THERMAL_TGA_DIRECT_PROCESS_TERMS))
        direct_modality_hits = _phrase_overlap_count(source_text, list(THERMAL_TGA_DIRECT_MODALITY_TERMS))
    score = overlap
    score += entity_hits * 4
    score += process_hits * 3
    score += modality_hits * 3
    score += temperature_hits * 2
    if analysis_type == "TGA":
        score += direct_entity_hits * 5
        score += direct_process_hits * 4
        score += direct_modality_hits * 4
        if direct_entity_hits and direct_process_hits:
            score += 10
        if direct_entity_hits and direct_modality_hits:
            score += 8
        if direct_process_hits and direct_modality_hits:
            score += 6
        if direct_entity_hits and direct_process_hits and direct_modality_hits:
            score += 10
        if temperature_hits and (direct_process_hits or process_hits):
            score += 2
    if access_class in {"open_access_full_text", "user_provided_document"}:
        score += 2
    if generic_neighbor_hits:
        direct_signal_count = int(bool(entity_hits or direct_entity_hits)) + int(bool(process_hits or direct_process_hits)) + int(bool(modality_hits or direct_modality_hits))
        if direct_signal_count == 0:
            score -= generic_neighbor_hits * 5
        elif direct_signal_count == 1:
            score -= generic_neighbor_hits * 4
        elif direct_signal_count == 2:
            score -= generic_neighbor_hits * 2
    low_specificity = (
        score < 12
        and access_class in {"metadata_only", "abstract_only"}
        and not (direct_entity_hits and (direct_process_hits or direct_modality_hits))
        and process_hits == 0
    )
    return score, low_specificity


def _thermal_query_is_too_narrow(query_payload: Mapping[str, Any]) -> bool:
    subject = _clean_text((query_payload.get("evidence_snapshot") or {}).get("sample_name"))
    return not subject and not any(_clean_text(item) for item in _as_list(query_payload.get("query_display_terms")))


def _thermal_validation_posture(
    *,
    analysis_type: str,
    access_class: str,
    overlap: int,
    source_text: str,
    hint: str,
    precision_score: int,
) -> str:
    lowered = source_text.lower()
    if hint in {"contradicts", "contradict"} or any(phrase in lowered for phrase in CONTRADICT_PHRASES):
        return "alternative_interpretation"
    if precision_score >= 10 and access_class in {"open_access_full_text", "user_provided_document", "abstract_only"}:
        return "related_support"
    if analysis_type in {"DSC", "DTA", "TGA"} and precision_score >= 5:
        return "contextual_only"
    return "non_validating"


def _thermal_support_label_for_posture(posture: str) -> str:
    if posture == "related_support":
        return "partially_supports"
    if posture == "alternative_interpretation":
        return "contradicts"
    return "related_but_inconclusive"


def _thermal_evidence_basis(access_field: str, access_class: str) -> str:
    field = _clean_text(access_field).lower()
    token = _clean_text(access_class).lower()
    if field in {"", "metadata_only"}:
        return "metadata_only"
    if field in {"oa_full_text", "user_provided_document"} or token in {"open_access_full_text", "user_provided_document"}:
        return "oa_backed"
    if field == "abstract_text" or token == "abstract_only":
        return "abstract_backed"
    return "metadata_only"


def _thermal_evidence_specificity_summary(*, source_count: int, accessible_source_count: int, used_access_fields: set[str]) -> str:
    if used_access_fields & {"oa_full_text", "user_provided_document"}:
        return "oa_backed"
    if used_access_fields & {"abstract_text"}:
        if source_count > accessible_source_count:
            return "mixed_metadata_and_abstract"
        return "abstract_backed"
    return "metadata_only" if source_count else ""


def _merge_thermal_surfaced_comparisons(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged_rows: list[dict[str, Any]] = []
    for row in rows:
        similarity_key = (
            _clean_text(row.get("claim_id")).casefold(),
            _clean_text(row.get("support_label")).casefold(),
            _clean_text(row.get("validation_posture")).casefold(),
            _clean_text(row.get("confidence")).casefold(),
            _clean_text(row.get("access_class")).casefold(),
            _clean_text(row.get("comparison_note")).casefold(),
        )
        existing = next((item for item in merged_rows if item.get("_similarity_key") == similarity_key), None)
        if existing is None:
            merged = dict(row)
            merged["_similarity_key"] = similarity_key
            merged_rows.append(merged)
            continue
        for citation_id in _as_list(row.get("citation_ids")):
            cleaned = _clean_text(citation_id)
            if cleaned and cleaned not in existing.get("citation_ids", []):
                existing.setdefault("citation_ids", []).append(cleaned)
        for evidence in _as_list(row.get("evidence_used")):
            cleaned = _clean_text(evidence)
            if cleaned and cleaned not in existing.get("evidence_used", []):
                existing.setdefault("evidence_used", []).append(cleaned)
        for source_id in _as_list(row.get("retrieved_sources")):
            cleaned = _clean_text(source_id)
            if cleaned and cleaned not in existing.get("retrieved_sources", []):
                existing.setdefault("retrieved_sources", []).append(cleaned)
        existing["sources_considered"] = max(
            _clean_int(existing.get("sources_considered")) or 0,
            _clean_int(row.get("sources_considered")) or 0,
        )
    for item in merged_rows:
        item.pop("_similarity_key", None)
    return merged_rows


def _thermal_comparison_confidence(posture: str, access_class: str, overlap: int, *, precision_score: int, access_field: str) -> str:
    evidence_basis = _thermal_evidence_basis(access_field, access_class)
    if posture == "related_support" and evidence_basis == "oa_backed" and overlap >= 2:
        return "moderate"
    if posture == "related_support" and evidence_basis == "abstract_backed" and precision_score >= 14 and overlap >= 2:
        return "moderate"
    if posture == "related_support" and access_class in {"open_access_full_text", "user_provided_document"} and overlap >= 2:
        return "moderate"
    if posture == "alternative_interpretation" and overlap >= 1:
        return "moderate"
    return "low"


def _thermal_subject_label(query_payload: Mapping[str, Any], record: Mapping[str, Any]) -> str:
    summary = dict(record.get("summary") or {})
    metadata = dict(record.get("metadata") or {})
    return (
        _clean_text(query_payload.get("query_display_title"))
        or _clean_text(summary.get("sample_name"))
        or _clean_text(metadata.get("sample_name"))
        or _clean_text(metadata.get("display_name"))
        or "the thermal result"
    )


def _thermal_comparison_note(
    *,
    analysis_type: str,
    subject: str,
    posture: str,
    query_payload: Mapping[str, Any],
    access_field: str,
    source_text: str,
) -> str:
    evidence_snapshot = dict(query_payload.get("evidence_snapshot") or {})
    evidence_basis = _thermal_evidence_basis(access_field, "")
    basis_note = (
        "Reasoning used accessible open-access or user-provided text."
        if evidence_basis == "oa_backed"
        else "Reasoning used accessible abstract-level text."
        if evidence_basis == "abstract_backed"
        else "Reasoning was limited to metadata-level overlap."
    )
    if analysis_type == "DSC":
        tg_midpoint = _clean_float(evidence_snapshot.get("tg_midpoint"))
        event_label = _clean_text(evidence_snapshot.get("peak_type")) or "thermal event"
        if posture == "alternative_interpretation":
            return (
                f"This paper discusses DSC behavior relevant to {subject}. It may indicate an alternative interpretation for the recorded calorimetric event rather than confirming the present result. {basis_note}"
            )
        if posture == "related_support":
            if tg_midpoint is not None:
                return (
                    f"This paper discusses DSC glass-transition or event behavior relevant to {subject}. It is directionally consistent with a transition near {tg_midpoint:.0f} C, but it remains contextual support rather than confirmation. {basis_note}"
                )
            return (
                f"This paper discusses DSC {event_label} behavior relevant to {subject}. It adds contextual support for the recorded event, but it does not validate the current result. {basis_note}"
            )
        if posture == "contextual_only":
            return (
                f"This paper discusses DSC behavior relevant to {subject}. It provides thermal-event context only and should not be treated as confirmation of the current interpretation. {basis_note}"
            )
        return (
            f"This paper is related to the DSC interpretation for {subject}, but the current evidence remains limited and non-validating. {basis_note}"
        )
    if analysis_type == "DTA":
        direction = _clean_text(evidence_snapshot.get("event_direction")) or "thermal event"
        if posture == "alternative_interpretation":
            return (
                f"This paper discusses DTA behavior relevant to {subject}. It may point toward an alternative reading of the recorded {direction} event rather than confirming the present interpretation. {basis_note}"
            )
        if posture == "related_support":
            return (
                f"This paper discusses DTA behavior relevant to {subject}. It is directionally consistent with the recorded {direction} event, but it remains qualitative context rather than validation. {basis_note}"
            )
        if posture == "contextual_only":
            return (
                f"This paper discusses DTA behavior relevant to {subject}. It adds qualitative thermal-event context only and does not validate the current result. {basis_note}"
            )
        return (
            f"This paper is related to the DTA interpretation for {subject}, but the current evidence remains limited and non-validating. {basis_note}"
        )
    total_mass_loss = _clean_float(evidence_snapshot.get("total_mass_loss_percent"))
    residue = _clean_float(evidence_snapshot.get("residue_percent"))
    lowered = source_text.lower()
    entity_bits = [term for term in ("calcium carbonate", "calcite", "caco3") if term in lowered]
    process_bits = [term for term in ("decarbonation", "calcination", "thermal decomposition", "decomposition") if term in lowered]
    modality_bits = [term for term in ("thermogravimetric analysis", "thermogravimetric", "tga") if term in lowered]
    product_bits = [term for term in ("cao", "co2 release", "co2 evolution") if term in lowered]
    topic_tokens = _dedupe(entity_bits + process_bits + modality_bits + product_bits)
    topic_clause = f" It explicitly discusses {' / '.join(topic_tokens[:4])}." if topic_tokens else ""
    if posture == "alternative_interpretation":
        return (
            f"This paper discusses TGA decomposition behavior relevant to {subject}.{topic_clause} It may indicate an alternative interpretation for the recorded mass-loss profile rather than confirming the current result. {basis_note}"
        )
    if posture == "related_support":
        detail = []
        if total_mass_loss is not None:
            detail.append(f"total mass loss around {total_mass_loss:.1f}%")
        if residue is not None:
            detail.append(f"residue around {residue:.1f}%")
        suffix = f" ({', '.join(detail)})" if detail else ""
        return (
            f"This paper discusses TGA decomposition behavior relevant to {subject}.{topic_clause} It is directionally consistent with the recorded mass-loss profile{suffix}, but it remains contextual support rather than validation. {basis_note}"
        )
    if posture == "contextual_only":
        return (
            f"This paper discusses TGA decomposition behavior relevant to {subject}.{topic_clause} It provides decomposition-profile context only and does not validate the current result. {basis_note}"
        )
    return (
        f"This paper is related to the TGA interpretation for {subject}.{topic_clause} The current evidence remains limited and non-validating. {basis_note}"
    )


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
        metadata_only_evidence=bool(all_sources_seen) and not bool(used_access_fields),
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


def _compare_thermal_result_to_literature(
    record: Mapping[str, Any],
    *,
    provider: LiteratureProvider,
    provider_scope: list[str],
    max_claims: int,
    filters: Mapping[str, Any] | None,
    user_documents: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    comparison_run_id = f"litcmp_{uuid.uuid4().hex[:12]}"
    analysis_type = _clean_text(record.get("analysis_type")).upper()
    query_payload = _thermal_query_payload(record)
    query_presentation = build_thermal_query_presentation(query_payload)
    claims = extract_literature_claims(record, max_claims=max(1, int(max_claims or 1)))
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
    if analysis_type not in modalities:
        modalities.insert(0, analysis_type)
    search_filters["modalities"] = modalities
    search_filters["analysis_type"] = analysis_type
    search_filters.setdefault("top_k", 5)

    executed_queries: list[str] = []
    for query_text in _thermal_search_queries(query_payload):
        executed_queries.append(query_text)
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
    provider_query_status = _provider_query_status(provider)
    provider_error_message = _provider_error_message(provider)

    citations_by_identity: dict[str, dict[str, Any]] = {}
    comparisons_with_rank: list[tuple[int, bool, dict[str, Any]]] = []
    accessible_source_ids: set[str] = set()
    restricted_source_ids: set[str] = set()
    used_access_fields: set[str] = set()
    subject_tokens = _thermal_subject_tokens(query_payload, record)
    subject_label = _thermal_subject_label(query_payload, record)
    real_literature_available = False

    for source in search_results.values():
        source_identity = _search_result_identity(source)
        access_class = _clean_text(source.get("access_class")).lower() or "metadata_only"
        accessible = _fetch_accessible_text(source, provider=provider)
        if accessible is None:
            if access_class == "restricted_external":
                restricted_source_ids.add(source_identity)
            evidence_used: list[str] = []
            access_field = "metadata_only"
        else:
            accessible_source_ids.add(source_identity)
            access_field = _clean_text(accessible.get("field")).lower() or "abstract_text"
            used_access_fields.add(access_field)
            evidence_used = [_brief_evidence(_clean_text(accessible.get("text")))] if _clean_text(accessible.get("text")) else []

        source_text = _thermal_source_text(source, accessible)
        overlap = _thermal_subject_overlap(source_text, subject_tokens)
        hint = _clean_text((source.get("provenance") or {}).get("comparison_hint")).lower()
        precision_score, low_specificity = _thermal_relevance_score(
            source_text=source_text,
            access_class=access_class,
            query_payload=query_payload,
            analysis_type=analysis_type,
            overlap=overlap,
        )
        posture = _thermal_validation_posture(
            analysis_type=analysis_type,
            access_class=access_class,
            overlap=overlap,
            source_text=source_text,
            hint=hint,
            precision_score=precision_score,
        )
        note = _thermal_comparison_note(
            analysis_type=analysis_type,
            subject=subject_label,
            posture=posture,
            query_payload=query_payload,
            access_field=access_field,
            source_text=source_text,
        )
        citation_key = citation_identity_key(source)
        if citation_key not in citations_by_identity:
            citations_by_identity[citation_key] = build_citation_entry(source, citation_id=f"ref{len(citations_by_identity) + 1}")
        citation = citations_by_identity[citation_key]
        provider_id = _clean_text((source.get("provenance") or {}).get("provider_id"))
        if provider_id in REAL_BIBLIOGRAPHIC_PROVIDERS:
            real_literature_available = True

        claim = claims[0] if claims else {}
        comparison = LiteratureComparison(
            claim_id=str(claim.get("claim_id") or "C1"),
            claim_text=str(claim.get("claim_text") or ""),
            candidate_name=subject_label,
            paper_title=_clean_text(source.get("title")),
            paper_year=source.get("year"),
            paper_journal=_clean_text(source.get("journal")),
            paper_doi=_clean_text(source.get("doi")),
            paper_url=_clean_text(source.get("url")),
            provider_id=provider_id,
            access_class=access_class,
            comparison_note=note,
            validation_posture=posture,
            query_text=executed_queries[0] if executed_queries else _clean_text(query_payload.get("query_text")),
            retrieved_sources=[_clean_text(source.get("source_id"))] if _clean_text(source.get("source_id")) else [],
            support_label=_thermal_support_label_for_posture(posture),
            rationale=note,
            evidence_used=evidence_used,
            citation_ids=[citation["citation_id"]],
            confidence=_thermal_comparison_confidence(posture, access_class, overlap, precision_score=precision_score, access_field=access_field),
            sources_considered=len(search_results),
        ).to_dict()
        score = precision_score + (6 if posture == "related_support" else 4 if posture == "alternative_interpretation" else 2 if posture == "contextual_only" else 0)
        comparisons_with_rank.append((score, low_specificity, comparison))

    comparisons_with_rank.sort(key=lambda item: (-item[0], item[1], -(item[2].get("paper_year") or 0), str(item[2].get("paper_title") or "")))
    surfaced_comparisons: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    strong_rows = [item for item in comparisons_with_rank if item[0] >= 10 and not item[1]]
    candidate_rows = strong_rows if strong_rows else comparisons_with_rank
    limit = 2 if strong_rows else 1
    for _score, low_specificity, item in candidate_rows:
        title_key = _clean_text(item.get("paper_title") or item.get("paper_doi") or item.get("paper_url")).casefold()
        if title_key and title_key in seen_titles:
            continue
        if low_specificity and strong_rows:
            continue
        if title_key:
            seen_titles.add(title_key)
        surfaced_comparisons.append(item)
        if len(surfaced_comparisons) >= limit:
            break
    if not surfaced_comparisons and comparisons_with_rank:
        surfaced_comparisons = [comparisons_with_rank[0][2]]
    comparisons = _merge_thermal_surfaced_comparisons(surfaced_comparisons)
    low_specificity_retrieval = bool(comparisons_with_rank) and not strong_rows and all(item[1] for item in comparisons_with_rank[: min(len(comparisons_with_rank), 3)])
    evidence_specificity = _thermal_evidence_specificity_summary(
        source_count=len(search_results),
        accessible_source_count=len(accessible_source_ids),
        used_access_fields=used_access_fields,
    )
    evidence_snapshot = dict(query_payload.get("evidence_snapshot") or {})
    context = LiteratureContext(
        mode="metadata_abstract_oa_only",
        comparison_run_id=comparison_run_id,
        provider_scope=provider_scope,
        result_id=_clean_text(record.get("id")),
        analysis_type=analysis_type,
        provider_request_ids=provider_request_ids,
        provider_result_source=(
            "multi_provider_search"
            if len(provider_scope) > 1
            else (sorted(provider_result_sources)[0] if len(provider_result_sources) == 1 else _provider_result_source(provider, provider_scope=provider_scope))
        ),
        query_count=len(executed_queries),
        source_count=len(search_results),
        citation_count=len(citations_by_identity),
        accessible_source_count=len(accessible_source_ids),
        restricted_source_count=len(restricted_source_ids),
        metadata_only_evidence=evidence_specificity == "metadata_only",
        restricted_content_used=False,
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
        query_text=executed_queries[0] if executed_queries else _clean_text(query_payload.get("query_text")),
        candidate_name=subject_label,
        candidate_display_name=subject_label,
        real_literature_available=real_literature_available,
        fixture_fallback_used=bool(search_filters.get("allow_fixture_fallback")) and not real_literature_available and any(
            _is_fixture_source(source) for source in search_results.values()
        ),
        query_rationale=_clean_text(query_payload.get("query_rationale")),
        provider_query_status=provider_query_status,
        no_results_reason=(
            "provider_unavailable"
            if provider_query_status == "provider_unavailable"
            else "request_failed"
            if provider_query_status == "request_failed"
            else "not_configured"
            if provider_query_status == "not_configured"
            else "query_too_narrow"
            if not search_results and _thermal_query_is_too_narrow(query_payload)
            else "query_too_narrow"
            if provider_query_status == "query_too_narrow"
            else "no_real_results"
            if not search_results and provider_query_status in {"no_results", "success", ""}
            else ""
        ),
        fixture_fallback_allowed=bool(search_filters.get("allow_fixture_fallback")),
        query_display_title=_clean_text(query_presentation.get("display_title")),
        query_display_mode=_clean_text(query_presentation.get("display_mode")),
        query_display_terms=_as_list(query_presentation.get("display_terms")),
        low_specificity_retrieval=low_specificity_retrieval,
        surfaced_comparison_count=len(comparisons),
        evidence_specificity_summary=evidence_specificity,
        shared_peak_count_snapshot=_clean_int(evidence_snapshot.get("peak_count") or evidence_snapshot.get("step_count")),
        coverage_ratio_snapshot=_clean_float(evidence_snapshot.get("total_mass_loss_percent")),
        weighted_overlap_score_snapshot=_clean_float(
            evidence_snapshot.get("tg_midpoint")
            or evidence_snapshot.get("peak_temperature")
            or evidence_snapshot.get("midpoint_temperature")
        ),
    ).to_dict()
    if provider_error_message:
        context["provider_error_message"] = provider_error_message

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
    family_label = _clean_text((query_payload.get("evidence_snapshot") or {}).get("family_label") or summary.get("family_context_label"))

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
    elif match_status == "family_consistent":
        claims.append(
            LiteratureClaim(
                claim_id="C1",
                claim_text=(
                    f"The current XRD result supports a family-level context around {family_label or candidate}, "
                    "but literature remains non-validating and does not justify an exact phase identification."
                ),
                claim_type="cautionary_interpretation",
                modality="XRD",
                strength="low",
                evidence_snapshot=dict(query_payload.get("evidence_snapshot") or {}),
                uncertainty_notes=[warning_reason] if warning_reason else [],
                suggested_query_terms=[family_label or _clean_text(query_payload.get("candidate_name")), _clean_text(query_payload.get("candidate_formula")), "XRD"],
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


def _xrd_query_is_too_narrow(query_payload: Mapping[str, Any]) -> bool:
    return not any(
        _clean_text(query_payload.get(key))
        for key in ("candidate_display_name", "candidate_name", "candidate_formula")
    )


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
    candidate_label = candidate or "the candidate phase"
    if match_status == "no_match":
        return (
            f"This paper discusses XRD characterization of {candidate_label}. The current result remains a no_match screening outcome and stays below the XRD acceptance threshold, so the paper provides candidate-level context rather than validation."
        )
    if match_status == "family_consistent":
        return (
            f"This paper discusses XRD characterization relevant to {candidate_label}. The current result supports only family-level context, so the source should be used as non-validating literature support rather than exact phase confirmation."
        )
    if posture == "alternative_interpretation":
        return (
            f"This paper discusses XRD characterization of {candidate_label}. The present pattern remains qualitative and non-validating, and this source may point to an alternative interpretation rather than confirming the candidate."
        )
    if posture == "related_support" and confidence_band not in {"low", "no_match"}:
        return (
            f"This paper discusses XRD characterization of {candidate_label}. It is relevant to the top-ranked candidate, but the present result remains qualitative and should be treated as contextual support rather than phase confirmation."
        )
    return (
        f"This paper discusses XRD characterization of {candidate_label}. The current XRD evidence remains limited and non-validating, so the source should be used as contextual literature only."
    )


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
    query_presentation = build_xrd_query_presentation(query_payload)
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
    provider_query_status = _provider_query_status(provider)
    provider_error_message = _provider_error_message(provider)

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
        metadata_only_evidence=bool(search_results) and not bool(used_access_fields),
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
        provider_query_status=provider_query_status,
        no_results_reason=(
            "provider_unavailable"
            if provider_query_status == "provider_unavailable"
            else "request_failed"
            if provider_query_status == "request_failed"
            else "not_configured"
            if provider_query_status == "not_configured"
            else "query_too_narrow"
            if not search_results and _xrd_query_is_too_narrow(query_payload)
            else "query_too_narrow"
            if provider_query_status == "query_too_narrow"
            else "no_real_results"
            if not search_results and provider_query_status in {"no_results", "success", ""}
            else ""
        ),
        fixture_fallback_allowed=bool(search_filters.get("allow_fixture_fallback")),
        query_display_title=_clean_text(query_presentation.get("display_title")),
        query_display_mode=_clean_text(query_presentation.get("display_mode")),
        query_display_terms=_as_list(query_presentation.get("display_terms")),
    ).to_dict()
    if provider_error_message:
        context["provider_error_message"] = provider_error_message

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
    analysis_type = _clean_text(record.get("analysis_type")).upper()
    if analysis_type == "XRD":
        return _compare_xrd_candidate_to_literature(
            record,
            provider=active_provider,
            provider_scope=scope,
            max_claims=max_claims,
            filters=filters,
            user_documents=user_documents,
        )
    if analysis_type in {"DSC", "DTA", "TGA"}:
        return _compare_thermal_result_to_literature(
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
