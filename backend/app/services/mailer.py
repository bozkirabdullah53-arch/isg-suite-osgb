"""SMTP e-posta gönderici — yapılandırma yoksa kuyruk/bildirim düşer, hata fırlatmaz."""
from __future__ import annotations

from datetime import datetime
import logging
import smtplib
from email.message import EmailMessage
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import EmailDeliveryLog

logger = logging.getLogger(__name__)


def smtp_configured() -> bool:
    return bool((settings.smtp_host or "").strip() and (settings.smtp_from_email or "").strip())


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
    if not smtp_configured():
        logger.info("SMTP yok — e-posta kuyruğa alınmadı: %s | %s", to, subject)
        _finish_delivery_log(
            db,
            log_row,
            status="failed",
            error_code="smtp_not_configured",
            error_message="SMTP e-posta ayarları yapılandırılmamış.",
        )
        return {
            "ok": False,
            "status": "smtp_not_configured",
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
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password or "")
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
