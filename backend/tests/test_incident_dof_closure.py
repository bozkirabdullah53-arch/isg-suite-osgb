import pytest
from fastapi import HTTPException

from app.api.incidents import _validate_dof_completion
from app.schemas.incident import IncidentDofComplete


def test_dof_completion_requires_effectiveness_evidence():
    with pytest.raises(HTTPException) as error:
        _validate_dof_completion(
            IncidentDofComplete(close_approval="Abdullah Bozkır")
        )

    assert error.value.status_code == 422
    assert "kapanış kanıtı" in str(error.value.detail)


def test_dof_completion_requires_closing_person():
    with pytest.raises(HTTPException) as error:
        _validate_dof_completion(
            IncidentDofComplete(effectiveness_note="Faaliyet sonrası kontrol yapıldı.")
        )

    assert error.value.status_code == 422
    assert "kapatan kişi" in str(error.value.detail)


def test_dof_completion_rejects_placeholder_evidence():
    with pytest.raises(HTTPException) as error:
        _validate_dof_completion(
            IncidentDofComplete(
                effectiveness_note="test",
                close_approval="Abdullah Bozkır",
            )
        )

    assert error.value.status_code == 422


def test_dof_completion_returns_clean_evidence_and_approver():
    assert _validate_dof_completion(
        IncidentDofComplete(
            effectiveness_note="  Faaliyet sonrası kontrol yapıldı.  ",
            close_approval="Abdullah Bozkır",
        )
    ) == ("Faaliyet sonrası kontrol yapıldı.", "Abdullah Bozkır")
