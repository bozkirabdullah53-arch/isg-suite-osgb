"""Health field encryption — flag off leaves plaintext; enc:v1 decrypts on read."""
from app.core.config import settings
from app.services import health_field_crypto as crypto


def test_roundtrip_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "health_field_encryption_enabled", True)
    monkeypatch.setattr(settings, "secret_key", "test-secret-key-at-least-32-chars-long!!")
    monkeypatch.setattr(settings, "health_field_encryption_key", None)
    enc = crypto.encrypt_field("gizli not")
    assert enc.startswith(crypto.PREFIX)
    assert crypto.decrypt_field(enc) == "gizli not"


def test_flag_off_keeps_plaintext(monkeypatch):
    monkeypatch.setattr(settings, "health_field_encryption_enabled", False)
    assert crypto.encrypt_field("acik metin") == "acik metin"
    assert crypto.decrypt_field("acik metin") == "acik metin"


def test_encrypt_payload_selective(monkeypatch):
    monkeypatch.setattr(settings, "health_field_encryption_enabled", True)
    monkeypatch.setattr(settings, "secret_key", "test-secret-key-at-least-32-chars-long!!")
    out = crypto.encrypt_payload({"summary": "hasta özeti", "blood_lead_value": 12.5})
    assert out["summary"].startswith(crypto.PREFIX)
    assert out["blood_lead_value"] == 12.5


def test_decrypted_record_view(monkeypatch):
    monkeypatch.setattr(settings, "health_field_encryption_enabled", True)
    monkeypatch.setattr(settings, "secret_key", "test-secret-key-at-least-32-chars-long!!")

    class R:
        confidential_note = crypto.encrypt_field("hekim notu")
        summary = "duz"
        blood_lead_value = 1.0

    view = crypto.DecryptedRecordView(R())
    assert view.confidential_note == "hekim notu"
    assert view.summary == "duz"
    assert view.blood_lead_value == 1.0
