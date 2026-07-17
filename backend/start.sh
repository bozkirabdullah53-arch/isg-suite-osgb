#!/usr/bin/env sh
set +e
echo "=== Running alembic upgrade ==="
alembic upgrade head 2>&1 || echo "Alembic migration skipped (non-fatal)"
echo "=== Starting uvicorn ==="
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
