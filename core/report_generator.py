"""Report generation for normalized ThermoAnalyzer result records."""

from __future__ import annotations

import csv
import io
import datetime
from typing import Optional, Union

from core.result_serialization import flatten_result_records, partition_results_by_status, split_valid_results

try:
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "python-docx is required for DOCX report generation. Install it with: pip install python-docx"
    ) from exc


def _set_cell_bg(cell, hex_color: str) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tc_pr.append(shd)


def _add_heading(doc: Document, text: str, level: int = 1) -> None:
    doc.add_heading(text, level=level)


def _add_key_value_table(doc: Document, data: dict) -> None:
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


def _format_value(value):
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return str(value)


def _record_title(record: dict) -> str:
    dataset_key = record.get("dataset_key")
    if dataset_key:
        return f"{record['analysis_type']} - {dataset_key}"
    return record["analysis_type"]


def _record_headers(record: dict) -> list[str]:
    rows = record.get("rows") or []
    if not rows:
        return []
    first_row = rows[0]
    return list(first_row.keys())


def _add_cover_page(doc: Document, branding: dict | None, license_state: dict | None) -> None:
    branding = branding or {}
    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    title = branding.get("report_title") or "ThermoAnalyzer Professional Report"
    title_run = title_para.add_run(title)
    title_run.bold = True
    title_run.font.size = Pt(20)

    if branding.get("logo_bytes"):
        try:
            doc.add_picture(io.BytesIO(branding["logo_bytes"]), width=Inches(1.4))
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        except Exception:
            pass

    subtitle_para = doc.add_paragraph()
    subtitle_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle_bits = [branding.get("company_name"), branding.get("lab_name")]
    subtitle = " | ".join(bit for bit in subtitle_bits if bit)
    if subtitle:
        subtitle_para.add_run(subtitle)

    meta_para = doc.add_paragraph()
    meta_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    analyst = branding.get("analyst_name") or "Analyst not specified"
    meta_para.add_run(
        f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d  %H:%M')} | Analyst: {analyst}"
    )

    if license_state and license_state.get("status") in {"trial", "activated"}:
        license_para = doc.add_paragraph()
        license_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        sku = (license_state.get("license") or {}).get("sku", "Professional")
        license_para.add_run(f"License status: {license_state['status']} ({sku})")

    doc.add_page_break()


def _render_comparison_workspace(
    doc: Document,
    comparison_workspace: dict | None,
    datasets: dict,
) -> None:
    comparison_workspace = comparison_workspace or {}
    selected = comparison_workspace.get("selected_datasets") or []
    if not selected:
        return

    _add_heading(doc, "2. Compare Workspace", level=1)
    overview = {
        "Analysis Type": comparison_workspace.get("analysis_type", "N/A"),
        "Selected Runs": ", ".join(selected),
        "Saved Figure": comparison_workspace.get("figure_key") or "None",
        "Saved At": comparison_workspace.get("saved_at") or "Not saved",
    }
    _add_key_value_table(doc, overview)
    doc.add_paragraph()

    rows = []
    for dataset_key in selected:
        dataset = datasets.get(dataset_key)
        if dataset is None:
            continue
        rows.append(
            [
                dataset_key,
                dataset.metadata.get("sample_name") or "Unnamed",
                dataset.metadata.get("vendor", "Generic"),
                dataset.metadata.get("heating_rate") or "—",
                dataset.metadata.get("instrument") or "—",
            ]
        )
    if rows:
        _add_results_table(doc, ["Run", "Sample", "Vendor", "Heating Rate", "Instrument"], rows)
        doc.add_paragraph()

    if comparison_workspace.get("notes"):
        doc.add_paragraph("Comparison Notes", style="Heading 2")
        doc.add_paragraph(str(comparison_workspace["notes"]))


def generate_docx_report(
    results: dict,
    datasets: dict,
    figures: Optional[dict] = None,
    file_path_or_buffer: Optional[Union[str, io.BytesIO]] = None,
    branding: Optional[dict] = None,
    comparison_workspace: Optional[dict] = None,
    license_state: Optional[dict] = None,
) -> bytes:
    """Generate a DOCX report from normalized stable/experimental records."""
    valid_results, issues = split_valid_results(results)
    stable_results, experimental_results = partition_results_by_status(valid_results)

    doc = Document()
    _add_cover_page(doc, branding, license_state)

    _add_heading(doc, "1. Experimental Conditions", level=1)
    if not datasets:
        doc.add_paragraph("No dataset metadata available.")
    else:
        for ds_name, ds in datasets.items():
            meta = getattr(ds, "metadata", {}) or {}
            doc.add_paragraph(f"Dataset: {ds_name}", style="Heading 2")
            if meta:
                _add_key_value_table(doc, meta)
            else:
                doc.add_paragraph("No metadata available for this dataset.")
            doc.add_paragraph()

    _render_comparison_workspace(doc, comparison_workspace, datasets)

    _add_heading(doc, "3. Stable Analyses", level=1)
    if not stable_results:
        doc.add_paragraph("No stable analysis results available.")
    else:
        for record in stable_results:
            doc.add_paragraph(_record_title(record), style="Heading 2")
            if record.get("summary"):
                _add_key_value_table(
                    doc,
                    {key: _format_value(value) for key, value in record["summary"].items()},
                )
                doc.add_paragraph()
            headers = _record_headers(record)
            if headers:
                rows = [
                    [_format_value(row.get(header)) for header in headers]
                    for row in record["rows"]
                ]
                _add_results_table(doc, headers, rows)
                doc.add_paragraph()

    _add_heading(doc, "4. Experimental Analyses", level=1)
    if not experimental_results:
        doc.add_paragraph("No experimental analysis results available.")
    else:
        doc.add_paragraph(
            "These results are included for reference but are outside the Phase 1 stability guarantee."
        )
        for record in experimental_results:
            doc.add_paragraph(_record_title(record), style="Heading 2")
            if record.get("summary"):
                _add_key_value_table(
                    doc,
                    {key: _format_value(value) for key, value in record["summary"].items()},
                )
                doc.add_paragraph()
            headers = _record_headers(record)
            if headers:
                rows = [
                    [_format_value(row.get(header)) for header in headers]
                    for row in record["rows"]
                ]
                _add_results_table(doc, headers, rows)
                doc.add_paragraph()

    report_notes = (branding or {}).get("report_notes")
    if report_notes:
        _add_heading(doc, "5. Analyst Notes", level=1)
        doc.add_paragraph(str(report_notes))

    if issues:
        _add_heading(doc, "6. Skipped Records", level=1)
        for issue in issues:
            doc.add_paragraph(issue, style="List Bullet")

    if figures:
        _add_heading(doc, "7. Figures", level=1)
        for caption, png_bytes in figures.items():
            doc.add_paragraph(caption, style="Heading 2")
            try:
                img_stream = io.BytesIO(png_bytes)
                doc.add_picture(img_stream, width=Inches(5.5))
                doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            except Exception:
                doc.add_paragraph("Figure could not be embedded and was skipped.")
            doc.add_paragraph()

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
    """Generate a flat CSV summary from normalized result records."""
    valid_results, _ = split_valid_results(results)
    flat_rows = flatten_result_records(valid_results)

    fieldnames = [
        "result_id",
        "status",
        "analysis_type",
        "dataset_key",
        "section",
        "row_index",
        "field",
        "value",
    ]

    str_buffer = io.StringIO()
    writer = csv.DictWriter(str_buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in flat_rows:
        writer.writerow(row)
    csv_str = str_buffer.getvalue()

    if isinstance(file_path_or_buffer, str):
        with open(file_path_or_buffer, "w", newline="", encoding="utf-8") as fh:
            fh.write(csv_str)
    elif isinstance(file_path_or_buffer, io.StringIO):
        file_path_or_buffer.write(csv_str)
        file_path_or_buffer.seek(0)

    return csv_str


def pdf_export_available() -> bool:
    """Return whether reportlab is installed for PDF export."""
    try:  # pragma: no cover - availability depends on environment
        import reportlab  # noqa: F401
    except ImportError:
        return False
    return True


def generate_pdf_report(
    results: dict,
    datasets: dict,
    figures: Optional[dict] = None,
    file_path_or_buffer: Optional[Union[str, io.BytesIO]] = None,
    branding: Optional[dict] = None,
    comparison_workspace: Optional[dict] = None,
    license_state: Optional[dict] = None,
) -> bytes:
    """Generate a simple branded PDF report when reportlab is available."""
    try:  # pragma: no cover - optional dependency
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError("PDF export requires reportlab. Install it with: pip install reportlab") from exc

    valid_results, issues = split_valid_results(results)
    stable_results, experimental_results = partition_results_by_status(valid_results)
    styles = getSampleStyleSheet()
    story = []

    title = (branding or {}).get("report_title") or "ThermoAnalyzer Professional Report"
    story.append(Paragraph(title, styles["Title"]))
    story.append(Paragraph(datetime.datetime.now().strftime("Generated: %Y-%m-%d %H:%M"), styles["Normal"]))
    if branding:
        header_bits = [branding.get("company_name"), branding.get("lab_name"), branding.get("analyst_name")]
        header = " | ".join(bit for bit in header_bits if bit)
        if header:
            story.append(Paragraph(header, styles["Normal"]))
    if license_state and license_state.get("status"):
        story.append(Paragraph(f"License: {license_state['status']}", styles["Normal"]))
    story.append(Spacer(1, 0.2 * inch))

    if branding and branding.get("logo_bytes"):
        try:
            story.append(Image(io.BytesIO(branding["logo_bytes"]), width=1.4 * inch, height=0.8 * inch))
            story.append(Spacer(1, 0.2 * inch))
        except Exception:
            pass

    story.append(Paragraph("Experimental Conditions", styles["Heading1"]))
    for ds_name, ds in datasets.items():
        story.append(Paragraph(ds_name, styles["Heading2"]))
        meta_rows = [["Parameter", "Value"]]
        for key, value in (getattr(ds, "metadata", {}) or {}).items():
            meta_rows.append([str(key), str(value)])
        table = Table(meta_rows, hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EEF3F8")]),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 0.15 * inch))

    if comparison_workspace and comparison_workspace.get("selected_datasets"):
        story.append(Paragraph("Compare Workspace", styles["Heading1"]))
        story.append(Paragraph(", ".join(comparison_workspace["selected_datasets"]), styles["Normal"]))
        if comparison_workspace.get("notes"):
            story.append(Paragraph(str(comparison_workspace["notes"]), styles["Normal"]))
        story.append(Spacer(1, 0.15 * inch))

    def _append_record_block(heading, record_list):
        story.append(Paragraph(heading, styles["Heading1"]))
        if not record_list:
            story.append(Paragraph("No results available.", styles["Normal"]))
            return
        for record in record_list:
            story.append(Paragraph(_record_title(record), styles["Heading2"]))
            summary_rows = [["Parameter", "Value"]]
            for key, value in record.get("summary", {}).items():
                summary_rows.append([str(key), _format_value(value)])
            if len(summary_rows) > 1:
                summary_table = Table(summary_rows, hAlign="LEFT")
                summary_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                        ]
                    )
                )
                story.append(summary_table)
            story.append(Spacer(1, 0.1 * inch))

    _append_record_block("Stable Analyses", stable_results)
    _append_record_block("Experimental Analyses", experimental_results)

    if (branding or {}).get("report_notes"):
        story.append(Paragraph("Analyst Notes", styles["Heading1"]))
        story.append(Paragraph(str((branding or {})["report_notes"]), styles["Normal"]))

    if issues:
        story.append(Paragraph("Skipped Records", styles["Heading1"]))
        for issue in issues:
            story.append(Paragraph(issue, styles["Normal"]))

    if figures:
        story.append(Paragraph("Figures", styles["Heading1"]))
        for caption, png_bytes in figures.items():
            story.append(Paragraph(caption, styles["Heading2"]))
            try:
                story.append(Image(io.BytesIO(png_bytes), width=5.5 * inch, height=3.4 * inch))
            except Exception:
                continue
            story.append(Spacer(1, 0.12 * inch))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    doc.build(story)
    pdf_bytes = buffer.getvalue()

    if isinstance(file_path_or_buffer, str):
        with open(file_path_or_buffer, "wb") as fh:
            fh.write(pdf_bytes)
    elif isinstance(file_path_or_buffer, io.BytesIO):
        file_path_or_buffer.write(pdf_bytes)
        file_path_or_buffer.seek(0)

    return pdf_bytes
