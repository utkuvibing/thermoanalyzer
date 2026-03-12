from __future__ import annotations

import pytest

from core.modalities.registry import get_modality, require_stable_modality, stable_analysis_types
from core.modalities.state_keys import analysis_state_key


def _assert_lifecycle_surface(adapter) -> None:
    for name in (
        "import_data",
        "preprocess",
        "analyze",
        "serialize",
        "report_context",
        "is_dataset_eligible",
        "run",
    ):
        assert hasattr(adapter, name), f"Adapter missing lifecycle hook: {name}"


def test_stable_analysis_types_are_explicit_and_sorted():
    assert stable_analysis_types() == ("DSC", "DTA", "FTIR", "RAMAN", "TGA")


def test_require_stable_modality_returns_registered_specs_with_contract_surface():
    for analysis_type in stable_analysis_types():
        spec = require_stable_modality(analysis_type)
        assert spec.analysis_type == analysis_type
        assert spec.stable is True
        assert spec.default_workflow_template_id
        _assert_lifecycle_surface(spec.adapter)


def test_get_modality_returns_none_for_unknown_type():
    assert get_modality("XRD") is None


def test_require_stable_modality_rejects_unsupported_types():
    with pytest.raises(ValueError, match="Unsupported stable analysis_type"):
        require_stable_modality("XRD")


def test_state_key_mapping_is_centralized_and_deterministic():
    assert analysis_state_key("DSC", "run_1") == "dsc_state_run_1"
    assert analysis_state_key("DTA", "run_2") == "dta_state_run_2"
    assert analysis_state_key("FTIR", "run_3") == "ftir_state_run_3"
    assert analysis_state_key("RAMAN", "run_4") == "raman_state_run_4"
    assert analysis_state_key("TGA", "run_5") == "tga_state_run_5"

    with pytest.raises(ValueError, match="Unsupported stable analysis_type"):
        analysis_state_key("XRD", "run_6")


def test_adapter_run_delegates_to_batch_template(monkeypatch):
    from core.modalities.adapters import DSCAdapter

    captured: dict[str, object] = {}

    def fake_execute_batch_template(**kwargs):
        captured.update(kwargs)
        return {"status": "saved", "analysis_type": kwargs["analysis_type"], "dataset_key": kwargs["dataset_key"]}

    monkeypatch.setattr("core.modalities.adapters.execute_batch_template", fake_execute_batch_template)

    adapter = DSCAdapter()
    outcome = adapter.run(
        dataset_key="synthetic_dsc",
        dataset=object(),
        workflow_template_id="dsc.general",
        existing_processing={"workflow_template_id": "dsc.general"},
        analysis_history=[],
        analyst_name="Ada",
        app_version="2.0",
        batch_run_id="batch_demo",
    )

    assert outcome["status"] == "saved"
    assert captured["analysis_type"] == "DSC"
    assert captured["workflow_template_id"] == "dsc.general"
    assert captured["dataset_key"] == "synthetic_dsc"


@pytest.mark.parametrize(
    ("analysis_type", "dataset_type", "expected"),
    (
        ("DSC", "DSC", True),
        ("DSC", "DTA", True),
        ("DSC", "UNKNOWN", True),
        ("DSC", "TGA", False),
        ("DTA", "DTA", True),
        ("DTA", "UNKNOWN", True),
        ("DTA", "DSC", False),
        ("DTA", "TGA", False),
        ("FTIR", "FTIR", True),
        ("FTIR", "UNKNOWN", True),
        ("FTIR", "RAMAN", False),
        ("RAMAN", "RAMAN", True),
        ("RAMAN", "UNKNOWN", True),
        ("RAMAN", "FTIR", False),
        ("TGA", "TGA", True),
        ("TGA", "UNKNOWN", True),
        ("TGA", "DSC", False),
    ),
)
def test_dataset_eligibility_follows_stable_rules(analysis_type, dataset_type, expected):
    spec = require_stable_modality(analysis_type)
    assert spec.adapter.is_dataset_eligible(dataset_type) is expected
