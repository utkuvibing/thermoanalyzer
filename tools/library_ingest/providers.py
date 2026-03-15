"""Provider-specific normalization helpers for reference-library ingest."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .common import (
    BUILDER_VERSION,
    NORMALIZED_SCHEMA_VERSION,
    ChunkedPackageEmitter,
    canonicalize_axis_signal,
    d_spacing_from_two_theta,
    download_text,
    ensure_dir,
    load_provider_sources,
    normalize_xrd_peaks,
    parse_jcamp_xy,
    provider_output_root,
    read_json_records,
    safe_slug,
    sorted_entries,
)
from .schema import normalized_spectral_entry, normalized_xrd_entry


@dataclass(frozen=True)
class XRDPatternOptions:
    wavelength_angstrom: float = 1.5406
    two_theta_min: float = 5.0
    two_theta_max: float = 90.0
    min_relative_intensity: float = 0.01


def _provider_meta(provider_id: str) -> dict[str, Any]:
    payload = load_provider_sources().get(provider_id) or {}
    if not isinstance(payload, dict):
        payload = {}
    return payload


def provider_metadata(provider_id: str) -> dict[str, Any]:
    return dict(_provider_meta(provider_id))


def _first_non_empty(mapping: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = mapping.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _coerce_float_list(value: Any) -> list[float]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                return [float(item) for item in json.loads(text)]
            except (TypeError, ValueError, json.JSONDecodeError):
                return []
        parts = [item for item in text.replace(";", ",").replace(" ", ",").split(",") if item]
        try:
            return [float(item) for item in parts]
        except ValueError:
            return []
    if isinstance(value, Iterable):
        floats: list[float] = []
        for item in value:
            try:
                floats.append(float(item))
            except (TypeError, ValueError):
                continue
        return floats
    return []


def _load_text_record(record: dict[str, Any], *, text_keys: tuple[str, ...], path_keys: tuple[str, ...], url_keys: tuple[str, ...]) -> str:
    for key in text_keys:
        text = _first_non_empty(record, key)
        if text:
            return text
    for key in path_keys:
        path_text = _first_non_empty(record, key)
        if path_text:
            return Path(path_text).read_text(encoding="utf-8")
    for key in url_keys:
        url = _first_non_empty(record, key)
        if url:
            return download_text(url)
    raise ValueError(f"Record is missing a usable source payload: keys={text_keys + path_keys + url_keys}")


def _require_pymatgen() -> tuple[Any, Any]:
    try:
        from pymatgen.analysis.diffraction.xrd import XRDCalculator
        from pymatgen.core import Structure
    except ImportError as exc:  # pragma: no cover - exercised only when optional deps missing
        raise RuntimeError(
            "pymatgen is required for COD and Materials Project ingest. Install requirements-ingest.txt."
        ) from exc
    return Structure, XRDCalculator


def _structure_from_record(record: dict[str, Any]) -> Any:
    Structure, _ = _require_pymatgen()

    structure_payload = record.get("structure")
    if isinstance(structure_payload, dict):
        return Structure.from_dict(structure_payload)
    if isinstance(structure_payload, str) and structure_payload.strip().startswith("{"):
        return Structure.from_dict(json.loads(structure_payload))

    cif_text = _load_text_record(
        record,
        text_keys=("structure_cif", "cif"),
        path_keys=("structure_cif_path", "cif_path"),
        url_keys=("structure_cif_url", "cif_url"),
    )
    return Structure.from_str(cif_text, fmt="cif")


def _xrd_peaks_from_structure(structure: Any, *, options: XRDPatternOptions) -> list[dict[str, float]]:
    _, XRDCalculator = _require_pymatgen()
    calculator = XRDCalculator(wavelength=options.wavelength_angstrom)
    pattern = calculator.get_pattern(
        structure,
        two_theta_range=(float(options.two_theta_min), float(options.two_theta_max)),
    )
    positions = [float(value) for value in getattr(pattern, "x", [])]
    intensities = [float(value) for value in getattr(pattern, "y", [])]
    if not positions or not intensities:
        return []
    max_intensity = max(intensities) or 0.0
    if max_intensity <= 0.0:
        return []

    peaks: list[dict[str, float]] = []
    for position, intensity in zip(positions, intensities):
        relative = intensity / max_intensity
        if relative < float(options.min_relative_intensity):
            continue
        d_spacing = d_spacing_from_two_theta(position, float(options.wavelength_angstrom))
        if d_spacing is None:
            continue
        peaks.append(
            {
                "position": position,
                "intensity": relative,
                "d_spacing": d_spacing,
            }
        )
    return normalize_xrd_peaks(peaks)


def normalize_cod_record(
    record: dict[str, Any],
    *,
    generated_at: str,
    provider_dataset_version: str,
    options: XRDPatternOptions,
) -> dict[str, Any]:
    provider = _provider_meta("cod")
    source_id = _first_non_empty(record, "source_id", "cod_id", "id")
    if not source_id:
        raise ValueError("COD record is missing source_id.")
    structure = _structure_from_record(record)
    candidate_name = _first_non_empty(record, "candidate_name", "formula", "name") or str(structure.composition.reduced_formula)
    entry = normalized_xrd_entry(
        candidate_id=_first_non_empty(record, "candidate_id") or f"cod_{safe_slug(source_id)}",
        candidate_name=candidate_name,
        provider=str(provider.get("provider_name") or "COD"),
        source_id=source_id,
        source_url=_first_non_empty(record, "source_url") or str(provider.get("cif_base_url") or "").format(source_id=source_id),
        peaks=_xrd_peaks_from_structure(structure, options=options),
        generated_at=generated_at,
        provider_dataset_version=provider_dataset_version,
        builder_version=BUILDER_VERSION,
        normalized_schema_version=NORMALIZED_SCHEMA_VERSION,
    )
    formula = _first_non_empty(record, "formula") or str(structure.composition.reduced_formula)
    if formula:
        entry["formula"] = formula
    return entry


def fetch_materials_project_records(*, api_key: str, material_ids: Iterable[str]) -> list[dict[str, Any]]:
    try:
        from mp_api.client import MPRester
    except ImportError as exc:  # pragma: no cover - exercised only when optional deps missing
        raise RuntimeError(
            "mp-api is required for live Materials Project ingest. Install requirements-ingest.txt."
        ) from exc

    ordered_ids = [str(item).strip() for item in material_ids if str(item).strip()]
    if not ordered_ids:
        return []

    with MPRester(api_key) as client:
        docs = client.materials.summary.search(
            material_ids=ordered_ids,
            fields=["material_id", "formula_pretty", "structure", "last_updated"],
        )

    records: list[dict[str, Any]] = []
    for doc in docs:
        if hasattr(doc, "model_dump"):
            records.append(dict(doc.model_dump()))
        elif hasattr(doc, "dict"):
            records.append(dict(doc.dict()))
        else:
            records.append(dict(doc))
    return records


def normalize_materials_project_record(
    record: dict[str, Any],
    *,
    generated_at: str,
    provider_dataset_version: str,
    options: XRDPatternOptions,
) -> dict[str, Any]:
    provider = _provider_meta("materials_project")
    source_id = _first_non_empty(record, "material_id", "source_id", "id")
    if not source_id:
        raise ValueError("Materials Project record is missing material_id.")
    structure = _structure_from_record(record)
    candidate_name = _first_non_empty(record, "candidate_name", "formula_pretty", "formula", "name") or str(structure.composition.reduced_formula)
    entry = normalized_xrd_entry(
        candidate_id=_first_non_empty(record, "candidate_id") or f"materials_project_{safe_slug(source_id)}",
        candidate_name=candidate_name,
        provider=str(provider.get("provider_name") or "Materials Project"),
        source_id=source_id,
        source_url=_first_non_empty(record, "source_url") or str(provider.get("material_base_url") or "").format(source_id=source_id),
        peaks=_xrd_peaks_from_structure(structure, options=options),
        generated_at=generated_at,
        provider_dataset_version=provider_dataset_version,
        builder_version=BUILDER_VERSION,
        normalized_schema_version=NORMALIZED_SCHEMA_VERSION,
    )
    formula = _first_non_empty(record, "formula_pretty", "formula") or str(structure.composition.reduced_formula)
    if formula:
        entry["formula"] = formula
    last_updated = _first_non_empty(record, "last_updated")
    if last_updated:
        entry["last_updated"] = last_updated
    return entry


def load_openspecy_records(*, input_json: str | Path | None = None, input_rds: str | Path | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if input_json:
        rows.extend(read_json_records(input_json))
    if input_rds:
        rows.extend(_load_openspecy_rds(input_rds))
    return rows


def _load_openspecy_rds(path: str | Path) -> list[dict[str, Any]]:
    try:
        import pyreadr
    except ImportError as exc:  # pragma: no cover - exercised only when optional deps missing
        raise RuntimeError(
            "pyreadr is required for raw OpenSpecy RDS ingest. Install requirements-ingest.txt."
        ) from exc

    result = pyreadr.read_r(str(path))
    records: list[dict[str, Any]] = []
    for frame in result.values():
        if frame is None:
            continue
        records.extend(_dataframe_to_spectral_records(frame))
    return records


def _dataframe_to_spectral_records(frame: Any) -> list[dict[str, Any]]:
    columns = [str(column) for column in getattr(frame, "columns", [])]
    numeric_columns = [column for column in columns if _looks_like_float(column)]
    records: list[dict[str, Any]] = []
    if len(numeric_columns) >= 3:
        axis = [float(column) for column in numeric_columns]
        for row in frame.to_dict(orient="records"):
            signal = [row.get(column) for column in numeric_columns]
            metadata = {str(key): value for key, value in row.items() if str(key) not in numeric_columns}
            metadata["axis"] = axis
            metadata["signal"] = signal
            records.append(metadata)
        return records

    x_key = _find_column(columns, "axis", "wavenumber", "raman_shift", "wn", "x")
    y_key = _find_column(columns, "signal", "intensity", "value", "absorbance", "transmittance", "y")
    id_key = _find_column(columns, "source_id", "spectrum_id", "id", "spec_id", "name")
    if not x_key or not y_key:
        return records

    grouped: dict[str, dict[str, Any]] = {}
    for row in frame.to_dict(orient="records"):
        group_id = str(row.get(id_key) if id_key else len(grouped)).strip() or str(len(grouped) + 1)
        bucket = grouped.setdefault(group_id, {"axis": [], "signal": []})
        bucket["axis"].append(row.get(x_key))
        bucket["signal"].append(row.get(y_key))
        for key, value in row.items():
            token = str(key)
            if token in {x_key, y_key}:
                continue
            bucket.setdefault(token, value)
    return list(grouped.values())


def _looks_like_float(value: str) -> bool:
    try:
        float(str(value).strip())
    except ValueError:
        return False
    return True


def _find_column(columns: list[str], *candidates: str) -> str:
    lowered = {column.lower(): column for column in columns}
    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    for column in columns:
        token = column.lower()
        if any(candidate.lower() in token for candidate in candidates):
            return column
    return ""


def _analysis_type_from_record(record: dict[str, Any], *, default: str = "") -> str:
    for key in ("analysis_type", "modality", "mode", "spectrum_type", "instrument_type", "technique"):
        token = _first_non_empty(record, key).upper()
        if not token:
            continue
        if "RAMAN" in token:
            return "RAMAN"
        if token in {"FTIR", "IR", "ATR-FTIR", "ATR_FTIR"} or "FTIR" in token or token == "IR":
            return "FTIR"
    return default.strip().upper()


def normalize_openspecy_record(
    record: dict[str, Any],
    *,
    generated_at: str,
    provider_dataset_version: str,
    default_analysis_type: str = "",
    invert_signal: bool = False,
) -> tuple[str, dict[str, Any]]:
    provider = _provider_meta("openspecy")
    analysis_type = _analysis_type_from_record(record, default=default_analysis_type)
    if analysis_type not in {"FTIR", "RAMAN"}:
        raise ValueError("OpenSpecy record is missing a supported analysis_type (FTIR or RAMAN).")
    axis = _coerce_float_list(record.get("axis") or record.get("wavenumber") or record.get("raman_shift") or record.get("x"))
    signal = _coerce_float_list(record.get("signal") or record.get("intensity") or record.get("y") or record.get("value"))
    axis_values, signal_values = canonicalize_axis_signal(axis, signal, invert=invert_signal)
    source_id = _first_non_empty(record, "source_id", "spectrum_id", "id")
    candidate_name = _first_non_empty(record, "candidate_name", "name", "material_name", "sample_name", "title")
    if not candidate_name:
        candidate_name = source_id or "OpenSpecy Spectrum"
    if not source_id:
        source_id = safe_slug(candidate_name)
    entry = normalized_spectral_entry(
        candidate_id=_first_non_empty(record, "candidate_id") or f"openspecy_{analysis_type.lower()}_{safe_slug(source_id)}",
        candidate_name=candidate_name,
        provider=str(provider.get("provider_name") or "OpenSpecy"),
        source_id=source_id,
        source_url=_first_non_empty(record, "source_url", "source_link", "url") or str(provider.get("source_url") or provider.get("raw_rds_url") or ""),
        axis=axis_values,
        signal=signal_values,
        generated_at=generated_at,
        provider_dataset_version=provider_dataset_version,
        builder_version=BUILDER_VERSION,
        normalized_schema_version=NORMALIZED_SCHEMA_VERSION,
    )
    return analysis_type, entry


def normalize_rod_record(
    record: dict[str, Any],
    *,
    generated_at: str,
    provider_dataset_version: str,
    default_analysis_type: str = "RAMAN",
    invert_signal: bool = False,
) -> tuple[str, dict[str, Any]]:
    provider = _provider_meta("rod")
    source_id = _first_non_empty(record, "source_id", "rod_id", "id")
    if not source_id:
        raise ValueError("ROD record is missing source_id.")
    normalized_record = dict(record)
    if not _first_non_empty(normalized_record, "jcamp", "jdx", "jcamp_text", "jcamp_path", "jdx_path", "jcamp_url", "jdx_url"):
        normalized_record["jcamp_url"] = str(provider.get("jcamp_base_url") or "").format(source_id=source_id)
    jcamp_text = _load_text_record(
        normalized_record,
        text_keys=("jcamp", "jdx", "jcamp_text"),
        path_keys=("jcamp_path", "jdx_path"),
        url_keys=("jcamp_url", "jdx_url"),
    )
    metadata, axis, signal = parse_jcamp_xy(jcamp_text)
    analysis_type = _analysis_type_from_record(record, default=default_analysis_type) or default_analysis_type.strip().upper() or "RAMAN"
    axis_values, signal_values = canonicalize_axis_signal(axis, signal, invert=invert_signal)
    candidate_name = _first_non_empty(record, "candidate_name", "name", "title") or metadata.get("TITLE") or source_id
    entry = normalized_spectral_entry(
        candidate_id=_first_non_empty(record, "candidate_id") or f"rod_{safe_slug(source_id)}",
        candidate_name=candidate_name,
        provider=str(provider.get("provider_name") or "ROD"),
        source_id=source_id,
        source_url=_first_non_empty(normalized_record, "source_url", "record_url") or str(provider.get("record_base_url") or "").format(source_id=source_id),
        axis=axis_values,
        signal=signal_values,
        generated_at=generated_at,
        provider_dataset_version=provider_dataset_version,
        builder_version=BUILDER_VERSION,
        normalized_schema_version=NORMALIZED_SCHEMA_VERSION,
    )
    if metadata.get("XUNITS"):
        entry["axis_unit"] = metadata["XUNITS"]
    if metadata.get("YUNITS"):
        entry["signal_unit"] = metadata["YUNITS"]
    return analysis_type, entry


def emit_grouped_packages(
    *,
    provider_id: str,
    output_root: str | Path,
    generated_at: str,
    provider_dataset_version: str,
    chunk_size: int,
    entries_by_analysis_type: dict[str, list[dict[str, Any]]],
) -> list[str]:
    provider = _provider_meta(provider_id)
    provider_root = provider_output_root(output_root, provider_id)
    emitted_package_ids: list[str] = []
    for analysis_type in sorted(entries_by_analysis_type):
        package_prefix = f"{safe_slug(provider_id)}_{analysis_type.lower()}"
        emitter = ChunkedPackageEmitter(
            output_root=provider_root,
            package_prefix=package_prefix,
            analysis_type=analysis_type,
            provider_name=str(provider.get("provider_name") or provider_id),
            source_url=str(provider.get("source_url") or provider.get("raw_rds_url") or ""),
            license_name=str(provider.get("license_name") or ""),
            license_text=str(provider.get("license_text") or ""),
            attribution=str(provider.get("attribution") or ""),
            priority=int(provider.get("priority") or 0),
            generated_at=generated_at,
            provider_dataset_version=provider_dataset_version,
            chunk_size=max(int(chunk_size), 1),
        )
        for entry in sorted_entries(entries_by_analysis_type[analysis_type]):
            emitted_package_ids.extend([package_id for package_id in emitter.append(entry) if package_id])
        emitted_package_ids.extend([package_id for package_id in emitter.close() if package_id])
    ensure_dir(provider_root)
    return emitted_package_ids


def group_entries_by_analysis_type(entries: Iterable[tuple[str, dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for analysis_type, entry in entries:
        grouped[str(analysis_type).upper()].append(dict(entry))
    return {key: value for key, value in grouped.items() if value}
