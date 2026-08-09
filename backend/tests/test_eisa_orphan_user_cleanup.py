from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.models.entities import UserRole
from app.services import user_retirement


class _FakeSession:
    def __init__(self):
        self.flushed = False

    def flush(self):
        self.flushed = True


def _orphan_user():
    return SimpleNamespace(
        id=136,
        email="hekimbir@gmail.com",
        full_name="Hekim bir",
        hashed_password="old-hash",
        role=UserRole.WORKPLACE_PHYSICIAN,
        is_active=False,
        company_id=None,
        osgb_id=None,
        failed_login_count=4,
        locked_until="locked",
        mfa_enabled=True,
        mfa_secret_encrypted="secret",
        mfa_recovery_hashes="hashes",
        token_version=3,
    )


def test_anonymize_orphan_user_removes_login_identity_but_keeps_numeric_subject(monkeypatch):
    db = _FakeSession()
    user = _orphan_user()
    monkeypatch.setattr(
        user_retirement,
        "orphan_account_state",
        lambda _db, _user: {"eligible": True, "scope_valid": False},
    )

    original = user_retirement.anonymize_orphan_user(db, user)

    assert original == "hekimbir@gmail.com"
    assert user.id == 136
    assert user.email.startswith("deleted-user-136-")
    assert user.email.endswith("@invalid.local")
    assert "hekimbir" not in user.email
    assert user.full_name == "Silinmiş Kullanıcı"
    assert user.hashed_password != "old-hash"
    assert user.is_active is False
    assert user.company_id is None
    assert user.osgb_id is None
    assert user.failed_login_count == 0
    assert user.locked_until is None
    assert user.mfa_enabled is False
    assert user.mfa_secret_encrypted is None
    assert user.mfa_recovery_hashes is None
    assert user.token_version == 4
    assert db.flushed is True


def test_anonymize_orphan_user_refuses_scoped_or_active_account(monkeypatch):
    db = _FakeSession()
    user = _orphan_user()
    monkeypatch.setattr(
        user_retirement,
        "orphan_account_state",
        lambda _db, _user: {"eligible": False, "scope_valid": True},
    )

    with pytest.raises(ValueError, match="uygun değil"):
        user_retirement.anonymize_orphan_user(db, user)

    assert user.email == "hekimbir@gmail.com"
    assert db.flushed is False
