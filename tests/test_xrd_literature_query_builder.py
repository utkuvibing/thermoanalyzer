from __future__ import annotations

from core.xrd_literature_query_builder import build_xrd_literature_query


def _record(summary: dict) -> dict:
    return {
        "id": "xrd_demo",
        "analysis_type": "XRD",
        "summary": summary,
        "rows": [
            {
                "rank": 1,
                "candidate_name": "Phase Alpha",
                "normalized_score": 0.77,
                "evidence": {"shared_peak_count": 5, "coverage_ratio": 0.61},
            }
        ],
    }


def test_query_builder_prefers_unicode_display_name():
    payload = build_xrd_literature_query(
        _record(
            {
                "top_candidate_display_name_unicode": "MgB₂",
                "top_candidate_name": "MgB2",
                "top_candidate_formula": "MgB2",
                "top_candidate_id": "cod_123",
                "match_status": "matched",
                "confidence_band": "medium",
                "top_candidate_score": 0.81,
                "top_candidate_shared_peak_count": 6,
                "top_candidate_coverage_ratio": 0.72,
                "top_candidate_weighted_overlap_score": 0.76,
                "top_candidate_provider": "COD",
                "library_result_source": "xrd_cloud_search",
                "library_provider_scope": ["cod"],
            }
        )
    )

    assert "MgB₂" in payload["query_text"]
    assert payload["candidate_display_name"] == "MgB₂"
    assert payload["match_status_snapshot"] == "matched"
    assert payload["evidence_snapshot"]["top_candidate_score"] == 0.81


def test_query_builder_falls_back_to_formula_when_name_is_weak():
    payload = build_xrd_literature_query(
        _record(
            {
                "top_candidate_name": "phase",
                "top_candidate_formula": "CaCO3",
                "top_candidate_id": "cod_999",
                "match_status": "matched",
                "confidence_band": "low",
            }
        )
    )

    assert "CaCO3" in payload["query_text"]
    assert "XRD" in payload["query_text"]
    assert payload["candidate_formula"] == "CaCO3"


def test_query_builder_degrades_to_generic_xrd_terms_when_candidate_is_missing():
    payload = build_xrd_literature_query(_record({"match_status": "no_match", "confidence_band": "no_match"}))

    assert payload["query_text"] == "XRD phase identification diffraction pattern"
    assert payload["match_status_snapshot"] == "no_match"
    assert "no_match" in payload["query_rationale"]
