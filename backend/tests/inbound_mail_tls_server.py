"""Loopback-only mail fixture: records command names and encryption, never values."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import ipaddress
import socketserver
import ssl
from threading import Thread

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID


@contextmanager
def mail_server(tmp_path, *, protocol, implicit=False, upgrade=True, expired=False, wrong_host=False, fail_close=False):
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "loopback-mail-test")])
    now = datetime.now(timezone.utc)
    identities = [x509.DNSName("wrong.example.invalid")] if wrong_host else [
        x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
    ]
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=2))
            .not_valid_after(now - timedelta(days=1) if expired else now + timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName(identities), critical=False)
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))
    cert_path = tmp_path / "loopback-cert.pem"
    key_path = tmp_path / "loopback-key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                         serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)

    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            sock = self.request
            sock.settimeout(3)
            stream = None
            try:
                if implicit:
                    sock = context.wrap_socket(sock, server_side=True)
                stream = sock.makefile("rb")
                sock.sendall(b"* OK loopback test\r\n" if protocol == "imap" else b"+OK loopback test\r\n")
                while line := stream.readline():
                    words = line.decode("ascii").strip().split()
                    if not words:
                        break
                    tag, command = (words[0], words[1].upper()) if protocol == "imap" else ("", words[0].upper())
                    self.server.commands.append((command, isinstance(sock, ssl.SSLSocket)))
                    if command == "CAPABILITY":
                        sock.sendall(f"* CAPABILITY IMAP4rev1 STARTTLS\r\n{tag} OK done\r\n".encode())
                    elif command == "CAPA":
                        sock.sendall(b"+OK capabilities\r\nSTLS\r\nUSER\r\n.\r\n")
                    elif command in {"STARTTLS", "STLS"}:
                        if not upgrade:
                            sock.sendall(f"{tag} NO TLS unavailable\r\n".encode() if tag else b"-ERR TLS unavailable\r\n")
                            continue
                        sock.sendall(f"{tag} OK begin TLS\r\n".encode() if tag else b"+OK begin TLS\r\n")
                        stream.close()
                        stream = None
                        sock = context.wrap_socket(sock, server_side=True)
                        stream = sock.makefile("rb")
                    elif command in {"USER", "PASS", "LOGIN"}:
                        sock.sendall(f"{tag} OK authenticated\r\n".encode() if tag else b"+OK accepted\r\n")
                    elif command in {"LOGOUT", "QUIT"}:
                        if fail_close:
                            sock.sendall(f"{tag} BAD logout unavailable\r\n".encode() if tag else b"-ERR quit unavailable\r\n")
                            continue
                        sock.sendall(f"* BYE closing\r\n{tag} OK done\r\n".encode() if tag else b"+OK closing\r\n")
                        break
                    else:
                        sock.sendall(f"{tag} BAD unsupported\r\n".encode() if tag else b"-ERR unsupported\r\n")
            except (OSError, ssl.SSLError):
                # Certificate rejection is the behavior under test.
                pass
            finally:
                if stream is not None:
                    stream.close()
                sock.close()

    class Server(socketserver.ThreadingTCPServer):
        daemon_threads = True
        block_on_close = True

    server = Server(("127.0.0.1", 0), Handler)
    server.commands = []
    server.cert_path = cert_path
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def configure_inbound(monkeypatch, settings, server, *, protocol, implicit):
    monkeypatch.setattr(settings, "inbound_mail_enabled", True)
    monkeypatch.setattr(settings, "inbound_mail_host", "127.0.0.1")
    monkeypatch.setattr(settings, "inbound_mail_port", server.server_address[1])
    monkeypatch.setattr(settings, "inbound_mail_protocol", protocol)
    monkeypatch.setattr(settings, "inbound_mail_use_ssl", implicit)
    monkeypatch.setattr(settings, "inbound_mail_username", "tls-test@example.invalid")
    monkeypatch.setattr(settings, "inbound_mail_password", "synthetic-local-test-password")
    monkeypatch.setattr(settings, "inbound_mail_timeout_sec", 3)


def close_mail_client(client, protocol):
    if protocol == "imap":
        client.logout()
    else:
        client.quit()


def track_connections(monkeypatch, inbound_mail, *, protocol, implicit):
    module = inbound_mail.imaplib if protocol == "imap" else inbound_mail.poplib
    class_name = ("IMAP4_SSL" if implicit else "IMAP4") if protocol == "imap" else ("POP3_SSL" if implicit else "POP3")
    original = getattr(module, class_name)
    connections = []

    def record(*args, **kwargs):
        client = original(*args, **kwargs)
        connections.append((client.sock, client.file))
        return client

    if protocol == "imap":
        record.error = original.error
    monkeypatch.setattr(module, class_name, record)
    return connections
