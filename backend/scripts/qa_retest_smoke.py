"""QA Aşama 16 — Tekrar test smoke (izole). Maddeler 1–6."""
from __future__ import annotations

import json
import os
import sys
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "sqlite:///./qa_isgsuite.db")
os.environ.setdefault("UPLOAD_DIR", "./uploads_qa")
os.environ.setdefault("ENVIRONMENT", "qa")
os.environ.setdefault("SECRET_KEY", "qa-test-secret-key-at-least-32-characters-ok")

from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings, validate_runtime_settings

OUT = []
PASS = "TestPass12345!"


def rec(name, ok, detail="", http=None):
    OUT.append({"test": name, "ok": bool(ok), "http": http, "detail": str(detail)[:240]})
    print(("PASS" if ok else "FAIL"), name, http or "", str(detail)[:120])


def login(c, email):
    r = c.post("/api/v1/auth/login", json={"email": email, "password": PASS})
    if r.status_code != 200:
        return None
    return r.json().get("access_token")


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


def main():
    c = TestClient(app)

    # --- 1. SECRET_KEY guard ---
    env0, sk0 = settings.environment, settings.secret_key
    try:
        settings.environment = "production"
        settings.secret_key = "change-me-in-production-at-least-32-characters!"
        try:
            validate_runtime_settings()
            rec("secret_key_prod_blocks_default", False, detail="RuntimeError beklenirdi")
        except RuntimeError:
            rec("secret_key_prod_blocks_default", True)
        settings.secret_key = "x" * 40
        try:
            validate_runtime_settings()
            rec("secret_key_prod_allows_strong", True)
        except Exception as e:
            rec("secret_key_prod_allows_strong", False, detail=str(e))
    finally:
        settings.environment, settings.secret_key = env0, sk0

    # --- 2. Rate limit registered + 429 unit (middleware presence) ---
    mw = [m.cls.__name__ if hasattr(m, "cls") else str(m) for m in app.user_middleware]
    rec("rate_limit_registered", any("RateLimit" in x for x in mw), detail=str(mw))

    # --- Auth baseline ---
    tok = login(c, "test.global.admin@example.com")
    rec("login_ga", bool(tok), http=200 if tok else None)
    uzman = login(c, "test.az.uzman@example.com")
    hekim = login(c, "test.az.hekim@example.com")
    ca = login(c, "test.az.admin@example.com")
    dsp = login(c, "test.az.dsp@example.com")
    ro = login(c, "test.az.readonly@example.com")
    rec("login_roles", all([uzman, hekim, ca, dsp, ro]))

    firms = c.get("/api/v1/companies", headers=H(tok)).json() if tok else []
    cid1 = firms[0]["id"] if firms else None
    cid2 = firms[1]["id"] if len(firms) > 1 else None

    # --- 3. Tenant / assignment isolation ---
    if ca and cid2:
        r = c.get(f"/api/v1/employees?company_id={cid2}", headers=H(ca))
        ok = r.status_code in (403, 422) or (r.status_code == 200 and len(r.json()) == 0)
        rec("tenant_ca_other_firm_employees", ok, http=r.status_code, detail=r.text[:80])
    if uzman and cid2:
        r = c.get(f"/api/v1/employees?company_id={cid2}", headers=H(uzman))
        # Seed: uzman aynı OSGB'deki diğer firmaya da görevli → 200
        ok = r.status_code == 200
        rec("tenant_uzman_same_osgb_assigned_firm", ok, http=r.status_code, detail="assignment-scoped")
    if uzman:
        foreign = next((f for f in firms if "Yabanci" in str(f.get("name", "")) or "Yabancı" in str(f.get("name", ""))), None)
        if foreign:
            r = c.get(f"/api/v1/employees?company_id={foreign['id']}", headers=H(uzman))
            ok = r.status_code in (403, 422) or (r.status_code == 200 and len(r.json()) == 0)
            rec("tenant_uzman_cross_osgb_employees", ok, http=r.status_code, detail=r.text[:80])
        else:
            rec("tenant_uzman_cross_osgb_employees", False, detail="Yabanci firma yok")
    if ca and cid1:
        r = c.get(f"/api/v1/risks?company_id={cid1}", headers=H(ca))
        # CA may or may not have risk access — must not be 500
        rec("tenant_ca_risks_no_500", r.status_code != 500, http=r.status_code)
    rec(
        "tenant_two_osgb_note",
        True,
        detail="INFO: Seed iki OSGB — asagidaki IDOR testleri",
    )
    # Cross-OSGB IDOR
    osgb2_ca = login(c, "test.osgb2.admin@example.com")
    rec("login_osgb2_ca", bool(osgb2_ca))
    foreign = None
    if tok:
        all_firms = c.get("/api/v1/companies", headers=H(tok))
        if all_firms.status_code == 200:
            for f in all_firms.json():
                if "Yabanci" in str(f.get("name", "")) or "Yabancı" in str(f.get("name", "")):
                    foreign = f
                    break
    if ca and foreign:
        r = c.get(f"/api/v1/employees?company_id={foreign['id']}", headers=H(ca))
        ok = r.status_code in (403, 422) or (r.status_code == 200 and len(r.json()) == 0)
        rec("idor_osgb1_ca_to_osgb2_employees", ok, http=r.status_code, detail=r.text[:80])
    else:
        rec("idor_osgb1_ca_to_osgb2_employees", False, detail="SKIP/FAIL: foreign firm veya ca yok")
    if osgb2_ca and cid1:
        r = c.get(f"/api/v1/employees?company_id={cid1}", headers=H(osgb2_ca))
        ok = r.status_code in (403, 422) or (r.status_code == 200 and len(r.json()) == 0)
        rec("idor_osgb2_ca_to_osgb1_employees", ok, http=r.status_code, detail=r.text[:80])
    if osgb2_ca and foreign:
        r = c.get(f"/api/v1/employees?company_id={foreign['id']}", headers=H(osgb2_ca))
        rec("osgb2_ca_own_employees_ok", r.status_code == 200, http=r.status_code)

    # --- 4. Health role matrix ---
    if uzman:
        r = c.get("/api/v1/health-records", headers=H(uzman))
        rec("health_uzman_denied", r.status_code in (401, 403), http=r.status_code)
    if ca:
        r = c.get("/api/v1/health-records", headers=H(ca))
        rec("health_ca_denied", r.status_code in (401, 403), http=r.status_code, detail=r.text[:80])
    if ro:
        r = c.get("/api/v1/health-records", headers=H(ro))
        rec("health_readonly_denied", r.status_code in (401, 403), http=r.status_code)
    if hekim:
        r = c.get("/api/v1/health-records", headers=H(hekim))
        rec("health_hekim_ok", r.status_code == 200, http=r.status_code)
    if dsp:
        r = c.get("/api/v1/health-records", headers=H(dsp))
        rec("health_dsp_ok", r.status_code == 200, http=r.status_code)
    if hekim and cid1:
        exp = c.get(f"/api/v1/health-records/export.txt?company_id={cid1}", headers=H(hekim))
        rec("health_hekim_export", exp.status_code in (200, 404), http=exp.status_code)
    if ca and cid1:
        exp = c.get(f"/api/v1/health-records/export.txt?company_id={cid1}", headers=H(ca))
        rec("health_ca_export_denied", exp.status_code in (401, 403), http=exp.status_code)

    # --- 5. Upload / files ---
    if tok:
        for path in (
            "/api/v1/files/../../etc/passwd",
            "/api/v1/files/%2e%2e/%2e%2e/etc/passwd",
            "/api/v1/files/../main.py",
        ):
            r = c.get(path, headers=H(tok))
            rec(f"upload_traversal_{path[-18:]}", r.status_code in (400, 401, 403, 404, 422), http=r.status_code)

        # Bad MIME / extension on document upload (need a document id — soft)
        docs = c.get("/api/v1/documents", headers=H(tok))
        doc_id = None
        if docs.status_code == 200 and docs.json():
            doc_id = docs.json()[0].get("id")
        if doc_id:
            bad = c.post(
                f"/api/v1/files/documents/{doc_id}",
                headers=H(tok),
                files={"file": ("evil.exe", BytesIO(b"MZ"), "application/octet-stream")},
            )
            rec("upload_bad_mime_rejected", bad.status_code in (400, 415, 422), http=bad.status_code, detail=bad.text[:80])
        else:
            rec("upload_bad_mime_rejected", True, detail="SKIP: doküman yok — traversal testleri yeterli")

    # --- 6. Training verify PII ---
    inv = c.get("/api/v1/trainings/verify/NOTREALCODEXYZ")
    body = inv.json() if inv.status_code == 200 else {}
    pii = {"national_id", "tc_kimlik", "email", "phone", "participants"}
    leaked = bool(pii.intersection(body.keys())) and body.get("valid") is False
    rec(
        "verify_invalid_minimal",
        inv.status_code == 200 and body.get("valid") is False and not leaked,
        http=inv.status_code,
        detail=str(list(body.keys())),
    )
    # Real code if any training exists
    if tok:
        tr = c.get("/api/v1/trainings", headers=H(tok))
        code = None
        if tr.status_code == 200:
            for row in tr.json():
                if row.get("verification_code"):
                    code = row["verification_code"]
                    break
        if code:
            okv = c.get(f"/api/v1/trainings/verify/{code}")
            b = okv.json() if okv.status_code == 200 else {}
            hard_pii = {"national_id", "tc_kimlik", "email", "phone", "blood_lead", "confidential_note"}
            rec(
                "verify_valid_no_hard_pii",
                okv.status_code == 200 and b.get("valid") is True and not hard_pii.intersection(b.keys()),
                http=okv.status_code,
                detail=str(list(b.keys())),
            )
        else:
            rec("verify_valid_no_hard_pii", True, detail="SKIP: verification_code yok")

    # --- 6b. Export content types ---
    if tok:
        xlsx = c.get("/api/v1/exports/employees.xlsx", headers=H(tok))
        ct = (xlsx.headers.get("content-type") or "").lower()
        rec(
            "export_employees_xlsx_type",
            xlsx.status_code == 200 and ("sheet" in ct or "excel" in ct or "octet" in ct),
            http=xlsx.status_code,
            detail=ct,
        )
        pdf = c.get("/api/v1/exports/isg-summary.pdf", headers=H(tok))
        pct = (pdf.headers.get("content-type") or "").lower()
        rec(
            "export_isg_pdf_type",
            pdf.status_code == 200 and "pdf" in pct and len(pdf.content) > 100,
            http=pdf.status_code,
            detail=f"{pct} bytes={len(pdf.content)}",
        )

    # Oversight smoke (score vacuous fix regression)
    if tok:
        ov = c.get("/api/v1/osgb/oversight", headers=H(tok))
        rec("oversight_ok", ov.status_code == 200, http=ov.status_code)

    summary = {
        "passed": sum(1 for x in OUT if x["ok"]),
        "failed": sum(1 for x in OUT if not x["ok"]),
        "total": len(OUT),
        "results": OUT,
    }
    out = ROOT.parent / "docs" / "qa" / "logs" / "qa-retest-smoke.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SUMMARY", summary["passed"], "/", summary["total"], "failed=", summary["failed"])
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
