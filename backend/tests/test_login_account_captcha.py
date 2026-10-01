"""Catch distributed guesses, alias bypass and CAPTCHA fail-open regressions."""
import httpx
import pytest

from app.core.config import settings
from test_faz0_security import client


@pytest.fixture(autouse=True)
def captcha_settings(monkeypatch):
    from app.services import auth_security
    monkeypatch.setattr(auth_security, "_login_hits", {})
    for key, value in {
        "login_captcha_enabled": True,
        "login_account_window_limit": 3,
        "turnstile_site_key": "test-public-key",
        "turnstile_secret_key": "test-secret-key",
        "turnstile_allowed_hostnames": "www.isgsuite.tr,isgsuite.tr",
    }.items():
        monkeypatch.setitem(settings.__dict__, key, value)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_shared_counter_failure_requires_captcha_immediately():
    from app.core import rate_limit
    class Unavailable:
        async def account_attempt(self, *args, **kwargs):
            raise ConnectionError("unavailable")
    rate_limit.reset_rate_limit_store_for_tests(Unavailable())
    allowed, retry = await rate_limit.login_account_budget("account", 10)
    assert not allowed
    assert 1 <= retry <= 600


@pytest.mark.anyio
async def test_production_memory_fallback_requires_captcha(monkeypatch):
    from app.core import rate_limit
    monkeypatch.setitem(settings.__dict__, "environment", "production")
    rate_limit.reset_rate_limit_store_for_tests()
    allowed, retry = await rate_limit.login_account_budget("account", 10)
    assert not allowed
    assert 1 <= retry <= 600


def test_unused_captcha_token_does_not_trigger_provider_io(client, monkeypatch):
    def unavailable(*args, **kwargs):
        raise httpx.ConnectError("unavailable")
    monkeypatch.setattr(httpx, "post", unavailable)
    result = login(client, 0, password="UzmanPass123!", captcha_token="junk")
    assert result.status_code == 200
    assert result.json().get("access_token")


def test_provider_verification_does_not_hold_a_database_connection(client, monkeypatch):
    from sqlalchemy import event
    import app.core.database as dbmod
    exhaust(client)
    checked_out = [0]
    def checkout(*args): checked_out[0] += 1
    def checkin(*args): checked_out[0] -= 1
    event.listen(dbmod.engine, "checkout", checkout)
    event.listen(dbmod.engine, "checkin", checkin)
    def provider(*args, **kwargs):
        assert checked_out[0] == 0
        return httpx.Response(200, json={"success": True, "hostname": "www.isgsuite.tr", "action": "login"}, request=httpx.Request("POST", args[0]))
    monkeypatch.setattr(httpx, "post", provider)
    try:
        assert login(client, 4, password="UzmanPass123!", captcha_token="valid").json().get("access_token")
    finally:
        event.remove(dbmod.engine, "checkout", checkout)
        event.remove(dbmod.engine, "checkin", checkin)


@pytest.mark.anyio
async def test_account_budget_is_shared_and_atomic_across_workers():
    import os
    from uuid import uuid4
    import asyncio
    import redis.asyncio as redis_async
    from app.core.rate_limit import RedisRateLimitStore
    url = os.environ.get("PENTEST_REDIS_URL")
    if not url:
        pytest.skip("Redis integration uses the dedicated CI service")
    connection = redis_async.from_url(url)
    key = "test-account-" + uuid4().hex
    one = RedisRateLimitStore(connection)
    two = RedisRateLimitStore(connection)
    try:
        results = await asyncio.gather(*[
            (one if n % 2 else two).account_attempt(key, limit=10) for n in range(20)
        ])
        assert sum(allowed for allowed, _ in results) == 10
        assert all(1 <= retry <= 600 for allowed, retry in results if not allowed)
    finally:
        await connection.delete("isg:rl:" + key + ":account-attempts")
        await connection.aclose()


def login(client, n, *, email="uzman@example.com", password="WrongPassword!", captcha_token=None):
    return client.post("/api/v1/auth/login", json={
        "email": email, "password": password, "captcha_token": captcha_token,
    }, headers={"X-Forwarded-For": f"198.51.{n}.10"})


def exhaust(client):
    for n in range(3):
        assert login(client, n).status_code == 401


def test_rotating_ips_cannot_obtain_access_without_captcha(client):
    exhaust(client)
    blocked = login(client, 4, password="UzmanPass123!")
    assert blocked.status_code == 429
    assert blocked.json()["detail"]["code"] == "login_captcha_required"
    assert 1 <= int(blocked.headers["Retry-After"]) <= 600
    assert not blocked.json().get("access_token")


def test_email_and_username_share_the_account_budget(client):
    import app.core.database as dbmod
    from app.models.entities import User
    with dbmod.SessionLocal() as db:
        db.query(User).filter_by(email="uzman@example.com").one().username = "CaptchaUzman"
        db.commit()
    for n, name in enumerate(("CaptchaUzman", " UZMAN@example.com ", "captchaUZMAN")):
        assert login(client, n, email=name).status_code == 401
    assert login(client, 4, email="uzman@example.com").status_code == 429


def test_unknown_accounts_are_challenged_too_without_account_enumeration(client):
    for n in range(3):
        assert login(client, n, email="nobody@example.invalid").status_code == 401
    assert login(client, 4, email="NOBODY@example.invalid").status_code == 429


def test_a_different_account_remains_usable(client):
    exhaust(client)
    assert login(client, 4, email="hekim@example.com", password="HekimPass123!").json().get("access_token")


@pytest.mark.parametrize("validation", [
    {"success": False, "error-codes": ["timeout-or-duplicate"]},
    {"success": True, "hostname": "attacker.example", "action": "login"},
    {"success": True, "hostname": "www.isgsuite.tr", "action": "other-form"},
    {"success": "true", "hostname": "www.isgsuite.tr", "action": "login"},
])
def test_invalid_or_wrong_origin_captcha_never_grants_access(client, monkeypatch, validation):
    exhaust(client)
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: httpx.Response(200, json=validation, request=httpx.Request("POST", a[0])))
    assert login(client, 4, password="UzmanPass123!", captcha_token="fake-token").status_code == 429


def test_valid_captcha_allows_the_real_user_without_unlocking_attackers(client, monkeypatch):
    exhaust(client)
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: httpx.Response(200, json={
        "success": True, "hostname": "www.isgsuite.tr", "action": "login",
    }, request=httpx.Request("POST", a[0])))
    result = login(client, 4, password="UzmanPass123!", captcha_token="valid-token")
    assert result.status_code == 200
    assert result.json().get("access_token")
    assert login(client, 5).status_code == 429


def test_provider_failure_never_bypasses_captcha(client, monkeypatch):
    exhaust(client)
    def unavailable(*a, **kw):
        raise httpx.ConnectError("unavailable")
    monkeypatch.setattr(httpx, "post", unavailable)
    assert login(client, 4, password="UzmanPass123!", captcha_token="token").status_code == 503


def test_captcha_is_not_a_password_or_mfa_bypass(client, monkeypatch):
    exhaust(client)
    monkeypatch.setattr(httpx, "post", lambda *a, **kw: httpx.Response(200, json={
        "success": True, "hostname": "www.isgsuite.tr", "action": "login",
    }, request=httpx.Request("POST", a[0])))
    assert login(client, 4, captcha_token="valid-token").status_code == 401
    import app.core.database as dbmod
    import pyotp
    from app.models.entities import User
    from app.services.auth_security import encrypt_secret
    with dbmod.SessionLocal() as db:
        user = db.query(User).filter_by(email="uzman@example.com").one()
        user.mfa_enabled = True
        user.mfa_secret_encrypted = encrypt_secret(pyotp.random_base32())
        db.commit()
    result = login(client, 5, password="UzmanPass123!", captcha_token="another-valid-token")
    assert result.json()["mfa_required"]
    assert not result.json().get("access_token")


def test_unconfigured_rollout_preserves_existing_login(client, monkeypatch):
    monkeypatch.setitem(settings.__dict__, "login_captcha_enabled", False)
    exhaust(client)
    assert login(client, 4, password="UzmanPass123!").json().get("access_token")


def test_public_configuration_never_exposes_secret(client):
    result = client.get("/api/v1/auth/login-protection")
    assert result.status_code == 200
    assert result.json() == {"enabled": True, "site_key": "test-public-key"}


def test_protected_health_requires_auth_but_liveness_has_no_body(client, monkeypatch):
    monkeypatch.setitem(settings.__dict__, "health_auth_required", True)
    assert client.get("/health").status_code == 401
    live = client.get("/live")
    assert live.status_code == 204
    assert live.content == b""
    api_live = client.get("/api/v1/live")
    assert api_live.status_code == 204
    assert api_live.content == b""
    assert client.get("/api/v1/system/health").status_code == 401


def test_health_rollout_preserves_render_until_probe_is_switched(client, monkeypatch):
    monkeypatch.setitem(settings.__dict__, "health_auth_required", False)
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/live").status_code == 204


def test_health_is_only_available_to_global_admin(client, monkeypatch):
    from app.core.security import create_access_token
    import app.core.database as dbmod
    from app.models.entities import User, UserRole
    monkeypatch.setitem(settings.__dict__, "health_auth_required", True)
    with dbmod.SessionLocal() as db:
        user = db.query(User).filter_by(email="uzman@example.com").one()
        token = create_access_token(str(user.id))
        assert client.get("/health", headers={"Authorization": f"Bearer {token}"}).status_code == 403
        user.role = UserRole.GLOBAL_ADMIN
        db.commit()
    assert client.get("/health", headers={"Authorization": f"Bearer {token}"}).json() == {"status": "ok"}
    assert client.get("/health", headers={"Authorization": "Bearer invalid"}).status_code == 401
