"""Eyas Digital Approval API — bayrakla anında kapatılabilir."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.company_access import company_ids_for_query, ensure_company_access
from app.api.deps import get_current_user, require_roles
from app.core.config import eyas_digital_approval_active
from app.core.database import get_db
from app.models.entities import EyasEvent, EyasStep, EyasWorkflow, User, UserRole
from app.schemas.eyas import (
    EyasDecideBody,
    EyasEventOut,
    EyasMetaOut,
    EyasStepOut,
    EyasWorkflowCreate,
    EyasWorkflowOut,
)
from app.services import eyas_approval as svc

router = APIRouter(prefix="/eyas", tags=["Eyas Digital Approval"])

CREATE_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST)
VIEW_ROLES = (
    UserRole.GLOBAL_ADMIN,
    UserRole.SAFETY_SPECIALIST,
    UserRole.WORKPLACE_PHYSICIAN,
    UserRole.COMPANY_ADMIN,
)


def _require_eyas() -> None:
    if not eyas_digital_approval_active():
        raise HTTPException(
            503,
            "Eyas Digital Approval kapalı (EYAS_DIGITAL_APPROVAL_FORCE_OFF veya ENABLED=false).",
        )


def _client_ip(request: Request) -> str | None:
    xff = (request.headers.get("x-forwarded-for") or "").strip()
    if xff:
        return xff.split(",")[0].strip()[:64]
    if request.client:
        return (request.client.host or "")[:64] or None
    return None


def _ua(request: Request) -> str | None:
    return (request.headers.get("user-agent") or "")[:500] or None


def _assignee_name(db: Session, user_id: int) -> str | None:
    u = db.get(User, user_id)
    return u.full_name if u else None


def _step_out(db: Session, step: EyasStep) -> EyasStepOut:
    return EyasStepOut(
        id=step.id,
        workflow_id=step.workflow_id,
        company_id=step.company_id,
        step_order=step.step_order,
        assignee_user_id=step.assignee_user_id,
        assignee_name=_assignee_name(db, step.assignee_user_id),
        role_label=step.role_label,
        status=step.status,
        decided_at=step.decided_at,
        ip_address=step.ip_address,
        user_agent=step.user_agent,
        device_note=step.device_note,
        note=step.note,
        created_at=step.created_at,
    )


def _wf_out(db: Session, wf: EyasWorkflow) -> EyasWorkflowOut:
    steps = svc.list_steps(db, wf.id)
    return EyasWorkflowOut(
        id=wf.id,
        company_id=wf.company_id,
        title=wf.title,
        document_kind=wf.document_kind,
        source_document_id=wf.source_document_id,
        source_sha256=wf.source_sha256,
        status=wf.status,
        current_step_order=wf.current_step_order,
        legal_label=wf.legal_label,
        qes_request_id=wf.qes_request_id,
        archive_path=wf.archive_path,
        locked_at=wf.locked_at,
        created_by_id=wf.created_by_id,
        is_active=wf.is_active,
        created_at=wf.created_at,
        updated_at=wf.updated_at,
        steps=[_step_out(db, s) for s in steps],
    )


@router.get("/meta", response_model=EyasMetaOut)
def meta(user: User = Depends(get_current_user)):
    _ = user
    return EyasMetaOut(enabled=eyas_digital_approval_active())


@router.get("/workflows", response_model=list[EyasWorkflowOut])
def list_workflows(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    _require_eyas()
    ids = company_ids_for_query(db, user, company_id)
    stmt = (
        select(EyasWorkflow)
        .where(EyasWorkflow.is_active.is_(True))
        .order_by(EyasWorkflow.id.desc())
    )
    if ids == []:
        return []
    if ids is not None:
        stmt = stmt.where(EyasWorkflow.company_id.in_(ids))
    # company_admin: kendi oluşturduğu veya adımında olduğu akışlar
    if user.role == UserRole.COMPANY_ADMIN:
        own_ids = {
            s.workflow_id
            for s in db.scalars(
                select(EyasStep).where(EyasStep.assignee_user_id == user.id)
            ).all()
        }
        rows = list(db.scalars(stmt.limit(300)).all())
        rows = [w for w in rows if w.created_by_id == user.id or w.id in own_ids]
        return [_wf_out(db, w) for w in rows[:100]]
    return [_wf_out(db, w) for w in db.scalars(stmt.limit(100)).all()]


@router.get("/inbox", response_model=list[EyasWorkflowOut])
def inbox(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    _require_eyas()
    ids = company_ids_for_query(db, user, None)
    steps = svc.inbox_for_user(db, user, ids)
    out: list[EyasWorkflowOut] = []
    seen: set[int] = set()
    for st in steps:
        if st.workflow_id in seen:
            continue
        wf = db.get(EyasWorkflow, st.workflow_id)
        if wf:
            out.append(_wf_out(db, wf))
            seen.add(wf.id)
    return out


@router.post("/workflows", response_model=EyasWorkflowOut)
def create_workflow(
    payload: EyasWorkflowCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*CREATE_ROLES)),
):
    _require_eyas()
    ensure_company_access(db, user, payload.company_id)
    wf = svc.create_workflow(
        db,
        user=user,
        company_id=payload.company_id,
        title=payload.title,
        document_kind=payload.document_kind,
        steps=[s.model_dump() for s in payload.steps],
        source_document_id=payload.source_document_id,
        source_sha256=payload.source_sha256,
        ip=_client_ip(request),
        user_agent=_ua(request),
    )
    return _wf_out(db, wf)


@router.get("/workflows/{workflow_id}", response_model=EyasWorkflowOut)
def get_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    _require_eyas()
    wf = db.get(EyasWorkflow, workflow_id)
    if not wf or not wf.is_active:
        raise HTTPException(404, "Onay akışı bulunamadı.")
    ensure_company_access(db, user, wf.company_id)
    return _wf_out(db, wf)


@router.get("/workflows/{workflow_id}/events", response_model=list[EyasEventOut])
def list_events(
    workflow_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    _require_eyas()
    wf = db.get(EyasWorkflow, workflow_id)
    if not wf:
        raise HTTPException(404, "Onay akışı bulunamadı.")
    ensure_company_access(db, user, wf.company_id)
    rows = list(
        db.scalars(
            select(EyasEvent).where(EyasEvent.workflow_id == workflow_id).order_by(EyasEvent.id)
        ).all()
    )
    return rows


@router.post("/workflows/{workflow_id}/approve", response_model=EyasWorkflowOut)
def approve(
    workflow_id: int,
    payload: EyasDecideBody,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    _require_eyas()
    wf0 = db.get(EyasWorkflow, workflow_id)
    if not wf0:
        raise HTTPException(404, "Onay akışı bulunamadı.")
    ensure_company_access(db, user, wf0.company_id)
    wf = svc.decide_step(
        db,
        workflow_id=workflow_id,
        user=user,
        approve=True,
        note=payload.note,
        device_note=payload.device_note,
        ip=_client_ip(request),
        user_agent=_ua(request),
    )
    return _wf_out(db, wf)


@router.post("/workflows/{workflow_id}/reject", response_model=EyasWorkflowOut)
def reject(
    workflow_id: int,
    payload: EyasDecideBody,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    _require_eyas()
    wf0 = db.get(EyasWorkflow, workflow_id)
    if not wf0:
        raise HTTPException(404, "Onay akışı bulunamadı.")
    ensure_company_access(db, user, wf0.company_id)
    wf = svc.decide_step(
        db,
        workflow_id=workflow_id,
        user=user,
        approve=False,
        note=payload.note,
        device_note=payload.device_note,
        ip=_client_ip(request),
        user_agent=_ua(request),
    )
    return _wf_out(db, wf)
