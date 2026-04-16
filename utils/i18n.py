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
    # --- Dash analysis (shared + modality) ---
    "dash.analysis.badge": {"tr": "Analiz", "en": "Analysis"},
    "dash.analysis.result_summary": {"tr": "Sonuç özeti", "en": "Result Summary"},
    "dash.analysis.dataset_selection_title": {"tr": "Veri seti seçimi", "en": "Dataset Selection"},
    "dash.analysis.workflow_template_title": {"tr": "İş akışı şablonu", "en": "Workflow Template"},
    "dash.analysis.execute_title": {"tr": "Çalıştır", "en": "Execute"},
    "dash.analysis.unit_mode_title": {"tr": "Birim modu", "en": "Unit Mode"},
    "dash.analysis.workspace_inactive": {
        "tr": "Etkin çalışma alanı yok. Önce bir çalışma alanı oluşturun.",
        "en": "No workspace active. Create one first.",
    },
    "dash.analysis.error_loading_datasets": {"tr": "Veri setleri yüklenemedi: {error}", "en": "Error loading datasets: {error}"},
    "dash.analysis.error_loading_result": {"tr": "Sonuç yüklenemedi: {error}", "en": "Error loading result: {error}"},
    "dash.analysis.analysis_failed": {"tr": "Analiz başarısız: {error}", "en": "Analysis failed: {error}"},
    "dash.analysis.no_eligible_prefix": {
        "tr": "Uygun veri seti bulunamadı ({types}). {empty}",
        "en": "No eligible datasets found ({types}). {empty}",
    },
    "dash.analysis.eligible_count": {
        "tr": "{eligible}/{total} veri seti uygun (türler: {types}).",
        "en": "{eligible} of {total} datasets are eligible (types: {types}).",
    },
    "dash.analysis.interpret_saved": {
        "tr": "Analiz kaydedildi (sonuç: {rid}). Doğrulama: {vstatus}, uyarılar: {warnings}.",
        "en": "Analysis saved (result: {rid}). Validation: {vstatus}, warnings: {warnings}.",
    },
    "dash.analysis.interpret_blocked": {"tr": "Analiz engellendi: {reason}", "en": "Analysis blocked: {reason}"},
    "dash.analysis.interpret_failed": {"tr": "Analiz başarısız: {reason}", "en": "Analysis failed: {reason}"},
    "dash.analysis.processing_title": {"tr": "İşleme ayrıntıları", "en": "Processing Details"},
    "dash.analysis.processing_workflow": {"tr": "İş akışı: {label} (v{version})", "en": "Workflow: {label} (v{version})"},
    "dash.analysis.processing_smoothing": {"tr": "Yumuşatma: {detail}", "en": "Smoothing: {detail}"},
    "dash.analysis.empty_run_result": {
        "tr": "Sonuçları burada görmek için bir analiz çalıştırın.",
        "en": "Run an analysis to see results here.",
    },
    "dash.analysis.empty_figure": {"tr": "Grafik için veri yok.", "en": "No data available for plotting."},
    "dash.analysis.na": {"tr": "Yok", "en": "N/A"},
    "dash.analysis.metric.peaks": {"tr": "Tepe", "en": "Peaks"},
    "dash.analysis.metric.glass_transitions": {"tr": "Cam geçişleri", "en": "Glass Transitions"},
    "dash.analysis.metric.template": {"tr": "Şablon", "en": "Template"},
    "dash.analysis.metric.sample": {"tr": "Numune", "en": "Sample"},
    "dash.analysis.metric.steps": {"tr": "Adımlar", "en": "Steps"},
    "dash.analysis.metric.total_mass_loss": {"tr": "Toplam kütle kaybı", "en": "Total Mass Loss"},
    "dash.analysis.metric.residue": {"tr": "Kalıntı", "en": "Residue"},
    "dash.analysis.metric.matches": {"tr": "Eşleşmeler", "en": "Matches"},
    "dash.analysis.metric.events": {"tr": "Olaylar", "en": "Events"},
    "dash.analysis.metric.candidates": {"tr": "Adaylar", "en": "Candidates"},
    "dash.analysis.metric.exothermic": {"tr": "Ekzotermik", "en": "Exothermic"},
    "dash.analysis.metric.endothermic": {"tr": "Endotermik", "en": "Endothermic"},
    "dash.analysis.metric.match_status": {"tr": "Eşleşme durumu", "en": "Match Status"},
    "dash.analysis.metric.top_score": {"tr": "En yüksek skor", "en": "Top Score"},
    "dash.analysis.metric.top_candidate_score": {"tr": "En iyi aday skoru", "en": "Top Candidate Score"},
    "dash.analysis.metric.detected_peaks": {"tr": "Algılanan tepeler", "en": "Detected Peaks"},
    "dash.analysis.match_status.no_match": {"tr": "Eşleşme yok", "en": "No Match"},
    "dash.analysis.match_status.partial_match": {"tr": "Kısmi eşleşme", "en": "Partial Match"},
    "dash.analysis.match_status.matched": {"tr": "Eşleşti", "en": "Matched"},
    "dash.analysis.match_status.high_confidence": {"tr": "Yüksek güven", "en": "High Confidence"},
    "dash.analysis.confidence.high_confidence": {"tr": "Yüksek güven", "en": "High Confidence"},
    "dash.analysis.confidence.moderate_confidence": {"tr": "Orta güven", "en": "Moderate Confidence"},
    "dash.analysis.confidence.low_confidence": {"tr": "Düşük güven", "en": "Low Confidence"},
    "dash.analysis.confidence.no_match": {"tr": "Eşleşme yok", "en": "No Match"},
    "dash.analysis.section.key_thermal_events": {"tr": "Önemli termal olaylar", "en": "Key Thermal Events"},
    "dash.analysis.section.all_event_details": {"tr": "Tüm olay ayrıntıları", "en": "All Event Details"},
    "dash.analysis.section.match_data_table": {"tr": "Eşleşme veri tablosu", "en": "Match Data Table"},
    "dash.analysis.section.candidate_matches": {"tr": "Aday eşleşmeleri", "en": "Candidate Matches"},
    "dash.analysis.section.candidate_evidence_table": {"tr": "Aday kanıt tablosu", "en": "Candidate Evidence Table"},
    "dash.analysis.state.no_thermal_events": {"tr": "Termal olay algılanmadı.", "en": "No thermal events detected."},
    "dash.analysis.state.no_event_data": {"tr": "Olay verisi yok.", "en": "No event data."},
    "dash.analysis.state.no_library_matches": {"tr": "Kütüphane eşleşmesi bulunamadı.", "en": "No library matches found."},
    "dash.analysis.state.no_match_data": {"tr": "Eşleşme verisi yok.", "en": "No match data."},
    "dash.analysis.state.no_candidate_matches": {"tr": "Aday eşleşmesi döndürülmedi.", "en": "No candidate matches were returned."},
    "dash.analysis.state.no_processed_signal_plot": {
        "tr": "Grafik için işlenmiş sinyal yok.",
        "en": "No processed signal is available for plotting.",
    },
    "dash.analysis.dta.events_cards_intro": {
        "tr": "{shown} olay kartı gösteriliyor (en güçlü imzalar). Aşağıdaki tam tablo tüm {total} olayı listeler.",
        "en": "Showing {shown} event card(s) with the strongest resolved signatures. The full event table below keeps all {total} event(s).",
    },
    "dash.analysis.dta.show_more_events": {"tr": "{n} ek olay göster", "en": "Show {n} additional event(s)"},
    "dash.analysis.dta.baseline": {"tr": "Taban çizgisi: {detail}", "en": "Baseline: {detail}"},
    "dash.analysis.dta.peak_detection": {"tr": "Tepe algılama: {detail}", "en": "Peak Detection: {detail}"},
    "dash.analysis.dta.sign_convention": {"tr": "İşaret anlaşması: {detail}", "en": "Sign Convention: {detail}"},
    "dash.analysis.dta.no_plot_signal": {
        "tr": "Grafik için işlenmiş DTA sinyali yok.",
        "en": "No processed DTA signal is available for plotting.",
    },
    "dash.analysis.dta.direction.unknown": {"tr": "Bilinmeyen", "en": "Unknown"},
    "dash.analysis.figure.title_dta": {"tr": "DTA — {name}", "en": "DTA - {name}"},
    "dash.analysis.figure.axis_delta_t": {"tr": "Delta-T (a.b.)", "en": "Delta-T (a.u.)"},
    "dash.analysis.figure.legend_dtg": {"tr": "DTG (dm/dT)", "en": "DTG (dm/dT)"},
    "dash.analysis.figure.step_mid": {"tr": "Adım orta {v} C", "en": "Step mid {v} C"},
    "dash.analysis.figure.title_ftir_main": {"tr": "FTIR sorgu spektrumu", "en": "FTIR Query Spectrum"},
    "dash.analysis.figure.title_raman_main": {"tr": "Raman sorgu spektrumu", "en": "RAMAN Query Spectrum"},
    "dash.analysis.figure.title_xrd_main": {"tr": "XRD birincil difraktogram", "en": "XRD Primary Diffractogram"},
    "dash.analysis.figure.axis_wavenumber": {"tr": "Dalga sayısı (cm⁻¹)", "en": "Wavenumber (cm^-1)"},
    "dash.analysis.figure.axis_raman_shift": {"tr": "Raman kayması (cm⁻¹)", "en": "Raman Shift (cm^-1)"},
    "dash.analysis.figure.axis_signal_au": {"tr": "Sinyal (a.b.)", "en": "Signal (a.u.)"},
    "dash.analysis.figure.axis_intensity_au": {"tr": "Yoğunluk (a.b.)", "en": "Intensity (a.u.)"},
    "dash.analysis.figure.axis_two_theta": {"tr": "2θ (°)", "en": "2theta (deg)"},
    "dash.analysis.figure.axis_x_generic": {"tr": "X ekseni ({role})", "en": "X axis ({role})"},
    "dash.analysis.figure.legend_estimated_baseline": {"tr": "Tahmini taban çizgisi", "en": "Estimated Baseline"},
    "dash.analysis.figure.legend_imported_spectrum": {"tr": "İçe aktarılan spektrum", "en": "Imported Spectrum"},
    "dash.analysis.figure.legend_smoothed_spectrum": {"tr": "Yumuşatılmış spektrum", "en": "Smoothed Spectrum"},
    "dash.analysis.figure.legend_query_spectrum": {"tr": "Sorgu spektrumu", "en": "Query Spectrum"},
    "dash.analysis.figure.legend_raw_diffractogram": {"tr": "Ham difraktogram", "en": "Raw Diffractogram"},
    "dash.analysis.figure.legend_smoothed_diffractogram": {"tr": "Yumuşatılmış difraktogram", "en": "Smoothed Diffractogram"},
    "dash.analysis.figure.legend_corrected_diffractogram": {"tr": "Düzeltilmiş difraktogram", "en": "Corrected Diffractogram"},
    "dash.analysis.figure.legend_dta_primary_corrected": {"tr": "Düzeltilmiş sinyal", "en": "Corrected Signal"},
    "dash.analysis.figure.legend_dta_primary_smoothed": {"tr": "Yumuşatılmış sinyal", "en": "Smoothed Signal"},
    "dash.analysis.figure.legend_dta_primary_raw": {"tr": "Ham sinyal", "en": "Raw Signal"},
    "dash.analysis.ftir.top_match": {"tr": "En iyi eşleşme: {name}", "en": "Top match: {name}"},
    "dash.analysis.ftir.baseline": {"tr": "Taban çizgisi: {detail}", "en": "Baseline: {detail}"},
    "dash.analysis.ftir.normalization": {"tr": "Normalizasyon: {detail}", "en": "Normalization: {detail}"},
    "dash.analysis.ftir.peak_detection": {"tr": "Tepe algılama: {detail}", "en": "Peak Detection: {detail}"},
    "dash.analysis.ftir.similarity_matching": {"tr": "Benzerlik eşlemesi: {detail}", "en": "Similarity Matching: {detail}"},
    "dash.analysis.ftir.library": {"tr": "Kütüphane: {mode} (kaynak: {source})", "en": "Library: {mode} (source: {source})"},
    "dash.analysis.raman.top_match": {"tr": "En iyi eşleşme: {name}", "en": "Top match: {name}"},
    "dash.analysis.raman.baseline": {"tr": "Taban çizgisi: {detail}", "en": "Baseline: {detail}"},
    "dash.analysis.raman.normalization": {"tr": "Normalizasyon: {detail}", "en": "Normalization: {detail}"},
    "dash.analysis.raman.peak_detection": {"tr": "Tepe algılama: {detail}", "en": "Peak Detection: {detail}"},
    "dash.analysis.raman.similarity_matching": {"tr": "Benzerlik eşlemesi: {detail}", "en": "Similarity Matching: {detail}"},
    "dash.analysis.raman.library": {"tr": "Kütüphane: {mode} (kaynak: {source})", "en": "Library: {mode} (source: {source})"},
    "dash.analysis.xrd.top_candidate": {"tr": "En iyi aday: {name}", "en": "Top candidate: {name}"},
    "dash.analysis.xrd.axis_role_note": {
        "tr": "Eksen rolü: {role}; çıktı 2θ odaklı difraktogram olarak gösteriliyor.",
        "en": "Axis role: {role}; output shown as 2theta-oriented diffractogram.",
    },
    "dash.analysis.xrd.wavelength_line": {"tr": "Dalga boyu (Å): {value}", "en": "Wavelength (angstrom): {value}"},
    "dash.analysis.xrd.wavelength_not_provided": {"tr": "sağlanmadı", "en": "not provided"},
    "dash.analysis.xrd.provenance_state": {"tr": "XRD provenance durumu: {state}", "en": "XRD provenance state: {state}"},
    "dash.analysis.xrd.provenance_warning": {"tr": "Provenance uyarısı: {warning}", "en": "Provenance warning: {warning}"},
    "dash.analysis.xrd.qualitative_notice": {
        "tr": "Bu sayfa nitel faz taraması içindir; en iyi adayları kesin tanımlama olarak düşünmeyin.",
        "en": "This page is for qualitative phase-screening; do not treat top candidates as definitive identification.",
    },
    "dash.analysis.xrd.peak_detection": {"tr": "Tepe algılama: {detail}", "en": "Peak Detection: {detail}"},
    "dash.analysis.xrd.no_plot_signal": {
        "tr": "Grafik için işlenmiş XRD sinyali yok.",
        "en": "No processed XRD signal is available for plotting.",
    },
    "dash.analysis.label.midpoint": {"tr": "Orta nokta", "en": "Midpoint"},
    "dash.analysis.label.onset": {"tr": "Başlangıç", "en": "Onset"},
    "dash.analysis.label.endset": {"tr": "Bitiş", "en": "Endset"},
    "dash.analysis.label.area": {"tr": "Alan", "en": "Area"},
    "dash.analysis.label.dcp": {"tr": "dCp", "en": "dCp"},
    "dash.analysis.label.fwhm": {"tr": "FWHM", "en": "FWHM"},
    "dash.analysis.label.height": {"tr": "Yükseklik", "en": "Height"},
    "dash.analysis.label.mass_loss": {"tr": "Kütle kaybı", "en": "Mass Loss"},
    "dash.analysis.label.residual": {"tr": "Kalıntı", "en": "Residual"},
    "dash.analysis.label.peak_n": {"tr": "Tepe {n}", "en": "Peak {n}"},
    "dash.analysis.label.step_n": {"tr": "Adım {n}", "en": "Step {n}"},
    "dash.analysis.label.match_n": {"tr": "Eşleşme {n}", "en": "Match {n}"},
    "dash.analysis.label.candidate_n": {"tr": "Aday {n}", "en": "Candidate {n}"},
    "dash.analysis.label.glass_transition_n": {"tr": "Cam geçişi {n}", "en": "Glass Transition {n}"},
    "dash.analysis.label.candidate": {"tr": "Aday", "en": "Candidate"},
    "dash.analysis.label.score": {"tr": "Skor", "en": "Score"},
    "dash.analysis.label.peak_overlap": {"tr": "Tepe örtüşmesi", "en": "Peak Overlap"},
    "dash.analysis.label.provider": {"tr": "Sağlayıcı", "en": "Provider"},
    "dash.analysis.label.phase": {"tr": "Faz", "en": "Phase"},
    "dash.analysis.label.formula": {"tr": "Formül", "en": "Formula"},
    "dash.analysis.label.shared_peaks": {"tr": "Ortak tepeler", "en": "Shared Peaks"},
    "dash.analysis.section.glass_transitions": {"tr": "Cam geçişleri", "en": "Glass Transitions"},
    "dash.analysis.section.detected_peaks": {"tr": "Algılanan tepeler", "en": "Detected Peaks"},
    "dash.analysis.section.detected_steps": {"tr": "Algılanan adımlar", "en": "Detected Steps"},
    "dash.analysis.section.step_table": {"tr": "Adım veri tablosu", "en": "Step Data Table"},
    "dash.analysis.section.detected_events": {"tr": "Algılanan olaylar", "en": "Detected Events"},
    "dash.analysis.section.library_matches": {"tr": "Kütüphane eşleşmeleri", "en": "Library Matches"},
    "dash.analysis.section.phase_candidates": {"tr": "Faz adayları", "en": "Phase Candidates"},
    "dash.analysis.state.not_detected": {"tr": "Algılanmadı.", "en": "Not detected."},
    "dash.analysis.state.no_peaks": {"tr": "Tepe algılanmadı.", "en": "No peaks detected."},
    "dash.analysis.state.no_steps": {"tr": "Adım algılanmadı.", "en": "No steps detected."},
    "dash.analysis.state.no_step_data": {"tr": "Adım verisi yok.", "en": "No step data."},
    "dash.analysis.state.more_transitions": {"tr": "... ve {n} ek geçiş.", "en": "... and {n} more transition(s)."},
    "dash.analysis.figure.axis_temperature_c": {"tr": "Sıcaklık (°C)", "en": "Temperature (C)"},
    "dash.analysis.figure.axis_heat_flow": {"tr": "Isı akışı (a.b.)", "en": "Heat Flow (a.u.)"},
    "dash.analysis.figure.axis_mass_pct": {"tr": "Kütle (%)", "en": "Mass (%)"},
    "dash.analysis.figure.axis_dtg": {"tr": "DTG (%/°C)", "en": "DTG (%/C)"},
    "dash.analysis.figure.legend_raw_signal": {"tr": "Ham sinyal", "en": "Raw Signal"},
    "dash.analysis.figure.legend_smoothed": {"tr": "Yumuşatılmış", "en": "Smoothed"},
    "dash.analysis.figure.legend_baseline": {"tr": "Taban çizgisi", "en": "Baseline"},
    "dash.analysis.figure.legend_corrected": {"tr": "Düzeltilmiş", "en": "Corrected"},
    "dash.analysis.figure.title_dsc": {"tr": "DSC — {name}", "en": "DSC - {name}"},
    "dash.analysis.figure.title_tga": {"tr": "TGA — {name}", "en": "TGA - {name}"},
    "dash.analysis.figure.annot_tg": {"tr": "Tg {v}", "en": "Tg {v}"},
    "dash.analysis.figure.annot_on": {"tr": "Baş {v}", "en": "On {v}"},
    "dash.analysis.figure.annot_end": {"tr": "Son {v}", "en": "End {v}"},
    "dash.analysis.figure.legend_raw_mass": {"tr": "Ham kütle", "en": "Raw Mass"},
    "dash.analysis.figure.legend_smoothed_mass": {"tr": "Yumuşatılmış kütle", "en": "Smoothed Mass"},
    "dash.analysis.dsc.title": {"tr": "DSC analizi", "en": "DSC Analysis"},
    "dash.analysis.dsc.caption": {
        "tr": "DSC uyumlu bir veri seti seçin, iş akışı şablonunu seçin ve termal analizi çalıştırın.",
        "en": "Select a DSC-eligible dataset, choose a workflow template, and run thermal analysis.",
    },
    "dash.analysis.dsc.run_btn": {"tr": "DSC analizini çalıştır", "en": "Run DSC Analysis"},
    "dash.analysis.dsc.empty_import": {"tr": "Önce bir DSC dosyası içe aktarın.", "en": "Import a DSC file first."},
    "dash.analysis.dsc.workflow_fallback": {"tr": "DSC analiz iş akışı.", "en": "DSC analysis workflow."},
    "dash.analysis.dsc.baseline": {"tr": "Taban çizgisi: {detail}", "en": "Baseline: {detail}"},
    "dash.analysis.dsc.peak_detection": {"tr": "Tepe algılama: {detail}", "en": "Peak Detection: {detail}"},
    "dash.analysis.dsc.tg_detection": {"tr": "Tg algılama: {detail}", "en": "Tg Detection: {detail}"},
    "dash.analysis.dsc.sign_convention": {"tr": "İşaret anlaşması: {detail}", "en": "Sign Convention: {detail}"},
    "dash.analysis.dsc.template.dsc.general.label": {"tr": "Genel DSC", "en": "General DSC"},
    "dash.analysis.dsc.template.dsc.polymer_tg.label": {"tr": "Polimer Tg", "en": "Polymer Tg"},
    "dash.analysis.dsc.template.dsc.polymer_melting_crystallization.label": {
        "tr": "Polimer erime/kristalleşme",
        "en": "Polymer Melting/Crystallization",
    },
    "dash.analysis.dsc.template.dsc.general.desc": {
        "tr": "Genel DSC: Savitzky-Golay yumuşatma, ASLS taban çizgisi, çift yönlü tepe algılama, otomatik Tg algılama.",
        "en": "General DSC: Savitzky-Golay smoothing, ASLS baseline, peak detection (both directions), automatic Tg detection.",
    },
    "dash.analysis.dsc.template.dsc.polymer_tg.desc": {
        "tr": "Polimer Tg: Daha net cam geçişi için daha geniş yumuşatma penceresi, ASLS taban çizgisi, otomatik Tg algılama.",
        "en": "Polymer Tg: Wider smoothing window for clearer glass transition, ASLS baseline, automatic Tg detection.",
    },
    "dash.analysis.dsc.template.dsc.polymer_melting_crystallization.desc": {
        "tr": "Polimer erime/kristalleşme: Standart yumuşatma, ASLS taban çizgisi, erime ve kristalleşme olayları için tepe algılama.",
        "en": "Polymer Melting/Crystallization: Standard smoothing, ASLS baseline, peak detection for melting and crystallization events.",
    },
    "dash.analysis.tga.title": {"tr": "TGA analizi", "en": "TGA Analysis"},
    "dash.analysis.tga.caption": {
        "tr": "TGA uyumlu veri seti seçin, birim modu ve iş akışı şablonunu seçin ve termogravimetrik analizi çalıştırın.",
        "en": "Select a TGA-eligible dataset, choose unit mode and workflow template, and run thermogravimetric analysis.",
    },
    "dash.analysis.tga.run_btn": {"tr": "TGA analizini çalıştır", "en": "Run TGA Analysis"},
    "dash.analysis.tga.empty_import": {"tr": "Önce bir TGA dosyası içe aktarın.", "en": "Import a TGA file first."},
    "dash.analysis.tga.workflow_fallback": {"tr": "TGA analiz iş akışı.", "en": "TGA analysis workflow."},
    "dash.analysis.tga.unit_mode_help": {
        "tr": "Otomatik: aralık ve birim metadata’sından çıkar. Yüzde: sinyal kütle % olarak. Mutlak kütle: sinyal mg, %’ye dönüştürülür.",
        "en": "Auto: infer from signal range and unit metadata. Percent: signal is mass %. Absolute Mass: signal is mg, will be converted to %.",
    },
    "dash.analysis.tga.unit.auto.desc": {
        "tr": "Otomatik: aralık ve birim metadata’sından çıkar. Çoğu durum için en iyisi.",
        "en": "Auto: infer from signal range and unit metadata. Best for most cases.",
    },
    "dash.analysis.tga.unit.percent.desc": {
        "tr": "Yüzde: sinyal kütle % olarak. Veri zaten %100’e normalize edildiğinde kullanın.",
        "en": "Percent: signal is mass %. Use when data is already normalized to 100%.",
    },
    "dash.analysis.tga.unit.absolute_mass.desc": {
        "tr": "Mutlak kütle: sinyal mg cinsinden. Başlangıç kütle referansı ile %’ye dönüştürülür.",
        "en": "Absolute Mass: signal is in mg. Will be converted to % using initial mass reference.",
    },
    "dash.analysis.tga.unit.fallback": {"tr": "TGA birim modu.", "en": "TGA unit mode."},
    "dash.analysis.tga.step_detection": {"tr": "Adım algılama: {detail}", "en": "Step Detection: {detail}"},
    "dash.analysis.tga.unit_mode_line": {"tr": "Birim modu: {label} (temel: {basis})", "en": "Unit Mode: {label} (basis: {basis})"},
    "dash.analysis.tga.calibration": {"tr": "Kalibrasyon: {detail}", "en": "Calibration: {detail}"},
    "dash.analysis.tga.template.tga.general.label": {"tr": "Genel TGA", "en": "General TGA"},
    "dash.analysis.tga.template.tga.single_step_decomposition.label": {"tr": "Tek adım ayrışma", "en": "Single-Step Decomposition"},
    "dash.analysis.tga.template.tga.multi_step_decomposition.label": {"tr": "Çok adımlı ayrışma", "en": "Multi-Step Decomposition"},
    "dash.analysis.tga.template.tga.general.desc": {
        "tr": "Genel TGA: Savitzky-Golay yumuşatma, DTG hesaplama, DTG tepe bulma ile adım algılama.",
        "en": "General TGA: Savitzky-Golay smoothing, DTG computation, step detection via DTG peak finding.",
    },
    "dash.analysis.tga.template.tga.single_step_decomposition.desc": {
        "tr": "Tek adım ayrışma: Standart yumuşatma, tek kütle kaybı olayı için DTG tepe algılama.",
        "en": "Single-Step Decomposition: Standard smoothing, DTG peak detection for a single mass-loss event.",
    },
    "dash.analysis.tga.template.tga.multi_step_decomposition.desc": {
        "tr": "Çok adımlı ayrışma: Daha geniş yumuşatma penceresi, üst üste binen birden fazla adım için daha düşük kütle kaybı eşiği.",
        "en": "Multi-Step Decomposition: Wider smoothing window, lower mass-loss threshold for multiple overlapping steps.",
    },
    "dash.analysis.tga.unit.auto.label": {"tr": "Otomatik", "en": "Auto"},
    "dash.analysis.tga.unit.percent.label": {"tr": "Yüzde (%)", "en": "Percent (%)"},
    "dash.analysis.tga.unit.absolute_mass.label": {"tr": "Mutlak kütle (mg)", "en": "Absolute Mass (mg)"},
    "dash.analysis.tga.mass_loss_mg": {"tr": "Kütle kaybı: {v:.3f} mg", "en": "Mass loss: {v:.3f} mg"},
    "dash.analysis.dta.title": {"tr": "DTA analizi", "en": "DTA Analysis"},
    "dash.analysis.dta.caption": {
        "tr": "DTA uyumlu veri seti seçin, şablonu seçin ve diferansiyel termal analizi çalıştırın.",
        "en": "Select a DTA-eligible dataset, choose a template, and run differential thermal analysis.",
    },
    "dash.analysis.dta.run_btn": {"tr": "DTA analizini çalıştır", "en": "Run DTA Analysis"},
    "dash.analysis.dta.empty_import": {"tr": "Önce bir DTA dosyası içe aktarın.", "en": "Import a DTA file first."},
    "dash.analysis.dta.workflow_fallback": {"tr": "DTA analiz iş akışı.", "en": "DTA analysis workflow."},
    "dash.analysis.dta.direction.exo": {"tr": "Ekzo", "en": "Exo"},
    "dash.analysis.dta.direction.endo": {"tr": "Endo", "en": "Endo"},
    "dash.analysis.dta.template.dta.general.label": {"tr": "Genel DTA", "en": "General DTA"},
    "dash.analysis.dta.template.dta.thermal_events.label": {"tr": "Termal olay taraması", "en": "Thermal Event Screening"},
    "dash.analysis.dta.template.dta.general.desc": {
        "tr": "Genel DTA: Savitzky-Golay yumuşatma, ASLS taban çizgisi, çift yönlü tepe algılama (ekzotermik + endotermik).",
        "en": "General DTA: Savitzky-Golay smoothing, ASLS baseline, bidirectional peak detection (exothermic + endothermic).",
    },
    "dash.analysis.dta.template.dta.thermal_events.desc": {
        "tr": "Termal olay taraması: Daha geniş yumuşatma penceresi, karmaşık termal geçmişler için daha toleranslı tepe algılama.",
        "en": "Thermal Event Screening: Wider smoothing window, more permissive peak detection for complex thermal histories.",
    },
    "dash.analysis.ftir.title": {"tr": "FTIR analizi", "en": "FTIR Analysis"},
    "dash.analysis.ftir.caption": {
        "tr": "FTIR uyumlu veri seti seçin, şablonu seçin ve spektral analizi çalıştırın.",
        "en": "Select an FTIR-eligible dataset, choose a workflow template, and run spectral analysis.",
    },
    "dash.analysis.ftir.run_btn": {"tr": "FTIR analizini çalıştır", "en": "Run FTIR Analysis"},
    "dash.analysis.ftir.empty_import": {"tr": "Önce bir FTIR dosyası içe aktarın.", "en": "Import an FTIR file first."},
    "dash.analysis.ftir.workflow_fallback": {"tr": "FTIR analiz iş akışı.", "en": "FTIR analysis workflow."},
    "dash.analysis.ftir.template.ftir.general.label": {"tr": "Genel FTIR", "en": "General FTIR"},
    "dash.analysis.ftir.template.ftir.functional_groups.label": {"tr": "Fonksiyonel grup taraması", "en": "Functional Group Screening"},
    "dash.analysis.ftir.template.ftir.general.desc": {
        "tr": "Genel FTIR: hareketli ortalama yumuşatma, doğrusal taban çizgisi, vektör normalizasyonu, tepe algılama, kosinüs/Pearson benzerliği.",
        "en": "General FTIR: Moving-average smoothing, linear baseline, vector normalization, peak detection, cosine/Pearson similarity matching.",
    },
    "dash.analysis.ftir.template.ftir.functional_groups.desc": {
        "tr": "Fonksiyonel grup taraması: daha kısa yumuşatma, daha toleranslı tepe algılama, fonksiyonel grup tanıma için daha geniş benzerlik.",
        "en": "Functional Group Screening: Shorter smoothing window, more permissive peak detection, broader similarity matching for functional group identification.",
    },
    "dash.analysis.raman.title": {"tr": "Raman analizi", "en": "RAMAN Analysis"},
    "dash.analysis.raman.caption": {
        "tr": "Raman uyumlu veri seti seçin, şablonu seçin ve spektral eşleştirmeyi çalıştırın.",
        "en": "Select a RAMAN-eligible dataset, choose a workflow template, and run spectral matching.",
    },
    "dash.analysis.raman.run_btn": {"tr": "Raman analizini çalıştır", "en": "Run RAMAN Analysis"},
    "dash.analysis.raman.empty_import": {"tr": "Önce bir Raman dosyası içe aktarın.", "en": "Import a RAMAN file first."},
    "dash.analysis.raman.workflow_fallback": {"tr": "Raman analiz iş akışı.", "en": "RAMAN analysis workflow."},
    "dash.analysis.raman.template.raman.general.label": {"tr": "Genel Raman", "en": "General Raman"},
    "dash.analysis.raman.template.raman.polymorph_screening.label": {"tr": "Polimorf taraması", "en": "Polymorph Screening"},
    "dash.analysis.raman.template.raman.general.desc": {
        "tr": "Genel Raman: hareketli ortalama yumuşatma, doğrusal taban çizgisi, SNV normalizasyonu, kosinüs benzerliği eşlemesi.",
        "en": "General Raman: Moving-average smoothing, linear baseline, SNV normalization, cosine similarity matching.",
    },
    "dash.analysis.raman.template.raman.polymorph_screening.desc": {
        "tr": "Polimorf taraması: daha kısa yumuşatma, daha sık tepe çıkarma, Pearson odaklı eşleştirme.",
        "en": "Polymorph Screening: Shorter smoothing window, denser peak extraction, Pearson-focused matching.",
    },
    "dash.analysis.xrd.title": {"tr": "XRD analizi", "en": "XRD Analysis"},
    "dash.analysis.xrd.caption": {
        "tr": "XRD uyumlu veri seti seçin, şablonu seçin ve nitel faz taramasını çalıştırın.",
        "en": "Select an XRD-eligible dataset, choose a workflow template, and run qualitative phase screening.",
    },
    "dash.analysis.xrd.run_btn": {"tr": "XRD analizini çalıştır", "en": "Run XRD Analysis"},
    "dash.analysis.xrd.empty_import": {"tr": "Önce bir XRD dosyası içe aktarın.", "en": "Import an XRD file first."},
    "dash.analysis.xrd.workflow_fallback": {"tr": "XRD analiz iş akışı.", "en": "XRD analysis workflow."},
    "dash.analysis.xrd.template.xrd.general.label": {"tr": "Genel XRD", "en": "General XRD"},
    "dash.analysis.xrd.template.xrd.phase_screening.label": {"tr": "Faz taraması", "en": "Phase Screening"},
    "dash.analysis.xrd.template.xrd.general.desc": {
        "tr": "Genel XRD: eksen normalizasyonu, yumuşatma, taban çizgisi düzeltmesi ve ağırlıklı tepe örtüşmesi taraması.",
        "en": "General XRD: axis normalization, smoothing, baseline correction, and weighted peak-overlap screening.",
    },
    "dash.analysis.xrd.template.xrd.phase_screening.desc": {
        "tr": "Faz taraması: daha sıkı tepe filtreleri ve nitel üst-N aday incelemesi.",
        "en": "Phase Screening: tighter peak filters and qualitative top-N candidate review.",
    },
    "dash.analysis.xrd.candidate_unknown": {"tr": "Bilinmeyen aday", "en": "Unknown Candidate"},
    "dash.analysis.xrd.match_detail_line": {
        "tr": "Ağırlıklı örtüşme: {overlap}; kapsam: {coverage}; ortalama delta 2θ: {delta}",
        "en": "Weighted overlap: {overlap}; coverage: {coverage}; mean delta 2theta: {delta}",
    },
    "dash.analysis.id_label": {"tr": "Kimlik: {id}", "en": "ID: {id}"},
    "dash.analysis.unknown_candidate": {"tr": "Bilinmiyor", "en": "Unknown"},
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
