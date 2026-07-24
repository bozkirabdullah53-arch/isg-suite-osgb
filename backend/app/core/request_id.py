"""Her isteğe X-Request-ID ekler (P1-07 observability)."""
from __future__ import annotations

from contextvars import ContextVar
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


def current_request_id() -> str:
    return request_id_ctx.get() or ""


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        incoming = (request.headers.get("x-request-id") or "").strip()
        rid = incoming[:80] if incoming else uuid4().hex
        token = request_id_ctx.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(token)
        response.headers["X-Request-ID"] = rid
        return response
