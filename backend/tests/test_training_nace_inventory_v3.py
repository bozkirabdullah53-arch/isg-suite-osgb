from __future__ import annotations

from scripts.inventory_training_nace_profiles_v3 import build_inventory


def test_inventory_v3_is_read_only_and_covers_entire_exact_nace_catalog():
    payload = build_inventory()

    assert payload["safety"] == {
        "read_only": True,
        "database_writes": False,
        "api_routes_changed": False,
        "runtime_registration": False,
        "generated_files": False,
    }
    assert payload["catalog_option_count"] == 2142
    assert payload["official_nace_count"] == 2141
    assert payload["non_nace_option_count"] == 1
    assert payload["resolved_official_count"] == payload["official_nace_count"]
    assert payload["verified_official_count"] == payload["official_nace_count"]
    assert payload["invalid_official_count"] == 0
    assert payload["structural_coverage_complete"] is True
    assert payload["verified_coverage_complete"] is True
    assert payload["topic_slot_count"] == payload["official_nace_count"] * 5


def test_inventory_v3_profile_and_risk_distributions_balance_to_catalog():
    payload = build_inventory()
    profiles = payload["profile_distribution"]
    risk_packs = payload["technical_risk_pack_distribution"]
    topic_signatures = payload["training_topic_signature_distribution"]

    assert payload["profile_count"] == len(profiles)
    assert sum(row["nace_count"] for row in profiles) == payload["official_nace_count"]
    assert all(row["nace_count"] > 0 for row in profiles)
    assert all(row["topic_slot_count"] == row["nace_count"] * 5 for row in profiles)
    assert all(row["training_topic_variant_count"] >= 1 for row in profiles)
    assert all(row["technical_risk_tags"] for row in profiles)

    assert payload["technical_risk_pack_count"] == len(risk_packs)
    assert risk_packs
    assert all(row["nace_count"] > 0 for row in risk_packs)
    assert all(row["profile_count"] == len(row["profiles"]) for row in risk_packs)

    assert payload["training_topic_signature_count"] == len(topic_signatures)
    assert topic_signatures
    assert sum(row["nace_count"] for row in topic_signatures) == payload["official_nace_count"]
    assert all(len(row["topics"]) == 5 for row in topic_signatures)
