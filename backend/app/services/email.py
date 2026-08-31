from sqlalchemy.orm import Session

from app.services.mailer import send_email as _send_email


def send_email(
    *,
    to_email: str,
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
    attachments: list[dict] | None = None,
) -> bool:
    """Backward-compatible bool wrapper around the tracked mailer."""
    result = _send_email(
        to=to_email,
        subject=subject,
        body=body,
        db=db,
        event_type=event_type,
        recipient_name=recipient_name,
        user_id=user_id,
        osgb_id=osgb_id,
        triggered_by_user_id=triggered_by_user_id,
        related_type=related_type,
        related_id=related_id,
        attachments=attachments,
    )
    return bool(result.get("ok"))
