from unittest import mock

import pytest

from app.core.config import settings, validate_runtime_settings
from app.services.clamav_scan import (
    clamav_readiness,
    clamav_status_label,
    is_clamav_configured,
    is_clamav_required,
    scan_bytes,
)


def test_not_configured_optional_rollout(monkeypatch):
    monkeypatch.setattr(settings, "clamav_host", None)
    monkeypatch.setattr(settings, "clamav_required", False)
    assert not is_clamav_configured()
    assert not is_clamav_required()
    assert clamav_status_label() == "disabled"
    clean, detail = scan_bytes(b"any")
    assert clean is True
    assert detail == "skipped"
    readiness = clamav_readiness()
    assert readiness["scan_policy"] == "optional-rollout"
    assert readiness["upload_allowed_without_antivirus"] is True
    assert readiness["ready"] is False


def test_required_without_host_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "clamav_host", None)
    monkeypatch.setattr(settings, "clamav_required", True)

    assert is_clamav_required()
    assert not is_clamav_configured()
    assert clamav_status_label() == "required-missing"
    clean, detail = scan_bytes(b"any")
    assert clean is False
    assert detail == "clamav_required_unconfigured"
    readiness = clamav_readiness()
    assert readiness["scan_policy"] == "enforced"
    assert readiness["upload_allowed_without_antivirus"] is False
    assert readiness["ready"] is False


def test_production_required_without_host_blocks_startup(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "secret_key", "strong-production-secret-key-at-least-32-chars")
    monkeypatch.setattr(settings, "clamav_required", True)
    monkeypatch.setattr(settings, "clamav_host", None)

    with pytest.raises(RuntimeError, match="CLAMAV_HOST"):
        validate_runtime_settings()


def test_non_production_required_without_host_does_not_block_startup(monkeypatch):
    monkeypatch.setattr(settings, "environment", "staging")
    monkeypatch.setattr(settings, "secret_key", "staging-secret-key-at-least-32-characters")
    monkeypatch.setattr(settings, "clamav_required", True)
    monkeypatch.setattr(settings, "clamav_host", None)

    validate_runtime_settings()


def test_configured_unprobed_readiness_does_not_open_network(monkeypatch):
    monkeypatch.setattr(settings, "clamav_host", "clamav.internal")
    monkeypatch.setattr(settings, "clamav_required", True)
    readiness = clamav_readiness(probe=False)
    assert readiness == {
        "required": True,
        "configured": True,
        "status": "configured-unprobed",
        "scan_policy": "enforced",
        "upload_allowed_without_antivirus": False,
        "ready": True,
    }


def test_status_reachable(monkeypatch):
    monkeypatch.setattr(settings, "clamav_host", "127.0.0.1")

    class FakeSock:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def settimeout(self, _):
            pass

        def sendall(self, _data):
            pass

        def recv(self, _n):
            return b"PONG\0"

    monkeypatch.setattr("app.services.clamav_scan.socket.create_connection", lambda *_a, **_k: FakeSock())
    assert clamav_status_label() == "reachable"
    assert clamav_readiness(probe=True)["ready"] is True


def test_status_unreachable(monkeypatch):
    monkeypatch.setattr(settings, "clamav_host", "127.0.0.1")
    monkeypatch.setattr(
        "app.services.clamav_scan.socket.create_connection",
        mock.Mock(side_effect=OSError("connection refused")),
    )
    assert clamav_status_label() == "unreachable"
    assert clamav_readiness(probe=True)["ready"] is False


def test_instream_ok(monkeypatch):
    monkeypatch.setattr(settings, "clamav_host", "127.0.0.1")

    class FakeSock:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def settimeout(self, _):
            pass

        def sendall(self, _data):
            pass

        def recv(self, _n):
            return b"stream: OK\n"

    monkeypatch.setattr("app.services.clamav_scan.socket.create_connection", lambda *_a, **_k: FakeSock())
    clean, detail = scan_bytes(b"%PDF-1.4")
    assert clean is True
    assert "OK" in detail


def test_instream_found(monkeypatch):
    monkeypatch.setattr(settings, "clamav_host", "127.0.0.1")

    class FakeSock:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def settimeout(self, _):
            pass

        def sendall(self, _data):
            pass

        def recv(self, _n):
            return b"stream: Eicar-Test-Signature FOUND\n"

    monkeypatch.setattr("app.services.clamav_scan.socket.create_connection", lambda *_a, **_k: FakeSock())
    clean, detail = scan_bytes(b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR")
    assert clean is False
    assert "FOUND" in detail


def test_unreachable(monkeypatch):
    monkeypatch.setattr(settings, "clamav_host", "127.0.0.1")
    monkeypatch.setattr(
        "app.services.clamav_scan.socket.create_connection",
        mock.Mock(side_effect=OSError("connection refused")),
    )
    clean, detail = scan_bytes(b"data")
    assert clean is False
    assert "clamav_unreachable" in detail
