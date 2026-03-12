"""Stable modality adapters that wrap existing batch execution kernels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from core.batch_runner import execute_batch_template


def _normalize_dataset_type(dataset_type: str | None) -> str:
    return str(dataset_type or "UNKNOWN").upper()


@dataclass(frozen=True)
class StableBatchAdapter:
    """Adapter for stable modalities implemented via execute_batch_template."""

    analysis_type: str
    default_workflow_template_id: str
    eligible_dataset_types: frozenset[str]
    stable: bool = True

    def import_data(self, source: Any, **kwargs: Any) -> Any:
        return source

    def preprocess(self, dataset: Any, processing: Mapping[str, Any] | None = None) -> Any:
        return dataset

    def analyze(self, dataset: Any, processing: Mapping[str, Any] | None = None) -> Any:
        return dataset

    def serialize(self, outcome: Mapping[str, Any]) -> dict[str, Any]:
        return dict(outcome)

    def report_context(self, outcome: Mapping[str, Any]) -> dict[str, Any]:
        record = outcome.get("record") if isinstance(outcome, Mapping) else None
        if not isinstance(record, Mapping):
            return {}
        return {"analysis_type": record.get("analysis_type"), "result_id": record.get("id")}

    def is_dataset_eligible(self, dataset_type: str) -> bool:
        return _normalize_dataset_type(dataset_type) in self.eligible_dataset_types

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
    ) -> dict[str, Any]:
        return execute_batch_template(
            dataset_key=dataset_key,
            dataset=dataset,
            analysis_type=self.analysis_type,
            workflow_template_id=workflow_template_id,
            existing_processing=existing_processing,
            analysis_history=analysis_history,
            analyst_name=analyst_name,
            app_version=app_version,
            batch_run_id=batch_run_id,
        )


class DSCAdapter(StableBatchAdapter):
    def __init__(self) -> None:
        super().__init__(
            analysis_type="DSC",
            default_workflow_template_id="dsc.general",
            eligible_dataset_types=frozenset({"DSC", "DTA", "UNKNOWN"}),
        )


class DTAAdapter(StableBatchAdapter):
    def __init__(self) -> None:
        super().__init__(
            analysis_type="DTA",
            default_workflow_template_id="dta.general",
            eligible_dataset_types=frozenset({"DTA", "UNKNOWN"}),
        )


class TGAAdapter(StableBatchAdapter):
    def __init__(self) -> None:
        super().__init__(
            analysis_type="TGA",
            default_workflow_template_id="tga.general",
            eligible_dataset_types=frozenset({"TGA", "UNKNOWN"}),
        )


class FTIRAdapter(StableBatchAdapter):
    def __init__(self) -> None:
        super().__init__(
            analysis_type="FTIR",
            default_workflow_template_id="ftir.general",
            eligible_dataset_types=frozenset({"FTIR", "UNKNOWN"}),
        )


class RAMANAdapter(StableBatchAdapter):
    def __init__(self) -> None:
        super().__init__(
            analysis_type="RAMAN",
            default_workflow_template_id="raman.general",
            eligible_dataset_types=frozenset({"RAMAN", "UNKNOWN"}),
        )

class XRDAdapter(StableBatchAdapter):
    def __init__(self) -> None:
        super().__init__(
            analysis_type="XRD",
            default_workflow_template_id="xrd.general",
            eligible_dataset_types=frozenset({"XRD", "UNKNOWN"}),
        )

