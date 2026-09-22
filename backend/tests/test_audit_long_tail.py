"""İBYS Veritabanı Değişiklik Prosedürü §8 — uzun kuyruk denetim kaydı testleri.

Mutasyon uçlarının ``audit_logs`` tablosuna beklenen ``action`` ile satır
yazdığını ve hedef kaydın firma id'sinin (aktörün değil) kaydedildiğini
doğrular. En kritik modüller: üyelik/yetki, OSGB görevlendirme, şube ve
e-reçete (sağlık verisi).
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.models.entities import (
    AssignmentStatus,
    AuditLog,
    Company,
    Employee,
    IsgProfessional,
    OsgbOrganization,
    ProfessionalType,
    User,
    UserRole,
    WorkplaceAssignment,
)


@pytest.fixture()
def setup():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        osgb = OsgbOrganization(
            name="Denetim OSGB",
            authorization_number="YETKI-DEN-1",
            tax_number="9998887776",
            responsible_manager="Denetim Yonetici",
            email="denetim-osgb@test.com",
            is_active=True,
        )
        db.add(osgb)
        db.flush()

        company = Company(name="Denetim Firma", osgb_id=osgb.id, is_active=True)
        other = Company(name="Diger Firma", osgb_id=osgb.id, is_active=True)
        db.add_all([company, other])
        db.flush()

        employee = Employee(company_id=company.id, full_name="Denetim Personel", is_active=True)
        db.add(employee)
        db.flush()

        safety_pro = IsgProfessional(
            osgb_id=osgb.id,
            full_name="Denetim Uzman",
            email=None,
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            is_active=True,
        )
        physician_pro = IsgProfessional(
            osgb_id=osgb.id,
            full_name="Denetim Hekim",
            email="denetim-hekim@test.com",
            professional_type=ProfessionalType.WORKPLACE_PHYSICIAN,
            is_active=True,
        )
        db.add_all([safety_pro, physician_pro])
        db.flush()
        db.add(
            WorkplaceAssignment(
                osgb_id=osgb.id,
                company_id=company.id,
                professional_id=physician_pro.id,
                professional_type=ProfessionalType.WORKPLACE_PHYSICIAN,
                start_date=date.today() - timedelta(days=1),
                status=AssignmentStatus.ACTIVE,
            )
        )

        global_admin = User(
            email="denetim-root@test.com",
            full_name="Denetim Root",
            hashed_password="x",
            role=UserRole.GLOBAL_ADMIN,
            is_active=True,
        )
        physician = User(
            email="denetim-hekim@test.com",
            full_name="Denetim Hekim",
            hashed_password="x",
            role=UserRole.WORKPLACE_PHYSICIAN,
            osgb_id=osgb.id,
            company_id=company.id,
            is_active=True,
        )
        db.add_all([global_admin, physician])
        db.commit()
        db.refresh(global_admin)
        db.refresh(physician)

        ids = {
            "osgb_id": osgb.id,
            "company_id": company.id,
            "other_company_id": other.id,
            "employee_id": employee.id,
            "professional_id": safety_pro.id,
            "physician_professional_id": physician_pro.id,
            "global_admin_id": global_admin.id,
            "physician_id": physician.id,
        }
    return factory, ids


def _client(factory, user_id):
    from app.api.deps import get_current_user
    from app.core.tenant_context import bind_user_tenant
    from app.main import app

    def db_dep():
        with factory() as db:
            yield db

    def user_dep():
        with factory() as db:
            user = db.get(User, user_id)
            bind_user_tenant(user)
            return user

    app.dependency_overrides[get_db] = db_dep
    app.dependency_overrides[get_current_user] = user_dep
    return app, TestClient(app)


def _audits(factory, action: str) -> list[AuditLog]:
    with factory() as db:
        return list(
            db.scalars(select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.id)).all()
        )


def test_branch_create_and_update_write_audit(setup):
    factory, ids = setup
    app, client = _client(factory, ids["global_admin_id"])
    try:
        created = client.post(
            "/api/v1/branches",
            json={"company_id": ids["company_id"], "name": "Merkez Şube"},
        )
        assert created.status_code == 200, created.text
        branch_id = created.json()["id"]

        updated = client.put(f"/api/v1/branches/{branch_id}", json={"name": "Merkez Şube 2"})
        assert updated.status_code == 200, updated.text
    finally:
        app.dependency_overrides.clear()

    created_rows = _audits(factory, "branch_created")
    assert len(created_rows) == 1
    assert created_rows[0].company_id == ids["company_id"]
    assert created_rows[0].module == "branch"
    assert created_rows[0].entity_id == str(branch_id)
    assert created_rows[0].new_value and "Merkez Şube" in created_rows[0].new_value

    updated_rows = _audits(factory, "branch_updated")
    assert len(updated_rows) == 1
    assert updated_rows[0].company_id == ids["company_id"]
    assert updated_rows[0].old_value and "Merkez Şube" in updated_rows[0].old_value
    assert updated_rows[0].new_value and "Merkez Şube 2" in updated_rows[0].new_value


def test_membership_mutations_write_audit(setup):
    factory, ids = setup
    app, client = _client(factory, ids["global_admin_id"])
    try:
        org = client.post(
            "/api/v1/memberships/organization",
            json={"user_id": ids["physician_id"], "osgb_id": ids["osgb_id"], "role": "company_admin"},
        )
        assert org.status_code == 200, org.text

        first = client.post(
            "/api/v1/memberships/workplace",
            json={"user_id": ids["physician_id"], "company_id": ids["company_id"], "role": "read_only"},
        )
        assert first.status_code == 200, first.text
        # Aynı üyeliği tekrar vermek mevcut satırı yeniden etkinleştirir.
        again = client.post(
            "/api/v1/memberships/workplace",
            json={"user_id": ids["physician_id"], "company_id": ids["company_id"], "role": "read_only"},
        )
        assert again.status_code == 200, again.text
    finally:
        app.dependency_overrides.clear()

    org_rows = _audits(factory, "organization_membership_created")
    assert len(org_rows) == 1
    assert org_rows[0].module == "membership"
    assert org_rows[0].new_value and str(ids["physician_id"]) in org_rows[0].new_value

    wp_created = _audits(factory, "workplace_membership_created")
    assert len(wp_created) == 1
    assert wp_created[0].company_id == ids["company_id"]
    assert wp_created[0].new_value and "read_only" in wp_created[0].new_value

    wp_reactivated = _audits(factory, "workplace_membership_reactivated")
    assert len(wp_reactivated) == 1
    assert wp_reactivated[0].company_id == ids["company_id"]
    assert wp_reactivated[0].old_value and "false" in wp_reactivated[0].old_value.lower()
    assert wp_reactivated[0].new_value and "true" in wp_reactivated[0].new_value.lower()


def test_osgb_assignment_mutations_write_audit_with_target_company(setup):
    factory, ids = setup
    app, client = _client(factory, ids["global_admin_id"])
    try:
        created = client.post(
            "/api/v1/osgb/assignments",
            json={
                "osgb_id": ids["osgb_id"],
                "company_id": ids["company_id"],
                "professional_id": ids["professional_id"],
                "professional_type": "safety_specialist",
                "start_date": (date.today() - timedelta(days=1)).isoformat(),
                "isg_katip_contract_number": "KATIP-DEN-1",
            },
        )
        assert created.status_code == 200, created.text
        assignment_id = created.json()["id"]

        suspended = client.patch(f"/api/v1/osgb/assignments/{assignment_id}/suspend")
        assert suspended.status_code == 200, suspended.text
    finally:
        app.dependency_overrides.clear()

    created_rows = _audits(factory, "assignment_created")
    assert len(created_rows) == 1
    # Aktör global yönetici (company_id yok); denetim hedef firmanın id'sini taşımalı.
    assert created_rows[0].company_id == ids["company_id"]
    assert created_rows[0].module == "assignment"
    assert created_rows[0].entity_id == str(assignment_id)
    assert created_rows[0].new_value and "KATIP-DEN-1" in created_rows[0].new_value

    suspended_rows = _audits(factory, "assignment_suspended")
    assert len(suspended_rows) == 1
    assert suspended_rows[0].company_id == ids["company_id"]
    assert suspended_rows[0].old_value and "active" in suspended_rows[0].old_value
    assert suspended_rows[0].new_value and "suspended" in suspended_rows[0].new_value


def test_prescription_create_and_update_write_audit(setup):
    factory, ids = setup
    app, client = _client(factory, ids["physician_id"])
    try:
        created = client.post(
            "/api/v1/prescriptions",
            json={
                "company_id": ids["company_id"],
                "employee_id": ids["employee_id"],
                "prescription_date": date.today().isoformat(),
                "diagnosis_code": "J06",
                "diagnosis_text": "Üst solunum yolu enfeksiyonu",
                "items": [
                    {
                        "medication_name": "Parasetamol",
                        "dose": "500 mg",
                        "frequency": "Günde 2",
                        "quantity": 1,
                    }
                ],
            },
        )
        assert created.status_code == 201, created.text
        prescription_id = created.json()["id"]

        updated = client.patch(
            f"/api/v1/prescriptions/{prescription_id}",
            json={"diagnosis_code": "J07", "clinical_note": "Kontrol önerildi"},
        )
        assert updated.status_code == 200, updated.text
    finally:
        app.dependency_overrides.clear()

    created_rows = _audits(factory, "prescription_created")
    assert len(created_rows) == 1
    assert created_rows[0].company_id == ids["company_id"]
    assert created_rows[0].module == "prescription"
    assert created_rows[0].new_value and "J06" in created_rows[0].new_value
    # Sağlık verisi serbest metni denetime düz yazılmaz; yalnız varlık bilgisi tutulur.
    assert "Üst solunum" not in (created_rows[0].new_value or "")

    updated_rows = _audits(factory, "prescription_updated")
    assert len(updated_rows) == 1
    assert updated_rows[0].company_id == ids["company_id"]
    assert updated_rows[0].old_value and "J06" in updated_rows[0].old_value
    assert updated_rows[0].new_value and "J07" in updated_rows[0].new_value
