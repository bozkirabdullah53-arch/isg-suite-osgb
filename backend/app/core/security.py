from datetime import datetime, timedelta, timezone
from uuid import uuid4

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings


ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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
    ttl = minutes if minutes is not None else settings.access_token_expire_minutes
    expire = datetime.now(timezone.utc) + timedelta(minutes=ttl)
    payload = {
        "sub": subject,
        "exp": expire,
        "purpose": purpose,
        "jti": uuid4().hex,
        "tv": int(token_version or 0),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_refresh_token(subject: str, *, token_version: int = 0) -> str:
    days = int(getattr(settings, "refresh_token_expire_days", 14) or 14)
    return create_access_token(
        subject,
        purpose="refresh",
        minutes=max(60, days * 24 * 60),
        token_version=token_version,
    )
