# 18 — Risk kabulü / backlog

QA kritik kapanış sonrası kalan maddeler (bloke edici değil):

| ID | Madde | Öneri | Öncelik |
| --- | --- | --- | --- |
| B-01 | ClamAV / gerçek AV motoru | Render worker veya harici tarama | P2 |
| B-02 | Yerel Docker PostgreSQL parity | Docker Desktop kurulu ortamda `compose up db` + alembic | P3 |
| B-03 | Render uzun sleep cold-start | Free tier sleep sonrası ölçüm; warm-up cron | P2 |
| B-04 | PDF piksel/Türkçe font görsel QA | Örnek PDF’lerin manuel/görsel kontrolü | P2 |
| B-05 | Lifespan DDL sadeleştirme | Heal’i migration’a taşıyıp bootstrap’ı incelter | P2 |

Canlı API doğrulama (2026-07-20): **0.9.61** (upload_security) yayında; **0.9.62** GA OSGB fallback.
