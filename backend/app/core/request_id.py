"""Her isteğe X-Request-ID ekler (P1-07 observability)."""
from __future__ import annotations

import logging
from contextvars import ContextVar
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


def current_request_id() -> str:
    return request_id_ctx.get() or ""


class RequestIdLogFilter(logging.Filter):
    """Log kayıtlarına request_id ekler (yoksa '-')."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = current_request_id() or "-"  # type: ignore[attr-defined]
        return True


def install_request_id_logging() -> None:
    """Root logger'a bir kez RequestIdLogFilter bağla."""
    root = logging.getLogger()
    marker = "isg_request_id_filter"
    if any(getattr(f, "name", "") == marker for f in root.filters):
        return
    filt = RequestIdLogFilter()
    filt.name = marker  # type: ignore[attr-defined]
    root.addFilter(filt)
    for handler in root.handlers:
        if not any(getattr(f, "name", "") == marker for f in handler.filters):
            handler.addFilter(filt)


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
