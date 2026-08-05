from __future__ import annotations

import pytest

from app.services.ibys_application_profile import (
    APPLICATION_PROFILE_VERSION,
    CONTRACT_STATUS,
    application_profile_readiness,
    build_application_mapping_matrix,
    build_submission_envelope,
    canonical_record_hash,
    dataset_codes,
    validate_candidate_records,
)


def _workplace_record() -> dict:
    return {
        "source_id": 11,
        "name": "Başvuru Demo İşyerı",
        "sgk_registry_no": "12345678901234567890123",
        "nace_code": "27.20.01",
        "hazard_class": "Çok Tehlikeli",
        "active": True,
    }


def test_application_profile_is_explicitly_non_official_and_complete_candidate_matrix():
    matrix = build_application_mapping_matrix()

    assert matrix["profile_version"] == APPLICATION_PROFILE_VERSION
    assert matrix["contract_status"] == CONTRACT_STATUS
    assert matrix["official_compliance_claim"] is False
    assert len(matrix["datasets"]) == 12
    assert len(set(dataset_codes())) == 12
    assert all(dataset["official_dataset_code"] is None for dataset in matrix["datasets"])
    assert all(dataset["required_demo_fields"] for dataset in matrix["datasets"])


def test_candidate_validation_reports_only_fingerprint_and_missing_fields():
    secret_value = "12345678901"
    records = [
        _workplace_record(),
        {"source_id": 12, "name": "Eksik İşyerı", "sgk_registry_no": secret_value},
    ]

    result = validate_candidate_records("workplace", records)

    assert result["accepted_count"] == 1
    assert result["rejected_count"] == 1
    assert result["valid"] is False
    assert result["rejected"][0]["missing_fields"] == ["nace_code", "hazard_class", "active"]
    assert secret_value not in str(result)


def test_record_hash_is_deterministic_and_ignores_volatile_timestamps():
    first = {**_workplace_record(), "updated_at": "2026-08-01T00:00:00Z"}
    second = {**_workplace_record(), "updated_at": "2026-08-05T00:00:00Z"}

    assert canonical_record_hash("workplace", first) == canonical_record_hash("workplace", second)


def test_submission_envelope_has_stable_idempotency_key():
    records = [_workplace_record()]

    first = build_submission_envelope(
        "workplace", records, osgb_id=7, source_system_version="1.0.0"
    )
    second = build_submission_envelope(
        "workplace", records, osgb_id=7, source_system_version="1.0.0"
    )

    assert first["idempotency_key"] == second["idempotency_key"]
    assert first["record_count"] == 1
    assert first["validation"]["valid"] is True
    assert first["official_compliance_claim"] is False


def test_unknown_dataset_is_rejected_before_envelope_generation():
    with pytest.raises(ValueError, match="unknown dataset"):
        validate_candidate_records("not-a-dataset", [])


def test_readiness_separates_technical_application_profile_from_official_contract():
    readiness = application_profile_readiness()

    assert readiness["technical_application_profile_ready"] is True
    assert readiness["candidate_mapping_complete_pct"] == 100
    assert readiness["official_contract_received"] is False
    assert readiness["official_mapping_complete_pct"] == 0
    assert readiness["official_compliance_claim"] is False
    assert readiness["dataset_count"] == 12


def test_router_is_registered_in_application():
    from app.main import app

    paths = {route.path for route in app.routes}
    assert "/api/v1/ibys-application/profile" in paths
    assert "/api/v1/ibys-application/readiness" in paths
    assert "/api/v1/ibys-application/validate/{dataset_code}" in paths
    assert "/api/v1/ibys-application/envelope/{dataset_code}" in paths
