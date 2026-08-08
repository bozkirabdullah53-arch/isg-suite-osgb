# Phase 9 — NACE Kapsam Genişletme ve Eğitmen Modu Görsel Kalite

Tarih: 9 Ağustos 2026
Bağlı issue: #129
Önceki faz: #124 / Phase 8

## Amaç

Phase 8 ile canlıya alınan 20/20 soru-slayt-kaynak izlenebilirliği korunarak ilk kontrollü NACE kapsam genişlemesi yapılır. Phase 9 ayrıca yalnız yeni Phase 9 manifestlerinde `instructor-mode-v2` işaretini üretir; tarihsel Phase 8 sunumlarının görünümü ve içeriği yerinde değiştirilmez.

## Yeni feature flag

- `NACE_TRAINING_PRESENTATION_COVERAGE_V2_ENABLED=false`
- `NACE_TRAINING_PRESENTATION_COVERAGE_V2_FORCE_OFF=false`

Varsayılan davranış kapalıdır. `ENABLED=true` olsa bile `FORCE_OFF=true` her zaman önceliklidir.

## İlk kontrollü kapsam

Phase 9 exact-first bilgi paketleri yalnız aşağıdaki 15 konu için tanımlıdır.

### İnşaat / Şantiye

1. Yüksekte çalışma, düşmeyi önleme ve kurtarma
2. İskele, merdiven, platform ve kenar koruma güvenliği
3. Kazı, iksa, göçük ve yeraltı hatları
4. Vinç, kaldırma ekipmanı ve düşen cisim riskleri
5. Şantiye içi trafik, iş makineleri ve geçici elektrik

### Depo / Lojistik

1. Forklift, transpalet ve yaya trafiği güvenliği
2. Raf sistemleri, istif ve yük düşmesi riskleri
3. Yükleme rampası, dorse ve araç sabitleme
4. Elle taşıma, kaldırma yardımcıları ve ergonomi
5. Akü şarj alanı, yangın ve acil çıkış düzeni

### Sağlık / Hastane

1. Biyolojik etkenler, enfeksiyon kontrolü ve izolasyon
2. Kesici-delici yaralanmaları ve tıbbi atıklar
3. Hasta taşıma, ergonomi ve şiddet riski
4. İlaç, dezenfektan, sterilizasyon ve radyasyon riskleri
5. Acil durum, tahliye ve güvenli sağlık hizmeti sunumu

## Kaynak politikası

Phase 9 kaynakları 9 Ağustos 2026 tarihinde kontrol edilmiştir.

- 6331 sayılı İş Sağlığı ve Güvenliği Kanunu: `https://www.csgb.gov.tr/media/2670/6331_isgkanunu_tr.pdf`
- ÇSGB İnşaat Sektöründe İş Sağlığı ve Güvenliği: `https://guvenliinsaat.csgb.gov.tr/`
- ÇSGB İnşaat Sektörü İSG Mevzuatı: `https://guvenliinsaat.csgb.gov.tr/mevzuat/`
- ÇSGB İSGGM Yayınlar ve Afişler: `https://www.csgb.gov.tr/isggm/yayinlar-ve-afisler/`

Lojistik paketinde özellikle Forkliftlerde Güvenli Çalışma Uygulama Rehberi, Güvenli İstifleme Rehberi, Elle Taşıma İşleri Yönetmeliği Uygulama Rehberi ve lojistik depolama yayınları referans alınır. Sağlık paketinde Kamu Hastanelerinde İSG Uygulama Rehberi ile biyolojik etken, kesici-delici, ergonomi ve acil durum yayınları referans alınır.

## Fail-closed eşleşme

Phase 9 tek bir genel kelimeyle eşleşmez. Her yeni konu paketi birden fazla ayırt edici kelime parçasının birlikte bulunmasını gerektirir. Örneğin yalnız `elektrik`, `yangın`, `trafik` veya `ergonomi` ifadesi Phase 9 paketine geçmek için yeterli değildir.

Phase 9 konusu eşleşmezse resolver Phase 8'e delege eder. Phase 8 de desteklemiyorsa mevcut davranış korunur:

`İçerik doğrulaması bekleniyor`

Cross-sector fallback eklenmez.

## Eğitmen Modu v2

Yeni Phase 9 manifestleri:

- `rendering.instructor_mode_ui = instructor-mode-v2`
- `rendering.coverage_v2_active = true`
- `coverage_v2.version = nace-training-presentation-coverage-v2`

V2 arayüzünde:

- Tehlike
- Kontrol tedbiri
- Güvenli davranış
- Teknik/özel risk
- NACE ve değerlendirme bilgileri

ayrı semantik kartlarda gösterilir. Kaynaklar URL ise erişilebilir bağlantı, metin ise kaynak etiketi olarak gösterilir. Masaüstü, tablet ve mobil görünümde yatay taşma olmamalıdır. Klavye, Escape, PageUp/PageDown, Home/End ve reduced-motion davranışları korunur.

Tarihsel manifestte `instructor_mode_ui` bulunmuyorsa v1 görünümü aynen kullanılır.

## Korunan davranışlar

- mevcut eğitim kayıtları değiştirilmez
- mevcut sınav kayıtları değiştirilmez
- mevcut 5 temel + 15 işe özgü soru sözleşmesi korunur
- mevcut PDF/sertifika/katılım/imza akışı değiştirilmez
- tarihsel sunum manifestleri yeniden yazılmaz
- migration yoktur
- veri dönüşümü yoktur
- otomatik sunum üretimi yapılmaz
- mevcut Phase 8 ve Phase 7 force-off mekanizmaları korunur
- mevcut pilot company allowlist genişletilmez

## CI yayın kapısı

Backend:

- Phase 8 rollout testleri
- Phase 9 flag/force-off testi
- 15/15 kaynak kontrollü konu paketi
- 3 hedef profil için 5/5 konu readiness
- her hedef profil için 15 benzersiz işe özgü soru
- ambiguous topic yanlış eşleşmiyor
- Phase 9 kapalıyken Phase 8 delegasyonu korunuyor
- manifest v2 işareti additive ve rehash davranışı

Frontend:

- unit test
- lint
- production build
- masaüstü/laptop/tablet/mobil Playwright
- kart türleri ve kaynak bağlantısı
- 390px yatay taşma kontrolü
- tarihsel v1 manifest uyumluluğu

## Staging yayın sırası

1. Kod Phase 9 flag kapalı olacak şekilde staging'e alınır.
2. Migration head değişmediği doğrulanır.
3. API ve web aynı committe `live` olmalıdır.
4. `/health` 200 olmalıdır.
5. Error/warning logları incelenir.
6. `NACE_TRAINING_PRESENTATION_COVERAGE_V2_ENABLED=true` yapılır.
7. `NACE_TRAINING_PRESENTATION_COVERAGE_V2_FORCE_OFF=false` doğrulanır.
8. Aynı commit yeniden deploy edilir ve health/log kapısı tekrar geçilir.

## Production yayın sırası

1. Master merge edilir.
2. İlk production deploy Phase 9 kapalı gerçekleşir.
3. Migration, startup, health, web live ve tarihsel veri sayıları doğrulanır.
4. Phase 9 yalnız mevcut sunum pilot sınırı içinde açılır.
5. Aktivasyon deployunda migration tekrar no-op/head olmalıdır.
6. `/health` 200 ve error/warning temiz olmalıdır.
7. Otomatik sunum oluşturulmaz; yeni manifest yalnız kullanıcı eylemiyle oluşur.

## Rollback

İlk ve en hızlı müdahale:

`NACE_TRAINING_PRESENTATION_COVERAGE_V2_FORCE_OFF=true`

Bu işlem:

- Phase 9 exact-first kapsam genişlemesini kapatır,
- yeni manifestlerde Phase 9 v2 işaretini üretmez,
- resolver davranışını Phase 8'e döndürür,
- veri silmez,
- migration downgrade gerektirmez.

Gerekirse ikinci katman olarak mevcut Phase 8 force-off kullanılır:

`NACE_TRAINING_PRESENTATION_TRACEABILITY_FORCE_OFF=true`

Ana sunum özelliği için Phase 7 rollback prosedürü ayrıca geçerlidir.
