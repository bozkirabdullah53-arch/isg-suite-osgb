from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.health import _validate_health_date_pair, _validate_periodic_exam_ceiling
from app.models.entities import HealthRecordType
from app.schemas.health import HealthRecordUpdate
from app.services.health_meta import default_next_exam, is_special_policy_status


def test_health_update_rejects_future_examination_date():
    with pytest.raises(ValidationError, match="Muayene tarihi"):
        HealthRecordUpdate(examination_date=date.today() + timedelta(days=1))


def test_health_update_rejects_next_examination_before_exam_when_both_are_supplied():
    exam_date = date.today() - timedelta(days=1)
    with pytest.raises(ValidationError, match="Sonraki muayene"):
        HealthRecordUpdate(
            examination_date=exam_date,
            next_examination_date=exam_date - timedelta(days=1),
        )


def test_health_update_preserves_explicit_next_examination_clear():
    payload = HealthRecordUpdate(next_examination_date=None)

    assert "next_examination_date" in payload.model_fields_set
    assert payload.next_examination_date is None


def test_partial_health_update_rejects_next_examination_before_existing_exam():
    with pytest.raises(HTTPException) as error:
        _validate_health_date_pair(
            examination_date=date.today(),
            next_examination_date=date.today() - timedelta(days=1),
        )

    assert error.value.status_code == 422
    assert "Sonraki muayene" in str(error.value.detail)


def test_partial_health_update_rejects_future_examination_against_existing_next_date():
    with pytest.raises(HTTPException) as error:
        _validate_health_date_pair(
            examination_date=date.today() + timedelta(days=1),
            next_examination_date=date.today() + timedelta(days=30),
        )

    assert error.value.status_code == 422
    assert "Muayene tarihi" in str(error.value.detail)


def test_periodic_exam_ceiling_allows_shorter_physician_interval():
    from datetime import date

    _validate_periodic_exam_ceiling(
        record_type=HealthRecordType.PERIODIC_EXAM,
        examination_date=date(2026, 1, 10),
        next_examination_date=date(2028, 1, 10),
        hazard_class="Tehlikeli",
    )


def test_special_policy_period_is_six_calendar_months():
    assert is_special_policy_status("Çocuk çalışan") is True
    assert is_special_policy_status("Gebe") is True
    assert default_next_exam(date(2026, 8, 31), "Çok Tehlikeli", "Gebe") == date(2027, 2, 28)


def test_special_policy_ceiling_rejects_longer_interval():
    with pytest.raises(HTTPException) as error:
        _validate_periodic_exam_ceiling(
            record_type=HealthRecordType.PERIODIC_EXAM,
            examination_date=date(2026, 3, 10),
            next_examination_date=date(2026, 9, 11),
            hazard_class="Tehlikeli",
            special_status="Gebe",
        )
    assert error.value.status_code == 422
