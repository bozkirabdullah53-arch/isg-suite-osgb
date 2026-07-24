import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.core.config import validate_runtime_settings, settings
from app.core.rate_limit import SimpleRateLimitMiddleware, rate_limit_backend
from app.main import app


def test_rate_limit_middleware_registered():
    names = [m.cls.__name__ for m in app.user_middleware if hasattr(m, "cls")]
    assert "SimpleRateLimitMiddleware" in names


def test_rate_limit_returns_429_when_exceeded():
    async def ok(_request):
        return PlainTextResponse("ok")

    mini = Starlette(routes=[Route("/ping", ok)])
    mini.add_middleware(SimpleRateLimitMiddleware, requests_per_minute=3, auth_requests_per_minute=3)
    client = TestClient(mini)
    assert client.get("/ping").status_code == 200
    assert client.get("/ping").status_code == 200
    assert client.get("/ping").status_code == 200
    blocked = client.get("/ping")
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
    detail = blocked.json()["detail"].lower()
    assert "fazla" in detail


def test_health_path_exempt_from_rate_limit():
    async def ok(_request):
        return PlainTextResponse("ok")

    mini = Starlette(routes=[Route("/health", ok)])
    mini.add_middleware(SimpleRateLimitMiddleware, requests_per_minute=2, auth_requests_per_minute=2)
    client = TestClient(mini)
    for _ in range(6):
        assert client.get("/health").status_code == 200


def test_auth_path_has_stricter_bucket():
    async def ok(_request):
        return PlainTextResponse("ok")

    mini = Starlette(routes=[Route("/api/v1/auth/login", ok, methods=["POST"])])
    mini.add_middleware(SimpleRateLimitMiddleware, requests_per_minute=100, auth_requests_per_minute=2)
    client = TestClient(mini)
    assert client.post("/api/v1/auth/login").status_code == 200
    assert client.post("/api/v1/auth/login").status_code == 200
    assert client.post("/api/v1/auth/login").status_code == 429


def test_xff_separates_clients():
    async def ok(_request):
        return PlainTextResponse("ok")

    mini = Starlette(routes=[Route("/ping", ok)])
    mini.add_middleware(SimpleRateLimitMiddleware, requests_per_minute=2, auth_requests_per_minute=2)
    client = TestClient(mini)
    assert client.get("/ping", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
    assert client.get("/ping", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
    assert client.get("/ping", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 429
    # Farklı istemci etkilenmez
    assert client.get("/ping", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 200


class _FakeRedis:
    def __init__(self):
        self.counts: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    async def incr(self, key):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key, ttl):
        self.ttls[key] = ttl
        return True

    async def ttl(self, key):
        return self.ttls.get(key, 60)


def test_redis_store_blocks_over_limit():
    import asyncio

    from app.core.rate_limit import RedisRateLimitStore

    store = RedisRateLimitStore(_FakeRedis())

    async def _run():
        assert (await store.hit("k", limit=2))[0] is True
        assert (await store.hit("k", limit=2))[0] is True
        allowed, retry = await store.hit("k", limit=2)
        assert allowed is False
        assert retry >= 1

    asyncio.run(_run())


def test_rate_limit_backend_default_memory():
    from app.core.rate_limit import reset_rate_limit_store_for_tests

    reset_rate_limit_store_for_tests()
    assert rate_limit_backend() in {"memory", "memory-fallback", "redis"}


def test_request_id_header_present():
    from starlette.applications import Starlette
    from starlette.responses import PlainTextResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    from app.core.request_id import RequestIdMiddleware

    async def ok(_request):
        return PlainTextResponse("ok")

    mini = Starlette(routes=[Route("/ping", ok)])
    mini.add_middleware(RequestIdMiddleware)
    client = TestClient(mini)
    r = client.get("/ping")
    assert r.status_code == 200
    assert r.headers.get("x-request-id")
    custom = client.get("/ping", headers={"X-Request-ID": "client-trace-1"})
    assert custom.headers.get("x-request-id") == "client-trace-1"


def test_production_allows_strong_secret(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "secret_key", "x" * 40)
    validate_runtime_settings()


def test_production_blocks_default_secret(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "secret_key", "change-me-in-production-at-least-32-characters!")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        validate_runtime_settings()


def test_qa_env_allows_test_secret(monkeypatch):
    monkeypatch.setattr(settings, "environment", "qa")
    monkeypatch.setattr(settings, "secret_key", "qa-test-secret-key-at-least-32-characters-ok")
    validate_runtime_settings()
