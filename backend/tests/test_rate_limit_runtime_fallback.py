from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.rate_limit import MemoryRateLimitStore, SimpleRateLimitMiddleware, rate_limit_backend


class _FailingStore:
    async def hit(self, key: str, *, limit: int, window_sec: int = 60):
        _ = key, limit, window_sec
        raise ConnectionError("redis unavailable")


def test_runtime_store_failure_keeps_local_rate_limit_protection():
    app = FastAPI()
    app.add_middleware(
        SimpleRateLimitMiddleware,
        requests_per_minute=2,
        auth_requests_per_minute=1,
        store=_FailingStore(),
    )

    @app.get("/api/data")
    def data():
        return {"ok": True}

    with TestClient(app) as client:
        headers = {"X-Forwarded-For": "203.0.113.10"}
        assert client.get("/api/data", headers=headers).status_code == 200
        assert client.get("/api/data", headers=headers).status_code == 200
        third = client.get("/api/data", headers=headers)

    assert third.status_code == 429
    assert int(third.headers["Retry-After"]) >= 1
    assert rate_limit_backend() == "memory-fallback"


def test_auth_limit_remains_stricter_during_store_failure():
    app = FastAPI()
    app.add_middleware(
        SimpleRateLimitMiddleware,
        requests_per_minute=10,
        auth_requests_per_minute=1,
        store=_FailingStore(),
    )

    @app.post("/api/v1/auth/login")
    def login():
        return {"ok": True}

    with TestClient(app) as client:
        headers = {"X-Forwarded-For": "203.0.113.20"}
        assert client.post("/api/v1/auth/login", headers=headers).status_code == 200
        second = client.post("/api/v1/auth/login", headers=headers)

    assert second.status_code == 429


def test_public_verification_uses_dedicated_low_limit(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "verification_requests_per_minute", 2)
    app = FastAPI()
    app.add_middleware(
        SimpleRateLimitMiddleware,
        requests_per_minute=100,
        auth_requests_per_minute=100,
        store=MemoryRateLimitStore(),
    )

    @app.get("/api/v1/trainings/remote/certificates/verify/{code}")
    def verify(code: str):
        return {"code": code}

    with TestClient(app) as client:
        headers = {"X-Forwarded-For": "203.0.113.40"}
        assert client.get("/api/v1/trainings/remote/certificates/verify/first-code", headers=headers).status_code == 200
        assert client.get("/api/v1/trainings/remote/certificates/verify/second-code", headers=headers).status_code == 200
        blocked = client.get("/api/v1/trainings/remote/certificates/verify/third-code", headers=headers)

    assert blocked.status_code == 429
