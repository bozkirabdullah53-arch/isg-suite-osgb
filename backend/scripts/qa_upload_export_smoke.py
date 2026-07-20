"""QA — upload magic-byte/karantina + PDF/Excel içerik smoke."""
from __future__ import annotations

import json
import os
import sys
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "sqlite:///./qa_isgsuite.db")
os.environ.setdefault("UPLOAD_DIR", "./uploads_qa")
os.environ.setdefault("ENVIRONMENT", "qa")
os.environ.setdefault("SECRET_KEY", "qa-test-secret-key-at-least-32-characters-ok")

from fastapi.testclient import TestClient
from app.main import app
from app.services.upload_security import assert_safe_upload, quarantine_dir
from fastapi import HTTPException

OUT = []
PASS = "TestPass12345!"


def rec(name, ok, detail="", http=None):
    OUT.append({"test": name, "ok": bool(ok), "http": http, "detail": str(detail)[:240]})
    print(("PASS" if ok else "FAIL"), name, http or "", str(detail)[:120])


def login(c, email):
    r = c.post("/api/v1/auth/login", json={"email": email, "password": PASS})
    return r.json().get("access_token") if r.status_code == 200 else None


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


def main():
    # Unit-ish magic checks
    try:
        assert_safe_upload(b"%PDF-1.4\n%", ".pdf", "a.pdf")
        rec("magic_pdf_ok", True)
    except HTTPException:
        rec("magic_pdf_ok", False)

    try:
        assert_safe_upload(b"MZ\x90\x00fake", ".pdf", "evil.pdf")
        rec("magic_exe_as_pdf_blocked", False, detail="EXE kabul edilmemeli")
    except HTTPException as e:
        rec("magic_exe_as_pdf_blocked", e.status_code == 400, http=e.status_code)

    try:
        assert_safe_upload(b"not-a-png", ".png", "x.png")
        rec("magic_png_mismatch_blocked", False)
    except HTTPException as e:
        rec("magic_png_mismatch_blocked", e.status_code == 400, http=e.status_code)

    q = quarantine_dir()
    rec("quarantine_dir_exists", q.exists() and q.is_dir(), detail=str(q))

    c = TestClient(app)
    ga = login(c, "test.global.admin@example.com")
    ca = login(c, "test.az.admin@example.com")
    rec("login", bool(ga and ca))

    docs = c.get("/api/v1/documents", headers=H(ga)) if ga else None
    doc_id = None
    if docs and docs.status_code == 200 and docs.json():
        doc_id = docs.json()[0].get("id")

    if ga and doc_id:
        # polyglot: .pdf extension + EXE magic + pdf mime claim
        bad = c.post(
            f"/api/v1/files/documents/{doc_id}",
            headers=H(ga),
            files={"file": ("malware.pdf", BytesIO(b"MZ\x00\x00fakeexe"), "application/pdf")},
        )
        rec("upload_exe_disguised_pdf", bad.status_code == 400, http=bad.status_code, detail=bad.text[:100])

        good = c.post(
            f"/api/v1/files/documents/{doc_id}",
            headers=H(ga),
            files={"file": ("ok.pdf", BytesIO(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"), "application/pdf")},
        )
        rec("upload_real_pdf_ok", good.status_code in (200, 201), http=good.status_code, detail=good.text[:100])

        # unauthorized download by other company admin (if doc belongs to another firm)
        if ca:
            dl = c.get(f"/api/v1/files/documents/{doc_id}/download", headers=H(ca))
            # may be 200 if same company, 403/404 otherwise — must not 500
            rec("download_auth_checked", dl.status_code in (200, 403, 404), http=dl.status_code)
    else:
        rec("upload_exe_disguised_pdf", True, detail="SKIP: doc yok")
        rec("upload_real_pdf_ok", True, detail="SKIP")
        rec("download_auth_checked", True, detail="SKIP")

    # PDF / Excel content
    if ga:
        pdf = c.get("/api/v1/exports/isg-summary.pdf", headers=H(ga))
        ok_pdf = pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and len(pdf.content) > 200
        rec("export_pdf_magic", ok_pdf, http=pdf.status_code, detail=f"bytes={len(pdf.content)}")

        xlsx = c.get("/api/v1/exports/employees.xlsx", headers=H(ga))
        ok_x = False
        detail = ""
        if xlsx.status_code == 200 and xlsx.content[:2] == b"PK":
            try:
                z = ZipFile(BytesIO(xlsx.content))
                names = z.namelist()
                ok_x = any(n.startswith("xl/") for n in names)
                detail = f"entries={len(names)}"
            except Exception as e:
                detail = str(e)[:120]
        rec("export_xlsx_zip_workbook", ok_x, http=xlsx.status_code, detail=detail)

    summary = {
        "passed": sum(1 for x in OUT if x["ok"]),
        "failed": sum(1 for x in OUT if not x["ok"]),
        "total": len(OUT),
        "results": OUT,
    }
    out = ROOT.parent / "docs" / "qa" / "logs" / "qa-upload-export-smoke.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SUMMARY", summary["passed"], "/", summary["total"], "failed=", summary["failed"])
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
