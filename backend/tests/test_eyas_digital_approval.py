"""Eyas Digital Approval — sıralı onay, MFA, bayrak kill-switch."""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import eyas_digital_approval_active, settings
from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.entities import Company, OsgbOrganization, User, UserRole
from app.services import eyas_approval as svc


@pytest.fixture()
def db():
    session = SessionLocal()
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
