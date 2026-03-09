"""FastAPI app for incremental ThermoAnalyzer desktop backend tranches."""

from __future__ import annotations

import base64
import binascii
import io
import uuid

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
from backend.models import (
    AnalysisRunRequest,
    AnalysisRunResponse,
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
    ProjectLoadRequest,
    ProjectLoadResponse,
    ProjectSaveRequest,
    ProjectSaveResponse,
    ProjectSummary,
    ResultDetailResponse,
    ResultsListResponse,
    ValidationSummary,
    VersionResponse,
    WorkspaceCreateResponse,
    WorkspaceSummaryResponse,
)
from backend.store import ProjectStore
from backend.workspace import (
    add_history_event,
    normalize_workspace_state,
    summarize_dataset,
    summarize_result,
    unique_dataset_key,
)
from core.batch_runner import execute_batch_template
from core.data_io import read_thermal_data
from core.project_io import PROJECT_EXTENSION, load_project_archive, save_project_archive
from core.result_serialization import split_valid_results
from core.validation import validate_thermal_dataset
from utils.license_manager import APP_VERSION


def _require_token(expected_token: str | None, provided_token: str | None) -> None:
    if expected_token and provided_token != expected_token:
        raise HTTPException(status_code=401, detail="Invalid or missing API token.")


def _decode_base64_field(payload: str, *, field_name: str) -> bytes:
    try:
        return base64.b64decode(payload.encode("ascii"), validate=True)
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(status_code=400, detail=f"{field_name} is not valid base64: {exc}") from exc


def _project_summary(project_state: dict) -> ProjectSummary:
    return ProjectSummary(
        active_dataset=project_state.get("active_dataset"),
        dataset_count=len(project_state.get("datasets", {}) or {}),
        result_count=len(project_state.get("results", {}) or {}),
        figure_count=len(project_state.get("figures", {}) or {}),
        analysis_history_count=len(project_state.get("analysis_history", []) or []),
    )


def _require_project_state(project_store: ProjectStore, project_id: str) -> dict:
    project_state = project_store.get(project_id)
    if project_state is None:
        raise HTTPException(status_code=404, detail=f"Unknown project_id: {project_id}")
    return project_state


def create_app(*, api_token: str | None = None, store: ProjectStore | None = None) -> FastAPI:
    """Create a backend app instance with an in-memory project store."""
    app = FastAPI(title="ThermoAnalyzer Backend", version=BACKEND_API_VERSION)
    project_store = store or ProjectStore()

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
        dataset = (state.get("datasets") or {}).get(request.dataset_key)
        if dataset is None:
            raise HTTPException(status_code=404, detail=f"Unknown dataset_key: {request.dataset_key}")

        analysis_type = request.analysis_type.upper()
        if analysis_type not in {"DSC", "TGA"}:
            raise HTTPException(status_code=400, detail="analysis_type must be DSC or TGA for this tranche.")
        dataset_type = str(getattr(dataset, "data_type", "unknown") or "unknown").upper()
        if analysis_type == "DSC" and dataset_type not in {"DSC", "DTA", "UNKNOWN"}:
            raise HTTPException(status_code=400, detail=f"Dataset '{request.dataset_key}' is not eligible for DSC analysis.")
        if analysis_type == "TGA" and dataset_type not in {"TGA", "UNKNOWN"}:
            raise HTTPException(status_code=400, detail=f"Dataset '{request.dataset_key}' is not eligible for TGA analysis.")

        default_template = "dsc.general" if analysis_type == "DSC" else "tga.general"
        workflow_template_id = request.workflow_template_id or default_template
        state_key = f"dsc_state_{request.dataset_key}" if analysis_type == "DSC" else f"tga_state_{request.dataset_key}"
        existing_state = state.get(state_key, {}) or {}

        try:
            outcome = execute_batch_template(
                dataset_key=request.dataset_key,
                dataset=dataset,
                analysis_type=analysis_type,
                workflow_template_id=workflow_template_id,
                existing_processing=existing_state.get("processing"),
                analysis_history=state.get("analysis_history", []),
                analyst_name=((state.get("branding") or {}).get("analyst_name") or ""),
                app_version=APP_VERSION,
                batch_run_id=f"desktop_single_{uuid.uuid4().hex[:8]}",
            )
        except Exception as exc:
            add_history_event(
                state,
                action="Analysis Failed",
                details=str(exc),
                dataset_key=request.dataset_key,
                status="error",
            )
            project_store.set(request.project_id, state)
            return AnalysisRunResponse(
                project_id=request.project_id,
                dataset_key=request.dataset_key,
                analysis_type=analysis_type,
                execution_status="failed",
                result_id=None,
                failure_reason=str(exc),
                validation=ValidationSummary(status="error", warning_count=0, issue_count=1),
                provenance={"saved_at_utc": None, "calibration_state": None, "reference_state": None},
                summary=_project_summary(state),
            )

        validation = outcome.get("validation") or {}
        record = outcome.get("record") or {}
        execution_status = outcome.get("status") or "failed"
        result_id = record.get("id")
        failure_reason = None
        if execution_status != "saved":
            failure_reason = (outcome.get("summary_row") or {}).get("failure_reason") or "Analysis did not save a result."

        if execution_status == "saved" and result_id:
            state.setdefault("results", {})[result_id] = record
            state[state_key] = outcome.get("state") or {}
            add_history_event(
                state,
                action="Analysis Saved",
                details=f"{analysis_type} result saved with {workflow_template_id}",
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
        provenance = record.get("provenance") or {}
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
