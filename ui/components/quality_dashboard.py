"""Data-quality metrics dashboard.

Computes NaN count, noise level, heating-rate CV, baseline drift, outlier
percentage, SNR, and an overall grade.  Renders an expandable panel with
colour-coded indicators (green / yellow / red).
"""

import numpy as np
import streamlit as st


def compute_quality_metrics(temperature: np.ndarray, signal: np.ndarray) -> dict:
    """Return a dict of quality metrics for a temperature/signal pair."""

    metrics: dict = {}

    # --- NaN count ---
    nan_count = int(np.isnan(signal).sum() + np.isnan(temperature).sum())
    metrics["NaN Count"] = {
        "value": nan_count,
        "display": str(nan_count),
        "level": "green" if nan_count == 0 else "red",
    }

    # Work with finite values only from here on
    mask = np.isfinite(temperature) & np.isfinite(signal)
    t = temperature[mask]
    s = signal[mask]

    if len(s) < 10:
        # Not enough data for meaningful metrics
        return metrics

    # --- Noise level (std of first differences) ---
    noise = float(np.std(np.diff(s)))
    if noise < 0.01:
        nlevel = "green"
    elif noise < 0.1:
        nlevel = "yellow"
    else:
        nlevel = "red"
    metrics["Noise Level"] = {
        "value": noise,
        "display": f"{noise:.4f}",
        "level": nlevel,
    }

    # --- Heating rate CV ---
    dt = np.diff(t)
    if len(dt) > 1 and np.mean(np.abs(dt)) > 1e-12:
        cv = float(np.std(dt) / np.abs(np.mean(dt)))
    else:
        cv = 0.0
    if cv < 0.05:
        cvlevel = "green"
    elif cv < 0.15:
        cvlevel = "yellow"
    else:
        cvlevel = "red"
    metrics["Heating Rate CV"] = {
        "value": cv,
        "display": f"{cv:.4f}",
        "level": cvlevel,
    }

    # --- Baseline drift (normalised slope of linear fit) ---
    if len(s) > 2:
        coeffs = np.polyfit(np.arange(len(s)), s, 1)
        slope = abs(coeffs[0])
        sig_range = float(np.ptp(s)) or 1.0
        norm_drift = slope * len(s) / sig_range
    else:
        norm_drift = 0.0
    if norm_drift < 0.2:
        dlevel = "green"
    elif norm_drift < 0.5:
        dlevel = "yellow"
    else:
        dlevel = "red"
    metrics["Baseline Drift"] = {
        "value": norm_drift,
        "display": f"{norm_drift:.3f}",
        "level": dlevel,
    }

    # --- Outliers (>3-sigma from rolling mean) ---
    win = max(5, len(s) // 50)
    kernel = np.ones(win) / win
    rolling_mean = np.convolve(s, kernel, mode="same")
    residuals = np.abs(s - rolling_mean)
    threshold = 3 * np.std(residuals)
    outlier_frac = float(np.sum(residuals > threshold) / len(s)) if threshold > 0 else 0.0
    if outlier_frac == 0:
        olevel = "green"
    elif outlier_frac < 0.005:
        olevel = "yellow"
    else:
        olevel = "red"
    metrics["Outliers (>3σ)"] = {
        "value": outlier_frac,
        "display": f"{outlier_frac * 100:.2f}%",
        "level": olevel,
    }

    # --- SNR (signal range / noise std) ---
    snr = float(np.ptp(s) / np.std(np.diff(s))) if np.std(np.diff(s)) > 0 else 999.0
    if snr > 10:
        slevel = "green"
    elif snr > 5:
        slevel = "yellow"
    else:
        slevel = "red"
    metrics["SNR"] = {
        "value": snr,
        "display": f"{snr:.1f}",
        "level": slevel,
    }

    # --- Overall grade ---
    red_count = sum(1 for m in metrics.values() if m["level"] == "red")
    yellow_count = sum(1 for m in metrics.values() if m["level"] == "yellow")
    if red_count > 0:
        grade, glevel = "Poor", "red"
    elif yellow_count > 1:
        grade, glevel = "Fair", "yellow"
    else:
        grade, glevel = "Good", "green"
    metrics["Overall Grade"] = {
        "value": grade,
        "display": grade,
        "level": glevel,
    }

    return metrics


_LEVEL_ICONS = {"green": "🟢", "yellow": "🟡", "red": "🔴"}


def render_quality_dashboard(
    temperature: np.ndarray,
    signal: np.ndarray,
    key_prefix: str = "qd",
):
    """Render an expandable data-quality panel below a plot."""
    metrics = compute_quality_metrics(temperature, signal)
    if not metrics:
        return

    grade = metrics.get("Overall Grade", {})
    grade_icon = _LEVEL_ICONS.get(grade.get("level", "green"), "")
    label = f"Data Quality — {grade_icon} {grade.get('display', 'N/A')}"

    with st.expander(label, expanded=False):
        cols = st.columns(len(metrics))
        for col, (name, m) in zip(cols, metrics.items()):
            icon = _LEVEL_ICONS.get(m["level"], "")
            col.markdown(
                f"**{name}**  \n"
                f"{icon} {m['display']}",
            )
