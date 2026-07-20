# 18 — Risk kabulü / backlog

QA kritik kapanış sonrası kalan maddeler (bloke edici değil):

| ID | Madde | Öneri | Öncelik | Durum |
| --- | --- | --- | --- | --- |
| B-01 | ClamAV / gerçek AV motoru | Render worker veya harici tarama | P2 | Kısmi — `CLAMAV_HOST` + INSTREAM; `docker compose --profile clamav up -d clamav` |
| B-02 | Yerel Docker PostgreSQL parity | Docker Desktop kurulu ortamda `compose up db` + alembic | P3 | Kısmi — `scripts/dev_pg_parity.py` (Docker yoksa SKIP) |
| B-03 | Render uzun sleep cold-start | Free tier sleep sonrası ölçüm; warm-up cron | P2 | Kısmi — cron `*/14 * * * *` + `warmup_ping.py`; canlı warm ~210 ms |
| B-04 | PDF piksel/Türkçe font görsel QA | Örnek PDF’lerin manuel/görsel kontrolü | P2 | Kısmi — `qa_pdf_turkish_smoke.py` (DejaVu + pypdf metin çıkarma) |
| B-05 | Lifespan DDL sadeleştirme | Heal’i migration’a taşıyıp bootstrap’ı incelter | P2 | Kısmi — migration `0015`; lifespan heal kaldırıldı |

Canlı API (2026-07-20): **0.9.77** — EİSA + `central_archive`. Yerel paket: `python scripts/qa_run_all.py` → **8/8** suite OK (pytest 53 + smoke + `qa_eisa_archive_smoke` 54).
