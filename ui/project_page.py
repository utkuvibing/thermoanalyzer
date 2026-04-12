"""Project workspace overview page."""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from core.project_io import PROJECT_EXTENSION, load_project_archive, save_project_archive
from core.result_serialization import split_valid_results
from ui.components.chrome import render_page_header
from utils.diagnostics import record_exception
from utils.i18n import t
from utils.license_manager import license_allows_write
from utils.session_state import clear_project_state, replace_project_state


def _tx(lang: str, tr: str, en: str) -> str:
    return tr if lang == "tr" else en


def _prepare_project_archive(lang: str, datasets: dict) -> bool:
    try:
        st.session_state["project_archive_bytes"] = save_project_archive(st.session_state)
        st.session_state["project_archive_ready"] = True
        st.success(_tx(lang, "Proje arşivi hazırlandı.", "Project archive prepared."))
        return True
    except Exception as exc:
        error_id = record_exception(
            st.session_state,
            area="project_load",
            action="project_prepare",
            message="Preparing project archive failed.",
            context={"dataset_count": len(datasets)},
            exception=exc,
        )
        st.error(f"Project archive preparation failed: {exc} (Error ID: {error_id})")
        return False


def _load_project_from_session_payload(lang: str) -> None:
    payload = st.session_state.get("project_pending_upload_bytes")
    file_name = st.session_state.get("project_pending_upload_name", f"project{PROJECT_EXTENSION}")
    if not payload:
        return
    try:
        buffer = io.BytesIO(payload)
        buffer.name = file_name
        project_state = load_project_archive(buffer)
        replace_project_state(project_state)
        st.session_state.pop("project_confirm_load", None)
        st.session_state.pop("project_pending_upload_bytes", None)
        st.session_state.pop("project_pending_upload_name", None)
        st.success(_tx(lang, "Proje yüklendi.", "Project loaded."))
        st.rerun()
    except Exception as exc:
        error_id = record_exception(
            st.session_state,
            area="project_load",
            action="project_load",
            message="Loading project archive failed.",
            context={"file_name": file_name},
            exception=exc,
        )
        st.error(f"Project load failed: {exc} (Error ID: {error_id})")


def render():
    render_page_header(t("project.title"), t("project.caption"), badge=t("project.hero_badge"))
    lang = st.session_state.get("ui_language", "tr")

    datasets = st.session_state.get("datasets", {})
    valid_results, issues = split_valid_results(st.session_state.get("results", {}))
    figures = st.session_state.get("figures", {}) or {}
    workspace = st.session_state.get("comparison_workspace", {}) or {}
    history_steps = st.session_state.get("analysis_history", []) or []

    archive_ready = bool(st.session_state.get("project_archive_ready") and st.session_state.get("project_archive_bytes"))
    has_workspace_content = bool(datasets or valid_results or figures or workspace.get("selected_datasets") or history_steps)
    has_project_artifacts = bool(valid_results or figures or history_steps)
    can_write = license_allows_write(st.session_state.get("license_state"))

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(_tx(lang, "Veri Seti", "Datasets"), str(len(datasets)))
    m2.metric(_tx(lang, "Kayıtlı Sonuç", "Saved Results"), str(len(valid_results)))
    m3.metric(_tx(lang, "Görsel", "Figures"), str(len(figures)))
    m4.metric(_tx(lang, "Arşiv", "Archive"), _tx(lang, "Hazır" if archive_ready else "Bekliyor", "Ready" if archive_ready else "Pending"))

    action_cards_col, upload_panel_col = st.columns([1.6, 1.0], gap="large")

    with action_cards_col:
        st.subheader(_tx(lang, "Hızlı İşlemler", "Quick Actions"))
        new_card_col, prepare_card_col, download_card_col = st.columns(3, gap="small")

        with new_card_col:
            with st.container(border=True):
                st.caption(_tx(lang, "Mevcut çalışma alanını sıfırdan başlat.", "Start a fresh workspace."))
                if st.button(t("sidebar.project.new"), key="project_new_page", use_container_width=True):
                    if has_workspace_content:
                        st.session_state["project_confirm_clear"] = True
                    else:
                        clear_project_state()
                        st.rerun()

        with prepare_card_col:
            with st.container(border=True):
                st.caption(
                    _tx(
                        lang,
                        "En az bir analiz sonucu varsa indirilebilir arşiv hazırla.",
                        "Prepare a downloadable archive once at least one analysis result exists.",
                    )
                )
                if st.button(
                    t("sidebar.project.prepare"),
                    key="project_prepare_page",
                    disabled=not has_project_artifacts or not can_write,
                    use_container_width=True,
                    help=_tx(
                        lang,
                        "En az bir analiz sonucu oluştuktan sonra arşiv hazırlanabilir.",
                        "An archive can be prepared after at least one analysis result exists.",
                    ),
                ):
                    _prepare_project_archive(lang, datasets)

        with download_card_col:
            with st.container(border=True):
                st.caption(_tx(lang, "Hazır arşivi indir ve oturumu dışa aktar.", "Download the prepared archive and export the session."))
                st.download_button(
                    t("sidebar.project.download"),
                    data=st.session_state.get("project_archive_bytes") or b"",
                    file_name=f"materialscope_project{PROJECT_EXTENSION}",
                    mime="application/zip",
                    key="project_save_page",
                    on_click="ignore",
                    disabled=not archive_ready,
                    use_container_width=True,
                )

        with st.container(border=True):
            st.markdown(f"**{_tx(lang, 'Durum', 'Status')}**")
            status_lines = [
                (_tx(lang, "Çalışma alanı", "Workspace"), _tx(lang, "Aktif" if has_workspace_content else "Boş", "Active" if has_workspace_content else "Empty")),
                (_tx(lang, "Kaydedilmiş sonuçlar", "Saved results"), str(len(valid_results))),
                (_tx(lang, "Karşılaştırma alanı", "Compare workspace"), _tx(lang, "Hazır" if workspace.get("selected_datasets") else "Boş", "Ready" if workspace.get("selected_datasets") else "Empty")),
                (_tx(lang, "Arşiv durumu", "Archive status"), _tx(lang, "Hazır" if archive_ready else "Hazır değil", "Ready" if archive_ready else "Not ready")),
            ]
            for label, value in status_lines:
                st.markdown(f"**{label}:** {value}")

        next_step_message = (
            _tx(lang, "Önce Veri Al sayfasından koşu yükle.", "Start by loading runs from Import Runs.")
            if not datasets
            else _tx(lang, "Sıradaki doğru adım: analiz sayfalarından en az bir sonucu kaydet.", "Next step: save at least one result from the analysis pages.")
            if not valid_results
            else _tx(lang, "Sıradaki doğru adım: Karşılaştırma Alanı'nda koşuları eşleştir.", "Next step: align runs in the Compare Workspace.")
            if not workspace.get("selected_datasets")
            else _tx(lang, "Sıradaki doğru adım: Rapor Merkezi'nde çıktı paketini hazırla.", "Next step: prepare the output package in Report Center.")
        )
        st.info(next_step_message)

        if st.session_state.get("project_confirm_clear"):
            with st.container(border=True):
                st.warning(
                    _tx(
                        lang,
                        "Mevcut çalışma alanı üzerine yazılacak. İstersen önce arşiv hazırla, sonra temizle.",
                        "The current workspace will be overwritten. Prepare an archive first if you need to keep it.",
                    )
                )
                clear_action_col, save_first_col, cancel_clear_col = st.columns(3, gap="small")
                with clear_action_col:
                    if st.button(_tx(lang, "Kaydetmeden Temizle", "Clear Without Saving"), key="project_clear_confirm", use_container_width=True):
                        st.session_state.pop("project_confirm_clear", None)
                        clear_project_state()
                        st.rerun()
                with save_first_col:
                    if st.button(
                        _tx(lang, "Önce Arşivi Hazırla", "Prepare Archive First"),
                        key="project_prepare_before_clear",
                        disabled=not has_project_artifacts or not can_write,
                        use_container_width=True,
                    ):
                        _prepare_project_archive(lang, datasets)
                with cancel_clear_col:
                    if st.button(_tx(lang, "Vazgeç", "Cancel"), key="project_clear_cancel", use_container_width=True):
                        st.session_state.pop("project_confirm_clear", None)
                        st.rerun()

    with upload_panel_col:
        with st.container(border=True):
            st.subheader(_tx(lang, "Proje Yükle", "Load Project"))
            st.caption(
                _tx(
                    lang,
                    "Arşivi sürükle-bırak ya da seç, sonra mevcut çalışma alanına uygula.",
                    "Drag and drop an archive or browse for it, then apply it to the current workspace.",
                )
            )
            uploaded_project = st.file_uploader(
                t("sidebar.project.load"),
                type=[PROJECT_EXTENSION.lstrip(".")],
                key="project_loader_page",
                help="Load a previously saved MaterialScope project archive.",
            )
            incoming_name = getattr(uploaded_project, "name", None) or _tx(lang, "Dosya seçilmedi", "No file selected")
            st.markdown(f"**{_tx(lang, 'Seçilen arşiv', 'Selected archive')}:** {incoming_name}")
            if st.button(t("sidebar.project.load_selected"), key="project_load_btn_page", disabled=uploaded_project is None, use_container_width=True):
                if uploaded_project is not None:
                    st.session_state["project_pending_upload_bytes"] = uploaded_project.getvalue()
                    st.session_state["project_pending_upload_name"] = uploaded_project.name
                    if has_workspace_content:
                        st.session_state["project_confirm_load"] = True
                    else:
                        _load_project_from_session_payload(lang)

            if st.session_state.get("project_confirm_load"):
                st.warning(
                    _tx(
                        lang,
                        "Seçili arşiv mevcut çalışma alanının üzerine yüklenecek.",
                        "The selected archive will replace the current workspace.",
                    )
                )
                load_confirm_col, load_cancel_col = st.columns(2, gap="small")
                with load_confirm_col:
                    if st.button(_tx(lang, "Yüklemeye Devam Et", "Continue Loading"), key="project_load_confirm", use_container_width=True):
                        _load_project_from_session_payload(lang)
                with load_cancel_col:
                    if st.button(_tx(lang, "İptal", "Cancel"), key="project_load_cancel", use_container_width=True):
                        st.session_state.pop("project_confirm_load", None)
                        st.session_state.pop("project_pending_upload_bytes", None)
                        st.session_state.pop("project_pending_upload_name", None)
                        st.rerun()

    overview_tab, actions_tab = st.tabs(
        [
            "Çalışma Alanı Özeti" if lang == "tr" else "Workspace Summary",
            "Proje İşlemleri" if lang == "tr" else "Project Actions",
        ]
    )

    with overview_tab:
        if datasets:
            st.subheader("Yüklenen Koşular" if lang == "tr" else "Loaded Runs")
            dataset_rows = []
            for key, dataset in datasets.items():
                dataset_rows.append(
                    {
                        ("Anahtar" if lang == "tr" else "Key"): key,
                        ("Tip" if lang == "tr" else "Type"): dataset.data_type,
                        "Vendor": dataset.metadata.get("vendor", "Generic"),
                        ("Numune" if lang == "tr" else "Sample"): dataset.metadata.get("sample_name") or ("Adsız" if lang == "tr" else "Unnamed"),
                        ("Isıtma Hızı" if lang == "tr" else "Heating Rate"): dataset.metadata.get("heating_rate") or "—",
                        ("Nokta" if lang == "tr" else "Points"): len(dataset.data),
                    }
                )
            st.dataframe(pd.DataFrame(dataset_rows), width="stretch", hide_index=True)

        if valid_results:
            st.subheader("Kayıtlı Sonuç Kayıtları" if lang == "tr" else "Saved Result Records")
            result_rows = []
            for record in valid_results.values():
                result_rows.append(
                    {
                        "ID": record["id"],
                        ("Tip" if lang == "tr" else "Type"): record["analysis_type"],
                        ("Durum" if lang == "tr" else "Status"): record["status"],
                        ("Veri Seti" if lang == "tr" else "Dataset"): record.get("dataset_key") or "—",
                        ("Satır" if lang == "tr" else "Rows"): len(record.get("rows", [])),
                    }
                )
            st.dataframe(pd.DataFrame(result_rows), width="stretch", hide_index=True)

        if workspace.get("selected_datasets"):
            st.subheader("Karşılaştırma Alanı" if lang == "tr" else "Comparison Workspace")
            st.write(f"**{'Tip' if lang == 'tr' else 'Type'}:** {workspace.get('analysis_type', 'N/A')}")
            st.write(f"**{'Seçili koşular' if lang == 'tr' else 'Selected runs'}:** {', '.join(workspace['selected_datasets'])}")
            if workspace.get("figure_key"):
                st.write(f"**{'Kaydedilen görsel' if lang == 'tr' else 'Saved figure'}:** {workspace['figure_key']}")
            if workspace.get("notes"):
                st.write(f"**{'Notlar' if lang == 'tr' else 'Notes'}**")
                st.write(workspace["notes"])

        if issues:
            st.warning(
                "Bazı sonuç kayıtları eksik; export sırasında atlanacak."
                if lang == "tr"
                else "Some result records are incomplete and will be skipped from exports."
            )
            for issue in issues:
                st.caption(f"- {issue}")

    with actions_tab:
        st.info(t("project.sidebar_hint"))
        st.markdown(f"**{_tx(lang, 'Operasyon Notları', 'Operational Notes')}**")
        st.markdown(
            f"- {_tx(lang, 'Arşiv hazırlama yalnızca en az bir analiz sonucu üretildiğinde aktif olur.', 'Archive preparation activates only after at least one analysis result exists.')}"
        )
        st.markdown(
            f"- {_tx(lang, 'Yükleme işlemi mevcut çalışma alanını değiştireceği için önce açık bir onay ister.', 'Loading asks for confirmation before replacing the current workspace.')}"
        )
        st.markdown(
            f"- {_tx(lang, 'Rapor Merkezi ve Karşılaştırma Alanı için sıradaki adım önerisi üstteki dashboard üzerinde gösterilir.', 'The next recommended action for Compare Workspace and Report Center is shown in the dashboard above.')}"
        )
