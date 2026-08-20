from datetime import date

import pytest
from pydantic import ValidationError

from app.models.entities import ProfessionalType
from app.schemas.osgb import AssignmentCreate


def _payload(**overrides):
    data = {
        "osgb_id": 1,
        "company_id": 2,
        "professional_id": 3,
        "professional_type": ProfessionalType.SAFETY_SPECIALIST,
        "start_date": date(2026, 8, 20),
        "end_date": None,
        "required_minutes_monthly": 0,
        "planned_minutes_monthly": 0,
        "actual_minutes_monthly": 0,
        "isg_katip_contract_number": "KATIP-TEST-001",
    }
    data.update(overrides)
    return data


def test_assignment_rejects_end_date_before_start_date() -> None:
    with pytest.raises(ValidationError, match="bitiş tarihi"):
        AssignmentCreate(
            **_payload(
                start_date=date(2026, 8, 20),
                end_date=date(2026, 8, 19),
            )
        )


def test_assignment_accepts_same_day_end_date_and_zero_minutes() -> None:
    assignment = AssignmentCreate(
        **_payload(
            end_date=date(2026, 8, 20),
            required_minutes_monthly=0,
            planned_minutes_monthly=0,
            actual_minutes_monthly=0,
        )
    )
    assert assignment.end_date == assignment.start_date
    assert assignment.required_minutes_monthly == 0


@pytest.mark.parametrize(
    "field_name",
    [
        "required_minutes_monthly",
        "planned_minutes_monthly",
        "actual_minutes_monthly",
    ],
)
def test_assignment_rejects_negative_capacity_minutes(field_name: str) -> None:
    with pytest.raises(ValidationError):
        AssignmentCreate(**_payload(**{field_name: -1}))
