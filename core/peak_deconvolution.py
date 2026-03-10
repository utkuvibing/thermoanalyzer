"""
Multi-peak deconvolution using lmfit.

Supports Gaussian, Lorentzian, and pseudo-Voigt peak shapes.
Initial parameters can be supplied manually or estimated automatically
via scipy.signal.find_peaks.
"""

from __future__ import annotations

import numpy as np
from typing import Optional
from scipy.signal import find_peaks

try:
    from lmfit import CompositeModel, Model, Parameters
    from lmfit.models import GaussianModel, LorentzianModel, PseudoVoigtModel
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "lmfit is required for peak deconvolution. "
        "Install it with:  pip install lmfit"
    ) from exc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def deconvolve_peaks(
    x: np.ndarray,
    y: np.ndarray,
    n_peaks: int,
    peak_shape: str = "gaussian",
    initial_params: Optional[list[dict]] = None,
) -> dict:
    """
    Fit *n_peaks* overlapping peaks to the data (x, y).

    Parameters
    ----------
    x : np.ndarray
        Independent axis (e.g., temperature, wavenumber, 2θ).
    y : np.ndarray
        Signal intensity / heat-flow values.
    n_peaks : int
        Number of peaks to fit.  Must be >= 1.
    peak_shape : {'gaussian', 'lorentzian', 'pseudo_voigt'}
        Functional form for every peak component.
    initial_params : list[dict], optional
        Per-peak initial guesses.  Each dict may contain any subset of:
        ``{'center': float, 'amplitude': float, 'sigma': float}``.
        Missing keys are filled by the auto-estimator.  If *None* the
        auto-estimator is used for all peaks.

    Returns
    -------
    dict with keys:

    ``'params'``
        dict – fitted lmfit Parameters values keyed by parameter name.
    ``'fitted'``
        np.ndarray – total fitted curve evaluated on *x*.
    ``'components'``
        list[np.ndarray] – individual peak contributions on *x*.
    ``'residual'``
        np.ndarray – y minus fitted (should be small / noise-like).
    ``'r_squared'``
        float – coefficient of determination for the total fit.
    ``'report'``
        str – full lmfit fit report.

    Raises
    ------
    ValueError
        If *n_peaks* < 1 or *peak_shape* is not recognised.
    RuntimeError
        If lmfit fails to converge.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    if n_peaks < 1:
        raise ValueError("n_peaks must be >= 1.")

    valid_shapes = {"gaussian", "lorentzian", "pseudo_voigt"}
    if peak_shape.lower() not in valid_shapes:
        raise ValueError(
            f"peak_shape must be one of {valid_shapes!r}, got {peak_shape!r}."
        )

    # Build the composite model and set initial parameters
    composite_model, param_names_per_peak = _build_model(n_peaks, peak_shape)
    auto_estimates = _auto_estimate_params(x, y, n_peaks)

    params = composite_model.make_params()
    used_initial_guesses: list[dict] = []

    for peak_idx in range(n_peaks):
        auto = auto_estimates[peak_idx]
        user = (initial_params[peak_idx] if initial_params and peak_idx < len(initial_params)
                else {})

        center = user.get("center", auto["center"])
        amplitude = user.get("amplitude", auto["amplitude"])
        sigma = user.get("sigma", auto["sigma"])
        used_initial_guesses.append(
            {
                "peak": peak_idx + 1,
                "center": float(center),
                "amplitude": float(amplitude),
                "sigma": float(sigma),
                "source": "user" if user else "auto",
            }
        )

        prefix = f"p{peak_idx + 1}_"
        params[f"{prefix}center"].set(value=center, min=x.min(), max=x.max())
        params[f"{prefix}amplitude"].set(value=amplitude, min=0)
        params[f"{prefix}sigma"].set(value=sigma, min=1e-6)

        if peak_shape.lower() == "pseudo_voigt":
            params[f"{prefix}fraction"].set(value=0.5, min=0.0, max=1.0)

    # Perform the fit
    result = composite_model.fit(y, params, x=x)

    if not result.success and result.aborted:
        raise RuntimeError(
            "lmfit minimisation did not converge. "
            "Try providing better initial_params."
        )

    # Evaluate total fit and individual components
    fitted = result.eval(x=x)
    components = _eval_components(result, x, n_peaks, peak_shape)
    residual = y - fitted
    r_squared = _r_squared(y, fitted)
    rmse = float(np.sqrt(np.mean(residual ** 2)))
    mae = float(np.mean(np.abs(residual)))
    max_abs_residual = float(np.max(np.abs(residual)))
    param_count = sum(1 for key in result.params if not key.startswith("__"))
    dof = max(len(y) - param_count, 1)
    reduced_chi_squared = float(np.sum(residual ** 2) / dof)

    # Collect fitted parameter values into a plain dict
    fitted_params = {name: result.params[name].value for name in result.params}

    return {
        "params": fitted_params,
        "fitted": fitted,
        "components": components,
        "residual": residual,
        "r_squared": r_squared,
        "report": result.fit_report(),
        "initial_guesses": used_initial_guesses,
        "residual_stats": {
            "rmse": rmse,
            "mae": mae,
            "max_abs_residual": max_abs_residual,
            "reduced_chi_squared": reduced_chi_squared,
            "dof": int(dof),
        },
        "fit_quality": {
            "r_squared": r_squared,
            "rmse": rmse,
            "reduced_chi_squared": reduced_chi_squared,
            "dof": int(dof),
        },
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _build_model(
    n_peaks: int,
    peak_shape: str,
) -> tuple[CompositeModel, list[list[str]]]:
    """
    Build an lmfit CompositeModel for *n_peaks* peaks.

    Returns the composite model and a list of parameter-name lists,
    one sub-list per peak.
    """
    shape = peak_shape.lower()
    param_names_per_peak: list[list[str]] = []
    composite: Optional[CompositeModel] = None

    for i in range(n_peaks):
        prefix = f"p{i + 1}_"

        if shape == "gaussian":
            peak_model = GaussianModel(prefix=prefix)
        elif shape == "lorentzian":
            peak_model = LorentzianModel(prefix=prefix)
        else:  # pseudo_voigt
            peak_model = PseudoVoigtModel(prefix=prefix)

        param_names_per_peak.append(list(peak_model.param_names))

        if composite is None:
            composite = peak_model
        else:
            composite = composite + peak_model

    return composite, param_names_per_peak


def _auto_estimate_params(
    x: np.ndarray,
    y: np.ndarray,
    n_peaks: int,
) -> list[dict]:
    """
    Automatically estimate initial center, amplitude, and sigma for each peak.

    Strategy
    --------
    1. Run scipy.signal.find_peaks on the (positive) signal.
    2. If fewer peaks are detected than requested, distribute the remaining
       centers evenly across the x-range.
    3. Amplitude is set to the signal value at the estimated center.
    4. Sigma is set to one quarter of the average spacing between peaks
       (or a fraction of the x-range if only one peak).
    """
    y_pos = np.clip(y, 0, None)

    # Prominence threshold: 5% of the signal range
    prominence = 0.05 * (y_pos.max() - y_pos.min()) if y_pos.max() > y_pos.min() else 0.0

    detected_indices, _ = find_peaks(y_pos, prominence=prominence)

    # Sort by descending height and take up to n_peaks
    if len(detected_indices) > 0:
        order = np.argsort(y_pos[detected_indices])[::-1]
        detected_indices = detected_indices[order]

    centers_x = x[detected_indices].tolist() if len(detected_indices) > 0 else []

    # Pad with evenly spaced positions if we have fewer than n_peaks
    if len(centers_x) < n_peaks:
        evenly_spaced = np.linspace(x.min(), x.max(), n_peaks + 2)[1:-1].tolist()
        existing = set(centers_x)
        for c in evenly_spaced:
            if len(centers_x) >= n_peaks:
                break
            # Avoid duplicating a center that is already close to an existing one
            if not any(abs(c - ex) < (x.max() - x.min()) / (n_peaks * 4) for ex in existing):
                centers_x.append(c)
                existing.add(c)

    # If still not enough (very unlikely), just use evenly spaced
    if len(centers_x) < n_peaks:
        centers_x = np.linspace(x.min(), x.max(), n_peaks + 2)[1:-1].tolist()

    centers_x = sorted(centers_x[:n_peaks])

    # Sigma: ~ quarter of average inter-peak spacing
    if n_peaks > 1:
        avg_spacing = (x.max() - x.min()) / (n_peaks - 1)
        sigma_default = avg_spacing / 4.0
    else:
        sigma_default = (x.max() - x.min()) / 6.0

    sigma_default = max(sigma_default, 1e-6)

    estimates: list[dict] = []
    for c in centers_x:
        # Amplitude at nearest grid point
        idx = int(np.argmin(np.abs(x - c)))
        amp = float(y_pos[idx]) if y_pos[idx] > 0 else float(y_pos.max()) / n_peaks
        estimates.append({"center": c, "amplitude": amp, "sigma": sigma_default})

    return estimates


def _eval_components(
    result,
    x: np.ndarray,
    n_peaks: int,
    peak_shape: str,
) -> list[np.ndarray]:
    """
    Evaluate each individual peak component from the fit result.

    lmfit's eval_components returns a dict keyed by prefix; we reorder
    to match the 1..n_peaks order used in _build_model.
    """
    comp_dict = result.eval_components(x=x)
    components: list[np.ndarray] = []

    for i in range(n_peaks):
        prefix = f"p{i + 1}_"
        if prefix in comp_dict:
            components.append(np.asarray(comp_dict[prefix], dtype=float))
        else:
            # Fallback: zero-filled array (should not happen in normal usage)
            components.append(np.zeros_like(x))

    return components


def _r_squared(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Compute coefficient of determination R²."""
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    if np.isclose(ss_tot, 0.0):
        return 1.0 if np.isclose(ss_res, 0.0) else 0.0
    return float(1.0 - ss_res / ss_tot)
