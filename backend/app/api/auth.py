from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_mfa_challenge_user
from app.core.database import get_db
from app.core.security import create_access_token, verify_password
from app.models.entities import User
from app.schemas.auth import (
    CurrentUserResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MfaVerifyRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.services.auth_security import (
    clear_throttle,
    consume_password_reset,
    create_password_reset,
    create_purpose_token,
    get_mfa_secret,
    is_locked,
    register_failed_login,
    register_success_login,
    role_requires_mfa,
    send_reset_email,
    throttle_login,
    verify_recovery_code,
)
from app.services.audit import add_audit_log

router = APIRouter(prefix="/auth", tags=["Kimlik Doğrulama"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _sync_field(db: Session, user: User) -> User:
    from app.api.company_access import sync_all_assigned_field_roles, sync_user_from_professional

    try:
        sync_all_assigned_field_roles(db)
    except Exception:
        db.rollback()
    user = db.get(User, user.id) or user
    return sync_user_from_professional(db, user, commit=True)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = _client_ip(request)
    email = str(payload.email).strip().lower()
    try:
        throttle_login(email, ip)
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    user = db.scalar(select(User).where(User.email == payload.email))
    if user and is_locked(user):
        register_failed_login(db, user, email=email, ip=ip)
        db.commit()
        raise HTTPException(
            status_code=423,
            detail="Hesap geçici olarak kilitli. Lütfen daha sonra tekrar deneyin.",
        )

    if not user or not verify_password(payload.password, user.hashed_password):
        register_failed_login(db, user, email=email, ip=ip)
        db.commit()
        raise HTTPException(status_code=401, detail="E-posta veya şifre hatalı.")

    if not user.is_active:
        register_failed_login(db, user, email=email, ip=ip)
        db.commit()
        raise HTTPException(status_code=401, detail="Hesap pasif. Yöneticinizle iletişime geçin.")

    user = _sync_field(db, user)
    clear_throttle(email, ip)

    if getattr(user, "mfa_enabled", False):
        register_success_login(db, user, ip=ip)
        db.commit()
        return TokenResponse(
            mfa_required=True,
            mfa_token=create_purpose_token(str(user.id), "mfa_challenge", minutes=10),
        )

    if role_requires_mfa(user.role) and not getattr(user, "mfa_enabled", False):
        register_success_login(db, user, ip=ip)
        db.commit()
        return TokenResponse(
            mfa_setup_required=True,
            mfa_token=create_purpose_token(str(user.id), "mfa_setup", minutes=30),
        )

    register_success_login(db, user, ip=ip)
    db.commit()
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/mfa/verify", response_model=TokenResponse)
def verify_mfa_login(
    payload: MfaVerifyRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_mfa_challenge_user),
):
    import pyotp

    code = (payload.code or "").strip().replace(" ", "")
    secret = get_mfa_secret(user)
    ok = False
    if secret:
        ok = pyotp.TOTP(secret).verify(code, valid_window=1)
    if not ok:
        ok = verify_recovery_code(user, code)
    if not ok:
        add_audit_log(
            db,
            user=user,
            action="mfa_failed",
            entity_type="user",
            entity_id=str(user.id),
            description="MFA doğrulama başarısız",
            ip_address=_client_ip(request),
            module="auth",
        )
        db.commit()
        raise HTTPException(status_code=401, detail="Doğrulama kodu hatalı.")
    add_audit_log(
        db,
        user=user,
        action="mfa_success",
        entity_type="user",
        entity_id=str(user.id),
        description="MFA doğrulama başarılı",
        ip_address=_client_ip(request),
        module="auth",
    )
    db.commit()
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """Her zaman nötr yanıt — kullanıcı varlığını sızdırma."""
    user = db.scalar(select(User).where(User.email == payload.email))
    if user and user.is_active:
        raw = create_password_reset(db, user)
        send_reset_email(user.email, raw)
        add_audit_log(
            db,
            user=user,
            action="password_reset_requested",
            entity_type="user",
            entity_id=str(user.id),
            description="Parola sıfırlama istendi",
            ip_address=_client_ip(request),
            module="auth",
        )
        db.commit()
    return {"message": "Eğer hesap varsa sıfırlama bağlantısı e-posta ile gönderildi."}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)):
    try:
        user = consume_password_reset(db, payload.token, payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    add_audit_log(
        db,
        user=user,
        action="password_reset_completed",
        entity_type="user",
        entity_id=str(user.id),
        description="Parola sıfırlandı",
        ip_address=_client_ip(request),
        module="auth",
    )
    db.commit()
    return {"message": "Şifreniz güncellendi. Giriş yapabilirsiniz."}


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
        mfa_enabled=bool(getattr(user, "mfa_enabled", False)),
        mfa_required=role_requires_mfa(user.role),
    )
