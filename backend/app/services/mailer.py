"""SMTP e-posta gönderici — yapılandırma yoksa kuyruk/bildirim düşer, hata fırlatmaz."""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


def smtp_configured() -> bool:
    return bool((settings.smtp_host or "").strip() and (settings.smtp_from_email or "").strip())


def send_email(*, to: str, subject: str, body: str) -> dict[str, Any]:
    to = (to or "").strip()
    if not to:
        return {"ok": False, "status": "no_recipient"}
    if not smtp_configured():
        logger.info("SMTP yok — e-posta kuyruğa alınmadı: %s | %s", to, subject)
        return {"ok": False, "status": "smtp_not_configured", "to": to, "subject": subject}
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
        return {"ok": True, "status": "sent", "to": to}
    except Exception as exc:  # noqa: BLE001 — bildirim yolunu kırma
        logger.warning("E-posta gönderilemedi: %s", exc)
        return {"ok": False, "status": "send_failed", "error": str(exc)[:200], "to": to}
