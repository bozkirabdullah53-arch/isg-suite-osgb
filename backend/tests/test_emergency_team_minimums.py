"""Mevzuat kademeleri, eksik veri ve sabit eski hedeflerin regresyonları."""
import pytest

from app.services.emergency_team_logic import team_minimum_requirement


@pytest.mark.parametrize("hazard,staff,support,first_aid", [
    ("Az Tehlikeli", 9, 1, 1),
    ("Az Tehlikeli", 10, 1, 1),
    ("Az Tehlikeli", 20, 1, 1),
    ("Az Tehlikeli", 21, 1, 2),
    ("Az Tehlikeli", 50, 1, 3),
    ("Az Tehlikeli", 51, 2, 3),
    ("Az Tehlikeli", 100, 2, 5),
    ("Az Tehlikeli", 101, 3, 6),
    ("Tehlikeli", 9, 1, 1),
    ("Tehlikeli", 10, 1, 1),
    ("Tehlikeli", 15, 1, 1),
    ("Tehlikeli", 16, 1, 2),
    ("Tehlikeli", 40, 1, 3),
    ("Tehlikeli", 41, 2, 3),
    ("Tehlikeli", 80, 2, 6),
    ("Tehlikeli", 81, 3, 6),
    ("Çok Tehlikeli", 9, 1, 1),
    ("Çok Tehlikeli", 10, 1, 1),
    ("Çok Tehlikeli", 11, 1, 2),
    ("Çok Tehlikeli", 30, 1, 3),
    ("Çok Tehlikeli", 31, 2, 4),
    ("Çok Tehlikeli", 60, 2, 6),
    ("Çok Tehlikeli", 61, 3, 7),
    ("Çok Tehlikeli", 65, 3, 7),
    ("  ÇOK TEHLİKELİ  ", 31, 2, 4),
    ("Cok Tehlikeli", 31, 2, 4),
])
def test_employee_thresholds(hazard, staff, support, first_aid):
    for code in ("sondurme", "kurtarma", "koruma"):
        result = team_minimum_requirement(code, staff, hazard, configured_minimum=2)
        assert result["required_members"] == support
        assert result["minimum_source"] == "legal"
    assert team_minimum_requirement("ilk_yardim", staff, hazard, 2)["required_members"] == first_aid


@pytest.mark.parametrize("code", ["sondurme", "kurtarma", "koruma", "ilk_yardim"])
def test_no_workers_does_not_report_an_invented_minimum(code):
    result = team_minimum_requirement(code, 0, "Tehlikeli", 2)
    assert result["required_members"] is None
    assert result["minimum_source"] == "incomplete"


@pytest.mark.parametrize("hazard", [None, "", "Orta tehlikeli", "belirsiz"])
def test_unknown_hazard_is_not_guessed(hazard):
    assert team_minimum_requirement("sondurme", 10, hazard, 2)["required_members"] is None
    assert team_minimum_requirement("ilk_yardim", 9, hazard, 2)["required_members"] is None
    small = team_minimum_requirement("sondurme", 9, hazard, 2)
    assert small["required_members"] == 1
    assert small["minimum_basis"] == "İADY m.11/4"


@pytest.mark.parametrize("code", ["tahliye", "haberlesme"])
def test_optional_teams_do_not_inherit_a_legal_minimum_of_two(code):
    result = team_minimum_requirement(code, 100, "Çok Tehlikeli", 2)
    assert result["required_members"] is None
    assert result["minimum_source"] == "risk_assessment"


def test_custom_team_retains_its_workplace_target():
    result = team_minimum_requirement("kimyasal_mudahale", 100, "Çok Tehlikeli", 4)
    assert result["required_members"] == 4
    assert result["minimum_source"] == "workplace"
