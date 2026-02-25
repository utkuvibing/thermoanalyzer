"""
Data validation functions for thermal analysis datasets.

Every public function returns a (is_valid: bool, message: str) tuple so
callers can branch on the result and surface a human-readable reason when
validation fails.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Tuple

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    # Import only for type hints; avoids a hard runtime dependency on the
    # ThermalDataset model from within this utility module.
    from thermoanalyzer.models import ThermalDataset

# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------

ValidationResult = Tuple[bool, str]


# ---------------------------------------------------------------------------
# Temperature range validation
# ---------------------------------------------------------------------------

# Physical bounds used when checking recorded temperatures [degrees C]
TEMPERATURE_MIN_C = -200.0
TEMPERATURE_MAX_C = 2000.0


def validate_temperature_range(temps: pd.Series) -> ValidationResult:
    """
    Check that a temperature column is monotonically increasing and falls
    within the physically reasonable range for thermal analysis equipment.

    Parameters
    ----------
    temps:
        A pandas Series of temperature values in degrees Celsius.

    Returns
    -------
    (True, "OK") on success or (False, <reason>) on failure.
    """
    if temps is None or len(temps) == 0:
        return False, "Temperature series is empty."

    if not pd.api.types.is_numeric_dtype(temps):
        return False, "Temperature column contains non-numeric values."

    nan_count = temps.isna().sum()
    if nan_count > 0:
        return False, f"Temperature column contains {nan_count} NaN value(s)."

    t_min = temps.min()
    t_max = temps.max()

    if t_min < TEMPERATURE_MIN_C:
        return (
            False,
            f"Minimum temperature {t_min:.2f} C is below the allowed "
            f"lower bound of {TEMPERATURE_MIN_C} C.",
        )

    if t_max > TEMPERATURE_MAX_C:
        return (
            False,
            f"Maximum temperature {t_max:.2f} C exceeds the allowed "
            f"upper bound of {TEMPERATURE_MAX_C} C.",
        )

    diffs = temps.diff().dropna()
    if (diffs <= 0).any():
        n_violations = (diffs <= 0).sum()
        return (
            False,
            f"Temperature column is not strictly monotonically increasing "
            f"({n_violations} non-positive step(s) detected).",
        )

    return True, "Temperature range is valid."


# ---------------------------------------------------------------------------
# Numeric column validation
# ---------------------------------------------------------------------------


def validate_numeric_column(series: pd.Series) -> ValidationResult:
    """
    Verify that a DataFrame column contains numeric data and report NaN
    statistics.

    Parameters
    ----------
    series:
        Any pandas Series expected to hold numeric values.

    Returns
    -------
    (True, "OK") on success or (False, <reason>) on failure.
    A warning-level message is included when NaN values are present but the
    column is otherwise numeric (is_valid remains True with an informational
    note).
    """
    if series is None or len(series) == 0:
        return False, "Column is empty."

    if not pd.api.types.is_numeric_dtype(series):
        # Try to determine the actual dtype for a more helpful message.
        return (
            False,
            f"Column '{series.name}' has dtype '{series.dtype}', "
            "which is not numeric.",
        )

    nan_count = int(series.isna().sum())
    total = len(series)

    if nan_count == total:
        return False, f"Column '{series.name}' contains only NaN values."

    if nan_count > 0:
        pct = 100.0 * nan_count / total
        return (
            True,
            f"Column '{series.name}' is numeric but contains "
            f"{nan_count} NaN value(s) ({pct:.1f} %). "
            "Consider interpolating or dropping missing rows before analysis.",
        )

    return True, f"Column '{series.name}' is valid numeric data with no NaN values."


# ---------------------------------------------------------------------------
# Heating rate validation
# ---------------------------------------------------------------------------

# Practical upper bound for a heating rate used in laboratory instruments [K/min]
HEATING_RATE_MAX = 500.0


def validate_heating_rate(rate: float) -> ValidationResult:
    """
    Check that a heating rate is a positive, finite number within the range
    achievable by standard thermal analysis instruments.

    Parameters
    ----------
    rate:
        Heating rate in K/min (or equivalently degrees C/min).

    Returns
    -------
    (True, "OK") on success or (False, <reason>) on failure.
    """
    if rate is None:
        return False, "Heating rate is None."

    try:
        rate = float(rate)
    except (TypeError, ValueError):
        return False, f"Heating rate '{rate}' cannot be converted to a number."

    if not np.isfinite(rate):
        return False, f"Heating rate must be a finite number, got {rate}."

    if rate <= 0:
        return False, f"Heating rate must be positive, got {rate} K/min."

    if rate > HEATING_RATE_MAX:
        return (
            False,
            f"Heating rate {rate} K/min exceeds the practical maximum of "
            f"{HEATING_RATE_MAX} K/min for standard instruments.",
        )

    return True, f"Heating rate {rate} K/min is valid."


# ---------------------------------------------------------------------------
# Sample mass validation
# ---------------------------------------------------------------------------

# Reasonable mass bounds for DSC / TGA sample pans [mg]
SAMPLE_MASS_MIN_MG = 0.01
SAMPLE_MASS_MAX_MG = 1000.0


def validate_sample_mass(mass: float) -> ValidationResult:
    """
    Check that a sample mass is positive and within the practical range of
    DSC and TGA crucibles / pans.

    Parameters
    ----------
    mass:
        Sample mass in milligrams.

    Returns
    -------
    (True, "OK") on success or (False, <reason>) on failure.
    """
    if mass is None:
        return False, "Sample mass is None."

    try:
        mass = float(mass)
    except (TypeError, ValueError):
        return False, f"Sample mass '{mass}' cannot be converted to a number."

    if not np.isfinite(mass):
        return False, f"Sample mass must be a finite number, got {mass}."

    if mass <= 0:
        return False, f"Sample mass must be positive, got {mass} mg."

    if mass < SAMPLE_MASS_MIN_MG:
        return (
            False,
            f"Sample mass {mass} mg is below the practical minimum of "
            f"{SAMPLE_MASS_MIN_MG} mg.",
        )

    if mass > SAMPLE_MASS_MAX_MG:
        return (
            False,
            f"Sample mass {mass} mg exceeds the practical maximum of "
            f"{SAMPLE_MASS_MAX_MG} mg.",
        )

    return True, f"Sample mass {mass} mg is valid."


# ---------------------------------------------------------------------------
# Comprehensive ThermalDataset validation
# ---------------------------------------------------------------------------


def validate_thermal_dataset(dataset: "ThermalDataset") -> ValidationResult:
    """
    Run all applicable validation checks against a ThermalDataset object and
    aggregate the results into a single (is_valid, message) tuple.

    Checks performed
    ----------------
    1.  The dataset object itself is not None and has a non-empty DataFrame.
    2.  A temperature column is present, numeric, and within valid range.
    3.  A time column (if present) is numeric with acceptable NaN counts.
    4.  A heat-flow column (if present) is numeric.
    5.  A mass column (if present) is numeric.
    6.  Sample mass (if recorded on the dataset) passes validate_sample_mass.
    7.  Heating rate (if recorded on the dataset) passes validate_heating_rate.

    Parameters
    ----------
    dataset:
        An instance of thermoanalyzer.models.ThermalDataset (or any object
        that exposes the attributes described above).

    Returns
    -------
    (True, "All checks passed.") when every check succeeds, or
    (False, <concatenated failure messages>) otherwise.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # -- 1. Object-level check -----------------------------------------------
    if dataset is None:
        return False, "ThermalDataset is None."

    df = getattr(dataset, "data", None)
    if df is None or not isinstance(df, pd.DataFrame):
        return False, "ThermalDataset.data is not a pandas DataFrame."

    if df.empty:
        return False, "ThermalDataset.data is an empty DataFrame."

    # -- 2. Temperature column ------------------------------------------------
    temp_col = getattr(dataset, "temperature_column", None)
    if temp_col is None or temp_col not in df.columns:
        errors.append(
            "No temperature column is defined or the specified column "
            f"'{temp_col}' does not exist in the dataset."
        )
    else:
        ok, msg = validate_temperature_range(df[temp_col])
        if not ok:
            errors.append(f"Temperature column '{temp_col}': {msg}")

    # -- 3. Time column (optional) -------------------------------------------
    time_col = getattr(dataset, "time_column", None)
    if time_col is not None and time_col in df.columns:
        ok, msg = validate_numeric_column(df[time_col])
        if not ok:
            errors.append(f"Time column '{time_col}': {msg}")
        elif "NaN" in msg or "nan" in msg.lower():
            warnings.append(f"Time column '{time_col}': {msg}")

    # -- 4. Heat-flow column (optional) --------------------------------------
    hf_col = getattr(dataset, "heat_flow_column", None)
    if hf_col is not None and hf_col in df.columns:
        ok, msg = validate_numeric_column(df[hf_col])
        if not ok:
            errors.append(f"Heat-flow column '{hf_col}': {msg}")
        elif "NaN" in msg or "nan" in msg.lower():
            warnings.append(f"Heat-flow column '{hf_col}': {msg}")

    # -- 5. Mass column (optional) -------------------------------------------
    mass_col = getattr(dataset, "mass_column", None)
    if mass_col is not None and mass_col in df.columns:
        ok, msg = validate_numeric_column(df[mass_col])
        if not ok:
            errors.append(f"Mass column '{mass_col}': {msg}")
        elif "NaN" in msg or "nan" in msg.lower():
            warnings.append(f"Mass column '{mass_col}': {msg}")

    # -- 6. Sample mass scalar -----------------------------------------------
    sample_mass = getattr(dataset, "sample_mass_mg", None)
    if sample_mass is not None:
        ok, msg = validate_sample_mass(sample_mass)
        if not ok:
            errors.append(f"Sample mass: {msg}")

    # -- 7. Heating rate scalar ----------------------------------------------
    heating_rate = getattr(dataset, "heating_rate", None)
    if heating_rate is not None:
        ok, msg = validate_heating_rate(heating_rate)
        if not ok:
            errors.append(f"Heating rate: {msg}")

    # -- Aggregate results ---------------------------------------------------
    if errors:
        full_message = "Validation failed.\nErrors:\n  " + "\n  ".join(errors)
        if warnings:
            full_message += "\nWarnings:\n  " + "\n  ".join(warnings)
        return False, full_message

    if warnings:
        return True, "Validation passed with warnings.\nWarnings:\n  " + "\n  ".join(
            warnings
        )

    return True, "All checks passed."
