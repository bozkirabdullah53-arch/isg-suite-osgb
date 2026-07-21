"""Kapasite motoru — mevzuat dakika tablosu."""
from app.services.capacity_engine import (
    compute_legal_required_minutes,
    employee_bracket,
    normalize_hazard,
)
from app.models.entities import ProfessionalType


def test_employee_bracket():
    assert employee_bracket(0) == "1-9"
    assert employee_bracket(9) == "1-9"
    assert employee_bracket(10) == "10-49"
    assert employee_bracket(250) == "250+"


def test_legal_minutes_specialist():
    az_small = compute_legal_required_minutes("Az Tehlikeli", 5, ProfessionalType.SAFETY_SPECIALIST)
    cok_large = compute_legal_required_minutes("Çok Tehlikeli", 300, ProfessionalType.SAFETY_SPECIALIST)
    assert az_small == 120
    assert cok_large == 1920
    assert cok_large > az_small


def test_legal_minutes_physician():
    mins = compute_legal_required_minutes("Tehlikeli", 25, ProfessionalType.WORKPLACE_PHYSICIAN)
    assert mins == 240


def test_normalize_hazard():
    assert normalize_hazard("tehlikeli") == "Tehlikeli"
    assert normalize_hazard("cok tehlikeli") == "Çok Tehlikeli"
