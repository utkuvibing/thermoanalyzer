"""Deterministic thermal literature query builders for DSC, DTA, and TGA."""

from __future__ import annotations

import re
from pathlib import PurePath
from typing import Any, Mapping


FILENAME_EXTENSIONS = (".csv", ".txt", ".xlsx", ".xls", ".tsv", ".dat")
TECHNICAL_EDGE_TOKENS = {
    "analysis",
    "analiz",
    "dataset",
    "export",
    "file",
    "record",
    "result",
    "results",
    "run",
    "sample",
    "tga",
    "dsc",
    "dta",
    "tg",
}
CHEMICAL_ALIASES = {
    "caco3": ["calcium carbonate", "calcite"],
}


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _clean_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_int(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _round_temperature(value: Any) -> int | None:
    numeric = _clean_float(value)
    if numeric is None:
        return None
    return int(round(numeric))


def _tokenize(value: str) -> list[str]:
    cleaned = "".join(ch if ch.isalnum() else " " for ch in str(value or "").lower())
    return [token for token in cleaned.split() if token]


def _rows(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(item) for item in (record.get("rows") or []) if isinstance(item, Mapping)]


def _summary(record: Mapping[str, Any]) -> dict[str, Any]:
    return dict(record.get("summary") or {})


def _metadata(record: Mapping[str, Any]) -> dict[str, Any]:
    return dict(record.get("metadata") or {})


def _workflow_label(record: Mapping[str, Any]) -> str:
    processing = dict(record.get("processing") or {})
    return _clean_text(processing.get("workflow_template_label") or processing.get("workflow_template"))


def _strip_filename_artifacts(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    text = PurePath(text).name
    lowered = text.lower()
    for extension in FILENAME_EXTENSIONS:
        if lowered.endswith(extension):
            text = text[: -len(extension)]
            break
    text = text.replace("_", " ").replace("\\", " ").replace("/", " ")
    text = re.sub(r"\s+", " ", text).strip(" -_.")
    tokens = [token for token in re.split(r"\s+", text) if token]
    while tokens and tokens[0].lower() in TECHNICAL_EDGE_TOKENS:
        tokens.pop(0)
    while tokens and tokens[-1].lower() in TECHNICAL_EDGE_TOKENS:
        tokens.pop()
    text = " ".join(tokens)
    text = re.sub(r"\s+", " ", text).strip(" -_.")
    return text


def _looks_like_filename(value: Any) -> bool:
    text = _clean_text(value)
    if not text:
        return False
    lowered = text.lower()
    if any(marker in text for marker in ("\\", "/")):
        return True
    if any(lowered.endswith(extension) for extension in FILENAME_EXTENSIONS):
        return True
    if re.search(r"\b(?:tga|dsc|dta|tg)[\s_-]", lowered):
        return True
    if lowered.startswith(("result_", "results_", "analysis_", "dataset_", "sample_")):
        return True
    if "__" in text or text.count("_") >= 1:
        return True
    return False


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


def _is_scientific_subject(value: str) -> bool:
    cleaned = _strip_filename_artifacts(value)
    if not cleaned:
        return False
    lowered = cleaned.lower()
    if lowered in {"tga", "dsc", "dta", "thermal", "decomposition", "thermal event"}:
        return False
    tokens = _tokenize(cleaned)
    if not tokens:
        return False
    return any(any(ch.isalpha() for ch in token) for token in tokens) or any(any(ch.isdigit() for ch in token) for token in tokens)


def _normalized_subject_candidates(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    summary = _summary(record)
    metadata = _metadata(record)
    raw_candidates = [
        ("summary.sample_name", summary.get("sample_name")),
        ("metadata.sample_name", metadata.get("sample_name")),
        ("metadata.display_name", metadata.get("display_name")),
        ("metadata.file_name", metadata.get("file_name")),
    ]
    ranked: list[dict[str, Any]] = []
    for index, (source, raw_value) in enumerate(raw_candidates):
        raw = _clean_text(raw_value)
        cleaned = _strip_filename_artifacts(raw)
        if not cleaned:
            continue
        filename_like = _looks_like_filename(raw)
        score = 100 - index * 10
        if source.endswith("sample_name"):
            score += 20
        if filename_like:
            score -= 35
        if not _is_scientific_subject(cleaned):
            score -= 20
        ranked.append(
            {
                "source": source,
                "raw": raw,
                "cleaned": cleaned,
                "filename_like": filename_like,
                "quote_safe": not filename_like and _is_scientific_subject(cleaned),
                "score": score,
            }
        )
    ranked.sort(key=lambda item: (-item["score"], item["source"]))
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in ranked:
        key = item["cleaned"].casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _best_subject(record: Mapping[str, Any]) -> dict[str, Any]:
    candidates = _normalized_subject_candidates(record)
    if candidates:
        return candidates[0]
    return {
        "source": "",
        "raw": "",
        "cleaned": "",
        "filename_like": False,
        "quote_safe": False,
        "score": 0,
    }


def _quoted_subject(subject: Mapping[str, Any]) -> str:
    cleaned = _clean_text(subject.get("cleaned"))
    if cleaned and subject.get("quote_safe"):
        return f"\"{cleaned}\""
    return cleaned


def _subject_expansions(subject: Mapping[str, Any]) -> list[str]:
    subject_tokens = _tokenize(_clean_text(subject.get("cleaned")))
    expansions: list[str] = []
    for token in subject_tokens:
        expansions.extend(CHEMICAL_ALIASES.get(token.lower(), []))
    return _dedupe(expansions)


def _tga_process_expansions(*, subject: Mapping[str, Any], midpoint: int | None, total_mass_loss: float | None) -> list[str]:
    tokens = {token.lower() for token in _tokenize(_clean_text(subject.get("cleaned")))}
    expansions: list[str] = []
    if "caco3" in tokens or any(alias in _subject_expansions(subject) for alias in ("calcium carbonate", "calcite")):
        expansions.extend(["decarbonation", "calcination", "CaO", "CO2 release"])
    if midpoint is not None and 680 <= midpoint <= 820 and total_mass_loss is not None and 40.0 <= total_mass_loss <= 48.0:
        expansions.extend(["decarbonation", "calcination", "CO2 release"])
    return _dedupe(expansions)


def _generic_subject_query(subject: Mapping[str, Any], *, analysis_type: str, fallback_label: str) -> str:
    cleaned = _clean_text(subject.get("cleaned"))
    if cleaned:
        return " ".join(part for part in [cleaned, analysis_type, fallback_label] if part)
    return f"{analysis_type} {fallback_label}"


def _build_payload(
    *,
    analysis_type: str,
    query_text: str,
    fallback_queries: list[str],
    query_rationale: str,
    query_display_title: str,
    query_display_mode: str,
    query_display_terms: list[str],
    evidence_snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "analysis_type": analysis_type,
        "query_text": _clean_text(query_text),
        "fallback_queries": _dedupe([_clean_text(item) for item in fallback_queries if _clean_text(item)]),
        "query_rationale": _clean_text(query_rationale),
        "query_display_title": _clean_text(query_display_title),
        "query_display_mode": _clean_text(query_display_mode),
        "query_display_terms": _dedupe([_clean_text(item) for item in query_display_terms if _clean_text(item)]),
        "evidence_snapshot": dict(evidence_snapshot or {}),
    }


def build_dsc_literature_query(record: Mapping[str, Any]) -> dict[str, Any]:
    summary = _summary(record)
    rows = _rows(record)
    subject = _best_subject(record)
    subject_label = _clean_text(subject.get("cleaned"))
    quoted_subject = _quoted_subject(subject)
    tg_midpoint = _round_temperature(summary.get("tg_midpoint"))
    first_peak = rows[0] if rows else {}
    peak_type = _clean_text(first_peak.get("peak_type")).lower()
    peak_temp = _round_temperature(first_peak.get("peak_temperature"))
    peak_count = _clean_int(summary.get("peak_count")) or len(rows)
    glass_transition_count = _clean_int(summary.get("glass_transition_count")) or 0

    if tg_midpoint is not None:
        query_text = " ".join(
            part for part in [quoted_subject, "DSC glass transition thermal analysis", f"{tg_midpoint} C"] if part
        )
        fallback_queries = [
            _generic_subject_query(subject, analysis_type="DSC", fallback_label="glass transition"),
            "DSC glass transition calorimetry",
            _generic_subject_query(subject, analysis_type="thermal analysis", fallback_label="glass transition polymer"),
        ]
        display_title = subject_label or "DSC glass transition"
        rationale = f"The DSC literature search is centered on a glass-transition signal near {tg_midpoint} C."
        display_terms = ["glass transition", "calorimetry", "thermal event"]
    else:
        event_label = peak_type or "thermal event"
        query_text = " ".join(
            part
            for part in [quoted_subject, "DSC thermal event calorimetry", event_label, f"{peak_temp} C" if peak_temp is not None else ""]
            if part
        )
        fallback_queries = [
            _generic_subject_query(subject, analysis_type="DSC", fallback_label="thermal event"),
            "DSC endothermic exothermic event calorimetry",
            _generic_subject_query(subject, analysis_type="thermal analysis", fallback_label=event_label),
        ]
        display_title = subject_label or "DSC thermal event"
        rationale = f"The DSC literature search is centered on the leading {event_label} event" + (f" near {peak_temp} C." if peak_temp is not None else ".")
        display_terms = ["thermal event", "calorimetry", event_label]

    return _build_payload(
        analysis_type="DSC",
        query_text=query_text,
        fallback_queries=fallback_queries,
        query_rationale=rationale,
        query_display_title=display_title,
        query_display_mode="DSC / thermal interpretation",
        query_display_terms=display_terms,
        evidence_snapshot={
            "sample_name": subject_label,
            "raw_subject": _clean_text(subject.get("raw")),
            "filename_like_subject": bool(subject.get("filename_like")),
            "workflow_template": _workflow_label(record),
            "peak_count": peak_count,
            "glass_transition_count": glass_transition_count,
            "tg_midpoint": _clean_float(summary.get("tg_midpoint")),
            "peak_type": peak_type,
            "peak_temperature": _clean_float(first_peak.get("peak_temperature")),
        },
    )


def build_dta_literature_query(record: Mapping[str, Any]) -> dict[str, Any]:
    summary = _summary(record)
    rows = _rows(record)
    subject = _best_subject(record)
    subject_label = _clean_text(subject.get("cleaned"))
    quoted_subject = _quoted_subject(subject)
    first_peak = rows[0] if rows else {}
    direction = _clean_text(first_peak.get("peak_type") or first_peak.get("direction")).lower() or "thermal event"
    peak_temp = _round_temperature(first_peak.get("peak_temperature"))
    processing = dict(record.get("processing") or {})
    method_context = dict(processing.get("method_context") or {})

    query_text = " ".join(
        part for part in [quoted_subject, "DTA differential thermal analysis", direction, f"{peak_temp} C" if peak_temp is not None else ""] if part
    )
    fallback_queries = [
        _generic_subject_query(subject, analysis_type="DTA", fallback_label="thermal event"),
        "DTA endothermic exothermic event differential thermal analysis",
        _generic_subject_query(subject, analysis_type="thermal analysis", fallback_label=direction),
    ]
    return _build_payload(
        analysis_type="DTA",
        query_text=query_text,
        fallback_queries=fallback_queries,
        query_rationale=f"The DTA literature search is centered on the leading {direction} event" + (f" near {peak_temp} C." if peak_temp is not None else "."),
        query_display_title=subject_label or "DTA thermal event",
        query_display_mode="DTA / thermal events",
        query_display_terms=["thermal event", "differential thermal analysis", direction],
        evidence_snapshot={
            "sample_name": subject_label,
            "raw_subject": _clean_text(subject.get("raw")),
            "filename_like_subject": bool(subject.get("filename_like")),
            "workflow_template": _workflow_label(record),
            "peak_count": _clean_int(summary.get("peak_count")) or len(rows),
            "event_direction": direction,
            "peak_temperature": _clean_float(first_peak.get("peak_temperature")),
            "sign_convention": _clean_text(method_context.get("sign_convention_label") or method_context.get("sign_convention")),
        },
    )


def build_tga_literature_query(record: Mapping[str, Any]) -> dict[str, Any]:
    summary = _summary(record)
    rows = _rows(record)
    subject = _best_subject(record)
    subject_label = _clean_text(subject.get("cleaned"))
    quoted_subject = _quoted_subject(subject)
    first_step = rows[0] if rows else {}
    midpoint = _round_temperature(first_step.get("midpoint_temperature"))
    total_mass_loss = _clean_float(summary.get("total_mass_loss_percent"))
    residue = _clean_float(summary.get("residue_percent"))
    subject_aliases = _subject_expansions(subject)
    process_terms = _tga_process_expansions(subject=subject, midpoint=midpoint, total_mass_loss=total_mass_loss)

    query_text = " ".join(
        part
        for part in [quoted_subject, "TGA decomposition mass loss residue", f"{midpoint} C" if midpoint is not None else ""]
        if part
    )
    fallback_queries = [
        _generic_subject_query(subject, analysis_type="thermogravimetric analysis", fallback_label="decomposition"),
        _generic_subject_query(subject, analysis_type="TGA", fallback_label="mass loss residue"),
        "thermogravimetric analysis decomposition mass loss residue",
    ]
    if subject_label and not subject.get("quote_safe"):
        fallback_queries.insert(1, f"{subject_label} decomposition mass loss residue")
    if subject_aliases:
        fallback_queries.append(" ".join(subject_aliases + ["thermogravimetric analysis", "decomposition"]))
    if process_terms:
        process_query_parts = subject_aliases[:1] or ([subject_label] if subject_label else [])
        fallback_queries.append(" ".join(process_query_parts + process_terms + ["thermogravimetric analysis"]))

    rationale = "The TGA literature search is centered on the decomposition profile"
    if midpoint is not None:
        rationale += f" with a leading step near {midpoint} C"
    if total_mass_loss is not None:
        rationale += f" and total mass loss around {total_mass_loss:.1f}%"
    rationale += "."
    return _build_payload(
        analysis_type="TGA",
        query_text=query_text,
        fallback_queries=fallback_queries,
        query_rationale=rationale,
        query_display_title=subject_label or (subject_aliases[0] if subject_aliases else "TGA decomposition profile"),
        query_display_mode="TGA / decomposition profile",
        query_display_terms=["decomposition", "mass loss", "residue", *subject_aliases[:2], *process_terms[:2]],
        evidence_snapshot={
            "sample_name": subject_label,
            "raw_subject": _clean_text(subject.get("raw")),
            "filename_like_subject": bool(subject.get("filename_like")),
            "subject_aliases": subject_aliases,
            "workflow_template": _workflow_label(record),
            "step_count": _clean_int(summary.get("step_count")) or len(rows),
            "total_mass_loss_percent": total_mass_loss,
            "residue_percent": residue,
            "midpoint_temperature": _clean_float(first_step.get("midpoint_temperature")),
            "mass_loss_percent": _clean_float(first_step.get("mass_loss_percent")),
            "process_terms": process_terms,
        },
    )


def build_thermal_query_presentation(query_payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "display_title": _clean_text(query_payload.get("query_display_title")) or "Thermal literature search",
        "display_mode": _clean_text(query_payload.get("query_display_mode")) or "Thermal / interpretation",
        "display_terms": [_clean_text(item) for item in (query_payload.get("query_display_terms") or []) if _clean_text(item)],
        "raw_query": _clean_text(query_payload.get("query_text")),
    }
