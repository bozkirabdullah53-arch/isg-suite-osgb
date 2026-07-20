"""QA comprehensive API smoke — Phase 3–5. Isolated DB only.

  $env:DATABASE_URL='sqlite:///./qa_isgsuite.db'
  $env:UPLOAD_DIR='./uploads_qa'
  $env:ENVIRONMENT='qa'
  python scripts/qa_api_smoke.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///./qa_isgsuite.db")
os.environ.setdefault("UPLOAD_DIR", "./uploads_qa")
os.environ.setdefault("BACKUP_DIR", "./backups_qa")
os.environ.setdefault("ENVIRONMENT", "qa")
os.environ.setdefault("SECRET_KEY", "qa-test-secret-key-at-least-32-characters-ok")

from fastapi.testclient import TestClient

from app.main import app

PASS = "TestPass12345!"
OUT: list[dict] = []


def rec(name: str, ok: bool, detail: str = "", http: int | None = None):
    OUT.append({"test": name, "ok": ok, "http": http, "detail": detail[:300]})
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" HTTP {http}" if http is not None else "") + (f" — {detail[:120]}" if detail else ""))


def login(client: TestClient, email: str, password: str = PASS):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        return None, r
    return r.json().get("access_token"), r


def H(token: str):
    return {"Authorization": f"Bearer {token}"}


def main():
    client = TestClient(app)

    # --- Auth ---
    tok, r = login(client, "test.global.admin@example.com")
    rec("login_global_admin", bool(tok), http=r.status_code)
    bad = client.post("/api/v1/auth/login", json={"email": "test.global.admin@example.com", "password": "wrong"})
    rec("login_wrong_password", bad.status_code in (401, 400, 422), http=bad.status_code)
    me = client.get("/api/v1/auth/me", headers=H(tok) if tok else {})
    rec("auth_me", me.status_code == 200 and me.json().get("role") == "global_admin", http=me.status_code)
    rec("companies_no_token", client.get("/api/v1/companies").status_code == 401, http=401)
    rec("bad_jwt", client.get("/api/v1/companies", headers=H("not.a.jwt")).status_code == 401)

    health = client.get("/health")
    ver = health.json().get("version") if health.status_code == 200 else None
    rec("health_root", health.status_code == 200, http=health.status_code, detail=f"version={ver}")

    # --- Companies ---
    firms = client.get("/api/v1/companies", headers=H(tok)) if tok else None
    firm_list = firms.json() if firms and firms.status_code == 200 else []
    rec("companies_list_ga", firms is not None and firms.status_code == 200 and len(firm_list) >= 1, http=getattr(firms, "status_code", None), detail=f"n={len(firm_list)}")
    test_firms = [c for c in firm_list if str(c.get("name", "")).startswith("TEST_")]
    firm_ids = [c["id"] for c in test_firms]
    cid = firm_ids[0] if firm_ids else None
    cid2 = firm_ids[1] if len(firm_ids) > 1 else None

    br = client.get("/api/v1/branches", headers=H(tok)) if tok else None
    rec("branches_list_ga", br is not None and br.status_code == 200, http=getattr(br, "status_code", None))

    emp = client.get("/api/v1/employees", headers=H(tok)) if tok else None
    rec("employees_list_ga", emp is not None and emp.status_code == 200, http=getattr(emp, "status_code", None), detail=f"n={len(emp.json()) if emp and emp.status_code==200 else 0}")

    # --- OSGB ---
    if tok:
        pros = client.get("/api/v1/osgb/professionals", headers=H(tok))
        # GA without osgb_id may auto-pick first
        osgb = client.get("/api/v1/osgb", headers=H(tok))
        oid = osgb.json()[0]["id"] if osgb.status_code == 200 and osgb.json() else None
        if oid:
            pros = client.get(f"/api/v1/osgb/professionals?osgb_id={oid}", headers=H(tok))
        rec("professionals_list", pros.status_code == 200, http=pros.status_code, detail=f"n={len(pros.json()) if pros.status_code==200 else 0}")
        asg = client.get("/api/v1/osgb/assignments", headers=H(tok))
        rec("assignments_list", asg.status_code == 200, http=asg.status_code, detail=f"n={len(asg.json()) if asg.status_code==200 else 0}")
        pack = client.get(f"/api/v1/osgb/csgb-audit-pack" + (f"?osgb_id={oid}" if oid else ""), headers=H(tok))
        rec("csgb_audit_pack", pack.status_code == 200 and "summary" in (pack.json() or {}), http=pack.status_code)
        overs = client.get("/api/v1/osgb/oversight" + (f"?osgb_id={oid}" if oid else ""), headers=H(tok))
        rec("osgb_oversight", overs.status_code == 200, http=overs.status_code)

    # --- Role logins ---
    uzman_tok, ur = login(client, "test.az.uzman@example.com")
    rec("login_specialist", bool(uzman_tok), http=ur.status_code)
    hekim_tok, hr = login(client, "test.az.hekim@example.com")
    rec("login_physician", bool(hekim_tok), http=hr.status_code)
    ca_tok, cr = login(client, "test.az.admin@example.com")
    rec("login_company_admin", bool(ca_tok), http=cr.status_code)

    # --- Annual plan ---
    if uzman_tok and cid:
        gen = client.post("/api/v1/annual-plans/generate", headers=H(uzman_tok), json={"company_id": cid, "year": 2026})
        rec("annual_plan_generate", gen.status_code == 200, http=gen.status_code, detail=str(gen.json())[:160] if gen.status_code == 200 else gen.text[:120])
        gen2 = client.post("/api/v1/annual-plans/generate", headers=H(uzman_tok), json={"company_id": cid, "year": 2026})
        rec("annual_plan_idempotent", gen2.status_code == 200 and gen2.json().get("created", -1) == 0, http=gen2.status_code)

    # --- Health privacy ---
    if uzman_tok:
        h_uz = client.get("/api/v1/health-records", headers=H(uzman_tok))
        rec("health_specialist_denied", h_uz.status_code in (403, 401), http=h_uz.status_code, detail=h_uz.text[:100])
    if hekim_tok:
        h_ok = client.get("/api/v1/health-records", headers=H(hekim_tok))
        rec("health_physician_ok", h_ok.status_code == 200, http=h_ok.status_code)
    if ca_tok:
        h_ca = client.get("/api/v1/health-records", headers=H(ca_tok))
        rec(
            "health_company_admin_blocked_or_empty",
            h_ca.status_code in (403, 401) or (h_ca.status_code == 200 and len(h_ca.json()) == 0),
            http=h_ca.status_code,
            detail="CA sağlık PII görmemeli",
        )

    # --- IDOR employees ---
    if ca_tok and cid2:
        steal = client.get(f"/api/v1/employees?company_id={cid2}", headers=H(ca_tok))
        ok = steal.status_code in (403, 422) or (steal.status_code == 200 and len(steal.json()) == 0)
        rec("idor_ca_employees_other_firm", ok, http=steal.status_code, detail=steal.text[:100])
    if uzman_tok and cid2:
        steal2 = client.get(f"/api/v1/employees?company_id={cid2}", headers=H(uzman_tok))
        ok2 = steal2.status_code in (403, 422) or (steal2.status_code == 200 and len(steal2.json()) == 0)
        rec("idor_uzman_employees_other_firm", ok2, http=steal2.status_code)

    # --- Risk / incidents / PPE / training ---
    for role, tkn, label in (("uzman", uzman_tok, "specialist"), ("ga", tok, "ga")):
        if not tkn:
            continue
        rm = client.get("/api/v1/risks/meta", headers=H(tkn))
        rec(f"risks_meta_{label}", rm.status_code in (200, 403), http=rm.status_code)
        rl = client.get("/api/v1/risks", headers=H(tkn))
        rec(f"risks_list_{label}", rl.status_code in (200, 403), http=rl.status_code, detail=f"n={len(rl.json()) if rl.status_code==200 else '-'}")

    if uzman_tok:
        # seed library once
        seed = client.post("/api/v1/risks/seed-library", headers=H(uzman_tok))
        rec("risks_seed_library", seed.status_code in (200, 201, 409, 400), http=seed.status_code)

        inc = client.get("/api/v1/incidents", headers=H(uzman_tok))
        rec("incidents_list", inc.status_code in (200, 403), http=inc.status_code)

        ppe = client.get("/api/v1/ppe", headers=H(uzman_tok))
        if ppe.status_code == 404:
            ppe = client.get("/api/v1/ppe/assignments", headers=H(uzman_tok))
        rec("ppe_list", ppe.status_code in (200, 403, 404), http=ppe.status_code)

        tr = client.get("/api/v1/trainings", headers=H(uzman_tok))
        rec("trainings_list", tr.status_code == 200, http=tr.status_code, detail=f"n={len(tr.json()) if tr.status_code==200 else 0}")
        sec = client.get("/api/v1/trainings/sectors", headers=H(uzman_tok))
        rec("trainings_sectors", sec.status_code == 200, http=sec.status_code)

    tv = client.get("/api/v1/trainings/verify/NOTREALCODEXYZ")
    body = tv.json() if tv.status_code == 200 else {}
    leak = any(k in body for k in ("national_id", "tc", "email", "phone", "full_name")) and body.get("valid") is False
    rec(
        "training_verify_invalid_no_pii",
        tv.status_code == 200 and body.get("valid") is False and not leak,
        http=tv.status_code,
        detail=str(body)[:160],
    )

    # --- Docs / notifications / ops / reports / exports ---
    if tok:
        docs = client.get("/api/v1/documents", headers=H(tok))
        rec("documents_list", docs.status_code in (200, 403), http=docs.status_code)
        nref = client.post("/api/v1/notifications/refresh", headers=H(tok))
        rec("notifications_refresh_ga", nref.status_code == 200, http=nref.status_code, detail=str(nref.json())[:120] if nref.status_code == 200 else nref.text[:80])
        nlist = client.get("/api/v1/notifications", headers=H(tok))
        rec("notifications_list", nlist.status_code == 200, http=nlist.status_code)

        if oid:
            leads = client.get(f"/api/v1/operations/leads?osgb_id={oid}", headers=H(tok))
            rec("crm_leads", leads.status_code == 200, http=leads.status_code)
            fin = client.get(f"/api/v1/operations/finance?osgb_id={oid}", headers=H(tok))
            rec("finance_list", fin.status_code == 200, http=fin.status_code)
            vis = client.get(f"/api/v1/operations/visits?osgb_id={oid}", headers=H(tok))
            rec("visits_list", vis.status_code == 200, http=vis.status_code)

        rep = client.get("/api/v1/reports/summary", headers=H(tok))
        rec("reports_summary", rep.status_code == 200, http=rep.status_code)

        ex = client.get("/api/v1/exports/employees.xlsx", headers=H(tok))
        rec("export_employees_xlsx", ex.status_code in (200, 400, 404), http=ex.status_code)
        pdf = client.get("/api/v1/exports/isg-summary.pdf", headers=H(tok))
        rec("export_isg_pdf", pdf.status_code in (200, 400, 404), http=pdf.status_code)

    # --- Controlled path traversal ---
    if tok:
        for path in ("/api/v1/files/../../etc/passwd", "/api/v1/files/%2e%2e/%2e%2e/etc/passwd"):
            pt = client.get(path, headers=H(tok))
            rec(
                f"files_path_traversal_{path[-20:]}",
                pt.status_code in (400, 401, 403, 404, 422),
                http=pt.status_code,
            )

    # --- Rate limit middleware presence (code check) ---
    from app.main import app as _app
    names = [type(m).__name__ for m in getattr(_app, "user_middleware", [])]
    # Starlette stores differently
    mw = []
    try:
        mw = [m.cls.__name__ if hasattr(m, "cls") else type(m).__name__ for m in _app.user_middleware]
    except Exception:
        mw = []
    has_rl = any("RateLimit" in n or "rate" in n.lower() for n in mw)
    rec(
        "rate_limit_middleware_registered",
        has_rl,
        detail=f"middleware={mw}; EXPECT FAIL if SimpleRateLimit not added — known P0",
    )

    passed = sum(1 for x in OUT if x["ok"])
    failed = sum(1 for x in OUT if not x["ok"])
    summary = {
        "passed": passed,
        "failed": failed,
        "total": len(OUT),
        "results": OUT,
        "note": "Isolated QA only; Phase 8 fixes not applied",
    }
    out_path = ROOT.parent / "docs" / "qa" / "logs" / "qa-api-smoke.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT.parent / "docs" / "qa" / "logs" / "qa-api-smoke.txt").write_text(
        "\n".join(f"{'PASS' if x['ok'] else 'FAIL'} {x['test']} http={x.get('http')} {x.get('detail','')}" for x in OUT)
        + f"\nSUMMARY {passed}/{len(OUT)}\n",
        encoding="utf-8",
    )
    print(f"\nSUMMARY passed={passed} failed={failed} total={len(OUT)}")
    print(f"Wrote {out_path}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
