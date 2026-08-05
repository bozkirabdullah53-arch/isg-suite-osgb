# Faz 3 Kullanıcı Kabul Testi

Bu kontrol listesi yalnız Faz 3 soru seçimi içindir. Strict özellik bayrağı kapalıyken mevcut canlı sınav davranışı değişmez.

## A. Snapshot doğrulama

1. Yeni ve tam NACE seçilmiş bir eğitim açın.
2. `GET /api/v1/trainings/{training_id}/nace-classification` çağrısında:
   - `persisted=true`
   - `classification_status=verified`
   - `catalog_key=nace_...`
   - tam NACE kodu ve içerik profili
   göründüğünü doğrulayın.

## B. Soru seçimi audit raporu

1. `GET /api/v1/trainings/{training_id}/exam-selection-audit` çağrısını yapın.
2. `verified_snapshot=true` olmalıdır.
3. `legacy` ve `strict` sayaçlarını karşılaştırın.
4. `legacy_ready_but_strict_blocked=true` ise sınav yalnız alias/genel fallback sayesinde tamamlanabiliyor demektir.
5. `alias_only_sector_question_codes` alanındaki sorular ilgili eğitim için strict seçimde kullanılmayacaktır.

## C. Bayrak kapalı regresyonu

Render ortamında `TRAINING_EXACT_NACE_EXAM_STRICT` tanımlı değilken veya `false` iken:

- Mevcut sınav PDF davranışı değişmemelidir.
- Tarihsel snapshot tekrar indirildiğinde aynı içerik gelmelidir.
- Legacy eğitimlerde mevcut fallback çalışmaya devam etmelidir.

## D. Kontrollü strict test

Yalnız staging/canary ortamında:

```text
TRAINING_EXACT_NACE_EXAM_STRICT=true
```

- Verified eğitimde `genel_uretim` veya ilgisiz alias sorusu seçilmemelidir.
- Exact NACE, NACE öneki veya incelenmiş içerik profiline ait yeterli soru varsa sınav hazırlanmalıdır.
- Yeterli soru yoksa sistem açık hata vermeli; ilgisiz soruyla sınavı tamamlamamalıdır.
- Legacy eğitimler aynı davranışı sürdürmelidir.

## E. Üretim açma kararı

Strict mod ancak hedef NACE/profillerin tamamında `strict.ready=true` olduktan ve sınav PDF'leri uzman tarafından içerik yönünden incelendikten sonra üretimde açılmalıdır.
