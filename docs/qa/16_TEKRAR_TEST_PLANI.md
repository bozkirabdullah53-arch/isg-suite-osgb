# 16 — Tekrar Test Planı

**Son koşum:** 2026-07-20 — iki-OSGB IDOR + F-13 + export MIME

| Sıra | Alan | Durum |
| ---: | --- | --- |
| 1–2 | SECRET_KEY + rate limit | ✅ |
| 3 | Tenant / iki OSGB IDOR | ✅ Seed `TEST_OSGB Rakip` + çapraz 403 (`qa_retest` 29/29) |
| 4 | Sağlık rolleri | ✅ |
| 5 | Dosya traversal/MIME | ⚠️ AV yok |
| 6 | Eğitim verify + kod UNIQUE | ✅ F-13 kapandı (`uuid-unique`) |
| 7 | PostgreSQL | ⚠️ Yerel Docker yok; canlı PG OK |
| 8 | CRUD | ✅ 20/20 |
| 9 | UI E2E | ✅ |
| 10 | Deploy | ✅ 15/15 |
| — | Export PDF/XLSX content-type | ✅ xlsx + pdf bytes |

## Koşum özeti

| Suite | Sonuç |
| --- | --- |
| `qa_retest_smoke` | **29/29** |
| `qa_crud_smoke` | **20/20** |
| `qa_live_render_smoke` | **15/15** |

**Kalan:** Upload AV, yerel PG Docker, PDF görsel kalite, uzun sleep cold-start.
