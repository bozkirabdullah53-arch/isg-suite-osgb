"""Tek komutla yerel QA paketi (pytest + smoke scriptleri).

Çalıştır:
  cd backend
  python scripts/seed_test_data.py   # ilk kurulumda
  python scripts/qa_run_all.py

İsteğe bağlı canlı smoke:
  $env:QA_INCLUDE_LIVE='1'
  python scripts/qa_run_all.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
LOG_DIR = REPO / "docs" / "qa" / "logs"
PY = sys.executable

SUITES: list[tuple[str, list[str]]] = [
    ("pytest", ["-m", "pytest", "tests/", "-q", "--tb=no"]),
    ("qa_api_smoke", ["scripts/qa_api_smoke.py"]),
    ("qa_security_smoke", ["scripts/qa_security_smoke.py"]),
    ("qa_retest_smoke", ["scripts/qa_retest_smoke.py"]),
    ("qa_crud_smoke", ["scripts/qa_crud_smoke.py"]),
    ("qa_upload_export_smoke", ["scripts/qa_upload_export_smoke.py"]),
    ("qa_pdf_turkish_smoke", ["scripts/qa_pdf_turkish_smoke.py"]),
]

if os.environ.get("QA_INCLUDE_LIVE", "").strip().lower() in ("1", "true", "yes"):
    SUITES.append(("qa_live_render_smoke", ["scripts/qa_live_render_smoke.py"]))


def run_suite(name: str, args: list[str]) -> dict:
    t0 = time.perf_counter()
    env = {
        **os.environ,
        "DATABASE_URL": os.environ.get("DATABASE_URL", "sqlite:///./qa_isgsuite.db"),
        "UPLOAD_DIR": os.environ.get("UPLOAD_DIR", "./uploads_qa"),
        "ENVIRONMENT": os.environ.get("ENVIRONMENT", "qa"),
        "SECRET_KEY": os.environ.get("SECRET_KEY", "qa-test-secret-key-at-least-32-characters-ok"),
    }
    proc = subprocess.run([PY, *args], cwd=ROOT, env=env, capture_output=True, text=True)
    ms = round((time.perf_counter() - t0) * 1000, 1)
    ok = proc.returncode == 0
    tail = (proc.stdout or proc.stderr or "").strip().splitlines()
    detail = tail[-1][:200] if tail else f"exit={proc.returncode}"
    print(("PASS" if ok else "FAIL"), name, f"{ms}ms", detail)
    return {
        "suite": name,
        "ok": ok,
        "ms": ms,
        "exit_code": proc.returncode,
        "detail": detail,
    }


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    results = [run_suite(name, args) for name, args in SUITES]
    passed = sum(1 for r in results if r["ok"])
    failed = sum(1 for r in results if not r["ok"])
    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "passed": passed,
        "failed": failed,
        "total": len(results),
        "include_live": os.environ.get("QA_INCLUDE_LIVE", ""),
        "suites": results,
    }
    out = LOG_DIR / "qa-run-all.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSUMMARY {passed}/{len(results)} suites OK | failed={failed}")
    print("Wrote", out)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
