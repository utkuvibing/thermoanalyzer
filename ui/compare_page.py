"""Commercial comparison workspace for DSC/TGA runs."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from core.result_serialization import split_valid_results
from ui.components.chrome import render_page_header
from ui.components.history_tracker import _log_event
from ui.components.plot_builder import PLOTLY_CONFIG, create_overlay_plot, fig_to_bytes
from utils.i18n import t


ANALYSIS_LABELS = {
    "DSC": "Heat Flow",
    "TGA": "Mass",
}


def render():
    render_page_header(t("compare.title"), t("compare.caption"), badge=t("compare.hero_badge"))
    lang = st.session_state.get("ui_language", "tr")

    datasets = st.session_state.get("datasets", {})
    compareable = {key: ds for key, ds in datasets.items() if ds.data_type in {"DSC", "TGA", "UNKNOWN", "unknown"}}
    if not compareable:
        st.warning("Henüz DSC/TGA verisi yok. Önce veri yükle." if lang == "tr" else "No DSC/TGA datasets are available yet. Import runs first.")
        return

    valid_results, _ = split_valid_results(st.session_state.get("results", {}))
    workspace = st.session_state.setdefault("comparison_workspace", {})

    available_types = []
    if any(ds.data_type in {"DSC", "UNKNOWN", "unknown"} for ds in compareable.values()):
        available_types.append("DSC")
    if any(ds.data_type in {"TGA", "UNKNOWN", "unknown"} for ds in compareable.values()):
        available_types.append("TGA")

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
        if ds.data_type == analysis_type or ds.data_type in {"UNKNOWN", "unknown"}
    }
    options = list(eligible.keys())
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
    y_label = f"{ANALYSIS_LABELS[analysis_type]} ({y_unit})"
    fig = create_overlay_plot(
        series,
        title=f"{analysis_type} Compare Workspace",
        y_label=y_label,
    )
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    m1, m2, m3 = st.columns(3)
    m1.metric("Karşılaştırılan Koşu" if lang == "tr" else "Runs Compared", str(len(selected)))
    m2.metric("Vendor Sayısı" if lang == "tr" else "Vendors Present", str(len({eligible[key].metadata.get('vendor', 'Generic') for key in selected})))
    m3.metric("Kayıtlı Stable Sonuç" if lang == "tr" else "Saved Stable Results", str(sum(1 for key in selected if _has_saved_result(valid_results, analysis_type, key))))

    st.subheader("Alan Özeti" if lang == "tr" else "Workspace Summary")
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

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
                "Comparison Saved",
                f"{analysis_type} overlay with {len(selected)} run(s)",
                "Compare Workspace",
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

    _render_saved_result_preview(valid_results, analysis_type, selected, lang)


def _resolve_signal(dataset_key, dataset, analysis_type, signal_mode):
    raw_signal = dataset.data["signal"].values
    if signal_mode == "raw":
        return raw_signal, "Ham" if st.session_state.get("ui_language", "tr") == "tr" else "Raw"

    if analysis_type == "DSC":
        state = st.session_state.get(f"dsc_state_{dataset_key}", {})
        if state.get("corrected") is not None:
            return state["corrected"], "Baseline düzeltilmiş" if st.session_state.get("ui_language", "tr") == "tr" else "Baseline corrected"
        if state.get("smoothed") is not None:
            return state["smoothed"], "Yumuşatılmış" if st.session_state.get("ui_language", "tr") == "tr" else "Smoothed"
        return raw_signal, "Ham" if st.session_state.get("ui_language", "tr") == "tr" else "Raw"

    state = st.session_state.get(f"tga_state_{dataset_key}", {})
    result = state.get("tga_result")
    if result is not None and getattr(result, "smoothed_signal", None) is not None:
        return result.smoothed_signal, "İşlemci yumuşatılmış" if st.session_state.get("ui_language", "tr") == "tr" else "Processor smoothed"
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
        st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)
