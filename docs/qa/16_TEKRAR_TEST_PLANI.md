# 16 — Tekrar Test Planı (kapanış)

| Sıra | Alan | Durum |
| ---: | --- | --- |
| 1–6 | Config, rate limit, tenant, sağlık, upload, verify | ✅ |
| 7 | PG | ⚠️ Canlı OK / yerel Docker yok (kabul) |
| 8 | CRUD | ✅ 20/20 |
| 9 | UI + PDF/XLSX içerik | ✅ |
| 10 | Deploy latency | ✅ warm p95 <1s (uykulu cold opsiyonel kabul) |

| Suite | Sonuç |
| --- | --- |
| `qa_retest_smoke` | 29/29 |
| `qa_crud_smoke` | 20/20 |
| `qa_upload_export_smoke` | **10/10** |
| `qa_live_render_smoke` | **12/12** public (+latency budget) |
| pytest upload | 3/3 |

**Çıkış:** P0/P1 çekirdek kapalı; P2 kalanlar risk kabulü ile dokümante.
