from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from app.api.incidents import _validate_incident_date_state


def test_partial_incident_update_rejects_sgk_date_before_existing_event_date():
    with pytest.raises(HTTPException) as error:
        _validate_incident_date_state(
            event_date=date.today(),
            sgk_report_date=date.today() - timedelta(days=1),
            sgk_reported=True,
        )

    assert error.value.status_code == 422
    assert "SGK bildirim tarihi" in str(error.value.detail)


def test_partial_incident_update_requires_sgk_date_when_marked_reported():
    with pytest.raises(HTTPException) as error:
        _validate_incident_date_state(
            event_date=date.today(),
            sgk_report_date=None,
            sgk_reported=True,
        )

    assert error.value.status_code == 422
    assert "bildirim tarihi" in str(error.value.detail)


def test_incident_update_date_state_accepts_same_day_sgk_report():
    event_date = date.today() - timedelta(days=1)
    assert _validate_incident_date_state(
        event_date=event_date,
        sgk_report_date=event_date,
        sgk_reported=True,
    ) == (event_date, event_date)


def test_incident_update_date_state_rejects_future_event_date():
    with pytest.raises(HTTPException) as error:
        _validate_incident_date_state(
            event_date=date.today() + timedelta(days=1),
            sgk_report_date=None,
            sgk_reported=False,
        )

    assert error.value.status_code == 422
    assert "Olay tarihi" in str(error.value.detail)
