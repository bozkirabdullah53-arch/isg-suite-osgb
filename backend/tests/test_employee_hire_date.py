"""Personel hire_date → start_date alias (FAZ 0.4)."""
from datetime import date

from app.schemas.employee import EmployeeCreate, EmployeeUpdate


def test_hire_date_maps_to_start_date():
    obj = EmployeeCreate(
        company_id=1,
        full_name="Ali Veli",
        hire_date="2024-03-01",
    )
    assert obj.start_date == date(2024, 3, 1)
    dumped = obj.model_dump()
    assert dumped["start_date"] == date(2024, 3, 1)
    assert "hire_date" not in dumped


def test_start_date_wins_over_hire_date():
    obj = EmployeeCreate(
        company_id=1,
        full_name="Ali Veli",
        start_date="2024-01-15",
        hire_date="2024-03-01",
    )
    assert obj.start_date == date(2024, 1, 15)


def test_update_hire_date_alias():
    obj = EmployeeUpdate(hire_date="2023-06-01")
    assert obj.start_date == date(2023, 6, 1)
