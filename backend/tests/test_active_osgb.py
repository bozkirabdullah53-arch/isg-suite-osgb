"""active_osgb resolution for global admin."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.operations import active_osgb
from app.models.entities import UserRole


def test_ga_uses_user_osgb_when_no_query():
    user = SimpleNamespace(role=UserRole.GLOBAL_ADMIN, osgb_id=7)
    assert active_osgb(user, requested=None, db=None) == 7


def test_ga_prefers_query_param():
    user = SimpleNamespace(role=UserRole.GLOBAL_ADMIN, osgb_id=7)
    assert active_osgb(user, requested=3, db=None) == 3


def test_ga_without_osgb_raises():
    user = SimpleNamespace(role=UserRole.GLOBAL_ADMIN, osgb_id=None)
    with pytest.raises(HTTPException) as ei:
        active_osgb(user, requested=None, db=None)
    assert ei.value.status_code == 400
