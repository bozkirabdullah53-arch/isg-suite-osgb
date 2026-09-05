from datetime import date, datetime

import pytest
from pydantic import ValidationError

from app.models.entities import AssignmentStatus, ProfessionalType
from app.schemas.osgb import AssignmentCreate, AssignmentResponse


def _assignment_values(**overrides):
    values = {
        "id": 189,
        "osgb_id": 1,
        "company_id": 10,
        "professional_id": 20,
        "professional_type": ProfessionalType.SAFETY_SPECIALIST,
        "start_date": date(2026, 9, 5),
        "end_date": date(2026, 8, 1),
        "required_minutes_monthly": -60,
        "planned_minutes_monthly": -120,
        "actual_minutes_monthly": -30,
        "isg_katip_contract_number": "legacy-contract",
        "status": AssignmentStatus.ACTIVE,
        "created_at": datetime(2026, 1, 1),
    }
    values.update(overrides)
    return values


def test_assignment_response_accepts_legacy_invalid_period_and_minutes():
    response = AssignmentResponse.model_validate(_assignment_values())

    assert response.start_date == date(2026, 9, 5)
    assert response.end_date == date(2026, 8, 1)
    assert response.required_minutes_monthly == -60
    assert response.planned_minutes_monthly == -120
    assert response.actual_minutes_monthly == -30


def test_assignment_create_keeps_write_time_period_and_negative_minute_validation():
    with pytest.raises(ValidationError):
        AssignmentCreate(
            osgb_id=1,
            company_id=10,
            professional_id=20,
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            start_date=date(2026, 9, 5),
            end_date=date(2026, 8, 1),
        )

    with pytest.raises(ValidationError):
        AssignmentCreate(
            osgb_id=1,
            company_id=10,
            professional_id=20,
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            start_date=date(2026, 9, 5),
            required_minutes_monthly=-1,
        )
