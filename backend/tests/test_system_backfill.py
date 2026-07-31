"""GA health crypto backfill endpoint."""
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def test_health_crypto_backfill_requires_auth():
    client = TestClient(app)
    r = client.post("/api/v1/system/health-crypto-backfill")
    assert r.status_code in (401, 403)


def test_health_crypto_backfill_write_needs_confirm(monkeypatch):
    monkeypatch.setattr(settings, "health_field_encryption_enabled", True)
    # Endpoint logic unit-check via import
    from app.api import system as system_api
    from fastapi import HTTPException

    class _User:
        email = "ga@test"
        role = type("R", (), {"value": "global_admin"})()

    class _DB:
        def scalars(self, *_a, **_k):
            return self

        def all(self):
            return []

        def commit(self):
            pass

        def rollback(self):
            pass

    try:
        system_api.health_crypto_backfill(dry_run=False, confirm=None, db=_DB(), user=_User())
        assert False, "expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 400
