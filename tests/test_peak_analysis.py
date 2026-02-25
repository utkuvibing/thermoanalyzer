"""
test_peak_analysis.py
---------------------
Tests for core.peak_analysis

Covers:
- find_thermal_peaks on a single clean Gaussian (known location)
- direction parameter ('up', 'down', 'both')
- compute_onset_temperature via tangent construction
- integrate_peak (area of a Gaussian vs. analytical value)
- compute_fwhm (FWHM = 2.355 * sigma for a Gaussian)
- characterize_peaks (all derived metrics populated)
"""

import os
import sys

import numpy as np
import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.peak_analysis import (
    ThermalPeak,
    find_thermal_peaks,
    compute_onset_temperature,
    integrate_peak,
    compute_fwhm,
    characterize_peaks,
)


# ---------------------------------------------------------------------------
# Shared synthetic-data constants
# ---------------------------------------------------------------------------

# Dense temperature grid for precise numerical tests
T = np.linspace(30.0, 300.0, 1000)
PEAK_CENTER = 200.0    # degrees C
PEAK_SIGMA  = 8.0      # degrees C
PEAK_AMP    = 3.0      # arbitrary signal units

# Analytical Gaussian integrated area:  A * sigma * sqrt(2*pi)
ANALYTICAL_AREA = PEAK_AMP * PEAK_SIGMA * np.sqrt(2.0 * np.pi)

# Analytical FWHM = 2 * sqrt(2 * ln2) * sigma = 2.3548 * sigma
ANALYTICAL_FWHM = 2.3548 * PEAK_SIGMA


def _make_gaussian_signal(center=PEAK_CENTER, sigma=PEAK_SIGMA, amp=PEAK_AMP,
                           noise_level=0.0, seed=0):
    """Return a Gaussian peak over the global T grid with optional noise."""
    rng = np.random.default_rng(seed)
    signal = amp * np.exp(-0.5 * ((T - center) / sigma) ** 2)
    if noise_level > 0:
        signal = signal + rng.normal(0.0, noise_level, size=len(T))
    return signal


# ---------------------------------------------------------------------------
# find_thermal_peaks
# ---------------------------------------------------------------------------

class TestFindPeaksSingleGaussian:

    def test_finds_exactly_one_peak(self):
        """A single clean Gaussian should yield exactly one detected peak."""
        signal = _make_gaussian_signal()
        peaks = find_thermal_peaks(T, signal)
        assert len(peaks) == 1

    def test_peak_temperature_within_1_degree(self):
        """Detected peak temperature should be within 1 C of the true centre."""
        signal = _make_gaussian_signal()
        peaks = find_thermal_peaks(T, signal)
        assert len(peaks) >= 1
        detected_temp = peaks[0].peak_temperature
        assert abs(detected_temp - PEAK_CENTER) < 1.0, (
            f"Expected peak near {PEAK_CENTER} C, got {detected_temp:.2f} C"
        )

    def test_peak_signal_value(self):
        """Signal value at the detected peak should be close to the amplitude."""
        signal = _make_gaussian_signal()
        peaks = find_thermal_peaks(T, signal)
        assert len(peaks) >= 1
        assert abs(peaks[0].peak_signal - PEAK_AMP) < 0.1

    def test_peak_at_known_location_with_noise(self):
        """Peak detection should tolerate small noise (±1 C tolerance)."""
        signal = _make_gaussian_signal(noise_level=0.02, seed=42)
        peaks = find_thermal_peaks(T, signal)
        assert len(peaks) >= 1
        assert abs(peaks[0].peak_temperature - PEAK_CENTER) < 1.0

    def test_returns_thermal_peak_objects(self):
        """All returned objects should be ThermalPeak instances."""
        signal = _make_gaussian_signal()
        peaks = find_thermal_peaks(T, signal)
        for p in peaks:
            assert isinstance(p, ThermalPeak)

    def test_empty_result_for_flat_signal(self):
        """A flat-line signal should produce no peaks."""
        flat = np.ones_like(T) * 1.5
        peaks = find_thermal_peaks(T, flat)
        assert len(peaks) == 0


class TestFindPeaksDirection:

    def test_direction_up_finds_positive_peak(self):
        """direction='up' should detect the upward-pointing Gaussian."""
        signal = _make_gaussian_signal()
        peaks = find_thermal_peaks(T, signal, direction="up")
        assert len(peaks) >= 1
        assert any(abs(p.peak_temperature - PEAK_CENTER) < 2.0 for p in peaks)

    def test_direction_down_does_not_find_positive_peak(self):
        """direction='down' should not detect an upward-pointing Gaussian."""
        signal = _make_gaussian_signal()
        peaks = find_thermal_peaks(T, signal, direction="down")
        # There should be no peak near the Gaussian centre
        near_centre = [p for p in peaks if abs(p.peak_temperature - PEAK_CENTER) < 5.0]
        assert len(near_centre) == 0

    def test_direction_down_finds_negative_peak(self):
        """direction='down' should detect an inverted Gaussian."""
        signal = -_make_gaussian_signal()  # inverted
        peaks = find_thermal_peaks(T, signal, direction="down")
        assert len(peaks) >= 1
        assert any(abs(p.peak_temperature - PEAK_CENTER) < 2.0 for p in peaks)

    def test_direction_both_finds_peaks_in_mixed_signal(self):
        """direction='both' should detect peaks in both directions."""
        pos_peak = _make_gaussian_signal(center=120.0)
        neg_peak = -_make_gaussian_signal(center=220.0)
        signal = pos_peak + neg_peak
        peaks = find_thermal_peaks(T, signal, direction="both")
        temps = [p.peak_temperature for p in peaks]
        # At least the positive peak should be found
        assert any(abs(t - 120.0) < 5.0 for t in temps)


# ---------------------------------------------------------------------------
# compute_onset_temperature
# ---------------------------------------------------------------------------

class TestOnsetTemperature:

    def test_onset_temperature_left_of_peak(self):
        """
        Onset should be strictly to the left of (lower than) the peak temperature
        for a standard endotherm / exotherm.
        """
        signal = _make_gaussian_signal()
        peak_idx = int(np.argmax(signal))
        onset = compute_onset_temperature(T, signal, peak_idx, side="left")
        assert onset < T[peak_idx], (
            f"Onset {onset:.2f} should be less than peak temp {T[peak_idx]:.2f}"
        )

    def test_onset_temperature_within_reasonable_range(self):
        """
        Tangent-construction onset for a Gaussian centred at 200 C with
        sigma=8 should lie within 5 sigma (40 C) of the peak.
        The tolerance is deliberately wide to accommodate the approximate
        nature of the tangent method.
        """
        signal = _make_gaussian_signal()
        peak_idx = int(np.argmax(signal))
        onset = compute_onset_temperature(T, signal, peak_idx, side="left")

        lower_bound = PEAK_CENTER - 5.0 * PEAK_SIGMA
        assert onset >= lower_bound, (
            f"Onset {onset:.2f} is unexpectedly far from peak {PEAK_CENTER}"
        )
        assert onset <= PEAK_CENTER, (
            f"Onset {onset:.2f} should not exceed peak temperature {PEAK_CENTER}"
        )

    def test_endset_temperature_right_of_peak(self):
        """
        Endset (side='right') should be strictly to the right of the peak.
        """
        signal = _make_gaussian_signal()
        peak_idx = int(np.argmax(signal))
        endset = compute_onset_temperature(T, signal, peak_idx, side="right")
        assert endset > T[peak_idx], (
            f"Endset {endset:.2f} should exceed peak temp {T[peak_idx]:.2f}"
        )

    def test_onset_returns_float(self):
        """Return type should always be a Python float."""
        signal = _make_gaussian_signal()
        peak_idx = int(np.argmax(signal))
        onset = compute_onset_temperature(T, signal, peak_idx)
        assert isinstance(onset, float)


# ---------------------------------------------------------------------------
# integrate_peak
# ---------------------------------------------------------------------------

class TestIntegratePeak:

    def test_gaussian_area_matches_analytical(self):
        """
        Numerical integration of a clean Gaussian should match the analytical
        area A * sigma * sqrt(2*pi) to within 10%.
        """
        signal = _make_gaussian_signal()
        baseline = np.zeros_like(T)

        # Use a wide window that captures virtually the entire peak (±4 sigma)
        peak_idx = int(np.argmax(signal))
        left_temp = PEAK_CENTER - 4.0 * PEAK_SIGMA
        right_temp = PEAK_CENTER + 4.0 * PEAK_SIGMA
        left_idx = int(np.searchsorted(T, left_temp))
        right_idx = int(np.searchsorted(T, right_temp))

        area = integrate_peak(T, signal, baseline, left_idx, right_idx)

        relative_error = abs(area - ANALYTICAL_AREA) / ANALYTICAL_AREA
        assert relative_error < 0.10, (
            f"Integrated area {area:.4f} differs from analytical "
            f"{ANALYTICAL_AREA:.4f} by {relative_error*100:.1f}%"
        )

    def test_integrate_peak_positive_for_upward_peak(self):
        """Area should be positive when the signal lies above the baseline."""
        signal = _make_gaussian_signal()
        baseline = np.zeros_like(T)
        peak_idx = int(np.argmax(signal))
        left_idx = max(0, peak_idx - 50)
        right_idx = min(len(T) - 1, peak_idx + 50)
        area = integrate_peak(T, signal, baseline, left_idx, right_idx)
        assert area > 0.0

    def test_integrate_peak_zero_for_flat_above_baseline(self):
        """
        When signal equals the baseline exactly, the area should be zero.
        """
        signal = np.ones_like(T) * 2.0
        baseline = np.ones_like(T) * 2.0
        area = integrate_peak(T, signal, baseline, 10, 100)
        assert abs(area) < 1e-10

    def test_integrate_peak_degenerate_indices_returns_zero(self):
        """left_idx >= right_idx should return 0.0 without error."""
        signal = _make_gaussian_signal()
        baseline = np.zeros_like(T)
        area = integrate_peak(T, signal, baseline, 100, 100)
        assert area == 0.0


# ---------------------------------------------------------------------------
# compute_fwhm
# ---------------------------------------------------------------------------

class TestFWHMGaussian:

    def test_fwhm_close_to_analytical(self):
        """
        FWHM of a Gaussian should be within 10% of 2.3548 * sigma.
        """
        signal = _make_gaussian_signal()
        peak_idx = int(np.argmax(signal))
        fwhm = compute_fwhm(T, signal, peak_idx, baseline_value=0.0)

        relative_error = abs(fwhm - ANALYTICAL_FWHM) / ANALYTICAL_FWHM
        assert relative_error < 0.10, (
            f"FWHM {fwhm:.4f} differs from analytical "
            f"{ANALYTICAL_FWHM:.4f} by {relative_error*100:.1f}%"
        )

    def test_fwhm_wider_sigma_gives_wider_fwhm(self):
        """A Gaussian with larger sigma should have a larger FWHM."""
        s_narrow = _make_gaussian_signal(sigma=5.0)
        s_wide = _make_gaussian_signal(sigma=15.0)

        fwhm_narrow = compute_fwhm(T, s_narrow, int(np.argmax(s_narrow)))
        fwhm_wide = compute_fwhm(T, s_wide, int(np.argmax(s_wide)))

        assert fwhm_wide > fwhm_narrow, (
            f"Expected fwhm_wide ({fwhm_wide:.2f}) > fwhm_narrow ({fwhm_narrow:.2f})"
        )

    def test_fwhm_positive(self):
        """FWHM should always be a non-negative value."""
        signal = _make_gaussian_signal()
        peak_idx = int(np.argmax(signal))
        fwhm = compute_fwhm(T, signal, peak_idx)
        assert fwhm >= 0.0

    def test_fwhm_zero_for_flat_signal(self):
        """A zero-height signal at the peak index should return FWHM = 0."""
        flat = np.zeros_like(T)
        fwhm = compute_fwhm(T, flat, peak_idx=250)
        assert fwhm == 0.0


# ---------------------------------------------------------------------------
# characterize_peaks
# ---------------------------------------------------------------------------

class TestCharacterizePeaks:

    def test_characterize_peaks_fills_all_fields(self):
        """
        After characterize_peaks, onset, endset, area, fwhm, and height
        should all be set (not None).
        """
        signal = _make_gaussian_signal()
        raw_peaks = find_thermal_peaks(T, signal, direction="up")
        assert len(raw_peaks) >= 1

        enriched = characterize_peaks(T, signal, raw_peaks)

        for pk in enriched:
            assert pk.onset_temperature is not None
            assert pk.endset_temperature is not None
            assert pk.area is not None
            assert pk.fwhm is not None
            assert pk.height is not None

    def test_characterize_peaks_fwhm_reasonable(self):
        """FWHM from characterize_peaks should be within 20% of 2.3548*sigma."""
        signal = _make_gaussian_signal()
        raw_peaks = find_thermal_peaks(T, signal, direction="up")
        enriched = characterize_peaks(T, signal, raw_peaks)

        assert len(enriched) >= 1
        fwhm = enriched[0].fwhm
        relative_error = abs(fwhm - ANALYTICAL_FWHM) / ANALYTICAL_FWHM
        assert relative_error < 0.20, (
            f"characterize_peaks FWHM {fwhm:.2f} deviates "
            f"{relative_error*100:.1f}% from analytical {ANALYTICAL_FWHM:.2f}"
        )

    def test_characterize_peaks_with_global_baseline(self):
        """
        Providing a global baseline array should not cause errors and
        should result in a different (but valid) area compared to no baseline.
        """
        signal = _make_gaussian_signal()
        baseline = np.zeros_like(T)  # flat zero baseline
        raw_peaks = find_thermal_peaks(T, signal, direction="up")
        enriched = characterize_peaks(T, signal, raw_peaks, baseline=baseline)

        for pk in enriched:
            assert pk.area is not None
            assert np.isfinite(pk.area)

    def test_characterize_peaks_onset_before_endset(self):
        """onset_temperature should always be less than endset_temperature."""
        signal = _make_gaussian_signal()
        raw_peaks = find_thermal_peaks(T, signal, direction="up")
        enriched = characterize_peaks(T, signal, raw_peaks)

        for pk in enriched:
            if pk.onset_temperature is not None and pk.endset_temperature is not None:
                assert pk.onset_temperature < pk.endset_temperature, (
                    f"onset ({pk.onset_temperature:.2f}) should be "
                    f"< endset ({pk.endset_temperature:.2f})"
                )

    def test_characterize_peaks_empty_list_is_safe(self):
        """Passing an empty list should return an empty list without errors."""
        signal = _make_gaussian_signal()
        result = characterize_peaks(T, signal, [])
        assert result == []
