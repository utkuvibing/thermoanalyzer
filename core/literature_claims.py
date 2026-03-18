"""Deterministic claim extraction for literature comparison."""

from __future__ import annotations

from typing import Any, Mapping

from core.literature_models import normalize_literature_claims


STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "were",
    "was",
    "into",
    "under",
    "than",
    "then",
    "when",
    "where",
    "their",
    "there",
    "because",
    "should",
    "could",
    "remain",
    "results",
    "result",
    "analysis",
    "measured",
    "current",
    "using",
}


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for item in values:
        cleaned = _clean_text(item)
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        output.append(cleaned)
    return output


def _tokenize(value: str) -> list[str]:
    cleaned = "".join(ch if ch.isalnum() else " " for ch in str(value or "").lower())
    return [token for token in cleaned.split() if len(token) >= 3 and token not in STOPWORDS]


def _summary_snapshot(summary: Mapping[str, Any], *, limit: int = 8) -> dict[str, Any]:
    preferred_keys = [
        "match_status",
        "top_match_name",
        "top_candidate_name",
        "top_phase",
        "top_match_score",
        "top_candidate_score",
        "top_phase_score",
        "confidence_band",
        "candidate_count",
        "peak_count",
        "step_count",
        "total_mass_loss_percent",
        "residue_percent",
        "caution_code",
        "caution_message",
        "library_request_id",
        "library_result_source",
        "library_provider_scope",
    ]
    snapshot: dict[str, Any] = {}
    for key in preferred_keys:
        if summary.get(key) not in (None, "", [], {}):
            snapshot[key] = summary.get(key)
        if len(snapshot) >= limit:
            break
    return snapshot


def _claim_type_from_strength(value: str) -> str:
    token = _clean_text(value).lower()
    if token == "descriptive":
        return "observation"
    if token == "comparative":
        return "comparison"
    if token == "mechanistic":
        return "interpretation"
    return "interpretation"


def _claim_strength(
    scientific_claim: Mapping[str, Any],
    uncertainty: Mapping[str, Any],
    validation: Mapping[str, Any],
) -> str:
    strength = _clean_text(scientific_claim.get("strength")).lower()
    overall = _clean_text(uncertainty.get("overall_confidence")).lower()
    validation_status = _clean_text(validation.get("status")).lower()
    if validation_status == "warn" or overall == "low":
        return "low"
    if strength == "mechanistic" and overall in {"high", "moderate"}:
        return "moderate"
    if overall == "high":
        return "high"
    return "moderate"


def _suggested_query_terms(
    *,
    claim_text: str,
    analysis_type: str,
    summary: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> list[str]:
    terms: list[str] = [analysis_type.upper()]
    for key in ("top_match_name", "top_candidate_name", "top_phase", "sample_name"):
        raw = summary.get(key)
        if raw in (None, ""):
            raw = metadata.get(key)
        if raw not in (None, ""):
            terms.append(str(raw))
    tokens = _tokenize(claim_text)
    terms.extend(tokens[:6])
    return _dedupe(terms)[:8]


def _fallback_claim(record: Mapping[str, Any]) -> dict[str, Any]:
    analysis_type = _clean_text(record.get("analysis_type")).upper() or "UNKNOWN"
    summary = dict(record.get("summary") or {})
    validation = dict(record.get("validation") or {})
    metadata = dict(record.get("metadata") or {})

    if str(summary.get("match_status") or "").lower() == "no_match":
        claim_text = (
            f"The {analysis_type} result remained a cautionary no_match outcome, so any literature comparison "
            "should be treated as qualitative and non-definitive."
        )
        claim_type = "cautionary_interpretation"
    elif summary.get("top_candidate_name") or summary.get("top_match_name") or summary.get("top_phase"):
        candidate = summary.get("top_candidate_name") or summary.get("top_match_name") or summary.get("top_phase")
        claim_text = (
            f"The leading {analysis_type} interpretation is qualitatively consistent with {candidate} "
            "as a follow-up target rather than a confirmed identification."
        )
        claim_type = "interpretation"
    else:
        claim_text = f"The {analysis_type} record contains a qualitative interpretation derived from the current summary metrics."
        claim_type = "observation"

    uncertainty_notes = _dedupe([str(item) for item in (validation.get("warnings") or []) if str(item).strip()])[:4]
    return {
        "claim_id": "C1",
        "claim_text": claim_text,
        "claim_type": claim_type,
        "modality": analysis_type,
        "strength": "low" if validation.get("status") == "warn" else "moderate",
        "evidence_snapshot": _summary_snapshot(summary),
        "uncertainty_notes": uncertainty_notes,
        "suggested_query_terms": _suggested_query_terms(
            claim_text=claim_text,
            analysis_type=analysis_type,
            summary=summary,
            metadata=metadata,
        ),
    }


def extract_literature_claims(record: Mapping[str, Any], *, max_claims: int = 4) -> list[dict[str, Any]]:
    summary = dict(record.get("summary") or {})
    metadata = dict(record.get("metadata") or {})
    scientific_context = dict(record.get("scientific_context") or {})
    uncertainty = dict(scientific_context.get("uncertainty_assessment") or {})
    validation = dict(record.get("validation") or {})
    evidence_map = dict(scientific_context.get("evidence_map") or {})
    analysis_type = _clean_text(record.get("analysis_type")).upper() or "UNKNOWN"

    uncertainty_notes = _dedupe(
        [str(item) for item in (uncertainty.get("items") or []) if str(item).strip()]
        + [str(item) for item in (validation.get("warnings") or []) if str(item).strip()]
    )

    extracted: list[dict[str, Any]] = []
    for index, item in enumerate(scientific_context.get("scientific_claims") or [], start=1):
        if not isinstance(item, Mapping):
            continue
        claim_text = _clean_text(item.get("claim") or item.get("statement"))
        if not claim_text:
            continue
        claim_id = _clean_text(item.get("id")) or f"C{index}"
        evidence_snapshot = _summary_snapshot(summary)
        evidence_snapshot["scientific_evidence"] = [
            str(entry) for entry in (evidence_map.get(claim_id) or item.get("evidence") or []) if str(entry).strip()
        ]
        extracted.append(
            {
                "claim_id": claim_id,
                "claim_text": claim_text,
                "claim_type": _claim_type_from_strength(str(item.get("strength") or "")),
                "modality": analysis_type,
                "strength": _claim_strength(item, uncertainty, validation),
                "evidence_snapshot": evidence_snapshot,
                "uncertainty_notes": uncertainty_notes[:5],
                "suggested_query_terms": _suggested_query_terms(
                    claim_text=claim_text,
                    analysis_type=analysis_type,
                    summary=summary,
                    metadata=metadata,
                ),
            }
        )
        if len(extracted) >= max_claims:
            break

    if not extracted:
        extracted = [_fallback_claim(record)]

    return normalize_literature_claims(extracted)


def build_claim_queries(claim: Mapping[str, Any], *, max_queries: int = 3) -> list[str]:
    terms = [str(item) for item in (claim.get("suggested_query_terms") or []) if str(item).strip()]
    modality = _clean_text(claim.get("modality")).upper()
    claim_type = _clean_text(claim.get("claim_type")).replace("_", " ")
    query_seeds = [
        " ".join([modality, *terms[:4]]).strip(),
        " ".join([modality, claim_type, *terms[:5]]).strip(),
        " ".join(terms[:6]).strip(),
    ]
    return [query for query in _dedupe(query_seeds)[:max_queries] if query]
