"""IP tabanlı istek limiti — bellek içi pencere (Redis sonraki adım).

Sertleştirme (0.9.154):
- /health muaf (warmup + monitoring kırılmaz)
- /api/v1/auth/* daha düşük limit (brute-force)
- X-Forwarded-For (Render proxy arkasında gerçek istemci)
- 429 yanıtında Retry-After
- Boş anahtar temizliği (bellek sızıntısı azaltma)
"""
from __future__ import annotations

from collections import defaultdict, deque
from time import monotonic

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings

_EXEMPT_PREFIXES = ("/health",)
_AUTH_PREFIXES = ("/api/v1/auth",)


def _client_ip(request) -> str:
    xff = (request.headers.get("x-forwarded-for") or "").strip()
    if xff:
        # Sol: orijinal istemci (Render / tipik reverse-proxy)
        first = xff.split(",")[0].strip()
        if first:
            return first
    real = (request.headers.get("x-real-ip") or "").strip()
    if real:
        return real
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _is_exempt(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in _EXEMPT_PREFIXES)


def _is_auth(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in _AUTH_PREFIXES)


class SimpleRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        requests_per_minute: int | None = None,
        auth_requests_per_minute: int | None = None,
    ):
        super().__init__(app)
        self.limit = int(
            requests_per_minute
            if requests_per_minute is not None
            else getattr(settings, "rate_limit_rpm", 120)
        )
        self.auth_limit = int(
            auth_requests_per_minute
            if auth_requests_per_minute is not None
            else getattr(settings, "rate_limit_auth_rpm", 30)
        )
        self.hits: dict[str, deque] = defaultdict(deque)
        self._last_prune = monotonic()

    def _prune(self, now: float) -> None:
        if now - self._last_prune < 30:
            return
        self._last_prune = now
        dead = [k for k, window in self.hits.items() if not window or now - window[-1] > 60]
        for k in dead:
            self.hits.pop(k, None)

    async def dispatch(self, request, call_next):
        path = request.url.path or "/"
        if _is_exempt(path):
            return await call_next(request)

        client = _client_ip(request)
        auth = _is_auth(path)
        limit = self.auth_limit if auth else self.limit
        # Auth: IP bazlı; diğer: IP+path (SPA çoklu endpoint'i bozmasın)
        key = f"{client}:auth" if auth else f"{client}:{path}"
        now = monotonic()
        self._prune(now)
        window = self.hits[key]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= limit:
            retry = max(1, int(60 - (now - window[0]))) if window else 60
            return JSONResponse(
                {"detail": "Çok fazla istek gönderildi. Lütfen kısa süre sonra tekrar deneyin."},
                status_code=429,
                headers={"Retry-After": str(retry)},
            )
        window.append(now)
        return await call_next(request)
