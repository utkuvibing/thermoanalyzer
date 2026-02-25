"""
test_preprocessing.py
---------------------
Tests for core.preprocessing

Covers:
- smooth_signal with savgol, moving_average, and gaussian methods
- compute_derivative for linear and quadratic inputs
- normalize_by_mass
- interpolate_signal
"""

import os
import sys

import numpy as np
import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.preprocessing import (
    smooth_signal,
    compute_derivative,
    normalize_by_mass,
    interpolate_signal,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _signal_roughness(signal: np.ndarray) -> float:
    """
    Compute signal roughness as the RMS of the second-order finite differences.
    A lower value indicates a smoother signal.
    """
    d2 = np.diff(np.diff(signal))
    return float(np.sqrt(np.mean(d2 ** 2)))


# ---------------------------------------------------------------------------
# smooth_signal - Savitzky-Golay
# ---------------------------------------------------------------------------

class TestSmoothSavgol:

    def test_smooth_savgol_reduces_roughness(self, dsc_signal):
        """Savitzky-Golay filter should produce a strictly smoother signal."""
        smoothed = smooth_signal(dsc_signal, method="savgol", window_length=11, polyorder=3)

        roughness_before = _signal_roughness(dsc_signal)
        roughness_after = _signal_roughness(smoothed)

        assert roughness_after < roughness_before, (
            f"Expected roughness to decrease after smoothing, "
            f"got {roughness_before:.6f} -> {roughness_after:.6f}"
        )

    def test_smooth_savgol_preserves_length(self, dsc_signal):
        """Output length must match input length."""
        smoothed = smooth_signal(dsc_signal, method="savgol", window_length=11, polyorder=3)
        assert len(smoothed) == len(dsc_signal)

    def test_smooth_savgol_on_clean_signal(self, temperature_range):
        """Smoothing a noiseless Gaussian should not significantly distort the peak."""
        clean = 2.0 * np.exp(-0.5 * ((temperature_range - 150.0) / 5.0) ** 2)
        smoothed = smooth_signal(clean, method="savgol", window_length=11, polyorder=3)
        # Peak location should be preserved
        assert temperature_range[np.argmax(smoothed)] == pytest.approx(
            temperature_range[np.argmax(clean)], abs=1.0
        )

    def test_smooth_savgol_default_kwargs(self, dsc_signal):
        """smooth_signal should work without explicit keyword arguments."""
        smoothed = smooth_signal(dsc_signal, method="savgol")
        assert smoothed.shape == dsc_signal.shape


# ---------------------------------------------------------------------------
# smooth_signal - Moving average
# ---------------------------------------------------------------------------

class TestSmoothMovingAverage:

    def test_smooth_moving_average_reduces_roughness(self, dsc_signal):
        """Moving-average filter should produce a smoother signal."""
        smoothed = smooth_signal(dsc_signal, method="moving_average", window=15)
        assert _signal_roughness(smoothed) < _signal_roughness(dsc_signal)

    def test_smooth_moving_average_preserves_length(self, dsc_signal):
        """Output length must equal input length."""
        smoothed = smooth_signal(dsc_signal, method="moving_average", window=15)
        assert len(smoothed) == len(dsc_signal)

    def test_smooth_moving_average_flat_signal(self):
        """
        Smoothing a constant signal should return the same constant value
        in the interior of the array.  The 'same' convolution mode introduces
        edge artefacts (partial-overlap windows at the boundaries), so only
        the interior points are checked.
        """
        flat = np.ones(200) * 3.14
        window = 11
        smoothed = smooth_signal(flat, method="moving_average", window=window)
        # Only interior points (far from edge effects) should match exactly
        half_w = window // 2
        interior = smoothed[half_w:-half_w]
        np.testing.assert_allclose(interior, 3.14, atol=1e-10)


# ---------------------------------------------------------------------------
# smooth_signal - Gaussian
# ---------------------------------------------------------------------------

class TestSmoothGaussian:

    def test_smooth_gaussian_reduces_roughness(self, dsc_signal):
        """Gaussian filter should produce a smoother signal."""
        smoothed = smooth_signal(dsc_signal, method="gaussian", sigma=2)
        assert _signal_roughness(smoothed) < _signal_roughness(dsc_signal)

    def test_smooth_gaussian_preserves_length(self, dsc_signal):
        """Output length must equal input length."""
        smoothed = smooth_signal(dsc_signal, method="gaussian", sigma=2)
        assert len(smoothed) == len(dsc_signal)

    def test_smooth_gaussian_larger_sigma_smoother(self, dsc_signal):
        """Larger sigma should yield a smoother (lower roughness) output."""
        s1 = smooth_signal(dsc_signal, method="gaussian", sigma=1)
        s5 = smooth_signal(dsc_signal, method="gaussian", sigma=5)
        assert _signal_roughness(s5) < _signal_roughness(s1)

    def test_smooth_unknown_method_raises(self, dsc_signal):
        """Passing an unrecognised method name should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown smoothing method"):
            smooth_signal(dsc_signal, method="magic_filter")


# ---------------------------------------------------------------------------
# compute_derivative
# ---------------------------------------------------------------------------

class TestDerivativeLinear:

    def test_derivative_linear_signal(self):
        """
        Derivative of a linear signal y = m*x + b should equal m everywhere,
        within numerical differentiation tolerance.
        """
        slope = 3.7
        x = np.linspace(0.0, 100.0, 300)
        y = slope * x + 5.0

        dy_dx = compute_derivative(x, y, order=1, smooth_first=False)

        # Interior points should be very close to the true slope
        interior = dy_dx[10:-10]
        np.testing.assert_allclose(interior, slope, atol=0.05)

    def test_derivative_linear_constant_output(self):
        """
        The derivative of a linear signal should be nearly constant
        (low standard deviation).
        """
        x = np.linspace(10.0, 200.0, 400)
        y = 2.5 * x - 7.0
        dy_dx = compute_derivative(x, y, order=1, smooth_first=False)
        # Standard deviation of the derivative should be very small
        assert np.std(dy_dx[5:-5]) < 0.1


class TestDerivativeQuadratic:

    def test_derivative_quadratic_equals_2x(self):
        """
        For y = x^2, dy/dx should equal 2*x at interior points,
        within the tolerance of numerical differentiation.
        """
        x = np.linspace(1.0, 50.0, 400)
        y = x ** 2

        dy_dx = compute_derivative(x, y, order=1, smooth_first=False)

        expected = 2.0 * x
        # Trim boundary effects and check relative error
        interior = slice(10, -10)
        rel_error = np.abs(dy_dx[interior] - expected[interior]) / np.abs(expected[interior])
        # Allow 5% relative error for numerical differentiation
        assert np.max(rel_error) < 0.05

    def test_second_derivative_quadratic_equals_2(self):
        """
        For y = x^2, d^2y/dx^2 should equal 2 throughout the interior.
        """
        x = np.linspace(1.0, 50.0, 400)
        y = x ** 2
        d2y_dx2 = compute_derivative(x, y, order=2, smooth_first=False)
        interior = d2y_dx2[30:-30]
        np.testing.assert_allclose(interior, 2.0, atol=0.5)

    def test_derivative_mismatched_lengths_raises(self):
        """x and y arrays of different lengths should raise ValueError."""
        x = np.linspace(0.0, 10.0, 50)
        y = np.ones(60)
        with pytest.raises(ValueError, match="same length"):
            compute_derivative(x, y)

    def test_derivative_invalid_order_raises(self):
        """Order values other than 1 or 2 should raise ValueError."""
        x = np.linspace(0.0, 10.0, 50)
        y = x.copy()
        with pytest.raises(ValueError, match="order"):
            compute_derivative(x, y, order=3)


# ---------------------------------------------------------------------------
# normalize_by_mass
# ---------------------------------------------------------------------------

class TestNormalizeByMass:

    def test_normalize_by_mass_scales_correctly(self, dsc_signal):
        """Signal divided by mass should produce signal/mass at every point."""
        mass_mg = 5.0
        normalized = normalize_by_mass(dsc_signal, sample_mass_mg=mass_mg)
        expected = dsc_signal / mass_mg
        np.testing.assert_allclose(normalized, expected, rtol=1e-10)

    def test_normalize_by_mass_preserves_shape(self, dsc_signal):
        """Output array should have the same shape as input."""
        normalized = normalize_by_mass(dsc_signal, sample_mass_mg=10.0)
        assert normalized.shape == dsc_signal.shape

    def test_normalize_by_mass_zero_mass_raises(self, dsc_signal):
        """Zero sample mass should raise ValueError."""
        with pytest.raises(ValueError, match="> 0"):
            normalize_by_mass(dsc_signal, sample_mass_mg=0.0)

    def test_normalize_by_mass_negative_mass_raises(self, dsc_signal):
        """Negative sample mass should raise ValueError."""
        with pytest.raises(ValueError, match="> 0"):
            normalize_by_mass(dsc_signal, sample_mass_mg=-2.5)

    def test_normalize_by_mass_unit_mass_is_identity(self, dsc_signal):
        """Normalizing by mass=1.0 should return an identical array."""
        normalized = normalize_by_mass(dsc_signal, sample_mass_mg=1.0)
        np.testing.assert_allclose(normalized, dsc_signal, rtol=1e-10)


# ---------------------------------------------------------------------------
# interpolate_signal
# ---------------------------------------------------------------------------

class TestInterpolateSignal:

    def test_interpolate_signal_num_points(self, temperature_range, dsc_signal):
        """Resampling to num_points should return arrays of that exact length."""
        x_out, y_out = interpolate_signal(
            temperature_range, dsc_signal, num_points=200
        )
        assert len(x_out) == 200
        assert len(y_out) == 200

    def test_interpolate_signal_x_bounds(self, temperature_range, dsc_signal):
        """Resampled x-axis should span the same range as the input."""
        x_out, _ = interpolate_signal(temperature_range, dsc_signal, num_points=100)
        assert x_out[0] == pytest.approx(temperature_range[0], abs=0.1)
        assert x_out[-1] == pytest.approx(temperature_range[-1], abs=0.1)

    def test_interpolate_signal_explicit_x_new(self, temperature_range, dsc_signal):
        """Interpolating to an explicit x_new grid should produce matching lengths."""
        x_new = np.linspace(50.0, 250.0, 150)
        x_out, y_out = interpolate_signal(temperature_range, dsc_signal, x_new=x_new)
        assert len(x_out) == 150
        np.testing.assert_array_equal(x_out, x_new)

    def test_interpolate_signal_linear_exact(self):
        """
        Interpolating a known linear signal onto a refined grid should recover
        exact values (since cubic interpolation is exact for polynomials up to
        degree 3).
        """
        x = np.linspace(0.0, 10.0, 10)
        y = 3.0 * x + 1.0
        x_new = np.linspace(0.0, 10.0, 50)
        _, y_out = interpolate_signal(x, y, x_new=x_new)
        expected = 3.0 * x_new + 1.0
        np.testing.assert_allclose(y_out, expected, atol=1e-8)

    def test_interpolate_signal_no_args_raises(self, temperature_range, dsc_signal):
        """Calling without num_points or x_new should raise ValueError."""
        with pytest.raises(ValueError):
            interpolate_signal(temperature_range, dsc_signal)

    def test_interpolate_signal_both_args_raises(self, temperature_range, dsc_signal):
        """Supplying both num_points and x_new should raise ValueError."""
        x_new = np.linspace(50.0, 250.0, 100)
        with pytest.raises(ValueError):
            interpolate_signal(temperature_range, dsc_signal, num_points=100, x_new=x_new)

    def test_interpolate_signal_mismatched_lengths_raises(self):
        """x and y of different lengths should raise ValueError."""
        x = np.linspace(0.0, 10.0, 20)
        y = np.ones(30)
        with pytest.raises(ValueError, match="same length"):
            interpolate_signal(x, y, num_points=50)
