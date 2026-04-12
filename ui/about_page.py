"""Expanded product/about page."""

from __future__ import annotations

import streamlit as st

from ui.components.chrome import render_page_header
from utils.i18n import t, tx


def render() -> None:
    render_page_header(t("about.title"), t("about.caption"), badge=t("about.hero_badge"))

    overview_tab, scope_tab, standards_tab = st.tabs(
        [
            tx("Genel Bakış", "Overview"),
            tx("Kapsam ve Yol Haritası", "Scope and Roadmap"),
            tx("Referanslar", "References"),
        ]
    )

    with overview_tab:
        col1, col2 = st.columns([1.35, 1])

        with col1:
            st.markdown(
                tx(
                    """
**MaterialScope**, QC ve Ar-Ge laboratuvarları için cihazdan bağımsız, çok modlu bir karakterizasyon çalışma alanıdır.

Bu ürün tek bir vendor formatına kilitlenmeden DSC, TGA, DTA, FTIR, Raman ve XRD koşularını aynı oturum içinde içe aktarmayı, karşılaştırmayı, analiz etmeyi ve raporlamayı hedefler.

Merkez yaklaşım şudur:
- ham veriyi tek bir normalize çalışma alanında toplamak
- her modalite için kararlı ve izlenebilir analiz akışı sunmak
- sonuçları rapor, proje arşivi ve dışa aktarım yüzeyiyle aynı ürün mantığında bağlamak
                    """,
                    """
**MaterialScope** is a vendor-independent, multimodal characterization workbench for QC and R&D laboratories.

The product is designed to import, compare, analyze, and report DSC, TGA, DTA, FTIR, Raman, and XRD runs inside one shared session without locking the workflow to a single vendor format.

The core approach is:
- collect raw runs inside one normalized workspace
- provide stable and traceable analysis flows for each modality
- connect results to reporting, project archive, and export surfaces inside the same product logic
                    """,
                )
            )

        with col2:
            st.metric(tx("Kararlı Modalite", "Stable Modalities"), "6")
            st.metric(tx("Ana Yüzey", "Core Surfaces"), "Import / Compare / Analyze / Report / Project")
            st.metric(tx("Dağıtım Profili", "Deployment Profile"), tx("Web Demo + Masaüstü Yönü", "Web Demo + Desktop Direction"))

        st.info(
            tx(
                "Bu sayfa ürünün neyi çözmeye çalıştığını, bugün hangi kapsamın kararlı olduğunu ve hangi alanların önizleme olarak tutulduğunu açıklar.",
                "This page explains what the product is trying to solve, which scope is stable today, and which areas remain preview-only.",
            )
        )

    with scope_tab:
        stable_col, preview_col = st.columns(2)

        with stable_col:
            st.markdown(f"### {tx('Kararlı Beta Kapsamı', 'Stable Beta Scope')}")
            st.markdown(
                tx(
                    """
- CSV/TXT/XLSX exportlarından DSC, TGA, DTA, FTIR, Raman ve XRD koşularını içe aktarma
- Karşılaştırma Alanı ile çoklu koşu overlay ve ortak metadata kontrolü
- Modalite bazlı kararlı analiz akışları
- Rapor Merkezi ile dışa aktarım ve rapor üretimi
- Proje Alanı ile oturum/proje arşivleme
                    """,
                    """
- Import DSC, TGA, DTA, FTIR, Raman, and XRD runs from CSV/TXT/XLSX exports
- Multi-run overlays and shared metadata review through Compare Workspace
- Stable modality-specific analysis workflows
- Export and report generation through Report Center
- Session/project archiving through Project Workspace
                    """,
                )
            )

        with preview_col:
            st.markdown(f"### {tx('Önizleme ve Gelecek Alanlar', 'Preview and Next Areas')}")
            st.markdown(
                tx(
                    """
- Kinetik ve dekonvolüsyon modülleri hâlâ önizleme katmanında tutulur
- Üyelik/lisans/ticari paketleme akışı henüz son ürün seviyesinde değildir
- Custom domain, son prod sertleştirme ve geniş erişim politikaları daha sonraki fazdadır
                    """,
                    """
- Kinetics and deconvolution remain in the preview layer
- Membership, licensing, and commercial packaging are not yet in final-product shape
- Custom domain, final production hardening, and broader access policies are planned for a later phase
                    """,
                )
            )

        st.caption(
            tx(
                "Hedef kısa vadede hazır görünen değil, güvenilir kullanılan bir analiz yüzeyi oluşturmaktır.",
                "The near-term goal is not to look finished, but to become reliably usable.",
            )
        )

    with standards_tab:
        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"### {tx('Referans Standartlar', 'Reference Standards')}")
            st.markdown(
                tx(
                    """
- ASTM E967 — DSC sıcaklık ve entalpi kalibrasyonu
- ASTM E1131 — TGA ile kompozisyon analizi
- ASTM E1356 — DSC ile cam geçişi
- ICTAC kinetik analiz rehberleri
                    """,
                    """
- ASTM E967 — DSC temperature and enthalpy calibration
- ASTM E1131 — compositional analysis by TGA
- ASTM E1356 — glass transition by DSC
- ICTAC kinetic analysis guidance
                    """,
                )
            )

        with col2:
            st.markdown(f"### {tx('Ürün Yönü', 'Product Direction')}")
            st.markdown(
                tx(
                    """
- bugün: hoca/demo odaklı web erişimi
- yakın hedef: ready-to-use ürün yüzeyi ve kararlı proje/rapor akışı
- daha sonra: masaüstü kabuk, lisans yönetimi ve ticari dağıtım
                    """,
                    """
- today: instructor/demo-focused web access
- near-term goal: ready-to-use product surface and stable project/report flow
- later: desktop shell, license management, and commercial distribution
                    """,
                )
            )
