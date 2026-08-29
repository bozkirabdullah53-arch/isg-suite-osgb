#!/usr/bin/env sh
set -eu

echo "=== ISG Suite API boot ==="
echo "RENDER_GIT_COMMIT=${RENDER_GIT_COMMIT:-unknown}"
echo "PORT=${PORT:-8000}"
echo "ENVIRONMENT=${ENVIRONMENT:-development}"

ENV_LC=$(printf '%s' "${ENVIRONMENT:-development}" | tr '[:upper:]' '[:lower:]')

echo "=== Approved training features are source-controlled ==="

echo "=== Running database migrations ==="
if alembic upgrade head; then
  echo "=== Migrations OK ==="
else
  # Üretimde create_all + stamp head şema sapmasına yol açar — fail-fast
  case "$ENV_LC" in
    production|prod|live)
      echo "ERROR: alembic upgrade FAILED in production — refusing schema fallback"
      exit 1
      ;;
  esac
  echo "WARN: alembic upgrade FAILED — fallback create_all + stamp head (non-production only)"
  python - <<'PY'
from app.core.database import Base, engine
from app.models import entities  # noqa: F401

Base.metadata.create_all(bind=engine)
print("create_all OK")
PY
  alembic stamp head
  echo "=== Schema fallback OK ==="
fi

# Tek seferlik merkezi arşiv sıfırlama kancası.
# Sadece EISA_PURGE_ARCHIVES_ONCE doluysa çalışır; aynı token kalıcı disk üzerindeki
# marker nedeniyle ikinci kez çalışmaz. Başka uygulama verilerine dokunmaz.
if [ -n "${EISA_PURGE_ARCHIVES_ONCE:-}" ]; then
  echo "=== One-time central archive purge requested ==="
  python - <<'PY'
from __future__ import annotations

import os
import shutil
from pathlib import Path

from sqlalchemy import delete, func, select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.entities import EisaArchiveRecord

token = (os.environ.get("EISA_PURGE_ARCHIVES_ONCE") or "").strip()
if not token:
    raise SystemExit(0)

safe_token = "".join(ch for ch in token if ch.isalnum() or ch in ("-", "_"))[:80] or "once"
backup_base = Path(settings.backup_dir).resolve()
backup_base.mkdir(parents=True, exist_ok=True)
marker = backup_base / f".eisa-central-archive-purge-{safe_token}.done"
archive_root = backup_base / "central_archive"
staged_root = backup_base / f".central_archive-purge-{safe_token}"

if marker.exists():
    print(f"Central archive purge already completed for token={safe_token}; skipping.")
    raise SystemExit(0)

if staged_root.exists():
    shutil.rmtree(staged_root)

# Dosya ağacını önce aynı disk üzerinde atomik olarak kenara al. DB işlemi başarısız
# olursa klasörü geri taşıyarak kayıt/dosya tutarlılığını koru.
if archive_root.exists():
    archive_root.replace(staged_root)

try:
    with SessionLocal() as db:
        count = db.scalar(select(func.count()).select_from(EisaArchiveRecord)) or 0
        db.execute(delete(EisaArchiveRecord))
        db.commit()
except Exception:
    if staged_root.exists() and not archive_root.exists():
        staged_root.replace(archive_root)
    raise

archive_root.mkdir(parents=True, exist_ok=True)
if staged_root.exists():
    shutil.rmtree(staged_root)

marker.write_text(f"purged_records={int(count)}\n", encoding="utf-8")
print(f"Central archive purge completed: {int(count)} records removed; archive files cleared.")
PY
  echo "=== One-time central archive purge hook finished ==="
fi

case "$ENV_LC" in
  staging)
    echo "=== Running OSGB professional card scope tests ==="
    python -m pytest -q tests/test_personnel_profile_osgb_scope.py
    echo "=== OSGB professional card scope tests OK ==="
    ;;
esac

echo "=== Starting API (uvicorn) ==="
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
