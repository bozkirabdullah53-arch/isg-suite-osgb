"""Auth refresh cookie helpers (P1-01)."""
from __future__ import annotations

from fastapi import Response

from app.core.config import settings

REFRESH_COOKIE_NAME = "isg_refresh"


def refresh_cookie_enabled() -> bool:
    """P1-01: production'da varsayılan açık; FORCE_OFF veya non-prod flag ile kontrol."""
    if bool(getattr(settings, "auth_refresh_cookie_force_off", False)):
        return False
    env = (settings.environment or "").strip().lower()
    if env in {"production", "prod", "live"}:
        return True
    return bool(getattr(settings, "auth_refresh_cookie_enabled", False))


def access_token_ttl_minutes() -> int:
    """Refresh cookie açıksa kısa access; değilse normal süre."""
    if refresh_cookie_enabled():
        return int(getattr(settings, "access_token_expire_minutes_short", 15) or 15)
    return int(settings.access_token_expire_minutes or 60)


def _cookie_flags() -> tuple[bool, str, bool]:
    """Prod: Secure + SameSite=None + Partitioned (cross-site SPA). Yerel: Lax."""
    env = (settings.environment or "").strip().lower()
    secure = env in {"production", "prod", "live"}
    samesite = "none" if secure else "lax"
    partitioned = secure  # CHIPS — üçüncü taraf cookie engeline karşı
    return secure, samesite, partitioned


def set_refresh_cookie(response: Response, token: str) -> None:
    if not refresh_cookie_enabled() or not token:
        return
    secure, samesite, partitioned = _cookie_flags()
    days = int(getattr(settings, "refresh_token_expire_days", 14) or 14)
    kwargs = dict(
        key=REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        max_age=max(60, days * 86400),
        path="/api/v1/auth",
    )
    if partitioned:
        kwargs["partitioned"] = True
    response.set_cookie(**kwargs)


def clear_refresh_cookie(response: Response) -> None:
    secure, samesite, partitioned = _cookie_flags()
    kwargs = dict(
        key=REFRESH_COOKIE_NAME,
        path="/api/v1/auth",
        httponly=True,
        secure=secure,
        samesite=samesite,
    )
    if partitioned:
        kwargs["partitioned"] = True
    response.delete_cookie(**kwargs)
