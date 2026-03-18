"""Citation formatting helpers for literature comparison outputs."""

from __future__ import annotations

from typing import Any, Mapping

from core.literature_models import CitationEntry, LiteratureSource


def _authors_token(authors: list[str]) -> str:
    if not authors:
        return "Unknown author"
    if len(authors) == 1:
        return authors[0]
    if len(authors) == 2:
        return f"{authors[0]} and {authors[1]}"
    return f"{authors[0]} et al."


def format_citation_text(source: Mapping[str, Any]) -> str:
    authors = [str(item).strip() for item in (source.get("authors") or []) if str(item).strip()]
    year = source.get("year")
    journal = str(source.get("journal") or "").strip()
    title = str(source.get("title") or "Untitled source").strip()
    doi = str(source.get("doi") or "").strip()
    url = str(source.get("url") or "").strip()

    segments = [f"{_authors_token(authors)} ({year or 'n.d.'})", title]
    if journal:
        segments.append(journal)
    if doi:
        segments.append(f"DOI: {doi}")
    elif url:
        segments.append(url)
    return ". ".join(segment.rstrip(".") for segment in segments if segment).strip() + "."


def build_citation_entry(source: Mapping[str, Any], *, citation_id: str) -> dict[str, Any]:
    normalized_source = LiteratureSource(
        source_id=str(source.get("source_id") or ""),
        title=str(source.get("title") or ""),
        authors=[str(item) for item in (source.get("authors") or [])],
        journal=str(source.get("journal") or ""),
        year=source.get("year"),
        doi=str(source.get("doi") or ""),
        url=str(source.get("url") or ""),
        access_class=str(source.get("access_class") or "metadata_only"),
        available_fields=[str(item) for item in (source.get("available_fields") or [])],
        abstract_text=str(source.get("abstract_text") or ""),
        oa_full_text=str(source.get("oa_full_text") or ""),
        source_license_note=str(source.get("source_license_note") or ""),
        citation_text=str(source.get("citation_text") or ""),
        provenance=dict(source.get("provenance") or {}),
    ).to_dict()

    citation = CitationEntry(
        citation_id=citation_id,
        title=normalized_source["title"],
        authors=normalized_source["authors"],
        year=normalized_source.get("year"),
        journal=normalized_source["journal"],
        doi=normalized_source["doi"],
        url=normalized_source["url"],
        access_class=normalized_source["access_class"],
        citation_text=normalized_source.get("citation_text") or format_citation_text(normalized_source),
        provenance=normalized_source["provenance"],
    )
    return citation.to_dict()
