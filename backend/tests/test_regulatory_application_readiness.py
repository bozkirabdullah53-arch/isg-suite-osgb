from __future__ import annotations

import json

import pytest

from app.services.authority_integration_gate import (
    AuthorityGateError,
    assert_authority_send_allowed,
    public_authority_status,
)
from app.services.regulatory_identity_vault import (
    RegulatoryIdentityError,
    decrypt_identity,
    encrypt_identity,
    key_ready,
    lookup_hash,
    mask_identity,
    valid_tckn,
)
from app.services.regulatory_submission_envelope import build_submission_envelope


def _clear_authority_env(monkeypatch):
    prefixes = ("IBYS_OFFICIAL_", "ISBS_ERECETE_", "ISBS_KTS_")
    for name in list(__import__("os").environ):
        if name.startswith(prefixes):
            monkeypatch.delenv(name, raising=False)


def test_official_authority_send_is_fail_closed_by_default(monkeypatch):
    _clear_authority_env(monkeypatch)
    with pytest.raises(AuthorityGateError):
        assert_authority_send_allowed("ibys", "test")
    with pytest.raises(AuthorityGateError):
        assert_authority_send_allowed("isbs_erecete", "production")


def test_authority_snapshot_never_exposes_secret_values(monkeypatch):
    _clear_authority_env(monkeypatch)
    secret = "TEST-CODE-DO-NOT-LEAK"
    monkeypatch.setenv("IBYS_OFFICIAL_TEST_ENDPOINT", "https://authority.invalid/test")
    monkeypatch.setenv("IBYS_OFFICIAL_PROFILE_VERSION", "profile-v-test")
    monkeypatch.setenv("IBYS_OFFICIAL_TEST_CODE", secret)
    monkeypatch.setenv("IBYS_OFFICIAL_TEST_SEND_ENABLED", "true")
    snapshot = public_authority_status()
    encoded = json.dumps(snapshot, ensure_ascii=False)
    assert secret not in encoded
    assert "authority.invalid" not in encoded
    assert snapshot["ibys"]["test"]["ready"] is True
    assert snapshot["secrets_exposed"] is False


def test_production_gate_requires_registration_as_well(monkeypatch):
    _clear_authority_env(monkeypatch)
    monkeypatch.setenv("IBYS_OFFICIAL_PROD_ENDPOINT", "https://authority.invalid/prod")
    monkeypatch.setenv("IBYS_OFFICIAL_PROFILE_VERSION", "profile-v1")
    monkeypatch.setenv("IBYS_OFFICIAL_ACCESS_CODE", "secret")
    monkeypatch.setenv("IBYS_OFFICIAL_PROD_SEND_ENABLED", "true")
    with pytest.raises(AuthorityGateError):
        assert_authority_send_allowed("ibys", "production")
    monkeypatch.setenv("IBYS_OFFICIAL_REGISTRATION_NO", "REG-TEST")
    assert assert_authority_send_allowed("ibys", "production").ready is True


def test_submission_envelope_is_stable_for_same_business_payload():
    payload = {"b": 2, "a": 1, "nested": {"z": "x"}}
    first = build_submission_envelope(
        authority="ibys",
        schema_profile="official-test-profile",
        payload=payload,
        actor_user_id=9,
        osgb_id=3,
        company_id=5,
        request_id="req-one",
    )
    second = build_submission_envelope(
        authority="ibys",
        schema_profile="official-test-profile",
        payload={"nested": {"z": "x"}, "a": 1, "b": 2},
        actor_user_id=9,
        osgb_id=3,
        company_id=5,
        request_id="req-two",
    )
    assert first.payload_sha256 == second.payload_sha256
    assert first.idempotency_key == second.idempotency_key
    assert first.request_id != second.request_id
    assert "payload" not in first.public_audit()


def test_regulatory_identity_crypto_is_dedicated_and_masked(monkeypatch):
    monkeypatch.setenv("REGULATORY_IDENTITY_ENCRYPTION_KEY", "R" * 48)
    tckn = "10000000146"  # algorithmically valid synthetic test value
    assert valid_tckn(tckn) is True
    assert key_ready() is True
    cipher = encrypt_identity("tckn", tckn)
    assert tckn not in cipher
    assert cipher.startswith("rid:v1:")
    assert decrypt_identity(cipher) == tckn
    assert mask_identity(tckn) == "*******0146"
    digest = lookup_hash("tckn", tckn)
    assert len(digest) == 64
    assert tckn not in digest


def test_regulatory_identity_refuses_weak_or_missing_dedicated_key(monkeypatch):
    monkeypatch.delenv("REGULATORY_IDENTITY_ENCRYPTION_KEY", raising=False)
    assert key_ready() is False
    with pytest.raises(RegulatoryIdentityError):
        encrypt_identity("tckn", "10000000146")
