# Eğitim Faz 3–6 Kontrollü Canlı Geçiş Notu

## Özellik bayrakları

```text
TRAINING_EXACT_NACE_EXAM_STRICT=true
TRAINING_EXACT_NACE_EXAM_STRICT_AFTER=<CANLI_DEPLOY_UTC_ZAMANI>
TRAINING_COMPLETION_STRICT=true
TRAINING_COMPLETION_STRICT_AFTER=<CANLI_DEPLOY_UTC_ZAMANI>
```

## Güvenlik etkisi

- Cutover öncesi `legacy_unverified` ve verified eğitimler mevcut davranışını sürdürür.
- Cutover sonrası yeni verified eğitimlerde sınav 5 temel + 15 işe özgü sorudan oluşur.
- Cutover sonrası yeni verified eğitimlerde belge yalnız katılan ve başarı koşulunu sağlayan kişiler için üretilir.
- Tarihsel sınav snapshotları ve PDF'ler değiştirilmez.

## Canlı doğrulama

1. Render deploy commit SHA'sı PR merge SHA'sıyla eşleşmelidir.
2. `/health` 200 dönmelidir.
3. Startup logunda exact NACE selection ve completion guard `active` görünmelidir.
4. Cutover env değerleri deploy zamanından önce olmamalıdır.
5. Eski bir eğitimde mevcut PDF indirme davranışı korunmalıdır.
6. Cutover sonrası test eğitiminde completion preflight strict enforced dönmelidir.
7. Test eğitiminde 20 soruluk snapshot politikası `exact-nace-snapshot-foundation-5-plus-work-specific-15-v2` olmalıdır.
8. Devamsız veya geçemeyen katılımcı sertifika PDF'sine alınmamalıdır.

## Acil geri dönüş

```text
TRAINING_EXACT_NACE_EXAM_STRICT=false
TRAINING_COMPLETION_STRICT=false
```

Bayraklar kapatıldığında legacy davranış yeniden kullanılır. Veri migrationı veya tarihsel kayıt geri dönüşü gerekmez.
