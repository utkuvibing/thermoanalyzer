"""
conftest.py
-----------
Shared pytest fixtures for the ThermoAnalyzer test suite.

All fixtures generate synthetic data with known analytical properties so
that tests are deterministic and require no external files.
"""

import sys
import os

# Ensure the thermoanalyzer package root is importable regardless of where
# pytest is invoked from.
_THERMOANALYZER_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)
if _THERMOANALYZER_ROOT not in sys.path:
    sys.path.insert(0, _THERMOANALYZER_ROOT)

import numpy as np
import pandas as pd
import pytest

from core.data_io import ThermalDataset


# ---------------------------------------------------------------------------
# Constants that define the synthetic signals
# ---------------------------------------------------------------------------

# Temperature axis
T_START = 30.0
T_END = 300.0
N_POINTS = 500

# DSC Gaussian peak parameters
DSC_PEAK_CENTER = 250.0    # degrees C
DSC_PEAK_SIGMA = 5.0       # degrees C
DSC_PEAK_AMPLITUDE = 2.0   # mW/mg

# TGA sigmoid step parameters
TGA_STEP_CENTER = 150.0    # degrees C  (inflection of sigmoid)
TGA_STEP_WIDTH = 10.0      # controls steepness  (smaller -> steeper)
TGA_INITIAL_MASS = 100.0   # %
TGA_MASS_LOSS = 12.0       # % (known mass loss through the step)

# Known linear baseline slope for the dsc_with_baseline fixture
DSC_BASELINE_SLOPE = 0.001  # mW/mg per degree C

# Kissinger multi-rate parameters
KISSINGER_HEATING_RATES = [5.0, 10.0, 20.0, 40.0]   # K/min
KISSINGER_ACTIVATION_ENERGY = 120e3                   # J/mol  (known Ea)
KISSINGER_A_FACTOR = 1e12                             # pre-exponential (s^-1)
R_GAS = 8.314                                         # J / (mol K)


# ---------------------------------------------------------------------------
# Helper: Gaussian function
# ---------------------------------------------------------------------------

def _gaussian(x, center, sigma, amplitude):
    """Return a Gaussian peak over array x."""
    return amplitude * np.exp(-0.5 * ((x - center) / sigma) ** 2)


# ---------------------------------------------------------------------------
# Helper: sigmoid step
# ---------------------------------------------------------------------------

def _sigmoid_step(x, center, width, initial, loss):
    """
    Return a sigmoid mass-% curve that drops by *loss* % around *center*.

    mass(T) = initial - loss * sigmoid((T - center) / width)
    """
    return initial - loss / (1.0 + np.exp(-(x - center) / width))


def _tanh_step(x, center, width, amplitude):
    """Return a Tg-like DSC baseline step centered at *center*."""
    return amplitude * np.tanh((x - center) / width)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_thermoanalyzer_home(monkeypatch, tmp_path):
    """Isolate license/library disk state so global cache never leaks across tests."""
    storage_root = tmp_path / "thermoanalyzer-home"
    storage_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("THERMOANALYZER_HOME", str(storage_root))
    yield


@pytest.fixture(scope="session")
def temperature_range():
    """Uniform temperature grid from 30 to 300 degrees C with 500 points."""
    return np.linspace(T_START, T_END, N_POINTS)


@pytest.fixture(scope="session")
def dsc_signal(temperature_range):
    """
    Synthetic DSC heat-flow signal.

    Contains a single Gaussian peak centred at DSC_PEAK_CENTER (250 C)
    with amplitude DSC_PEAK_AMPLITUDE (2.0 mW/mg) and sigma DSC_PEAK_SIGMA
    (5.0 C).  A small amount of white noise is added to simulate realistic
    data.  The random seed is fixed so tests are reproducible.
    """
    rng = np.random.default_rng(42)
    noise = rng.normal(0.0, 0.005, size=N_POINTS)
    peak = _gaussian(temperature_range, DSC_PEAK_CENTER, DSC_PEAK_SIGMA, DSC_PEAK_AMPLITUDE)
    return peak + noise


@pytest.fixture(scope="session")
def tga_signal(temperature_range):
    """
    Synthetic TGA mass-% signal.

    A sigmoid step centred at TGA_STEP_CENTER (150 C) with TGA_MASS_LOSS
    (12 %) total mass loss.  Noise is added at a level that should not
    interfere with step detection.
    """
    rng = np.random.default_rng(7)
    noise = rng.normal(0.0, 0.02, size=N_POINTS)
    mass = _sigmoid_step(
        temperature_range,
        TGA_STEP_CENTER,
        TGA_STEP_WIDTH,
        TGA_INITIAL_MASS,
        TGA_MASS_LOSS,
    )
    return mass + noise


@pytest.fixture(scope="session")
def dsc_tg_signal(temperature_range):
    """Deterministic polymer-like DSC signal dominated by a Tg step near 120 C."""
    rng = np.random.default_rng(101)
    baseline = 0.0004 * (temperature_range - T_START)
    tg_step = _tanh_step(temperature_range, center=120.0, width=4.0, amplitude=0.08)
    noise = rng.normal(0.0, 0.0015, size=N_POINTS)
    return baseline + tg_step + noise


@pytest.fixture(scope="session")
def dsc_melting_crystallization_signal(temperature_range):
    """Deterministic DSC signal with one exotherm and one endotherm."""
    rng = np.random.default_rng(202)
    baseline = 0.0002 * (temperature_range - T_START)
    crystallization = _gaussian(temperature_range, center=125.0, sigma=7.0, amplitude=1.2)
    melting = -_gaussian(temperature_range, center=215.0, sigma=9.0, amplitude=1.6)
    noise = rng.normal(0.0, 0.002, size=N_POINTS)
    return baseline + crystallization + melting + noise


@pytest.fixture(scope="session")
def tga_percent_signal(temperature_range):
    """Deterministic single-step TGA signal in mass-percent units."""
    rng = np.random.default_rng(303)
    mass = _sigmoid_step(temperature_range, center=150.0, width=9.0, initial=100.0, loss=12.0)
    return mass + rng.normal(0.0, 0.008, size=N_POINTS)


@pytest.fixture(scope="session")
def tga_noisy_signal(temperature_range):
    """Deterministic noisy single-step TGA signal for step-detection regression."""
    rng = np.random.default_rng(404)
    mass = _sigmoid_step(temperature_range, center=150.0, width=10.0, initial=100.0, loss=12.0)
    return mass + rng.normal(0.0, 0.06, size=N_POINTS)


@pytest.fixture(scope="session")
def tga_multi_step_signal(temperature_range):
    """Deterministic multi-step TGA signal with two separated decomposition steps."""
    rng = np.random.default_rng(505)
    first = _sigmoid_step(temperature_range, center=125.0, width=7.0, initial=100.0, loss=7.0)
    second = _sigmoid_step(temperature_range, center=225.0, width=9.0, initial=0.0, loss=10.0)
    mass = first + second
    return mass + rng.normal(0.0, 0.01, size=N_POINTS)


@pytest.fixture(scope="session")
def tga_mg_signal(temperature_range):
    """Deterministic single-step TGA signal in absolute-mass units (>105 mg path)."""
    initial_mass_mg = 250.0
    percent = _sigmoid_step(temperature_range, center=150.0, width=9.0, initial=100.0, loss=12.0)
    return initial_mass_mg * percent / 100.0


@pytest.fixture(scope="session")
def thermal_dataset(temperature_range, dsc_signal):
    """
    A ThermalDataset built from the synthetic DSC signal.

    Includes realistic metadata so tests of export and metadata access work.
    """
    df = pd.DataFrame(
        {
            "temperature": temperature_range,
            "signal": dsc_signal,
        }
    )
    return ThermalDataset(
        data=df,
        metadata={
            "sample_name": "SyntheticDSC",
            "sample_mass": 5.0,
            "heating_rate": 10.0,
            "instrument": "TestInstrument",
            "source_data_hash": "synthetic-dsc-hash",
        },
        data_type="DSC",
        units={"temperature": "degC", "signal": "mW/mg"},
        original_columns={"temperature": "temperature", "signal": "signal"},
        file_path="",
    )


@pytest.fixture(scope="session")
def dsc_with_baseline(temperature_range, dsc_signal):
    """
    DSC signal superimposed on a known linear baseline.

    baseline(T) = DSC_BASELINE_SLOPE * (T - T_START)

    Tests can verify that baseline correction recovers the original peak
    signal to within numerical tolerances.
    """
    baseline = DSC_BASELINE_SLOPE * (temperature_range - T_START)
    composite = dsc_signal + baseline
    return composite, baseline


@pytest.fixture(scope="session")
def multi_rate_data(temperature_range):
    """
    Synthetic multi-heating-rate DSC data for Kissinger analysis.

    For each heating rate beta (K/min) the peak temperature Tp is computed
    from the Kissinger equation:

        ln(beta / Tp^2) = ln(A * R / Ea) - Ea / (R * Tp)

    We solve for Tp numerically given the known Ea and A.  The fixture
    returns a list of (beta, temperature_array, dsc_signal_array) tuples.

    The peak temperature at each heating rate shifts to higher values as
    beta increases, which is the hallmark of kinetically controlled events.
    """
    from scipy.optimize import brentq

    dataset = []
    for beta in KISSINGER_HEATING_RATES:
        beta_per_s = beta / 60.0  # convert K/min -> K/s

        # Kissinger equation rearranged: f(Tp) = 0
        # ln(beta/Tp^2) = ln(A*R/Ea) - Ea/(R*Tp)
        # => A*R/Ea * exp(-Ea/(R*Tp)) * Tp^2 - beta = 0
        def _kissinger_residual(Tp_kelvin):
            return (
                KISSINGER_A_FACTOR
                * R_GAS
                / KISSINGER_ACTIVATION_ENERGY
                * np.exp(-KISSINGER_ACTIVATION_ENERGY / (R_GAS * Tp_kelvin))
                * Tp_kelvin ** 2
                - beta_per_s
            )

        # Search in the range 350 K - 750 K (77 C - 477 C)
        try:
            Tp_K = brentq(_kissinger_residual, 350.0, 750.0)
        except ValueError:
            # If brentq fails, use a reasonable approximation
            Tp_K = 500.0 + beta * 2.0

        Tp_C = Tp_K - 273.15

        # Build a synthetic DSC peak centred at Tp_C
        rng = np.random.default_rng(int(beta * 10))
        noise = rng.normal(0.0, 0.005, size=N_POINTS)
        signal = _gaussian(temperature_range, Tp_C, DSC_PEAK_SIGMA, DSC_PEAK_AMPLITUDE) + noise

        dataset.append((beta, temperature_range.copy(), signal))

    return dataset
