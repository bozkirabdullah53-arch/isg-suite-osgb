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


def test_readiness_missing(monkeypatch):
    monkeypatch.setattr(settings, "health_field_encryption_enabled", False)
    monkeypatch.setattr(settings, "health_field_encryption_key", None)
    monkeypatch.setattr(settings, "secret_key", "")
    assert crypto.encryption_key_status() == "missing"
    assert crypto.health_crypto_ready_label() == "not_ready"
    ready = crypto.encryption_readiness()
    assert ready["enabled"] is False
    assert ready["can_enable"] is False
    assert ready["probe_ok"] is False


def test_readiness_weak_fallback(monkeypatch):
    monkeypatch.setattr(settings, "health_field_encryption_enabled", False)
    monkeypatch.setattr(settings, "health_field_encryption_key", None)
    monkeypatch.setattr(settings, "secret_key", "change-me-in-production-at-least-32-characters!")
    assert crypto.encryption_key_status() == "weak_fallback"
    assert crypto.health_crypto_ready_label() == "not_ready"


def test_readiness_secret_key_fallback(monkeypatch):
    monkeypatch.setattr(settings, "health_field_encryption_enabled", False)
    monkeypatch.setattr(settings, "health_field_encryption_key", None)
    monkeypatch.setattr(settings, "secret_key", "test-secret-key-at-least-32-chars-long!!")
    assert crypto.encryption_key_status() == "secret_key_fallback"
    assert crypto.health_crypto_ready_label() == "ok"
    assert crypto.encryption_readiness()["can_enable"] is False


def test_readiness_dedicated(monkeypatch):
    monkeypatch.setattr(settings, "health_field_encryption_enabled", False)
    monkeypatch.setattr(settings, "health_field_encryption_key", "dedicated-health-key-32chars-min!!")
    monkeypatch.setattr(settings, "secret_key", "change-me-in-production-at-least-32-characters!")
    assert crypto.encryption_key_status() == "dedicated"
    assert crypto.health_crypto_ready_label() == "ok"
    assert crypto.encryption_readiness()["can_enable"] is True


def test_enable_health_crypto_production(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "health_field_encryption_force_off", False)
    monkeypatch.setattr(settings, "health_field_encryption_enabled", False)
    monkeypatch.setattr(settings, "health_field_encryption_key", None)
    monkeypatch.setattr(settings, "secret_key", "test-secret-key-at-least-32-chars-long!!")
    assert crypto.enable_health_crypto_for_production().startswith("enabled:")
    assert settings.health_field_encryption_enabled is True


def test_backfill_plaintext_records(monkeypatch):
    monkeypatch.setattr(settings, "health_field_encryption_enabled", True)
    monkeypatch.setattr(settings, "secret_key", "test-secret-key-at-least-32-chars-long!!")
    monkeypatch.setattr(settings, "health_field_encryption_key", None)

    class _Row:
        summary = "duz ozet"
        confidential_note = None
        audiometry_result = None
        spirometry_result = None
        chest_xray_result = None
        follow_up_note = None
        other_biological_test = None
        exposures = None
        suggested_tests = None

    class _DB:
        def __init__(self):
            self.row = _Row()
            self.committed = False
            self.rolled = False

        def scalars(self, _q):
            return self

        def all(self):
            return [self.row]

        def commit(self):
            self.committed = True

        def rollback(self):
            self.rolled = True

    db = _DB()
    out = crypto.backfill_plaintext_records(db, commit=False)
    assert out["status"] == "ok"
    assert out["fields_touched"] == 1
    assert db.row.summary.startswith(crypto.PREFIX)
    assert db.rolled is True
    assert db.committed is False


def test_decrypt_falls_back_to_secret_after_dedicated_cutover(monkeypatch):
    """Dedicated key ile yazmadan önce SECRET_KEY ile şifrelenen veri okunabilmeli."""
    monkeypatch.setattr(settings, "health_field_encryption_enabled", True)
    monkeypatch.setattr(settings, "secret_key", "old-secret-key-at-least-32-characters!!")
    monkeypatch.setattr(settings, "health_field_encryption_key", None)
    legacy = crypto.encrypt_field("eski not")
    monkeypatch.setattr(settings, "health_field_encryption_key", "new-dedicated-health-key-32chars-min!")
    assert crypto.decrypt_field(legacy) == "eski not"
    fresh = crypto.encrypt_field("yeni not")
    assert crypto.decrypt_field(fresh) == "yeni not"
