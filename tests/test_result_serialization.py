from __future__ import annotations

from core.result_serialization import (
    flatten_result_records,
    make_result_record,
    split_valid_results,
    validate_result_record,
)


def _base_record():
    return make_result_record(
        result_id="demo_result",
        analysis_type="DSC",
        status="stable",
        dataset_key="demo_dataset",
        metadata={"sample_name": "Demo"},
        summary={"peak_count": 1},
        rows=[{"peak_temperature": 123.4}],
    )


def test_validate_result_record_accepts_scientific_context_dict():
    record = _base_record()
    record["scientific_context"] = {
        "methodology": {"method": "demo"},
        "equations": [{"name": "E1", "formula": "y=x"}],
    }

    issues = validate_result_record("demo_result", record)

    assert issues == []


def test_validate_result_record_rejects_non_dict_scientific_context():
    record = _base_record()
    record["scientific_context"] = ["not", "a", "dict"]

    issues = validate_result_record("demo_result", record)

    assert any("scientific_context must be a dict" in issue for issue in issues)


def test_split_valid_results_backfills_scientific_context():
    record = _base_record()
    record.pop("scientific_context", None)

    valid, issues = split_valid_results({"demo_result": record})

    assert issues == []
    assert "demo_result" in valid
    assert valid["demo_result"]["scientific_context"] == {
        "methodology": {},
        "equations": [],
        "numerical_interpretation": [],
        "fit_quality": {},
        "warnings": [],
        "limitations": [],
        "scientific_claims": [],
        "evidence_map": {},
        "uncertainty_assessment": {},
        "alternative_hypotheses": [],
        "next_experiments": [],
    }


def test_flatten_result_records_emits_scientific_context_section():
    record = _base_record()
    record["scientific_context"] = {
        "methodology": {"workflow_template": "General DSC"},
        "equations": [{"name": "Energy", "formula": "DeltaH=int(q dT)"}],
    }

    flat_rows = flatten_result_records({"demo_result": record})

    assert any(row["section"] == "scientific_context" and row["field"] == "methodology" for row in flat_rows)
    assert any(row["section"] == "scientific_context" and row["field"] == "equations" for row in flat_rows)
