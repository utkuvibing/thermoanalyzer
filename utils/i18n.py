"""Minimal UI translation helpers for ThermoAnalyzer."""

from __future__ import annotations

import streamlit as st


SUPPORTED_LANGUAGES = {
    "tr": "TR",
    "en": "EN",
}

TRANSLATIONS = {
    "app.brand": {
        "tr": "THERMOANALYZER PRO",
        "en": "THERMOANALYZER PRO",
    },
    "app.tagline": {
        "tr": "Cihazdan bağımsız DSC/TGA/DTA/FTIR/RAMAN/XRD çalışma alanı",
        "en": "Vendor-independent DSC/TGA/DTA/FTIR/RAMAN/XRD workbench",
    },
    "app.preview_toggle": {
        "tr": "Laboratuvar Önizleme Modüllerini Göster",
        "en": "Show Lab Preview Modules",
    },
    "app.preview_toggle_help": {
        "tr": "Kinetik ve dekonvolüsyon sayfalarını pilot değerlendirme için açar.",
        "en": "Expose kinetics and deconvolution pages used for pilot evaluations.",
    },
    "app.language": {
        "tr": "Dil",
        "en": "Language",
    },
    "app.license.development": {
        "tr": "Geliştirme",
        "en": "Development",
    },
    "app.license.trial": {
        "tr": "Deneme",
        "en": "Trial",
    },
    "app.license.activated": {
        "tr": "Aktif",
        "en": "Activated",
    },
    "app.license.read_only": {
        "tr": "Salt Okunur",
        "en": "Read Only",
    },
    "app.license.unlicensed": {
        "tr": "Lisanssız",
        "en": "Unlicensed",
    },
    "nav.import": {
        "tr": "Veri Al",
        "en": "Import Runs",
    },
    "nav.compare": {
        "tr": "Karşılaştırma",
        "en": "Compare Workspace",
    },
    "nav.dsc": {
        "tr": "DSC Analizi",
        "en": "DSC Analysis",
    },
    "nav.tga": {
        "tr": "TGA Analizi",
        "en": "TGA Analysis",
    },
    "nav.ftir": {
        "tr": "FTIR Analizi",
        "en": "FTIR Analysis",
    },
    "nav.raman": {
        "tr": "Raman Analizi",
        "en": "Raman Analysis",
    },
    "nav.xrd": {
        "tr": "XRD Analizi",
        "en": "XRD Analysis",
    },
    "nav.report": {
        "tr": "Rapor Merkezi",
        "en": "Report Center",
    },
    "nav.project": {
        "tr": "Proje Alanı",
        "en": "Project Workspace",
    },
    "nav.license": {
        "tr": "Lisans ve Marka",
        "en": "License & Branding",
    },
    "nav.preview": {
        "tr": "Laboratuvar Önizlemesi",
        "en": "Lab Preview",
    },
    "sidebar.project": {
        "tr": "Proje",
        "en": "Project",
    },
    "sidebar.project.caption": {
        "tr": "Mevcut çalışma alanını `.thermozip` arşivi olarak kaydet veya yükle.",
        "en": "Save or load the current workspace as a reusable `.thermozip` archive.",
    },
    "sidebar.project.new": {
        "tr": "Yeni Proje",
        "en": "New Project",
    },
    "sidebar.project.prepare": {
        "tr": "Proje Dosyasını Hazırla",
        "en": "Prepare Project File",
    },
    "sidebar.project.download": {
        "tr": "Proje Dosyasını İndir",
        "en": "Download Project File",
    },
    "sidebar.project.load": {
        "tr": "Projeyi Yükle",
        "en": "Load Project",
    },
    "sidebar.project.load_selected": {
        "tr": "Seçili Projeyi Aç",
        "en": "Load Selected Project",
    },
    "sidebar.pipeline": {
        "tr": "Analiz Geçmişi",
        "en": "Analysis Pipeline",
    },
    "sidebar.about": {
        "tr": "ThermoAnalyzer Hakkında",
        "en": "About ThermoAnalyzer",
    },
    "home.title": {
        "tr": "Veri Al",
        "en": "Import Runs",
    },
    "home.caption": {
        "tr": "Termal analiz koşularını içe aktar, metadatasını düzenle ve karşılaştırma ya da analize geç.",
        "en": "Import thermal runs, normalize metadata, and continue into comparison or analysis.",
    },
    "home.hero_badge": {
        "tr": "Çalışma Başlangıcı",
        "en": "Workspace Entry",
    },
    "compare.title": {
        "tr": "Karşılaştırma Alanı",
        "en": "Compare Workspace",
    },
    "compare.caption": {
        "tr": "Kararlı modaliteleri üst üste koy, normalize metadata’yı gör ve rapora girecek overlay’i hazırla.",
        "en": "Overlay stable-modality runs, review normalized metadata, and prepare a report-ready comparison figure.",
    },
    "compare.hero_badge": {
        "tr": "Çoklu Koşu Overlay",
        "en": "Multi-Run Overlay",
    },
    "report.title": {
        "tr": "Rapor Merkezi",
        "en": "Report Center",
    },
    "report.caption": {
        "tr": "Normalize sonuçları dışa aktar, markalı raporu önizle ve müşteri sunumuna uygun çıktı üret.",
        "en": "Export normalized results, preview the branded report package, and generate customer-ready outputs.",
    },
    "report.hero_badge": {
        "tr": "Teslimat Katmanı",
        "en": "Delivery Layer",
    },
    "project.title": {
        "tr": "Proje Alanı",
        "en": "Project Workspace",
    },
    "project.caption": {
        "tr": "Yüklenen koşuları, kaydedilmiş analizleri ve rapor varlıklarını tek proje görünümünde denetle.",
        "en": "Review loaded runs, saved analyses, and report assets in one project overview.",
    },
    "project.hero_badge": {
        "tr": "Oturum Yönetimi",
        "en": "Session Management",
    },
    "license.title": {
        "tr": "Lisans ve Marka",
        "en": "License & Branding",
    },
    "license.caption": {
        "tr": "Ticari aktivasyonu test et ve raporların şirket markasıyla çıkmasını yapılandır.",
        "en": "Test commercial activation and configure company branding for reports.",
    },
    "license.hero_badge": {
        "tr": "Ticari Katman",
        "en": "Commercial Layer",
    },
    "dsc.title": {
        "tr": "DSC Analizi",
        "en": "DSC Analysis",
    },
    "dsc.caption": {
        "tr": "Ham sinyalden Tg, baseline ve peak karakterizasyonuna kadar DSC akışını yönet.",
        "en": "Run the DSC workflow from raw signal through Tg, baseline, and peak characterization.",
    },
    "tga.title": {
        "tr": "TGA Analizi",
        "en": "TGA Analysis",
    },
    "tga.caption": {
        "tr": "Kütle kaybı adımlarını, DTG eğrisini ve kalıntı yüzdesini tek iş akışında çıkar.",
        "en": "Extract mass-loss steps, DTG curves, and residue metrics in one workflow.",
    },
    "xrd.title": {
        "tr": "XRD Analizi",
        "en": "XRD Analysis",
    },
    "xrd.caption": {
        "tr": "XRD desenlerinde ön işleme, pik çıkarımı ve nitel faz adayı eşlemesini kararlı akışta çalıştır.",
        "en": "Run stable XRD preprocessing, peak extraction, and qualitative phase-candidate matching workflows.",
    },
    "xrd.hero_badge": {
        "tr": "Difraksiyon İş Akışı",
        "en": "Diffraction Workflow",
    },
    "ftir.title": {
        "tr": "FTIR Analizi",
        "en": "FTIR Analysis",
    },
    "ftir.caption": {
        "tr": "FTIR spektrumlarında ön işleme, pik çıkarımı ve nitel benzerlik adayı sıralamasını kararlı akışta çalıştır.",
        "en": "Run stable FTIR preprocessing, peak extraction, and qualitative similarity-candidate ranking workflows.",
    },
    "ftir.hero_badge": {
        "tr": "FTIR İş Akışı",
        "en": "FTIR Workflow",
    },
    "raman.title": {
        "tr": "Raman Analizi",
        "en": "Raman Analysis",
    },
    "raman.caption": {
        "tr": "Raman spektrumlarında ön işleme, pik çıkarımı ve nitel benzerlik adayı sıralamasını kararlı akışta çalıştır.",
        "en": "Run stable Raman preprocessing, peak extraction, and qualitative similarity-candidate ranking workflows.",
    },
    "raman.hero_badge": {
        "tr": "Raman İş Akışı",
        "en": "Raman Workflow",
    },
}


def get_language() -> str:
    """Return the active UI language."""
    lang = st.session_state.get("ui_language", "tr")
    if lang not in SUPPORTED_LANGUAGES:
        lang = "tr"
        st.session_state["ui_language"] = lang
    return lang


def t(key: str, **kwargs) -> str:
    """Translate a UI key using the current session language."""
    lang = get_language()
    entry = TRANSLATIONS.get(key)
    if entry is None:
        text = key
    else:
        text = entry.get(lang) or entry.get("en") or key
    if kwargs:
        return text.format(**kwargs)
    return text


def tx(tr: str, en: str, **kwargs) -> str:
    """Translate inline text using the current session language."""
    text = tr if get_language() == "tr" else en
    if kwargs:
        return text.format(**kwargs)
    return text
