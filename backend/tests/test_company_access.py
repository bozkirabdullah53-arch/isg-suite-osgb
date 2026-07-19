"""Görevlendirme bazlı firma erişim testleri."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api import company_access as ca
from app.models.entities import UserRole


def test_company_admin_only_own_firm(monkeypatch):
    db = MagicMock()
    user = SimpleNamespace(role=UserRole.COMPANY_ADMIN, company_id=3, osgb_id=1, email="a@b.com", full_name="A")
    monkeypatch.setattr(ca, "assigned_company_ids", lambda _db, _u: [3])
    assert ca.ensure_company_access(db, user, 3) == 3
    with pytest.raises(HTTPException) as exc:
        ca.ensure_company_access(db, user, 9)
    assert exc.value.status_code == 403


def test_specialist_only_assigned_firms(monkeypatch):
    db = MagicMock()
    user = SimpleNamespace(
        role=UserRole.SAFETY_SPECIALIST,
        company_id=None,
        osgb_id=1,
        email="uzman@test.com",
        full_name="Test Uzman",
    )
    monkeypatch.setattr(ca, "assigned_company_ids", lambda _db, _u: [10, 12])
    assert ca.ensure_company_access(db, user, 10) == 10
    with pytest.raises(HTTPException) as exc:
        ca.ensure_company_access(db, user, 99)
    assert exc.value.status_code == 403
    assert "görevlendirildiğiniz" in exc.value.detail.lower() or "görev" in exc.value.detail.lower()


def test_specialist_no_assignment_message(monkeypatch):
    db = MagicMock()
    user = SimpleNamespace(
        role=UserRole.SAFETY_SPECIALIST,
        company_id=None,
        osgb_id=1,
        email="x@y.com",
        full_name="X",
    )
    monkeypatch.setattr(ca, "assigned_company_ids", lambda _db, _u: [])
    with pytest.raises(HTTPException) as exc:
        ca.ensure_company_access(db, user, 1)
    assert exc.value.status_code == 403
    assert "atanmış" in exc.value.detail.lower() or "görev" in exc.value.detail.lower()
