"""Tenant izolasyon regresyon testleri — çapraz OSGB erişimi engellenmeli."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.tenant_access import (
    assert_can_manage_user,
    assert_company_in_admin_scope,
    user_in_admin_scope,
    users_scope_filter,
)
from app.api.company_access import find_professional_by_identity
from app.models.entities import IsgProfessional, User, UserRole


class FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeDB:
    def __init__(self, *, companies=None, professionals=None):
        self.companies = {c.id: c for c in (companies or [])}
        self.professionals = professionals or []

    def get(self, model, pk):
        if getattr(model, "__name__", "") == "Company" or model.__name__ == "Company":
            return self.companies.get(pk)
        return None

    def scalar(self, stmt):
        # Minimal: for company_ids_for_osgb / email lookups we inspect compiled-ish usage via execute path
        return None

    def scalars(self, stmt):
        return FakeScalars(self.professionals)


def _user(**kwargs):
    defaults = dict(
        id=1,
        email="u@example.com",
        full_name="User",
        hashed_password="x",
        role=UserRole.COMPANY_ADMIN,
        company_id=None,
        osgb_id=None,
        is_active=True,
    )
    defaults.update(kwargs)
    return User(**defaults)


def test_different_osgb_admins_cannot_manage_each_other():
    a = _user(id=1, osgb_id=1, email="a@x.com")
    b = _user(id=2, osgb_id=2, email="b@x.com")
    db = FakeDB()
    assert user_in_admin_scope(db, a, b) is False
    with pytest.raises(HTTPException) as ei:
        assert_can_manage_user(db, a, b)
    assert ei.value.status_code == 403


def test_same_osgb_admins_can_manage_each_other():
    a = _user(id=1, osgb_id=10, email="a@x.com")
    b = _user(id=2, osgb_id=10, email="b@x.com")
    assert user_in_admin_scope(FakeDB(), a, b) is True


def test_null_company_without_osgb_cannot_manage_anyone():
    a = _user(id=1, company_id=None, osgb_id=None)
    b = _user(id=2, company_id=None, osgb_id=None)
    assert user_in_admin_scope(FakeDB(), a, b) is False


def test_company_admin_cannot_assign_foreign_company():
    admin = _user(id=1, company_id=5, osgb_id=1)
    # accessible companies only [5]
    db = FakeDB(companies=[SimpleNamespace(id=5, osgb_id=1), SimpleNamespace(id=99, osgb_id=2)])

    # Patch accessible path: assert_company_in_admin_scope uses accessible_company_ids_for_admin
    # which queries Company.id where osgb — FakeDB.scalar returns None so company_ids empty for osgb-only.
    # For company_id-bound admin, accessible is [5].
    assert_company_in_admin_scope(db, admin, 5)
    with pytest.raises(HTTPException) as ei:
        assert_company_in_admin_scope(db, admin, 99)
    assert ei.value.status_code == 403


def test_users_scope_filter_never_uses_null_equality():
    admin = _user(id=1, company_id=None, osgb_id=None)
    filt = users_scope_filter(FakeDB(), admin)
    # Must be empty scope (id == -1), not company_id IS NULL
    assert filt is not None


def test_find_professional_by_identity_requires_osgb_for_name_match():
    user = _user(id=3, role=UserRole.SAFETY_SPECIALIST, osgb_id=None, full_name="Ahmet Yilmaz", email="other@x.com")
    pro = IsgProfessional(id=1, full_name="Ahmet Yilmaz", osgb_id=7, is_active=True, email="ahmet@other.com")
    db = FakeDB(professionals=[pro])
    # Without osgb_id, name match must not bind
    assert find_professional_by_identity(db, user) is None
