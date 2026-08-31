from types import SimpleNamespace

from app.core.config import contextual_assistant_active, settings
from app.services import contextual_assistant as assistant
from app.services.contextual_assistant import answer, sanitize_context


def user(role="read_only", company_id=None):
    return SimpleNamespace(role=SimpleNamespace(value=role), company_id=company_id, id=7)


class DummySession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_context_is_sanitized_and_server_role_wins():
    context = sanitize_context({"user": {"role": "global_admin", "accessibleModules": ["risk"]}, "state": {"national_id": "123", "companySelected": True}}, user())
    assert context["user"]["role"] == "read_only"
    assert "risk" not in context["user"]["accessibleModules"]
    assert "national_id" not in context["state"]
    assert context["state"]["companySelected"] is True


def test_verified_answer_has_no_provider_dependency(monkeypatch):
    monkeypatch.setattr(settings, "contextual_assistant_enabled", True)
    monkeypatch.setattr(settings, "contextual_assistant_force_off", False)
    monkeypatch.setattr(settings, "contextual_assistant_api_key", None)
    monkeypatch.setattr(assistant, "SessionLocal", lambda: DummySession())
    monkeypatch.setattr(assistant, "managed_config", lambda db: None)
    result = answer(question="Bu sayfada ne yapabilirim?", raw_context={"currentPage": {"id": "employees", "module": "employees", "title": "Personel", "purpose": "Personel"}, "user": {"accessibleModules": ["employees"]}, "capabilities": ["employee.create"]}, user=user("safety_specialist"))
    assert result["source"] == "verified"
    assert "Personel" in result["message"]


def test_managed_ai_panel_is_assistant_source_of_truth(monkeypatch):
    monkeypatch.setattr(settings, "vision_analysis_force_off", False)
    monkeypatch.setattr(settings, "contextual_assistant_api_key", "legacy-key")
    monkeypatch.setattr(settings, "contextual_assistant_api_url", "https://legacy.example/v1")
    monkeypatch.setattr(settings, "contextual_assistant_model", "legacy-model")
    monkeypatch.setattr(assistant, "SessionLocal", lambda: DummySession())
    monkeypatch.setattr(assistant, "managed_config", lambda db: {
        "managed": True,
        "enabled": True,
        "provider": "custom_openai",
        "base_url": "https://api.xkiro.com/v1",
        "model": "qwen/qwen3-vl-plus:free",
        "timeout_sec": 90,
        "api_key": "xkiro-secret",
        "api_key_configured": True,
    })
    provider = assistant._provider_config()
    assert provider is not None
    assert provider["source"] == "global_panel"
    assert provider["api_url"] == "https://api.xkiro.com/v1"
    assert provider["model"] == "qwen/qwen3-vl-plus:free"
    assert provider["api_key"] == "xkiro-secret"
    assert provider["timeout_sec"] == 90


def test_managed_disabled_does_not_fall_back_to_legacy_external_ai(monkeypatch):
    monkeypatch.setattr(settings, "contextual_assistant_api_key", "legacy-key")
    monkeypatch.setattr(settings, "contextual_assistant_api_url", "https://legacy.example/v1")
    monkeypatch.setattr(settings, "contextual_assistant_model", "legacy-model")
    monkeypatch.setattr(assistant, "SessionLocal", lambda: DummySession())
    monkeypatch.setattr(assistant, "managed_config", lambda db: {
        "managed": True,
        "enabled": False,
        "provider": "custom_openai",
        "base_url": "https://api.xkiro.com/v1",
        "model": "qwen/qwen3-vl-plus:free",
        "timeout_sec": 90,
        "api_key": "xkiro-secret",
        "api_key_configured": True,
    })
    assert assistant._provider_config() is None


def test_missing_managed_config_does_not_use_a_second_contextual_provider(monkeypatch):
    monkeypatch.setattr(settings, "contextual_assistant_api_key", "legacy-key")
    monkeypatch.setattr(settings, "contextual_assistant_api_url", "https://legacy.example/v1")
    monkeypatch.setattr(settings, "contextual_assistant_model", "legacy-model")
    monkeypatch.setattr(assistant, "SessionLocal", lambda: DummySession())
    monkeypatch.setattr(assistant, "managed_config", lambda db: None)
    assert assistant._provider_config() is None


def test_force_off_isolated(monkeypatch):
    monkeypatch.setattr(settings, "contextual_assistant_force_off", True)
    assert contextual_assistant_active() is False
    assert answer(question="Yardım", raw_context={}, user=user())["source"] == "disabled"
