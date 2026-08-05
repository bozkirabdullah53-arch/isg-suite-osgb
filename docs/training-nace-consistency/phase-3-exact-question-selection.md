# Faz 3–6 — NACE'ye Bağlı Sınav, Sonuç ve Belgelendirme Zinciri

**Tarih:** 5 Ağustos 2026  
**Dal:** `agent/training-exact-nace-question-selection-phase-3`  
**Durum:** Uygulama tamamlandı; CI ve regresyonlar başarılı; kontrollü cutover ile canlıya alınabilir.

## Amaç

Faz 2'de oluşturulan değişmez ve doğrulanmış NACE snapshot'ını eğitim sınavı, katılım, başarı ve belge üretiminin güven kaynağı yapmak. Doğrulanmış yeni eğitimlerde ilgisiz sektör alias'ı, `genel_uretim` sorusu, doğrulanmamış katılım veya başarısız personele belge üretimi engellenir.

## Korunan davranışlar

- Tarihsel sınav snapshotları değiştirilmez.
- Tarihsel PDF dosyaları ve mevcut belge düzeni değiştirilmez.
- `legacy_unverified` eğitimler eski davranışını kullanmaya devam eder.
- Cutover tarihinden önce oluşturulan verified eğitimler de mevcut akışını sürdürür.
- Yeni davranış iki özellik bayrağı ve iki ISO cutover zamanı ile sınırlandırılır.
- Veritabanı şeması değiştirilmez; yeni migration gerekmez.

## Yeni sınav politikası

Yeni verified NACE eğitimlerinde sınav dağılımı:

```text
5 sabit temel İSG sorusu + 15 işe ve işyerine özgü NACE sorusu = 20 soru
```

On beş işe özgü soru, snapshot'ta dondurulmuş beş eğitim konusunun her biri için üç ölçme yaklaşımıyla oluşturulur:

1. İş öncesi hazırlık ve risk değerlendirmesi
2. Kontrol tedbirleri hiyerarşisi
3. Öğrenmenin sahadaki davranışa yansıması

Her soru:

- tam NACE kodunu,
- incelenmiş içerik profilini,
- frozen eğitim konusunu,
- dört benzersiz seçeneği,
- doğru cevap gerekçesini,
- resmî ÇSGB kaynak bilgisini

taşır ve sınav snapshot'ına sabitlenir.

Seçim politikası:

```text
exact-nace-snapshot-foundation-5-plus-work-specific-15-v2
```

## Sınav cutover ayarları

```text
TRAINING_EXACT_NACE_EXAM_STRICT=true
TRAINING_EXACT_NACE_EXAM_STRICT_AFTER=2026-08-05T00:00:00Z
```

`STRICT_AFTER` öncesindeki eğitimlerde eski sınav seçimi korunur. Sonrasındaki persisted/verified NACE eğitimleri yeni 5+15 politikasını kullanır.

## Katılım, başarı ve belge zinciri

Yeni verified eğitim için sonuç akışı:

1. Katılımcının katılım durumu girilir.
2. Sınavlı eğitimde 0–100 arası puan girilir.
3. Sonuç kaydı yapılınca önceki final doğrulaması otomatik kaldırılır.
4. Kesinleştirme işleminde başarı, puan ve geçme puanından sistem tarafından türetilir.
5. Devamsız kişinin puanı temizlenir ve başarısız sayılır.
6. Eğitim tamamlandı durumuna alınır.
7. Belge PDF'sine yalnız katılan ve başarılı olan kişiler eklenir.
8. Kamuya açık doğrulamada yalnız belge almaya hak kazanan kişiler görünür.

Belge öncesi kontroller:

- Eğitim iptal edilmemiş olmalı.
- Bitiş tarihi gelmiş olmalı.
- Eğitim tamamlandı durumunda olmalı.
- Katılım kayıtları doğrulanmış olmalı.
- Sınavlı eğitimde geçme puanı ve puanlar bulunmalı.
- Başarı sonuçları doğrulanmış olmalı.
- En az bir katılımcı belgeye hak kazanmış olmalı.

## Belge cutover ayarları

```text
TRAINING_COMPLETION_STRICT=true
TRAINING_COMPLETION_STRICT_AFTER=2026-08-05T00:00:00Z
```

Cutover öncesindeki verified eğitimler ve bütün legacy eğitimler mevcut belge davranışını korur. Cutover sonrasındaki yeni verified eğitimlerde katılım–başarı zinciri zorunludur.

## API uçları

### Sınav seçim denetimi

```http
GET /api/v1/trainings/{training_id}/exam-selection-audit
```

### Belge uygunluk ön kontrolü

```http
GET /api/v1/trainings/{training_id}/completion-preflight
```

### Tek katılımcı sonucu

```http
PATCH /api/v1/trainings/{training_id}/participants/{participant_id}/result
```

### Toplu sonuç girişi

```http
PUT /api/v1/trainings/{training_id}/participant-results
```

### Sonuç kesinleştirme

```http
POST /api/v1/trainings/{training_id}/finalize
```

### Kamuya açık belge doğrulama

```http
GET /api/v1/trainings/verify/{verification_code}
```

## Kullanıcı arayüzü

Mevcut eğitim ekranı yeniden yazılmadan eklemeli bir sonuç paneli bağlanmıştır.

Panel:

- eğitim kaydını ve katılımcıları yükler,
- katılım işaretlemeyi,
- sınav puanı girişini,
- toplu kaydı,
- sonuç kesinleştirmeyi,
- belgeye hak kazanan/eksik kişi sayılarını,
- belge üretim blokajlarını

gösterir. Yeni strict eğitimde sertifika düğmesi koşullar tamamlanana kadar güvenli biçimde kilitlenir. Legacy ve cutover öncesi eğitimlerde düğme davranışı değiştirilmez.

## Otomatik test kapsamı

- 2.141 resmî NACE satırının her biri için 15 benzersiz işe özgü soru üretilir.
- Her soruda dört benzersiz seçenek, doğru cevap, gerekçe, NACE scope ve resmî kaynak bulunur.
- 5 temel + 15 işe özgü sorudan 20 soruluk sabit snapshot oluşturulur.
- Feature flag kapalıyken mevcut seçim motoru korunur.
- Legacy eğitim strict bayrak açık olsa bile korunur.
- Gelecekteki cutover tarihi mevcut verified sınav ve belge indirmelerini korur.
- Cutover sonrası eğitimde yeni sınav ve belge kuralları uygulanır.
- Eksik puanla finalizasyon reddedilir.
- Başarı puandan türetilir.
- Devamsız ve başarısız katılımcı belgeye alınmaz.
- Mevcut PDF görsel düzeni korunur.
- SQLite tam test paketi başarılıdır.
- PostgreSQL Alembic upgrade ve ORM parity başarılıdır.
- Frontend test, lint, build, E2E smoke ve bağımlılık audit başarılıdır.

## Rollback

1. Özellik bayraklarını `false` yapın; uygulama anında legacy davranışa döner.
2. Gerekirse cutover zamanlarını ileri bir tarihe taşıyın.
3. Kod rollback'i gerekirse bu sürüm öncesindeki `master` SHA kullanılmalıdır.
4. Tarihsel sınav snapshotı veya PDF verisi değiştirilmediği için veri geri dönüş işlemi gerekmez.
