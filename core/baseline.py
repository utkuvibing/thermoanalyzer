"""
baseline.py
-----------
Baseline correction utilities for thermal analysis data (DSC, TGA, DTA).

Wraps pybaselines algorithms and adds a few lightweight custom methods
(linear endpoints, rubber-band convex hull, spline through anchor points).
All functions operate on plain NumPy arrays; no GUI dependencies.
"""

import numpy as np
from scipy.interpolate import interp1d, CubicSpline
from scipy.spatial import ConvexHull

import pybaselines
from pybaselines import Baseline


# ---------------------------------------------------------------------------
# Public method catalogue
# ---------------------------------------------------------------------------

AVAILABLE_METHODS: dict = {
    "asls":       "Asymmetric Least Squares",
    "airpls":     "Adaptive Iteratively Reweighted Penalized Least Squares",
    "modpoly":    "Modified Polynomial",
    "imodpoly":   "Improved Modified Polynomial",
    "snip":       "Statistics-sensitive Non-linear Iterative Peak-clipping",
    "rubberband": "Rubber Band (Convex Hull)",
    "linear":     "Linear between endpoints",
    "spline":     "Spline through anchor points",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _rubberband_baseline(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """
    Compute a rubber-band (convex-hull) baseline.

    The lower convex hull of the (x, y) point set is used as the baseline.
    This mimics manually stretching a rubber band below the spectrum.

    Parameters
    ----------
    x : np.ndarray
        Independent variable array.
    y : np.ndarray
        Signal array.

    Returns
    -------
    np.ndarray
        Baseline array of the same length as *x*.
    """
    points = np.column_stack([x, y])
    hull = ConvexHull(points)

    # Collect all hull vertex indices, then filter to the lower hull by
    # keeping only vertices that form the bottom boundary (minimum y envelope).
    hull_vertices = hull.vertices
    hull_points = points[hull_vertices]

    # Sort hull vertices by x coordinate
    sort_idx = np.argsort(hull_points[:, 0])
    hull_points_sorted = hull_points[sort_idx]

    # Keep only the lower envelope: for each x, take the lowest y on the hull.
    # We do this by interpolating the sorted hull vertices across the full x range.
    baseline_interp = interp1d(
        hull_points_sorted[:, 0],
        hull_points_sorted[:, 1],
        kind="linear",
        bounds_error=False,
        fill_value=(hull_points_sorted[0, 1], hull_points_sorted[-1, 1]),
    )
    baseline = baseline_interp(x)

    # The convex hull includes the upper boundary too; clip baseline so that
    # it never exceeds the original signal.
    baseline = np.minimum(baseline, y)
    return baseline


def _linear_baseline(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """
    Straight line connecting the first and last data points.

    This is the simplest possible baseline and is appropriate when the
    background changes monotonically across the temperature range.

    Parameters
    ----------
    x : np.ndarray
        Independent variable array.
    y : np.ndarray
        Signal array.

    Returns
    -------
    np.ndarray
        Linear baseline array of the same length as *x*.
    """
    slope = (y[-1] - y[0]) / (x[-1] - x[0]) if not np.isclose(x[-1], x[0]) else 0.0
    return y[0] + slope * (x - x[0])


def _spline_baseline(
    x: np.ndarray,
    y: np.ndarray,
    anchor_x: np.ndarray = None,
    anchor_y: np.ndarray = None,
    n_anchors: int = 6,
) -> np.ndarray:
    """
    Cubic-spline baseline through a set of anchor points.

    Anchor points can be supplied explicitly via *anchor_x* / *anchor_y*
    (e.g., user-selected baseline regions in a GUI).  When omitted the
    function selects *n_anchors* evenly-spaced points from the signal that
    are likely to lie on the baseline (local minima in each segment).

    Parameters
    ----------
    x : np.ndarray
        Independent variable array.
    y : np.ndarray
        Signal array.
    anchor_x : np.ndarray, optional
        X-coordinates of user-defined anchor points.
    anchor_y : np.ndarray, optional
        Y-coordinates of user-defined anchor points.
    n_anchors : int, default 6
        Number of automatically selected anchors when explicit anchors are
        not provided.

    Returns
    -------
    np.ndarray
        Spline baseline array of the same length as *x*.
    """
    if anchor_x is not None and anchor_y is not None:
        ax = np.asarray(anchor_x, dtype=float)
        ay = np.asarray(anchor_y, dtype=float)
        sort_idx = np.argsort(ax)
        ax, ay = ax[sort_idx], ay[sort_idx]
    else:
        # Automatic anchor selection: divide x-range into n_anchors segments
        # and pick the minimum y in each segment as the anchor.
        edges = np.linspace(0, len(x), n_anchors + 1, dtype=int)
        ax_list, ay_list = [], []
        for i in range(n_anchors):
            seg_x = x[edges[i]: edges[i + 1]]
            seg_y = y[edges[i]: edges[i + 1]]
            if len(seg_y) == 0:
                continue
            local_min_idx = np.argmin(seg_y)
            ax_list.append(seg_x[local_min_idx])
            ay_list.append(seg_y[local_min_idx])
        ax = np.array(ax_list)
        ay = np.array(ay_list)

    if len(ax) < 2:
        # Degenerate case: fall back to linear
        return _linear_baseline(x, y)

    cs = CubicSpline(ax, ay, extrapolate=True)
    return cs(x)


# ---------------------------------------------------------------------------
# Standalone ALS baseline function (primary public API for DSC)
# ---------------------------------------------------------------------------

def als_baseline(
    x: np.ndarray,
    y: np.ndarray,
    lam: float = 1e6,
    p: float = 0.01,
) -> np.ndarray:
    """
    Asymmetric Least Squares (ALS) baseline correction for DSC signals.

    Fits a smooth baseline that hugs the lower envelope of the signal by
    iteratively re-weighting a penalised least-squares fit.  Small *p* values
    push the baseline below peaks (suitable for DSC where peaks protrude above
    the background); large *lam* values enforce a smooth, slowly varying
    baseline.

    This function is the recommended entry point for the DSC "fully automatic"
    baseline correction workflow.  It follows the exotherm-up / endotherm-down
    convention: positive signal deviations above the baseline correspond to
    exothermic events, negative deviations to endothermic events.

    Parameters
    ----------
    x : np.ndarray
        Temperature (or time) axis; used by pybaselines for polynomial methods
        but does not affect the ALS fit directly.
    y : np.ndarray
        DSC heat-flow signal (same length as *x*).
    lam : float, default 1e6
        Smoothness penalty.  Larger values produce a smoother (less wiggly)
        baseline.  Typical range: 1e3 – 1e8.
    p : float, default 0.01
        Asymmetry parameter.  Values close to 0 push the baseline below peaks;
        values close to 1 push it above.  Typical DSC range: 0.001 – 0.1.

    Returns
    -------
    np.ndarray
        Baseline array of the same length as *y*.

    Raises
    ------
    ValueError
        If *x* and *y* have different lengths, or if *lam* or *p* are
        out of valid range.

    Examples
    --------
    >>> bl = als_baseline(temperature, heat_flow, lam=1e6, p=0.01)
    >>> corrected = heat_flow - bl
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    if x.shape != y.shape:
        raise ValueError(
            f"x and y must have the same length, got {len(x)} and {len(y)}."
        )
    if lam <= 0:
        raise ValueError(f"lam must be positive, got {lam}.")
    if not (0 < p < 1):
        raise ValueError(f"p must be in the open interval (0, 1), got {p}.")

    fitter = Baseline(x_data=x)
    baseline, _ = fitter.asls(y, lam=lam, p=p)
    return baseline


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------

def correct_baseline(
    x: np.ndarray,
    y: np.ndarray,
    method: str = "asls",
    region: tuple = None,
    **kwargs,
) -> tuple:
    """
    Subtract a baseline from a thermal signal.

    Wraps pybaselines algorithms and adds lightweight custom methods
    ('rubberband', 'linear', 'spline').  Returns both the corrected signal
    and the baseline itself so callers can inspect or plot the fit.

    Parameters
    ----------
    x : np.ndarray
        Independent variable (temperature in degC/K or time in min/s).
    y : np.ndarray
        Raw signal (heat flow mW, mass %, …).
    method : str, default 'asls'
        Baseline algorithm.  Must be a key in :data:`AVAILABLE_METHODS`.
    region : tuple (x_min, x_max), optional
        If provided, baseline estimation is performed only within this
        temperature / time window.  Data outside the region are returned
        unchanged and the baseline is linearly extrapolated to the full range.
    **kwargs
        Method-specific parameters.  Defaults are chosen for typical thermal
        analysis data; see individual algorithm documentation below.

        asls      : lam=1e6, p=0.01
        airpls    : lam=1e6
        modpoly   : poly_order=6
        imodpoly  : poly_order=6
        snip      : max_half_window=40
        rubberband: (no extra parameters)
        linear    : (no extra parameters)
        spline    : anchor_x=None, anchor_y=None, n_anchors=6

    Returns
    -------
    (corrected_signal, baseline) : tuple of np.ndarray
        Both arrays have the same length as *y*.
        ``corrected_signal = y - baseline``

    Raises
    ------
    ValueError
        If *method* is not in :data:`AVAILABLE_METHODS`, or if *x* and *y*
        have different lengths, or if *region* bounds are outside *x*.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    if x.shape != y.shape:
        raise ValueError(
            f"x and y must have the same length, got {len(x)} and {len(y)}."
        )
    if method not in AVAILABLE_METHODS:
        raise ValueError(
            f"Unknown method '{method}'. "
            f"Available methods: {list(AVAILABLE_METHODS.keys())}"
        )

    # --- Optional region masking -------------------------------------------
    if region is not None:
        x_min_reg, x_max_reg = float(region[0]), float(region[1])
        if x_min_reg >= x_max_reg:
            raise ValueError("region[0] must be strictly less than region[1].")
        mask = (x >= x_min_reg) & (x <= x_max_reg)
        if mask.sum() < 4:
            raise ValueError(
                f"Region ({x_min_reg}, {x_max_reg}) contains fewer than 4 "
                "data points; cannot fit a reliable baseline."
            )
        x_reg, y_reg = x[mask], y[mask]
        baseline_reg = _compute_baseline_array(x_reg, y_reg, method, **kwargs)

        # Linearly extrapolate the region baseline across the full x range
        extrap = interp1d(
            x_reg, baseline_reg,
            kind="linear",
            bounds_error=False,
            fill_value=(baseline_reg[0], baseline_reg[-1]),
        )
        baseline = extrap(x)
    else:
        baseline = _compute_baseline_array(x, y, method, **kwargs)

    corrected_signal = y - baseline
    return corrected_signal, baseline


# ---------------------------------------------------------------------------
# Internal dispatch
# ---------------------------------------------------------------------------

def _compute_baseline_array(
    x: np.ndarray,
    y: np.ndarray,
    method: str,
    **kwargs,
) -> np.ndarray:
    """
    Dispatch to the appropriate baseline algorithm and return a baseline array.

    Parameters
    ----------
    x : np.ndarray
        Independent variable (used as-is for custom methods; pybaselines
        algorithms receive only *y* and use index-based fitting internally).
    y : np.ndarray
        Signal array.
    method : str
        Algorithm name from :data:`AVAILABLE_METHODS`.
    **kwargs
        Forwarded to the selected algorithm.

    Returns
    -------
    np.ndarray
        Baseline array of the same length as *y*.
    """
    # ------------------------------------------------------------------
    # Custom lightweight methods (no pybaselines)
    # ------------------------------------------------------------------
    if method == "rubberband":
        return _rubberband_baseline(x, y)

    if method == "linear":
        return _linear_baseline(x, y)

    if method == "spline":
        anchor_x = kwargs.pop("anchor_x", None)
        anchor_y = kwargs.pop("anchor_y", None)
        n_anchors = kwargs.pop("n_anchors", 6)
        return _spline_baseline(x, y, anchor_x=anchor_x, anchor_y=anchor_y, n_anchors=n_anchors)

    # ------------------------------------------------------------------
    # pybaselines-backed methods
    # ------------------------------------------------------------------
    # pybaselines.Baseline works with x_data for polynomial methods; for
    # iterative penalized methods (asls, airpls) x_data is ignored but
    # passing it does no harm.
    fitter = Baseline(x_data=x)

    if method == "asls":
        lam = kwargs.get("lam", 1e6)
        p   = kwargs.get("p",   0.01)
        baseline = als_baseline(x, y, lam=lam, p=p)

    elif method == "airpls":
        lam = kwargs.get("lam", 1e6)
        baseline, _ = fitter.airpls(y, lam=lam)

    elif method == "modpoly":
        poly_order = kwargs.get("poly_order", 6)
        baseline, _ = fitter.modpoly(y, poly_order=poly_order)

    elif method == "imodpoly":
        poly_order = kwargs.get("poly_order", 6)
        baseline, _ = fitter.imodpoly(y, poly_order=poly_order)

    elif method == "snip":
        max_half_window = kwargs.get("max_half_window", 40)
        baseline, _ = fitter.snip(y, max_half_window=max_half_window)

    else:
        # Fallback: should never be reached given the earlier validation
        raise ValueError(f"Unhandled method '{method}'.")

    return baseline


# ---------------------------------------------------------------------------
# Baseline quality metrics
# ---------------------------------------------------------------------------

def estimate_baseline_quality(
    y_original: np.ndarray,
    baseline: np.ndarray,
) -> dict:
    """
    Compute diagnostic metrics that characterise how well a baseline fits
    the background of a thermal signal.

    A good baseline sits smoothly under the peaks without introducing
    artefacts; these metrics help compare candidate algorithms or parameter
    settings programmatically.

    Parameters
    ----------
    y_original : np.ndarray
        Original (uncorrected) signal.
    baseline : np.ndarray
        Estimated baseline array of the same length as *y_original*.

    Returns
    -------
    dict with keys
        residual_std : float
            Standard deviation of the residual ``y_original - baseline``.
            Lower values indicate the baseline tracks the background closely.
            Very low values may indicate over-fitting.
        smoothness : float
            Root-mean-square of the second-order finite differences of the
            baseline:
                ``RMS( diff(diff(baseline)) )``
            A smooth baseline should have a low smoothness score.  Jagged
            baselines produce large values.
        snr : float
            Approximate signal-to-noise ratio:
                ``peak-to-peak amplitude of corrected signal
                  / std(corrected signal)``
            Interpreted loosely: higher SNR suggests the correction preserved
            the genuine thermal features while removing the background.

    Raises
    ------
    ValueError
        If *y_original* and *baseline* have different lengths.
    """
    y_original = np.asarray(y_original, dtype=float)
    baseline   = np.asarray(baseline,   dtype=float)

    if y_original.shape != baseline.shape:
        raise ValueError(
            f"y_original and baseline must have the same length, "
            f"got {len(y_original)} and {len(baseline)}."
        )

    residual = y_original - baseline

    # 1. Residual standard deviation
    residual_std = float(np.std(residual))

    # 2. Baseline smoothness (second-difference RMS)
    second_diff = np.diff(np.diff(baseline))
    if len(second_diff) > 0:
        smoothness = float(np.sqrt(np.mean(second_diff ** 2)))
    else:
        smoothness = 0.0

    # 3. Signal-to-noise ratio of the corrected signal
    corrected_amplitude = float(residual.max() - residual.min())
    corrected_std = float(np.std(residual))
    if corrected_std > 0:
        snr = corrected_amplitude / corrected_std
    else:
        snr = float("inf")

    return {
        "residual_std": residual_std,
        "smoothness":   smoothness,
        "snr":          snr,
    }
