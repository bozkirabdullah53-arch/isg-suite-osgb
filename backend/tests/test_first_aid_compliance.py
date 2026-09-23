from datetime import date

from app.services.first_aid_compliance import build_first_aid_compliance, required_first_aiders


def test_required_first_aiders_boundary_values():
    assert required_first_aiders(1, "Çok Tehlikeli") == 1
    assert required_first_aiders(10, "Çok Tehlikeli") == 1
    assert required_first_aiders(11, "Çok Tehlikeli") == 2
    assert required_first_aiders(15, "Tehlikeli") == 1
    assert required_first_aiders(16, "Tehlikeli") == 2
    assert required_first_aiders(20, "Az Tehlikeli") == 1
    assert required_first_aiders(21, "Az Tehlikeli") == 2
    assert required_first_aiders(10, "Bilinmiyor") is None


def test_first_aid_status_helpers_keep_expiring_documents_currently_valid():
    from app.services.first_aid_compliance import _status

    assert _status(date.today(), date.today())[0] == "expiring_soon"
