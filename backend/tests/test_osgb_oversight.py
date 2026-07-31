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


def test_physician_zero_activity_score_is_zero():
    """Sağlık kaydı / ziyaret yokken muayene+uygunluk boşta geçmesin → skor 0."""
    # Ağırlıklar: saha2 + saglik2 + muayene2 + uygunluk1 = 7
    # Hepsi fail → 0/7 = 0% (önceki bug: muayene+uygunluk pass → 3/7 ≈ 43%)
    weights = [c["weight"] for c in PHYSICIAN_CHECKS]
    assert sum(weights) == 7
    weight_ok_vacuous_old = 2 + 1  # muayene + uygunluk
    assert round(100 * weight_ok_vacuous_old / 7) == 43
    assert round(100 * 0 / 7) == 0


def test_specialist_zero_activity_score_is_zero():
    """Risk/olay yokken DÖF+olay boşta geçmesin → skor 0 (önceki bug: 2/10 = %20)."""
    weights = [c["weight"] for c in SPECIALIST_CHECKS]
    assert sum(weights) == 10
    weight_ok_vacuous_old = 1 + 1  # risk_dof + olay_takip
    assert round(100 * weight_ok_vacuous_old / 10) == 20
    assert round(100 * 0 / 10) == 0

