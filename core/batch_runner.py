"""Brownfield batch template execution for compare-workspace stable modalities."""

from __future__ import annotations

import copy
from typing import Any, Mapping

import numpy as np
from scipy.signal import find_peaks, savgol_filter

from core.dta_processor import DTAProcessor
from core.dsc_processor import DSCProcessor
from core.peak_analysis import characterize_peaks
from core.processing_schema import (
    ensure_processing_payload,
    get_workflow_templates,
    update_method_context,
    update_processing_step,
    update_tga_unit_context,
)
from core.provenance import build_calibration_reference_context, build_result_provenance
from core.reference_library import get_reference_library_manager
from core.result_serialization import (
    make_result_record,
    serialize_dsc_result,
    serialize_dta_result,
    serialize_spectral_result,
    serialize_tga_result,
    serialize_xrd_result,
)
from core.tga_processor import TGAProcessor, resolve_tga_unit_interpretation
from core.validation import enrich_spectral_result_validation, enrich_xrd_result_validation, validate_thermal_dataset


_DSC_TEMPLATE_DEFAULTS = {
    "dsc.general": {
        "smoothing": {"method": "savgol", "window_length": 11, "polyorder": 3},
        "baseline": {"method": "asls"},
        "peak_detection": {"direction": "both"},
        "glass_transition": {"mode": "auto", "region": None},
    },
    "dsc.polymer_tg": {
        "smoothing": {"method": "savgol", "window_length": 15, "polyorder": 3},
        "baseline": {"method": "asls"},
        "peak_detection": {"direction": "both"},
        "glass_transition": {"mode": "auto", "region": None},
    },
    "dsc.polymer_melting_crystallization": {
        "smoothing": {"method": "savgol", "window_length": 11, "polyorder": 3},
        "baseline": {"method": "asls"},
        "peak_detection": {"direction": "both"},
        "glass_transition": {"mode": "auto", "region": None},
    },
}

_TGA_TEMPLATE_DEFAULTS = {
    "tga.general": {
        "smoothing": {"method": "savgol", "window_length": 11, "polyorder": 3},
        "step_detection": {"method": "dtg_peaks", "prominence": None, "min_mass_loss": 0.5, "search_half_width": 80},
    },
    "tga.single_step_decomposition": {
        "smoothing": {"method": "savgol", "window_length": 11, "polyorder": 3},
        "step_detection": {"method": "dtg_peaks", "prominence": None, "min_mass_loss": 0.5, "search_half_width": 80},
    },
    "tga.multi_step_decomposition": {
        "smoothing": {"method": "savgol", "window_length": 15, "polyorder": 3},
        "step_detection": {"method": "dtg_peaks", "prominence": None, "min_mass_loss": 0.3, "search_half_width": 100},
    },
}
_DTA_TEMPLATE_DEFAULTS = {
    "dta.general": {
        "smoothing": {"method": "savgol", "window_length": 11, "polyorder": 3},
        "baseline": {"method": "asls"},
        "peak_detection": {
            "detect_endothermic": True,
            "detect_exothermic": True,
        },
    },
    "dta.thermal_events": {
        "smoothing": {"method": "savgol", "window_length": 15, "polyorder": 3},
        "baseline": {"method": "asls"},
        "peak_detection": {
            "detect_endothermic": True,
            "detect_exothermic": True,
            "prominence": 0.0,
            "distance": 8,
        },
    },
}
_FTIR_TEMPLATE_DEFAULTS = {
    "ftir.general": {
        "smoothing": {"method": "moving_average", "window_length": 11},
        "baseline": {"method": "linear"},
        "normalization": {"method": "vector"},
        "peak_detection": {"prominence": 0.05, "min_distance": 6, "max_peaks": 12},
        "similarity_matching": {"metric": "cosine", "top_n": 3, "minimum_score": 0.45},
    },
    "ftir.functional_groups": {
        "smoothing": {"method": "moving_average", "window_length": 9},
        "baseline": {"method": "linear"},
        "normalization": {"method": "vector"},
        "peak_detection": {"prominence": 0.04, "min_distance": 5, "max_peaks": 16},
        "similarity_matching": {"metric": "cosine", "top_n": 5, "minimum_score": 0.42},
    },
}
_RAMAN_TEMPLATE_DEFAULTS = {
    "raman.general": {
        "smoothing": {"method": "moving_average", "window_length": 9},
        "baseline": {"method": "linear"},
        "normalization": {"method": "snv"},
        "peak_detection": {"prominence": 0.04, "min_distance": 5, "max_peaks": 14},
        "similarity_matching": {"metric": "cosine", "top_n": 3, "minimum_score": 0.45},
    },
    "raman.polymorph_screening": {
        "smoothing": {"method": "moving_average", "window_length": 7},
        "baseline": {"method": "linear"},
        "normalization": {"method": "snv"},
        "peak_detection": {"prominence": 0.03, "min_distance": 4, "max_peaks": 18},
        "similarity_matching": {"metric": "pearson", "top_n": 5, "minimum_score": 0.4},
    },
}
_XRD_TEMPLATE_DEFAULTS = {
    "xrd.general": {
        "axis_normalization": {"sort_axis": True, "deduplicate": "first", "axis_min": None, "axis_max": None},
        "smoothing": {"method": "savgol", "window_length": 11, "polyorder": 3},
        "baseline": {"method": "rolling_minimum", "window_length": 31},
        "peak_detection": {"method": "scipy_find_peaks", "prominence": 0.08, "distance": 6, "width": 2, "max_peaks": 12},
        "method_context": {
            "xrd_match_metric": "peak_overlap_weighted",
            "xrd_match_tolerance_deg": 0.28,
            "xrd_match_top_n": 5,
            "xrd_match_minimum_score": 0.42,
            "xrd_match_intensity_weight": 0.35,
            "xrd_match_major_peak_fraction": 0.4,
        },
    },
    "xrd.phase_screening": {
        "axis_normalization": {"sort_axis": True, "deduplicate": "first", "axis_min": 5.0, "axis_max": 90.0},
        "smoothing": {"method": "savgol", "window_length": 15, "polyorder": 3},
        "baseline": {"method": "rolling_minimum", "window_length": 41},
        "peak_detection": {"method": "scipy_find_peaks", "prominence": 0.12, "distance": 8, "width": 3, "max_peaks": 16},
        "method_context": {
            "xrd_match_metric": "peak_overlap_weighted",
            "xrd_match_tolerance_deg": 0.24,
            "xrd_match_top_n": 7,
            "xrd_match_minimum_score": 0.45,
            "xrd_match_intensity_weight": 0.4,
            "xrd_match_major_peak_fraction": 0.45,
        },
    },
}
_VALID_EXECUTION_STATUSES = {"saved", "blocked", "failed"}


def _resolve_batch_tga_processing(processing: dict[str, Any], dataset) -> tuple[dict[str, Any], dict[str, Any]]:
    method_context = processing.get("method_context") or {}
    unit_context = resolve_tga_unit_interpretation(
        dataset.data["signal"].values,
        unit_mode=method_context.get("tga_unit_mode_declared") or "auto",
        signal_unit=(dataset.units or {}).get("signal"),
        initial_mass_mg=dataset.metadata.get("sample_mass"),
    )
    return update_tga_unit_context(processing, unit_context), unit_context


def execute_batch_template(
    *,
    dataset_key: str,
    dataset,
    analysis_type: str,
    workflow_template_id: str,
    existing_processing: Mapping[str, Any] | None = None,
    analysis_history: list[dict[str, Any]] | None = None,
    analyst_name: str | None = None,
    app_version: str | None = None,
    batch_run_id: str | None = None,
) -> dict[str, Any]:
    """Execute one batch template against one dataset without UI dependencies."""
    normalized_type = (analysis_type or "UNKNOWN").upper()
    processing = _build_processing_payload(
        analysis_type=normalized_type,
        workflow_template_id=workflow_template_id,
        existing_processing=existing_processing,
        batch_run_id=batch_run_id,
    )

    pre_validation = validate_thermal_dataset(dataset, analysis_type=normalized_type, processing=processing)
    if pre_validation["status"] == "fail":
        return {
            "status": "blocked",
            "analysis_type": normalized_type,
            "dataset_key": dataset_key,
            "processing": processing,
            "validation": pre_validation,
            "record": None,
            "state": None,
            "summary_row": _make_summary_row(
                dataset_key=dataset_key,
                dataset=dataset,
                analysis_type=normalized_type,
                processing=processing,
                validation=pre_validation,
                execution_status="blocked",
                failure_reason="; ".join(pre_validation["issues"]) or "Dataset blocked by validation.",
            ),
        }

    if normalized_type == "DSC":
        return _execute_dsc_batch(
            dataset_key=dataset_key,
            dataset=dataset,
            processing=processing,
            analysis_history=analysis_history,
            analyst_name=analyst_name,
            app_version=app_version,
            batch_run_id=batch_run_id,
        )
    if normalized_type == "TGA":
        return _execute_tga_batch(
            dataset_key=dataset_key,
            dataset=dataset,
            processing=processing,
            analysis_history=analysis_history,
            analyst_name=analyst_name,
            app_version=app_version,
            batch_run_id=batch_run_id,
        )
    if normalized_type == "DTA":
        return _execute_dta_batch(
            dataset_key=dataset_key,
            dataset=dataset,
            processing=processing,
            analysis_history=analysis_history,
            analyst_name=analyst_name,
            app_version=app_version,
            batch_run_id=batch_run_id,
        )
    if normalized_type in {"FTIR", "RAMAN"}:
        return _execute_spectral_batch(
            dataset_key=dataset_key,
            dataset=dataset,
            analysis_type=normalized_type,
            processing=processing,
            analysis_history=analysis_history,
            analyst_name=analyst_name,
            app_version=app_version,
            batch_run_id=batch_run_id,
        )
    if normalized_type == "XRD":
        return _execute_xrd_batch(
            dataset_key=dataset_key,
            dataset=dataset,
            processing=processing,
            analysis_history=analysis_history,
            analyst_name=analyst_name,
            app_version=app_version,
            batch_run_id=batch_run_id,
        )
    raise ValueError(f"Unsupported batch analysis type '{analysis_type}'")


def _build_processing_payload(
    *,
    analysis_type: str,
    workflow_template_id: str,
    existing_processing: Mapping[str, Any] | None,
    batch_run_id: str | None,
) -> dict[str, Any]:
    template_label = _workflow_template_label(analysis_type, workflow_template_id)
    processing = ensure_processing_payload(
        dict(existing_processing or {}),
        analysis_type=analysis_type,
        workflow_template=workflow_template_id,
        workflow_template_label=template_label,
    )
    defaults = _template_defaults(analysis_type, workflow_template_id)
    for section_name, values in defaults.items():
        override = _resolve_processing_override(processing, section_name)
        merged_values = copy.deepcopy(values)
        if isinstance(override, Mapping):
            merged_values.update(copy.deepcopy(dict(override)))
        if section_name == "method_context":
            processing = update_method_context(processing, merged_values, analysis_type=analysis_type)
        else:
            processing = update_processing_step(processing, section_name, merged_values, analysis_type=analysis_type)

    method_context = {
        "batch_template_runner": "compare_workspace",
        "batch_run_id": batch_run_id or "",
    }
    return update_method_context(processing, method_context, analysis_type=analysis_type)


def _resolve_processing_override(processing: Mapping[str, Any], section_name: str) -> Mapping[str, Any]:
    signal_pipeline = processing.get("signal_pipeline")
    if isinstance(signal_pipeline, Mapping) and isinstance(signal_pipeline.get(section_name), Mapping):
        return dict(signal_pipeline.get(section_name) or {})
    analysis_steps = processing.get("analysis_steps")
    if isinstance(analysis_steps, Mapping) and isinstance(analysis_steps.get(section_name), Mapping):
        return dict(analysis_steps.get(section_name) or {})
    section = processing.get(section_name)
    if isinstance(section, Mapping):
        return dict(section)
    return {}


def _execute_dsc_batch(
    *,
    dataset_key: str,
    dataset,
    processing: dict[str, Any],
    analysis_history: list[dict[str, Any]] | None,
    analyst_name: str | None,
    app_version: str | None,
    batch_run_id: str | None,
) -> dict[str, Any]:
    temperature = dataset.data["temperature"].values
    signal = dataset.data["signal"].values
    sample_mass = dataset.metadata.get("sample_mass")
    heating_rate = dataset.metadata.get("heating_rate")

    smoothing = copy.deepcopy((processing.get("signal_pipeline") or {}).get("smoothing") or {})
    baseline = copy.deepcopy((processing.get("signal_pipeline") or {}).get("baseline") or {})
    peak_detection = copy.deepcopy((processing.get("analysis_steps") or {}).get("peak_detection") or {})
    glass_transition = copy.deepcopy((processing.get("analysis_steps") or {}).get("glass_transition") or {})

    processor = DSCProcessor(
        temperature,
        signal,
        sample_mass=sample_mass,
        heating_rate=heating_rate,
    )

    smooth_method = smoothing.pop("method", "savgol")
    processor.smooth(method=smooth_method, **smoothing)
    processor.normalize()
    smoothed_signal = processor.get_result().smoothed_signal.copy()

    baseline_method = baseline.pop("method", "asls")
    processor.correct_baseline(method=baseline_method, **baseline)
    corrected_signal = processor.get_result().smoothed_signal.copy()

    processor.find_peaks(**peak_detection)
    tg_region = glass_transition.get("region")
    processor.detect_glass_transition(region=tuple(tg_region) if isinstance(tg_region, (list, tuple)) and len(tg_region) == 2 else None)
    result = processor.get_result()

    calibration_context = build_calibration_reference_context(
        dataset=dataset,
        analysis_type="DSC",
        reference_temperature_c=_select_dsc_reference_temperature(result),
    )
    processing = update_method_context(processing, calibration_context, analysis_type="DSC")
    validation = validate_thermal_dataset(dataset, analysis_type="DSC", processing=processing)
    provenance = build_result_provenance(
        dataset=dataset,
        dataset_key=dataset_key,
        analysis_history=analysis_history,
        app_version=app_version,
        analyst_name=analyst_name,
        extra={
            "batch_run_id": batch_run_id,
            "batch_runner": "compare_workspace",
            "calibration_state": calibration_context.get("calibration_state"),
            "reference_state": calibration_context.get("reference_state"),
            "reference_name": calibration_context.get("reference_name"),
            "reference_delta_c": calibration_context.get("reference_delta_c"),
        },
    )
    record = serialize_dsc_result(
        dataset_key,
        dataset,
        result.peaks,
        glass_transitions=result.glass_transitions,
        artifacts={},
        processing=processing,
        provenance=provenance,
        validation=validation,
        review={"commercial_scope": "stable_dsc", "batch_runner": "compare_workspace"},
    )
    state = {
        "smoothed": smoothed_signal,
        "baseline": result.baseline,
        "corrected": corrected_signal,
        "peaks": result.peaks,
        "glass_transitions": result.glass_transitions,
        "processor": None,
        "processing": processing,
    }
    return {
        "status": "saved",
        "analysis_type": "DSC",
        "dataset_key": dataset_key,
        "processing": processing,
        "validation": validation,
        "record": record,
        "state": state,
        "summary_row": _make_summary_row(
            dataset_key=dataset_key,
            dataset=dataset,
            analysis_type="DSC",
            processing=processing,
            validation=validation,
            execution_status="saved",
            record=record,
            failure_reason="",
        ),
    }


def _execute_tga_batch(
    *,
    dataset_key: str,
    dataset,
    processing: dict[str, Any],
    analysis_history: list[dict[str, Any]] | None,
    analyst_name: str | None,
    app_version: str | None,
    batch_run_id: str | None,
) -> dict[str, Any]:
    temperature = dataset.data["temperature"].values
    signal = dataset.data["signal"].values
    initial_mass_mg = dataset.metadata.get("sample_mass")
    processing, unit_context = _resolve_batch_tga_processing(processing, dataset)

    smoothing = copy.deepcopy((processing.get("signal_pipeline") or {}).get("smoothing") or {})
    step_detection = copy.deepcopy((processing.get("analysis_steps") or {}).get("step_detection") or {})

    processor = TGAProcessor(
        temperature,
        signal,
        initial_mass_mg=initial_mass_mg,
        metadata=dataset.metadata,
        unit_mode=str(unit_context["resolved_unit_mode"]),
        signal_unit=(dataset.units or {}).get("signal"),
    )

    smooth_method = smoothing.pop("method", "savgol")
    processor.smooth(method=smooth_method, **smoothing)
    processor.compute_dtg(
        smooth_dtg=True,
        window_length=smoothing.get("window_length", 11),
        polyorder=smoothing.get("polyorder", 3),
    )
    step_detection.pop("method", None)
    processor.detect_steps(
        prominence=step_detection.pop("prominence", None),
        min_mass_loss=step_detection.pop("min_mass_loss", 0.5),
        search_half_width=step_detection.pop("search_half_width", 80),
        **step_detection,
    )
    result = processor.get_result()

    calibration_context = build_calibration_reference_context(
        dataset=dataset,
        analysis_type="TGA",
        reference_temperature_c=_select_tga_reference_temperature(result),
    )
    processing = update_method_context(processing, calibration_context, analysis_type="TGA")
    validation = validate_thermal_dataset(dataset, analysis_type="TGA", processing=processing)
    provenance = build_result_provenance(
        dataset=dataset,
        dataset_key=dataset_key,
        analysis_history=analysis_history,
        app_version=app_version,
        analyst_name=analyst_name,
        extra={
            "batch_run_id": batch_run_id,
            "batch_runner": "compare_workspace",
            "calibration_state": calibration_context.get("calibration_state"),
            "reference_state": calibration_context.get("reference_state"),
            "reference_name": calibration_context.get("reference_name"),
            "reference_delta_c": calibration_context.get("reference_delta_c"),
        },
    )
    record = serialize_tga_result(
        dataset_key,
        dataset,
        result,
        artifacts={},
        processing=processing,
        provenance=provenance,
        validation=validation,
        review={"commercial_scope": "stable_tga", "batch_runner": "compare_workspace"},
    )
    state = {
        "smoothed": result.smoothed_signal,
        "dtg": result.dtg_signal,
        "tga_result": result,
        "processing": processing,
    }
    return {
        "status": "saved",
        "analysis_type": "TGA",
        "dataset_key": dataset_key,
        "processing": processing,
        "validation": validation,
        "record": record,
        "state": state,
        "summary_row": _make_summary_row(
            dataset_key=dataset_key,
            dataset=dataset,
            analysis_type="TGA",
            processing=processing,
            validation=validation,
            execution_status="saved",
            record=record,
            failure_reason="",
        ),
    }


def _template_defaults(analysis_type: str, workflow_template_id: str) -> dict[str, Any]:
    if analysis_type == "DSC":
        catalog = _DSC_TEMPLATE_DEFAULTS
        fallback = "dsc.general"
    elif analysis_type == "TGA":
        catalog = _TGA_TEMPLATE_DEFAULTS
        fallback = "tga.general"
    elif analysis_type == "DTA":
        catalog = _DTA_TEMPLATE_DEFAULTS
        fallback = "dta.general"
    elif analysis_type == "FTIR":
        catalog = _FTIR_TEMPLATE_DEFAULTS
        fallback = "ftir.general"
    elif analysis_type == "RAMAN":
        catalog = _RAMAN_TEMPLATE_DEFAULTS
        fallback = "raman.general"
    elif analysis_type == "XRD":
        catalog = _XRD_TEMPLATE_DEFAULTS
        fallback = "xrd.general"
    else:
        raise ValueError(f"Unsupported batch analysis type '{analysis_type}'")

    if workflow_template_id in catalog:
        return copy.deepcopy(catalog[workflow_template_id])
    return copy.deepcopy(catalog[fallback])


def _workflow_template_label(analysis_type: str, workflow_template_id: str) -> str:
    for entry in get_workflow_templates(analysis_type):
        if entry["id"] == workflow_template_id:
            return entry["label"]
    return workflow_template_id


def _select_dsc_reference_temperature(result) -> float | None:
    peaks = getattr(result, "peaks", []) or []
    if peaks:
        return getattr(peaks[0], "peak_temperature", None)
    glass_transitions = getattr(result, "glass_transitions", []) or []
    if glass_transitions:
        return getattr(glass_transitions[0], "tg_midpoint", None)
    return None


def _select_tga_reference_temperature(result) -> float | None:
    steps = getattr(result, "steps", []) or []
    if steps:
        return getattr(steps[0], "midpoint_temperature", None) or getattr(steps[0], "onset_temperature", None)
    return None


def _execute_dta_batch(
    *,
    dataset_key: str,
    dataset,
    processing: dict[str, Any],
    analysis_history: list[dict[str, Any]] | None,
    analyst_name: str | None,
    app_version: str | None,
    batch_run_id: str | None,
) -> dict[str, Any]:
    temperature = dataset.data["temperature"].values
    signal = dataset.data["signal"].values

    smoothing = copy.deepcopy((processing.get("signal_pipeline") or {}).get("smoothing") or {})
    baseline = copy.deepcopy((processing.get("signal_pipeline") or {}).get("baseline") or {})
    peak_detection = copy.deepcopy((processing.get("analysis_steps") or {}).get("peak_detection") or {})

    processor = DTAProcessor(
        temperature,
        signal,
        metadata=dataset.metadata,
    )

    smooth_method = smoothing.pop("method", "savgol")
    processor.smooth(method=smooth_method, **smoothing)

    baseline_method = baseline.pop("method", "asls")
    processor.correct_baseline(method=baseline_method, **baseline)

    direction = str(peak_detection.pop("direction", "both") or "both").lower()
    detect_endothermic = peak_detection.pop("detect_endothermic", None)
    detect_exothermic = peak_detection.pop("detect_exothermic", None)
    if detect_endothermic is None:
        detect_endothermic = direction in {"both", "down", "endo", "endothermic"}
    if detect_exothermic is None:
        detect_exothermic = direction in {"both", "up", "exo", "exothermic"}
    if not detect_endothermic and not detect_exothermic:
        detect_endothermic = True
        detect_exothermic = True
    if peak_detection.get("prominence") in ("", 0, 0.0):
        peak_detection["prominence"] = None
    if peak_detection.get("distance") in ("", 0, 0.0):
        peak_detection["distance"] = None
    if peak_detection.get("min_peak_height") in ("", 0, 0.0):
        peak_detection["min_peak_height"] = None

    processor.find_peaks(
        detect_endothermic=bool(detect_endothermic),
        detect_exothermic=bool(detect_exothermic),
        **peak_detection,
    )
    result = processor.get_result()
    if result.peaks:
        result.peaks = characterize_peaks(
            temperature,
            result.smoothed_signal,
            list(result.peaks),
            baseline=result.baseline,
        )

    calibration_context = build_calibration_reference_context(
        dataset=dataset,
        analysis_type="DTA",
        reference_temperature_c=_select_dta_reference_temperature(result),
    )
    processing = update_method_context(processing, calibration_context, analysis_type="DTA")
    validation = validate_thermal_dataset(dataset, analysis_type="DTA", processing=processing)
    provenance = build_result_provenance(
        dataset=dataset,
        dataset_key=dataset_key,
        analysis_history=analysis_history,
        app_version=app_version,
        analyst_name=analyst_name,
        extra={
            "batch_run_id": batch_run_id,
            "batch_runner": "compare_workspace",
            "calibration_state": calibration_context.get("calibration_state"),
            "reference_state": calibration_context.get("reference_state"),
            "reference_name": calibration_context.get("reference_name"),
            "reference_delta_c": calibration_context.get("reference_delta_c"),
        },
    )
    record = serialize_dta_result(
        dataset_key,
        dataset,
        result.peaks,
        artifacts={},
        processing=processing,
        provenance=provenance,
        validation=validation,
        review={"commercial_scope": "stable_dta", "batch_runner": "compare_workspace"},
    )
    state = {
        "smoothed": result.smoothed_signal,
        "baseline": result.baseline,
        "corrected": result.smoothed_signal,
        "peaks": result.peaks,
        "processing": processing,
    }
    return {
        "status": "saved",
        "analysis_type": "DTA",
        "dataset_key": dataset_key,
        "processing": processing,
        "validation": validation,
        "record": record,
        "state": state,
        "summary_row": _make_summary_row(
            dataset_key=dataset_key,
            dataset=dataset,
            analysis_type="DTA",
            processing=processing,
            validation=validation,
            execution_status="saved",
            record=record,
            failure_reason="",
        ),
    }


def _select_dta_reference_temperature(result) -> float | None:
    peaks = getattr(result, "peaks", []) or []
    if peaks:
        return getattr(peaks[0], "peak_temperature", None) or getattr(peaks[0], "temperature", None)
    return None


def _slug_token(value: Any) -> str:
    text = "".join(char.lower() if char.isalnum() else "_" for char in str(value or "").strip())
    token = "_".join(part for part in text.split("_") if part)
    return token or "reference"


def _to_float_array(values: Any) -> np.ndarray | None:
    if values is None:
        return None
    try:
        array = np.asarray(values, dtype=float)
    except Exception:
        return None
    if array.ndim != 1 or array.size < 3:
        return None
    if not np.isfinite(array).all():
        return None
    return array


def _sorted_axis_signal(axis: np.ndarray, signal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    order = np.argsort(axis)
    sorted_axis = axis[order]
    sorted_signal = signal[order]
    unique_axis, unique_idx = np.unique(sorted_axis, return_index=True)
    return unique_axis, sorted_signal[unique_idx]


def _apply_spectral_smoothing(signal: np.ndarray, config: Mapping[str, Any]) -> np.ndarray:
    method = str(config.get("method") or "moving_average").strip().lower()
    if method in {"none", "off"}:
        return signal.copy()
    window = int(config.get("window_length") or 9)
    if window < 3:
        window = 3
    if window % 2 == 0:
        window += 1
    kernel = np.ones(window, dtype=float) / float(window)
    pad = window // 2
    padded = np.pad(signal, (pad, pad), mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def _estimate_spectral_baseline(axis: np.ndarray, signal: np.ndarray, config: Mapping[str, Any]) -> np.ndarray:
    method = str(config.get("method") or "linear").strip().lower()
    if method in {"none", "off"}:
        return np.zeros_like(signal)
    if method in {"linear", "asls", "rubberband"}:
        start = float(signal[0])
        end = float(signal[-1])
        if float(axis[-1]) == float(axis[0]):
            return np.full_like(signal, start)
        slope = (end - start) / (float(axis[-1]) - float(axis[0]))
        return start + slope * (axis - float(axis[0]))
    offset = float(np.min(signal))
    return np.full_like(signal, offset)


def _normalize_spectral_signal(signal: np.ndarray, config: Mapping[str, Any]) -> np.ndarray:
    method = str(config.get("method") or "vector").strip().lower()
    centered = signal - float(np.mean(signal))
    if method == "snv":
        std = float(np.std(centered))
        return centered / std if std > 0 else centered
    if method == "max":
        scale = float(np.max(np.abs(signal)))
        return signal / scale if scale > 0 else signal.copy()
    norm = float(np.linalg.norm(signal))
    return signal / norm if norm > 0 else signal.copy()


def _detect_spectral_peaks(axis: np.ndarray, signal: np.ndarray, config: Mapping[str, Any]) -> list[dict[str, float]]:
    prominence = float(config.get("prominence") or 0.05)
    min_distance = int(config.get("min_distance") or 5)
    max_peaks = int(config.get("max_peaks") or 10)

    candidate_indices: list[int] = []
    for idx in range(1, signal.size - 1):
        if signal[idx] < prominence:
            continue
        if signal[idx] >= signal[idx - 1] and signal[idx] >= signal[idx + 1]:
            candidate_indices.append(idx)

    selected: list[int] = []
    for idx in sorted(candidate_indices, key=lambda item: float(signal[item]), reverse=True):
        if any(abs(idx - prev) < min_distance for prev in selected):
            continue
        selected.append(idx)
        if len(selected) >= max_peaks:
            break

    return [
        {"position": float(axis[idx]), "intensity": float(signal[idx])}
        for idx in sorted(selected)
    ]


def _first_defined_value(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, (list, tuple, dict, set)) and not value:
            continue
        return value
    return None


def _extract_reference_signal(entry: Mapping[str, Any]) -> tuple[np.ndarray | None, np.ndarray | None]:
    axis = _to_float_array(_first_defined_value(entry.get("axis"), entry.get("temperature"), entry.get("x")))
    signal = _to_float_array(_first_defined_value(entry.get("signal"), entry.get("intensity"), entry.get("y")))
    if axis is None or signal is None or axis.size != signal.size:
        return None, None
    return _sorted_axis_signal(axis, signal)


def _reference_row(
    *,
    candidate_id: str,
    candidate_name: str,
    priority: int = 0,
    provider: str = "",
    package_id: str = "",
    package_version: str = "",
    attribution: str = "",
    source_url: str = "",
    axis: np.ndarray | None = None,
    signal: np.ndarray | None = None,
    peaks: list[dict[str, float]] | None = None,
) -> dict[str, Any]:
    payload = {
        "candidate_id": _slug_token(candidate_id),
        "candidate_name": candidate_name,
        "priority": int(priority),
        "provider": provider,
        "package_id": package_id,
        "package_version": package_version,
        "attribution": attribution,
        "source_url": source_url,
    }
    if axis is not None and signal is not None:
        payload["axis"] = axis
        payload["signal"] = signal
    if peaks is not None:
        payload["peaks"] = peaks
    return payload


def _resolve_spectral_references(
    *,
    dataset,
    analysis_type: str,
    processing: Mapping[str, Any],
) -> list[dict[str, Any]]:
    metadata = getattr(dataset, "metadata", {}) or {}
    method_context = (processing.get("method_context") or {}) if isinstance(processing, Mapping) else {}
    raw_references = (
        metadata.get("spectral_reference_library")
        or metadata.get("reference_library")
        or method_context.get("spectral_reference_library")
        or []
    )
    normalized: list[dict[str, Any]] = []
    if isinstance(raw_references, list):
        for index, item in enumerate(raw_references, start=1):
            if not isinstance(item, Mapping):
                continue
            candidate_id = str(item.get("id") or item.get("candidate_id") or f"reference_{index}")
            candidate_name = str(item.get("name") or item.get("candidate_name") or candidate_id)
            axis, signal = _extract_reference_signal(item)
            if axis is None or signal is None:
                continue
            normalized.append(
                _reference_row(
                    candidate_id=candidate_id,
                    candidate_name=candidate_name,
                    priority=1000,
                    provider=str(item.get("provider") or "dataset"),
                    package_id=str(item.get("package_id") or "dataset_metadata"),
                    package_version=str(item.get("package_version") or "embedded"),
                    attribution=str(item.get("attribution") or ""),
                    source_url=str(item.get("source_url") or ""),
                    axis=axis,
                    signal=signal,
                )
            )
    manager = get_reference_library_manager()
    for entry in manager.load_entries(analysis_type):
        axis, signal = _extract_reference_signal(entry)
        if axis is None or signal is None:
            continue
        normalized.append(
            _reference_row(
                candidate_id=str(entry.get("candidate_id") or ""),
                candidate_name=str(entry.get("candidate_name") or ""),
                priority=int(entry.get("priority") or 0),
                provider=str(entry.get("provider") or ""),
                package_id=str(entry.get("package_id") or ""),
                package_version=str(entry.get("package_version") or ""),
                attribution=str(entry.get("attribution") or ""),
                source_url=str(entry.get("source_url") or ""),
                axis=axis,
                signal=signal,
            )
        )
    normalized.sort(
        key=lambda item: (
            -int(item.get("priority") or 0),
            str(item.get("provider") or ""),
            str(item.get("candidate_id") or ""),
        )
    )
    return normalized


def _spectral_similarity(observed: np.ndarray, reference: np.ndarray, metric: str) -> float:
    token = metric.strip().lower()
    if token == "pearson":
        obs = observed - float(np.mean(observed))
        ref = reference - float(np.mean(reference))
        obs_norm = float(np.linalg.norm(obs))
        ref_norm = float(np.linalg.norm(ref))
        if obs_norm == 0.0 or ref_norm == 0.0:
            return 0.0
        correlation = float(np.dot(obs, ref) / (obs_norm * ref_norm))
        return max(0.0, min(1.0, (correlation + 1.0) / 2.0))
    obs_norm = float(np.linalg.norm(observed))
    ref_norm = float(np.linalg.norm(reference))
    if obs_norm == 0.0 or ref_norm == 0.0:
        return 0.0
    similarity = float(np.dot(observed, reference) / (obs_norm * ref_norm))
    return max(0.0, min(1.0, (similarity + 1.0) / 2.0))


def _confidence_band(score: float, minimum_score: float) -> str:
    if score >= max(minimum_score + 0.35, 0.85):
        return "high"
    if score >= max(minimum_score + 0.15, 0.65):
        return "medium"
    if score >= minimum_score:
        return "low"
    return "no_match"


def _shared_peak_count(observed_peaks: list[dict[str, float]], reference_peaks: list[dict[str, float]], tolerance: float = 12.0) -> int:
    if not observed_peaks or not reference_peaks:
        return 0
    remaining = [float(item["position"]) for item in reference_peaks]
    shared = 0
    for observed in observed_peaks:
        position = float(observed["position"])
        closest_index = None
        closest_delta = None
        for idx, candidate in enumerate(remaining):
            delta = abs(position - candidate)
            if closest_delta is None or delta < closest_delta:
                closest_delta = delta
                closest_index = idx
        if closest_delta is not None and closest_delta <= tolerance and closest_index is not None:
            shared += 1
            remaining.pop(closest_index)
    return shared


def _rank_spectral_matches(
    *,
    axis: np.ndarray,
    normalized_signal: np.ndarray,
    observed_peaks: list[dict[str, float]],
    references: list[dict[str, Any]],
    matching_config: Mapping[str, Any],
    peak_config: Mapping[str, Any],
) -> list[dict[str, Any]]:
    top_n = int(matching_config.get("top_n") or 3)
    minimum_score = float(matching_config.get("minimum_score") or 0.45)
    if top_n < 1:
        top_n = 1

    preranked: list[dict[str, Any]] = []
    for reference in references:
        reference_axis = reference["axis"]
        reference_signal = reference["signal"]
        interpolated = np.interp(axis, reference_axis, reference_signal)
        reference_smoothed = _apply_spectral_smoothing(interpolated, {"method": "none"})
        reference_normalized = _normalize_spectral_signal(reference_smoothed, {"method": "vector"})
        reference_peaks = _detect_spectral_peaks(axis, reference_normalized, peak_config)
        cosine_score = _spectral_similarity(normalized_signal, reference_normalized, "cosine")
        preranked.append(
            {
                "reference": reference,
                "reference_normalized": reference_normalized,
                "reference_peaks": reference_peaks,
                "cosine_score": cosine_score,
            }
        )

    preranked.sort(
        key=lambda item: (
            -float(item["cosine_score"]),
            -int((item["reference"] or {}).get("priority") or 0),
            str((item["reference"] or {}).get("candidate_id") or ""),
        )
    )
    shortlist_count = min(len(preranked), max(top_n * 5, 10))
    ranked: list[dict[str, Any]] = []
    for item in preranked[:shortlist_count]:
        reference = item["reference"]
        reference_normalized = item["reference_normalized"]
        reference_peaks = item["reference_peaks"]
        shared = _shared_peak_count(observed_peaks, reference_peaks)
        overlap_ratio = float(shared / max(len(observed_peaks), len(reference_peaks), 1))
        pearson_score = _spectral_similarity(normalized_signal, reference_normalized, "pearson")
        score = float(max(0.0, min(1.0, (0.7 * pearson_score) + (0.3 * overlap_ratio))))
        confidence_band = _confidence_band(score, minimum_score)
        ranked.append(
            {
                "candidate_id": reference["candidate_id"],
                "candidate_name": reference["candidate_name"],
                "normalized_score": round(score, 4),
                "confidence_band": confidence_band,
                "library_provider": reference.get("provider") or "",
                "library_package": reference.get("package_id") or "",
                "library_version": reference.get("package_version") or "",
                "evidence": {
                    "metric": "cosine_prerank_then_pearson_peak_overlap",
                    "observed_peak_count": len(observed_peaks),
                    "reference_peak_count": len(reference_peaks),
                    "shared_peak_count": shared,
                    "peak_overlap_ratio": round(overlap_ratio, 4),
                    "cosine_prerank_score": round(float(item["cosine_score"]), 4),
                    "pearson_score": round(pearson_score, 4),
                    "library_provider": reference.get("provider") or "",
                    "library_package": reference.get("package_id") or "",
                    "library_version": reference.get("package_version") or "",
                },
            }
        )

    ranked.sort(
        key=lambda item: (
            -float(item["normalized_score"]),
            str(item.get("library_provider") or ""),
            str(item["candidate_id"]),
        )
    )
    trimmed = ranked[:top_n]
    for rank, item in enumerate(trimmed, start=1):
        item["rank"] = rank
    return trimmed


def _execute_spectral_batch(
    *,
    dataset_key: str,
    dataset,
    analysis_type: str,
    processing: dict[str, Any],
    analysis_history: list[dict[str, Any]] | None,
    analyst_name: str | None,
    app_version: str | None,
    batch_run_id: str | None,
) -> dict[str, Any]:
    axis = np.asarray(dataset.data["temperature"], dtype=float)
    signal = np.asarray(dataset.data["signal"], dtype=float)
    axis, signal = _sorted_axis_signal(axis, signal)

    smoothing = copy.deepcopy((processing.get("signal_pipeline") or {}).get("smoothing") or {})
    baseline = copy.deepcopy((processing.get("signal_pipeline") or {}).get("baseline") or {})
    normalization = copy.deepcopy((processing.get("signal_pipeline") or {}).get("normalization") or {})
    peak_detection = copy.deepcopy((processing.get("analysis_steps") or {}).get("peak_detection") or {})
    similarity_matching = copy.deepcopy((processing.get("analysis_steps") or {}).get("similarity_matching") or {})

    smoothed = _apply_spectral_smoothing(signal, smoothing)
    baseline_curve = _estimate_spectral_baseline(axis, smoothed, baseline)
    corrected = smoothed - baseline_curve
    normalized_signal = _normalize_spectral_signal(corrected, normalization)
    observed_peaks = _detect_spectral_peaks(axis, normalized_signal, peak_detection)

    manager = get_reference_library_manager()
    library_context = manager.library_context(analysis_type)
    references = _resolve_spectral_references(dataset=dataset, analysis_type=analysis_type, processing=processing)
    ranked_matches = _rank_spectral_matches(
        axis=axis,
        normalized_signal=normalized_signal,
        observed_peaks=observed_peaks,
        references=references,
        matching_config=similarity_matching,
        peak_config=peak_detection,
    )

    minimum_score = float(similarity_matching.get("minimum_score") or 0.45)
    top_match = ranked_matches[0] if ranked_matches else None
    matched = bool(top_match) and float(top_match["normalized_score"]) >= minimum_score
    match_status = "matched" if matched else "no_match"
    top_score = float(top_match["normalized_score"]) if top_match else 0.0
    confidence_band = top_match["confidence_band"] if matched and top_match else "no_match"
    top_provider = str(top_match.get("library_provider") or "") if top_match else ""
    top_package = str(top_match.get("library_package") or "") if top_match else ""
    top_version = str(top_match.get("library_version") or "") if top_match else ""
    caution_payload = (
        {}
        if matched
        else {
            "code": "spectral_no_match",
            "message": "No reference candidate met the minimum similarity threshold.",
            "minimum_score": minimum_score,
            "top_candidate_score": round(top_score, 4),
        }
    )

    processing = update_method_context(
        processing,
        {
            "batch_run_id": batch_run_id or "",
            "batch_template_runner": "compare_workspace",
            "reference_candidate_count": len(references),
            "matching_metric": "cosine_prerank_then_pearson_peak_overlap",
            "matching_top_n": int(similarity_matching.get("top_n") or 3),
            "matching_minimum_score": minimum_score,
            "library_sync_mode": library_context["library_sync_mode"],
            "library_cache_status": library_context["library_cache_status"],
            "library_reference_package_count": library_context["reference_package_count"],
            "library_reference_candidate_count": library_context["reference_candidate_count"],
        },
        analysis_type=analysis_type,
    )
    validation = validate_thermal_dataset(dataset, analysis_type=analysis_type, processing=processing)
    provenance = build_result_provenance(
        dataset=dataset,
        dataset_key=dataset_key,
        analysis_history=analysis_history,
        app_version=app_version,
        analyst_name=analyst_name,
        extra={
            "batch_run_id": batch_run_id,
            "batch_runner": "compare_workspace",
            "analysis_type": analysis_type,
            "match_status": match_status,
            "reference_candidate_count": len(references),
            "library_provider": top_provider,
            "library_package": top_package,
            "library_version": top_version,
            "library_sync_mode": library_context["library_sync_mode"],
            "library_cache_status": library_context["library_cache_status"],
        },
    )

    summary = {
        "peak_count": len(observed_peaks),
        "match_status": match_status,
        "candidate_count": len(ranked_matches),
        "top_match_id": top_match["candidate_id"] if matched and top_match else None,
        "top_match_name": top_match["candidate_name"] if matched and top_match else None,
        "top_match_score": round(top_score, 4),
        "confidence_band": confidence_band,
        "caution_code": caution_payload.get("code", ""),
        "caution_message": caution_payload.get("message", ""),
        "library_provider": top_provider,
        "library_package": top_package,
        "library_version": top_version,
        "library_sync_mode": library_context["library_sync_mode"],
        "library_cache_status": library_context["library_cache_status"],
        "library_reference_package_count": library_context["reference_package_count"],
        "library_reference_candidate_count": library_context["reference_candidate_count"],
    }
    rows = [
        {
            "rank": item["rank"],
            "candidate_id": item["candidate_id"],
            "candidate_name": item["candidate_name"],
            "normalized_score": item["normalized_score"],
            "confidence_band": item["confidence_band"],
            "library_provider": item.get("library_provider") or "",
            "library_package": item.get("library_package") or "",
            "library_version": item.get("library_version") or "",
            "evidence": item["evidence"],
        }
        for item in ranked_matches
    ]
    validation = enrich_spectral_result_validation(
        validation,
        analysis_type=analysis_type,
        summary=summary,
        rows=rows,
    )
    record = serialize_spectral_result(
        dataset_key,
        dataset,
        analysis_type=analysis_type,
        summary=summary,
        rows=rows,
        status="stable",
        artifacts={},
        processing=processing,
        provenance=provenance,
        validation=validation,
        review={
            "commercial_scope": f"stable_{analysis_type.lower()}",
            "batch_runner": "compare_workspace",
            "caution": caution_payload,
        },
    )
    state = {
        "axis": axis.tolist(),
        "smoothed": smoothed.tolist(),
        "baseline": baseline_curve.tolist(),
        "corrected": corrected.tolist(),
        "normalized": normalized_signal.tolist(),
        "peaks": observed_peaks,
        "matches": ranked_matches,
        "processing": processing,
    }

    return {
        "status": "saved",
        "analysis_type": analysis_type,
        "dataset_key": dataset_key,
        "processing": processing,
        "validation": validation,
        "record": record,
        "state": state,
        "summary_row": _make_summary_row(
            dataset_key=dataset_key,
            dataset=dataset,
            analysis_type=analysis_type,
            processing=processing,
            validation=validation,
            execution_status="saved",
            record=record,
            failure_reason="",
        ),
    }


def _coerce_optional_float(value: Any, default: float | None = None) -> float | None:
    if value in (None, ""):
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if not np.isfinite(parsed):
        return default
    return parsed


def _coerce_positive_float(value: Any, default: float) -> float:
    parsed = _coerce_optional_float(value, default)
    if parsed is None or parsed <= 0.0:
        return default
    return float(parsed)


def _coerce_positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if parsed < 1:
        return default
    return parsed


def _resolve_odd_window(window: int, sample_count: int, *, minimum: int = 3) -> int:
    resolved = max(int(window), minimum)
    if resolved % 2 == 0:
        resolved += 1
    max_allowed = sample_count if sample_count % 2 == 1 else sample_count - 1
    if max_allowed < minimum:
        return minimum
    return min(resolved, max_allowed)


def _apply_xrd_smoothing(signal: np.ndarray, config: Mapping[str, Any]) -> np.ndarray:
    method = str(config.get("method") or "savgol").strip().lower()
    if method in {"none", "off"}:
        return signal.copy()
    if method in {"moving_average", "mean"}:
        return _apply_spectral_smoothing(signal, config)

    window = _resolve_odd_window(
        _coerce_positive_int(config.get("window_length"), 11),
        signal.size,
    )
    polyorder = _coerce_positive_int(config.get("polyorder"), 3)
    if polyorder >= window:
        polyorder = max(1, window - 2)
    return savgol_filter(signal, window_length=window, polyorder=polyorder, mode="interp")


def _rolling_minimum(signal: np.ndarray, window: int) -> np.ndarray:
    half = window // 2
    padded = np.pad(signal, (half, half), mode="edge")
    slices = [padded[index:index + signal.size] for index in range(window)]
    return np.min(np.vstack(slices), axis=0)


def _estimate_xrd_baseline(signal: np.ndarray, config: Mapping[str, Any]) -> np.ndarray:
    method = str(config.get("method") or "rolling_minimum").strip().lower()
    if method in {"none", "off"}:
        return np.zeros_like(signal)
    if method in {"linear", "asls"}:
        return np.linspace(float(signal[0]), float(signal[-1]), num=signal.size, endpoint=True)

    window = _resolve_odd_window(
        _coerce_positive_int(config.get("window_length"), 31),
        signal.size,
    )
    baseline = _rolling_minimum(signal, window)
    smooth_window = _resolve_odd_window(
        _coerce_positive_int(config.get("smoothing_window"), 9),
        signal.size,
    )
    if smooth_window >= 3:
        kernel = np.ones(smooth_window, dtype=float) / float(smooth_window)
        pad = smooth_window // 2
        padded = np.pad(baseline, (pad, pad), mode="edge")
        baseline = np.convolve(padded, kernel, mode="valid")
    return baseline


def _detect_xrd_peaks(
    axis: np.ndarray,
    corrected_signal: np.ndarray,
    config: Mapping[str, Any],
) -> tuple[list[dict[str, float]], dict[str, Any]]:
    prominence = _coerce_positive_float(config.get("prominence"), 0.08)
    distance = _coerce_positive_int(config.get("distance"), 6)
    width = _coerce_positive_int(config.get("width"), 2)
    max_peaks = _coerce_positive_int(config.get("max_peaks"), 12)

    peak_indices, properties = find_peaks(
        corrected_signal,
        prominence=prominence,
        distance=distance,
        width=width,
    )
    prominences = np.asarray(properties.get("prominences", []), dtype=float)
    widths = np.asarray(properties.get("widths", []), dtype=float)
    if peak_indices.size == 0:
        return [], {
            "method": "scipy_find_peaks",
            "prominence": prominence,
            "distance": distance,
            "width": width,
            "max_peaks": max_peaks,
            "peak_ranking": "prominence_desc_then_position_asc",
        }

    ranking = sorted(
        range(len(peak_indices)),
        key=lambda idx: (-float(prominences[idx]), float(axis[peak_indices[idx]])),
    )
    selected = ranking[:max_peaks]
    peaks: list[dict[str, float]] = []
    for rank, index in enumerate(selected, start=1):
        peak_index = int(peak_indices[index])
        peaks.append(
            {
                "rank": rank,
                "position": float(axis[peak_index]),
                "intensity": float(corrected_signal[peak_index]),
                "prominence": float(prominences[index]),
                "width": float(widths[index]) if index < len(widths) else 0.0,
            }
        )

    return peaks, {
        "method": "scipy_find_peaks",
        "prominence": prominence,
        "distance": distance,
        "width": width,
        "max_peaks": max_peaks,
        "peak_ranking": "prominence_desc_then_position_asc",
    }


def _coerce_unit_interval(value: Any, default: float) -> float:
    parsed = _coerce_optional_float(value, default)
    if parsed is None:
        return float(default)
    return float(max(0.0, min(1.0, parsed)))


def _resolve_xrd_matching_config(processing: Mapping[str, Any]) -> dict[str, Any]:
    method_context = (processing.get("method_context") or {}) if isinstance(processing, Mapping) else {}
    tolerance_deg = _coerce_positive_float(method_context.get("xrd_match_tolerance_deg"), 0.28)
    top_n = _coerce_positive_int(method_context.get("xrd_match_top_n"), 5)
    minimum_score = _coerce_unit_interval(method_context.get("xrd_match_minimum_score"), 0.42)
    intensity_weight = _coerce_unit_interval(method_context.get("xrd_match_intensity_weight"), 0.35)
    major_peak_fraction = _coerce_unit_interval(method_context.get("xrd_match_major_peak_fraction"), 0.4)
    return {
        "metric": str(method_context.get("xrd_match_metric") or "peak_overlap_weighted"),
        "tolerance_deg": tolerance_deg,
        "top_n": top_n,
        "minimum_score": minimum_score,
        "intensity_weight": intensity_weight,
        "major_peak_fraction": major_peak_fraction,
    }


def _extract_xrd_reference_peaks(entry: Mapping[str, Any]) -> list[dict[str, float]]:
    raw_peaks = entry.get("peaks") or entry.get("reference_peaks") or []
    normalized: list[dict[str, float]] = []
    if isinstance(raw_peaks, list):
        for item in raw_peaks:
            if not isinstance(item, Mapping):
                continue
            position = _coerce_optional_float(
                item.get("position")
                or item.get("two_theta")
                or item.get("x")
                or item.get("temperature")
            )
            if position is None:
                continue
            intensity = _coerce_positive_float(
                item.get("intensity")
                or item.get("relative_intensity")
                or item.get("signal"),
                1.0,
            )
            normalized.append({"position": float(position), "intensity": float(intensity)})

    if not normalized:
        positions = _to_float_array(entry.get("peak_positions") or entry.get("positions") or entry.get("two_theta"))
        intensities = _to_float_array(entry.get("peak_intensities") or entry.get("intensities") or entry.get("signal"))
        if positions is None:
            return []
        if intensities is None or intensities.size != positions.size:
            intensities = np.ones_like(positions, dtype=float)
        for position, intensity in zip(positions, intensities):
            normalized.append(
                {
                    "position": float(position),
                    "intensity": float(max(float(intensity), 1e-9)),
                }
            )

    normalized.sort(key=lambda item: float(item["position"]))
    return normalized


def _resolve_xrd_references(
    *,
    dataset,
    processing: Mapping[str, Any],
) -> list[dict[str, Any]]:
    metadata = getattr(dataset, "metadata", {}) or {}
    method_context = (processing.get("method_context") or {}) if isinstance(processing, Mapping) else {}
    raw_references = (
        metadata.get("xrd_reference_library")
        or metadata.get("reference_library")
        or method_context.get("xrd_reference_library")
        or []
    )
    normalized: list[dict[str, Any]] = []
    if isinstance(raw_references, list):
        for index, entry in enumerate(raw_references, start=1):
            if not isinstance(entry, Mapping):
                continue
            peaks = _extract_xrd_reference_peaks(entry)
            if not peaks:
                continue
            candidate_id = str(entry.get("id") or entry.get("candidate_id") or f"xrd_reference_{index}")
            candidate_name = str(entry.get("name") or entry.get("candidate_name") or candidate_id)
            normalized.append(
                _reference_row(
                    candidate_id=candidate_id,
                    candidate_name=candidate_name,
                    priority=1000,
                    provider=str(entry.get("provider") or "dataset"),
                    package_id=str(entry.get("package_id") or "dataset_metadata"),
                    package_version=str(entry.get("package_version") or "embedded"),
                    attribution=str(entry.get("attribution") or ""),
                    source_url=str(entry.get("source_url") or ""),
                    peaks=peaks,
                )
            )
    manager = get_reference_library_manager()
    for entry in manager.load_entries("XRD"):
        peaks = _extract_xrd_reference_peaks(entry)
        if not peaks:
            continue
        normalized.append(
            _reference_row(
                candidate_id=str(entry.get("candidate_id") or ""),
                candidate_name=str(entry.get("candidate_name") or ""),
                priority=int(entry.get("priority") or 0),
                provider=str(entry.get("provider") or ""),
                package_id=str(entry.get("package_id") or ""),
                package_version=str(entry.get("package_version") or ""),
                attribution=str(entry.get("attribution") or ""),
                source_url=str(entry.get("source_url") or ""),
                peaks=peaks,
            )
        )
    normalized.sort(
        key=lambda item: (
            -int(item.get("priority") or 0),
            str(item.get("provider") or ""),
            str(item.get("candidate_id") or ""),
        )
    )
    return normalized


def _match_xrd_reference_peaks(
    observed_peaks: list[dict[str, float]],
    reference_peaks: list[dict[str, float]],
    *,
    tolerance_deg: float,
) -> tuple[list[dict[str, float]], list[int]]:
    if not observed_peaks or not reference_peaks:
        return [], list(range(len(reference_peaks)))

    used_observed: set[int] = set()
    matches: list[dict[str, float]] = []
    unmatched_reference_indices: list[int] = []
    for ref_index, reference in enumerate(reference_peaks):
        reference_position = float(reference["position"])
        best_observed_index: int | None = None
        best_delta: float | None = None
        for obs_index, observed in enumerate(observed_peaks):
            if obs_index in used_observed:
                continue
            delta = abs(float(observed["position"]) - reference_position)
            if best_delta is None or delta < best_delta:
                best_delta = delta
                best_observed_index = obs_index
        if best_delta is None or best_delta > tolerance_deg or best_observed_index is None:
            unmatched_reference_indices.append(ref_index)
            continue
        used_observed.add(best_observed_index)
        observed = observed_peaks[best_observed_index]
        matches.append(
            {
                "reference_position": reference_position,
                "observed_position": float(observed["position"]),
                "delta_position": float(best_delta),
                "reference_intensity": float(reference["intensity"]),
                "observed_intensity": float(observed.get("intensity", 0.0)),
            }
        )
    return matches, unmatched_reference_indices


def _rank_xrd_phase_candidates(
    *,
    observed_peaks: list[dict[str, float]],
    references: list[dict[str, Any]],
    matching_config: Mapping[str, Any],
) -> list[dict[str, Any]]:
    tolerance_deg = _coerce_positive_float(matching_config.get("tolerance_deg"), 0.28)
    top_n = _coerce_positive_int(matching_config.get("top_n"), 5)
    minimum_score = _coerce_unit_interval(matching_config.get("minimum_score"), 0.42)
    intensity_weight = _coerce_unit_interval(matching_config.get("intensity_weight"), 0.35)
    major_peak_fraction = _coerce_unit_interval(matching_config.get("major_peak_fraction"), 0.4)
    metric = str(matching_config.get("metric") or "peak_overlap_weighted")

    observed_scale = max([float(item.get("intensity", 0.0)) for item in observed_peaks] + [1.0])
    prefiltered: list[dict[str, Any]] = []
    prefilter_tolerance = tolerance_deg * 2.0
    prefilter_limit = max(top_n * 10, 20)
    for reference in references:
        reference_peaks = [dict(item) for item in reference.get("peaks") or [] if isinstance(item, Mapping)]
        loose_matches, _ = _match_xrd_reference_peaks(
            observed_peaks=observed_peaks,
            reference_peaks=reference_peaks,
            tolerance_deg=prefilter_tolerance,
        )
        prefiltered.append(
            {
                "reference": reference,
                "shared_peak_count": len(loose_matches),
            }
        )
    prefiltered.sort(
        key=lambda item: (
            -int(item["shared_peak_count"]),
            -int((item["reference"] or {}).get("priority") or 0),
            str((item["reference"] or {}).get("candidate_id") or ""),
        )
    )
    ranked: list[dict[str, Any]] = []
    for candidate in prefiltered[:prefilter_limit]:
        reference = candidate["reference"]
        reference_peaks = [dict(item) for item in reference.get("peaks") or [] if isinstance(item, Mapping)]
        if not reference_peaks:
            continue

        matches, unmatched_indices = _match_xrd_reference_peaks(
            observed_peaks=observed_peaks,
            reference_peaks=reference_peaks,
            tolerance_deg=tolerance_deg,
        )
        reference_scale = max([float(item.get("intensity", 0.0)) for item in reference_peaks] + [1.0])
        total_reference_weight = sum(
            max(float(item.get("intensity", 0.0)) / reference_scale, 0.0)
            for item in reference_peaks
        )
        matched_weight = 0.0
        for item in matches:
            ref_weight = max(float(item["reference_intensity"]) / reference_scale, 0.0)
            obs_weight = max(float(item["observed_intensity"]) / observed_scale, 0.0)
            matched_weight += min(ref_weight, obs_weight)

        shared_peak_count = len(matches)
        weighted_overlap_score = (
            float(matched_weight / max(total_reference_weight, 1e-9))
            if total_reference_weight > 0.0
            else 0.0
        )
        coverage_ratio = float(shared_peak_count / max(len(reference_peaks), 1))
        mean_delta = (
            float(sum(item["delta_position"] for item in matches) / shared_peak_count)
            if shared_peak_count > 0
            else None
        )
        delta_score = (
            float(max(0.0, 1.0 - (mean_delta / tolerance_deg)))
            if mean_delta is not None and tolerance_deg > 0.0
            else 0.0
        )

        max_reference_intensity = max(float(item.get("intensity", 0.0)) for item in reference_peaks)
        major_threshold = major_peak_fraction * max_reference_intensity
        major_reference_indices = [
            idx for idx, item in enumerate(reference_peaks)
            if float(item.get("intensity", 0.0)) >= major_threshold
        ]
        unmatched_major_positions = [
            float(reference_peaks[idx]["position"])
            for idx in unmatched_indices
            if idx in major_reference_indices
        ]
        major_penalty = float(len(unmatched_major_positions) / max(len(major_reference_indices), 1))

        delta_weight = max(0.0, 0.45 - intensity_weight)
        score = (0.5 * coverage_ratio) + (intensity_weight * weighted_overlap_score) + (delta_weight * delta_score)
        score -= 0.15 * major_penalty
        score = float(max(0.0, min(1.0, score)))
        confidence_band = _confidence_band(score, minimum_score)
        ranked.append(
            {
                "candidate_id": reference["candidate_id"],
                "candidate_name": reference["candidate_name"],
                "normalized_score": round(score, 4),
                "confidence_band": confidence_band,
                "library_provider": reference.get("provider") or "",
                "library_package": reference.get("package_id") or "",
                "library_version": reference.get("package_version") or "",
                "evidence": {
                    "metric": metric,
                    "tolerance_deg": tolerance_deg,
                    "observed_peak_count": len(observed_peaks),
                    "reference_peak_count": len(reference_peaks),
                    "shared_peak_count": shared_peak_count,
                    "weighted_overlap_score": round(weighted_overlap_score, 4),
                    "coverage_ratio": round(coverage_ratio, 4),
                    "mean_delta_position": round(mean_delta, 4) if mean_delta is not None else None,
                    "unmatched_major_peak_count": len(unmatched_major_positions),
                    "unmatched_major_peak_positions": [round(item, 4) for item in sorted(unmatched_major_positions)],
                    "library_provider": reference.get("provider") or "",
                    "library_package": reference.get("package_id") or "",
                    "library_version": reference.get("package_version") or "",
                },
            }
        )

    ranked.sort(
        key=lambda item: (
            -float(item["normalized_score"]),
            -int(item["evidence"]["shared_peak_count"]),
            float(item["evidence"]["mean_delta_position"] if item["evidence"]["mean_delta_position"] is not None else 1e9),
            str(item.get("library_provider") or ""),
            str(item["candidate_id"]),
        )
    )
    trimmed = ranked[:top_n]
    for rank, item in enumerate(trimmed, start=1):
        item["rank"] = rank
    return trimmed


def _execute_xrd_batch(
    *,
    dataset_key: str,
    dataset,
    processing: dict[str, Any],
    analysis_history: list[dict[str, Any]] | None,
    analyst_name: str | None,
    app_version: str | None,
    batch_run_id: str | None,
) -> dict[str, Any]:
    axis = np.asarray(dataset.data["temperature"], dtype=float)
    signal = np.asarray(dataset.data["signal"], dtype=float)
    axis, signal = _sorted_axis_signal(axis, signal)

    axis_normalization = copy.deepcopy((processing.get("signal_pipeline") or {}).get("axis_normalization") or {})
    smoothing = copy.deepcopy((processing.get("signal_pipeline") or {}).get("smoothing") or {})
    baseline = copy.deepcopy((processing.get("signal_pipeline") or {}).get("baseline") or {})
    peak_detection = copy.deepcopy((processing.get("analysis_steps") or {}).get("peak_detection") or {})

    axis_min = _coerce_optional_float(axis_normalization.get("axis_min"))
    axis_max = _coerce_optional_float(axis_normalization.get("axis_max"))
    if axis_min is not None or axis_max is not None:
        mask = np.ones(axis.shape[0], dtype=bool)
        if axis_min is not None:
            mask &= axis >= float(axis_min)
        if axis_max is not None:
            mask &= axis <= float(axis_max)
        if int(np.count_nonzero(mask)) >= 3:
            axis = axis[mask]
            signal = signal[mask]

    smoothed = _apply_xrd_smoothing(signal, smoothing)
    baseline_curve = _estimate_xrd_baseline(smoothed, baseline)
    corrected = np.maximum(smoothed - baseline_curve, 0.0)
    peaks, resolved_peak_detection = _detect_xrd_peaks(axis, corrected, peak_detection)
    manager = get_reference_library_manager()
    library_context = manager.library_context("XRD")
    references = _resolve_xrd_references(dataset=dataset, processing=processing)
    matching_config = _resolve_xrd_matching_config(processing)
    ranked_matches = _rank_xrd_phase_candidates(
        observed_peaks=peaks,
        references=references,
        matching_config=matching_config,
    )

    minimum_score = float(matching_config["minimum_score"])
    top_match = ranked_matches[0] if ranked_matches else None
    top_score = float(top_match["normalized_score"]) if top_match else 0.0
    matched = bool(top_match) and top_score >= minimum_score and top_match["confidence_band"] != "no_match"
    top_provider = str(top_match.get("library_provider") or "") if top_match else ""
    top_package = str(top_match.get("library_package") or "") if top_match else ""
    top_version = str(top_match.get("library_version") or "") if top_match else ""
    caution_payload = {}
    if not references:
        match_status = "not_run"
        confidence_band = "not_run"
        caution_payload = {
            "code": "xrd_reference_library_unavailable",
            "message": "No XRD reference candidates are installed or embedded; qualitative phase matching was not run.",
            "minimum_score": minimum_score,
            "top_phase_score": round(top_score, 4),
        }
    else:
        match_status = "matched" if matched else "no_match"
        confidence_band = top_match["confidence_band"] if matched and top_match else "no_match"
        if not matched:
            caution_payload = {
                "code": "xrd_no_match",
                "message": "No reference phase candidate met the minimum qualitative matching threshold.",
                "minimum_score": minimum_score,
                "top_phase_score": round(top_score, 4),
            }
        elif confidence_band == "low":
            caution_payload = {
                "code": "xrd_low_confidence",
                "message": "Top XRD candidate is low confidence; review evidence before interpretation.",
                "minimum_score": minimum_score,
                "top_phase_score": round(top_score, 4),
            }
        if library_context["reference_candidate_count"] <= 0 and not caution_payload:
            caution_payload = {
                "code": "xrd_reference_coverage_limited",
                "message": "Installed XRD library coverage is limited; treat qualitative candidate ranking with caution.",
                "minimum_score": minimum_score,
                "top_phase_score": round(top_score, 4),
            }

    resolved_axis_normalization = {
        "sort_axis": bool(axis_normalization.get("sort_axis", True)),
        "deduplicate": str(axis_normalization.get("deduplicate") or "first"),
        "axis_min": axis_min,
        "axis_max": axis_max,
    }
    processing = update_processing_step(processing, "axis_normalization", resolved_axis_normalization, analysis_type="XRD")
    processing = update_processing_step(processing, "smoothing", smoothing, analysis_type="XRD")
    processing = update_processing_step(processing, "baseline", baseline, analysis_type="XRD")
    processing = update_processing_step(processing, "peak_detection", resolved_peak_detection, analysis_type="XRD")

    processing = update_method_context(
        processing,
        {
            "batch_run_id": batch_run_id or "",
            "batch_template_runner": "compare_workspace",
            "xrd_axis_role": dataset.metadata.get("xrd_axis_role") or "two_theta",
            "xrd_axis_unit": (dataset.metadata.get("xrd_axis_unit") or (dataset.units or {}).get("temperature") or "degree_2theta"),
            "xrd_wavelength_angstrom": dataset.metadata.get("xrd_wavelength_angstrom"),
            "xrd_preprocessing_order": ["axis_normalization", "smoothing", "baseline", "peak_detection"],
            "xrd_peak_detection_method": resolved_peak_detection["method"],
            "xrd_peak_prominence": resolved_peak_detection["prominence"],
            "xrd_peak_distance": resolved_peak_detection["distance"],
            "xrd_peak_width": resolved_peak_detection["width"],
            "xrd_peak_max": resolved_peak_detection["max_peaks"],
            "xrd_peak_ranking": resolved_peak_detection["peak_ranking"],
            "xrd_peak_count": len(peaks),
            "xrd_reference_candidate_count": len(references),
            "xrd_match_metric": matching_config["metric"],
            "xrd_match_tolerance_deg": matching_config["tolerance_deg"],
            "xrd_match_top_n": matching_config["top_n"],
            "xrd_match_minimum_score": matching_config["minimum_score"],
            "xrd_match_intensity_weight": matching_config["intensity_weight"],
            "xrd_match_major_peak_fraction": matching_config["major_peak_fraction"],
            "library_sync_mode": library_context["library_sync_mode"],
            "library_cache_status": library_context["library_cache_status"],
            "library_reference_package_count": library_context["reference_package_count"],
            "library_reference_candidate_count": library_context["reference_candidate_count"],
        },
        analysis_type="XRD",
    )
    validation = validate_thermal_dataset(dataset, analysis_type="XRD", processing=processing)
    provenance = build_result_provenance(
        dataset=dataset,
        dataset_key=dataset_key,
        analysis_history=analysis_history,
        app_version=app_version,
        analyst_name=analyst_name,
        extra={
            "batch_run_id": batch_run_id,
            "batch_runner": "compare_workspace",
            "analysis_type": "XRD",
            "peak_count": len(peaks),
            "match_status": match_status,
            "reference_candidate_count": len(references),
            "library_provider": top_provider,
            "library_package": top_package,
            "library_version": top_version,
            "library_sync_mode": library_context["library_sync_mode"],
            "library_cache_status": library_context["library_cache_status"],
        },
    )

    summary = {
        "peak_count": len(peaks),
        "match_status": match_status,
        "candidate_count": len(ranked_matches),
        "top_phase_id": top_match["candidate_id"] if matched and top_match else None,
        "top_phase": top_match["candidate_name"] if matched and top_match else None,
        "top_phase_score": round(top_score, 4),
        "top_match_id": top_match["candidate_id"] if matched and top_match else None,
        "top_match_name": top_match["candidate_name"] if matched and top_match else None,
        "top_match_score": round(top_score, 4),
        "confidence_band": confidence_band,
        "caution_code": str(caution_payload.get("code") or ""),
        "caution_message": str(caution_payload.get("message") or ""),
        "reference_candidate_count": len(references),
        "match_tolerance_deg": matching_config["tolerance_deg"],
        "match_metric": matching_config["metric"],
        "library_provider": top_provider,
        "library_package": top_package,
        "library_version": top_version,
        "library_sync_mode": library_context["library_sync_mode"],
        "library_cache_status": library_context["library_cache_status"],
        "library_reference_package_count": library_context["reference_package_count"],
        "library_reference_candidate_count": library_context["reference_candidate_count"],
    }
    rows = [
        {
            "rank": item["rank"],
            "candidate_id": item["candidate_id"],
            "candidate_name": item["candidate_name"],
            "normalized_score": item["normalized_score"],
            "confidence_band": item["confidence_band"],
            "library_provider": item.get("library_provider") or "",
            "library_package": item.get("library_package") or "",
            "library_version": item.get("library_version") or "",
            "evidence": item["evidence"],
        }
        for item in ranked_matches
    ]
    validation = enrich_xrd_result_validation(
        validation,
        summary=summary,
        rows=rows,
    )
    record = serialize_xrd_result(
        dataset_key,
        dataset,
        summary=summary,
        rows=rows,
        status="stable",
        artifacts={},
        processing=processing,
        provenance=provenance,
        validation=validation,
        review={
            "commercial_scope": "stable_xrd",
            "batch_runner": "compare_workspace",
            "caution": caution_payload,
        },
    )
    state = {
        "axis": axis.tolist(),
        "smoothed": smoothed.tolist(),
        "baseline": baseline_curve.tolist(),
        "corrected": corrected.tolist(),
        "peaks": peaks,
        "matches": ranked_matches,
        "processing": processing,
    }
    return {
        "status": "saved",
        "analysis_type": "XRD",
        "dataset_key": dataset_key,
        "processing": processing,
        "validation": validation,
        "record": record,
        "state": state,
        "summary_row": _make_summary_row(
            dataset_key=dataset_key,
            dataset=dataset,
            analysis_type="XRD",
            processing=processing,
            validation=validation,
            execution_status="saved",
            record=record,
            failure_reason="",
        ),
    }


def _make_summary_row(
    *,
    dataset_key: str,
    dataset,
    analysis_type: str,
    processing: Mapping[str, Any],
    validation: Mapping[str, Any],
    execution_status: str,
    record: Mapping[str, Any] | None = None,
    failure_reason: str = "",
) -> dict[str, Any]:
    method_context = (processing.get("method_context") or {}) if isinstance(processing, Mapping) else {}
    summary = (record or {}).get("summary") or {}
    row = {
        "dataset_key": dataset_key,
        "analysis_type": analysis_type,
        "sample_name": (dataset.metadata or {}).get("sample_name") or dataset_key,
        "workflow_template_id": processing.get("workflow_template_id"),
        "workflow_template": processing.get("workflow_template"),
        "execution_status": execution_status,
        "validation_status": validation.get("status"),
        "warning_count": len(validation.get("warnings") or []),
        "issue_count": len(validation.get("issues") or []),
        "calibration_state": method_context.get("calibration_state") or (validation.get("checks") or {}).get("calibration_state"),
        "reference_state": method_context.get("reference_state") or (validation.get("checks") or {}).get("reference_state"),
        "result_id": (record or {}).get("id"),
        "failure_reason": failure_reason,
        "message": failure_reason,
        "error_id": "",
    }
    row.update(summary)
    return row


def normalize_batch_summary_rows(summary_rows: list[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    """Return backward-compatible normalized batch-summary rows."""
    normalized_rows: list[dict[str, Any]] = []
    for row in summary_rows or []:
        payload = dict(row or {})
        status = str(payload.get("execution_status") or "").strip().lower()
        if status == "error":
            status = "failed"
        if status not in _VALID_EXECUTION_STATUSES:
            status = "failed" if payload.get("error_id") else "blocked" if payload.get("issue_count") else "saved"
        failure_reason = payload.get("failure_reason")
        if failure_reason in (None, ""):
            failure_reason = payload.get("message", "")
        payload["execution_status"] = status
        payload["failure_reason"] = failure_reason or ""
        payload["message"] = payload["failure_reason"]
        payload["error_id"] = payload.get("error_id") or ""
        normalized_rows.append(payload)
    return normalized_rows


def summarize_batch_outcomes(summary_rows: list[Mapping[str, Any]] | None) -> dict[str, int]:
    """Return counts for normalized batch outcome categories."""
    rows = normalize_batch_summary_rows(summary_rows)
    return {
        "total": len(rows),
        "saved": sum(1 for row in rows if row["execution_status"] == "saved"),
        "blocked": sum(1 for row in rows if row["execution_status"] == "blocked"),
        "failed": sum(1 for row in rows if row["execution_status"] == "failed"),
    }


def filter_batch_summary_rows(
    summary_rows: list[Mapping[str, Any]] | None,
    *,
    execution_status: str = "all",
) -> list[dict[str, Any]]:
    """Filter normalized batch-summary rows by outcome label."""
    rows = normalize_batch_summary_rows(summary_rows)
    token = str(execution_status or "all").strip().lower()
    if token in {"all", ""}:
        return rows
    return [row for row in rows if row["execution_status"] == token]
