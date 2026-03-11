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


def test_build_scientific_reasoning_tga_hydrate_mass_balance_avoids_incomplete_decomposition_wording():
    payload = build_scientific_reasoning(
        analysis_type="TGA",
        summary={
            "sample_name": "CuSO4·5H2O",
            "step_count": 4,
            "total_mass_loss_percent": 36.06,
            "residue_percent": 63.99,
        },
        rows=[
            {"midpoint_temperature": 118.0, "mass_loss_percent": 14.5},
            {"midpoint_temperature": 172.0, "mass_loss_percent": 11.2},
            {"midpoint_temperature": 223.0, "mass_loss_percent": 8.1},
            {"midpoint_temperature": 318.0, "mass_loss_percent": 2.3},
        ],
        metadata={
            "sample_name": "CuSO4·5H2O",
            "file_name": "tga_CuSO4_5H2O_dehydration.csv",
            "sample_mass": 10.0,
            "heating_rate": 10.0,
            "instrument": "TA",
            "atmosphere": "N2",
        },
        fit_quality={"r_squared": 0.995},
        validation={"status": "pass", "warnings": []},
    )

    comparative_claims = [item["claim"] for item in payload["scientific_claims"] if item.get("strength") == "comparative"]
    assert comparative_claims
    joined = " ".join(comparative_claims).lower()
    assert "near-complete dehydration" in joined
    assert "incomplete decomposition" not in joined


def test_build_scientific_reasoning_tga_carbonate_mass_balance_detects_decarbonation():
    payload = build_scientific_reasoning(
        analysis_type="TGA",
        summary={
            "sample_name": "CaCO3",
            "step_count": 2,
            "total_mass_loss_percent": 43.96,
            "residue_percent": 56.10,
        },
        rows=[
            {"midpoint_temperature": 312.0, "mass_loss_percent": 2.4},
            {"midpoint_temperature": 720.0, "mass_loss_percent": 41.5},
        ],
        metadata={
            "sample_name": "CaCO3",
            "file_name": "tga_CaCO3_decomposition.csv",
            "sample_mass": 12.0,
            "heating_rate": 10.0,
            "instrument": "STA",
            "atmosphere": "N2",
        },
        fit_quality={"r_squared": 0.994},
        validation={"status": "pass", "warnings": []},
    )

    comparative_claims = [item["claim"] for item in payload["scientific_claims"] if item.get("strength") == "comparative"]
    assert comparative_claims
    joined = " ".join(comparative_claims).lower()
    assert "near-complete decarbonation" in joined
    assert "incomplete decomposition" not in joined
    assert all("char" not in alt.lower() for alt in payload["alternative_hypotheses"])
    assert all("filler" not in alt.lower() for alt in payload["alternative_hypotheses"])


def test_build_scientific_reasoning_tga_dtg_step_wording_flags_possible_subdivision():
    payload = build_scientific_reasoning(
        analysis_type="TGA",
        summary={"sample_name": "CaCO3", "step_count": 4, "total_mass_loss_percent": 44.0, "residue_percent": 56.0},
        rows=[
            {"midpoint_temperature": 690.0, "mass_loss_percent": 20.5},
            {"midpoint_temperature": 708.0, "mass_loss_percent": 3.1},
            {"midpoint_temperature": 722.0, "mass_loss_percent": 18.8},
            {"midpoint_temperature": 735.0, "mass_loss_percent": 1.6},
        ],
        metadata={
            "sample_name": "CaCO3",
            "file_name": "tga_CaCO3_decomposition.csv",
            "sample_mass": 12.0,
            "heating_rate": 10.0,
            "instrument": "STA",
            "atmosphere": "N2",
        },
        fit_quality={"r_squared": 0.985},
        validation={"status": "pass", "warnings": []},
    )

    descriptive_claims = [item["claim"] for item in payload["scientific_claims"] if item.get("strength") == "descriptive"]
    assert descriptive_claims
    joined = " ".join(descriptive_claims).lower()
    assert "dtg-resolved events" in joined
    assert "subdivision" in joined


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
