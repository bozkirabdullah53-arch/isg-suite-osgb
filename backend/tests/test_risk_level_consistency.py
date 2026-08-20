"""Risk level display must remain derived from the selected method and score."""

import pytest

from app.services.risk_scoring import canonical_risk_level


@pytest.mark.parametrize(
    ("method_code", "score", "stored_level", "expected"),
    [
        ("5x5_l", 5, "Düşük", "Kabul Edilebilir"),
        ("5x5_l", 9, "Yüksek", "Orta"),
        ("5x5_l", 17, "Yüksek", "Çok Yüksek"),
        (None, 8, "Orta", "Düşük"),
    ],
)
def test_legacy_5x5_display_level_comes_from_score(
    method_code, score, stored_level, expected
):
    assert canonical_risk_level(method_code, score, stored_level) == expected


def test_non_5x5_display_level_keeps_method_specific_stored_value():
    assert canonical_risk_level("fine_kinney", 270, "Yüksek") == "Yüksek"
    assert canonical_risk_level("hazop", 15, "Yüksek") == "Yüksek"
