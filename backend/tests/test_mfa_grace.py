"""FAZ 1 — MFA erteleme, uzman kayıt (hayalet OSGB yok)."""
from datetime import datetime, timedelta

from app.models.entities import User, UserRole
from app.services.auth_security import mfa_setup_grace_active


def _user(**kwargs):
    defaults = dict(
        email="osgb@example.com",
        full_name="OSGB Admin",
        hashed_password="x",
        role=UserRole.COMPANY_ADMIN,
        company_id=None,
        osgb_id=1,
        mfa_enabled=False,
        created_at=datetime.utcnow(),
    )
    defaults.update(kwargs)
    return User(**defaults)


def test_grace_active_for_new_osgb_admin():
    assert mfa_setup_grace_active(_user()) is True


def test_grace_inactive_when_mfa_already_on():
    assert mfa_setup_grace_active(_user(mfa_enabled=True)) is False


def test_grace_inactive_for_workplace_kiosk_admin():
    assert mfa_setup_grace_active(_user(company_id=1)) is False


def test_grace_inactive_after_7_days():
    old = datetime.utcnow() - timedelta(days=8)
    assert mfa_setup_grace_active(_user(created_at=old)) is False


def test_grace_inactive_for_global_admin():
    assert mfa_setup_grace_active(_user(role=UserRole.GLOBAL_ADMIN)) is False
