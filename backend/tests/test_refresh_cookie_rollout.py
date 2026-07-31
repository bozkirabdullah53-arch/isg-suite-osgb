"""P1-01 refresh cookie prod rollout helpers."""
from app.core import auth_cookies as ac
from app.core.config import settings


def test_prod_refresh_on_by_default(monkeypatch):
    settings.environment = "production"
    settings.auth_refresh_cookie_enabled = False
    settings.auth_refresh_cookie_force_off = False
    assert ac.refresh_cookie_enabled() is True
    assert ac.access_token_ttl_minutes() == settings.access_token_expire_minutes_short


def test_prod_refresh_force_off(monkeypatch):
    settings.environment = "production"
    settings.auth_refresh_cookie_force_off = True
    assert ac.refresh_cookie_enabled() is False
    settings.auth_refresh_cookie_force_off = False


def test_dev_requires_explicit_flag():
    settings.environment = "development"
    settings.auth_refresh_cookie_enabled = False
    settings.auth_refresh_cookie_force_off = False
    assert ac.refresh_cookie_enabled() is False
    settings.auth_refresh_cookie_enabled = True
    assert ac.refresh_cookie_enabled() is True
    settings.auth_refresh_cookie_enabled = False
