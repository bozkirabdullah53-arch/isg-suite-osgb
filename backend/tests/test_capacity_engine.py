"""Aktif çalışan bazlı aylık İSG hizmet süresi kuralları."""
from __future__ import annotations

import pytest
from types import SimpleNamespace

from app.models.entities import Company, ProfessionalType
from app.services.capacity_engine import (
    build_service_requirement_summary,
    count_active_employees,
    compute_legal_required_minutes,
    employee_bracket,
    minutes_to_display,
    normalize_hazard,
    resolve_company_service_context,
)


def test_employee_bracket_is_kept_for_legacy_consumers():
    assert employee_bracket(0) == "1-9"
    assert employee_bracket(9) == "1-9"
    assert employee_bracket(10) == "10-49"
    assert employee_bracket(250) == "250+"


@pytest.mark.parametrize(
    ("hazard", "role", "expected"),
    [
        ("Az Tehlikeli", ProfessionalType.SAFETY_SPECIALIST, 10),
        ("Az Tehlikeli", ProfessionalType.WORKPLACE_PHYSICIAN, 5),
        ("Tehlikeli", ProfessionalType.SAFETY_SPECIALIST, 20),
        ("Tehlikeli", ProfessionalType.WORKPLACE_PHYSICIAN, 10),
        ("Çok Tehlikeli", ProfessionalType.SAFETY_SPECIALIST, 40),
        ("Çok Tehlikeli", ProfessionalType.WORKPLACE_PHYSICIAN, 15),
    ],
)
def test_one_employee_matrix(hazard, role, expected):
    assert compute_legal_required_minutes(hazard, 1, role) == expected


@pytest.mark.parametrize(
    ("hazard", "role", "expected"),
    [
        ("Az Tehlikeli", ProfessionalType.SAFETY_SPECIALIST, 100),
        ("Az Tehlikeli", ProfessionalType.WORKPLACE_PHYSICIAN, 50),
        ("Tehlikeli", ProfessionalType.SAFETY_SPECIALIST, 200),
        ("Tehlikeli", ProfessionalType.WORKPLACE_PHYSICIAN, 100),
        ("Çok Tehlikeli", ProfessionalType.SAFETY_SPECIALIST, 400),
        ("Çok Tehlikeli", ProfessionalType.WORKPLACE_PHYSICIAN, 150),
    ],
)
def test_ten_employee_matrix(hazard, role, expected):
    assert compute_legal_required_minutes(hazard, 10, role) == expected


@pytest.mark.parametrize(
    ("hazard", "role", "expected"),
    [
        ("Az Tehlikeli", ProfessionalType.SAFETY_SPECIALIST, 1000),
        ("Az Tehlikeli", ProfessionalType.WORKPLACE_PHYSICIAN, 500),
        ("Tehlikeli", ProfessionalType.SAFETY_SPECIALIST, 2000),
        ("Tehlikeli", ProfessionalType.WORKPLACE_PHYSICIAN, 1000),
        ("Çok Tehlikeli", ProfessionalType.SAFETY_SPECIALIST, 4000),
        ("Çok Tehlikeli", ProfessionalType.WORKPLACE_PHYSICIAN, 1500),
    ],
)
def test_one_hundred_employee_matrix(hazard, role, expected):
    assert compute_legal_required_minutes(hazard, 100, role) == expected


def test_sixty_hazardous_employees_examples():
    assert compute_legal_required_minutes("Tehlikeli", 60, ProfessionalType.SAFETY_SPECIALIST) == 1200
    assert compute_legal_required_minutes("Tehlikeli", 60, ProfessionalType.WORKPLACE_PHYSICIAN) == 600


def test_zero_and_negative_employee_counts_are_safe():
    assert compute_legal_required_minutes("Tehlikeli", 0, ProfessionalType.SAFETY_SPECIALIST) == 0
    assert compute_legal_required_minutes("Tehlikeli", -10, ProfessionalType.WORKPLACE_PHYSICIAN) == 0
    assert compute_legal_required_minutes("Tehlikeli", "not-a-number", ProfessionalType.WORKPLACE_PHYSICIAN) == 0


def test_duplicate_active_personnel_do_not_inflate_population():
    employees = [
        SimpleNamespace(id=1, full_name="Ayşe Yılmaz", national_id_masked=None, is_active=True),
        SimpleNamespace(id=2, full_name="  AYŞE   YILMAZ ", national_id_masked=None, is_active=True),
        SimpleNamespace(id=3, full_name="Mehmet Kaya", national_id_masked="masked-3", is_active=False),
    ]
    assert count_active_employees(employees) == 1


def test_unknown_hazard_never_guesses():
    assert normalize_hazard("bilinmiyor") is None
    assert compute_legal_required_minutes("bilinmiyor", 60, ProfessionalType.SAFETY_SPECIALIST) == 0
    summary = build_service_requirement_summary("bilinmiyor", 60)
    assert summary["hazard_known"] is False
    assert summary["hazard_warning"]
    assert summary["roles"]["safety_specialist"]["required_minutes"] == 0
    assert summary["roles"]["safety_specialist"]["equivalent"] == "Hesaplanamadı"


def test_minute_to_hour_conversion_uses_remainder_not_decimal_hours():
    assert minutes_to_display(4000) == {
        "total_minutes": 4000,
        "hours": 66,
        "remaining_minutes": 40,
        "equivalent": "66 saat 40 dakika / ay",
    }
    assert minutes_to_display(1235)["hours"] == 20
    assert minutes_to_display(1235)["remaining_minutes"] == 35
    assert ".35" not in minutes_to_display(1235)["equivalent"]


def test_sgk_identity_resolves_embedded_nace_code():
    company = Company(
        name="Alçat Çelik",
        sgk_registry_no="22410010110202140161220000",
        nace_code=None,
        hazard_class=None,
    )
    context = resolve_company_service_context(company)
    assert context["nace_code"] == "24.10.01"
    assert context["nace_source"] == "sgk_registry_nace"
    assert context["hazard_class"] in {"Az Tehlikeli", "Tehlikeli", "Çok Tehlikeli"}
