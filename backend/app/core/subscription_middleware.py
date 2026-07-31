"""Abonelik süresi dolunca yazma işlemlerini engeller (salt okunur)."""
from __future__ import annotations

from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core import database as dbmod
from app.core.security import ALGORITHM
from app.models.entities import User, UserRole
from app.services.osgb_subscription import (
    get_or_create_subscription,
    resolve_user_osgb_id,
    subscription_allows_write,
)

WRITE_EXEMPT_PREFIXES = (
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/v1/auth",
    "/api/v1/osgb-applications",
    "/api/v1/eisa",
    "/api/v1/trainings/verify",
    "/api/v1/legal",
)


class OsgbSubscriptionWriteMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)
        path = request.url.path
        if any(path.startswith(p) for p in WRITE_EXEMPT_PREFIXES):
            return await call_next(request)

        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            return await call_next(request)

        token = auth.split(" ", 1)[1].strip()
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
            user_id = int(payload.get("sub"))
        except (JWTError, TypeError, ValueError):
            return await call_next(request)

        with dbmod.SessionLocal() as db:
            user = db.get(User, user_id)
            if not user or not user.is_active or user.role == UserRole.GLOBAL_ADMIN:
                return await call_next(request)
            oid = resolve_user_osgb_id(db, user)
            if not oid:
                return await call_next(request)
            sub = get_or_create_subscription(db, oid)
            if not subscription_allows_write(sub):
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": (
                            "Abonelik süresi doldu veya askıda. Veri girişi kapalı — salt okunur moddasınız. "
                            "EİSA ile iletişime geçin."
                        )
                    },
                )
        return await call_next(request)
