"""Reusable Streamlit helpers for backend-driven literature comparison."""

from __future__ import annotations

import base64
import copy
import os
from contextlib import nullcontext
from typing import Any, Mapping

import httpx
import streamlit as st

from core.project_io import save_project_archive
from utils.diagnostics import record_exception


DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"
DEMO_PROVIDER_IDS = {"fixture_provider"}
DEMO_RESULT_SOURCES = {"fixture_search"}
DEFAULT_LITERATURE_COMPARE_REQUEST = {
    "provider_ids": ["openalex_like_provider"],
    "persist": True,
    "max_claims": 2,
    "filters": {"analysis_type": "XRD", "allow_fixture_fallback": False},
    "user_documents": [],
}


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _ui_text(lang: str, tr: str, en: str, **kwargs: Any) -> str:
    text = tr if _clean_text(lang).lower() == "tr" else en
    if kwargs:
        return text.format(**kwargs)
    return text


def _to_text_list(value: Any) -> list[str]:
    if value in (None, "", [], (), {}):
        return []
    if isinstance(value, str):
        cleaned = _clean_text(value)
        return [cleaned] if cleaned else []
    if isinstance(value, (list, tuple, set)):
        items: list[str] = []
        for item in value:
            cleaned = _clean_text(item)
            if cleaned:
                items.append(cleaned)
        return items
    cleaned = _clean_text(value)
    return [cleaned] if cleaned else []


def _streamlit_block():
    container = getattr(st, "container", None)
    if callable(container):
        return container()
    return nullcontext()


def _provider_scope_tokens(value: Any) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for item in _to_text_list(value):
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        tokens.append(item)
    return tokens


def _is_fixture_marker(value: str) -> bool:
    token = _clean_text(value).lower()
    return token in DEMO_PROVIDER_IDS or token in DEMO_RESULT_SOURCES


def _citation_provenance(citation: Mapping[str, Any]) -> dict[str, Any]:
    provenance = citation.get("provenance")
    return dict(provenance) if isinstance(provenance, Mapping) else {}


def _citation_is_fixture(citation: Mapping[str, Any]) -> bool:
    provenance = _citation_provenance(citation)
    providers = _provider_scope_tokens(provenance.get("provider_scope"))
    provider_id = _clean_text(provenance.get("provider_id"))
    result_source = _clean_text(provenance.get("result_source"))
    return any(_is_fixture_marker(token) for token in providers + [provider_id, result_source])


def _comparison_is_fixture(
    comparison: Mapping[str, Any],
    *,
    citations: list[dict[str, Any]],
    provider_badges: list[str],
) -> bool:
    if citations:
        return all(_citation_is_fixture(citation) for citation in citations)
    tokens = [_clean_text(comparison.get("provider_id"))] + provider_badges
    return any(_is_fixture_marker(token) for token in tokens)


def _record_literature_flags(record: Mapping[str, Any] | None) -> dict[str, Any]:
    source = dict(record or {})
    context = dict(source.get("literature_context") or {})
    citations = [dict(item) for item in (source.get("citations") or []) if isinstance(item, Mapping)]
    provider_scope = _provider_scope_tokens(context.get("provider_scope"))
    fixture_from_scope = any(_is_fixture_marker(token) for token in provider_scope)
    fixture_citations = [citation for citation in citations if _citation_is_fixture(citation)]
    fixture_detected = fixture_from_scope or bool(fixture_citations)
    fixture_only = fixture_detected and (
        not citations or len(fixture_citations) == len(citations)
    )
    return {
        "provider_scope": provider_scope,
        "fixture_detected": fixture_detected,
        "fixture_only": fixture_only,
    }


def _apply_report_guardrail_flags(record: dict[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(record)
    flags = _record_literature_flags(updated)
    report_payload = dict(updated.get("report_payload") or {})
    report_payload["literature_fixture_detected"] = flags["fixture_detected"]
    report_payload["literature_fixture_only"] = flags["fixture_only"]
    report_payload["literature_report_default_policy"] = (
        "exclude_from_production_report" if flags["fixture_only"] else "production"
    )
    updated["report_payload"] = report_payload
    return updated


def _comparison_claim_lookup(record: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    claims: dict[str, dict[str, Any]] = {}
    for item in record.get("literature_claims") or []:
        if not isinstance(item, Mapping):
            continue
        claim_id = _clean_text(item.get("claim_id"))
        if claim_id:
            claims[claim_id] = dict(item)
    return claims


def _access_basis_key(*, access_class: str, fixture: bool) -> str:
    if fixture:
        return "fixture"
    token = _clean_text(access_class).lower()
    if token == "user_provided_document":
        return "user_document"
    if token == "open_access_full_text":
        return "open_access"
    if token == "abstract_only":
        return "abstract"
    return "metadata"


def _provider_badges_for_citations(
    citations: list[dict[str, Any]],
    *,
    provider_scope: list[str],
) -> list[str]:
    providers: list[str] = []
    seen: set[str] = set()
    for citation in citations:
        provenance = _citation_provenance(citation)
        candidates = _provider_scope_tokens(provenance.get("provider_scope"))
        if not candidates:
            candidates = _provider_scope_tokens(
                [provenance.get("provider_id")] + provider_scope
            )
        for item in candidates:
            key = item.casefold()
            if key in seen:
                continue
            seen.add(key)
            providers.append(item)
    if not providers:
        return provider_scope
    return providers


def _evidence_badges_for_citations(citations: list[dict[str, Any]]) -> list[str]:
    badges: list[str] = []
    seen: set[str] = set()
    for citation in citations:
        badge = _access_basis_key(
            access_class=_clean_text(citation.get("access_class")),
            fixture=_citation_is_fixture(citation),
        )
        if badge in seen:
            continue
        seen.add(badge)
        badges.append(badge)
    if not badges:
        return ["metadata"]
    return badges


def _label_text(lang: str, key: str) -> str:
    labels = {
        "supports": (
            "Temkinli uyumlu",
            "Cautiously consistent",
        ),
        "partially_supports": (
            "Kısmi uyumlu",
            "Partially consistent",
        ),
        "contradicts": (
            "Alternatif veya çelişen",
            "Alternative or contradictory",
        ),
        "related_but_inconclusive": (
            "İlgili ama sonuçsuz",
            "Related but inconclusive",
        ),
        "insufficient_literature_evidence": (
            "Yetersiz literatür kanıtı",
            "Insufficient literature evidence",
        ),
        "demo_fixture_only": (
            "Yalnızca demo fixture",
            "Demo fixture only",
        ),
        "related_but_non_validating": (
            "İlgili ama doğrulayıcı değil",
            "Related but non-validating",
        ),
    }
    tr, en = labels.get(key, ("İlgili ama sonuçsuz", "Related but inconclusive"))
    return _ui_text(lang, tr, en)


def _confidence_text(lang: str, value: str) -> str:
    labels = {
        "high": ("yüksek", "high"),
        "moderate": ("orta", "moderate"),
        "low": ("düşük", "low"),
    }
    tr, en = labels.get(_clean_text(value).lower(), ("düşük", "low"))
    return _ui_text(lang, tr, en)


def _evidence_badge_text(lang: str, key: str) -> str:
    labels = {
        "fixture": ("fixture", "fixture"),
        "metadata": ("metadata", "metadata"),
        "abstract": ("özet", "abstract"),
        "open_access": ("açık erişim", "open access"),
        "user_document": ("kullanıcı dokümanı", "user document"),
    }
    tr, en = labels.get(key, ("metadata", "metadata"))
    return _ui_text(lang, tr, en)


def _validation_posture_text(lang: str, value: str) -> str:
    labels = {
        "contextual_only": ("yalnızca bağlamsal", "contextual only"),
        "related_support": ("aday fazla ilişkili", "related support"),
        "alternative_interpretation": ("alternatif yorum", "alternative interpretation"),
        "non_validating": ("doğrulayıcı değil", "non-validating"),
    }
    tr, en = labels.get(_clean_text(value).lower(), ("doğrulayıcı değil", "non-validating"))
    return _ui_text(lang, tr, en)


def _match_status_text(lang: str, value: str) -> str:
    labels = {
        "matched": ("matched", "matched"),
        "no_match": ("no_match", "no_match"),
        "not_run": ("not_run", "not_run"),
    }
    tr, en = labels.get(_clean_text(value).lower(), (value or "n/a", value or "n/a"))
    return _ui_text(lang, tr, en)


def _xrd_comparison_note_text(row: Mapping[str, Any], *, lang: str) -> str:
    candidate = _clean_text(row.get("candidate_name")) or _ui_text(lang, "aday faz", "the candidate phase")
    match_status = _clean_text(row.get("match_status_snapshot")).lower()
    confidence_band = _clean_text(row.get("confidence_band_snapshot")).lower()
    posture = _clean_text(row.get("validation_posture")).lower()

    if match_status == "no_match":
        return _ui_text(
            lang,
            "{candidate} için XRD karakterizasyonu tartışılır; mevcut örnek için faz doğrulaması sağlamaz ve sonuç no_match olarak kalır.",
            "This paper discusses XRD characterization of {candidate}; it does not validate a phase call for the current sample, and the result remains no_match.",
            candidate=candidate,
        )
    if posture == "alternative_interpretation":
        return _ui_text(
            lang,
            "Kaynak aday fazla ilişkilidir ancak mevcut desen için doğrulayıcı destek sağlamaz; alternatif bir yorum olasılığına işaret edebilir.",
            "This source is related to the candidate context, but it does not provide validating support for the current pattern and may indicate an alternative interpretation.",
        )
    if posture == "related_support" and confidence_band not in {"low", "no_match", "not_run"}:
        return _ui_text(
            lang,
            "{candidate} için literatürde benzer XRD tartışmaları bulundu; yine de mevcut sonuç yalnızca nitel faz taraması bağlamında yorumlanmalıdır.",
            "This paper is relevant to {candidate}, but the present result should still be interpreted within qualitative phase-screening limits.",
            candidate=candidate,
        )
    if posture == "contextual_only":
        return _ui_text(
            lang,
            "Bu kaynak yalnızca aday faz bağlamı sunar; mevcut örnek için faz doğrulaması sağlamaz.",
            "This source provides candidate-phase context only and does not validate the current sample as that phase.",
        )
    return _ui_text(
        lang,
        "Kaynak en iyi adayla ilişkilidir, ancak mevcut XRD kanıtı sınırlıdır ve faz doğrulaması sağlamaz.",
        "This source is relevant to the top-ranked candidate, but the current XRD evidence remains limited and non-validating.",
    )


def _comparison_display_label(
    row: Mapping[str, Any],
    *,
    summary: Mapping[str, Any],
    context: Mapping[str, Any],
    citations: list[dict[str, Any]],
) -> str:
    raw_label = _clean_text(row.get("support_label")).lower() or "related_but_inconclusive"
    if raw_label not in {"supports", "partially_supports"}:
        return raw_label

    if any(_citation_is_fixture(citation) for citation in citations):
        return "demo_fixture_only"

    match_status = _clean_text(summary.get("match_status")).lower()
    confidence_band = _clean_text(summary.get("confidence_band")).lower()
    comparison_confidence = _clean_text(row.get("confidence")).lower()
    access_classes = {
        _clean_text(citation.get("access_class")).lower()
        for citation in citations
        if _clean_text(citation.get("access_class"))
    }
    weak_evidence = (
        context.get("metadata_only_evidence")
        or comparison_confidence == "low"
        or (access_classes and access_classes.issubset({"metadata_only", "abstract_only"}))
        or not citations
    )

    if match_status == "no_match" or confidence_band in {"no_match", "low", "not_run"}:
        return "insufficient_literature_evidence"
    if weak_evidence:
        return "related_but_non_validating"
    return raw_label


def _follow_up_check_text(lang: str, key: str) -> str:
    messages = {
        "citation_limited": (
            "En az bir iddia yeterli atıfla desteklenmedi; daha güçlü bilimsel yorum için ek doğrulayıcı deneyler gerekebilir.",
            "At least one claim remained citation-limited; additional confirmatory experiments may be required before stronger interpretation.",
        ),
        "low_confidence": (
            "Düşük güvenli literatür çıktıları doğrulama olarak değil, tarama bağlamı olarak ele alınmalıdır.",
            "Low-confidence literature outcomes should be treated as screening context only, not as validation.",
        ),
        "metadata_only": (
            "Literatür gerekçesinin bir bölümü yalnızca metadata veya özet düzeyine dayanıyor; açık erişim ya da kullanıcı dokümanları karşılaştırmayı iyileştirebilir.",
            "Some literature reasoning relies on metadata or abstract-level evidence only; open-access or user-provided documents could refine the comparison.",
        ),
        "restricted_excluded": (
            "Kapalı erişimli tam metin bilinçli olarak dışlandı; karşılaştırma tasarım gereği yasal olarak güvenlidir.",
            "Closed-access full text was intentionally excluded; the comparison remains legal-safe by design.",
        ),
        "demo_fixture": (
            "Fixture/demo kaynakları gerçek bibliyografik kanıt sayılmaz; üretim yorumlarında kullanılmamalıdır.",
            "Fixture/demo sources are not real bibliographic evidence and should not be used for production interpretation.",
        ),
    }
    tr, en = messages[key]
    return _ui_text(lang, tr, en)


def _backend_base_url(base_url: str | None = None) -> str:
    explicit = _clean_text(base_url)
    if explicit:
        return explicit.rstrip("/")
    env_value = (
        os.getenv("THERMOANALYZER_BACKEND_URL")
        or os.getenv("TA_BACKEND_URL")
        or DEFAULT_BACKEND_URL
    )
    return _clean_text(env_value).rstrip("/")


def _backend_token(api_token: str | None = None) -> str:
    explicit = _clean_text(api_token)
    if explicit:
        return explicit
    return _clean_text(
        os.getenv("THERMOANALYZER_BACKEND_TOKEN")
        or os.getenv("TA_BACKEND_TOKEN")
        or ""
    )


def _backend_headers(api_token: str | None = None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    token = _backend_token(api_token)
    if token:
        headers["X-TA-Token"] = token
    return headers


def _request_json(
    method: str,
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    json_payload: Mapping[str, Any] | None = None,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    response = httpx.request(
        method=method,
        url=url,
        headers=dict(headers or {}),
        json=dict(json_payload or {}) if json_payload is not None else None,
        timeout=timeout_seconds,
    )
    try:
        payload = response.json()
    except Exception:
        payload = {}
    if not response.is_success:
        detail = payload.get("detail") if isinstance(payload, Mapping) else ""
        raise RuntimeError(_clean_text(detail) or f"Backend request failed ({response.status_code}).")
    return dict(payload or {})


def _project_archive_base64(session_state: Mapping[str, Any]) -> str:
    archive_bytes = save_project_archive(session_state)
    return base64.b64encode(archive_bytes).decode("ascii")


def _default_compare_request(
    overrides: Mapping[str, Any] | None = None,
    *,
    current_record: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = copy.deepcopy(DEFAULT_LITERATURE_COMPARE_REQUEST)
    if _clean_text((current_record or {}).get("analysis_type")).upper() != "XRD":
        payload = {
            "provider_ids": ["fixture_provider"],
            "persist": True,
            "max_claims": 3,
            "filters": {},
            "user_documents": [],
        }
    for key, value in dict(overrides or {}).items():
        payload[key] = copy.deepcopy(value)
    return payload


def _load_backend_project(
    session_state: Mapping[str, Any],
    *,
    base_url: str | None = None,
    api_token: str | None = None,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    return _request_json(
        "POST",
        f"{_backend_base_url(base_url)}/project/load",
        headers=_backend_headers(api_token),
        json_payload={"archive_base64": _project_archive_base64(session_state)},
        timeout_seconds=timeout_seconds,
    )


def _fetch_result_detail(
    *,
    project_id: str,
    result_id: str,
    base_url: str | None = None,
    api_token: str | None = None,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    return _request_json(
        "GET",
        f"{_backend_base_url(base_url)}/workspace/{project_id}/results/{result_id}",
        headers=_backend_headers(api_token),
        timeout_seconds=timeout_seconds,
    )


def merge_literature_detail_into_record(
    record: Mapping[str, Any] | None,
    *,
    compare_response: Mapping[str, Any] | None = None,
    detail_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    updated = copy.deepcopy(dict(record or {}))
    detail = dict(detail_payload or {})
    compare = dict(compare_response or {})

    for key in ("summary", "processing", "provenance", "validation", "review"):
        if isinstance(detail.get(key), Mapping):
            updated[key] = copy.deepcopy(detail[key])

    if detail.get("result") and not updated.get("id"):
        updated["id"] = detail["result"].get("id")

    if detail.get("result") and detail["result"].get("dataset_key") and not updated.get("dataset_key"):
        updated["dataset_key"] = detail["result"].get("dataset_key")

    updated["literature_context"] = copy.deepcopy(
        detail.get("literature_context")
        or compare.get("literature_context")
        or updated.get("literature_context")
        or {}
    )
    updated["literature_claims"] = copy.deepcopy(
        detail.get("literature_claims")
        or compare.get("literature_claims")
        or updated.get("literature_claims")
        or []
    )
    updated["literature_comparisons"] = copy.deepcopy(
        detail.get("literature_comparisons")
        or compare.get("literature_comparisons")
        or updated.get("literature_comparisons")
        or []
    )
    updated["citations"] = copy.deepcopy(
        detail.get("citations")
        or compare.get("citations")
        or updated.get("citations")
        or []
    )
    return _apply_report_guardrail_flags(updated)


def call_literature_compare(
    *,
    session_state: Mapping[str, Any],
    result_id: str,
    current_record: Mapping[str, Any] | None = None,
    request_payload: Mapping[str, Any] | None = None,
    base_url: str | None = None,
    api_token: str | None = None,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    loaded = _load_backend_project(
        session_state,
        base_url=base_url,
        api_token=api_token,
        timeout_seconds=timeout_seconds,
    )
    project_id = _clean_text(loaded.get("project_id"))
    if not project_id:
        raise RuntimeError("Backend project load did not return a project_id.")

    compare_response = _request_json(
        "POST",
        f"{_backend_base_url(base_url)}/workspace/{project_id}/results/{result_id}/literature/compare",
        headers=_backend_headers(api_token),
        json_payload=_default_compare_request(request_payload, current_record=current_record),
        timeout_seconds=timeout_seconds,
    )
    detail_payload = compare_response.get("detail")
    if not isinstance(detail_payload, Mapping):
        detail_payload = _fetch_result_detail(
            project_id=project_id,
            result_id=result_id,
            base_url=base_url,
            api_token=api_token,
            timeout_seconds=timeout_seconds,
        )

    updated_record = merge_literature_detail_into_record(
        current_record,
        compare_response=compare_response,
        detail_payload=detail_payload,
    )
    return {
        "project_id": project_id,
        "response": compare_response,
        "detail": dict(detail_payload or {}),
        "updated_record": updated_record,
    }


def _citation_lookup(record: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for item in record.get("citations") or []:
        if not isinstance(item, Mapping):
            continue
        citation_id = _clean_text(item.get("citation_id"))
        if citation_id:
            lookup[citation_id] = dict(item)
    return lookup


def build_literature_sections(record: Mapping[str, Any] | None) -> dict[str, Any]:
    source = dict(record or {})
    comparisons = [dict(item) for item in (source.get("literature_comparisons") or []) if isinstance(item, Mapping)]
    citations_by_id = _citation_lookup(source)
    context = dict(source.get("literature_context") or {})
    summary = dict(source.get("summary") or {})
    claim_lookup = _comparison_claim_lookup(source)
    flags = _record_literature_flags(source)
    xrd_candidate_mode = bool(
        _clean_text(source.get("analysis_type")).upper() == "XRD"
        and (
            _clean_text(context.get("query_text"))
            or any(_clean_text(item.get("paper_title")) for item in comparisons if isinstance(item, Mapping))
        )
    )

    if not comparisons and not citations_by_id and not context:
        return {
            "has_payload": False,
            "comparisons": [],
            "supporting_references": [],
            "alternative_references": [],
            "follow_up_checks": [],
            "context": {},
            "fixture_detected": False,
            "fixture_only": False,
            "provider_scope": [],
            "xrd_candidate_mode": False,
            "paper_cards": [],
            "candidate_summary": {},
        }

    supporting_ids: list[str] = []
    alternative_ids: list[str] = []
    comparison_rows: list[dict[str, Any]] = []
    for item in comparisons:
        citation_ids = [
            _clean_text(token)
            for token in (item.get("citation_ids") or [])
            if _clean_text(token)
        ]
        citation_items = [citations_by_id[citation_id] for citation_id in citation_ids if citation_id in citations_by_id]
        display_label_key = _comparison_display_label(
            item,
            summary=summary,
            context=context,
            citations=citation_items,
        )
        claim = claim_lookup.get(_clean_text(item.get("claim_id")))
        provider_badges = _provider_badges_for_citations(citation_items, provider_scope=flags["provider_scope"])
        evidence_badges = _evidence_badges_for_citations(citation_items)
        paper_title = _clean_text(item.get("paper_title")) or _clean_text((citation_items[0] if citation_items else {}).get("title"))
        paper_year = item.get("paper_year") if item.get("paper_year") not in (None, "") else (citation_items[0].get("year") if citation_items else None)
        paper_journal = _clean_text(item.get("paper_journal")) or _clean_text((citation_items[0] if citation_items else {}).get("journal"))
        paper_doi = _clean_text(item.get("paper_doi")) or _clean_text((citation_items[0] if citation_items else {}).get("doi"))
        paper_url = _clean_text(item.get("paper_url")) or _clean_text((citation_items[0] if citation_items else {}).get("url"))
        provider_id = _clean_text(item.get("provider_id")) or ", ".join(provider_badges)
        fixture_row = _comparison_is_fixture(item, citations=citation_items, provider_badges=provider_badges)
        comparison_rows.append(
            {
                "claim_id": _clean_text(item.get("claim_id")) or "C1",
                "claim_text": _clean_text((claim or {}).get("claim_text"))
                or _clean_text(item.get("claim_text"))
                or "No human-readable scientific claim was recorded.",
                "candidate_name": _clean_text(item.get("candidate_name")) or _clean_text(context.get("candidate_display_name") or context.get("candidate_name")),
                "candidate_formula": _clean_text(item.get("candidate_formula")) or _clean_text(context.get("candidate_formula")),
                "paper_title": paper_title,
                "paper_year": paper_year,
                "paper_journal": paper_journal,
                "paper_doi": paper_doi,
                "paper_url": paper_url,
                "provider_id": provider_id,
                "access_class": _clean_text(item.get("access_class")) or _clean_text((citation_items[0] if citation_items else {}).get("access_class")) or "metadata_only",
                "comparison_note": _clean_text(item.get("comparison_note")) or _clean_text(item.get("rationale")),
                "validation_posture": _clean_text(item.get("validation_posture")) or "non_validating",
                "query_text": _clean_text(item.get("query_text")) or _clean_text(context.get("query_text")),
                "match_status_snapshot": _clean_text(item.get("match_status_snapshot")) or _clean_text(context.get("match_status_snapshot") or summary.get("match_status")),
                "confidence_band_snapshot": _clean_text(item.get("confidence_band_snapshot")) or _clean_text(context.get("confidence_band_snapshot") or summary.get("confidence_band")),
                "support_label": _clean_text(item.get("support_label")) or "related_but_inconclusive",
                "display_label_key": display_label_key,
                "confidence": _clean_text(item.get("confidence")) or "low",
                "rationale": _clean_text(item.get("rationale")) or "",
                "citation_ids": citation_ids,
                "provider_badges": provider_badges,
                "evidence_badges": evidence_badges,
                "fixture": fixture_row,
            }
        )
        if display_label_key in {"supports", "partially_supports"}:
            for citation_id in citation_ids:
                if citation_id not in supporting_ids:
                    supporting_ids.append(citation_id)
        else:
            for citation_id in citation_ids:
                if citation_id not in alternative_ids:
                    alternative_ids.append(citation_id)

    follow_up_checks: list[str] = []
    if any(not row["citation_ids"] for row in comparison_rows):
        follow_up_checks.append("citation_limited")
    if any(row["confidence"].lower() == "low" for row in comparison_rows):
        follow_up_checks.append("low_confidence")
    citation_access_classes = {
        _clean_text(item.get("access_class")).lower()
        for item in citations_by_id.values()
        if _clean_text(item.get("access_class"))
    }
    if context.get("metadata_only_evidence") or citation_access_classes & {"abstract_only", "metadata_only"}:
        follow_up_checks.append("metadata_only")
    if context.get("restricted_content_used") is False:
        follow_up_checks.append("restricted_excluded")
    if flags["fixture_detected"]:
        follow_up_checks.append("demo_fixture")

    paper_cards = [
        row
        for row in comparison_rows
        if not row.get("fixture") and (row.get("paper_title") or row.get("paper_doi") or row.get("paper_url"))
    ]
    candidate_summary = {
        "accepted_match_status": _clean_text(summary.get("match_status") or context.get("match_status_snapshot")),
        "best_ranked_candidate": _clean_text(
            context.get("candidate_display_name")
            or context.get("candidate_name")
            or summary.get("top_candidate_display_name_unicode")
            or summary.get("top_candidate_display_name")
            or summary.get("top_candidate_name")
        ),
        "formula": _clean_text(context.get("candidate_formula") or summary.get("top_candidate_formula")),
        "score": summary.get("top_candidate_score") if summary.get("top_candidate_score") not in (None, "") else context.get("top_candidate_score_snapshot"),
        "shared_peaks": summary.get("top_candidate_shared_peak_count") if summary.get("top_candidate_shared_peak_count") not in (None, "") else context.get("shared_peak_count_snapshot"),
        "coverage": summary.get("top_candidate_coverage_ratio") if summary.get("top_candidate_coverage_ratio") not in (None, "") else context.get("coverage_ratio_snapshot"),
        "weighted_overlap": summary.get("top_candidate_weighted_overlap_score") if summary.get("top_candidate_weighted_overlap_score") not in (None, "") else context.get("weighted_overlap_score_snapshot"),
        "provider": _clean_text(summary.get("top_candidate_provider") or context.get("candidate_provider_snapshot")),
        "result_source": _clean_text(summary.get("library_result_source") or context.get("candidate_result_source_snapshot")),
        "query_text": _clean_text(context.get("query_text")),
        "query_rationale": _clean_text(context.get("query_rationale")),
        "real_literature_available": bool(context.get("real_literature_available")),
        "fixture_only": flags["fixture_only"],
    }

    return {
        "has_payload": True,
        "comparisons": comparison_rows,
        "supporting_references": [citations_by_id[citation_id] for citation_id in supporting_ids if citation_id in citations_by_id],
        "alternative_references": [citations_by_id[citation_id] for citation_id in alternative_ids if citation_id in citations_by_id],
        "follow_up_checks": follow_up_checks,
        "context": context,
        "fixture_detected": flags["fixture_detected"],
        "fixture_only": flags["fixture_only"],
        "provider_scope": flags["provider_scope"],
        "summary": summary,
        "xrd_candidate_mode": xrd_candidate_mode,
        "paper_cards": paper_cards,
        "candidate_summary": candidate_summary,
    }


def _render_citation_item(citation: Mapping[str, Any], *, lang: str, provider_scope: list[str]) -> None:
    title = _clean_text(citation.get("title")) or "Untitled source"
    year = _clean_text(citation.get("year")) or "n.d."
    journal = _clean_text(citation.get("journal"))
    doi = _clean_text(citation.get("doi"))
    url = _clean_text(citation.get("url"))
    access_class = _clean_text(citation.get("access_class")) or "metadata_only"
    fixture = _citation_is_fixture(citation)
    provider_badges = _provider_badges_for_citations([dict(citation)], provider_scope=provider_scope)
    evidence_badge = _evidence_badge_text(
        lang,
        _access_basis_key(access_class=access_class, fixture=fixture),
    )

    with _streamlit_block():
        st.markdown(f"**{title}**")
        detail_parts = [f"{year}"]
        if journal:
            detail_parts.append(journal)
        detail_parts.append(f"`{access_class}`")
        if provider_badges:
            detail_parts.append(
                _ui_text(
                    lang,
                    "sağlayıcı: {providers}",
                    "provider: {providers}",
                    providers=", ".join(provider_badges),
                )
            )
        detail_parts.append(
            _ui_text(lang, "kanıt temeli: {basis}", "evidence basis: {basis}", basis=evidence_badge)
        )
        if fixture:
            detail_parts.append(_ui_text(lang, "demo fixture", "demo fixture"))
        st.caption(" | ".join(detail_parts))

        if fixture:
            if doi or url:
                st.caption(
                    _ui_text(
                        lang,
                        "Demo DOI/URL gösterimi üretim referansı değildir; yetkili bibliyografik doğrulama olarak kullanılmamalıdır.",
                        "Demo DOI/URL display is not a production reference and must not be treated as authoritative bibliographic validation.",
                    )
                )
        elif doi:
            st.markdown(f"DOI: `{doi}`")
        elif url:
            st.markdown(url)


def _render_xrd_candidate_summary(candidate_summary: Mapping[str, Any], *, lang: str) -> None:
    st.markdown(f"**{_ui_text(lang, 'XRD Aday Kanıt Özeti', 'XRD Candidate Evidence Summary')}**")
    with _streamlit_block():
        st.caption(
            _ui_text(
                lang,
                "Kabul durumu: {status} | En iyi aday: {candidate}",
                "Accepted match status: {status} | Best-ranked candidate: {candidate}",
                status=_match_status_text(lang, _clean_text(candidate_summary.get("accepted_match_status")) or "n/a"),
                candidate=_clean_text(candidate_summary.get("best_ranked_candidate")) or _ui_text(lang, "kayıt yok", "not recorded"),
            )
        )
        st.caption(
            _ui_text(
                lang,
                "Formül: {formula} | Skor: {score} | Ortak pik: {shared_peaks}",
                "Formula: {formula} | Score: {score} | Shared peaks: {shared_peaks}",
                formula=_clean_text(candidate_summary.get("formula")) or _ui_text(lang, "kayıt yok", "not recorded"),
                score=str(candidate_summary.get("score") if candidate_summary.get("score") not in (None, "") else _ui_text(lang, "kayıt yok", "not recorded")),
                shared_peaks=str(candidate_summary.get("shared_peaks") if candidate_summary.get("shared_peaks") not in (None, "") else _ui_text(lang, "kayıt yok", "not recorded")),
            )
        )
        st.caption(
            _ui_text(
                lang,
                "Kapsama: {coverage} | Ağırlıklı örtüşme: {weighted} | Sağlayıcı/kaynak: {provider} / {result_source}",
                "Coverage: {coverage} | Weighted overlap: {weighted} | Provider/result source: {provider} / {result_source}",
                coverage=str(candidate_summary.get("coverage") if candidate_summary.get("coverage") not in (None, "") else _ui_text(lang, "kayıt yok", "not recorded")),
                weighted=str(candidate_summary.get("weighted_overlap") if candidate_summary.get("weighted_overlap") not in (None, "") else _ui_text(lang, "kayıt yok", "not recorded")),
                provider=_clean_text(candidate_summary.get("provider")) or _ui_text(lang, "kayıt yok", "not recorded"),
                result_source=_clean_text(candidate_summary.get("result_source")) or _ui_text(lang, "kayıt yok", "not recorded"),
            )
        )


def _render_xrd_paper_card(row: Mapping[str, Any], *, lang: str) -> None:
    with _streamlit_block():
        st.markdown(f"**{_clean_text(row.get('paper_title')) or _ui_text(lang, 'Başlık kaydedilmedi', 'Title not recorded')}**")
        st.caption(
            _ui_text(
                lang,
                "Yıl: {year} | Dergi: {journal} | Sağlayıcı: {provider} | Erişim: {access} | Duruş: {posture}",
                "Year: {year} | Journal: {journal} | Provider: {provider} | Access: {access} | Posture: {posture}",
                year=str(row.get("paper_year") if row.get("paper_year") not in (None, "") else "n.d."),
                journal=_clean_text(row.get("paper_journal")) or _ui_text(lang, "kayıt yok", "not recorded"),
                provider=_clean_text(row.get("provider_id")) or _ui_text(lang, "kayıt yok", "not recorded"),
                access=_evidence_badge_text(lang, _access_basis_key(access_class=_clean_text(row.get("access_class")), fixture=False)),
                posture=_validation_posture_text(lang, _clean_text(row.get("validation_posture"))),
            )
        )
        st.markdown(_xrd_comparison_note_text(row, lang=lang))
        if _clean_text(row.get("paper_doi")):
            st.markdown(f"DOI: `{_clean_text(row.get('paper_doi'))}`")
        elif _clean_text(row.get("paper_url")):
            st.markdown(_clean_text(row.get("paper_url")))


def render_literature_sections(record: Mapping[str, Any] | None, *, lang: str) -> None:
    sections = build_literature_sections(record)
    if not sections["has_payload"]:
        st.caption(
            _ui_text(
                lang,
                "Henüz literatür karşılaştırması çalıştırılmadı. Kaydedilmiş sonuç üzerinden karşılaştırmayı tetikleyin.",
                "No literature comparison has been run yet. Trigger compare from the saved result to populate this panel.",
            )
        )
        return

    if sections.get("xrd_candidate_mode"):
        if sections["fixture_detected"]:
            st.warning(
                _ui_text(
                    lang,
                    "Demo literature fixture output — gerçek bibliyografik kaynak değildir",
                    "Demo literature fixture output — not a real bibliographic source",
                )
            )
        _render_xrd_candidate_summary(sections.get("candidate_summary") or {}, lang=lang)
        st.markdown(f"**{_ui_text(lang, 'En İyi Aday İçin Literatür Taraması', 'Literature Check For Top-Ranked Candidate')}**")
        if _clean_text((sections.get("candidate_summary") or {}).get("query_text")):
            st.caption(
                _ui_text(
                    lang,
                    "Sorgu: {query}",
                    "Query: {query}",
                    query=_clean_text((sections.get("candidate_summary") or {}).get("query_text")),
                )
            )
        if _clean_text((sections.get("candidate_summary") or {}).get("query_rationale")):
            st.caption(_clean_text((sections.get("candidate_summary") or {}).get("query_rationale")))
        if _clean_text((sections.get("candidate_summary") or {}).get("accepted_match_status")).lower() == "no_match":
            st.caption(
                _ui_text(
                    lang,
                    "Literatürde benzer XRD tartışmaları bulunsa bile mevcut örnek için faz doğrulaması sağlamaz; sonuç no_match olarak kalır.",
                    "Even if related XRD papers are found, they do not validate a phase call for the current sample; the result remains no_match.",
                )
            )
        elif sections["fixture_detected"] and not (sections.get("candidate_summary") or {}).get("real_literature_available"):
            st.caption(
                _ui_text(
                    lang,
                    "Gerçek bibliyografik sonuç bulunamadı; varsa fixture/demo çıktıları yetkili yayın kartı olarak gösterilmez.",
                    "No real bibliographic papers were found; any fixture/demo output is not shown as authoritative paper cards.",
                )
            )
        elif not (sections.get("candidate_summary") or {}).get("real_literature_available") and not sections["fixture_detected"]:
            st.caption(
                _ui_text(
                    lang,
                    "Bu aday için gerçek bibliyografik sonuç bulunamadı veya gerçek literatür araması şu anda kullanılamıyor.",
                    "No real bibliographic papers were found for this candidate, or real literature search is currently unavailable.",
                )
            )

        if sections.get("paper_cards"):
            for row in sections["paper_cards"]:
                _render_xrd_paper_card(row, lang=lang)
        else:
            st.caption(
                _ui_text(
                    lang,
                    "Bu aday için görüntülenecek yayın kartı bulunamadı.",
                    "No paper cards are available for this candidate.",
                )
            )

        st.markdown(f"**{_ui_text(lang, 'Önerilen Takip Literatür Kontrolleri', 'Recommended Follow-Up Literature Checks')}**")
        for item in sections["follow_up_checks"]:
            st.markdown(f"- {_follow_up_check_text(lang, item)}")
        if not sections["follow_up_checks"]:
            st.caption(
                _ui_text(
                    lang,
                    "Ek takip kontrolü kaydedilmedi; yine de literatür mevcut XRD sonucunun yerine geçmez.",
                    "No additional follow-up checks were recorded; literature still does not replace the current XRD result.",
                )
            )
        return

    if sections["fixture_detected"]:
        st.warning(
            _ui_text(
                lang,
                "Demo literature fixture output — gerçek bibliyografik kaynak değildir",
                "Demo literature fixture output — not a real bibliographic source",
            )
        )
        st.caption(
            _ui_text(
                lang,
                "Bu panel geliştirme/demo çıktısı içeriyor; dış bilimsel doğrulama olarak yorumlanmamalıdır.",
                "This panel contains development/demo output and must not be interpreted as external scientific validation.",
            )
        )
    elif _clean_text(sections["summary"].get("match_status")).lower() == "no_match":
        st.caption(
            _ui_text(
                lang,
                "Literatür karşılaştırması no_match sonucunu doğrulamaz; çıktı yalnızca temkinli tarama bağlamı sunar.",
                "Literature comparison does not validate a no_match result; it only adds cautious screening context.",
            )
        )

    st.markdown(f"**{_ui_text(lang, 'Literatür Karşılaştırması', 'Literature Comparison')}**")
    for row in sections["comparisons"]:
        citation_note = ", ".join(row["citation_ids"]) if row["citation_ids"] else _ui_text(lang, "yok", "none")
        provider_note = ", ".join(row["provider_badges"]) or _ui_text(lang, "kayıt yok", "not recorded")
        evidence_note = ", ".join(_evidence_badge_text(lang, item) for item in row["evidence_badges"])
        with _streamlit_block():
            st.markdown(f"**{row['claim_text']}**")
            st.caption(
                _ui_text(
                    lang,
                    "İddia Kimliği: {claim_id} | Durum: {label} | Güven: {confidence}",
                    "Claim ID: {claim_id} | Status: {label} | Confidence: {confidence}",
                    claim_id=row["claim_id"],
                    label=_label_text(lang, row["display_label_key"]),
                    confidence=_confidence_text(lang, row["confidence"]),
                )
            )
            st.caption(
                _ui_text(
                    lang,
                    "Sağlayıcı: {providers} | Kanıt temeli: {evidence}",
                    "Provider: {providers} | Evidence basis: {evidence}",
                    providers=provider_note,
                    evidence=evidence_note,
                )
            )
            st.markdown(row["rationale"] or _ui_text(lang, "Ek gerekçe kaydedilmedi.", "No additional rationale was recorded."))
            st.caption(
                _ui_text(
                    lang,
                    "Atıflar: {citations}",
                    "Citations: {citations}",
                    citations=citation_note,
                )
            )

    st.markdown(f"**{_ui_text(lang, 'Destekleyen Kaynaklar', 'Supporting References')}**")
    if sections["supporting_references"]:
        for citation in sections["supporting_references"]:
            _render_citation_item(citation, lang=lang, provider_scope=sections["provider_scope"])
    else:
        st.caption(
            _ui_text(
                lang,
                "Destekleyen erişilebilir kaynak kaydedilmedi; çıktı niteliksel ve temkinli kalır.",
                "No supporting accessible references were retained; the output remains qualitative and cautionary.",
            )
        )

    st.markdown(f"**{_ui_text(lang, 'Çelişen veya Alternatif Kaynaklar', 'Contradictory or Alternative References')}**")
    if sections["alternative_references"]:
        for citation in sections["alternative_references"]:
            _render_citation_item(citation, lang=lang, provider_scope=sections["provider_scope"])
    else:
        st.caption(
            _ui_text(
                lang,
                "Çelişen erişilebilir kaynak kaydedilmedi; bu durum yine de doğrulama anlamına gelmez.",
                "No contradictory accessible references were retained; this still does not imply confirmation.",
            )
        )

    st.markdown(f"**{_ui_text(lang, 'Önerilen Takip Literatür Kontrolleri', 'Recommended Follow-Up Literature Checks')}**")
    for index, item in enumerate(sections["follow_up_checks"], start=1):
        st.markdown(f"- {_follow_up_check_text(lang, item)}")
    if not sections["follow_up_checks"]:
        st.caption(
            _ui_text(
                lang,
                "Ek takip kontrolü kaydedilmedi; yine de karşılaştırma doğrulama yerine tarama bağlamı sağlar.",
                "No additional follow-up checks were recorded; the comparison still provides screening context rather than confirmation.",
            )
        )


def render_literature_compare_panel(
    *,
    record: Mapping[str, Any] | None,
    result_id: str | None,
    lang: str,
    key_prefix: str,
    request_payload: Mapping[str, Any] | None = None,
    base_url: str | None = None,
    api_token: str | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    current_record = copy.deepcopy(dict(record or {})) if record else None
    action_result: dict[str, Any] | None = None

    button_label = _ui_text(lang, "Literatür Karşılaştırması", "Literature Compare")
    helper_caption = _ui_text(
        lang,
        "Karşılaştırma yalnızca metadata, abstract, açık erişim veya kullanıcı dokümanlarını kullanır; kapalı metin kullanılmaz.",
        "Comparison uses metadata, abstracts, open-access text, or user documents only; closed text is never used.",
    )

    if not current_record or not _clean_text(result_id):
        st.button(button_label, disabled=True, key=f"{key_prefix}_run")
        st.caption(
            _ui_text(
                lang,
                "Önce sonuç oturuma kaydedilmelidir; ardından literatür karşılaştırması tetiklenebilir.",
                "The result must be saved first; literature compare can then be triggered.",
            )
        )
        render_literature_sections({}, lang=lang)
        return current_record, action_result

    if st.button(button_label, key=f"{key_prefix}_run"):
        try:
            with st.spinner(_ui_text(lang, "Literatür karşılaştırması çalışıyor...", "Running literature compare...")):
                outcome = call_literature_compare(
                    session_state=st.session_state,
                    result_id=_clean_text(result_id),
                    current_record=current_record,
                    request_payload=request_payload,
                    base_url=base_url,
                    api_token=api_token,
                )
            updated_record = outcome["updated_record"]
            st.session_state.setdefault("results", {})[updated_record["id"]] = updated_record
            current_record = updated_record
            action_result = {"status": "success", **outcome}
            st.success(
                _ui_text(
                    lang,
                    "Literatür karşılaştırması tamamlandı ve kaydedilmiş sonuca işlendi.",
                    "Literature comparison completed and was applied to the saved result.",
                )
            )
        except Exception as exc:
            error_id = record_exception(
                st.session_state,
                area="literature_compare",
                action="backend_compare",
                message="Literature compare request failed.",
                context={"result_id": _clean_text(result_id)},
                exception=exc,
            )
            st.warning(
                _ui_text(
                    lang,
                    "Literatür karşılaştırması tamamlanamadı: {error}",
                    "Literature comparison could not be completed: {error}",
                    error=f"{exc} (Error ID: {error_id})",
                )
            )
            action_result = {"status": "error", "error": str(exc), "error_id": error_id}

    st.caption(helper_caption)
    render_literature_sections(current_record or {}, lang=lang)
    return current_record, action_result
