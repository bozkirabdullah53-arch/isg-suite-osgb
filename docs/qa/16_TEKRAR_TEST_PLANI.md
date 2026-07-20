# 16 — Tekrar Test Planı

**Son koşum:** 2026-07-20 — izolasyon + canlı auth + UI E2E + CRUD

| Sıra | Alan | Durum |
| ---: | --- | --- |
| 1 | Konfigürasyon SECRET_KEY | ✅ |
| 2 | Rate limit | ✅ |
| 3 | Tenant IDOR | ⚠️ Kısmi (tek OSGB seed) |
| 4 | Sağlık rolleri | ✅ |
| 5 | Dosya traversal/MIME | ⚠️ Kısmi (AV yok) |
| 6 | Eğitim verify | ✅ |
| 7 | PostgreSQL migration | ⚠️ Yerel Docker yok; canlı PG + oversight/`delayed` OK |
| 8 | Fonksiyon CRUD | ✅ `qa_crud_smoke` **20/20** |
| 9 | UI E2E | ✅ Canlı GA login + menü (`10_UI_TARAYICI.md`) |
| 10 | Deploy Render | ✅ Public+auth **15/15** |

## Koşum özeti

| Suite | Sonuç |
| --- | --- |
| pytest | 18 |
| `qa_api_smoke` | 45/45 |
| `qa_security_smoke` | 9/9 |
| `qa_retest_smoke` | 23/23 |
| `qa_live_render_smoke` | 15/15 |
| `qa_crud_smoke` | **20/20** |
| Canlı UI E2E | Login + Hizmet Denetimi + ÇSGB + İşyerleri |

**Kalan:** İki-OSGB seed, upload AV, yerel PG Docker, PDF/Excel görsel, uzun sleep cold-start.
