"""EİSA Global e-posta teslimat izleme uçları."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.entities import EmailDeliveryLog, EmailInboxMessage, User, UserRole
from app.services.inbound_mail import inbound_mail_status, sync_inbox
from app.services.mailer import email_provider_name, send_email, smtp_configured


router = APIRouter(prefix="/eisa/emails", tags=["EİSA E-posta"])


class EmailSendRequest(BaseModel):
    recipient_email: EmailStr
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=100_000)


def _filters(
    *,
    q: str | None = None,
    status: str | None = None,
    event_type: str | None = None,
):
    conditions = []
    needle = (q or "").strip().casefold()
    if needle:
        pattern = f"%{needle}%"
        conditions.append(
            or_(
                func.lower(EmailDeliveryLog.recipient_email).like(pattern),
                func.lower(EmailDeliveryLog.recipient_name).like(pattern),
                func.lower(EmailDeliveryLog.subject).like(pattern),
                func.lower(EmailDeliveryLog.event_type).like(pattern),
            )
        )
    clean_status = (status or "").strip().casefold()
    if clean_status in {"queued", "sent", "failed"}:
        conditions.append(EmailDeliveryLog.status == clean_status)
    clean_event = (event_type or "").strip()
    if clean_event:
        conditions.append(EmailDeliveryLog.event_type == clean_event[:80])
    return conditions


def _row_payload(row: EmailDeliveryLog) -> dict:
    return {
        "id": row.id,
        "event_type": row.event_type,
        "provider": row.provider,
        "recipient_email": row.recipient_email,
        "recipient_name": row.recipient_name,
        "subject": row.subject,
        "status": row.status,
        "error_code": row.error_code,
        "error_message": row.error_message,
        "attempt_count": row.attempt_count,
        "user_id": row.user_id,
        "osgb_id": row.osgb_id,
        "triggered_by_user_id": row.triggered_by_user_id,
        "related_type": row.related_type,
        "related_id": row.related_id,
        "created_at": row.created_at,
        "sent_at": row.sent_at,
    }


def _inbox_payload(row: EmailInboxMessage, *, include_body: bool = True) -> dict:
    payload = {
        "id": row.id,
        "mailbox": row.mailbox,
        "imap_uid": row.imap_uid,
        "message_id": row.message_id,
        "sender_email": row.sender_email,
        "sender_name": row.sender_name,
        "recipients": row.recipients,
        "subject": row.subject,
        "has_attachments": row.has_attachments,
        "attachment_count": row.attachment_count,
        "is_read": row.is_read,
        "received_at": row.received_at,
        "synced_at": row.synced_at,
    }
    if include_body:
        payload["body_text"] = row.body_text
    return payload


@router.get("/summary")
def email_summary(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    def count(status: str | None = None, *, since: datetime | None = None) -> int:
        conditions = []
        if status:
            conditions.append(EmailDeliveryLog.status == status)
        if since:
            conditions.append(EmailDeliveryLog.created_at >= since)
        return int(db.scalar(select(func.count()).select_from(EmailDeliveryLog).where(*conditions)) or 0)

    last_24_hours = datetime.utcnow() - timedelta(hours=24)
    return {
        "provider": email_provider_name(),
        "smtp_configured": smtp_configured(),
        "inbound": inbound_mail_status(),
        "inbox_total": int(db.scalar(select(func.count()).select_from(EmailInboxMessage)) or 0),
        "inbox_unread": int(
            db.scalar(
                select(func.count())
                .select_from(EmailInboxMessage)
                .where(EmailInboxMessage.is_read.is_(False))
            )
            or 0
        ),
        "total": count(),
        "sent": count("sent"),
        "failed": count("failed"),
        "queued": count("queued"),
        "last_24_hours": count(since=last_24_hours),
        "last_24_hours_sent": count("sent", since=last_24_hours),
        "last_24_hours_failed": count("failed", since=last_24_hours),
    }


@router.get("")
def list_email_deliveries(
    q: str | None = Query(default=None, max_length=120),
    status: str | None = Query(default=None, max_length=32),
    event_type: str | None = Query(default=None, max_length=80),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    conditions = _filters(q=q, status=status, event_type=event_type)
    total = int(db.scalar(select(func.count()).select_from(EmailDeliveryLog).where(*conditions)) or 0)
    rows = list(
        db.scalars(
            select(EmailDeliveryLog)
            .where(*conditions)
            .order_by(desc(EmailDeliveryLog.created_at), desc(EmailDeliveryLog.id))
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return {
        "items": [_row_payload(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total else 0,
    }


@router.post("/send")
def send_platform_email(
    payload: EmailSendRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    result = send_email(
        to=str(payload.recipient_email),
        subject=payload.subject,
        body=payload.body,
        db=db,
        event_type="generic",
        triggered_by_user_id=user.id,
        related_type="global_mail_compose",
    )
    db.commit()
    if not result.get("ok"):
        raise HTTPException(
            status_code=502,
            detail=result.get("error_message") or result.get("error") or "E-posta gönderilemedi.",
        )
    return result


@router.post("/inbox/sync")
def sync_email_inbox(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    """İsimtescil IMAP gelen kutusunu Global ekranı için yeniler."""
    return sync_inbox(db)


@router.get("/inbox")
def list_email_inbox(
    q: str | None = Query(default=None, max_length=120),
    unread_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    conditions = []
    needle = (q or "").strip().casefold()
    if needle:
        pattern = f"%{needle}%"
        conditions.append(
            or_(
                func.lower(EmailInboxMessage.sender_email).like(pattern),
                func.lower(EmailInboxMessage.sender_name).like(pattern),
                func.lower(EmailInboxMessage.subject).like(pattern),
                func.lower(EmailInboxMessage.body_text).like(pattern),
            )
        )
    if unread_only:
        conditions.append(EmailInboxMessage.is_read.is_(False))
    total = int(db.scalar(select(func.count()).select_from(EmailInboxMessage).where(*conditions)) or 0)
    rows = list(
        db.scalars(
            select(EmailInboxMessage)
            .where(*conditions)
            .order_by(
                desc(EmailInboxMessage.received_at),
                desc(EmailInboxMessage.created_at),
                desc(EmailInboxMessage.id),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return {
        "items": [_inbox_payload(row, include_body=False) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total else 0,
    }


@router.get("/inbox/{message_id}")
def get_email_inbox_message(
    message_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    row = db.get(EmailInboxMessage, message_id)
    if not row:
        raise HTTPException(status_code=404, detail="Gelen e-posta bulunamadı.")
    return _inbox_payload(row)


@router.patch("/inbox/{message_id}/read")
def mark_email_inbox_message_read(
    message_id: int,
    is_read: bool = Query(default=True),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    row = db.get(EmailInboxMessage, message_id)
    if not row:
        raise HTTPException(status_code=404, detail="Gelen e-posta bulunamadı.")
    row.is_read = is_read
    db.commit()
    db.refresh(row)
    return _inbox_payload(row, include_body=False)


@router.get("/{email_id}")
def get_email_delivery(
    email_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    row = db.get(EmailDeliveryLog, email_id)
    if not row:
        raise HTTPException(status_code=404, detail="E-posta kaydı bulunamadı.")
    return _row_payload(row)
