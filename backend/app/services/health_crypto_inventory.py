"""Privacy-safe inventory for health-field encryption rollout.

The inventory returns counts only. It never includes health values, ciphertext,
keys, hashes of values, employee identifiers, or record identifiers.
"""
from __future__ import annotations

from typing import Any, Literal

from sqlalchemy import select

from app.models.entities import HealthRecord
from app.services.health_field_crypto import (
    PREFIX,
    SENSITIVE_TEXT_FIELDS,
    _decrypt_key_candidates,
    _fernet_from,
    encryption_readiness,
    is_encrypted,
)

CryptoValueState = Literal[
    "empty",
    "plaintext",
    "encrypted_readable",
    "encrypted_unreadable",
]


def classify_health_crypto_value(value: str | None) -> CryptoValueState:
    """Classify one value without returning or logging its content."""
    if value is None or value == "":
        return "empty"
    if not is_encrypted(value):
        return "plaintext"

    try:
        token = str(value)[len(PREFIX) :].encode("ascii")
    except Exception:
        return "encrypted_unreadable"

    for raw in _decrypt_key_candidates():
        try:
            _fernet_from(raw).decrypt(token)
            return "encrypted_readable"
        except Exception:
            continue
    return "encrypted_unreadable"


def build_health_crypto_inventory(db: Any) -> dict[str, Any]:
    """Count health-field crypto states for global-admin rollout planning."""
    rows = list(db.scalars(select(HealthRecord)).all())
    totals = {
        "empty": 0,
        "plaintext": 0,
        "encrypted_readable": 0,
        "encrypted_unreadable": 0,
    }
    fields: dict[str, dict[str, int]] = {}
    rows_with_plaintext = 0
    rows_with_unreadable = 0

    for field in SENSITIVE_TEXT_FIELDS:
        fields[field] = dict(totals)

    for row in rows:
        has_plaintext = False
        has_unreadable = False
        for field in SENSITIVE_TEXT_FIELDS:
            state = classify_health_crypto_value(getattr(row, field, None))
            totals[state] += 1
            fields[field][state] += 1
            has_plaintext = has_plaintext or state == "plaintext"
            has_unreadable = has_unreadable or state == "encrypted_unreadable"
        rows_with_plaintext += int(has_plaintext)
        rows_with_unreadable += int(has_unreadable)

    readiness = encryption_readiness()
    present_fields = (
        totals["plaintext"]
        + totals["encrypted_readable"]
        + totals["encrypted_unreadable"]
    )
    return {
        "inventory_version": "health-crypto-inventory-v1",
        "privacy": "counts-only",
        "record_count": len(rows),
        "sensitive_field_count": len(SENSITIVE_TEXT_FIELDS),
        "field_slots_scanned": len(rows) * len(SENSITIVE_TEXT_FIELDS),
        "present_fields": present_fields,
        "rows_with_plaintext": rows_with_plaintext,
        "rows_with_unreadable_ciphertext": rows_with_unreadable,
        "totals": totals,
        "fields": fields,
        "readiness": readiness,
        "safe_for_key_rotation": (
            totals["encrypted_unreadable"] == 0
            and totals["plaintext"] == 0
            and readiness.get("key_status") == "dedicated"
        ),
    }
