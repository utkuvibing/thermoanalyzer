from __future__ import annotations

import io
import json
import zipfile

import pandas as pd
import pytest

from core.data_io import ThermalDataset
from core.literature_claims import extract_literature_claims
from core.literature_compare import attach_literature_package, compare_result_to_literature
from core.literature_provider import FixtureLiteratureProvider, default_literature_provider_registry, resolve_literature_provider
from core.report_generator import generate_docx_report, generate_pdf_report
from core.result_serialization import flatten_result_records, make_result_record, split_valid_results


class StubProvider:
    provider_id = "stub_provider"

    def __init__(self, sources: list[dict]) -> None:
        self.sources = sources

    def search(self, query: str, filters: dict | None = None) -> list[dict]:
        del query, filters
        return list(self.sources)

    def fetch_accessible_text(self, candidate: dict) -> dict | None:
        if str(candidate.get("access_class") or "").lower() == "restricted_external":
            return None
        text = str(candidate.get("oa_full_text") or candidate.get("abstract_text") or "").strip()
        if not text:
            return None
        field = "oa_full_text" if candidate.get("oa_full_text") else "abstract_text"
        return {
            "source_id": candidate.get("source_id"),
            "text": text,
            "field": field,
            "access_class": candidate.get("access_class"),
        }


def _base_record() -> dict:
    return make_result_record(
        result_id="xrd_demo",
        analysis_type="XRD",
        status="stable",
        dataset_key="xrd_demo",
        metadata={"sample_name": "Phase Alpha Sample", "display_name": "Synthetic XRD Pattern"},
        summary={
            "top_candidate_name": "Phase Alpha",
            "match_status": "matched",
            "confidence_band": "medium",
            "library_request_id": "libreq_demo_xrd_001",
            "library_result_source": "fixture_search",
            "library_provider_scope": ["fixture_provider"],
        },
        rows=[{"rank": 1, "candidate_name": "Phase Alpha", "normalized_score": 0.78}],
        scientific_context={
            "scientific_claims": [
                {
                    "id": "C1",
                    "strength": "mechanistic",
                    "claim": "Phase Alpha remains a qualitative XRD follow-up candidate rather than a confirmed phase call.",
                    "evidence": ["Shared peaks remain consistent with the retained candidate."],
                }
            ],
            "evidence_map": {
                "C1": ["Shared peaks remain consistent with the retained candidate."]
            },
            "uncertainty_assessment": {
                "overall_confidence": "moderate",
                "items": ["Interpretation remains qualitative and cautionary."],
            },
        },
        validation={"status": "pass", "warnings": [], "issues": []},
    )


def _multi_claim_record() -> dict:
    record = _base_record()
    record["scientific_context"] = {
        "scientific_claims": [
            {
                "id": "C1",
                "strength": "mechanistic",
                "claim": "Phase Alpha remains a qualitative XRD follow-up candidate rather than a confirmed phase call.",
                "evidence": ["Shared peaks remain consistent with the retained candidate."],
            },
            {
                "id": "C2",
                "strength": "comparative",
                "claim": "Phase Alpha remains more consistent than Phase Beta in the retained XRD ranking.",
                "evidence": ["The top-ranked candidate remains Phase Alpha."],
            },
            {
                "id": "C3",
                "strength": "descriptive",
                "claim": "The observed pattern still shows the strongest overlap with the leading qualitative candidate.",
                "evidence": ["The normalized score remains highest for the leading candidate."],
            },
        ],
        "evidence_map": {
            "C1": ["Shared peaks remain consistent with the retained candidate."],
            "C2": ["The top-ranked candidate remains Phase Alpha."],
            "C3": ["The normalized score remains highest for the leading candidate."],
        },
        "uncertainty_assessment": {
            "overall_confidence": "moderate",
            "items": ["Interpretation remains qualitative and cautionary."],
        },
    }
    return record


def _source(*, source_id: str, access_class: str, text: str, hint: str) -> dict:
    return {
        "source_id": source_id,
        "title": f"{source_id} title",
        "authors": ["A. Author"],
        "journal": "Fixture Journal",
        "year": 2025,
        "doi": f"10.1000/{source_id}",
        "url": f"https://example.test/{source_id}",
        "access_class": access_class,
        "available_fields": ["metadata", "abstract"],
        "abstract_text": text if access_class != "restricted_external" else "",
        "oa_full_text": text if access_class == "open_access_full_text" else "",
        "source_license_note": "fixture",
        "citation_text": "",
        "provenance": {
            "modalities": ["XRD"],
            "keywords": ["phase alpha", "xrd"],
            "comparison_hint": hint,
        },
    }


def test_claim_extraction_uses_result_fields_deterministically():
    claims = extract_literature_claims(_base_record())

    assert len(claims) == 1
    claim = claims[0]
    assert claim["claim_id"] == "C1"
    assert claim["modality"] == "XRD"
    assert claim["claim_type"] == "interpretation"
    assert claim["strength"] == "moderate"
    assert claim["evidence_snapshot"]["top_candidate_name"] == "Phase Alpha"
    assert "qualitative" in claim["claim_text"].lower()
    assert "Phase Alpha" in claim["suggested_query_terms"]


def test_fixture_provider_search_returns_ranked_candidates():
    provider = FixtureLiteratureProvider()

    results = provider.search("XRD Phase Alpha qualitative screening", filters={"modalities": ["XRD"], "top_k": 3})

    assert results
    assert results[0]["source_id"] == "fixture_xrd_phase_alpha_oa"
    assert results[0]["access_class"] == "open_access_full_text"
    assert results[0]["provenance"]["provider_id"] == "fixture_provider"
    assert results[0]["provenance"]["request_id"].startswith("litreq_fixture_provider_")


def test_compare_result_to_literature_limits_max_claims():
    package = compare_result_to_literature(
        _multi_claim_record(),
        provider=StubProvider(
            [
                _source(
                    source_id="fixture_support",
                    access_class="open_access_full_text",
                    text="This accessible note supports the Phase Alpha qualitative XRD interpretation.",
                    hint="supports",
                )
            ]
        ),
        max_claims=2,
    )

    assert [claim["claim_id"] for claim in package["literature_claims"]] == ["C1", "C2"]
    assert len(package["literature_comparisons"]) == 2


@pytest.mark.parametrize(
    ("hint", "access_class", "expected_label"),
    [
        ("supports", "open_access_full_text", "supports"),
        ("partially_supports", "abstract_only", "partially_supports"),
        ("contradicts", "abstract_only", "contradicts"),
        ("related_but_inconclusive", "metadata_only", "related_but_inconclusive"),
    ],
)
def test_comparison_engine_assigns_expected_labels(hint: str, access_class: str, expected_label: str):
    package = compare_result_to_literature(
        _base_record(),
        provider=StubProvider(
            [
                _source(
                    source_id=f"fixture_{expected_label}",
                    access_class=access_class,
                    text=f"This accessible note {hint} the Phase Alpha qualitative XRD interpretation.",
                    hint=hint,
                )
            ]
        ),
    )

    comparison = package["literature_comparisons"][0]

    assert comparison["support_label"] == expected_label
    assert comparison["sources_considered"] == 1
    if expected_label == "related_but_inconclusive":
        assert comparison["confidence"] == "low"
    else:
        assert comparison["confidence"] == "moderate"


def test_restricted_content_guardrail_excludes_closed_access_reasoning():
    package = compare_result_to_literature(
        _base_record(),
        provider=StubProvider(
            [
                _source(
                    source_id="restricted_only",
                    access_class="restricted_external",
                    text="Closed access text that must never be used.",
                    hint="supports",
                )
            ]
        ),
    )

    comparison = package["literature_comparisons"][0]

    assert package["literature_context"]["restricted_content_used"] is False
    assert comparison["support_label"] == "related_but_inconclusive"
    assert comparison["citation_ids"] == []
    assert "Closed-access full text was not used" in comparison["rationale"]


def test_user_provided_document_is_compared_and_cited():
    package = compare_result_to_literature(
        _base_record(),
        provider=StubProvider([]),
        user_documents=[
            {
                "document_id": "lab_note_alpha",
                "title": "Lab note alpha",
                "authors": ["U. Analyst"],
                "year": 2026,
                "text": "This lab note supports the Phase Alpha qualitative XRD interpretation and aligns with the retained candidate.",
                "comparison_hint": "supports",
            }
        ],
    )

    comparison = package["literature_comparisons"][0]

    assert comparison["support_label"] == "supports"
    assert comparison["sources_considered"] == 1
    assert package["citations"][0]["access_class"] == "user_provided_document"
    assert package["citations"][0]["title"] == "Lab note alpha"
    assert package["citations"][0]["provenance"]["result_source"] == "user_provided_document"


def test_provider_registry_resolves_fixture_by_default():
    provider, provider_scope = resolve_literature_provider(
        registry=default_literature_provider_registry(),
    )

    assert isinstance(provider, FixtureLiteratureProvider)
    assert provider_scope == ["fixture_provider"]


def test_provider_registry_resolves_requested_provider_from_registry():
    registry = {"stub_provider": lambda: StubProvider([])}

    provider, provider_scope = resolve_literature_provider(
        ["stub_provider"],
        registry=registry,
    )

    assert isinstance(provider, StubProvider)
    assert provider_scope == ["stub_provider"]


def test_long_accessible_text_is_not_persisted_in_normalized_result_records():
    long_text = "USER_DOCUMENT_TEXT_BLOCK " * 80
    package = compare_result_to_literature(
        _base_record(),
        provider=StubProvider([]),
        user_documents=[
            {
                "document_id": "lab_note_alpha",
                "title": "Lab note alpha",
                "authors": ["U. Analyst"],
                "text": f"{long_text} supports the Phase Alpha qualitative XRD interpretation.",
                "comparison_hint": "supports",
            },
        ],
    )
    record = attach_literature_package(_base_record(), package)

    valid, issues = split_valid_results({record["id"]: record})
    assert issues == []

    persisted = valid[record["id"]]
    assert long_text not in json.dumps(persisted)
    assert all("oa_full_text" not in citation for citation in persisted["citations"])
    assert all("abstract_text" not in citation for citation in persisted["citations"])


def test_result_serialization_includes_literature_payload_sections():
    package = compare_result_to_literature(
        _base_record(),
        provider=StubProvider([_source(source_id="support_a", access_class="open_access_full_text", text="This source supports the Phase Alpha XRD interpretation.", hint="supports")]),
    )
    record = attach_literature_package(_base_record(), package)

    valid, issues = split_valid_results({record["id"]: record})
    assert issues == []
    flat_rows = flatten_result_records(valid)

    assert valid[record["id"]]["literature_context"]["mode"] == "metadata_abstract_oa_only"
    assert any(row["section"] == "literature_context" and row["field"] == "comparison_run_id" for row in flat_rows)
    assert any(row["section"] == "literature_claims" and row["field"] == "claim_id" for row in flat_rows)
    assert any(row["section"] == "literature_comparisons" and row["field"] == "support_label" for row in flat_rows)
    assert any(row["section"] == "citations" and row["field"] == "citation_id" for row in flat_rows)


def test_docx_and_pdf_reports_render_literature_sections():
    pytest.importorskip("reportlab")
    pypdf = pytest.importorskip("pypdf")

    record = attach_literature_package(
        _base_record(),
        {
            "literature_context": {
                "mode": "metadata_abstract_oa_only",
                "comparison_run_id": "litcmp_demo_001",
                "provider_scope": ["fixture_provider"],
                "query_count": 2,
                "restricted_content_used": False,
            },
            "literature_claims": extract_literature_claims(_base_record()),
            "literature_comparisons": [
                {
                    "claim_id": "C1",
                    "retrieved_sources": ["fixture_support", "fixture_alt"],
                    "support_label": "partially_supports",
                    "rationale": "Accessible literature is partly consistent with the claim, but evidence is limited or mixed.",
                    "evidence_used": ["Phase Alpha shows partial overlap in accessible text."],
                    "citation_ids": ["ref1", "ref2"],
                    "confidence": "moderate",
                    "sources_considered": 2,
                }
            ],
            "citations": [
                {
                    "citation_id": "ref1",
                    "title": "Supporting paper",
                    "authors": ["A. Author"],
                    "year": 2024,
                    "journal": "Fixture Journal",
                    "doi": "10.1000/support",
                    "url": "https://example.test/support",
                    "access_class": "open_access_full_text",
                    "citation_text": "A. Author (2024). Supporting paper. Fixture Journal. DOI: 10.1000/support.",
                },
                {
                    "citation_id": "ref2",
                    "title": "Alternative paper",
                    "authors": ["B. Author"],
                    "year": 2025,
                    "journal": "Fixture Journal",
                    "doi": "10.1000/alternative",
                    "url": "https://example.test/alternative",
                    "access_class": "abstract_only",
                    "citation_text": "B. Author (2025). Alternative paper. Fixture Journal. DOI: 10.1000/alternative.",
                },
            ],
        },
    )
    dataset = ThermalDataset(
        data=pd.DataFrame({"temperature": [18.2, 27.5, 36.1], "signal": [130.0, 290.0, 175.0]}),
        metadata={
            "sample_name": "Phase Alpha Sample",
            "display_name": "Synthetic XRD Pattern",
            "instrument": "XRDBench",
            "xrd_axis_role": "two_theta",
            "xrd_axis_unit": "degree_2theta",
        },
        data_type="XRD",
        units={"temperature": "degree_2theta", "signal": "counts"},
        original_columns={"temperature": "two_theta", "signal": "intensity"},
        file_path="",
    )

    docx_bytes = generate_docx_report(results={record["id"]: record}, datasets={"xrd_demo": dataset})
    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    assert "Literature Comparison" in xml
    assert "Supporting References" in xml
    assert "Contradictory or Alternative References" in xml
    assert "Recommended Follow-Up Literature Checks" in xml
    assert "litcmp_demo_001" in xml

    pdf_bytes = generate_pdf_report(results={record["id"]: record}, datasets={"xrd_demo": dataset})
    extracted = "\n".join(page.extract_text() or "" for page in pypdf.PdfReader(io.BytesIO(pdf_bytes)).pages)

    assert "Literature Comparison" in extracted
    assert "Supporting References" in extracted
    assert "Contradictory or Alternative References" in extracted
    assert "Recommended Follow-Up Literature Checks" in extracted
