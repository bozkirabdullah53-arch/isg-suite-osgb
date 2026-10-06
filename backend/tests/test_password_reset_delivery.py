"""Password recovery delivery, transport failures and account-neutral responses."""
from __future__ import annotations

import smtplib
import ssl
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import router
from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import get_password_hash, verify_password
from app.models.entities import EmailDeliveryLog, PasswordResetToken, User, UserRole
from app.services import mailer


@pytest.fixture()
def recovery(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "frontend_origin", "https://www.isgsuite.tr")
    monkeypatch.setattr(settings, "smtp_host", "giden.mailmatik.com")
    monkeypatch.setattr(settings, "smtp_port", 465)
    monkeypatch.setattr(settings, "smtp_username", "info@isgsuite.tr")
    monkeypatch.setattr(settings, "smtp_password", "test-only-credential")
    monkeypatch.setattr(settings, "smtp_from_email", "info@isgsuite.tr")
    monkeypatch.setattr(settings, "smtp_use_ssl", True)
    monkeypatch.setattr(settings, "smtp_use_tls", False)
    connections, messages = [], []

    class FakeSmtp:
        def __init__(self, host, port, *, timeout, context=None):
            self.secured = context is not None
            self.authenticated = False
            if context is not None:
                assert context.check_hostname
                assert context.verify_mode == ssl.CERT_REQUIRED
            connections.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def starttls(self, *, context):
            assert context.check_hostname
            assert context.verify_mode == ssl.CERT_REQUIRED
            self.secured = True

        def ehlo(self):
            assert self.secured

        def login(self, *_args):
            assert self.secured, "Credentials must never be sent over plaintext SMTP."
            self.authenticated = True

        def send_message(self, message):
            assert self.secured and self.authenticated
            messages.append(message)

    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", FakeSmtp)
    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSmtp)
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False)
    with sessions() as db:
        db.add(User(
            email="recovery@example.com",
            full_name="Recovery Test",
            hashed_password=get_password_hash("OldPassword123!"),
            role=UserRole.READ_ONLY,
            is_active=True,
        ))
        db.commit()

    def override_db():
        with sessions() as db:
            yield db

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield SimpleNamespace(
            client=client, sessions=sessions, connections=connections,
            messages=messages, smtp_class=FakeSmtp,
        )
    engine.dispose()


def _request(recovery, email="recovery@example.com"):
    return recovery.client.post("/api/v1/auth/forgot-password", json={"email": email})


@pytest.mark.parametrize("use_ssl", [True, False])
def test_email_link_completes_reset_using_one_verified_connection(recovery, monkeypatch, use_ssl):
    monkeypatch.setattr(settings, "smtp_use_ssl", use_ssl)
    monkeypatch.setattr(settings, "smtp_use_tls", not use_ssl)
    response = _request(recovery)
    assert response.status_code == 200, response.text
    assert len(recovery.connections) == 1  # preflight and send share the transport
    assert len(recovery.messages) == 1
    message = recovery.messages[0]
    assert message["To"] == "recovery@example.com"
    link = next(line for line in message.get_content().splitlines() if line.startswith("https://"))
    assert urlsplit(link).netloc == "www.isgsuite.tr"
    assert not urlsplit(link).query  # tokens must not enter server request logs
    token = parse_qs(urlsplit(link).fragment)["sifre-sifirla"][0]
    mismatch = recovery.client.post("/api/v1/auth/reset-password", json={
        "token": token, "new_password": "NewPassword123!", "new_password_confirm": "DifferentPassword123!",
    })
    assert mismatch.status_code == 422
    completed = recovery.client.post("/api/v1/auth/reset-password", json={
        "token": token, "new_password": "NewPassword123!", "new_password_confirm": "NewPassword123!",
    })
    assert completed.status_code == 200, completed.text
    reused = recovery.client.post("/api/v1/auth/reset-password", json={
        "token": token, "new_password": "AnotherPassword123!",
    })
    assert reused.status_code == 400
    with recovery.sessions() as db:
        user = db.scalar(select(User).where(User.email == "recovery@example.com"))
        assert verify_password("NewPassword123!", user.hashed_password)
        assert not verify_password("OldPassword123!", user.hashed_password)
        assert user.token_version == 1
        log = db.scalar(select(EmailDeliveryLog))
        assert log.status == "sent" and log.sent_at is not None


def test_registered_and_unknown_addresses_receive_same_neutral_response(recovery):
    known = _request(recovery)
    unknown = _request(recovery, "unknown@example.com")
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert "gönderildi" not in known.json()["message"]
    assert len(recovery.connections) == 2
    assert len(recovery.messages) == 1


@pytest.mark.parametrize("problem", ["plaintext", "no_password", "no_host"])
def test_bad_configuration_is_unavailable_before_any_account_lookup(recovery, monkeypatch, problem):
    if problem == "plaintext":
        monkeypatch.setattr(settings, "smtp_use_ssl", False)
        monkeypatch.setattr(settings, "smtp_use_tls", False)
    elif problem == "no_password":
        monkeypatch.setattr(settings, "smtp_password", None)
    else:
        monkeypatch.setattr(settings, "smtp_host", None)
    known = _request(recovery)
    unknown = _request(recovery, "unknown@example.com")
    assert known.status_code == unknown.status_code == 503
    assert known.json() == unknown.json()
    assert known.headers["Retry-After"] == "60"
    assert not recovery.connections and not recovery.messages
    with recovery.sessions() as db:
        assert db.scalar(select(func.count()).select_from(PasswordResetToken)) == 0


@pytest.mark.parametrize("failure", [OSError("unreachable"), smtplib.SMTPAuthenticationError(535, b"rejected")])
def test_transport_outage_is_reported_identically_for_all_accounts(recovery, monkeypatch, failure):
    class BrokenSmtp(recovery.smtp_class):
        def login(self, *_args):
            raise failure

    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", BrokenSmtp)
    known = _request(recovery)
    unknown = _request(recovery, "unknown@example.com")
    assert known.status_code == unknown.status_code == 503
    assert known.json() == unknown.json()
    assert not recovery.messages
    with recovery.sessions() as db:
        assert db.scalar(select(func.count()).select_from(PasswordResetToken)) == 0


def test_plaintext_mail_is_rejected_without_connecting(recovery, monkeypatch):
    monkeypatch.setattr(settings, "smtp_use_ssl", False)
    monkeypatch.setattr(settings, "smtp_use_tls", False)
    result = mailer.send_email(to="recovery@example.com", subject="Test", body="Test")
    assert result["ok"] is False and result["status"] == "smtp_tls_required"
    assert not recovery.connections


def test_recipient_rejection_is_logged_without_claiming_delivery(recovery, monkeypatch):
    class RejectSmtp(recovery.smtp_class):
        def send_message(self, message):
            raise smtplib.SMTPRecipientsRefused({message["To"]: (550, b"unavailable")})

    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", RejectSmtp)
    response = _request(recovery)
    assert response.status_code == 200
    assert "gönderildi" not in response.json()["message"]
    with recovery.sessions() as db:
        log = db.scalar(select(EmailDeliveryLog))
        assert log.status == "failed" and log.sent_at is None
