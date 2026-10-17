"""Hata izleme (Sentry) entegrasyonu: DSN yokken etkisiz, varken kişisel veri göndermez."""
import pytest

import app.core.monitoring as monitoring
from app.core.config import settings


def test_monitoring_is_noop_without_dsn(monkeypatch):
    monkeypatch.setattr(settings, "sentry_dsn", "")
    assert monitoring.init_error_monitoring() is False


def test_monitoring_initializes_with_personal_data_disabled(monkeypatch):
    sentry_sdk = pytest.importorskip("sentry_sdk")
    calls = {}
    monkeypatch.setattr(settings, "sentry_dsn", "https://public@example.ingest.sentry.io/1")
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: calls.update(kwargs))

    assert monitoring.init_error_monitoring() is True
    assert calls["send_default_pii"] is False
    assert calls["traces_sample_rate"] == 0.0
    assert calls["before_send"] is monitoring._scrub_event


def test_scrub_removes_request_and_user_data_but_keeps_message():
    event = {
        "message": "işlem hatası",
        "request": {"data": "gizli-gövde", "headers": {"cookie": "oturum"}},
        "user": {"email": "kisi@example.com"},
    }
    cleaned = monitoring._scrub_event(event)
    assert cleaned == {"message": "işlem hatası"}
