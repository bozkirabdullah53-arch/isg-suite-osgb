"""FAZ A PTW tamamlayıcıları; mevcut work_permits CRUD akışını değiştirmez."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.company_access import ensure_company_access
from app.api.deps import require_roles
from app.core.database import get_db
from app.models.entities import AuditLog, User, UserRole
from app.models.field_inspection import FieldInspection
from app.models.work_permit import WorkPermit
from app.schemas.work_permit import WorkPermitCreate, WorkPermitStatusUpdate

router = APIRouter()
FIELD_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST, UserRole.OTHER_HEALTH_PERSONNEL)


def validate_field_inspection_link(db: Session, payload: WorkPermitCreate) -> None:
    """Nullable saha denetimi bağı yalnız aynı işyerinden olabilir."""
    if not payload.field_inspection_id:
        return
    linked = db.scalar(
        select(FieldInspection.id).where(
            FieldInspection.id == payload.field_inspection_id,
            FieldInspection.company_id == payload.company_id,
            FieldInspection.deleted_at.is_(None),
        )
    )
    if not linked:
        raise HTTPException(422, "Bağlanan saha denetimi bu işyerine ait değil.")


@router.get("/field-inspections")
def permit_field_inspections(
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*FIELD_ROLES)),
):
    ensure_company_access(db, user, company_id)
    rows = db.scalars(
        select(FieldInspection)
        .where(FieldInspection.company_id == company_id, FieldInspection.deleted_at.is_(None))
        .order_by(FieldInspection.inspection_at.desc())
        .limit(100)
    ).all()
    return {
        "items": [
            {
                "id": row.id,
                "inspection_no": row.inspection_no,
                "inspection_date": row.inspection_date,
                "status": row.status,
            }
            for row in rows
        ]
    }


@router.post("/{permit_id}/cancel")
def cancel_permit(
    permit_id: int,
    payload: WorkPermitStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*FIELD_ROLES)),
):
    row = db.get(WorkPermit, permit_id)
    if not row:
        raise HTTPException(404, "Çalışma izni bulunamadı.")
    ensure_company_access(db, user, row.company_id)
    if row.status in {"closed", "rejected", "cancelled"}:
        raise HTTPException(409, "Kapanmış, reddedilmiş veya iptal edilmiş izin tekrar iptal edilemez.")
    row.status = "cancelled"
    row.cancelled_at = datetime.utcnow()
    row.cancelled_by_id = user.id
    row.cancellation_note = payload.note
    db.add(
        AuditLog(
            user_id=user.id,
            company_id=row.company_id,
            action="work_permit_cancelled",
            entity_type="work_permit",
            entity_id=str(row.id),
            description=(payload.note or "Çalışma izni iptal edildi.")[:1200],
            module="work_permit",
        )
    )
    db.commit()
    return {
        "id": row.id,
        "permit_no": row.permit_no,
        "status": row.status,
        "cancelled_at": row.cancelled_at,
        "cancelled_by_id": row.cancelled_by_id,
    }
