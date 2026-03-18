"""Provider abstraction for legal-safe literature metadata and text retrieval."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Protocol

from core.citation_formatter import format_citation_text
from core.literature_models import normalize_literature_sources


def _tokenize(value: str) -> list[str]:
    cleaned = "".join(ch if ch.isalnum() else " " for ch in str(value or "").lower())
    return [token for token in cleaned.split() if len(token) >= 3]


class LiteratureProvider(Protocol):
    provider_id: str

    def search(self, query: str, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        ...

    def fetch_accessible_text(self, candidate: dict[str, Any]) -> dict[str, Any] | None:
        ...


class FixtureLiteratureProvider:
    """Synthetic provider used for MVP development and test coverage."""

    provider_id = "fixture_provider"

    def __init__(self, fixture_path: str | Path | None = None) -> None:
        self.fixture_path = Path(fixture_path) if fixture_path else (
            Path(__file__).resolve().parents[1] / "sample_data" / "literature_fixture_sources.json"
        )
        raw_payload = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        self._sources = normalize_literature_sources(raw_payload.get("sources") or [])

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
                "result_source": "fixture_search",
                "query": query,
                "provider_scope": [self.provider_id],
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
