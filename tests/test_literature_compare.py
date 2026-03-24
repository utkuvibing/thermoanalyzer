from __future__ import annotations

import io
import json
import uuid
import zipfile

import pandas as pd
import pytest

from core.data_io import ThermalDataset
from core.literature_claims import extract_literature_claims
from core.literature_compare import _thermal_search_queries, attach_literature_package, compare_result_to_literature
from core.literature_provider import (
    FixtureLiteratureProvider,
    MetadataAPILiteratureProvider,
    MultiLiteratureProviderAggregator,
    OpenAlexLikeLiteratureProvider,
    build_openalex_like_client_from_env,
    default_literature_provider_registry,
    resolve_literature_provider,
    resolve_literature_providers,
)
from core.report_generator import generate_docx_report, generate_pdf_report
from core.result_serialization import flatten_result_records, make_result_record, split_valid_results
from core.thermal_literature_query_builder import build_dsc_literature_query, build_dta_literature_query, build_tga_literature_query


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


class QueryAwareStubProvider(StubProvider):
    def __init__(self, query_map: dict[str, list[dict]]) -> None:
        super().__init__([])
        self.provider_id = "query_aware_stub"
        self.query_map = query_map
        self.queries_seen: list[str] = []
        self.last_request_ids: list[str] = []

    def search(self, query: str, filters: dict | None = None) -> list[dict]:
        del filters
        self.queries_seen.append(query)
        request_id = f"litreq_{self.provider_id}_{len(self.queries_seen)}"
        self.last_request_id = request_id
        self.last_request_ids.append(request_id)
        rows: list[dict] = []
        for source in self.query_map.get(query, []):
            provenance = dict(source.get("provenance") or {})
            rows.append(
                {
                    **dict(source),
                    "provenance": {
                        **provenance,
                        "provider_id": self.provider_id,
                        "request_id": request_id,
                        "result_source": self.provider_result_source,
                        "query": query,
                        "provider_scope": [self.provider_id],
                        "provider_request_ids": [request_id],
                    },
                }
            )
        self.last_query_status = "success" if rows else "no_results"
        return rows


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


def _thermal_record(analysis_type: str) -> dict:
    normalized = analysis_type.upper()
    if normalized == "DSC":
        return make_result_record(
            result_id="dsc_demo",
            analysis_type="DSC",
            status="stable",
            dataset_key="dsc_demo",
            metadata={"sample_name": "Polymer A", "display_name": "Polymer A DSC"},
            summary={"sample_name": "Polymer A", "peak_count": 1, "glass_transition_count": 1, "tg_midpoint": 118.4},
            rows=[{"peak_type": "endo", "peak_temperature": 121.2, "onset_temperature": 113.0, "endset_temperature": 126.0}],
            scientific_context={
                "scientific_claims": [
                    {
                        "id": "C1",
                        "strength": "comparative",
                        "claim": "The DSC result indicates a glass-transition-related thermal feature that remains qualitative and requires cautious interpretation.",
                    }
                ],
                "uncertainty_assessment": {"overall_confidence": "moderate", "items": ["Interpretation remains qualitative."]},
            },
            validation={"status": "pass", "warnings": [], "issues": []},
        )
    if normalized == "DTA":
        return make_result_record(
            result_id="dta_demo",
            analysis_type="DTA",
            status="stable",
            dataset_key="dta_demo",
            metadata={"sample_name": "Ore B", "display_name": "Ore B DTA"},
            summary={"sample_name": "Ore B", "peak_count": 1},
            rows=[{"peak_type": "exo", "peak_temperature": 642.8, "onset_temperature": 620.0, "endset_temperature": 661.0}],
            scientific_context={
                "scientific_claims": [
                    {
                        "id": "C1",
                        "strength": "descriptive",
                        "claim": "The DTA result indicates a leading exothermic event that remains a qualitative thermal interpretation.",
                    }
                ],
                "uncertainty_assessment": {"overall_confidence": "moderate", "items": ["Interpretation remains qualitative."]},
            },
            validation={"status": "pass", "warnings": [], "issues": []},
        )
    return make_result_record(
        result_id="tga_demo",
        analysis_type="TGA",
        status="stable",
        dataset_key="tga_demo",
        metadata={"sample_name": "Composite C", "display_name": "Composite C TGA"},
        summary={"sample_name": "Composite C", "step_count": 1, "total_mass_loss_percent": 32.4, "residue_percent": 67.6},
        rows=[{"midpoint_temperature": 411.0, "mass_loss_percent": 32.4, "onset_temperature": 380.0, "endset_temperature": 438.0}],
        scientific_context={
            "scientific_claims": [
                {
                    "id": "C1",
                    "strength": "descriptive",
                    "claim": "The TGA result indicates a decomposition profile with a dominant mass-loss step and residual mass that remain qualitative.",
                }
            ],
            "uncertainty_assessment": {"overall_confidence": "moderate", "items": ["Interpretation remains qualitative."]},
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


@pytest.mark.parametrize("analysis_type", ["DSC", "DTA", "TGA"])
def test_thermal_compare_uses_traceable_live_query_context(analysis_type: str):
    record = _thermal_record(analysis_type)
    provider = OpenAlexLikeLiteratureProvider(
        search_client=lambda query, filters: {
            "request_id": f"openalex_req_{analysis_type.lower()}",
            "result_source": "openalex_api",
            "query_status": "success",
            "results": [
                {
                    "id": f"https://openalex.org/W_{analysis_type.lower()}",
                    "display_name": f"{analysis_type} interpretation study",
                    "publication_year": 2024,
                    "doi": f"https://doi.org/10.1000/{analysis_type.lower()}-study",
                    "authorships": [{"author": {"display_name": "A. Author"}}],
                    "primary_location": {"source": {"display_name": "Journal of Thermal Analysis"}},
                }
            ],
        }
    )

    package = compare_result_to_literature(record, provider=provider, provider_scope=["openalex_like_provider"], max_claims=2)

    context = package["literature_context"]
    comparison = package["literature_comparisons"][0]
    assert context["analysis_type"] == analysis_type
    assert context["provider_request_ids"] == [f"openalex_req_{analysis_type.lower()}"]
    assert context["provider_query_status"] == "success"
    assert context["query_text"]
    assert context["query_display_mode"]
    assert context["query_rationale"]
    assert comparison["validation_posture"] in {"related_support", "contextual_only", "non_validating"}
    assert comparison["support_label"] in {"partially_supports", "related_but_inconclusive", "contradicts"}
    assert comparison["support_label"] != "supports"


def test_tga_compare_no_results_persists_traceability():
    record = _thermal_record("TGA")
    provider = OpenAlexLikeLiteratureProvider(
        search_client=lambda query, filters: {
            "request_id": "openalex_req_tga_none",
            "result_source": "openalex_api",
            "query_status": "not_configured",
            "results": [],
        }
    )

    package = compare_result_to_literature(record, provider=provider, provider_scope=["openalex_like_provider"])

    context = package["literature_context"]
    assert context["provider_query_status"] == "not_configured"
    assert context["no_results_reason"] == "not_configured"
    assert context["real_literature_available"] is False


def test_tga_query_builder_strips_filename_artifacts_and_adds_scientific_fallbacks():
    record = _thermal_record("TGA")
    record["metadata"]["display_name"] = "tga_CaCO3_decomposition.csv"
    record["metadata"]["file_name"] = "tga_CaCO3_decomposition.csv"
    record["metadata"]["sample_name"] = ""
    record["summary"]["sample_name"] = ""
    record["summary"]["total_mass_loss_percent"] = 43.9
    record["rows"][0]["midpoint_temperature"] = 718.0

    payload = build_tga_literature_query(record)

    assert ".csv" not in payload["query_text"]
    assert payload["query_display_title"] == "CaCO3 decomposition"
    assert not payload["query_text"].startswith('"CaCO3 decomposition.csv"')
    assert any("thermogravimetric analysis" in query.lower() for query in payload["fallback_queries"])
    assert any("calcium carbonate" in query.lower() or "calcite" in query.lower() for query in payload["fallback_queries"])
    assert any("decarbonation" in query.lower() or "calcination" in query.lower() for query in payload["fallback_queries"])


def test_tga_query_builder_does_not_preserve_exact_quoted_filename_subject():
    record = _thermal_record("TGA")
    record["metadata"]["display_name"] = "CaCO3 decomposition.csv"
    record["metadata"]["sample_name"] = ""
    record["summary"]["sample_name"] = ""

    payload = build_tga_literature_query(record)

    assert payload["query_display_title"] == "CaCO3 decomposition"
    assert '"CaCO3 decomposition.csv"' not in payload["query_text"]
    assert ".csv" not in payload["query_text"]


def test_thermal_search_queries_keeps_broader_prioritized_fallbacks():
    query_payload = {
        "query_text": "CaCO3 TGA decomposition mass loss residue 718 C",
        "fallback_queries": [
            "CaCO3 thermogravimetric analysis decomposition",
            "CaCO3 decomposition mass loss residue",
            "calcium carbonate thermogravimetric analysis decomposition",
            "calcium carbonate decarbonation calcination CO2 release thermogravimetric analysis",
            "thermogravimetric analysis decomposition mass loss residue",
        ],
    }

    queries = _thermal_search_queries(query_payload)

    assert len(queries) > 2
    assert len(queries) <= 5
    assert queries[0] == "CaCO3 TGA decomposition mass loss residue 718 C"
    assert len(set(queries)) == len(queries)


def test_tga_query_builder_generates_precision_first_query_plan_for_caco3():
    record = _thermal_record("TGA")
    record["metadata"]["display_name"] = "tga_CaCO3_decomposition.csv"
    record["metadata"]["sample_name"] = ""
    record["summary"]["sample_name"] = ""
    record["summary"]["total_mass_loss_percent"] = 43.9
    record["rows"][0]["midpoint_temperature"] = 718.0

    payload = build_tga_literature_query(record)
    queries = _thermal_search_queries(payload)

    assert len(queries) >= 4
    assert "calcium carbonate thermogravimetric analysis decarbonation" in queries[0].lower()
    assert any("caco3 calcination tga" in query.lower() for query in queries)
    assert any("calcite decomposition thermogravimetric analysis" in query.lower() for query in queries)
    assert any("700 800 c" in query.lower() for query in queries)


def test_dsc_and_dta_query_builders_keep_existing_semantics_without_filename_noise():
    dsc_payload = build_dsc_literature_query(_thermal_record("DSC"))
    dta_payload = build_dta_literature_query(_thermal_record("DTA"))

    assert dsc_payload["query_display_mode"] == "DSC / thermal interpretation"
    assert "glass transition" in dsc_payload["query_text"].lower() or "thermal event" in dsc_payload["query_text"].lower()
    assert dta_payload["query_display_mode"] == "DTA / thermal events"
    assert "differential thermal analysis" in dta_payload["query_text"].lower()


def test_thermal_compare_executes_multiple_prioritized_queries_when_available():
    record = _thermal_record("TGA")
    record["metadata"]["display_name"] = "tga_CaCO3_decomposition.csv"
    record["metadata"]["sample_name"] = ""
    record["summary"]["sample_name"] = ""
    record["summary"]["total_mass_loss_percent"] = 43.9
    record["rows"][0]["midpoint_temperature"] = 718.0
    payload = build_tga_literature_query(record)
    provider = QueryAwareStubProvider(
        {
            _thermal_search_queries(payload)[0]: [],
            _thermal_search_queries(payload)[1]: [
                _source(
                    source_id="direct_tga_hit",
                    access_class="abstract_only",
                    text="Calcium carbonate thermogravimetric analysis shows decarbonation and mass loss during calcination.",
                    hint="related",
                )
            ],
        }
    )

    package = compare_result_to_literature(record, provider=provider, provider_scope=["query_aware_stub"])

    assert package["literature_context"]["query_count"] > 1
    assert len(provider.queries_seen) > 1


def test_tga_ranking_prefers_direct_decomposition_papers_over_generic_neighbors():
    record = _thermal_record("TGA")
    record["metadata"]["display_name"] = "CaCO3 decomposition"
    record["metadata"]["sample_name"] = ""
    record["summary"]["sample_name"] = ""
    record["summary"]["total_mass_loss_percent"] = 43.9
    record["rows"][0]["midpoint_temperature"] = 718.0

    provider = StubProvider(
        [
            {
                **_source(
                    source_id="generic_cement_neighbor",
                    access_class="metadata_only",
                    text="Carbonation and low-clinker cement materials study with calcined clay additives.",
                    hint="related",
                ),
                "title": "Low-clinker cement carbonation study",
            },
            {
                **_source(
                    source_id="direct_tga_decomposition",
                    access_class="abstract_only",
                    text="Calcium carbonate thermogravimetric analysis during decarbonation and calcination shows CO2 release and mass loss.",
                    hint="related",
                ),
                "title": "Calcium carbonate thermogravimetric decarbonation",
            },
        ]
    )

    package = compare_result_to_literature(record, provider=provider, provider_scope=["stub_provider"])

    comparisons = package["literature_comparisons"]
    assert comparisons
    assert comparisons[0]["paper_title"] == "Calcium carbonate thermogravimetric decarbonation"
    assert package["literature_context"]["real_literature_available"] is False


def test_tga_primary_surfaced_citation_prefers_direct_decomposition_paper():
    record = _thermal_record("TGA")
    record["metadata"]["display_name"] = "CaCO3 decomposition"
    record["metadata"]["sample_name"] = ""
    record["summary"]["sample_name"] = ""
    record["summary"]["total_mass_loss_percent"] = 43.9
    record["rows"][0]["midpoint_temperature"] = 718.0

    provider = StubProvider(
        [
            {
                **_source(
                    source_id="carbonation_neighbor",
                    access_class="abstract_only",
                    text="Carbonation cycle behavior in cement and calcined clay systems.",
                    hint="related",
                ),
                "title": "Carbonation cycle in blended cement systems",
                "doi": "10.1000/cement-neighbor",
            },
            {
                **_source(
                    source_id="direct_calcite_tga",
                    access_class="abstract_only",
                    text="Calcite thermal decomposition by thermogravimetric analysis produces CaO and CO2 release during calcination.",
                    hint="related",
                ),
                "title": "Calcite thermal decomposition by thermogravimetric analysis",
                "doi": "10.1000/calcite-direct",
            },
        ]
    )

    package = compare_result_to_literature(record, provider=provider, provider_scope=["stub_provider"])

    top_comparison = package["literature_comparisons"][0]
    citations_by_id = {item["citation_id"]: item for item in package["citations"]}

    assert top_comparison["paper_title"] == "Calcite thermal decomposition by thermogravimetric analysis"
    assert citations_by_id[top_comparison["citation_ids"][0]]["doi"] == "10.1000/calcite-direct"


def test_thermal_compare_counts_abstract_backed_accessible_sources_and_sets_evidence_specificity():
    record = _thermal_record("TGA")
    record["metadata"]["display_name"] = "CaCO3 decomposition"
    record["metadata"]["sample_name"] = ""
    record["summary"]["sample_name"] = ""
    record["summary"]["total_mass_loss_percent"] = 43.9
    record["rows"][0]["midpoint_temperature"] = 718.0

    provider = OpenAlexLikeLiteratureProvider(
        search_client=lambda query, filters: {
            "request_id": "openalex_req_tga_abs",
            "result_source": "openalex_api",
            "results": [
                {
                    "source_id": "calcite_abs",
                    "title": "Calcite thermal decomposition by thermogravimetric analysis",
                    "year": 2024,
                    "doi": "10.1000/calcite-abs",
                    "summary": "Calcium carbonate thermogravimetric analysis shows decarbonation, CaO formation, and CO2 release during calcination.",
                }
            ],
        }
    )

    package = compare_result_to_literature(record, provider=provider, provider_scope=["openalex_like_provider"])

    context = package["literature_context"]
    comparison = package["literature_comparisons"][0]
    assert context["accessible_source_count"] == 1
    assert context["evidence_specificity_summary"] == "abstract_backed"
    assert context["metadata_only_evidence"] is False
    assert comparison["access_class"] == "abstract_only"
    assert comparison["confidence"] == "moderate"


def test_thermal_comparison_note_reflects_abstract_vs_metadata_evidence_basis():
    record = _thermal_record("TGA")
    record["metadata"]["display_name"] = "CaCO3 decomposition"
    record["metadata"]["sample_name"] = ""
    record["summary"]["sample_name"] = ""
    record["summary"]["total_mass_loss_percent"] = 43.9
    record["rows"][0]["midpoint_temperature"] = 718.0

    abstract_package = compare_result_to_literature(
        record,
        provider=StubProvider(
            [
                {
                    **_source(
                        source_id="calcite_abs_note",
                        access_class="abstract_only",
                        text="Calcium carbonate thermogravimetric analysis during decarbonation and calcination leads to CaO and CO2 release.",
                        hint="related",
                    ),
                    "title": "Calcite thermal decomposition",
                }
            ]
        ),
        provider_scope=["stub_provider"],
    )
    metadata_package = compare_result_to_literature(
        record,
        provider=StubProvider(
            [
                {
                    **_source(
                        source_id="calcite_meta_note",
                        access_class="metadata_only",
                        text="",
                        hint="related",
                    ),
                    "title": "Calcite thermal decomposition",
                }
            ]
        ),
        provider_scope=["stub_provider"],
    )

    assert "Reasoning used accessible abstract-level text." in abstract_package["literature_comparisons"][0]["comparison_note"]
    assert "calcite" in abstract_package["literature_comparisons"][0]["comparison_note"].lower() or "calcium carbonate" in abstract_package["literature_comparisons"][0]["comparison_note"].lower()
    assert "Reasoning was limited to metadata-level overlap." in metadata_package["literature_comparisons"][0]["comparison_note"]


def test_thermal_compare_merges_near_duplicate_supportive_rows_and_retains_multiple_citations():
    record = _thermal_record("TGA")
    record["metadata"]["display_name"] = "CaCO3 decomposition"
    record["metadata"]["sample_name"] = ""
    record["summary"]["sample_name"] = ""
    record["summary"]["total_mass_loss_percent"] = 43.9
    record["rows"][0]["midpoint_temperature"] = 718.0

    provider = StubProvider(
        [
            {
                **_source(
                    source_id="calcite_support_a",
                    access_class="abstract_only",
                    text="Calcium carbonate thermogravimetric analysis during decarbonation and calcination leads to CaO and CO2 release.",
                    hint="related",
                ),
                "title": "Calcite thermal decomposition A",
            },
            {
                **_source(
                    source_id="calcite_support_b",
                    access_class="abstract_only",
                    text="Calcium carbonate thermogravimetric analysis during decarbonation and calcination leads to CaO and CO2 release.",
                    hint="related",
                ),
                "title": "Calcite thermal decomposition B",
            },
        ]
    )

    package = compare_result_to_literature(record, provider=provider, provider_scope=["stub_provider"])

    assert len(package["literature_comparisons"]) == 1
    assert len(package["literature_comparisons"][0]["citation_ids"]) == 2


def test_weak_metadata_only_neighbors_are_filtered_from_surfaced_thermal_comparisons():
    record = _thermal_record("TGA")
    record["metadata"]["display_name"] = "CaCO3 decomposition"
    record["metadata"]["sample_name"] = ""
    record["summary"]["sample_name"] = ""

    provider = StubProvider(
        [
            {
                **_source(
                    source_id="cement_neighbor_a",
                    access_class="metadata_only",
                    text="Carbonation in low-clinker cement systems.",
                    hint="related",
                ),
                "title": "Carbonation in low-clinker cement systems",
            },
            {
                **_source(
                    source_id="cement_neighbor_b",
                    access_class="metadata_only",
                    text="Calcined clay and alkali-activated cement durability.",
                    hint="related",
                ),
                "title": "Calcined clay and alkali-activated cement durability",
            },
        ]
    )

    package = compare_result_to_literature(record, provider=provider, provider_scope=["stub_provider"])

    assert package["literature_context"]["low_specificity_retrieval"] is True
    assert len(package["literature_comparisons"]) <= 1


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


def test_build_openalex_like_client_from_env_requires_explicit_config(monkeypatch):
    monkeypatch.delenv("MATERIALSCOPE_OPENALEX_EMAIL", raising=False)
    monkeypatch.delenv("THERMOANALYZER_OPENALEX_EMAIL", raising=False)
    monkeypatch.delenv("MATERIALSCOPE_OPENALEX_API_KEY", raising=False)
    monkeypatch.delenv("THERMOANALYZER_OPENALEX_API_KEY", raising=False)
    monkeypatch.delenv("MATERIALSCOPE_OPENALEX_BASE_URL", raising=False)
    monkeypatch.delenv("THERMOANALYZER_OPENALEX_BASE_URL", raising=False)

    assert build_openalex_like_client_from_env() is None


def test_default_registry_builds_env_backed_openalex_provider(monkeypatch):
    monkeypatch.setenv("MATERIALSCOPE_OPENALEX_EMAIL", "research@example.test")

    provider, provider_scope = resolve_literature_provider(
        ["openalex_like_provider"],
        registry=default_literature_provider_registry(),
    )

    assert isinstance(provider, OpenAlexLikeLiteratureProvider)
    assert provider_scope == ["openalex_like_provider"]
    assert getattr(provider, "_search_client", None) is not None


def test_openalex_like_provider_normalizes_raw_openalex_style_rows():
    provider = OpenAlexLikeLiteratureProvider(
        search_client=lambda query, filters: {
            "request_id": "openalex_req_raw",
            "result_source": "openalex_api",
            "results": [
                {
                    "id": "https://openalex.org/W1234567890",
                    "display_name": "MgB2 XRD structure study",
                    "publication_year": 2024,
                    "doi": "https://doi.org/10.1000/raw-openalex",
                    "authorships": [
                        {"author": {"display_name": "A. Author"}},
                        {"author": {"display_name": "B. Author"}},
                    ],
                    "primary_location": {
                        "source": {"display_name": "Journal of XRD"},
                        "landing_page_url": "https://example.test/landing",
                    },
                    "best_oa_location": {"landing_page_url": "https://example.test/oa"},
                }
            ],
        }
    )

    results = provider.search("MgB2 XRD", filters={"top_k": 3})

    assert results[0]["source_id"] == "https://openalex.org/W1234567890"
    assert results[0]["title"] == "MgB2 XRD structure study"
    assert results[0]["authors"] == ["A. Author", "B. Author"]
    assert results[0]["journal"] == "Journal of XRD"
    assert results[0]["doi"] == "10.1000/raw-openalex"
    assert results[0]["url"] == "https://example.test/oa"
    assert results[0]["access_class"] == "metadata_only"
    assert results[0]["provenance"]["provider_id"] == "openalex_like_provider"
    assert results[0]["provenance"]["request_id"] == "openalex_req_raw"


def test_openalex_like_provider_captures_alternate_abstract_shapes():
    provider = OpenAlexLikeLiteratureProvider(
        search_client=lambda query, filters: {
            "request_id": "openalex_req_alt_abs",
            "result_source": "openalex_api",
            "results": [
                {
                    "id": "https://openalex.org/W555",
                    "display_name": "Calcite thermogravimetric decomposition",
                    "publication_year": 2024,
                    "ids": {"doi": "https://doi.org/10.1000/calcite-alt"},
                    "summary": "Calcium carbonate thermogravimetric analysis during calcination and decarbonation.",
                    "best_oa_location": {"landing_page_url": "https://example.test/calcite-alt"},
                },
                {
                    "id": "https://openalex.org/W556",
                    "display_name": "Calcite thermal analysis",
                    "publication_year": 2023,
                    "ids": {"doi": "https://doi.org/10.1000/calcite-inverted"},
                    "abstract_inverted_index": {
                        "Calcite": [0],
                        "decomposition": [1],
                        "during": [2],
                        "thermogravimetric": [3],
                        "analysis": [4],
                    },
                },
            ],
        }
    )

    results = provider.search("calcite thermogravimetric analysis", filters={"top_k": 5})

    assert results[0]["access_class"] == "abstract_only"
    assert "calcium carbonate thermogravimetric analysis" in results[0]["abstract_text"].lower()
    assert results[1]["access_class"] == "abstract_only"
    assert "calcite decomposition during thermogravimetric analysis" in results[1]["abstract_text"].lower()


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
    assert package["literature_context"]["metadata_only_evidence"] is False
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
    assert "candidate-level context" in comparison["comparison_note"]
    assert "Phase Alpha" in comparison["comparison_note"]


def test_xrd_zero_hit_real_provider_persists_no_results_traceability():
    provider = OpenAlexLikeLiteratureProvider(
        search_client=lambda query, filters: {
            "request_id": "openalex_req_zero",
            "result_source": "openalex_api",
            "query_status": "no_results",
            "results": [],
        }
    )

    package = compare_result_to_literature(_base_record(), provider=provider, provider_scope=["openalex_like_provider"])

    context = package["literature_context"]
    assert context["provider_query_status"] == "no_results"
    assert context["no_results_reason"] == "no_real_results"
    assert context["real_literature_available"] is False
    assert context["fixture_fallback_allowed"] is False
    assert context["query_display_title"] == "Phase Alpha"
    assert context["query_display_terms"][:3] == ["powder diffraction", "crystal structure", "phase identification"]
    assert "Synthetic XRD Pattern" in context["query_display_terms"]


def test_xrd_not_configured_provider_persists_traceability():
    provider = OpenAlexLikeLiteratureProvider(search_client=None)

    package = compare_result_to_literature(_base_record(), provider=provider, provider_scope=["openalex_like_provider"])

    context = package["literature_context"]
    assert context["provider_query_status"] == "not_configured"
    assert context["no_results_reason"] == "not_configured"
    assert context["real_literature_available"] is False


def test_xrd_provider_unavailable_persists_traceability():
    def _raising_client(query, filters):
        raise RuntimeError("temporary outage")

    provider = OpenAlexLikeLiteratureProvider(search_client=_raising_client)
    package = compare_result_to_literature(_base_record(), provider=provider, provider_scope=["openalex_like_provider"])

    context = package["literature_context"]
    assert context["provider_query_status"] == "provider_unavailable"
    assert context["no_results_reason"] == "provider_unavailable"
    assert context["provider_error_message"] == "temporary outage"


def test_xrd_request_failed_persists_traceability():
    provider = OpenAlexLikeLiteratureProvider(
        search_client=lambda query, filters: {
            "request_id": "openalex_req_failed",
            "result_source": "openalex_api",
            "query_status": "request_failed",
            "error": "upstream returned malformed payload",
            "results": [],
        }
    )

    package = compare_result_to_literature(_base_record(), provider=provider, provider_scope=["openalex_like_provider"])

    context = package["literature_context"]
    assert context["provider_query_status"] == "request_failed"
    assert context["no_results_reason"] == "request_failed"
    assert context["provider_error_message"] == "upstream returned malformed payload"


def test_xrd_query_too_narrow_persists_traceability():
    record = _base_record()
    record["summary"]["top_candidate_name"] = ""
    record["summary"]["top_candidate_display_name_unicode"] = ""
    record["summary"]["top_candidate_formula"] = ""
    record["summary"]["top_candidate_id"] = ""

    provider = OpenAlexLikeLiteratureProvider(
        search_client=lambda query, filters: {
            "request_id": "openalex_req_narrow",
            "result_source": "openalex_api",
            "query_status": "no_results",
            "results": [],
        }
    )

    package = compare_result_to_literature(record, provider=provider, provider_scope=["openalex_like_provider"])

    context = package["literature_context"]
    assert context["query_text"] == "\"Synthetic XRD Pattern\" XRD mineral phase identification diffraction pattern"
    assert context["provider_query_status"] == "no_results"
    assert context["no_results_reason"] == "no_real_results"
    assert context["real_literature_available"] is False


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


def test_docx_report_appendix_notes_real_provider_zero_hit_xrd_run():
    record = attach_literature_package(
        _base_record(),
        {
            "literature_context": {
                "mode": "metadata_abstract_oa_only",
                "comparison_run_id": "litcmp_zero_001",
                "provider_scope": ["openalex_like_provider"],
                "provider_request_ids": ["openalex_req_zero"],
                "provider_result_source": "openalex_api",
                "query_text": "\"MgB₂\" XRD powder diffraction phase identification crystal structure MgB2",
                "query_display_title": "MgB₂",
                "query_display_mode": "XRD / phase identification",
                "query_display_terms": ["powder diffraction", "crystal structure", "phase identification"],
                "candidate_name": "MgB2",
                "candidate_display_name": "MgB₂",
                "match_status_snapshot": "no_match",
                "confidence_band_snapshot": "no_match",
                "source_count": 0,
                "citation_count": 0,
                "real_literature_available": False,
                "fixture_fallback_used": False,
                "fixture_fallback_allowed": False,
                "provider_query_status": "no_results",
                "no_results_reason": "no_real_results",
            },
            "literature_claims": [],
            "literature_comparisons": [],
            "citations": [],
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

    assert "Literature Comparison Context" in xml
    assert "Candidate Label" in xml
    assert "MgB₂" in xml
    assert "Real Literature Search Outcome" in xml
    assert "did not return suitable bibliographic results" in xml


def test_docx_report_appendix_notes_not_configured_real_provider_xrd_run():
    record = attach_literature_package(
        _base_record(),
        {
            "literature_context": {
                "mode": "metadata_abstract_oa_only",
                "comparison_run_id": "litcmp_not_configured_001",
                "provider_scope": ["openalex_like_provider"],
                "provider_request_ids": ["openalex_req_missing"],
                "provider_result_source": "openalex_api",
                "query_text": "\"Phase Alpha\" XRD powder diffraction phase identification crystal structure",
                "query_display_title": "Phase Alpha",
                "query_display_mode": "XRD / phase identification",
                "candidate_name": "Phase Alpha",
                "candidate_display_name": "Phase Alpha",
                "match_status_snapshot": "matched",
                "confidence_band_snapshot": "medium",
                "source_count": 0,
                "citation_count": 0,
                "real_literature_available": False,
                "fixture_fallback_used": False,
                "fixture_fallback_allowed": False,
                "provider_query_status": "not_configured",
                "no_results_reason": "not_configured",
            },
            "literature_claims": [],
            "literature_comparisons": [],
            "citations": [],
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

    assert "Real Literature Search Outcome" in xml
    assert "was not configured for this environment" in xml
    assert "XRD accepted match status remains authoritative" in xml


def test_docx_report_appendix_notes_request_failed_real_provider_xrd_run():
    record = attach_literature_package(
        _base_record(),
        {
            "literature_context": {
                "mode": "metadata_abstract_oa_only",
                "comparison_run_id": "litcmp_request_failed_001",
                "provider_scope": ["openalex_like_provider"],
                "provider_request_ids": ["openalex_req_failed"],
                "provider_result_source": "openalex_api",
                "query_text": "\"Phase Alpha\" XRD powder diffraction phase identification crystal structure",
                "query_display_title": "Phase Alpha",
                "query_display_mode": "XRD / phase identification",
                "candidate_name": "Phase Alpha",
                "candidate_display_name": "Phase Alpha",
                "match_status_snapshot": "matched",
                "confidence_band_snapshot": "medium",
                "source_count": 0,
                "citation_count": 0,
                "real_literature_available": False,
                "fixture_fallback_used": False,
                "fixture_fallback_allowed": False,
                "provider_query_status": "request_failed",
                "provider_error_message": "upstream returned malformed payload",
                "no_results_reason": "request_failed",
            },
            "literature_claims": [],
            "literature_comparisons": [],
            "citations": [],
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

    assert "Real Literature Search Outcome" in xml
    assert "did not return a usable bibliographic response" in xml
    assert "upstream returned malformed payload" in xml


def test_docx_report_thermal_literature_sections_use_thermal_wording():
    record = attach_literature_package(
        _thermal_record("TGA"),
        {
            "literature_context": {
                "mode": "metadata_abstract_oa_only",
                "comparison_run_id": "litcmp_tga_001",
                "provider_scope": ["openalex_like_provider"],
                "provider_request_ids": ["openalex_req_tga"],
                "provider_result_source": "openalex_api",
                "query_text": "\"Composite C\" TGA decomposition mass loss residue 411 C",
                "query_display_title": "Composite C TGA decomposition profile",
                "query_display_mode": "TGA / decomposition profile",
                "query_rationale": "The TGA literature search is centered on the decomposition profile with a leading step near 411 C.",
                "real_literature_available": True,
            },
            "literature_claims": [{"claim_id": "C1", "claim_text": "The TGA result indicates a decomposition profile with a dominant mass-loss step that remains qualitative."}],
            "literature_comparisons": [
                {
                    "claim_id": "C1",
                    "claim_text": "The TGA result indicates a decomposition profile with a dominant mass-loss step that remains qualitative.",
                    "support_label": "partially_supports",
                    "confidence": "moderate",
                    "rationale": "This paper discusses TGA decomposition behavior relevant to Composite C. It remains contextual support rather than validation.",
                    "validation_posture": "related_support",
                    "paper_title": "Composite C decomposition study",
                    "paper_year": 2024,
                    "paper_journal": "Journal of Thermal Analysis",
                    "provider_id": "openalex_like_provider",
                    "access_class": "abstract_only",
                    "citation_ids": ["ref1"],
                }
            ],
            "citations": [{"citation_id": "ref1", "title": "Composite C decomposition study", "access_class": "abstract_only"}],
        },
    )
    dataset = ThermalDataset(
        data=pd.DataFrame({"temperature": [350.0, 411.0, 470.0], "signal": [100.0, 82.0, 67.6]}),
        metadata={"sample_name": "Composite C", "display_name": "Composite C TGA"},
        data_type="TGA",
        units={"temperature": "degC", "signal": "%"},
        original_columns={"temperature": "temperature", "signal": "signal"},
        file_path="",
    )

    docx_bytes = generate_docx_report(results={record["id"]: record}, datasets={record["dataset_key"]: dataset})
    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    assert "Thermal Literature Search Summary" in xml
    assert "Relevant References" in xml
    assert "Alternative or Non-Validating References" in xml
    assert "does not validate or override the current result" in xml
    assert "XRD screening" not in xml
    assert "top-ranked candidate" not in xml


def test_docx_report_thermal_low_specificity_retrieval_note_is_rendered():
    record = attach_literature_package(
        _thermal_record("TGA"),
        {
            "literature_context": {
                "mode": "metadata_abstract_oa_only",
                "comparison_run_id": "litcmp_tga_low_specificity",
                "provider_scope": ["openalex_like_provider"],
                "provider_request_ids": ["openalex_req_tga_low"],
                "provider_result_source": "openalex_api",
                "query_text": "calcium carbonate thermogravimetric analysis decarbonation",
                "query_display_title": "CaCO3 decomposition",
                "query_display_mode": "TGA / decomposition profile",
                "query_rationale": "The TGA literature search is centered on the decomposition profile with a leading step near 718 C.",
                "real_literature_available": True,
                "metadata_only_evidence": True,
                "low_specificity_retrieval": True,
            },
            "literature_claims": [{"claim_id": "C1", "claim_text": "The TGA result indicates a decomposition profile."}],
            "literature_comparisons": [
                {
                    "claim_id": "C1",
                    "claim_text": "The TGA result indicates a decomposition profile.",
                    "support_label": "related_but_inconclusive",
                    "confidence": "low",
                    "rationale": "Weak neighboring materials paper.",
                    "citation_ids": ["ref1"],
                }
            ],
            "citations": [{"citation_id": "ref1", "title": "Carbonation in low-clinker cement systems", "access_class": "metadata_only"}],
        },
    )
    dataset = ThermalDataset(
        data=pd.DataFrame({"temperature": [650.0, 718.0, 790.0], "signal": [100.0, 82.0, 56.1]}),
        metadata={"sample_name": "CaCO3 decomposition", "display_name": "CaCO3 decomposition"},
        data_type="TGA",
        units={"temperature": "degC", "signal": "%"},
        original_columns={"temperature": "temperature", "signal": "signal"},
        file_path="",
    )

    docx_bytes = generate_docx_report(results={record["id"]: record}, datasets={record["dataset_key"]: dataset})
    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    assert "low-specificity and mostly metadata/abstract-level" in xml


def test_docx_report_thermal_evidence_basis_note_is_rendered_for_abstract_backed_results():
    record = attach_literature_package(
        _thermal_record("TGA"),
        {
            "literature_context": {
                "mode": "metadata_abstract_oa_only",
                "comparison_run_id": "litcmp_tga_abstract_backed",
                "provider_scope": ["openalex_like_provider"],
                "provider_request_ids": ["openalex_req_tga_abstract_backed"],
                "provider_result_source": "openalex_api",
                "query_text": "calcium carbonate thermogravimetric analysis decarbonation",
                "query_display_title": "CaCO3 decomposition",
                "query_display_mode": "TGA / decomposition profile",
                "real_literature_available": True,
                "evidence_specificity_summary": "abstract_backed",
            },
            "literature_claims": [{"claim_id": "C1", "claim_text": "The TGA result indicates a decomposition profile."}],
            "literature_comparisons": [
                {
                    "claim_id": "C1",
                    "claim_text": "The TGA result indicates a decomposition profile.",
                    "support_label": "partially_supports",
                    "confidence": "moderate",
                    "rationale": "Abstract-backed direct decomposition reference.",
                    "citation_ids": ["ref1"],
                }
            ],
            "citations": [{"citation_id": "ref1", "title": "Calcite thermal decomposition", "access_class": "abstract_only"}],
        },
    )
    dataset = ThermalDataset(
        data=pd.DataFrame({"temperature": [650.0, 718.0, 790.0], "signal": [100.0, 82.0, 56.1]}),
        metadata={"sample_name": "CaCO3 decomposition", "display_name": "CaCO3 decomposition"},
        data_type="TGA",
        units={"temperature": "degC", "signal": "%"},
        original_columns={"temperature": "temperature", "signal": "signal"},
        file_path="",
    )

    docx_bytes = generate_docx_report(results={record["id"]: record}, datasets={record["dataset_key"]: dataset})
    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    assert "accessible abstract-level evidence" in xml


def test_docx_report_places_abstract_backed_supportive_thermal_reference_in_relevant_references():
    record = attach_literature_package(
        _thermal_record("TGA"),
        {
            "literature_context": {
                "mode": "metadata_abstract_oa_only",
                "comparison_run_id": "litcmp_tga_partition",
                "provider_scope": ["openalex_like_provider"],
                "provider_request_ids": ["openalex_req_tga_partition"],
                "provider_result_source": "openalex_api",
                "analysis_type": "TGA",
                "query_text": "calcium carbonate thermogravimetric analysis decarbonation",
                "query_display_title": "CaCO3 decomposition",
                "query_display_mode": "TGA / decomposition profile",
                "real_literature_available": True,
                "metadata_only_evidence": False,
                "evidence_specificity_summary": "mixed_metadata_and_abstract",
            },
            "literature_claims": [{"claim_id": "C1", "claim_text": "The TGA result indicates a decomposition profile."}],
            "literature_comparisons": [
                {
                    "claim_id": "C1",
                    "claim_text": "The TGA result indicates a decomposition profile.",
                    "support_label": "related_but_inconclusive",
                    "confidence": "moderate",
                    "validation_posture": "contextual_only",
                    "rationale": "Abstract-backed direct decomposition reference.",
                    "citation_ids": ["ref7"],
                },
                {
                    "claim_id": "C1",
                    "claim_text": "The TGA result indicates a decomposition profile.",
                    "support_label": "related_but_inconclusive",
                    "confidence": "low",
                    "validation_posture": "non_validating",
                    "rationale": "Weak neighboring materials paper.",
                    "citation_ids": ["ref6"],
                },
            ],
            "citations": [
                {"citation_id": "ref7", "title": "Calcite thermal decomposition by thermogravimetric analysis", "access_class": "abstract_only"},
                {"citation_id": "ref6", "title": "Carbonation in low-clinker cement systems", "access_class": "metadata_only"},
            ],
        },
    )
    dataset = ThermalDataset(
        data=pd.DataFrame({"temperature": [650.0, 718.0, 790.0], "signal": [100.0, 82.0, 56.1]}),
        metadata={"sample_name": "CaCO3 decomposition", "display_name": "CaCO3 decomposition"},
        data_type="TGA",
        units={"temperature": "degC", "signal": "%"},
        original_columns={"temperature": "temperature", "signal": "signal"},
        file_path="",
    )

    docx_bytes = generate_docx_report(results={record["id"]: record}, datasets={record["dataset_key"]: dataset})
    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    assert "Relevant References" in xml
    assert "Calcite thermal decomposition by thermogravimetric analysis" in xml
    assert "Alternative or Non-Validating References" in xml
    assert "Carbonation in low-clinker cement systems" in xml


def test_docx_report_preserves_clickable_doi_links_for_thermal_references():
    record = attach_literature_package(
        _thermal_record("TGA"),
        {
            "literature_context": {
                "mode": "metadata_abstract_oa_only",
                "comparison_run_id": "litcmp_tga_doi_links",
                "provider_scope": ["openalex_like_provider"],
                "provider_request_ids": ["openalex_req_tga_doi"],
                "provider_result_source": "openalex_api",
                "query_text": "calcium carbonate thermogravimetric analysis decarbonation",
                "query_display_title": "Calcium carbonate decomposition",
                "query_display_mode": "TGA / decomposition profile",
                "real_literature_available": True,
            },
            "literature_claims": [{"claim_id": "C1", "claim_text": "The TGA result indicates a decomposition profile."}],
            "literature_comparisons": [
                {
                    "claim_id": "C1",
                    "claim_text": "The TGA result indicates a decomposition profile.",
                    "support_label": "partially_supports",
                    "confidence": "low",
                    "rationale": "Direct calcite TGA decomposition reference.",
                    "validation_posture": "related_support",
                    "citation_ids": ["ref1"],
                }
            ],
            "citations": [
                {
                    "citation_id": "ref1",
                    "title": "Calcite thermal decomposition by thermogravimetric analysis",
                    "authors": ["A. Author"],
                    "year": 2024,
                    "journal": "Journal of Thermal Analysis",
                    "doi": "10.1000/calcite-direct",
                    "url": "https://example.test/calcite-direct",
                    "access_class": "abstract_only",
                    "citation_text": "A. Author (2024). Calcite thermal decomposition by thermogravimetric analysis. Journal of Thermal Analysis.",
                    "source_license_note": "provider_abstract",
                    "provenance": {
                        "provider_id": "openalex_like_provider",
                        "result_source": "openalex_api",
                        "provider_scope": ["openalex_like_provider"],
                        "provider_request_ids": ["openalex_req_tga_doi"],
                    },
                }
            ],
        },
    )
    dataset = ThermalDataset(
        data=pd.DataFrame({"temperature": [650.0, 718.0, 790.0], "signal": [100.0, 82.0, 56.1]}),
        metadata={"sample_name": "CaCO3 decomposition", "display_name": "CaCO3 decomposition"},
        data_type="TGA",
        units={"temperature": "degC", "signal": "%"},
        original_columns={"temperature": "temperature", "signal": "signal"},
        file_path="",
    )

    docx_bytes = generate_docx_report(results={record["id"]: record}, datasets={record["dataset_key"]: dataset})
    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
        rels = archive.read("word/_rels/document.xml.rels").decode("utf-8")

    assert "10.1000/calcite-direct" in xml
    assert "https://doi.org/10.1000/calcite-direct" in rels


def test_docx_report_formats_chemical_formulas_in_literature_text_without_breaking_doi_links():
    record = attach_literature_package(
        _thermal_record("TGA"),
        {
            "literature_context": {
                "mode": "metadata_abstract_oa_only",
                "comparison_run_id": "litcmp_tga_formula_docx",
                "provider_scope": ["openalex_like_provider"],
                "provider_request_ids": ["openalex_req_tga_formula"],
                "provider_result_source": "openalex_api",
                "query_text": "CaCO3 decomposition CO2 capture",
                "query_display_title": "CaCO3 decomposition",
                "query_display_mode": "TGA / decomposition profile",
                "query_rationale": "CaCO3 decomposition with CO<sub>2</sub> release from Ca(OH)2–CaCO3–CaO systems.",
                "real_literature_available": True,
                "evidence_specificity_summary": "abstract_backed",
            },
            "literature_claims": [{"claim_id": "C1", "claim_text": "CaCO3 decomposition remains qualitative."}],
            "literature_comparisons": [
                {
                    "claim_id": "C1",
                    "claim_text": "CaCO3 decomposition remains qualitative.",
                    "support_label": "partially_supports",
                    "confidence": "moderate",
                    "rationale": "CaCO3 decomposition discusses CO<sub>2</sub> release from Ca(OH)2–CaCO3–CaO systems.",
                    "validation_posture": "related_support",
                    "citation_ids": ["ref1"],
                }
            ],
            "citations": [
                {
                    "citation_id": "ref1",
                    "title": "CaCO3 decomposition and CO2 capture",
                    "authors": ["A. Author"],
                    "year": 2024,
                    "journal": "Journal of CaCO3 Studies",
                    "doi": "10.1000/calcite-direct",
                    "url": "https://example.test/calcite-direct",
                    "access_class": "abstract_only",
                    "citation_text": "A. Author (2024). CaCO3 decomposition and CO2 capture. Journal of CaCO3 Studies.",
                    "source_license_note": "provider_abstract",
                    "provenance": {
                        "provider_id": "openalex_like_provider",
                        "result_source": "openalex_api",
                        "provider_scope": ["openalex_like_provider"],
                        "provider_request_ids": ["openalex_req_tga_formula"],
                    },
                }
            ],
        },
    )
    dataset = ThermalDataset(
        data=pd.DataFrame({"temperature": [650.0, 718.0, 790.0], "signal": [100.0, 82.0, 56.1]}),
        metadata={"sample_name": "CaCO3 decomposition", "display_name": "CaCO3 decomposition"},
        data_type="TGA",
        units={"temperature": "degC", "signal": "%"},
        original_columns={"temperature": "temperature", "signal": "signal"},
        file_path="",
    )

    docx_bytes = generate_docx_report(results={record["id"]: record}, datasets={record["dataset_key"]: dataset})
    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
        rels = archive.read("word/_rels/document.xml.rels").decode("utf-8")

    assert "CaCO₃ decomposition" in xml
    assert "CO₂ capture" in xml
    assert "Ca(OH)₂–CaCO₃–CaO" in xml
    assert "https://doi.org/10.1000/calcite-direct" in rels
    assert "10.1000/calcite-direct" in xml
