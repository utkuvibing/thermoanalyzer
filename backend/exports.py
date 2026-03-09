"""Export/report preparation helpers for desktop backend endpoints."""

from __future__ import annotations

import base64
import copy
from typing import Any

from backend.detail import normalize_compare_workspace
from backend.workspace import summarize_result
from core.report_generator import generate_csv_summary, generate_docx_report
from core.result_serialization import split_valid_results


def _selected_records(results: dict[str, dict[str, Any]], selected_result_ids: list[str] | None) -> dict[str, dict[str, Any]]:
    if not results:
        raise ValueError("No valid saved results are available for export/report.")

    if not selected_result_ids:
        return dict(results)

    selected: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for raw_id in selected_result_ids:
        result_id = str(raw_id)
        if result_id in selected:
            continue
        record = results.get(result_id)
        if record is None:
            missing.append(result_id)
            continue
        selected[result_id] = record

    if missing:
        raise ValueError(f"Unknown selected_result_ids: {', '.join(missing)}")
    if not selected:
        raise ValueError("No exportable saved results selected.")
    return selected


def build_export_preparation(state: dict[str, Any]) -> dict[str, Any]:
    valid_results, issues = split_valid_results((state.get("results") or {}))
    items = [summarize_result(record) for record in valid_results.values()]
    items.sort(key=lambda item: item.id)
    branding = copy.deepcopy(state.get("branding") or {})
    return {
        "exportable_results": items,
        "skipped_record_issues": issues,
        "supported_outputs": ["results_csv", "report_docx"],
        "branding": {
            "report_title": branding.get("report_title") or "ThermoAnalyzer Professional Report",
            "company_name": branding.get("company_name") or "",
            "lab_name": branding.get("lab_name") or "",
            "analyst_name": branding.get("analyst_name") or "",
        },
        "compare_workspace": normalize_compare_workspace(state),
    }


def generate_results_csv_artifact(state: dict[str, Any], *, selected_result_ids: list[str] | None) -> dict[str, Any]:
    valid_results, issues = split_valid_results((state.get("results") or {}))
    selected = _selected_records(valid_results, selected_result_ids)
    csv_text = generate_csv_summary(selected)
    csv_base64 = base64.b64encode(csv_text.encode("utf-8")).decode("ascii")
    return {
        "output_type": "results_csv",
        "file_name": "thermoanalyzer_results.csv",
        "mime_type": "text/csv",
        "included_result_ids": list(selected.keys()),
        "skipped_record_issues": issues,
        "artifact_base64": csv_base64,
    }


def generate_report_docx_artifact(state: dict[str, Any], *, selected_result_ids: list[str] | None) -> dict[str, Any]:
    valid_results, issues = split_valid_results((state.get("results") or {}))
    selected = _selected_records(valid_results, selected_result_ids)
    docx_bytes = generate_docx_report(
        results=selected,
        datasets=state.get("datasets") or {},
        figures=state.get("figures") or {},
        branding=state.get("branding") or {},
        comparison_workspace=state.get("comparison_workspace") or {},
        license_state=state.get("license_state") or {},
    )
    docx_base64 = base64.b64encode(docx_bytes).decode("ascii")
    return {
        "output_type": "report_docx",
        "file_name": "thermoanalyzer_report.docx",
        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "included_result_ids": list(selected.keys()),
        "skipped_record_issues": issues,
        "artifact_base64": docx_base64,
    }
