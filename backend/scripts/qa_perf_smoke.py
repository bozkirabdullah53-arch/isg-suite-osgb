"""QA light performance smoke — Phase 6. Isolated."""
from __future__ import annotations

import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "sqlite:///./qa_isgsuite.db")
os.environ.setdefault("UPLOAD_DIR", "./uploads_qa")
os.environ.setdefault("ENVIRONMENT", "qa")
os.environ.setdefault("SECRET_KEY", "qa-test-secret-key-at-least-32-characters-ok")

from fastapi.testclient import TestClient
from app.main import app

N = 20
PASS = "TestPass12345!"


def timed(fn, n=N):
    xs = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        xs.append((time.perf_counter() - t0) * 1000)
    xs.sort()
    return {
        "n": n,
        "p50_ms": round(xs[len(xs) // 2], 2),
        "p95_ms": round(xs[int(len(xs) * 0.95)], 2),
        "avg_ms": round(statistics.mean(xs), 2),
        "max_ms": round(max(xs), 2),
    }


def main():
    c = TestClient(app)
    r = c.post("/api/v1/auth/login", json={"email": "test.global.admin@example.com", "password": PASS})
    if r.status_code != 200:
        print("LOGIN FAIL", r.status_code, r.text[:200])
        return 1
    tok = r.json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}

    results = {
        "companies": timed(lambda: c.get("/api/v1/companies", headers=h)),
        "assignments": timed(lambda: c.get("/api/v1/osgb/assignments", headers=h)),
        "health_me": timed(lambda: c.get("/api/v1/auth/me", headers=h)),
    }
    uzman = c.post("/api/v1/auth/login", json={"email": "test.az.uzman@example.com", "password": PASS})
    if uzman.status_code == 200:
        uh = {"Authorization": f"Bearer {uzman.json()['access_token']}"}
        results["risks"] = timed(lambda: c.get("/api/v1/risks", headers=uh))
        results["trainings"] = timed(lambda: c.get("/api/v1/trainings", headers=uh))

    out = ROOT.parent / "docs" / "qa" / "logs" / "qa-perf-smoke.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    print("Wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
