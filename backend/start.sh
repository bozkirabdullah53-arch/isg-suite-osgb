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

case "$ENV_LC" in
  staging)
    echo "=== Running OSGB professional card scope tests ==="
    python -m pytest -q tests/test_personnel_profile_osgb_scope.py
    echo "=== OSGB professional card scope tests OK ==="
    ;;
esac

echo "=== Starting API (uvicorn) ==="
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
