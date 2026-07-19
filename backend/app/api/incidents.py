"""Olay kayıtları API — ramak kala / iş kazası / kök neden / olay DÖF."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.company_access import company_ids_for_query, ensure_company_access
from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import Company, IncidentDof, IncidentEvent, IncidentRootCause, User, UserRole
from app.schemas.incident import (
    IncidentCreate,
    IncidentDofComplete,
    IncidentDofCreate,
    IncidentDofResponse,
    IncidentResponse,
    IncidentUpdate,
    RootCauseResponse,
    RootCauseUpsert,
)
from app.services.incident_meta import (
    EVENT_PREFIX,
    build_auto_warning,
    meta_payload,
    risk_level_for,
)
from app.services.incident_reports import build_incident_pdf

router = APIRouter(prefix="/incidents", tags=["Olay / Ramak Kala"])
EDIT_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN, UserRole.SAFETY_SPECIALIST)


def ensure_access(db: Session, user: User, company_id: int) -> None:
    ensure_company_access(db, user, company_id)


def _apply_scoring(row: IncidentEvent) -> None:
    p = int(row.probability or 0)
    s = int(row.severity or 0)
    score = p * s
    row.risk_score = score
    row.risk_level = risk_level_for(score) if score else None
    row.auto_warning = build_auto_warning(
        event_type=row.event_type,
        injury=bool(row.injury_occurred),
        health_complaint=bool(row.health_complaint),
        medical=bool(row.medical_intervention),
        incapacity=bool(row.work_incapacity_report),
        sgk=bool(row.sgk_reported),
        police=bool(row.police_reported),
    )


def _next_form_no(db: Session, event_type: str) -> str:
    year = datetime.utcnow().year
    prefix = EVENT_PREFIX.get(event_type, "XX")
    count = db.scalar(select(func.count()).select_from(IncidentEvent)) or 0
    code = f"ISG-{prefix}-{year}-{count + 1:04d}"
    while db.scalar(select(IncidentEvent).where(IncidentEvent.form_no == code)):
        count += 1
        code = f"ISG-{prefix}-{year}-{count + 1:04d}"
    return code


def _next_dof_no(db: Session) -> str:
    year = datetime.utcnow().year
    count = db.scalar(select(func.count()).select_from(IncidentDof)) or 0
    code = f"ISG-DOF-{year}-{count + 1:04d}"
    while db.scalar(select(IncidentDof).where(IncidentDof.dof_no == code)):
        count += 1
        code = f"ISG-DOF-{year}-{count + 1:04d}"
    return code


def _load(db: Session, incident_id: int) -> IncidentEvent:
    row = db.scalar(
        select(IncidentEvent)
        .options(selectinload(IncidentEvent.root_cause), selectinload(IncidentEvent.dofs))
        .where(IncidentEvent.id == incident_id)
    )
    if not row:
        raise HTTPException(404, "Olay kaydı bulunamadı.")
    return row


@router.get("/meta")
def incidents_meta(user: User = Depends(get_current_user)):
    return meta_payload()


@router.get("", response_model=list[IncidentResponse])
def list_incidents(
    event_type: str | None = None,
    company_id: int | None = None,
    status: str | None = None,
    q: str | None = Query(None, max_length=120),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(IncidentEvent)
        .options(selectinload(IncidentEvent.root_cause), selectinload(IncidentEvent.dofs))
        .order_by(IncidentEvent.event_date.desc(), IncidentEvent.id.desc())
    )
    company_ids = company_ids_for_query(db, user, company_id)
    if company_ids == []:
        return []
    if company_ids is not None:
        stmt = stmt.where(IncidentEvent.company_id.in_(company_ids))
    if event_type:
        stmt = stmt.where(IncidentEvent.event_type == event_type)
    if status:
        stmt = stmt.where(IncidentEvent.status == status)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                IncidentEvent.form_no.ilike(like),
                IncidentEvent.short_summary.ilike(like),
                IncidentEvent.location.ilike(like),
                IncidentEvent.department.ilike(like),
                IncidentEvent.classification.ilike(like),
            )
        )
    return list(db.scalars(stmt.limit(500)).unique().all())


@router.post("", response_model=IncidentResponse)
def create_incident(
    payload: IncidentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    ensure_access(db, user, payload.company_id)
    if not db.get(Company, payload.company_id):
        raise HTTPException(404, "Firma bulunamadı.")
    values = payload.model_dump()
    recorded = values.pop("recorded_by_name", None) or user.full_name
    row = IncidentEvent(
        **values,
        form_no=_next_form_no(db, payload.event_type),
        recorded_by_name=recorded,
        created_by_id=user.id,
    )
    _apply_scoring(row)
    db.add(row)
    db.commit()
    return _load(db, row.id)


@router.get("/{incident_id}", response_model=IncidentResponse)
def get_incident(
    incident_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = _load(db, incident_id)
    ensure_access(db, user, row.company_id)
    return row


@router.patch("/{incident_id}", response_model=IncidentResponse)
def update_incident(
    incident_id: int,
    payload: IncidentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = _load(db, incident_id)
    ensure_access(db, user, row.company_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    _apply_scoring(row)
    db.commit()
    return _load(db, incident_id)


@router.get("/{incident_id}/report.pdf")
def incident_report_pdf(
    incident_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = _load(db, incident_id)
    ensure_access(db, user, row.company_id)
    company = db.get(Company, row.company_id)
    try:
        pdf = build_incident_pdf(
            company_name=company.name if company else str(row.company_id),
            incident=row,
            root_cause=row.root_cause,
            dofs=row.dofs or [],
        )
    except RuntimeError as exc:
        raise HTTPException(500, str(exc)) from exc
    return StreamingResponse(
        BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="olay-{row.form_no}.pdf"'},
    )


@router.put("/{incident_id}/root-cause", response_model=RootCauseResponse)
def upsert_root_cause(
    incident_id: int,
    payload: RootCauseUpsert,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = _load(db, incident_id)
    ensure_access(db, user, row.company_id)
    if not payload.root_cause_category:
        raise HTTPException(422, "En az bir kök neden kategorisi seçilmelidir.")
    rc = row.root_cause
    if not rc:
        rc = IncidentRootCause(incident_id=row.id)
        db.add(rc)
    for k, v in payload.model_dump().items():
        setattr(rc, k, v)
    db.commit()
    db.refresh(rc)
    return rc


@router.post("/{incident_id}/dofs", response_model=IncidentDofResponse)
def add_incident_dof(
    incident_id: int,
    payload: IncidentDofCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = _load(db, incident_id)
    ensure_access(db, user, row.company_id)
    dof = IncidentDof(
        dof_no=_next_dof_no(db),
        incident_id=row.id,
        finding=payload.finding,
        root_cause=payload.root_cause,
        corrective_action=payload.corrective_action,
        preventive_action=payload.preventive_action,
        responsible_person=payload.responsible_person,
        term_date=payload.term_date,
        priority=payload.priority,
        created_by_id=user.id,
    )
    db.add(dof)
    db.commit()
    db.refresh(dof)
    return dof


@router.post("/{incident_id}/dofs/{dof_id}/complete", response_model=IncidentDofResponse)
def complete_incident_dof(
    incident_id: int,
    dof_id: int,
    payload: IncidentDofComplete = IncidentDofComplete(),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = _load(db, incident_id)
    ensure_access(db, user, row.company_id)
    dof = db.get(IncidentDof, dof_id)
    if not dof or dof.incident_id != incident_id:
        raise HTTPException(404, "Olay DÖF kaydı bulunamadı.")
    dof.status = "Tamamlandı"
    dof.completion_date = date.today()
    if payload.effectiveness_note:
        dof.effectiveness_note = payload.effectiveness_note
    if payload.close_approval:
        dof.close_approval = payload.close_approval
    db.commit()
    db.refresh(dof)
    return dof
