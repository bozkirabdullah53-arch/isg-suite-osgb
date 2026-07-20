"""QA G1–G6 — EİSA platform + merkezi arşiv + OSGB Sil smoke (izole).

  $env:DATABASE_URL='sqlite:///./qa_isgsuite.db'
  $env:UPLOAD_DIR='./uploads_qa'
  $env:BACKUP_DIR='./backups_qa'
  $env:ENVIRONMENT='qa'
  python scripts/qa_eisa_archive_smoke.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
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
STAMP = time.strftime("%Y%m%d%H%M%S")
UID = uuid.uuid4().hex[:8]


def rec(name: str, ok: bool, detail: str = "", http: int | None = None) -> None:
    OUT.append({"test": name, "ok": bool(ok), "http": http, "detail": str(detail)[:300]})
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" HTTP {http}" if http is not None else "") + (f" — {detail[:140]}" if detail else ""))


def login(client: TestClient, email: str):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": PASS})
    if r.status_code != 200:
        return None, r
    return r.json().get("access_token"), r


def H(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def app_payload(name: str, auth_no: str, tax: str) -> dict:
    return {
        "name": name,
        "authorization_number": auth_no,
        "tax_number": tax,
        "responsible_manager": "TEST_ QA Mudur",
        "contact_email": f"qa.{UID}@example.com",
        "contact_phone": "05550001122",
        "address": "TEST_ QA Adres",
        "applicant_name": "TEST_ QA Basvuran",
        "applicant_email": f"qa.applicant.{UID}@example.com",
        "notes": "QA smoke",
        "contract_accepted": True,
        "personal_data_accepted": True,
    }


def main() -> int:
    client = TestClient(app, raise_server_exceptions=False)

    ga, gr = login(client, "test.global.admin@example.com")
    ca, cr = login(client, "test.az.admin@example.com")
    uzman, ur = login(client, "test.az.uzman@example.com")
    osgb2, o2r = login(client, "test.osgb2.admin@example.com")
    rec("login_roles", all([ga, ca, uzman]), http=gr.status_code)

    # --- G6: EİSA yalnız global_admin ---
    if uzman:
        r = client.get("/api/v1/eisa/dashboard", headers=H(uzman))
        rec("g6_uzman_eisa_denied", r.status_code in (401, 403), http=r.status_code)
    if ca:
        r = client.get("/api/v1/eisa/dashboard", headers=H(ca))
        rec("g6_ca_eisa_denied", r.status_code in (401, 403), http=r.status_code, detail=r.text[:80])
    if ga:
        dash = client.get("/api/v1/eisa/dashboard", headers=H(ga))
        rec("g6_ga_eisa_dashboard", dash.status_code == 200, http=dash.status_code)
        pkgs = client.get("/api/v1/eisa/packages", headers=H(ga))
        rec("g1_packages_list", pkgs.status_code == 200, http=pkgs.status_code)
        subs = client.get("/api/v1/eisa/subscriptions?filter=all", headers=H(ga))
        rec("g1_subscriptions_list", subs.status_code == 200, http=subs.status_code, detail=f"n={len(subs.json()) if subs.status_code==200 else 0}")
        users = client.get("/api/v1/eisa/osgb-users", headers=H(ga))
        rec("g1_osgb_users_list", users.status_code == 200, http=users.status_code)

    # --- G1: Başvuru akışı (red + sil + onay) ---
    reject_id = delete_id = approve_id = None
    if ga:
        for label, suffix in (("reject", "01"), ("delete", "02"), ("approve", "03")):
            body = app_payload(
                f"TEST_QA_OSGB_{label}_{UID}",
                f"QA-AUTH-{UID}-{suffix}",
                f"8888{UID[:4]}{suffix}",
            )
            # tax must be >= 8 chars
            body["tax_number"] = f"8888{UID}{suffix}"[:20]
            r = client.post("/api/v1/osgb-applications", json=body)
            ok = r.status_code in (200, 201)
            aid = (r.json() or {}).get("id") if ok else None
            rec(f"g1_submit_{label}", ok, http=r.status_code, detail=r.text[:100])
            if label == "reject":
                reject_id = aid
            elif label == "delete":
                delete_id = aid
            else:
                approve_id = aid

        pending = client.get("/api/v1/eisa/applications?status=pending", headers=H(ga))
        rec("g1_list_pending", pending.status_code == 200, http=pending.status_code)

        if reject_id:
            rj = client.post(
                f"/api/v1/eisa/applications/{reject_id}/reject",
                headers=H(ga),
                json={"reason": "TEST_ QA red gerekcesi"},
            )
            rec("g1_reject", rj.status_code == 200 and (rj.json() or {}).get("status") == "rejected", http=rj.status_code)

        if delete_id:
            dl = client.delete(f"/api/v1/eisa/applications/{delete_id}", headers=H(ga))
            rec("g1_delete_application", dl.status_code == 200, http=dl.status_code)
            gone = client.get("/api/v1/eisa/applications?status=all", headers=H(ga))
            still = False
            if gone.status_code == 200:
                still = any(a.get("id") == delete_id for a in gone.json())
            rec("g1_delete_not_listed", not still, http=gone.status_code)

        approved_osgb_id = None
        if approve_id:
            ap = client.post(f"/api/v1/eisa/applications/{approve_id}/approve", headers=H(ga))
            ok = ap.status_code == 200
            app_row = (ap.json() or {}).get("application") if ok else None
            approved_osgb_id = (app_row or {}).get("matched_osgb_id")
            # after approve, matched_osgb_id should be set; also check osgb-users
            rec("g1_approve", ok, http=ap.status_code, detail=str(ap.json())[:120] if ok else ap.text[:100])
            if ok:
                users2 = client.get("/api/v1/eisa/osgb-users", headers=H(ga))
                names = [u.get("name") for u in (users2.json() if users2.status_code == 200 else [])]
                rec("g1_approve_osgb_visible", any(f"TEST_QA_OSGB_approve_{UID}" in (n or "") for n in names), http=users2.status_code)
                if not approved_osgb_id and users2.status_code == 200:
                    hit = next((u for u in users2.json() if f"TEST_QA_OSGB_approve_{UID}" in (u.get("name") or "")), None)
                    approved_osgb_id = hit["id"] if hit else None

        # --- G2: OSGB kalıcı Sil ---
        if approved_osgb_id:
            before = client.get("/api/v1/eisa/osgb-users", headers=H(ga))
            rm = client.delete(f"/api/v1/eisa/osgb-users/{approved_osgb_id}", headers=H(ga))
            rec("g2_osgb_hard_delete", rm.status_code == 200, http=rm.status_code, detail=rm.text[:120])
            after = client.get("/api/v1/eisa/osgb-users", headers=H(ga))
            still = False
            if after.status_code == 200:
                still = any(u.get("id") == approved_osgb_id for u in after.json())
            rec("g2_osgb_gone_from_list", not still, http=after.status_code)
            # archives should still list something (backup before delete)
            arch = client.get("/api/v1/archives?kind=tenant_backup", headers=H(ga))
            rec(
                "g2_backup_before_delete_recorded",
                arch.status_code == 200 and len(arch.json() or []) >= 1,
                http=arch.status_code,
                detail=f"n={len(arch.json()) if arch.status_code==200 else 0}",
            )
        else:
            rec("g2_osgb_hard_delete", False, detail="approve_id/osgb yok — atlandi")

    # --- G4: Merkezi arşiv ---
    if ga:
        # pick seed TEST OSGB
        osgbs = client.get("/api/v1/osgb", headers=H(ga))
        oid = None
        if osgbs.status_code == 200 and osgbs.json():
            hit = next((o for o in osgbs.json() if str(o.get("name", "")).startswith("TEST_")), osgbs.json()[0])
            oid = hit.get("id")
        if oid:
            bk = client.post("/api/v1/archives/backup", headers=H(ga), json={"osgb_id": oid})
            rec("g4_ga_tenant_backup", bk.status_code == 200, http=bk.status_code, detail=bk.text[:100])
            aid = (bk.json() or {}).get("id") if bk.status_code == 200 else None
            lst = client.get("/api/v1/archives", headers=H(ga))
            rec("g4_ga_list_archives", lst.status_code == 200 and len(lst.json() or []) >= 1, http=lst.status_code)
            if aid:
                dl = client.get(f"/api/v1/archives/{aid}/download", headers=H(ga))
                rec("g4_ga_download", dl.status_code == 200 and len(dl.content) > 20, http=dl.status_code, detail=f"bytes={len(dl.content)}")
                if ca:
                    # CA may or may not access depending on scope
                    ca_dl = client.get(f"/api/v1/archives/{aid}/download", headers=H(ca))
                    rec(
                        "g4_ca_cross_archive_denied_or_own",
                        ca_dl.status_code in (200, 403),
                        http=ca_dl.status_code,
                        detail="403 beklenen (baska OSGB) veya 200 (aynı kapsam)",
                    )
        if uzman:
            z = client.get("/api/v1/archives", headers=H(uzman))
            rec("g4_uzman_archives_denied", z.status_code in (401, 403), http=z.status_code)

    if ca:
        # company admin backup of own scope
        ca_bk = client.post("/api/v1/archives/backup", headers=H(ca), json={})
        rec(
            "g4_ca_backup_own",
            ca_bk.status_code in (200, 400),
            http=ca_bk.status_code,
            detail=ca_bk.text[:120],
        )
        # 400 if no osgb/company scope is acceptable for some seed users; 200 preferred
        if ca_bk.status_code == 200:
            rec("g4_ca_backup_ok", True, http=200)
        else:
            rec("g4_ca_backup_ok", False, http=ca_bk.status_code, detail="CA yedek alamadi (kapsam/osgb_id?)")

    # --- G3: Abonelik listesinde Sil = aynı DELETE API (doğrudan) ---
    # Create another disposable OSGB via application for subscription-row delete path
    if ga:
        body = app_payload(f"TEST_QA_OSGB_subdel_{UID}", f"QA-AUTH-{UID}-99", f"7777{UID}99"[:20])
        body["tax_number"] = f"7777{UID}99"[:20]
        r = client.post("/api/v1/osgb-applications", json=body)
        aid = (r.json() or {}).get("id") if r.status_code in (200, 201) else None
        if aid:
            ap = client.post(f"/api/v1/eisa/applications/{aid}/approve", headers=H(ga))
            users = client.get("/api/v1/eisa/osgb-users", headers=H(ga))
            hit = next((u for u in (users.json() if users.status_code == 200 else []) if f"subdel_{UID}" in (u.get("name") or "")), None)
            sid = hit["id"] if hit else None
            if sid:
                # appears in subscriptions
                subs = client.get("/api/v1/eisa/subscriptions?filter=all", headers=H(ga))
                in_subs = any(s.get("osgb_id") == sid for s in (subs.json() if subs.status_code == 200 else []))
                rec("g3_osgb_in_subscriptions", in_subs, http=subs.status_code)
                rm = client.delete(f"/api/v1/eisa/osgb-users/{sid}", headers=H(ga))
                rec("g3_delete_via_subscription_path", rm.status_code == 200, http=rm.status_code)
                subs2 = client.get("/api/v1/eisa/subscriptions?filter=all", headers=H(ga))
                gone = not any(s.get("osgb_id") == sid for s in (subs2.json() if subs2.status_code == 200 else []))
                rec("g3_gone_from_subscriptions", gone, http=subs2.status_code)
            else:
                rec("g3_osgb_in_subscriptions", False, detail="approve sonrasi OSGB bulunamadi")
        else:
            rec("g3_osgb_in_subscriptions", False, detail="basvuru olusturulamadi")

    # --- G5: risk medya silme → arşiv (hafif) ---
    if ga and uzman:
        firms = client.get("/api/v1/companies", headers=H(ga))
        firm = next((f for f in (firms.json() if firms.status_code == 200 else []) if str(f.get("name", "")).startswith("TEST_")), None)
        cid = firm["id"] if firm else None
        if cid:
            client.post("/api/v1/risks/seed-library", headers=H(uzman))
            meta = client.get("/api/v1/risks/meta", headers=H(uzman))
            hazards = []
            if meta.status_code == 200:
                hazards = meta.json().get("hazards") or []
            hid = hazards[0]["id"] if hazards and isinstance(hazards[0], dict) else 1
            rb = client.post(
                "/api/v1/risks",
                headers=H(uzman),
                json={
                    "company_id": cid,
                    "department_name": "TEST_ QA",
                    "hazard_id": hid,
                    "activity": "TEST_ arsiv risk",
                    "risk_definition": "TEST_ arsiv risk tanimi yeterince uzun",
                    "probability": 2,
                    "severity": 2,
                    "status": "Açık",
                },
            )
            rid = (rb.json() or {}).get("id") if rb.status_code in (200, 201) else None
            rec("g5_risk_create", bool(rid), http=rb.status_code)
            if rid:
                # Risk medya yalnızca jpg/png/webp/gif kabul eder
                png_1x1 = (
                    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
                    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
                    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
                )
                files = {"file": ("qa.png", png_1x1, "image/png")}
                up = client.post(f"/api/v1/risks/{rid}/media", headers=H(uzman), files=files)
                mid = None
                if up.status_code in (200, 201):
                    data = up.json()
                    if isinstance(data, dict):
                        mid = data.get("id") or (data.get("media") or {}).get("id")
                        if not mid and isinstance(data.get("media_files"), list) and data["media_files"]:
                            mid = data["media_files"][-1].get("id")
                rec("g5_risk_media_upload", up.status_code in (200, 201), http=up.status_code, detail=up.text[:100])
                if mid:
                    before_n = len(client.get("/api/v1/archives?kind=deleted_file", headers=H(ga)).json() or [])
                    rm = client.delete(f"/api/v1/risks/{rid}/media/{mid}", headers=H(uzman))
                    after = client.get("/api/v1/archives?kind=deleted_file", headers=H(ga))
                    after_n = len(after.json() or []) if after.status_code == 200 else 0
                    rec("g5_media_delete", rm.status_code == 200, http=rm.status_code)
                    rec(
                        "g5_deleted_file_archived",
                        after_n > before_n,
                        http=after.status_code,
                        detail=f"{before_n}->{after_n}",
                    )
                else:
                    rec("g5_media_delete", False, detail="media id yok — silme atlandi")
                    rec("g5_deleted_file_archived", False, detail="media id yok")

    # --- O2: çapraz-OSGB arşiv IDOR ---
    if ga and osgb2:
        osgbs = client.get("/api/v1/osgb", headers=H(ga))
        oid1 = None
        if osgbs.status_code == 200:
            hit = next((o for o in osgbs.json() if "Denetim" in str(o.get("name", "")) or str(o.get("name", "")).startswith("TEST_OSGB D")), None)
            if not hit:
                hit = next((o for o in osgbs.json() if str(o.get("name", "")).startswith("TEST_") and "Rakip" not in str(o.get("name", ""))), None)
            oid1 = hit["id"] if hit else None
        if oid1:
            bk = client.post("/api/v1/archives/backup", headers=H(ga), json={"osgb_id": oid1})
            aid = (bk.json() or {}).get("id") if bk.status_code == 200 else None
            rec("o2_backup_osgb1", bool(aid), http=bk.status_code)
            if aid:
                denied = client.get(f"/api/v1/archives/{aid}/download", headers=H(osgb2))
                rec(
                    "o2_osgb2_cannot_download_osgb1_archive",
                    denied.status_code == 403,
                    http=denied.status_code,
                    detail=denied.text[:120],
                )
                # osgb2 own list should not include osgb1-only rows when filtered by access
                lst2 = client.get("/api/v1/archives", headers=H(osgb2))
                leak = False
                if lst2.status_code == 200:
                    leak = any(a.get("id") == aid for a in lst2.json())
                rec("o2_osgb2_list_hides_osgb1_archive", not leak, http=lst2.status_code)
        else:
            rec("o2_backup_osgb1", False, detail="TEST OSGB1 bulunamadi")
    elif not osgb2:
        rec("o2_osgb2_cannot_download_osgb1_archive", False, detail="osgb2 login yok — atlandi")

    # Seed'de profesyonel e-postası kullanıcıyla hizalı (seed_test_data); yine de idempotent hizala
    try:
        from sqlalchemy import select as sa_select

        from app.core.database import SessionLocal
        from app.models.entities import IsgProfessional, ProfessionalType, User as UEnt

        with SessionLocal() as db:
            for email, ptype in (
                ("test.az.uzman@example.com", ProfessionalType.SAFETY_SPECIALIST),
                ("test.az.hekim@example.com", ProfessionalType.WORKPLACE_PHYSICIAN),
                ("test.az.dsp@example.com", ProfessionalType.OTHER_HEALTH_PERSONNEL),
            ):
                urow = db.scalar(sa_select(UEnt).where(UEnt.email == email))
                if not urow or not urow.osgb_id:
                    continue
                prow = db.scalar(
                    sa_select(IsgProfessional).where(
                        IsgProfessional.osgb_id == urow.osgb_id,
                        IsgProfessional.professional_type == ptype,
                        IsgProfessional.is_active.is_(True),
                    ).limit(1)
                )
                if prow and ((prow.email or "").casefold() != email or prow.full_name != urow.full_name):
                    prow.email = email
                    prow.full_name = urow.full_name
            db.commit()
        rec("o3_fixture_align_professional_email", True, detail="idempotent")
    except Exception as exc:
        rec("o3_fixture_align_professional_email", False, detail=str(exc)[:120])

    # --- O3: diğer silme→arşiv kancaları ---
    PNG = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    PDF = b"%PDF-1.4\n1 0 obj<< /Type /Catalog >>endobj\ntrailer<<>>\n%%EOF\n"

    def deleted_count() -> int:
        if not ga:
            return 0
        r = client.get("/api/v1/archives?kind=deleted_file", headers=H(ga))
        return len(r.json() or []) if r.status_code == 200 else 0

    if ga and uzman:
        firms = client.get("/api/v1/companies", headers=H(ga))
        firm = next((f for f in (firms.json() if firms.status_code == 200 else []) if str(f.get("name", "")).startswith("TEST_ Firma Az")), None)
        cid = firm["id"] if firm else None
        oid = None
        os = client.get("/api/v1/osgb", headers=H(ga))
        if os.status_code == 200 and os.json():
            oid = next((o["id"] for o in os.json() if "Rakip" not in o.get("name", "")), os.json()[0]["id"])

        # O3a document deactivate
        if cid:
            doc = client.post(
                "/api/v1/documents",
                headers=H(uzman),
                json={
                    "company_id": cid,
                    "category": "general",
                    "title": f"TEST_ QA Doc {UID}",
                    "file_name": "qa.pdf",
                    "description": "QA",
                    "version": "1.0",
                },
            )
            did = (doc.json() or {}).get("id") if doc.status_code in (200, 201) else None
            rec("o3_document_create", bool(did), http=doc.status_code)
            if did:
                up = client.post(
                    f"/api/v1/files/documents/{did}",
                    headers=H(uzman),
                    files={"file": ("qa.pdf", PDF, "application/pdf")},
                )
                rec("o3_document_file_upload", up.status_code == 200, http=up.status_code, detail=up.text[:100])
                before = deleted_count()
                de = client.patch(f"/api/v1/documents/{did}/deactivate", headers=H(uzman))
                after = deleted_count()
                rec("o3_document_deactivate", de.status_code == 200, http=de.status_code)
                rec("o3_document_archived", after > before, detail=f"{before}->{after}")

        # O3b visit notebook replace
        if cid and oid and uzman:
            from datetime import date

            vis = client.post(
                "/api/v1/operations/visits",
                headers=H(uzman),
                json={
                    "osgb_id": oid,
                    "company_id": cid,
                    "visit_date": date.today().isoformat(),
                    "subject": f"TEST_ QA Visit {UID}",
                    "duration_minutes": 30,
                },
            )
            vid = (vis.json() or {}).get("id") if vis.status_code in (200, 201) else None
            rec("o3_visit_create", bool(vid), http=vis.status_code, detail=vis.text[:100])
            if vid:
                n1 = client.post(
                    f"/api/v1/operations/visits/{vid}/notebook",
                    headers=H(uzman),
                    files={"file": ("defter1.pdf", PDF, "application/pdf")},
                )
                rec("o3_notebook_upload1", n1.status_code == 200, http=n1.status_code, detail=n1.text[:80])
                before = deleted_count()
                n2 = client.post(
                    f"/api/v1/operations/visits/{vid}/notebook",
                    headers=H(uzman),
                    files={"file": ("defter2.pdf", PDF, "application/pdf")},
                )
                after = deleted_count()
                rec("o3_notebook_replace", n2.status_code == 200, http=n2.status_code, detail=n2.text[:80])
                rec("o3_notebook_archived_on_replace", after > before, detail=f"{before}->{after}")

        # O3c assignment contract replace
        if ga and oid:
            asg = client.get(f"/api/v1/osgb/assignments?osgb_id={oid}", headers=H(ga))
            aid = None
            if asg.status_code == 200 and asg.json():
                aid = asg.json()[0].get("id")
            rec("o3_assignment_picked", bool(aid), http=getattr(asg, "status_code", None))
            if aid:
                c1 = client.post(
                    f"/api/v1/osgb/assignments/{aid}/contract",
                    headers=H(ga),
                    files={"file": ("soz1.pdf", PDF, "application/pdf")},
                )
                rec("o3_contract_upload1", c1.status_code == 200, http=c1.status_code, detail=c1.text[:80])
                before = deleted_count()
                c2 = client.post(
                    f"/api/v1/osgb/assignments/{aid}/contract",
                    headers=H(ga),
                    files={"file": ("soz2.pdf", PDF, "application/pdf")},
                )
                after = deleted_count()
                rec("o3_contract_replace", c2.status_code == 200, http=c2.status_code)
                rec("o3_contract_archived_on_replace", after > before, detail=f"{before}->{after}")

    # O3d health report replace
    hekim_tok, _ = login(client, "test.az.hekim@example.com")
    if hekim_tok and ga:
        firms = client.get("/api/v1/companies", headers=H(ga))
        firm = next((f for f in (firms.json() if firms.status_code == 200 else []) if "Az Tehlikeli" in str(f.get("name", ""))), None)
        cid = firm["id"] if firm else None
        emps = client.get(f"/api/v1/employees?company_id={cid}", headers=H(hekim_tok)) if cid else None
        eid = None
        if emps and emps.status_code == 200 and emps.json():
            eid = emps.json()[0].get("id")
        if cid and eid:
            from datetime import date

            hr = client.post(
                "/api/v1/health-records",
                headers=H(hekim_tok),
                json={
                    "company_id": cid,
                    "employee_id": eid,
                    "record_type": "periodic_exam",
                    "examination_date": date.today().isoformat(),
                    "fitness_status": "fit",
                    "summary": "TEST_ QA saglik",
                },
            )
            hid = (hr.json() or {}).get("id") if hr.status_code in (200, 201) else None
            rec("o3_health_create", bool(hid), http=hr.status_code, detail=hr.text[:100])
            if hid:
                h1 = client.post(
                    f"/api/v1/health-records/{hid}/report",
                    headers=H(hekim_tok),
                    files={"file": ("rapor1.pdf", PDF, "application/pdf")},
                )
                rec("o3_health_report_upload1", h1.status_code == 200, http=h1.status_code, detail=h1.text[:80])
                before = deleted_count()
                h2 = client.post(
                    f"/api/v1/health-records/{hid}/report",
                    headers=H(hekim_tok),
                    files={"file": ("rapor2.pdf", PDF, "application/pdf")},
                )
                after = deleted_count()
                rec("o3_health_report_replace", h2.status_code == 200, http=h2.status_code)
                rec("o3_health_report_archived_on_replace", after > before, detail=f"{before}->{after}")
        else:
            rec("o3_health_create", False, detail="employee/company yok")

    # health flags
    health = client.get("/health")
    hj = health.json() if health.status_code == 200 else {}
    rec(
        "health_flags_eisa_archive",
        hj.get("eisa_platform") and hj.get("central_archive"),
        http=health.status_code,
        detail=f"v={hj.get('version')} eisa={hj.get('eisa_platform')} arch={hj.get('central_archive')}",
    )

    passed = sum(1 for x in OUT if x["ok"])
    failed = sum(1 for x in OUT if not x["ok"])
    summary = {"passed": passed, "failed": failed, "total": len(OUT), "results": OUT, "stamp": STAMP}
    out = REPO / "docs" / "qa" / "logs" / "qa-eisa-archive-smoke.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"SUMMARY {passed} / {len(OUT)} failed= {failed}")
    print("Wrote", out)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
