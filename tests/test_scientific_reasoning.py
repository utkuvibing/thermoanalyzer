from __future__ import annotations

from core.scientific_reasoning import build_scientific_reasoning


def test_build_scientific_reasoning_tga_emits_structured_payload():
    payload = build_scientific_reasoning(
        analysis_type="TGA",
        summary={"step_count": 3, "total_mass_loss_percent": 97.8, "residue_percent": 2.1},
        rows=[
            {"midpoint_temperature": 341.0, "mass_loss_percent": 80.0},
            {"midpoint_temperature": 420.0, "mass_loss_percent": 10.0},
            {"midpoint_temperature": 510.0, "mass_loss_percent": 7.8},
        ],
        metadata={"sample_mass": 10.0, "heating_rate": 20.0, "instrument": "TA", "atmosphere": "N2"},
        fit_quality={"r_squared": 0.991},
        validation={"status": "pass", "warnings": []},
    )

    assert payload["scientific_claims"]
    assert payload["evidence_map"]
    assert payload["uncertainty_assessment"]
    assert payload["alternative_hypotheses"]
    assert payload["next_experiments"]
    strengths = {claim["strength"] for claim in payload["scientific_claims"]}
    assert "descriptive" in strengths
    assert "comparative" in strengths
    assert "mechanistic" in strengths


def test_build_scientific_reasoning_tga_avoids_mechanistic_overclaim_when_metadata_missing():
    payload = build_scientific_reasoning(
        analysis_type="TGA",
        summary={"step_count": 2, "total_mass_loss_percent": 75.0, "residue_percent": 22.0},
        rows=[
            {"midpoint_temperature": 320.0, "mass_loss_percent": 45.0},
            {"midpoint_temperature": 450.0, "mass_loss_percent": 30.0},
        ],
        metadata={"sample_mass": None, "heating_rate": None, "instrument": None, "atmosphere": None},
        fit_quality={"r_squared": 0.91},
        validation={"status": "warn", "warnings": ["heating rate is missing"]},
    )

    strengths = {claim["strength"] for claim in payload["scientific_claims"]}
    assert "descriptive" in strengths
    assert "mechanistic" not in strengths
    assert payload["uncertainty_assessment"]["overall_confidence"] in {"low", "moderate"}


def test_build_scientific_reasoning_kinetics_flags_cross_method_limitations():
    payload = build_scientific_reasoning(
        analysis_type="Friedman",
        summary={"conversion_point_count": 3},
        rows=[
            {"alpha": 0.2, "activation_energy_kj_mol": 95.0, "r_squared": 0.98},
            {"alpha": 0.4, "activation_energy_kj_mol": 110.0, "r_squared": 0.97},
            {"alpha": 0.6, "activation_energy_kj_mol": 130.0, "r_squared": 0.96},
        ],
        metadata={},
        fit_quality={"mean_r_squared": 0.97},
        validation={"status": "pass", "warnings": []},
    )

    assert any("Cross-method agreement" in item for item in payload["alternative_hypotheses"])
    assert payload["next_experiments"]
