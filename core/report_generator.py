"""
Report generation for thermal analysis results.

Provides:
- generate_docx_report  : produces a styled DOCX document (python-docx)
- generate_csv_summary  : produces a flat CSV string of all numeric results
"""

from __future__ import annotations

import csv
import io
import datetime
from typing import Optional, Union

try:
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "python-docx is required for DOCX report generation. "
        "Install it with:  pip install python-docx"
    ) from exc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_cell_bg(cell, hex_color: str) -> None:
    """Set the background colour of a table cell (hex, e.g. 'D9E1F2')."""
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tc_pr.append(shd)


def _add_heading(doc: Document, text: str, level: int = 1) -> None:
    """Add a heading paragraph, styled with the built-in Heading styles."""
    doc.add_heading(text, level=level)


def _add_key_value_table(doc: Document, data: dict) -> None:
    """
    Add a two-column (Key | Value) table from a flat dict.
    Header row is shaded blue-grey.
    """
    table = doc.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.LEFT

    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "Parameter"
    hdr_cells[1].text = "Value"
    for cell in hdr_cells:
        _set_cell_bg(cell, "4472C4")
        for para in cell.paragraphs:
            run = para.runs[0] if para.runs else para.add_run(cell.text)
            run.font.bold = True
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    for key, value in data.items():
        row_cells = table.add_row().cells
        row_cells[0].text = str(key)
        row_cells[1].text = str(value)


def _add_results_table(doc: Document, headers: list[str], rows: list[list]) -> None:
    """
    Add a results table with custom headers and data rows.
    Alternate rows are shaded light grey for readability.
    """
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"

    hdr_cells = table.rows[0].cells
    for i, header in enumerate(headers):
        hdr_cells[i].text = header
        _set_cell_bg(hdr_cells[i], "4472C4")
        for para in hdr_cells[i].paragraphs:
            run = para.runs[0] if para.runs else para.add_run(hdr_cells[i].text)
            run.font.bold = True
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    for row_idx, row_data in enumerate(rows):
        row_cells = table.add_row().cells
        for i, value in enumerate(row_data):
            row_cells[i].text = str(value)
            if row_idx % 2 == 1:
                _set_cell_bg(row_cells[i], "DCE6F1")


def _format_float(value, decimals: int = 4) -> str:
    """Format a numeric value; return 'N/A' for None."""
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return str(value)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_docx_report(
    results: dict,
    datasets: dict,
    figures: Optional[dict] = None,
    file_path_or_buffer: Optional[Union[str, io.BytesIO]] = None,
) -> bytes:
    """
    Generate a DOCX thermal analysis report.

    Parameters
    ----------
    results : dict
        Analysis results.  Recognised keys (all optional):

        - ``'kissinger'`` : a ``KineticResult`` (from kinetics.py)
        - ``'ozawa_flynn_wall'`` : list of ``KineticResult``
        - ``'friedman'`` : list of ``KineticResult``
        - ``'peak_deconvolution'`` : dict returned by deconvolve_peaks()
        - ``'metadata'`` : dict of free-form experimental conditions

    datasets : dict
        Mapping of dataset name -> object (or dict).  Only the keys and any
        ``metadata`` attribute / key are used for the Experimental Conditions
        section.

    figures : dict, optional
        Mapping of figure caption -> PNG bytes.  Each entry is embedded as an
        inline image at 5.5 inches wide.

    file_path_or_buffer : str or BytesIO, optional
        If a file path string is given the DOCX is saved there *and* returned
        as bytes.  If a BytesIO is given it is written to that buffer.
        If None (default) only bytes are returned.

    Returns
    -------
    bytes
        Raw bytes of the DOCX file.
    """
    doc = Document()

    # ---- Title page --------------------------------------------------------
    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title_para.add_run("Thermal Analysis Report")
    title_run.bold = True
    title_run.font.size = Pt(20)

    date_para = doc.add_paragraph()
    date_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    date_para.add_run(
        f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d  %H:%M')}"
    )
    doc.add_paragraph()  # spacer

    # ---- Experimental Conditions -------------------------------------------
    _add_heading(doc, "1. Experimental Conditions", level=1)

    # Global metadata block (from results dict)
    global_meta = results.get("metadata", {})
    if global_meta:
        doc.add_paragraph("Global Parameters", style="Heading 2")
        _add_key_value_table(doc, global_meta)
        doc.add_paragraph()

    # Per-dataset metadata
    for ds_name, ds in datasets.items():
        meta = {}
        if hasattr(ds, "metadata"):
            meta = ds.metadata or {}
        elif isinstance(ds, dict):
            meta = ds.get("metadata", {})

        doc.add_paragraph(f"Dataset: {ds_name}", style="Heading 2")
        if meta:
            _add_key_value_table(doc, meta)
        else:
            doc.add_paragraph("No metadata available for this dataset.")
        doc.add_paragraph()

    # ---- Kinetic Analysis Results ------------------------------------------
    _add_heading(doc, "2. Kinetic Analysis", level=1)

    # Kissinger
    kissinger = results.get("kissinger")
    if kissinger is not None:
        doc.add_paragraph("Kissinger Method", style="Heading 2")
        kd = {
            "Activation Energy (kJ/mol)": _format_float(
                kissinger.activation_energy, 2
            ),
            "ln(A)  [pre-exponential]": _format_float(
                kissinger.pre_exponential, 4
            ),
            "R²": _format_float(kissinger.r_squared, 6),
        }
        _add_key_value_table(doc, kd)
        doc.add_paragraph()

    # Ozawa-Flynn-Wall
    ofw_list = results.get("ozawa_flynn_wall")
    if ofw_list:
        doc.add_paragraph("Ozawa-Flynn-Wall (Isoconversional)", style="Heading 2")
        headers = ["Conversion α", "Ea (kJ/mol)", "R²"]
        rows = [
            [
                _format_float(r.plot_data.get("alpha") if r.plot_data else None, 2),
                _format_float(r.activation_energy, 2),
                _format_float(r.r_squared, 6),
            ]
            for r in ofw_list
        ]
        _add_results_table(doc, headers, rows)
        doc.add_paragraph()

    # Friedman
    friedman_list = results.get("friedman")
    if friedman_list:
        doc.add_paragraph("Friedman (Differential Isoconversional)", style="Heading 2")
        headers = ["Conversion α", "Ea (kJ/mol)", "ln[A·f(α)]", "R²"]
        rows = [
            [
                _format_float(r.plot_data.get("alpha") if r.plot_data else None, 2),
                _format_float(r.activation_energy, 2),
                _format_float(r.pre_exponential, 4),
                _format_float(r.r_squared, 6),
            ]
            for r in friedman_list
        ]
        _add_results_table(doc, headers, rows)
        doc.add_paragraph()

    # ---- Peak Deconvolution Results ----------------------------------------
    peak_deconv = results.get("peak_deconvolution")
    if peak_deconv is not None:
        _add_heading(doc, "3. Peak Deconvolution", level=1)
        doc.add_paragraph(
            f"Overall R² = {_format_float(peak_deconv.get('r_squared'), 6)}"
        )

        # Individual peak parameters
        params = peak_deconv.get("params", {})
        if params:
            # Group parameters by peak prefix (p1_, p2_, ...)
            peak_groups: dict[str, dict] = {}
            for param_name, value in params.items():
                parts = param_name.split("_", 1)
                prefix = parts[0] + "_" if len(parts) == 2 else param_name
                peak_groups.setdefault(prefix, {})[param_name] = value

            headers = ["Peak", "Parameter", "Value"]
            rows: list[list] = []
            for prefix, param_dict in sorted(peak_groups.items()):
                for pname, pval in sorted(param_dict.items()):
                    rows.append([prefix.rstrip("_"), pname, _format_float(pval, 6)])
            _add_results_table(doc, headers, rows)
            doc.add_paragraph()

        # lmfit report (in a monospace paragraph)
        report_text = peak_deconv.get("report", "")
        if report_text:
            doc.add_paragraph("lmfit Fit Report", style="Heading 2")
            p = doc.add_paragraph()
            run = p.add_run(report_text)
            run.font.name = "Courier New"
            run.font.size = Pt(8)
            doc.add_paragraph()

    # ---- Figures -----------------------------------------------------------
    if figures:
        section_num = 4
        _add_heading(doc, f"{section_num}. Figures", level=1)
        for caption, png_bytes in figures.items():
            doc.add_paragraph(caption, style="Heading 2")
            img_stream = io.BytesIO(png_bytes)
            doc.add_picture(img_stream, width=Inches(5.5))
            last_para = doc.paragraphs[-1]
            last_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            doc.add_paragraph()

    # ---- Serialise ---------------------------------------------------------
    buffer = io.BytesIO()
    doc.save(buffer)
    docx_bytes = buffer.getvalue()

    if isinstance(file_path_or_buffer, str):
        with open(file_path_or_buffer, "wb") as fh:
            fh.write(docx_bytes)
    elif isinstance(file_path_or_buffer, io.BytesIO):
        file_path_or_buffer.write(docx_bytes)
        file_path_or_buffer.seek(0)

    return docx_bytes


def generate_csv_summary(
    results: dict,
    file_path_or_buffer: Optional[Union[str, io.StringIO]] = None,
) -> str:
    """
    Generate a flat CSV summary of all numeric analysis results.

    Parameters
    ----------
    results : dict
        Same structure as accepted by generate_docx_report.
    file_path_or_buffer : str or StringIO, optional
        If a file path string is given the CSV is written there.
        If a StringIO is given it is written to that buffer.
        In both cases the CSV string is also returned.

    Returns
    -------
    str
        Complete CSV content as a string.
    """
    rows: list[list] = []

    # Header
    rows.append(["method", "alpha", "activation_energy_kJ_mol",
                 "pre_exponential", "r_squared", "notes"])

    # Kissinger
    kissinger = results.get("kissinger")
    if kissinger is not None:
        rows.append([
            "kissinger",
            "",
            _format_float(kissinger.activation_energy, 4),
            _format_float(kissinger.pre_exponential, 6),
            _format_float(kissinger.r_squared, 6),
            "",
        ])

    # OFW
    ofw_list = results.get("ozawa_flynn_wall", []) or []
    for r in ofw_list:
        alpha = r.plot_data.get("alpha", "") if r.plot_data else ""
        rows.append([
            "ozawa_flynn_wall",
            _format_float(alpha, 4) if alpha != "" else "",
            _format_float(r.activation_energy, 4),
            "",
            _format_float(r.r_squared, 6),
            "",
        ])

    # Friedman
    friedman_list = results.get("friedman", []) or []
    for r in friedman_list:
        alpha = r.plot_data.get("alpha", "") if r.plot_data else ""
        rows.append([
            "friedman",
            _format_float(alpha, 4) if alpha != "" else "",
            _format_float(r.activation_energy, 4),
            _format_float(r.pre_exponential, 6),
            _format_float(r.r_squared, 6),
            "",
        ])

    # Peak deconvolution summary row
    peak_deconv = results.get("peak_deconvolution")
    if peak_deconv is not None:
        rows.append([
            "peak_deconvolution",
            "",
            "",
            "",
            _format_float(peak_deconv.get("r_squared"), 6),
            "see params dict for individual peak values",
        ])
        # One row per fitted parameter
        for param_name, param_value in sorted(
            (peak_deconv.get("params") or {}).items()
        ):
            rows.append([
                "peak_deconvolution_param",
                "",
                "",
                "",
                "",
                f"{param_name} = {_format_float(param_value, 6)}",
            ])

    # Serialise
    str_buffer = io.StringIO()
    writer = csv.writer(str_buffer)
    writer.writerows(rows)
    csv_str = str_buffer.getvalue()

    if isinstance(file_path_or_buffer, str):
        with open(file_path_or_buffer, "w", newline="", encoding="utf-8") as fh:
            fh.write(csv_str)
    elif isinstance(file_path_or_buffer, io.StringIO):
        file_path_or_buffer.write(csv_str)
        file_path_or_buffer.seek(0)

    return csv_str
