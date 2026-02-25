"""
Peak detection and characterisation for thermal analysis signals.

Provides scipy-backed peak finding with thermal-analysis defaults and a suite
of characterisation helpers (onset/endset via tangent construction, FWHM,
integrated area).  All public functions operate on plain NumPy arrays so they
are independent of any I/O or UI layer.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
from scipy.signal import find_peaks, peak_widths
from scipy.interpolate import interp1d


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class ThermalPeak:
    """Container for a single detected thermal peak and its derived metrics."""

    peak_index: int
    peak_temperature: float          # Temperature at peak maximum
    peak_signal: float               # Signal value at peak maximum
    onset_temperature: Optional[float] = None   # Tangent-construction onset
    endset_temperature: Optional[float] = None  # Tangent-construction endset
    area: Optional[float] = None     # Integrated area (enthalpy for DSC)
    fwhm: Optional[float] = None     # Full width at half maximum [temperature units]
    peak_type: str = 'unknown'       # 'endotherm', 'exotherm', 'step'
    height: Optional[float] = None   # Peak height above local baseline


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_linregress(x: np.ndarray, y: np.ndarray):
    """Return (slope, intercept) for a least-squares fit of y on x."""
    if len(x) < 2:
        return 0.0, float(np.mean(y)) if len(y) > 0 else 0.0
    A = np.vstack([x, np.ones(len(x))]).T
    result = np.linalg.lstsq(A, y, rcond=None)
    slope, intercept = result[0]
    return float(slope), float(intercept)


def _estimate_fwhm_indices(signal: np.ndarray, peak_idx: int, half_value: float):
    """
    Return the (left_idx, right_idx) indices where the signal crosses
    half_value on each side of peak_idx.  Falls back to array bounds when
    no crossing is found.
    """
    n = len(signal)

    # Left crossing
    left_idx = 0
    for i in range(peak_idx, -1, -1):
        if signal[i] <= half_value:
            left_idx = i
            break

    # Right crossing
    right_idx = n - 1
    for i in range(peak_idx, n):
        if signal[i] <= half_value:
            right_idx = i
            break

    return left_idx, right_idx


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_thermal_peaks(
    temperature: np.ndarray,
    signal: np.ndarray,
    prominence: Optional[float] = None,
    height: Optional[float] = None,
    distance: Optional[int] = None,
    width: Optional[float] = None,
    direction: str = 'both',
) -> List[ThermalPeak]:
    """
    Detect peaks in a thermal analysis signal using scipy.signal.find_peaks
    with thermal-analysis appropriate defaults.

    Parameters
    ----------
    temperature:
        1-D array of temperatures (x-axis).
    signal:
        1-D array of the measured signal (same length as temperature).
    prominence:
        Minimum peak prominence.  Defaults to 10 % of the signal range.
    height:
        Minimum absolute height for a peak.
    distance:
        Minimum sample distance between neighbouring peaks.
        Defaults to len(signal) // 20 (at least 1).
    width:
        Minimum peak width in samples.
    direction:
        'up'   - detect upward peaks only (exotherms in heat-flow convention).
        'down' - detect downward peaks only (endotherms).
        'both' - detect peaks in both directions.

    Returns
    -------
    List of ThermalPeak objects sorted by peak_index.
    """
    temperature = np.asarray(temperature, dtype=float)
    signal = np.asarray(signal, dtype=float)

    if temperature.shape != signal.shape:
        raise ValueError(
            f"temperature and signal must have the same length, "
            f"got {temperature.shape} and {signal.shape}."
        )

    n = len(signal)
    if n < 3:
        return []

    sig_range = float(np.ptp(signal))
    if prominence is None:
        prominence = max(sig_range * 0.10, 1e-12)

    if distance is None:
        distance = max(1, n // 20)

    kwargs = dict(prominence=prominence, distance=distance)
    if height is not None:
        kwargs['height'] = height
    if width is not None:
        kwargs['width'] = width

    peaks: List[ThermalPeak] = []

    def _collect(sig_work: np.ndarray, ptype: str) -> None:
        idxs, _ = find_peaks(sig_work, **kwargs)
        for idx in idxs:
            p = ThermalPeak(
                peak_index=int(idx),
                peak_temperature=float(temperature[idx]),
                peak_signal=float(signal[idx]),
                peak_type=ptype,
            )
            peaks.append(p)

    if direction in ('up', 'both'):
        _collect(signal, 'exotherm')

    if direction in ('down', 'both'):
        _collect(-signal, 'endotherm')

    # Deduplicate (same index can appear if signal has a flat top)
    seen: set[int] = set()
    unique_peaks: List[ThermalPeak] = []
    for p in sorted(peaks, key=lambda x: x.peak_index):
        if p.peak_index not in seen:
            seen.add(p.peak_index)
            unique_peaks.append(p)

    return unique_peaks


# ---------------------------------------------------------------------------

def compute_onset_temperature(
    temperature: np.ndarray,
    signal: np.ndarray,
    peak_idx: int,
    side: str = 'left',
) -> float:
    """
    Compute onset (side='left') or endset (side='right') temperature using
    the standard tangent-construction method.

    Algorithm
    ---------
    1. Estimate a rough FWHM from the peak to bound the analysis region.
    2. On the chosen side, locate the inflection point (maximum of
       |dSignal/dT| in that region).
    3. Fit a tangent line through the inflection point.
    4. Fit a linear baseline to the flat region well away from the peak.
    5. Return the intersection of tangent and baseline.

    Parameters
    ----------
    temperature:
        1-D temperature array.
    signal:
        1-D signal array.
    peak_idx:
        Index of the peak maximum.
    side:
        'left' for onset, 'right' for endset.

    Returns
    -------
    Intersection temperature as a float.  Falls back to peak_temperature
    if the geometry is degenerate.
    """
    temperature = np.asarray(temperature, dtype=float)
    signal = np.asarray(signal, dtype=float)
    n = len(temperature)

    peak_val = signal[peak_idx]

    # --- estimate FWHM to define the analysis window -------------------------
    half_val = peak_val / 2.0  # rough half-maximum (baseline ~ 0)
    raw_left, raw_right = _estimate_fwhm_indices(signal, peak_idx, half_val)
    rough_fwhm_samples = max(raw_right - raw_left, 5)

    window = int(rough_fwhm_samples * 3)

    if side == 'left':
        region_start = max(0, peak_idx - window)
        region_end = peak_idx
    else:
        region_start = peak_idx
        region_end = min(n - 1, peak_idx + window)

    if region_end <= region_start + 2:
        return float(temperature[peak_idx])

    t_region = temperature[region_start:region_end + 1]
    s_region = signal[region_start:region_end + 1]

    # --- derivative and inflection -------------------------------------------
    ds_dt = np.gradient(s_region, t_region)
    abs_deriv = np.abs(ds_dt)
    infl_local = int(np.argmax(abs_deriv))
    infl_global = region_start + infl_local

    # Tangent line at inflection point: y = m*(T - T_infl) + s_infl
    t_infl = float(temperature[infl_global])
    s_infl = float(signal[infl_global])
    m_tangent = float(ds_dt[infl_local])

    # --- baseline region (flat area far from peak) ---------------------------
    baseline_samples = max(5, window // 3)

    if side == 'left':
        bl_start = max(0, region_start - baseline_samples)
        bl_end = max(0, region_start)
    else:
        bl_start = min(n - 1, region_end)
        bl_end = min(n - 1, region_end + baseline_samples)

    if bl_end <= bl_start:
        # Fall back to a horizontal baseline at the region edge
        bl_slope, bl_intercept = 0.0, float(signal[region_start if side == 'left' else region_end])
    else:
        t_bl = temperature[bl_start:bl_end + 1]
        s_bl = signal[bl_start:bl_end + 1]
        bl_slope, bl_intercept = _safe_linregress(t_bl, s_bl)

    # --- intersection: tangent vs baseline -----------------------------------
    # tangent:  s = m_tangent * (T - t_infl) + s_infl
    #         = m_tangent*T + (s_infl - m_tangent*t_infl)
    # baseline: s = bl_slope*T + bl_intercept
    # solve:   (m_tangent - bl_slope)*T = bl_intercept - s_infl + m_tangent*t_infl

    denom = m_tangent - bl_slope
    if abs(denom) < 1e-12:
        # Lines are parallel; return the peak temperature as a safe fallback
        return float(temperature[peak_idx])

    t_intersect = (bl_intercept - s_infl + m_tangent * t_infl) / denom

    # Clamp to array bounds
    t_min = float(temperature[0])
    t_max = float(temperature[-1])
    t_intersect = float(np.clip(t_intersect, t_min, t_max))

    return t_intersect


# ---------------------------------------------------------------------------

def compute_endset_temperature(
    temperature: np.ndarray,
    signal: np.ndarray,
    peak_idx: int,
) -> float:
    """
    Compute endset temperature using the right-side tangent construction.

    Delegates to compute_onset_temperature with side='right'.

    Parameters
    ----------
    temperature:
        1-D temperature array.
    signal:
        1-D signal array.
    peak_idx:
        Index of the peak maximum.

    Returns
    -------
    Endset temperature as a float.
    """
    return compute_onset_temperature(temperature, signal, peak_idx, side='right')


# ---------------------------------------------------------------------------

def integrate_peak(
    temperature: np.ndarray,
    signal: np.ndarray,
    baseline: np.ndarray,
    left_idx: int,
    right_idx: int,
) -> float:
    """
    Integrate (signal - baseline) over the temperature interval
    [left_idx, right_idx] using the trapezoidal rule.

    Parameters
    ----------
    temperature:
        Full 1-D temperature array.
    signal:
        Full 1-D signal array.
    baseline:
        Full 1-D baseline array (same length as signal).
    left_idx:
        Start index of integration window.
    right_idx:
        End index of integration window (inclusive).

    Returns
    -------
    Signed area.  Positive when the signal lies above the baseline (endotherm
    in a heat-flow-up convention); negative when below.
    """
    temperature = np.asarray(temperature, dtype=float)
    signal = np.asarray(signal, dtype=float)
    baseline = np.asarray(baseline, dtype=float)

    left_idx = int(np.clip(left_idx, 0, len(temperature) - 1))
    right_idx = int(np.clip(right_idx, 0, len(temperature) - 1))

    if left_idx >= right_idx:
        return 0.0

    t_seg = temperature[left_idx:right_idx + 1]
    net_signal = signal[left_idx:right_idx + 1] - baseline[left_idx:right_idx + 1]

    # Use numpy.trapezoid (NumPy >= 2.0) with fallback to np.trapz
    try:
        area = float(np.trapezoid(net_signal, t_seg))
    except AttributeError:
        area = float(np.trapz(net_signal, t_seg))

    return area


# ---------------------------------------------------------------------------

def compute_fwhm(
    temperature: np.ndarray,
    signal: np.ndarray,
    peak_idx: int,
    baseline_value: float = 0.0,
) -> float:
    """
    Compute the full width at half maximum (FWHM) of a peak relative to a
    baseline level.

    The half-maximum level is defined as:
        level = baseline_value + (signal[peak_idx] - baseline_value) / 2

    Linear interpolation is used to find sub-sample crossing positions.

    Parameters
    ----------
    temperature:
        1-D temperature array.
    signal:
        1-D signal array.
    peak_idx:
        Index of the peak maximum.
    baseline_value:
        Baseline signal level (default 0).

    Returns
    -------
    FWHM in the same units as temperature.  Returns 0.0 if the half-maximum
    crossing cannot be determined.
    """
    temperature = np.asarray(temperature, dtype=float)
    signal = np.asarray(signal, dtype=float)
    n = len(signal)

    peak_height = float(signal[peak_idx]) - baseline_value
    if peak_height == 0.0:
        return 0.0

    half_level = baseline_value + peak_height / 2.0

    # --- left crossing -------------------------------------------------------
    t_left = float(temperature[0])
    for i in range(peak_idx, 0, -1):
        if signal[i - 1] <= half_level <= signal[i]:
            # Linear interpolation
            frac = (half_level - signal[i - 1]) / (signal[i] - signal[i - 1])
            t_left = float(temperature[i - 1]) + frac * (
                float(temperature[i]) - float(temperature[i - 1])
            )
            break
        if signal[i] < half_level:
            t_left = float(temperature[i])
            break

    # --- right crossing ------------------------------------------------------
    t_right = float(temperature[-1])
    for i in range(peak_idx, n - 1):
        if signal[i + 1] <= half_level <= signal[i]:
            frac = (signal[i] - half_level) / (signal[i] - signal[i + 1])
            t_right = float(temperature[i]) + frac * (
                float(temperature[i + 1]) - float(temperature[i])
            )
            break
        if signal[i] < half_level:
            t_right = float(temperature[i])
            break

    fwhm = max(0.0, t_right - t_left)
    return float(fwhm)


# ---------------------------------------------------------------------------

def characterize_peaks(
    temperature: np.ndarray,
    signal: np.ndarray,
    peaks: List[ThermalPeak],
    baseline: Optional[np.ndarray] = None,
) -> List[ThermalPeak]:
    """
    Augment each ThermalPeak with onset, endset, area, height, and FWHM.

    For each peak the integration window is estimated from the FWHM
    (window = peak_index +/- 2*FWHM_samples, clamped to array bounds).

    Parameters
    ----------
    temperature:
        1-D temperature array.
    signal:
        1-D signal array.
    peaks:
        List of ThermalPeak objects (as returned by find_thermal_peaks).
    baseline:
        Optional 1-D baseline array.  When None a linear baseline is
        constructed for each peak individually by connecting the signal
        values at the left and right integration boundaries.

    Returns
    -------
    The same list with onset_temperature, endset_temperature, area, fwhm,
    and height filled in.
    """
    temperature = np.asarray(temperature, dtype=float)
    signal = np.asarray(signal, dtype=float)
    n = len(temperature)

    has_global_baseline = baseline is not None
    if has_global_baseline:
        baseline = np.asarray(baseline, dtype=float)

    for pk in peaks:
        idx = int(pk.peak_index)

        # --- onset / endset --------------------------------------------------
        try:
            pk.onset_temperature = compute_onset_temperature(
                temperature, signal, idx, side='left'
            )
        except Exception as exc:
            warnings.warn(f"Onset computation failed for peak at index {idx}: {exc}")
            pk.onset_temperature = float(temperature[idx])

        try:
            pk.endset_temperature = compute_endset_temperature(
                temperature, signal, idx
            )
        except Exception as exc:
            warnings.warn(f"Endset computation failed for peak at index {idx}: {exc}")
            pk.endset_temperature = float(temperature[idx])

        # --- FWHM ------------------------------------------------------------
        # Determine local baseline level for FWHM calculation
        if has_global_baseline:
            bl_at_peak = float(baseline[idx])
        else:
            bl_at_peak = 0.0  # will be updated with local linear baseline below

        pk.fwhm = compute_fwhm(temperature, signal, idx, baseline_value=bl_at_peak)

        # --- integration window from FWHM ------------------------------------
        # Map FWHM (temperature units) to an approximate sample count
        dt_mean = float(np.mean(np.diff(temperature)))
        if dt_mean > 0 and pk.fwhm > 0:
            fwhm_samples = int(pk.fwhm / dt_mean)
        else:
            fwhm_samples = max(5, n // 40)

        win = max(int(fwhm_samples * 2), 5)
        left_idx = max(0, idx - win)
        right_idx = min(n - 1, idx + win)

        # --- build or slice baseline -----------------------------------------
        if has_global_baseline:
            bl_for_integration = baseline
        else:
            # Linear interpolation between boundary signal values
            t_l = float(temperature[left_idx])
            t_r = float(temperature[right_idx])
            s_l = float(signal[left_idx])
            s_r = float(signal[right_idx])
            if t_r > t_l:
                slope = (s_r - s_l) / (t_r - t_l)
            else:
                slope = 0.0
            local_bl = s_l + slope * (temperature - t_l)
            bl_for_integration = local_bl

            # Recompute FWHM with the local baseline level at peak
            bl_at_peak = float(bl_for_integration[idx])
            pk.fwhm = compute_fwhm(
                temperature, signal, idx, baseline_value=bl_at_peak
            )

        # --- area ------------------------------------------------------------
        pk.area = integrate_peak(
            temperature, signal, bl_for_integration, left_idx, right_idx
        )

        # --- height ----------------------------------------------------------
        if has_global_baseline:
            pk.height = float(signal[idx]) - float(baseline[idx])
        else:
            pk.height = float(signal[idx]) - float(bl_for_integration[idx])

    return peaks
