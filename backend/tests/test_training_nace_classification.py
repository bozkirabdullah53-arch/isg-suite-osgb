from __future__ import annotations

import pytest

from app.services.training_nace_classification import (
    classify_legacy,
    resolve_exact_nace,
)


def _first_catalog_key(prefix: str) -> str:
    from app.services.training_topics import sectors_list_for_api

    for row in sectors_list_for_api():
        if str(row.get("nace") or "").startswith(prefix):
            return str(row["code"])
    raise AssertionError(f"NACE prefix not found in catalog: {prefix}")


def test_exact_construction_nace_is_verified_and_keeps_identity():
    key = _first_catalog_key("41.")
    result = resolve_exact_nace(key)
    assert result.classification_status == "verified"
    assert result.catalog_key == key
    assert result.nace_code and result.nace_code.startswith("41.")
    assert result.nace_section_code == "F"
    assert result.hazard_class in {"Az Tehlikeli", "Tehlikeli", "Çok Tehlikeli"}
    assert len(result.training_topics) == 5
    assert "working_at_height" in result.technical_risk_tags


def test_numeric_exact_nace_resolves_to_same_catalog_row():
    key = _first_catalog_key("86.")
    first = resolve_exact_nace(key)
    second = resolve_exact_nace(first.nace_code)
    assert second.catalog_key == first.catalog_key
    assert second.catalog_hash == first.catalog_hash


def test_general_sector_or_unknown_value_never_becomes_verified_nace():
    with pytest.raises(ValueError):
        resolve_exact_nace("genel_uretim")
    with pytest.raises(ValueError):
        resolve_exact_nace("metal")
    with pytest.raises(ValueError):
        resolve_exact_nace("99.99.99")


def test_legacy_profile_does_not_invent_nace_identity():
    result = classify_legacy("genel_uretim", "Tehlikeli")
    assert result.classification_status == "legacy_unverified"
    assert result.nace_code is None
    assert result.nace_description is None
    assert result.technical_risk_tags == ()


def test_catalog_hash_is_deterministic():
    key = _first_catalog_key("10.")
    assert resolve_exact_nace(key).catalog_hash == resolve_exact_nace(key).catalog_hash


def test_duration_is_derived_from_resolved_hazard_class():
    key = _first_catalog_key("62.")
    result = resolve_exact_nace(key)
    expected = {"Az Tehlikeli": 8, "Tehlikeli": 12, "Çok Tehlikeli": 16}
    assert result.required_duration_hours == expected[result.hazard_class]
    assert result.required_duration_minutes == result.required_duration_hours * 45
