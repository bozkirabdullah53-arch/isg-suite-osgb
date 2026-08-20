from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from app.api.annual_plans import _validate_plan_date_pair


def test_partial_annual_plan_update_rejects_completion_before_existing_target():
    target_date = date.today()
    with pytest.raises(HTTPException) as error:
        _validate_plan_date_pair(
            target_date=target_date,
            completion_date=target_date - timedelta(days=1),
        )

    assert error.value.status_code == 422
    assert "Tamamlanma tarihi" in str(error.value.detail)


def test_partial_annual_plan_update_rejects_future_completion_date():
    with pytest.raises(HTTPException) as error:
        _validate_plan_date_pair(
            target_date=date.today(),
            completion_date=date.today() + timedelta(days=1),
        )

    assert error.value.status_code == 422
    assert "Tamamlanma tarihi" in str(error.value.detail)


def test_annual_plan_update_allows_clearing_target_date():
    assert _validate_plan_date_pair(
        target_date=None,
        completion_date=date.today(),
    ) == (None, date.today())


def test_annual_plan_update_accepts_completion_on_target_date():
    target_date = date.today() - timedelta(days=1)
    assert _validate_plan_date_pair(
        target_date=target_date,
        completion_date=target_date,
    ) == (target_date, target_date)
