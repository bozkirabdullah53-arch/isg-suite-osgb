# 17 — Nihai QA Kararı

## AŞAMA 16 TEKRAR TEST SONRASI — P1 KISMİ / P2 AÇIK

İzole QA tekrar smoke (**23/23**), API smoke (**45/45**), security smoke (**9/9**) ve pytest geçti.

**Kapanan:**
- P0 rate-limit + SECRET_KEY guard
- Postgres `delayed` enum
- Oversight vacuous skor (hekim/uzman)
- CA sağlık API erişimi (403)

**Hâlâ açık / kısmi:**
- İki OSGB tenant IDOR kanıtı (seed’de tek OSGB)
- Upload AV/karantina
- PostgreSQL migrate/restore, tarayıcı E2E
- Canlı **auth’lu** smoke (credential ile oversight/enum)
- Render uzun sleep cold-start (bu turda servis zaten sıcaktı: 731 ms)

**Canlı public smoke (2026-07-20):** API `0.9.59`, CORS + web OK — `docs/qa/logs/qa-live-render-smoke.json`

**Karar:** İzole P0/kritik P1 + canlı public deploy doğrulandı. Tam canlı kabul için auth’lu Render smoke, PG/restore ve UI E2E tamamlanmalıdır.
