"""Real protocol tests: no credentials before verified inbound TLS."""
import pytest

from app.services import inbound_mail
from inbound_mail_tls_server import mail_server, configure_inbound, close_mail_client, track_connections


def connect(protocol):
    return (inbound_mail._connect_imap_with_retry() if protocol == "imap"
            else inbound_mail._connect_pop3_with_retry())


@pytest.fixture(autouse=True)
def no_retry_delay(monkeypatch):
    monkeypatch.setattr(inbound_mail.time, "sleep", lambda _: None)


@pytest.mark.parametrize("protocol,implicit", [("imap", True), ("imap", False), ("pop3", True), ("pop3", False)])
def test_untrusted_certificate_never_receives_credentials(tmp_path, monkeypatch, protocol, implicit):
    with mail_server(tmp_path, protocol=protocol, implicit=implicit) as server:
        configure_inbound(monkeypatch, inbound_mail.settings, server, protocol=protocol, implicit=implicit)
        client = None
        try:
            with pytest.raises(RuntimeError):
                client = connect(protocol)
        finally:
            if client is not None:
                close_mail_client(client, protocol)
        assert not any(command in {"USER", "PASS", "LOGIN"} for command, _ in server.commands)


@pytest.mark.parametrize("protocol", ["imap", "pop3"])
def test_failed_upgrade_closes_transport_even_when_logout_unavailable(tmp_path, monkeypatch, protocol):
    with mail_server(tmp_path, protocol=protocol, upgrade=False, fail_close=True) as server:
        configure_inbound(monkeypatch, inbound_mail.settings, server, protocol=protocol, implicit=False)
        connections = track_connections(monkeypatch, inbound_mail, protocol=protocol, implicit=False)
        with pytest.raises(RuntimeError):
            connect(protocol)
        assert connections
        assert all(sock.fileno() == -1 and stream.closed for sock, stream in connections)


def test_refused_pop3_stls_never_receives_credentials(tmp_path, monkeypatch):
    with mail_server(tmp_path, protocol="pop3", upgrade=False) as server:
        configure_inbound(monkeypatch, inbound_mail.settings, server, protocol="pop3", implicit=False)
        client = None
        try:
            with pytest.raises(RuntimeError):
                client = connect("pop3")
        finally:
            if client is not None:
                close_mail_client(client, "pop3")
        assert not any(command in {"USER", "PASS"} for command, _ in server.commands)


@pytest.mark.parametrize("protocol,implicit", [("imap", True), ("imap", False), ("pop3", True), ("pop3", False)])
def test_valid_tls_still_authenticates_without_plaintext_credentials(tmp_path, monkeypatch, protocol, implicit):
    with mail_server(tmp_path, protocol=protocol, implicit=implicit) as server:
        configure_inbound(monkeypatch, inbound_mail.settings, server, protocol=protocol, implicit=implicit)
        monkeypatch.setenv("SSL_CERT_FILE", str(server.cert_path))
        client = connect(protocol)
        close_mail_client(client, protocol)
        auth = [(command, encrypted) for command, encrypted in server.commands if command in {"USER", "PASS", "LOGIN"}]
        assert auth
        assert all(encrypted for _, encrypted in auth)


@pytest.mark.parametrize("protocol", ["imap", "pop3"])
@pytest.mark.parametrize("problem", ["expired", "wrong_host"])
def test_invalid_trusted_certificate_never_receives_credentials(tmp_path, monkeypatch, protocol, problem):
    with mail_server(tmp_path, protocol=protocol, implicit=True, **{problem: True}) as server:
        configure_inbound(monkeypatch, inbound_mail.settings, server, protocol=protocol, implicit=True)
        monkeypatch.setenv("SSL_CERT_FILE", str(server.cert_path))
        client = None
        try:
            with pytest.raises(RuntimeError):
                client = connect(protocol)
        finally:
            if client is not None:
                close_mail_client(client, protocol)
        assert not any(command in {"USER", "PASS", "LOGIN"} for command, _ in server.commands)
