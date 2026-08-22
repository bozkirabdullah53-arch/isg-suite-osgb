from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
import jwt
from jwt import InvalidTokenError
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
import logging

from app.api.deps import get_current_user, get_mfa_challenge_user, oauth2_scheme
from app.core.auth_cookies import (
    REFRESH_COOKIE_NAME,
    access_token_ttl_minutes,
    clear_refresh_cookie,
    refresh_cookie_enabled,
    set_refresh_cookie,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.security import ALGORITHM, create_access_token, create_refresh_token, get_password_hash, verify_password
from app.models.entities import (
    IsgProfessional,
    OsgbOrganization,
    OsgbSubscription,
    OsgbSubscriptionPlan,
    ProfessionalType,
    SubscriptionStatus,
    User,
    UserRole,
)
from app.schemas.auth import (
    CurrentUserResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MfaRestartSetupRequest,
    MfaVerifyRequest,
    RegisterRequest,
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
from app.services.access_scope import ensure_login_scope
from app.services.token_revoke import is_jti_revoked, revoke_jti

router = APIRouter(prefix="/auth", tags=["Kimlik Doğrulama"])
logger = logging.getLogger(__name__)


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _sync_field(db: Session, user: User) -> User:
    from app.api.company_access import sync_all_assigned_field_roles, sync_user_from_professional

    try:
        sync_all_assigned_field_roles(db)
    except Exception:
        logger.warning("auth _sync_field: bulk role sync failed", exc_info=True)
        db.rollback()
    user = db.get(User, user.id) or user
    return sync_user_from_professional(db, user, commit=True)


def _issue_access(user: User, response: Response) -> TokenResponse:
    tv = int(getattr(user, "token_version", 0) or 0)
    ttl_min = access_token_ttl_minutes()
    body = TokenResponse(
        access_token=create_access_token(str(user.id), token_version=tv, minutes=ttl_min),
        password_change_required=bool(getattr(user, "password_change_required", False)),
        expires_in=max(60, ttl_min * 60),
    )
    if refresh_cookie_enabled():
        set_refresh_cookie(response, create_refresh_token(str(user.id), token_version=tv))
        body.refresh_cookie = True
    return body


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Mobil uygulamadan bireysel İSG uzmanı hesabı oluşturur.

    Yeni hesap, mevcut tenant kapsam modelini bozmamak için otomatik olarak
    kişisel bir OSGB çalışma alanına ve deneme aboneliğine bağlanır. Böylece
    uzman kaydı oluşmadan token verilmez ve mevcut ``ensure_login_scope``
    güvenlik kontrolü devre dışı bırakılmaz.
    """
    email = str(payload.email).strip().lower()
    full_name = payload.full_name.strip()
    certificate_number = payload.certificate_number.strip()
    if payload.password != payload.password_confirm:
        raise HTTPException(422, "Şifreler aynı değil.")
    if not payload.contract_accepted or not payload.personal_data_accepted:
        raise HTTPException(422, "Kullanım koşulları ve kişisel veri işleme onayı zorunludur.")
    if len(full_name) < 2:
        raise HTTPException(422, "Ad soyad zorunludur.")
    if len(certificate_number) < 3:
        raise HTTPException(422, "İSG sertifika numarası zorunludur.")

    ip = _client_ip(request)
    try:
        throttle_login(f"register:{email}", ip)
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    existing = db.scalar(
        select(User).where(
            or_(func.lower(User.email) == email, func.lower(User.username) == email)
        )
    )
    if existing:
        raise HTTPException(409, "Bu e-posta zaten kayıtlı. Giriş yapın veya şifremi unuttum seçeneğini kullanın.")

    from app.services.eisa_platform import resolved_trial_days
    from app.services.audit import add_audit_log

    now = datetime.utcnow()
    trial_days = resolved_trial_days(db)
    workspace = OsgbOrganization(
        name=f"{full_name} — Bireysel Uzman Çalışma Alanı"[:220],
        authorization_number=f"MOBIL-{uuid4().hex[:12].upper()}",
        email=email,
        phone=(payload.phone or "").strip() or None,
        responsible_manager=full_name,
        is_active=True,
    )
    db.add(workspace)
    db.flush()

    user = User(
        email=email,
        full_name=full_name,
        hashed_password=get_password_hash(payload.password),
        role=UserRole.SAFETY_SPECIALIST,
        osgb_id=workspace.id,
        is_active=True,
    )
    professional = IsgProfessional(
        osgb_id=workspace.id,
        full_name=full_name,
        email=email,
        phone=(payload.phone or "").strip() or None,
        professional_type=ProfessionalType.SAFETY_SPECIALIST,
        certificate_class=payload.certificate_class,
        certificate_number=certificate_number,
        is_active=True,
    )
    subscription = OsgbSubscription(
        osgb_id=workspace.id,
        plan=OsgbSubscriptionPlan.STANDARD,
        status=SubscriptionStatus.TRIAL,
        trial_ends_at=now + timedelta(days=trial_days),
        max_users=1,
        max_workplaces=50,
    )
    db.add_all([user, professional, subscription])
    db.flush()
    add_audit_log(
        db,
        user=user,
        action="self_register",
        entity_type="user",
        entity_id=str(user.id),
        description="Mobil uygulamadan bireysel İSG uzmanı hesabı oluşturuldu; kullanım ve KVKK onayları alındı.",
        ip_address=ip,
        module="auth",
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Bu e-posta veya sertifika numarası zaten kayıtlı.") from exc

    db.refresh(user)
    return _issue_access(user, response)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    ip = _client_ip(request)
    identifier = str(payload.email).strip()
    lookup_value = identifier.casefold()
    try:
        throttle_login(lookup_value, ip)
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    user = db.scalar(
        select(User).where(
            or_(
                func.lower(User.email) == lookup_value,
                func.lower(User.username) == lookup_value,
            )
        )
    )
    if user and is_locked(user):
        register_failed_login(db, user, email=identifier, ip=ip)
        db.commit()
        raise HTTPException(
            status_code=423,
            detail="Hesap geçici olarak kilitli. Lütfen daha sonra tekrar deneyin.",
        )

    if not user or not verify_password(payload.password, user.hashed_password):
        register_failed_login(db, user, email=identifier, ip=ip)
        db.commit()
        raise HTTPException(status_code=401, detail="E-posta/kullanıcı adı veya şifre hatalı.")

    if not user.is_active:
        register_failed_login(db, user, email=identifier, ip=ip)
        db.commit()
        raise HTTPException(status_code=401, detail="Hesap pasif. Yöneticinizle iletişime geçin.")

    user = _sync_field(db, user)
    ensure_login_scope(db, user)
    clear_throttle(lookup_value, ip)

    mfa_on = bool(getattr(user, "mfa_enabled", False))
    mfa_secret = get_mfa_secret(user) if mfa_on else None
    # MFA bayrağı açık ama gizli anahtar yoksa doğrulama ekranına düşmesin; kurulum zorunlu.
    if mfa_on and not mfa_secret:
        user.mfa_enabled = False
        mfa_on = False

    if mfa_on:
        register_success_login(db, user, ip=ip)
        db.commit()
        return TokenResponse(
            mfa_required=True,
            mfa_token=create_purpose_token(
                str(user.id), "mfa_challenge", minutes=10, token_version=getattr(user, "token_version", 0) or 0
            ),
        )

    if role_requires_mfa(user.role) and not mfa_on:
        register_success_login(db, user, ip=ip)
        db.commit()
        return TokenResponse(
            mfa_setup_required=True,
            mfa_token=create_purpose_token(
                str(user.id), "mfa_setup", minutes=30, token_version=getattr(user, "token_version", 0) or 0
            ),
        )

    register_success_login(db, user, ip=ip)
    db.commit()
    return _issue_access(user, response)


@router.post("/mfa/restart-setup", response_model=TokenResponse)
def restart_mfa_setup(
    payload: MfaRestartSetupRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Authenticator kurulumu yapılamadıysa: giriş bilgileriyle MFA’yı sıfırlar."""
    ip = _client_ip(request)
    identifier = str(payload.email).strip()
    lookup_value = identifier.casefold()
    try:
        throttle_login(lookup_value, ip)
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    user = db.scalar(
        select(User).where(
            or_(
                func.lower(User.email) == lookup_value,
                func.lower(User.username) == lookup_value,
            )
        )
    )
    if not user or not verify_password(payload.password, user.hashed_password):
        register_failed_login(db, user, email=identifier, ip=ip)
        db.commit()
        raise HTTPException(status_code=401, detail="E-posta/kullanıcı adı veya şifre hatalı.")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Hesap pasif. Yöneticinizle iletişime geçin.")
    user = _sync_field(db, user)
    ensure_login_scope(db, user)
    if not role_requires_mfa(user.role):
        raise HTTPException(status_code=400, detail="Bu hesap için MFA kurulumu gerekmez.")

    user.mfa_enabled = False
    user.mfa_secret_encrypted = None
    user.mfa_recovery_hashes = None
    clear_throttle(lookup_value, ip)
    add_audit_log(
        db,
        user=user,
        action="mfa_restart_setup",
        entity_type="user",
        entity_id=str(user.id),
        description="MFA kurulum yeniden başlatıldı (şifre doğrulamalı)",
        ip_address=ip,
        module="auth",
    )
    register_success_login(db, user, ip=ip)
    db.commit()
    return TokenResponse(
        mfa_setup_required=True,
        mfa_token=create_purpose_token(
            str(user.id), "mfa_setup", minutes=30, token_version=getattr(user, "token_version", 0) or 0
        ),
    )


@router.post("/mfa/verify", response_model=TokenResponse)
def verify_mfa_login(
    payload: MfaVerifyRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_mfa_challenge_user),
):
    import pyotp

    user = _sync_field(db, user)
    ensure_login_scope(db, user)
    if not user.mfa_enabled:
        raise HTTPException(
            status_code=403,
            detail="MFA henüz etkinleştirilmedi. Önce güvenlik ayarlarından MFA’yı tamamlayın.",
        )
    code = (payload.code or "").strip().replace(" ", "")
    secret = get_mfa_secret(user)
    ok = False
    if secret:
        ok = pyotp.TOTP(secret).verify(code, valid_window=2)
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
    return _issue_access(user, response)


@router.post("/refresh", response_model=TokenResponse)
def refresh_access_token(request: Request, response: Response, db: Session = Depends(get_db)):
    """HttpOnly refresh cookie → yeni access token. Flag kapalıysa 404."""
    if not refresh_cookie_enabled():
        raise HTTPException(404, "Refresh cookie kapalı.")

    raw = (request.cookies.get(REFRESH_COOKIE_NAME) or "").strip()
    if not raw:
        raise HTTPException(401, "Oturum yenilenemedi — tekrar giriş yapın.")
    try:
        payload = jwt.decode(raw, settings.secret_key, algorithms=[ALGORITHM])
        if (payload.get("purpose") or "") != "refresh":
            raise HTTPException(401, "Oturum yenilenemedi.")
        user_id = int(payload.get("sub"))
        jti = payload.get("jti")
        tv = int(payload.get("tv") or 0)
        exp = payload.get("exp")
    except (InvalidTokenError, TypeError, ValueError, OverflowError, OSError, HTTPException):
        clear_refresh_cookie(response)
        raise HTTPException(401, "Oturum yenilenemedi — tekrar giriş yapın.")

    if jti and is_jti_revoked(db, str(jti)):
        clear_refresh_cookie(response)
        raise HTTPException(401, "Oturum yenilenemedi — tekrar giriş yapın.")

    user = db.get(User, user_id)
    if not user or not user.is_active:
        clear_refresh_cookie(response)
        raise HTTPException(401, "Oturum yenilenemedi — tekrar giriş yapın.")
    if tv != int(getattr(user, "token_version", 0) or 0):
        clear_refresh_cookie(response)
        raise HTTPException(401, "Oturum yenilenemedi — tekrar giriş yapın.")

    user = _sync_field(db, user)
    try:
        ensure_login_scope(db, user)
    except HTTPException:
        clear_refresh_cookie(response)
        raise

    # Eski refresh'i düşür (rotation)
    if jti and exp:
        expires_at = datetime.fromtimestamp(int(exp), tz=timezone.utc).replace(tzinfo=None)
        revoke_jti(db, jti=str(jti), user_id=user.id, expires_at=expires_at)
        db.commit()

    return _issue_access(user, response)


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    token: str = Depends(oauth2_scheme),
):
    """Aktif access token'ı denylist'e yazar; istemci oturum belirtecini temizlemeli."""

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        jti = payload.get("jti")
        exp = payload.get("exp")
        if jti and exp:
            expires_at = datetime.fromtimestamp(int(exp), tz=timezone.utc).replace(tzinfo=None)
            revoke_jti(db, jti=str(jti), user_id=user.id, expires_at=expires_at)
            add_audit_log(
                db,
                user=user,
                action="logout",
                entity_type="user",
                entity_id=str(user.id),
                description="Oturum sonlandırıldı (token iptal)",
                ip_address=_client_ip(request),
                module="auth",
            )
            db.commit()
    except (InvalidTokenError, TypeError, ValueError, OverflowError, OSError):
        logger.warning("logout: access jti revoke failed", exc_info=True)
    # Refresh cookie varsa temizle (flag açıkken)
    raw = (request.cookies.get(REFRESH_COOKIE_NAME) or "").strip()
    if raw:
        try:
            payload = jwt.decode(raw, settings.secret_key, algorithms=[ALGORITHM])
            jti = payload.get("jti")
            exp = payload.get("exp")
            if jti and exp:
                expires_at = datetime.fromtimestamp(int(exp), tz=timezone.utc).replace(tzinfo=None)
                revoke_jti(db, jti=str(jti), user_id=user.id, expires_at=expires_at)
                db.commit()
        except (InvalidTokenError, TypeError, ValueError, OverflowError, OSError):
            logger.warning("logout: refresh jti revoke failed", exc_info=True)
    clear_refresh_cookie(response)
    return {"ok": True, "message": "Oturum sonlandırıldı."}


@router.post("/logout-all")
def logout_all_sessions(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Tüm cihazlardaki JWT'leri düşürür (token_version++). Bu istekteki token da geçersiz olur."""
    from app.services.token_revoke import bump_token_version, prune_expired_denylist

    bump_token_version(user)
    try:
        prune_expired_denylist(db)
    except Exception:
        logger.warning("logout_all: denylist prune failed", exc_info=True)
    add_audit_log(
        db,
        user=user,
        action="logout_all",
        entity_type="user",
        entity_id=str(user.id),
        description="Tüm oturumlar sonlandırıldı (token_version)",
        ip_address=_client_ip(request),
        module="auth",
    )
    db.commit()
    clear_refresh_cookie(response)
    return {
        "ok": True,
        "message": "Tüm cihazlardaki oturumlar kapatıldı. Lütfen yeniden giriş yapın.",
        "token_version": int(getattr(user, "token_version", 0) or 0),
    }


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    """Her zaman nötr yanıt — kullanıcı varlığını sızdırma."""
    email = str(payload.email).strip().lower()
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user and user.is_active:
