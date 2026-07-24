"""P1-03 TenantContext scaffold tests."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.tenant_context import (
    assert_osgb_access,
    bind_user_tenant,
    clear_tenant,
    current_tenant,
    require_osgb_id,
    require_tenant,
    tenant_from_user,
)
from app.models.entities import UserRole


def _user(**kwargs):
    base = dict(id=1, role=UserRole.COMPANY_ADMIN, osgb_id=7, company_id=3)
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_bind_and_clear_tenant():
    clear_tenant()
    assert current_tenant() is None
    bind_user_tenant(_user())
    ctx = require_tenant()
    assert ctx.osgb_id == 7
    assert ctx.company_id == 3
    assert ctx.is_global is False
    clear_tenant()
    assert current_tenant() is None


def test_global_admin_flags():
    ctx = tenant_from_user(_user(role=UserRole.GLOBAL_ADMIN, osgb_id=None, company_id=None))
    assert ctx.is_global is True
    assert ctx.has_osgb is False


def test_assert_osgb_access_allows_own():
    clear_tenant()
    bind_user_tenant(_user(osgb_id=7))
    assert_osgb_access(7)


def test_assert_osgb_access_blocks_other():
    clear_tenant()
    bind_user_tenant(_user(osgb_id=7))
    with pytest.raises(HTTPException) as exc:
        assert_osgb_access(99)
    assert exc.value.status_code == 403


def test_assert_osgb_access_global_ok():
    clear_tenant()
    bind_user_tenant(_user(role=UserRole.GLOBAL_ADMIN, osgb_id=None))
    assert_osgb_access(99)


def test_require_osgb_id_blocks_global():
    clear_tenant()
    bind_user_tenant(_user(role=UserRole.GLOBAL_ADMIN, osgb_id=None))
    with pytest.raises(HTTPException) as exc:
        require_osgb_id()
    assert exc.value.status_code == 400


def test_require_osgb_id_ok_for_company_admin():
    clear_tenant()
    bind_user_tenant(_user(osgb_id=12))
    assert require_osgb_id() == 12


def test_tenant_middleware_registered():
    from app.main import app

    names = [m.cls.__name__ for m in app.user_middleware if hasattr(m, "cls")]
    assert "TenantContextMiddleware" in names
