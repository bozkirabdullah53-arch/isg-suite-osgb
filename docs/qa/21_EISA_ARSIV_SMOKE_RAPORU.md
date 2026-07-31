# 21 — EİSA / Arşiv Smoke Raporu (G1–G6)

**Tarih:** 2026-07-20  
**Ortam:** İzole SQLite `qa_isgsuite.db` · canlı DB yok · ürün kodu değiştirilmedi  
**Script:** `backend/scripts/qa_eisa_archive_smoke.py`  
**Kanıt:** `docs/qa/logs/qa-eisa-archive-smoke.json`  
**Sonuç:** **34/34 PASS**

---

## Özet

| Durum | Sayı |
| --- | ---: |
| Başarılı | 34 |
| Başarısız | 0 |
| Atlanan | 0 |

| Gap | Konu | Sonuç |
| --- | --- | --- |
| G1 | Başvuru gönder / red / sil / onay | Çalışıyor |
| G2 | OSGB kalıcı Sil + yedek kaydı | Çalışıyor |
| G3 | Abonelik listesinden Sil (aynı API) | Çalışıyor |
| G4 | Arşiv backup / liste / indir + rol | Çalışıyor |
| G5 | Risk medya sil → `deleted_file` arşiv | Çalışıyor |
| G6 | Uzman/CA → EİSA 403; GA OK | Çalışıyor |

---

## Başarılı testler (özet)

- Auth: GA / CA / uzman login  
- G6: uzman+CA `/eisa/dashboard` → **403**; GA → **200**  
- G1: paket/abonelik/OSGB listeleri; 3 başvuru; red; başvuru sil; onay; OSGB listede görünür  
- G2: `DELETE /eisa/osgb-users/{id}` → listeden düşer; `tenant_backup` oluşur  
- G4: GA yedek + indir; uzman arşiv **403**; CA kendi kapsam yedeği **200**  
- G3: onaylı OSGB abonelikte görünür → Sil → abonelikten düşer  
- G5: PNG medya yükle → sil → `deleted_file` arşiv sayısı artar  
- Health: `eisa_platform` + `central_archive` bayrakları

---

## Başarısız

Yok (son koşum).

---

## Atlanan

Yok. (İlk denemede G5 medya id yokken silme dalı atlanıyordu; PNG düzeltmesi sonrası koşuldu.)

---

## Tespit edilen durumlar (ürün düzeltmesi önerilmeden önce)

| # | Önem | Açıklama | Kanıt |
| --- | --- | --- | --- |
| O1 | Bilgi | Risk medya API yalnızca **jpg/png/webp/gif** kabul eder (PDF 422). Smoke yanlışlıkla PDF denemişti → test düzeltildi. | İlk koşum `g5_risk_media_upload` 422 |
| O2 | Orta / doğrulama eksik | CA, GA’nın aldığı OSGB1 yedeğini indirebildi (**200**) çünkü seed’de aynı `osgb_id`. Çapraz-OSGB arşiv IDOR (`osgb2` admin ≠ OSGB1 arşiv) bu suite’te **kanıtlanmadı**. | `g4_ca_cross_archive_denied_or_own` HTTP 200 |
| O3 | Kapsam | G5’te yalnızca **risk medya** kancası otomatik. Doküman pasife / ziyaret defteri / sözleşme değişimi / sağlık raporu arşivi **test edilmedi**. | Script kapsamı |

**P0 ürün hatası bu koşumda yok.**

---

## Teslim / runbook

- Script: `backend/scripts/qa_eisa_archive_smoke.py`  
- `qa_run_all.py` suite listesine eklendi  
- `docs/qa/19_QA_RUNBOOK.md` güncellendi  
- Delta: `docs/qa/20_DELTA_REGRESSION_077.md`

Ürün koduna düzeltme **yapılmadı** — onayın sonrası O2/O3 derinleştirmesi veya Aşama 8.
