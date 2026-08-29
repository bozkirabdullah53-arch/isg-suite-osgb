"""FAZ 0.5 — 422 alan adları Türkçe."""
from app.core.validation_tr import field_label, format_validation_errors


def test_risk_field_labels():
    assert field_label("hazard_id") == "Tehlike"
    assert field_label("activity") == "Faaliyet"
    assert field_label("risk_definition") == "Risk tanımı"
    assert field_label("hire_date") == "İşe giriş tarihi"


def test_missing_fields_join_turkish():
    detail = format_validation_errors(
        [
            {"type": "missing", "loc": ("body", "hazard_id"), "msg": "Field required"},
            {"type": "missing", "loc": ("body", "activity"), "msg": "Field required"},
            {"type": "missing", "loc": ("body", "risk_definition"), "msg": "Field required"},
        ]
    )
    assert "Tehlike: bu alan zorunludur" in detail
    assert "Faaliyet: bu alan zorunludur" in detail
    assert "Risk tanımı: bu alan zorunludur" in detail
