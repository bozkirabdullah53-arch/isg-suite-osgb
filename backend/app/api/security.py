from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.api.tenant_access import accessible_company_ids_for_admin
from app.core.database import get_db
from app.core.security import get_password_hash, verify_password
from app.models.entities import AuditLog, User, UserRole
from app.schemas.security import PasswordChangeRequest
from app.services.audit import add_audit_log

router = APIRouter(prefix="/security", tags=["Güvenlik"])


@router.post("/change-password")
def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Mevcut şifre hatalı.")
    if verify_password(payload.new_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Yeni şifre mevcut şifreyle aynı olamaz.")
    user.hashed_password = get_password_hash(payload.new_password)
    add_audit_log(
        db,
        user=user,
        action="password_changed",
        entity_type="user",
        entity_id=str(user.id),
        description="Kullanıcı şifresini değiştirdi.",
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return {"message": "Şifre başarıyla değiştirildi."}


@router.get("/audit-logs")
def list_audit_logs(
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    query = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(min(limit, 500))
    if user.role != UserRole.GLOBAL_ADMIN:
        company_ids = accessible_company_ids_for_admin(db, user)
        if not company_ids:
            # NULL company_id sızıntısını engelle — kapsam yoksa boş
            query = query.where(AuditLog.id == -1)
        else:
            query = query.where(AuditLog.company_id.in_(company_ids))
    rows = db.scalars(query).all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "company_id": r.company_id,
            "action": r.action,
            "module": r.module,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "description": r.description,
            "old_value": r.old_value,
            "new_value": r.new_value,
            "ip_address": r.ip_address,
            "created_at": r.created_at,
        }
        for r in rows
    ]
