from unittest import mock

from app.services.clamav_scan import is_clamav_configured, scan_bytes


def test_not_configured(monkeypatch):
    monkeypatch.setattr("app.services.clamav_scan.settings.clamav_host", None)
    assert not is_clamav_configured()
    clean, detail = scan_bytes(b"any")
    assert clean is True
    assert detail == "skipped"


def test_instream_ok(monkeypatch):
    monkeypatch.setattr("app.services.clamav_scan.settings.clamav_host", "127.0.0.1")

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
    monkeypatch.setattr("app.services.clamav_scan.settings.clamav_host", "127.0.0.1")

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
    monkeypatch.setattr("app.services.clamav_scan.settings.clamav_host", "127.0.0.1")
    monkeypatch.setattr(
        "app.services.clamav_scan.socket.create_connection",
        mock.Mock(side_effect=OSError("connection refused")),
    )
    clean, detail = scan_bytes(b"data")
    assert clean is False
    assert "clamav_unreachable" in detail
