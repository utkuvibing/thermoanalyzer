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
from typing import Optional
from scipy import integrate, interpolate, stats

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
