"""Auth refresh cookie helpers (P1-01) — varsayılan kapalı."""
from __future__ import annotations

from fastapi import Response

from app.core.config import settings

REFRESH_COOKIE_NAME = "isg_refresh"


def refresh_cookie_enabled() -> bool:
    return bool(getattr(settings, "auth_refresh_cookie_enabled", False))


def set_refresh_cookie(response: Response, token: str) -> None:
    if not refresh_cookie_enabled() or not token:
        return
    env = (settings.environment or "").strip().lower()
    secure = env in {"production", "prod", "live"}
    days = int(getattr(settings, "refresh_token_expire_days", 14) or 14)
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=max(60, days * 86400),
        path="/api/v1/auth",
    )


def clear_refresh_cookie(response: Response) -> None:
    env = (settings.environment or "").strip().lower()
    secure = env in {"production", "prod", "live"}
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/api/v1/auth",
        httponly=True,
        secure=secure,
        samesite="lax",
    )
