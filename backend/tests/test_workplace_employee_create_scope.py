from types import SimpleNamespace

import pytest

from app.api.employees import resolve_create_company_id
from app.models.entities import UserRole


def test_workplace_manager_create_ignores_missing_company_id(monkeypatch):
    user = SimpleNamespace(
        role=UserRole.COMPANY_ADMIN,
        company_id=42,
        email="ik@example.com",
    )
    monkeypatch.setattr("app.api.employees.check_company", lambda _db, _user, _cid: None)

    assert resolve_create_company_id(None, user, None) == 42
    assert resolve_create_company_id(None, user, 42) == 42


def test_workplace_manager_create_rejects_foreign_company(monkeypatch):
    user = SimpleNamespace(
        role=UserRole.COMPANY_ADMIN,
        company_id=42,
        email="ik@example.com",
    )
    monkeypatch.setattr("app.api.employees.check_company", lambda _db, _user, _cid: None)

    with pytest.raises(Exception) as exc:
        resolve_create_company_id(None, user, 99)
    assert getattr(exc.value, "status_code", None) == 403
