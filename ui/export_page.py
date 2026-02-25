"""Export & Report page - Download results in various formats."""

import streamlit as st
import pandas as pd
import io

from core.data_io import export_results_csv, export_data_xlsx
from core.report_generator import generate_docx_report, generate_csv_summary
from ui.components.plot_builder import fig_to_bytes


def render():
    st.title("Export & Report")

    datasets = st.session_state.get("datasets", {})
    results = st.session_state.get("results", {})

    if not datasets and not results:
        st.warning("No data or results available. Upload data and run analyses first.")
        return

    tab_data, tab_results, tab_report = st.tabs(
        ["Export Data", "Export Results", "Generate Report"]
    )

    # ===================== EXPORT DATA TAB =====================
    with tab_data:
        st.subheader("Export Raw/Processed Data")

        if not datasets:
            st.info("No datasets loaded.")
        else:
            selected_datasets = st.multiselect(
                "Select datasets to export",
                list(datasets.keys()),
                default=list(datasets.keys()),
                key="export_data_select",
            )

            if selected_datasets:
                export_format = st.selectbox(
                    "Export Format",
                    ["CSV", "Excel (XLSX)"],
                    key="export_data_format",
                )

                if st.button("Export Data", key="export_data_btn"):
                    try:
                        if export_format == "CSV":
                            for key in selected_datasets:
                                ds = datasets[key]
                                csv_buf = io.StringIO()
                                ds.data.to_csv(csv_buf, index=False)
                                csv_bytes = csv_buf.getvalue().encode("utf-8")
                                st.download_button(
                                    label=f"Download {key} (CSV)",
                                    data=csv_bytes,
                                    file_name=f"{key.rsplit('.', 1)[0]}_export.csv",
                                    mime="text/csv",
                                    key=f"dl_csv_{key}",
                                )
                        else:
                            buf = io.BytesIO()
                            ds_list = [datasets[k] for k in selected_datasets]
                            export_data_xlsx(ds_list, buf)
                            buf.seek(0)
                            st.download_button(
                                label="Download Excel File",
                                data=buf.getvalue(),
                                file_name="thermoanalyzer_data.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key="dl_xlsx",
                            )
                    except Exception as e:
                        st.error(f"Export failed: {e}")

    # ===================== EXPORT RESULTS TAB =====================
    with tab_results:
        st.subheader("Export Analysis Results")

        if not results:
            st.info("No analysis results available. Run analyses first.")
        else:
            st.write(f"**Available results:** {len(results)}")
            for key, val in results.items():
                atype = val.get("analysis_type", "Unknown")
                st.write(f"- **{key}**: {atype}")

            col1, col2 = st.columns(2)

            with col1:
                if st.button("Export as CSV", key="export_results_csv"):
                    try:
                        csv_str = generate_csv_summary(results)
                        st.download_button(
                            label="Download Results CSV",
                            data=csv_str.encode("utf-8"),
                            file_name="thermoanalyzer_results.csv",
                            mime="text/csv",
                            key="dl_results_csv",
                        )
                    except Exception as e:
                        st.error(f"CSV export failed: {e}")

            with col2:
                if st.button("Export as Excel", key="export_results_xlsx"):
                    try:
                        buf = io.BytesIO()
                        _results_to_xlsx(results, buf)
                        buf.seek(0)
                        st.download_button(
                            label="Download Results Excel",
                            data=buf.getvalue(),
                            file_name="thermoanalyzer_results.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dl_results_xlsx",
                        )
                    except Exception as e:
                        st.error(f"Excel export failed: {e}")

    # ===================== REPORT TAB =====================
    with tab_report:
        st.subheader("Generate DOCX Report")

        if not results:
            st.info("No results to include in report. Run analyses first.")
        else:
            st.markdown("Generate a formatted Word document with all analysis results.")

            report_title = st.text_input("Report Title", value="Thermal Analysis Report",
                                         key="report_title")
            n_figs = len(st.session_state.get("figures", {}))
            include_figures = st.checkbox(
                f"Include figures in report ({n_figs} available)",
                value=True,
                key="report_figures",
            )

            if st.button("Generate Report", key="generate_report"):
                try:
                    figures = None
                    if include_figures:
                        figures = _collect_figures()

                    docx_bytes = generate_docx_report(
                        results=results,
                        datasets=datasets,
                        figures=figures,
                    )

                    st.download_button(
                        label="Download DOCX Report",
                        data=docx_bytes,
                        file_name="thermoanalyzer_report.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key="dl_report",
                    )
                    st.success("Report generated!")
                except Exception as e:
                    st.error(f"Report generation failed: {e}")


def _results_to_xlsx(results, buf):
    """Write results dict to an Excel file."""
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for key, val in results.items():
            atype = val.get("analysis_type", "Unknown")
            sheet_name = f"{atype}_{key}"[:31]

            if "peaks" in val and val["peaks"]:
                rows = []
                for i, p in enumerate(val["peaks"]):
                    rows.append({
                        "Peak #": i + 1,
                        "Type": getattr(p, "peak_type", ""),
                        "Peak T (°C)": getattr(p, "peak_temperature", None),
                        "Onset T (°C)": getattr(p, "onset_temperature", None),
                        "Endset T (°C)": getattr(p, "endset_temperature", None),
                        "Area": getattr(p, "area", None),
                        "FWHM (°C)": getattr(p, "fwhm", None),
                    })
                df = pd.DataFrame(rows)
                df.to_excel(writer, sheet_name=sheet_name, index=False)

            elif "data" in val:
                df = pd.DataFrame(val["data"])
                df.to_excel(writer, sheet_name=sheet_name, index=False)

            else:
                flat = {k: v for k, v in val.items()
                        if not isinstance(v, (list, dict, np.ndarray))}
                df = pd.DataFrame([flat])
                df.to_excel(writer, sheet_name=sheet_name, index=False)


def _collect_figures():
    """Collect any figures stored in session state as PNG bytes."""
    return st.session_state.get("figures", {}) or None
