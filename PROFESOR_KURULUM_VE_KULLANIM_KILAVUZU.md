# Profesor Kurulum ve Kullanim Kilavuzu

Bu dokuman, ThermoAnalyzer'in mevcut kararlı beta akisinin hocalar ve laboratuvar kullanicilari tarafindan hizli ve kontrollu sekilde kurulup test edilebilmesi icin hazirlandi.

## 1. Su anda hangi kisimlar kararlı?
Kararlı beta kapsaminda olan akislar:

- DSC analizi
- TGA analizi
- Karsilastirma Alani
- Toplu Sablon Uygulayici
- Rapor / disa aktarma uretimi
- `.thermozip` ile proje kaydetme ve yeniden acma

Onizleme durumunda olan ve uretim-guveni ile yorumlanmamasi gereken kisimlar:

- DTA
- Kinetik analiz
- Pik dekonvolusyonu

## 2. Hocalar icin gerekli olan seyler

- Windows bilgisayar
- size verilen `ThermoAnalyzer_Beta_Setup.exe` dosyasi

Bu beta dagitiminda **Python, pip veya terminal kullanmaniz gerekmez**.

## 3. Kurulum

1. `ThermoAnalyzer_Beta_Setup.exe` dosyasini cift tiklayin.
2. Kurulum sihirbazinda `Ileri / Next` adimlarini izleyin.
3. Istiyorsaniz masaustu kisayolu secenegini acik birakin.
4. `Bitir / Finish` sonrasinda uygulamayi hemen baslatabilirsiniz.

Kurulum tamamlandiginda:

- Baslat Menusu'nde `ThermoAnalyzer Beta` kisayolu olusur
- secildi ise masaustu kisayolu da olusur
- uygulama tek tikla acilir ve varsayilan tarayicida calisir

Not:

- Ilk acilista Windows tarayici veya yerel ag erisimiyle ilgili bir soruya izin istemi gosterebilir
- uygulama sadece yerel makinede calisir; bulut servisine veri gondermez

## 4. Onerilen kullanim akisi

1. Uygulamayi acin ve bir DSC veya TGA dosyasi yukleyin.
2. Ice aktarma sonrasinda gorunen `Ice Aktarma Guveni`, `Ice Aktarma Incelemesi`, veri tipi ve sinyal birimi alanlarini kontrol edin.
3. Gerekirse kolon eslemeyi manuel olarak duzeltin.
4. Karsilastirma Alani icinde kosulari ust uste inceleyin.
5. DSC veya TGA sayfasinda analizi calistirin.
6. Sonucu oturum icine kaydedin.
7. Gerekirse ayni is akisi sablonunu Toplu Sablon Uygulayici ile birden fazla kosuya uygulayin.
8. Sonuclari `Rapor Merkezi` sayfasindan:
   - DOCX / PDF rapor
   - CSV / XLSX disa aktarma
   - `.thermozip` proje arsivi
   - destek tanilama goruntusu
   olarak alin.

## 5. En iyi sonuc icin onerilen dosyalar

- CSV
- TXT / TSV
- XLSX / XLS

Su anda en guvenilir ice aktarma senaryolari:

- basliklari duzgun genel ayracli disa aktarma dosyalari
- TA benzeri metin disa aktarmalari
- NETZSCH benzeri metin disa aktarmalari

## 6. Dikkat edilmesi gerekenler

- `Ice Aktarma Incelemesi` uyarisı varsa veri tipini, sinyal kolonunu ve birimini elle dogrulayin.
- Onizleme modulleri kararlı beta vaadinin disindadir.
- Proprietary binary formatlar su anda destek kapsaminda degildir.
- Eksik kalibrasyon bilgisi varsa sonucu tam dogrulanmis kabul etmeyin.

## 7. Sorun bildirirken neler gonderilmeli?
Mumkunse sunlari ekleyin:

- problemli giris dosyasi
- kullanilan sayfa / is akisi
- beklenen sonuc ve gozlenen sonuc
- ekran goruntusu
- `thermoanalyzer_support_snapshot.json`
- ilgili `.thermozip` proje dosyasi

## 8. Ek dokumanlar

- Beta sinirlari ve geri bildirim beklentileri icin [PROFESSOR_BETA_GUIDE.md](PROFESSOR_BETA_GUIDE.md)
- Ingilizce kurulum ve kullanim karsiligi icin [PROFESSOR_SETUP_AND_USAGE_GUIDE.md](PROFESSOR_SETUP_AND_USAGE_GUIDE.md)
