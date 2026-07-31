# Aşama 3 — Fonksiyon Smoke (kısmi) Sonuçları

**Tarih:** 2026-07-20  
**Ortam:** `qa_isgsuite.db` + `seed_test_data.py` (`TEST_` önekli)  
**Kanıt:** `docs/qa/logs/qa-api-smoke.json`, `seed-test-data.txt`

---

## Seed

| Öğe | Sonuç |
| --- | --- |
| TEST_OSGB | ✅ TEST_OSGB Denetim Merkezi |
| Firmalar | ✅ 3 (Az / Tehlikeli / Çok Tehlikeli) |
| Kullanıcılar | ✅ 17 (GA, CA, uzman, hekim, DSP, readonly, inactive) |
| Parola (QA) | `TestPass12345!` (yalnızca test) |

---

## API smoke sonuçları (TestClient)

| Test | Sonuç | HTTP | Not |
| --- | --- | --- | --- |
| Login global admin | ✅ Çalışıyor | 200 | — |
| Yanlış şifre | ✅ Çalışıyor | 401 | — |
| `/auth/me` | ✅ Çalışıyor | 200 | role=global_admin |
| Token yok → companies | ✅ Çalışıyor | 401 | — |
| Companies list (GA) | ✅ Çalışıyor | 200 | n=3 TEST_ |
| Login uzman | ✅ Çalışıyor | 200 | — |
| **Otomatik yıllık plan üret (uzman)** | ✅ **Çalışıyor** | 200 | created=13, workday_adjusted |
| Aynı yıl tekrar üret | ✅ Çalışıyor | 200 | created=0 (idempotent) |
| Sağlık listesi (uzman) | ✅ Çalışıyor | **403** | Uzman engelli |
| Login hekim | ✅ Çalışıyor | 200 | — |
| Sağlık listesi (hekim) | ✅ Çalışıyor | 200 | — |
| Login firma admin | ✅ Çalışıyor | 200 | — |
| IDOR employees diğer firma | ✅ Çalışıyor | **403** | Mesaj: görevlendirilen işyerleri |
| Assignments list (GA) | ✅ Çalışıyor | 200 | n=9 |
| Eğitim verify geçersiz kod | ✅ Çalışıyor | 200 | `valid:false` (tasarım) |

**Özet:** 15/15 geçti (verify beklentisi düzeltildi: 200+valid:false).

---

## Önemli bulgu (ürün)

Canlıda “Otomatik Plan Üret” Failed to fetch idi; **izole QA’da uzman hesabıyla generate çalışıyor**.  
→ Canlı sorun büyük olasılıkla **Render cold-start / ağ**, iş kuralı değil. Deploy + wake/retry sonrası doğrulanmalı.

---

## Henüz test edilmedi (Aşama 3 devam)

- Risk / olay / KKD / eğitim PDF / Excel import  
- Görevlendirme sonlandır/askı/sil HTTP  
- CRM / finans  
- Dosya upload path traversal  
- Tarayıcı UI  
- Çok OSGB izolasyonu (tek TEST_OSGB seed)

---

## Aşama 3 ara hükmü

| Alan | Durum |
| --- | --- |
| Auth temel | Çalışıyor |
| Firma listesi + IDOR engeli (örnek) | Çalışıyor |
| Yıllık plan otomatik üret (uzman) | Çalışıyor |
| Sağlık rol ayrımı (uzman 403 / hekim 200) | Çalışıyor |
| Tam modül kapsamı | Test edilemedi (devam) |

**Düzeltme yapılmadı** (plan gereği).
