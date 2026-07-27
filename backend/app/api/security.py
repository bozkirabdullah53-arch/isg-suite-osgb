from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_mfa_setup_user, require_roles
from app.api.tenant_access import accessible_company_ids_for_admin
from app.core.database import get_db
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.entities import AuditLog, User, UserRole
from app.schemas.security import PasswordChangeRequest
from app.services.audit import add_audit_log
from app.services.auth_security import (
    encrypt_secret,
    generate_recovery_codes,
    get_mfa_secret,
)

router = APIRouter(prefix="/security", tags=["Güvenlik"])


class MfaEnableRequest(BaseModel):
    code: str = Field(min_length=6, max_length=16)


class MfaDisableRequest(BaseModel):
    password: str = Field(min_length=1)
    code: str = Field(min_length=6, max_length=16)


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
    from app.services.token_revoke import bump_token_version

    bump_token_version(user)
    add_audit_log(
        db,
        user=user,
        action="password_changed",
        entity_type="user",
        entity_id=str(user.id),
        description="Kullanıcı şifresini değiştirdi.",
        ip_address=request.client.host if request.client else None,
        module="security",
    )
    db.commit()
    return {"message": "Şifre başarıyla değiştirildi. Diğer oturumlar kapatıldı."}


@router.get("/mfa/status")
def mfa_status(user: User = Depends(get_mfa_setup_user)):
    from app.services.auth_security import role_requires_mfa

    return {
        "mfa_enabled": bool(getattr(user, "mfa_enabled", False)),
        "mfa_required": role_requires_mfa(user.role),
    }


@router.post("/mfa/setup")
def mfa_setup(
    db: Session = Depends(get_db),
    user: User = Depends(get_mfa_setup_user),
):
    import pyotp

    if getattr(user, "mfa_enabled", False):
        raise HTTPException(status_code=400, detail="MFA zaten açık. Önce kapatın.")
    existing = get_mfa_secret(user)
    if existing:
        secret = existing
    else:
        secret = pyotp.random_base32()
        user.mfa_secret_encrypted = encrypt_secret(secret)
        user.mfa_enabled = False
        db.commit()
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="ISG Suite")
    return {"secret": secret, "otpauth_uri": uri, "pending": not getattr(user, "mfa_enabled", False)}


@router.post("/mfa/enable")
def mfa_enable(
    payload: MfaEnableRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_mfa_setup_user),
):
    import pyotp

    secret = get_mfa_secret(user)
    if not secret:
        raise HTTPException(status_code=400, detail="Önce MFA kurulumu başlatın.")
    code = (payload.code or "").strip().replace(" ", "")
    if not pyotp.TOTP(secret).verify(code, valid_window=2):
        raise HTTPException(status_code=400, detail="Doğrulama kodu hatalı.")
    codes, hashes_json = generate_recovery_codes()
    user.mfa_enabled = True
    user.mfa_recovery_hashes = hashes_json
    add_audit_log(
        db,
        user=user,
        action="mfa_enabled",
        entity_type="user",
        entity_id=str(user.id),
        description="MFA etkinleştirildi",
        ip_address=request.client.host if request.client else None,
        module="security",
    )
    db.commit()
    # Kurulum token'ından sonra tam erişim ver
    return {
        "message": "MFA etkinleştirildi.",
        "recovery_codes": codes,
        "access_token": create_access_token(
            str(user.id), token_version=getattr(user, "token_version", 0) or 0
        ),
        "token_type": "bearer",
    }


@router.post("/mfa/disable")
def mfa_disable(
    payload: MfaDisableRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    import pyotp

    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Şifre hatalı.")
    secret = get_mfa_secret(user)
    code = (payload.code or "").strip().replace(" ", "")
    ok = bool(secret and pyotp.TOTP(secret).verify(code, valid_window=2))
    if not ok:
        raise HTTPException(status_code=400, detail="Doğrulama kodu hatalı.")
    user.mfa_enabled = False
    user.mfa_secret_encrypted = None
    user.mfa_recovery_hashes = None
    add_audit_log(
        db,
        user=user,
        action="mfa_disabled",
        entity_type="user",
        entity_id=str(user.id),
        description="MFA kapatıldı",
        ip_address=request.client.host if request.client else None,
        module="security",
    )
    db.commit()
    return {"message": "MFA kapatıldı."}


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
