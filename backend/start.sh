#!/usr/bin/env sh
set -eu

echo "=== ISG Suite API boot ==="
echo "RENDER_GIT_COMMIT=${RENDER_GIT_COMMIT:-unknown}"
echo "PORT=${PORT:-8000}"

echo "=== Running database migrations ==="
if alembic upgrade head; then
  echo "=== Migrations OK ==="
else
  echo "WARN: alembic upgrade FAILED — fallback create_all + stamp head"
  python - <<'PY'
from app.core.database import Base, engine
from app.models import entities  # noqa: F401

Base.metadata.create_all(bind=engine)
print("create_all OK")
PY
  alembic stamp head
  echo "=== Schema fallback OK ==="
fi

echo "=== Starting API (uvicorn) ==="
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
