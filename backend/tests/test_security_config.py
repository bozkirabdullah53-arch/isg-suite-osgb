import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.core.config import validate_runtime_settings, settings
from app.core.rate_limit import SimpleRateLimitMiddleware
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
