from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.company_access import company_ids_for_query, ensure_company_access
from app.api.deps import require_roles
from app.core.database import get_db
from app.models.entities import Company, Employee, HealthRecord, Prescription, PrescriptionItem, PrescriptionStatus, User, UserRole
from app.schemas.prescriptions import PrescriptionCancel, PrescriptionCreate, PrescriptionResponse, PrescriptionUpdate
from app.services.health_field_crypto import decrypt_field, encrypt_field

router = APIRouter(prefix="/prescriptions", tags=["e-Reçete"])
PHYSICIAN_ONLY = (UserRole.WORKPLACE_PHYSICIAN,)
READ_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.WORKPLACE_PHYSICIAN)


def _to_response(db: Session, row: Prescription) -> PrescriptionResponse:
    employee = db.get(Employee, row.employee_id)
    company = db.get(Company, row.company_id)
    physician = db.get(User, row.physician_user_id)
    items = list(db.scalars(select(PrescriptionItem).where(PrescriptionItem.prescription_id == row.id).order_by(PrescriptionItem.sort_order, PrescriptionItem.id)).all())
    data = PrescriptionResponse.model_validate(row)
    data.employee_name = employee.full_name if employee else None
    data.company_name = company.name if company else None
    data.physician_name = physician.full_name if physician else None
    data.diagnosis_text = decrypt_field(row.diagnosis_text)
    data.clinical_note = decrypt_field(row.clinical_note)
    data.cancel_reason = decrypt_field(row.cancel_reason)
    data.items = items
    data.medula_configured = False
    return data


def _owned_draft(db: Session, prescription_id: int, user: User) -> Prescription:
    row = db.get(Prescription, prescription_id)
    if not row:
        raise HTTPException(status_code=404, detail="Reçete bulunamadı.")
    ensure_company_access(db, user, row.company_id)
    if row.physician_user_id != user.id:
        raise HTTPException(status_code=403, detail="Bu reçeteyi yalnızca reçeteyi yazan işyeri hekimi değiştirebilir.")
    if row.status != PrescriptionStatus.DRAFT:
        raise HTTPException(status_code=409, detail="Yalnızca taslak reçeteler değiştirilebilir.")
    return row


@router.get("", response_model=list[PrescriptionResponse])
def list_prescriptions(company_id: int | None = None, employee_id: int | None = None, status: PrescriptionStatus | None = None, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    ids = company_ids_for_query(db, user, company_id)
    query = select(Prescription).order_by(Prescription.prescription_date.desc(), Prescription.id.desc())
    if ids == []:
        return []
    if ids is not None:
        query = query.where(Prescription.company_id.in_(ids))
    if employee_id:
        query = query.where(Prescription.employee_id == employee_id)
    if status:
        query = query.where(Prescription.status == status)
    if user.role == UserRole.WORKPLACE_PHYSICIAN:
        query = query.where(Prescription.physician_user_id == user.id)
    return [_to_response(db, row) for row in db.scalars(query).all()]


@router.post("", response_model=PrescriptionResponse, status_code=201)
def create_prescription(payload: PrescriptionCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*PHYSICIAN_ONLY))):
    ensure_company_access(db, user, payload.company_id)
    employee = db.get(Employee, payload.employee_id)
    if not employee or employee.company_id != payload.company_id or not employee.is_active:
        raise HTTPException(status_code=400, detail="Çalışan seçilen işyerine ait ve aktif olmalıdır.")
    if payload.health_record_id is not None:
        record = db.get(HealthRecord, payload.health_record_id)
        if not record or record.company_id != payload.company_id or record.employee_id != payload.employee_id:
            raise HTTPException(status_code=400, detail="Muayene kaydı çalışan ve işyeri ile eşleşmiyor.")
    row = Prescription(company_id=payload.company_id, employee_id=payload.employee_id, health_record_id=payload.health_record_id, physician_user_id=user.id, status=PrescriptionStatus.DRAFT, prescription_date=payload.prescription_date, diagnosis_code=payload.diagnosis_code, diagnosis_text=encrypt_field(payload.diagnosis_text), clinical_note=encrypt_field(payload.clinical_note), created_by_id=user.id)
    db.add(row)
    db.flush()
    for item in payload.items:
        db.add(PrescriptionItem(prescription_id=row.id, **item.model_dump()))
    db.commit()
    db.refresh(row)
    return _to_response(db, row)


@router.patch("/{prescription_id}", response_model=PrescriptionResponse)
def update_prescription(prescription_id: int, payload: PrescriptionUpdate, db: Session = Depends(get_db), user: User = Depends(require_roles(*PHYSICIAN_ONLY))):
    row = _owned_draft(db, prescription_id, user)
    data = payload.model_dump(exclude_unset=True)
    items = data.pop("items", None)
    for key, value in data.items():
        if key in {"diagnosis_text", "clinical_note"}:
            value = encrypt_field(value)
        setattr(row, key, value)
    if items is not None:
        db.execute(delete(PrescriptionItem).where(PrescriptionItem.prescription_id == row.id))
        for item in items:
            db.add(PrescriptionItem(prescription_id=row.id, **item))
    row.version += 1
    db.commit()
    db.refresh(row)
    return _to_response(db, row)


@router.post("/{prescription_id}/ready", response_model=PrescriptionResponse)
def mark_ready(prescription_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*PHYSICIAN_ONLY))):
    row = _owned_draft(db, prescription_id, user)
    item_count = len(list(db.scalars(select(PrescriptionItem.id).where(PrescriptionItem.prescription_id == row.id)).all()))
    if item_count < 1:
        raise HTTPException(status_code=409, detail="En az bir ilaç kalemi zorunludur.")
    if not row.diagnosis_code and not decrypt_field(row.diagnosis_text):
        raise HTTPException(status_code=409, detail="Tanı bilgisi zorunludur.")
    row.status = PrescriptionStatus.READY
    row.approved_at = datetime.utcnow()
    row.version += 1
    db.commit()
    db.refresh(row)
    return _to_response(db, row)


@router.post("/{prescription_id}/cancel", response_model=PrescriptionResponse)
def cancel_prescription(prescription_id: int, payload: PrescriptionCancel, db: Session = Depends(get_db), user: User = Depends(require_roles(*PHYSICIAN_ONLY))):
    row = db.get(Prescription, prescription_id)
    if not row:
        raise HTTPException(status_code=404, detail="Reçete bulunamadı.")
    ensure_company_access(db, user, row.company_id)
    if row.physician_user_id != user.id:
        raise HTTPException(status_code=403, detail="Bu reçeteyi yalnızca reçeteyi yazan işyeri hekimi iptal edebilir.")
    if row.status == PrescriptionStatus.CANCELLED:
        return _to_response(db, row)
    if row.status == PrescriptionStatus.APPROVED:
        raise HTTPException(status_code=409, detail="MEDULA tarafından onaylanmış reçete bu ekrandan iptal edilemez.")
    row.status = PrescriptionStatus.CANCELLED
    row.cancelled_at = datetime.utcnow()
    row.cancel_reason = encrypt_field(payload.reason)
    row.version += 1
    db.commit()
    db.refresh(row)
    return _to_response(db, row)


@router.post("/{prescription_id}/submit")
def submit_to_medula(prescription_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*PHYSICIAN_ONLY))):
    row = db.get(Prescription, prescription_id)
    if not row:
        raise HTTPException(status_code=404, detail="Reçete bulunamadı.")
    ensure_company_access(db, user, row.company_id)
    if row.physician_user_id != user.id:
        raise HTTPException(status_code=403, detail="Gönderimi yalnızca reçeteyi yazan işyeri hekimi yapabilir.")
    raise HTTPException(status_code=503, detail="MEDULA bağlantısı henüz yapılandırılmadı. Reçete kaydı güvenle saklandı ancak SGK'ya gönderilmedi.")
