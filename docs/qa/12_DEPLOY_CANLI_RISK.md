# 12 — Deploy ve Canlı Risk Değerlendirmesi

**Güncelleme:** 2026-07-20 canlı Render public smoke (`qa_live_render_smoke.py`)

| Risk | Kanıt | Etki | Durum |
| --- | --- | --- | --- |
| Render cold-start | Canlı `/health` cold **731 ms**, warm **227 ms** (servis uyanıktı) | Uzun uyku sonrası p95 henüz ölçülmedi | ⚠️ Kısmi — warm OK; derin sleep senaryosu yok |
| Ağ/CORS/proxy | Preflight `ACA-Origin=https://www.isgsuite.tr` 200; web home 200 | API erişimi | ✅ Public CORS OK |
| Canlı API sürümü | `version=0.9.59` + rate_limit / secret_key_guard / health_roles marker | Deploy doğrulandı | ✅ |
| Canlı DB migration | Auth’lu oversight/enum bu turda çalıştırılmadı (credential yok) | Enum/şema | ⏳ Auth smoke bekliyor |
| Sır yapılandırması | Canlı `.env` okunmadı; app ayakta + marker `secret_key_guard` | JWT | ⚠️ Marker var; sır değeri görülmedi (doğru) |
| Rate limit | Marker `simple-rpm-120`; canlıda 429 yük testi yok | Abuse | ⚠️ Kayıtlı; canlı 429 yükü yok |
| Upload kalıcılığı | Test edilmedi | Veri | Doğrulanmadı |
| İzleme/rollback | Runbook yok | Müdahale | Doğrulanmadı |

## Canlı public smoke özeti

| Test | Sonuç |
| --- | --- |
| `GET /health` cold/warm | ✅ 200 |
| Version ≥ 0.9.56 | ✅ 0.9.59 |
| Unauth companies | ✅ 401 |
| Training verify invalid | ✅ minimal alanlar |
| `www.isgsuite.tr` | ✅ 200 |
| CORS preflight | ✅ |

Kanıt: `docs/qa/logs/qa-live-render-smoke.json`

**Auth’lu canlı smoke:** `LIVE_SMOKE_EMAIL` + `LIVE_SMOKE_PASSWORD` ile tekrar çalıştırılmalı (login, companies, oversight, delayed-enum regresyon).
