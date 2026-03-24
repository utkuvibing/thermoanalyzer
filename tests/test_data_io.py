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
    detect_vendor_info,
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
        assert ds.metadata["source_data_hash"]
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

    def test_detect_vendor_info_reports_review_for_generic_headers(self):
        info = detect_vendor_info("generic.csv", ["Temperature", "Signal"])

        assert info["vendor"] == "Generic"
        assert info["confidence"] == "review"
        assert info["warnings"]

    def test_guess_columns_ambiguous_signal_column_warns_and_leaves_type_unknown(self):
        df = pd.DataFrame(
            {
                "Temperature": [30.0, 50.0, 70.0],
                "Signal": [0.1, 0.2, 0.3],
                "Reference": [1.0, 1.0, 1.0],
            }
        )

        result = guess_columns(df)

        assert result["temperature"] == "Temperature"
        assert result["signal"] == "Signal"
        assert result["data_type"] == "unknown"
        assert result["confidence"]["overall"] == "review"
        assert any("analysis type remains unknown" in warning.lower() for warning in result["warnings"])

    def test_guess_columns_misleading_header_warns_instead_of_overclaiming(self):
        df = pd.DataFrame(
            {
                "Temp": [30.0, 50.0, 70.0],
                "Weight (mW)": [1.0, 0.8, 0.5],
            }
        )

        result = guess_columns(df)

        assert result["temperature"] == "Temp"
        assert result["signal"] == "Weight (mW)"
        assert result["data_type"] == "unknown"
        assert any("ambiguous" in warning.lower() for warning in result["warnings"])

    def test_guess_columns_ftir_wavenumber_and_absorbance(self):
        df = pd.DataFrame(
            {
                "Wavenumber (cm-1)": [4000.0, 3500.0, 3000.0],
                "Absorbance": [0.02, 0.18, 0.31],
            }
        )

        result = guess_columns(df)

        assert result["temperature"] == "Wavenumber (cm-1)"
        assert result["signal"] == "Absorbance"
        assert result["data_type"] == "FTIR"

    def test_guess_columns_raman_shift_and_intensity(self):
        df = pd.DataFrame(
            {
                "Raman Shift (cm-1)": [120.0, 350.0, 620.0],
                "Raman Intensity (counts)": [10.0, 35.0, 18.0],
            }
        )

        result = guess_columns(df)

        assert result["temperature"] == "Raman Shift (cm-1)"
        assert result["signal"] == "Raman Intensity (counts)"
        assert result["data_type"] == "RAMAN"

    def test_guess_columns_xrd_from_axis_and_intensity_headers(self):
        df = pd.DataFrame(
            {
                "2theta (deg)": [10.0, 10.5, 11.0],
                "Intensity (counts)": [120.0, 210.0, 160.0],
            }
        )

        result = guess_columns(df)

        assert result["temperature"] == "2theta (deg)"
        assert result["signal"] == "Intensity (counts)"
        assert result["data_type"] == "XRD"

    def test_guess_columns_xrd_source_name_bias_for_generic_headers(self):
        df = pd.DataFrame(
            {
                "temperature": [5.0, 5.2, 5.4],
                "signal": [1000.0, 1500.0, 1100.0],
            }
        )

        result = guess_columns(df, source_name="xrd_2024_0303_zenodo.csv")

        assert result["data_type"] == "XRD"


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

    def test_read_semicolon_delimited_generic_csv_records_import_review(self):
        buf = io.StringIO(
            "Temperature (°C);Signal\n"
            "30.0;0.1\n"
            "50.0;0.5\n"
            "70.0;0.2\n"
        )

        ds = read_thermal_data(buf)

        assert isinstance(ds, ThermalDataset)
        assert len(ds.data) == 3
        assert ds.metadata["import_delimiter"] == ";"
        assert ds.metadata["import_confidence"] == "review"
        assert ds.metadata["import_review_required"] is True

    def test_read_tab_delimited_netzsch_like_export_is_unambiguous(self):
        buf = io.StringIO(
            "Temp./°C\tDSC/(mW/mg)\n"
            "30.0\t0.10\n"
            "50.0\t0.50\n"
            "70.0\t0.15\n"
        )

        ds = read_thermal_data(buf)

        assert ds.data_type == "DSC"
        assert ds.units["signal"] == "mW/mg"
        assert ds.metadata["vendor"] == "NETZSCH"
        assert ds.metadata["vendor_detection_confidence"] in {"high", "medium"}
        assert ds.metadata["import_delimiter"] == "\t"

    def test_read_ta_like_export_sets_inferred_vendor_and_type(self):
        buf = io.StringIO(
            "Temperature (°C),Heat Flow (W/g)\n"
            "30.0,0.10\n"
            "50.0,0.50\n"
            "70.0,0.15\n"
        )

        ds = read_thermal_data(buf)

        assert ds.data_type == "DSC"
        assert ds.units["signal"] == "W/g"
        assert ds.metadata["vendor"] == "TA"
        assert ds.metadata["inferred_vendor"] == "TA"
        assert ds.metadata["import_confidence"] in {"high", "medium"}

    def test_read_ambiguous_weight_column_requires_review(self):
        buf = io.StringIO(
            "Temperature,Weight\n"
            "30.0,100.0\n"
            "50.0,95.0\n"
            "70.0,90.0\n"
        )

        ds = read_thermal_data(buf)

        assert ds.data_type == "TGA"
        assert ds.units["signal"] == "a.u."
        assert ds.metadata["import_review_required"] is True
        assert ds.metadata["import_confidence"] == "review"
        assert any("absolute mass" in warning.lower() for warning in ds.metadata["import_warnings"])

    def test_read_missing_metadata_still_populates_import_context(self):
        buf = io.StringIO(
            "Temperature (°C),Heat Flow (mW)\n"
            "30.0,0.1\n"
            "50.0,0.4\n"
            "70.0,0.2\n"
        )

        ds = read_thermal_data(buf)

        assert ds.metadata["import_method"] == "auto"
        assert "import_confidence" in ds.metadata
        assert "inferred_analysis_type" in ds.metadata
        assert "inferred_signal_unit" in ds.metadata
        assert "inferred_vendor" in ds.metadata
        assert isinstance(ds.metadata["import_warnings"], list)

    def test_read_ftir_csv_applies_user_confirmation_for_low_confidence_modality(self):
        buf = io.StringIO(
            "X,Intensity\n"
            "4000,0.12\n"
            "3500,0.24\n"
            "3000,0.18\n"
        )

        ds = read_thermal_data(buf, data_type="FTIR")

        assert ds.data_type == "FTIR"
        assert ds.units["temperature"] == "cm^-1"
        assert ds.metadata["modality_confirmation_required"] is True
        assert ds.metadata["modality_confirmation_applied"] is True
        assert any("user-confirmed" in warning.lower() for warning in ds.metadata["import_warnings"])

    def test_read_raman_csv_infers_spectral_contract_metadata(self):
        buf = io.StringIO(
            "Raman Shift (cm-1),Raman Intensity (counts)\n"
            "100,11\n"
            "150,28\n"
            "220,16\n"
        )

        ds = read_thermal_data(buf)

        assert ds.data_type == "RAMAN"
        assert ds.units["temperature"] == "cm^-1"
        assert ds.metadata["spectral_axis_role"] == "wavenumber"
        assert ds.metadata["modality_confirmation_required"] is False

    def test_read_jcamp_single_spectrum_imports_as_ftir_mvp(self):
        buf = io.StringIO(
            "##TITLE=FTIR Demo\n"
            "##JCAMP-DX=5.00\n"
            "##DATA TYPE=INFRARED SPECTRUM\n"
            "##XUNITS=1/CM\n"
            "##YUNITS=ABSORBANCE\n"
            "##XYDATA=(X++(Y..Y))\n"
            "4000 0.10\n"
            "3998 0.11\n"
            "3996 0.12\n"
            "##END=\n"
        )
        buf.name = "sample.jdx"

        ds = read_thermal_data(buf)

        assert ds.data_type == "FTIR"
        assert len(ds.data) == 3
        assert ds.units["temperature"] == "cm^-1"
        assert ds.metadata["import_format"] == "jcamp_dx"

    def test_read_jcamp_rejects_multiblock_variants_with_explicit_message(self):
        buf = io.StringIO(
            "##TITLE=Linked Spectra\n"
            "##JCAMP-DX=5.00\n"
            "##BLOCKS=2\n"
            "##XYDATA=(X++(Y..Y))\n"
            "4000 0.10\n"
            "3998 0.11\n"
            "##END=\n"
        )
        buf.name = "linked.dx"

        with pytest.raises(ValueError, match="single-spectrum files only"):
            read_thermal_data(buf)

    def test_read_xrd_xy_infers_normalized_contract_metadata(self):
        buf = io.StringIO(
            "# wavelength 1.5406\n"
            "2theta intensity\n"
            "10.0 100\n"
            "10.5 140\n"
            "11.0 120\n"
        )
        buf.name = "pattern.xy"

        ds = read_thermal_data(buf)

        assert ds.data_type == "XRD"
        assert len(ds.data) == 3
        assert ds.metadata["import_format"] == "xrd_xy_dat"
        assert ds.metadata["xrd_axis_role"] == "two_theta"
        assert ds.metadata["xrd_axis_unit"] == "degree_2theta"
        assert ds.metadata["xrd_wavelength_angstrom"] == pytest.approx(1.5406)
        assert ds.units["temperature"] == "degree_2theta"

    def test_read_xrd_dat_respects_explicit_xrd_type_even_without_headers(self):
        buf = io.StringIO(
            "5.0 20\n"
            "6.0 25\n"
            "7.0 30\n"
        )
        buf.name = "unknown_pattern.dat"

        ds = read_thermal_data(buf, data_type="XRD")

        assert ds.data_type == "XRD"
        assert len(ds.data) == 3
        assert ds.metadata["import_format"] == "xrd_xy_dat"
        assert ds.metadata["xrd_axis_role"] == "two_theta"

    def test_read_xrd_txt_with_whitespace_numeric_pairs_infers_from_filename(self):
        buf = io.StringIO(
            "\n"
            "   5.00173         78 \n"
            "   5.01789         83 \n"
            "   5.03404         98 \n"
            "   5.05019        104 \n"
            "   5.06634        109 \n"
            "   5.08249        100 \n"
            "   5.09865        121 \n"
            "   5.11480         94 \n"
            "   5.13095         95 \n"
            "   5.14710        112 \n"
        )
        buf.name = "xrd_garnet.txt"

        ds = read_thermal_data(buf)

        assert ds.data_type == "XRD"
        assert len(ds.data) == 10
        assert ds.metadata["import_format"] == "xrd_xy_dat"
        assert ds.units["temperature"] == "degree_2theta"
        assert ds.units["signal"] == "counts"

    def test_read_xrd_csv_infers_type_from_source_name_and_normalizes_units(self):
        buf = io.StringIO(
            "temperature,signal\n"
            "5.01,10100\n"
            "5.02,10210\n"
            "5.03,10080\n"
        )
        buf.name = "xrd_2024_0303_zenodo.csv"

        ds = read_thermal_data(buf)

        assert ds.data_type == "XRD"
        assert ds.units["temperature"] == "degree_2theta"
        assert ds.units["signal"] == "counts"

    def test_read_xrd_manual_mapping_rewrites_non_xrd_units_to_xrd_defaults(self):
        buf = io.StringIO(
            "Temperature (°C),Heat Flow (mW)\n"
            "5.01,10100\n"
            "5.02,10210\n"
            "5.03,10080\n"
        )
        buf.name = "generic.csv"

        ds = read_thermal_data(
            buf,
            column_mapping={"temperature": "Temperature (°C)", "signal": "Heat Flow (mW)"},
            data_type="XRD",
        )

        assert ds.data_type == "XRD"
        assert ds.units["temperature"] == "degree_2theta"
        assert ds.units["signal"] == "counts"

    def test_read_xrd_manual_mapping_marks_suspicious_axis_as_stable_match_blocker(self):
        buf = io.BytesIO()
        pd.DataFrame(
            {
                "Run": [1, 2, 3],
                "Temperature": [5.01, 5.02, 5.03],
                "Intensity": [10100, 10210, 10080],
            }
        ).to_excel(buf, index=False)
        buf.seek(0)
        buf.name = "generic_columns.xlsx"

        ds = read_thermal_data(
            buf,
            column_mapping={"temperature": "Temperature", "signal": "Intensity"},
            data_type="XRD",
        )

        assert ds.data_type == "XRD"
        assert ds.metadata["xrd_axis_mapping_review_required"] is True
        assert ds.metadata["xrd_stable_matching_blocked"] is True
        assert ds.metadata["xrd_provenance_state"] == "incomplete"
        assert "2theta/angle" in " ".join(ds.metadata["import_warnings"]).lower()

    def test_read_xrd_manual_mapping_honors_explicit_axis_confirmation_override(self):
        buf = io.BytesIO()
        pd.DataFrame(
            {
                "Run": [1, 2, 3],
                "Temperature": [5.01, 5.02, 5.03],
                "Intensity": [10100, 10210, 10080],
            }
        ).to_excel(buf, index=False)
        buf.seek(0)
        buf.name = "generic_columns.xlsx"

        ds = read_thermal_data(
            buf,
            column_mapping={"temperature": "Temperature", "signal": "Intensity"},
            data_type="XRD",
            metadata={"xrd_axis_mapping_confirmed": True, "xrd_wavelength_angstrom": 1.5406},
        )

        assert ds.data_type == "XRD"
        assert ds.metadata["xrd_axis_mapping_confirmed"] is True
        assert ds.metadata["xrd_axis_mapping_review_required"] is False
        assert ds.metadata["xrd_stable_matching_blocked"] is False
        assert ds.metadata["xrd_wavelength_angstrom"] == 1.5406

    def test_read_xrd_cif_supports_bounded_powder_pattern_loop(self):
        buf = io.StringIO(
            "data_demo\n"
            "_diffrn_radiation_wavelength 1.5406\n"
            "loop_\n"
            "_pd_meas_2theta_scan\n"
            "_pd_meas_intensity_total\n"
            "10.0 100\n"
            "10.2 125\n"
            "10.4 110\n"
        )
        buf.name = "pattern.cif"

        ds = read_thermal_data(buf)

        assert ds.data_type == "XRD"
        assert len(ds.data) == 3
        assert ds.metadata["import_format"] == "xrd_cif"
        assert ds.metadata["xrd_axis_role"] == "two_theta"
        assert ds.metadata["xrd_wavelength_angstrom"] == pytest.approx(1.5406)

    def test_read_xrd_cif_rejects_structural_only_scope_with_explicit_message(self):
        buf = io.StringIO(
            "data_struct\n"
            "_cell_length_a 5.43\n"
            "loop_\n"
            "_atom_site_label\n"
            "_atom_site_fract_x\n"
            "Si1 0.0\n"
        )
        buf.name = "structure_only.cif"

        with pytest.raises(ValueError, match="outside MVP scope"):
            read_thermal_data(buf)

    def test_read_xrd_cif_rejects_multiblock_variants(self):
        buf = io.StringIO(
            "data_one\n"
            "loop_\n"
            "_pd_meas_2theta_scan\n"
            "_pd_meas_intensity_total\n"
            "10.0 100\n"
            "data_two\n"
            "loop_\n"
            "_pd_meas_2theta_scan\n"
            "_pd_meas_intensity_total\n"
            "10.5 110\n"
        )
        buf.name = "multiblock.cif"

        with pytest.raises(ValueError, match="exactly one data_ block"):
            read_thermal_data(buf)

    def test_read_academic_dta_sample_with_explicit_type(self):
        sample_path = os.path.join(_ROOT, "sample_data", "dta_tnaa_5c_mendeley.csv")
        if not os.path.exists(sample_path):
            pytest.skip("Academic DTA sample not present in this checkout.")

        ds = read_thermal_data(sample_path, data_type="DTA")

        assert ds.data_type == "DTA"
        assert len(ds.data) > 1000
        assert "temperature" in ds.data.columns
        assert "signal" in ds.data.columns

    def test_read_academic_xrd_sample_with_explicit_type(self):
        sample_path = os.path.join(_ROOT, "sample_data", "xrd_2024_0304_zenodo.csv")
        if not os.path.exists(sample_path):
            pytest.skip("Academic XRD sample not present in this checkout.")

        ds = read_thermal_data(sample_path, data_type="XRD")

        assert ds.data_type == "XRD"
        assert len(ds.data) > 1000
        assert ds.metadata["xrd_axis_role"] == "two_theta"
        assert ds.units["temperature"] == "degree_2theta"

    def test_read_academic_ftir_sample_with_explicit_type(self):
        sample_path = os.path.join(_ROOT, "sample_data", "ftir_particleboard_50g_figshare.csv")
        if not os.path.exists(sample_path):
            pytest.skip("Academic FTIR sample not present in this checkout.")

        ds = read_thermal_data(sample_path, data_type="FTIR")

        assert ds.data_type == "FTIR"
        assert len(ds.data) > 1000
        assert ds.units["temperature"] == "cm^-1"

    def test_read_academic_raman_sample_with_explicit_type(self):
        sample_path = os.path.join(_ROOT, "sample_data", "raman_cnt_figshare.csv")
        if not os.path.exists(sample_path):
            pytest.skip("Academic Raman sample not present in this checkout.")

        ds = read_thermal_data(sample_path, data_type="RAMAN")

        assert ds.data_type == "RAMAN"
        assert len(ds.data) > 500
        assert ds.units["temperature"] == "cm^-1"

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

