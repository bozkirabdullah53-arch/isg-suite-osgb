from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from jwt import InvalidTokenError
from passlib.context import CryptContext

from app.core.auth_cookies import access_token_ttl_minutes
from app.core.config import settings


ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def jwt_signing_key() -> str:
    """ISG-005: JWT_SECRET tanımlıysa imza onunla; değilse mevcut secret_key."""
    return (getattr(settings, "jwt_secret", None) or "").strip() or settings.secret_key


def jwt_verification_keys() -> list[str]:
    """Doğrulama anahtarları (öncelik: jwt_secret, fallback: secret_key)."""
    keys: list[str] = []
    for key in (getattr(settings, "jwt_secret", None), settings.secret_key):
        value = (key or "").strip()
        if value and value not in keys:
            keys.append(value)
    return keys


def decode_access_token(token: str) -> dict:
    """ISG-005: anahtar rotasyonunda oturum düşürmeyen çok anahtarlı çözümleme."""
    last_error: Exception | None = None
    for key in jwt_verification_keys():
        try:
            return jwt.decode(token, key, algorithms=[ALGORITHM])
        except InvalidTokenError as exc:
            last_error = exc
    raise last_error if last_error else InvalidTokenError("no verification key configured")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(
    subject: str,
    *,
    purpose: str = "access",
    minutes: int | None = None,
    token_version: int = 0,
) -> str:
    if minutes is not None:
        ttl = minutes
    elif purpose == "access":
        ttl = access_token_ttl_minutes()
    else:
        ttl = settings.access_token_expire_minutes
    expire = datetime.now(timezone.utc) + timedelta(minutes=ttl)
    payload = {
        "sub": subject,
        "exp": expire,
        "purpose": purpose,
        "jti": uuid4().hex,
        "tv": int(token_version or 0),
    }
    return jwt.encode(payload, jwt_signing_key(), algorithm=ALGORITHM)


def create_refresh_token(subject: str, *, token_version: int = 0) -> str:
    days = int(getattr(settings, "refresh_token_expire_days", 14) or 14)
    return create_access_token(
        subject,
        purpose="refresh",
        minutes=max(60, days * 24 * 60),
        token_version=token_version,
    )
