from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from app.api.annual_eval import _validate_eval_actual_date_pair


def test_annual_eval_update_rejects_end_before_existing_start():
    start = date.today() - timedelta(days=2)

    with pytest.raises(HTTPException) as error:
        _validate_eval_actual_date_pair(
            actual_start=start,
            actual_end=start - timedelta(days=1),
        )

    assert error.value.status_code == 422
    assert "Fiili bitiş tarihi" in str(error.value.detail)


def test_annual_eval_update_rejects_future_actual_start():
    with pytest.raises(HTTPException) as error:
        _validate_eval_actual_date_pair(
            actual_start=date.today() + timedelta(days=1),
            actual_end=None,
        )

    assert error.value.status_code == 422
    assert "Fiili başlangıç tarihi" in str(error.value.detail)


def test_annual_eval_update_rejects_future_actual_end():
    with pytest.raises(HTTPException) as error:
        _validate_eval_actual_date_pair(
            actual_start=date.today(),
            actual_end=date.today() + timedelta(days=1),
        )

    assert error.value.status_code == 422
    assert "Fiili bitiş tarihi" in str(error.value.detail)


def test_annual_eval_update_allows_clearing_existing_actual_start():
    end = date.today()

    assert _validate_eval_actual_date_pair(
        actual_start=None,
        actual_end=end,
    ) == (None, end)


def test_annual_eval_update_accepts_same_day_actual_dates():
    today = date.today()

    assert _validate_eval_actual_date_pair(
        actual_start=today,
        actual_end=today,
    ) == (today, today)
