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
- PostgreSQL migrate/restore, Render cold-start, tarayıcı E2E

**Karar:** İzole ortamda P0 ve kritik P1 sağlık/skor maddeleri kapatıldı. Tam canlı kabul için madde 7–10 (migration PG, UI/E2E, deploy) ve iki-OSGB IDOR tamamlanmalıdır.
