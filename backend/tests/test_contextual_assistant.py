from types import SimpleNamespace

from app.core.config import contextual_assistant_active, settings
from app.services.contextual_assistant import answer, sanitize_context


def user(role="read_only", company_id=None):
    return SimpleNamespace(role=SimpleNamespace(value=role), company_id=company_id, id=7)


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
    result = answer(question="Bu sayfada ne yapabilirim?", raw_context={"currentPage": {"id": "employees", "module": "employees", "title": "Personel", "purpose": "Personel"}, "user": {"accessibleModules": ["employees"]}, "capabilities": ["employee.create"]}, user=user("safety_specialist"))
    assert result["source"] == "verified"
    assert "Personel" in result["message"]


def test_force_off_isolated(monkeypatch):
    monkeypatch.setattr(settings, "contextual_assistant_force_off", True)
    assert contextual_assistant_active() is False
    assert answer(question="Yardım", raw_context={}, user=user())["source"] == "disabled"
