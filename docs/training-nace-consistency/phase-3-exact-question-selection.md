# Faz 3 — Doğrulanmış NACE Snapshot'ına Bağlı Soru Seçimi

**Tarih:** 5 Ağustos 2026  
**Dal:** `agent/training-exact-nace-question-selection-phase-3`  
**Durum:** Geliştirme ve CI doğrulaması; canlı strict mod varsayılan olarak kapalıdır.

## Amaç

Faz 2'de oluşturulan değişmez ve doğrulanmış NACE snapshot'ını sınav soru seçiminin güven kaynağı yapmak; doğrulanmış yeni eğitimlerde ilgisiz sektör alias'ı veya `genel_uretim` sorusuyla sessiz tamamlama yapılmasını engellemek.

## Korunan davranışlar

- Tarihsel sınav snapshotları değiştirilmez.
- `legacy_unverified` eğitimler eski seçim davranışını kullanmaya devam eder.
- Mevcut PDF düzeni ve 20 soru yapısı değiştirilmez.
- Özellik bayrağı kapalıyken doğrulanmış eğitimlerde de mevcut davranış korunur.
- Soru bankası veya sınav verileri otomatik olarak değiştirilmez.

## Yeni strict seçim yolu

`TRAINING_EXACT_NACE_EXAM_STRICT=true` olduğunda ve eğitim için `persisted + verified` NACE snapshot bulunduğunda soru seçimi şu kapsamlarla sınırlandırılır:

1. Ortak soru (`common=*`)
2. Snapshot tehlike sınıfı
3. Snapshot'taki tam NACE katalog anahtarı
4. Snapshot'taki açıkça incelenmiş içerik profili
5. Snapshot NACE koduyla segment sınırlarında eşleşen NACE kapsamı

Aşağıdakiler strict yolda kullanılmaz:

- `genel_uretim` sessiz tamamlama
- Başka sektöre yönlendiren curated alias
- Faaliyet adı benzerliğine dayalı tahmin
- Doğrulanmamış legacy kayda uydurma NACE

Yeterli soru yoksa sistem fail-closed davranır ve sınav üretmez.

## Özellik bayrağı

```text
TRAINING_EXACT_NACE_EXAM_STRICT=false
```

Varsayılan `false` değeridir. Canlıda ayrıca bir ayar değişikliği yapılmadıkça mevcut sınav davranışı değişmez.

## Salt okunur denetim API'si

```http
GET /api/v1/trainings/{training_id}/exam-selection-audit
```

Yanıt şu karşılaştırmayı verir:

- `legacy.database`: mevcut DB seçimi
- `legacy.curated`: mevcut alias destekli paket seçimi
- `strict.database`: exact NACE/profile seçimi
- `strict.curated`: alias kullanılmadan exact NACE/profile seçimi
- `legacy_ready_but_strict_blocked`: yalnız eski fallback sayesinde hazır görünen eğitim
- `alias_only_sector_question_count`: strict seçimde kabul edilmeyen alias kaynaklı soru sayısı

Endpoint salt okunurdur; sınav oluşturmaz, soru bankasını değiştirmez ve özellik bayrağını açmaz.

## Test kapsamı

- Verified snapshot + strict modda `genel_uretim` soruları reddedilir.
- Verified snapshot + incelenmiş içerik profili soruları kabul edilir.
- Legacy eğitim strict bayrak açık olsa bile geriye uyumlu kalır.
- Bayrak kapalıyken canlı davranış değişmez.
- Curated alias ile gelen sektör soruları audit raporunda görünür.
- Strict seçimle üretilen snapshot ayrı selection policy ile işaretlenir.

## Faz sınırı

Bu faz 20 soruluk mevcut `5 temel + 5 ortak + 5 tehlike + 5 sektör` dağılımını değiştirmez. `5 temel + 15 doğrulanmış NACE/işe özgü teknik soru` hedefi, yeterli ve onaylı soru kapsamı oluşturulduktan sonra ayrı ve kontrollü bir fazda uygulanacaktır.

## Canlıya geçiş ön koşulları

1. CI tamamen yeşil olmalıdır.
2. Audit API ile temsilî sektörler kontrol edilmelidir.
3. Strict seçimde bloklanan NACE/profil listesi çıkarılmalıdır.
4. Her hedef profil için yeterli onaylı soru bulunmalıdır.
5. Önce staging veya kontrollü canary ortamında `TRAINING_EXACT_NACE_EXAM_STRICT=true` denenmelidir.
6. PDF, mevcut snapshot tekrar indirme ve legacy eğitim regresyon testleri başarılı olmalıdır.
7. Ardından üretim bayrağı kontrollü biçimde açılmalıdır.
