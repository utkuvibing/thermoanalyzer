"""Shared helpers for XRD reference-dossier normalization and serialization."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from core.xrd_display import (
    format_scientific_formula_text,
    xrd_candidate_display_payload,
    xrd_candidate_display_variants,
)

XRD_REFERENCE_DOSSIER_LIMIT = 3
XRD_REFERENCE_PEAK_DISPLAY_LIMIT = 20
XRD_REFERENCE_PEAK_SELECTION_POLICY = "matched_and_major_then_fill_to_top_20_by_intensity"
XRD_NO_VISUAL_ASSET_NOTE = (
    "No provider structure image or visual asset was available in the current reference payload. "
    "Structure metadata and traceable source links are provided for follow-up review."
)


def _text(value: Any) -> str | None:
    token = str(value or "").strip()
    return token or None


def _float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _round_float(value: Any, *, digits: int = 4) -> float | None:
    parsed = _float(value)
    if parsed is None:
        return None
    return round(parsed, digits)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list_of_mappings(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    output: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, Mapping):
            output.append(dict(item))
    return output


def _coerce_reference_peaks(peaks: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, peak in enumerate(_list_of_mappings(peaks), start=1):
        normalized.append(
            {
                "peak_number": _int(peak.get("peak_number")) or index,
                "position": _round_float(peak.get("position")),
                "d_spacing": _round_float(peak.get("d_spacing")),
                "intensity": _round_float(peak.get("intensity")),
                "relative_intensity": _round_float(
                    peak.get("relative_intensity") if peak.get("relative_intensity") not in (None, "") else peak.get("intensity")
                ),
                "is_major": bool(peak.get("is_major") or peak.get("major")),
            }
        )
    return normalized


def _infer_major_reference_indices(reference_peaks: list[dict[str, Any]]) -> set[int]:
    explicit = {index for index, peak in enumerate(reference_peaks) if bool(peak.get("is_major"))}
    if explicit:
        return explicit
    intensities = [float(peak.get("relative_intensity") or peak.get("intensity") or 0.0) for peak in reference_peaks]
    if not intensities:
        return set()
    threshold = max(intensities) * 0.4
    return {
        index
        for index, peak in enumerate(reference_peaks)
        if float(peak.get("relative_intensity") or peak.get("intensity") or 0.0) >= threshold
    }


def _normalize_source_assets(
    source_assets: Any,
    *,
    source_url: str | None = None,
    provider_url: str | None = None,
) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for item in _list_of_mappings(source_assets):
        kind = _text(item.get("kind")) or "source_url"
        url = _text(item.get("url"))
        artifact_key = _text(item.get("artifact_key"))
        available = bool(item.get("available"))
        if artifact_key:
            available = True
        assets.append(
            {
                "kind": kind,
                "label": _text(item.get("label")) or kind.replace("_", " ").title(),
                "url": url,
                "artifact_key": artifact_key,
                "available": available,
            }
        )

    existing_urls = {asset.get("url") for asset in assets if asset.get("url")}
    if source_url and source_url not in existing_urls:
        assets.append(
            {
                "kind": "source_url",
                "label": "Source Reference",
                "url": source_url,
                "artifact_key": None,
                "available": True,
            }
        )
        existing_urls.add(source_url)
    if provider_url and provider_url not in existing_urls:
        assets.append(
            {
                "kind": "source_url",
                "label": "Provider Reference",
                "url": provider_url,
                "artifact_key": None,
                "available": True,
            }
        )
    return assets


def build_xrd_reference_bundle(
    match_or_row: Mapping[str, Any] | None,
    reference_entry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    primary = dict(match_or_row or {})
    reference = dict(reference_entry or {})
    existing_metadata = _mapping(primary.get("reference_metadata"))
    display_payload = xrd_candidate_display_payload(primary, reference)
    display_variants = xrd_candidate_display_variants(primary, reference)
    provider = _text(primary.get("library_provider") or existing_metadata.get("provider") or reference.get("provider"))
    package = _text(primary.get("library_package") or existing_metadata.get("package_id") or reference.get("package_id"))
    version = _text(primary.get("library_version") or existing_metadata.get("package_version") or reference.get("package_version"))
    formula_token = (
        _text(display_payload.get("formula_pretty"))
        or _text(display_payload.get("formula"))
        or _text(existing_metadata.get("formula_pretty"))
        or _text(existing_metadata.get("formula"))
        or _text(reference.get("formula_pretty"))
        or _text(reference.get("formula"))
    )
    formula_unicode = _text(primary.get("formula_unicode")) or format_scientific_formula_text(formula_token, target="unicode")

    reference_metadata = {
        "provider": provider,
        "package_id": package,
        "package_version": version,
        "provider_dataset_version": _text(existing_metadata.get("provider_dataset_version") or reference.get("provider_dataset_version")),
        "hosted_dataset_version": _text(existing_metadata.get("hosted_dataset_version") or reference.get("hosted_dataset_version") or reference.get("package_version")),
        "hosted_published_at": _text(existing_metadata.get("hosted_published_at") or reference.get("hosted_published_at") or reference.get("published_at")),
        "published_at": _text(existing_metadata.get("published_at") or reference.get("published_at")),
        "generated_at": _text(existing_metadata.get("generated_at") or reference.get("generated_at")),
        "last_updated": _text(existing_metadata.get("last_updated") or reference.get("last_updated")),
        "canonical_material_key": _text(existing_metadata.get("canonical_material_key") or reference.get("canonical_material_key")),
        "phase_family": _text(existing_metadata.get("phase_family") or reference.get("phase_family")),
        "space_group": _text(existing_metadata.get("space_group") or reference.get("space_group")),
        "symmetry": _text(existing_metadata.get("symmetry") or reference.get("symmetry")),
        "formula": _text(display_payload.get("formula")) or _text(existing_metadata.get("formula")) or _text(reference.get("formula")),
        "formula_unicode": formula_unicode,
        "formula_pretty": _text(display_payload.get("formula_pretty")) or _text(existing_metadata.get("formula_pretty")) or _text(reference.get("formula_pretty")),
        "phase_name": _text(display_payload.get("phase_name")) or _text(existing_metadata.get("phase_name")) or _text(reference.get("phase_name")),
        "display_name": _text(display_payload.get("display_name")) or _text(existing_metadata.get("display_name")) or _text(reference.get("display_name")),
        "display_name_unicode": _text(primary.get("display_name_unicode")) or _text(display_variants.get("unicode_display_name")),
        "source_url": _text(existing_metadata.get("source_url") or primary.get("source_url") or reference.get("source_url")),
        "provider_url": _text(existing_metadata.get("provider_url") or reference.get("provider_url")),
        "attribution": _text(existing_metadata.get("attribution") or primary.get("attribution") or reference.get("attribution")),
    }

    source_assets = _normalize_source_assets(
        primary.get("source_assets") or reference.get("source_assets"),
        source_url=reference_metadata.get("source_url"),
        provider_url=reference_metadata.get("provider_url"),
    )

    reference_peaks = _coerce_reference_peaks(primary.get("reference_peaks") or reference.get("peaks"))
    major_indices = _infer_major_reference_indices(reference_peaks)
    for index in major_indices:
        reference_peaks[index]["is_major"] = True

    base_structure = _mapping(primary.get("structure_payload"))
    structure_source_url = _text(
        base_structure.get("source_url")
        or reference_metadata.get("source_url")
        or reference_metadata.get("provider_url")
    )
    has_rendered_asset = any(asset.get("artifact_key") and asset.get("available") for asset in source_assets)
    structure_formula = _text(base_structure.get("formula")) or _text(reference_metadata.get("formula_pretty")) or _text(reference_metadata.get("formula"))
    structure_payload = {
        "availability": (
            "rendered_asset"
            if has_rendered_asset
            else "metadata_only"
            if any(
                (
                    _text(base_structure.get("space_group") or reference_metadata.get("space_group")),
                    _text(base_structure.get("symmetry") or reference_metadata.get("symmetry")),
                    structure_formula,
                )
            )
            else "source_only"
            if structure_source_url
            else "none"
        ),
        "space_group": _text(base_structure.get("space_group") or reference_metadata.get("space_group")),
        "symmetry": _text(base_structure.get("symmetry") or reference_metadata.get("symmetry")),
        "formula": structure_formula,
        "formula_unicode": _text(base_structure.get("formula_unicode")) or format_scientific_formula_text(structure_formula, target="unicode"),
        "source_url": structure_source_url,
        "provider_url": _text(base_structure.get("provider_url") or reference_metadata.get("provider_url")),
        "source_asset_count": len(source_assets),
        "rendered_asset_count": sum(1 for asset in source_assets if asset.get("artifact_key") and asset.get("available")),
        "notes": _text(base_structure.get("notes")),
    }

    return {
        "display_name_unicode": _text(primary.get("display_name_unicode")) or _text(display_variants.get("unicode_display_name")),
        "formula_unicode": formula_unicode,
        "reference_metadata": reference_metadata,
        "reference_peaks": reference_peaks,
        "structure_payload": structure_payload,
        "source_assets": source_assets,
    }


def build_xrd_reference_peak_summary(
    reference_peaks: Any,
    evidence: Mapping[str, Any] | None,
    *,
    peak_display_limit: int = XRD_REFERENCE_PEAK_DISPLAY_LIMIT,
) -> dict[str, Any]:
    normalized_peaks = _coerce_reference_peaks(reference_peaks)
    evidence_payload = dict(evidence or {})
    matched_indices: list[int] = []
    for item in _list_of_mappings(evidence_payload.get("matched_peak_pairs")):
        reference_index = _int(item.get("reference_index"))
        if reference_index is not None and 0 <= reference_index < len(normalized_peaks):
            matched_indices.append(reference_index)

    major_indices = _infer_major_reference_indices(normalized_peaks)
    selected: list[int] = []
    seen: set[int] = set()
    for index in matched_indices:
        if index not in seen:
            selected.append(index)
            seen.add(index)
    for index in sorted(major_indices):
        if index not in seen:
            selected.append(index)
            seen.add(index)
    remaining = sorted(
        [idx for idx in range(len(normalized_peaks)) if idx not in seen],
        key=lambda idx: float(normalized_peaks[idx].get("relative_intensity") or normalized_peaks[idx].get("intensity") or 0.0),
        reverse=True,
    )
    for index in remaining:
        if len(selected) >= peak_display_limit:
            break
        selected.append(index)
        seen.add(index)

    display_rows: list[dict[str, Any]] = []
    matched_index_set = set(matched_indices)
    for index in selected[:peak_display_limit]:
        peak = dict(normalized_peaks[index])
        display_rows.append(
            {
                "peak_number": _int(peak.get("peak_number")) or (index + 1),
                "position": _round_float(peak.get("position")),
                "d_spacing": _round_float(peak.get("d_spacing")),
                "relative_intensity": _round_float(peak.get("relative_intensity") or peak.get("intensity")),
                "matched": index in matched_index_set,
                "major": index in major_indices,
            }
        )
    display_rows.sort(key=lambda item: (_float(item.get("position")) or 0.0, _int(item.get("peak_number")) or 0))
    total_peak_count = len(normalized_peaks)
    displayed_peak_count = len(display_rows)
    return {
        "display_rows": display_rows,
        "displayed_peak_count": displayed_peak_count,
        "total_peak_count": total_peak_count,
        "truncated_count": max(total_peak_count - displayed_peak_count, 0),
        "selection_policy": XRD_REFERENCE_PEAK_SELECTION_POLICY,
    }


def build_xrd_reference_dossiers(
    summary: Mapping[str, Any] | None,
    rows: Sequence[Mapping[str, Any]] | None,
    *,
    dossier_limit: int = XRD_REFERENCE_DOSSIER_LIMIT,
    peak_display_limit: int = XRD_REFERENCE_PEAK_DISPLAY_LIMIT,
) -> list[dict[str, Any]]:
    summary_payload = dict(summary or {})
    dossiers: list[dict[str, Any]] = []
    for index, row in enumerate(rows or [], start=1):
        if index > dossier_limit or not isinstance(row, Mapping):
            break
        payload = dict(row)
        bundle = build_xrd_reference_bundle(payload)
        evidence = _mapping(payload.get("evidence"))
        reference_metadata = _mapping(bundle.get("reference_metadata"))
        reference_peaks = build_xrd_reference_peak_summary(
            bundle.get("reference_peaks"),
            evidence,
            peak_display_limit=peak_display_limit,
        )
        overall_match_status = _text(summary_payload.get("match_status")) or _text(payload.get("match_status")) or "no_match"
        confidence_band = _text(payload.get("confidence_band")) or _text(summary_payload.get("confidence_band"))
        raw_label = _text(payload.get("candidate_name"))
        reason_below_threshold = _text(payload.get("reason_below_threshold"))
        if reason_below_threshold is None and int(payload.get("rank") or index) == 1:
            reason_below_threshold = _text(summary_payload.get("top_candidate_reason_below_threshold"))

        if overall_match_status.lower() == "no_match":
            caution_note = (
                "This dossier is candidate/reference evidence for qualitative screening only and does not confirm phase identification."
            )
        elif int(payload.get("rank") or index) > 1:
            caution_note = (
                "This dossier is comparative supporting evidence for a ranked candidate and should not be treated as the accepted phase call by itself."
            )
        elif str(confidence_band or "").lower() == "low":
            caution_note = (
                "This candidate was retained with low confidence; evidence requires review before interpretation."
            )
        else:
            caution_note = (
                "This dossier summarizes library-backed reference evidence for the ranked candidate and should be interpreted with the reported qualitative match status."
            )

        dossiers.append(
            {
                "rank": int(payload.get("rank") or index),
                "candidate_overview": {
                    "display_name": _text(payload.get("display_name")) or _text(reference_metadata.get("display_name")),
                    "display_name_unicode": _text(payload.get("display_name_unicode")) or _text(reference_metadata.get("display_name_unicode")),
                    "formula": _text(payload.get("formula")) or _text(reference_metadata.get("formula")),
                    "formula_unicode": _text(payload.get("formula_unicode")) or _text(reference_metadata.get("formula_unicode")),
                    "raw_label": raw_label,
                    "candidate_id": _text(payload.get("candidate_id")),
                    "source_id": _text(payload.get("source_id")),
                    "provider": _text(payload.get("library_provider")) or _text(reference_metadata.get("provider")),
                    "package": _text(payload.get("library_package")) or _text(reference_metadata.get("package_id")),
                    "package_version": _text(payload.get("library_version")) or _text(reference_metadata.get("package_version")),
                    "confidence_band": confidence_band,
                    "match_status": overall_match_status,
                    "candidate_score": _round_float(payload.get("normalized_score")),
                    "canonical_material_key": _text(reference_metadata.get("canonical_material_key")),
                },
                "match_evidence": {
                    "shared_peak_count": _int(evidence.get("shared_peak_count")),
                    "weighted_overlap_score": _round_float(evidence.get("weighted_overlap_score")),
                    "coverage_ratio": _round_float(evidence.get("coverage_ratio")),
                    "mean_delta_position": _round_float(evidence.get("mean_delta_position")),
                    "unmatched_major_peak_count": _int(evidence.get("unmatched_major_peak_count")),
                    "matched_peak_pair_count": len(_list_of_mappings(evidence.get("matched_peak_pairs"))),
                    "unmatched_observed_count": len(_list_of_mappings(evidence.get("unmatched_observed_peaks"))),
                    "unmatched_reference_count": len(_list_of_mappings(evidence.get("unmatched_reference_peaks"))),
                    "reason_below_threshold": reason_below_threshold,
                    "caution_note": caution_note,
                },
                "reference_metadata": {
                    "provider_dataset_version": _text(reference_metadata.get("provider_dataset_version")),
                    "hosted_dataset_version": _text(reference_metadata.get("hosted_dataset_version")),
                    "hosted_published_at": _text(reference_metadata.get("hosted_published_at")),
                    "published_at": _text(reference_metadata.get("published_at")),
                    "generated_at": _text(reference_metadata.get("generated_at")),
                    "last_updated": _text(reference_metadata.get("last_updated")),
                    "canonical_material_key": _text(reference_metadata.get("canonical_material_key")),
                    "space_group": _text(reference_metadata.get("space_group")),
                    "symmetry": _text(reference_metadata.get("symmetry")),
                    "formula": _text(reference_metadata.get("formula")),
                    "formula_unicode": _text(reference_metadata.get("formula_unicode")),
                    "formula_pretty": _text(reference_metadata.get("formula_pretty")),
                    "phase_name": _text(reference_metadata.get("phase_name")),
                    "display_name": _text(reference_metadata.get("display_name")),
                    "display_name_unicode": _text(reference_metadata.get("display_name_unicode")),
                    "source_url": _text(reference_metadata.get("source_url")),
                    "provider_url": _text(reference_metadata.get("provider_url")),
                    "attribution": _text(reference_metadata.get("attribution")),
                },
                "reference_peaks": reference_peaks,
                "structure_payload": {
                    "availability": _text(_mapping(bundle.get("structure_payload")).get("availability")) or "none",
                    "space_group": _text(_mapping(bundle.get("structure_payload")).get("space_group")),
                    "symmetry": _text(_mapping(bundle.get("structure_payload")).get("symmetry")),
                    "formula": _text(_mapping(bundle.get("structure_payload")).get("formula")),
                    "formula_unicode": _text(_mapping(bundle.get("structure_payload")).get("formula_unicode")),
                    "source_url": _text(_mapping(bundle.get("structure_payload")).get("source_url")),
                    "provider_url": _text(_mapping(bundle.get("structure_payload")).get("provider_url")),
                    "source_asset_count": _int(_mapping(bundle.get("structure_payload")).get("source_asset_count")),
                    "rendered_asset_count": _int(_mapping(bundle.get("structure_payload")).get("rendered_asset_count")),
                    "notes": _text(_mapping(bundle.get("structure_payload")).get("notes")),
                },
                "source_assets": _list_of_mappings(bundle.get("source_assets")),
                "provenance": {
                    "provider": _text(payload.get("library_provider")) or _text(reference_metadata.get("provider")),
                    "package": _text(payload.get("library_package")) or _text(reference_metadata.get("package_id")),
                    "package_version": _text(payload.get("library_version")) or _text(reference_metadata.get("package_version")),
                    "library_request_id": _text(summary_payload.get("library_request_id")),
                    "candidate_id": _text(payload.get("candidate_id")),
                    "source_id": _text(payload.get("source_id")),
                    "raw_label": raw_label,
                    "attribution": _text(reference_metadata.get("attribution")),
                },
            }
        )
    return dossiers
