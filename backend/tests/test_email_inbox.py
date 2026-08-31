"""EİSA Global IMAP gelen kutusu testleri."""
from __future__ import annotations

from email.message import EmailMessage

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.entities import EmailInboxMessage
from app.services import inbound_mail


def _session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _raw_message(subject: str = "Deneme gelen posta") -> bytes:
    message = EmailMessage()
    message["From"] = "Abdullah <abdullah@example.com>"
    message["To"] = "info@isgsuite.tr"
    message["Subject"] = subject
    message["Message-ID"] = "<test-message@example.com>"
    message.set_content("Gelen e-postanın güvenli metin içeriği.")
    return message.as_bytes()


class _FakeImap:
    raw = _raw_message()

    def __init__(self, *_args, **_kwargs):
        self.logged_in = False

    def login(self, username, password):
        assert username == "info@isgsuite.tr"
        assert password == "secret"
        self.logged_in = True
        return "OK", [b"logged in"]

    def select(self, mailbox, readonly=True):
        assert mailbox == "INBOX"
        assert readonly is True
        return "OK", [b"1"]

    def uid(self, command, *args):
        if command == "search":
            return "OK", [b"1"]
        if command == "fetch":
            return "OK", [(b"header", self.raw)]
        raise AssertionError(command)

    def close(self):
        return "OK", [b"closed"]

    def logout(self):
        return "BYE", [b"logged out"]


class _FlakyImap(_FakeImap):
    attempts = 0

    def __init__(self, *_args, **_kwargs):
        type(self).attempts += 1
        if type(self).attempts == 1:
            raise EOFError("transient server EOF")


def test_inbound_mail_sync_is_idempotent_and_keeps_body_as_text(monkeypatch):
    SessionLocal = _session_factory()
    monkeypatch.setattr(inbound_mail.settings, "inbound_mail_enabled", True)
    monkeypatch.setattr(inbound_mail.settings, "inbound_mail_host", "imap.example.com")
    monkeypatch.setattr(inbound_mail.settings, "inbound_mail_username", "info@isgsuite.tr")
    monkeypatch.setattr(inbound_mail.settings, "inbound_mail_password", "secret")
    monkeypatch.setattr(inbound_mail.imaplib, "IMAP4_SSL", _FakeImap)

    with SessionLocal() as db:
        first = inbound_mail.sync_inbox(db)
        second = inbound_mail.sync_inbox(db)
        row = db.scalar(select(EmailInboxMessage))

        assert first["connected"] is True
        assert first["new_count"] == 1
        assert second["new_count"] == 0
        assert row is not None
        assert row.sender_email == "abdullah@example.com"
        assert row.subject == "Deneme gelen posta"
        assert "güvenli metin" in row.body_text
        assert row.is_read is False


def test_inbound_mail_is_fail_closed_without_secret(monkeypatch):
    SessionLocal = _session_factory()
    monkeypatch.setattr(inbound_mail.settings, "inbound_mail_enabled", True)
    monkeypatch.setattr(inbound_mail.settings, "inbound_mail_username", "info@isgsuite.tr")
    monkeypatch.setattr(inbound_mail.settings, "inbound_mail_password", None)

    with SessionLocal() as db:
        result = inbound_mail.sync_inbox(db)
        assert result["configured"] is False
        assert result["connected"] is False
        assert result["new_count"] == 0
        assert result["error"]


def test_inbound_mail_retries_transient_connection_eof(monkeypatch):
    SessionLocal = _session_factory()
    _FlakyImap.attempts = 0
    monkeypatch.setattr(inbound_mail.settings, "inbound_mail_enabled", True)
    monkeypatch.setattr(inbound_mail.settings, "inbound_mail_host", "imap.example.com")
    monkeypatch.setattr(inbound_mail.settings, "inbound_mail_username", "info@isgsuite.tr")
    monkeypatch.setattr(inbound_mail.settings, "inbound_mail_password", "secret")
    monkeypatch.setattr(inbound_mail.imaplib, "IMAP4_SSL", _FlakyImap)

    with SessionLocal() as db:
        result = inbound_mail.sync_inbox(db)

        assert result["connected"] is True
        assert result["new_count"] == 1
        assert _FlakyImap.attempts == 2


def test_deleted_inbox_message_is_not_restored_by_sync(monkeypatch):
    from datetime import datetime

    SessionLocal = _session_factory()
    monkeypatch.setattr(inbound_mail.settings, "inbound_mail_enabled", True)
    monkeypatch.setattr(inbound_mail.settings, "inbound_mail_host", "imap.example.com")
    monkeypatch.setattr(inbound_mail.settings, "inbound_mail_username", "info@isgsuite.tr")
    monkeypatch.setattr(inbound_mail.settings, "inbound_mail_password", "secret")
    monkeypatch.setattr(inbound_mail.imaplib, "IMAP4_SSL", _FakeImap)

    with SessionLocal() as db:
        inbound_mail.sync_inbox(db)
        row = db.scalar(select(EmailInboxMessage))
        assert row is not None
        row.deleted_at = datetime.utcnow()
        db.commit()

        result = inbound_mail.sync_inbox(db)
        db.refresh(row)

        assert result["new_count"] == 0
        assert row.deleted_at is not None
        assert db.scalar(select(EmailInboxMessage).where(EmailInboxMessage.deleted_at.is_(None))) is None
