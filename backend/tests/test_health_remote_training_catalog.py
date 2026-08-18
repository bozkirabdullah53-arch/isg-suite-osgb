"""Regression coverage for the hospital and healthcare remote-training package."""
from __future__ import annotations


def test_health_remote_catalog_uses_reviewed_exam_and_health_scope():
    from app.models.remote_training import (
        REMOTE_CATALOG_PACKAGE_SECTOR_CODES,
        REMOTE_SECTOR_LABELS,
        catalog_package_sector_code,
    )
    from app.services.remote_training import automatic_exam_items_for_package

    assert REMOTE_CATALOG_PACKAGE_SECTOR_CODES["health-services-ohs"] == "health"
    assert catalog_package_sector_code("health-services-ohs") == "health"
    assert REMOTE_SECTOR_LABELS["health"] == "Hastaneler ve Sağlık Hizmetleri"

    items = automatic_exam_items_for_package("health-services-ohs")
    assert len(items) == 10
    assert len({item["question_code"] for item in items}) == 10
    assert all(
        item["question_text"]
        and len(item["options"]) == 4
        and item["correct_option"] in "ABCD"
        and item["answer_explanation"]
        for item in items
    )
    assert all(
        any(
            scope.get("value") in {"saglik", "saglik_hastane_klinik"}
            for scope in item.get("scopes", [])
            if scope.get("type") == "sector"
        )
        for item in items
    )
