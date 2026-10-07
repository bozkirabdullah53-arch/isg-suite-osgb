"""0.9.134 — Acil durum ekipleri (emergency teams) smoke tests."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _freeze_emergency_clock(monkeypatch, instant="2026-10-05T21:14:08+00:00"):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    utc_now = datetime.fromisoformat(instant)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            assert tz is not None, "Business dates must use an explicit time zone"
            return utc_now.astimezone(tz)

    monkeypatch.setattr("app.core.input_rules.datetime", FrozenDateTime)
    return utc_now.astimezone(ZoneInfo("Europe/Istanbul")).date()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "emg.db"
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
    from datetime import date, timedelta
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import (
        AssignmentStatus,
        Company,
        Employee,
        IsgProfessional,
        OsgbOrganization,
        ProfessionalType,
        User,
        UserRole,
        WorkplaceAssignment,
    )

    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="Acil OSGB",
            authorization_number="YETKI-ACIL-1",
            tax_number="1112223334",
            responsible_manager="Acil Yonetici",
            email="acil-osgb@test.com",
            is_active=True,
        )
        db.add(osgb)
        db.flush()

        company = Company(
            name="Acil Firma",
            osgb_id=osgb.id,
            tax_number="1234567890",
            sgk_registry_no="1234567890123",
            hazard_class="Tehlikeli",
            address="Ankara",
            is_active=True,
        )
        db.add(company)
        # İzolasyon testi için ikinci firma
        other = Company(name="Diger Firma", osgb_id=osgb.id, is_active=True)
        db.add(other)
        db.flush()

        emps = []
        for i in range(4):
            e = Employee(
                company_id=company.id,
                full_name=f"Personel {i + 1}",
                job_title="Operatör",
                department="Üretim",
                is_active=True,
            )
            db.add(e)
            emps.append(e)
        other_emp = Employee(company_id=other.id, full_name="Diger Personel", is_active=True)
        db.add(other_emp)

        professional = IsgProfessional(
            osgb_id=osgb.id,
            full_name="Acil Uzman",
            email="acil-uzman@test.com",
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            is_active=True,
        )
        db.add(professional)
        db.flush()
        db.add(
            WorkplaceAssignment(
                osgb_id=osgb.id,
                company_id=company.id,
                professional_id=professional.id,
                professional_type=ProfessionalType.SAFETY_SPECIALIST,
                start_date=date.today() - timedelta(days=1),
                status=AssignmentStatus.ACTIVE,
            )
        )

        db.add(
            User(
                email="acil-uzman@test.com",
                full_name="Acil Uzman",
                hashed_password=get_password_hash("TestPass123!"),
                role=UserRole.SAFETY_SPECIALIST,
                osgb_id=osgb.id,
                company_id=company.id,
                is_active=True,
            )
        )
        db.commit()
        db.refresh(company)
        db.refresh(other)
        emp_ids = [e.id for e in db.query(Employee).filter(Employee.company_id == company.id).all()]

    r = client.post(
        "/api/v1/auth/login",
        json={"email": "acil-uzman@test.com", "password": "TestPass123!"},
    )
    assert r.status_code == 200, r.text
    return {
        "token": r.json()["access_token"],
        "company_id": company.id,
        "other_company_id": other.id,
        "employee_ids": emp_ids,
    }


def test_health_acil_ekipler_flag(release_flags):
    body = release_flags
    assert body.get("version")
    assert body["acil_ekipler"] == "emergency-teams-v1"


def test_overview_seeds_default_teams(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}
    r = client.get(f"/api/v1/emergency-teams/overview?company_id={seed['company_id']}", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    # 6 varsayılan ekip otomatik oluşur
    assert body["kpis"]["team_count"] == 6
    assert body["company"]["sgk_registry_no"] == "1234567890123"
    assert body["can_edit"] is True
    codes = {t["type_code"] for t in body["teams"]}
    assert "sondurme" in codes and "ilk_yardim" in codes


def test_midnight_assignments_appear_in_team_counts_immediately(client, monkeypatch):
    from datetime import timedelta

    seed = _seed(client)
    today = _freeze_emergency_clock(monkeypatch)
    headers = {"Authorization": f"Bearer {seed['token']}"}
    url = f"/api/v1/emergency-teams/overview?company_id={seed['company_id']}"
    initial = client.get(url, headers=headers).json()
    team_id = next(t["id"] for t in initial["teams"] if t["type_code"] == "sondurme")
    assignment_ids = []
    for index, employee_id in enumerate(seed["employee_ids"][:2]):
        created = client.post("/api/v1/emergency-teams/assignments", headers=headers, json={
            "company_id": seed["company_id"], "team_id": team_id,
            "employee_id": employee_id, "membership": "asil", "is_leader": index == 0,
            "assign_start": today.isoformat(), "assign_end": today.isoformat(),
            "letter_date": today.isoformat(),
        })
        assert created.status_code == 200, created.text
        assignment_ids.append(created.json()["id"])

    listed = client.get(
        f"/api/v1/emergency-teams/assignments?company_id={seed['company_id']}", headers=headers,
    )
    assert listed.status_code == 200, listed.text
    assert {a["id"] for a in listed.json()} == set(assignment_ids)
    current = client.get(url, headers=headers).json()
    team = next(t for t in current["teams"] if t["id"] == team_id)
    assert team["member_count"] == team["asil_count"] == 2
    assert team["yedek_count"] == 0
    assert team["leader_name"] == "Personel 1"
    assert all(t["member_count"] == 0 for t in current["teams"] if t["id"] != team_id)
    teams_response = client.get(
        f"/api/v1/emergency-teams/teams?company_id={seed['company_id']}", headers=headers,
    )
    assert teams_response.status_code == 200, teams_response.text
    assert next(t for t in teams_response.json() if t["id"] == team_id)["asil_count"] == 2

    future = client.post("/api/v1/emergency-teams/assignments", headers=headers, json={
        "company_id": seed["company_id"], "team_id": team_id,
        "employee_id": seed["employee_ids"][2], "membership": "asil",
        "assign_start": (today + timedelta(days=1)).isoformat(),
    })
    assert future.status_code == 200, future.text
    still_current = next(t for t in client.get(url, headers=headers).json()["teams"] if t["id"] == team_id)
    assert still_current["asil_count"] == 2

    # Türkiye'de ertesi gün: eski üyelikler biter, ileri tarihli üyelik başlar.
    _freeze_emergency_clock(monkeypatch, "2026-10-06T21:00:00+00:00")
    next_day = next(t for t in client.get(url, headers=headers).json()["teams"] if t["id"] == team_id)
    assert next_day["member_count"] == next_day["asil_count"] == 1
    assert next_day["leader_name"] is None


def test_midnight_employee_population_uses_turkey_day(client, monkeypatch):
    from datetime import timedelta
    from app.core.database import SessionLocal
    from app.models.entities import Employee

    seed = _seed(client)
    today = _freeze_emergency_clock(monkeypatch)
    headers = {"Authorization": f"Bearer {seed['token']}"}
    url = f"/api/v1/emergency-teams/overview?company_id={seed['company_id']}"
    with SessionLocal() as db:
        db.get(Employee, seed["employee_ids"][0]).start_date = today
        db.commit()
    assert client.get(url, headers=headers).json()["employee_count"] == 4

    with SessionLocal() as db:
        db.get(Employee, seed["employee_ids"][1]).exit_date = today
        db.get(Employee, seed["employee_ids"][2]).start_date = today + timedelta(days=1)
        db.get(Employee, seed["employee_ids"][3]).is_active = False
        db.commit()
    assert client.get(url, headers=headers).json()["employee_count"] == 1


def test_midnight_certificate_status_uses_turkey_day(monkeypatch):
    from datetime import timedelta
    from app.services.emergency_team_logic import cert_status

    today = _freeze_emergency_clock(monkeypatch)
    yesterday = today - timedelta(days=1)
    assert cert_status(yesterday) == "red"
    assert cert_status(today) == "yellow"
    assert cert_status(today + timedelta(days=30)) == "yellow"
    assert cert_status(today + timedelta(days=31)) == "green"
    assert cert_status(None) == "grey"
    assert cert_status(yesterday, today=yesterday) == "yellow"


def test_emergency_plan_legend_reports_drill_and_team_readiness(client):
    from datetime import date

    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}

    # Uzman görünümünde varsayılan ekipler oluşur; üye atanmadığı için kadro
    # hazır kabul edilmemelidir.
    overview = client.get(
        f"/api/v1/emergency-teams/overview?company_id={seed['company_id']}",
        headers=headers,
    )
    assert overview.status_code == 200, overview.text

    created = client.post(
        "/api/v1/emergency-plans",
        headers=headers,
        json={
            "company_id": seed["company_id"],
            "title": "Acil Durum Planı",
            "plan_date": date.today().isoformat(),
            "next_review_date": date.today().isoformat(),
            "assembly_areas": "Açık otopark",
            "scenario_summary": "Yangın sonrası tahliye ve toplanma akışı",
        },
    )
    assert created.status_code == 200, created.text
    plan_id = created.json()["id"]

    missing = client.get(f"/api/v1/emergency-plans/{plan_id}/legend", headers=headers)
    assert missing.status_code == 200, missing.text
    missing_body = missing.json()
    assert missing_body["team_readiness"]["ready"] is False
    assert missing_body["drill_readiness"]["status"] == "missing"
    assert "Tamamlanmış tatbikat kaydı bulunmuyor" in missing_body["missing"]

    drill = client.post(
        "/api/v1/drills",
        headers=headers,
        json={
            "company_id": seed["company_id"],
            "drill_type": "Yangın",
            "drill_date": date.today().isoformat(),
            "status": "yapildi",
            "scenario": "Yangın alarmı sonrası tahliye",
        },
    )
    assert drill.status_code == 200, drill.text

    current = client.get(f"/api/v1/emergency-plans/{plan_id}/legend", headers=headers)
    assert current.status_code == 200, current.text
    current_body = current.json()
    assert current_body["drill_readiness"]["status"] == "current"
    assert current_body["drill_readiness"]["latest_date"] == date.today().isoformat()


def test_create_team_assign_list_soft_delete(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}

    # meta -> tür id
    meta = client.get("/api/v1/emergency-teams/meta", headers=headers).json()
    type_id = meta["team_types"][0]["id"]

    created = client.post(
        "/api/v1/emergency-teams/teams",
        headers=headers,
        json={
            "company_id": seed["company_id"],
            "type_id": type_id,
            "name": "Özel Söndürme Ekibi",
            "min_members": 3,
        },
    )
    assert created.status_code == 200, created.text
    team_id = created.json()["id"]

    # üye ata
    assigned = client.post(
        "/api/v1/emergency-teams/assignments",
        headers=headers,
        json={
            "company_id": seed["company_id"],
            "team_id": team_id,
            "employee_id": seed["employee_ids"][0],
            "membership": "asil",
            "is_leader": True,
            "role_title": "Ekip Başı",
        },
    )
    assert assigned.status_code == 200, assigned.text
    assignment_id = assigned.json()["id"]
    assert assigned.json()["cert_status"] == "grey"  # eğitim yok

    listed = client.get(
        f"/api/v1/emergency-teams/assignments?company_id={seed['company_id']}&team_id={team_id}",
        headers=headers,
    )
    assert listed.status_code == 200
    assert any(a["id"] == assignment_id for a in listed.json())

    # aynı personel ikinci kez -> 409
    dup = client.post(
        "/api/v1/emergency-teams/assignments",
        headers=headers,
        json={
            "company_id": seed["company_id"],
            "team_id": team_id,
            "employee_id": seed["employee_ids"][0],
        },
    )
    assert dup.status_code == 409

    # soft delete üye
    d = client.delete(f"/api/v1/emergency-teams/assignments/{assignment_id}", headers=headers)
    assert d.status_code == 200
    listed2 = client.get(
        f"/api/v1/emergency-teams/assignments?company_id={seed['company_id']}&team_id={team_id}",
        headers=headers,
    )
    assert all(a["id"] != assignment_id for a in listed2.json())

    # soft delete ekip
    dt = client.delete(f"/api/v1/emergency-teams/teams/{team_id}", headers=headers)
    assert dt.status_code == 200
    teams = client.get(f"/api/v1/emergency-teams/teams?company_id={seed['company_id']}", headers=headers)
    assert all(t["id"] != team_id for t in teams.json())

    restored = client.post(
        f"/api/v1/emergency-teams/restore-inactive?company_id={seed['company_id']}",
        headers=headers,
    )
    assert restored.status_code == 200, restored.text
    body = restored.json()
    assert body["restored_teams"] >= 1
    teams2 = client.get(f"/api/v1/emergency-teams/teams?company_id={seed['company_id']}", headers=headers)
    assert any(t["id"] == team_id for t in teams2.json())
    listed3 = client.get(
        f"/api/v1/emergency-teams/assignments?company_id={seed['company_id']}&team_id={team_id}",
        headers=headers,
    )
    assert any(a["id"] == assignment_id for a in listed3.json())


def test_cert_status_yellow_after_training(client):
    from datetime import date, timedelta

    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}
    meta = client.get("/api/v1/emergency-teams/meta", headers=headers).json()
    type_id = meta["team_types"][0]["id"]
    team_id = client.post(
        "/api/v1/emergency-teams/teams",
        headers=headers,
        json={"company_id": seed["company_id"], "type_id": type_id, "name": "İlk Yardım"},
    ).json()["id"]
    a_id = client.post(
        "/api/v1/emergency-teams/assignments",
        headers=headers,
        json={"company_id": seed["company_id"], "team_id": team_id, "employee_id": seed["employee_ids"][1]},
    ).json()["id"]

    soon = (date.today() + timedelta(days=10)).isoformat()
    tr = client.post(
        f"/api/v1/emergency-teams/assignments/{a_id}/trainings",
        headers=headers,
        json={"training_type": "İlk Yardım", "valid_until": soon},
    )
    assert tr.status_code == 200, tr.text

    lst = client.get(
        f"/api/v1/emergency-teams/assignments?company_id={seed['company_id']}&team_id={team_id}",
        headers=headers,
    ).json()
    row = next(a for a in lst if a["id"] == a_id)
    assert row["cert_status"] == "yellow"


def test_company_isolation(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}
    # Uzmanın erişemeyeceği başka firma (görevlendirme yok, company_id farklı)
    r = client.get(
        f"/api/v1/emergency-teams/overview?company_id={seed['other_company_id']}",
        headers=headers,
    )
    assert r.status_code == 403


def _emergency_viewer_headers(seed, *, email, company_bound=True, role=None):
    from app.core.database import SessionLocal
    from app.core.security import create_access_token
    from app.models.entities import Company, User, UserRole, WorkplaceMembership

    with SessionLocal() as db:
        specialist = db.query(User).filter_by(email="acil-uzman@test.com").one()
        user = User(
            email=email, full_name="Ekip Görüntüleyen",
            hashed_password=specialist.hashed_password,
            role=role or UserRole.COMPANY_ADMIN,
            company_id=seed["company_id"] if company_bound else None,
            osgb_id=db.get(Company, seed["company_id"]).osgb_id,
            is_active=True,
        )
        db.add(user)
        db.flush()
        if company_bound:
            # Eski/hatalı üyelik başka işyerine erişim vermemeli.
            db.add(WorkplaceMembership(
                user_id=user.id, company_id=seed["other_company_id"],
                role="company_admin", is_active=True,
            ))
        token = create_access_token(str(user.id))
        db.commit()
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("email", ["workplace@test.com", "isyeri.1@kiosk.isgsuite.tr"])
def test_workplace_emergency_teams_read_only_and_company_scoped(client, email):
    from app.core.database import SessionLocal
    from app.models.entities import EmergencyTeamAssignment, EmergencyTeamTraining, Employee, User
    from app.services.emergency_team_logic import ensure_default_teams

    seed = _seed(client)
    headers = _emergency_viewer_headers(seed, email=email)
    own_id, foreign_id = seed["company_id"], seed["other_company_id"]
    base = "/api/v1/emergency-teams"

    # Görüntüleme boş işyerine ekip/görevlendirme oluşturmaz.
    empty = client.get(f"{base}/overview?company_id={own_id}", headers=headers)
    assert empty.status_code == 200, empty.text
    assert empty.json()["teams"] == []
    assert empty.json()["can_edit"] is False

    with SessionLocal() as db:
        specialist = db.query(User).filter_by(email="acil-uzman@test.com").one()
        teams = {}
        assignments = {}
        for cid in (own_id, foreign_id):
            team = ensure_default_teams(db, cid, specialist.id)[0]
            employee = db.query(Employee).filter_by(company_id=cid).first()
            member = EmergencyTeamAssignment(
                company_id=cid, team_id=team.id, employee_id=employee.id,
                membership="asil", created_by_id=specialist.id,
            )
            db.add(member)
            db.flush()
            db.add(EmergencyTeamTraining(assignment_id=member.id, training_type="Ekip Eğitimi"))
            teams[cid] = {"id": team.id, "type_id": team.type_id}
            assignments[cid] = member.id
        db.commit()

    assert client.get(f"{base}/meta", headers=headers).status_code == 200
    overview = client.get(f"{base}/overview?company_id={own_id}", headers=headers)
    assert overview.status_code == 200, overview.text
    assert overview.json()["company"]["id"] == own_id
    assert overview.json()["can_edit"] is False
    for resource in ("teams", "assignments"):
        for query in ("", f"?company_id={own_id}"):
            result = client.get(f"{base}/{resource}{query}", headers=headers)
            assert result.status_code == 200, result.text
            assert result.json()
            assert {row["company_id"] for row in result.json()} == {own_id}

    own_member = assignments[own_id]
    foreign_member = assignments[foreign_id]
    trainings = client.get(f"{base}/assignments/{own_member}/trainings", headers=headers)
    assert trainings.status_code == 200, trainings.text
    assert trainings.json()[0]["training_type"] == "Ekip Eğitimi"
    for path in (f"export.xlsx?company_id={own_id}", f"export.pdf?company_id={own_id}",
                 f"assignments/{own_member}/letter.pdf"):
        result = client.get(f"{base}/{path}", headers=headers)
        assert result.status_code == 200, result.text
        assert result.content.startswith(b"PK" if ".xlsx" in path else b"%PDF")

    for path in (f"overview?company_id={foreign_id}", f"teams?company_id={foreign_id}",
                 f"assignments?company_id={foreign_id}", f"export.xlsx?company_id={foreign_id}",
                 f"export.pdf?company_id={foreign_id}", f"assignments/{foreign_member}/trainings",
                 f"assignments/{foreign_member}/letter.pdf"):
        assert client.get(f"{base}/{path}", headers=headers).status_code == 403, path

    # Kendi işyerinde bile mevcut uzman düzenleme/silme sınırı korunur.
    own_team = teams[own_id]
    for method, path, payload in (
        ("POST", "teams", {"company_id": own_id, "type_id": own_team["type_id"], "name": "Yeni Ekip"}),
        ("PUT", f"teams/{own_team['id']}", {"name": "Değiştirildi"}),
        ("DELETE", f"teams/{own_team['id']}", None),
        ("POST", f"teams/{own_team['id']}/restore", None),
        ("POST", f"restore-inactive?company_id={own_id}", None),
        ("POST", "assignments", {"company_id": own_id, "team_id": own_team["id"], "employee_id": seed["employee_ids"][1]}),
        ("PUT", f"assignments/{own_member}", {"notes": "Değiştirildi"}),
        ("DELETE", f"assignments/{own_member}", None),
        ("POST", f"assignments/{own_member}/restore", None),
        ("POST", f"assignments/{own_member}/trainings", {"training_type": "Yeni Eğitim"}),
    ):
        result = client.request(method, f"{base}/{path}", headers=headers, json=payload)
        assert result.status_code == 403, (method, path, result.text)
    upload = client.post(f"{base}/assignments/{own_member}/certificate-file", headers=headers,
                         files={"file": ("belge.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")})
    assert upload.status_code == 403
    with SessionLocal() as db:
        member = db.get(EmergencyTeamAssignment, own_member)
        assert member.is_active is True and member.notes is None
        assert len(member.trainings) == 1


@pytest.mark.parametrize("account", ["osgb_admin", "employee"])
def test_emergency_teams_does_not_expand_osgb_or_employee_access(client, account):
    from app.models.entities import UserRole

    seed = _seed(client)
    headers = _emergency_viewer_headers(
        seed, email=f"{account}@test.com", company_bound=account == "employee",
        role=UserRole.READ_ONLY if account == "employee" else UserRole.COMPANY_ADMIN,
    )
    base = "/api/v1/emergency-teams"
    for path in (f"overview?company_id={seed['company_id']}", "teams", "assignments",
                 f"export.xlsx?company_id={seed['company_id']}",
                 f"export.pdf?company_id={seed['company_id']}"):
        assert client.get(f"{base}/{path}", headers=headers).status_code == 403, path


def test_export_xlsx_and_pdf(client):
    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}
    # overview varsayılan ekipleri kurar
    client.get(f"/api/v1/emergency-teams/overview?company_id={seed['company_id']}", headers=headers)

    x = client.get(f"/api/v1/emergency-teams/export.xlsx?company_id={seed['company_id']}", headers=headers)
    assert x.status_code == 200
    assert len(x.content) > 100

    p = client.get(f"/api/v1/emergency-teams/export.pdf?company_id={seed['company_id']}", headers=headers)
    assert p.status_code == 200
    assert p.content[:4] == b"%PDF"


def test_overview_recalculates_from_only_current_company_workers(client):
    from datetime import timedelta
    from sqlalchemy import select
    from app.core.database import SessionLocal
    from app.models.entities import Company, Employee, EmergencyTeam
    from app.services.emergency_team_logic import emergency_team_today

    seed = _seed(client)
    today = emergency_team_today()
    headers = {"Authorization": f"Bearer {seed['token']}"}
    url = f"/api/v1/emergency-teams/overview?company_id={seed['company_id']}"
    initial = client.get(url, headers=headers).json()
    assert initial["employee_count"] == 4
    assert initial["shared_support_allowed"] is True
    assert all(t["required_members"] == 1 for t in initial["teams"] if t["type_code"] in {"sondurme", "kurtarma", "koruma", "ilk_yardim"})

    with SessionLocal() as db:
        db.add_all([Employee(company_id=seed["company_id"], full_name=f"Aktif {i}", is_active=True) for i in range(37)])
        db.add_all([Employee(company_id=seed["other_company_id"], full_name=f"Diğer {i}", is_active=True) for i in range(60)])
        db.add(Employee(company_id=seed["company_id"], full_name="Pasif", is_active=False))
        db.add(Employee(company_id=seed["company_id"], full_name="Ayrılan", is_active=True, exit_date=today))
        db.add(Employee(company_id=seed["company_id"], full_name="Gelecek", is_active=True, start_date=today + timedelta(days=1)))
        db.commit()

    current = client.get(url, headers=headers).json()
    assert current["employee_count"] == 41
    assert current["shared_support_allowed"] is False
    by_code = {t["type_code"]: t for t in current["teams"]}
    assert by_code["sondurme"]["required_members"] == 2
    assert by_code["ilk_yardim"]["required_members"] == 3
    assert by_code["ilk_yardim"]["missing_members"] == 3
    assert by_code["tahliye"]["required_members"] is None
    assert by_code["tahliye"]["status"]["code"] == "planlama"
    listed = client.get(f"/api/v1/emergency-teams/teams?company_id={seed['company_id']}", headers=headers).json()
    assert {t["type_code"]: t["required_members"] for t in listed} == {t["type_code"]: t["required_members"] for t in current["teams"]}

    with SessionLocal() as db:
        db.get(Company, seed["company_id"]).hazard_class = "Çok Tehlikeli"
        db.commit()
        # Hesaplama mevcut ekip hedeflerine yazmaz, kayıtları değiştirmez.
        assert all(t.min_members == 2 for t in db.scalars(select(EmergencyTeam).where(EmergencyTeam.company_id == seed["company_id"])).all())
    changed = client.get(url, headers=headers).json()
    assert next(t for t in changed["teams"] if t["type_code"] == "ilk_yardim")["required_members"] == 5


def test_reserves_and_departed_workers_do_not_fill_primary_shortage(client):
    from app.core.database import SessionLocal
    from app.models.entities import Company, Employee
    from app.services.emergency_team_logic import emergency_team_today

    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}
    url = f"/api/v1/emergency-teams/overview?company_id={seed['company_id']}"
    with SessionLocal() as db:
        db.get(Company, seed["company_id"]).hazard_class = "Çok Tehlikeli"
        db.add_all([Employee(company_id=seed["company_id"], full_name=f"Aktif {i}", is_active=True) for i in range(37)])
        db.commit()
    overview = client.get(url, headers=headers).json()
    team_id = next(t["id"] for t in overview["teams"] if t["type_code"] == "sondurme")
    for index, employee_id in enumerate(seed["employee_ids"][:3]):
        created = client.post("/api/v1/emergency-teams/assignments", headers=headers, json={
            "company_id": seed["company_id"], "team_id": team_id, "employee_id": employee_id,
            "membership": "asil" if index == 0 else "yedek", "is_leader": index == 0,
        })
        assert created.status_code == 200, created.text
    current = next(t for t in client.get(url, headers=headers).json()["teams"] if t["id"] == team_id)
    assert current["member_count"] == 3
    assert current["asil_count"] == 1
    assert current["missing_members"] == 1
    assert current["status"]["code"] == "kritik"

    with SessionLocal() as db:
        db.get(Employee, seed["employee_ids"][0]).exit_date = emergency_team_today()
        db.commit()
    departed = next(t for t in client.get(url, headers=headers).json()["teams"] if t["id"] == team_id)
    assert departed["asil_count"] == 0
    assert departed["missing_members"] == 2
    assert departed["leader_name"] is None


def test_missing_population_or_hazard_is_visible(client):
    from sqlalchemy import update
    from app.core.database import SessionLocal
    from app.models.entities import Company, Employee

    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}
    url = f"/api/v1/emergency-teams/overview?company_id={seed['company_id']}"
    with SessionLocal() as db:
        db.get(Company, seed["company_id"]).hazard_class = None
        db.commit()
    unknown = client.get(url, headers=headers).json()
    first_aid = next(t for t in unknown["teams"] if t["type_code"] == "ilk_yardim")
    assert first_aid["required_members"] is None
    assert first_aid["missing_members"] is None
    assert first_aid["status"]["code"] == "veri_eksik"
    with SessionLocal() as db:
        db.execute(update(Employee).where(Employee.company_id == seed["company_id"]).values(is_active=False))
        db.commit()
    empty = client.get(url, headers=headers).json()
    assert empty["employee_count"] == 0
    assert all(t["required_members"] is None for t in empty["teams"])


@pytest.mark.parametrize("code, reference, keyword", [
    ("sondurme", "m.11/2-a", "Yangına"),
    ("kurtarma", "m.11/2-b", "kurtarmaya"),
    ("koruma", "m.11/2-c", "sayımı"),
    ("ilk_yardim", "m.11/5", "İlkyardım Yönetmeliği"),
    ("tahliye", "m.10", "yardımcı görevini"),
    ("haberlesme", "m.5/1-e", "yardımcı görevini"),
])
def test_assignment_letter_legal_content_and_scope(client, code, reference, keyword):
    from io import BytesIO
    from pypdf import PdfReader
    from app.core.database import SessionLocal
    from app.models.entities import EmergencyTeamAssignment

    seed = _seed(client)
    headers = {"Authorization": f"Bearer {seed['token']}"}
    teams = client.get(f"/api/v1/emergency-teams/overview?company_id={seed['company_id']}", headers=headers).json()["teams"]
    team = next(t for t in teams if t["type_code"] == code)
    created = client.post("/api/v1/emergency-teams/assignments", headers=headers, json={
        "company_id": seed["company_id"], "team_id": team["id"],
        "employee_id": seed["employee_ids"][0], "membership": "yedek",
        "is_leader": True, "assign_start": "2026-10-05", "letter_date": "2026-10-04",
        "assigned_by": "İşveren & Vekili <A>", "role_title": "Operatör",
    })
    assert created.status_code == 200, created.text
    assignment_id = created.json()["id"]
    path = f"/api/v1/emergency-teams/assignments/{assignment_id}/letter.pdf"
    downloaded = client.get(path, headers=headers)
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.headers["content-type"] == "application/pdf"
    assert f"gorevlendirme-yazisi-{assignment_id}.pdf" in downloaded.headers["content-disposition"]
    reader = PdfReader(BytesIO(downloaded.content))
    assert len(reader.pages) == 1
    text = " ".join(page.extract_text() for page in reader.pages)
    for expected in ["6331", "m.11/1-c", "m.15", reference, keyword, "Personel 1", "Acil Firma", "İşveren & Vekili <A>", "04.10.2026", "05.10.2026", "Yedek", "Ekip lideri", "Tebellüğ tarihi", "m.5/2"]:
        assert expected in text
    assert "Bölüm" not in text
    assert "Sicil No" not in text
    assert "Diger Firma" not in text
    assert f"AD-{seed['company_id']}-{assignment_id}" in text
    if code == "ilk_yardim":
        assert "m.19" in text
        assert "belgesi yerine geçmez" in text

    # Belge indirmek görevlendirme veya eğitim verisini değiştirmez.
    with SessionLocal() as db:
        row = db.get(EmergencyTeamAssignment, assignment_id)
        assert row.section == "Üretim"
        assert row.letter_no is None
        assert len(row.trainings) == 0

    # Yetkisiz firma ve kaldırılmış görevlendirme için belge verilemez.
    with SessionLocal() as db:
        row = db.get(EmergencyTeamAssignment, assignment_id)
        row.company_id = seed["other_company_id"]
        db.commit()
    assert client.get(path, headers=headers).status_code == 403
    with SessionLocal() as db:
        row = db.get(EmergencyTeamAssignment, assignment_id)
        row.is_active = False
        db.commit()
    assert client.get(path, headers=headers).status_code == 404


def test_assignment_letter_wraps_literal_input_and_keeps_original_issue_date():
    from datetime import datetime
    from io import BytesIO
    from types import SimpleNamespace as NS
    from pypdf import PdfReader
    from app.services.emergency_team_reports import build_assignment_letter_pdf

    assignment = NS(id=17, created_at=datetime(2024, 1, 2), membership="asil",
                    letter_no="ÖZEL & <17>", assigned_by="İşveren & <Vekili>",
                    notes="İşyerine özel açıklama <eğitim> & ekipman.")
    company = NS(id=4, name="Şirket <A> & B " * 10, address="Uzun adres " * 15)
    team = NS(name="Özel Söndürme", team_type=NS(code="sondurme"))
    output = build_assignment_letter_pdf(company=company, team=team, assignment=assignment, employee_name="Ayşe <Yılmaz> & Şahin")
    reader = PdfReader(BytesIO(output))
    text = " ".join(p.extract_text() for p in reader.pages)
    assert "02.01.2024" in text
    assert "ÖZEL & <17>" in text
    assert "Ayşe <Yılmaz> & Şahin" in text
    assert "<eğitim> & ekipman" in text
    assert "m.11/2-a" in text  # özel isim yerine ekip türü esas alınır
