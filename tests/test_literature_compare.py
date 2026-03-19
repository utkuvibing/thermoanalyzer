from __future__ import annotations

import io
import json
import uuid
import zipfile

import pandas as pd
import pytest

from core.data_io import ThermalDataset
from core.literature_claims import extract_literature_claims
from core.literature_compare import attach_literature_package, compare_result_to_literature
from core.literature_provider import (
    FixtureLiteratureProvider,
    MetadataAPILiteratureProvider,
    MultiLiteratureProviderAggregator,
    OpenAlexLikeLiteratureProvider,
    default_literature_provider_registry,
    resolve_literature_provider,
    resolve_literature_providers,
)
from core.report_generator import generate_docx_report, generate_pdf_report
from core.result_serialization import flatten_result_records, make_result_record, split_valid_results


class StubProvider:
    provider_id = "stub_provider"
    provider_result_source = "stub_search"

    def __init__(self, sources: list[dict]) -> None:
        self.sources = sources
        self.last_request_id = ""

    def search(self, query: str, filters: dict | None = None) -> list[dict]:
        del filters
        self.last_request_id = f"litreq_{self.provider_id}_{uuid.uuid4().hex[:8]}"
        rows: list[dict] = []
        for source in self.sources:
            provenance = dict(source.get("provenance") or {})
            rows.append(
                {
                    **dict(source),
                    "provenance": {
                        **provenance,
                        "provider_id": self.provider_id,
                        "request_id": self.last_request_id,
                        "result_source": self.provider_result_source,
                        "query": query,
                        "provider_scope": [self.provider_id],
                        "provider_request_ids": [self.last_request_id],
                    },
                }
            )
        return rows

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
            "top_candidate_display_name_unicode": "Phase Alpha",
            "top_candidate_formula": "Al2O3",
            "top_candidate_id": "phase_alpha_001",
            "match_status": "matched",
            "confidence_band": "medium",
            "top_candidate_score": 0.78,
            "top_candidate_shared_peak_count": 5,
            "top_candidate_coverage_ratio": 0.64,
            "top_candidate_weighted_overlap_score": 0.71,
            "top_candidate_provider": "COD",
            "library_request_id": "libreq_demo_xrd_001",
            "library_result_source": "xrd_cloud_search",
            "library_provider_scope": ["cod"],
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
    record = _multi_claim_record()
    record["analysis_type"] = "FTIR"
    package = compare_result_to_literature(
        record,
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
    assert package["literature_context"]["source_count"] >= 1
    assert package["literature_context"]["provider_request_ids"]


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
    record = _base_record()
    record["analysis_type"] = "FTIR"
    package = compare_result_to_literature(
        record,
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
    record = _base_record()
    record["analysis_type"] = "FTIR"
    package = compare_result_to_literature(
        record,
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
    record = _base_record()
    record["analysis_type"] = "FTIR"
    package = compare_result_to_literature(
        record,
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
    assert package["citations"][0]["source_license_note"] == "user_provided_document"


def test_provider_registry_resolves_fixture_by_default():
    provider, provider_scope = resolve_literature_provider(
        registry=default_literature_provider_registry(),
    )

    assert isinstance(provider, FixtureLiteratureProvider)
    assert provider_scope == ["fixture_provider"]


def test_provider_registry_resolves_multiple_requested_providers():
    registry = {
        "stub_provider": lambda: StubProvider([]),
        "metadata_api_provider": lambda: MetadataAPILiteratureProvider(search_client=lambda query, filters: []),
    }

    providers, provider_scope = resolve_literature_providers(
        ["stub_provider", "metadata_api_provider"],
        registry=registry,
    )

    assert [provider.provider_id for provider in providers] == ["stub_provider", "metadata_api_provider"]
    assert provider_scope == ["stub_provider", "metadata_api_provider"]


def test_provider_registry_resolves_requested_provider_from_registry():
    registry = {"stub_provider": lambda: StubProvider([])}

    provider, provider_scope = resolve_literature_provider(
        ["stub_provider"],
        registry=registry,
    )

    assert isinstance(provider, StubProvider)
    assert provider_scope == ["stub_provider"]


def test_openalex_like_provider_normalizes_metadata_results():
    provider = OpenAlexLikeLiteratureProvider(
        search_client=lambda query, filters: {
            "request_id": "openalex_req_001",
            "result_source": "openalex_api",
            "results": [
                {
                    "source_id": "openalex_alpha",
                    "title": "MgB2 XRD phase analysis",
                    "authors": ["A. Author"],
                    "journal": "Journal of XRD",
                    "year": 2024,
                    "doi": "10.1000/openalex-alpha",
                    "url": "https://example.test/openalex-alpha",
                    "access_class": "abstract_only",
                    "abstract_text": "This paper discusses XRD characterization of MgB2 and a hexagonal phase assignment.",
                    "source_license_note": "provider_abstract",
                }
            ],
        }
    )

    package = compare_result_to_literature(_base_record(), provider=provider, provider_scope=["openalex_like_provider"])

    assert package["literature_context"]["provider_request_ids"] == ["openalex_req_001"]
    assert package["literature_context"]["provider_result_source"] == "openalex_api"
    assert package["literature_context"]["query_text"]
    assert package["literature_context"]["candidate_name"] == "Phase Alpha"
    assert package["literature_context"]["metadata_only_evidence"] is True
    assert package["citations"][0]["provenance"]["provider_id"] == "openalex_like_provider"
    assert package["literature_comparisons"][0]["paper_title"] == "MgB2 XRD phase analysis"
    assert package["literature_comparisons"][0]["validation_posture"] in {"non_validating", "related_support"}


def test_xrd_compare_builds_candidate_centered_comparison_note():
    provider = OpenAlexLikeLiteratureProvider(
        search_client=lambda query, filters: {
            "request_id": "openalex_req_002",
            "result_source": "openalex_api",
            "results": [
                {
                    "source_id": "paper_alpha",
                    "title": "Phase Alpha powder diffraction and crystal structure",
                    "authors": ["A. Author"],
                    "journal": "Powder Diffraction Letters",
                    "year": 2025,
                    "doi": "10.1000/paper-alpha",
                    "url": "https://example.test/paper-alpha",
                    "access_class": "abstract_only",
                    "abstract_text": "Phase Alpha XRD powder diffraction data and crystal structure are discussed.",
                    "source_license_note": "provider_abstract",
                }
            ],
        }
    )

    package = compare_result_to_literature(_base_record(), provider=provider, provider_scope=["openalex_like_provider"])

    comparison = package["literature_comparisons"][0]
    assert comparison["candidate_name"] == "Phase Alpha"
    assert comparison["paper_title"] == "Phase Alpha powder diffraction and crystal structure"
    assert comparison["comparison_note"]
    assert "Phase Alpha" in comparison["comparison_note"]
    assert comparison["support_label"] in {"partially_supports", "related_but_inconclusive"}


def test_xrd_no_match_remains_non_validating_under_literature():
    record = _base_record()
    record["summary"]["match_status"] = "no_match"
    record["summary"]["confidence_band"] = "no_match"
    record["summary"]["top_candidate_reason_below_threshold"] = "Weighted overlap remained below the configured acceptance threshold."

    provider = OpenAlexLikeLiteratureProvider(
        search_client=lambda query, filters: {
            "request_id": "openalex_req_003",
            "result_source": "openalex_api",
            "results": [
                {
                    "source_id": "paper_contextual",
                    "title": "Phase Alpha XRD characterization",
                    "authors": ["B. Author"],
                    "journal": "Journal of Phase Studies",
                    "year": 2023,
                    "doi": "10.1000/paper-contextual",
                    "url": "https://example.test/paper-contextual",
                    "access_class": "abstract_only",
                    "abstract_text": "The paper reports XRD characterization of Phase Alpha.",
                }
            ],
        }
    )

    package = compare_result_to_literature(record, provider=provider, provider_scope=["openalex_like_provider"])

    comparison = package["literature_comparisons"][0]
    assert comparison["validation_posture"] == "contextual_only"
    assert comparison["support_label"] == "related_but_inconclusive"
    assert "no_match screening outcome" in comparison["comparison_note"]


def test_multi_provider_aggregation_dedupes_by_doi_and_tracks_scope():
    fixture_like = StubProvider(
        [
            _source(
                source_id="alpha_a",
                access_class="abstract_only",
                text="This abstract supports the Phase Alpha qualitative XRD interpretation.",
                hint="supports",
            )
        ]
    )
    metadata_provider = MetadataAPILiteratureProvider(
        search_client=lambda query, filters: {
            "request_id": "meta_req_002",
            "result_source": "open_metadata_api",
            "results": [
                _source(
                    source_id="alpha_b",
                    access_class="open_access_full_text",
                    text="This open-access article supports the Phase Alpha qualitative XRD interpretation.",
                    hint="supports",
                )
            ],
        }
    )

    duplicate = _source(
        source_id="alpha_dup",
        access_class="abstract_only",
        text="This abstract supports the Phase Alpha qualitative XRD interpretation.",
        hint="supports",
    )
    duplicate["doi"] = "10.1000/shared-alpha"
    duplicate["url"] = "https://example.test/shared-alpha-a"
    fixture_like.sources = [duplicate]

    other_duplicate = _source(
        source_id="alpha_dup_other",
        access_class="open_access_full_text",
        text="This open-access article supports the Phase Alpha qualitative XRD interpretation.",
        hint="supports",
    )
    other_duplicate["doi"] = "10.1000/shared-alpha"
    other_duplicate["url"] = "https://example.test/shared-alpha-b"
    metadata_provider = MetadataAPILiteratureProvider(
        search_client=lambda query, filters: {
            "request_id": "meta_req_002",
            "result_source": "open_metadata_api",
            "results": [other_duplicate],
        }
    )

    package = compare_result_to_literature(
        _base_record(),
        provider=MultiLiteratureProviderAggregator([fixture_like, metadata_provider]),
        provider_scope=["stub_provider", "metadata_api_provider"],
    )

    assert package["literature_context"]["provider_scope"] == ["stub_provider", "metadata_api_provider"]
    assert package["literature_context"]["provider_result_source"] == "multi_provider_search"
    assert set(package["literature_context"]["provider_request_ids"]) == {"meta_req_002"} | {
        request_id for request_id in package["literature_context"]["provider_request_ids"] if request_id.startswith("litreq_stub_provider_")
    }
    assert package["literature_context"]["citation_count"] == 1
    assert package["literature_context"]["source_count"] == 1
    assert len(package["citations"]) == 1
    assert set(package["citations"][0]["provenance"]["provider_scope"]) == {"stub_provider", "metadata_api_provider"}


def test_literature_context_traceability_fields_persist_after_normalization():
    package = compare_result_to_literature(
        _base_record(),
        provider=OpenAlexLikeLiteratureProvider(
            search_client=lambda query, filters: {
                "request_id": "openalex_req_004",
                "result_source": "openalex_api",
                "results": [
                    {
                        "source_id": "support_a",
                        "title": "Phase Alpha XRD note",
                        "authors": ["A. Author"],
                        "journal": "Journal of XRD",
                        "year": 2024,
                        "doi": "10.1000/support-a",
                        "url": "https://example.test/support-a",
                        "access_class": "open_access_full_text",
                        "oa_full_text": "This source discusses Phase Alpha XRD characterization.",
                    }
                ],
            }
        ),
        provider_scope=["openalex_like_provider"],
    )
    record = attach_literature_package(_base_record(), package)

    valid, issues = split_valid_results({record["id"]: record})
    assert issues == []

    context = valid[record["id"]]["literature_context"]
    assert context["result_id"] == "xrd_demo"
    assert context["analysis_type"] == "XRD"
    assert context["provider_result_source"] == "openalex_api"
    assert context["provider_request_ids"] == ["openalex_req_004"]
    assert context["source_count"] == 1
    assert context["accessible_source_count"] == 1
    assert context["restricted_source_count"] == 0
    assert context["citation_count"] == 1
    assert context["generated_at_utc"]
    assert context["query_text"]
    assert context["candidate_name"] == "Phase Alpha"
    assert context["match_status_snapshot"] == "matched"
    assert context["top_candidate_score_snapshot"] == 0.78


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
    assert all("source_license_note" in citation for citation in persisted["citations"])


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
    assert any(row["section"] == "literature_context" and row["field"] == "provider_request_ids" for row in flat_rows)
    assert any(row["section"] == "literature_context" and row["field"] == "provider_result_source" for row in flat_rows)
    assert any(row["section"] == "literature_context" and row["field"] == "comparison_run_id" for row in flat_rows)
    assert any(row["section"] == "literature_claims" and row["field"] == "claim_id" for row in flat_rows)
    assert any(row["section"] == "literature_comparisons" and row["field"] == "support_label" for row in flat_rows)
    assert any(row["section"] == "citations" and row["field"] == "citation_id" for row in flat_rows)


def test_docx_and_pdf_reports_exclude_fixture_only_literature_by_default():
    pytest.importorskip("reportlab")
    pypdf = pytest.importorskip("pypdf")

    record = attach_literature_package(
        _base_record(),
        {
            "literature_context": {
                "mode": "metadata_abstract_oa_only",
                "comparison_run_id": "litcmp_demo_001",
                "provider_scope": ["fixture_provider"],
                "provider_request_ids": ["litreq_fixture_provider_demo"],
                "provider_result_source": "fixture_search",
                "source_count": 2,
                "citation_count": 2,
                "accessible_source_count": 2,
                "restricted_source_count": 0,
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
                    "source_license_note": "CC-BY-4.0",
                    "provenance": {
                        "provider_id": "fixture_provider",
                        "result_source": "fixture_search",
                        "provider_scope": ["fixture_provider"],
                        "provider_request_ids": ["litreq_fixture_provider_demo"],
                    },
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
                    "source_license_note": "publisher_abstract_only",
                    "provenance": {
                        "provider_id": "fixture_provider",
                        "result_source": "fixture_search",
                        "provider_scope": ["fixture_provider"],
                        "provider_request_ids": ["litreq_fixture_provider_demo"],
                    },
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

    assert "Development / Demo Literature Output" in xml
    assert "Fixture/demo-only literature output was excluded from the report by default because it is not a real bibliographic source." in xml
    assert "Supporting References" not in xml
    assert "Contradictory or Alternative References" not in xml
    assert "10.1000/support" not in xml
    assert "10.1000/alternative" not in xml

    pdf_bytes = generate_pdf_report(results={record["id"]: record}, datasets={"xrd_demo": dataset})
    extracted = "\n".join(page.extract_text() or "" for page in pypdf.PdfReader(io.BytesIO(pdf_bytes)).pages)

    assert "Development / Demo Literature Output" in extracted
    assert "excluded from the report by default" in extracted
    assert "Supporting References" not in extracted


def test_docx_report_renders_real_xrd_candidate_literature_sections():
    record = attach_literature_package(
        _base_record(),
        {
            "literature_context": {
                "mode": "metadata_abstract_oa_only",
                "comparison_run_id": "litcmp_real_001",
                "provider_scope": ["openalex_like_provider"],
                "provider_request_ids": ["openalex_req_010"],
                "provider_result_source": "openalex_api",
                "query_text": "\"Phase Alpha\" XRD powder diffraction phase identification crystal structure",
                "candidate_name": "Phase Alpha",
                "candidate_display_name": "Phase Alpha",
                "match_status_snapshot": "no_match",
                "confidence_band_snapshot": "no_match",
                "real_literature_available": True,
            },
            "literature_claims": [
                {
                    "claim_id": "C1",
                    "claim_text": "The current XRD result remains a no_match screening outcome; literature can only provide context around the top-ranked candidate Phase Alpha.",
                    "claim_type": "cautionary_interpretation",
                    "modality": "XRD",
                    "strength": "low",
                }
            ],
            "literature_comparisons": [
                {
                    "claim_id": "C1",
                    "claim_text": "The current XRD result remains a no_match screening outcome; literature can only provide context around the top-ranked candidate Phase Alpha.",
                    "candidate_name": "Phase Alpha",
                    "paper_title": "Phase Alpha XRD characterization",
                    "paper_year": 2024,
                    "paper_journal": "Journal of XRD",
                    "paper_doi": "10.1000/real-alpha",
                    "paper_url": "https://example.test/real-alpha",
                    "provider_id": "openalex_like_provider",
                    "access_class": "abstract_only",
                    "comparison_note": "This paper discusses XRD characterization of Phase Alpha. The current result remains a no_match screening outcome and the paper does not validate a phase call for the present sample.",
                    "validation_posture": "contextual_only",
                    "query_text": "\"Phase Alpha\" XRD powder diffraction phase identification crystal structure",
                    "match_status_snapshot": "no_match",
                    "confidence_band_snapshot": "no_match",
                    "support_label": "related_but_inconclusive",
                    "rationale": "This paper discusses XRD characterization of Phase Alpha. The current result remains a no_match screening outcome and the paper does not validate a phase call for the present sample.",
                    "citation_ids": ["ref1"],
                    "confidence": "low",
                    "sources_considered": 1,
                }
            ],
            "citations": [
                {
                    "citation_id": "ref1",
                    "title": "Phase Alpha XRD characterization",
                    "authors": ["A. Author"],
                    "year": 2024,
                    "journal": "Journal of XRD",
                    "doi": "10.1000/real-alpha",
                    "url": "https://example.test/real-alpha",
                    "access_class": "abstract_only",
                    "citation_text": "A. Author (2024). Phase Alpha XRD characterization. Journal of XRD. DOI: 10.1000/real-alpha.",
                    "source_license_note": "provider_abstract",
                    "provenance": {
                        "provider_id": "openalex_like_provider",
                        "result_source": "openalex_api",
                        "provider_scope": ["openalex_like_provider"],
                        "provider_request_ids": ["openalex_req_010"],
                    },
                }
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

    assert "XRD Candidate Literature Check" in xml
    assert "Relevant Papers" in xml
    assert "Alternative or Non-Validating Papers" in xml
    assert "Literature provides contextual evidence around the top-ranked candidate and does not override XRD screening." in xml
    assert "Phase Alpha XRD characterization" in xml


def test_docx_report_excludes_fixture_xrd_rows_when_real_and_fixture_results_mix():
    record = attach_literature_package(
        _base_record(),
        {
            "literature_context": {
                "mode": "metadata_abstract_oa_only",
                "comparison_run_id": "litcmp_real_fixture_001",
                "provider_scope": ["openalex_like_provider", "fixture_provider"],
                "provider_request_ids": ["openalex_req_011", "litreq_fixture_provider_demo"],
                "provider_result_source": "multi_provider_search",
                "query_text": "\"Phase Alpha\" XRD powder diffraction phase identification crystal structure",
                "candidate_name": "Phase Alpha",
                "candidate_display_name": "Phase Alpha",
                "match_status_snapshot": "matched",
                "confidence_band_snapshot": "medium",
                "real_literature_available": True,
            },
            "literature_claims": [
                {
                    "claim_id": "C1",
                    "claim_text": "The top-ranked XRD candidate is Phase Alpha, but the result remains qualitative and requires cautious interpretation.",
                    "claim_type": "interpretation",
                    "modality": "XRD",
                    "strength": "moderate",
                }
            ],
            "literature_comparisons": [
                {
                    "claim_id": "C1",
                    "claim_text": "The top-ranked XRD candidate is Phase Alpha, but the result remains qualitative and requires cautious interpretation.",
                    "candidate_name": "Phase Alpha",
                    "paper_title": "Phase Alpha XRD characterization",
                    "paper_year": 2024,
                    "paper_journal": "Journal of XRD",
                    "paper_doi": "10.1000/real-alpha",
                    "paper_url": "https://example.test/real-alpha",
                    "provider_id": "openalex_like_provider",
                    "access_class": "abstract_only",
                    "comparison_note": "This source is relevant to the top-ranked candidate, but the current XRD evidence remains limited and non-validating.",
                    "validation_posture": "non_validating",
                    "citation_ids": ["ref1"],
                    "confidence": "low",
                    "sources_considered": 2,
                },
                {
                    "claim_id": "C1",
                    "claim_text": "The top-ranked XRD candidate is Phase Alpha, but the result remains qualitative and requires cautious interpretation.",
                    "candidate_name": "Phase Alpha",
                    "paper_title": "Fixture-only paper",
                    "paper_year": 2025,
                    "paper_journal": "Fixture Journal",
                    "paper_doi": "10.1000/fixture-alpha",
                    "paper_url": "https://example.test/fixture-alpha",
                    "provider_id": "fixture_provider",
                    "access_class": "open_access_full_text",
                    "comparison_note": "Fixture/demo output only.",
                    "validation_posture": "non_validating",
                    "citation_ids": ["ref2"],
                    "confidence": "low",
                    "sources_considered": 2,
                },
            ],
            "citations": [
                {
                    "citation_id": "ref1",
                    "title": "Phase Alpha XRD characterization",
                    "authors": ["A. Author"],
                    "year": 2024,
                    "journal": "Journal of XRD",
                    "doi": "10.1000/real-alpha",
                    "url": "https://example.test/real-alpha",
                    "access_class": "abstract_only",
                    "citation_text": "A. Author (2024). Phase Alpha XRD characterization. Journal of XRD. DOI: 10.1000/real-alpha.",
                    "source_license_note": "provider_abstract",
                    "provenance": {
                        "provider_id": "openalex_like_provider",
                        "result_source": "openalex_api",
                        "provider_scope": ["openalex_like_provider"],
                        "provider_request_ids": ["openalex_req_011"],
                    },
                },
                {
                    "citation_id": "ref2",
                    "title": "Fixture-only paper",
                    "authors": ["Fixture Author"],
                    "year": 2025,
                    "journal": "Fixture Journal",
                    "doi": "10.1000/fixture-alpha",
                    "url": "https://example.test/fixture-alpha",
                    "access_class": "open_access_full_text",
                    "citation_text": "Fixture Author (2025). Fixture-only paper. Fixture Journal. DOI: 10.1000/fixture-alpha.",
                    "source_license_note": "fixture",
                    "provenance": {
                        "provider_id": "fixture_provider",
                        "result_source": "fixture_search",
                        "provider_scope": ["fixture_provider"],
                        "provider_request_ids": ["litreq_fixture_provider_demo"],
                    },
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

    assert "Phase Alpha XRD characterization" in xml
    assert "10.1000/real-alpha" in xml
    assert "Fixture-only paper" not in xml
    assert "10.1000/fixture-alpha" not in xml
