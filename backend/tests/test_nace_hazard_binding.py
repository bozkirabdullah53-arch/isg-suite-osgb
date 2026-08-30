from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.companies import _apply_nace_classification
from app.services.training_nace_classification import resolve_exact_nace
from app.services.training_topics import sectors_list_for_api


def test_all_catalog_rows_keep_the_official_count_and_legacy_aliases_are_additive():
    official = sectors_list_for_api()
    public = sectors_list_for_api(include_legacy_nace_aliases=True)

    assert len(official) == 2142
    assert len(public) == len(official) + 5
    assert {row["nace"] for row in public if row.get("is_legacy_alias")} == {
        "41.20.01",
        "41.20.02",
        "41.20.03",
        "41.20.04",
        "41.20.05",
    }


def test_legacy_nace_resolves_to_its_exact_activity_and_hazard_class():
    result = resolve_exact_nace("41.20.02")

    assert result.nace_code == "41.20.02"
    assert "İkamet amaçlı binaların inşaatı" in result.nace_description
    assert result.hazard_class == "Çok Tehlikeli"
    assert len(result.training_topics) == 5


def test_company_hazard_class_is_derived_for_any_exact_nace_code():
    data = {"nace_code": "46.83.06", "hazard_class": "Az Tehlikeli"}

    _apply_nace_classification(data)

    assert data["nace_code"] == "46.83.06"
    assert data["hazard_class"] == resolve_exact_nace("46.83.06").hazard_class


def test_company_rejects_an_unknown_nonempty_nace_code():
    with pytest.raises(HTTPException) as error:
        _apply_nace_classification({"nace_code": "99.99.99", "hazard_class": "Az Tehlikeli"})

    assert error.value.status_code == 422
