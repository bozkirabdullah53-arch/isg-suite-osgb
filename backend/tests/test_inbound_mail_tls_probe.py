"""Provider check uses real loopback TLS without reading or sending messages."""
import json
import pytest

from app.services import inbound_mail
from inbound_mail_tls_server import mail_server, configure_inbound, track_connections
from scripts.check_inbound_mail_tls import check_inbound_mail_tls, main


@pytest.fixture(autouse=True)
def no_retry_delay(monkeypatch):
    monkeypatch.setattr(inbound_mail.time, "sleep", lambda _: None)


@pytest.mark.parametrize("protocol,implicit", [("imap", True), ("imap", False), ("pop3", True), ("pop3", False)])
def test_probe_authenticates_verified_tls_without_message_operations(tmp_path, monkeypatch, capsys, protocol, implicit):
    with mail_server(tmp_path, protocol=protocol, implicit=implicit) as server:
        configure_inbound(monkeypatch, inbound_mail.settings, server, protocol=protocol, implicit=implicit)
        monkeypatch.setenv("SSL_CERT_FILE", str(server.cert_path))
        assert main() == 0
        printed = capsys.readouterr().out
        result = json.loads(printed)
        assert result["ok"] is True
        assert result["authenticated"] is True
        assert result["certificate_verified"] is True
        assert result["tls_version"] in {"TLSv1.2", "TLSv1.3"}
        assert "tls-test@example.invalid" not in printed
        assert "synthetic-local-test-password" not in printed
        assert not any(command in {"SELECT", "FETCH", "RETR", "DELE", "UIDL", "LIST", "STAT"} for command, _ in server.commands)


@pytest.mark.parametrize("protocol", ["imap", "pop3"])
def test_probe_reports_untrusted_certificate_without_credentials(tmp_path, monkeypatch, protocol):
    with mail_server(tmp_path, protocol=protocol, implicit=True) as server:
        configure_inbound(monkeypatch, inbound_mail.settings, server, protocol=protocol, implicit=True)
        result = check_inbound_mail_tls()
        assert result["ok"] is False
        assert result["authenticated"] is False
        assert result["error_kind"] == "SSLCertVerificationError"
        assert not any(command in {"USER", "PASS", "LOGIN"} for command, _ in server.commands)


def test_probe_reports_missing_configuration_without_connecting(monkeypatch):
    monkeypatch.setattr(inbound_mail.settings, "inbound_mail_password", None)
    result = check_inbound_mail_tls()
    assert result["ok"] is False
    assert result["error_kind"] == "not_configured"


def test_probe_rejects_unknown_protocol_without_connecting(monkeypatch):
    monkeypatch.setattr(inbound_mail.settings, "inbound_mail_enabled", True)
    monkeypatch.setattr(inbound_mail.settings, "inbound_mail_username", "tls-test@example.invalid")
    monkeypatch.setattr(inbound_mail.settings, "inbound_mail_password", "synthetic-local-test-password")
    monkeypatch.setattr(inbound_mail.settings, "inbound_mail_protocol", "unknown")
    result = check_inbound_mail_tls()
    assert result["ok"] is False
    assert result["error_kind"] == "unsupported_protocol"


@pytest.mark.parametrize("protocol", ["imap", "pop3"])
def test_probe_closes_transport_when_provider_rejects_logout(tmp_path, monkeypatch, protocol):
    with mail_server(tmp_path, protocol=protocol, implicit=True, fail_close=True) as server:
        configure_inbound(monkeypatch, inbound_mail.settings, server, protocol=protocol, implicit=True)
        monkeypatch.setenv("SSL_CERT_FILE", str(server.cert_path))
        connections = track_connections(monkeypatch, inbound_mail, protocol=protocol, implicit=True)
        assert check_inbound_mail_tls()["ok"] is True
        assert all(sock.fileno() == -1 and stream.closed for sock, stream in connections)
