"""Report center for branded exports and customer-facing outputs."""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from core.batch_runner import filter_batch_summary_rows, normalize_batch_summary_rows, summarize_batch_outcomes
from core.data_io import export_data_xlsx
from core.report_generator import (
    generate_csv_summary,
    generate_docx_report,
    generate_pdf_report,
    pdf_export_available,
)
from core.result_serialization import collect_figure_keys, split_valid_results
from ui.components.chrome import render_page_header
from utils.diagnostics import record_exception, serialize_support_snapshot
from utils.i18n import t
from utils.license_manager import APP_VERSION, license_allows_write


def render():
    render_page_header(t("report.title"), t("report.caption"), badge=t("report.hero_badge"))
    lang = st.session_state.get("ui_language", "tr")

    datasets = st.session_state.get("datasets", {})
    results = st.session_state.get("results", {})
    branding = st.session_state.get("branding", {}) or {}
    comparison_workspace = st.session_state.get("comparison_workspace", {}) or {}
    license_state = st.session_state.get("license_state") or {}

    valid_results, issues = split_valid_results(results)
    stable_count = sum(1 for record in valid_results.values() if record.get("status") == "stable")
    experimental_count = sum(1 for record in valid_results.values() if record.get("status") == "experimental")
    write_enabled = license_allows_write(license_state)

    if not datasets and not results:
        st.warning("Henüz veri veya sonuç yok. Önce veri yükleyip en az bir analiz sonucu kaydet." if lang == "tr" else "No data or results available yet. Import runs and save at least one analysis result.")
        return

    if not write_enabled:
        st.warning(
            "Bu build salt okunur modda. Geçerli lisans veya deneme kurulana kadar export/rapor/proje kaydı kapalı."
            if lang == "tr"
            else "This build is currently read-only. Import and review data are still available, but export/report/project-save actions are disabled until a valid license or trial is installed."
        )

    preview_tab, data_tab, results_tab, report_tab = st.tabs(
        [
            "Rapor Önizleme" if lang == "tr" else "Report Preview",
            "Veri Dışa Aktar" if lang == "tr" else "Export Data",
            "Sonuç Dışa Aktar" if lang == "tr" else "Export Results",
            "Rapor Üret" if lang == "tr" else "Generate Report",
        ]
    )

    with preview_tab:
        _render_preview(datasets, valid_results, issues, branding, comparison_workspace, license_state, lang)

    with data_tab:
        _render_data_export(datasets, write_enabled, lang)

    with results_tab:
        _render_result_export(valid_results, issues, write_enabled, lang)

    with report_tab:
        _render_report_export(
            datasets=datasets,
            valid_results=valid_results,
            issues=issues,
            branding=branding,
            comparison_workspace=comparison_workspace,
            license_state=license_state,
            write_enabled=write_enabled,
            lang=lang,
        )


def _render_preview(datasets, valid_results, issues, branding, comparison_workspace, license_state, lang):
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Veri Seti" if lang == "tr" else "Datasets", str(len(datasets)))
    m2.metric("Stable Analiz" if lang == "tr" else "Stable Analyses", str(sum(1 for record in valid_results.values() if record.get("status") == "stable")))
    m3.metric("Önizleme Analizi" if lang == "tr" else "Preview Analyses", str(sum(1 for record in valid_results.values() if record.get("status") == "experimental")))
    m4.metric("Rapor Görseli" if lang == "tr" else "Report Figures", str(len(_collect_figures(valid_results, comparison_workspace) or {})))

    company = branding.get("company_name") or (license_state.get("license") or {}).get("company_name") or "Not set"
    lab_name = branding.get("lab_name") or "Not set"
    analyst = branding.get("analyst_name") or "Not set"

    st.subheader("Marka" if lang == "tr" else "Branding")
    st.write(f"**{'Rapor Başlığı' if lang == 'tr' else 'Report Title'}:** {branding.get('report_title') or 'ThermoAnalyzer Professional Report'}")
    st.write(f"**{'Şirket' if lang == 'tr' else 'Company'}:** {company}")
    st.write(f"**{'Laboratuvar' if lang == 'tr' else 'Laboratory'}:** {lab_name}")
    st.write(f"**{'Analist' if lang == 'tr' else 'Analyst'}:** {analyst}")
    if branding.get("logo_bytes"):
        st.image(branding["logo_bytes"], width=220)

    st.subheader("Rapor Paketi" if lang == "tr" else "Report Package")
    overview_rows = [
        {
            "ID": record["id"],
            ("Tip" if lang == "tr" else "Type"): record["analysis_type"],
            ("Durum" if lang == "tr" else "Status"): record["status"],
            ("Veri Seti" if lang == "tr" else "Dataset"): record.get("dataset_key") or "—",
            ("Satır" if lang == "tr" else "Rows"): len(record.get("rows", [])),
        }
        for record in valid_results.values()
    ]
    if overview_rows:
        st.dataframe(pd.DataFrame(overview_rows), width="stretch", hide_index=True)
    else:
        st.info("Henüz normalize sonuç kaydı yok." if lang == "tr" else "No normalized result records are saved yet.")

    if comparison_workspace.get("selected_datasets"):
        st.subheader("Karşılaştırma Alanı" if lang == "tr" else "Comparison Workspace")
        st.write(f"**{'Analiz Tipi' if lang == 'tr' else 'Analysis Type'}:** {comparison_workspace.get('analysis_type', 'N/A')}")
        st.write(f"**{'Seçili Koşular' if lang == 'tr' else 'Selected Runs'}:** {', '.join(comparison_workspace.get('selected_datasets', []))}")
        if comparison_workspace.get("notes"):
            st.write(f"**{'Karşılaştırma Notları' if lang == 'tr' else 'Comparison Notes'}**")
            st.write(comparison_workspace["notes"])
        _render_batch_preview(comparison_workspace, lang)

    if branding.get("report_notes"):
        st.subheader("Analist Notları" if lang == "tr" else "Analyst Notes")
        st.write(branding["report_notes"])

    if issues:
        st.warning("Bazı kayıtlar eksik ve atlanacak." if lang == "tr" else "Some saved records are incomplete and will be skipped.")
        for issue in issues:
            st.caption(f"- {issue}")

    with st.expander("Destek Tanı Paketi" if lang == "tr" else "Support Diagnostics", expanded=False):
        st.caption(
            "Bu JSON snapshot hata bildirimi ve destek talepleri için son olayları, log yolunu ve çalışma alanı özetini içerir."
            if lang == "tr"
            else "This JSON snapshot includes recent events, the diagnostics log path, and a workspace summary for bug reports and support requests."
        )
        if st.button("Destek Snapshot Hazırla" if lang == "tr" else "Prepare Support Snapshot", key="prepare_support_snapshot"):
            try:
                st.session_state["prepared_support_snapshot"] = serialize_support_snapshot(
                    st.session_state,
                    app_version=APP_VERSION,
                    log_file=st.session_state.get("diagnostics_log_path"),
                )
            except Exception as exc:
                error_id = record_exception(
                    st.session_state,
                    area="export",
                    action="support_snapshot",
                    message="Support snapshot generation failed.",
                    exception=exc,
                )
                st.error(
                    "Destek snapshot oluşturulamadı: {error}".format(error=f"{exc} (Error ID: {error_id})")
                    if lang == "tr"
                    else f"Support snapshot generation failed: {exc} (Error ID: {error_id})"
                )
        if st.session_state.get("prepared_support_snapshot"):
            st.download_button(
                label="Destek Snapshot İndir" if lang == "tr" else "Download Support Snapshot",
                data=st.session_state["prepared_support_snapshot"],
                file_name="thermoanalyzer_support_snapshot.json",
                mime="application/json",
                key="dl_support_snapshot",
                on_click="ignore",
            )


def _render_data_export(datasets, write_enabled, lang):
    st.subheader("Ham / İçe Aktarılan Veriyi Dışa Aktar" if lang == "tr" else "Export Raw / Imported Data")
    if not datasets:
        st.info("Yüklü veri seti yok." if lang == "tr" else "No datasets loaded.")
        return

    selected_datasets = st.multiselect(
        "Dışa aktarılacak veri setleri" if lang == "tr" else "Select datasets to export",
        list(datasets.keys()),
        default=list(datasets.keys()),
        key="export_data_select",
    )
    export_format = st.selectbox(
        "Dışa Aktarım Formatı" if lang == "tr" else "Export Format",
        ["CSV", "Excel (XLSX)"],
        key="export_data_format",
    )

    if not selected_datasets:
        st.info("En az bir veri seti seç." if lang == "tr" else "Select at least one dataset.")
        return

    if export_format == "CSV":
        if st.button(
            "CSV Dosyalarını Hazırla" if lang == "tr" else "Prepare Data CSV Files",
            key="prepare_data_csv",
            disabled=not write_enabled,
        ):
            prepared = []
            for key in selected_datasets:
                dataset = datasets[key]
                prepared.append(
                    {
                        "label": f"{key} CSV indir" if lang == "tr" else f"Download {key} (CSV)",
                        "data": dataset.data.to_csv(index=False).encode("utf-8"),
                        "file_name": f"{key.rsplit('.', 1)[0]}_export.csv",
                        "mime": "text/csv",
                        "key": f"dl_csv_{key}",
                    }
                )
            st.session_state["prepared_data_exports"] = prepared
    else:
        if st.button(
            "Excel Çalışma Kitabını Hazırla" if lang == "tr" else "Prepare Data Workbook",
            key="prepare_data_xlsx",
            disabled=not write_enabled,
        ):
            try:
                buffer = io.BytesIO()
                export_data_xlsx([datasets[k] for k in selected_datasets], buffer)
                buffer.seek(0)
                st.session_state["prepared_data_exports"] = [
                    {
                        "label": "Veri çalışma kitabını indir" if lang == "tr" else "Download Data Workbook",
                        "data": buffer.getvalue(),
                        "file_name": "thermoanalyzer_data.xlsx",
                        "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        "key": "dl_data_xlsx",
                    }
                ]
            except Exception as exc:
                error_id = record_exception(
                    st.session_state,
                    area="export",
                    action="data_workbook",
                    message="Preparing data workbook failed.",
                    context={"dataset_count": len(selected_datasets)},
                    exception=exc,
                )
                st.error(
                    "Excel çalışma kitabı hazırlanamadı: {error}".format(error=f"{exc} (Error ID: {error_id})")
                    if lang == "tr"
                    else f"Preparing the data workbook failed: {exc} (Error ID: {error_id})"
                )

    for item in st.session_state.get("prepared_data_exports", []):
        st.download_button(
            label=item["label"],
            data=item["data"],
            file_name=item["file_name"],
            mime=item["mime"],
            key=item["key"],
            on_click="ignore",
        )


def _render_result_export(valid_results, issues, write_enabled, lang):
    st.subheader("Normalize Sonuç Kayıtlarını Dışa Aktar" if lang == "tr" else "Export Normalized Result Records")

    if issues:
        st.warning("Bazı sonuç kayıtları eksik veya geçersiz olduğu için atlandı." if lang == "tr" else "Some result records were skipped because they are incomplete or invalid.")
        for issue in issues:
            st.caption(f"- {issue}")

    if not valid_results:
        st.info("Geçerli analiz sonucu yok. Önce analiz çalıştırıp sonuç kaydet." if lang == "tr" else "No valid analysis results available. Run analyses and save their results first.")
        return

    overview_rows = [
        {
            "ID": record["id"],
            ("Tip" if lang == "tr" else "Type"): record["analysis_type"],
            ("Durum" if lang == "tr" else "Status"): record["status"],
            ("Veri Seti" if lang == "tr" else "Dataset"): record.get("dataset_key") or "—",
            ("Satır" if lang == "tr" else "Rows"): len(record.get("rows", [])),
        }
        for record in valid_results.values()
    ]
    st.dataframe(pd.DataFrame(overview_rows), width="stretch", hide_index=True)

    if st.button(
        "Sonuç Dosyalarını Hazırla" if lang == "tr" else "Prepare Result Exports",
        key="prepare_result_exports",
        disabled=not write_enabled,
    ):
        try:
            csv_text = generate_csv_summary(valid_results)
            xlsx_buffer = io.BytesIO()
            _results_to_xlsx(valid_results, issues, xlsx_buffer)
            xlsx_buffer.seek(0)
            st.session_state["prepared_results_csv"] = csv_text.encode("utf-8")
            st.session_state["prepared_results_xlsx"] = xlsx_buffer.getvalue()
        except Exception as exc:
            error_id = record_exception(
                st.session_state,
                area="export",
                action="result_exports",
                message="Preparing normalized result exports failed.",
                context={"result_count": len(valid_results)},
                exception=exc,
            )
            st.error(
                "Sonuç export paketi hazırlanamadı: {error}".format(error=f"{exc} (Error ID: {error_id})")
                if lang == "tr"
                else f"Preparing result exports failed: {exc} (Error ID: {error_id})"
            )

    c1, c2 = st.columns(2)
    if st.session_state.get("prepared_results_csv"):
        c1.download_button(
            label="Sonuç CSV indir" if lang == "tr" else "Download Results CSV",
            data=st.session_state["prepared_results_csv"],
            file_name="thermoanalyzer_results.csv",
            mime="text/csv",
            key="dl_results_csv",
            on_click="ignore",
        )
    if st.session_state.get("prepared_results_xlsx"):
        c2.download_button(
            label="Sonuç Excel indir" if lang == "tr" else "Download Results Excel",
            data=st.session_state["prepared_results_xlsx"],
            file_name="thermoanalyzer_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_results_xlsx",
            on_click="ignore",
        )


def _render_report_export(
    *,
    datasets,
    valid_results,
    issues,
    branding,
    comparison_workspace,
    license_state,
    write_enabled,
    lang,
):
    st.subheader("Markalı Rapor Üret" if lang == "tr" else "Generate Branded Reports")

    if not valid_results:
        st.info("Rapora girecek geçerli sonuç yok. Önce en az bir analiz sonucu kaydet." if lang == "tr" else "No valid results to include in report. Save at least one analysis result first.")
        return

    if issues:
        st.caption("Geçersiz kayıtlar rapordan atlanacak." if lang == "tr" else "Invalid saved records will be skipped from the report.")

    figures = _collect_figures(valid_results, comparison_workspace)
    include_figures = st.checkbox(
        (f"Görselleri dahil et ({len(figures or {})} adet)" if lang == "tr" else f"Include figures ({len(figures or {})} available)"),
        value=True,
        key="report_figures",
    )

    if st.button(
        "Rapor Dosyalarını Hazırla" if lang == "tr" else "Prepare Report Files",
        key="prepare_report_files",
        disabled=not write_enabled,
    ):
        try:
            st.session_state["prepared_report_docx"] = generate_docx_report(
                results=valid_results,
                datasets=datasets,
                figures=figures if include_figures else None,
                branding=branding,
                comparison_workspace=comparison_workspace,
                license_state=license_state,
            )
            if pdf_export_available():
                st.session_state["prepared_report_pdf"] = generate_pdf_report(
                    results=valid_results,
                    datasets=datasets,
                    figures=figures if include_figures else None,
                    branding=branding,
                    comparison_workspace=comparison_workspace,
                    license_state=license_state,
                )
            else:
                st.session_state["prepared_report_pdf"] = None
        except Exception as exc:
            error_id = record_exception(
                st.session_state,
                area="report",
                action="report_generation",
                message="Preparing branded report files failed.",
                context={"result_count": len(valid_results), "figure_count": len(figures or {})},
                exception=exc,
            )
            st.error(
                "Rapor dosyaları hazırlanamadı: {error}".format(error=f"{exc} (Error ID: {error_id})")
                if lang == "tr"
                else f"Preparing report files failed: {exc} (Error ID: {error_id})"
            )

    if st.session_state.get("prepared_report_docx"):
        st.download_button(
            label="DOCX raporu indir" if lang == "tr" else "Download DOCX Report",
            data=st.session_state["prepared_report_docx"],
            file_name="thermoanalyzer_report.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            key="dl_report_docx",
            on_click="ignore",
        )

    if pdf_export_available():
        if st.session_state.get("prepared_report_pdf"):
            st.download_button(
                label="PDF raporu indir" if lang == "tr" else "Download PDF Report",
                data=st.session_state["prepared_report_pdf"],
                file_name="thermoanalyzer_report.pdf",
                mime="application/pdf",
                key="dl_report_pdf",
                on_click="ignore",
            )
    else:
        st.caption("PDF export için `reportlab` gerekir." if lang == "tr" else "PDF export requires `reportlab`. Install it to enable PDF output.")


def _results_to_xlsx(results, issues, buf):
    """Write normalized results dict to an Excel file."""
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        summary_rows = []
        for record in results.values():
            row = {
                "result_id": record["id"],
                "status": record["status"],
                "analysis_type": record["analysis_type"],
                "dataset_key": record.get("dataset_key"),
                "workflow_template": (record.get("processing") or {}).get("workflow_template"),
                "validation_status": (record.get("validation") or {}).get("status"),
                "saved_at_utc": (record.get("provenance") or {}).get("saved_at_utc"),
            }
            row.update(record.get("summary", {}))
            summary_rows.append(row)

        summary_df = pd.DataFrame(summary_rows) if summary_rows else pd.DataFrame([{"message": "No valid results"}])
        summary_df.to_excel(writer, sheet_name="Results", index=False)

        for record in results.values():
            if not record.get("rows"):
                continue
            sheet_name = f"{record['analysis_type']}_{record['id']}"[:31]
            pd.DataFrame(record["rows"]).to_excel(writer, sheet_name=sheet_name, index=False)

        if issues:
            pd.DataFrame({"issue": issues}).to_excel(writer, sheet_name="Skipped", index=False)


def _collect_figures(results, comparison_workspace):
    """Collect figures referenced by normalized results plus the compare workspace."""
    figure_keys = collect_figure_keys(results)
    compare_figure = (comparison_workspace or {}).get("figure_key")
    if compare_figure and compare_figure not in figure_keys:
        figure_keys.append(compare_figure)
    if not figure_keys:
        return None

    stored_figures = st.session_state.get("figures", {}) or {}
    figures = {key: stored_figures[key] for key in figure_keys if key in stored_figures}
    return figures or None


def _render_batch_preview(comparison_workspace, lang):
    batch_summary = normalize_batch_summary_rows(comparison_workspace.get("batch_summary") or [])
    if not batch_summary:
        return

    st.subheader("Batch Özeti" if lang == "tr" else "Batch Summary")
    totals = summarize_batch_outcomes(batch_summary)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Toplam" if lang == "tr" else "Total", str(totals["total"]))
    col2.metric("Kaydedilen" if lang == "tr" else "Saved", str(totals["saved"]))
    col3.metric("Bloklanan" if lang == "tr" else "Blocked", str(totals["blocked"]))
    col4.metric("Başarısız" if lang == "tr" else "Failed", str(totals["failed"]))

    outcome_filter = st.selectbox(
        "Batch filtresi" if lang == "tr" else "Batch filter",
        ["all", "saved", "blocked", "failed"],
        format_func=lambda value: {
            "all": "Tümü" if lang == "tr" else "All",
            "saved": "Kaydedilen" if lang == "tr" else "Saved",
            "blocked": "Bloklanan" if lang == "tr" else "Blocked",
            "failed": "Başarısız" if lang == "tr" else "Failed",
        }[value],
        index=0,
        key="export_batch_filter",
    )
    filtered_rows = filter_batch_summary_rows(batch_summary, execution_status=outcome_filter)
    if filtered_rows:
        st.dataframe(_batch_summary_preview_frame(filtered_rows, lang), width="stretch", hide_index=True)


def _batch_summary_preview_frame(summary_rows, lang):
    df = pd.DataFrame(summary_rows)
    preferred = [
        "dataset_key",
        "sample_name",
        "workflow_template",
        "execution_status",
        "validation_status",
        "result_id",
        "error_id",
        "failure_reason",
    ]
    available = [column for column in preferred if column in df.columns]
    df = df[available]
    return df.rename(
        columns={
            "dataset_key": "Koşu" if lang == "tr" else "Run",
            "sample_name": "Numune" if lang == "tr" else "Sample",
            "workflow_template": "Şablon" if lang == "tr" else "Template",
            "execution_status": "Çalıştırma" if lang == "tr" else "Execution",
            "validation_status": "Doğrulama" if lang == "tr" else "Validation",
            "result_id": "Sonuç ID" if lang == "tr" else "Result ID",
            "error_id": "Hata ID" if lang == "tr" else "Error ID",
            "failure_reason": "Neden" if lang == "tr" else "Reason",
        }
    )

