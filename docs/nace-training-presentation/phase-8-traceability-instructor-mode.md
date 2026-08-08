# Faz 8 — Soru-Slayt İzlenebilirliği ve Eğitmen Modu

Bağlı epic: #74  
Görev: #124

## Amaç

Yeni NACE eğitim sunumu sürümlerinde her 20 sınav sorusunu, öğretildiği bilgi kavramı, sunum slaytı ve kaynak ile makine tarafından doğrulanabilir biçimde bağlamak; doğrulanmış manifesti uygulama içinde tam ekran Eğitmen Modu ile göstermek.

Bu faz mevcut eğitim, sınav, puanlama, katılım, PDF, sertifika, imza ve tarihsel sunum kayıtlarını yeniden yazmaz.

## Güvenli varsayılan ve kill-switch

Kod production'a alınırken yeni katman varsayılan olarak kapalıdır:

```env
NACE_TRAINING_PRESENTATION_TRACEABILITY_ENABLED=false
NACE_TRAINING_PRESENTATION_TRACEABILITY_FORCE_OFF=false
```

Acil kapatma:

```env
NACE_TRAINING_PRESENTATION_TRACEABILITY_FORCE_OFF=true
```

Phase 8 kapalıyken Phase 1–7 davranışı aynen korunur. Ana sunum özelliğinin mevcut `NACE_TRAINING_PRESENTATION_ENABLED`, `NACE_TRAINING_PRESENTATION_FORCE_OFF` ve şirket allowlist sınırları ayrıca geçerliliğini korur.

## Veri ve migration kararı

Bu fazda migration yoktur.

Yeni izlenebilirlik verisi yalnız yeni oluşturulan değişmez sunum manifestinin içine dondurulur:

- `learning_concepts`
- `question_links`
- `coverage`

Eski sunum sürümleri, sınav snapshotları ve belge kayıtları yerinde değiştirilmez. Yeni manifest sürümü eski kaydı migrate etmez.

## Zorunlu 20/20 kalite kapısı

Yeni sunum oluşturma ve onay akışı aşağıdaki şartların tamamını arar:

- toplam soru: **20**
- bağlı soru: **20/20**
- kaynak bağlantısı bulunan soru: **20/20**
- orphan soru: **0**
- geçersiz slayt bağlantısı: **0**
- başka sektör fallback'i: **0**
- dondurulmuş işe özgü konu: **5/5**
- doğrulanmış teknik bilgi paketi: **5/5**

Bu kapı tamamlanmazsa yeni sunum üretimi/onayı fail-closed durur. Çekirdek eğitim/sınav/PDF/sertifika akışı açık kalır.

## İçerik yaklaşımı

İşe özgü 15 soru, beş dondurulmuş konu için üç öğrenme boyutuna ayrılır:

1. tehlikeyi tanıma
2. kontrol tedbirleri
3. güvenli saha davranışı

Bir konu için kaynak kontrollü teknik bilgi paketi yoksa genel içerik veya başka sektör sorusu kullanılmaz. Durum `İçerik doğrulaması bekleniyor` olarak kalır.

## Eğitmen Modu

Mevcut Eğitim sayfasındaki sunum paneline izole `Eğitmen Modu` eylemi eklenir.

Eğitmen Modu yalnız 20/20 izlenebilirlik taşıyan üretilmiş/onaylanmış/arşivlenmiş yeni sürümü açar. Eski v1 manifestte kullanıcıya yeni sürüm oluşturması gerektiği söylenir; tarihsel kayıt değiştirilmez.

Kontroller:

- tam ekran slayt görünümü
- önceki/sonraki
- `←` / `→`
- `PageUp` / `PageDown`
- `Home` / `End`
- `Escape` ile kapanış
- slayta bağlı sınav soru sayısı
- kaynak özeti
- uzman/işyeri onayı gerekli slayt göstergesi
- mobil ve reduced-motion uyumu

## Staging sırası

1. Phase 8 kodu CI kapılarından geçirilir.
2. Staging branch'e alınır ve Render staging API/web auto-deploy tamamlanır.
3. Staging API'de `NACE_TRAINING_PRESENTATION_TRACEABILITY_ENABLED=true` açılır.
4. Health/startup/migration kontrolü yapılır.
5. Desteklenen exact-NACE örneklerinde 20/20 manifest ve Eğitmen Modu doğrulanır.
6. Desteklenmeyen konuda üretimin güvenli biçimde durduğu doğrulanır.

## Production pilot sırası

Production genel aktivasyon yapılmaz. Mevcut kontrollü pilot sınırı korunur.

Hedef doğrulanmış pilot:

```text
AYAN ACADEMY
company_id=118
```

Sıra:

1. Kod master'a alınır; Phase 8 flag kapalı kalır.
2. Production API/web deploylarının live ve `/health` 200 olduğu doğrulanır.
3. Mevcut eğitim/sınav/PDF/sertifika davranışında regresyon olmadığı kontrol edilir.
4. Yalnız bundan sonra `NACE_TRAINING_PRESENTATION_TRACEABILITY_ENABLED=true` açılır.
5. Yeni deploy live olduktan sonra health/log/metric kontrolleri tekrarlanır.
6. Pilot şirket için yeni sunum sürümü ancak açık kullanıcı eylemiyle oluşturulur; otomatik kayıt üretilmez.
7. Pilot kalite kapısı geçmeden allowlist genişletilmez.

## Rollback

İlk müdahale:

```env
NACE_TRAINING_PRESENTATION_TRACEABILITY_FORCE_OFF=true
```

Gerekirse:

```env
NACE_TRAINING_PRESENTATION_TRACEABILITY_ENABLED=false
```

Sunum ana özelliğinin de kapatılması gerekirse mevcut Phase 7 sırası kullanılır:

```env
NACE_TRAINING_PRESENTATION_FORCE_OFF=true
```

Rollback sırasında veri silinmez, destructive downgrade yapılmaz ve tarihsel manifest/PPTX/PDF/onay kayıtları korunur.
