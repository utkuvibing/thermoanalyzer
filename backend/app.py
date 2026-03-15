"""FastAPI app for incremental ThermoAnalyzer desktop backend tranches."""

from __future__ import annotations

import base64
import binascii
import io
from datetime import datetime
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException

from backend import BACKEND_API_VERSION
from backend.detail import (
    build_dataset_detail,
    build_result_detail,
    normalize_compare_workspace,
    update_compare_workspace,
)
from backend.exports import (
    build_export_preparation,
    generate_report_docx_artifact,
    generate_results_csv_artifact,
)
from backend.library_cloud_service import ManagedLibraryCloudService
from backend.models import (
    ActiveDatasetResponse,
    ActiveDatasetUpdateRequest,
    AnalysisRunRequest,
    AnalysisRunResponse,
    BatchRunRequest,
    BatchRunResponse,
    CompareSelectionResponse,
    CompareSelectionUpdateRequest,
    CompareWorkspaceResponse,
    CompareWorkspaceUpdateRequest,
    DatasetDetailResponse,
    DatasetImportRequest,
    DatasetImportResponse,
    DatasetsListResponse,
    ExportArtifactResponse,
    ExportGenerateRequest,
    ExportPreparationResponse,
    HealthResponse,
    LibraryCatalogResponse,
    LibraryCloudAuthTokenResponse,
    LibraryCoverageResponse,
    LibraryPrefetchRequest,
    LibraryPrefetchResponse,
    LibraryProvidersResponse,
    LibrarySearchResponse,
    LibraryStatusResponse,
    LibrarySyncRequest,
    LibrarySyncResponse,
    ProjectLoadRequest,
    ProjectLoadResponse,
    ProjectSaveRequest,
    ProjectSaveResponse,
    ProjectSummary,
    ResultDetailResponse,
    ResultsListResponse,
    SpectralLibrarySearchRequest,
    ValidationSummary,
    VersionResponse,
    WorkspaceContextResponse,
    WorkspaceCreateResponse,
    WorkspaceSummaryResponse,
    XRDLibrarySearchRequest,
)
from backend.store import ProjectStore
from backend.workspace import (
    add_history_event,
    normalize_workspace_state,
    summarize_dataset,
    summarize_result,
    unique_dataset_key,
)
from backend.workspace_context import build_workspace_context, set_active_dataset, update_compare_selection
from core.data_io import read_thermal_data
from core.execution_engine import run_batch_analysis, run_single_analysis
from core.modalities import stable_analysis_types
from core.project_io import PROJECT_EXTENSION, load_project_archive, save_project_archive
from core.reference_library import ReferenceLibraryManager, get_reference_library_manager
from core.result_serialization import split_valid_results
from core.validation import validate_thermal_dataset
from utils.license_manager import APP_VERSION, commercial_mode_enabled, load_license_state

load_dotenv()


def _require_token(expected_token: str | None, provided_token: str | None) -> None:
    if expected_token and provided_token != expected_token:
        raise HTTPException(status_code=401, detail="Invalid or missing API token.")


def _decode_base64_field(payload: str, *, field_name: str) -> bytes:
    try:
        return base64.b64decode(payload.encode("ascii"), validate=True)
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(status_code=400, detail=f"{field_name} is not valid base64: {exc}") from exc


def _model_payload(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return dict(model.model_dump())
    if hasattr(model, "dict"):
        return dict(model.dict())
    return dict(model or {})


def _project_summary(project_state: dict) -> ProjectSummary:
    return ProjectSummary(
        active_dataset=project_state.get("active_dataset"),
        dataset_count=len(project_state.get("datasets", {}) or {}),
        result_count=len(project_state.get("results", {}) or {}),
        figure_count=len(project_state.get("figures", {}) or {}),
        analysis_history_count=len(project_state.get("analysis_history", []) or []),
    )


def _normalize_stable_analysis_error(detail: str) -> str:
    token = str(detail or "")
    if token.startswith("Unsupported stable analysis_type:"):
        return f"analysis_type must be one of: {', '.join(stable_analysis_types())}."
    return token


def _require_project_state(project_store: ProjectStore, project_id: str) -> dict:
    project_state = project_store.get(project_id)
    if project_state is None:
        raise HTTPException(status_code=404, detail=f"Unknown project_id: {project_id}")
    return project_state


def _library_status_payload(manager: ReferenceLibraryManager) -> dict:
    license_state = _backend_license_state()
    try:
        if manager.client.configured and (manager.load_manifest() is None or manager.needs_manifest_refresh()):
            status = manager.check_manifest(license_state=license_state, force=True)
        else:
            status = manager.status()
    except Exception:
        status = manager.status()
    return {
        **status,
        "license_status": license_state.get("status"),
    }


def _backend_license_state() -> dict:
    try:
        return load_license_state(app_version=APP_VERSION)
    except Exception as exc:
        return {
            "status": "unlicensed" if commercial_mode_enabled() else "development",
            "message": f"Stored license could not be loaded: {exc}",
            "license": None,
            "source": None,
            "commercial_mode": commercial_mode_enabled(),
        }


def create_app(*, api_token: str | None = None, store: ProjectStore | None = None, library_manager: ReferenceLibraryManager | None = None) -> FastAPI:
    """Create a backend app instance with an in-memory project store."""
    app = FastAPI(title="ThermoAnalyzer Backend", version=BACKEND_API_VERSION)
    project_store = store or ProjectStore()
    global_library_manager = library_manager or get_reference_library_manager()
    cloud_library_service = ManagedLibraryCloudService(global_library_manager)

    def _record_cloud_lookup_success(payload: dict[str, Any]) -> None:
        provider_count: int | None = None
        provider_scope = [str(item).strip() for item in (payload.get("library_provider_scope") or []) if str(item).strip()]
        if provider_scope:
            provider_count = len(set(provider_scope))
        elif isinstance(payload.get("providers"), list):
            provider_count = len(payload["providers"])
        elif isinstance(payload.get("coverage"), dict):
            coverage = payload.get("coverage") or {}
            seen: set[str] = set()
            for row in coverage.values():
                if not isinstance(row, dict):
                    continue
                providers = row.get("providers") or {}
                if isinstance(providers, dict):
                    for provider_id in providers:
                        token = str(provider_id).strip()
                        if token:
                            seen.add(token)
                else:
                    for provider in providers:
                        token = str(provider).strip()
                        if token:
                            seen.add(token)
            provider_count = len(seen)
        global_library_manager.record_cloud_lookup(success=True, provider_count=provider_count)

    def _record_cloud_lookup_failure(exc: Exception) -> None:
        if isinstance(exc, HTTPException):
            detail = str(exc.detail or "").strip() or str(exc)
        else:
            detail = str(exc or "").strip()
        global_library_manager.record_cloud_lookup(success=False, error=detail)

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(api_version=BACKEND_API_VERSION)

    @app.get("/version", response_model=VersionResponse)
    def version(x_ta_token: str | None = Header(default=None, alias="X-TA-Token")) -> VersionResponse:
        _require_token(api_token, x_ta_token)
        return VersionResponse(
            app_version=APP_VERSION,
            api_version=BACKEND_API_VERSION,
            project_extension=PROJECT_EXTENSION,
        )

    @app.get("/library/status", response_model=LibraryStatusResponse)
    def library_status(x_ta_token: str | None = Header(default=None, alias="X-TA-Token")) -> LibraryStatusResponse:
        _require_token(api_token, x_ta_token)
        return LibraryStatusResponse(**_library_status_payload(global_library_manager))

    @app.get("/library/catalog", response_model=LibraryCatalogResponse)
    def library_catalog(x_ta_token: str | None = Header(default=None, alias="X-TA-Token")) -> LibraryCatalogResponse:
        _require_token(api_token, x_ta_token)
        return LibraryCatalogResponse(
            status=LibraryStatusResponse(**_library_status_payload(global_library_manager)),
            libraries=global_library_manager.catalog(),
        )

    @app.post("/library/sync", response_model=LibrarySyncResponse)
    def library_sync(
        request: LibrarySyncRequest,
        x_ta_token: str | None = Header(default=None, alias="X-TA-Token"),
    ) -> LibrarySyncResponse:
        _require_token(api_token, x_ta_token)
        license_state = _backend_license_state()
        try:
            status = global_library_manager.sync(
                license_state=license_state,
                package_ids=request.package_ids,
                force=request.force,
            )
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text or str(exc)
            raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return LibrarySyncResponse(
            status=LibraryStatusResponse(**{**status, "license_status": license_state.get("status")}),
            libraries=global_library_manager.catalog(),
            synced_package_ids=[item.package_id for item in global_library_manager.installed_packages()],
        )

    @app.post("/v1/library/auth/token", response_model=LibraryCloudAuthTokenResponse)
    def library_auth_token(
        x_ta_license: str | None = Header(default=None, alias="X-TA-License"),
    ) -> LibraryCloudAuthTokenResponse:
        return LibraryCloudAuthTokenResponse(**cloud_library_service.issue_token(x_ta_license=x_ta_license))

    @app.post("/v1/library/search/ftir", response_model=LibrarySearchResponse)
    def library_search_ftir(
        request: SpectralLibrarySearchRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> LibrarySearchResponse:
        try:
            payload = cloud_library_service.search_spectral(
                analysis_type="FTIR",
                request_payload=_model_payload(request),
                authorization=authorization,
            )
        except Exception as exc:
            _record_cloud_lookup_failure(exc)
            raise
        _record_cloud_lookup_success(payload)
        return LibrarySearchResponse(**payload)

    @app.post("/v1/library/search/raman", response_model=LibrarySearchResponse)
    def library_search_raman(
        request: SpectralLibrarySearchRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> LibrarySearchResponse:
        try:
            payload = cloud_library_service.search_spectral(
                analysis_type="RAMAN",
                request_payload=_model_payload(request),
                authorization=authorization,
            )
        except Exception as exc:
            _record_cloud_lookup_failure(exc)
            raise
        _record_cloud_lookup_success(payload)
        return LibrarySearchResponse(**payload)

    @app.post("/v1/library/search/xrd", response_model=LibrarySearchResponse)
    def library_search_xrd(
        request: XRDLibrarySearchRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> LibrarySearchResponse:
        try:
            payload = cloud_library_service.search_xrd(
                request_payload=_model_payload(request),
                authorization=authorization,
            )
        except Exception as exc:
            _record_cloud_lookup_failure(exc)
            raise
        _record_cloud_lookup_success(payload)
        return LibrarySearchResponse(**payload)

    @app.get("/v1/library/providers", response_model=LibraryProvidersResponse)
    def library_providers(
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> LibraryProvidersResponse:
        try:
            payload = cloud_library_service.providers(authorization=authorization)
        except Exception as exc:
            _record_cloud_lookup_failure(exc)
            raise
        _record_cloud_lookup_success(payload)
        return LibraryProvidersResponse(**payload)

    @app.get("/v1/library/coverage", response_model=LibraryCoverageResponse)
    def library_coverage(
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> LibraryCoverageResponse:
        try:
            payload = cloud_library_service.coverage(authorization=authorization)
        except Exception as exc:
            _record_cloud_lookup_failure(exc)
            raise
        _record_cloud_lookup_success(payload)
        return LibraryCoverageResponse(**payload)

    @app.post("/v1/library/prefetch", response_model=LibraryPrefetchResponse)
    def library_prefetch(
        request: LibraryPrefetchRequest,
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> LibraryPrefetchResponse:
        try:
            payload = cloud_library_service.prefetch(
                request_payload=_model_payload(request),
                authorization=authorization,
            )
        except Exception as exc:
            _record_cloud_lookup_failure(exc)
            raise
        _record_cloud_lookup_success(payload)
        return LibraryPrefetchResponse(**payload)

    @app.post("/project/load", response_model=ProjectLoadResponse)
    def project_load(
        request: ProjectLoadRequest,
        x_ta_token: str | None = Header(default=None, alias="X-TA-Token"),
    ) -> ProjectLoadResponse:
        _require_token(api_token, x_ta_token)
        archive_bytes = _decode_base64_field(request.archive_base64, field_name="archive_base64")

        try:
            project_state = load_project_archive(io.BytesIO(archive_bytes))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Project archive could not be loaded: {exc}") from exc

        normalized_state = normalize_workspace_state(project_state)
        project_id = project_store.put(normalized_state)
        return ProjectLoadResponse(
            project_id=project_id,
            project_extension=PROJECT_EXTENSION,
            summary=_project_summary(normalized_state),
        )

    @app.post("/project/save", response_model=ProjectSaveResponse)
    def project_save(
        request: ProjectSaveRequest,
        x_ta_token: str | None = Header(default=None, alias="X-TA-Token"),
    ) -> ProjectSaveResponse:
        _require_token(api_token, x_ta_token)

        project_state = _require_project_state(project_store, request.project_id)

        try:
            archive_bytes = save_project_archive(project_state)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Project archive could not be saved: {exc}") from exc

        archive_base64 = base64.b64encode(archive_bytes).decode("ascii")
        return ProjectSaveResponse(
            project_id=request.project_id,
            file_name=f"thermoanalyzer_project{PROJECT_EXTENSION}",
            archive_base64=archive_base64,
        )

    @app.post("/workspace/new", response_model=WorkspaceCreateResponse)
    def workspace_new(x_ta_token: str | None = Header(default=None, alias="X-TA-Token")) -> WorkspaceCreateResponse:
        _require_token(api_token, x_ta_token)
        state = normalize_workspace_state({})
        project_id = project_store.put(state)
        return WorkspaceCreateResponse(project_id=project_id, summary=_project_summary(state))

    @app.get("/workspace/{project_id}", response_model=WorkspaceSummaryResponse)
    def workspace_summary(
        project_id: str,
        x_ta_token: str | None = Header(default=None, alias="X-TA-Token"),
    ) -> WorkspaceSummaryResponse:
        _require_token(api_token, x_ta_token)
        state = _require_project_state(project_store, project_id)
        return WorkspaceSummaryResponse(project_id=project_id, summary=_project_summary(state))

    @app.get("/workspace/{project_id}/context", response_model=WorkspaceContextResponse)
    def workspace_context(
        project_id: str,
        x_ta_token: str | None = Header(default=None, alias="X-TA-Token"),
    ) -> WorkspaceContextResponse:
        _require_token(api_token, x_ta_token)
        state = _require_project_state(project_store, project_id)
        payload = build_workspace_context(state)
        return WorkspaceContextResponse(project_id=project_id, summary=_project_summary(state), **payload)

    @app.get("/workspace/{project_id}/datasets", response_model=DatasetsListResponse)
    def workspace_datasets(
        project_id: str,
        x_ta_token: str | None = Header(default=None, alias="X-TA-Token"),
    ) -> DatasetsListResponse:
        _require_token(api_token, x_ta_token)
        state = _require_project_state(project_store, project_id)
        datasets = state.get("datasets", {}) or {}
        items = [summarize_dataset(dataset_key, dataset) for dataset_key, dataset in datasets.items()]
        return DatasetsListResponse(
            project_id=project_id,
            active_dataset=state.get("active_dataset"),
            datasets=items,
        )

    @app.get("/workspace/{project_id}/results", response_model=ResultsListResponse)
    def workspace_results(
        project_id: str,
        x_ta_token: str | None = Header(default=None, alias="X-TA-Token"),
    ) -> ResultsListResponse:
        _require_token(api_token, x_ta_token)
        state = _require_project_state(project_store, project_id)
        valid_results, _issues = split_valid_results(state.get("results", {}))
        items = [summarize_result(record) for record in valid_results.values()]
        items.sort(key=lambda item: item.id)
        return ResultsListResponse(project_id=project_id, results=items)

    @app.get("/workspace/{project_id}/datasets/{dataset_key}", response_model=DatasetDetailResponse)
    def dataset_detail(
        project_id: str,
        dataset_key: str,
        x_ta_token: str | None = Header(default=None, alias="X-TA-Token"),
    ) -> DatasetDetailResponse:
        _require_token(api_token, x_ta_token)
        state = _require_project_state(project_store, project_id)
        try:
            payload = build_dataset_detail(state, dataset_key)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return DatasetDetailResponse(project_id=project_id, **payload)

    @app.get("/workspace/{project_id}/results/{result_id}", response_model=ResultDetailResponse)
    def result_detail(
        project_id: str,
        result_id: str,
        x_ta_token: str | None = Header(default=None, alias="X-TA-Token"),
    ) -> ResultDetailResponse:
        _require_token(api_token, x_ta_token)
        state = _require_project_state(project_store, project_id)
        try:
            payload = build_result_detail(state, result_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ResultDetailResponse(project_id=project_id, **payload)

    @app.get("/workspace/{project_id}/compare", response_model=CompareWorkspaceResponse)
    def compare_workspace_get(
        project_id: str,
        x_ta_token: str | None = Header(default=None, alias="X-TA-Token"),
    ) -> CompareWorkspaceResponse:
        _require_token(api_token, x_ta_token)
        state = _require_project_state(project_store, project_id)
        payload = normalize_compare_workspace(state)
        return CompareWorkspaceResponse(project_id=project_id, compare_workspace=payload)

    @app.put("/workspace/{project_id}/compare", response_model=CompareWorkspaceResponse)
    def compare_workspace_put(
        project_id: str,
        request: CompareWorkspaceUpdateRequest,
        x_ta_token: str | None = Header(default=None, alias="X-TA-Token"),
    ) -> CompareWorkspaceResponse:
        _require_token(api_token, x_ta_token)
        state = _require_project_state(project_store, project_id)
        try:
            payload = update_compare_workspace(
                state,
                analysis_type=request.analysis_type,
                selected_datasets=request.selected_datasets,
                notes=request.notes,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        project_store.set(project_id, state)
        return CompareWorkspaceResponse(project_id=project_id, compare_workspace=payload)

    @app.post("/workspace/{project_id}/compare/selection", response_model=CompareSelectionResponse)
    def compare_selection_update(
        project_id: str,
        request: CompareSelectionUpdateRequest,
        x_ta_token: str | None = Header(default=None, alias="X-TA-Token"),
    ) -> CompareSelectionResponse:
        _require_token(api_token, x_ta_token)
        state = _require_project_state(project_store, project_id)
        try:
            payload = update_compare_selection(
                state,
                operation=request.operation,
                dataset_keys=request.dataset_keys,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        project_store.set(project_id, state)
        return CompareSelectionResponse(
            project_id=project_id,
            summary=_project_summary(state),
            compare_workspace=payload,
            selected_dataset_count=len(payload.selected_datasets),
        )

    @app.put("/workspace/{project_id}/active-dataset", response_model=ActiveDatasetResponse)
    def workspace_active_dataset_set(
        project_id: str,
        request: ActiveDatasetUpdateRequest,
        x_ta_token: str | None = Header(default=None, alias="X-TA-Token"),
    ) -> ActiveDatasetResponse:
        _require_token(api_token, x_ta_token)
        state = _require_project_state(project_store, project_id)
        try:
            active_dataset = set_active_dataset(state, request.dataset_key)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        project_store.set(project_id, state)
        return ActiveDatasetResponse(
            project_id=project_id,
            summary=_project_summary(state),
            active_dataset_key=state.get("active_dataset"),
            active_dataset=active_dataset,
        )

    @app.post("/workspace/{project_id}/batch/run", response_model=BatchRunResponse)
    def batch_run(
        project_id: str,
        request: BatchRunRequest,
        x_ta_token: str | None = Header(default=None, alias="X-TA-Token"),
    ) -> BatchRunResponse:
        _require_token(api_token, x_ta_token)
        state = _require_project_state(project_store, project_id)
        try:
            execution = run_batch_analysis(
                state=state,
                analysis_type=request.analysis_type,
                workflow_template_id=request.workflow_template_id,
                dataset_keys=request.dataset_keys,
                app_version=APP_VERSION,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=_normalize_stable_analysis_error(str(exc))) from exc

        analysis_type = execution["analysis_type"]
        workflow_template_id = execution["workflow_template_id"]
        workflow_template_label = execution["workflow_template_label"]
        batch_run_id = execution["batch_run_id"]
        selected_dataset_keys = execution["selected_dataset_keys"]
        normalized_rows = execution["batch_summary"]
        outcomes = execution["outcomes"]
        saved_result_ids = execution["saved_result_ids"]

        completed_at = datetime.now().isoformat(timespec="seconds")

        compare_workspace = state.setdefault("comparison_workspace", {})
        compare_workspace["analysis_type"] = analysis_type
        compare_workspace["selected_datasets"] = selected_dataset_keys
        compare_workspace["saved_at"] = completed_at
        compare_workspace["batch_run_id"] = batch_run_id
        compare_workspace["batch_template_id"] = workflow_template_id
        compare_workspace["batch_template_label"] = workflow_template_label
        compare_workspace["batch_completed_at"] = completed_at
        compare_workspace["batch_summary"] = normalized_rows
        compare_workspace["batch_result_ids"] = saved_result_ids
        compare_workspace["batch_last_feedback"] = outcomes

        add_history_event(
            state,
            action="Batch Template Executed",
            details=f"{analysis_type} {workflow_template_id}: saved={outcomes['saved']}, blocked={outcomes['blocked']}, failed={outcomes['failed']}",
            dataset_key=state.get("active_dataset"),
            status="warning" if outcomes["failed"] or outcomes["blocked"] else "info",
        )
        project_store.set(project_id, state)

        return BatchRunResponse(
            project_id=project_id,
            analysis_type=analysis_type,
            workflow_template_id=workflow_template_id,
            workflow_template_label=workflow_template_label,
            batch_run_id=batch_run_id,
            selected_dataset_keys=selected_dataset_keys,
            batch_summary=normalized_rows,
            outcomes=outcomes,
            saved_result_ids=saved_result_ids,
            compare_workspace=normalize_compare_workspace(state),
            summary=_project_summary(state),
        )

    @app.get("/workspace/{project_id}/exports/preparation", response_model=ExportPreparationResponse)
    def export_preparation(
        project_id: str,
        x_ta_token: str | None = Header(default=None, alias="X-TA-Token"),
    ) -> ExportPreparationResponse:
        _require_token(api_token, x_ta_token)
        state = _require_project_state(project_store, project_id)
        payload = build_export_preparation(state)
        return ExportPreparationResponse(project_id=project_id, summary=_project_summary(state), **payload)

    @app.post("/workspace/{project_id}/exports/results-csv", response_model=ExportArtifactResponse)
    def export_results_csv(
        project_id: str,
        request: ExportGenerateRequest,
        x_ta_token: str | None = Header(default=None, alias="X-TA-Token"),
    ) -> ExportArtifactResponse:
        _require_token(api_token, x_ta_token)
        state = _require_project_state(project_store, project_id)
        try:
            payload = generate_results_csv_artifact(state, selected_result_ids=request.selected_result_ids)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ExportArtifactResponse(project_id=project_id, **payload)

    @app.post("/workspace/{project_id}/exports/report-docx", response_model=ExportArtifactResponse)
    def export_report_docx(
        project_id: str,
        request: ExportGenerateRequest,
        x_ta_token: str | None = Header(default=None, alias="X-TA-Token"),
    ) -> ExportArtifactResponse:
        _require_token(api_token, x_ta_token)
        state = _require_project_state(project_store, project_id)
        try:
            payload = generate_report_docx_artifact(state, selected_result_ids=request.selected_result_ids)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ExportArtifactResponse(project_id=project_id, **payload)

    @app.post("/dataset/import", response_model=DatasetImportResponse)
    def dataset_import(
        request: DatasetImportRequest,
        x_ta_token: str | None = Header(default=None, alias="X-TA-Token"),
    ) -> DatasetImportResponse:
        _require_token(api_token, x_ta_token)
        state = _require_project_state(project_store, request.project_id)

        file_bytes = _decode_base64_field(request.file_base64, field_name="file_base64")
        source = io.BytesIO(file_bytes)
        source.name = request.file_name

        try:
            dataset = read_thermal_data(source, data_type=request.data_type)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Dataset import failed: {exc}") from exc

        normalized_dataset_type = str(getattr(dataset, "data_type", "unknown") or "unknown").upper()
        if normalized_dataset_type in {"FTIR", "RAMAN", "XRD"}:
            import_warnings = [str(item) for item in (dataset.metadata or {}).get("import_warnings", []) if item]
            validation = {
                "status": "warn" if ((dataset.metadata or {}).get("import_review_required") or import_warnings) else "pass",
                "warnings": import_warnings,
                "issues": [],
            }
        else:
            validation = validate_thermal_dataset(dataset, analysis_type=dataset.data_type)
            if validation.get("status") == "fail":
                issues = "; ".join(validation.get("issues") or [])
                raise HTTPException(status_code=400, detail=f"Dataset blocked by validation: {issues}")

        dataset_key = unique_dataset_key(state.get("datasets", {}), request.file_name)
        dataset.metadata.setdefault("file_name", request.file_name)
        dataset.metadata.setdefault("display_name", request.file_name)
        state.setdefault("datasets", {})[dataset_key] = dataset
        state["active_dataset"] = dataset_key
        add_history_event(
            state,
            action="Data Imported",
            details=f"{request.file_name} -> {dataset.data_type}",
            dataset_key=dataset_key,
        )
        project_store.set(request.project_id, state)

        return DatasetImportResponse(
            project_id=request.project_id,
            dataset=summarize_dataset(dataset_key, dataset),
            validation=ValidationSummary(
                status=validation.get("status", "unknown"),
                warning_count=len(validation.get("warnings") or []),
                issue_count=len(validation.get("issues") or []),
            ),
            summary=_project_summary(state),
        )

    @app.post("/analysis/run", response_model=AnalysisRunResponse)
    def analysis_run(
        request: AnalysisRunRequest,
        x_ta_token: str | None = Header(default=None, alias="X-TA-Token"),
    ) -> AnalysisRunResponse:
        _require_token(api_token, x_ta_token)
        state = _require_project_state(project_store, request.project_id)
        try:
            execution = run_single_analysis(
                state=state,
                dataset_key=request.dataset_key,
                analysis_type=request.analysis_type,
                workflow_template_id=request.workflow_template_id,
                app_version=APP_VERSION,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=_normalize_stable_analysis_error(str(exc))) from exc

        analysis_type = execution["analysis_type"]
        execution_status = execution["execution_status"]
        result_id = execution["result_id"]
        failure_reason = execution["failure_reason"]
        validation = execution["validation"]
        record = execution["record"] or {}
        state_key = execution["state_key"]

        if execution_status == "saved" and result_id:
            state.setdefault("results", {})[result_id] = record
            state[state_key] = execution["state_payload"] or {}
            add_history_event(
                state,
                action="Analysis Saved",
                details=f"{analysis_type} result saved with {execution['workflow_template_id']}",
                dataset_key=request.dataset_key,
                result_id=result_id,
            )
        elif execution_status == "blocked":
            add_history_event(
                state,
                action="Analysis Blocked",
                details=failure_reason or "Validation blocked analysis.",
                dataset_key=request.dataset_key,
                status="warning",
            )
        else:
            add_history_event(
                state,
                action="Analysis Failed",
                details=failure_reason or "Unknown analysis failure.",
                dataset_key=request.dataset_key,
                status="error",
            )

        project_store.set(request.project_id, state)
        provenance = execution["provenance"] or {}
        return AnalysisRunResponse(
            project_id=request.project_id,
            dataset_key=request.dataset_key,
            analysis_type=analysis_type,
            execution_status=execution_status,
            result_id=result_id,
            failure_reason=failure_reason,
            validation=ValidationSummary(
                status=validation.get("status", "unknown"),
                warning_count=len(validation.get("warnings") or []),
                issue_count=len(validation.get("issues") or []),
            ),
            provenance={
                "saved_at_utc": provenance.get("saved_at_utc"),
                "calibration_state": provenance.get("calibration_state"),
                "reference_state": provenance.get("reference_state"),
            },
            summary=_project_summary(state),
        )

    return app

