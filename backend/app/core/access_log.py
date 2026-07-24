"""Structured access log — JSON satır + X-Request-ID (P1-07b)."""
from __future__ import annotations

import json
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware

from app.core.request_id import current_request_id

logger = logging.getLogger("isg.access")


class StructuredAccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            ms = round((time.perf_counter() - start) * 1000, 1)
            path = request.url.path or "/"
            # Sağlık/warmup gürültüsünü azalt
            if path == "/health" or path.startswith("/health/"):
                pass
            else:
                payload = {
                    "event": "http_access",
                    "method": request.method,
                    "path": path,
                    "status": status,
                    "ms": ms,
                    "request_id": current_request_id() or None,
                }
                logger.info(json.dumps(payload, ensure_ascii=False))
