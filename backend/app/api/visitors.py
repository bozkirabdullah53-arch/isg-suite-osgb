from __future__ import annotations

import hashlib
import secrets
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.company_access import ensure_company_access
from app.api.deps import require_roles
from app.core.database import get_db
from app.models.entities import AuditLog, User, UserRole
from app.models.visitor import VisitorPass
from app.schemas.visitor import VisitorPassCreate

router = APIRouter(prefix="/visitors", tags=["Ziyaretçiler"])
READ_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN, UserRole.SAFETY_SPECIALIST)
EDIT_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN, UserRole.SAFETY_SPECIALIST)


def _load(db: Session, user: User, pass_id: int) -> VisitorPass:
    row = db.get(VisitorPass, pass_id)
    if not row:
        raise HTTPException(404, "Ziyaretçi geçişi bulunamadı.")
    ensure_company_access(db, user, row.company_id)
    return row


def _payload(row: VisitorPass, token: str | None = None) -> dict:
    return {"id": row.id, "company_id": row.company_id, "full_name": row.full_name, "organization": row.organization, "phone": row.phone, "purpose": row.purpose, "valid_from": row.valid_from, "valid_until": row.valid_until, "status": row.status, "checked_in_at": row.checked_in_at, "checked_out_at": row.checked_out_at, "notes": row.notes, "qr_token": token}


def _audit(db: Session, user: User, row: VisitorPass, action: str, description: str) -> None:
    db.add(AuditLog(user_id=user.id, company_id=row.company_id, action=action, entity_type="visitor_pass", entity_id=str(row.id), description=description[:1200], module="visitor"))


@router.get("")
def list_visitors(company_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    if company_id:
        ensure_company_access(db, user, company_id)
    stmt = select(VisitorPass).order_by(VisitorPass.created_at.desc())
    if company_id:
        stmt = stmt.where(VisitorPass.company_id == company_id)
    return {"items": [_payload(row) for row in db.scalars(stmt).all()]}


@router.post("")
def create_visitor(payload: VisitorPassCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    ensure_company_access(db, user, payload.company_id)
    token = secrets.token_urlsafe(24)
    row = VisitorPass(company_id=payload.company_id, full_name=payload.full_name, organization=payload.organization, phone=payload.phone, purpose=payload.purpose, valid_from=payload.valid_from, valid_until=payload.valid_until, token_hash=hashlib.sha256(token.encode()).hexdigest(), created_by_id=user.id, notes=payload.notes)
    db.add(row); db.flush(); _audit(db, user, row, "visitor_pass_created", "Ziyaretçi geçişi oluşturuldu."); db.commit(); db.refresh(row)
    return _payload(row, token)


@router.post("/{pass_id}/check-in")
def check_in(pass_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    row = _load(db, user, pass_id)
    now = datetime.utcnow()
    if row.status != "issued" or now < row.valid_from or now > row.valid_until:
        raise HTTPException(409, "Ziyaretçi geçişi geçerli değil veya zaten kullanıldı.")
    row.status = "inside"; row.checked_in_at = now; _audit(db, user, row, "visitor_checked_in", "Ziyaretçi saha girişine alındı."); db.commit()
    return _payload(row)


@router.post("/{pass_id}/check-out")
def check_out(pass_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    row = _load(db, user, pass_id)
    if row.status != "inside":
        raise HTTPException(409, "Ziyaretçi içeride görünmüyor.")
    row.status = "used"; row.checked_out_at = datetime.utcnow(); _audit(db, user, row, "visitor_checked_out", "Ziyaretçi saha çıkışı yapıldı."); db.commit()
    return _payload(row)


@router.post("/redeem/{token}/check-in")
def redeem_check_in(token: str, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    row = db.scalar(select(VisitorPass).where(VisitorPass.token_hash == token_hash))
    if not row:
        raise HTTPException(404, "Geçersiz ziyaretçi QR kodu.")
    ensure_company_access(db, user, row.company_id)
    return check_in(row.id, db, user)
