"""
test_report_generator.py
------------------------
Tests for core.report_generator

Covers:
- generate_docx_report: returns valid DOCX bytes for DSC results
- generate_docx_report: embeds metadata, Kissinger, OFW, Friedman, and
  peak-deconvolution sections correctly
- generate_docx_report: works with an empty results dict
- generate_docx_report: writes to a BytesIO buffer
- generate_csv_summary: returns a non-empty CSV string
- generate_csv_summary: header row contains expected column names
- generate_csv_summary: Kissinger row is present with correct values
- generate_csv_summary: OFW and Friedman rows are written
- generate_csv_summary: peak-deconvolution summary row is written
- generate_csv_summary: writes to a StringIO buffer and to a file
"""

from __future__ import annotations

import csv
import io
import os
import sys
import tempfile

import numpy as np
import pytest

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.report_generator import generate_docx_report, generate_csv_summary
from core.kinetics import KineticResult


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

def _make_kissinger(ea=120.0, ln_a=28.5, r2=0.998):
    """Return a minimal KineticResult for Kissinger testing."""
    return KineticResult(
        method="kissinger",
        activation_energy=ea,
        pre_exponential=ln_a,
        r_squared=r2,
    )


def _make_ofw_list():
    """Return a small list of OFW KineticResult objects with alpha in plot_data."""
    return [
        KineticResult(
            method="ozawa_flynn_wall",
            activation_energy=115.0 + i * 2.0,
            r_squared=0.99 - i * 0.01,
            plot_data={"alpha": 0.2 + i * 0.1},
        )
        for i in range(3)
    ]


def _make_friedman_list():
    """Return a small list of Friedman KineticResult objects with alpha in plot_data."""
    return [
        KineticResult(
            method="friedman",
            activation_energy=118.0 + i * 1.5,
            pre_exponential=27.0 + i * 0.5,
            r_squared=0.995 - i * 0.005,
            plot_data={"alpha": 0.2 + i * 0.1},
        )
        for i in range(3)
    ]


def _make_peak_deconv():
    """Return a minimal peak_deconvolution result dict."""
    return {
        "r_squared": 0.9987,
        "params": {
            "p1_center": 200.3,
            "p1_amplitude": 2.1,
            "p1_sigma": 7.8,
        },
        "report": "Fit report text\n",
    }


def _make_dsc_dataset():
    """Return a minimal dataset dict with DSC metadata."""
    class _DS:
        metadata = {"sample_name": "TestSample", "heating_rate": 10.0}

    return {"dsc_test.csv": _DS()}


# ---------------------------------------------------------------------------
# generate_docx_report – return type and size
# ---------------------------------------------------------------------------

class TestGenerateDocxReportReturnType:

    def test_returns_bytes(self):
        """generate_docx_report must return bytes."""
        result = generate_docx_report(results={}, datasets={})
        assert isinstance(result, bytes)

    def test_returns_non_empty_bytes(self):
        """Returned bytes must be non-empty (a real DOCX file)."""
        result = generate_docx_report(results={}, datasets={})
        assert len(result) > 0

    def test_bytes_start_with_zip_magic(self):
        """DOCX files are ZIP archives; the first bytes must be the ZIP magic number."""
        result = generate_docx_report(results={}, datasets={})
        # PK\x03\x04 is the local file header signature of a ZIP file
        assert result[:4] == b"PK\x03\x04", (
            "DOCX output does not start with ZIP magic bytes; file may be corrupt."
        )


# ---------------------------------------------------------------------------
# generate_docx_report – content with DSC-derived results
# ---------------------------------------------------------------------------

class TestGenerateDocxReportContent:

    def test_with_metadata_does_not_raise(self):
        """Passing a global metadata dict must not raise any exception."""
        results = {"metadata": {"operator": "Alice", "instrument": "DSC 3+"}}
        generate_docx_report(results=results, datasets={})

    def test_with_dataset_metadata_does_not_raise(self):
        """Passing a dataset with metadata must not raise any exception."""
        generate_docx_report(results={}, datasets=_make_dsc_dataset())

    def test_with_kissinger_does_not_raise(self):
        """A Kissinger KineticResult in results must not raise."""
        results = {"kissinger": _make_kissinger()}
        generate_docx_report(results=results, datasets={})

    def test_with_ofw_list_does_not_raise(self):
        """A list of OFW KineticResults in results must not raise."""
        results = {"ozawa_flynn_wall": _make_ofw_list()}
        generate_docx_report(results=results, datasets={})

    def test_with_friedman_list_does_not_raise(self):
        """A list of Friedman KineticResults in results must not raise."""
        results = {"friedman": _make_friedman_list()}
        generate_docx_report(results=results, datasets={})

    def test_with_peak_deconvolution_does_not_raise(self):
        """A peak_deconvolution dict in results must not raise."""
        results = {"peak_deconvolution": _make_peak_deconv()}
        generate_docx_report(results=results, datasets={})

    def test_full_dsc_results_does_not_raise(self):
        """All DSC reporting fields together must not raise."""
        results = {
            "metadata": {"sample_name": "Nylon6", "heating_rate": 10.0},
            "kissinger": _make_kissinger(),
            "ozawa_flynn_wall": _make_ofw_list(),
            "friedman": _make_friedman_list(),
            "peak_deconvolution": _make_peak_deconv(),
        }
        generate_docx_report(results=results, datasets=_make_dsc_dataset())

    def test_full_dsc_results_returns_bytes(self):
        """Full DSC report generation must return non-empty bytes."""
        results = {
            "metadata": {"sample_name": "Nylon6", "heating_rate": 10.0},
            "kissinger": _make_kissinger(),
            "ozawa_flynn_wall": _make_ofw_list(),
            "friedman": _make_friedman_list(),
            "peak_deconvolution": _make_peak_deconv(),
        }
        docx_bytes = generate_docx_report(results=results, datasets=_make_dsc_dataset())
        assert isinstance(docx_bytes, bytes) and len(docx_bytes) > 0

    def test_dataset_without_metadata_does_not_raise(self):
        """A dataset dict entry that has no 'metadata' key must not raise."""
        datasets = {"bare_dataset.csv": {}}
        generate_docx_report(results={}, datasets=datasets)

    def test_kissinger_none_values_handled(self):
        """Kissinger result with None pre_exponential / r_squared must not raise."""
        kissinger = KineticResult(
            method="kissinger",
            activation_energy=120.0,
            pre_exponential=None,
            r_squared=None,
        )
        generate_docx_report(results={"kissinger": kissinger}, datasets={})


# ---------------------------------------------------------------------------
# generate_docx_report – output to BytesIO buffer and file path
# ---------------------------------------------------------------------------

class TestGenerateDocxReportOutputTargets:

    def test_writes_to_bytesio_buffer(self):
        """When a BytesIO is passed, it should be written to and seeked back."""
        buf = io.BytesIO()
        result = generate_docx_report(results={}, datasets={}, file_path_or_buffer=buf)
        assert buf.tell() == 0, "BytesIO was not seeked back to 0 after writing"
        assert len(buf.read()) > 0, "BytesIO buffer is empty after report generation"
        assert isinstance(result, bytes)

    def test_writes_to_file_path(self, tmp_path):
        """When a file path string is given, the DOCX should be saved to disk."""
        out_path = str(tmp_path / "test_report.docx")
        generate_docx_report(results={}, datasets={}, file_path_or_buffer=out_path)
        assert os.path.exists(out_path), "DOCX file was not written to the given path"
        assert os.path.getsize(out_path) > 0, "DOCX file is empty"

    def test_file_and_return_value_identical(self, tmp_path):
        """Bytes returned and bytes on disk must be identical."""
        out_path = str(tmp_path / "test_report2.docx")
        results = {"kissinger": _make_kissinger()}
        docx_bytes = generate_docx_report(
            results=results, datasets={}, file_path_or_buffer=out_path
        )
        with open(out_path, "rb") as fh:
            disk_bytes = fh.read()
        assert docx_bytes == disk_bytes


# ---------------------------------------------------------------------------
# generate_csv_summary – return type and structure
# ---------------------------------------------------------------------------

class TestGenerateCsvSummaryReturnType:

    def test_returns_string(self):
        """generate_csv_summary must return a str."""
        result = generate_csv_summary({})
        assert isinstance(result, str)

    def test_returns_non_empty_string(self):
        """Returned string must be non-empty (contains at least a header row)."""
        result = generate_csv_summary({})
        assert len(result.strip()) > 0

    def test_header_row_present(self):
        """The first row must contain the expected column names."""
        csv_str = generate_csv_summary({})
        reader = csv.reader(io.StringIO(csv_str))
        header = next(reader)
        expected_cols = [
            "method", "alpha", "activation_energy_kJ_mol",
            "pre_exponential", "r_squared", "notes",
        ]
        assert header == expected_cols, (
            f"CSV header mismatch.  Got: {header}"
        )


# ---------------------------------------------------------------------------
# generate_csv_summary – DSC kinetic content
# ---------------------------------------------------------------------------

class TestGenerateCsvSummaryContent:

    def _parse_rows(self, results):
        """Helper: return all data rows (excluding header) as list-of-dicts."""
        csv_str = generate_csv_summary(results)
        reader = csv.DictReader(io.StringIO(csv_str))
        return list(reader)

    def test_kissinger_row_written(self):
        """A 'kissinger' row must appear when Kissinger results are present."""
        rows = self._parse_rows({"kissinger": _make_kissinger(ea=120.0, ln_a=28.5, r2=0.998)})
        methods = [r["method"] for r in rows]
        assert "kissinger" in methods

    def test_kissinger_activation_energy_value(self):
        """The Kissinger activation energy in the CSV must match the input (4 d.p.)."""
        rows = self._parse_rows({"kissinger": _make_kissinger(ea=123.456, ln_a=28.5, r2=0.998)})
        kissinger_row = next(r for r in rows if r["method"] == "kissinger")
        assert kissinger_row["activation_energy_kJ_mol"] == "123.4560"

    def test_kissinger_r_squared_value(self):
        """The Kissinger R² in the CSV must match the input (6 d.p.)."""
        rows = self._parse_rows({"kissinger": _make_kissinger(ea=120.0, ln_a=28.5, r2=0.9987654)})
        kissinger_row = next(r for r in rows if r["method"] == "kissinger")
        assert kissinger_row["r_squared"] == "0.998765"

    def test_ofw_rows_written(self):
        """One 'ozawa_flynn_wall' row must appear for each OFW result."""
        ofw = _make_ofw_list()
        rows = self._parse_rows({"ozawa_flynn_wall": ofw})
        ofw_rows = [r for r in rows if r["method"] == "ozawa_flynn_wall"]
        assert len(ofw_rows) == len(ofw)

    def test_friedman_rows_written(self):
        """One 'friedman' row must appear for each Friedman result."""
        friedman = _make_friedman_list()
        rows = self._parse_rows({"friedman": friedman})
        fr_rows = [r for r in rows if r["method"] == "friedman"]
        assert len(fr_rows) == len(friedman)

    def test_peak_deconvolution_summary_row(self):
        """A 'peak_deconvolution' row must be written when that key is present."""
        rows = self._parse_rows({"peak_deconvolution": _make_peak_deconv()})
        methods = [r["method"] for r in rows]
        assert "peak_deconvolution" in methods

    def test_peak_deconvolution_param_rows(self):
        """One 'peak_deconvolution_param' row per fitted parameter must appear."""
        pd_result = _make_peak_deconv()
        n_params = len(pd_result["params"])
        rows = self._parse_rows({"peak_deconvolution": pd_result})
        param_rows = [r for r in rows if r["method"] == "peak_deconvolution_param"]
        assert len(param_rows) == n_params

    def test_empty_results_only_header(self):
        """With no results, only the header row should be present."""
        csv_str = generate_csv_summary({})
        reader = csv.reader(io.StringIO(csv_str))
        all_rows = list(reader)
        # Only the header row; no data rows
        assert len(all_rows) == 1

    def test_none_values_render_as_na(self):
        """KineticResult with None pre_exponential must produce 'N/A' in the CSV."""
        kissinger = KineticResult(
            method="kissinger",
            activation_energy=120.0,
            pre_exponential=None,
            r_squared=None,
        )
        rows = self._parse_rows({"kissinger": kissinger})
        k_row = next(r for r in rows if r["method"] == "kissinger")
        assert k_row["pre_exponential"] == "N/A"
        assert k_row["r_squared"] == "N/A"

    def test_full_dsc_csv_row_count(self):
        """
        Combining Kissinger (1 row), OFW (3 rows), Friedman (3 rows), and
        peak-deconvolution (1 summary + 3 param rows) must produce exactly
        11 data rows plus 1 header row.
        """
        results = {
            "kissinger": _make_kissinger(),
            "ozawa_flynn_wall": _make_ofw_list(),    # 3 items
            "friedman": _make_friedman_list(),        # 3 items
            "peak_deconvolution": _make_peak_deconv(),  # 1 summary + 3 params
        }
        csv_str = generate_csv_summary(results)
        all_rows = list(csv.reader(io.StringIO(csv_str)))
        # 1 header + 1 Kissinger + 3 OFW + 3 Friedman + 1 deconv + 3 params = 12
        assert len(all_rows) == 12


# ---------------------------------------------------------------------------
# generate_csv_summary – output to StringIO buffer and file path
# ---------------------------------------------------------------------------

class TestGenerateCsvSummaryOutputTargets:

    def test_writes_to_stringio_buffer(self):
        """When a StringIO is passed, it should be written to and seeked back."""
        buf = io.StringIO()
        csv_str = generate_csv_summary({"kissinger": _make_kissinger()}, buf)
        assert buf.tell() == 0, "StringIO was not seeked back to 0 after writing"
        assert len(buf.read()) > 0, "StringIO buffer is empty after summary generation"
        assert isinstance(csv_str, str)

    def test_writes_to_file_path(self, tmp_path):
        """When a file path string is given, the CSV should be saved to disk."""
        out_path = str(tmp_path / "results.csv")
        generate_csv_summary({"kissinger": _make_kissinger()}, out_path)
        assert os.path.exists(out_path), "CSV file was not written to the given path"
        assert os.path.getsize(out_path) > 0, "CSV file is empty"

    def test_file_and_return_value_identical(self, tmp_path):
        """String returned and content on disk must be identical (newline-normalised)."""
        out_path = str(tmp_path / "results2.csv")
        results = {"kissinger": _make_kissinger()}
        csv_str = generate_csv_summary(results, out_path)
        with open(out_path, newline="", encoding="utf-8") as fh:
            disk_content = fh.read()
        assert csv_str == disk_content
