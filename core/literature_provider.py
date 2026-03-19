"""Provider abstraction for legal-safe literature metadata and text retrieval."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Protocol

from core.citation_formatter import format_citation_text
from core.literature_models import normalize_literature_sources


ACCESS_CLASS_PRIORITY = {
    "restricted_external": 0,
    "metadata_only": 1,
    "abstract_only": 2,
    "open_access_full_text": 3,
    "user_provided_document": 4,
}


def _tokenize(value: str) -> list[str]:
    cleaned = "".join(ch if ch.isalnum() else " " for ch in str(value or "").lower())
    return [token for token in cleaned.split() if len(token) >= 3]


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _as_str_list(value: Any) -> list[str]:
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


def _access_rank(access_class: Any) -> int:
    return ACCESS_CLASS_PRIORITY.get(_clean_text(access_class).lower(), 0)


def citation_identity_key(candidate: Mapping[str, Any]) -> str:
    doi = _clean_text(candidate.get("doi")).lower()
    if doi:
        return f"doi:{doi}"
    url = _clean_text(candidate.get("url")).lower()
    if url:
        return f"url:{url}"
    title = _clean_text(candidate.get("title")).casefold()
    year = _clean_text(candidate.get("year"))
    if title:
        return f"title_year:{title}|{year}"
    provider_id = _clean_text((candidate.get("provenance") or {}).get("provider_id")).lower()
    source_id = _clean_text(candidate.get("source_id")).lower()
    return f"provider_source:{provider_id}|{source_id}"


def merge_literature_candidates(existing: Mapping[str, Any], incoming: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    incoming_map = dict(incoming)

    for key in ("title", "journal", "doi", "url", "citation_text", "source_license_note"):
        if not _clean_text(merged.get(key)) and _clean_text(incoming_map.get(key)):
            merged[key] = incoming_map.get(key)

    if not merged.get("year") and incoming_map.get("year"):
        merged["year"] = incoming_map.get("year")

    merged_authors = _as_str_list(merged.get("authors"))
    for author in _as_str_list(incoming_map.get("authors")):
        if author not in merged_authors:
            merged_authors.append(author)
    merged["authors"] = merged_authors

    merged_fields = _as_str_list(merged.get("available_fields"))
    for field_name in _as_str_list(incoming_map.get("available_fields")):
        if field_name not in merged_fields:
            merged_fields.append(field_name)
    merged["available_fields"] = merged_fields

    if _access_rank(incoming_map.get("access_class")) > _access_rank(merged.get("access_class")):
        merged["access_class"] = incoming_map.get("access_class")
        if _clean_text(incoming_map.get("abstract_text")):
            merged["abstract_text"] = incoming_map.get("abstract_text")
        if _clean_text(incoming_map.get("oa_full_text")):
            merged["oa_full_text"] = incoming_map.get("oa_full_text")
    else:
        if not _clean_text(merged.get("abstract_text")) and _clean_text(incoming_map.get("abstract_text")):
            merged["abstract_text"] = incoming_map.get("abstract_text")
        if not _clean_text(merged.get("oa_full_text")) and _clean_text(incoming_map.get("oa_full_text")):
            merged["oa_full_text"] = incoming_map.get("oa_full_text")

    existing_provenance = dict(existing.get("provenance") or {})
    incoming_provenance = dict(incoming_map.get("provenance") or {})
    provider_scope = _as_str_list(existing_provenance.get("provider_scope"))
    for provider_id in _as_str_list(incoming_provenance.get("provider_scope") or incoming_provenance.get("provider_id")):
        if provider_id not in provider_scope:
            provider_scope.append(provider_id)
    request_ids = _as_str_list(existing_provenance.get("provider_request_ids") or existing_provenance.get("request_id"))
    for request_id in _as_str_list(incoming_provenance.get("provider_request_ids") or incoming_provenance.get("request_id")):
        if request_id not in request_ids:
            request_ids.append(request_id)

    merged["provenance"] = {
        **existing_provenance,
        **incoming_provenance,
        "provider_id": _clean_text(existing_provenance.get("provider_id") or incoming_provenance.get("provider_id")),
        "provider_scope": provider_scope,
        "provider_request_ids": request_ids,
        "result_source": _clean_text(existing_provenance.get("result_source") or incoming_provenance.get("result_source")),
        "query": _clean_text(existing_provenance.get("query") or incoming_provenance.get("query")),
    }
    return merged


class LiteratureProvider(Protocol):
    provider_id: str
    provider_result_source: str
    last_request_id: str

    def search(self, query: str, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        ...

    def fetch_accessible_text(self, candidate: dict[str, Any]) -> dict[str, Any] | None:
        ...


class FixtureLiteratureProvider:
    """Synthetic provider used for MVP development and test coverage."""

    provider_id = "fixture_provider"
    provider_result_source = "fixture_search"

    def __init__(self, fixture_path: str | Path | None = None) -> None:
        self.fixture_path = Path(fixture_path) if fixture_path else (
            Path(__file__).resolve().parents[1] / "sample_data" / "literature_fixture_sources.json"
        )
        raw_payload = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        self._sources = normalize_literature_sources(raw_payload.get("sources") or [])
        self.last_request_id = ""

    def search(self, query: str, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        filters = dict(filters or {})
        modality_filter = {
            str(item).upper()
            for item in (filters.get("modalities") or [])
            if str(item).strip()
        }
        access_filter = {
            str(item).lower()
            for item in (filters.get("access_classes") or [])
            if str(item).strip()
        }
        query_tokens = _tokenize(query)
        request_id = f"litreq_{self.provider_id}_{uuid.uuid4().hex[:12]}"
        self.last_request_id = request_id

        ranked: list[tuple[int, dict[str, Any]]] = []
        for source in self._sources:
            provenance = dict(source.get("provenance") or {})
            source_modalities = {
                str(item).upper()
                for item in (provenance.get("modalities") or [])
                if str(item).strip()
            }
            if modality_filter and not (modality_filter & source_modalities):
                continue
            if access_filter and str(source.get("access_class") or "").lower() not in access_filter:
                continue

            searchable = " ".join(
                [
                    str(source.get("title") or ""),
                    str(source.get("abstract_text") or ""),
                    str(source.get("oa_full_text") or ""),
                    " ".join(str(item) for item in (provenance.get("keywords") or [])),
                ]
            ).lower()
            score = 0
            for token in query_tokens:
                if token in searchable:
                    score += 3
            for keyword in provenance.get("keywords") or []:
                if str(keyword).lower() in str(query).lower():
                    score += 2
            if query_tokens and score <= 0:
                continue

            candidate = dict(source)
            candidate["citation_text"] = candidate.get("citation_text") or format_citation_text(candidate)
            candidate["provenance"] = {
                **provenance,
                "provider_id": self.provider_id,
                "request_id": request_id,
                "result_source": self.provider_result_source,
                "query": query,
                "provider_scope": [self.provider_id],
                "provider_request_ids": [request_id],
            }
            ranked.append((score, candidate))

        ranked.sort(
            key=lambda item: (
                -item[0],
                -(item[1].get("year") or 0),
                str(item[1].get("title") or ""),
            )
        )
        return [candidate for _score, candidate in ranked[: int(filters.get("top_k") or 5)]]

    def fetch_accessible_text(self, candidate: dict[str, Any]) -> dict[str, Any] | None:
        access_class = str(candidate.get("access_class") or "metadata_only").lower()
        source_id = str(candidate.get("source_id") or "")

        # Legal guardrail: restricted external items are discoverable as metadata,
        # but their full text must not be fetched, cached, or reused in reasoning.
        if access_class == "restricted_external":
            return None

        if access_class == "open_access_full_text":
            text = str(candidate.get("oa_full_text") or candidate.get("abstract_text") or "").strip()
            if text:
                return {"source_id": source_id, "text": text, "field": "oa_full_text", "access_class": access_class}
            return None

        if access_class in {"abstract_only", "metadata_only"}:
            text = str(candidate.get("abstract_text") or "").strip()
            if text:
                return {"source_id": source_id, "text": text, "field": "abstract_text", "access_class": access_class}
            return None

        if access_class == "user_provided_document":
            text = str(candidate.get("oa_full_text") or candidate.get("abstract_text") or "").strip()
            if text:
                return {"source_id": source_id, "text": text, "field": "user_provided_document", "access_class": access_class}
            return None

        return None


class MetadataAPILiteratureProvider:
    """HTTP-client-ready metadata provider shell.

    Legal guardrail: this provider only returns provider-supplied metadata and any
    explicitly accessible text returned by the API. It must never crawl or retain
    closed/paywalled full text.
    """

    provider_id = "metadata_api_provider"
    provider_result_source = "metadata_api_search"

    def __init__(
        self,
        *,
        search_client: Callable[[str, dict[str, Any]], Any] | None = None,
    ) -> None:
        self._search_client = search_client
        self.last_request_id = ""

    def _request_payload(self, query: str, filters: dict[str, Any]) -> dict[str, Any]:
        return {
            "query": _clean_text(query),
            "filters": dict(filters or {}),
            "request_id": f"litreq_{self.provider_id}_{uuid.uuid4().hex[:12]}",
            "result_source": self.provider_result_source,
        }

    def search(self, query: str, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        payload = self._request_payload(query, dict(filters or {}))
        self.last_request_id = payload["request_id"]
        if self._search_client is None:
            return []

        raw_response = self._search_client(query, dict(filters or {}))
        result_source = payload["result_source"]
        request_id = payload["request_id"]
        rows: list[dict[str, Any]] = []

        if isinstance(raw_response, Mapping):
            request_id = _clean_text(raw_response.get("request_id")) or request_id
            result_source = _clean_text(raw_response.get("result_source")) or result_source
            rows = [dict(item) for item in (raw_response.get("results") or []) if isinstance(item, Mapping)]
        elif isinstance(raw_response, list):
            rows = [dict(item) for item in raw_response if isinstance(item, Mapping)]

        self.last_request_id = request_id
        normalized: list[dict[str, Any]] = []
        for item in normalize_literature_sources(rows):
            provenance = dict(item.get("provenance") or {})
            normalized.append(
                {
                    **item,
                    "citation_text": item.get("citation_text") or format_citation_text(item),
                    "provenance": {
                        **provenance,
                        "provider_id": self.provider_id,
                        "request_id": request_id,
                        "result_source": result_source,
                        "query": query,
                        "provider_scope": [self.provider_id],
                        "provider_request_ids": [request_id],
                    },
                }
            )
        return normalized

    def fetch_accessible_text(self, candidate: dict[str, Any]) -> dict[str, Any] | None:
        access_class = _clean_text(candidate.get("access_class")).lower() or "metadata_only"
        source_id = _clean_text(candidate.get("source_id"))
        if access_class == "restricted_external":
            return None
        if access_class in {"open_access_full_text", "user_provided_document"}:
            text = _clean_text(candidate.get("oa_full_text") or candidate.get("abstract_text"))
            if text:
                field = "oa_full_text" if access_class == "open_access_full_text" else "user_provided_document"
                return {"source_id": source_id, "text": text, "field": field, "access_class": access_class}
            return None
        if access_class in {"abstract_only", "metadata_only"}:
            text = _clean_text(candidate.get("abstract_text"))
            if text:
                return {"source_id": source_id, "text": text, "field": "abstract_text", "access_class": access_class}
        return None


class OpenAlexLikeLiteratureProvider(MetadataAPILiteratureProvider):
    """OpenAlex-style metadata provider shell.

    Legal guardrail: this provider is metadata-first and only uses abstract or
    open-access text when the provider response already exposes it legally.
    """

    provider_id = "openalex_like_provider"
    provider_result_source = "openalex_like_search"


class MultiLiteratureProviderAggregator:
    provider_id = "multi_provider_aggregator"
    provider_result_source = "multi_provider_search"

    def __init__(self, providers: list[LiteratureProvider]) -> None:
        self.providers = list(providers)
        self.last_request_id = ""
        self.last_request_ids: list[str] = []

    def search(self, query: str, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        aggregated: dict[str, dict[str, Any]] = {}
        self.last_request_ids = []
        for provider in self.providers:
            for candidate in provider.search(query, filters=filters):
                identity = citation_identity_key(candidate)
                if identity in aggregated:
                    aggregated[identity] = merge_literature_candidates(aggregated[identity], candidate)
                else:
                    aggregated[identity] = dict(candidate)
            request_id = _clean_text(getattr(provider, "last_request_id", ""))
            if request_id and request_id not in self.last_request_ids:
                self.last_request_ids.append(request_id)
        self.last_request_id = self.last_request_ids[-1] if self.last_request_ids else ""
        return list(aggregated.values())

    def fetch_accessible_text(self, candidate: dict[str, Any]) -> dict[str, Any] | None:
        provider_scope = _as_str_list((candidate.get("provenance") or {}).get("provider_scope"))
        provider_id = _clean_text((candidate.get("provenance") or {}).get("provider_id"))
        candidate_scope = provider_scope or ([provider_id] if provider_id else [])
        for provider in self.providers:
            if provider.provider_id not in candidate_scope:
                continue
            accessible = provider.fetch_accessible_text(candidate)
            if accessible is not None:
                return accessible
        return None


def default_literature_provider_registry() -> dict[str, Callable[[], LiteratureProvider]]:
    return {
        "fixture_provider": FixtureLiteratureProvider,
        "metadata_api_provider": MetadataAPILiteratureProvider,
        "openalex_like_provider": OpenAlexLikeLiteratureProvider,
    }


def available_literature_provider_ids(
    *,
    registry: Mapping[str, Callable[[], LiteratureProvider]] | None = None,
) -> list[str]:
    return sorted(str(provider_id).strip() for provider_id in (registry or default_literature_provider_registry()) if str(provider_id).strip())


def resolve_literature_provider(
    provider_ids: list[str] | None = None,
    *,
    registry: Mapping[str, Callable[[], LiteratureProvider]] | None = None,
) -> tuple[LiteratureProvider, list[str]]:
    providers, provider_scope = resolve_literature_providers(provider_ids, registry=registry)
    if len(providers) != 1:
        raise ValueError("Multiple literature providers were requested; use resolve_literature_providers instead.")
    return providers[0], provider_scope


def resolve_literature_providers(
    provider_ids: list[str] | None = None,
    *,
    registry: Mapping[str, Callable[[], LiteratureProvider]] | None = None,
) -> tuple[list[LiteratureProvider], list[str]]:
    registry_map = dict(registry or default_literature_provider_registry())
    requested_ids: list[str] = []
    for item in provider_ids or []:
        token = str(item).strip()
        if token and token not in requested_ids:
            requested_ids.append(token)

    selected_ids = requested_ids or ["fixture_provider"]
    providers: list[LiteratureProvider] = []
    for provider_id in selected_ids:
        factory = registry_map.get(provider_id)
        if factory is None:
            available = ", ".join(available_literature_provider_ids(registry=registry_map)) or "none"
            raise ValueError(f"Unknown literature provider '{provider_id}'. Available providers: {available}.")
        providers.append(factory())
    return providers, selected_ids
