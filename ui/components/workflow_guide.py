"""Informational workflow guides for trial and onboarding flows."""

from __future__ import annotations

import streamlit as st

from utils.i18n import tx


def _render_list(title: str, items: list[str]) -> None:
    st.markdown(f"**{title}**")
    for item in items:
        st.markdown(f"- {item}")


_ANALYSIS_GUIDES = {
    "DSC": {
        "title": ("DSC Sayfası Rehberi", "DSC Page Guide"),
        "what": [
            (
                "Ham DSC eğrisini ısı akışı ve sıcaklık ekseninde gösterir.",
                "Shows the raw DSC curve on heat-flow versus temperature axes.",
            ),
            (
                "Yumuşatma, baz çizgisi düzeltmesi, Tg tespiti ve pik karakterizasyonunu aynı oturum state'i üzerinde yürütür.",
                "Runs smoothing, baseline correction, Tg detection, and peak characterization on the same in-session state.",
            ),
            (
                "Kaydedilen sonuçları rapor, proje arşivi ve literatür karşılaştırması akışına hazırlar.",
                "Prepares saved results for report, project archive, and literature comparison flows.",
            ),
        ],
        "order": [
            (
                "1. Ham Veri sekmesinde sıcaklık aralığını, sinyal yönünü ve metadata bilgisini doğrulayın.",
                "1. Use Raw Data to confirm the temperature range, signal direction, and metadata.",
            ),
            (
                "2. Gürültü Tg veya pik yorumunu bozuyorsa Yumuşatma sekmesinde kontrollü smoothing uygulayın.",
                "2. Apply controlled smoothing only when noise hides Tg or peak behavior.",
            ),
            (
                "3. Baz çizgisi kayıyorsa Baseline Correction ile çalışma sinyalini stabilize edin.",
                "3. Stabilize the working signal with Baseline Correction when the baseline drifts.",
            ),
            (
                "4. Amorf geçiş arıyorsanız Tg sekmesini, termal olay arıyorsanız Pik Analizi sekmesini izleyin.",
                "4. Use Glass Transition for amorphous transitions and Peak Analysis for thermal events.",
            ),
            (
                "5. Sonuç Özeti sekmesinde doğrulayıp sonucu oturuma kaydedin.",
                "5. Validate the output in Results Summary, then save it to the session.",
            ),
        ],
        "notes": [
            (
                "Aşırı yumuşatma Tg orta noktasını ve pik alanını kaydırabilir; minimum gerekli smoothing ile ilerleyin.",
                "Over-smoothing can shift Tg midpoints and peak areas; use the minimum smoothing needed.",
            ),
            (
                "Baz çizgisi seçimi entalpi ve onset/endset değerlerini doğrudan etkiler.",
                "Baseline selection directly affects enthalpy and onset/endset values.",
            ),
            (
                "Numune kütlesi metadata'da varsa normalize ve rapor metrikleri daha tutarlı olur.",
                "Metadata sample mass improves normalization and report consistency when it is available.",
            ),
        ],
        "footer": (
            "Bu iş akışı ham veriyi değiştirmez; yalnızca oturum içi analiz katmanları ve kaydedilebilir sonuçlar üretir.",
            "This workflow does not modify raw data; it only creates in-session analysis layers and saveable results.",
        ),
    },
    "DTA": {
        "title": ("DTA Sayfası Rehberi", "DTA Page Guide"),
        "what": [
            (
                "Ham DTA eğrisini sıcaklığa karşı termal fark sinyali olarak gösterir.",
                "Shows the raw DTA curve as a thermal-difference signal versus temperature.",
            ),
            (
                "Yumuşatma, baz çizgisi düzeltmesi ve ekzotermik/endotermik olay tespitini aynı analiz akışında toplar.",
                "Combines smoothing, baseline correction, and exothermic/endothermic event detection in one analysis flow.",
            ),
            (
                "Pik sonuçlarını proje kalıcılığı ve rapor çıktısı için kaydedilebilir hale getirir.",
                "Makes peak results saveable for project persistence and report outputs.",
            ),
        ],
        "order": [
            (
                "1. Ham Veri sekmesinde sinyal yönünü, aralığı ve numune metadata bilgisini kontrol edin.",
                "1. Inspect signal direction, range, and sample metadata in Raw Data.",
            ),
            (
                "2. Gürültü baskınsa Yumuşatma sekmesinde kontrollü smoothing uygulayın.",
                "2. Apply controlled smoothing in Smoothing when noise dominates the curve.",
            ),
            (
                "3. Baz çizgisi kayıyorsa Baseline Correction ile çalışma sinyalini düzeltin.",
                "3. Use Baseline Correction when the working signal drifts.",
            ),
            (
                "4. Pik Analizi sekmesinde endotermik/ekzotermik aramayı ve eşikleri ayarlayın.",
                "4. Tune endothermic/exothermic search and thresholds in Peak Analysis.",
            ),
            (
                "5. Sonuç Özeti sekmesinde doğrulayıp kaydı oturuma alın.",
                "5. Validate the output in Results Summary, then save it to the session.",
            ),
        ],
        "notes": [
            (
                "Ham sinyalin yönü cihaz ve export formatına göre değişebilir; yorumu pik tipine göre doğrulayın.",
                "Raw signal direction can vary by instrument and export format; confirm interpretation from the detected peak type.",
            ),
            (
                "Aşırı baz çizgisi düzeltmesi küçük termal olayları bastırabilir.",
                "Aggressive baseline correction can suppress subtle thermal events.",
            ),
            (
                "Metadata'daki ısıtma hızı yorum ve karşılaştırma notları için önemlidir.",
                "Heating-rate metadata matters for interpretation and comparison notes.",
            ),
        ],
        "footer": (
            "Bu iş akışı ham DTA verisini değiştirmez; yorum katmanları ve kaydedilebilir sonuçlar üretir.",
            "This workflow does not modify raw DTA data; it creates interpretation layers and saveable results.",
        ),
    },
    "TGA": {
        "title": ("TGA Sayfası Rehberi", "TGA Page Guide"),
        "what": [
            (
                "Ham TGA eğrisini sıcaklığa karşı kalan kütle olarak gösterir.",
                "Shows the raw TGA curve as remaining mass versus temperature.",
            ),
            (
                "DTG türevi ile en hızlı kütle kaybı bölgelerini görünür hale getirir.",
                "Computes the DTG derivative so rapid mass-loss regions become easier to inspect.",
            ),
            (
                "Başlangıç, orta nokta, bitiş, toplam kütle kaybı ve kalıntı yüzdesini otomatik çıkarır.",
                "Automatically extracts onset, midpoint, endset, total mass loss, and residue metrics.",
            ),
        ],
        "order": [
            (
                "1. Ham Veri sekmesinde veri aralığını ve metadata bilgisini kontrol edin.",
                "1. Use Raw Data to inspect range, quality, and metadata.",
            ),
            (
                "2. Gürültü varsa Yumuşatma / DTG sekmesinde yumuşatma uygulayın.",
                "2. Apply smoothing in Smoothing / DTG only when noise hides the decomposition shape.",
            ),
            (
                "3. Adım Analizi sekmesinde adım tespitini çalıştırıp prominence veya minimum kütle kaybı eşiğini ayarlayın.",
                "3. Run Step Analysis and tune prominence or minimum mass-loss thresholds when needed.",
            ),
            (
                "4. Sonuç Özeti sekmesinde özet metrikleri doğrulayıp sonucu oturuma kaydedin.",
                "4. Review Results Summary, then save the validated result to the session.",
            ),
        ],
        "notes": [
            (
                "DTG eğrisindeki en belirgin negatif bölgeler bozunmanın en hızlı olduğu sıcaklıkları temsil eder.",
                "The strongest negative DTG regions correspond to temperatures where decomposition is fastest.",
            ),
            (
                "Aşırı yumuşatma onset/endset sıcaklıklarını kaydırabilir; gürültüyü bastırırken adım kenarlarını koruyun.",
                "Over-smoothing can shift onset/endset temperatures; suppress noise without flattening step edges.",
            ),
            (
                "Numune kütlesi metadata olarak girilmişse yüzde kayba ek olarak mg cinsinden mutlak kayıp da hesaplanır.",
                "If sample mass is present in metadata, the workflow also calculates absolute mass loss in mg.",
            ),
        ],
        "footer": (
            "Bu iş akışı veriyi değiştirmez; yalnızca oturum içi analiz kopyaları ve dışa aktarılabilir sonuçlar üretir.",
            "This workflow does not modify the raw data; it creates in-session analysis layers and exportable results only.",
        ),
    },
    "FTIR": {
        "title": ("FTIR Sayfası Rehberi", "FTIR Page Guide"),
        "what": [
            (
                "Ham FTIR spektrumunu dalgasayısı ekseninde gösterir.",
                "Shows the raw FTIR spectrum on the wavenumber axis.",
            ),
            (
                "Ön işleme, pik çıkarımı ve nitel benzerlik aday sıralamasını aynı workflow içinde toplar.",
                "Combines preprocessing, peak extraction, and qualitative similarity ranking in one workflow.",
            ),
            (
                "Kaydedilen spektral sonuçları rapor ve proje akışına taşır.",
                "Carries saved spectral results into report and project flows.",
            ),
        ],
        "order": [
            (
                "1. Raw Spectrum sekmesinde eksen yönünü, aralığı ve metadata bilgisini kontrol edin.",
                "1. Inspect axis direction, range, and metadata in Raw Spectrum.",
            ),
            (
                "2. Ön işleme sekmesinde smoothing, baseline ve normalization adımlarını sadece gerektiği kadar uygulayın.",
                "2. Use preprocessing to apply only the smoothing, baseline, and normalization that the spectrum needs.",
            ),
            (
                "3. Peak Detection sekmesinde pik listesini ve eşikleri doğrulayın.",
                "3. Validate the peak list and thresholds in Peak Detection.",
            ),
            (
                "4. Similarity / Library sonuçlarını yorumlayıp sonucu oturuma kaydedin.",
                "4. Review similarity/library results and save the validated result to the session.",
            ),
        ],
        "notes": [
            (
                "FTIR'da ters eksen gösterimi yorum için önemlidir; dalgasayısı yönünü değiştirmeyin.",
                "Reverse-axis display matters in FTIR interpretation; keep the wavenumber direction consistent.",
            ),
            (
                "Aşırı smoothing dar bantları silebilir ve fonksiyonel grup yorumunu zayıflatabilir.",
                "Over-smoothing can erase narrow bands and weaken functional-group interpretation.",
            ),
            (
                "Kütüphane adayları nitel yönlendiricidir; son yorum spektrum bağlamı ile birlikte verilmelidir.",
                "Library candidates are qualitative guides; final interpretation still needs spectral context.",
            ),
        ],
        "footer": (
            "Bu iş akışı spektrumu değiştirmez; oturum içi işlenmiş katmanlar ve kaydedilebilir sonuçlar üretir.",
            "This workflow does not modify the raw spectrum; it creates in-session processed layers and saveable results.",
        ),
    },
    "RAMAN": {
        "title": ("Raman Sayfası Rehberi", "Raman Page Guide"),
        "what": [
            (
                "Ham Raman spektrumunu Raman kayması ekseninde gösterir.",
                "Shows the raw Raman spectrum on the Raman-shift axis.",
            ),
            (
                "Ön işleme, pik çıkarımı ve nitel benzerlik aday sıralamasını aynı workflow içinde yürütür.",
                "Runs preprocessing, peak extraction, and qualitative similarity ranking in one workflow.",
            ),
            (
                "Kaydedilen sonuçları rapor ve proje çıktısına hazır hale getirir.",
                "Prepares saved results for report and project outputs.",
            ),
        ],
        "order": [
            (
                "1. Raw Spectrum sekmesinde aralığı, sinyal kalitesini ve metadata bilgisini inceleyin.",
                "1. Review range, signal quality, and metadata in Raw Spectrum.",
            ),
            (
                "2. Ön işleme sekmesinde fluoresans veya taban etkisini bastıracak kadar smoothing/baseline uygulayın.",
                "2. Apply enough smoothing/baseline work to suppress fluorescence or background effects in preprocessing.",
            ),
            (
                "3. Peak Detection sekmesinde aday pikleri ve eşikleri doğrulayın.",
                "3. Validate candidate peaks and thresholds in Peak Detection.",
            ),
            (
                "4. Similarity / Library sonuçlarını inceleyip sadece doğruladığınız sonucu kaydedin.",
                "4. Review similarity/library output and save only the validated result.",
            ),
        ],
        "notes": [
            (
                "Raman'da taban etkisi ve fluoresans yükselmesi benzerlik skorlarını doğrudan etkiler.",
                "Background drift and fluorescence strongly affect Raman similarity scores.",
            ),
            (
                "Aşırı preprocessing zayıf fakat anlamlı pikleri kaybettirebilir.",
                "Aggressive preprocessing can remove weak but meaningful peaks.",
            ),
            (
                "Library eşleşmeleri tek başına kimlik doğrulaması değildir; pik bağlamı ile birlikte yorumlanmalıdır.",
                "Library matches alone are not identity proof; interpret them together with peak context.",
            ),
        ],
        "footer": (
            "Bu iş akışı ham Raman verisini değiştirmez; işlenmiş katmanlar ve kaydedilebilir sonuçlar üretir.",
            "This workflow does not modify raw Raman data; it creates processed layers and saveable results.",
        ),
    },
    "XRD": {
        "title": ("XRD Sayfası Rehberi", "XRD Page Guide"),
        "what": [
            (
                "Ham XRD desenini 2θ ekseninde gösterir ve eksen/metaveri uygunluğunu doğrular.",
                "Shows the raw XRD pattern on the 2θ axis and checks axis/metadata suitability.",
            ),
            (
                "Eksen normalizasyonu, pik çıkarımı ve nitel faz adayı eşlemesini tek workflow içinde yürütür.",
                "Runs axis normalization, peak extraction, and qualitative phase-candidate matching in one workflow.",
            ),
            (
                "Kaydedilen sonucu rapor grafiği, proje kalıcılığı ve library provenance ile ilişkilendirir.",
                "Links the saved result to report figures, project persistence, and library provenance.",
            ),
        ],
        "order": [
            (
                "1. Raw Pattern sekmesinde eksen tipini, aralığı ve dalgaboyu metadata'sını kontrol edin.",
                "1. Use Raw Pattern to confirm axis type, range, and wavelength metadata.",
            ),
            (
                "2. Pipeline sekmesinde eksen normalizasyonu, smoothing ve baseline parametrelerini ayarlayın.",
                "2. Configure axis normalization, smoothing, and baseline parameters in Pipeline.",
            ),
            (
                "3. Peaks sekmesinde gözlenen pik listesini ve eşiklerini doğrulayın.",
                "3. Validate observed peaks and thresholds in Peaks.",
            ),
            (
                "4. Matches sekmesinde faz adaylarını yorumlayın; ardından Results sekmesinden kaydı doğrulayın.",
                "4. Review phase candidates in Matches, then validate the saved record in Results.",
            ),
        ],
        "notes": [
            (
                "Yanlış 2θ ekseni veya eksik dalgaboyu bilgisi eşleştirme kalitesini düşürür.",
                "An incorrect 2θ axis or missing wavelength metadata lowers matching quality.",
            ),
            (
                "Pik eşiği çok düşük tutulursa gürültü faz adayı puanlarını bozabilir.",
                "Very low peak thresholds can let noise distort phase-candidate scores.",
            ),
            (
                "Library eşleşmeleri nitel faz taraması içindir; kesin faz doğrulaması değildir.",
                "Library matches support qualitative phase screening rather than definitive phase confirmation.",
            ),
        ],
        "footer": (
            "Bu iş akışı ham difraksiyon verisini değiştirmez; oturum içi yorum katmanları ve kaydedilebilir eşleşme sonuçları üretir.",
            "This workflow does not modify raw diffraction data; it creates in-session interpretation layers and saveable matching results.",
        ),
    },
}


def render_home_workflow_guide() -> None:
    """Explain the product scope and recommended operator workflow."""
    with st.expander(tx("Program Rehberi ve İş Akışı", "Program Guide and Workflow"), expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            _render_list(
                tx("Program ne yapar?", "What does the program do?"),
                [
                    tx(
                        "CSV, TXT ve Excel formatlarındaki DSC/TGA/DTA/FTIR/RAMAN/XRD veri setlerini cihazdan bağımsız olarak içe aktarır.",
                        "Imports DSC/TGA/DTA/FTIR/RAMAN/XRD datasets from CSV, TXT, and Excel files without locking the workflow to a single vendor.",
                    ),
                    tx(
                        "Sıcaklık, sinyal ve metadata alanlarını tek çalışma alanında normalize eder.",
                        "Normalizes temperature, signal, and metadata fields into one shared workspace.",
                    ),
                    tx(
                        "Analiz sonuçlarını, grafikleri, rapor çıktısını ve proje arşivini aynı oturum içinde yönetir.",
                        "Keeps analysis results, figures, report exports, and project archives in the same session.",
                    ),
                    tx(
                        "Belirsiz import durumlarında review uyarıları üretir; kolon, tip ve sinyal birimi tahminlerini gizli kesinlik gibi sunmaz.",
                        "Generates review warnings for ambiguous imports instead of presenting type, column, or signal-unit guesses as hidden certainty.",
                    ),
                ],
            )

        with col2:
            _render_list(
                tx("Önerilen kullanım sırası", "Recommended usage order"),
                [
                    tx("1. Ham dosyanızı veya örnek veriyi yükleyin.", "1. Load your raw file or one of the sample datasets."),
                    tx(
                        "2. Kolon eşlemesini, numune adını, numune kütlesini ve ısıtma hızını kontrol edin.",
                        "2. Review the column mapping, sample name, sample mass, and heating rate.",
                    ),
                    tx(
                        "2a. İçe aktarım güveni review ise veri tipini ve sinyal birimini manuel olarak doğrulayın.",
                        "2a. If the import confidence is review, manually confirm the data type and signal unit before continuing.",
                    ),
                    tx(
                        "3. Hızlı Görünüm veya Karşılaştırma Alanı ile koşunun beklediğiniz sinyali verdiğini doğrulayın.",
                        "3. Use Quick View or Compare Workspace to confirm that the run behaves as expected.",
                    ),
                    tx(
                        "4. Aktif koşuya göre DSC/TGA/DTA/FTIR/RAMAN/XRD Analizi sayfasına geçin ve sekmeleri soldan sağa takip edin.",
                        "4. Open DSC/TGA/DTA/FTIR/RAMAN/XRD Analysis for the active run and move through the tabs from left to right.",
                    ),
                    tx(
                        "5. Sonuçları oturuma kaydedin; ardından rapor veya proje çıktısını Rapor Merkezi / Proje Alanı sayfalarından alın.",
                        "5. Save the results to the session, then generate report or project outputs from the Report Center / Project Workspace pages.",
                    ),
                ],
            )

        st.caption(
            tx(
                "Kararlı beta kapsamı: DSC, TGA, DTA, FTIR, RAMAN, XRD, Karşılaştırma Alanı, Toplu Şablon Uygulayıcı, rapor/dışa aktarım ve proje arşivi. Kinetik ve dekonvolüsyon önizleme olarak kalır.",
                "Stable beta scope: DSC, TGA, DTA, FTIR, RAMAN, XRD, Compare Workspace, Batch Template Runner, report/export, and project archive flows. Kinetics and deconvolution remain preview.",
            )
        )


def render_analysis_workflow_guide(analysis_type: str) -> None:
    """Render a three-column workflow guide for a stable analysis page."""
    token = str(analysis_type or "").upper()
    guide = _ANALYSIS_GUIDES.get(token)
    if guide is None:
        return

    with st.expander(tx(*guide["title"]), expanded=True):
        col1, col2, col3 = st.columns(3)

        with col1:
            _render_list(
                tx("Bu sayfa ne yapar?", "What does this page do?"),
                [tx(tr, en) for tr, en in guide["what"]],
            )

        with col2:
            _render_list(
                tx("Sekmeleri hangi sırayla kullanmalı?", "Which tab order should you follow?"),
                [tx(tr, en) for tr, en in guide["order"]],
            )

        with col3:
            _render_list(
                tx("Yorumlama notları", "Interpretation notes"),
                [tx(tr, en) for tr, en in guide["notes"]],
            )

        st.caption(
            tx(*guide["footer"])
        )


def render_tga_workflow_guide() -> None:
    """Backward-compatible TGA workflow guide wrapper."""
    render_analysis_workflow_guide("TGA")
