# Gizlilik Sözleşmesi Doldurma Hazırlığı

ÇSGB İBYS Gizlilik ve Veri Paylaşım Sözleşmesi (https://ibys.csgb.gov.tr/files/basvuru/gizliliksozlesme.pdf)
imzalanmadan önce doldurulması gereken alanlar ve firma bilgileri.

## Sözleşmede doldurulacak alanlar

### 1. TANIM ve KAPSAM (s.1)
- **Firma:** `.............................................`
  - Doldurulacak: İSG Suite OSGB'yi üreten/temsil eden **firmanın resmi ticari unvanı**
  - Örnek: `EİSA PROGRAMLAMA [veya yazılım üretici firma unvanı]`

### 8. ÜCRET (s.8)
- **Tarih:** İmza tarihi
- **FİRMA adına:** Yetkilinin unvan/isim/kaşe/imza
  - Doldurulacak: Firma yetkilisinin adı, unvanı, kaşesi, ıslak imza
- **T.C. Çalışma ve Sosyal Güvenlik Bakanlığı — İSGGM Genel Müdürü**
  - (Bakanlık tarafı; siz doldurmazsınız)

## Başvuru öncesi firma bilgileri (tüm formlarda tutarlı olmalı)

| Bilgi | Değer |
|---|---|
| Firma ticari unvanı | [doldur] |
| Yetkili kişi adı/soyadı | [doldur] |
| Yetkili kişi unvanı | [doldur] |
| Kurumsal e-posta (Bakanlık iletişim) | [doldur — Gizlilik Sözleşmesi 7.3 tebligat adresi] |
| Adres (tebligat adresi, 5 iş günü içinde değişiklik bildirimi) | [doldur] |
| Telefon | [doldur] |
| Uygulama Ürün Adı (yazılımın ticari adı) | İSG Suite OSGB |
| IP adresi (Uzaktan Erişim Formu — yalnız 1 adet) | [sunucu çıkış IP'si] |
| Veri sorumlusu temsilcisi (KVKK) | [doldur] |

## İmzalama ve teslim

1. Sözleşme **2 (iki) asıl nüsha** düzenlenir (s.1).
2. Tüm belgeler **ıslak imzalı/kaşeli PDF** olarak İSGKatip sistemine yüklenir
   (Entegratör rehberi adım 7).
3. Başvuru **2 gün içinde** tamamlanmalı, aksi halde iptal olur (Başvuru Formları sayfası).

## Sözleşmenin teknik yükümlülük kontrol listesi (imza öncesi)

- [ ] 3.6 Backdoor/arka kapı kodu yok — ✅ kod denetimi yapıldı (SAST bandit)
- [ ] 3.9 ISO 27001 belgesi alındı/devamlılığı sağlanıyor — ❌ EKSİK
- [ ] 3.18 Sunucular Bakanlık onaylı mekânda — ❓ Render teyit edilmeli
- [ ] 3.22 Yıllık statik+dinamik güvenlik testi — ⚠️ SAST eklendi, resmi DAST/pen test gerekli
- [ ] KVKK uyumu (3.1, 3.10) — ✅ kod, ⚠️ Verbis/DPA prosedürü (yazıldı)
- [ ] Veri aktarım/izin dışı paylaşım yasağı (3.8, 3.14) — ✅
- [ ] Kullanıcı hesap koruması (3.15) — ✅
- [ ] Yedekleme prosedürü (Başvuru #5) — ✅ doküman yazıldı
- [ ] Veritabanı değişiklik prosedürü (Başvuru #6) — ✅ doküman yazıldı
