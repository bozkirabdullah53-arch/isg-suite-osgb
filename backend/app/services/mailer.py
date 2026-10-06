"""SMTP e-posta gönderici — yapılandırma yoksa kuyruk/bildirim düşer, hata fırlatmaz."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import EmailDeliveryLog

logger = logging.getLogger(__name__)


def smtp_configured() -> bool:
    return bool((settings.smtp_host or "").strip() and (settings.smtp_from_email or "").strip())


def smtp_configuration_error() -> tuple[str, str] | None:
    """Validate delivery settings without exposing credentials or contacting SMTP."""
    if not smtp_configured():
        return "smtp_not_configured", "SMTP e-posta ayarları yapılandırılmamış."
    if not settings.smtp_use_ssl and not settings.smtp_use_tls:
        return "smtp_tls_required", "SMTP aktarım şifrelemesi zorunludur (TLS/SSL)."
    if settings.smtp_username and not settings.smtp_password:
        return "smtp_credentials_missing", "SMTP kimlik doğrulama parolası eksik."
    return None


@contextmanager
def open_smtp_connection():
    """Authenticate only after verified TLS; callers may reuse one connection."""
    problem = smtp_configuration_error()
    if problem:
        raise RuntimeError(problem[1])
    tls_context = ssl.create_default_context()
    server = (
        smtplib.SMTP_SSL(
            settings.smtp_host, settings.smtp_port, timeout=20, context=tls_context
        )
        if settings.smtp_use_ssl
        else smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
    )
    with server:
        if settings.smtp_use_tls and not settings.smtp_use_ssl:
            server.starttls(context=tls_context)
            server.ehlo()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password or "")
        yield server


def email_provider_name() -> str:
    """Return a safe provider label; never expose SMTP credentials in the UI."""
    host = (settings.smtp_host or "").strip().casefold()
    return "resend_smtp" if "resend" in host else "smtp"


def _create_delivery_log(
    db: Session | None,
    *,
    to: str,
    subject: str,
    event_type: str,
    recipient_name: str | None,
    user_id: int | None,
    osgb_id: int | None,
    triggered_by_user_id: int | None,
    related_type: str | None,
    related_id: str | None,
) -> EmailDeliveryLog | None:
    if db is None:
        return None
    row = EmailDeliveryLog(
        event_type=(event_type or "generic")[:80],
        provider=email_provider_name(),
        recipient_email=to or None,
        recipient_name=(recipient_name or "")[:160] or None,
        subject=(subject or "")[:255],
        status="queued",
        user_id=user_id,
        osgb_id=osgb_id,
        triggered_by_user_id=triggered_by_user_id,
        related_type=(related_type or "")[:80] or None,
        related_id=(str(related_id) if related_id is not None else "")[:80] or None,
    )
    db.add(row)
    db.flush()
    return row


def _finish_delivery_log(
    db: Session | None,
    row: EmailDeliveryLog | None,
    *,
    status: str,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    if db is None or row is None:
        return
    row.status = status
    row.error_code = (error_code or "")[:80] or None
    row.error_message = (error_message or "")[:500] or None
    row.sent_at = datetime.utcnow() if status == "sent" else None
    db.flush()


def send_email(
    *,
    to: str,
    subject: str,
    body: str,
    db: Session | None = None,
    event_type: str = "generic",
    recipient_name: str | None = None,
    user_id: int | None = None,
    osgb_id: int | None = None,
    triggered_by_user_id: int | None = None,
    related_type: str | None = None,
    related_id: str | None = None,
    attachments: list[dict[str, Any]] | None = None,
    smtp_server: smtplib.SMTP | None = None,
) -> dict[str, Any]:
    to = (to or "").strip()
    subject = (subject or "").strip()
    log_row = _create_delivery_log(
        db,
        to=to,
        subject=subject,
        event_type=event_type,
        recipient_name=recipient_name,
        user_id=user_id,
        osgb_id=osgb_id,
        triggered_by_user_id=triggered_by_user_id,
        related_type=related_type,
        related_id=related_id,
    )
    if not to:
        _finish_delivery_log(
            db,
            log_row,
            status="failed",
            error_code="no_recipient",
            error_message="Alıcı e-posta adresi bulunamadı.",
        )
        return {"ok": False, "status": "no_recipient", "log_id": log_row.id if log_row else None}
    problem = smtp_configuration_error()
    if problem:
        error_code, error_message = problem
        logger.warning("E-posta gönderilemedi: %s", error_message)
        _finish_delivery_log(
            db,
            log_row,
            status="failed",
            error_code=error_code,
            error_message=error_message,
        )
        return {
            "ok": False,
            "status": error_code,
            "to": to,
            "subject": subject,
            "provider": email_provider_name(),
            "log_id": log_row.id if log_row else None,
        }
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_email
    msg["To"] = to
    msg.set_content(body)
    for attachment in attachments or []:
        content = attachment.get("content")
        filename = str(attachment.get("filename") or "ek-dosya")
        maintype = str(attachment.get("maintype") or "application")
        subtype = str(attachment.get("subtype") or "octet-stream")
        if isinstance(content, bytes):
            msg.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)
    try:
        if smtp_server is not None:
            smtp_server.send_message(msg)
        else:
            with open_smtp_connection() as server:
                server.send_message(msg)
        _finish_delivery_log(db, log_row, status="sent")
        return {
            "ok": True,
            "status": "sent",
            "to": to,
            "provider": email_provider_name(),
            "log_id": log_row.id if log_row else None,
        }
    except Exception as exc:  # noqa: BLE001 — bildirim yolunu kırma
        logger.warning("E-posta gönderilemedi: %s", exc)
        error = str(exc)[:200]
        _finish_delivery_log(
            db,
            log_row,
            status="failed",
            error_code="send_failed",
            error_message=error or "SMTP gönderimi başarısız oldu.",
        )
        return {
            "ok": False,
            "status": "send_failed",
            "error": error,
            "to": to,
            "provider": email_provider_name(),
            "log_id": log_row.id if log_row else None,
        }
