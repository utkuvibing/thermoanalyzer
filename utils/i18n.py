"""Minimal UI translation helpers for MaterialScope."""

from __future__ import annotations

import streamlit as st


SUPPORTED_LANGUAGES = {
    "tr": "TR",
    "en": "EN",
}

TRANSLATIONS = {
    "app.brand": {
        "tr": "MaterialScope",
        "en": "MaterialScope",
    },
    "app.tagline": {
        "tr": "Çok modlu DSC/TGA/DTA/FTIR/RAMAN/XRD karakterizasyon çalışma alanı",
        "en": "Multimodal DSC/TGA/DTA/FTIR/RAMAN/XRD characterization workbench",
    },
    "app.preview_toggle": {
        "tr": "Laboratuvar Önizleme Modüllerini Göster",
        "en": "Show Lab Preview Modules",
    },
    "app.preview_toggle_help": {
        "tr": "Kinetik ve dekonvolüsyon sayfalarını pilot değerlendirme için açar.",
        "en": "Expose kinetics and deconvolution pages used for pilot evaluations.",
    },
    "app.preview_disabled": {
        "tr": "Laboratuvar önizleme modülleri bu dağıtım profilinde kapalı.",
        "en": "Lab preview modules are disabled in this deployment profile.",
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
    "nav.primary": {
        "tr": "Ana Akış",
        "en": "Primary Flow",
    },
    "nav.analyses": {
        "tr": "Analizler",
        "en": "Analyses",
    },
    "nav.management": {
        "tr": "Yönetim",
        "en": "Management",
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
    "nav.about": {
        "tr": "Hakkında",
        "en": "About",
    },
    "nav.preview": {
        "tr": "Laboratuvar Önizlemesi",
        "en": "Lab Preview",
    },
    "nav.section_primary": {
        "tr": "Ana",
        "en": "Primary",
    },
    "nav.section_analysis": {
        "tr": "Analiz",
        "en": "Analysis",
    },
    "nav.section_management": {
        "tr": "Yönetim",
        "en": "Management",
    },
    "nav.dta": {
        "tr": "DTA Analizi",
        "en": "DTA Analysis",
    },
    "dash.sidebar.tagline": {
        "tr": "Çok modlu malzeme karakterizasyon çalışma alanı",
        "en": "Multimodal materials characterization workbench",
    },
    "sidebar.history_title": {
        "tr": "Son Geçmiş",
        "en": "Recent History",
    },
    "sidebar.history_empty": {
        "tr": "Henüz geçmiş yok.",
        "en": "No history yet.",
    },
    "ui.theme_hint": {
        "tr": "Renk teması",
        "en": "Color theme",
    },
    "ui.theme_use_light": {
        "tr": "Açık temayı kullan",
        "en": "Use light theme",
    },
    "ui.theme_use_dark": {
        "tr": "Koyu temayı kullan",
        "en": "Use dark theme",
    },
    "ui.theme_current_light": {
        "tr": "Açık",
        "en": "Light",
    },
    "ui.theme_current_dark": {
        "tr": "Koyu",
        "en": "Dark",
    },
    "ui.language": {
        "tr": "Dil",
        "en": "Language",
    },
    "dash.guidance.typical_workflow_title": {
        "tr": "Tipik iş akışı",
        "en": "Typical workflow",
    },
    "dash.guidance.next_step_title": {
        "tr": "Önerilen sonraki adım",
        "en": "Next recommended step",
    },
    "dash.guidance.prereq_title": {
        "tr": "Önce yapılacaklar",
        "en": "What to do first",
    },
    # --- Dash Compare workspace ---
    "dash.compare.title": {"tr": "Karşılaştırma Alanı", "en": "Compare Workspace"},
    "dash.compare.caption": {
        "tr": (
            "İşlenmiş eğrilerin en iyi sürümünü veya ham içe aktarım verisini üst üste koy; seçili koşularda toplu şablon çalıştır."
        ),
        "en": (
            "Overlay runs with best-available processed curves or raw import data; run batch templates across selected datasets."
        ),
    },
    "dash.compare.badge": {"tr": "Karşılaştır", "en": "Compare"},
    "dash.compare.guidance_what_title": {"tr": "Bu sayfa ne yapar?", "en": "What this page does"},
    "dash.compare.guidance_what_body": {
        "tr": (
            "Analiz türünü ve koşuları seçerek yeniden kullanılabilir bir karşılaştırma alanı oluşturun; ardından "
            "eğrileri en iyi sürüm veya ham modda üst üste yerleştirin."
        ),
        "en": (
            "Build a reusable compare workspace by selecting analysis type and runs, then overlaying curves in "
            "best-available or raw mode."
        ),
    },
    "dash.compare.workflow_step1": {
        "tr": "İçe aktardığınız koşularla uyumlu bir analiz türü seçin.",
        "en": "Choose an analysis type compatible with your imported runs.",
    },
    "dash.compare.workflow_step2": {
        "tr": "Koşuları seçin ve üst üste bindirmeyi gözden geçirin (karşılaştırma için 2+ koşu önerilir).",
        "en": "Select runs and review the overlay (2+ runs recommended for comparison).",
    },
    "dash.compare.workflow_step3": {
        "tr": "Karşılaştırma alanını kaydedin; ardından raporda bağlam için Rapor Merkezi'ni açın.",
        "en": "Save compare workspace, then open Report Center to include compare context.",
    },
    "dash.compare.usage_title": {"tr": "Kullanım notları", "en": "Usage notes"},
    "dash.compare.usage_bullet1": {
        "tr": "Üst üste karşılaştırma için en az iki seçili koşu gerekir.",
        "en": "Overlay comparison requires at least two selected runs.",
    },
    "dash.compare.usage_bullet2": {
        "tr": "Toplu çalıştırma bir veya daha fazla seçili koşu ile yapılabilir.",
        "en": "Batch execution can run with one or more selected runs.",
    },
    "dash.compare.next_step_body": {
        "tr": "Rapor çıktıları üretmeden önce Karşılaştırma Alanını kaydedin.",
        "en": "Save Compare Workspace before generating report outputs.",
    },
    "dash.compare.label_analysis_type": {"tr": "Analiz türü", "en": "Analysis Type"},
    "dash.compare.label_selected_runs": {"tr": "Seçili koşular", "en": "Selected Runs"},
    "dash.compare.label_overlay_signal": {"tr": "Bindirme sinyali", "en": "Overlay signal"},
    "dash.compare.label_workspace_notes": {"tr": "Çalışma alanı notları", "en": "Workspace Notes"},
    "dash.compare.overlay_best": {"tr": "En iyi kullanılabilir (analiz durumu)", "en": "Best available (analysis state)"},
    "dash.compare.overlay_raw": {"tr": "Ham içe aktarım verisi", "en": "Raw import data"},
    "dash.compare.btn_save_workspace": {"tr": "Karşılaştırma alanını kaydet", "en": "Save Compare Workspace"},
    "dash.compare.batch_title": {"tr": "Toplu şablon", "en": "Batch template"},
    "dash.compare.batch_label_template": {"tr": "İş akışı şablonu", "en": "Workflow template"},
    "dash.compare.batch_run_btn": {"tr": "Seçili koşularda toplu çalıştır", "en": "Run batch on selected runs"},
    "dash.compare.save_ok": {"tr": "Karşılaştırma alanı kaydedildi.", "en": "Compare workspace saved."},
    "dash.compare.save_fail": {"tr": "Kaydetme başarısız: {error}", "en": "Compare workspace save failed: {error}"},
    "dash.compare.batch_need_selection": {
        "tr": "Toplu çalıştırma için en az bir veri seti seçin.",
        "en": "Select at least one dataset for batch run.",
    },
    "dash.compare.batch_fail": {"tr": "Toplu çalıştırma başarısız: {error}", "en": "Batch run failed: {error}"},
    "dash.compare.batch_complete": {
        "tr": "Toplu işlem tamamlandı: kaydedilen={saved}, engellenen={blocked}, başarısız={failed}.",
        "en": "Batch complete: saved={saved}, blocked={blocked}, failed={failed}.",
    },
    "dash.compare.prereq_workspace_body": {
        "tr": "Karşılaştırmayı kullanmadan önce veri setlerini içe aktarın ve analiz sonuçlarını kaydedin.",
        "en": "No active workspace. Import datasets and save analysis results before using Compare.",
    },
    "dash.compare.prereq_workspace_title": {"tr": "Çalışma alanı gerekli", "en": "Workspace required"},
    "dash.compare.prereq_datasets_body": {
        "tr": "Önce koşuları içe aktarın, ardından karşılaştırma bindirmelerini oluşturmak için buraya dönün.",
        "en": "No datasets loaded. Import runs first, then return to build compare overlays.",
    },
    "dash.compare.prereq_datasets_title": {"tr": "Veri seti gerekli", "en": "Datasets required"},
    "dash.compare.prereq_no_eligible_body": {
        "tr": "Veri setleri yüklü ancak kararlı karşılaştırma türleri için uygun değil. Veri türlerini İçe Aktar/Proje üzerinden kontrol edin.",
        "en": "Datasets are loaded but none are eligible for stable compare analysis types. Check dataset data types in Import/Project.",
    },
    "dash.compare.prereq_no_eligible_title": {"tr": "Uygun analiz türü yok", "en": "No eligible analysis type"},
    "dash.compare.prereq_need_analysis_body": {
        "tr": "Uygun koşuları yüklemek ve karşılaştırma alanını kurmak için bir analiz türü seçin.",
        "en": "Select an analysis type to load eligible runs and build the compare workspace.",
    },
    "dash.compare.prereq_need_analysis_title": {"tr": "Analiz türü gerekli", "en": "Analysis type required"},
    "dash.compare.prereq_overlay_runs_body": {
        "tr": "Bindirme için en az iki koşu seçin. Toplu çalıştırma tek seçili koşu ile de çalışabilir.",
        "en": "Select at least two runs to build an overlay. Batch execution can still run with one selected run.",
    },
    "dash.compare.prereq_overlay_runs_title": {"tr": "Bindirme için daha fazla koşu", "en": "More runs needed for overlay"},
    "dash.compare.overlay_build_fail": {
        "tr": "Mevcut seçim için bindirme oluşturulamadı (eksik veri sütunları veya boş analiz durumu).",
        "en": "Could not build an overlay for the current selection (missing data columns or empty analysis state).",
    },
    "dash.compare.figure_caption_best": {"tr": "En iyi kullanılabilir (analiz durumu)", "en": "Best available (analysis state)"},
    "dash.compare.figure_caption_raw": {"tr": "Ham içe aktarım verisi", "en": "Raw import data"},
    "dash.compare.figure_title": {"tr": "{analysis} karşılaştırma — {mode}", "en": "{analysis} Compare — {mode}"},
    "dash.compare.trace_raw_fallback": {"tr": "{label} (ham yedek)", "en": "{label} (raw fallback)"},
    "dash.compare.trace_raw": {"tr": "{label} (ham)", "en": "{label} (raw)"},
    "dash.compare.summary_title": {"tr": "Çalışma alanı özeti", "en": "Workspace Summary"},
    "dash.compare.no_runs_selected": {"tr": "Henüz koşu seçilmedi.", "en": "No runs selected yet."},
    "dash.compare.saved_preview_title": {"tr": "Kayıtlı sonuç önizlemesi", "en": "Saved Result Preview"},
    "dash.compare.no_saved_for_runs": {
        "tr": "Seçili koşular için henüz kayıtlı sonuç yok.",
        "en": "No saved results for the selected runs yet.",
    },
    "dash.compare.batch_panel_title": {"tr": "Son toplu işlem", "en": "Last batch"},
    "dash.compare.batch_outcomes": {
        "tr": "Sonuçlar: kaydedilen={saved}, engellenen={blocked}, başarısız={failed}.",
        "en": "Outcomes: saved={saved}, blocked={blocked}, failed={failed}.",
    },
    "dash.compare.batch_template_line": {"tr": "Şablon: {name}", "en": "Template: {name}"},
    "dash.compare.batch_no_record": {
        "tr": "Bu çalışma alanı için henüz toplu çalıştırma kaydı yok.",
        "en": "No batch run recorded yet for this workspace.",
    },
    "dash.compare.summary_yes": {"tr": "Evet", "en": "Yes"},
    "dash.compare.summary_no": {"tr": "Hayır", "en": "No"},
    # --- Dash Export / Report center ---
    "dash.export.title": {"tr": "Rapor Merkezi", "en": "Report Center"},
    "dash.export.caption": {
        "tr": "Rapor yüklerini önizleyin, markayı düzenleyin, veri/sonuç dışa aktarın ve markalı raporlar üretin.",
        "en": "Preview report payloads, edit branding, export data/results, and generate branded reports.",
    },
    "dash.export.badge": {"tr": "Dışa aktar", "en": "Export"},
    "dash.export.guidance_what_title": {"tr": "Bu sayfa ne yapar?", "en": "What this page does"},
    "dash.export.guidance_what_body": {
        "tr": (
            "Etkin çalışma alanından dışa aktarma çıktıları hazırlayın: ham veri tabloları, normalize sonuçlar ve "
            "markalı DOCX/PDF raporları."
        ),
        "en": (
            "Prepare export artifacts from the active workspace: raw data tables, normalized results, and branded "
            "DOCX/PDF reports."
        ),
    },
    "dash.export.workflow_step1": {
        "tr": "Proje sayfasında çalışma alanı hazır olduğunu doğrulayın (veri setleri/sonuçlar mevcut).",
        "en": "Verify workspace readiness in Project (datasets/results available).",
    },
    "dash.export.workflow_step2": {
        "tr": "Marka alanlarını ayarlayın ve dışa aktarma seçimlerini onaylayın.",
        "en": "Set branding fields and confirm export selections.",
    },
    "dash.export.workflow_step3": {
        "tr": "Veri/sonuçları dışa aktarın veya rapor paketini oluşturun.",
        "en": "Export data/results or generate the report package.",
    },
    "dash.export.next_step_body": {
        "tr": "Dışa aktarmalar eksikse önce eksik analiz sonuçlarını kaydedin ve bu sayfaya dönün.",
        "en": "If exports are incomplete, save missing analysis results first and return to this page.",
    },
    "dash.export.tab_export_data": {"tr": "Veriyi dışa aktar", "en": "Export Data"},
    "dash.export.tab_export_results": {"tr": "Sonuçları dışa aktar", "en": "Export Results"},
    "dash.export.tab_generate_report": {"tr": "Rapor oluştur", "en": "Generate Report"},
    "dash.export.section_raw_data": {"tr": "Ham / içe aktarılan veriyi dışa aktar", "en": "Export Raw / Imported Data"},
    "dash.export.section_results": {"tr": "Normalize sonuçları dışa aktar", "en": "Export Normalized Results"},
    "dash.export.section_report": {"tr": "Markalı rapor oluştur", "en": "Generate Branded Report"},
    "dash.export.label_csv": {"tr": "CSV", "en": "CSV"},
    "dash.export.label_xlsx": {"tr": "Excel (XLSX)", "en": "Excel (XLSX)"},
    "dash.export.label_docx": {"tr": "DOCX", "en": "DOCX"},
    "dash.export.label_pdf": {"tr": "PDF", "en": "PDF"},
    "dash.export.label_select_datasets": {"tr": "Veri setlerini seçin", "en": "Select datasets"},
    "dash.export.label_select_results": {"tr": "Sonuç kayıtlarını seçin", "en": "Select result records"},
    "dash.export.btn_prepare_data": {"tr": "Veri dışa aktarmayı hazırla", "en": "Prepare Data Export"},
    "dash.export.btn_prepare_results": {"tr": "Sonuç dışa aktarmayı hazırla", "en": "Prepare Result Export"},
    "dash.export.btn_prepare_report": {"tr": "Raporu hazırla", "en": "Prepare Report"},
    "dash.export.label_include_figures": {"tr": "Görselleri dahil et", "en": "Include figures"},
    "dash.export.branding_title": {"tr": "Marka", "en": "Branding"},
    "dash.export.branding_report_title": {"tr": "Rapor başlığı", "en": "Report Title"},
    "dash.export.branding_company": {"tr": "Şirket", "en": "Company"},
    "dash.export.branding_lab": {"tr": "Laboratuvar", "en": "Laboratory"},
    "dash.export.branding_analyst": {"tr": "Analist", "en": "Analyst"},
    "dash.export.branding_notes": {"tr": "Varsayılan rapor notları", "en": "Default Report Notes"},
    "dash.export.branding_logo": {"tr": "Logo (PNG/JPG)", "en": "Logo (PNG/JPG)"},
    "dash.export.branding_upload_logo": {"tr": "Logo yükle", "en": "Upload logo"},
    "dash.export.btn_save_branding": {"tr": "Markayı kaydet", "en": "Save Branding"},
    "dash.export.prereq_workspace_body": {
        "tr": "Dışa aktarmaları hazırlamadan önce veri içe aktarın ve sonuçları kaydedin.",
        "en": "No active workspace. Import data and save results before preparing exports.",
    },
    "dash.export.prereq_workspace_title": {"tr": "Çalışma alanı gerekli", "en": "Workspace required"},
    "dash.export.error_prefix": {"tr": "Hata:", "en": "Error:"},
    "dash.export.metric_datasets": {"tr": "Veri setleri", "en": "Datasets"},
    "dash.export.metric_stable": {"tr": "Kararlı analizler", "en": "Stable Analyses"},
    "dash.export.metric_preview": {"tr": "Önizleme analizleri", "en": "Preview Analyses"},
    "dash.export.metric_outputs": {"tr": "Desteklenen çıktılar", "en": "Supported Outputs"},
    "dash.export.preview_branding": {"tr": "Marka önizlemesi", "en": "Branding Preview"},
    "dash.export.preview_compare": {"tr": "Karşılaştırma alanı önizlemesi", "en": "Compare Workspace Preview"},
    "dash.export.preview_report_pkg": {"tr": "Rapor paketi", "en": "Report Package"},
    "dash.export.preview_li_report_title": {"tr": "Rapor başlığı: {value}", "en": "Report Title: {value}"},
    "dash.export.preview_li_company": {"tr": "Şirket: {value}", "en": "Company: {value}"},
    "dash.export.preview_li_lab": {"tr": "Laboratuvar: {value}", "en": "Laboratory: {value}"},
    "dash.export.preview_li_analyst": {"tr": "Analist: {value}", "en": "Analyst: {value}"},
    "dash.export.not_set": {"tr": "Ayarlanmadı", "en": "Not set"},
    "dash.export.analysis_type": {"tr": "Analiz türü: {value}", "en": "Analysis Type: {value}"},
    "dash.export.selected_runs": {"tr": "Seçili koşular: {value}", "en": "Selected Runs: {value}"},
    "dash.export.no_compare_notes": {"tr": "Henüz karşılaştırma notu yok.", "en": "No compare notes yet."},
    "dash.export.none": {"tr": "Yok", "en": "None"},
    "dash.export.na": {"tr": "Yok", "en": "N/A"},
    "dash.export.default_report_title": {
        "tr": "MaterialScope Profesyonel Rapor",
        "en": "MaterialScope Professional Report",
    },
    "dash.export.prereq_results_body": {
        "tr": "Sonuç tabloları veya raporları dışa aktarmadan önce analizleri çalıştırıp sonuçları kaydedin.",
        "en": "No normalized result records are saved yet. Run analyses and save results before exporting result tables or reports.",
    },
    "dash.export.prereq_results_title": {
        "tr": "Rapor çıktıları için sonuç gerekli",
        "en": "Results required for report outputs",
    },
    "dash.export.records_incomplete": {
        "tr": "Bazı kayıtlar eksik ve atlanacak.",
        "en": "Some saved records are incomplete and will be skipped.",
    },
    "dash.export.branding_save_fail": {"tr": "Marka kaydı başarısız: {error}", "en": "Branding save failed: {error}"},
    "dash.export.branding_save_ok": {
        "tr": "Marka güncel çalışma alanı için kaydedildi.",
        "en": "Branding updated for the current workspace.",
    },
    "dash.export.logo_current": {"tr": "Mevcut logo: {name}", "en": "Current logo: {name}"},
    "dash.export.prereq_workspace_data": {
        "tr": "Ham/içe aktarılan veriyi dışa aktarmadan önce veri setlerini yükleyin.",
        "en": "No active workspace. Load datasets before exporting raw/imported data.",
    },
    "dash.export.prereq_title_select_datasets": {
        "tr": "Veri seti seçimi gerekli",
        "en": "Dataset selection required",
    },
    "dash.export.prereq_title_select_results": {
        "tr": "Sonuç seçimi gerekli",
        "en": "Result selection required",
    },
    "dash.export.prereq_select_datasets": {
        "tr": "Ham/içe aktarılan veri dışa aktarımı için en az bir veri seti seçin.",
        "en": "Select at least one dataset for raw/imported data export.",
    },
    "dash.export.prereq_workspace_results": {
        "tr": "Sonuç tablolarını dışa aktarmadan önce analiz sonuçlarını kaydedin.",
        "en": "No active workspace. Save analysis results before exporting result tables.",
    },
    "dash.export.prereq_select_results": {
        "tr": "Sonuç dışa aktarımı için en az bir kayıtlı sonuç seçin.",
        "en": "Select at least one saved result record for result export.",
    },
    "dash.export.prereq_workspace_report": {
        "tr": "Rapor oluşturmadan önce analiz sonuçlarını kaydedin.",
        "en": "No active workspace. Save analysis results before generating reports.",
    },
    "dash.export.prereq_select_report_results": {
        "tr": "Rapor oluşturmak için en az bir kayıtlı sonuç kaydı seçin.",
        "en": "Select at least one saved result record to generate a report.",
    },
    "dash.export.data_export_fail": {"tr": "Veri dışa aktarma başarısız: {error}", "en": "Data export failed: {error}"},
    "dash.export.data_csv_ready": {"tr": "CSV hazır: {key}", "en": "CSV ready: {key}"},
    "dash.export.data_zip_ready": {"tr": "{count} CSV dosyası ZIP olarak hazırlandı.", "en": "Prepared {count} CSV files as ZIP."},
    "dash.export.data_xlsx_ready": {"tr": "Çalışma kitabı hazır: {count} veri seti.", "en": "Workbook ready: {count} dataset(s)."},
    "dash.export.result_export_fail": {"tr": "Sonuç dışa aktarma başarısız: {error}", "en": "Result export failed: {error}"},
    "dash.export.result_ready": {
        "tr": "{otype} hazır: {count} sonuç.",
        "en": "{otype} ready: {count} results.",
    },
    "dash.export.report_export_fail": {"tr": "Rapor dışa aktarma başarısız: {error}", "en": "Report export failed: {error}"},
    # --- Dash Import (home) ---
    "dash.home.title": {"tr": "Veri içe aktarma", "en": "Data Import"},
    "dash.home.caption": {
        "tr": "Modalite öncelikli sihirbaz: teknik seçin, yükleyin, eşleyin, gözden geçirin ve onaylayın.",
        "en": "Modality-first import wizard: select technique, upload, map, review, and confirm.",
    },
    "dash.home.badge": {"tr": "İçe aktar", "en": "Import"},
    "dash.home.guidance_title": {"tr": "Modalite öncelikli içe aktarma", "en": "Modality-first import"},
    "dash.home.guidance_body": {
        "tr": (
            "Veriyi yüklemeden önce ölçüm tekniğini seçin. Ayrıştırıcının sütun algılama, birim doğrulama ve "
            "bilimsel tutarlılık kontrolleri için tekniğe özel kurallar kullanmasını sağlar."
        ),
        "en": (
            "Select a measurement technique before uploading data. This ensures the parser uses technique-specific "
            "rules for column detection, unit validation, and scientific credibility checks."
        ),
    },
    "dash.home.mapping_none": {"tr": "-- Yok --", "en": "-- None --"},
    "dash.home.metric_loaded_runs": {"tr": "Yüklenen koşular", "en": "Loaded Runs"},
    "dash.home.metric_type_breakdown": {"tr": "D / T / DTA / F / R / X", "en": "D / T / DTA / F / R / X"},
    "dash.home.metric_vendors": {"tr": "Üreticiler", "en": "Vendors"},
    "dash.home.step1_title": {"tr": "Ölçüm tekniğini seçin", "en": "Select Measurement Technique"},
    "dash.home.step1_intro": {
        "tr": (
            "İçe aktarmak üzere olduğunuz veri için analiz tekniğini seçin. Bu, beklenen eksen rolleri, birimler ve "
            "doğrulama kurallarını belirler."
        ),
        "en": (
            "Choose the analysis technique for the data you are about to import. This determines the expected axis "
            "roles, units, and validation rules."
        ),
    },
    "dash.home.step2_title": {"tr": "Veri yükle", "en": "Upload Data"},
    "dash.home.upload_drop": {"tr": "Dosyaları buraya sürükleyin veya ", "en": "Drag and drop files here, or "},
    "dash.home.upload_browse": {"tr": "göz at", "en": "browse"},
    "dash.home.sample_section_title": {"tr": "Örnek veri yükle", "en": "Load Sample Data"},
    "dash.home.sample_section_intro": {
        "tr": "Test için yerleşik örnek veri setlerini yükleyin. Modaliteleri önceden etiketlenmiştir.",
        "en": "Load built-in sample datasets for testing. These are pre-tagged with their modality.",
    },
    "dash.home.btn_back": {"tr": "Geri", "en": "Back"},
    "dash.home.btn_next_preview": {"tr": "İleri: Önizleme", "en": "Next: Preview"},
    "dash.home.btn_next_map": {"tr": "İleri: Sütun eşleme", "en": "Next: Map Columns"},
    "dash.home.btn_next_review": {"tr": "İleri: Gözden geçir", "en": "Next: Review"},
    "dash.home.btn_next_confirm": {"tr": "İleri: İçe aktarmayı onayla", "en": "Next: Confirm Import"},
    "dash.home.step3_title": {"tr": "Ham veri önizlemesi", "en": "Raw Data Preview"},
    "dash.home.step4_title": {"tr": "Sütun eşleme", "en": "Column Mapping"},
    "dash.home.step4_intro": {
        "tr": (
            "Ham sütunları standart eksen/sinyal rollerine eşleyin. Değerler modaliteye duyarlı algılamadan "
            "önceden doldurulur."
        ),
        "en": (
            "Map raw columns to standardized axis/signal roles. Values are pre-filled from modality-aware detection."
        ),
    },
    "dash.home.label_time_optional": {"tr": "Zaman sütunu (isteğe bağlı)", "en": "Time Column (optional)"},
    "dash.home.label_sample_name": {"tr": "Numune adı", "en": "Sample Name"},
    "dash.home.label_sample_mass": {"tr": "Numune kütlesi (mg)", "en": "Sample Mass (mg)"},
    "dash.home.label_xrd_wavelength": {"tr": "XRD dalga boyu (Å)", "en": "XRD Wavelength (Å)"},
    "dash.home.step5_title": {"tr": "Birim ve metadata gözden geçirmesi", "en": "Unit & Metadata Review"},
    "dash.home.step6_title": {"tr": "Doğrulama özeti", "en": "Validation Summary"},
    "dash.home.btn_confirm_import": {"tr": "İçe aktarmayı onayla", "en": "Confirm Import"},
    "dash.home.loaded_datasets_title": {"tr": "Yüklenen veri setleri", "en": "Loaded Datasets"},
    "dash.home.label_active_dataset": {"tr": "Etkin veri seti", "en": "Active Dataset"},
    "dash.home.btn_remove": {"tr": "Kaldır", "en": "Remove"},
    "dash.home.modality_selected": {"tr": "Seçildi: {modality} — {desc}", "en": "Selected: {modality} -- {desc}"},
    "dash.home.upload_queued_dup": {"tr": "Dosyalar içe aktarma önizlemesi için zaten kuyrukta.", "en": "Files already queued for import preview."},
    "dash.home.upload_queued_ok": {"tr": "Önizleme için kuyruğa alındı: {files}", "en": "Queued for preview: {files}"},
    "dash.home.pending_help_empty": {
        "tr": "Önizleme, eşleme ve çalışma alanına içe aktarma için bir dosya yükleyin.",
        "en": "Upload a file to preview, map, and import into the workspace.",
    },
    "dash.home.pending_help_count": {"tr": "{count} bekleyen dosya önizleme ve içe aktarma için hazır.", "en": "{count} pending file(s) ready for preview and import."},
    "dash.home.prereq_select_file_body": {
        "tr": "Ham veriyi önizlemek için bir dosya yükleyin ve seçin.",
        "en": "Upload a file and select it to preview raw data.",
    },
    "dash.home.prereq_select_file_title": {"tr": "Dosya seçilmedi", "en": "No file selected"},
    "dash.home.error_prefix": {"tr": "Hata:", "en": "Error:"},
    "dash.home.prereq_workspace_import_body": {
        "tr": "Çalışma alanı yok. Çalışma alanı oluşturmak veya yüklemek için Proje Alanı'nı açın, ardından İçe Aktar'a dönün.",
        "en": "No active workspace. Open Project Workspace to create or load a workspace, then return to Import.",
    },
    "dash.home.prereq_workspace_import_title": {"tr": "Çalışma alanı gerekli", "en": "Workspace required"},
    "dash.home.prereq_no_datasets_body": {
        "tr": "Henüz veri seti yok. Çalışma alanını doldurmak için dosya yükleyin veya örnek veri yükleyin.",
        "en": "No datasets are loaded yet. Upload files or load sample datasets to populate this workspace.",
    },
    "dash.home.prereq_no_datasets_title": {"tr": "Çalışma alanında veri seti yok", "en": "No datasets in workspace"},
    "dash.home.remove_fail": {"tr": "Kaldırma başarısız: {error}", "en": "Remove failed: {error}"},
    "dash.home.remove_ok": {"tr": "Veri seti kaldırıldı: {key}", "en": "Removed dataset: {key}"},
    "dash.home.prereq_workspace_detail_body": {
        "tr": "Çalışma alanı yok. Veri setlerini içe aktarmak için önce Proje'de çalışma alanı başlatın veya yükleyin.",
        "en": "No active workspace. Start or load a workspace in Project, then import datasets here.",
    },
    "dash.home.prereq_select_dataset_body": {
        "tr": "Metadata, önizleme ve hızlı grafik için Yüklenen Veri Setleri panelinden etkin bir veri seti seçin.",
        "en": "Select an active dataset from the Loaded Datasets panel to inspect metadata, preview, and quick plot.",
    },
    "dash.home.prereq_select_dataset_title": {"tr": "Veri seti seçin", "en": "Select a dataset"},
    "dash.home.detail_metadata": {"tr": "Metadata", "en": "Metadata"},
    "dash.home.detail_columns": {"tr": "Sütun eşlemesi", "en": "Column Mapping"},
    "dash.home.detail_preview": {"tr": "Veri önizlemesi", "en": "Data Preview"},
    "dash.home.detail_stats": {"tr": "İstatistikler", "en": "Statistics"},
    "dash.home.detail_quick_view": {"tr": "Hızlı görünüm", "en": "Quick View"},
    "dash.home.sample_loaded": {"tr": "Örnek yüklendi: {name}", "en": "Loaded sample: {name}"},
    "dash.home.axis_column_generic": {"tr": "Eksen sütunu", "en": "Axis Column"},
    "dash.home.signal_column_generic": {"tr": "Sinyal sütunu", "en": "Signal Column"},
    "dash.home.heating_rate_label": {"tr": "Isıtma hızı (°C/dk)", "en": "Heating Rate (°C/min)"},
    "dash.home.stepper.step1_label": {"tr": "1. Teknik", "en": "1. Technique"},
    "dash.home.stepper.step1_desc": {"tr": "Ölçüm tekniğini seçin", "en": "Select measurement technique"},
    "dash.home.stepper.step2_label": {"tr": "2. Yükleme", "en": "2. Upload"},
    "dash.home.stepper.step2_desc": {"tr": "Dosya yükleyin veya örnek veri yükleyin", "en": "Upload file or load sample data"},
    "dash.home.stepper.step3_label": {"tr": "3. Önizleme", "en": "3. Preview"},
    "dash.home.stepper.step3_desc": {"tr": "Ham veriyi ve algılanan biçimi inceleyin", "en": "Inspect raw data and detected format"},
    "dash.home.stepper.step4_label": {"tr": "4. Eşleme", "en": "4. Mapping"},
    "dash.home.stepper.step4_desc": {"tr": "Sütunları eksen/sinyal rollerine eşleyin", "en": "Map columns to axis/signal roles"},
    "dash.home.stepper.step5_label": {"tr": "5. Gözden geçirme", "en": "5. Review"},
    "dash.home.stepper.step5_desc": {"tr": "Birimleri, metadata ve uyarıları gözden geçirin", "en": "Review units, metadata, and warnings"},
    "dash.home.stepper.step6_label": {"tr": "6. Onay", "en": "6. Confirm"},
    "dash.home.stepper.step6_desc": {"tr": "Doğrula ve içe aktarmayı onayla", "en": "Validate and confirm import"},
    "dash.home.modality_axis.dsc": {"tr": "Sıcaklık sütunu", "en": "Temperature Column"},
    "dash.home.modality_axis.tga": {"tr": "Sıcaklık sütunu", "en": "Temperature Column"},
    "dash.home.modality_axis.dta": {"tr": "Sıcaklık sütunu", "en": "Temperature Column"},
    "dash.home.modality_axis.ftir": {"tr": "Dalga sayısı sütunu", "en": "Wavenumber Column"},
    "dash.home.modality_axis.raman": {"tr": "Raman kayması sütunu", "en": "Raman Shift Column"},
    "dash.home.modality_axis.xrd": {"tr": "2θ sütunu", "en": "2θ Column"},
    "dash.home.modality_signal.dsc": {"tr": "Isı akışı sütunu", "en": "Heat Flow Column"},
    "dash.home.modality_signal.tga": {"tr": "Kütle sütunu", "en": "Mass Column"},
    "dash.home.modality_signal.dta": {"tr": "ΔT sütunu", "en": "ΔT Column"},
    "dash.home.modality_signal.ftir": {"tr": "Soğurganlık/geçirgenlik sütunu", "en": "Absorbance/Transmittance Column"},
    "dash.home.modality_signal.raman": {"tr": "Şiddet sütunu", "en": "Intensity Column"},
    "dash.home.modality_signal.xrd": {"tr": "Şiddet sütunu", "en": "Intensity Column"},
    "dash.home.modality_desc.dsc": {
        "tr": "Diferansiyel tarama kalorimetrisi — Sıcaklık / Isı akışı (mW/mg)",
        "en": "Differential Scanning Calorimetry -- Temperature vs Heat Flow (mW/mg)",
    },
    "dash.home.modality_desc.tga": {
        "tr": "Termogravimetrik analiz — Sıcaklık / Kütle (%/mg)",
        "en": "Thermogravimetric Analysis -- Temperature vs Mass (%/mg)",
    },
    "dash.home.modality_desc.dta": {
        "tr": "Diferansiyel termal analiz — Sıcaklık / ΔT (µV)",
        "en": "Differential Thermal Analysis -- Temperature vs ΔT (µV)",
    },
    "dash.home.modality_desc.ftir": {
        "tr": "Fourier dönüşümlü kızılötesi — Dalga sayısı (cm⁻¹) / Soğurganlık veya geçirgenlik",
        "en": "Fourier Transform Infrared -- Wavenumber (cm⁻¹) vs Absorbance/Transmittance",
    },
    "dash.home.modality_desc.raman": {
        "tr": "Raman spektroskopisi — Raman kayması (cm⁻¹) / Şiddet",
        "en": "Raman Spectroscopy -- Raman Shift (cm⁻¹) vs Intensity",
    },
    "dash.home.modality_desc.xrd": {
        "tr": "X-ışını difraksiyonu — 2θ (derece) / Şiddet (sayım)",
        "en": "X-Ray Diffraction -- 2θ (degrees) vs Intensity (counts)",
    },
    "dash.home.validation_badge.pass": {"tr": "GEÇTİ", "en": "PASS"},
    "dash.home.validation_badge.pass_with_review": {"tr": "İNCELE", "en": "REVIEW"},
    "dash.home.validation_badge.warn": {"tr": "UYARI", "en": "WARN"},
    "dash.home.validation_badge.fail": {"tr": "HATA", "en": "FAIL"},
    "dash.home.validation_badge.unknown": {"tr": "BİLİNMEYEN", "en": "UNKNOWN"},
    "dash.home.validation_text.pass": {
        "tr": "Tüm kontroller geçti. İçe aktarmaya hazır.",
        "en": "All checks passed. Ready to import.",
    },
    "dash.home.validation_text.pass_with_review": {
        "tr": "Veri içe aktarılabilir ancak inceleme bayrakları var. Onaylamadan önce uyarıları inceleyin.",
        "en": "Data is importable but review flags detected. Inspect warnings before confirming.",
    },
    "dash.home.validation_text.warn": {
        "tr": "Uyarılar algılandı. Onaylamadan önce gözden geçirin.",
        "en": "Warnings detected. Review before confirming.",
    },
    "dash.home.validation_text.fail": {
        "tr": "Engelleyici sorunlar var. Geri dönüp sütun eşlemesini düzeltin.",
        "en": "Blocking issues detected. Go back and fix column mapping.",
    },
    "dash.home.label_import_status": {"tr": "İçe aktarma durumu:", "en": "Import Status:"},
    "dash.home.label_warnings_block": {"tr": "Uyarılar:", "en": "Warnings:"},
    "dash.home.label_summary": {"tr": "Özet:", "en": "Summary:"},
    "dash.home.summary_li_technique": {"tr": "Teknik: {value}", "en": "Technique: {value}"},
    "dash.home.summary_li_axis": {"tr": "Eksen sütunu: {value}", "en": "Axis column: {value}"},
    "dash.home.summary_li_signal": {"tr": "Sinyal sütunu: {value}", "en": "Signal column: {value}"},
    "dash.home.summary_li_confidence": {"tr": "Güven: {value}", "en": "Confidence: {value}"},
    "dash.home.review_th_role": {"tr": "Rol", "en": "Role"},
    "dash.home.review_th_column": {"tr": "Sütun", "en": "Column"},
    "dash.home.review_td_axis": {"tr": "Eksen", "en": "Axis"},
    "dash.home.review_td_signal": {"tr": "Sinyal", "en": "Signal"},
    "dash.home.review_td_time": {"tr": "Zaman", "en": "Time"},
    "dash.home.meta_th_field": {"tr": "Alan", "en": "Field"},
    "dash.home.meta_th_value": {"tr": "Değer", "en": "Value"},
    "dash.home.meta_modality": {"tr": "Modalite", "en": "Modality"},
    "dash.home.meta_sample_name": {"tr": "Numune adı", "en": "Sample Name"},
    "dash.home.meta_sample_mass": {"tr": "Numune kütlesi", "en": "Sample Mass"},
    "dash.home.meta_heating_rate": {"tr": "Isıtma hızı", "en": "Heating Rate"},
    "dash.home.meta_wavelength": {"tr": "Dalga boyu", "en": "Wavelength"},
    "dash.home.meta_unknown": {"tr": "Bilinmiyor", "en": "Unknown"},
    "dash.home.meta_not_set": {"tr": "Ayarlanmadı", "en": "Not set"},
    "dash.home.meta_mass_fmt": {"tr": "{value} mg", "en": "{value} mg"},
    "dash.home.meta_rate_fmt": {"tr": "{value} °C/dk", "en": "{value} °C/min"},
    "dash.home.meta_wavelength_fmt": {"tr": "{value} Å", "en": "{value} Å"},
    "dash.home.label_unit_review": {"tr": "Birim gözden geçirmesi:", "en": "Unit Review:"},
    "dash.home.label_metadata_summary": {"tr": "Metadata özeti:", "en": "Metadata Summary:"},
    "dash.home.label_warnings_flags": {"tr": "Uyarılar ve bayraklar:", "en": "Warnings & Flags:"},
    "dash.home.no_warnings": {"tr": "Uyarı algılanmadı.", "en": "No warnings detected."},
    "dash.home.confidence_badge": {"tr": "Güven: {value}", "en": "Confidence: {value}"},
    "dash.home.preview_failed": {"tr": "Önizleme başarısız: {error}", "en": "Preview failed: {error}"},
    "dash.home.preview_status": {
        "tr": "Önizleme hazır: {file} | satır={rows} | algılanan tür={dtype} | güven={conf}",
        "en": "Preview ready: {file} | rows={rows} | detected type={dtype} | confidence={conf}",
    },
    "dash.home.preview_warnings_suffix": {"tr": " | {n} uyarı", "en": " | {n} warning(s)"},
    "dash.home.prereq_no_review_data_body": {
        "tr": "Gözden geçirme verisi yok.",
        "en": "No review data available.",
    },
    "dash.home.title_no_data": {"tr": "Veri yok", "en": "No data"},
    "dash.home.prereq_no_preview_for_review_body": {
        "tr": "Önizleme verisi yok. Geri dönüp bir dosya yükleyin.",
        "en": "No preview data available. Go back and upload a file.",
    },
    "dash.home.prereq_preview_required_title": {"tr": "Önizleme gerekli", "en": "Preview required"},
    "dash.home.prereq_preview_required_body": {
        "tr": "İçe aktarmadan önce bekleyen bir dosya seçerek önizleme oluşturun.",
        "en": "Select a pending file to build a preview before importing.",
    },
    "dash.home.import_axis_signal_required": {
        "tr": "Eksen ve sinyal sütunları zorunludur.",
        "en": "Axis and signal columns are required.",
    },
    "dash.home.import_mapping_stale": {
        "tr": "Sütun eşlemesi güncel değil. Dosyayı yeniden seçip eksen ve sinyal sütunlarını yeniden eşleyin.",
        "en": "Column mapping is stale. Select the file again, then re-map axis and signal columns.",
    },
    "dash.home.import_failed": {"tr": "İçe aktarma başarısız: {error}", "en": "Import failed: {error}"},
    "dash.home.import_hint_wavenumber": {
        "tr": " İpucu: eksen aralığı dalga sayısı verisine benziyor — FTIR veya RAMAN seçmeyi deneyin.",
        "en": " Hint: the axis range looks like wavenumber data -- try selecting FTIR or RAMAN.",
    },
    "dash.home.import_hint_monotonic": {
        "tr": " İpucu: eksen monoton değil — sütun eşlemesini kontrol edin veya spektral veri için FTIR/RAMAN deneyin.",
        "en": " Hint: the axis is not monotonic -- check column mapping or try FTIR/RAMAN for spectral data.",
    },
    "dash.home.import_success": {
        "tr": "İçe aktarıldı: {name} ({dtype}).",
        "en": "Imported: {name} ({dtype}).",
    },
    "dash.home.import_success_next": {
        "tr": "Sonraki: durumu Proje Çalışma Alanı'nda doğrulayın.",
        "en": "Next: confirm workspace status in Project Workspace.",
    },
    "dash.home.sample_not_found": {"tr": "Örnek dosyası bulunamadı: {name}", "en": "Sample file not found: {name}"},
    "dash.home.sample_load_failed": {"tr": "Örnek yükleme başarısız: {error}", "en": "Sample load failed: {error}"},
    "dash.home.prereq_workspace_sample_body": {
        "tr": "Çalışma alanı yok. Örnek veri yüklemek için Proje Çalışma Alanı'nı açıp bir çalışma alanı başlatın veya yükleyin.",
        "en": "No active workspace. Open Project Workspace to start or load one, then load sample data.",
    },
    "about.title": {
        "tr": "Hakkında",
        "en": "About",
    },
    "about.caption": {
        "tr": "MaterialScope’un neyi çözdüğünü, bugün hangi kapsamın kararlı olduğunu ve ürün yönünü tek sayfada özetle.",
        "en": "Summarize what MaterialScope solves, which scope is stable today, and the current product direction in one page.",
    },
    "about.hero_badge": {
        "tr": "Ürün Bağlamı",
        "en": "Product Context",
    },
    "sidebar.project": {
        "tr": "Proje",
        "en": "Project",
    },
    "sidebar.project.caption": {
        "tr": "Mevcut çalışma alanını `.scopezip` arşivi olarak kaydet veya yükle (`.thermozip` da desteklenir).",
        "en": "Save or load the current workspace as a reusable `.scopezip` archive (`.thermozip` is still supported).",
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
        "tr": "MaterialScope Hakkında",
        "en": "About MaterialScope",
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
    "project.sidebar_hint": {
        "tr": "`Proje İşlemleri` sekmesinden `Yeni Proje`, `Proje Dosyasını Hazırla`, `Projeyi Yükle` ve `Seçili Projeyi Aç` eylemlerini kullan.",
        "en": "Use the `Project Actions` tab for `New Project`, `Prepare Project File`, `Load Project`, and `Load Selected Project` actions.",
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
        "tr": "Diferansiyel Taramalı Kalorimetri (DSC) koşularında ham sinyal, Tg, baseline ve pik karakterizasyonunu tek kararlı iş akışında yönet.",
        "en": "Run Differential Scanning Calorimetry (DSC) from raw signal through Tg, baseline, and peak characterization in one stable workflow.",
    },
    "dsc.hero_badge": {
        "tr": "Diferansiyel Taramalı Kalorimetri İş Akışı",
        "en": "Differential Scanning Calorimetry Workflow",
    },
    "tga.title": {
        "tr": "TGA Analizi",
        "en": "TGA Analysis",
    },
    "tga.caption": {
        "tr": "Termogravimetrik Analiz (TGA) koşularında kütle kaybı adımlarını, DTG eğrisini ve kalıntı metriklerini tek kararlı iş akışında çıkar.",
        "en": "Extract mass-loss steps, DTG curves, and residue metrics for Thermogravimetric Analysis (TGA) in one stable workflow.",
    },
    "tga.hero_badge": {
        "tr": "Termogravimetrik Analiz İş Akışı",
        "en": "Thermogravimetric Analysis Workflow",
    },
    "dta.title": {
        "tr": "DTA Analizi",
        "en": "DTA Analysis",
    },
    "dta.caption": {
        "tr": "Diferansiyel Termal Analiz (DTA) sinyalini yumuşatma, baseline düzeltme ve pik yorumu ile aynı kararlı rapor akışında işle.",
        "en": "Process Differential Thermal Analysis (DTA) signals with smoothing, baseline correction, and peak interpretation inside the same stable reporting flow.",
    },
    "dta.hero_badge": {
        "tr": "Diferansiyel Termal Analiz İş Akışı",
        "en": "Differential Thermal Analysis Workflow",
    },
    "xrd.title": {
        "tr": "XRD Analizi",
        "en": "XRD Analysis",
    },
    "xrd.caption": {
        "tr": "X-Işını Difraksiyonu (XRD) desenlerinde ön işleme, pik çıkarımı ve nitel faz adayı eşlemesini kararlı akışta çalıştır.",
        "en": "Run stable preprocessing, peak extraction, and qualitative phase-candidate matching for X-Ray Diffraction (XRD).",
    },
    "xrd.hero_badge": {
        "tr": "X-Işını Difraksiyonu İş Akışı",
        "en": "X-Ray Diffraction Workflow",
    },
    "ftir.title": {
        "tr": "FTIR Analizi",
        "en": "FTIR Analysis",
    },
    "ftir.caption": {
        "tr": "Fourier Dönüşümlü Kızılötesi (FTIR) spektrumlarında ön işleme, pik çıkarımı ve nitel benzerlik adayı sıralamasını kararlı akışta çalıştır.",
        "en": "Run stable preprocessing, peak extraction, and qualitative similarity-candidate ranking for Fourier Transform Infrared (FTIR) spectra.",
    },
    "ftir.hero_badge": {
        "tr": "Fourier Dönüşümlü Kızılötesi İş Akışı",
        "en": "Fourier Transform Infrared Workflow",
    },
    "raman.title": {
        "tr": "Raman Analizi",
        "en": "Raman Analysis",
    },
    "raman.caption": {
        "tr": "Raman Spektroskopisi spektrumlarında ön işleme, pik çıkarımı ve nitel benzerlik adayı sıralamasını kararlı akışta çalıştır.",
        "en": "Run stable preprocessing, peak extraction, and qualitative similarity-candidate ranking for Raman Spectroscopy spectra.",
    },
    "raman.hero_badge": {
        "tr": "Raman Spektroskopisi İş Akışı",
        "en": "Raman Spectroscopy Workflow",
    },
    # Dash Project workspace page (explicit locale via translate_ui; keep in sync with Streamlit where noted)
    "project.dash.guidance_title": {
        "tr": "Bu sayfa ne yapar?",
        "en": "What this page does",
    },
    "project.dash.guidance_body": {
        "tr": (
            "Bu sayfayı çalışma alanı kontrol noktası olarak kullanın: yüklenen koşuları doğrulayın, kaydedilmiş "
            "sonuçları gözden geçirin, karşılaştırma durumunu inceleyin ve MaterialScope `.scopezip` arşivi "
            "kaydetme/yükleme işlemlerini yönetin (eski `.thermozip` içe aktarımı desteklenir)."
        ),
        "en": (
            "Use this page as the workspace checkpoint: verify loaded runs, review saved results, inspect compare "
            "state, and manage MaterialScope `.scopezip` archive save/load (legacy `.thermozip` import is supported)."
        ),
    },
    "project.dash.workflow_title": {
        "tr": "Tipik iş akışı",
        "en": "Typical workflow",
    },
    "project.dash.workflow_step1": {
        "tr": "Koşuları Veri Al sayfasında içe aktarın.",
        "en": "Import runs on the Import Runs page.",
    },
    "project.dash.workflow_step2": {
        "tr": "Proje Alanı’nda veri seti ve kayıtlı sonuç sayılarını doğrulayın.",
        "en": "Use Project Workspace to verify dataset and saved-result counts.",
    },
    "project.dash.workflow_step3": {
        "tr": "Çalışma alanı özeti hazır olduğunda Karşılaştırma ve Rapor’a geçin.",
        "en": "Proceed to Compare Workspace and Report Center when the workspace summary is ready.",
    },
    "project.dash.quick_actions": {
        "tr": "Hızlı işlemler",
        "en": "Quick Actions",
    },
    "project.dash.start_new_workspace": {
        "tr": "Yeni çalışma alanı başlat",
        "en": "Start New Workspace",
    },
    "project.dash.prepare_and_download": {
        "tr": "Arşivi hazırla ve indir (.scopezip)",
        "en": "Prepare & Download Archive (.scopezip)",
    },
    "project.dash.upload_cta": {
        "tr": "MaterialScope proje arşivi yükle (.scopezip veya eski .thermozip)",
        "en": "Upload a MaterialScope project archive (.scopezip or legacy .thermozip)",
    },
    "project.dash.selected_archive_prefix": {
        "tr": "Seçilen arşiv:",
        "en": "Selected archive:",
    },
    "project.dash.invalid_archive_extension": {
        "tr": "Yalnızca `.scopezip` veya eski `.thermozip` MaterialScope proje arşivleri kabul edilir.",
        "en": "Only `.scopezip` or legacy `.thermozip` MaterialScope project archives are accepted.",
    },
    "project.dash.metric_datasets": {
        "tr": "Veri setleri",
        "en": "Datasets",
    },
    "project.dash.metric_saved_results": {
        "tr": "Kayıtlı sonuçlar",
        "en": "Saved Results",
    },
    "project.dash.metric_figures": {
        "tr": "Görseller",
        "en": "Figures",
    },
    "project.dash.metric_history_steps": {
        "tr": "Geçmiş adımları",
        "en": "History Steps",
    },
    "project.dash.active_dataset": {
        "tr": "Etkin veri seti: {name}",
        "en": "Active dataset: {name}",
    },
    "project.dash.compare_workspace_status": {
        "tr": "Karşılaştırma alanı: {state}",
        "en": "Compare workspace: {state}",
    },
    "project.dash.compare_ready": {
        "tr": "Hazır",
        "en": "Ready",
    },
    "project.dash.compare_empty": {
        "tr": "Boş",
        "en": "Empty",
    },
    "project.dash.archive_status": {
        "tr": "Arşiv durumu: {detail}",
        "en": "Archive status: {detail}",
    },
    "project.dash.archive_ready_detail": {
        "tr": "Hazırlanabilir (en az bir kayıtlı sonuç, görsel veya geçmiş adımı)",
        "en": "Ready to prepare (at least one saved result, figure, or history step)",
    },
    "project.dash.archive_needs_detail": {
        "tr": "En az bir kayıtlı sonuç, görsel veya geçmiş adımı gerekir",
        "en": "Needs at least one saved result, figure, or history step",
    },
    "project.dash.next_step_import": {
        "tr": "Önce {import_nav} sayfasından koşu yükleyin.",
        "en": "Start by loading runs from {import_nav}.",
    },
    "project.dash.next_step_results": {
        "tr": "Sıradaki adım: analiz sayfalarından en az bir sonucu kaydedin.",
        "en": "Next step: save at least one analysis result.",
    },
    "project.dash.next_step_compare": {
        "tr": "Sıradaki adım: {compare_nav} içinde koşuları eşleştirin.",
        "en": "Next step: align runs in {compare_nav}.",
    },
    "project.dash.next_step_report": {
        "tr": "Sıradaki adım: {report_nav} içinde çıktı paketini hazırlayın.",
        "en": "Next step: prepare the output package in {report_nav}.",
    },
    "project.dash.workspace_required_title": {
        "tr": "Çalışma alanı gerekli",
        "en": "Workspace required",
    },
    "project.dash.workspace_required_body": {
        "tr": (
            "Etkin çalışma alanı yok. Koşuları yüklemek için Veri Al’a gidin veya buradaki Hızlı İşlemler ile "
            "yeni bir çalışma alanı başlatın / arşiv yükleyin."
        ),
        "en": (
            "No active workspace. Go to Import Runs to load runs, or use Quick Actions here to start or load a "
            "workspace."
        ),
    },
    "project.dash.error_prefix": {
        "tr": "Hata:",
        "en": "Error:",
    },
    "project.dash.loaded_runs": {
        "tr": "Yüklenen koşular",
        "en": "Loaded Runs",
    },
    "project.dash.no_loaded_runs_title": {
        "tr": "Yüklenen koşu yok",
        "en": "No loaded runs",
    },
    "project.dash.no_loaded_runs_body": {
        "tr": "Veri seti yok. Bu çalışma alanını doldurmak için önce koşuları içe aktarın.",
        "en": "No datasets loaded. Import runs first to populate this workspace.",
    },
    "project.dash.saved_result_records": {
        "tr": "Kayıtlı sonuç kayıtları",
        "en": "Saved Result Records",
    },
    "project.dash.results_incomplete_hint": {
        "tr": "Bazı sonuç kayıtları eksik; dışa aktarmada dışlanır.",
        "en": "Some result records are incomplete and are excluded from exports.",
    },
    "project.dash.no_saved_results_title": {
        "tr": "Kayıtlı sonuç yok",
        "en": "No saved results",
    },
    "project.dash.no_saved_results_body": {
        "tr": "Henüz kayıtlı sonuç yok. Analizleri çalıştırın, ardından sonuç kayıtlarını burada doğrulayın.",
        "en": "No saved results yet. Run analyses, then return here to confirm result records.",
    },
    "project.dash.compare_workspace": {
        "tr": "Karşılaştırma alanı",
        "en": "Compare Workspace",
    },
    "project.dash.analysis_type": {
        "tr": "Analiz türü:",
        "en": "Analysis Type:",
    },
    "project.dash.selected_runs": {
        "tr": "Seçili koşular:",
        "en": "Selected Runs:",
    },
    "project.dash.saved_figure": {
        "tr": "Kaydedilen görsel:",
        "en": "Saved Figure:",
    },
    "project.dash.no_compare_notes": {
        "tr": "Henüz karşılaştırma notu yok.",
        "en": "No compare notes yet.",
    },
    "project.dash.none_label": {
        "tr": "Yok",
        "en": "None",
    },
    "project.dash.na_label": {
        "tr": "Yok",
        "en": "N/A",
    },
    "project.dash.choose_archive_first": {
        "tr": "Önce bir MaterialScope proje arşivi seçin (.scopezip veya eski .thermozip).",
        "en": "Choose a MaterialScope project archive first (.scopezip or legacy .thermozip).",
    },
    "project.dash.clear_workspace_warning": {
        "tr": (
            "Mevcut çalışma alanı silinecek. Saklamak istiyorsanız önce MaterialScope `.scopezip` arşivini "
            "hazırlayıp indirin."
        ),
        "en": (
            "The current workspace will be cleared. Prepare and download a MaterialScope `.scopezip` archive first "
            "if you need to keep it."
        ),
    },
    "project.dash.clear_workspace_confirm": {
        "tr": "Yeni bir çalışma alanı başlatmayı onaylayın.",
        "en": "Confirm to start a fresh workspace.",
    },
    "project.dash.load_replace_warning": {
        "tr": "Seçilen arşiv mevcut çalışma alanının yerine geçecek. Devam etmek için onaylayın.",
        "en": "Loading the selected archive will replace the current workspace. Confirm to continue.",
    },
    "project.dash.load_confirm_simple": {
        "tr": "Seçilen MaterialScope arşivini yüklemeyi onaylayın.",
        "en": "Confirm to load the selected archive.",
    },
    "project.dash.confirm_clear": {
        "tr": "Çalışma alanını temizle",
        "en": "Confirm clear",
    },
    "project.dash.confirm_generic": {
        "tr": "Onayla",
        "en": "Confirm",
    },
    "project.dash.continue_loading": {
        "tr": "Yüklemeye devam et",
        "en": "Continue loading",
    },
    "project.dash.prepare_archive_first": {
        "tr": "Önce arşivi hazırla",
        "en": "Prepare archive first",
    },
    "project.dash.cancel": {
        "tr": "İptal",
        "en": "Cancel",
    },
    "project.dash.action_cancelled": {
        "tr": "Proje eylemi iptal edildi.",
        "en": "Project action cancelled.",
    },
    "project.dash.workspace_cleared": {
        "tr": "Yeni bir çalışma alanı başlatıldı.",
        "en": "Started a fresh workspace.",
    },
    "project.dash.project_loaded": {
        "tr": "Proje yüklendi: {datasets} veri seti, {results} sonuç.",
        "en": "Project loaded: {datasets} datasets, {results} results.",
    },
    "project.dash.archive_eligibility_warning": {
        "tr": "Arşiv, en az bir kayıtlı sonuç, görsel veya geçmiş adımından sonra hazırlanabilir.",
        "en": "Archive preparation is enabled after at least one saved result, figure, or history step.",
    },
    "project.dash.archive_downloading": {
        "tr": "Arşiv hazırlandı. MaterialScope `.scopezip` indiriliyor…",
        "en": "Archive prepared. Downloading MaterialScope `.scopezip`…",
    },
    "project.dash.save_failed": {
        "tr": "Kaydetme başarısız: {error}",
        "en": "Save failed: {error}",
    },
    "project.dash.no_workspace_save_title": {
        "tr": "Çalışma alanı gerekli",
        "en": "Workspace required",
    },
    "project.dash.no_workspace_save_body": {
        "tr": "Kaydedilecek etkin çalışma alanı yok. Önce veri içe aktarın veya bir `.scopezip` / eski `.thermozip` proje arşivi yükleyin.",
        "en": "No active workspace to save. Import data or load a MaterialScope project archive (.scopezip or legacy .thermozip) first.",
    },
}


def normalize_ui_locale(locale: str | None) -> str:
    """Normalize a UI locale string to a supported language code (tr/en)."""
    loc = (locale or "en").lower().split("-", 1)[0]
    return loc if loc in SUPPORTED_LANGUAGES else "en"


def translate_ui(locale: str | None, key: str, **kwargs) -> str:
    """Translate a UI key using explicit locale (Dash and other non-Streamlit callers).

    Does not read Streamlit session state. Falls back to English when a key or language is missing.
    """
    lang = normalize_ui_locale(locale)
    entry = TRANSLATIONS.get(key)
    if entry is None:
        text = key
    else:
        text = entry.get(lang) or entry.get("en") or key
    if kwargs:
        return text.format(**kwargs)
    return text


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
