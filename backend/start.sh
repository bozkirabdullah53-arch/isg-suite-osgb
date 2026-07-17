#!/usr/bin/env sh
set -eu

echo "=== Running database migrations ==="
alembic upgrade head

echo "=== Starting API ==="
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
