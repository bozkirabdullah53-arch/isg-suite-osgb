"""Fine–Kinney scoring contract and 5x5 compatibility checks."""

import pytest

from app.services.risk_scoring import (
    evaluate,
    evaluate_fine_kinney,
    evaluate_method,
    fine_kinney_meta_payload,
)


def test_fine_kinney_uses_probability_frequency_severity_product():
    result = evaluate_fine_kinney(3, 6, 15)

    assert result["risk_score"] == 270
    assert result["risk_level"] == "Yüksek"
    assert result["risk_level_label"] == "Yüksek Risk"
    assert result["frequency"] == 6


@pytest.mark.parametrize(
    ("probability", "frequency", "severity", "level"),
    [
        (0.1, 1, 100, "Kabul Edilebilir"),
        (0.1, 2, 100, "Düşük"),
        (1, 2, 40, "Orta"),
        (1, 6, 40, "Yüksek"),
        (1, 10, 40, "Çok Yüksek"),
    ],
)
def test_fine_kinney_thresholds(probability, frequency, severity, level):
    assert evaluate_fine_kinney(probability, frequency, severity)["risk_level"] == level


def test_method_dispatch_keeps_5x5_engine_compatible():
    assert evaluate(3, 4)["risk_score"] == 12
    assert evaluate_method("5x5_l", 3, 4)["risk_score"] == 12


def test_unsupported_method_never_falls_back_to_5x5():
    with pytest.raises(ValueError):
        evaluate_method("hazop", 3, 4)


def test_fine_kinney_metadata_exposes_all_three_axes():
    metadata = fine_kinney_meta_payload()

    assert metadata["method_code"] == "fine_kinney"
    assert len(metadata["probability_defs"]) == 7
    assert len(metadata["frequency_defs"]) == 6
    assert len(metadata["severity_defs"]) == 6
    assert metadata["planning_note"]
