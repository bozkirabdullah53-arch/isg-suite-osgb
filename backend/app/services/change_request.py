"""İBYS Değişiklik Talebi servisi (§3-§5).

Akış: submitted → verified → approved → applied
veya reddedilir (rejected) / iptal edilir (cancelled).

4 göz prensibi: talebi açan ile onaylayan farklı kişi olmalı; uygulayan,
onaylayan kişiyle de farklı olmalıdır.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Callable

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    ChangeRequest,
    ChangeRequestEvent,
    ChangeRequestStatus,
    User,
    UserRole,
)
from app.services.audit import add_audit_log, serialize_audit_value

logger = logging.getLogger(__name__)

MIN_JUSTIFICATION_CHARS = 10
MIN_REJECTION_CHARS = 10
SLA_DAYS = 10


class ChangeRequestError(HTTPException):
    """Değişiklik talebi iş kuralı ihlalinde kullanılır."""


def _now() -> datetime:
    return datetime.utcnow()


def _next_request_no(db: Session, *, now: datetime) -> str:
    year = now.year
    count = int(
        db.scalar(
            select(func.count())
            .select_from(ChangeRequest)
            .where(ChangeRequest.request_no.like(f"CR-{year}-%"))
        )
        or 0
    )
    return f"CR-{year}-{count + 1:04d}"


def _record_event(
    db: Session,
    *,
    request_id: int,
    from_status: str | None,
    to_status: str,
    actor_user_id: int | None,
    note: str | None,
) -> ChangeRequestEvent:
    event = ChangeRequestEvent(
        change_request_id=request_id,
        from_status=from_status,
        to_status=to_status,
        actor_user_id=actor_user_id,
        note=(note or None),
    )
    db.add(event)
    db.flush()
    return event


_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    ChangeRequestStatus.SUBMITTED.value: {
        ChangeRequestStatus.VERIFIED.value,
        ChangeRequestStatus.REJECTED.value,
        ChangeRequestStatus.CANCELLED.value,
    },
    ChangeRequestStatus.VERIFIED.value: {
        ChangeRequestStatus.APPROVED.value,
        ChangeRequestStatus.REJECTED.value,
        ChangeRequestStatus.CANCELLED.value,
    },
    ChangeRequestStatus.APPROVED.value: {
        ChangeRequestStatus.APPLIED.value,
        ChangeRequestStatus.REJECTED.value,
        ChangeRequestStatus.CANCELLED.value,
    },
    ChangeRequestStatus.APPLIED.value: set(),
    ChangeRequestStatus.REJECTED.value: set(),
    ChangeRequestStatus.CANCELLED.value: set(),
}


def _transition(request: ChangeRequest, to_status: str) -> None:
    """Durum makinesi geçişini doğrular (geriye doğru akışa izin vermez)."""
    if to_status not in _ALLOWED_TRANSITIONS.get(request.status, set()):
        raise ChangeRequestError(
            status_code=422,
            detail=f"Talep '{request.status}' durumundan '{to_status}' durumuna geçemez.",
        )


def create_request(db: Session, *, user: User, payload: dict) -> ChangeRequest:
    """Yeni değişiklik talebi açar (§3)."""
    justification = (payload.get("justification") or "").strip()
    if len(justification) < MIN_JUSTIFICATION_CHARS:
        raise ChangeRequestError(
            status_code=422,
            detail=f"Gerekçe zorunludur (en az {MIN_JUSTIFICATION_CHARS} karakter).",
        )

    target_entity_type = (payload.get("target_entity_type") or "").strip()
    if not target_entity_type:
        raise ChangeRequestError(status_code=422, detail="Hedef varlık türü zorunludur.")

    requested_value = payload.get("requested_value")
    if requested_value is None or str(requested_value).strip() == "":
        raise ChangeRequestError(status_code=422, detail="İstenen yeni değer zorunludur.")

    now = _now()
    request = ChangeRequest(
        request_no=_next_request_no(db, now=now),
        company_id=payload.get("company_id"),
        requested_by_user_id=user.id,
        requester_type=(payload.get("requester_type") or "employer").strip() or "employer",
        channel=(payload.get("channel") or "platform").strip() or "platform",
        request_kind=(payload.get("request_kind") or None),
        identity_verified=bool(payload.get("identity_verified", False)),
        verification_method=(payload.get("verification_method") or None),
        target_entity_type=target_entity_type,
        target_entity_id=(payload.get("target_entity_id") or None),
        field_name=(payload.get("field_name") or None),
        old_value=(payload.get("old_value") or None),
        requested_value=str(requested_value),
        justification=justification,
        attachment_path=(payload.get("attachment_path") or None),
        status=ChangeRequestStatus.SUBMITTED.value,
        sla_due_at=now + timedelta(days=SLA_DAYS),
    )
    db.add(request)
    db.flush()
    _record_event(
        db,
        request_id=request.id,
        from_status=None,
        to_status=ChangeRequestStatus.SUBMITTED.value,
        actor_user_id=user.id,
        note="Talep oluşturuldu.",
    )
    add_audit_log(
        db,
        user=user,
        action="change_request_created",
        module="change_request",
        entity_type="change_request",
        entity_id=str(request.id),
        company_id=request.company_id,
        description=f"Değişiklik talebi oluşturuldu: {request.request_no}",
        new_value=serialize_audit_value(
            {
                "request_no": request.request_no,
                "target_entity_type": request.target_entity_type,
                "target_entity_id": request.target_entity_id,
                "field_name": request.field_name,
                "channel": request.channel,
                "sla_due_at": request.sla_due_at,
            }
        ),
    )
    db.commit()
    db.refresh(request)
    return request


def _get(db: Session, request_id: int) -> ChangeRequest:
    request = db.get(ChangeRequest, request_id)
    if request is None:
        raise ChangeRequestError(status_code=404, detail="Talep bulunamadı.")
    return request


def verify_request(db: Session, *, request_id: int, user: User, note: str | None = None) -> ChangeRequest:
    """Talebi doğrular (§3.2 kimlik doğrulama)."""
    request = _get(db, request_id)
    _transition(request, ChangeRequestStatus.VERIFIED.value)
    previous = request.status
    request.verified_by_id = user.id
    request.verified_at = _now()
    request.status = ChangeRequestStatus.VERIFIED.value
    _record_event(
        db,
        request_id=request.id,
        from_status=previous,
        to_status=ChangeRequestStatus.VERIFIED.value,
        actor_user_id=user.id,
        note=note,
    )
    add_audit_log(
        db,
        user=user,
        action="change_request_verified",
        module="change_request",
        entity_type="change_request",
        entity_id=str(request.id),
        company_id=request.company_id,
        description=f"Talep doğrulandı: {request.request_no}",
        old_value=serialize_audit_value({"status": previous}),
        new_value=serialize_audit_value({"status": request.status, "note": note}),
    )
    db.commit()
    db.refresh(request)
    return request


def approve_request(db: Session, *, request_id: int, user: User, note: str | None = None) -> ChangeRequest:
    """Talebi onaylar (4 göz: talep eden/doğrulayanla aynı kişi olamaz)."""
    request = _get(db, request_id)
    if request.requested_by_user_id == user.id:
        raise ChangeRequestError(
            status_code=403,
            detail="Kendi açtığınız talebi onaylayamazsınız (4 göz prensibi).",
        )
    if request.verified_by_id == user.id:
        raise ChangeRequestError(
            status_code=403,
            detail="Talebi doğrulayan kişi onaylayamaz (4 göz prensibi).",
        )
    _transition(request, ChangeRequestStatus.APPROVED.value)
    previous = request.status
    request.approved_by_id = user.id
    request.approved_at = _now()
    request.status = ChangeRequestStatus.APPROVED.value
    _record_event(
        db,
        request_id=request.id,
        from_status=previous,
        to_status=ChangeRequestStatus.APPROVED.value,
        actor_user_id=user.id,
        note=note,
    )
    add_audit_log(
        db,
        user=user,
        action="change_request_approved",
        module="change_request",
        entity_type="change_request",
        entity_id=str(request.id),
        company_id=request.company_id,
        description=f"Talep onaylandı: {request.request_no}",
        old_value=serialize_audit_value({"status": previous}),
        new_value=serialize_audit_value({"status": request.status, "note": note}),
    )
    db.commit()
    db.refresh(request)
    return request


def reject_request(db: Session, *, request_id: int, user: User, reason: str) -> ChangeRequest:
    """Talebi gerekçeli reddeder (§7)."""
    cleaned = (reason or "").strip()
    if len(cleaned) < MIN_REJECTION_CHARS:
        raise ChangeRequestError(
            status_code=422,
            detail=f"Reddetme gerekçesi zorunludur (en az {MIN_REJECTION_CHARS} karakter).",
        )
    request = _get(db, request_id)
    _transition(request, ChangeRequestStatus.REJECTED.value)
    previous = request.status
    request.rejected_by_id = user.id
    request.rejected_at = _now()
    request.rejection_reason = cleaned[:2000]
    request.status = ChangeRequestStatus.REJECTED.value
    _record_event(
        db,
        request_id=request.id,
        from_status=previous,
        to_status=ChangeRequestStatus.REJECTED.value,
        actor_user_id=user.id,
        note=cleaned,
    )
    add_audit_log(
        db,
        user=user,
        action="change_request_rejected",
        module="change_request",
        entity_type="change_request",
        entity_id=str(request.id),
        company_id=request.company_id,
        description=f"Talep reddedildi: {request.request_no}",
        old_value=serialize_audit_value({"status": previous}),
        new_value=serialize_audit_value({"status": request.status, "reason": cleaned}),
    )
    db.commit()
    db.refresh(request)
    return request


def cancel_request(db: Session, *, request_id: int, user: User, note: str | None = None) -> ChangeRequest:
    """Bekleyen bir talebi iptal eder."""
    request = _get(db, request_id)
    _transition(request, ChangeRequestStatus.CANCELLED.value)
    previous = request.status
    request.status = ChangeRequestStatus.CANCELLED.value
    request.rejected_by_id = user.id
    request.rejected_at = _now()
    request.rejection_reason = (note or "Talep iptal edildi.")[:2000]
    _record_event(
        db,
        request_id=request.id,
        from_status=previous,
        to_status=ChangeRequestStatus.CANCELLED.value,
        actor_user_id=user.id,
        note=note,
    )
    add_audit_log(
        db,
        user=user,
        action="change_request_cancelled",
        module="change_request",
        entity_type="change_request",
        entity_id=str(request.id),
        company_id=request.company_id,
        description=f"Talep iptal edildi: {request.request_no}",
        old_value=serialize_audit_value({"status": previous}),
        new_value=serialize_audit_value({"status": request.status, "note": note}),
    )
    db.commit()
    db.refresh(request)
    return request


def apply_request(
    db: Session,
    *,
    request_id: int,
    user: User,
    applier: Callable[[ChangeRequest, Session], Any] | None = None,
) -> ChangeRequest:
    """Onaylı talebi uygular (§5.3). 4 göz: onaylayan kişi uygulayamaz."""
    request = _get(db, request_id)
    if request.approved_by_id == user.id:
        raise ChangeRequestError(
            status_code=403,
            detail="Onaylayan kişi talebi kendisi uygulayamaz (4 göz prensibi).",
        )
    _transition(request, ChangeRequestStatus.APPLIED.value)
    previous = request.status
    result: Any = None
    if applier is not None:
        try:
            result = applier(request, db)
        except ChangeRequestError:
            raise
        except Exception as exc:  # noqa: BLE001 - uygulama hatası kullanıcıya bildirilir
            db.rollback()
            logger.exception("Değişiklik talebi uygulanamadı: request_no=%s", request.request_no)
            raise
        request = _get(db, request_id)
    request.applied_by_id = user.id
    request.applied_at = _now()
    request.status = ChangeRequestStatus.APPLIED.value
    _record_event(
        db,
        request_id=request.id,
        from_status=previous,
        to_status=ChangeRequestStatus.APPLIED.value,
        actor_user_id=user.id,
        note=None,
    )
    add_audit_log(
        db,
        user=user,
        action="change_request_applied",
        module="change_request",
        entity_type="change_request",
        entity_id=str(request.id),
        company_id=request.company_id,
        description=f"Değişiklik uygulandı: {request.request_no}",
        old_value=serialize_audit_value({"status": previous}),
        new_value=serialize_audit_value(
            {
                "status": request.status,
                "target_entity_type": request.target_entity_type,
                "target_entity_id": request.target_entity_id,
                "field_name": request.field_name,
            }
        ),
    )
    db.commit()
    db.refresh(request)
    return request


def list_requests(
    db: Session,
    *,
    user: User,
    status: str | None = None,
    company_id: int | None = None,
    limit: int = 200,
) -> list[ChangeRequest]:
    """Kullanıcı kapsamına göre filtrelenmiş talep listesi."""
    stmt = select(ChangeRequest).order_by(ChangeRequest.created_at.desc()).limit(max(1, min(limit, 500)))
    if status:
        try:
            normalized = ChangeRequestStatus(status).value
        except ValueError:
            raise ChangeRequestError(status_code=422, detail="Geçersiz talep durumu.") from None
        stmt = stmt.where(ChangeRequest.status == normalized)
    if company_id is not None:
        stmt = stmt.where(ChangeRequest.company_id == company_id)
    if user.role != UserRole.GLOBAL_ADMIN:
        if user.company_id is not None:
            stmt = stmt.where(ChangeRequest.company_id == user.company_id)
        else:
            stmt = stmt.where(ChangeRequest.requested_by_user_id == user.id)
    return list(db.scalars(stmt).all())


def get_request(db: Session, request_id: int) -> ChangeRequest:
    return _get(db, request_id)


def events_for_request(db: Session, request_id: int) -> list[ChangeRequestEvent]:
    return list(
        db.scalars(
            select(ChangeRequestEvent)
            .where(ChangeRequestEvent.change_request_id == request_id)
            .order_by(ChangeRequestEvent.id)
        ).all()
    )


def sla_overdue_requests(db: Session, *, now: datetime | None = None) -> list[ChangeRequest]:
    """SLA süresi geçmiş, hâlâ açık talepler."""
    moment = now or _now()
    return list(
        db.scalars(
            select(ChangeRequest).where(
                ChangeRequest.sla_due_at.is_not(None),
                ChangeRequest.sla_due_at < moment,
                ChangeRequest.status.in_(
                    (
                        ChangeRequestStatus.SUBMITTED.value,
                        ChangeRequestStatus.VERIFIED.value,
                        ChangeRequestStatus.APPROVED.value,
                    )
                ),
            )
        ).all()
    )
