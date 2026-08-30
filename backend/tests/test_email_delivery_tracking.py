"""EİSA Global e-posta teslimat günlüğü ve yetki testleri."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.api.eisa_emails import router
from app.core.database import Base, get_db
from app.models.entities import EmailDeliveryLog, User, UserRole
from app.services import mailer


class _FakeSmtp:
    def __init__(self, *_args, **_kwargs):
        self.messages = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def starttls(self):
        return None

    def login(self, *_args):
        return None

    def send_message(self, message):
        self.messages.append(message)


def _session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def test_mailer_records_successful_delivery(monkeypatch):
    SessionLocal = _session_factory()
    monkeypatch.setattr(mailer.settings, "smtp_host", "smtp.resend.com")
    monkeypatch.setattr(mailer.settings, "smtp_from_email", "noreply@isgsuite.tr")
    monkeypatch.setattr(mailer.smtplib, "SMTP", _FakeSmtp)

    with SessionLocal() as db:
        result = mailer.send_email(
            to="admin@example.com",
            subject="Deneme",
            body="İçerik saklanmamalı.",
            db=db,
            event_type="password_reset",
            recipient_name="Admin",
            related_type="password_reset_token",
        )
        db.commit()
        row = db.scalar(select(EmailDeliveryLog).where(EmailDeliveryLog.id == result["log_id"]))

        assert result["ok"] is True
        assert result["status"] == "sent"
        assert result["provider"] == "resend_smtp"
        assert row is not None
        assert row.status == "sent"
        assert row.sent_at is not None
        assert row.error_message is None


def test_mailer_records_missing_smtp_as_failed(monkeypatch):
    SessionLocal = _session_factory()
    monkeypatch.setattr(mailer.settings, "smtp_host", None)
    monkeypatch.setattr(mailer.settings, "smtp_from_email", "noreply@isgsuite.tr")

    with SessionLocal() as db:
        result = mailer.send_email(
            to="admin@example.com",
            subject="Deneme",
            body="İçerik",
            db=db,
            event_type="generic",
        )
        db.commit()
        row = db.scalar(select(EmailDeliveryLog).where(EmailDeliveryLog.id == result["log_id"]))

        assert result["ok"] is False
        assert result["status"] == "smtp_not_configured"
        assert row is not None
        assert row.status == "failed"
        assert row.error_code == "smtp_not_configured"


def test_email_center_is_global_admin_only(monkeypatch):
    SessionLocal = _session_factory()
    with SessionLocal() as db:
        db.add(
            EmailDeliveryLog(
                event_type="password_reset",
                provider="smtp",
                recipient_email="admin@example.com",
                subject="Şifre sıfırlama",
                status="sent",
            )
        )
        db.commit()

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        def override_db():
            yield db

        current = User(id=1, email="global@example.com", full_name="Global", role=UserRole.GLOBAL_ADMIN)
        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: current

        with TestClient(app) as client:
            summary = client.get("/api/v1/eisa/emails/summary")
            listing = client.get("/api/v1/eisa/emails")
            assert summary.status_code == 200
            assert summary.json()["total"] == 1
            assert listing.status_code == 200
            assert listing.json()["items"][0]["recipient_email"] == "admin@example.com"
            assert "body" not in listing.json()["items"][0]

            current.role = UserRole.SAFETY_SPECIALIST
            forbidden = client.get("/api/v1/eisa/emails/summary")
            assert forbidden.status_code == 403
