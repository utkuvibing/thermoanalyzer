# XRD / FTIR / Raman Materyal Eşleştirme — Kütüphane & Veritabanı Araştırması

ThermoAnalyzer projesine XRD, FTIR ve Raman spektral analiz + materyal eşleştirme (phase identification) kabiliyeti eklemek için kullanılabilecek **tüm ücretsiz ve ticari** seçeneklerin araştırma özeti.

---

## 1. Spektral Veritabanları (Referans Veri Kaynakları)

### 🟢 ÜCRETSİZ / OPEN-ACCESS

| Veritabanı | Teknik | İçerik | Erişim | Entegrasyon Notu |
|---|---|---|---|---|
| **[COD](https://www.crystallography.net/cod/)** (Crystallography Open Database) | XRD | 520.000+ kristal yapı, CIF formatı | Web + API + Dump | Python'dan CIF parse edilebilir (`pymatgen`, `ase`) |
| **[AMCSD](http://rruff.geo.arizona.edu/AMS/amcsd.php)** (Amer. Mineralogist Crystal Structure DB) | XRD | Mineral kristal yapıları | Web | COD'un alt kümesi, mineral odaklı |
| **[RRUFF Project](https://rruff.info/)** | Raman + XRD | Binlerce mineral Raman + XRD pattern'ı | Web + Dosya indirme | `.txt` formatında spektra, kolay parse |
| **[Raman Open Database (ROD)](https://solsa.crystallography.net/rod/)** | Raman | COD ile bağlantılı Raman spektraları | Web + API | CIF formatı ile yapısal veri entegre |
| **[NIST Chemistry WebBook](https://webbook.nist.gov/)** | FTIR | Geniş organik/inorganik IR spektra koleksiyonu | Web | Web scraping veya JCAMP-DX format |
| **[SDBS](https://sdbs.db.aist.go.jp/)** (AIST Japan) | FTIR + Raman + NMR + MS | Organik bileşikler (inorganik alt DB de var) | Web (ücretsiz) | Görsel + veri indirilebilir |
| **[IRUG Spectral Database](https://irug.org/)** | FTIR + Raman | Sanat/kültürel miras materyalleri | Web | Topluluk katkılı, niş ama kaliteli |
| **[INFRA-ART](https://infraart.inoe.ro/)** | ATR-FTIR + XRF + Raman | Sanatçı boyama malzemeleri | Web (open-access) | Niş alan |
| **[Pigments Checker](https://chsopensource.org/)** | Raman | Tarihsel + modern pigmentler | Web (.txt format) | Kolay parse |
| **[RamanBase](https://ramanbase.org/)** | Raman | Çeşitli materyaller, AI-based ID | Web + API | Public API mevcut |

---

### 🔴 TİCARİ (PAID / LİSANSLI)

| Veritabanı / Ürün | Teknik | İçerik | Fiyat Aralığı | Not |
|---|---|---|---|---|
| **[ICDD PDF](https://www.icdd.com/)** (Powder Diffraction File) | XRD | En kapsamlı XRD referans DB (PDF-2, PDF-4, PDF-5+) | **~$2.600–$18.000** (akademik–ticari, süreye göre) | Endüstri standardı, SIeve search yazılımı dahil |
| **[Wiley KnowItAll](https://sciencesolutions.wiley.com/)** (eski Bio-Rad/Sadtler) | FTIR + Raman | 343.000+ IR, 28.000+ Raman spektra | **Teklif bazlı** (yıllık abonelik) | En büyük ticari FTIR/Raman kütüphanesi |
| **[Match!](https://www.crystalimpact.com/match/)** | XRD | Phase identification yazılımı (COD + ICDD desteği) | ~€600+ (lisans) | COD ile ücretsiz kullanılabilir |
| **NICODOM Libraries** | FTIR | Polimer, ilaç, organik/inorganik | ~€200-2.000+ | 50 spektralık demo ücretsiz |

---

## 2. Python Kütüphaneleri (Kod/İşleme Araçları)

### XRD Phase Identification

| Kütüphane | Durum | Özellikler | `pip install` |
|---|---|---|---|
| **[pymatgen](https://pymatgen.org/)** | ⭐ Ücretsiz, açık kaynak | XRD pattern simülasyonu, kristal yapı eşleştirme, COD/Materials Project entegrasyonu | `pip install pymatgen` |
| **[GSAS-II](https://subversion.xray.aps.anl.gov/trac/pyGSAS)** | Ücretsiz, açık kaynak | Rietveld refinement, kapsamlı XRD analiz | Özel kurulum gerekli |
| **[Profex](https://www.profex-xrd.org/)** | Ücretsiz (GUI) | Rietveld refinement, COD browse, search-match | Standalone uygulama |
| **[PyFAI](https://pyfai.readthedocs.io/)** | Ücretsiz, açık kaynak | Azimuthal integration, kalibrasyon | `pip install pyfai` |
| **[HEXRD](https://github.com/HEXRD/hexrd)** | Ücretsiz, açık kaynak | Genel XRD analiz (powder, Laue) | `pip install hexrd` |
| **[XRD-AutoAnalyzer](https://github.com/)** | Ücretsiz, açık kaynak | Deep learning tabanlı otomatik faz tanıma | GitHub'dan |

### FTIR / Raman Spektral Analiz

| Kütüphane | Teknik | Özellikler | `pip install` |
|---|---|---|---|
| **[RamanSPy](https://ramanspy.readthedocs.io/)** | Raman (+ IR uygulanabilir) | Veri yükleme, ön-işleme, analiz, ML entegrasyonu | `pip install ramanspy` |
| **[boxsers](https://pypi.org/project/boxsers/)** | Raman + FTIR + SERS | Data augmentation, boyut indirgeme, ML yöntemleri | `pip install boxsers` |
| **[pyspectra](https://pypi.org/project/pyspectra/)** | NIR + FTIR + Raman | MSC, SNV, Savitzky-Golay filtre, ön-işleme | `pip install pyspectra` |
| **[SpectraFit](https://pypi.org/project/spectrafit/)** | Genel spektroskopi | İnteraktif pik fitting, ATR-FTIR destekli | `pip install spectrafit` |
| **[ramanbiolib](https://github.com/mteranm/ramanbiolib)** | Raman | Biyolojik molekül tanıma, spektral benzerlik + pik eşleştirme | GitHub'dan |

### Genel Sinyal İşleme (Tüm Teknikler İçin)

| Kütüphane | Kullanım | Not |
|---|---|---|
| **scipy.signal** | Filtreleme, FFT, pik bulma, konvolüsyon | Zaten `requirements.txt`'te mevcut ✅ |
| **numpy** | Dizi işlemleri, korelasyon hesaplamaları | Zaten mevcut ✅ |
| **lmfit** | Pik fitting, curve fitting | Zaten mevcut ✅ |
| **pybaselines** | Baseline düzeltme | Zaten mevcut ✅ |

### Standalone Yazılımlar (GUI Tabanlı)

| Yazılım | Durum | Özellikler |
|---|---|---|
| **[SpectraGryph](https://www.effemm2.de/spectragryph/)** | Ücretsiz (akademik) | FTIR + Raman format açma, kütüphane arama, RRUFF entegrasyonu |
| **[OpenXRD](https://sourceforge.net/projects/openxrd/)** | Ücretsiz, GPL | XRD analiz, pik arama, mineral tanıma |

---

## 3. Tavsiye: ThermoAnalyzer İçin En Uygun Strateji

### Hemen Uygulanabilir (Ücretsiz)

Projenin mevcut Python stack'ine en uyumlu yaklaşım:

```
Aşama 1 — Veritabanı Entegrasyonu
├── XRD: COD (CIF dosyaları) + pymatgen ile pattern simülasyonu/eşleştirme
├── Raman: RRUFF Project + ROD (indirilebilir spektra)
└── FTIR: NIST WebBook + SDBS (parse edilebilir veri)

Aşama 2 — Python İşleme Katmanı
├── pymatgen → XRD faz tanıma motoru
├── RamanSPy / boxsers → Raman spektral ön-işleme + eşleştirme
├── scipy.signal (mevcut) → Korelasyon bazlı matching algoritması
└── pybaselines + lmfit (mevcut) → Baseline düzeltme + pik fitting

Aşama 3 — Eşleştirme Algoritması
├── Cosine similarity / Pearson korelasyon → hızlı kaba eşleştirme
├── Peak-position matching → hassas doğrulama
└── Kullanıcı kendi kütüphanesini yükleyebilme (custom library)
```

### Ticari Yükseltme (İhtiyaç Olursa)

| Öncelik | Ürün | Neden |
|---|---|---|
| 1 | **ICDD PDF-2** (~$2.600 akademik) | XRD faz tanıma için altın standart |
| 2 | **Wiley KnowItAll** (teklif bazlı) | FTIR/Raman eşleştirme için en kapsamlı |
| 3 | **Match! + COD** (~€600) | Hızlı GUI tabanlı XRD faz tanıma |

---

## 4. Özet Karşılaştırma

| Kriter | Ücretsiz Yol | Ticari Yol |
|---|---|---|
| **Maliyet** | $0 | $3.000–$20.000+/yıl |
| **XRD kapsamı** | COD (520K+ yapı) — iyi ama ICDD kadar kuratlı değil | ICDD PDF (endüstri standardı) |
| **FTIR kapsamı** | NIST + SDBS — orta düzey | KnowItAll (343K+ spektra) — çok kapsamlı |
| **Raman kapsamı** | RRUFF + ROD — mineraller için mükemmel | KnowItAll (28K+ spektra) — geniş kapsam |
| **Python entegrasyonu** | Kolay (pymatgen, RamanSPy, scipy) | Zor (genelde kapalı format, API yok) |
| **Uygunluk** | Akademik/startup/MVP | Endüstriyel QC/sertifikasyon |

> [!TIP]
> **Başlangıç için önerim:** COD + RRUFF + NIST ücretsiz veritabanları + `pymatgen` + `RamanSPy` kombinasyonu, ThermoAnalyzer'a hızlıca materyal eşleştirme kabiliyeti kazandırır. İleride ihtiyaç olursa ICDD PDF veya KnowItAll aboneliği eklenebilir.
