from __future__ import annotations

from pathlib import Path
from contextlib import nullcontext
from types import SimpleNamespace

from ui.components import literature_compare_panel


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
                    "comparison_note": "This paper discusses XRD characterization of Phase Alpha. The current result remains a no_match screening outcome and the paper does not validate a phase call for the present sample.",
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
    assert any("do not validate a phase call" in item for item in captions)


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

    assert any("literatürde benzer XRD tartışmaları bulundu" in item for item in markdowns)
    assert not any("Secondary metadata: claim" in item for item in captions)


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
    source = Path("C:/MaterialScope/ui/xrd_page.py").read_text(encoding="utf-8")

    assert "render_literature_compare_panel(" in source
