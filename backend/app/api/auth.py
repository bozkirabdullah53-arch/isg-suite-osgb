from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import create_access_token, verify_password
from app.models.entities import User
from app.schemas.auth import CurrentUserResponse, LoginRequest, TokenResponse


router = APIRouter(prefix="/auth", tags=["Kimlik Doğrulama"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="E-posta veya şifre hatalı.")
    from app.api.company_access import sync_all_assigned_field_roles, sync_user_from_professional
    # Önce tüm aktif görevlendirmeleri eşle (hekim/uzman/DSP menüleri)
    try:
        sync_all_assigned_field_roles(db)
    except Exception:
        db.rollback()
    user = db.get(User, user.id) or user
    sync_user_from_professional(db, user, commit=True)
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=CurrentUserResponse)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.api.company_access import sync_user_from_professional
    from app.models.entities import UserRole
    from app.services.osgb_subscription import (
        effective_subscription_status,
        get_or_create_subscription,
        resolve_user_osgb_id,
        subscription_allows_write,
    )

    user = sync_user_from_professional(db, user, commit=True)
    is_eisa = user.role == UserRole.GLOBAL_ADMIN
    sub_status = None
    write_ok = True
    if not is_eisa:
        oid = resolve_user_osgb_id(db, user)
        if oid:
            sub = get_or_create_subscription(db, oid)
            eff = effective_subscription_status(sub)
            sub_status = eff.value
            write_ok = subscription_allows_write(sub)
    return CurrentUserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        company_id=user.company_id,
        osgb_id=user.osgb_id,
        is_eisa=is_eisa,
        subscription_write_allowed=write_ok,
        subscription_status=sub_status,
    )
