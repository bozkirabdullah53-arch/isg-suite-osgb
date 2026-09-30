"""IP tabanlı istek limiti — Redis (paylaşımlı) veya bellek içi yedek (P1-02).

Sertleştirme:
- /health muaf
- /api/v1/auth/* daha düşük limit
- Güvenilir proxy zincirinden IP (XFF spoof koruması)
- 429 + Retry-After
- REDIS_URL yoksa veya Redis hata verirse bellek içi koruma devam eder
"""
from __future__ import annotations

import logging
import os
import ipaddress
import hashlib
import hmac
import math
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

# Güvenilir proxy zinciri: Render/Cloudflare her zaman bu header'ları ekler.
# İstemci bu header'ları spoof edemez çünkü proxy en sağdaki (en dış) giriştedir
# ve güvenilmeyen değerleri çıkarır/üzerine yazar. Yine de XFF içindeki en sağdaki
# (proxy'ye en yakın) segmenti alırız; istemci tarafından eklenen sol taraftaki
# spoof değerleri yok sayılır.
_PROXY_TRUST_DEPTH = int(getattr(settings, "proxy_trust_depth", 1))


def _client_ip(request) -> str:
    # ISG-009: TRUST_PROXY_HEADERS=false ise proxy header'larına hiç bakılmaz;
    # yalnızca gerçek socket peer kullanılır (XFF spoof baypası kapanır).
    if not bool(getattr(settings, "trust_proxy_headers", True)):
        if request.client and request.client.host:
            return request.client.host
        return "unknown"
    # Güvenilir proxy arkasında çalışıyoruz: X-Forwarded-For zincirinin en
    # sağındaki (proxy'ye en yakın) girişi al. Sol taraftaki girişler istemci
    # tarafından spoof edilebilir ve yok sayılır.
    xff = (request.headers.get("x-forwarded-for") or "").strip()
    if xff:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if parts:
            if os.getenv("RENDER", "").lower() == "true":
                # Render appends internal hops after the external client.
                # Walk from the trusted end, ignoring private proxy addresses;
                # never use the attacker-controlled leftmost value directly.
                for part in reversed(parts):
                    try:
                        address = ipaddress.ip_address(part)
                    except ValueError:
                        continue
                    if address.is_global:
                        return str(address)
                return "render-proxy-unknown"
            idx = max(0, len(parts) - _PROXY_TRUST_DEPTH)
            candidate = parts[idx]
            if candidate:
                return candidate
    # X-Real-IP tek başına güven sınırı değildir. XFF yoksa socket peer'e
    # dönmek, doğrudan erişilebilen origin'de sahte X-Real-IP ile rate-limit
    # anahtarı değiştirilmesini engeller.
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

    async def failed_accounts(self, key: str, *, member: str | None = None, window_sec: int = 600) -> tuple[int, int]:
        """Sliding count of distinct failed accounts and time until one expires."""


class MemoryRateLimitStore:
    def __init__(self) -> None:
        self.hits: dict[str, deque] = defaultdict(deque)
        self.accounts: dict[str, dict[str, float]] = {}
        self._last_prune = monotonic()

    def _prune(self, now: float) -> None:
        if now - self._last_prune < 30:
            return
        self._last_prune = now
        dead = [k for k, window in self.hits.items() if not window or now - window[-1] > 600]
        for k in dead:
            self.hits.pop(k, None)
        for k in list(self.accounts):
            if not self.accounts[k] or now - max(self.accounts[k].values()) >= 600:
                self.accounts.pop(k, None)

    async def hit(self, key: str, *, limit: int, window_sec: int = 60) -> tuple[bool, int]:
        now = monotonic()
        self._prune(now)
        # ISG-009: benzersiz path'lerle sözlük şişirme (bellek DoS) denemesine
        # karşı sert üst sınır — en eski yarısını düşür, servis ayakta kalır.
        if len(self.hits) > 100_000:
            for old_key in list(self.hits.keys())[:50_000]:
                self.hits.pop(old_key, None)
        window = self.hits[key]
        while window and now - window[0] > window_sec:
            window.popleft()
        if len(window) >= limit:
            retry = max(1, int(window_sec - (now - window[0]))) if window else window_sec
            return False, retry
        window.append(now)
        return True, 0

    async def failed_accounts(self, key: str, *, member: str | None = None, window_sec: int = 600) -> tuple[int, int]:
        now = monotonic()
        self._prune(now)
        if key not in self.accounts and member is None:
            return 0, 0
        if len(self.accounts) >= 100_000 and key not in self.accounts:
            # Preserve protection if the bounded fallback is saturated.
            return 100_000, window_sec
        accounts = self.accounts.setdefault(key, {})
        for old in [m for m, stamp in accounts.items() if now - stamp >= window_sec]:
            accounts.pop(old)
        if member is not None:
            accounts[member] = now
        retry = max(1, math.ceil(window_sec - (now - min(accounts.values())))) if accounts else 0
        return len(accounts), retry


class RedisRateLimitStore:
    """Sabit 60 sn pencere — Redis INCR (çoklu worker paylaşımı)."""

    def __init__(self, client) -> None:
        self._client = client

    async def hit(self, key: str, *, limit: int, window_sec: int = 60) -> tuple[bool, int]:
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

    async def failed_accounts(self, key: str, *, member: str | None = None, window_sec: int = 600) -> tuple[int, int]:
        # Server time and a single atomic operation keep all workers consistent.
        script = """
local clock = redis.call('TIME')
local now = tonumber(clock[1]) + tonumber(clock[2]) / 1000000
local window = tonumber(ARGV[1])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - window)
if ARGV[2] ~= '' then
  redis.call('ZADD', KEYS[1], now, ARGV[2])
  redis.call('EXPIRE', KEYS[1], window + 1)
end
local count = redis.call('ZCARD', KEYS[1])
local first = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
local retry = 0
if count > 0 then retry = math.max(1, math.ceil(tonumber(first[2]) + window - now)) end
return {count, retry}
"""
        count, retry = await self._client.eval(script, 1, f"{_REDIS_KEY_PREFIX}{key}:failed-accounts", window_sec, member or "")
        return int(count), int(retry)


_store: RateLimitStore | None = None
_backend_name = "memory"


def rate_limit_backend() -> str:
    return _backend_name


def redis_status_label() -> str:
    """Health için: unset | ok | unreachable (canlıyı bozmaz)."""
    url = (getattr(settings, "redis_url", None) or "").strip()
    if not url:
        return "unset"
    try:
        import redis

        client = redis.from_url(url, decode_responses=True, socket_connect_timeout=1.5)
        client.ping()
        return "ok"
    except Exception as exc:  # pragma: no cover
        logger.warning("Redis ping failed: %s", exc)
        return "unreachable"


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
        self._runtime_fallback = MemoryRateLimitStore()

    @property
    def store(self) -> RateLimitStore:
        return self._store if self._store is not None else get_rate_limit_store()

    async def _failed_accounts(self, key: str, member: str | None = None) -> tuple[int, int]:
        global _backend_name
        # Always mirror locally so a Redis outage does not erase recent history.
        local = await self._runtime_fallback.failed_accounts(key, member=member)
        try:
            shared = await self.store.failed_accounts(key, member=member)
            return max((local, shared), key=lambda result: result[0])
        except Exception:
            _backend_name = "memory-fallback"
            return local

    @staticmethod
    def _blocked(retry: int):
        return JSONResponse(
            {"detail": "Çok fazla istek gönderildi. Lütfen kısa süre sonra tekrar deneyin."},
            status_code=429, headers={"Retry-After": str(retry or 60)},
        )

    async def dispatch(self, request, call_next):
        global _backend_name

        path = request.url.path or "/"
        if _is_exempt(path):
            return await call_next(request)

        client = _client_ip(request)
        login = request.method == "POST" and path.rstrip("/") == "/api/v1/auth/login"
        spray_key = f"{client}:login-spray"
        if login:
            count, retry = await self._failed_accounts(spray_key)
            if count >= settings.login_spray_account_limit:
                logger.warning("auth_password_spray_blocked source=%s distinct_accounts=%s", client, count)
                return self._blocked(retry)
        auth = _is_auth(path)
        limit = self.auth_limit if auth else self.limit
        key = f"{client}:auth" if auth else f"{client}:{path}"
        checks = [(key, limit, 60)]
        if request.method == "POST" and path.rstrip("/") in (
            "/api/v1/auth/login", "/api/v1/auth/mfa/verify",
        ):
            # Shared across accounts and workers; also slow sustained spraying
            # that stays below the per-minute limit. Keep NAT capacity tunable.
            checks.append((f"{client}:login-window", settings.login_source_window_limit, 600))
            try:
                network = ipaddress.ip_network(
                    f"{client}/{64 if ':' in client else 24}", strict=False
                )
            except ValueError:
                network = None
            if network is not None:
                checks.append((f"{network}:login-subnet", settings.login_subnet_window_limit, 600))
        for check_key, check_limit, window_sec in checks:
            try:
                allowed, retry = await self.store.hit(check_key, limit=check_limit, window_sec=window_sec)
            except Exception as exc:
                logger.warning("Rate limit store error; using memory fallback: %s", exc)
                _backend_name = "memory-fallback"
                allowed, retry = await self._runtime_fallback.hit(
                    check_key, limit=check_limit, window_sec=window_sec,
                )
            if not allowed:
                break
        if not allowed:
            return JSONResponse(
                {"detail": "Çok fazla istek gönderildi. Lütfen kısa süre sonra tekrar deneyin."},
                status_code=429,
                headers={"Retry-After": str(retry or 60)},
            )
        identifier = None
        if login:
            try:
                payload = await request.json()
                value = payload.get("email") if isinstance(payload, dict) else None
                if isinstance(value, str) and value.strip():
                    identifier = hmac.new(settings.secret_key.encode(), value.strip().casefold().encode(), hashlib.sha256).hexdigest()
            except (ValueError, UnicodeError):
                pass  # Request validation still owns malformed JSON responses.
        response = await call_next(request)
        if login and identifier and response.status_code == 401:
            count, retry = await self._failed_accounts(spray_key, identifier)
            if count > settings.login_spray_account_limit:
                return self._blocked(retry)
            if count == settings.login_spray_account_limit:
                logger.warning("auth_password_spray_detected source=%s distinct_accounts=%s", client, count)
        return response
