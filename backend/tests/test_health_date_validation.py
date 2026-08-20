from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.health import _validate_health_date_pair
from app.schemas.health import HealthRecordUpdate


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
