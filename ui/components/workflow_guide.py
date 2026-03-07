"""Informational workflow guides for trial and onboarding flows."""

from __future__ import annotations

import streamlit as st

from utils.i18n import tx


def _render_list(title: str, items: list[str]) -> None:
    st.markdown(f"**{title}**")
    for item in items:
        st.markdown(f"- {item}")


def render_home_workflow_guide() -> None:
    """Explain the product scope and recommended operator workflow."""
    with st.expander(tx("Program Rehberi ve İş Akışı", "Program Guide and Workflow"), expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            _render_list(
                tx("Program ne yapar?", "What does the program do?"),
                [
                    tx(
                        "CSV, TXT ve Excel formatlarındaki DSC/TGA veri setlerini cihazdan bağımsız olarak içe aktarır.",
                        "Imports DSC/TGA datasets from CSV, TXT, and Excel files without locking the workflow to a single vendor.",
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
                        "4. Aktif koşuya göre DSC Analizi veya TGA Analizi sayfasına geçin ve sekmeleri soldan sağa takip edin.",
                        "4. Open DSC Analysis or TGA Analysis for the active run and move through the tabs from left to right.",
                    ),
                    tx(
                        "5. Sonuçları oturuma kaydedin; ardından rapor veya proje çıktısını Rapor Merkezi / Proje Alanı sayfalarından alın.",
                        "5. Save the results to the session, then generate report or project outputs from the Report Center / Project Workspace pages.",
                    ),
                ],
            )

        st.caption(
            tx(
                "Kararlı beta kapsamı: DSC, TGA, Karşılaştırma Alanı, Toplu Şablon Uygulayıcı, rapor/dışa aktarım ve proje arşivi. DTA, kinetik ve dekonvolüsyon önizleme olarak kalır.",
                "Stable beta scope: DSC, TGA, Compare Workspace, Batch Template Runner, report/export, and project archive flows. DTA, kinetics, and deconvolution remain preview.",
            )
        )


def render_tga_workflow_guide() -> None:
    """Explain the purpose and interpretation of the TGA workflow."""
    with st.expander(tx("TGA Sayfası Rehberi", "TGA Page Guide"), expanded=True):
        col1, col2, col3 = st.columns(3)

        with col1:
            _render_list(
                tx("Bu sayfa ne yapar?", "What does this page do?"),
                [
                    tx(
                        "Ham TGA eğrisini sıcaklığa karşı kalan kütle olarak gösterir.",
                        "Shows the raw TGA curve as remaining mass versus temperature.",
                    ),
                    tx(
                        "DTG türevi ile en hızlı kütle kaybı bölgelerini görünür hale getirir.",
                        "Computes the DTG derivative so rapid mass-loss regions become easier to inspect.",
                    ),
                    tx(
                        "Başlangıç, orta nokta, bitiş, toplam kütle kaybı ve kalıntı yüzdesini otomatik çıkarır.",
                        "Automatically extracts onset, midpoint, endset, total mass loss, and residue metrics.",
                    ),
                ],
            )

        with col2:
            _render_list(
                tx("Sekmeleri hangi sırayla kullanmalı?", "Which tab order should you follow?"),
                [
                    tx("1. Ham Veri sekmesinde veri aralığını ve metadata bilgisini kontrol edin.", "1. Use Raw Data to inspect range, quality, and metadata."),
                    tx("2. Gürültü varsa Yumuşatma / DTG sekmesinde yumuşatma uygulayın.", "2. Apply smoothing in Smoothing / DTG only when noise hides the decomposition shape."),
                    tx(
                        "3. Adım Analizi sekmesinde adım tespitini çalıştırıp prominence veya minimum kütle kaybı eşiğini ayarlayın.",
                        "3. Run Step Analysis and tune prominence or minimum mass-loss thresholds when needed.",
                    ),
                    tx(
                        "4. Sonuç Özeti sekmesinde özet metrikleri doğrulayıp sonucu oturuma kaydedin.",
                        "4. Review Results Summary, then save the validated result to the session.",
                    ),
                ],
            )

        with col3:
            _render_list(
                tx("Yorumlama notları", "Interpretation notes"),
                [
                    tx(
                        "DTG eğrisindeki en belirgin negatif bölgeler bozunmanın en hızlı olduğu sıcaklıkları temsil eder.",
                        "The strongest negative DTG regions correspond to temperatures where decomposition is fastest.",
                    ),
                    tx(
                        "Aşırı yumuşatma onset/endset sıcaklıklarını kaydırabilir; gürültüyü bastırırken adım kenarlarını koruyun.",
                        "Over-smoothing can shift onset/endset temperatures; suppress noise without flattening step edges.",
                    ),
                    tx(
                        "Numune kütlesi metadata olarak girilmişse yüzde kayba ek olarak mg cinsinden mutlak kayıp da hesaplanır.",
                        "If sample mass is present in metadata, the workflow also calculates absolute mass loss in mg.",
                    ),
                ],
            )

        st.caption(
            tx(
                "Bu iş akışı veriyi değiştirmez; yalnızca oturum içi analiz kopyaları ve dışa aktarılabilir sonuçlar üretir.",
                "This workflow does not modify the raw data; it creates in-session analysis layers and exportable results only.",
            )
        )
