from __future__ import annotations

from pathlib import Path
from contextlib import nullcontext
from types import SimpleNamespace

from core.chemical_formula_formatting import format_chemical_formula_text
from ui.components import literature_compare_panel

_REPO_ROOT = Path(__file__).resolve().parents[1]


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self):
        return self._payload


def test_merge_literature_detail_into_record_updates_saved_result_fields():
    record = {
        "id": "xrd_demo",
        "dataset_key": "xrd_demo",
        "summary": {"match_status": "matched"},
        "processing": {"workflow": "before"},
        "citations": [],
    }
    detail = {
        "summary": {"match_status": "matched", "top_candidate_name": "Phase Alpha"},
        "processing": {"workflow": "after"},
        "provenance": {"saved_at_utc": "2026-03-19T00:00:00Z"},
        "validation": {"status": "pass"},
        "review": {"status": "screening"},
        "literature_context": {"comparison_run_id": "litcmp_demo_001"},
        "literature_claims": [{"claim_id": "C1"}],
        "literature_comparisons": [{"claim_id": "C1", "support_label": "supports"}],
        "citations": [{"citation_id": "ref1", "title": "Supporting paper"}],
    }

    updated = literature_compare_panel.merge_literature_detail_into_record(
        record,
        detail_payload=detail,
    )

    assert updated["summary"]["top_candidate_name"] == "Phase Alpha"
    assert updated["processing"]["workflow"] == "after"
    assert updated["literature_context"]["comparison_run_id"] == "litcmp_demo_001"
    assert updated["literature_claims"][0]["claim_id"] == "C1"
    assert updated["citations"][0]["citation_id"] == "ref1"
    assert updated["report_payload"]["literature_fixture_detected"] is False


def test_merge_literature_detail_into_record_prefers_empty_final_detail_over_stale_local_payload():
    record = {
        "id": "tga_demo",
        "literature_context": {"comparison_run_id": "old_run"},
        "literature_claims": [{"claim_id": "C1"}],
        "literature_comparisons": [{"claim_id": "C1", "support_label": "related_but_inconclusive"}],
        "citations": [{"citation_id": "ref_old", "title": "Old paper"}],
    }
    detail = {
        "result": {"id": "tga_demo"},
        "literature_context": {},
        "literature_claims": [],
        "literature_comparisons": [],
        "citations": [],
    }
    compare = {
        "literature_context": {"comparison_run_id": "stale_compare"},
        "literature_claims": [{"claim_id": "C_stale"}],
        "literature_comparisons": [{"claim_id": "C_stale", "support_label": "supports"}],
        "citations": [{"citation_id": "ref_stale", "title": "Stale paper"}],
    }

    updated = literature_compare_panel.merge_literature_detail_into_record(
        record,
        compare_response=compare,
        detail_payload=detail,
    )

    assert updated["literature_context"] == {}
    assert updated["literature_claims"] == []
    assert updated["literature_comparisons"] == []
    assert updated["citations"] == []


def test_build_literature_sections_handles_absent_payload():
    sections = literature_compare_panel.build_literature_sections({})

    assert sections["has_payload"] is False
    assert sections["comparisons"] == []
    assert sections["supporting_references"] == []
    assert sections["alternative_references"] == []


def test_render_literature_sections_no_crash_when_payload_absent(monkeypatch):
    captions: list[str] = []
    markdowns: list[str] = []

    fake_st = SimpleNamespace(
        caption=lambda text: captions.append(str(text)),
        markdown=lambda text: markdowns.append(str(text)),
        warning=lambda text: captions.append(str(text)),
        container=lambda: nullcontext(),
    )
    monkeypatch.setattr(literature_compare_panel, "st", fake_st)

    literature_compare_panel.render_literature_sections({}, lang="en")

    assert markdowns == []
    assert any("No literature comparison has been run yet" in item for item in captions)


def test_render_literature_sections_renders_compact_payload(monkeypatch):
    captions: list[str] = []
    markdowns: list[str] = []
    warnings: list[str] = []

    fake_st = SimpleNamespace(
        caption=lambda text: captions.append(str(text)),
        markdown=lambda text: markdowns.append(str(text)),
        warning=lambda text: warnings.append(str(text)),
        container=lambda: nullcontext(),
    )
    monkeypatch.setattr(literature_compare_panel, "st", fake_st)

    literature_compare_panel.render_literature_sections(
        {
            "summary": {"match_status": "matched", "confidence_band": "medium"},
            "literature_context": {"restricted_content_used": False, "metadata_only_evidence": True},
            "literature_claims": [
                {
                    "claim_id": "C1",
                    "claim_text": "Phase Alpha remains a qualitative follow-up target rather than a confirmed identification.",
                }
            ],
            "literature_comparisons": [
                {
                    "claim_id": "C1",
                    "support_label": "supports",
                    "confidence": "moderate",
                    "rationale": "Accessible literature supports the claim in a cautionary, non-definitive way.",
                    "citation_ids": ["ref1"],
                }
            ],
            "citations": [
                {
                    "citation_id": "ref1",
                    "title": "Supporting paper",
                    "year": 2025,
                    "journal": "Fixture Journal",
                    "doi": "10.1000/support",
                    "access_class": "abstract_only",
                }
            ],
        },
        lang="en",
    )

    assert any("Literature Comparison" in item for item in markdowns)
    assert any("Supporting References" in item for item in markdowns)
    assert any("Contradictory or Alternative References" in item for item in markdowns)
    assert any("Recommended Follow-Up Literature Checks" in item for item in markdowns)
    assert any("Phase Alpha remains a qualitative follow-up target" in item for item in markdowns)
    assert any("Supporting paper" in item for item in markdowns)
    assert any("abstract_only" in item for item in captions)
    assert warnings == []


def test_render_citation_item_renders_clickable_doi_link(monkeypatch):
    markdowns: list[str] = []
    captions: list[str] = []

    fake_st = SimpleNamespace(
        caption=lambda text: captions.append(str(text)),
        markdown=lambda text: markdowns.append(str(text)),
        warning=lambda text: captions.append(str(text)),
        container=lambda: nullcontext(),
    )
    monkeypatch.setattr(literature_compare_panel, "st", fake_st)

    literature_compare_panel._render_citation_item(
        {
            "title": "Calcite thermal decomposition by thermogravimetric analysis",
            "year": 2024,
            "journal": "Journal of Thermal Analysis",
            "doi": "10.1000/calcite-direct",
            "access_class": "abstract_only",
        },
        lang="en",
        provider_scope=[],
    )

    assert any("DOI: [10.1000/calcite-direct](https://doi.org/10.1000/calcite-direct)" in item for item in markdowns)


def test_format_chemical_formula_text_formats_formulas_but_not_doi_or_urls():
    text = "CaCO3 decomposition and CO<sub>2</sub> capture. DOI: 10.1000/caco3-study https://doi.org/10.1000/caco3-study"

    formatted = format_chemical_formula_text(text)

    assert "CaCO₃ decomposition" in formatted
    assert "CO₂ capture" in formatted
    assert "10.1000/caco3-study" in formatted
    assert "https://doi.org/10.1000/caco3-study" in formatted


def test_build_literature_sections_marks_xrd_candidate_mode_and_paper_cards():
    sections = literature_compare_panel.build_literature_sections(
        {
            "analysis_type": "XRD",
            "summary": {
                "match_status": "matched",
                "top_candidate_name": "Phase Alpha",
                "top_candidate_score": 0.78,
            },
            "literature_context": {
                "query_text": "\"Phase Alpha\" XRD powder diffraction",
                "candidate_name": "Phase Alpha",
                "real_literature_available": True,
            },
            "literature_claims": [{"claim_id": "C1", "claim_text": "Phase Alpha remains qualitative."}],
            "literature_comparisons": [
                {
                    "claim_id": "C1",
                    "claim_text": "Phase Alpha remains qualitative.",
                    "paper_title": "Phase Alpha XRD characterization",
                    "paper_year": 2024,
                    "paper_journal": "Journal of XRD",
                    "paper_url": "https://example.test/real-alpha",
                    "provider_id": "openalex_like_provider",
                    "access_class": "abstract_only",
                    "comparison_note": "This paper discusses XRD characterization of Phase Alpha.",
                    "validation_posture": "non_validating",
                    "support_label": "related_but_inconclusive",
                    "confidence": "low",
                    "citation_ids": ["ref1"],
                }
            ],
            "citations": [{"citation_id": "ref1", "title": "Phase Alpha XRD characterization", "access_class": "abstract_only"}],
        }
    )

    assert sections["xrd_candidate_mode"] is True
    assert sections["candidate_summary"]["best_ranked_candidate"] == "Phase Alpha"
    assert sections["paper_cards"][0]["paper_title"] == "Phase Alpha XRD characterization"


def test_default_compare_request_uses_real_xrd_provider():
    payload = literature_compare_panel._default_compare_request(current_record={"analysis_type": "XRD"})

    assert payload["provider_ids"] == ["openalex_like_provider"]
    assert payload["filters"]["analysis_type"] == "XRD"
    assert payload["filters"]["allow_fixture_fallback"] is False


def test_default_compare_request_uses_real_provider_for_thermal_modalities():
    for analysis_type in ("DSC", "DTA", "TGA"):
        payload = literature_compare_panel._default_compare_request(current_record={"analysis_type": analysis_type})

        assert payload["provider_ids"] == ["openalex_like_provider"]
        assert payload["max_claims"] == 2
        assert payload["filters"]["analysis_type"] == analysis_type
        assert payload["filters"]["allow_fixture_fallback"] is False


def test_default_compare_request_uses_real_provider_for_ftir():
    payload = literature_compare_panel._default_compare_request(current_record={"analysis_type": "FTIR"})

    assert payload["provider_ids"] == ["openalex_like_provider"]
    assert payload["max_claims"] == 2
    assert payload["filters"]["analysis_type"] == "FTIR"
    assert payload["filters"]["allow_fixture_fallback"] is False


def test_render_literature_sections_renders_xrd_candidate_summary_before_paper_cards(monkeypatch):
    captions: list[str] = []
    markdowns: list[str] = []
    warnings: list[str] = []

    fake_st = SimpleNamespace(
        caption=lambda text: captions.append(str(text)),
        markdown=lambda text: markdowns.append(str(text)),
        warning=lambda text: warnings.append(str(text)),
        container=lambda: nullcontext(),
    )
    monkeypatch.setattr(literature_compare_panel, "st", fake_st)

    literature_compare_panel.render_literature_sections(
        {
            "analysis_type": "XRD",
            "summary": {
                "match_status": "no_match",
                "confidence_band": "no_match",
                "top_candidate_name": "Phase Alpha",
                "top_candidate_score": 0.33,
                "top_candidate_shared_peak_count": 2,
            },
            "literature_context": {
                "query_text": "\"Phase Alpha\" XRD powder diffraction",
                "query_rationale": "The literature search is centered on the top-ranked XRD candidate 'Phase Alpha'.",
                "candidate_name": "Phase Alpha",
                "candidate_display_name": "Phase Alpha",
                "match_status_snapshot": "no_match",
                "confidence_band_snapshot": "no_match",
                "real_literature_available": True,
            },
            "literature_claims": [{"claim_id": "C1", "claim_text": "The current XRD result remains a no_match screening outcome."}],
            "literature_comparisons": [
                {
                    "claim_id": "C1",
                    "claim_text": "The current XRD result remains a no_match screening outcome.",
                    "paper_title": "Phase Alpha XRD characterization",
                    "paper_year": 2024,
                    "paper_journal": "Journal of XRD",
                    "paper_url": "https://example.test/real-alpha",
                    "provider_id": "openalex_like_provider",
                    "access_class": "abstract_only",
                    "comparison_note": "This paper discusses XRD characterization of Phase Alpha. The result remains no_match and the source provides candidate-level context rather than phase validation.",
                    "validation_posture": "contextual_only",
                    "support_label": "related_but_inconclusive",
                    "confidence": "low",
                    "citation_ids": ["ref1"],
                }
            ],
            "citations": [{"citation_id": "ref1", "title": "Phase Alpha XRD characterization", "access_class": "abstract_only"}],
        },
        lang="en",
    )

    assert warnings == []
    assert markdowns[0] == "**XRD Candidate Evidence Summary**"
    assert any("Literature Check For Top-Ranked Candidate" in item for item in markdowns)
    assert any("Phase Alpha XRD characterization" in item for item in markdowns)
    assert any("candidate-level context rather than phase validation" in item for item in markdowns)


def test_render_literature_sections_localizes_xrd_note_in_turkish(monkeypatch):
    captions: list[str] = []
    markdowns: list[str] = []

    fake_st = SimpleNamespace(
        caption=lambda text: captions.append(str(text)),
        markdown=lambda text: markdowns.append(str(text)),
        warning=lambda text: captions.append(str(text)),
        container=lambda: nullcontext(),
    )
    monkeypatch.setattr(literature_compare_panel, "st", fake_st)

    literature_compare_panel.render_literature_sections(
        {
            "analysis_type": "XRD",
            "summary": {
                "match_status": "matched",
                "confidence_band": "medium",
                "top_candidate_name": "MgB2",
            },
            "literature_context": {
                "query_text": "\"MgB2\" XRD powder diffraction",
                "candidate_name": "MgB2",
                "candidate_display_name": "MgB₂",
                "match_status_snapshot": "matched",
                "confidence_band_snapshot": "medium",
                "real_literature_available": True,
            },
            "literature_claims": [{"claim_id": "C1", "claim_text": "MgB₂ remains qualitative."}],
            "literature_comparisons": [
                {
                    "claim_id": "C1",
                    "claim_text": "MgB₂ remains qualitative.",
                    "candidate_name": "MgB₂",
                    "paper_title": "MgB2 XRD characterization",
                    "paper_year": 2024,
                    "paper_journal": "Journal of XRD",
                    "paper_url": "https://example.test/mgb2",
                    "provider_id": "openalex_like_provider",
                    "access_class": "abstract_only",
                    "comparison_note": "This paper discusses XRD characterization of MgB2.",
                    "validation_posture": "related_support",
                    "match_status_snapshot": "matched",
                    "confidence_band_snapshot": "medium",
                    "support_label": "partially_supports",
                    "confidence": "low",
                    "citation_ids": ["ref1"],
                }
            ],
            "citations": [{"citation_id": "ref1", "title": "MgB2 XRD characterization", "access_class": "abstract_only"}],
        },
        lang="tr",
    )

    assert any("faz doğrulaması yapmaz" in item for item in markdowns)
    assert not any("Secondary metadata: claim" in item for item in captions)


def test_render_literature_sections_renders_xrd_zero_hit_real_search_block(monkeypatch):
    captions: list[str] = []
    markdowns: list[str] = []

    fake_st = SimpleNamespace(
        caption=lambda text: captions.append(str(text)),
        markdown=lambda text: markdowns.append(str(text)),
        warning=lambda text: captions.append(str(text)),
        container=lambda: nullcontext(),
    )
    monkeypatch.setattr(literature_compare_panel, "st", fake_st)

    literature_compare_panel.render_literature_sections(
        {
            "analysis_type": "XRD",
            "summary": {
                "match_status": "no_match",
                "confidence_band": "no_match",
                "top_candidate_name": "cod_1000026",
                "top_candidate_display_name_unicode": "MgB₂",
            },
            "literature_context": {
                "query_text": "\"MgB₂\" XRD powder diffraction phase identification crystal structure MgB2",
                "query_display_title": "MgB₂",
                "query_display_mode": "XRD / phase identification",
                "query_display_terms": ["powder diffraction", "crystal structure", "phase identification"],
                "candidate_name": "MgB2",
                "candidate_display_name": "MgB₂",
                "candidate_id": "cod_1000026",
                "match_status_snapshot": "no_match",
                "confidence_band_snapshot": "no_match",
                "real_literature_available": False,
                "fixture_fallback_used": False,
                "fixture_fallback_allowed": False,
                "provider_query_status": "no_results",
                "no_results_reason": "no_real_results",
                "source_count": 0,
                "citation_count": 0,
            },
            "literature_claims": [],
            "literature_comparisons": [],
            "citations": [],
        },
        lang="en",
    )

    assert markdowns[0] == "**XRD Candidate Evidence Summary**"
    assert any("**Literature Search Summary**" == item for item in markdowns)
    assert any("**Real Literature Search Status**" == item for item in markdowns)
    assert any("Candidate phase: MgB₂" in item for item in captions)
    assert any("No displayable real papers were found for this candidate phase" in item for item in captions)
    assert any("accepted XRD result remains no_match" in item for item in captions)
    assert not any("Candidate phase: cod_1000026" in item for item in captions)
    assert not any(item == "**Literature Check For Top-Ranked Candidate**" for item in markdowns)
    assert not any(item == "\"MgB₂\" XRD powder diffraction phase identification crystal structure MgB2" for item in markdowns)


def test_render_literature_sections_renders_xrd_request_failed_block(monkeypatch):
    captions: list[str] = []
    markdowns: list[str] = []

    fake_st = SimpleNamespace(
        caption=lambda text: captions.append(str(text)),
        markdown=lambda text: markdowns.append(str(text)),
        warning=lambda text: captions.append(str(text)),
        container=lambda: nullcontext(),
    )
    monkeypatch.setattr(literature_compare_panel, "st", fake_st)

    literature_compare_panel.render_literature_sections(
        {
            "analysis_type": "XRD",
            "summary": {
                "match_status": "matched",
                "confidence_band": "medium",
                "top_candidate_name": "Phase Alpha",
            },
            "literature_context": {
                "query_text": "\"Phase Alpha\" XRD powder diffraction phase identification crystal structure",
                "query_display_title": "Phase Alpha",
                "query_display_mode": "XRD / phase identification",
                "query_display_terms": ["powder diffraction", "crystal structure", "phase identification"],
                "candidate_name": "Phase Alpha",
                "candidate_display_name": "Phase Alpha",
                "match_status_snapshot": "matched",
                "confidence_band_snapshot": "medium",
                "real_literature_available": False,
                "fixture_fallback_used": False,
                "fixture_fallback_allowed": False,
                "provider_query_status": "request_failed",
                "no_results_reason": "request_failed",
                "provider_error_message": "upstream returned malformed payload",
                "source_count": 0,
                "citation_count": 0,
            },
            "literature_claims": [],
            "literature_comparisons": [],
            "citations": [],
        },
        lang="en",
    )

    assert any("**Real Literature Search Status**" == item for item in markdowns)
    assert any("The real literature request failed" in item for item in captions)
    assert any("usable bibliographic response" in item for item in captions)
    assert any("Technical provider note: upstream returned malformed payload" in item for item in captions)


def test_render_literature_sections_renders_thermal_search_summary_without_xrd_copy(monkeypatch):
    captions: list[str] = []
    markdowns: list[str] = []

    fake_st = SimpleNamespace(
        caption=lambda text: captions.append(str(text)),
        markdown=lambda text: markdowns.append(str(text)),
        warning=lambda text: captions.append(str(text)),
        container=lambda: nullcontext(),
    )
    monkeypatch.setattr(literature_compare_panel, "st", fake_st)

    literature_compare_panel.render_literature_sections(
        {
            "analysis_type": "TGA",
            "summary": {
                "sample_name": "Composite C",
            },
            "literature_context": {
                "query_text": "\"Composite C\" TGA decomposition mass loss residue 411 C",
                "query_display_title": "Composite C TGA decomposition profile",
                "query_display_mode": "TGA / decomposition profile",
                "query_display_terms": ["decomposition", "mass loss", "residue"],
                "query_rationale": "The TGA literature search is centered on the decomposition profile with a leading step near 411 C.",
                "real_literature_available": False,
                "provider_query_status": "not_configured",
                "no_results_reason": "not_configured",
                "source_count": 0,
                "citation_count": 0,
            },
            "literature_claims": [],
            "literature_comparisons": [],
            "citations": [],
        },
        lang="en",
    )

    assert any("**Thermal Literature Search Summary**" == item for item in markdowns)
    assert any("Search mode: TGA / decomposition profile" in item for item in captions)
    assert not any("XRD Candidate Evidence Summary" in item for item in markdowns)
    assert not any("top-ranked candidate" in item.lower() for item in captions)


def test_render_literature_sections_shows_cleaned_thermal_focus_label(monkeypatch):
    captions: list[str] = []
    markdowns: list[str] = []

    fake_st = SimpleNamespace(
        caption=lambda text: captions.append(str(text)),
        markdown=lambda text: markdowns.append(str(text)),
        warning=lambda text: captions.append(str(text)),
        container=lambda: nullcontext(),
    )
    monkeypatch.setattr(literature_compare_panel, "st", fake_st)

    literature_compare_panel.render_literature_sections(
        {
            "analysis_type": "TGA",
            "summary": {"sample_name": ""},
            "literature_context": {
                "query_text": "CaCO3 thermogravimetric analysis decomposition",
                "query_display_title": "CaCO3 decomposition",
                "query_display_mode": "TGA / decomposition profile",
                "query_display_terms": ["decomposition", "mass loss", "residue"],
                "real_literature_available": False,
                "provider_query_status": "not_configured",
                "no_results_reason": "not_configured",
                "source_count": 0,
                "citation_count": 0,
            },
            "literature_claims": [],
            "literature_comparisons": [],
            "citations": [],
        },
        lang="en",
    )

    assert any("Focus: CaCO₃ decomposition" in item for item in captions)
    assert not any(".csv" in item for item in captions)


def test_render_literature_sections_shows_low_specificity_thermal_note_without_noise(monkeypatch):
    captions: list[str] = []
    markdowns: list[str] = []

    fake_st = SimpleNamespace(
        caption=lambda text: captions.append(str(text)),
        markdown=lambda text: markdowns.append(str(text)),
        warning=lambda text: captions.append(str(text)),
        container=lambda: nullcontext(),
    )
    monkeypatch.setattr(literature_compare_panel, "st", fake_st)

    literature_compare_panel.render_literature_sections(
        {
            "analysis_type": "TGA",
            "summary": {"sample_name": ""},
            "literature_context": {
                "query_text": "calcium carbonate thermogravimetric analysis decarbonation",
                "query_display_title": "CaCO3 decomposition",
                "query_display_mode": "TGA / decomposition profile",
                "query_display_terms": ["decomposition", "mass loss", "residue"],
                "real_literature_available": True,
                "metadata_only_evidence": True,
                "low_specificity_retrieval": True,
                "source_count": 4,
                "citation_count": 1,
            },
            "literature_claims": [{"claim_id": "C1", "claim_text": "The TGA result indicates a decomposition profile."}],
            "literature_comparisons": [
                {
                    "claim_id": "C1",
                    "claim_text": "The TGA result indicates a decomposition profile.",
                    "paper_title": "Carbonation in low-clinker cement systems",
                    "provider_id": "openalex_like_provider",
                    "access_class": "metadata_only",
                    "support_label": "related_but_inconclusive",
                    "confidence": "low",
                    "rationale": "Weak neighboring materials paper.",
                    "citation_ids": ["ref1"],
                }
            ],
            "citations": [{"citation_id": "ref1", "title": "Carbonation in low-clinker cement systems", "access_class": "metadata_only"}],
        },
        lang="en",
    )

    assert any("low-specificity and metadata/abstract-heavy" in item for item in captions)
    assert sum(1 for item in markdowns if item == "**Literature Comparison**") == 1


def test_render_literature_sections_shows_abstract_backed_evidence_basis_note(monkeypatch):
    captions: list[str] = []
    markdowns: list[str] = []

    fake_st = SimpleNamespace(
        caption=lambda text: captions.append(str(text)),
        markdown=lambda text: markdowns.append(str(text)),
        warning=lambda text: captions.append(str(text)),
        container=lambda: nullcontext(),
    )
    monkeypatch.setattr(literature_compare_panel, "st", fake_st)

    literature_compare_panel.render_literature_sections(
        {
            "analysis_type": "TGA",
            "summary": {"sample_name": ""},
            "literature_context": {
                "query_text": "calcium carbonate thermogravimetric analysis decarbonation",
                "query_display_title": "CaCO3 decomposition",
                "query_display_mode": "TGA / decomposition profile",
                "query_display_terms": ["decomposition", "mass loss", "residue"],
                "real_literature_available": True,
                "metadata_only_evidence": True,
                "evidence_specificity_summary": "abstract_backed",
                "source_count": 2,
                "citation_count": 1,
                "accessible_source_count": 1,
            },
            "literature_claims": [{"claim_id": "C1", "claim_text": "The TGA result indicates a decomposition profile."}],
            "literature_comparisons": [
                {
                    "claim_id": "C1",
                    "claim_text": "The TGA result indicates a decomposition profile.",
                    "paper_title": "Calcite thermal decomposition by thermogravimetric analysis",
                    "provider_id": "openalex_like_provider",
                    "access_class": "abstract_only",
                    "support_label": "partially_supports",
                    "confidence": "moderate",
                    "rationale": "Abstract-backed direct decomposition reference.",
                    "citation_ids": ["ref1"],
                }
            ],
            "citations": [{"citation_id": "ref1", "title": "Calcite thermal decomposition by thermogravimetric analysis", "access_class": "abstract_only"}],
        },
        lang="en",
    )

    assert any("accessible abstract-level evidence" in item for item in captions)


def test_build_literature_sections_places_abstract_backed_supportive_thermal_citation_in_relevant_references():
    sections = literature_compare_panel.build_literature_sections(
        {
            "analysis_type": "TGA",
            "summary": {"sample_name": ""},
            "literature_context": {
                "analysis_type": "TGA",
                "query_text": "calcium carbonate thermogravimetric analysis decarbonation",
                "query_display_title": "CaCO3 decomposition",
                "real_literature_available": True,
                "metadata_only_evidence": False,
                "evidence_specificity_summary": "mixed_metadata_and_abstract",
            },
            "literature_claims": [{"claim_id": "C1", "claim_text": "The TGA result indicates a decomposition profile."}],
            "literature_comparisons": [
                {
                    "claim_id": "C1",
                    "paper_title": "Calcite thermal decomposition by thermogravimetric analysis",
                    "access_class": "abstract_only",
                    "validation_posture": "contextual_only",
                    "support_label": "related_but_inconclusive",
                    "confidence": "moderate",
                    "rationale": "Abstract-backed direct decomposition reference.",
                    "citation_ids": ["ref7"],
                }
            ],
            "citations": [{"citation_id": "ref7", "title": "Calcite thermal decomposition by thermogravimetric analysis", "access_class": "abstract_only"}],
        }
    )

    assert [item["citation_id"] for item in sections["supporting_references"]] == ["ref7"]
    assert sections["alternative_references"] == []


def test_render_literature_sections_uses_persisted_mixed_thermal_record_for_relevant_references(monkeypatch):
    captions: list[str] = []
    markdowns: list[str] = []

    fake_st = SimpleNamespace(
        caption=lambda text: captions.append(str(text)),
        markdown=lambda text: markdowns.append(str(text)),
        warning=lambda text: captions.append(str(text)),
        container=lambda: nullcontext(),
    )
    monkeypatch.setattr(literature_compare_panel, "st", fake_st)

    literature_compare_panel.render_literature_sections(
        {
            "analysis_type": "TGA",
            "summary": {"sample_name": ""},
            "literature_context": {
                "analysis_type": "TGA",
                "query_text": "calcium carbonate thermogravimetric analysis decarbonation",
                "query_display_title": "CaCO3 decomposition",
                "real_literature_available": True,
                "metadata_only_evidence": False,
                "evidence_specificity_summary": "mixed_metadata_and_abstract",
            },
            "literature_claims": [{"claim_id": "C1", "claim_text": "The TGA result indicates a decomposition profile."}],
            "literature_comparisons": [
                {
                    "claim_id": "C1",
                    "paper_title": "Calcite thermal decomposition by thermogravimetric analysis",
                    "access_class": "abstract_only",
                    "validation_posture": "contextual_only",
                    "support_label": "partially_supports",
                    "confidence": "moderate",
                    "rationale": "Abstract-backed direct decomposition reference.",
                    "citation_ids": ["ref7"],
                }
            ],
            "citations": [{"citation_id": "ref7", "title": "Calcite thermal decomposition by thermogravimetric analysis", "access_class": "abstract_only"}],
        },
        lang="en",
    )

    assert any(item == "**Relevant References**" for item in markdowns)
    assert any("Calcite thermal decomposition by thermogravimetric analysis" in item for item in markdowns)
    assert not any("No supporting accessible references were retained" in item for item in captions)


def test_render_literature_sections_formats_chemical_formulas_in_user_facing_text(monkeypatch):
    captions: list[str] = []
    markdowns: list[str] = []

    fake_st = SimpleNamespace(
        caption=lambda text: captions.append(str(text)),
        markdown=lambda text: markdowns.append(str(text)),
        warning=lambda text: captions.append(str(text)),
        container=lambda: nullcontext(),
    )
    monkeypatch.setattr(literature_compare_panel, "st", fake_st)

    literature_compare_panel.render_literature_sections(
        {
            "analysis_type": "TGA",
            "summary": {"sample_name": "CaCO3 decomposition"},
            "literature_context": {
                "analysis_type": "TGA",
                "query_text": "calcium carbonate thermogravimetric analysis decarbonation",
                "query_display_title": "CaCO3 decomposition",
                "query_rationale": "CaCO3 decomposition with CO<sub>2</sub> release from Ca(OH)2–CaCO3–CaO context.",
                "query_display_mode": "TGA / decomposition profile",
                "real_literature_available": True,
                "metadata_only_evidence": False,
                "evidence_specificity_summary": "abstract_backed",
            },
            "literature_claims": [{"claim_id": "C1", "claim_text": "CaCO3 decomposition remains qualitative."}],
            "literature_comparisons": [
                {
                    "claim_id": "C1",
                    "paper_title": "CaCO3 decomposition and CO2 capture",
                    "access_class": "abstract_only",
                    "validation_posture": "contextual_only",
                    "support_label": "partially_supports",
                    "confidence": "moderate",
                    "rationale": "CaCO3 decomposition discusses CO<sub>2</sub> release from Ca(OH)2–CaCO3–CaO systems.",
                    "citation_ids": ["ref7"],
                }
            ],
            "citations": [
                {
                    "citation_id": "ref7",
                    "title": "CaCO3 decomposition and CO2 capture",
                    "journal": "Journal of CaCO3 Studies",
                    "doi": "10.1000/calcite-direct",
                    "access_class": "abstract_only",
                }
            ],
        },
        lang="en",
    )

    assert any("CaCO₃ decomposition" in item for item in captions + markdowns)
    assert any("CO₂" in item for item in captions + markdowns)
    assert any("Ca(OH)₂–CaCO₃–CaO" in item for item in captions + markdowns)
    assert any("DOI: [10.1000/calcite-direct](https://doi.org/10.1000/calcite-direct)" in item for item in markdowns)


def test_build_literature_sections_keeps_weak_metadata_only_neighbor_in_alternative_references():
    sections = literature_compare_panel.build_literature_sections(
        {
            "analysis_type": "TGA",
            "summary": {"sample_name": ""},
            "literature_context": {
                "analysis_type": "TGA",
                "query_text": "calcium carbonate thermogravimetric analysis decarbonation",
                "query_display_title": "CaCO3 decomposition",
                "real_literature_available": True,
                "metadata_only_evidence": True,
                "evidence_specificity_summary": "metadata_only",
            },
            "literature_claims": [{"claim_id": "C1", "claim_text": "The TGA result indicates a decomposition profile."}],
            "literature_comparisons": [
                {
                    "claim_id": "C1",
                    "paper_title": "Carbonation in low-clinker cement systems",
                    "access_class": "metadata_only",
                    "validation_posture": "non_validating",
                    "support_label": "related_but_inconclusive",
                    "confidence": "low",
                    "rationale": "Weak neighboring materials paper.",
                    "citation_ids": ["ref6"],
                }
            ],
            "citations": [{"citation_id": "ref6", "title": "Carbonation in low-clinker cement systems", "access_class": "metadata_only"}],
        }
    )

    assert sections["supporting_references"] == []
    assert [item["citation_id"] for item in sections["alternative_references"]] == ["ref6"]


def test_render_literature_sections_keeps_turkish_zero_hit_copy_fully_turkish(monkeypatch):
    captions: list[str] = []
    markdowns: list[str] = []

    fake_st = SimpleNamespace(
        caption=lambda text: captions.append(str(text)),
        markdown=lambda text: markdowns.append(str(text)),
        warning=lambda text: captions.append(str(text)),
        container=lambda: nullcontext(),
    )
    monkeypatch.setattr(literature_compare_panel, "st", fake_st)

    literature_compare_panel.render_literature_sections(
        {
            "analysis_type": "XRD",
            "summary": {
                "match_status": "no_match",
                "confidence_band": "no_match",
                "top_candidate_name": "cod_1000026",
                "top_candidate_display_name_unicode": "MgB₂",
            },
            "literature_context": {
                "query_text": "\"MgB₂\" XRD powder diffraction phase identification crystal structure MgB2",
                "query_display_title": "MgB₂",
                "query_display_mode": "XRD / faz tanımlama",
                "query_display_terms": ["powder diffraction", "crystal structure", "phase identification"],
                "candidate_name": "MgB2",
                "candidate_display_name": "MgB₂",
                "candidate_id": "cod_1000026",
                "match_status_snapshot": "no_match",
                "confidence_band_snapshot": "no_match",
                "real_literature_available": False,
                "fixture_fallback_used": False,
                "fixture_fallback_allowed": False,
                "provider_query_status": "no_results",
                "no_results_reason": "no_real_results",
                "source_count": 0,
                "citation_count": 0,
            },
            "literature_claims": [],
            "literature_comparisons": [],
            "citations": [],
        },
        lang="tr",
    )

    assert any("Gerçek literatür araması tamamlandı" in item for item in captions)
    assert any("Bu aday faz için gösterilebilir gerçek yayın bulunamadı" in item for item in captions)
    assert any("yalnızca bu sorguda uygun bibliyografik sonuç bulunamadı" in item for item in captions)
    assert any("Kabul edilen XRD sonucu no_match olarak kalır" in item for item in captions)
    assert any("Aday faz: MgB₂" in item for item in captions)
    assert not any("Aday faz: cod_1000026" in item for item in captions)
    assert not any("Real literature search completed" in item for item in captions)
    assert not any("Search Interpretation" in item for item in markdowns)


def test_render_literature_sections_shows_fixture_banner_and_demo_citation_guardrail(monkeypatch):
    captions: list[str] = []
    markdowns: list[str] = []
    warnings: list[str] = []

    fake_st = SimpleNamespace(
        caption=lambda text: captions.append(str(text)),
        markdown=lambda text: markdowns.append(str(text)),
        warning=lambda text: warnings.append(str(text)),
        container=lambda: nullcontext(),
    )
    monkeypatch.setattr(literature_compare_panel, "st", fake_st)

    literature_compare_panel.render_literature_sections(
        {
            "summary": {"match_status": "matched", "confidence_band": "medium"},
            "literature_context": {"provider_scope": ["fixture_provider"], "restricted_content_used": False},
            "literature_claims": [{"claim_id": "C1", "claim_text": "Phase Alpha remains a qualitative follow-up candidate."}],
            "literature_comparisons": [
                {
                    "claim_id": "C1",
                    "support_label": "supports",
                    "confidence": "moderate",
                    "rationale": "Fixture literature appears directionally aligned but is not real evidence.",
                    "citation_ids": ["ref1"],
                }
            ],
            "citations": [
                {
                    "citation_id": "ref1",
                    "title": "Fixture paper",
                    "year": 2025,
                    "journal": "Fixture Journal",
                    "doi": "10.1000/fixture",
                    "access_class": "open_access_full_text",
                    "provenance": {
                        "provider_id": "fixture_provider",
                        "result_source": "fixture_search",
                        "provider_scope": ["fixture_provider"],
                    },
                }
            ],
        },
        lang="en",
    )

    assert warnings == ["Demo literature fixture output — not a real bibliographic source"]
    assert any("Demo DOI/URL display is not a production reference" in item for item in captions)
    assert any("Demo fixture only" in item for item in captions)


def test_no_match_weak_literature_does_not_render_misleading_support_label(monkeypatch):
    captions: list[str] = []
    markdowns: list[str] = []
    warnings: list[str] = []

    fake_st = SimpleNamespace(
        caption=lambda text: captions.append(str(text)),
        markdown=lambda text: markdowns.append(str(text)),
        warning=lambda text: warnings.append(str(text)),
        container=lambda: nullcontext(),
    )
    monkeypatch.setattr(literature_compare_panel, "st", fake_st)

    literature_compare_panel.render_literature_sections(
        {
            "summary": {"match_status": "no_match", "confidence_band": "no_match"},
            "literature_context": {"metadata_only_evidence": True, "restricted_content_used": False},
            "literature_claims": [{"claim_id": "C1", "claim_text": "The XRD output remained a cautionary no_match result."}],
            "literature_comparisons": [
                {
                    "claim_id": "C1",
                    "support_label": "supports",
                    "confidence": "low",
                    "rationale": "Metadata overlap exists, but it does not validate the analytical outcome.",
                    "citation_ids": ["ref1"],
                }
            ],
            "citations": [
                {
                    "citation_id": "ref1",
                    "title": "Metadata-only paper",
                    "access_class": "metadata_only",
                    "provenance": {"provider_id": "metadata_api_provider", "result_source": "open_metadata_api"},
                }
            ],
        },
        lang="en",
    )

    assert warnings == []
    assert any("Insufficient literature evidence" in item for item in captions)
    assert not any("Cautiously consistent" in item for item in captions)


def test_render_literature_sections_turkish_path_stays_turkish(monkeypatch):
    captions: list[str] = []
    markdowns: list[str] = []
    warnings: list[str] = []

    fake_st = SimpleNamespace(
        caption=lambda text: captions.append(str(text)),
        markdown=lambda text: markdowns.append(str(text)),
        warning=lambda text: warnings.append(str(text)),
        container=lambda: nullcontext(),
    )
    monkeypatch.setattr(literature_compare_panel, "st", fake_st)

    literature_compare_panel.render_literature_sections(
        {
            "summary": {"match_status": "matched", "confidence_band": "medium"},
            "literature_context": {"provider_scope": ["fixture_provider"], "restricted_content_used": False},
            "literature_claims": [{"claim_id": "C1", "claim_text": "Faz Alfa yalnızca nitel bir takip adayıdır."}],
            "literature_comparisons": [
                {
                    "claim_id": "C1",
                    "support_label": "supports",
                    "confidence": "moderate",
                    "rationale": "Bu çıktı yalnızca demo amaçlıdır.",
                    "citation_ids": ["ref1"],
                }
            ],
            "citations": [
                {
                    "citation_id": "ref1",
                    "title": "Demo makalesi",
                    "access_class": "metadata_only",
                    "provenance": {
                        "provider_id": "fixture_provider",
                        "result_source": "fixture_search",
                        "provider_scope": ["fixture_provider"],
                    },
                }
            ],
        },
        lang="tr",
    )

    assert warnings == ["Demo literature fixture output — gerçek bibliyografik kaynak değildir"]
    assert any("Literatür Karşılaştırması" in item for item in markdowns)
    assert any("İddia Kimliği" in item for item in captions)
    assert not any("Literature Comparison" in item for item in markdowns)


def test_call_literature_compare_maps_backend_response_into_updated_record(monkeypatch):
    request_log: list[tuple[str, str]] = []

    def _fake_request(method: str, url: str, *, headers=None, json=None, timeout=None):
        del headers, json, timeout
        request_log.append((method, url))
        if url.endswith("/project/load"):
            return _FakeResponse(200, {"project_id": "proj_123"})
        if url.endswith("/workspace/proj_123/results/xrd_demo/literature/compare"):
            return _FakeResponse(
                200,
                {
                    "project_id": "proj_123",
                    "result_id": "xrd_demo",
                    "literature_context": {"comparison_run_id": "litcmp_demo_001"},
                    "detail": {
                        "result": {"id": "xrd_demo", "dataset_key": "xrd_demo"},
                        "summary": {"match_status": "matched", "top_candidate_name": "Phase Alpha"},
                        "processing": {"workflow": "xrd.general"},
                        "provenance": {"saved_at_utc": "2026-03-19T00:00:00Z"},
                        "validation": {"status": "pass"},
                        "review": {"status": "screening"},
                        "literature_context": {"comparison_run_id": "litcmp_demo_001"},
                        "literature_claims": [{"claim_id": "C1"}],
                        "literature_comparisons": [{"claim_id": "C1", "support_label": "supports"}],
                        "citations": [{"citation_id": "ref1", "title": "Supporting paper"}],
                    },
                },
            )
        raise AssertionError(f"Unexpected backend request: {method} {url}")

    monkeypatch.setattr(literature_compare_panel, "save_project_archive", lambda state: b"archive-bytes")
    monkeypatch.setattr(literature_compare_panel.httpx, "request", _fake_request)

    outcome = literature_compare_panel.call_literature_compare(
        session_state={"results": {"xrd_demo": {"id": "xrd_demo"}}},
        result_id="xrd_demo",
        current_record={"id": "xrd_demo", "summary": {"match_status": "matched"}},
    )

    assert [entry[1] for entry in request_log] == [
        "http://127.0.0.1:8000/project/load",
        "http://127.0.0.1:8000/workspace/proj_123/results/xrd_demo/literature/compare",
    ]
    assert outcome["project_id"] == "proj_123"
    assert outcome["updated_record"]["summary"]["top_candidate_name"] == "Phase Alpha"
    assert outcome["updated_record"]["literature_context"]["comparison_run_id"] == "litcmp_demo_001"
    assert outcome["updated_record"]["citations"][0]["citation_id"] == "ref1"


def test_render_literature_compare_panel_updates_session_state_on_success(monkeypatch):
    session_state = {"results": {"xrd_demo": {"id": "xrd_demo", "summary": {"match_status": "matched"}}}}
    markdowns: list[str] = []
    captions: list[str] = []

    fake_st = SimpleNamespace(
        session_state=session_state,
        button=lambda *args, **kwargs: True,
        spinner=lambda *args, **kwargs: nullcontext(),
        success=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        caption=lambda text: captions.append(str(text)),
        markdown=lambda text: markdowns.append(str(text)),
        container=lambda: nullcontext(),
    )
    monkeypatch.setattr(literature_compare_panel, "st", fake_st)
    monkeypatch.setattr(
        literature_compare_panel,
        "call_literature_compare",
        lambda **kwargs: {
            "project_id": "proj_123",
            "response": {"result_id": "xrd_demo"},
            "detail": {"result": {"id": "xrd_demo"}},
            "updated_record": {
                "id": "xrd_demo",
                "summary": {"match_status": "matched"},
                "literature_context": {"comparison_run_id": "litcmp_demo_001"},
                "literature_claims": [{"claim_id": "C1"}],
                "literature_comparisons": [{"claim_id": "C1", "support_label": "supports", "confidence": "moderate", "rationale": "Cautionary rationale", "citation_ids": ["ref1"]}],
                "citations": [{"citation_id": "ref1", "title": "Supporting paper", "access_class": "metadata_only"}],
            },
        },
    )

    record, action = literature_compare_panel.render_literature_compare_panel(
        record={"id": "xrd_demo", "summary": {"match_status": "matched"}},
        result_id="xrd_demo",
        lang="en",
        key_prefix="xrd_literature_compare_demo",
    )

    assert action["status"] == "success"
    assert record["literature_context"]["comparison_run_id"] == "litcmp_demo_001"
    assert session_state["results"]["xrd_demo"]["literature_context"]["comparison_run_id"] == "litcmp_demo_001"


def test_xrd_page_results_summary_uses_literature_compare_panel():
    source = (_REPO_ROOT / "ui" / "xrd_page.py").read_text(encoding="utf-8")

    assert "render_literature_compare_panel(" in source


def test_thermal_pages_results_summary_use_literature_compare_panel():
    for path in (
        _REPO_ROOT / "ui" / "dsc_page.py",
        _REPO_ROOT / "ui" / "dta_page.py",
        _REPO_ROOT / "ui" / "tga_page.py",
    ):
        source = Path(path).read_text(encoding="utf-8")
        assert "render_literature_compare_panel(" in source


def test_ftir_results_summary_uses_literature_compare_panel():
    source = (_REPO_ROOT / "ui" / "spectral_page.py").read_text(encoding="utf-8")

    assert "_render_literature_compare_if_supported(" in source
    assert "_LITERATURE_COMPARE_ENABLED_TYPES = {\"FTIR\"}" in source
    assert "render_literature_compare_panel(" in source
