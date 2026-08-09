# Faz 10 — Boya/Kimya NACE 20.30.90 Sınav ve Sunum Kapsamı

## Amaç

Boya, vernik, matbaa mürekkebi, solvent ve inceltici üretimi gibi `kimyasal_boya` profilindeki doğrulanmış NACE kayıtlarında beş işe özgü konunun tamamını kaynak kontrollü teknik paketlerle desteklemek; 5 temel + 15 işe özgü soru ve 20/20 soru-slayt-kaynak izlenebilirliği üretimini fail-closed sözleşmesini bozmadan açmak.

İlk doğrulanan canlı örnek NACE: `20.30.90`.

## Beş doğrulanmış konu

1. Kimyasal etiketler, SDS ve maruziyet yolları
2. Solvent, izosiyanat, aerosol ve toksik buhar maruziyeti
3. Yanıcı atmosfer, statik elektrik ve ex-proof ekipman
4. Uyumsuz kimyasalların güvenli depolanması ve transferi
5. Dökülme, sızıntı, acil duş ve müdahale prosedürleri

Her konu tehlike tanımı, iki öncelikli kontrol, güvenli saha davranışı ve resmî ÇSGB/İSGGM-İSGÜM kaynak referansları taşır.

## Kaynak yaklaşımı

Birincil kaynaklar:

- 6331 sayılı İş Sağlığı ve Güvenliği Kanunu
- ÇSGB İSGGM Yayınlar ve Afişler: Malzeme Güvenlik Bilgi Formları (MSDS), kimyasal etiketleme ve kimyasal risk yayınları
- ÇSGB İSGÜM İSG Dokümanları: Boya Sektöründe Solvent Kullanımı, Patlayıcı Ortamlarda İş Güvenliği, Endüstriyel Havalandırmaya Giriş ve kimyasal yangın/patlama risk dokümanları

## Güvenlik sözleşmesi

- Cross-sector fallback eklenmez.
- Beş konudan biri eşleşmezse sınav ve sunum yine fail-closed kalır.
- Mevcut Phase 8 ve Phase 9 davranışı değiştirilmez; yeni resolver eşleşmezse mevcut zincire delegasyon yapılır.
- Tarihsel sınav, sunum, PDF, sertifika, katılım, imza veya onay kaydı yeniden yazılmaz.
- Migration yoktur.
- Canlı kayıt üzerinde otomatik sınav veya sunum üretimi yapılmaz; yalnız üretim kapısı doğru içerik mevcut olduğunda açılır.

## Feature flag / rollback

Aktivasyon:

- `NACE_TRAINING_PRESENTATION_CHEMICAL_PACK_ENABLED=true`
- `NACE_TRAINING_PRESENTATION_CHEMICAL_PACK_FORCE_OFF=false`

İlk rollback işlemi:

- `NACE_TRAINING_PRESENTATION_CHEMICAL_PACK_FORCE_OFF=true`

Rollback veritabanı downgrade gerektirmez. Flag kapatıldığında resolver mevcut Phase 9/Phase 8 zincirine aynen delegasyon yapar.

## Test kapıları

- Bayrak varsayılan kapalı ve force-off öncelikli.
- Beş kimya/boya konusu 5/5 benzersiz teknik pakete çözülür.
- Genel `yangın`, `elektrik`, `kimyasal`, `solvent` gibi tekil kelimeler yanlış eşleşme oluşturmaz.
- NACE 20.30.90 için tam 15 benzersiz işe özgü soru üretilir.
- Sunum manifesti 20/20 soru-slayt-kaynak doğrulamasını geçer.
- Teknik bekleme blokları doğrulanmış içerikle değiştirilir.
- Force-off sonrası eski fail-closed davranış geri gelir.
