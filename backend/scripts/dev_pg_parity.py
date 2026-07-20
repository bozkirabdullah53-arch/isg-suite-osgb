"""Docker PostgreSQL parity helper (B-02). No-op when Docker is unavailable."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "docker-compose.yml"


def main() -> int:
    if not COMPOSE.exists():
        print("FAIL docker-compose.yml bulunamadı:", COMPOSE)
        return 1
    try:
        subprocess.run(["docker", "--version"], check=True, capture_output=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("SKIP Docker yüklü değil — B-02 yerel parity bu makinede çalıştırılamaz.")
        print("Kurulum: Docker Desktop + ardından:")
        print("  docker compose up -d db")
        print("  cd backend && alembic upgrade head")
        return 0

    print("=== docker compose up -d db ===")
    subprocess.run(["docker", "compose", "-f", str(COMPOSE), "up", "-d", "db"], check=True, cwd=ROOT)

    print("=== alembic upgrade head (Postgres) ===")
    env = {
        **dict(__import__("os").environ),
        "DATABASE_URL": "postgresql+psycopg://isgsuite:isgsuite_dev_password@localhost:5432/isgsuite",
    }
    backend = ROOT / "backend"
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend,
        env=env,
    )
    if r.returncode != 0:
        print("FAIL alembic upgrade")
        return r.returncode
    print("OK Postgres parity — DATABASE_URL ile backend başlatılabilir.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
