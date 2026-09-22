"""İBYS Değişiklik Talebi API (§3-§5, §8).

Talep açma → doğrulama → onay → uygulama/red akışını yönetir.
4 göz prensibi servis katmanında zorlanır.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.company_access import ensure_company_access
from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import ChangeRequest, User, UserRole
from app.services.audit import request_ip, request_user_agent
from app.services.change_request import (
    ChangeRequestError,
    apply_request,
    approve_request,
    cancel_request,
    create_request,
    events_for_request,
    get_request,
    list_requests,
    reject_request,
    sla_overdue_requests,
    verify_request,
)
from app.services.change_request_apply import ApplyError, apply_change

router = APIRouter(prefix="/change-requests", tags=["Değişiklik Talepleri"])


class ChangeRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_entity_type: str = Field(min_length=2, max_length=80)
    target_entity_id: str | None = Field(default=None, max_length=80)
    field_name: str | None = Field(default=None, max_length=80)
    old_value: str | None = Field(default=None, max_length=4000)
    requested_value: str = Field(min_length=1, max_length=4000)
    justification: str = Field(min_length=10, max_length=4000)
    company_id: int | None = None
    requester_type: str = Field(default="employer", max_length=20)
    channel: str = Field(default="platform", max_length=20)
    attachment_path: str | None = Field(default=None, max_length=500)


class ChangeRequestDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=2000)


class ChangeRequestReject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=10, max_length=2000)


class DataSubjectRequest(BaseModel):
    """KVKK md.11 veri sahibi başvurusu."""

    model_config = ConfigDict(extra="forbid")

    request_kind: str = Field(pattern="^(access|rectification|erasure|portability)$")
    company_id: int
    employee_id: int | None = None
    target_entity_type: str = Field(default="employee", max_length=80)
    target_entity_id: str | None = Field(default=None, max_length=80)
    field_name: str | None = Field(default=None, max_length=80)
    old_value: str | None = Field(default=None, max_length=4000)
    requested_value: str = Field(default="-", max_length=4000)
    justification: str = Field(min_length=10, max_length=4000)
    channel: str = Field(default="platform", max_length=20)
    verification_method: str | None = Field(default=None, max_length=40)


class ChangeRequestResponse(BaseModel):
    id: int
    request_no: str
    company_id: int | None
    requested_by_user_id: int | None
    requester_type: str
    channel: str
    request_kind: str | None = None
    identity_verified: bool = False
    verification_method: str | None = None
    target_entity_type: str
    target_entity_id: str | None
    field_name: str | None
    old_value: str | None
    requested_value: str
    justification: str
    status: str
    verified_by_id: int | None
    verified_at: datetime | None
    approved_by_id: int | None
    approved_at: datetime | None
    applied_by_id: int | None
    applied_at: datetime | None
    rejected_by_id: int | None
    rejected_at: datetime | None
    rejection_reason: str | None
    sla_due_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


def _response(row: ChangeRequest) -> ChangeRequestResponse:
    return ChangeRequestResponse.model_validate(row)


def _assert_can_view(db: Session, user: User, row: ChangeRequest) -> None:
    if user.role == UserRole.GLOBAL_ADMIN:
        return
    if row.requested_by_user_id == user.id:
        return
    if user.company_id is not None and row.company_id == user.company_id:
        return
    raise HTTPException(403, "Bu talebe erişemezsiniz.")


def _run(action):
    try:
        return action()
    except ChangeRequestError:
        raise
    except ApplyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("", response_model=ChangeRequestResponse)
def create(
    payload: ChangeRequestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Yeni değişiklik talebi açar (kimliği doğrulanmış kanal)."""
    if payload.company_id is not None:
        ensure_company_access(db, user, payload.company_id)
    return _response(_run(lambda: create_request(db, user=user, payload=payload.model_dump())))


@router.get("", response_model=list[ChangeRequestResponse])
def listing(
    status: str | None = Query(None),
    company_id: int | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = _run(lambda: list_requests(db, user=user, status=status, company_id=company_id))
    return [_response(row) for row in rows]


@router.get("/sla-overdue", response_model=list[ChangeRequestResponse])
def sla_overdue(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    """SLA süresi geçmiş açık talepler (§5.5)."""
    rows = sla_overdue_requests(db)
    if user.role != UserRole.GLOBAL_ADMIN and user.company_id is not None:
        rows = [row for row in rows if row.company_id == user.company_id]
    return [_response(row) for row in rows]


@router.get("/{request_id}")
def detail(
    request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = _run(lambda: get_request(db, request_id))
    _assert_can_view(db, user, row)
    events = events_for_request(db, request_id)
    return {
        **_response(row).model_dump(),
        "events": [
            {
                "id": event.id,
                "from_status": event.from_status,
                "to_status": event.to_status,
                "actor_user_id": event.actor_user_id,
                "note": event.note,
                "created_at": event.created_at,
            }
            for event in events
        ],
    }


@router.post("/{request_id}/verify", response_model=ChangeRequestResponse)
def verify(
    request_id: int,
    payload: ChangeRequestDecision,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    row = _run(lambda: get_request(db, request_id))
    if row.company_id is not None:
        ensure_company_access(db, user, row.company_id)
    _ = request_ip(request), request_user_agent(request)
    return _response(_run(lambda: verify_request(db, request_id=request_id, user=user, note=payload.note)))


@router.post("/{request_id}/approve", response_model=ChangeRequestResponse)
def approve(
    request_id: int,
    payload: ChangeRequestDecision,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    """Onay yalnızca global yöneticiye açıktır (4 göz)."""
    return _response(_run(lambda: approve_request(db, request_id=request_id, user=user, note=payload.note)))


@router.post("/{request_id}/reject", response_model=ChangeRequestResponse)
def reject(
    request_id: int,
    payload: ChangeRequestReject,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    row = _run(lambda: get_request(db, request_id))
    if row.company_id is not None:
        ensure_company_access(db, user, row.company_id)
    return _response(_run(lambda: reject_request(db, request_id=request_id, user=user, reason=payload.reason)))


@router.post("/{request_id}/apply", response_model=ChangeRequestResponse)
def apply(
    request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    """Onaylı talebi gerçek kayda uygular (beyaz liste + çakışma kontrolü)."""
    return _response(
        _run(lambda: apply_request(db, request_id=request_id, user=user, applier=apply_change))
    )


@router.post("/{request_id}/cancel", response_model=ChangeRequestResponse)
def cancel(
    request_id: int,
    payload: ChangeRequestDecision,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = _run(lambda: get_request(db, request_id))
    if user.role != UserRole.GLOBAL_ADMIN and row.requested_by_user_id != user.id:
        raise HTTPException(403, "Yalnızca talebi açan kişi iptal edebilir.")
    return _response(_run(lambda: cancel_request(db, request_id=request_id, user=user, note=payload.note)))


@router.post("/data-subject", response_model=ChangeRequestResponse)
def create_data_subject_request(
    payload: DataSubjectRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """KVKK md.11 veri sahibi başvurusu (erişim/düzeltme/silme/taşınabilirlik)."""
    ensure_company_access(db, user, payload.company_id)
    data = payload.model_dump()
    data["requester_type"] = "data_subject"
    data["target_entity_type"] = data.get("target_entity_type") or "employee"
    if data.get("target_entity_id") is None and data.get("employee_id") is not None:
        data["target_entity_id"] = str(data["employee_id"])
    return _response(_run(lambda: create_request(db, user=user, payload=data)))


@router.post("/{request_id}/verify-identity", response_model=ChangeRequestResponse)
def verify_identity(
    request_id: int,
    payload: ChangeRequestDecision,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    """Veri sahibinin kimliğini doğrular (§3.2) ve talebi doğrulanmış işaretler."""
    row = _run(lambda: get_request(db, request_id))
    if row.company_id is not None:
        ensure_company_access(db, user, row.company_id)
    row.identity_verified = True
    row.verification_method = (payload.note or "kayitli-yetkili-eslesmesi")[:40]
    db.commit()
    return _response(_run(lambda: verify_request(db, request_id=request_id, user=user, note=payload.note)))


@router.get("/{request_id}/export")
def export_data_subject(
    request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    """KVKK md.11 taşınabilirlik/erişim: kişinin verisini JSON olarak verir.

    Yalnızca kimliği doğrulanmış ve doğrulanmış (verified+) talepte çalışır.
    Sağlık serbest metni şifreli hâliyle döner; bu uç düz metin çözmez.
    """
    row = _run(lambda: get_request(db, request_id))
    if row.company_id is not None:
        ensure_company_access(db, user, row.company_id)
    if not row.identity_verified:
        raise HTTPException(403, "Kimlik doğrulanmadan veri paylaşılamaz (KVKK md.11).")
    if row.status not in ("verified", "approved", "applied"):
        raise HTTPException(409, "Talep doğrulanmadan veri paylaşılamaz.")

    from app.models.entities import Employee, HealthRecord

    try:
        employee_id = int(str(row.target_entity_id or ""))
    except ValueError as exc:
        raise HTTPException(422, "Hedef kişi kimliği geçersiz.") from exc
    employee = db.get(Employee, employee_id)
    if employee is None or employee.company_id != row.company_id:
        raise HTTPException(404, "Kişi kaydı bulunamadı.")

    health_rows = list(
        db.scalars(
            select(HealthRecord).where(
                HealthRecord.employee_id == employee_id,
                HealthRecord.company_id == row.company_id,
            )
        ).all()
    )
    payload = {
        "request_no": row.request_no,
        "request_kind": row.request_kind,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "identity_verified": row.identity_verified,
        "person": {
            "id": employee.id,
            "full_name": employee.full_name,
            "national_id_masked": employee.national_id_masked,
            "job_title": employee.job_title,
            "department": employee.department,
            "start_date": employee.start_date.isoformat() if employee.start_date else None,
            "exit_date": employee.exit_date.isoformat() if employee.exit_date else None,
            "is_active": employee.is_active,
        },
        "health_records": [
            {
                "id": record.id,
                "record_type": record.record_type.value if hasattr(record.record_type, "value") else record.record_type,
                "examination_date": record.examination_date.isoformat() if record.examination_date else None,
                "fitness_status": record.fitness_status.value
                if hasattr(record.fitness_status, "value")
                else record.fitness_status,
                # Sağlık serbest metni şifreli (enc:v1:) olarak döner; uç çözmez.
                "summary_encrypted": record.summary,
                "confidential_note_encrypted": record.confidential_note,
            }
            for record in health_rows
        ],
    }
    return payload
