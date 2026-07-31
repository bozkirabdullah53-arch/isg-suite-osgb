import smtplib
from email.message import EmailMessage

from app.core.config import settings


def send_email(*, to_email: str, subject: str, body: str) -> bool:
    """Send a plain-text email when SMTP is configured.

    Returns False instead of raising when SMTP is intentionally not configured.
    Production callers should log and retry failed deliveries.
    """
    if not settings.smtp_host:
        return False

    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_username and settings.smtp_password:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)
    return True
