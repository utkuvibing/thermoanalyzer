import pytest

from core.preset_store import (
    MAX_PRESETS_PER_ANALYSIS,
    PresetLimitError,
    PresetStoreError,
    count_presets,
    delete_preset,
    list_presets,
    load_preset,
    save_preset,
)
from core.processing_schema import ensure_processing_payload


def _payload(analysis_type: str, workflow_template_id: str) -> dict:
    processing = ensure_processing_payload(
        analysis_type=analysis_type,
        workflow_template=workflow_template_id,
    )
    return {
        "workflow_template_id": workflow_template_id,
        "processing": processing,
    }


def test_preset_store_crud_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMOANALYZER_HOME", str(tmp_path))

    save_preset("XRD", "xrd-default", _payload("XRD", "xrd.general"))
    save_preset("XRD", "xrd-screening", _payload("XRD", "xrd.phase_screening"))

    items = list_presets("XRD")
    names = {item["preset_name"] for item in items}
    assert names == {"xrd-default", "xrd-screening"}
    assert count_presets("XRD") == 2

    loaded = load_preset("XRD", "xrd-default")
    assert loaded is not None
    assert loaded["workflow_template_id"] == "xrd.general"
    assert loaded["processing"]["workflow_template_id"] == "xrd.general"

    assert delete_preset("XRD", "xrd-default") is True
    assert delete_preset("XRD", "xrd-default") is False
    assert count_presets("XRD") == 1


def test_preset_store_enforces_per_analysis_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMOANALYZER_HOME", str(tmp_path))

    for index in range(MAX_PRESETS_PER_ANALYSIS):
        save_preset("DSC", f"preset-{index}", _payload("DSC", "dsc.general"))

    assert count_presets("DSC") == MAX_PRESETS_PER_ANALYSIS
    with pytest.raises(PresetLimitError):
        save_preset("DSC", "preset-overflow", _payload("DSC", "dsc.general"))


def test_preset_store_same_name_updates_without_increasing_count(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMOANALYZER_HOME", str(tmp_path))

    for index in range(MAX_PRESETS_PER_ANALYSIS):
        save_preset("TGA", f"preset-{index}", _payload("TGA", "tga.general"))

    # Same-name save must update existing row, not consume another slot.
    save_preset("TGA", "preset-0", _payload("TGA", "tga.multi_step_decomposition"))

    assert count_presets("TGA") == MAX_PRESETS_PER_ANALYSIS
    loaded = load_preset("TGA", "preset-0")
    assert loaded is not None
    assert loaded["workflow_template_id"] == "tga.multi_step_decomposition"


def test_preset_store_rejects_invalid_payload(tmp_path, monkeypatch):
    monkeypatch.setenv("THERMOANALYZER_HOME", str(tmp_path))

    with pytest.raises(PresetStoreError):
        save_preset("FTIR", "bad", None)  # type: ignore[arg-type]
