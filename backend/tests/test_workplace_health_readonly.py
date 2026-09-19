"""Workplace medical reads are complete, scoped and strictly non-mutating."""
from datetime import date
import pytest
from test_health_consent_pro import client, _headers, _ids, _payload


def setup_records(client):
    import app.core.database as dbmod
    from app.core.security import get_password_hash
    from app.models.entities import Company, Employee, HealthRecord, User, UserRole
    cid, eid = _ids()
    physician = _headers(client, "onam-hekim@test.com", "HekimPass123!")
    created = client.post("/api/v1/health-records", headers=physician,
        json=_payload(cid, eid, confidential_note="Gizli hekim notu", audiometry_result="Normal sonuç"))
    assert created.status_code == 200, created.text
    with dbmod.SessionLocal() as db:
        company = db.get(Company, cid)
        for email, company_id in [("manager@test.com", cid), ("shared@kiosk.isgsuite.tr", cid)]:
            db.add(User(email=email, full_name="Test Yetkili", role=UserRole.COMPANY_ADMIN,
                company_id=company_id, osgb_id=company.osgb_id, is_active=True,
                hashed_password=get_password_hash("ManagerPass123!")))
        other = Company(name="Other Company", osgb_id=company.osgb_id, hazard_class="Tehlikeli", is_active=True)
        db.add(other); db.flush()
        emp = Employee(company_id=other.id, full_name="Other Employee", is_active=True)
        db.add(emp); db.flush()
        rec = HealthRecord(record_type="periodic_exam", company_id=other.id, employee_id=emp.id, examination_date=date.today(),
            created_by_id=created.json()["created_by_id"], confidential_note="Other secret")
        db.add(rec); db.commit()
        other_cid, other_rid = other.id, rec.id
    return cid, eid, created.json()["id"], other_cid, other_rid, _headers(client, "manager@test.com", "ManagerPass123!")


def test_workplace_reads_complete_records_and_documents(client):
    cid, eid, rid, other_cid, other_rid, headers = setup_records(client)
    r = client.get("/api/v1/health-records", headers=headers)
    assert r.status_code == 200, r.text
    assert [x["id"] for x in r.json()] == [rid]
    assert r.json()[0]["confidential_note"] == "Gizli hekim notu"
    assert r.json()[0]["audiometry_result"] == "Normal sonuç"
    for path in ["meta", "summary", "analysis", "export.txt", "export.xlsx", "analysis.txt", f"{rid}/form.html", f"{rid}/fitness.html"]:
        r = client.get(f"/api/v1/health-records/{path}?company_id={cid}", headers=headers)
        assert r.status_code == 200, (path, r.text)
    r = client.get(f"/api/v1/health-records/{rid}/form.html", headers=headers)
    assert "Gizli hekim notu" in r.text
    from app.core.config import settings
    from pathlib import Path
    import app.core.database as dbmod
    from app.models.entities import HealthRecord, HealthAccessLog
    root = Path(settings.upload_dir); root.mkdir(parents=True, exist_ok=True)
    (root / "medical.pdf").write_bytes(b"%PDF-1.4 test medical report")
    with dbmod.SessionLocal() as db:
        record = db.get(HealthRecord, rid)
        record.report_storage_path = "medical.pdf"
        record.report_file_name = "medical.pdf"
        record.report_content_type = "application/pdf"
        db.commit()
    r = client.get(f"/api/v1/health-records/{rid}/report", headers=headers)
    assert r.status_code == 200, r.text
    assert r.content == b"%PDF-1.4 test medical report"
    with dbmod.SessionLocal() as db:
        assert db.query(HealthAccessLog).filter_by(record_id=rid, action="report_download").count() == 1


def test_workplace_cannot_write_or_access_other_workplace(client):
    cid, eid, rid, other_cid, other_rid, headers = setup_records(client)
    for method, path, kwargs in [
        ("post", "", {"json": _payload(cid, eid)}),
        ("patch", f"/{rid}", {"json": {"summary": "Changed confidential summary"}}),
        ("delete", f"/{rid}?reason=delete-test", {}),
        ("post", f"/{rid}/report", {"files": {"file": ("x.pdf", b"%PDF-1.4", "application/pdf")}}),
    ]:
        r = getattr(client, method)("/api/v1/health-records" + path, headers=headers, **kwargs)
        assert r.status_code == 403, (path, r.text)
    for path in ["", "/summary", "/analysis", "/export.txt", "/export.xlsx", "/analysis.txt"]:
        r = client.get(f"/api/v1/health-records{path}?company_id={other_cid}", headers=headers)
        assert r.status_code == 403, (path, r.text)
    for path in ["report", "form.html", "fitness.html"]:
        r = client.get(f"/api/v1/health-records/{other_rid}/{path}", headers=headers)
        assert r.status_code in (403, 404), (path, r.text)
    r = client.get("/api/v1/health-records", headers=headers)
    assert r.status_code == 200
    assert r.json()[0]["summary"] == "Periyodik muayene bulgulari uygun"
    assert r.json()[0]["version"] == 1
    kiosk = _headers(client, "shared@kiosk.isgsuite.tr", "ManagerPass123!")
    assert client.get("/api/v1/health-records", headers=kiosk).status_code == 403
