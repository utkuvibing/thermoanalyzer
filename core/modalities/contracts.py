"""Shared modality contracts for stable analysis execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, runtime_checkable


@runtime_checkable
class ModalityAdapter(Protocol):
    """Contract surface that every stable modality adapter must expose."""

    analysis_type: str
    stable: bool
    default_workflow_template_id: str

    def import_data(self, source: Any, **kwargs: Any) -> Any: ...

    def preprocess(self, dataset: Any, processing: Mapping[str, Any] | None = None) -> Any: ...

    def analyze(self, dataset: Any, processing: Mapping[str, Any] | None = None) -> Any: ...

    def serialize(self, outcome: Mapping[str, Any]) -> dict[str, Any]: ...

    def report_context(self, outcome: Mapping[str, Any]) -> dict[str, Any]: ...

    def is_dataset_eligible(self, dataset_type: str) -> bool: ...

    def run(
        self,
        *,
        dataset_key: str,
        dataset: Any,
        workflow_template_id: str,
        existing_processing: Mapping[str, Any] | None = None,
        analysis_history: list[dict[str, Any]] | None = None,
        analyst_name: str | None = None,
        app_version: str | None = None,
        batch_run_id: str | None = None,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ModalitySpec:
    """Immutable registry metadata for one analysis type."""

    analysis_type: str
    stable: bool
    default_workflow_template_id: str
    adapter: ModalityAdapter
