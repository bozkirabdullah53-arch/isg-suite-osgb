"""Global-admin cleanup endpoint for detached/orphan user accounts."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.entities import User, UserRole
from app.services.audit import add_audit_log
from app.services.user_retirement import anonymize_orphan_user, orphan_account_state

router = APIRouter(prefix="/eisa/users", tags=["EİSA Yetim Kullanıcı Temizliği"])


class OrphanUserCleanupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)


@router.post("/cleanup-orphan")
def cleanup_orphan_user(
    payload: OrphanUserCleanupRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    email = payload.email.strip().lower()
    target = db.scalar(select(User).where(func.lower(User.email) == email).limit(1))
    if not target:
        raise HTTPException(404, "Kullanıcı bulunamadı.")
    if target.id == admin.id or target.role == UserRole.GLOBAL_ADMIN:
        raise HTTPException(403, "Global yönetici hesabı bu işlemle temizlenemez.")

    state = orphan_account_state(db, target)
    if not bool(state["eligible"]):
        raise HTTPException(
            409,
            {
                "code": "user_not_orphan",
                "message": "Bu hesap aktif veya hâlâ bir OSGB/işyeri/profesyonel/üyelik kapsamına bağlı; kalıcı yetim temizliği uygulanamaz.",
                "scope_valid": bool(state["scope_valid"]),
            },
        )

    user_id = int(target.id)
    anonymize_orphan_user(db, target)
    add_audit_log(
        db,
        user=admin,
        action="orphan_user_retired",
        module="eisa",
        entity_type="user",
        entity_id=str(user_id),
        description=f"Yetim kullanıcı hesabı anonimleştirilerek kalıcı olarak emekliye ayrıldı (kullanıcı #{user_id}).",
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    return {
        "ok": True,
        "user_id": user_id,
        "message": "Yetim hesap temizlendi. Eski e-posta artık kullanıcı aramalarında bulunmaz ve yeniden kullanılabilir.",
    }
