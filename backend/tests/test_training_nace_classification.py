from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.schemas.training import TrainingCreate
from app.services.training_nace_classification import (
    classify_legacy,
    resolve_exact_nace,
)
from app.services.training_topics import sektorel_konular


def _all_catalog_rows() -> list[dict]:
    from app.services.training_topics import sectors_list_for_api

    return list(sectors_list_for_api())


def _official_catalog_rows() -> list[dict]:
    return [
        row
        for row in _all_catalog_rows()
        if str(row.get("code") or "").startswith("nace_")
        and str(row.get("nace") or "").strip()
    ]


def _first_catalog_key(prefix: str) -> str:
    for row in _official_catalog_rows():
        if str(row.get("nace") or "").startswith(prefix):
            return str(row["code"])
    raise AssertionError(f"NACE prefix not found in catalog: {prefix}")


def _first_catalog_key_for_profile(profile: str) -> str:
    for row in _official_catalog_rows():
        key = str(row["code"])
        if resolve_exact_nace(key).content_profile_code == profile:
            return key
    raise AssertionError(f"Content profile not found in catalog: {profile}")


def test_every_official_catalog_row_has_identity_hazard_topics_and_auditable_status():
    rows = _official_catalog_rows()
    assert rows
    seen_keys: set[str] = set()
    seen_nace_codes: set[str] = set()
    for row in rows:
        result = resolve_exact_nace(str(row["code"]))
        assert result.catalog_key not in seen_keys
        assert result.nace_code not in seen_nace_codes
        seen_keys.add(str(result.catalog_key))
        seen_nace_codes.add(str(result.nace_code))
        assert result.nace_description
        assert result.hazard_class in {
            "Az Tehlikeli",
            "Tehlikeli",
            "Çok Tehlikeli",
        }
        assert len(result.training_topics) == 5
        assert result.classification_status in {"verified", "review_required"}


def test_non_nace_catalog_options_are_not_accepted_as_exact_nace():
    options = [
        row
        for row in _all_catalog_rows()
        if not str(row.get("code") or "").startswith("nace_")
    ]
    assert options
    for row in options:
        with pytest.raises(ValueError):
            resolve_exact_nace(str(row.get("code") or ""))


def test_exact_construction_nace_is_verified_and_keeps_identity():
    key = _first_catalog_key("41.")
    result = resolve_exact_nace(key)
    assert result.classification_status == "verified"
    assert result.catalog_key == key
    assert result.nace_code and result.nace_code.startswith("41.")
    assert result.nace_section_code == "F"
    assert result.hazard_class in {"Az Tehlikeli", "Tehlikeli", "Çok Tehlikeli"}
    assert len(result.training_topics) == 5
    assert set(result.technical_risk_tags) & {
        "working_at_height",
        "excavation",
        "lifting",
        "temporary_electricity",
    }


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


def test_unreviewed_profile_does_not_receive_main_sector_risk_fallback():
    key = _first_catalog_key("62.")
    result = resolve_exact_nace(key)
    assert result.classification_status == "review_required"
    assert result.technical_risk_tags == ()
    assert result.source_snapshot["risk_mapping"]["review_reasons"] == [
        "technical_risk_tags_missing"
    ]


@pytest.mark.parametrize(
    ("profile", "required_terms", "forbidden_terms"),
    [
        (
            "avukatlik_hukuk_burosu",
            ("ekranlı araçlarla çalışma", "ergonomi", "arşiv"),
            ("kanalizasyon", "klor", "atıksu"),
        ),
        (
            "guzellik_kuafor_spa",
            ("kozmetik kimyasallar", "sterilizasyon", "cilt koruma"),
            ("lpg", "kızgın yağ", "mutfak"),
        ),
        (
            "bilisim_yazilim_it",
            ("ekranlı araçlarla çalışma", "sistem odası", "kablo düzeni"),
            ("forklift", "kaynak dumanı", "iskele"),
        ),
    ],
)
def test_corrected_canonical_topics_override_unrelated_catalog_topics(
    profile: str,
    required_terms: tuple[str, ...],
    forbidden_terms: tuple[str, ...],
):
    key = _first_catalog_key_for_profile(profile)
    result = resolve_exact_nace(key)
    canonical_topics = tuple(sektorel_konular(key))
    joined = " ".join(result.training_topics).casefold()

    assert result.training_topics == canonical_topics
    assert result.source_snapshot["topic_mapping"] == {
        "source": "canonical_training_topics_v1",
        "catalog_topics_overridden": True,
    }
    for term in required_terms:
        assert term.casefold() in joined
    for term in forbidden_terms:
        assert term.casefold() not in joined


def test_training_create_canonicalizes_exact_nace_and_hazard_class():
    key = _first_catalog_key("41.")
    classification = resolve_exact_nace(key)
    start = date.today()
    end = start + timedelta(days=2)
    payload = TrainingCreate(
        company_id=1,
        title="Temel İş Sağlığı ve Güvenliği Eğitimi",
        training_type="İlk Defa",
        delivery_method="Yüz yüze",
        start_date=start,
        end_date=end,
        hazard_class="Az Tehlikeli",
        sector=classification.nace_code,
        instructor_name="Test Eğitmen",
        participant_ids=[1],
    )
    assert payload.sector == classification.catalog_key
    assert payload.hazard_class == classification.hazard_class


def test_training_create_rejects_general_profile_code():
    start = date.today()
    with pytest.raises(ValueError):
        TrainingCreate(
            company_id=1,
            title="Temel İş Sağlığı ve Güvenliği Eğitimi",
            start_date=start,
            end_date=start + timedelta(days=2),
            hazard_class="Tehlikeli",
            sector="genel_uretim",
            instructor_name="Test Eğitmen",
            participant_ids=[1],
        )
