# 12 — Deploy ve Canlı Risk Değerlendirmesi

**Güncelleme:** 2026-07-20 canlı latency smoke

| Risk | Kanıt | Durum |
| --- | --- | --- |
| Cold/warm latency | cold ~233–413 ms; warm p95 ~710 ms (servis uyanık) | ✅ Bütçe <5s |
| Uzun sleep cold-start | Render free sleep zorlanmadı | ⚠️ Opsiyonel |
| CORS | `www.isgsuite.tr` | ✅ |
| Auth smoke | 15/15 | ✅ |
| Sürüm | Deploy öncesi 0.9.60; `0.9.61` upload security push sonrası | ⏳ Deploy bekler |

Kanıt: `qa-live-render-smoke.json`
