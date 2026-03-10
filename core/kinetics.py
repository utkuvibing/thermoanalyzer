"""
Kinetic analysis methods for thermal data.

Supports:
- Kissinger method
- Ozawa-Flynn-Wall (OFW) isoconversional method
- Friedman differential isoconversional method
- Conversion computation from DSC/TGA signals
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Any, Optional
from scipy import integrate, interpolate, stats

from core.scientific_sections import (
    build_equation,
    build_fit_quality,
    build_interpretation,
    build_scientific_context,
)
from core.scientific_reasoning import build_scientific_reasoning

GAS_CONSTANT_R = 8.314462  # J/(mol·K)


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class KineticResult:
    """Container for a single kinetic analysis result."""

    method: str                            # 'kissinger', 'ozawa_flynn_wall', 'friedman'
    activation_energy: float               # kJ/mol
    pre_exponential: Optional[float] = None   # ln(A) for Kissinger
    r_squared: Optional[float] = None        # Regression quality (0–1)
    plot_data: Optional[dict] = field(default=None)  # Data for plotting


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def kissinger_analysis(
    heating_rates: list[float],
    peak_temperatures: list[float],
) -> KineticResult:
    """
    Kissinger kinetic analysis.

    Parameters
    ----------
    heating_rates : list[float]
        Heating rates β in K/min or °C/min (units cancel in the ratio).
    peak_temperatures : list[float]
        Peak temperatures Tp in °C (converted internally to K).

    Returns
    -------
    KineticResult
        Activation energy (kJ/mol), ln(A), R², and plot data.

    Notes
    -----
    The Kissinger equation is:

        ln(β / Tp²) = -Ea / (R · Tp) + ln(A · R / Ea)

    A linear regression of ln(β/Tp²) vs 1/Tp gives:
        slope  = -Ea / R
        intercept = ln(A · R / Ea)
    """
    beta = np.asarray(heating_rates, dtype=float)
    tp_celsius = np.asarray(peak_temperatures, dtype=float)
    tp_kelvin = tp_celsius + 273.15

    if len(beta) < 2:
        raise ValueError("At least two data points are required for Kissinger analysis.")
    if len(beta) != len(tp_kelvin):
        raise ValueError("heating_rates and peak_temperatures must have the same length.")

    inv_tp = 1.0 / tp_kelvin
    ln_beta_tp2 = np.log(beta / tp_kelvin**2)

    slope, intercept, r_value, _, _ = stats.linregress(inv_tp, ln_beta_tp2)

    ea_j_per_mol = -slope * GAS_CONSTANT_R          # J/mol
    ea_kj_per_mol = ea_j_per_mol / 1000.0            # kJ/mol
    ln_a = intercept                                  # ln(A·R/Ea) ≈ ln(A) for reporting

    r_squared = r_value**2

    # Points along the fitted line for plotting
    x_fit = np.linspace(inv_tp.min(), inv_tp.max(), 200)
    y_fit = slope * x_fit + intercept

    plot_data = {
        "inv_tp": inv_tp.tolist(),
        "ln_beta_tp2": ln_beta_tp2.tolist(),
        "x_fit": x_fit.tolist(),
        "y_fit": y_fit.tolist(),
        "xlabel": "1/Tp  (K⁻¹)",
        "ylabel": "ln(β / Tp²)  (K⁻² min⁻¹)",
    }

    return KineticResult(
        method="kissinger",
        activation_energy=ea_kj_per_mol,
        pre_exponential=ln_a,
        r_squared=r_squared,
        plot_data=plot_data,
    )


def ozawa_flynn_wall_analysis(
    heating_rates: list[float],
    temperature_data: list[np.ndarray],
    conversion_data: list[np.ndarray],
    alpha_values: Optional[list[float]] = None,
) -> list[KineticResult]:
    """
    Ozawa-Flynn-Wall (OFW) isoconversional analysis.

    For each conversion level α the method fits:

        log(β) = -0.4567 · Ea / (R · T) + const

    using Doyle's approximation for the temperature integral.

    Parameters
    ----------
    heating_rates : list[float]
        List of heating rates β.
    temperature_data : list[np.ndarray]
        Temperature arrays (°C) – one array per heating rate.
    conversion_data : list[np.ndarray]
        Conversion arrays (0–1) – one array per heating rate, same length as
        the corresponding temperature array.
    alpha_values : list[float], optional
        Conversion levels at which Ea is evaluated.
        Default: np.arange(0.1, 0.95, 0.05).

    Returns
    -------
    list[KineticResult]
        One KineticResult per α value.  Results where fewer than two heating
        rates yield a valid temperature are silently skipped.
    """
    if alpha_values is None:
        alpha_values = np.arange(0.1, 0.95, 0.05).tolist()

    beta = np.asarray(heating_rates, dtype=float)
    log_beta = np.log10(beta)

    if len(beta) != len(temperature_data) or len(beta) != len(conversion_data):
        raise ValueError(
            "heating_rates, temperature_data, and conversion_data must all "
            "have the same number of elements."
        )

    results: list[KineticResult] = []

    for alpha in alpha_values:
        temps_at_alpha: list[float] = []
        valid_log_beta: list[float] = []

        for i, (T_arr, alpha_arr) in enumerate(zip(temperature_data, conversion_data)):
            T_arr = np.asarray(T_arr, dtype=float)
            alpha_arr = np.asarray(alpha_arr, dtype=float)

            # Require the conversion range to span α
            if alpha_arr.min() >= alpha or alpha_arr.max() <= alpha:
                continue

            # Interpolate temperature at this α
            try:
                interp_func = interpolate.interp1d(
                    alpha_arr, T_arr, kind="linear", bounds_error=False,
                    fill_value="extrapolate"
                )
                t_at_alpha = float(interp_func(alpha))
            except Exception:
                continue

            temps_at_alpha.append(t_at_alpha + 273.15)  # convert to K
            valid_log_beta.append(log_beta[i])

        if len(temps_at_alpha) < 2:
            continue

        inv_t = np.array([1.0 / t for t in temps_at_alpha])
        log_b = np.array(valid_log_beta)

        slope, intercept, r_value, _, _ = stats.linregress(inv_t, log_b)

        # Doyle approximation: slope = -0.4567 * Ea / R
        ea_j_per_mol = -slope * GAS_CONSTANT_R / 0.4567
        ea_kj_per_mol = ea_j_per_mol / 1000.0

        x_fit = np.linspace(inv_t.min(), inv_t.max(), 200)
        y_fit = slope * x_fit + intercept

        plot_data = {
            "alpha": float(alpha),
            "inv_t": inv_t.tolist(),
            "log_beta": log_b.tolist(),
            "x_fit": x_fit.tolist(),
            "y_fit": y_fit.tolist(),
            "xlabel": "1/T  (K⁻¹)",
            "ylabel": "log(β)  (log K·min⁻¹)",
        }

        results.append(
            KineticResult(
                method="ozawa_flynn_wall",
                activation_energy=ea_kj_per_mol,
                pre_exponential=None,
                r_squared=r_value**2,
                plot_data=plot_data,
            )
        )

    return results


def friedman_analysis(
    heating_rates: list[float],
    temperature_data: list[np.ndarray],
    conversion_data: list[np.ndarray],
    dalpha_dt_data: list[np.ndarray],
    alpha_values: Optional[list[float]] = None,
) -> list[KineticResult]:
    """
    Friedman differential isoconversional analysis.

    At each conversion α the method fits:

        ln(dα/dt) = -Ea / (R · T) + ln[A · f(α)]

    Parameters
    ----------
    heating_rates : list[float]
        List of heating rates β (used for labelling only in this method).
    temperature_data : list[np.ndarray]
        Temperature arrays (°C) – one per heating rate.
    conversion_data : list[np.ndarray]
        Conversion arrays (0–1) – one per heating rate.
    dalpha_dt_data : list[np.ndarray]
        Conversion-rate arrays dα/dt (s⁻¹ or min⁻¹) – one per heating rate,
        same length as the corresponding temperature and conversion arrays.
    alpha_values : list[float], optional
        Conversion levels at which Ea is evaluated.
        Default: np.arange(0.1, 0.95, 0.05).

    Returns
    -------
    list[KineticResult]
        One KineticResult per α value.
    """
    if alpha_values is None:
        alpha_values = np.arange(0.1, 0.95, 0.05).tolist()

    n = len(heating_rates)
    if len(temperature_data) != n or len(conversion_data) != n or len(dalpha_dt_data) != n:
        raise ValueError(
            "heating_rates, temperature_data, conversion_data, and "
            "dalpha_dt_data must all have the same number of elements."
        )

    results: list[KineticResult] = []

    for alpha in alpha_values:
        inv_t_vals: list[float] = []
        ln_dalpha_dt_vals: list[float] = []

        for T_arr, alpha_arr, dalpha_arr in zip(
            temperature_data, conversion_data, dalpha_dt_data
        ):
            T_arr = np.asarray(T_arr, dtype=float)
            alpha_arr = np.asarray(alpha_arr, dtype=float)
            dalpha_arr = np.asarray(dalpha_arr, dtype=float)

            if alpha_arr.min() >= alpha or alpha_arr.max() <= alpha:
                continue

            try:
                interp_t = interpolate.interp1d(
                    alpha_arr, T_arr, kind="linear", bounds_error=False,
                    fill_value="extrapolate"
                )
                interp_dalpha = interpolate.interp1d(
                    alpha_arr, dalpha_arr, kind="linear", bounds_error=False,
                    fill_value="extrapolate"
                )
                t_at_alpha = float(interp_t(alpha)) + 273.15  # K
                da_at_alpha = float(interp_dalpha(alpha))
            except Exception:
                continue

            if da_at_alpha <= 0:
                continue

            inv_t_vals.append(1.0 / t_at_alpha)
            ln_dalpha_dt_vals.append(np.log(da_at_alpha))

        if len(inv_t_vals) < 2:
            continue

        inv_t = np.array(inv_t_vals)
        ln_da = np.array(ln_dalpha_dt_vals)

        slope, intercept, r_value, _, _ = stats.linregress(inv_t, ln_da)

        ea_j_per_mol = -slope * GAS_CONSTANT_R
        ea_kj_per_mol = ea_j_per_mol / 1000.0

        x_fit = np.linspace(inv_t.min(), inv_t.max(), 200)
        y_fit = slope * x_fit + intercept

        plot_data = {
            "alpha": float(alpha),
            "inv_t": inv_t.tolist(),
            "ln_dalpha_dt": ln_da.tolist(),
            "x_fit": x_fit.tolist(),
            "y_fit": y_fit.tolist(),
            "xlabel": "1/T  (K⁻¹)",
            "ylabel": "ln(dα/dt)  (ln min⁻¹)",
        }

        results.append(
            KineticResult(
                method="friedman",
                activation_energy=ea_kj_per_mol,
                pre_exponential=intercept,   # ln[A·f(α)]
                r_squared=r_value**2,
                plot_data=plot_data,
            )
        )

    return results


def compute_conversion(
    temperature: np.ndarray,
    signal: np.ndarray,
    baseline: Optional[np.ndarray] = None,
    mode: str = "dsc",
) -> np.ndarray:
    """
    Convert a DSC or TGA signal to fractional conversion α (0–1).

    Parameters
    ----------
    temperature : np.ndarray
        Temperature axis (°C or K – only used as the integration variable).
    signal : np.ndarray
        For DSC: heat-flow signal (mW or mW/mg).
        For TGA: sample mass (mg or %).
    baseline : np.ndarray, optional
        Baseline signal to subtract before integration (DSC only).
        For TGA this parameter is ignored.
    mode : {'dsc', 'tga'}
        'dsc' uses cumulative integration of (signal − baseline).
        'tga' uses (m0 − m) / (m0 − mf).

    Returns
    -------
    np.ndarray
        Conversion array of the same length as *signal*, values in [0, 1].

    Raises
    ------
    ValueError
        If the total area/mass change is zero (degenerate signal).
    """
    temperature = np.asarray(temperature, dtype=float)
    signal = np.asarray(signal, dtype=float)

    if mode.lower() == "tga":
        m0 = signal[0]
        mf = signal[-1]
        delta = m0 - mf
        if np.isclose(delta, 0.0):
            raise ValueError(
                "TGA signal shows no mass change; cannot compute conversion."
            )
        alpha = (m0 - signal) / delta
        return np.clip(alpha, 0.0, 1.0)

    # DSC mode ----------------------------------------------------------------
    if baseline is None:
        # Linear baseline between first and last point
        baseline = np.linspace(signal[0], signal[-1], len(signal))
    else:
        baseline = np.asarray(baseline, dtype=float)

    corrected = signal - baseline

    # Cumulative trapezoid integration with respect to temperature
    cumulative = integrate.cumulative_trapezoid(corrected, temperature, initial=0.0)
    total_area = cumulative[-1]

    if np.isclose(total_area, 0.0):
        raise ValueError(
            "DSC signal area is zero after baseline subtraction; "
            "cannot compute conversion."
        )

    alpha = cumulative / total_area
    return np.clip(alpha, 0.0, 1.0)


def _resolve_kinetic_method(method: str) -> tuple[str, str]:
    token = str(method or "").strip().lower().replace("_", " ").replace("-", " ")
    if token in {"kissinger"}:
        return "kissinger", "Kissinger"
    if token in {"ofw", "ozawa flynn wall", "ozawa flynnwall"}:
        return "ofw", "Ozawa-Flynn-Wall"
    if token in {"friedman"}:
        return "friedman", "Friedman"
    raise ValueError(f"Unsupported kinetic method: {method}")


def _kinetics_rows(method_id: str, results: list[KineticResult]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in results:
        row: dict[str, Any] = {
            "activation_energy_kj_mol": float(item.activation_energy),
            "r_squared": float(item.r_squared) if item.r_squared is not None else None,
        }
        if item.pre_exponential is not None:
            row["pre_exponential"] = float(item.pre_exponential)
        alpha = (item.plot_data or {}).get("alpha")
        if alpha is not None:
            row["alpha"] = float(alpha)
        if method_id == "kissinger":
            row["regression_axis_x"] = "1/Tp"
            row["regression_axis_y"] = "ln(beta/Tp^2)"
        rows.append(row)
    return rows


def _kinetics_summary(method_id: str, results: list[KineticResult]) -> dict[str, Any]:
    if method_id == "kissinger":
        result = results[0]
        return {
            "activation_energy_kj_mol": float(result.activation_energy),
            "pre_exponential": float(result.pre_exponential) if result.pre_exponential is not None else None,
            "r_squared": float(result.r_squared) if result.r_squared is not None else None,
        }

    ea = [float(item.activation_energy) for item in results]
    r2 = [float(item.r_squared) for item in results if item.r_squared is not None]
    return {
        "conversion_point_count": len(results),
        "activation_energy_min_kj_mol": min(ea) if ea else None,
        "activation_energy_max_kj_mol": max(ea) if ea else None,
        "activation_energy_mean_kj_mol": float(np.mean(ea)) if ea else None,
        "mean_r_squared": float(np.mean(r2)) if r2 else None,
    }


def _kinetics_scientific_context(method_id: str, label: str, results: list[KineticResult]) -> dict[str, Any]:
    equations: list[dict[str, Any]]
    if method_id == "kissinger":
        equations = [
            build_equation(
                "Kissinger Linearization",
                "ln(beta / Tp^2) = -Ea / (R * Tp) + ln(A * R / Ea)",
            )
        ]
    elif method_id == "ofw":
        equations = [
            build_equation(
                "OFW Approximation",
                "log(beta) = -0.4567 * Ea / (R * T_alpha) + C",
            )
        ]
    else:
        equations = [
            build_equation(
                "Friedman Differential Form",
                "ln(dalpha/dt) = -Ea / (R * T_alpha) + ln(A * f(alpha))",
            )
        ]

    interpretations = [
        build_interpretation(
            "Kinetic analysis finished successfully.",
            metric="result_count",
            value=len(results),
            unit="result rows",
        )
    ]
    if results:
        interpretations.append(
            build_interpretation(
                "Representative activation energy result.",
                metric="activation_energy_kj_mol",
                value=float(results[0].activation_energy),
                unit="kJ/mol",
            )
        )

    r2 = [float(item.r_squared) for item in results if item.r_squared is not None]
    fit_quality = build_fit_quality(
        {
            "evaluated_rows": len(results),
            "mean_r_squared": float(np.mean(r2)) if r2 else None,
            "min_r_squared": min(r2) if r2 else None,
            "max_r_squared": max(r2) if r2 else None,
        }
    )
    base_context = build_scientific_context(
        methodology={
            "analysis_family": "Kinetic Analysis",
            "method": label,
            "temperature_scale": "kelvin",
        },
        equations=equations,
        numerical_interpretation=interpretations,
        fit_quality=fit_quality,
        limitations=[
            "Interpretation quality depends on heating-rate spread and conversion interpolation quality.",
        ],
    )
    reasoning = build_scientific_reasoning(
        analysis_type=label,
        summary=_kinetics_summary(method_id, results),
        rows=_kinetics_rows(method_id, results),
        metadata={},
        fit_quality=fit_quality,
        validation={},
    )
    merged = dict(base_context)
    merged.update(reasoning)
    return merged


def run_kinetic_analysis(
    method: str,
    *,
    heating_rates: list[float],
    peak_temperatures: list[float] | None = None,
    temperature_data: list[np.ndarray] | None = None,
    conversion_data: list[np.ndarray] | None = None,
    dalpha_dt_data: list[np.ndarray] | None = None,
    alpha_values: Optional[list[float]] = None,
) -> dict[str, Any]:
    """
    Unified kinetics runner with report-ready payloads.

    Returns a dict containing method metadata, raw KineticResult rows, summary,
    and scientific_context for normalized report serialization.
    """
    method_id, method_label = _resolve_kinetic_method(method)

    if method_id == "kissinger":
        if peak_temperatures is None:
            raise ValueError("peak_temperatures is required for Kissinger analysis.")
        result = kissinger_analysis(heating_rates, peak_temperatures)
        results = [result]
    elif method_id == "ofw":
        if temperature_data is None or conversion_data is None:
            raise ValueError("temperature_data and conversion_data are required for OFW analysis.")
        results = ozawa_flynn_wall_analysis(
            heating_rates,
            temperature_data,
            conversion_data,
            alpha_values=alpha_values,
        )
    else:
        if temperature_data is None or conversion_data is None or dalpha_dt_data is None:
            raise ValueError(
                "temperature_data, conversion_data, and dalpha_dt_data are required for Friedman analysis."
            )
        results = friedman_analysis(
            heating_rates,
            temperature_data,
            conversion_data,
            dalpha_dt_data,
            alpha_values=alpha_values,
        )

    rows = _kinetics_rows(method_id, results)
    summary = _kinetics_summary(method_id, results)
    scientific_context = _kinetics_scientific_context(method_id, method_label, results)

    return {
        "method_id": method_id,
        "method_label": method_label,
        "results": results,
        "rows": rows,
        "summary": summary,
        "scientific_context": scientific_context,
    }
