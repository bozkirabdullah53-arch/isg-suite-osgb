"""5x5 L tipi risk eşiklerinin yöntem kataloğuyla uyumunu doğrula."""

import pytest

from app.services.risk_scoring import risk_level


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (4, "Kabul Edilebilir"),
        (5, "Kabul Edilebilir"),
        (6, "Düşük"),
        (8, "Düşük"),
        (9, "Orta"),
        (12, "Orta"),
        (13, "Yüksek"),
        (16, "Yüksek"),
        (17, "Çok Yüksek"),
        (25, "Çok Yüksek"),
    ],
)
def test_5x5_thresholds_match_method_catalog(score, expected):
    assert risk_level(score) == expected
