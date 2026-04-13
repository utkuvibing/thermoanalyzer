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
        h["X-TA-Token"] = _TOKEN
    return h


def _client() -> httpx.Client:
    return httpx.Client(base_url=_BASE_URL, headers=_headers(), timeout=_TIMEOUT)


def workspace_new() -> dict[str, Any]:
    with _client() as c:
        r = c.post("/workspace/new")
        r.raise_for_status()
        return r.json()


def workspace_summary(project_id: str) -> dict[str, Any]:
    with _client() as c:
        r = c.get(f"/workspace/{project_id}")
        r.raise_for_status()
        return r.json()


def workspace_datasets(project_id: str) -> dict[str, Any]:
    with _client() as c:
        r = c.get(f"/workspace/{project_id}/datasets")
        r.raise_for_status()
        return r.json()


def workspace_results(project_id: str) -> dict[str, Any]:
    with _client() as c:
        r = c.get(f"/workspace/{project_id}/results")
        r.raise_for_status()
        return r.json()


def workspace_context(project_id: str) -> dict[str, Any]:
    with _client() as c:
        r = c.get(f"/workspace/{project_id}/context")
        r.raise_for_status()
        return r.json()


def dataset_import(
    project_id: str,
    file_name: str,
    file_base64: str,
    data_type: str = "auto",
) -> dict[str, Any]:
    with _client() as c:
        r = c.post(
            "/dataset/import",
            json={
                "project_id": project_id,
                "file_name": file_name,
                "file_base64": file_base64,
                "data_type": data_type,
            },
        )
        r.raise_for_status()
        return r.json()


def analysis_run(
    project_id: str,
    dataset_key: str,
    analysis_type: str,
    workflow_template_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "project_id": project_id,
        "dataset_key": dataset_key,
        "analysis_type": analysis_type,
    }
    if workflow_template_id:
        payload["workflow_template_id"] = workflow_template_id
    with _client() as c:
        r = c.post("/analysis/run", json=payload)
        r.raise_for_status()
        return r.json()


def export_preparation(project_id: str) -> dict[str, Any]:
    with _client() as c:
        r = c.get(f"/workspace/{project_id}/exports/preparation")
        r.raise_for_status()
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
        r.raise_for_status()
        return r.json()


def export_report_docx(
    project_id: str,
    selected_result_ids: list[str] | None = None,
) -> dict[str, Any]:
    with _client() as c:
        r = c.post(
            f"/workspace/{project_id}/exports/report-docx",
            json={"selected_result_ids": selected_result_ids},
        )
        r.raise_for_status()
        return r.json()


def project_save(project_id: str) -> dict[str, Any]:
    with _client() as c:
        r = c.post("/project/save", json={"project_id": project_id})
        r.raise_for_status()
        return r.json()


def project_load(archive_base64: str) -> dict[str, Any]:
    with _client() as c:
        r = c.post("/project/load", json={"archive_base64": archive_base64})
        r.raise_for_status()
        return r.json()


def health() -> dict[str, Any]:
    with _client() as c:
        r = c.get("/health")
        r.raise_for_status()
        return r.json()
