from __future__ import annotations

from datetime import datetime
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.company_access import company_ids_for_query, ensure_company_access
from app.api.deps import require_roles
from app.api.work_permits_phase_a import router as phase_a_router, validate_field_inspection_link
from app.core.database import get_db
from app.models.entities import AuditLog, Company, Employee, IncidentEvent, RiskAssessment, RiskDof, User, UserRole
from app.models.work_permit import WorkPermit, WorkPermitApprover, WorkPermitControl, WorkPermitEmployee
from app.models.contractor import ContractorCompany
from app.schemas.work_permit import WorkPermitControlInput, WorkPermitCreate, WorkPermitExtension, WorkPermitStatusUpdate
from app.services.work_permit_validity import ensure_not_expired_for_activation, ensure_open_window

router = APIRouter(prefix="/work-permits", tags=["Çalışma İzni"])
router.include_router(phase_a_router)
READ_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST, UserRole.OTHER_HEALTH_PERSONNEL)
EDIT_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST, UserRole.OTHER_HEALTH_PERSONNEL)


def _load(db: Session, user: User, permit_id: int) -> WorkPermit:
    row = db.get(WorkPermit, permit_id)
    if not row:
        raise HTTPException(404, "Çalışma izni bulunamadı.")
    ensure_company_access(db, user, row.company_id)
    return row


def _payload(db: Session, row: WorkPermit) -> dict:
    employees = db.scalars(select(WorkPermitEmployee.employee_id).where(WorkPermitEmployee.permit_id == row.id)).all()
    controls = db.scalars(select(WorkPermitControl).where(WorkPermitControl.permit_id == row.id).order_by(WorkPermitControl.control_type)).all()
    approvers = db.scalars(select(WorkPermitApprover).where(WorkPermitApprover.permit_id == row.id).order_by(WorkPermitApprover.step_order)).all()
    return {"id": row.id, "permit_no": row.permit_no, "company_id": row.company_id, "permit_type": row.permit_type, "description": row.description, "location": row.location, "valid_from": row.valid_from, "valid_until": row.valid_until, "status": row.status, "employee_ids": employees, "contractor_id": row.contractor_id, "risk_id": row.risk_id, "incident_id": row.incident_id, "dof_id": row.dof_id, "client_reference": row.client_reference, "notes": row.notes, "opening_checked_at": row.opening_checked_at, "opening_checked_by_id": row.opening_checked_by_id, "closed_at": row.closed_at, "closed_by_id": row.closed_by_id, "approved_by_id": row.approved_by_id, "approved_at": row.approved_at, "approvers": [{"id": item.id, "user_id": item.approver_user_id, "step_order": item.step_order, "status": item.status, "note": item.note, "decided_at": item.decided_at} for item in approvers], "controls": [{"id": item.id, "control_type": item.control_type, "status": item.status, "details": item.details, "measured_value": item.measured_value, "unit": item.unit, "checked_at": item.checked_at} for item in controls], "created_at": row.created_at}


def _audit(db: Session, user: User, company_id: int, action: str, permit_id: int, description: str) -> None:
    db.add(AuditLog(user_id=user.id, company_id=company_id, action=action, entity_type="work_permit", entity_id=str(permit_id), description=description[:1200], module="work_permit"))


@router.get("")
def list_permits(company_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    if company_id:
        ensure_company_access(db, user, company_id)
    company_ids = company_ids_for_query(db, user, company_id)
    if company_ids == []:
        return {"items": []}
    stmt = select(WorkPermit).order_by(WorkPermit.created_at.desc())
    if company_ids is not None:
        stmt = stmt.where(WorkPermit.company_id.in_(company_ids))
    return {"items": [_payload(db, row) for row in db.scalars(stmt).all()]}


@router.get("/meta")
def permit_meta(user: User = Depends(require_roles(*READ_ROLES))):
    return {"types": [{"id": "hot_work", "label": "Sıcak iş"}, {"id": "work_at_height", "label": "Yüksekte çalışma"}, {"id": "confined_space", "label": "Kapalı alan"}, {"id": "electrical", "label": "Elektrik"}, {"id": "general", "label": "Genel"}], "statuses": ["draft", "pending_approval", "active", "suspended", "expired", "closed", "rejected", "cancelled"]}


@router.get("/employees")
def permit_employees(company_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    ensure_company_access(db, user, company_id)
    return {"items": [{"id": row.id, "full_name": row.full_name, "job_title": row.job_title} for row in db.scalars(select(Employee).where(Employee.company_id == company_id, Employee.is_active.is_(True)).order_by(Employee.full_name)).all()]}


@router.get("/approvers")
def permit_approvers(company_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    ensure_company_access(db, user, company_id)
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(404, "İşyeri bulunamadı.")
    rows = db.scalars(select(User).where(User.is_active.is_(True), User.osgb_id == company.osgb_id, User.role.in_((UserRole.SAFETY_SPECIALIST, UserRole.OTHER_HEALTH_PERSONNEL))).order_by(User.full_name)).all()
    return {"items": [{"id": row.id, "full_name": row.full_name, "role": row.role.value} for row in rows]}


@router.post("")
def create_permit(payload: WorkPermitCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    ensure_company_access(db, user, payload.company_id)
    if payload.client_reference and db.scalar(select(WorkPermit).where(WorkPermit.company_id == payload.company_id, WorkPermit.client_reference == payload.client_reference)):
        return _payload(db, db.scalar(select(WorkPermit).where(WorkPermit.company_id == payload.company_id, WorkPermit.client_reference == payload.client_reference)))
    employee_ids = set(db.scalars(select(Employee.id).where(Employee.company_id == payload.company_id, Employee.is_active.is_(True), Employee.id.in_(payload.employee_ids))).all()) if payload.employee_ids else set()
    if employee_ids != set(payload.employee_ids):
        raise HTTPException(422, "Çalışanlardan biri bu işyerine ait değil veya pasif.")
    company = db.get(Company, payload.company_id)
    approver_ids = set(db.scalars(select(User.id).where(User.id.in_(payload.approver_user_ids), User.is_active.is_(True), User.osgb_id == company.osgb_id, User.role.in_((UserRole.SAFETY_SPECIALIST, UserRole.OTHER_HEALTH_PERSONNEL)))).all()) if payload.approver_user_ids and company else set()
    if approver_ids != set(payload.approver_user_ids):
        raise HTTPException(422, "Onaylayan kullanıcılardan biri PTW saha rolünde veya bu OSGB kapsamında değil.")
    for model, field, value in ((RiskAssessment, "id", payload.risk_id), (IncidentEvent, "id", payload.incident_id), (RiskDof, "id", payload.dof_id)):
        if value and not db.scalar(select(model).where(getattr(model, field) == value, model.company_id == payload.company_id)):
            raise HTTPException(422, "Bağlanan kayıt bu işyerine ait değil.")
    validate_field_inspection_link(db, payload)
    if payload.contractor_id and not db.scalar(select(ContractorCompany.id).where(ContractorCompany.id == payload.contractor_id, ContractorCompany.company_id == payload.company_id, ContractorCompany.is_active.is_(True))):
        raise HTTPException(422, "Taşeron bu işyerine ait değil veya pasif.")
    row = WorkPermit(company_id=payload.company_id, permit_no=f"PTW-{datetime.utcnow():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}", permit_type=payload.permit_type, description=payload.description, location=payload.location, valid_from=payload.valid_from, valid_until=payload.valid_until, risk_id=payload.risk_id, incident_id=payload.incident_id, dof_id=payload.dof_id, field_inspection_id=payload.field_inspection_id, contractor_id=payload.contractor_id, client_reference=payload.client_reference, notes=payload.notes, created_by_id=user.id)
    db.add(row); db.flush()
    db.add_all([WorkPermitEmployee(permit_id=row.id, employee_id=employee_id) for employee_id in payload.employee_ids])
    db.add_all([WorkPermitApprover(permit_id=row.id, approver_user_id=approver_id, step_order=index) for index, approver_id in enumerate(payload.approver_user_ids, start=1)])
    _audit(db, user, row.company_id, "work_permit_created", row.id, "Çalışma izni oluşturuldu.")
    db.commit(); db.refresh(row)
    return _payload(db, row)


@router.get("/{permit_id}")
def get_permit(permit_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    return _payload(db, _load(db, user, permit_id))


@router.post("/{permit_id}/submit")
def submit_permit(permit_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    row = _load(db, user, permit_id)
    if row.status != "draft": raise HTTPException(409, "Yalnızca taslak izin onaya gönderilebilir.")
    row.status = "pending_approval"; _audit(db, user, row.company_id, "work_permit_submitted", row.id, "Çalışma izni onaya gönderildi."); db.commit()
    return _payload(db, row)


@router.post("/{permit_id}/approve")
def approve_permit(permit_id: int, payload: WorkPermitStatusUpdate, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    row = _load(db, user, permit_id)
    if row.status != "pending_approval": raise HTTPException(409, "İzin onay bekleyen durumda değil.")
    ensure_not_expired_for_activation(row)
    pending = db.scalar(select(WorkPermitApprover).where(WorkPermitApprover.permit_id == row.id, WorkPermitApprover.status == "pending").order_by(WorkPermitApprover.step_order))
    if pending and pending.approver_user_id != user.id:
        raise HTTPException(403, "Bu izin için sıradaki onaylayan siz değilsiniz.")
    if pending:
        pending.status = "approved"; pending.note = payload.note; pending.decided_at = datetime.utcnow()
        next_pending = db.scalar(select(WorkPermitApprover).where(WorkPermitApprover.permit_id == row.id, WorkPermitApprover.status == "pending", WorkPermitApprover.step_order > pending.step_order).order_by(WorkPermitApprover.step_order))
        if next_pending:
            _audit(db, user, row.company_id, "work_permit_step_approved", row.id, "Çalışma izni onay adımı tamamlandı."); db.commit(); return _payload(db, row)
    row.status = "active"; row.approved_by_id = user.id; row.approved_at = datetime.utcnow(); _audit(db, user, row.company_id, "work_permit_approved", row.id, "Çalışma izni onaylandı."); db.commit()
    return _payload(db, row)


@router.post("/{permit_id}/reject")
def reject_permit(permit_id: int, payload: WorkPermitStatusUpdate, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    row = _load(db, user, permit_id)
    if row.status != "pending_approval": raise HTTPException(409, "İzin onay bekleyen durumda değil.")
    pending = db.scalar(select(WorkPermitApprover).where(WorkPermitApprover.permit_id == row.id, WorkPermitApprover.status == "pending").order_by(WorkPermitApprover.step_order))
    if pending and pending.approver_user_id != user.id:
        raise HTTPException(403, "Bu izin için sıradaki onaylayan siz değilsiniz.")
    if pending:
        pending.status = "rejected"; pending.note = payload.note; pending.decided_at = datetime.utcnow()
    row.status = "rejected"; _audit(db, user, row.company_id, "work_permit_rejected", row.id, payload.note or "Çalışma izni reddedildi."); db.commit()
    return _payload(db, row)


@router.post("/{permit_id}/open")
def open_permit(permit_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    row = _load(db, user, permit_id)
    if row.status != "active": raise HTTPException(409, "Yalnızca aktif izin saha açılışına alınabilir.")
    if row.opening_checked_at is not None:
        raise HTTPException(409, "Çalışma izninin saha açılışı zaten yapılmış.")
    ensure_open_window(row)
    if row.contractor_id:
        from app.api.contractors import contractor_eligibility
        eligibility = contractor_eligibility(row.contractor_id, db, user)
        if not eligibility["eligible"]:
            raise HTTPException(409, "Taşeron uygunluk kontrolü başarısız: " + "; ".join(eligibility["reasons"]))
    controls = db.scalars(select(WorkPermitControl).where(WorkPermitControl.permit_id == row.id)).all()
    failed = [item.control_type for item in controls if item.status == "failed"]
    pending = [item.control_type for item in controls if item.status == "pending"]
    opening = next((item for item in controls if item.control_type == "site_opening"), None)
    if failed or pending or (opening and opening.status != "passed"):
        blocked = failed + pending + (["site_opening"] if opening and opening.status != "passed" else [])
        raise HTTPException(409, "PTW açılış kontrolleri tamamlanmadı: " + ", ".join(dict.fromkeys(blocked)))
    row.opening_checked_at = datetime.utcnow(); row.opening_checked_by_id = user.id; _audit(db, user, row.company_id, "work_permit_opened", row.id, "Saha açılış kontrolü yapıldı."); db.commit()
    return _payload(db, row)


@router.post("/{permit_id}/close")
def close_permit(permit_id: int, payload: WorkPermitStatusUpdate, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    row = _load(db, user, permit_id)
    if row.status != "active" or row.opening_checked_at is None: raise HTTPException(409, "İzin saha açılışı yapılmadan kapatılamaz.")
    closing = db.scalar(select(WorkPermitControl).where(WorkPermitControl.permit_id == row.id, WorkPermitControl.control_type == "site_closing"))
    if closing and closing.status != "passed":
        raise HTTPException(409, "Saha kapanış kontrolü uygun olarak tamamlanmalıdır.")
    row.status = "closed"; row.closed_at = datetime.utcnow(); row.closed_by_id = user.id; _audit(db, user, row.company_id, "work_permit_closed", row.id, payload.note or "Saha kapanış kontrolü yapıldı."); db.commit()
    return _payload(db, row)


@router.put("/{permit_id}/controls")
def save_controls(permit_id: int, payload: list[WorkPermitControlInput], db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    row = _load(db, user, permit_id)
    if row.status in {"closed", "rejected", "cancelled"}:
        raise HTTPException(409, "Kapanmış, reddedilmiş veya iptal edilmiş iznin kontrolleri değiştirilemez.")
    allowed = {"loto", "gas_measurement", "ppe", "equipment", "emergency_preparedness", "competency", "site_opening", "site_closing"}
    if any(item.control_type not in allowed for item in payload):
        raise HTTPException(422, "Geçersiz PTW kontrol türü.")
    existing = {item.control_type: item for item in db.scalars(select(WorkPermitControl).where(WorkPermitControl.permit_id == row.id)).all()}
    for item in payload:
        control = existing.get(item.control_type)
        if control is None:
            control = WorkPermitControl(permit_id=row.id, control_type=item.control_type); db.add(control)
        control.status = item.status; control.details = item.details; control.measured_value = item.measured_value; control.unit = item.unit; control.checked_by_id = user.id; control.checked_at = datetime.utcnow()
    _audit(db, user, row.company_id, "work_permit_controls_saved", row.id, "PTW operasyon kontrolleri kaydedildi.")
    db.commit()
    return _payload(db, row)


@router.post("/{permit_id}/suspend")
def suspend_permit(permit_id: int, payload: WorkPermitStatusUpdate, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    row = _load(db, user, permit_id)
    if row.status != "active":
        raise HTTPException(409, "Yalnızca aktif izin askıya alınabilir.")
    row.status = "suspended"; _audit(db, user, row.company_id, "work_permit_suspended", row.id, payload.note or "Çalışma izni askıya alındı."); db.commit()
    return _payload(db, row)


@router.post("/{permit_id}/extend")
def extend_permit(permit_id: int, payload: WorkPermitExtension, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    row = _load(db, user, permit_id)
    if row.status not in {"draft", "pending_approval", "active", "suspended"} or payload.valid_until <= row.valid_until:
        raise HTTPException(422, "İzin yalnızca geçerli bir ileri tarih ile uzatılabilir.")
    row.valid_until = payload.valid_until; _audit(db, user, row.company_id, "work_permit_extended", row.id, payload.note); db.commit()
    return _payload(db, row)