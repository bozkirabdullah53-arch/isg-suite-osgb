"""Görevlendirme bazlı firma erişim testleri."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api import company_access as ca
from app.core.tenant_context import clear_tenant
from app.models.entities import ProfessionalType, UserRole


@pytest.fixture(autouse=True)
def _clear_tenant():
    clear_tenant()
    yield
    clear_tenant()


def test_company_admin_only_own_firm(monkeypatch):
    db = MagicMock()
    user = SimpleNamespace(role=UserRole.COMPANY_ADMIN, company_id=3, osgb_id=1, email="a@b.com", full_name="A")
    monkeypatch.setattr(ca, "assigned_company_ids", lambda _db, _u: [3])
    assert ca.ensure_company_access(db, user, 3) == 3
    with pytest.raises(HTTPException) as exc:
        ca.ensure_company_access(db, user, 9)
    assert exc.value.status_code == 403


def test_specialist_scope_is_strict_even_with_legacy_membership():
    """Uzman erişimi üyelik/user.company_id ile aktif görevlendirmeyi aşmamalı."""
    assert UserRole.SAFETY_SPECIALIST in ca._STRICT_HEALTH_ASSIGNMENT_ROLES


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


def test_duplicate_professional_names_fail_closed_when_email_does_not_match():
    """Aynı isimli iki uzman varken ilk DB satırı yetki kaynağı olamaz."""
    db = MagicMock()
    db.scalar.return_value = None
    db.scalars.return_value.all.return_value = [
        SimpleNamespace(id=11, full_name="Ahmet Yılmaz", professional_type=ProfessionalType.SAFETY_SPECIALIST),
        SimpleNamespace(id=22, full_name="Ahmet Yılmaz", professional_type=ProfessionalType.SAFETY_SPECIALIST),
    ]
    user = SimpleNamespace(
        role=UserRole.SAFETY_SPECIALIST,
        company_id=None,
        osgb_id=7,
        email="hesap@example.com",
        full_name="Ahmet Yılmaz",
    )

    assert ca.find_professional_for_user(db, user) is None


def test_unique_legacy_professional_name_match_is_preserved():
    """Eski kurulumlarda tek isim eşleşmesi geriye dönük uyumluluğu korur."""
    db = MagicMock()
    db.scalar.return_value = None
    expected = SimpleNamespace(
        id=11,
        full_name="Ahmet Yılmaz",
        professional_type=ProfessionalType.SAFETY_SPECIALIST,
    )
    db.scalars.return_value.all.return_value = [expected]
    user = SimpleNamespace(
        role=UserRole.SAFETY_SPECIALIST,
        company_id=None,
        osgb_id=7,
        email="hesap@example.com",
        full_name="Ahmet Yılmaz",
    )

    assert ca.find_professional_for_user(db, user) is expected


def test_duplicate_user_names_do_not_auto_link_to_professional():
    """Startup rol senkronu aynı isimli hesaplardan rastgele birini değiştirmemeli."""
    db = MagicMock()
    db.scalar.return_value = None
    db.scalars.return_value.all.return_value = [
        SimpleNamespace(id=101, role=UserRole.SAFETY_SPECIALIST, full_name="Ayşe Kaya", is_active=True),
        SimpleNamespace(id=202, role=UserRole.SAFETY_SPECIALIST, full_name="Ayşe Kaya", is_active=True),
    ]
    professional = SimpleNamespace(
        id=55,
        is_active=True,
        email=None,
        full_name="Ayşe Kaya",
        osgb_id=9,
        professional_type=ProfessionalType.SAFETY_SPECIALIST,
    )

    assert ca.link_user_to_professional(db, professional) is None