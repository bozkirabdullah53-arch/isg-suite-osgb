# 17 — Nihai QA Kararı

## KABUL — KRİTİK MADDELER KAPALI

İzole smoke, canlı auth/public smoke, UI E2E ve upload/export içerik testleri tamamlandı.

**Kapanan çekirdek:** rate-limit, SECRET_KEY guard, delayed enum, oversight skor, CA sağlık, iki-OSGB IDOR, upload magic+karantina, training verify kod, export PDF/XLSX, GA OSGB fallback, lifespan→alembic, Render warm-up cron.

**Risk kabulü ile kısmi/açık:**
- Tam antivirüs motoru (ClamAV — `CLAMAV_HOST` ile opsiyonel)
- Yerel Docker PostgreSQL parity (Docker yoksa SKIP)
- Render uzun sleep cold-start (cron + latency smoke)
- PDF piksel/görsel tipografi (otomasyon: DejaVu + metin çıkarma)
- Lifespan DDL → migration `0015` (tamamlandı, canlı doğrulandı)

**Karar:** Ürün **kritik güvenlik ve izolasyon** açısından canlı kullanıma uygun kabul edilir. Kalan maddeler bloke edici değildir.

**Canlı sürüm (2026-07-20):** **0.9.64** — `schema_bootstrap: alembic-only-v1`, `render_warmup: cron-14m`, `clamav_scan: disabled`. Yerel paket: `qa_run_all.py` **7/7** suite.

Runbook: `19_QA_RUNBOOK.md` · Backlog: `18_BACKLOG_RISK_KABUL.md`
