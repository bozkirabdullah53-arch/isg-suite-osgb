"""IP tabanlı istek limiti — Redis (paylaşımlı) veya bellek içi yedek (P1-02).

Sertleştirme:
- /health muaf
- /api/v1/auth/* daha düşük limit
- X-Forwarded-For
- 429 + Retry-After
- REDIS_URL yoksa veya Redis hata verirse bellek içi (canlı bozulmaz)
"""
from __future__ import annotations

import logging
from collections import defaultdict, deque
from time import monotonic, time
from typing import Protocol

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings

logger = logging.getLogger(__name__)

_EXEMPT_PREFIXES = ("/health",)
_AUTH_PREFIXES = ("/api/v1/auth",)
_REDIS_KEY_PREFIX = "isg:rl:"


def _client_ip(request) -> str:
    xff = (request.headers.get("x-forwarded-for") or "").strip()
    if xff:
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


class RateLimitStore(Protocol):
    async def hit(self, key: str, *, limit: int, window_sec: int = 60) -> tuple[bool, int]:
        """(allowed, retry_after_sec)."""


class MemoryRateLimitStore:
    def __init__(self) -> None:
        self.hits: dict[str, deque] = defaultdict(deque)
        self._last_prune = monotonic()

    def _prune(self, now: float) -> None:
        if now - self._last_prune < 30:
            return
        self._last_prune = now
        dead = [k for k, window in self.hits.items() if not window or now - window[-1] > 60]
        for k in dead:
            self.hits.pop(k, None)

    async def hit(self, key: str, *, limit: int, window_sec: int = 60) -> tuple[bool, int]:
        now = monotonic()
        self._prune(now)
        window = self.hits[key]
        while window and now - window[0] > window_sec:
            window.popleft()
        if len(window) >= limit:
            retry = max(1, int(window_sec - (now - window[0]))) if window else window_sec
            return False, retry
        window.append(now)
        return True, 0


class RedisRateLimitStore:
    """Sabit 60 sn pencere — Redis INCR (çoklu worker paylaşımı)."""

    def __init__(self, client) -> None:
        self._client = client

    async def hit(self, key: str, *, limit: int, window_sec: int = 60) -> tuple[bool, int]:
        # Saniye bucket: aynı pencerede tüm worker'lar aynı sayacı paylaşır
        bucket = int(time()) // window_sec
        rkey = f"{_REDIS_KEY_PREFIX}{key}:{bucket}"
        count = int(await self._client.incr(rkey))
        if count == 1:
            await self._client.expire(rkey, window_sec + 1)
        if count > limit:
            ttl = await self._client.ttl(rkey)
            retry = max(1, int(ttl)) if ttl and ttl > 0 else window_sec
            return False, retry
        return True, 0


_store: RateLimitStore | None = None
_backend_name = "memory"


def rate_limit_backend() -> str:
    return _backend_name


def _init_store() -> RateLimitStore:
    global _backend_name
    url = (getattr(settings, "redis_url", None) or "").strip()
    if not url:
        _backend_name = "memory"
        return MemoryRateLimitStore()
    try:
        import redis.asyncio as redis_async

        client = redis_async.from_url(url, encoding="utf-8", decode_responses=True)
        _backend_name = "redis"
        logger.info("Rate limit: Redis backend (%s)", url.split("@")[-1] if "@" in url else "configured")
        return RedisRateLimitStore(client)
    except Exception as exc:  # pragma: no cover - bağlantı/kurulum
        logger.warning("Rate limit: Redis açılamadı (%s) — bellek içi yedek", exc)
        _backend_name = "memory-fallback"
        return MemoryRateLimitStore()


def get_rate_limit_store() -> RateLimitStore:
    global _store
    if _store is None:
        _store = _init_store()
    return _store


def reset_rate_limit_store_for_tests(store: RateLimitStore | None = None) -> None:
    """Testlerde store'u sıfırla / enjekte et."""
    global _store, _backend_name
    _store = store if store is not None else MemoryRateLimitStore()
    _backend_name = "memory" if store is None or isinstance(store, MemoryRateLimitStore) else "redis"


class SimpleRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        requests_per_minute: int | None = None,
        auth_requests_per_minute: int | None = None,
        store: RateLimitStore | None = None,
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
        self._store = store

    @property
    def store(self) -> RateLimitStore:
        return self._store if self._store is not None else get_rate_limit_store()

    async def dispatch(self, request, call_next):
        path = request.url.path or "/"
        if _is_exempt(path):
            return await call_next(request)

        client = _client_ip(request)
        auth = _is_auth(path)
        limit = self.auth_limit if auth else self.limit
        key = f"{client}:auth" if auth else f"{client}:{path}"
        try:
            allowed, retry = await self.store.hit(key, limit=limit, window_sec=60)
        except Exception as exc:
            # Redis transient hata → isteği düşürme (fail-open), bir sonraki istekte memory'ye düşülebilir
            logger.warning("Rate limit store error (fail-open): %s", exc)
            allowed, retry = True, 0
        if not allowed:
            return JSONResponse(
                {"detail": "Çok fazla istek gönderildi. Lütfen kısa süre sonra tekrar deneyin."},
                status_code=429,
                headers={"Retry-After": str(retry or 60)},
            )
        return await call_next(request)
