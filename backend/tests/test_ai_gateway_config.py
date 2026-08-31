from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import EisaPlatformSetting
from app.services import ai_gateway_config as gateway


@pytest.fixture(autouse=True)
def restore_vision_runtime():
    names = (
        "vision_analysis_enabled",
        "vision_analysis_force_off",
        "vision_provider",
        "vision_api_key",
        "vision_api_base_url",
        "vision_api_model",
        "vision_api_timeout_sec",
    )
    snapshot = {name: getattr(settings, name) for name in names}
    yield
    for name, value in snapshot.items():
        setattr(settings, name, value)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    EisaPlatformSetting.__table__.create(engine)
    with Session(engine) as session:
        yield session


def test_api_key_is_encrypted_and_public_config_never_returns_secret(db, monkeypatch):
    monkeypatch.setattr(settings, "secret_key", "test-secret-key-for-ai-gateway-32-bytes-minimum")
    monkeypatch.setattr(settings, "environment", "test")
    result = gateway.save_managed_config(
        db,
        enabled=True,
        provider="gemini",
        model="gemini-2.5-flash",
        base_url=None,
        timeout_sec=30,
        api_key="super-secret-gemini-key",
    )
    db.commit()
    stored = db.scalar(
        select(EisaPlatformSetting).where(
            EisaPlatformSetting.key == gateway.api_key_setting_key("gemini")
        )
    )
    assert stored is not None
    assert stored.value.startswith("enc:ai:v1:")
    assert "super-secret-gemini-key" not in stored.value
    assert result["api_key_configured"] is True
    assert "api_key" not in result
    assert gateway.managed_config(db)["api_key"] == "super-secret-gemini-key"


def test_named_provider_uses_official_base_url(db, monkeypatch):
    monkeypatch.setattr(settings, "secret_key", "test-secret-key-for-ai-gateway-32-bytes-minimum")
    monkeypatch.setattr(settings, "environment", "test")
    gateway.save_managed_config(
        db,
        enabled=True,
        provider="openai",
        model="gpt-4o",
        base_url="https://malicious.example/v1",
        timeout_sec=25,
        api_key="openai-test-key-123",
    )
    db.commit()
    assert gateway.managed_config(db)["base_url"] == "https://api.openai.com/v1"


def test_custom_provider_blocks_private_ip_in_production(db, monkeypatch):
    monkeypatch.setattr(settings, "secret_key", "test-secret-key-for-ai-gateway-32-bytes-minimum")
    monkeypatch.setattr(settings, "environment", "production")
    with pytest.raises(ValueError, match="yerel/özel ağ IP"):
        gateway.save_managed_config(
            db,
            enabled=True,
            provider="custom_openai",
            model="vision-model",
            base_url="https://127.0.0.1:8443/v1",
            timeout_sec=30,
            api_key="custom-test-key-123",
        )


def test_provider_keys_are_isolated(db, monkeypatch):
    monkeypatch.setattr(settings, "secret_key", "test-secret-key-for-ai-gateway-32-bytes-minimum")
    monkeypatch.setattr(settings, "environment", "test")
    gateway.save_managed_config(
        db,
        enabled=True,
        provider="openai",
        model="gpt-4o",
        base_url=None,
        timeout_sec=30,
        api_key="openai-only-secret-123",
    )
    db.commit()
    with pytest.raises(ValueError, match="bu sağlayıcıya ait API anahtarını"):
        gateway.save_managed_config(
            db,
            enabled=True,
            provider="gemini",
            model="gemini-2.5-flash",
            base_url=None,
            timeout_sec=30,
            api_key=None,
        )


def test_runtime_mapping_preserves_force_off(db, monkeypatch):
    monkeypatch.setattr(settings, "secret_key", "test-secret-key-for-ai-gateway-32-bytes-minimum")
    monkeypatch.setattr(settings, "environment", "test")
    monkeypatch.setattr(settings, "vision_analysis_force_off", True)
    gateway.save_managed_config(
        db,
        enabled=True,
        provider="gemini",
        model="gemini-2.5-flash",
        base_url=None,
        timeout_sec=45,
        api_key="gemini-test-key-123",
    )
    db.commit()
    gateway.apply_managed_runtime(db)
    assert settings.vision_provider == "api"
    assert settings.vision_api_base_url == "https://generativelanguage.googleapis.com/v1beta/openai"
    assert settings.vision_api_model == "gemini-2.5-flash"
    assert settings.vision_analysis_enabled is True
    assert settings.vision_analysis_force_off is True
