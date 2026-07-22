"""0.9.135 — Yıllık plan değerlendirme smoke tests."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "annual_eval.db"
    url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long!!")
    monkeypatch.setattr("app.api.auth.role_requires_mfa", lambda _role: False)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import app.core.database as dbmod
    import app.models.entities as ent
    from app.core.config import settings

    settings.database_url = url
    settings.secret_key = "test-secret-key-at-least-32-chars-long!!"
    settings.environment = "development"
    settings.upload_dir = str(tmp_path / "uploads")

    engine = create_engine(url, connect_args={"check_same_thread": False})
    dbmod.engine = engine
    dbmod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    ent.Base.metadata.create_all(bind=engine)

    from app.main import app

    return TestClient(app)


def _seed(client: TestClient) -> dict:
    from datetime import date
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import (
        AnnualPlanItem,
        AnnualPlanStatus,
        Company,
        OsgbOrganization,
        User,
        UserRole,
    )

    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="Eval OSGB",
            authorization_number="YETKI-EVAL-1",
            tax_number="1122334455",
            responsible_manager="Eval Yonetici",
            email="eval-osgb@test.com",
            phone="02120001122",
            address="Bursa",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        company = Company(name="Eval Firma", osgb_id=osgb.id, is_active=True)
        db.add(company)
        db.flush()
        user = User(
            email="eval-uzman@test.com",
            full_name="Eval Uzman",
            hashed_password=get_password_hash("TestPass123!"),
            role=UserRole.SAFETY_SPECIALIST,
            osgb_id=osgb.id,
            company_id=company.id,
            is_active=True,
        )
        db.add(user)
        db.flush()
        plan = AnnualPlanItem(
            company_id=company.id,
            year=2026,
            month=3,
            category="tatbikat",
            activity="Yangin tatbikati",
            description="Tahliye senaryosu",
            responsible_name="ISG Uzmani",
            target_date=date(2026, 3, 15),
            status=AnnualPlanStatus.PLANNED,
            created_by_id=user.id,
        )
        db.add(plan)
        db.commit()
        company_id = company.id
        plan_id = plan.id

    r = client.post("/api/v1/auth/login", json={"email": "eval-uzman@test.com", "password": "TestPass123!"})
    assert r.status_code == 200, r.text
    return {"token": r.json()["access_token"], "company_id": company_id, "plan_id": plan_id}


def test_health_annual_eval(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "0.9.142"
    assert body["annual_eval_report"] == "annual-eval-v7"


def test_start_sync_and_update_does_not_mutate_plan(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}

    start = client.post(
        "/api/v1/annual-evals/start",
        headers=headers,
        json={"company_id": seed["company_id"], "year": 2026},
    )
    assert start.status_code == 200, start.text
    ov = start.json()
    assert ov["plan_item_count"] == 1
    assert ov["evaluation_id"]

    items = client.get(
        f"/api/v1/annual-evals/items?company_id={seed['company_id']}&year=2026",
        headers=headers,
    )
    assert items.status_code == 200
    rows = items.json()
    assert len(rows) == 1
    assert rows[0]["plan"]["activity"] == "Yangin tatbikati"
    eval_item_id = rows[0]["id"]

    upd = client.put(
        f"/api/v1/annual-evals/items/{eval_item_id}",
        headers=headers,
        json={
            "outcome_status": "tamam",
            "actual_end": "2026-03-20",
            "result_text": "Tatbikat basariyla tamamlandi",
        },
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["delay_days"] == 5

    # Plan kaydı değişmemeli
    from app.core.database import SessionLocal
    from app.models.entities import AnnualPlanItem, AnnualPlanStatus

    with SessionLocal() as db:
        plan = db.get(AnnualPlanItem, seed["plan_id"])
        assert plan.activity == "Yangin tatbikati"
        assert plan.status == AnnualPlanStatus.PLANNED
        assert plan.completion_date is None


def test_unplanned_does_not_inflate_rate(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}
    start = client.post(
        "/api/v1/annual-evals/start",
        headers=headers,
        json={"company_id": seed["company_id"], "year": 2026},
    ).json()
    eid = start["evaluation_id"]
    client.post(
        f"/api/v1/annual-evals/{eid}/unplanned",
        headers=headers,
        json={"activity": "Plansiz egitim", "done_date": "2026-04-01", "suggest_next_year": True},
    )
    ov = client.get(
        f"/api/v1/annual-evals/overview?company_id={seed['company_id']}&year=2026",
        headers=headers,
    ).json()
    assert ov["kpis"]["unplanned"] == 1
    assert ov["kpis"]["planned_total"] == 1


def test_locked_after_employer_approve(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}
    eid = client.post(
        "/api/v1/annual-evals/start",
        headers=headers,
        json={"company_id": seed["company_id"], "year": 2026},
    ).json()["evaluation_id"]
    client.post(f"/api/v1/annual-evals/{eid}/workflow/approve-employer", headers=headers)
    items = client.get(
        f"/api/v1/annual-evals/items?company_id={seed['company_id']}&year=2026",
        headers=headers,
    ).json()
    bad = client.put(
        f"/api/v1/annual-evals/items/{items[0]['id']}",
        headers=headers,
        json={"outcome_status": "tamam", "actual_end": "2026-03-20", "result_text": "x"},
    )
    assert bad.status_code == 409


def test_transfer_next_year_creates_new_plan_only(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}
    client.post(
        "/api/v1/annual-evals/start",
        headers=headers,
        json={"company_id": seed["company_id"], "year": 2026},
    )
    items = client.get(
        f"/api/v1/annual-evals/items?company_id={seed['company_id']}&year=2026",
        headers=headers,
    ).json()
    client.put(
        f"/api/v1/annual-evals/items/{items[0]['id']}",
        headers=headers,
        json={
            "outcome_status": "gerceklesmedi",
            "deviation_reason": "Butce yok",
            "next_year_suggestion": "2027 planina al",
        },
    )
    tr = client.post(
        "/api/v1/annual-evals/transfer-to-next-year",
        headers=headers,
        json={
            "company_id": seed["company_id"],
            "from_year": 2026,
            "items": [{"activity": "Yangin tatbikati", "month": 3, "category": "tatbikat"}],
        },
    )
    assert tr.status_code == 200, tr.text
    assert tr.json()["created_count"] == 1
    assert tr.json()["to_year"] == 2027

    from app.core.database import SessionLocal
    from app.models.entities import AnnualPlanItem
    from sqlalchemy import select

    with SessionLocal() as db:
        old = db.get(AnnualPlanItem, seed["plan_id"])
        assert old.year == 2026
        assert old.activity == "Yangin tatbikati"
        news = list(
            db.scalars(
                select(AnnualPlanItem).where(
                    AnnualPlanItem.company_id == seed["company_id"],
                    AnnualPlanItem.year == 2027,
                )
            ).all()
        )
        assert len(news) == 1


def test_related_evidence_and_create_revision(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}
    eid = client.post(
        "/api/v1/annual-evals/start",
        headers=headers,
        json={"company_id": seed["company_id"], "year": 2026},
    ).json()["evaluation_id"]
    rel = client.get(
        f"/api/v1/annual-evals/related-evidence?company_id={seed['company_id']}&year=2026",
        headers=headers,
    )
    assert rel.status_code == 200
    body = rel.json()
    assert "trainings" in body and "health_summary" in body
    assert "Tanı" in body["health_summary"]["note"] or "toplulaştırılmış" in body["health_summary"]["note"]

    client.post(f"/api/v1/annual-evals/{eid}/workflow/approve-employer", headers=headers)
    rev = client.post(f"/api/v1/annual-evals/{eid}/workflow/create-revision", headers=headers)
    assert rev.status_code == 200
    assert rev.json()["report_status"] == "revizyon"
    items = client.get(
        f"/api/v1/annual-evals/items?company_id={seed['company_id']}&year=2026",
        headers=headers,
    ).json()
    ok = client.put(
        f"/api/v1/annual-evals/items/{items[0]['id']}",
        headers=headers,
        json={"outcome_status": "devam", "completion_pct": 40, "result_text": "devam"},
    )
    assert ok.status_code == 200


def test_analytics_and_bulk_note(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}
    client.post(
        "/api/v1/annual-evals/start",
        headers=headers,
        json={"company_id": seed["company_id"], "year": 2026},
    )
    an = client.get(
        f"/api/v1/annual-evals/analytics?company_id={seed['company_id']}&year=2026&period=quarter",
        headers=headers,
    )
    assert an.status_code == 200
    assert len(an.json()["buckets"]) == 4
    items = client.get(
        f"/api/v1/annual-evals/items?company_id={seed['company_id']}&year=2026",
        headers=headers,
    ).json()
    bulk = client.post(
        "/api/v1/annual-evals/bulk",
        headers=headers,
        json={"item_ids": [items[0]["id"]], "action": "note", "specialist_note": "Toplu not"},
    )
    assert bulk.status_code == 200, bulk.text
    assert bulk.json()["updated"] == 1
    detail = client.get(
        f"/api/v1/annual-evals/items?company_id={seed['company_id']}&year=2026",
        headers=headers,
    ).json()[0]
    assert "Toplu not" in (detail.get("specialist_note") or "")


def test_eval_notifications_rebuild(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}
    from app.services.notifications import rebuild_company_notifications
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        n = rebuild_company_notifications(db, seed["company_id"])
        assert n >= 1
    # refresh endpoint for specialist
    r = client.post("/api/v1/notifications/refresh", headers=headers)
    assert r.status_code == 200
    listed = client.get("/api/v1/notifications", headers=headers)
    assert listed.status_code == 200
    titles = [x.get("title") for x in listed.json()]
    assert any("değerlendirme" in (t or "").lower() or "Yıllık" in (t or "") for t in titles)


def test_year_compare_and_pdf_export(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}
    client.post(
        "/api/v1/annual-evals/start",
        headers=headers,
        json={"company_id": seed["company_id"], "year": 2026},
    )
    cmp = client.get(
        f"/api/v1/annual-evals/year-compare?company_id={seed['company_id']}&year=2026",
        headers=headers,
    )
    assert cmp.status_code == 200
    assert cmp.json()["prev_year"] == 2025
    pdf = client.get(
        f"/api/v1/annual-evals/export.pdf?company_id={seed['company_id']}&year=2026",
        headers=headers,
    )
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"


def test_evidence_unlink_and_history(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}
    client.post(
        "/api/v1/annual-evals/start",
        headers=headers,
        json={"company_id": seed["company_id"], "year": 2026},
    )
    item_id = client.get(
        f"/api/v1/annual-evals/items?company_id={seed['company_id']}&year=2026",
        headers=headers,
    ).json()[0]["id"]
    linked = client.post(
        f"/api/v1/annual-evals/items/{item_id}/evidences/link",
        headers=headers,
        json={"source_module": "training", "source_id": 1, "title": "Test egitim"},
    )
    assert linked.status_code == 200, linked.text
    eid = linked.json()["id"]
    hist = client.get(f"/api/v1/annual-evals/items/{item_id}/history", headers=headers)
    assert hist.status_code == 200
    un = client.delete(f"/api/v1/annual-evals/evidences/{eid}", headers=headers)
    assert un.status_code == 200
    left = client.get(f"/api/v1/annual-evals/items/{item_id}/evidences", headers=headers).json()
    assert all(x["id"] != eid for x in left)


def test_verify_code_public(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}
    ov = client.post(
        "/api/v1/annual-evals/start",
        headers=headers,
        json={"company_id": seed["company_id"], "year": 2026},
    ).json()
    code = ov.get("verify_code")
    assert code
    pub = client.get(f"/api/v1/annual-evals/verify/{code}")
    assert pub.status_code == 200
    assert pub.json()["valid"] is True
    assert pub.json()["year"] == 2026


def test_revision_field_diff_and_employer_approve(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}
    ov = client.post(
        "/api/v1/annual-evals/start",
        headers=headers,
        json={"company_id": seed["company_id"], "year": 2026},
    ).json()
    eid = ov["evaluation_id"]
    items = client.get(
        f"/api/v1/annual-evals/items?company_id={seed['company_id']}&year=2026",
        headers=headers,
    ).json()
    item_id = items[0]["id"]
    client.put(
        f"/api/v1/annual-evals/items/{item_id}",
        headers=headers,
        json={"outcome_status": "tamam", "completion_pct": 100, "actual_end": "2026-03-10"},
    )
    assert client.post(f"/api/v1/annual-evals/{eid}/workflow/approve-employer", headers=headers).status_code == 200
    rev1 = client.post(f"/api/v1/annual-evals/{eid}/workflow/create-revision", headers=headers)
    assert rev1.status_code == 200, rev1.text
    assert rev1.json().get("revision", {}).get("revision_no") == 1
    upd = client.put(
        f"/api/v1/annual-evals/items/{item_id}",
        headers=headers,
        json={"outcome_status": "kismi", "completion_pct": 50, "specialist_note": "revize", "result_text": "kismi"},
    )
    assert upd.status_code == 200, upd.text
    rev2 = client.post(f"/api/v1/annual-evals/{eid}/workflow/create-revision", headers=headers)
    assert rev2.status_code == 200, rev2.text
    assert rev2.json()["revision"]["revision_no"] == 2
    assert rev2.json()["revision"]["change_count"] >= 1
    listed = client.get(f"/api/v1/annual-evals/{eid}/revisions", headers=headers)
    assert listed.status_code == 200
    body = listed.json()
    assert len(body) >= 2
    assert any(r["revision_no"] == 2 and r["change_count"] >= 1 for r in body)

    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import User, UserRole

    with SessionLocal() as db:
        emp = User(
            email="eval-isveren@test.com",
            full_name="Eval Isveren",
            hashed_password=get_password_hash("TestPass123!"),
            role=UserRole.READ_ONLY,
            osgb_id=db.query(User).filter(User.email == "eval-uzman@test.com").one().osgb_id,
            company_id=seed["company_id"],
            is_active=True,
        )
        db.add(emp)
        db.commit()

    login = client.post("/api/v1/auth/login", json={"email": "eval-isveren@test.com", "password": "TestPass123!"})
    assert login.status_code == 200, login.text
    eh = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get(
        f"/api/v1/annual-evals/overview?company_id={seed['company_id']}&year=2026",
        headers=eh,
    ).status_code == 200
    client.post(f"/api/v1/annual-evals/{eid}/workflow/submit-specialist", headers=headers)
    client.post(f"/api/v1/annual-evals/{eid}/workflow/approve-physician", headers=headers)
    # Physician may not exist — specialist can move to isveren via approve-physician? Only physician role.
    # Specialist already can approve-employer; for employer path set status manually via specialist flow:
    # After create-revision status is revizyon; specialist submit then we need physician.
    # Simpler: specialist approve-employer again after moving — use specialist to set isveren_bekliyor via patch? No.
    # Force: specialist submit-specialist (hekim_bekliyor) then specialist cannot approve-physician.
    # Seed a physician or use DB to set status.
    with SessionLocal() as db:
        from app.models.entities import AnnualPlanEvaluation
        ev = db.get(AnnualPlanEvaluation, eid)
        ev.report_status = "isveren_bekliyor"
        db.commit()
    ok = client.post(f"/api/v1/annual-evals/{eid}/workflow/approve-employer", headers=eh)
    assert ok.status_code == 200, ok.text
    assert ok.json()["report_status"] == "onaylandi"
    forbidden = client.post(f"/api/v1/annual-evals/{eid}/workflow/create-revision", headers=eh)
    assert forbidden.status_code == 403

