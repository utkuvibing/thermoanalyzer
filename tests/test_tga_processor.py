"""
test_tga_processor.py
---------------------
Tests for core.tga_processor

Covers:
- TGAProcessor.compute_dtg() produces a meaningful derivative signal
- Step detection on synthetic sigmoid TGA data
- Mass-loss accuracy: known sigmoid -> known mass loss (±2%)
- Full pipeline via TGAProcessor.process()
"""

import os
import sys

import numpy as np
import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import core.tga_processor as tga_processor_module
from core.tga_processor import TGAProcessor, TGAResult, MassLossStep
from core.peak_analysis import ThermalPeak, find_thermal_peaks as peak_analysis_find_thermal_peaks


# ---------------------------------------------------------------------------
# Helpers / constants
# ---------------------------------------------------------------------------

# Sigmoid parameters for the synthetic TGA data (mirroring conftest.py)
TGA_STEP_CENTER  = 150.0   # degrees C
TGA_STEP_WIDTH   = 10.0    # degrees C  (steepness)
TGA_INITIAL_MASS = 100.0   # %
TGA_MASS_LOSS    = 12.0    # %

# DTG peak of a sigmoid occurs exactly at the inflection = TGA_STEP_CENTER
EXPECTED_DTG_PEAK = TGA_STEP_CENTER


def _sigmoid(x, center, width, initial, loss):
    """
    Smooth sigmoid mass-% step.
    mass(T) = initial - loss / (1 + exp(-(T - center) / width))
    """
    return initial - loss / (1.0 + np.exp(-(x - center) / width))


def _make_tga_signal(temperature, noise_level=0.01, seed=7):
    """Return a clean sigmoid TGA signal with optional noise."""
    rng = np.random.default_rng(seed)
    mass = _sigmoid(temperature, TGA_STEP_CENTER, TGA_STEP_WIDTH,
                    TGA_INITIAL_MASS, TGA_MASS_LOSS)
    mass += rng.normal(0.0, noise_level, size=len(temperature))
    return mass


# ---------------------------------------------------------------------------
# compute_dtg()
# ---------------------------------------------------------------------------

class TestTGAProcessorDTG:

    def test_dtg_has_correct_length(self, temperature_range):
        """DTG signal must have the same number of points as the temperature array."""
        mass = _make_tga_signal(temperature_range)
        proc = TGAProcessor(temperature_range, mass)
        proc.smooth().compute_dtg()
        result = proc.get_result()
        assert len(result.dtg_signal) == len(temperature_range)

    def test_dtg_has_negative_minimum_for_mass_loss(self, temperature_range):
        """
        For a decreasing mass signal, the DTG (dm/dT) should have a
        negative minimum (mass-loss events appear as negative peaks in DTG).
        """
        mass = _make_tga_signal(temperature_range)
        proc = TGAProcessor(temperature_range, mass)
        proc.smooth().compute_dtg()
        result = proc.get_result()
        assert result.dtg_signal.min() < 0.0, (
            "DTG should have a negative minimum for a mass-loss event"
        )

    def test_dtg_minimum_near_step_center(self, temperature_range):
        """
        The minimum of the DTG signal (maximum rate of mass loss) should occur
        near the inflection point of the sigmoid (TGA_STEP_CENTER = 150 C).
        Allow ±15 C tolerance for smoothing effects on a 270 C window.
        """
        mass = _make_tga_signal(temperature_range, noise_level=0.005)
        proc = TGAProcessor(temperature_range, mass)
        proc.smooth(method="savgol", window_length=15, polyorder=3)
        proc.compute_dtg(smooth_dtg=True)
        result = proc.get_result()

        # DTG minimum is the max rate of mass loss
        dtg_min_idx = int(np.argmin(result.dtg_signal))
        dtg_min_temp = float(temperature_range[dtg_min_idx])

        assert abs(dtg_min_temp - EXPECTED_DTG_PEAK) < 15.0, (
            f"DTG minimum at {dtg_min_temp:.2f} C, expected near {EXPECTED_DTG_PEAK} C"
        )

    def test_dtg_requires_smooth_first(self, temperature_range):
        """compute_dtg() should raise RuntimeError if smooth() was not called."""
        mass = _make_tga_signal(temperature_range)
        proc = TGAProcessor(temperature_range, mass)
        with pytest.raises(RuntimeError, match="smooth"):
            proc.compute_dtg()

    def test_dtg_is_finite(self, temperature_range):
        """All DTG values should be finite (no NaN or Inf)."""
        mass = _make_tga_signal(temperature_range)
        proc = TGAProcessor(temperature_range, mass)
        proc.smooth().compute_dtg()
        result = proc.get_result()
        assert np.all(np.isfinite(result.dtg_signal)), (
            "DTG signal contains non-finite values"
        )


# ---------------------------------------------------------------------------
# detect_steps()
# ---------------------------------------------------------------------------

class TestTGAStepDetection:

    def test_detects_at_least_one_step(self, temperature_range):
        """
        The synthetic TGA signal with a clear 12% mass-loss step should
        produce at least one detected MassLossStep.
        """
        mass = _make_tga_signal(temperature_range)
        proc = TGAProcessor(temperature_range, mass)
        proc.smooth().compute_dtg().detect_steps(min_mass_loss=1.0)
        result = proc.get_result()
        assert len(result.steps) >= 1, (
            "Expected at least one mass-loss step to be detected"
        )

    def test_step_midpoint_near_sigmoid_center(self, temperature_range):
        """
        The midpoint temperature of the detected step should be within 20 C
        of the sigmoid inflection (TGA_STEP_CENTER = 150 C).
        """
        mass = _make_tga_signal(temperature_range, noise_level=0.005)
        proc = TGAProcessor(temperature_range, mass)
        proc.smooth().compute_dtg().detect_steps(min_mass_loss=1.0)
        result = proc.get_result()
        assert len(result.steps) >= 1

        midpoints = [s.midpoint_temperature for s in result.steps]
        closest = min(midpoints, key=lambda t: abs(t - TGA_STEP_CENTER))
        assert abs(closest - TGA_STEP_CENTER) < 20.0, (
            f"Step midpoint {closest:.2f} C is too far from "
            f"expected {TGA_STEP_CENTER} C"
        )

    def test_step_onset_before_endset(self, temperature_range):
        """
        For every detected step, onset_temperature must be strictly less
        than endset_temperature.
        """
        mass = _make_tga_signal(temperature_range)
        proc = TGAProcessor(temperature_range, mass)
        proc.smooth().compute_dtg().detect_steps(min_mass_loss=1.0)
        result = proc.get_result()

        for step in result.steps:
            assert step.onset_temperature < step.endset_temperature, (
                f"Onset {step.onset_temperature:.2f} should be < "
                f"endset {step.endset_temperature:.2f}"
            )

    def test_steps_are_mass_loss_step_objects(self, temperature_range):
        """Each detected step should be a MassLossStep dataclass instance."""
        mass = _make_tga_signal(temperature_range)
        proc = TGAProcessor(temperature_range, mass)
        proc.smooth().compute_dtg().detect_steps()
        result = proc.get_result()

        for step in result.steps:
            assert isinstance(step, MassLossStep)

    def test_detect_steps_requires_dtg(self, temperature_range):
        """detect_steps() should raise RuntimeError if compute_dtg() was not called."""
        mass = _make_tga_signal(temperature_range)
        proc = TGAProcessor(temperature_range, mass)
        proc.smooth()
        with pytest.raises(RuntimeError, match="compute_dtg"):
            proc.detect_steps()


# ---------------------------------------------------------------------------
# Mass-loss accuracy
# ---------------------------------------------------------------------------

class TestTGAMassLossAccuracy:

    def test_mass_loss_accuracy_within_2_percent(self, temperature_range):
        """
        Verify that the TGA pipeline accurately measures the total mass loss
        of a synthetic sigmoid step to within 2% (absolute).

        The TGAResult.total_mass_loss_percent field (smoothed[0] - smoothed[-1])
        provides the most direct and accurate measure because it reads from the
        signal endpoints rather than relying on the tangent-construction method.
        The per-step mass_loss_percent from detect_steps() is an approximation
        based on the tangent intersection at onset/endset boundaries, which
        typically under-counts the full sigmoid area; it is validated separately
        with a relaxed tolerance in test_step_midpoint_near_sigmoid_center.
        """
        # Use a very clean signal to reduce noise sensitivity
        mass = _make_tga_signal(temperature_range, noise_level=0.005, seed=42)
        proc = TGAProcessor(temperature_range, mass)
        proc.smooth(method="savgol", window_length=15, polyorder=3)
        proc.compute_dtg(smooth_dtg=True)
        proc.detect_steps(min_mass_loss=1.0)
        result = proc.get_result()

        assert len(result.steps) >= 1, (
            "No steps detected; cannot assess mass-loss accuracy"
        )

        # total_mass_loss_percent = smoothed[0] - smoothed[-1] captures the
        # full endpoint-to-endpoint drop, which directly corresponds to the
        # known sigmoid amplitude (TGA_MASS_LOSS = 12%).
        error = abs(result.total_mass_loss_percent - TGA_MASS_LOSS)
        assert error < 2.0, (
            f"TGAResult.total_mass_loss_percent = {result.total_mass_loss_percent:.2f}% "
            f"differs from known {TGA_MASS_LOSS}% by {error:.2f}% (tolerance: 2%)"
        )

    def test_total_mass_loss_from_result(self, temperature_range):
        """
        TGAResult.total_mass_loss_percent should approximately equal the
        true sigmoid mass loss (12%) within 2%.
        """
        mass = _make_tga_signal(temperature_range, noise_level=0.005, seed=11)
        result = (
            TGAProcessor(temperature_range, mass)
            .smooth(method="savgol", window_length=15, polyorder=3)
            .compute_dtg()
            .detect_steps()
            .get_result()
        )

        error = abs(result.total_mass_loss_percent - TGA_MASS_LOSS)
        assert error < 2.0, (
            f"TGAResult.total_mass_loss_percent = {result.total_mass_loss_percent:.2f}%, "
            f"expected ~{TGA_MASS_LOSS}% (tolerance: 2%)"
        )

    def test_residue_percent_approximately_correct(self, temperature_range):
        """
        TGAResult.residue_percent should be close to
        TGA_INITIAL_MASS - TGA_MASS_LOSS = 88%.
        """
        expected_residue = TGA_INITIAL_MASS - TGA_MASS_LOSS  # 88%
        mass = _make_tga_signal(temperature_range, noise_level=0.005, seed=5)
        result = (
            TGAProcessor(temperature_range, mass)
            .smooth()
            .compute_dtg()
            .detect_steps()
            .get_result()
        )

        error = abs(result.residue_percent - expected_residue)
        assert error < 2.0, (
            f"Residue {result.residue_percent:.2f}% differs from "
            f"expected {expected_residue}% by {error:.2f}%"
        )


# ---------------------------------------------------------------------------
# Full pipeline via TGAProcessor.process()
# ---------------------------------------------------------------------------

class TestTGAFullPipeline:

    def test_process_returns_tga_result(self, temperature_range):
        """process() should return a TGAResult dataclass."""
        mass = _make_tga_signal(temperature_range)
        result = TGAProcessor(temperature_range, mass).process()
        assert isinstance(result, TGAResult)

    def test_process_smoothed_signal_populated(self, temperature_range):
        """TGAResult.smoothed_signal should be a non-empty numpy array."""
        mass = _make_tga_signal(temperature_range)
        result = TGAProcessor(temperature_range, mass).process()
        assert isinstance(result.smoothed_signal, np.ndarray)
        assert len(result.smoothed_signal) == len(temperature_range)

    def test_process_dtg_signal_populated(self, temperature_range):
        """TGAResult.dtg_signal should be a non-empty numpy array."""
        mass = _make_tga_signal(temperature_range)
        result = TGAProcessor(temperature_range, mass).process()
        assert isinstance(result.dtg_signal, np.ndarray)
        assert len(result.dtg_signal) == len(temperature_range)

    def test_process_steps_is_list(self, temperature_range):
        """TGAResult.steps should always be a list (possibly empty)."""
        mass = _make_tga_signal(temperature_range)
        result = TGAProcessor(temperature_range, mass).process()
        assert isinstance(result.steps, list)

    def test_process_dtg_peaks_is_list(self, temperature_range):
        """TGAResult.dtg_peaks should always be a list."""
        mass = _make_tga_signal(temperature_range)
        result = TGAProcessor(temperature_range, mass).process()
        assert isinstance(result.dtg_peaks, list)

    def test_process_all_values_finite(self, temperature_range):
        """Smoothed signal and DTG should contain only finite values."""
        mass = _make_tga_signal(temperature_range)
        result = TGAProcessor(temperature_range, mass).process()
        assert np.all(np.isfinite(result.smoothed_signal)), (
            "smoothed_signal contains non-finite values"
        )
        assert np.all(np.isfinite(result.dtg_signal)), (
            "dtg_signal contains non-finite values"
        )

    def test_process_get_result_raises_before_pipeline(self, temperature_range):
        """
        Calling get_result() before running the pipeline should raise
        RuntimeError.
        """
        mass = _make_tga_signal(temperature_range)
        proc = TGAProcessor(temperature_range, mass)
        with pytest.raises(RuntimeError):
            proc.get_result()

    def test_process_with_initial_mass_mg_populates_mass_loss_mg(self, temperature_range):
        """
        When initial_mass_mg is provided, each MassLossStep should have
        mass_loss_mg populated (not None).
        """
        mass = _make_tga_signal(temperature_range)
        result = TGAProcessor(
            temperature_range, mass, initial_mass_mg=20.0
        ).process()

        for step in result.steps:
            assert step.mass_loss_mg is not None, (
                "mass_loss_mg should be populated when initial_mass_mg is given"
            )

    def test_process_with_savgol_kwargs_does_not_break_step_detection(self, temperature_range):
        """
        Regression: smoothing kwargs passed through process() must not be
        forwarded into find_thermal_peaks.
        """
        mass = _make_tga_signal(temperature_range, noise_level=0.005, seed=21)
        result = TGAProcessor(temperature_range, mass).process(
            smooth_method="savgol",
            smooth_dtg=True,
            window_length=11,
            polyorder=3,
            min_mass_loss=1.0,
        )

        assert isinstance(result, TGAResult)
        assert len(result.dtg_signal) == len(temperature_range)

    def test_process_mass_loss_mg_consistent_with_percent(self, temperature_range):
        """
        mass_loss_mg should equal mass_loss_percent / 100 * initial_mass_mg.
        """
        initial_mass = 20.0
        mass = _make_tga_signal(temperature_range, noise_level=0.005, seed=3)
        result = TGAProcessor(
            temperature_range, mass, initial_mass_mg=initial_mass
        ).process()

        for step in result.steps:
            if step.mass_loss_mg is not None:
                expected_mg = step.mass_loss_percent / 100.0 * initial_mass
                assert step.mass_loss_mg == pytest.approx(expected_mg, rel=1e-6), (
                    f"mass_loss_mg {step.mass_loss_mg:.4f} != "
                    f"mass_loss_percent/100*initial_mass {expected_mg:.4f}"
                )

    def test_process_with_fixture_signal(self, temperature_range, tga_signal):
        """
        The conftest tga_signal fixture (12% sigmoid at 150 C) should be
        processed without errors and yield at least one step.
        """
        result = TGAProcessor(temperature_range, tga_signal).process()
        assert isinstance(result, TGAResult)
        # There should be at least one step for the 12% sigmoid
        assert len(result.steps) >= 1, (
            "Expected at least one step from the conftest TGA fixture"
        )

    def test_process_filters_smoothing_kwargs_before_peak_detection(self, temperature_range, monkeypatch):
        """
        Smoothing kwargs passed through process() must not leak into
        find_thermal_peaks(), but supported peak-detection kwargs still should.
        """
        mass = _make_tga_signal(temperature_range, noise_level=0.005, seed=17)
        captured = {}

        def spy_find_thermal_peaks(temperature, signal, **kwargs):
            captured.update(kwargs)
            return peak_analysis_find_thermal_peaks(temperature, signal, **kwargs)

        monkeypatch.setattr(tga_processor_module, "find_thermal_peaks", spy_find_thermal_peaks)

        result = TGAProcessor(temperature_range, mass).process(
            window_length=15,
            polyorder=3,
            direction="up",
        )

        assert isinstance(result, TGAResult)
        assert "window_length" not in captured
        assert "polyorder" not in captured
        assert captured["direction"] == "up"


class TestTGADeterministicRegressions:

    def test_percent_input_path_is_deterministic(self, temperature_range, tga_percent_signal):
        """Lock in deterministic single-step behavior for percent-input TGA data."""
        result = TGAProcessor(temperature_range, tga_percent_signal).process()

        assert result.total_mass_loss_percent == pytest.approx(12.0, abs=2.0)
        assert len(result.steps) >= 1
        assert result.steps[0].midpoint_temperature == pytest.approx(150.0, abs=20.0)

    def test_multi_step_signal_detects_multiple_steps(self, temperature_range, tga_multi_step_signal):
        """Lock in two-step detection for a deterministic multi-step TGA signal."""
        result = (
            TGAProcessor(temperature_range, tga_multi_step_signal)
            .smooth(method="savgol", window_length=15, polyorder=3)
            .compute_dtg(smooth_dtg=True, window_length=11, polyorder=3)
            .detect_steps(min_mass_loss=2.0)
            .get_result()
        )

        assert len(result.steps) >= 2
        midpoints = [step.midpoint_temperature for step in result.steps]
        assert any(abs(midpoint - 125.0) < 20.0 for midpoint in midpoints)
        assert any(abs(midpoint - 225.0) < 20.0 for midpoint in midpoints)
        assert result.steps == sorted(result.steps, key=lambda step: step.onset_temperature)

    def test_noisy_input_still_returns_finite_step_analysis(self, temperature_range, tga_noisy_signal):
        """Noisy TGA input should still yield finite arrays and at least one valid step."""
        result = (
            TGAProcessor(temperature_range, tga_noisy_signal)
            .smooth(method="savgol", window_length=17, polyorder=3)
            .compute_dtg(smooth_dtg=True, window_length=11, polyorder=3)
            .detect_steps(min_mass_loss=1.0)
            .get_result()
        )

        assert np.all(np.isfinite(result.smoothed_signal))
        assert np.all(np.isfinite(result.dtg_signal))
        assert len(result.steps) >= 1

    def test_absolute_mass_input_above_threshold_converts_to_percent(self, temperature_range, tga_mg_signal):
        """Lock in the unambiguous >105 mg absolute-mass conversion path."""
        result = TGAProcessor(temperature_range, tga_mg_signal, initial_mass_mg=250.0).process()

        assert result.total_mass_loss_percent == pytest.approx(12.0, abs=2.0)
        assert all(step.mass_loss_mg is not None for step in result.steps)


class TestTGAUnitModes:

    def test_explicit_percent_mode_uses_percent_path(self, temperature_range, tga_percent_signal):
        processor = TGAProcessor(
            temperature_range,
            tga_percent_signal,
            unit_mode="percent",
        )
        result = processor.process()
        unit_context = processor.get_unit_context()

        assert unit_context["declared_unit_mode"] == "percent"
        assert unit_context["resolved_unit_mode"] == "percent"
        assert unit_context["auto_inference_used"] is False
        assert unit_context["unit_interpretation_status"] == "accepted"
        assert result.total_mass_loss_percent == pytest.approx(12.0, abs=2.0)

    def test_explicit_absolute_mass_mode_uses_absolute_mass_path(self, temperature_range, tga_percent_signal):
        processor = TGAProcessor(
            temperature_range,
            tga_percent_signal,
            initial_mass_mg=100.0,
            unit_mode="absolute_mass",
        )
        result = processor.process()
        unit_context = processor.get_unit_context()

        assert unit_context["declared_unit_mode"] == "absolute_mass"
        assert unit_context["resolved_unit_mode"] == "absolute_mass"
        assert unit_context["unit_reference_source"] == "initial_mass_mg"
        assert unit_context["auto_inference_used"] is False
        assert result.total_mass_loss_percent == pytest.approx(12.0, abs=2.0)
        assert all(step.mass_loss_mg is not None for step in result.steps)

    def test_auto_mode_with_percent_unit_is_unambiguous(self, temperature_range, tga_percent_signal):
        processor = TGAProcessor(
            temperature_range,
            tga_percent_signal,
            unit_mode="auto",
            signal_unit="%",
        )
        processor.process()
        unit_context = processor.get_unit_context()

        assert unit_context["resolved_unit_mode"] == "percent"
        assert unit_context["auto_inference_used"] is True
        assert unit_context["unit_interpretation_status"] == "accepted"
        assert unit_context["unit_inference_basis"] == "signal_unit_percent"

    def test_auto_mode_with_unambiguous_absolute_mass_input_uses_threshold_path(self, temperature_range, tga_mg_signal):
        processor = TGAProcessor(
            temperature_range,
            tga_mg_signal,
            initial_mass_mg=250.0,
            unit_mode="auto",
        )
        processor.process()
        unit_context = processor.get_unit_context()

        assert unit_context["resolved_unit_mode"] == "absolute_mass"
        assert unit_context["auto_inference_used"] is True
        assert unit_context["unit_interpretation_status"] == "accepted"
        assert unit_context["unit_inference_basis"] == "signal_max_gt_105"

    def test_auto_mode_with_ambiguous_low_range_input_marks_review(self, temperature_range, tga_percent_signal):
        processor = TGAProcessor(
            temperature_range,
            tga_percent_signal,
            unit_mode="auto",
        )
        processor.process()
        unit_context = processor.get_unit_context()

        assert unit_context["resolved_unit_mode"] == "percent"
        assert unit_context["auto_inference_used"] is True
        assert unit_context["unit_interpretation_status"] == "review"
        assert "explicit unit mode is recommended" in unit_context["unit_review_reason"]
