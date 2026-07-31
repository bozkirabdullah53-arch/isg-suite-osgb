"""Her isteğin başında TenantContext temizler (worker sızıntısı önleme)."""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware

from app.core.tenant_context import clear_tenant


class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        clear_tenant()
        try:
            return await call_next(request)
        finally:
            clear_tenant()
