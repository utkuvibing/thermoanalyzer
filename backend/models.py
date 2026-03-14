"""Minimal DTOs for backend desktop workflow tranches."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "thermoanalyzer-backend"
    api_version: str


class VersionResponse(BaseModel):
    app_version: str
    api_version: str
    project_extension: str


class LibraryStatusResponse(BaseModel):
    feed_configured: bool
    feed_source: str = ""
    manifest_checked_at: str | None = None
    last_sync_at: str | None = None
    sync_mode: str = "not_synced"
    cache_status: str = "cold"
    installed_package_count: int = 0
    installed_entry_count: int = 0
    update_available_count: int = 0
    available_package_count: int = 0
    available_provider_count: int = 0
    manifest_etag: str = ""
    last_error: str = ""
    sync_due: bool = False
    license_status: str | None = None


class LibraryCatalogItem(BaseModel):
    package_id: str
    analysis_type: str
    provider: str
    version: str
    entry_count: int = 0
    source_url: str = ""
    license_name: str = ""
    attribution: str = ""
    priority: int = 0
    installed: bool = False
    installed_version: str | None = None
    update_available: bool = False


class LibraryCatalogResponse(BaseModel):
    status: LibraryStatusResponse
    libraries: list[LibraryCatalogItem] = Field(default_factory=list)


class LibrarySyncRequest(BaseModel):
    package_ids: list[str] | None = None
    force: bool = False


class LibrarySyncResponse(BaseModel):
    status: LibraryStatusResponse
    libraries: list[LibraryCatalogItem] = Field(default_factory=list)
    synced_package_ids: list[str] = Field(default_factory=list)


class ProjectSummary(BaseModel):
    active_dataset: str | None = None
    dataset_count: int = 0
    result_count: int = 0
    figure_count: int = 0
    analysis_history_count: int = 0


class ProjectLoadRequest(BaseModel):
    archive_base64: str = Field(..., min_length=1)


class ProjectLoadResponse(BaseModel):
    project_id: str
    project_extension: str
    summary: ProjectSummary


class ProjectSaveRequest(BaseModel):
    project_id: str = Field(..., min_length=1)


class ProjectSaveResponse(BaseModel):
    project_id: str
    file_name: str
    archive_base64: str


class WorkspaceCreateResponse(BaseModel):
    project_id: str
    summary: ProjectSummary


class WorkspaceSummaryResponse(BaseModel):
    project_id: str
    summary: ProjectSummary


class DatasetSummary(BaseModel):
    key: str
    display_name: str
    data_type: str
    points: int
    vendor: str
    sample_name: str
    heating_rate: float | None = None
    import_confidence: str | None = None
    validation_status: str
    warning_count: int
    issue_count: int


class DatasetsListResponse(BaseModel):
    project_id: str
    active_dataset: str | None = None
    datasets: list[DatasetSummary]


class ResultSummary(BaseModel):
    id: str
    analysis_type: str
    status: str
    dataset_key: str | None = None
    validation_status: str | None = None
    warning_count: int = 0
    issue_count: int = 0
    workflow_template: str | None = None
    saved_at_utc: str | None = None
    calibration_state: str | None = None
    reference_state: str | None = None


class ResultsListResponse(BaseModel):
    project_id: str
    results: list[ResultSummary]


class DatasetImportRequest(BaseModel):
    project_id: str = Field(..., min_length=1)
    file_name: str = Field(..., min_length=1)
    file_base64: str = Field(..., min_length=1)
    data_type: str | None = None


class ValidationSummary(BaseModel):
    status: str
    warning_count: int = 0
    issue_count: int = 0


class DatasetImportResponse(BaseModel):
    project_id: str
    dataset: DatasetSummary
    validation: ValidationSummary
    summary: ProjectSummary


class AnalysisRunRequest(BaseModel):
    project_id: str = Field(..., min_length=1)
    dataset_key: str = Field(..., min_length=1)
    analysis_type: str = Field(..., min_length=1)
    workflow_template_id: str | None = None


class AnalysisRunResponse(BaseModel):
    project_id: str
    dataset_key: str
    analysis_type: str
    execution_status: str
    result_id: str | None = None
    failure_reason: str | None = None
    validation: ValidationSummary
    provenance: dict[str, str | None]
    summary: ProjectSummary


class DatasetDetailResponse(BaseModel):
    project_id: str
    dataset: DatasetSummary
    validation: dict[str, Any]
    metadata: dict[str, Any]
    units: dict[str, Any]
    original_columns: dict[str, Any]
    data_preview: list[dict[str, Any]]
    compare_selected: bool = False


class ResultDetailResponse(BaseModel):
    project_id: str
    result: ResultSummary
    summary: dict[str, Any]
    processing: dict[str, Any]
    provenance: dict[str, Any]
    validation: dict[str, Any]
    review: dict[str, Any]
    rows_preview: list[dict[str, Any]]
    row_count: int


class CompareWorkspacePayload(BaseModel):
    analysis_type: str = "DSC"
    selected_datasets: list[str] = Field(default_factory=list)
    notes: str = ""
    figure_key: str | None = None
    saved_at: str | None = None
    batch_run_id: str | None = None
    batch_template_id: str | None = None
    batch_template_label: str | None = None
    batch_completed_at: str | None = None
    batch_summary: list[dict[str, Any]] = Field(default_factory=list)
    batch_result_ids: list[str] = Field(default_factory=list)
    batch_last_feedback: dict[str, int] = Field(default_factory=dict)


class CompareWorkspaceResponse(BaseModel):
    project_id: str
    compare_workspace: CompareWorkspacePayload


class CompareWorkspaceUpdateRequest(BaseModel):
    analysis_type: str | None = None
    selected_datasets: list[str] | None = None
    notes: str | None = None


class ExportPreparationResponse(BaseModel):
    project_id: str
    summary: ProjectSummary
    exportable_results: list[ResultSummary]
    skipped_record_issues: list[str]
    supported_outputs: list[str]
    branding: dict[str, Any]
    compare_workspace: CompareWorkspacePayload


class ExportGenerateRequest(BaseModel):
    selected_result_ids: list[str] | None = None


class ExportArtifactResponse(BaseModel):
    project_id: str
    output_type: str
    file_name: str
    mime_type: str
    included_result_ids: list[str]
    skipped_record_issues: list[str]
    artifact_base64: str


class WorkspaceContextResponse(BaseModel):
    project_id: str
    summary: ProjectSummary
    active_dataset_key: str | None = None
    active_dataset: DatasetSummary | None = None
    latest_result: ResultSummary | None = None
    compare_workspace: CompareWorkspacePayload
    compare_selected_datasets: list[DatasetSummary] = Field(default_factory=list)
    recent_history: list[dict[str, Any]] = Field(default_factory=list)


class ActiveDatasetUpdateRequest(BaseModel):
    dataset_key: str = Field(..., min_length=1)


class ActiveDatasetResponse(BaseModel):
    project_id: str
    summary: ProjectSummary
    active_dataset_key: str | None = None
    active_dataset: DatasetSummary | None = None


class CompareSelectionUpdateRequest(BaseModel):
    operation: str = Field(..., min_length=1)
    dataset_keys: list[str] | None = None


class CompareSelectionResponse(BaseModel):
    project_id: str
    summary: ProjectSummary
    compare_workspace: CompareWorkspacePayload
    selected_dataset_count: int


class BatchRunRequest(BaseModel):
    analysis_type: str = Field(..., min_length=1)
    workflow_template_id: str | None = None
    dataset_keys: list[str] | None = None


class BatchRunResponse(BaseModel):
    project_id: str
    analysis_type: str
    workflow_template_id: str
    workflow_template_label: str
    batch_run_id: str
    selected_dataset_keys: list[str]
    batch_summary: list[dict[str, Any]]
    outcomes: dict[str, int]
    saved_result_ids: list[str]
    compare_workspace: CompareWorkspacePayload
    summary: ProjectSummary
