from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("lmfit")

from core.peak_deconvolution import deconvolve_peaks
from core.result_serialization import serialize_deconvolution_result


def _synthetic_signal():
    x = np.linspace(50.0, 250.0, 500)
    y = (
        2.0 * np.exp(-0.5 * ((x - 120.0) / 8.0) ** 2)
        + 1.5 * np.exp(-0.5 * ((x - 170.0) / 10.0) ** 2)
    )
    return x, y


def test_deconvolve_peaks_returns_residual_stats_and_fit_quality():
    x, y = _synthetic_signal()

    result = deconvolve_peaks(x, y, n_peaks=2, peak_shape="gaussian")

    assert "initial_guesses" in result
    assert "residual_stats" in result
    assert "fit_quality" in result
    assert result["residual_stats"]["rmse"] >= 0.0
    assert result["fit_quality"]["dof"] > 0


def test_serialize_deconvolution_result_populates_scientific_context():
    x, y = _synthetic_signal()
    result = deconvolve_peaks(x, y, n_peaks=2, peak_shape="gaussian")
    result["x"] = x
    result["y"] = y
    dataset = SimpleNamespace(metadata={"sample_name": "Synthetic Deconv"})

    record = serialize_deconvolution_result(
        "synthetic_deconv",
        dataset,
        result,
        peak_shape="gaussian",
    )

    assert record["analysis_type"] == "Peak Deconvolution"
    assert record["scientific_context"]["fit_quality"]["r_squared"] is not None
    assert record["scientific_context"]["methodology"]["peak_shape"] == "gaussian"
    assert record["scientific_context"]["methodology"]["initial_guesses"]
