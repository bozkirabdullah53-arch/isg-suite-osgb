from app.schemas.auth import LoginRequest
from app.schemas.remote_training import RemoteEmployeeAccountProvision
from app.services.remote_training import (
    remote_employee_login_email,
    remote_employee_username,
    suggested_remote_employee_username,
)


def test_remote_employee_username_uses_ascii_initial_and_surname():
    assert remote_employee_username("Abdullah BOZKIR") == "A.bozkir"
    assert remote_employee_username("ABDÜLMETİN KESKİN") == "A.keskin"
    assert remote_employee_username("İpek ŞAHİN") == "I.sahin"
    assert remote_employee_username("Ayşe Nur Çelik") == "A.celik"


def test_remote_employee_username_preview_is_safe_for_incomplete_names():
    assert suggested_remote_employee_username("TekAd") is None
    assert suggested_remote_employee_username("  ") is None


def test_remote_employee_login_alias_is_not_the_employee_login_name():
    assert remote_employee_login_email("A.bozkir", 42) == "a-bozkir.42@remote.isgsuite.tr"


def test_remote_employee_provision_can_be_created_without_email():
    payload = RemoteEmployeeAccountProvision(company_id=1, employee_id=2)
    assert payload.company_id == 1
    assert payload.employee_id == 2


def test_login_request_accepts_username_in_legacy_email_field():
    payload = LoginRequest(email="A.bozkir", password="temporary-password")
    assert payload.email == "A.bozkir"
