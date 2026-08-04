from __future__ import annotations

from types import SimpleNamespace

from app.core.config import settings
from app.services.health_crypto_inventory import build_health_crypto_inventory
from app.services.health_field_crypto import PREFIX, SENSITIVE_TEXT_FIELDS, _fernet_from


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _FakeDb:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self, _statement):
        return _Rows(self._rows)


def _row(**values):
    data = {field: None for field in SENSITIVE_TEXT_FIELDS}
    data.update(values)
    return SimpleNamespace(**data)


def test_health_crypto_inventory_is_counts_only(monkeypatch):
    dedicated = "dedicated-health-key-at-least-32-characters"
    monkeypatch.setattr(settings, "health_field_encryption_key", dedicated)
    monkeypatch.setattr(
        settings,
        "secret_key",
        "ci-secret-key-at-least-32-characters-long",
    )
    monkeypatch.setattr(settings, "health_field_encryption_enabled", False)

    encrypted = PREFIX + _fernet_from(dedicated).encrypt(b"clinical secret").decode("ascii")
    rows = [
        _row(summary="plaintext clinical note", restrictions=encrypted),
        _row(follow_up_note=PREFIX + "invalid-token"),
    ]

    result = build_health_crypto_inventory(_FakeDb(rows))

    assert result["privacy"] == "counts-only"
    assert result["record_count"] == 2
    assert result["present_fields"] == 3
    assert result["totals"]["plaintext"] == 1
    assert result["totals"]["encrypted_readable"] == 1
    assert result["totals"]["encrypted_unreadable"] == 1
    assert result["rows_with_plaintext"] == 1
    assert result["rows_with_unreadable_ciphertext"] == 1
    assert result["safe_for_key_rotation"] is False

    rendered = repr(result)
    assert "plaintext clinical note" not in rendered
    assert "clinical secret" not in rendered
    assert encrypted not in rendered
    assert dedicated not in rendered


def test_health_crypto_inventory_rotation_ready(monkeypatch):
    dedicated = "another-dedicated-health-key-at-least-32-chars"
    monkeypatch.setattr(settings, "health_field_encryption_key", dedicated)
    monkeypatch.setattr(settings, "secret_key", "")
    monkeypatch.setattr(settings, "health_field_encryption_enabled", True)

    encrypted = PREFIX + _fernet_from(dedicated).encrypt(b"safe").decode("ascii")
    result = build_health_crypto_inventory(_FakeDb([_row(summary=encrypted)]))

    assert result["totals"]["plaintext"] == 0
    assert result["totals"]["encrypted_unreadable"] == 0
    assert result["readiness"]["key_status"] == "dedicated"
    assert result["safe_for_key_rotation"] is True
