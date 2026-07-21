"""Kimlik sertleştirme, parola sıfırlama, MFA yardımcıları."""
from __future__ import annotations

import hashlib
import json
import logging
import secrets
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import ALGORITHM, get_password_hash, verify_password
from app.models.entities import PasswordResetToken, User, UserRole
from app.services.audit import add_audit_log

logger = logging.getLogger(__name__)

LOGIN_MAX_FAILURES = 8
LOGIN_LOCK_MINUTES = 15
LOGIN_WINDOW_ATTEMPTS = 10
LOGIN_WINDOW_MINUTES = 10
RESET_TOKEN_HOURS = 2
MFA_REQUIRED_ROLES = frozenset({UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN})

# in-memory throttle: key -> list[datetime]
_login_hits: dict[str, list[datetime]] = {}


def _utcnow() -> datetime:
    return datetime.utcnow()


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
    # url-safe 32-byte key
    import base64

    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, Exception):
        return None


def create_purpose_token(subject: str, purpose: str, minutes: int = 10) -> str:
    expire = datetime.utcnow() + timedelta(minutes=minutes)
    payload = {"sub": subject, "exp": expire, "purpose": purpose}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token_payload(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])


def role_requires_mfa(role: UserRole | str) -> bool:
    if isinstance(role, str):
        try:
            role = UserRole(role)
        except ValueError:
            return False
    return role in MFA_REQUIRED_ROLES


def throttle_login(email: str, ip: str | None) -> None:
    """Raises ValueError if too many attempts."""
    key = f"{(email or '').strip().lower()}|{(ip or '').strip()}"
    now = _utcnow()
    window = now - timedelta(minutes=LOGIN_WINDOW_MINUTES)
    hits = [t for t in _login_hits.get(key, []) if t >= window]
    if len(hits) >= LOGIN_WINDOW_ATTEMPTS:
        raise ValueError("Çok fazla giriş denemesi. Lütfen birkaç dakika sonra tekrar deneyin.")
    hits.append(now)
    _login_hits[key] = hits


def clear_throttle(email: str, ip: str | None) -> None:
    key = f"{(email or '').strip().lower()}|{(ip or '').strip()}"
    _login_hits.pop(key, None)


def is_locked(user: User) -> bool:
    until = getattr(user, "locked_until", None)
    if not until:
        return False
    return until > _utcnow()


def register_failed_login(db: Session, user: User | None, *, email: str, ip: str | None) -> None:
    add_audit_log(
        db,
        user=user,
        action="login_failed",
        entity_type="user",
        entity_id=str(user.id) if user else None,
        description=f"Başarısız giriş: {email}",
        ip_address=ip,
        module="auth",
    )
    if not user:
        return
    user.failed_login_count = int(getattr(user, "failed_login_count", 0) or 0) + 1
    if user.failed_login_count >= LOGIN_MAX_FAILURES:
        user.locked_until = _utcnow() + timedelta(minutes=LOGIN_LOCK_MINUTES)
        user.failed_login_count = 0


def register_success_login(db: Session, user: User, *, ip: str | None) -> None:
    user.failed_login_count = 0
    user.locked_until = None
    add_audit_log(
        db,
        user=user,
        action="login_success",
        entity_type="user",
        entity_id=str(user.id),
        description="Başarılı giriş",
        ip_address=ip,
        module="auth",
    )


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_password_reset(db: Session, user: User) -> str:
    raw = secrets.token_urlsafe(32)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=_utcnow() + timedelta(hours=RESET_TOKEN_HOURS),
            created_at=_utcnow(),
        )
    )
    return raw


def consume_password_reset(db: Session, raw_token: str, new_password: str) -> User:
    th = hash_token(raw_token)
    row = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == th,
            PasswordResetToken.used_at.is_(None),
        )
    )
    if not row or row.expires_at < _utcnow():
        raise ValueError("Geçersiz veya süresi dolmuş sıfırlama bağlantısı.")
    user = db.get(User, row.user_id)
    if not user or not user.is_active:
        raise ValueError("Geçersiz veya süresi dolmuş sıfırlama bağlantısı.")
    user.hashed_password = get_password_hash(new_password)
    user.failed_login_count = 0
    user.locked_until = None
    row.used_at = _utcnow()
    return user


def send_reset_email(to_email: str, raw_token: str) -> bool:
    link = f"{settings.frontend_origin.rstrip('/')}/?sifre-sifirla={raw_token}"
    if not settings.smtp_host:
        env = (settings.environment or "").strip().lower()
        if env in ("production", "prod", "live"):
            logger.warning("SMTP yok; parola sıfırlama e-postası gönderilemedi (%s)", to_email)
            return False
        logger.info("DEV password reset token for %s: %s", to_email, raw_token)
        logger.info("DEV reset link: %s", link)
        return True
    msg = EmailMessage()
    msg["Subject"] = "İSG Suite — Şifre sıfırlama"
    msg["From"] = settings.smtp_from_email
    msg["To"] = to_email
    msg.set_content(
        "Şifrenizi sıfırlamak için bağlantıya tıklayın (2 saat geçerli):\n\n"
        f"{link}\n\n"
        "Bu isteği siz yapmadıysanız bu e-postayı yok sayın.\n"
    )
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password or "")
            smtp.send_message(msg)
        return True
    except Exception:
        logger.exception("SMTP send failed")
        return False


def generate_recovery_codes(n: int = 8) -> tuple[list[str], str]:
    codes = [secrets.token_hex(4) for _ in range(n)]
    hashes = [get_password_hash(c) for c in codes]
    return codes, json.dumps(hashes)


def verify_recovery_code(user: User, code: str) -> bool:
    raw = getattr(user, "mfa_recovery_hashes", None) or "[]"
    try:
        hashes = json.loads(raw)
    except Exception:
        return False
    remaining = []
    matched = False
    for h in hashes:
        if not matched and verify_password(code, h):
            matched = True
            continue
        remaining.append(h)
    if matched:
        user.mfa_recovery_hashes = json.dumps(remaining)
    return matched


def get_mfa_secret(user: User) -> str | None:
    enc = getattr(user, "mfa_secret_encrypted", None)
    if not enc:
        return None
    return decrypt_secret(enc)
