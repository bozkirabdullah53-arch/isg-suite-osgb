import pytest

from app.core.config import validate_runtime_settings, settings
from app.main import app


def test_rate_limit_middleware_registered():
    names = [m.cls.__name__ for m in app.user_middleware if hasattr(m, "cls")]
    assert "SimpleRateLimitMiddleware" in names


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
