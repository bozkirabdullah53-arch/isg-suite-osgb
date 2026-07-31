# PROMPT — İSG PRO 2026 Eğitim → OSGB Suite Eğitim (birebir aktarım)

Kaynak: `C:\Users\Abdullah\OneDrive\Desktop\İSG PRO 2026\Sistem\Moduller\egitim\`
Hedef: `isg-suite-osgb` → Eğitim menüsü + `/api/v1/trainings/*`

Kural: PRO’daki eğitim belgesi ve imza formu çıktısı **piksel/metin olarak aynı mantıkta** olmalı. Eski “EGITIM KATILIM VE IMZA LISTESI” (Helvetica, bozuk Türkçe) **yasak**.

---

## 1) Tehlike sınıfı (kullanıcı değiştiremez — sunucu hesaplar)

| Sınıf | Süre | Yenileme |
|-------|------|----------|
| Az Tehlikeli | 8 DERS SAAT (480 dk) | 3 yılda bir yenilenir |
| Tehlikeli | 12 DERS SAAT (720 dk) | 2 yılda bir yenilenir |
| Çok Tehlikeli | 16 DERS SAAT (960 dk) | Her yıl yenilenir |

Konu dakikaları hedef toplama **5’er dk** ile dağıtılır.

---

## 2) Katılımcı imza formu PDF (`/katilim-listesi-pdf` ↔ `GET .../attendance.pdf`)

- Yatay A4, dış+iç çerçeve (slate), üst bant `#E2EBF4`
- Başlık (2 satır, ortalı, Türkçe font Arial/DejaVu **zorunlu**):
  - `İŞ SAĞLIĞI VE GÜVENLİĞİ TEMEL EĞİTİMİ`
  - `KATILIMCI İMZA FORMU`
- Alt yazı: `Eğitim kaydı, katılımcı listesi ve eğitim konuları aynı veri setine bağlıdır.`
- Sağ üst: `Form No: İSG-EĞT-KF-01` · `Düzenleme: GG.AA.YYYY` · `Sayfa: n/toplam`
- Logo kutusu (varsa)
- Bilgi grid 4 sütun × ~13 hücre: Firma, Eğitimin Adı, Eğitim Tarihi, Eğitim Süresi, Yenileme Periyodu, Tehlike Sınıfı, Eğitim Türü, Eğitim Şekli, Sektör / İş Kolu, Eğitim Yeri, Eğitici / Yeterlilik, Değerlendirme / Puan, Doğrulama Kodu
- Amaç / Belgedeki Konu Başlıkları / Dayanak kutusu (PRO metinleri)
- Tablo 10 satır/sayfa, kolon mm: `10,55,31,45,58,20,62` → Sıra, Adı Soyadı, T.C. Kimlik No, Görevi / Bölümü, İmzası, Not, Açıklama (boş imza/not/açıklama)
- Alt 3 kaşe: Eğitimi Veren · Eğitimi Veren İşyeri Hekimi · İşveren / İşveren Vekili + “Kaşe / İmza”
- Dipnot: imzaların katılım doğrulama amaçlı olduğu

Referans görsel: kullanıcıdaki PRO imza formu ekran görüntüsü.

---

## 3) Kişi katılım belgeleri PDF (`/pdf` ↔ `GET .../certificates.pdf`)

- Yatay A4, mavi çift çerçeve + mavi üst bant
- Başlık: `TEMEL İŞ SAĞLIĞI VE GÜVENLİĞİ EĞİTİMİ KATILIM BELGESİ` + firma adı
- Belge No: `ISG-GGAAYYYY-001` (üretim tarihi + sıra; PRO: `ISG-05072026-001`)
- Meta satırı (ortalı): `Süre: … │ Tür: … │ Şekil: …` (+ varsa `│ Doğrulama: …`) — Tehlike/Sektör bu satıra **yazılmaz**
- Sn. + ad soyad + T.C. + Görev + Eğitim Tarihi (aralık varsa `GG.AA.YYYY - GG.AA.YYYY`)
- 6331 kanun metni (3 satır, PRO birebir)
- 3 imza kutusu: Eğitim Veren (uzman+unvan) · Eğitim Veren (işyeri hekimi) · Onaylayan (işveren vekili)
- Konu başlığı: `İŞ SAĞLIĞI VE GÜVENLİĞİ EĞİTİM KONULARI`
- 2 sütun müfredat: 1 Genel · 2 Teknik · 3 Sağlık · 4 İş/işyerine özgü (+ Risk Değerlendirmesine Dayalı + sektör 5 konu); her satır `… - NN DK`
- Footer: `6331 Sayılı İş Sağlığı ve Güvenliği Kanunu kapsamında düzenlenmiştir.` + sağda stamp/imza metni

Referans dosya: `C:\Users\Abdullah\Downloads\calisan_listesi (90).pdf`

---

## 4) Veri / UI (Suite)

- Eğitim oluştur: firma, başlık, tür, şekil, tarih(/bitiş), yer, tehlike, sektör, eğitici+yeterlilik, hekim, işveren, değerlendirme/puan, katılım+başarı beyanı, katılımcılar (personel / Excel)
- Excel: `.xlsx/.xlsm`, ad/TC/görev/bölüm eşleştirme
- Belge merkezi: logo, imza PDF, katılım belgesi PDF, doğrulama kodu/link
- `GET /trainings/verify/{code}` kamuya açık
- Font yoksa PDF **üretme** (Helvetica’ya sessiz düşüş yok)

---

## 5) Kabul kriteri (canlı)

1. OpenAPI’de `.../certificates.pdf` ve `.../verify/{code}` var
2. İmza PDF başlığı `KATILIMCI İMZA FORMU` (eski ASCII başlık yok; Türkçe karakter kutu değil)
3. Katılım belgesi `ISG-…-001` + konu dakikaları + 6331 footer
4. Akü Üretimi + Çok Tehlikeli → 4. bölümde kurşun/asit/hidrojen konuları

Deploy: Render `isg-suite-api` + `isg-suite-web` branch `feature/training-ui-cors` → **Clear build cache & Deploy**.
