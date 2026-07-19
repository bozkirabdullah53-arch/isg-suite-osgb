"""OSGB oversight unit smoke — checklist scoring helpers."""
from app.services.osgb_oversight import SPECIALIST_CHECKS, PHYSICIAN_CHECKS, _status_from_ratio


def test_check_catalogs_cover_6331_core():
    spec_codes = {c["code"] for c in SPECIALIST_CHECKS}
    assert "saha_sure" in spec_codes
    assert "risk_degerlendirme" in spec_codes
    assert "yillik_plan" in spec_codes
    assert "egitim" in spec_codes
    hek_codes = {c["code"] for c in PHYSICIAN_CHECKS}
    assert "saglik_gozetim" in hek_codes
    assert "muayene_gecikme" in hek_codes


def test_status_from_ratio_bands():
    assert _status_from_ratio(10, 10) == "ok"
    assert _status_from_ratio(6, 10) == "warning"
    assert _status_from_ratio(2, 10) == "critical"
    assert _status_from_ratio(0, 0) == "unknown"
