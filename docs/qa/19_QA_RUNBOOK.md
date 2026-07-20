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
| `qa_live_render_smoke.py` | Canlı Render (public + opsiyonel auth) |
| `dev_pg_parity.py` | Docker Postgres + alembic |
| `warmup_ping.py` | Render cron warm-up |

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

Beklenen (0.9.64+): `schema_bootstrap`, `render_warmup`, `clamav_scan`, `ga_osgb_fallback`.

## Karar

Nihai kabul: `17_NIHAI_KARAR.md` — açık maddeler: `18_BACKLOG_RISK_KABUL.md`.
