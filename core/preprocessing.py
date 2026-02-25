"""
preprocessing.py
----------------
Signal preprocessing utilities for thermal analysis data (DSC, TGA, DTA).

Provides smoothing, differentiation, normalization, and interpolation routines
suitable for noisy experimental thermal signals.
"""

import numpy as np
from scipy.signal import savgol_filter
from scipy.ndimage import gaussian_filter1d
from scipy.interpolate import interp1d


# ---------------------------------------------------------------------------
# Smoothing
# ---------------------------------------------------------------------------

def smooth_signal(signal: np.ndarray, method: str = "savgol", **kwargs) -> np.ndarray:
    """
    Smooth a 1-D thermal signal using one of several filters.

    Parameters
    ----------
    signal : np.ndarray
        Raw signal array (e.g., heat-flow in mW, mass in mg).
    method : str
        Smoothing algorithm. One of:
            'savgol'         - Savitzky-Golay filter (default)
            'moving_average' - Simple moving average
            'gaussian'       - Gaussian convolution
    **kwargs
        Algorithm-specific keyword arguments (see below).

    Savitzky-Golay keyword args
    ---------------------------
    window_length : int, default 11
        Must be odd and > polyorder.
    polyorder : int, default 3
        Polynomial order used to fit within each window.

    Moving-average keyword args
    ---------------------------
    window : int, default 11
        Number of points in the averaging window.

    Gaussian keyword args
    ---------------------
    sigma : float, default 2
        Standard deviation of the Gaussian kernel in samples.

    Returns
    -------
    np.ndarray
        Smoothed array of the same length as *signal*.

    Raises
    ------
    ValueError
        If an unknown method name is supplied.
    """
    signal = np.asarray(signal, dtype=float)

    if method == "savgol":
        window_length = kwargs.get("window_length", 11)
        polyorder = kwargs.get("polyorder", 3)
        # Clamp window so it never exceeds the signal length
        window_length = min(window_length, len(signal))
        if window_length % 2 == 0:
            window_length -= 1  # savgol_filter requires an odd window
        if window_length <= polyorder:
            window_length = polyorder + (1 if polyorder % 2 == 0 else 2)
        return savgol_filter(signal, window_length=window_length, polyorder=polyorder)

    elif method == "moving_average":
        window = kwargs.get("window", 11)
        window = min(window, len(signal))
        kernel = np.ones(window) / window
        # 'same' preserves length; edges use partial overlap
        return np.convolve(signal, kernel, mode="same")

    elif method == "gaussian":
        sigma = kwargs.get("sigma", 2)
        return gaussian_filter1d(signal, sigma=sigma)

    else:
        raise ValueError(
            f"Unknown smoothing method '{method}'. "
            "Choose from 'savgol', 'moving_average', or 'gaussian'."
        )


# ---------------------------------------------------------------------------
# Differentiation
# ---------------------------------------------------------------------------

def compute_derivative(
    x: np.ndarray,
    y: np.ndarray,
    order: int = 1,
    smooth_first: bool = True,
    smooth_method: str = "savgol",
    **smooth_kwargs,
) -> np.ndarray:
    """
    Compute the numerical derivative dy/dx using np.gradient.

    For TGA data this yields the DTG curve (rate of mass loss vs. temperature
    or time).  For DSC data the first derivative highlights peak onset/offset
    positions and the second derivative locates inflection points precisely.

    Parameters
    ----------
    x : np.ndarray
        Independent variable (temperature in degC/K, or time in min/s).
    y : np.ndarray
        Dependent variable (mass %, heat flow mW, …).
    order : int, default 1
        Derivative order. 1 -> dy/dx, 2 -> d²y/dx².
    smooth_first : bool, default True
        If True, apply *smooth_signal* to *y* before differentiation to
        reduce noise amplification inherent in numerical differentiation.
    smooth_method : str, default 'savgol'
        Smoothing method forwarded to :func:`smooth_signal`.
    **smooth_kwargs
        Additional keyword arguments forwarded to :func:`smooth_signal`.

    Returns
    -------
    np.ndarray
        Derivative array of the same length as *x* and *y*.

    Raises
    ------
    ValueError
        If *order* is not 1 or 2, or if *x* and *y* have different lengths.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    if x.shape != y.shape:
        raise ValueError(
            f"x and y must have the same length, got {len(x)} and {len(y)}."
        )
    if order not in (1, 2):
        raise ValueError(f"order must be 1 or 2, got {order}.")

    working_y = smooth_signal(y, method=smooth_method, **smooth_kwargs) if smooth_first else y.copy()

    dydx = np.gradient(working_y, x)

    if order == 2:
        # Optionally smooth again before second differentiation to limit
        # noise accumulation.
        if smooth_first:
            dydx = smooth_signal(dydx, method=smooth_method, **smooth_kwargs)
        dydx = np.gradient(dydx, x)

    return dydx


# ---------------------------------------------------------------------------
# Mass normalisation
# ---------------------------------------------------------------------------

def normalize_by_mass(signal: np.ndarray, sample_mass_mg: float) -> np.ndarray:
    """
    Normalize a thermal signal by the sample mass.

    Converts, for example, absolute heat-flow (mW) to specific heat-flow
    (mW/mg) so that results from different sample sizes are comparable.

    Parameters
    ----------
    signal : np.ndarray
        Raw signal array.
    sample_mass_mg : float
        Sample mass in milligrams.  Must be strictly positive.

    Returns
    -------
    np.ndarray
        Signal divided by *sample_mass_mg*, in units of [original unit / mg].

    Raises
    ------
    ValueError
        If *sample_mass_mg* is not strictly positive.
    """
    if sample_mass_mg <= 0:
        raise ValueError(
            f"sample_mass_mg must be > 0, got {sample_mass_mg}."
        )
    return np.asarray(signal, dtype=float) / sample_mass_mg


# ---------------------------------------------------------------------------
# Range normalisation
# ---------------------------------------------------------------------------

def normalize_to_range(
    signal: np.ndarray,
    new_min: float = 0.0,
    new_max: float = 1.0,
) -> np.ndarray:
    """
    Apply min-max normalization to rescale the signal to [new_min, new_max].

    Useful for overlaying signals recorded in different physical units on a
    common scale (e.g., comparing DSC and TGA curves).

    Parameters
    ----------
    signal : np.ndarray
        Input signal array.
    new_min : float, default 0
        Lower bound of the output range.
    new_max : float, default 1
        Upper bound of the output range.

    Returns
    -------
    np.ndarray
        Normalized array of the same length.

    Raises
    ------
    ValueError
        If *new_min* >= *new_max* or if the signal has zero range (flat line).
    """
    if new_min >= new_max:
        raise ValueError(
            f"new_min ({new_min}) must be strictly less than new_max ({new_max})."
        )

    signal = np.asarray(signal, dtype=float)
    sig_min = signal.min()
    sig_max = signal.max()

    if np.isclose(sig_min, sig_max):
        raise ValueError(
            "Signal has zero range (constant array); cannot normalize."
        )

    normalized = (signal - sig_min) / (sig_max - sig_min)
    return normalized * (new_max - new_min) + new_min


# ---------------------------------------------------------------------------
# Interpolation / resampling
# ---------------------------------------------------------------------------

def interpolate_signal(
    x: np.ndarray,
    y: np.ndarray,
    num_points: int = None,
    x_new: np.ndarray = None,
) -> tuple:
    """
    Resample a thermal signal to a uniform or user-specified x-grid.

    Thermal data imported from different instruments often have irregular
    spacing or different sampling densities.  This function resamples to a
    common grid using cubic interpolation, enabling direct array arithmetic
    between datasets.

    Parameters
    ----------
    x : np.ndarray
        Original independent variable (temperature or time).  Must be
        monotonically increasing and free of duplicates.
    y : np.ndarray
        Original signal values corresponding to *x*.
    num_points : int, optional
        If provided, create a uniform grid of *num_points* between
        ``x.min()`` and ``x.max()`` using ``np.linspace``.
        Mutually exclusive with *x_new*.
    x_new : np.ndarray, optional
        Explicit target x-grid.  Values outside [x.min(), x.max()] will
        raise an error (no extrapolation by default).
        Mutually exclusive with *num_points*.

    Returns
    -------
    (x_out, y_out) : tuple of np.ndarray
        Resampled independent and dependent variable arrays.

    Raises
    ------
    ValueError
        If neither or both of *num_points* and *x_new* are supplied, or if
        *x* and *y* have different lengths.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    if x.shape != y.shape:
        raise ValueError(
            f"x and y must have the same length, got {len(x)} and {len(y)}."
        )
    if num_points is None and x_new is None:
        raise ValueError("Provide either num_points or x_new.")
    if num_points is not None and x_new is not None:
        raise ValueError("Provide either num_points or x_new, not both.")

    # Build the interpolator (cubic spline where possible, linear fallback)
    kind = "cubic" if len(x) >= 4 else "linear"
    interpolator = interp1d(x, y, kind=kind, bounds_error=True)

    if num_points is not None:
        x_out = np.linspace(x.min(), x.max(), int(num_points))
    else:
        x_out = np.asarray(x_new, dtype=float)

    y_out = interpolator(x_out)
    return x_out, y_out
