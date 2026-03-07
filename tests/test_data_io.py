"""
test_data_io.py
---------------
Tests for core.data_io

Covers:
- ThermalDataset creation and deep-copy semantics
- guess_columns() column-role detection for DSC and TGA column naming conventions
- read_thermal_data() with a real (temp-file) CSV
- read_thermal_data() with an explicit column_mapping override
- export_results_csv() round-trip verification
"""

import io
import os
import sys
import tempfile

import numpy as np
import pandas as pd
import pytest

# Path insertion is handled by conftest.py; importing here as a safety net
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.data_io import (
    ThermalDataset,
    detect_vendor,
    guess_columns,
    read_thermal_data,
    export_results_csv,
)


# ---------------------------------------------------------------------------
# ThermalDataset creation
# ---------------------------------------------------------------------------

class TestThermalDatasetCreation:

    def test_thermal_dataset_creation(self, thermal_dataset):
        """ThermalDataset should store all required attributes correctly."""
        ds = thermal_dataset

        assert isinstance(ds, ThermalDataset)
        assert isinstance(ds.data, pd.DataFrame)
        assert "temperature" in ds.data.columns
        assert "signal" in ds.data.columns
        assert ds.data_type == "DSC"
        assert ds.metadata["sample_name"] == "SyntheticDSC"
        assert ds.units["temperature"] == "degC"
        assert ds.units["signal"] == "mW/mg"
        assert len(ds.data) == 500

    def test_thermal_dataset_data_types(self, thermal_dataset):
        """temperature and signal columns should be numeric (float64)."""
        ds = thermal_dataset
        assert pd.api.types.is_float_dtype(ds.data["temperature"])
        assert pd.api.types.is_float_dtype(ds.data["signal"])

    def test_thermal_dataset_copy(self, thermal_dataset):
        """copy() should produce an independent deep copy."""
        original = thermal_dataset
        copied = original.copy()

        # Structural equality
        assert copied.data_type == original.data_type
        assert copied.metadata == original.metadata
        pd.testing.assert_frame_equal(copied.data, original.data)

        # Independence: mutating the copy must not affect the original
        copied.data.at[0, "temperature"] = -9999.0
        assert original.data.at[0, "temperature"] != -9999.0

        copied.metadata["sample_name"] = "MUTATED"
        assert original.metadata["sample_name"] != "MUTATED"


# ---------------------------------------------------------------------------
# guess_columns
# ---------------------------------------------------------------------------

class TestGuessColumns:

    def test_guess_columns_dsc(self):
        """Typical DSC column headers should be classified correctly."""
        df = pd.DataFrame(
            {
                "Temperature": [100, 200, 300],
                "HeatFlow": [0.1, 0.5, 0.2],
                "Time": [1, 2, 3],
            }
        )
        result = guess_columns(df)

        assert result["temperature"] == "Temperature"
        assert result["signal"] == "HeatFlow"
        assert result["time"] == "Time"
        assert result["data_type"] == "DSC"

    def test_guess_columns_tga(self):
        """Typical TGA column headers should be classified correctly."""
        df = pd.DataFrame(
            {
                "Temp": [100, 200, 300],
                "Weight": [100.0, 95.0, 88.0],
            }
        )
        result = guess_columns(df)

        assert result["temperature"] == "Temp"
        assert result["signal"] == "Weight"
        assert result["data_type"] == "TGA"

    def test_guess_columns_dsc_mw_unit_in_header(self):
        """Column name containing 'mW' should be detected as DSC signal."""
        df = pd.DataFrame(
            {
                "T/degC": [50.0, 100.0, 150.0],
                "DSC/(mW)": [0.0, 1.0, 0.5],
            }
        )
        result = guess_columns(df)
        assert result["data_type"] == "DSC"
        assert result["signal"] == "DSC/(mW)"

    def test_guess_columns_mass_percent(self):
        """Column name ending in '%' should be detected as TGA signal."""
        df = pd.DataFrame(
            {
                "Temp": [50.0, 100.0, 150.0],
                "Mass%": [100.0, 95.0, 88.0],
            }
        )
        result = guess_columns(df)
        assert result["data_type"] == "TGA"

    def test_guess_columns_returns_none_for_missing(self):
        """When no time column exists the result should have time=None."""
        df = pd.DataFrame(
            {
                "Temperature": [100.0, 200.0, 300.0],
                "HeatFlow": [0.1, 0.5, 0.2],
            }
        )
        result = guess_columns(df)
        assert result["time"] is None

    def test_detect_vendor_from_common_headers(self):
        assert detect_vendor("netzsch_export.csv", ["Temp./°C", "DSC/(mW/mg)"]) == "NETZSCH"
        assert detect_vendor("trios.csv", ["Temperature (°C)", "Heat Flow (W/g)"]) == "TA"
        assert detect_vendor("generic.csv", ["Temperature", "Signal"]) == "Generic"


# ---------------------------------------------------------------------------
# read_thermal_data with a temporary CSV file
# ---------------------------------------------------------------------------

class TestReadCSV:

    def _make_temp_csv(self, content: str) -> str:
        """Write *content* to a temp file and return its path."""
        fd, path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        return path

    def test_read_csv_file(self):
        """read_thermal_data should parse a well-formed CSV into a ThermalDataset."""
        csv_content = (
            "Temperature,HeatFlow\n"
            "30.0,0.00\n"
            "50.0,0.05\n"
            "100.0,0.10\n"
            "150.0,0.50\n"
            "200.0,1.00\n"
            "250.0,2.00\n"
            "300.0,0.50\n"
        )
        path = self._make_temp_csv(csv_content)
        try:
            ds = read_thermal_data(path)
            assert isinstance(ds, ThermalDataset)
            assert len(ds.data) == 7
            assert "temperature" in ds.data.columns
            assert "signal" in ds.data.columns
            assert ds.data["temperature"].iloc[0] == pytest.approx(30.0)
            assert ds.data["temperature"].iloc[-1] == pytest.approx(300.0)
        finally:
            os.unlink(path)

    def test_read_csv_file_data_monotone(self):
        """Temperature column returned by read_thermal_data should be numeric."""
        csv_content = (
            "T_degC,DSC_mW\n"
            "100.0,0.1\n"
            "200.0,0.5\n"
            "300.0,0.2\n"
        )
        path = self._make_temp_csv(csv_content)
        try:
            ds = read_thermal_data(path)
            temps = ds.data["temperature"].values
            # Temperature values should be numeric floats
            assert np.issubdtype(temps.dtype, np.floating)
        finally:
            os.unlink(path)

    def test_read_with_column_mapping(self):
        """Explicit column_mapping should override automatic detection."""
        csv_content = (
            "T,F,t\n"
            "30.0,0.10,0.0\n"
            "100.0,0.50,1.0\n"
            "200.0,1.00,2.0\n"
            "300.0,0.20,3.0\n"
        )
        path = self._make_temp_csv(csv_content)
        try:
            ds = read_thermal_data(
                path,
                column_mapping={"temperature": "T", "signal": "F", "time": "t"},
                data_type="DSC",
            )
            assert isinstance(ds, ThermalDataset)
            assert ds.data_type == "DSC"
            assert "temperature" in ds.data.columns
            assert "signal" in ds.data.columns
            assert "time" in ds.data.columns
            assert ds.data["time"].iloc[-1] == pytest.approx(3.0)
        finally:
            os.unlink(path)

    def test_read_from_stringio(self):
        """read_thermal_data should accept a StringIO buffer as the source."""
        csv_content = (
            "Temperature,HeatFlow\n"
            "50.0,0.1\n"
            "100.0,0.5\n"
            "150.0,1.0\n"
        )
        buf = io.StringIO(csv_content)
        ds = read_thermal_data(buf)
        assert isinstance(ds, ThermalDataset)
        assert len(ds.data) == 3
        assert ds.metadata["vendor"] == "Generic"

    def test_read_csv_raises_on_missing_temperature(self):
        """read_thermal_data should raise ValueError when temperature cannot be identified."""
        csv_content = "Signal\n1.0\n2.0\n3.0\n"
        buf = io.StringIO(csv_content)
        with pytest.raises(ValueError, match="temperature"):
            read_thermal_data(buf)


# ---------------------------------------------------------------------------
# export_results_csv
# ---------------------------------------------------------------------------

class TestExportResultsCSV:

    def test_export_results_csv(self):
        """export_results_csv should write a readable two-column CSV."""
        results = {
            "peak_temperature": 250.3,
            "onset_temperature": 242.1,
            "area": -145.7,
            "metadata": {
                "sample": "TestSample",
                "rate": 10,
            },
        }
        buf = io.StringIO()
        export_results_csv(results, buf)
        buf.seek(0)
        df = pd.read_csv(buf)

        assert list(df.columns) == ["parameter", "value"]
        # Flat keys
        assert "peak_temperature" in df["parameter"].values
        assert "onset_temperature" in df["parameter"].values
        # Nested keys flattened with dot notation
        assert "metadata.sample" in df["parameter"].values
        assert "metadata.rate" in df["parameter"].values

    def test_export_results_csv_values_correct(self):
        """Exported numeric values should round-trip correctly."""
        results = {"peak_temp": 250.0, "area": -145.5}
        buf = io.StringIO()
        export_results_csv(results, buf)
        buf.seek(0)
        df = pd.read_csv(buf)
        row = df[df["parameter"] == "peak_temp"]
        assert float(row["value"].iloc[0]) == pytest.approx(250.0)

    def test_export_results_csv_to_file(self):
        """export_results_csv should successfully write to a file path."""
        results = {"test_key": 42}
        fd, path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            export_results_csv(results, path)
            df = pd.read_csv(path)
            assert "test_key" in df["parameter"].values
        finally:
            os.unlink(path)

    def test_export_results_csv_raises_on_non_dict(self):
        """export_results_csv should raise TypeError for non-dict input."""
        buf = io.StringIO()
        with pytest.raises(TypeError):
            export_results_csv([1, 2, 3], buf)
