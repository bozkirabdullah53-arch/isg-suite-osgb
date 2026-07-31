"""QA security smoke — Phase 5. Isolated. Non-destructive."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "sqlite:///./qa_isgsuite.db")
os.environ.setdefault("UPLOAD_DIR", "./uploads_qa")
os.environ.setdefault("ENVIRONMENT", "qa")
os.environ.setdefault("SECRET_KEY", "qa-test-secret-key-at-least-32-characters-ok")

from fastapi.testclient import TestClient
from app.main import app

OUT = []


def rec(name, ok, detail="", http=None):
    OUT.append({"test": name, "ok": ok, "http": http, "detail": detail[:240]})
    print(("PASS" if ok else "FAIL"), name, http or "", detail[:100])


def main():
    c = TestClient(app)
    rec("no_token_companies", c.get("/api/v1/companies").status_code == 401)
    rec("bad_bearer", c.get("/api/v1/companies", headers={"Authorization": "Bearer x.y.z"}).status_code == 401)
    rec("empty_login", c.post("/api/v1/auth/login", json={}).status_code in (422, 400))

    # OpenAPI exposure (info finding)
    docs = c.get("/docs")
    rec("openapi_docs_exposed", docs.status_code == 200, detail="INFO: /docs açık — canlıda kapatılabilir")

    # Rate limit registration
    mw = []
    try:
        mw = [m.cls.__name__ if hasattr(m, "cls") else str(m) for m in app.user_middleware]
    except Exception as e:
        mw = [str(e)]
    rec("rate_limit_registered", any("RateLimit" in str(x) for x in mw), detail=str(mw), http=None)

    # Default secret key smell in settings (code-level)
    from app.core.config import settings
    sk = settings.secret_key or ""
    weak = sk in ("change-me", "secret", "") or len(sk) < 16 or "dev" in sk.lower()
    # QA secret is intentional — flag if looks like production default from source
    rec("secret_key_not_trivial_in_qa_env", not weak or "qa-test" in sk, detail=f"len={len(sk)}")

    tv = c.get("/api/v1/trainings/verify/INVALID")
    body = tv.json() if tv.status_code == 200 else {}
    pii_keys = {"national_id", "tc_kimlik", "email", "phone", "full_name", "participants"}
    leaked = bool(pii_keys.intersection(body.keys())) and body.get("valid") is False
    rec("verify_invalid_no_pii", tv.status_code == 200 and body.get("valid") is False and not leaked, http=tv.status_code)

    for p in ["/api/v1/files/../main.py", "/api/v1/files/..%2F..%2Fetc/passwd"]:
        r = c.get(p)
        rec(f"path_traversal_{p[-24:]}", r.status_code in (400, 401, 403, 404, 422), http=r.status_code)

    summary = {"passed": sum(1 for x in OUT if x["ok"]), "failed": sum(1 for x in OUT if not x["ok"]), "total": len(OUT), "results": OUT}
    out = ROOT.parent / "docs" / "qa" / "logs" / "qa-security-smoke.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SUMMARY", summary["passed"], "/", summary["total"])
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
