"""HTTP client for the co-located FastAPI backend.

Since Dash and FastAPI run in the same process, we use httpx to call
the backend endpoints at localhost. The base URL is configurable for
testing and split-deployment scenarios.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

_BASE_URL = os.environ.get("MATERIALSCOPE_API_URL", "http://127.0.0.1:8050")
_TOKEN = os.environ.get("MATERIALSCOPE_API_TOKEN", "")
_TIMEOUT = 60.0


def _headers() -> dict[str, str]:
    h: dict[str, str] = {"Accept": "application/json"}
    if _TOKEN:
        h["X-MaterialScope-Token"] = _TOKEN
        h["X-TA-Token"] = _TOKEN
    return h


def _client() -> httpx.Client:
    return httpx.Client(base_url=_BASE_URL, headers=_headers(), timeout=_TIMEOUT)


def _raise_with_detail(r: httpx.Response) -> None:
    """Like ``_raise_with_detail(r)`` but includes the backend error detail."""
    if r.is_success:
        return
    try:
        body = r.json().get("detail", r.text)
    except Exception:
        body = r.text
    raise httpx.HTTPStatusError(
        f"{r.status_code} {r.reason_phrase}: {body}",
        request=r.request,
        response=r,
    )


def workspace_new() -> dict[str, Any]:
    with _client() as c:
        r = c.post("/workspace/new")
        _raise_with_detail(r)
        return r.json()


def workspace_summary(project_id: str) -> dict[str, Any]:
    with _client() as c:
        r = c.get(f"/workspace/{project_id}")
        _raise_with_detail(r)
        return r.json()


def workspace_datasets(project_id: str) -> dict[str, Any]:
    with _client() as c:
        r = c.get(f"/workspace/{project_id}/datasets")
        _raise_with_detail(r)
        return r.json()


def workspace_dataset_detail(project_id: str, dataset_key: str) -> dict[str, Any]:
    with _client() as c:
        r = c.get(f"/workspace/{project_id}/datasets/{dataset_key}")
        _raise_with_detail(r)
        return r.json()


def workspace_dataset_data(project_id: str, dataset_key: str) -> dict[str, Any]:
    with _client() as c:
        r = c.get(f"/workspace/{project_id}/datasets/{dataset_key}/data")
        _raise_with_detail(r)
        return r.json()


def workspace_delete_dataset(project_id: str, dataset_key: str) -> dict[str, Any]:
    with _client() as c:
        r = c.delete(f"/workspace/{project_id}/datasets/{dataset_key}")
        _raise_with_detail(r)
        return r.json()


def workspace_results(project_id: str) -> dict[str, Any]:
    with _client() as c:
        r = c.get(f"/workspace/{project_id}/results")
        _raise_with_detail(r)
        return r.json()


def workspace_result_detail(project_id: str, result_id: str) -> dict[str, Any]:
    with _client() as c:
        r = c.get(f"/workspace/{project_id}/results/{result_id}")
        _raise_with_detail(r)
        return r.json()


def analysis_state_curves(project_id: str, analysis_type: str, dataset_key: str) -> dict[str, Any]:
    with _client() as c:
        r = c.get(f"/workspace/{project_id}/analysis-state/{analysis_type}/{dataset_key}")
        _raise_with_detail(r)
        return r.json()


def workspace_context(project_id: str) -> dict[str, Any]:
    with _client() as c:
        r = c.get(f"/workspace/{project_id}/context")
        _raise_with_detail(r)
        return r.json()


def workspace_set_active_dataset(project_id: str, dataset_key: str) -> dict[str, Any]:
    with _client() as c:
        r = c.put(
            f"/workspace/{project_id}/active-dataset",
            json={"dataset_key": dataset_key},
        )
        _raise_with_detail(r)
        return r.json()


def dataset_import(
    project_id: str,
    file_name: str,
    file_base64: str,
    data_type: str | None = None,
    *,
    column_mapping: dict[str, str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with _client() as c:
        r = c.post(
            "/dataset/import",
            json={
                "project_id": project_id,
                "file_name": file_name,
                "file_base64": file_base64,
                "data_type": data_type,
                "column_mapping": column_mapping or {},
                "metadata": metadata or {},
            },
        )
        _raise_with_detail(r)
        return r.json()


def analysis_run(
    project_id: str,
    dataset_key: str,
    analysis_type: str,
    workflow_template_id: str | None = None,
    unit_mode: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "project_id": project_id,
        "dataset_key": dataset_key,
        "analysis_type": analysis_type,
    }
    if workflow_template_id:
        payload["workflow_template_id"] = workflow_template_id
    if unit_mode:
        payload["unit_mode"] = unit_mode
    with _client() as c:
        r = c.post("/analysis/run", json=payload)
        _raise_with_detail(r)
        return r.json()


def export_preparation(project_id: str) -> dict[str, Any]:
    with _client() as c:
        r = c.get(f"/workspace/{project_id}/exports/preparation")
        _raise_with_detail(r)
        return r.json()


def export_results_csv(
    project_id: str,
    selected_result_ids: list[str] | None = None,
) -> dict[str, Any]:
    with _client() as c:
        r = c.post(
            f"/workspace/{project_id}/exports/results-csv",
            json={"selected_result_ids": selected_result_ids},
        )
        _raise_with_detail(r)
        return r.json()


def export_results_xlsx(
    project_id: str,
    selected_result_ids: list[str] | None = None,
) -> dict[str, Any]:
    with _client() as c:
        r = c.post(
            f"/workspace/{project_id}/exports/results-xlsx",
            json={"selected_result_ids": selected_result_ids},
        )
        _raise_with_detail(r)
        return r.json()


def export_report_docx(
    project_id: str,
    selected_result_ids: list[str] | None = None,
    *,
    include_figures: bool = True,
) -> dict[str, Any]:
    with _client() as c:
        r = c.post(
            f"/workspace/{project_id}/exports/report-docx",
            json={
                "selected_result_ids": selected_result_ids,
                "include_figures": include_figures,
            },
        )
        _raise_with_detail(r)
        return r.json()


def export_report_pdf(
    project_id: str,
    selected_result_ids: list[str] | None = None,
    *,
    include_figures: bool = True,
) -> dict[str, Any]:
    with _client() as c:
        r = c.post(
            f"/workspace/{project_id}/exports/report-pdf",
            json={
                "selected_result_ids": selected_result_ids,
                "include_figures": include_figures,
            },
        )
        _raise_with_detail(r)
        return r.json()


def workspace_branding(project_id: str) -> dict[str, Any]:
    with _client() as c:
        r = c.get(f"/workspace/{project_id}/branding")
        _raise_with_detail(r)
        return r.json()


def update_workspace_branding(project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with _client() as c:
        r = c.put(f"/workspace/{project_id}/branding", json=payload)
        _raise_with_detail(r)
        return r.json()


def compare_workspace(project_id: str) -> dict[str, Any]:
    with _client() as c:
        r = c.get(f"/workspace/{project_id}/compare")
        _raise_with_detail(r)
        return r.json()


def workspace_batch_run(
    project_id: str,
    *,
    analysis_type: str,
    workflow_template_id: str | None = None,
    dataset_keys: list[str] | None = None,
) -> dict[str, Any]:
    """Run stable batch analysis for compare workspace (uses selected datasets when keys omitted)."""
    payload: dict[str, Any] = {"analysis_type": analysis_type}
    if workflow_template_id:
        payload["workflow_template_id"] = workflow_template_id
    if dataset_keys is not None:
        payload["dataset_keys"] = dataset_keys
    with _client() as c:
        r = c.post(f"/workspace/{project_id}/batch/run", json=payload)
        _raise_with_detail(r)
        return r.json()


def update_compare_workspace(
    project_id: str,
    *,
    analysis_type: str | None = None,
    selected_datasets: list[str] | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if analysis_type is not None:
        payload["analysis_type"] = analysis_type
    if selected_datasets is not None:
        payload["selected_datasets"] = selected_datasets
    if notes is not None:
        payload["notes"] = notes
    with _client() as c:
        r = c.put(f"/workspace/{project_id}/compare", json=payload)
        _raise_with_detail(r)
        return r.json()


def project_save(project_id: str) -> dict[str, Any]:
    with _client() as c:
        r = c.post("/project/save", json={"project_id": project_id})
        _raise_with_detail(r)
        return r.json()


def project_load(archive_base64: str) -> dict[str, Any]:
    with _client() as c:
        r = c.post("/project/load", json={"archive_base64": archive_base64})
        _raise_with_detail(r)
        return r.json()


def health() -> dict[str, Any]:
    with _client() as c:
        r = c.get("/health")
        _raise_with_detail(r)
        return r.json()
