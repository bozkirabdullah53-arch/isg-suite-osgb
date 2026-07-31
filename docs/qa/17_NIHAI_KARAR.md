# 17 — Nihai QA Kararı (güncelleme 0.9.77)

## KABUL — KRİTİK MADDELER KAPALI + EİSA/ARŞİV DOĞRULANDI

**Önceki kapanış:** 0.9.64 (`17` ilk sürüm)  
**Bu güncelleme:** 2026-07-20 · kod/canlı **0.9.77**

### Kanıt (izole QA)

`python scripts/qa_run_all.py` → **8/8 suite OK**

| Suite | Sonuç |
| --- | --- |
| pytest | 53 |
| qa_api_smoke | PASS |
| qa_security_smoke | 9/9 |
| qa_retest_smoke | 30/30 |
| qa_crud_smoke | 20/20 |
| qa_upload_export_smoke | 10/10 |
| qa_pdf_turkish_smoke | OK |
| qa_eisa_archive_smoke | 54/54 |

Log: `docs/qa/logs/qa-run-all.json` · EİSA detay: `21_` / `22_`

### Bu turda ek doğrulananlar

- EİSA başvuru onay/red/sil, OSGB kalıcı Sil, abonelik Sil  
- Merkezi arşiv backup/liste/indir  
- Çapraz-OSGB arşiv IDOR → **403**  
- Silme kancaları: risk medya, doküman, ziyaret defteri, sözleşme, sağlık raporu  
- Seed: saha kullanıcı ↔ profesyonel e-posta hizası  

### Risk kabulü (bloke edici değil)

- ClamAV prod disabled (`CLAMAV_HOST` opsiyonel)  
- Ödeme gateway / SMS / e-imza / İBYS yok  
- Yerel Docker PG parity opsiyonel  

### Karar

**CANLIYA ALINABİLİR** (kritik güvenlik + izolasyon + EİSA/arşiv smoke yeşil).

Yeni deploy bu QA turunda zorunlu değil; canlı zaten **0.9.77**. Seed/smoke script değişiklikleri commit/push için ayrı onay gerekir.

Runbook: `19_QA_RUNBOOK.md` · Backlog: `18_BACKLOG_RISK_KABUL.md` · Delta: `20_DELTA_REGRESSION_077.md`
