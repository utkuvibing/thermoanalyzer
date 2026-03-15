"""Commercial comparison workspace for stable modality runs."""

from __future__ import annotations

from datetime import datetime
import uuid

import pandas as pd
import streamlit as st

from core.batch_runner import execute_batch_template, filter_batch_summary_rows, normalize_batch_summary_rows, summarize_batch_outcomes
from core.modalities import analysis_state_key, get_modality, stable_analysis_types
from core.processing_schema import get_workflow_templates
from core.result_serialization import split_valid_results
from ui.components.chrome import render_page_header
from ui.components.history_tracker import _log_event
from ui.components.plot_builder import PLOTLY_CONFIG, create_overlay_plot, fig_to_bytes
from utils.diagnostics import make_error_id, record_diagnostic_event, record_exception
from utils.i18n import t, tx
from utils.license_manager import APP_VERSION


def render():
    render_page_header(t("compare.title"), t("compare.caption"), badge=t("compare.hero_badge"))
    lang = st.session_state.get("ui_language", "tr")

    datasets = st.session_state.get("datasets", {})
    stable_types = list(stable_analysis_types())
    if not stable_types:
        st.warning("Kararlı analiz tipi bulunamadı." if lang == "tr" else "No stable analysis types are currently available.")
        return

    normalized_types = {token.upper() for token in stable_types}
    compareable = {
        key: ds
        for key, ds in datasets.items()
        if str(getattr(ds, "data_type", "UNKNOWN") or "UNKNOWN").upper() in normalized_types | {"UNKNOWN"}
    }
    if not compareable:
        st.warning(
            "Henüz kararlı karşılaştırmaya uygun veri yok. Önce veri yükle." if lang == "tr"
            else "No stable compare-ready datasets are available yet. Import runs first."
        )
        return

    valid_results, _ = split_valid_results(st.session_state.get("results", {}))
    workspace = st.session_state.setdefault("comparison_workspace", {})
    available_types = []
    for token in stable_types:
        if any(_dataset_type_matches_analysis_type(ds, token) for ds in compareable.values()):
            available_types.append(token)

    if not available_types:
        st.warning(
            "Karşılaştırma için uygun kararlı analiz tipi bulunamadı." if lang == "tr"
            else "No stable analysis type is currently eligible for compare."
        )
        return

    default_type = workspace.get("analysis_type") if workspace.get("analysis_type") in available_types else available_types[0]
    analysis_type = st.segmented_control(
        "Koşu tipi" if lang == "tr" else "Run type",
        available_types,
        default=default_type,
        selection_mode="single",
        key="compare_analysis_type",
    )
    workspace["analysis_type"] = analysis_type

    eligible = {
        key: ds
        for key, ds in compareable.items()
        if _dataset_type_matches_analysis_type(ds, analysis_type)
    }
    options = list(eligible.keys())
    if not options:
        st.info(
            tx(
                "{analysis_type} için karşılaştırılabilir veri bulunamadı.",
                "No compareable datasets were found for {analysis_type}.",
                analysis_type=analysis_type,
            )
        )
        return

    previous_selection = [key for key in workspace.get("selected_datasets", []) if key in options]
    if len(previous_selection) < 2:
        previous_selection = options[: min(3, len(options))]

    selected = st.multiselect(
        "Karşılaştırılacak koşuları seç" if lang == "tr" else "Select runs to compare",
        options,
        default=previous_selection,
        key="compare_selected_runs",
        help="En temiz rapor çıktısı için aynı tipte 2-5 koşu seç." if lang == "tr" else "Use 2-5 runs of the same analysis type for the cleanest report output.",
    )
    workspace["selected_datasets"] = selected

    signal_mode = st.selectbox(
        "Sinyal kaynağı" if lang == "tr" else "Signal source",
        ["best", "raw"],
        format_func=lambda value: ("En İyi Mevcut" if value == "best" else "Sadece Ham") if lang == "tr" else ("Best Available" if value == "best" else "Raw Only"),
        index=0,
        key="compare_signal_mode",
        help="En İyi Mevcut seçeneği varsa corrected/smoothed state'i kullanır." if lang == "tr" else "Best Available uses corrected/smoothed state when present so the overlay matches your current analysis workspace.",
    )

    if len(selected) < 2:
        st.info("Overlay alanı kurmak için en az iki koşu seç." if lang == "tr" else "Select at least two runs to build an overlay workspace.")
        return

    series = []
    summary_rows = []
    for dataset_key in selected:
        dataset = eligible[dataset_key]
        signal, signal_source = _resolve_signal(dataset_key, dataset, analysis_type, signal_mode)
        label = _build_run_label(dataset_key, dataset)
        series.append(
            {
                "x": dataset.data["temperature"].values,
                "y": signal,
                "name": label,
            }
        )
        summary_rows.append(
            {
                ("Koşu" if lang == "tr" else "Run"): dataset_key,
                ("Numune" if lang == "tr" else "Sample"): dataset.metadata.get("sample_name") or ("Adsız" if lang == "tr" else "Unnamed"),
                ("Vendor" if lang == "tr" else "Vendor"): dataset.metadata.get("vendor", "Generic"),
                ("Isıtma Hızı" if lang == "tr" else "Heating Rate"): dataset.metadata.get("heating_rate") or "—",
                ("Cihaz" if lang == "tr" else "Instrument"): dataset.metadata.get("instrument") or "—",
                ("Sinyal Kaynağı" if lang == "tr" else "Signal Source"): signal_source,
                ("Kayıtlı Sonuç" if lang == "tr" else "Saved Result"): "Evet" if lang == "tr" and _has_saved_result(valid_results, analysis_type, dataset_key) else ("Yes" if _has_saved_result(valid_results, analysis_type, dataset_key) else ("Hayır" if lang == "tr" else "No")),
            }
        )

    y_unit = eligible[selected[0]].units.get("signal", "a.u.")
    x_label = _x_axis_label(analysis_type, lang)
    y_quantity = _y_quantity_label(analysis_type, lang)
    y_label = f"{y_quantity} ({y_unit})"
    fig = create_overlay_plot(
        series,
        title=tx("{analysis_type} Karşılaştırma Alanı", "{analysis_type} Compare Workspace", analysis_type=analysis_type),
        x_label=x_label,
        y_label=y_label,
    )
    st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)

    m1, m2, m3 = st.columns(3)
    m1.metric("Karşılaştırılan Koşu" if lang == "tr" else "Runs Compared", str(len(selected)))
    m2.metric("Vendor Sayısı" if lang == "tr" else "Vendors Present", str(len({eligible[key].metadata.get('vendor', 'Generic') for key in selected})))
    m3.metric("Kayıtlı Kararlı Sonuç" if lang == "tr" else "Saved Stable Results", str(sum(1 for key in selected if _has_saved_result(valid_results, analysis_type, key))))

    st.subheader("Alan Özeti" if lang == "tr" else "Workspace Summary")
    st.dataframe(pd.DataFrame(summary_rows), width="stretch", hide_index=True)

    notes = st.text_area(
        "Analist notları" if lang == "tr" else "Analyst notes",
        value=workspace.get("notes", ""),
        key="compare_notes",
        height=140,
        placeholder="Yorum, pass/fail notu veya müşteri bağlamı ekle." if lang == "tr" else "Add interpretation notes, pass/fail comments, or customer-facing context for this overlay.",
    )
    workspace["notes"] = notes

    save_col, info_col = st.columns([1, 2])
    with save_col:
        if st.button("Karşılaştırma Görselini Kaydet" if lang == "tr" else "Save Comparison Snapshot", key="compare_save_snapshot"):
            figure_key = f"Comparison Workspace - {analysis_type}"
            st.session_state.setdefault("figures", {})[figure_key] = fig_to_bytes(fig)
            workspace["figure_key"] = figure_key
            workspace["saved_at"] = datetime.now().isoformat(timespec="seconds")
            _log_event(
                tx("Karşılaştırma Kaydedildi", "Comparison Saved"),
                tx("{analysis_type} üst bindirme, {count} koşu", "{analysis_type} overlay with {count} run(s)", analysis_type=analysis_type, count=len(selected)),
                t("compare.title"),
            )
            st.success("Karşılaştırma görseli rapor için kaydedildi." if lang == "tr" else "Comparison figure saved for report generation.")
    with info_col:
        if workspace.get("figure_key"):
            st.caption(
                (
                    f"Kaydedilen görsel: `{workspace['figure_key']}`"
                    if lang == "tr"
                    else f"Saved figure: `{workspace['figure_key']}`"
                )
                + (
                    f" / {workspace['saved_at']}"
                    if workspace.get("saved_at")
                    else ""
                )
            )

    _render_batch_runner(workspace, eligible, selected, analysis_type, lang)
    refreshed_results, _ = split_valid_results(st.session_state.get("results", {}))
    _render_saved_result_preview(refreshed_results, analysis_type, selected, lang)


def _dataset_type_matches_analysis_type(dataset, analysis_type):
    token = str(analysis_type or "").upper()
    modality = get_modality(token)
    if modality is None:
        return False
    dtype = str(getattr(dataset, "data_type", "UNKNOWN") or "UNKNOWN")
    return modality.adapter.is_dataset_eligible(dtype)


def _x_axis_label(analysis_type, lang):
    if analysis_type == "FTIR":
        return "Dalgasayisi (cm^-1)" if lang == "tr" else "Wavenumber (cm^-1)"
    if analysis_type == "RAMAN":
        return "Raman Kaymasi (cm^-1)" if lang == "tr" else "Raman Shift (cm^-1)"
    if analysis_type == "XRD":
        return "2θ (derece)" if lang == "tr" else "2θ (degree)"
    return "Sicaklik (°C)" if lang == "tr" else "Temperature (°C)"


def _y_quantity_label(analysis_type, lang):
    if analysis_type == "DSC":
        return "Isi Akisi" if lang == "tr" else "Heat Flow"
    if analysis_type == "TGA":
        return "Kutle" if lang == "tr" else "Mass"
    if analysis_type == "DTA":
        return "Delta-T" if lang == "tr" else "Delta-T"
    if analysis_type == "FTIR":
        return "Absorbans" if lang == "tr" else "Absorbance"
    if analysis_type == "RAMAN":
        return "Yogunluk" if lang == "tr" else "Intensity"
    if analysis_type == "XRD":
        return "Yogunluk" if lang == "tr" else "Intensity"
    return "Sinyal" if lang == "tr" else "Signal"


def _resolve_signal(dataset_key, dataset, analysis_type, signal_mode):
    raw_signal = dataset.data["signal"].values
    if signal_mode == "raw":
        return raw_signal, "Ham" if st.session_state.get("ui_language", "tr") == "tr" else "Raw"

    state = st.session_state.get(_state_key(analysis_type, dataset_key), {})
    if analysis_type == "DSC":
        if state.get("corrected") is not None:
            return state["corrected"], "Baseline düzeltilmiş" if st.session_state.get("ui_language", "tr") == "tr" else "Baseline corrected"
        if state.get("smoothed") is not None:
            return state["smoothed"], "Yumuşatılmış" if st.session_state.get("ui_language", "tr") == "tr" else "Smoothed"
        return raw_signal, "Ham" if st.session_state.get("ui_language", "tr") == "tr" else "Raw"

    if analysis_type == "TGA":
        result = state.get("tga_result")
        if result is not None and getattr(result, "smoothed_signal", None) is not None:
            return result.smoothed_signal, "İşlemci yumuşatılmış" if st.session_state.get("ui_language", "tr") == "tr" else "Processor smoothed"
        if state.get("smoothed") is not None:
            return state["smoothed"], "Yumuşatılmış" if st.session_state.get("ui_language", "tr") == "tr" else "Smoothed"
        return raw_signal, "Ham" if st.session_state.get("ui_language", "tr") == "tr" else "Raw"

    if analysis_type == "DTA":
        if state.get("corrected") is not None:
            return state["corrected"], "Baseline düzeltilmiş" if st.session_state.get("ui_language", "tr") == "tr" else "Baseline corrected"
        if state.get("smoothed") is not None:
            return state["smoothed"], "Yumuşatılmış" if st.session_state.get("ui_language", "tr") == "tr" else "Smoothed"
        return raw_signal, "Ham" if st.session_state.get("ui_language", "tr") == "tr" else "Raw"

    if analysis_type in {"FTIR", "RAMAN"}:
        if state.get("normalized") is not None:
            return state["normalized"], "Normalize edilmiş" if st.session_state.get("ui_language", "tr") == "tr" else "Normalized"
        if state.get("corrected") is not None:
            return state["corrected"], "Baseline düzeltilmiş" if st.session_state.get("ui_language", "tr") == "tr" else "Baseline corrected"
        if state.get("smoothed") is not None:
            return state["smoothed"], "Yumuşatılmış" if st.session_state.get("ui_language", "tr") == "tr" else "Smoothed"
    if analysis_type == "XRD":
        if state.get("corrected") is not None:
            return state["corrected"], "Arkaplan düzeltilmiş" if st.session_state.get("ui_language", "tr") == "tr" else "Background corrected"
        if state.get("smoothed") is not None:
            return state["smoothed"], "Yumuşatılmış" if st.session_state.get("ui_language", "tr") == "tr" else "Smoothed"
    return raw_signal, "Ham" if st.session_state.get("ui_language", "tr") == "tr" else "Raw"


def _build_run_label(dataset_key, dataset):
    sample = dataset.metadata.get("sample_name") or dataset.metadata.get("file_name") or dataset_key
    vendor = dataset.metadata.get("vendor", "Generic")
    rate = dataset.metadata.get("heating_rate")
    if rate:
        return f"{sample} | {vendor} | {rate} °C/min"
    return f"{sample} | {vendor}"


def _has_saved_result(results, analysis_type, dataset_key):
    prefix = analysis_type.lower()
    return f"{prefix}_{dataset_key}" in results


def _render_saved_result_preview(results, analysis_type, selected, lang):
    preview_rows = []
    for dataset_key in selected:
        record = results.get(f"{analysis_type.lower()}_{dataset_key}")
        if not record:
            continue
        row = {
            ("Koşu" if lang == "tr" else "Run"): dataset_key,
            ("Tip" if lang == "tr" else "Type"): record["analysis_type"],
            ("Durum" if lang == "tr" else "Status"): record["status"],
        }
        row.update(record.get("summary", {}))
        preview_rows.append(row)

    if preview_rows:
        st.subheader("Kayıtlı Analiz Özetleri" if lang == "tr" else "Saved Analysis Summaries")
        st.dataframe(pd.DataFrame(preview_rows), width="stretch", hide_index=True)


def _render_batch_runner(workspace, eligible, selected, analysis_type, lang):
    st.subheader("Toplu Şablon Uygulayıcı" if lang == "tr" else "Batch Template Runner")
    workflow_catalog = get_workflow_templates(analysis_type)
    workflow_labels = {entry["id"]: entry["label"] for entry in workflow_catalog}
    workflow_options = list(workflow_labels)
    if not workflow_options:
        st.info("Bu analiz tipi için kayıtlı şablon bulunamadı." if lang == "tr" else "No workflow templates are available for this analysis type.")
        return

    current_template = workspace.get("batch_template_id")
    template_index = workflow_options.index(current_template) if current_template in workflow_options else 0
    workflow_template_id = st.selectbox(
        "Batch şablonu" if lang == "tr" else "Batch template",
        workflow_options,
        index=template_index,
        format_func=lambda template_id: workflow_labels.get(template_id, template_id),
        key=f"compare_batch_template_{analysis_type}",
        help=(
            "Seçili tüm koşulara aynı kararlı analiz şablonunu uygular ve sonuçları mevcut export/report akışına yazar."
            if lang == "tr"
            else "Applies the same stable modality template to every selected run and saves outputs into the existing export/report flow."
        ),
    )

    run_col, hint_col = st.columns([1, 2])
    with run_col:
        if st.button("Toplu Şablonu Çalıştır" if lang == "tr" else "Run Batch Template", key=f"compare_batch_run_{analysis_type}"):
            _apply_batch_template(workspace, eligible, selected, analysis_type, workflow_template_id, workflow_labels.get(workflow_template_id), lang)
            st.rerun()
    with hint_col:
        st.caption(
            (
                "Başarılı koşular kararlı sonuç olarak kaydedilir; hata alan koşular özet tabloda Error ID ile kalır."
                if lang == "tr"
                else "Successful runs are saved as stable results; failed runs stay in the batch summary with an Error ID."
            )
        )

    feedback = workspace.get("batch_last_feedback") or {}
    if feedback:
        message = (
            f"Son batch: {feedback.get('saved', 0)} kaydedildi, {feedback.get('blocked', 0)} bloklandı, {feedback.get('failed', 0)} başarısız oldu."
            if lang == "tr"
            else f"Last batch: {feedback.get('saved', 0)} saved, {feedback.get('blocked', 0)} blocked, {feedback.get('failed', 0)} failed."
        )
        if feedback.get("failed") or feedback.get("blocked"):
            st.warning(message)
        else:
            st.success(message)

    batch_summary = normalize_batch_summary_rows(workspace.get("batch_summary") or [])
    if batch_summary:
        metrics = summarize_batch_outcomes(batch_summary)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Batch Koşu" if lang == "tr" else "Batch Runs", str(metrics["total"]))
        col2.metric("Kaydedilen" if lang == "tr" else "Saved", str(metrics["saved"]))
        col3.metric("Bloklanan" if lang == "tr" else "Blocked", str(metrics["blocked"]))
        col4.metric("Başarısız" if lang == "tr" else "Failed", str(metrics["failed"]))

        if workspace.get("batch_completed_at"):
            st.caption(
                (
                    f"Son batch: `{workspace.get('batch_template_label', workspace.get('batch_template_id', ''))}` / {workspace['batch_completed_at']}"
                    if lang == "tr"
                    else f"Last batch: `{workspace.get('batch_template_label', workspace.get('batch_template_id', ''))}` / {workspace['batch_completed_at']}"
                )
            )

        filter_options = ["all", "saved", "blocked", "failed"]
        filter_value = st.segmented_control(
            "Sonuç filtresi" if lang == "tr" else "Outcome filter",
            filter_options,
            default=workspace.get("batch_filter") if workspace.get("batch_filter") in filter_options else "all",
            format_func=lambda value: {
                "all": "Tümü" if lang == "tr" else "All",
                "saved": "Kaydedilen" if lang == "tr" else "Saved",
                "blocked": "Bloklanan" if lang == "tr" else "Blocked",
                "failed": "Başarısız" if lang == "tr" else "Failed",
            }[value],
            selection_mode="single",
            key=f"compare_batch_filter_{analysis_type}",
        )
        workspace["batch_filter"] = filter_value
        filtered_rows = filter_batch_summary_rows(batch_summary, execution_status=filter_value)

        st.dataframe(
            _batch_summary_dataframe(filtered_rows, lang),
            width="stretch",
            hide_index=True,
        )


def _apply_batch_template(workspace, eligible, selected, analysis_type, workflow_template_id, workflow_template_label, lang):
    batch_run_id = f"batch_{analysis_type.lower()}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
    analysis_history = st.session_state.get("analysis_history", [])
    analyst_name = (st.session_state.get("branding", {}) or {}).get("analyst_name")
    area = {
        "DSC": "dsc_analysis",
        "DTA": "dta_analysis",
        "TGA": "tga_analysis",
        "FTIR": "ftir_analysis",
        "RAMAN": "raman_analysis",
    }.get(analysis_type, "compare_analysis")
    page_label = t("compare.title")

    _log_event(
        tx("Toplu Şablon Başlatıldı", "Batch Template Started"),
        tx("{analysis_type} şablonu {count} koşuda başlatıldı", "{analysis_type} template {template} on {count} run(s)", analysis_type=analysis_type, template=workflow_template_id, count=len(selected)),
        page_label,
        parameters={"workflow_template_id": workflow_template_id, "batch_run_id": batch_run_id},
        status="info",
    )

    summary_rows = []
    saved_result_ids = []
    for dataset_key in selected:
        dataset = eligible[dataset_key]
        existing_state = st.session_state.get(_state_key(analysis_type, dataset_key), {}) or {}
        try:
            outcome = execute_batch_template(
                dataset_key=dataset_key,
                dataset=dataset,
                analysis_type=analysis_type,
                workflow_template_id=workflow_template_id,
                existing_processing=existing_state.get("processing"),
                analysis_history=analysis_history,
                analyst_name=analyst_name,
                app_version=APP_VERSION,
                batch_run_id=batch_run_id,
            )
            row = dict(outcome["summary_row"])

            if outcome["status"] == "saved":
                st.session_state.setdefault("results", {})[outcome["record"]["id"]] = outcome["record"]
                st.session_state[_state_key(analysis_type, dataset_key)] = outcome["state"]
                saved_result_ids.append(outcome["record"]["id"])
                _log_event(
                    tx("Toplu Şablon Uygulandı", "Batch Template Applied"),
                    tx("{analysis_type} batch sonucu {template} ile kaydedildi", "{analysis_type} batch saved with {template}", analysis_type=analysis_type, template=workflow_template_id),
                    page_label,
                    dataset_key=dataset_key,
                    result_id=outcome["record"]["id"],
                    parameters={"workflow_template_id": workflow_template_id, "batch_run_id": batch_run_id},
                    status="info",
                )
            else:
                error_id = make_error_id(area)
                record_diagnostic_event(
                    st.session_state,
                    area=area,
                    action="batch_validation",
                    status="error",
                    message="Batch template blocked by dataset validation.",
                    context={
                        "dataset_key": dataset_key,
                        "analysis_type": analysis_type,
                        "workflow_template_id": workflow_template_id,
                        "batch_run_id": batch_run_id,
                        "issues": outcome["validation"].get("issues", []),
                    },
                    error_id=error_id,
                )
                row["error_id"] = error_id
                row["failure_reason"] = row.get("failure_reason") or ("Validation blocked this dataset." if lang != "tr" else "Veri seti doğrulama nedeniyle bloklandı.")
                row["message"] = row["failure_reason"]
                _log_event(
                    tx("Toplu Şablon Bloklandı", "Batch Template Blocked"),
                    row["failure_reason"],
                    page_label,
                    dataset_key=dataset_key,
                    parameters={"workflow_template_id": workflow_template_id, "batch_run_id": batch_run_id, "error_id": error_id},
                    status="error",
                )
            summary_rows.append(row)
        except Exception as exc:
            error_id = record_exception(
                st.session_state,
                area=area,
                action="batch_run",
                message="Batch template execution failed.",
                context={
                    "dataset_key": dataset_key,
                    "analysis_type": analysis_type,
                    "workflow_template_id": workflow_template_id,
                    "batch_run_id": batch_run_id,
                },
                exception=exc,
            )
            summary_rows.append(
                {
                    "dataset_key": dataset_key,
                    "analysis_type": analysis_type,
                    "sample_name": dataset.metadata.get("sample_name") or dataset_key,
                    "workflow_template_id": workflow_template_id,
                    "workflow_template": workflow_template_label,
                    "execution_status": "failed",
                    "validation_status": "not_run",
                    "warning_count": 0,
                    "issue_count": 1,
                    "calibration_state": dataset.metadata.get("calibration_status") or "unknown",
                    "reference_state": "not_run",
                    "result_id": None,
                    "failure_reason": str(exc),
                    "message": str(exc),
                    "error_id": error_id,
                }
            )
            _log_event(
                tx("Toplu Şablon Başarısız", "Batch Template Failed"),
                str(exc),
                page_label,
                dataset_key=dataset_key,
                parameters={"workflow_template_id": workflow_template_id, "batch_run_id": batch_run_id, "error_id": error_id},
                status="error",
            )

    workspace["batch_run_id"] = batch_run_id
    workspace["batch_template_id"] = workflow_template_id
    workspace["batch_template_label"] = workflow_template_label
    workspace["batch_completed_at"] = datetime.now().isoformat(timespec="seconds")
    workspace["batch_summary"] = normalize_batch_summary_rows(summary_rows)
    workspace["batch_result_ids"] = saved_result_ids
    workspace["batch_last_feedback"] = summarize_batch_outcomes(summary_rows)


def _state_key(analysis_type, dataset_key):
    return analysis_state_key(analysis_type, dataset_key)


def _batch_summary_dataframe(summary_rows, lang):
    df = pd.DataFrame(summary_rows)
    if df.empty:
        return df
    preferred = [
        "dataset_key",
        "sample_name",
        "workflow_template",
        "execution_status",
        "validation_status",
        "calibration_state",
        "reference_state",
        "result_id",
        "error_id",
        "failure_reason",
    ]
    available = [column for column in preferred if column in df.columns]
    df = df[available]
    rename_map = {
        "dataset_key": "Koşu" if lang == "tr" else "Run",
        "sample_name": "Numune" if lang == "tr" else "Sample",
        "workflow_template": "Şablon" if lang == "tr" else "Template",
        "execution_status": "Çalıştırma" if lang == "tr" else "Execution",
        "validation_status": "Doğrulama" if lang == "tr" else "Validation",
        "calibration_state": "Kalibrasyon" if lang == "tr" else "Calibration",
        "reference_state": "Referans" if lang == "tr" else "Reference",
        "result_id": "Sonuç ID" if lang == "tr" else "Result ID",
        "error_id": "Hata ID" if lang == "tr" else "Error ID",
        "failure_reason": "Neden" if lang == "tr" else "Reason",
    }
    return df.rename(columns=rename_map)

