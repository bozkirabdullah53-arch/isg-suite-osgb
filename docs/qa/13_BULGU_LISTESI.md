# 13 — Önceliklendirilmiş Bulgu Listesi

**Güncelleme:** 2026-07-20 (Aşama 16 tekrar test + P0/P1 kısmi kapanış)

| ID | Öncelik | Bulgu | Kanıt / durum |
| --- | --- | --- | --- |
| F-01 | P0 | Rate-limit middleware `main.py` içine kayıtlı değil | **KAPANDI** — kayıtlı + 429 birim testi |
| F-02 | P0 | Üretimde varsayılan `SECRET_KEY` kullanım riski | **KAPANDI** — `validate_runtime_settings()` |
| F-03 | P1 | Tenant izolasyonu tüm router/iki OSGB ile kanıtlanmadı | **Kısmi** — aynı OSGB firma-arası IDOR 403; iki OSGB seed yok |
| F-04 | P1 | Sağlık PII/CA ve alan bazlı gizlilik doğrulanmadı | **KAPANDI (CA)** — `COMPANY_ADMIN` `HEALTH_ROLES` dışına alındı; CA/uzman 403, hekim/DSP 200 |
| F-05 | P1 | Upload AV, traversal, içerik doğrulama ve indirme yetkisi test edilmedi | **Kısmi** — traversal + MIME reddi geçti; AV/karantina yok |
| F-06 | P1 | Public eğitim verify gerçek kodda PII sızdırma riski | **Kısmi/OK** — geçersiz minimal; geçerli kodda hard PII yok (ad/sertifika no kalır — belge doğrulama) |
| F-07 | P2 | Alembic ile `create_all`/lifespan DDL drift riski | Açık |
| F-08 | P2 | Render cold-start / “Failed to fetch” kök nedeni doğrulanmadı | Açık |
| F-09 | P2 | PDF/Excel ve UI E2E kalite kapsamı yok | Açık |
| F-10 | P3 | Docker Compose ve PostgreSQL parity çalıştırılmadı | Açık |
| F-11 | P1 | Oversight boşta geçiş skoru (hekim %43 / uzman %20) | **KAPANDI** — vacuous pass kaldırıldı (`0.9.57`–`0.9.58`) |
| F-12 | P0 | Postgres `annualplanstatus` enum’da `delayed` yok | **KAPANDI** — migration `0014` + startup heal |

P0 kapatıldı. P1 kalan: iki-OSGB IDOR kanıtı, upload AV. P2 canlı/E2E hâlâ açık.
