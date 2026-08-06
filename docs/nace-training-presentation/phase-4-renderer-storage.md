# Faz 4 — NACE Eğitim Sunumu Renderer ve Object Storage

Bağlı epic: #74  
Görev: #78

## Amaç

Faz 3'te dondurulan sunum manifestinden aynı içeriğe sahip iki çıktı üretmek:

- Ana çıktı: PPTX
- Yardımcı çıktı: PDF

Bu faz mevcut eğitim, sınav, puanlama, sertifika veya eğitim PDF servislerini değiştirmez.

## Renderer

PPTX:

- `python-pptx` ile doğrudan oluşturulur.
- 16:9 geniş ekran kullanılır.
- Mevcut İSG Suite turkuaz/beyaz tasarım dili uygulanır.
- Her slaytta bölüm, başlık, manifest içeriği, kaynak alt bilgisi ve sayfa numarası bulunur.
- Uzman onayı gereken slaytlar işaretlenir.
- Her slaytta konuşmacı notu bulunur.
- ZIP paket zamanları ve belge özellikleri normalize edilerek deterministik çıktı sağlanır.
- Üretilen dosya yeniden `python-pptx` ile açılıp slayt sayısı doğrulanır.

PDF:

- Office/LibreOffice dönüşümü kullanılmaz.
- ReportLab ile aynı manifestten doğrudan oluşturulur.
- Her PPTX slaydı PDF'de bir sayfadır.
- Türkçe Unicode font doğrulanır.
- ReportLab invariant modu ile deterministik çıktı üretilir.
- Üretilen dosya `pypdf` ile yeniden açılıp sayfa sayısı doğrulanır.

## İçerik sınırı

Renderer yalnız dondurulmuş manifest içindeki:

- başlıkları,
- NACE kimliğini,
- beş eğitim konusunu,
- teknik ve özel riskleri,
- kontrol hiyerarşisi işaretlerini,
- 5 + 15 sınav dağılımını,
- resmî kaynak kayıtlarını,
- uzman onayı yer tutucularını

kullanır.

Başka sektörden konu veya risk eklenmez. Kaynaksız teknik iddia üretilmez.

## Depolama

Dosyalar yalnız mevcut:

`get_object_store().put_bytes()`

üzerinden kaydedilir.

Doğrudan local disk, R2, S3 veya MinIO kodu yazılmaz. Böylece mevcut `local`, `dual`, `s3/r2` ve `remote-required` davranışları korunur.

Anahtar yapısı:

`training-presentations/company-{company_id}/training-{training_id}/version-{version}/...`

Şirket, eğitim ve sürüm sınırı dosya yolunda açıkça korunur.

## Atomik iki dosya davranışı

1. PPTX ve PDF önce bellekte üretilir ve yeniden açılarak doğrulanır.
2. İki dosyanın SHA-256 hash'i hesaplanır.
3. PPTX object storage'a yazılır.
4. PDF object storage'a yazılır.
5. Her iki yazma tamamlandıktan sonra sürüm kaydı `generated` yapılır.
6. Veritabanı commit'i başarılı olduktan sonra işlem tamamlanır.

PDF yazması başarısızsa PPTX silinir. Veritabanı commit'i başarısızsa iki dosya da silinir. Yarım sunum paketi başarılı gibi gösterilmez.

## Hata davranışı

Renderer, depolama veya veritabanı hatasında yalnız sunum sürümü `failed` olur.

Kaydedilen hata alanları:

- `failure_code`
- `failure_detail`
- `failed_at`

Eğitim, sınav, puanlama, PDF ve sertifika kayıtları etkilenmez.

Başarısız sürüm aynı değişmez manifestle tekrar üretilebilir. `generated`, `approved` veya `archived` sürüm yerinde yeniden üretilmez.

## İndirme

Uçlar:

- `POST /api/v1/trainings/{training_id}/presentation-versions/{version_id}/render`
- `GET /api/v1/trainings/{training_id}/presentation-versions/{version_id}/download/pptx`
- `GET /api/v1/trainings/{training_id}/presentation-versions/{version_id}/download/pdf`

Render ucu düzenleme yetkisi ve feature flag gerektirir.

Tarihsel indirme feature flag kapalı olsa da çalışabilir. Her indirmede object storage'dan okunan baytların SHA-256 değeri veritabanındaki hash ile karşılaştırılır. Eşleşmeyen dosya kullanıcıya verilmez.

## Production geçişi

Kod ve bağımlılık production'a alınsa da:

`NACE_TRAINING_PRESENTATION_ENABLED=false`

kalacaktır. Bu nedenle canlı kullanıcı render isteği başlatamaz, dosya üretilemez ve object storage yazması yapılamaz. Phase 5 arayüzü ve kullanıcı kabulü tamamlanmadan özellik açılmaz.

## Testler

- Aynı manifestten birebir aynı PPTX/PDF baytları
- PPTX paket ve slayt sayısı
- Konuşmacı notları
- PDF sayfa sayısı ve Türkçe metin
- Manifest hash bozulması
- Feature flag kapalı davranışı
- PPTX başarılı/PDF başarısız rollback
- DB commit başarısız object cleanup
- İndirme hash uyuşmazlığı
- Şirket erişim sınırı
- SQLite ve PostgreSQL regresyonları
