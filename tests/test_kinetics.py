import numpy as np

from core.kinetics import compute_conversion, run_kinetic_analysis


def test_compute_conversion_tga_mode_uses_mass_drop_fraction():
    temperature = np.array([25.0, 100.0, 200.0, 300.0])
    mass = np.array([100.0, 95.0, 70.0, 60.0])

    alpha = compute_conversion(temperature, mass, mode="tga")

    np.testing.assert_allclose(alpha, [0.0, 0.125, 0.75, 1.0], atol=1e-8)


def test_run_kinetic_analysis_returns_report_ready_kissinger_payload():
    payload = run_kinetic_analysis(
        "kissinger",
        heating_rates=[5.0, 10.0, 20.0],
        peak_temperatures=[210.0, 220.0, 232.0],
    )

    assert payload["method_id"] == "kissinger"
    assert payload["summary"]["activation_energy_kj_mol"] is not None
    assert len(payload["rows"]) == 1
    assert payload["scientific_context"]["equations"]
    assert payload["scientific_context"]["numerical_interpretation"]


def test_run_kinetic_analysis_returns_report_ready_ofw_payload():
    heating_rates = [5.0, 10.0, 20.0]
    temperature_data = [
        np.array([100.0, 120.0, 140.0, 160.0]),
        np.array([105.0, 125.0, 145.0, 165.0]),
        np.array([110.0, 130.0, 150.0, 170.0]),
    ]
    conversion_data = [
        np.array([0.0, 0.3, 0.7, 1.0]),
        np.array([0.0, 0.32, 0.72, 1.0]),
        np.array([0.0, 0.34, 0.74, 1.0]),
    ]

    payload = run_kinetic_analysis(
        "ofw",
        heating_rates=heating_rates,
        temperature_data=temperature_data,
        conversion_data=conversion_data,
        alpha_values=[0.2, 0.4, 0.6],
    )

    assert payload["method_id"] == "ofw"
    assert payload["summary"]["conversion_point_count"] >= 2
    assert payload["rows"]
    assert payload["scientific_context"]["fit_quality"]["evaluated_rows"] == len(payload["rows"])


def test_run_kinetic_analysis_returns_report_ready_friedman_payload():
    heating_rates = [5.0, 10.0, 20.0]
    temperature_data = [
        np.array([100.0, 120.0, 140.0, 160.0]),
        np.array([105.0, 125.0, 145.0, 165.0]),
        np.array([110.0, 130.0, 150.0, 170.0]),
    ]
    conversion_data = [
        np.array([0.0, 0.3, 0.7, 1.0]),
        np.array([0.0, 0.32, 0.72, 1.0]),
        np.array([0.0, 0.34, 0.74, 1.0]),
    ]
    dalpha_dt_data = [
        np.array([0.01, 0.03, 0.04, 0.02]),
        np.array([0.015, 0.028, 0.038, 0.022]),
        np.array([0.02, 0.03, 0.042, 0.025]),
    ]

    payload = run_kinetic_analysis(
        "friedman",
        heating_rates=heating_rates,
        temperature_data=temperature_data,
        conversion_data=conversion_data,
        dalpha_dt_data=dalpha_dt_data,
        alpha_values=[0.2, 0.4, 0.6],
    )

    assert payload["method_id"] == "friedman"
    assert payload["summary"]["conversion_point_count"] >= 2
    assert payload["scientific_context"]["equations"]
