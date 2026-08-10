"""Eyas Digital Approval — sıralı onay, MFA, bayrak kill-switch."""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import eyas_digital_approval_active, settings
from app.core.database import Base, SessionLocal
from app.core.security import get_password_hash
from app.models.entities import (
    AssignmentStatus,
    Company,
    IsgProfessional,
    OsgbOrganization,
    ProfessionalType,
    User,
    UserRole,
    WorkplaceAssignment,
)
from app.services import eyas_approval as svc




@pytest.fixture(autouse=True)
def _ensure_eyas_workflow_source_key(db):
    """Test DB may lag migrations; EyasWorkflow.source_key is required."""
    from sqlalchemy import text

    rows = db.execute(text("PRAGMA table_info(eyas_workflows)")).fetchall()
    if "source_key" not in {r[1] for r in rows}:
        db.execute(text("ALTER TABLE eyas_workflows ADD COLUMN source_key VARCHAR(160)"))
        db.commit()

@pytest.fixture()
def db(monkeypatch):
    """Her test için tam şemalı ve P0 görevlendirmeleri olan SQLite DB."""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool
    from sqlalchemy.orm import sessionmaker

    import app.core.database as database

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", session_factory)
    monkeypatch.setattr(sys.modules[__name__], "SessionLocal", session_factory)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def _mk_users(db):
    stamp = f"{datetime.utcnow().timestamp():.0f}"
    osgb = db.scalar(select(OsgbOrganization).limit(1))
    if not osgb:
        osgb = OsgbOrganization(name=f"Eyas OSGB {stamp}", is_active=True)
        db.add(osgb)
        db.flush()
    company = Company(
        name=f"Eyas Firma {stamp}",
        osgb_id=osgb.id,
        tax_number=f"9{stamp[-9:]}",
        is_active=True,
    )
    db.add(company)
    db.flush()

    professionals = {}
    for key, full_name, email, professional_type in (
        ("uzman", "Eyas Uzman", f"eyas.uzman.{stamp}@test.com", ProfessionalType.SAFETY_SPECIALIST),
        ("hekim", "Eyas Hekim", f"eyas.hekim.{stamp}@test.com", ProfessionalType.WORKPLACE_PHYSICIAN),
    ):
        professional = IsgProfessional(
            osgb_id=osgb.id,
            full_name=full_name,
            email=email,
            professional_type=professional_type,
            is_active=True,
        )
        db.add(professional)
        db.flush()
        professionals[key] = professional
        db.add(
            WorkplaceAssignment(
                osgb_id=osgb.id,
                company_id=company.id,
                professional_id=professional.id,
                professional_type=professional_type,
                start_date=date.today() - timedelta(days=1),
                status=AssignmentStatus.ACTIVE,
            )
        )

    def user(email: str, role: UserRole, name: str) -> User:
        u = User(
            email=email,
            full_name=name,
            hashed_password=get_password_hash("TestPass123!"),
            role=role,
            company_id=company.id if role != UserRole.COMPANY_ADMIN else None,
            osgb_id=osgb.id,
            is_active=True,
            mfa_enabled=True,
        )
        db.add(u)
        db.flush()
        return u

    uzman = user(f"eyas.uzman.{stamp}@test.com", UserRole.SAFETY_SPECIALIST, "Eyas Uzman")
    hekim = user(f"eyas.hekim.{stamp}@test.com", UserRole.WORKPLACE_PHYSICIAN, "Eyas Hekim")
    isveren = user(f"eyas.isveren.{stamp}@test.com", UserRole.COMPANY_ADMIN, "Eyas Isveren")
    db.commit()
    return company, uzman, hekim, isveren


def test_eyas_flag_helper(monkeypatch):
    monkeypatch.setattr(settings, "eyas_digital_approval_force_off", True)
    monkeypatch.setattr(settings, "eyas_digital_approval_enabled", True)
    assert eyas_digital_approval_active() is False
    monkeypatch.setattr(settings, "eyas_digital_approval_force_off", False)
    monkeypatch.setattr(settings, "eyas_digital_approval_enabled", False)
    assert eyas_digital_approval_active() is False
    monkeypatch.setattr(settings, "eyas_digital_approval_enabled", True)
    assert eyas_digital_approval_active() is True


def test_sequential_approve_and_lock(db, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "eyas_digital_approval_force_off", False)
    monkeypatch.setattr(settings, "eyas_digital_approval_enabled", True)
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    company, uzman, hekim, isveren = _mk_users(db)
    wf = svc.create_workflow(
        db,
        user=uzman,
        company_id=company.id,
        title="Risk Dijital Onay",
        document_kind="risk",
        steps=[
            {"assignee_user_id": uzman.id, "role_label": "İSG Uzmanı"},
            {"assignee_user_id": hekim.id, "role_label": "İşyeri Hekimi"},
            {"assignee_user_id": isveren.id, "role_label": "İşveren / vekili"},
        ],
        ip="127.0.0.1",
        user_agent="pytest",
    )
    assert wf.status == "in_progress"
    assert wf.current_step_order == 1

    with pytest.raises(HTTPException) as early:
        svc.decide_step(db, workflow_id=wf.id, user=hekim, approve=True, ip="1.1.1.1")
    assert early.value.status_code == 403

    svc.decide_step(db, workflow_id=wf.id, user=uzman, approve=True, ip="10.0.0.1", user_agent="ua1")
    db.refresh(wf)
    assert wf.current_step_order == 2

    svc.decide_step(db, workflow_id=wf.id, user=hekim, approve=True, ip="10.0.0.2")
    db.refresh(wf)
    assert wf.current_step_order == 3

    svc.decide_step(db, workflow_id=wf.id, user=isveren, approve=True, ip="10.0.0.3")
    db.refresh(wf)
    assert wf.status == "locked"
    assert wf.locked_at is not None
    assert wf.archive_path


def test_mfa_required(db, monkeypatch):
    monkeypatch.setattr(settings, "eyas_digital_approval_force_off", False)
    monkeypatch.setattr(settings, "eyas_digital_approval_enabled", True)
    company, uzman, hekim, isveren = _mk_users(db)
    uzman.mfa_enabled = False
    db.commit()
    wf = svc.create_workflow(
        db,
        user=uzman,
        company_id=company.id,
        title="MFA Test",
        document_kind="risk",
        steps=[{"assignee_user_id": uzman.id, "role_label": "İSG Uzmanı"}],
    )
    with pytest.raises(HTTPException) as exc:
        svc.decide_step(db, workflow_id=wf.id, user=uzman, approve=True)
    assert exc.value.status_code == 403
    assert "MFA" in str(exc.value.detail)


def test_eyas_router_mounted():
    from app.api import eyas

    assert eyas.router.prefix == "/eyas"
    paths = {getattr(r, "path", None) for r in eyas.router.routes}
    assert "/eyas/meta" in paths
    assert "/eyas/workflows" in paths
    assert "/eyas/inbox" in paths
    assert "/eyas/workflows/{workflow_id}/approve" in paths


def test_document_approvals_untouched():
    from app.api.compliance_registers import da_router

    paths = {getattr(r, "path", None) for r in da_router.routes}
    assert "/document-approvals/{item_id}/approve" in paths
    assert "/document-approvals/{item_id}/record-local-sign" in paths


def test_release_marker_present():
    from app.services.release_status import infra_detail_payload

    markers = infra_detail_payload().get("feature_flags") or infra_detail_payload()
    # markers may be nested
    blob = str(infra_detail_payload())
    assert "eyas_digital_approval" in blob


def test_workplace_documents_missing_risk(db):
    from app.services.eyas_workplace import list_approval_documents

    company, *_ = _mk_users(db)
    catalog = list_approval_documents(db, company.id)
    risk = next(i for i in catalog["items"] if i["source_key"] == "risk:report")
    assert risk["readiness"] == "missing"
    assert "hazır değil" in risk["readiness_detail"].lower() or "yok" in risk["readiness_detail"].lower()
    assert risk["selectable"] is False


def test_workplace_documents_ready_risk(db):
    from app.models.entities import Hazard, HazardCategory, RiskAssessment
    from app.services.eyas_workplace import list_approval_documents, resolve_document

    company, uzman, *_ = _mk_users(db)
    hazard = db.scalar(select(Hazard).limit(1))
    if not hazard:
        cat = db.scalar(select(HazardCategory).limit(1))
        if not cat:
            cat = HazardCategory(name=f"Cat {int(datetime.utcnow().timestamp())}")
            db.add(cat)
            db.flush()
        hazard = Hazard(
            category_id=cat.id,
            code=f"H{int(datetime.utcnow().timestamp()) % 100000}",
            name="Test Hazard",
        )
        db.add(hazard)
        db.flush()
    db.add(
        RiskAssessment(
            risk_code=f"R{int(datetime.utcnow().timestamp())}",
            company_id=company.id,
            hazard_id=hazard.id,
            activity="Test",
            risk_definition="Tanım",
            probability=2,
            severity=2,
            risk_score=4,
            risk_level="Düşük",
            status="Açık",
            created_by_id=uzman.id,
        )
    )
    db.commit()
    catalog = list_approval_documents(db, company.id)
    risk = next(i for i in catalog["items"] if i["source_key"] == "risk:report")
    assert risk["readiness"] == "ready"
    assert risk["selectable"] is True
    resolved = resolve_document(db, company.id, "risk:report")
    assert resolved["kind"] == "risk"


def test_suggested_assignees_chain_labels(db):
    from app.services.eyas_workplace import suggested_assignees

    company, *_ = _mk_users(db)
    out = suggested_assignees(db, company.id)
    labels = [s["role_label"] for s in out["steps"]]
    assert labels == ["İş Güvenliği Uzmanı", "İşyeri Hekimi", "İşveren / vekili"]


def test_eyas_workplace_routes_mounted():
    from app.api import eyas

    paths = {getattr(r, "path", None) for r in eyas.router.routes}
    assert "/eyas/workplaces/{company_id}/documents" in paths
    assert "/eyas/workplaces/{company_id}/assignees" in paths
    assert "/eyas/workflows/{workflow_id}/document" in paths
    assert "/eyas/workflows/{workflow_id}" in paths


def test_soft_delete_workflow(db, monkeypatch):
    monkeypatch.setattr(settings, "eyas_digital_approval_force_off", False)
    monkeypatch.setattr(settings, "eyas_digital_approval_enabled", True)
    company, uzman, hekim, isveren = _mk_users(db)
    wf = svc.create_workflow(
        db,
        user=uzman,
        company_id=company.id,
        title="Silinecek Akış",
        document_kind="risk",
        steps=[
            {"assignee_user_id": uzman.id, "role_label": "İSG Uzmanı"},
            {"assignee_user_id": hekim.id, "role_label": "İşyeri Hekimi"},
            {"assignee_user_id": isveren.id, "role_label": "İşveren / vekili"},
        ],
    )
    deleted = svc.soft_delete_workflow(db, workflow_id=wf.id, user=uzman)
    assert deleted.is_active is False
    assert deleted.status == "cancelled"
