# **Thermoanalyzer Projesi İçin XRD, FTIR ve Raman Analiz ve Materyal Eşleştirme Kütüphanelerinin Kapsamlı Mimari ve Algoritmik Değerlendirmesi**

Modern materyal bilimi, bileşiklerin sentezi, karakterizasyonu ve tersine mühendisliği süreçlerinde çok modlu (multi-modal) analitik tekniklerin entegrasyonuna dayanmaktadır. Diferansiyel Taramalı Kalorimetri (DSC), Termogravimetrik Analiz (TGA) ve Diferansiyel Termal Analiz (DTA) gibi termal analiz yöntemleri, bir malzemenin termal stabilitesi, bozunma kinetiği ve faz geçiş entalpileri hakkında kritik veriler sunarken, bu veriler malzemenin tam kimyasal veya kristalografik kimliğini belirlemek için tek başlarına yeterli olmamaktadır. Bu noktada X-Işını Kırınımı (XRD), Fourier Dönüşümlü Kızılötesi (FTIR) ve Raman spektroskopisi devreye girmektedir. Geliştirilmekte olan thermoanalyzer projesi, tedarikçiden bağımsız bir termal analiz çalışma alanı sunmakta olup, Streamlit tabanlı kullanıcı arayüzü ve FastAPI destekli arka uç mimarisi ile tekrarlanabilir bilimsel raporlamalar (.thermozip arşivi) yapmayı hedeflemektedir.1 Projenin dosya sisteminde yer alan .tmp/academic\_data/ftir\_raman\_raw dizini, sistemin termal verilerin ötesine geçerek spektroskopik ham verileri işlemeye yönelik mimari bir hazırlık içinde olduğunu göstermektedir.1

Bu rapor, thermoanalyzer ekosistemine entegre edilmek üzere, XRD, FTIR ve Raman verilerini kullanarak doğrudan materyal eşleştirme (phase identification ve spectral search-match) işlemlerini gerçekleştirebilecek açık kaynaklı (ücretsiz) ve ticari (ücretli) kütüphaneleri, algoritmik yaklaşımları ve veritabanı uygulama programlama arayüzlerini (API) derinlemesine incelemektedir. Analizler; kütüphanelerin matematiksel modellerini, Python entegrasyon kapasitelerini, lisans kısıtlamalarını ve çok modlu bir yazılım mimarisine uyum süreçlerini kapsamaktadır.

## **Thermoanalyzer Mimari Bağlamı ve Veri İşleme Dinamikleri**

Spektroskopik ve kristalografik kütüphanelerin değerlendirilmesine geçmeden önce, hedef sistemin mevcut mimarisinin anlaşılması gereklidir. thermoanalyzer projesi, modüler bir yapıya sahip olup bilimsel hesaplamaları core/ dizininde, arayüz bileşenlerini ui/ dizininde ve sunucu işlemlerini backend/ dizininde yürütmektedir.1 Veri içe aktarma süreci; CSV, TXT, TSV ve XLSX formatlarını desteklemekte olup, sütun rollerinin, ayırıcıların ve ondalık formatların otomatik olarak algılandığı, belirsizlik farkındalığına sahip (ambiguity-aware) bir güven mekanizması ile çalışmaktadır.1

Mevcut TGA ve DSC analiz modülleri, temel çizgi (baseline) düzeltmeleri, asimetrik tepe ayrıştırması (peak deconvolution), türev termogravimetri (DTG) çözünürlüklü olay yapıları ve stokiyometrik kütle dengesi kontrolleri gibi sinyal işleme algoritmalarına dayanmaktadır.1 Sisteme eklenecek olan XRD, FTIR ve Raman modüllerinin de bu mevcut veri işleme felsefesine uyum sağlaması, yani ham veriyi alıp ön işlemlerden (örneğin kozmik ışın temizleme, floresans arka plan çıkarımı) geçirdikten sonra referans veritabanları ile istatistiksel eşleştirme yapması gerekecektir. Sistem aynı zamanda Electron sarmalayıcısı aracılığıyla desktop/ dizini altında masaüstü uygulaması olarak da derlenebilmektedir.1 Bu masaüstü derleme yeteneği, ilerleyen bölümlerde tartışılacak olan ticari kütüphanelerin katı lisanslama (EULA) kısıtlamalarını aşmak için kritik bir çözüm yolu sunmaktadır.

## **X-Işını Kırınımı (XRD) Faz Tanımlama ve Materyal Eşleştirme Kütüphaneleri**

X-Işını kırınımı analizi, malzemelerin kristalografik yapısını, birim hücre parametrelerini ve faz bileşimlerini belirlemek için kullanılan temel bir analitik yöntemdir. Deneysel bir XRD deseninin analiz edilmesi, genellikle elde edilen pik konumlarının (![][image1] açıları) ve bağıl şiddetlerinin, bilinen materyallerin teorik veya ampirik referans desenleriyle karşılaştırılmasını (search-match) gerektirir. Python ekosisteminde bu süreci otomatikleştiren çeşitli açık kaynaklı ve ticari yaklaşımlar bulunmaktadır.

### **Açık Kaynaklı ve Ücretsiz Python Modülleri**

Açık kaynaklı XRD analiz kütüphaneleri, genellikle Crystallography Open Database (COD) veya Materials Project gibi açık erişimli veritabanlarıyla entegre çalışarak maliyetsiz ve genişletilebilir çözümler sunarlar. Bu kütüphaneler, sinyal işleme tabanlı eşleştirmeden derin öğrenme tabanlı örüntü tanımaya kadar geniş bir yelpazede algoritmik yaklaşımlar kullanmaktadır.

#### **Pymatgen (Python Materials Genomics)**

Materials Project'in temel hesaplama motoru olan Pymatgen, materyal bilimi verilerinin analizi için geliştirilmiş en sağlam, endüstri standardı açık kaynaklı Python kütüphanesidir.2 Kütüphane, materyallerin kristal yapılarını modellemek, işlemek ve bu yapılar üzerinden teorik fiziksel özellikleri hesaplamak için oldukça esnek nesne yönelimli sınıflar sunar.3

Pymatgen kütüphanesinin XRD analizi yetenekleri pymatgen.analysis.diffraction.xrd modülü altında toplanmıştır.5 Bu modül içerisinde yer alan XRDCalculator sınıfı, herhangi bir kristal yapı nesnesi (örneğin bir CIF dosyasından dönüştürülmüş bir model) üzerinden teorik toz kırınım (powder diffraction) desenlerini yüksek hassasiyetle hesaplayabilmektedir.7 Hesaplama algoritması, yalnızca basit bir Bragg açısı tespiti yapmakla kalmaz; aynı zamanda atomik saçılma faktörlerini, sıcaklığa bağlı Debye-Waller faktörlerini, Lorentz-polarizasyon düzeltmelerini ve kırınım düzlemlerinin çokluk (multiplicity) faktörlerini denkleme dahil ederek deneysel sonuçlara son derece yakın bağıl şiddetler üretir.8

Materyal eşleştirme bağlamında Pymatgen, pymatgen.ext.cod modülü aracılığıyla Crystallography Open Database (COD) ile doğrudan API düzeyinde iletişim kurabilir.6 Bir thermoanalyzer kullanıcısı sisteme deneysel bir XRD deseni yüklediğinde, algoritma öncelikle COD veritabanından şüpheli element sistemlerine ait CIF dosyalarını çekebilir, bu dosyaları XRDCalculator ile teorik desenlere dönüştürebilir ve ardından Jaccard benzerlik indeksi veya StructureMatcher sınıfını kullanarak deneysel veri ile eşleştirme yapabilir.9 Ek olarak, Pymatgen altyapısı, ağaç arama (tree search) tabanlı algoritmalar kullanılarak izostrüktürel (benzer yapılı) fazların otomatik olarak kümelenmesi ve elenmesi süreçlerinde de etkin rol oynamaktadır.10

#### **XERUS (X-ray Estimation and Refinement Using Similarity)**

Özellikle çok fazlı (multi-phase) inorganik karışımların analizinde geleneksel tepe noktası (peak-matching) yöntemleri yetersiz kalabilmektedir. XERUS, bu sorunu çözmek amacıyla geliştirilmiş, Python tabanlı açık kaynaklı bir faz tanımlama ve arıtım (refinement) otomasyon aracıdır.11

XERUS'un temel çalışma prensibi, önceden eğitilmiş ağır makine öğrenimi modellerine ihtiyaç duymadan, hesaplamalı veri tabanlarından (COD, Materials Project, AFLOW, OQMD) elde edilen referans yapılarla deneysel spektrumlar arasında Pearson korelasyon katsayılarına dayalı doğrudan bir benzerlik araması yapmasıdır.11 Uygulama, deneysel verideki en baskın fazı belirledikten sonra, iteratif bir desen çıkarma (pattern removal) işlemi uygular. Bu süreçte, tanımlanan baskın fazın sinyalleri genel spektrumdan matematiksel olarak çıkarılır ve kalan kalıntı (residual) arka plan üzerinde minör fazlar için yeniden benzerlik araması başlatılır.11 XERUS, elde edilen bu öncül eşleşmeleri doğrulamak ve fazların ağırlıkça yüzdelerini nicel olarak belirlemek için arka planda GSAS-II Scriptable Engine kütüphanesini kullanarak otomatik ve hızlı Rietveld arıtımı gerçekleştirir.11 thermoanalyzer projesinin "belirsizlik farkındalığına sahip" yaklaşımıyla mükemmel uyum sağlayan bu iteratif ve doğrulama odaklı metodoloji, karmaşık XRD verilerinin analizinde yüksek güvenilirlik sunar.

#### **Makine Öğrenimi ve Derin Öğrenme Temelli Yaklaşımlar (XRD-AutoAnalyzer ve CPICANN)**

Geleneksel faz eşleştirme algoritmalarının yerini, spektral veriyi bir bütün olarak değerlendiren yapay zeka modelleri almaya başlamıştır. XRD-AutoAnalyzer kütüphanesi, fizik bilgisiyle desteklenmiş veri artırma (physics-informed data augmentation) teknikleriyle eğitilmiş bir Olasılıklı Derin Öğrenme (Probabilistic Deep Learning) modelidir.15 Bu modül, referans CIF dosyalarından yalnızca ideal kristal desenlerini simüle etmekle kalmaz, aynı zamanda stokiyometrik olmayan katı çözeltileri (solid solutions), aletsel pik genişlemelerini ve çeşitli gürültü profillerini sisteme enjekte ederek (--include\_ns parametresi üzerinden) Evrişimli Sinir Ağlarını (CNN) eğitir.15 Deneysel bir spektrum analiz edildiğinde, model sadece bir eşleşme listesi sunmakla kalmaz, aynı zamanda her bir faz için bir "olasılık ve güven yüzdesi" döndürür.15 Bu olasılık bazlı çıktı formatı, thermoanalyzer arayüzündeki güven metrikleri sunumuna doğrudan entegre edilebilir.

Bir diğer çığır açıcı yaklaşım ise CPICANN (Convolutional Self-Attention Neural Network) mimarisidir. Geleneksel eşleştirme yazılımları genellikle kullanıcıdan öncül element bilgisi talep ederken, CPICANN herhangi bir element kısıtlaması olmaksızın faz tespiti yapabilmektedir.16 Literatürde, 23.073 farklı inorganik kristal yapıdan üretilmiş 692.190 adet simüle edilmiş toz kırınım deseni üzerinde eğitilen bu modelin, element bilgisi olmadan tek fazlı eşleştirmelerde %87.5, element bilgisi ile %98.5 doğruluğa ulaştığı rapor edilmiştir.16 Bu oranlar, ticari endüstri standartlarını geride bırakan bir yapay zeka devrimini işaret etmektedir. CPICANN kaynak kodlarının Python tabanlı olarak erişilebilir olması, modelin thermoanalyzer arka ucuna entegrasyonunu uygulanabilir kılmaktadır.16

#### **Veri İndirgeme ve Ön İşleme Araçları (xrayutilities ve PyXRD)**

Ham kırınım verilerinin doğrudan eşleştirmeye tabi tutulmadan önce fiziksel olarak anlamlı 1B spektrumlara dönüştürülmesi gereklidir. xrayutilities, C dilinde kodlanmış uzantıları sayesinde oldukça yüksek performanslı bir veri indirgeme ve analiz kütüphanesidir.17 Özellikle senkrotron ışınım hatlarından veya 2 boyutlu (alan) dedektörlerden elde edilen karmaşık görüntülerin (örneğin SPEC, EDF, XRDML, CBF formatları), kırınım geometrisi ve gonyometre açıları dikkate alınarak ters uzaya (reciprocal space) veya geleneksel ![][image1] ızgaralarına (grid) dönüştürülmesinde kullanılır.18 thermoanalyzer projesinin veri içe aktarma motoru, xrayutilities yardımıyla özel cihaz formatlarını standartlaştırılmış dizilere çevirebilir.

Daha spesifik materyal sınıfları için, özellikle toprak ve polimer biliminde sıklıkla karşılaşılan düzensiz tabakalı yapıların (örneğin karışık tabakalı kil mineralleri) modellenmesi amacıyla PyXRD kütüphanesi kullanılabilir.21 PyXRD, çoklu numune tam profil uydurma yöntemini destekler ve L-BFGS-B, Brute Force ve Parçacık Sürüsü Optimizasyonu (Particle Swarm Optimization \- MPSO) gibi algoritmalarla donatılmıştır.21

| Açık Kaynak Kütüphane | Temel İşlev ve Algoritmik Yaklaşım | Öne Çıkan Avantajlar | Entegrasyon Yöntemi |
| :---- | :---- | :---- | :---- |
| **Pymatgen** | Teorik kırınım deseni simülasyonu ve Jaccard indeksi tabanlı yapı eşleştirme | Geniş ekosistem, API desteği (COD, Materials Project), kararlı altyapı | Doğrudan Python modülü (import pymatgen) |
| **XERUS** | Pearson korelasyonu ile iteratif desen çıkarma ve GSAS-II destekli Rietveld arıtımı | Çok fazlı karışımlarda yüksek başarı, açık veritabanı kullanımı | Python tabanlı Jupyter/Scripting entegrasyonu |
| **XRD-AutoAnalyzer** | Veri artırımlı Evrişimli Sinir Ağları (CNN) ile olasılıklı faz sınıflandırma | Katı çözeltileri tanıma yeteneği, olasılık yüzdesi raporlama | CLI veya Python betiği (import autoXRD) |
| **CPICANN** | Öz-dikkat (Self-attention) tabanlı sinir ağları ile elementsiz faz tespiti | Ön bilgi gerektirmeyen yüksek doğruluklu tahmin | Python kaynak kodu uyarlaması |
| **xrayutilities** | 2B dedektör verilerinin ters uzaya dönüşümü ve format ayrıştırma | Yüksek performanslı C eklentileri, kapalı cihaz formatı desteği | Doğrudan Python modülü (import xrayutilities) |

### **Ticari ve Ücretli XRD Çözümleri**

Açık kaynaklı kütüphaneler hesaplama mimarisini güçlü bir şekilde sağlasa da, ticari çözümlerin asıl değeri barındırdıkları küratörlü, ISO sertifikalı ve kalitesi doğrulanmış ampirik veritabanlarından kaynaklanmaktadır. Bu alandaki pazar lideri Uluslararası Kırınım Verileri Merkezi'dir (ICDD).

#### **ICDD PDF-4 Veritabanı Ailesi ve SIeve+**

ICDD'nin Powder Diffraction File (PDF) veritabanları, dünya çapında kristalografik referans verilerinin altın standardı olarak kabul edilir. Bu veritabanları, CCDC, FIZ ve NIST gibi uluslararası kuruluşlarla yapılan işbirlikleri sayesinde sürekli güncellenmektedir.23

* **Veri İçeriği ve Çeşitlilik:** PDF-4+ serisi, yüz binlerce benzersiz materyal girişini içerir. Veritabanı içindeki kayıtlar, atomik koordinatları, moleküler grafikleri, Referans Şiddet Oranı (![][image2]) değerlerini ve yüksek kaliteli dijital ham deneysel desenleri barındırır.24 Bu veriler; seramikler, metaller ve alaşımlar, polimerler, eczacılık aktif bileşenleri (API) ve adli bilimler numuneleri gibi sayısız alt sınıfa (subfile) göre kategorize edilmiştir.25  
* **SIeve+ Arama Motoru:** Veritabanı lisanslarıyla birlikte kullanıcılara ücretsiz olarak sunulan SIeve+ yazılımı, bilinmeyen çok fazlı numunelerin tanımlanması için optimize edilmiş bir arama ve indeksleme motorudur.27 SIeve+, 118 farklı veri görüntüleme alanı ve 84 farklı arama filtresi (elementel bileşim, fiziksel özellikler, kristalografik veriler) sunarak Boolean mantığı ile karmaşık veri madenciliği yapılmasına imkan tanır.27  
* **Lisanslama Modelleri ve Maliyet Geometrisi:** thermoanalyzer projesine ICDD veritabanlarını entegre etmenin önündeki en büyük teknik ve ekonomik engel lisanslama politikalarıdır.  
  * **PDF-4/Axiom:** Temel düzey laboratuvar kullanıcıları için tasarlanmış, 114.000'den fazla giriş içeren daha uygun maliyetli bir sürümdür. Düzenli faz tanımlaması ve RIR tabanlı nicel analizler için yeterlidir.25 Bu ürün 3 yıllık bir lisans süresiyle sunulmakta olup, standart ticari liste fiyatı yaklaşık $3,715, akademik liste fiyatı ise $2,550 seviyelerindedir.24  
  * **PDF-4/Minerals:** Sadece mineralojik ve jeolojik materyallere odaklanan, Uluslararası Mineraloji Birliği (IMA) sınıflandırmalarına sahip 54.900'den fazla veri içeren özel bir pakettir.27 Yıllık abonelik modeline dayalı olarak çalışan bu paketin tekil lisans maliyeti ticari kurumlar için $1,840, akademik kullanıcılar için ise daha indirimli bir fiyattır.27  
* **Mimari ve API Kısıtlamaları:** Geliştiriciler için en kritik engel, ICDD Son Kullanıcı Lisans Sözleşmesi'nin (EULA) içerdiği katı kurallardır. Veritabanlarına bir ağ üzerinden (network) erişilmesi, bulut sunucularına yerleştirilmesi veya masaüstü paylaşım yazılımları üzerinden dağıtılması kesinlikle yasaklanmıştır.25 Bu durum, thermoanalyzer projesinin FastAPI tabanlı merkezi bir arka uç üzerinden kullanıcılara ICDD destekli bir arama hizmeti sunamayacağı anlamına gelir. ICDD veritabanı entegrasyonu ancak projenin desktop/ dizininde yer alan Electron tabanlı masaüstü uygulamasının, kullanıcının kendi yerel bilgisayarında kurulu olan yerel (local) lisanslı bir PDF-4 veritabanı ile etkileşime girmesi yoluyla yasal bir zemine oturtulabilir.

## ---

**Fourier Dönüşümlü Kızılötesi (FTIR) Spektroskopisi İçin Materyal Eşleştirme Çözümleri**

Kızılötesi spektroskopisi, moleküllerin titreşim frekanslarını ve dipol moment değişikliklerini ölçerek, numunenin fonksiyonel grup kompozisyonunu ve organik kimliğini belirleyen kritik bir yöntemdir. thermoanalyzer iş akışlarında özellikle TGA işleminden yayılan gazların analizinde (TGA-FTIR) veya bağımsız materyal doğrulama testlerinde kullanılır.32 FTIR spektrumları, XRD pikleri gibi keskin değil, aksine örtüşen geniş bantlardan oluştuğundan, eşleştirme algoritmaları doğrudan spektral korelasyona, türevsel haritalamaya ve derin öğrenmeye dayanmak zorundadır.

### **Açık Kaynaklı Python Araçları ve Eşleştirme Ekosistemi**

FTIR verilerinin işlenmesi, karbondioksit veya su buharı parazitlerinin giderilmesi, taban çizgisinin düzeltilmesi ve sinyal normalizasyonu gibi karmaşık ön işlem adımları gerektirir. Python ekosistemi, bu süreçleri yönetmek ve açık referans kütüphaneleriyle eşleştirme yapmak için güçlü modüller barındırır.

#### **OpenSpecy ve openspi (Python Interface)**

OpenSpecy, başlangıçta mikroplastikler, çevresel polimerler ve organik materyallerin FTIR ve Raman spektrumlarını analiz etmek, işlemek ve sınıflandırmak amacıyla geliştirilmiş kapsamlı bir R paketidir.33 Bu güçlü analitik motorun Python tabanlı projelere entegrasyonu, openspi isimli bir arayüz (wrapper) kütüphanesi aracılığıyla sağlanmaktadır.35

* **Çalışma Mekanizması ve Mimari:** openspi, rpy2 modülü üzerinden arka planda R çalışma ortamını tetikleyerek çalışır. Python betiği yürütülmeden önce R\_HOME çevre değişkeninin sistemde kurulu olan R derleyicisine işaret edecek şekilde tanımlanması zorunludur.35 openspi\_main fonksiyonu; CSV, SPC, SPA ve JDX gibi çeşitli spektral formatları toplu olarak içe aktarır, R paketine aktarır ve analiz sonuçlarını temizlenmiş bir Excel tablosuna dönüştürür.35  
* **Veri Ön İşleme:** Kütüphanenin process\_spec fonksiyonu; sinyal pürüzsüzleştirme, spektral düzleştirme, taban çizgisi düzeltmesi (baseline correction), dalga boyu hizalaması ve minimum-maksimum normalizasyonu gibi kritik ön işleme adımlarını uygular.36 Bu adımlar, cihaz kalibrasyon farklılıklarından kaynaklanan varyasyonları ortadan kaldırarak veriyi eşleştirmeye hazır hale getirir.  
* **Materyal Eşleştirme:** Eşleştirme işlemi, match\_spec fonksiyonu kullanılarak gerçekleştirilir. Bu algoritma, ön işlemden geçmiş deneysel spektrumu, OpenSpecy'nin açık erişimli çevrimiçi referans kütüphanesi (özellikle türev \- derivative kütüphanesi) ile Pearson korelasyon katsayısı üzerinden kıyaslar.35 Sistemin varsayılan konfigürasyonu, her bir spektrum için istatistiksel olarak en olası ilk 5 materyal eşleşmesini ("top 5") raporlamak üzere kurgulanmıştır.35  
* **Thermoanalyzer İçin Dezavantajlar:** thermoanalyzer projesi konteynerize edilmiş (Docker) bir bulut uygulaması olarak dağıtılacaksa, sunucu imajının içine hem Python hem de R dillerinin ve ilgili tüm istatistiksel kütüphanelerinin kurulması gerekecektir. Bu durum, DevOps süreçlerini zorlaştıracak ve sistem kaynak tüketimini artıracaktır.

#### **SpectraFit**

SpectraFit, moleküler spektrumların gelişmiş eğri uydurma (curve fitting) teknikleriyle analiz edilmesi için tasarlanmış çapraz platform destekli bir Python kütüphanesidir.38 Doğrudan eşleştirme yapmaktan ziyade, karmaşık FTIR bantlarını bireysel titreşim bileşenlerine ayırmak (deconvolution) için idealdir.

* **Matematiksel Temeller:** lmfit optimizasyon çerçevesi üzerine inşa edilen SpectraFit, Güven Bölgesi Yansıtmalı (Trust Region Reflective) yöntemi gibi 23 farklı doğrusal olmayan en küçük kareler optimizasyon algoritmasını bünyesinde barındırır.39 Karmaşık absorbsiyon bantlarını Gauss, Lorentz veya Voigt fonksiyonları kullanarak matematiksel bileşenlerine ayırır.  
* **Veri Mimarisi:** Yazılım, verileri yönetmek için Pandas DataFrame yapılarını kullanır. Bu mimari tercih, thermoanalyzer'ın halihazırda CSV ve XLSX dosyalarını içe aktarmak için kullandığı veri işleme akışıyla (pipeline) tam uyum sağlar.1 Terminal üzerinden (CLI) hızlı analizler yapılabileceği gibi, Jupyter ve Streamlit ortamlarında daha detaylı veri mühendisliği gerçekleştirilebilir.38

#### **Photizo**

Daha çok yüksek hacimli biyolojik ve klinik araştırmalar için geliştirilmiş olan Photizo, çoklu numune analizine (cross-sample analysis) odaklanan açık kaynaklı bir Python kütüphanesidir.40

* **Makromoleküler Haritalama:** Özellikle taramalı kızılötesi mikrospektroskopi ve odak düzlemli dizi (FPA) dedektörlerinden elde edilen devasa uzamsal veri kümelerini işlemek için tasarlanmıştır.40 Biyoinformatik alanından ödünç alınan SCANPY kütüphanesini ve AnnData nesnelerini entegre ederek, binlerce FTIR spektrumu üzerinde Temel Bileşenler Analizi (PCA), spektral kümeleme ve makromoleküler nicelleştirme işlemlerini son derece yüksek performansla gerçekleştirir.40

#### **OpenVibSpec**

Titreşimsel spektroskopi verilerindeki temel zorluklardan biri olan fiziksel optik hataları gidermeye odaklanan OpenVibSpec, makine öğrenimi modellerinin eğitilmesi için temiz veriler sağlamayı amaçlar.43

* **Fiziksel Düzeltmeler:** Özellikle biyolojik numunelerde veya mikropartiküllerde gözlemlenen ve kızılötesi absorbsiyon bantlarının şeklini ciddi şekilde bozan Mie saçılmasını (Mie scattering) gidermek için Genişletilmiş Çarpanlı Sinyal Düzeltme (EMSC) paketini kullanır.43 Ayrıca asimetrik en küçük kareler (AsLS) algoritması ile taban çizgisi düzeltmesini gerçekleştirir. Bu temizlenmiş veriler daha sonra kütüphane içindeki Rastgele Orman (Random Forest) algoritmalarıyla doğrudan sınıflandırmaya tabi tutulabilir.43

### **Ticari ve Ücretli FTIR Çözümleri**

Organik kimyasallar, polimerler, adli tıp numuneleri ve endüstriyel çözücülerin tam ve kesin olarak tanımlanması için ticari veritabanları vazgeçilmezdir. Endüstride bu alanın tartışmasız lideri Wiley KnowItAll ve NIST entegrasyonlarıdır.

#### **Wiley KnowItAll SDK ve SmartSpectra Veritabanı**

Wiley, ünlü Sadtler ve Hummel koleksiyonlarını barındıran, 343.000'den fazla ampirik (gerçek cihazlarda ölçülmüş) yüksek kaliteli IR spektrumu ile dünyanın en büyük kızılötesi referans kütüphanesine sahiptir.45 NIST'in (Ulusal Standartlar ve Teknoloji Enstitüsü) kapsamlı Kütle Spektrometrisi (MS) ve IR kütüphaneleri de Wiley sistemi üzerinden ortaklaşa sorgulanabilmektedir.46

* **Yapay Zeka ile Spektral Tahmin (SmartSpectra):** Ampirik veritabanları ne kadar büyük olursa olsun, sentezlenen yeni moleküllerin veya nadir bileşiklerin spektrumlarını kapsayamazlar. Bu sorunu çözmek için Wiley, makine öğrenimi tabanlı "SmartSpectra" teknolojisini geliştirmiştir.47 Bu teknoloji, Wiley'nin muazzam ampirik veritabanı üzerinde eğitilmiş yapay zeka modelleri kullanarak, sentezlenebilecek olası moleküllerin spektrumlarını kuantum mekaniksel hassasiyetle tahmin eder. Yeni piyasaya sürülen "Wiley Database of Predicted IR Spectra", 250.000'den fazla yapay zeka tarafından üretilmiş kızılötesi spektrum içermektedir.48 Deneysel eşleşmelerin (Hit Quality Index \- HQI) düşük kaldığı durumlarda bu tahmin veritabanı, bilinmeyen moleküllerin fonksiyonel yapılarını doğru bir şekilde teşhis edebilir.47  
* **Geliştirici Entegrasyonları (SDK):** thermoanalyzer gibi özel platformlar geliştirenler için Wiley, iki farklı Yazılım Geliştirme Kiti (SDK) sunar:  
  * **Spectrum Transfer SDK:** thermoanalyzer arayüzünden elde edilen bir spektrumu, doğrudan Wiley'nin tescilli KnowItAll yazılımına aktarmak için tasarlanmıştır. Bu işlem, paylaşılan bellek (shared memory) üzerinden veya bir terminal komut satırı (shell function) çağrısı ile gerçekleştirilir.50  
  * **KnowItAll Automate SDK:** Tam otomasyon hedefleyen projeler için en uygun yoldur. Bu SDK sayesinde, KnowItAll grafik kullanıcı arayüzü (GUI) açılmadan, arka planda (background) gizli olarak API üzerinden kütüphane aramaları tetiklenebilir, lisanslı sınıflandırma modelleri çalıştırılabilir ve sonuç raporları otomatik olarak oluşturularak thermoanalyzer'a geri döndürülebilir.51  
* **Maliyet Modelleri:** Wiley ürünleri, modüler yıllık abonelik (Annual Subscription) sistemiyle lisanslanmaktadır.52 Yalnızca temel yazılım olan "Analytical Edition", 12.000 spektrumluk sınırlı bir organik/polimer alt kümesi ile gelir.52 Genişletilmiş kütüphaneler için "KnowItAll IR Identification Pro" veya hem IR hem Raman verilerini içeren "IR/Raman Identification Pro" lisans paketlerinin satın alınması gerekir.52 Kesin liste fiyatları kurumsal/akademik talebe göre değişmekle birlikte, geniş çaplı ticari kütüphanelerin lisans bedelleri genellikle birkaç bin dolar seviyesinden başlamaktadır.52

## ---

**Raman Spektroskopisi Analizi ve Materyal Eşleştirme Kütüphaneleri**

Raman spektroskopisi, moleküllerin inelastik ışık saçılımı prensibine (polarizasyon değişimine) dayanarak titreşimsel ve dönmesel enerji seviyelerini ölçen tahribatsız bir analitik yöntemdir.53 Su moleküllerinin Raman aktif olmaması nedeniyle, kızılötesi spektroskopisinin zorlandığı sulu çözeltilerin, canlı biyolojik numunelerin ve kompleks jeolojik minerallerin analizinde eşsiz avantajlar sunar.53

Raman spektrumlarının analizindeki en büyük algoritmik zorluk, ölçüm sırasında ortaya çıkan yoğun floresans arka planının ve detektöre çarpan yüksek enerjili kozmik ışın (cosmic ray) parazitlerinin gerçek moleküler parmak izinden ayrıştırılmasıdır. Python ekosistemi, bu engelleri aşmak ve dünyanın en geniş mineral veritabanı olan RRUFF ile iletişim kurmak için modern açık kaynaklı mimarilere ev sahipliği yapmaktadır.

### **Açık Kaynaklı Python Araçları ve RRUFF Veritabanı Entegrasyonu**

Raman verilerinin temizlenmesi, modellenmesi ve çok bileşenli karışımların çözümlenmesi için açık kaynaklı Python kütüphaneleri, son teknoloji makine öğrenimi modülleriyle entegre bir biçimde çalışmaktadır.

#### **RamanSPy**

RamanSPy, donanım üreticilerinin kapalı ve kısıtlayıcı yazılım ekosistemlerinden (vendor lock-in) kaçınmak, araştırma süreçlerini standartlaştırmak ve yapay zeka teknolojilerini analitik süreçlere dahil etmek amacıyla geliştirilmiş, oldukça kapsamlı ve modüler bir açık kaynak Python kütüphanesidir.53 thermoanalyzer projesinin tedarikçiden bağımsız vizyonuyla birebir örtüşen bir felsefeye sahiptir.

* **Kapsamlı Veri Ön İşleme (Preprocessing):** Kütüphane, Raman analizine özgü tüm zorlukları adresleyen gelişmiş algoritma boru hatları (pipelines) barındırır. Kozmik ışınları tespit edip silmek için Whittaker-Hayes despiking algoritmasını, gürültüyü azaltmak için Savitzky-Golay ve Kernel filtrelerini kullanır.54 En kritik aşama olan floresans taban çizgisi düzeltmesi (baseline correction) için Asimetrik En Küçük Kareler (ASLS), AIRPLS, IARPLS, ModPoly ve Goldindec gibi endüstri standartlarını destekler.53  
* **İleri Ayrıştırma (Spectral Unmixing):** Deneysel verinin birden fazla molekül veya mineralden oluşan bir karışım olduğu durumlarda, RamanSPy sinyali saf endüstriyel bileşenlerine ayırmak için PPI, FIPPI, NFINDR ve VCA (Vertex Component Analysis) gibi matematiksel ayrıştırma algoritmaları kullanır.54 Bileşenlerin nicel bolluğunu belirlemek için tam kısıtlamalı en küçük kareler (FCLS) veya negatif olmayan en küçük kareler (NNLS) yöntemlerini entegre eder.55  
* **Veri Okuyucular ve Model Doğrulama:** WITec, Renishaw ve Ocean Insight gibi lider donanım üreticilerinin özel formatlarını doğrudan Python nesnelerine dönüştürebilir.54 Ayrıca makine öğrenimi modellerinin eğitilmesi için bakteri, hücre hatları, mineraller (RRUFF tabanlı) ve COVID-19 örneklerini içeren açık veri setlerini anında indiren veri yükleyicileri (data loaders) sunar.54 Modellerin validasyonu için bünyesinde sentetik Raman verisi üreteçleri de barındırır.57

#### **Ramanalysis ve RamanMatch**

Özellikle mineraloji, jeokimya ve inorganik kimya alanlarında numunelerin tanımlanması, genellikle çok büyük spektral kütüphaneler içerisinde manuel karşılaştırma gerektiren zahmetli bir süreçtir. Ramanalysis ve RamanMatch gibi Python araçları, açık erişimli RRUFF veritabanı API'sini entegre ederek bu süreci tam otomatik hale getirir.58

* **RRUFF Projesi Entegrasyonu:** RRUFF, dünyadaki en saygın ve kapsamlı açık mineral Raman spektrumu deposudur.60 Veritabanındaki her bir referans materyal, X-ışını kırınımı ve ıslak kimya analizleriyle çapraz olarak titizlikle doğrulanmıştır.60 Ramanalysis, bu kütüphanedeki referans spektrumları doğrudan indirip işleyebilen interaktif bir Python aracıdır.58  
* **Çoklu Pik Eşleştirme Algoritması (Multi-Peak Matching):** Pazardaki birçok basit eşleştirme aracı yalnızca spektrumdaki en yüksek şiddetli tek bir piki hedeflerken, bu yazılım asimetrik ağırlıklandırılmış cezalandırılmış en küçük kareler uyumu (asymmetrically-reweighted penalized least-squares fit) ile arka planı sildikten sonra, belirli bir "belirginlik" (prominence) eşiğini aşan tüm pikleri tespit eder.58 Eşleştirme algoritması, hem dalga sayısı (wavenumber) sapmalarını hem de pik belirginliğini aynı anda hesaba katan sofistike bir puanlama sistemi kullanır. Deneysel spektrum ile referans kütüphanesini korele ederek en yüksek puanı alan beş (top-5) minerali listeler.58 thermoanalyzer projesi, mineral veya inorganik kimya sektörünü hedefliyorsa, bu yaklaşımı sistem çekirdeğine dahil etmelidir.

#### **rampy ve ramanbiolib**

* **rampy:** Raman ve kızılötesi spektrumların temel işlenmesi için geliştirilmiş, köklü bir Python kütüphanesidir.62 Temel olarak scipy, numpy ve matplotlib üzerine inşa edilmiştir. lmfit optimizasyon aracıyla entegre çalışarak kullanıcıların karmaşık Raman piklerine Gauss, Lorentz veya Voigt profilleri uydurmalarını (peak fitting) sağlar.62  
* **ramanbiolib:** Araştırmanın odak noktası inorganik mineraller değil biyolojik numuneler ise, ramanbiolib kütüphanesi devreye girer. Lipitler, proteinler, karbonhidratlar, amino asitler ve nükleik asitler dahil olmak üzere 140'tan fazla biyolojik bileşene ait bir arama kütüphanesi içerir.64 Hem tüm spektrum profili üzerinden benzerlik hesaplama hem de sadece en önemli pik pozisyonlarını eşleştirme algoritmalarını destekler.64

### **Ticari ve Ücretli Raman Çözümleri**

Raman analizi alanında, mineralogik veriler için açık kaynaklı RRUFF ve Raman Open Database (ROD) gibi kütüphaneler akademik ve endüstriyel dünyada büyük kabul görmüş olsa da 60, farmasötik ürünler, endüstriyel polimerler, sentetik uyuşturucular veya monomerler analiz edilecekse ticari bir veritabanı kullanımı zorunlu hale gelir.

* **Wiley KnowItAll Raman Koleksiyonu:** Yukarıda FTIR bölümünde detaylıca açıklanan Wiley KnowItAll platformu, 25.000'den fazla organik, inorganik ve polimer molekülü barındıran dünyanın en geniş ticari Raman veritabanına sahiptir.52  
* **Otomasyon ve Entegrasyon:** Python ortamında geliştirilen ticari yazılımlar (örneğin Wasatch Photonics'in geliştirdiği ENLIGHTEN yazılımı), KnowItAll ekosistemine lisans anlaşmaları yoluyla entegre edilmiştir.67 thermoanalyzer geliştiricileri, Wiley'nin sunduğu Automate SDK aracılığıyla C++ kütüphanelerini veya Python sarmalayıcılarını kullanarak sistemlerini bu ticari güçle donatabilirler.51

## ---

**Thermoanalyzer İçin Mimarî Sentez ve Entegrasyon Stratejisi**

Elde edilen verilerin ışığında, thermoanalyzer projesinin XRD, FTIR ve Raman spektroskopisi veri işleme yetenekleriyle donatılması için modüler bir entegrasyon stratejisi izlenmelidir. Projenin açık kaynaklı, tekrarlanabilir ve web tabanlı (Streamlit/FastAPI) temel yapısı korunurken, ticari bağımlılıkların nasıl yönetileceği aşağıda detaylandırılmıştır.

| Kütüphane / Veritabanı | Hedef Analiz ve Spektroskopi Türü | Teknoloji Yığını ve Entegrasyon Yöntemi | Lisans Modeli ve Ölçeklenebilirlik | Kullanım Senaryosu ve Mimarideki Yeri |
| :---- | :---- | :---- | :---- | :---- |
| **Pymatgen \+ COD API** | XRD Faz Tanımlama ve Simülasyon | Doğal Python (Native). XRDCalculator modülü | Açık Kaynak (MIT). Ücretsiz ve sınırsız ölçeklenebilir. | Bulut üzerindeki backend/ klasöründe çalıştırılır. Element bazlı aramalarla standart faz eşleştirmesi yapar. |
| **XERUS** | XRD İteratif Çoklu Faz Arıtımı | Python \+ GSAS-II arayüzü | Açık Kaynak. Ücretsiz. | Karmaşık inorganik karışımların analizinde core/ motoruna yerleştirilebilir. |
| **ICDD PDF-4/Axiom** | XRD Ticari Materyal Kütüphanesi | Harici Masaüstü (SIeve+) veya Yerel Veritabanı | Kapalı Kaynak Ticari. Tek kullanıcı \~$3700. Ağ/API erişimi yasak. | Bulutta yayınlanamaz. Yalnızca Electron sarmalayıcısı ile desktop/ versiyonunda yerel komutlarla tetiklenebilir. |
| **OpenSpecy / openspi** | FTIR / Raman Eşleştirme | Python üzerinden R çağrısı (rpy2) | Açık Kaynak. Ücretsiz. Sunucu yükü fazla. | İlgili Docker imajına R derleyicisinin yüklenmesini gerektirir. Ücretsiz polimer ve çevresel plastik eşleştirmesi için kullanılır. |
| **SpectraFit** | FTIR İleri Tepe Ayrıştırması | Python (lmfit tabanlı) | Açık Kaynak. Ücretsiz. | thermoanalyzer'ın core/ dizinindeki DSC tepe ayrıştırma mantığına mükemmel uyar. |
| **RamanSPy** | Raman Ön İşleme ve Ayrıştırma | Doğal Python | Açık Kaynak. Ücretsiz. | Sinyal temizleme, floresans silme ve format dönüşümü için core/ klasöründe doğrudan kullanılmalıdır. |
| **Ramanalysis \+ RRUFF** | Raman Mineral Eşleştirme | Python \+ Açık REST API | Açık Kaynak \+ Ücretsiz Veritabanı. | backend/ üzerinden RRUFF API'sine bağlanarak maliyetsiz mineral eşleştirmesi sağlar. |
| **Wiley KnowItAll SDK** | FTIR / Raman / MS Endüstriyel Eşleştirme | C++ / CLI (Shell) / Shared Memory | Kurumsal Ticari. Yıllık abonelik. | ICDD gibi bulut API'sinden yayınlanamaz. Kullanıcının yerelinde kurulu yazılıma Python komut satırı ile komut göndererek sonuçları UI'a çeker. |

### **1\. Veri İçe Aktarma ve Sinyal Temizleme Aşamasında Dönüşüm**

thermoanalyzer'ın mevcut içe aktarma mekanizması ağırlıklı olarak CSV ve Excel dosyalarına odaklanmıştır.1 Ancak analitik cihazlar kapalı formatlar kullanır.

* **XRD için:** xrayutilities kütüphanesi kullanılarak alan dedektörlerinden veya XRDML dosyalarından gelen veriler 1B ![][image1] dizilerine dönüştürülerek sistemin genel DataFrame yapısına entegre edilmelidir.17  
* **Raman ve FTIR için:** RamanSPy'ın sahip olduğu zengin veri yükleyicileri sayesinde WITec, Renishaw (WDF) veya SPC formatlarındaki kapalı veriler okunmalıdır.54 Özellikle Raman verilerindeki kozmik parazitler ve FTIR verilerindeki su buharı veya Mie saçılmaları, eşleştirme algoritmalarından önce OpenVibSpec ve RamanSPy'ın ön işleme boru hatlarıyla (pipeline) mutlaka temizlenmelidir.43

### **2\. Algoritmik Eşleştirme Stratejisi**

* **XRD Ekosistemi:** pymatgen kütüphanesi projenin temel yapıtaşı olarak kodlanmalıdır. pymatgen.ext.cod arayüzü sayesinde, yüklü bir sunucu veritabanına ihtiyaç duymadan, açık erişimli COD veritabanı üzerinden anında bulut sorguları yapılabilir.6 Çok fazlı karışımlarda doğruluğu artırmak için derin öğrenme tabanlı XRD-AutoAnalyzer modelinin olasılık yüzdeli tahmin yapısı thermoanalyzer arayüzündeki (UI) güven skorlaması konseptiyle birleştirilmelidir.15  
* **Spektroskopi (FTIR ve Raman) Ekosistemi:** Bulut tabanlı bir sistem hedefleniyorsa, R diline bağımlılığı olan openspi yerine, tüm spektral özellikleri tek Python ortamında çözen SpectraFit ve Ramanalysis kod yapılarına ağırlık verilmelidir. RRUFF veritabanı API'si, uygulamanın çekirdek algoritmalarına dahil edilerek ücretsiz ve devasa bir mineral kütüphanesine anında erişim sağlanabilir.58

### **3\. Ticari Kısıtlamalar ve Masaüstü (Desktop) Dağıtımı**

ICDD (XRD için) ve Wiley (Kızılötesi ve Raman için) kütüphaneleri ticari anlamda pazarın standartlarıdır. Ancak bu firmaların Son Kullanıcı Lisans Sözleşmeleri (EULA), veritabanlarının açık bir web sunucusuna (örneğin FastAPI arka ucuna) yüklenerek birden fazla son kullanıcıya eşleştirme hizmeti verilmesini (ağ üzerinden erişimi) yasal olarak yasaklamaktadır.25 Bu kısıtlamayı aşmak için thermoanalyzer projesinin modüler yapısı büyük bir avantajdır. Proje ağacındaki desktop/ dizini altında bulunan Electron tabanlı masaüstü derleyicisi 1, bir "Yerel İstemci" (Local Client) olarak yapılandırılmalıdır. Kurumsal kullanıcılar kendi ICDD PDF-4+ lisanslarını veya Wiley KnowItAll yazılımlarını bilgisayarlarına kurduklarında, thermoanalyzer masaüstü sürümü komut satırı (subprocess/shell) aracılığıyla bu yerel yazılımlardaki SDK'ları (örneğin KnowItAll Automate SDK) tetikleyebilir ve ticari veritabanında eşleştirme sonuçlarını elde edip Streamlit arayüzünde listeleyebilir.50

Sonuç olarak; thermoanalyzer projesine XRD, FTIR ve Raman analiz yeteneklerinin eklenmesi, tamamen açık kaynaklı algoritmalar (Pymatgen, RamanSPy, SpectraFit) ve açık erişimli veritabanları (COD, RRUFF) ile bulut ortamında yüksek doğrulukla, sıfır lisans maliyetiyle gerçekleştirilebilir. Endüstriyel seviyede ticari kütüphane ihtiyacı duyan kurumsal kullanıcılar için ise, sistemin Electron tabanlı masaüstü sürümü, Wiley ve ICDD yazılım geliştirme kitleri (SDK) ile haberleşebilecek köprü betikleriyle donatılarak "Tedarikçiden Bağımsız (Vendor-independent)" proje vizyonu kusursuz bir şekilde korunabilir.

#### **Alıntılanan çalışmalar**

1. utkuvibing/thermoanalyzer: Vendor-independent thermal ... \- GitHub, erişim tarihi Mart 14, 2026, [https://github.com/utkuvibing/thermoanalyzer](https://github.com/utkuvibing/thermoanalyzer)  
2. SimXRD-4M: Big Simulated X-ray Diffraction Data Accelerate the Crystalline Symmetry Classification \- arXiv, erişim tarihi Mart 14, 2026, [https://arxiv.org/html/2406.15469v1](https://arxiv.org/html/2406.15469v1)  
3. Open Source Software \- Materials Project, erişim tarihi Mart 14, 2026, [https://next-gen.materialsproject.org/about/open-source-software](https://next-gen.materialsproject.org/about/open-source-software)  
4. Usage | pymatgen, erişim tarihi Mart 14, 2026, [https://pymatgen.org/usage.html](https://pymatgen.org/usage.html)  
5. pymatgen.core package — pymatgen 2025.6.14 documentation, erişim tarihi Mart 14, 2026, [https://pymatgen.org/pymatgen.core.html](https://pymatgen.org/pymatgen.core.html)  
6. pymatgen namespace — pymatgen 2025.6.14 documentation, erişim tarihi Mart 14, 2026, [https://pymatgen.org/pymatgen](https://pymatgen.org/pymatgen)  
7. How to calculate diffraction pattern from a model of unit cell?, erişim tarihi Mart 14, 2026, [https://mattermodeling.stackexchange.com/questions/142/how-to-calculate-diffraction-pattern-from-a-model-of-unit-cell](https://mattermodeling.stackexchange.com/questions/142/how-to-calculate-diffraction-pattern-from-a-model-of-unit-cell)  
8. pymatgen.analysis.diffraction package, erişim tarihi Mart 14, 2026, [https://pymatgen.org/pymatgen.analysis.diffraction.html](https://pymatgen.org/pymatgen.analysis.diffraction.html)  
9. pymatgen.analysis.diffraction.xrd — Schrödinger Python API 2021-2 documentation, erişim tarihi Mart 14, 2026, [https://content.schrodinger.com/Docs/r2021-2/python\_api/api/\_modules/pymatgen/analysis/diffraction/xrd.html](https://content.schrodinger.com/Docs/r2021-2/python_api/api/_modules/pymatgen/analysis/diffraction/xrd.html)  
10. Dara: Automated Multiple-Hypothesis Phase Identification and Refinement from Powder X‑ray Diffraction \- PMC, erişim tarihi Mart 14, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC12895389/](https://pmc.ncbi.nlm.nih.gov/articles/PMC12895389/)  
11. pedrobcst/Xerus: XRay Estimation and Refinement Using Similarity (XERUS) \- GitHub, erişim tarihi Mart 14, 2026, [https://github.com/pedrobcst/Xerus](https://github.com/pedrobcst/Xerus)  
12. (PDF) XERUS: An open-source tool for quick XRD phase identification and refinement automation \- ResearchGate, erişim tarihi Mart 14, 2026, [https://www.researchgate.net/publication/356913627\_XERUS\_An\_open-source\_tool\_for\_quick\_XRD\_phase\_identification\_and\_refinement\_automation](https://www.researchgate.net/publication/356913627_XERUS_An_open-source_tool_for_quick_XRD_phase_identification_and_refinement_automation)  
13. Deep Learning Models to Identify Common Phases across Material Systems from X-ray Diffraction | The Journal of Physical Chemistry C \- ACS Publications, erişim tarihi Mart 14, 2026, [https://pubs.acs.org/doi/10.1021/acs.jpcc.3c05147](https://pubs.acs.org/doi/10.1021/acs.jpcc.3c05147)  
14. Machine Learning Automated Approach for Enormous Synchrotron X-Ray Diffraction Data Interpretation \- OSTI.GOV, erişim tarihi Mart 14, 2026, [https://www.osti.gov/servlets/purl/2035565](https://www.osti.gov/servlets/purl/2035565)  
15. njszym/XRD-AutoAnalyzer \- GitHub, erişim tarihi Mart 14, 2026, [https://github.com/njszym/XRD-AutoAnalyzer](https://github.com/njszym/XRD-AutoAnalyzer)  
16. Crystallographic phase identifier of a convolutional self-attention neural network (CPICANN) on powder diffraction patterns \- IUCr Journals, erişim tarihi Mart 14, 2026, [https://journals.iucr.org/m/issues/2024/04/00/fc5077/fc5077.pdf](https://journals.iucr.org/m/issues/2024/04/00/fc5077/fc5077.pdf)  
17. xrayutilities \- PyPI, erişim tarihi Mart 14, 2026, [https://pypi.org/project/xrayutilities/](https://pypi.org/project/xrayutilities/)  
18. xrayutilities download | SourceForge.net, erişim tarihi Mart 14, 2026, [https://sourceforge.net/projects/xrayutilities/](https://sourceforge.net/projects/xrayutilities/)  
19. Welcome to xrayutilities's documentation\! — xrayutilities 1.7.12 documentation, erişim tarihi Mart 14, 2026, [https://xrayutilities.sourceforge.io/](https://xrayutilities.sourceforge.io/)  
20. xrayutilities Documentation, erişim tarihi Mart 14, 2026, [https://xrayutilities.sourceforge.io/xrayutilities.pdf](https://xrayutilities.sourceforge.io/xrayutilities.pdf)  
21. PyXRD \- PyPI, erişim tarihi Mart 14, 2026, [https://pypi.org/project/PyXRD/](https://pypi.org/project/PyXRD/)  
22. Welcome to the PyXRD docs\! — PyXRD documentation, erişim tarihi Mart 14, 2026, [https://pyxrd.readthedocs.io/](https://pyxrd.readthedocs.io/)  
23. PDF-4+, the material identification database \- International Centre for Diffraction Data, erişim tarihi Mart 14, 2026, [https://www.icdd.com/assets/support/Fawcett-PDF-4plus-material-id-db.pdf](https://www.icdd.com/assets/support/Fawcett-PDF-4plus-material-id-db.pdf)  
24. ICDD® 2026 Product Summary, erişim tarihi Mart 14, 2026, [https://www.icdd.com/assets/files/2026-Product-Summary.pdf](https://www.icdd.com/assets/files/2026-Product-Summary.pdf)  
25. Using PDF-4/Axiom 2026 \- International Centre for Diffraction Data, erişim tarihi Mart 14, 2026, [https://www.icdd.com/pdf-4-axiom/](https://www.icdd.com/pdf-4-axiom/)  
26. ICDD Annual Spring Meetings | Powder Diffraction | Cambridge Core, erişim tarihi Mart 14, 2026, [https://www.cambridge.org/core/journals/powder-diffraction/article/icdd-annual-spring-meetings/F682A6EAFB240427AD5648187B860FEA](https://www.cambridge.org/core/journals/powder-diffraction/article/icdd-annual-spring-meetings/F682A6EAFB240427AD5648187B860FEA)  
27. PDF-4/Minerals | Mineral Phase Identification & XRD Data \-, erişim tarihi Mart 14, 2026, [https://www.icdd.com/pdf-4-minerals/](https://www.icdd.com/pdf-4-minerals/)  
28. PDF-4+ 2023 \- International Centre for Diffraction Data, erişim tarihi Mart 14, 2026, [https://www.icdd.com/assets/tutorials/PDF4-2023-gettingstarted.pdf](https://www.icdd.com/assets/tutorials/PDF4-2023-gettingstarted.pdf)  
29. Data Mining in PDF-4+ \- An ICDD InSession Webinar by Justin Blanton \- YouTube, erişim tarihi Mart 14, 2026, [https://www.youtube.com/watch?v=ARJSW7Tre1c](https://www.youtube.com/watch?v=ARJSW7Tre1c)  
30. ICDD Pricing, Licensing & Purchasing Policies | PDF® Databases \-, erişim tarihi Mart 14, 2026, [https://www.icdd.com/pricing-policies/](https://www.icdd.com/pricing-policies/)  
31. PDF-4+ 2021, erişim tarihi Mart 14, 2026, [https://www.icdd.com/assets/files/2021-Purchase-Options.pdf](https://www.icdd.com/assets/files/2021-Purchase-Options.pdf)  
32. BOOK OF ABSTRACTS \- AKCongress, erişim tarihi Mart 14, 2026, [https://static.akcongress.com/downloads/jtacc/jtacc2025/jtacc2025-boa.pdf](https://static.akcongress.com/downloads/jtacc/jtacc2025/jtacc2025-boa.pdf)  
33. openspi \- PyPI, erişim tarihi Mart 14, 2026, [https://pypi.org/project/openspi/](https://pypi.org/project/openspi/)  
34. OpenSpecy: Analyze, Process, Identify, and Share Raman and (FT)IR Spectra \- wincowgerdev, erişim tarihi Mart 14, 2026, [https://wincowgerdev.r-universe.dev/OpenSpecy](https://wincowgerdev.r-universe.dev/OpenSpecy)  
35. kristopher-heath/OpenSpecy-Python-Interface \- GitHub, erişim tarihi Mart 14, 2026, [https://github.com/kristopher-heath/OpenSpecy-Python-Interface](https://github.com/kristopher-heath/OpenSpecy-Python-Interface)  
36. wincowgerDEV/OpenSpecy-package: Analyze, Process, Identify, and Share, Raman and (FT)IR Spectra \- GitHub, erişim tarihi Mart 14, 2026, [https://github.com/wincowgerDEV/OpenSpecy-package](https://github.com/wincowgerDEV/OpenSpecy-package)  
37. Match spectra with reference library \- R, erişim tarihi Mart 14, 2026, [https://examples.rpkg.net/packages/OpenSpecy/reference/match\_spec.ob](https://examples.rpkg.net/packages/OpenSpecy/reference/match_spec.ob)  
38. Introducing SpectraFit: An Open-Source Tool for Interactive Spectral Analysis | ACS Omega, erişim tarihi Mart 14, 2026, [https://pubs.acs.org/doi/10.1021/acsomega.3c09262](https://pubs.acs.org/doi/10.1021/acsomega.3c09262)  
39. Introducing SpectraFit: An Open-Source Tool for Interactive Spectral Analysis \- PMC, erişim tarihi Mart 14, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC11155667/](https://pmc.ncbi.nlm.nih.gov/articles/PMC11155667/)  
40. Photizo: an open-source library for cross-sample analysis of FTIR spectroscopy data, erişim tarihi Mart 14, 2026, [https://pubmed.ncbi.nlm.nih.gov/35608303/](https://pubmed.ncbi.nlm.nih.gov/35608303/)  
41. Photizo: an open-source library for cross-sample analysis of FTIR spectroscopy data \- PMC, erişim tarihi Mart 14, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC9237726/](https://pmc.ncbi.nlm.nih.gov/articles/PMC9237726/)  
42. Photizo: an open-source library for cross-sample analysis of FTIR spectroscopy data, erişim tarihi Mart 14, 2026, [https://www.biorxiv.org/content/10.1101/2022.02.25.481930v1](https://www.biorxiv.org/content/10.1101/2022.02.25.481930v1)  
43. Investigating Spectral Biomarker Candidates for Migratory Potential in Cancer Cells Using Micro-FTIR and O‑PTIR Spectroscopy \- PMC, erişim tarihi Mart 14, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC12921600/](https://pmc.ncbi.nlm.nih.gov/articles/PMC12921600/)  
44. RUB-Bioinf/OpenVibSpec: Open source python packages for the work in vibrational spectroscopy \- GitHub, erişim tarihi Mart 14, 2026, [https://github.com/RUB-Bioinf/OpenVibSpec](https://github.com/RUB-Bioinf/OpenVibSpec)  
45. KnowItAll IR Spectral Library Collection \- Wiley Science Solutions, erişim tarihi Mart 14, 2026, [https://sciencesolutions.wiley.com/solutions/technique/ir/knowitall-ir-collection/](https://sciencesolutions.wiley.com/solutions/technique/ir/knowitall-ir-collection/)  
46. Wiley Registry/NIST Mass Spectral Library 2023, erişim tarihi Mart 14, 2026, [https://sciencesolutions.wiley.com/solutions/technique/gc-ms/wiley-registry-nist-mass-spectral-library/](https://sciencesolutions.wiley.com/solutions/technique/gc-ms/wiley-registry-nist-mass-spectral-library/)  
47. Wiley SmartSpectra IR Database Collection, erişim tarihi Mart 14, 2026, [https://sciencesolutions.wiley.com/solutions/technique/ir/wiley-smartspectra-ir-database-collection/](https://sciencesolutions.wiley.com/solutions/technique/ir/wiley-smartspectra-ir-database-collection/)  
48. News: Wiley Launches New Database of Predicted Infrared Spectra, erişim tarihi Mart 14, 2026, [https://sciencesolutions.wiley.com/news-wiley-launches-new-database-of-predicted-infrared-spectra/](https://sciencesolutions.wiley.com/news-wiley-launches-new-database-of-predicted-infrared-spectra/)  
49. Wiley launches new database of predicted infrared spectra \- EurekAlert\!, erişim tarihi Mart 14, 2026, [https://www.eurekalert.org/news-releases/1007341](https://www.eurekalert.org/news-releases/1007341)  
50. KnowItAll Software Developer Kits (SDK) \- Wiley Science Solutions, erişim tarihi Mart 14, 2026, [https://sciencesolutions.wiley.com/knowitall-sdk/](https://sciencesolutions.wiley.com/knowitall-sdk/)  
51. KnowItAll Automate \- Wiley Science Solutions, erişim tarihi Mart 14, 2026, [https://sciencesolutions.wiley.com/knowitall-automate/](https://sciencesolutions.wiley.com/knowitall-automate/)  
52. Wiley KnowItAll Annual Subscriptions \- Photothermal, erişim tarihi Mart 14, 2026, [https://www.photothermal.com/wp-content/uploads/2024/10/Wiley-KnowItAll-onesheet.pdf](https://www.photothermal.com/wp-content/uploads/2024/10/Wiley-KnowItAll-onesheet.pdf)  
53. RamanSPy: An Open-Source Python Package for Integrative Raman Spectroscopy Data Analysis \- PMC, erişim tarihi Mart 14, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC11140669/](https://pmc.ncbi.nlm.nih.gov/articles/PMC11140669/)  
54. RamanSPy, erişim tarihi Mart 14, 2026, [https://ramanspy.readthedocs.io/](https://ramanspy.readthedocs.io/)  
55. Hyperspectral unmixing for Raman spectroscopy via physics-constrained autoencoders | PNAS, erişim tarihi Mart 14, 2026, [https://www.pnas.org/doi/10.1073/pnas.2407439121](https://www.pnas.org/doi/10.1073/pnas.2407439121)  
56. RamanSPy: An Open-Source Python Package for Integrative Raman Spectroscopy Data Analysis | Analytical Chemistry \- ACS Publications, erişim tarihi Mart 14, 2026, [https://pubs.acs.org/doi/10.1021/acs.analchem.4c00383](https://pubs.acs.org/doi/10.1021/acs.analchem.4c00383)  
57. Datasets \- RamanSPy, erişim tarihi Mart 14, 2026, [https://ramanspy.readthedocs.io/en/latest/datasets.html](https://ramanspy.readthedocs.io/en/latest/datasets.html)  
58. Ramanalysis: Interactive Comparison and Matching of Raman Spectra \- My Goldschmidt, erişim tarihi Mart 14, 2026, [https://conf.goldschmidt.info/goldschmidt/2025/meetingapp.cgi/Paper/31027](https://conf.goldschmidt.info/goldschmidt/2025/meetingapp.cgi/Paper/31027)  
59. meryemberradauwo/RamanMatch: Application for Raman Spectroscopy Analysis \- GitHub, erişim tarihi Mart 14, 2026, [https://github.com/meryemberradauwo/RamanMatch](https://github.com/meryemberradauwo/RamanMatch)  
60. Raman Mineral Identification Powered by StellarPro and the RRUFF Spectral Database, erişim tarihi Mart 14, 2026, [https://www.stellarnet.us/raman-mineral-identification-powered-by-stellarpro-and-the-rruff-spectral-database/](https://www.stellarnet.us/raman-mineral-identification-powered-by-stellarpro-and-the-rruff-spectral-database/)  
61. Rruff Project \- SERC (Carleton), erişim tarihi Mart 14, 2026, [https://serc.carleton.edu/resources/21028.html](https://serc.carleton.edu/resources/21028.html)  
62. Welcome to RamPy's documentation\!, erişim tarihi Mart 14, 2026, [http://charlesll.github.io/rampy/](http://charlesll.github.io/rampy/)  
63. WentongZhou/raman\_analyzer: The long-term goal of this script is to automate peak-fitting process of Raman Spectrum. \- GitHub, erişim tarihi Mart 14, 2026, [https://github.com/WentongZhou/raman\_analyzer](https://github.com/WentongZhou/raman_analyzer)  
64. mteranm/ramanbiolib: A Raman spectral search library for biological molecules identification, over a database of 140 components, including lipids, proteins, carbohydrates, amino acids, metabolites, nucleic acids, pigments and others. \- GitHub, erişim tarihi Mart 14, 2026, [https://github.com/mteranm/ramanbiolib](https://github.com/mteranm/ramanbiolib)  
65. Raman Open Database: first interconnected Raman–X-ray diffraction open-access resource for material identification \- PMC, erişim tarihi Mart 14, 2026, [https://pmc.ncbi.nlm.nih.gov/articles/PMC6557180/](https://pmc.ncbi.nlm.nih.gov/articles/PMC6557180/)  
66. KnowItAll Analytical Edition Software \- Wiley Science Solutions, erişim tarihi Mart 14, 2026, [https://sciencesolutions.wiley.com/knowitall-analytical-edition-software/](https://sciencesolutions.wiley.com/knowitall-analytical-edition-software/)  
67. ENLIGHTEN spectroscopy software \- Wasatch Photonics, erişim tarihi Mart 14, 2026, [https://wasatchphotonics.com/product-category/software/](https://wasatchphotonics.com/product-category/software/)  
68. WasatchPhotonics/KnowItAllWrapper: C++ wrapper over Wiley KnowItAll's ID-SDK API to simplify calling from Python \- GitHub, erişim tarihi Mart 14, 2026, [https://github.com/WasatchPhotonics/KnowItAllWrapper](https://github.com/WasatchPhotonics/KnowItAllWrapper)  
69. raman-spectroscopy · GitHub Topics, erişim tarihi Mart 14, 2026, [https://github.com/topics/raman-spectroscopy](https://github.com/topics/raman-spectroscopy)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABMAAAAYCAYAAAAYl8YPAAABjElEQVR4Xu2TvStHYRTHjzCIkhjIJimTJKQog2SxsEoysFgwiFIMVkUG2SSL1M9iEINM3v4CZSAvUQyKksT3e59zfs9z71Wy6vetT/c+5zn3POfluSI5/aJi0A3qQF5iT6rALFgD86A2vh1TGzgBIyADJsPNFrAPOkAD2AVf6pQ8lb6XoFXXXeACVHNRBHbAMMhXh3JwCl5Bk9qoUnAEVsQf0gxu9RmVdwVexGVlmhGX3URgGwBv4so09Yrz41MKwRLYExfYNKVOfFLM6ljhu4n7PCDK7CcVgG3wCTrVxmzewYKuKZa6CZ5AfWCPic1lvzhZZk6xXGb6CK6VO7WdgTL1i4klHIANcXfJtC7pDNrBB1gObFkxi1WwKG7KphJwKOkM5sSVHg4kkgWaFn9FmAVvuQVjf+xK2EC2xLciEh14Qcf13TQK+sQPhKWaesADaAxs0cdD4sZ7I7655FlcX6gxcQEZuBKcg37dy8ouLaeS5B7UqB/L4m/GgAw0KOlf7U9iLysk0aOc/qO+AWSWUP7OVqgfAAAAAElFTkSuQmCC>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACMAAAAYCAYAAABwZEQ3AAABsUlEQVR4Xu2VzSsFURjGH/nIV0kUsRBJKTs2ytKCjTXJSkrsbCgbKRtlgawoWVgo5R9Q7BX+AXVXlIUVG/LxvJ176sx755yZcd1rc3/16zbznpn7njnPnAEqlJY6WqtP/gdVdJMO6UKxzNAX+u34ShfdQYpeekQb1Pl+eo/ovT7pGW1yxgWRmR7TLzquanFM0wV90mEKppE9XUhDK72hOdodLRVQTw9pny44bME0I01lZpi+0XNao2oayckB/OOa6TV9QrhhL7MwM1nRhRiWYJbJhzQgjVwiQ04sNi8fdEzVNC0wYzt0wcHmRZYqMzYvDwj/iTBKt2Em4MPmZVIX0pAlLxsIv21ly0s7PYF5kj7KlpcJuq5PKv4kLzmE9xdpehdmSUOE9hf5jslbeEF3aGe0nD4vvu3fJZQXaUT2Jvn0yHLfwQn4HH1E9BvyTOftAIXMSPaXOAboLX1H9Nt2ShvzY+T6K5iGq2lb/jcz8sT2UTjbLEjwf5UjzSBMM6FlTEKWeNk5lrz0OMepSdr+0zACE1y5zypdQzh/scgF8hYl7cxpKCorQhfMkwlt/xVKwg+/DFZ5mB/kWQAAAABJRU5ErkJggg==>