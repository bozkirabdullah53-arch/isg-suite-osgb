# 19 — QA Runbook (hızlı)

## Yerel tam paket

```powershell
cd backend
python scripts/seed_test_data.py          # ilk kurulum
pip install -r requirements.txt
python scripts/qa_run_all.py              # pytest + 6 smoke
```

Canlı smoke dahil:

```powershell
$env:QA_INCLUDE_LIVE='1'
python scripts/qa_run_all.py
```

Çıktı: `docs/qa/logs/qa-run-all.json`

## Tekil scriptler

| Script | Amaç |
| --- | --- |
| `qa_api_smoke.py` | API uçları + auth |
| `qa_security_smoke.py` | Token, rate-limit, OpenAPI |
| `qa_retest_smoke.py` | P0/P1 regresyon |
| `qa_crud_smoke.py` | CRUD akışları |
| `qa_upload_export_smoke.py` | Magic-byte + PDF/XLSX export |
| `qa_pdf_turkish_smoke.py` | DejaVu + Türkçe metin çıkarma |
| `qa_eisa_archive_smoke.py` | EİSA G1–G6: başvuru, OSGB Sil, arşiv, izolasyon |
| `qa_live_render_smoke.py` | Canlı Render (public + opsiyonel auth) |
| `dev_pg_parity.py` | Docker Postgres + alembic |
| `warmup_ping.py` | Render cron warm-up |

EİSA/arşiv tekil koşum:

```powershell
cd backend
$env:DATABASE_URL='sqlite:///./qa_isgsuite.db'
$env:UPLOAD_DIR='./uploads_qa'
$env:BACKUP_DIR='./backups_qa'
$env:ENVIRONMENT='qa'
python scripts/qa_eisa_archive_smoke.py
# çıktı: docs/qa/logs/qa-eisa-archive-smoke.json
```

## ClamAV (B-01, opsiyonel)

```powershell
docker compose --profile clamav up -d clamav
# .env: CLAMAV_HOST=localhost
```

Render prod: `CLAMAV_HOST` env (harici clamd veya worker).

## Canlı doğrulama

```powershell
curl https://isg-suite-api-1u9t.onrender.com/health
```

Beklenen (0.9.77+): `eisa_platform`, `central_archive`, `tenant_isolation`, `schema_bootstrap`, `render_warmup`, `clamav_scan`.

## Karar

Nihai kabul: `17_NIHAI_KARAR.md` — açık maddeler: `18_BACKLOG_RISK_KABUL.md`.  
EİSA/arşiv: `21_EISA_ARSIV_SMOKE_RAPORU.md`, `22_O2_O3_ARSIV_SMOKE_RAPORU.md`.
