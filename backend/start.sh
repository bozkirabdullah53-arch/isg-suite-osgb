#!/usr/bin/env sh
set -eu

echo "=== ISG Suite API boot ==="
echo "RENDER_GIT_COMMIT=${RENDER_GIT_COMMIT:-unknown}"
echo "PORT=${PORT:-8000}"

echo "=== Running database migrations ==="
if ! alembic upgrade head; then
  echo "ERROR: alembic upgrade head FAILED"
  echo "Deploy cannot start with failed migrations."
  exit 1
fi
echo "=== Migrations OK ==="

echo "=== Starting API (uvicorn) ==="
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
