# Aşama 2 — Smoke Test Sonuçları

**Tarih:** 2026-07-20  
**Ortam:** İzole QA (canlı DB kullanılmadı)  
**Karar bu aşamada:** Smoke **geçti** — tam fonksiyon/güvenlik henüz yapılmadı.

---

## Ortam

| Öğe | Değer |
| --- | --- |
| DATABASE_URL | `sqlite:///./qa_isgsuite.db` |
| UPLOAD_DIR | `./uploads_qa` |
| BACKUP_DIR | `./backups_qa` |
| ENVIRONMENT | `qa` |
| SECRET_KEY | QA-only (kod deposuna yazılmadı) |
| Port | `127.0.0.1:8010` (geçici) |

Yedek: `docs/qa/backups/` (yerel `.env` / varsa `isgsuite.db` kopyası).  
Loglar: `docs/qa/logs/`

---

## Aşama 8 yeniden koşum (P0 düzeltmeler sonrası)

**Tarih:** 2026-07-20 (gece)  
**API sürümü:** `0.9.55`

| Test | Sonuç | Not |
| --- | --- | --- |
| Alembic `0013` (sgk_registry_no) | ✅ | QA DB güncellendi |
| Pytest | ✅ **15/15** | +4 güvenlik config testi; `docs/qa/logs/pytest-rerun.txt` |
| `qa_api_smoke.py` | ⚠️ **44/45** | Tek fail: `health_company_admin_blocked_or_empty` (P1 — CA sağlık erişimi) |
| `qa_security_smoke.py` | ✅ **9/9** | Rate-limit kaydı doğrulandı; verify geçersiz kod PII yok |
| P0 rate-limit | ✅ | `SimpleRateLimitMiddleware` kayıtlı |
| P0 SECRET_KEY guard | ✅ | `validate_runtime_settings()` prod’da varsayılan anahtarı reddeder |

---

| Test | Sonuç | Kanıt / not |
| --- | --- | --- |
| QA env override | ✅ Çalışıyor | Settings `qa_isgsuite.db` / `uploads_qa` |
| Alembic `upgrade head` | ✅ Çalışıyor | 0001→0012; exit 0; `docs/qa/logs/alembic-upgrade.txt` |
| Pytest | ✅ 11/11 geçti | `docs/qa/logs/pytest.txt` (~3.4s) |
| App import | ✅ Çalışıyor | 162 route; konsol Unicode başlık uyarısı (Windows cp1252) — uygulama hatası değil |
| `GET /health` | ✅ Çalışıyor | `version: 0.9.46` |
| `GET /openapi.json` | ✅ 200 | — |
| `GET /api/v1/system/health` | ✅ 200 | — |
| `POST /auth/login` boş body | ✅ 422 (beklenen) | 500 değil |
| `npm run build` | ✅ Çalışıyor | Vite 6.4.3; dist üretildi |
| `npm audit` | Aşağıda | — |
| Docker Compose | ⏳ Test edilemedi | Bu turda çalıştırılmadı |
| PostgreSQL parity | ⏳ Test edilemedi | Yalnızca SQLite QA |
| Tam rol/UI smoke | ⏳ Test edilemedi | Seed + tarayıcı Aşama 3 |

---

## Pytest detay

```
11 passed in 3.44s
- test_company_access (3)
- test_osgb_oversight (2)
- test_smoke (1)
- test_training_rules (2)
- test_training_topics (3)
```

Kapsam hâlâ **ince**: HTTP/IDOR/sağlık gizlilik yok.

---

## Bilinen smoke sınırları

1. Canlı Render / production DB test edilmedi (bilinçli).
2. Docker image build bu aşamada yok.
3. Frontend `npm run dev` + tarayıcı oturumu yok.
4. Rate limit hâlâ middleware’e bağlı değil (kod hipotezi; düzeltme onayı bekliyor).

---

## Aşama 2 hükmü

| Madde | Durum |
| --- | --- |
| Backend ayağa kalkıyor | Çalışıyor |
| Migration temiz SQLite | Çalışıyor |
| Mevcut birim testleri | Çalışıyor |
| Frontend production build | Çalışıyor |
| Canlıya hazır mı? | **Henüz karar verilmez** (Aşama 3–7 eksik) |

---

## Sonraki (Aşama 3)

Onayla devam: QA seed (`TEST_OSGB_*`) + API fonksiyon smoke (auth, companies, assignments, annual-plans generate, health meta) + kritik hipotezlerin ilk doğrulamaları.
