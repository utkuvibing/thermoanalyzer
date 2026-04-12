"""License activation and report branding page."""

from __future__ import annotations

import streamlit as st

from ui.components.chrome import render_page_header
from utils.i18n import t
from utils.license_manager import (
    APP_VERSION,
    activate_license_key,
    clear_saved_license,
    commercial_mode_enabled,
    get_machine_fingerprint,
    license_allows_write,
    load_license_state,
    start_trial,
)


def render():
    render_page_header(t("license.title"), t("license.caption"), badge=t("license.hero_badge"))
    lang = st.session_state.get("ui_language", "tr")

    try:
        state = st.session_state.get("license_state") or load_license_state(app_version=APP_VERSION)
    except Exception as exc:
        state = {
            "status": "unlicensed" if commercial_mode_enabled() else "development",
            "message": f"Stored license could not be loaded: {exc}",
            "license": None,
            "commercial_mode": commercial_mode_enabled(),
        }
    st.session_state["license_state"] = state

    c1, c2, c3 = st.columns(3)
    c1.metric("Durum" if lang == "tr" else "Status", _status_label(state, lang))
    c2.metric("Yazma Yetkisi" if lang == "tr" else "Write Access", "Açık" if lang == "tr" and license_allows_write(state) else ("Enabled" if license_allows_write(state) else ("Salt Okunur" if lang == "tr" else "Read Only")))
    c3.metric("Makine Parmak İzi" if lang == "tr" else "Machine Fingerprint", get_machine_fingerprint())

    if not commercial_mode_enabled():
        st.info(
            "Streamlit geliştirme build'i: ticari lisans enforcement kapalı. Aktivasyonu test edebilirsin ama tüm fonksiyonlar zaten açık."
            if lang == "tr"
            else "Streamlit development build: commercial license enforcement is disabled. You can still test activation here, but all app functions remain unlocked."
        )

    if state.get("message"):
        if state["status"] == "expired_read_only":
            st.warning(state["message"])
        elif state["status"] in {"unlicensed", "development"}:
            st.info(state["message"])
        else:
            st.success(state["message"])

    if state.get("license"):
        license_payload = state["license"]
        st.subheader("Yüklü Lisans" if lang == "tr" else "Installed License")
        st.json(
            {
                "license_key": license_payload.get("license_key"),
                "customer_name": license_payload.get("customer_name"),
                "company_name": license_payload.get("company_name"),
                "sku": license_payload.get("sku"),
                "seat_count": license_payload.get("seat_count"),
                "issued_at": license_payload.get("issued_at"),
                "expires_at": license_payload.get("expires_at"),
                "allowed_major_version": license_payload.get("allowed_major_version"),
                "offline_grace_days": license_payload.get("offline_grace_days"),
            },
            expanded=False,
        )

    activation_tab, branding_tab, about_tab = st.tabs([
        "Aktivasyon" if lang == "tr" else "Activation",
        "Rapor Markası" if lang == "tr" else "Report Branding",
        "Hakkında" if lang == "tr" else "About",
    ])

    with activation_tab:
        with st.form("activate_license_form", clear_on_submit=False):
            key_input = st.text_area(
                "İmzalı lisans anahtarı" if lang == "tr" else "Signed license key",
                height=120,
                placeholder="Buraya TAPRO-... lisans anahtarını yapıştır." if lang == "tr" else "Paste a TAPRO-... license key here.",
            )
            submitted = st.form_submit_button("Lisansı Aktifleştir" if lang == "tr" else "Activate License")
        if submitted:
            try:
                st.session_state["license_state"] = activate_license_key(key_input, app_version=APP_VERSION)
                st.success("Lisans yerel olarak aktifleştirildi." if lang == "tr" else "License activated locally.")
                st.rerun()
            except Exception as exc:
                st.error(f"Aktivasyon başarısız: {exc}" if lang == "tr" else f"Activation failed: {exc}")

        trial_col, clear_col = st.columns(2)
        with trial_col:
            if st.button("14 Günlük Denemeyi Başlat" if lang == "tr" else "Start 14-Day Trial", key="start_trial_btn", disabled=state["status"] in {"trial", "activated"}):
                st.session_state["license_state"] = start_trial(app_version=APP_VERSION)
                st.success("Deneme başlatıldı." if lang == "tr" else "Trial started.")
                st.rerun()
        with clear_col:
            if st.button("Yerel Lisansı Kaldır" if lang == "tr" else "Remove Local License", key="clear_license_btn"):
                clear_saved_license()
                st.session_state["license_state"] = load_license_state(app_version=APP_VERSION)
                st.success("Yerel lisans dosyaları kaldırıldı." if lang == "tr" else "Local license files removed.")
                st.rerun()

        st.caption(
            "Offline aktivasyon desteklenir. Ticari dağıtımda imzalı anahtarlar ayrı bir satış/admin aracı ile üretilmelidir."
            if lang == "tr"
            else "Offline activation is supported. For commercial deployments, signed keys should be generated by a separate sales/admin tool."
        )

    with branding_tab:
        branding = st.session_state.setdefault("branding", {})
        company_default = branding.get("company_name") or _license_company(state)
        with st.form("branding_form", clear_on_submit=False):
            report_title = st.text_input(
                "Rapor başlığı" if lang == "tr" else "Report title",
                value=branding.get("report_title", "MaterialScope Professional Report"),
            )
            company_name = st.text_input("Şirket" if lang == "tr" else "Company", value=company_default)
            lab_name = st.text_input("Laboratuvar" if lang == "tr" else "Laboratory", value=branding.get("lab_name", ""))
            analyst_name = st.text_input("Analist" if lang == "tr" else "Analyst", value=branding.get("analyst_name", ""))
            report_notes = st.text_area(
                "Varsayılan rapor notları" if lang == "tr" else "Default report notes",
                value=branding.get("report_notes", ""),
                height=140,
                placeholder="Kalite notları, kabul kriterleri veya müşteri çıktısı için yorumlar." if lang == "tr" else "Quality notes, acceptance criteria, or customer-facing conclusions.",
            )
            logo_file = st.file_uploader(
                "Şirket logosu (PNG/JPG)" if lang == "tr" else "Company logo (PNG/JPG)",
                type=["png", "jpg", "jpeg"],
                key="branding_logo_uploader",
            )
            saved = st.form_submit_button("Markayı Kaydet" if lang == "tr" else "Save Branding")

        if saved:
            branding["report_title"] = report_title
            branding["company_name"] = company_name
            branding["lab_name"] = lab_name
            branding["analyst_name"] = analyst_name
            branding["report_notes"] = report_notes
            if logo_file is not None:
                branding["logo_bytes"] = logo_file.getvalue()
                branding["logo_name"] = logo_file.name
            st.success("Marka ayarları güncellendi." if lang == "tr" else "Branding updated for the current project/session.")

        if branding.get("logo_bytes"):
            st.image(branding["logo_bytes"], width=220)
            if branding.get("logo_name"):
                st.caption(f"Mevcut logo: {branding['logo_name']}" if lang == "tr" else f"Current logo: {branding['logo_name']}")

    with about_tab:
        _render_about_materialscope(lang)


def _status_label(state, lang):
    labels = {
        "development": "Geliştirme Build'i" if lang == "tr" else "Development Build",
        "trial": "Deneme" if lang == "tr" else "Trial",
        "activated": "Aktif" if lang == "tr" else "Activated",
        "expired_read_only": "Süresi Dolmuş / Salt Okunur" if lang == "tr" else "Expired / Read Only",
        "unlicensed": "Lisanssız" if lang == "tr" else "Unlicensed",
    }
    return labels.get((state or {}).get("status"), "Unknown")


def _license_company(state):
    payload = (state or {}).get("license") or {}
    return payload.get("company_name", "")


def _render_about_materialscope(lang: str) -> None:
    if lang == "tr":
        st.markdown(
            f"**MaterialScope v{APP_VERSION}**\n\n"
            "QC ve Ar-Ge laboratuvarları için cihazdan bağımsız, çok modlu DSC/TGA/DTA/FTIR/RAMAN/XRD karakterizasyon çalışma alanı.\n\n"
            "**Kararlı beta kapsamı**\n"
            "- CSV/TXT/XLSX DSC, TGA, DTA, FTIR, RAMAN ve XRD koşularını içe aktar\n"
            "- DSC, TGA, DTA, FTIR, RAMAN ve XRD analiz akışlarını çalıştır\n"
            "- Çoklu koşuları Karşılaştırma Alanı ve Toplu Şablon Uygulayıcı ile yönet\n"
            "- Kararlı sonuçları proje durumu, rapor ve export akışıyla sakla\n"
            "- Laboratuvar önizleme modülleri yalnızca özel olarak etkinleştirilen buildlerde görünür\n\n"
            "**Laboratuvar önizleme modülleri**\n"
            "- Kinetik ve dekonvolüsyon modülleri önizleme anahtarı arkasında kalır ve ticari stabilite sözüne dahil değildir.\n\n"
            "**Referans standartlar**\n"
            "- ASTM E967 — DSC sıcaklık ve entalpi kalibrasyonu\n"
            "- ASTM E1131 — TGA ile kompozisyon analizi\n"
            "- ASTM E1356 — DSC ile cam geçişi\n"
            "- ICTAC kinetik analiz rehberleri"
        )
        st.caption(
            "Pilot kabuk: Streamlit\n"
            "Ticari yön: offline masaüstü kabuk + yıllık cihaz lisansı"
        )
        return

    st.markdown(
        f"**MaterialScope v{APP_VERSION}**\n\n"
        "Vendor-independent multimodal DSC/TGA/DTA/FTIR/RAMAN/XRD characterization workbench for QC and R&D labs.\n\n"
        "**Stable beta scope**\n"
        "- Import DSC, TGA, DTA, FTIR, RAMAN, and XRD runs from CSV/TXT/XLSX exports\n"
        "- Execute stable DSC, TGA, DTA, FTIR, RAMAN, and XRD analysis workflows\n"
        "- Manage multiple runs through Compare Workspace and the Batch Template Runner\n"
        "- Save stable results through the current project, report, and export flows\n"
        "- Lab preview modules appear only in explicitly enabled builds\n\n"
        "**Lab Preview modules**\n"
        "- Kinetics and deconvolution stay available behind the preview toggle and are excluded from the commercial stability promise.\n\n"
        "**Reference standards**\n"
        "- ASTM E967 — DSC Temperature & Enthalpy Calibration\n"
        "- ASTM E1131 — Compositional Analysis by TGA\n"
        "- ASTM E1356 — Glass Transition by DSC\n"
        "- ICTAC kinetic analysis guidance"
    )
    st.caption(
        "Pilot shell: Streamlit\n"
        "Commercial direction: offline desktop shell + annual device licensing"
    )
