"""Nitelikli e-imza orkestrasyon API (Desktop v0.10 birleşimi).

ÖNEMLİ: Mevcut lokal agent hattı /api/v1/esign altında kalır.
Bu router /api/v1/esign-orch — çakışma yok, mevcut akış bozulmaz.
PIN/özel anahtar sunucuda tutulmaz.
"""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.company_access import company_ids_for_query, ensure_company_access
from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import ESignatureAuditEvent, ESignatureRequest, User, UserRole
from app.schemas.esign import ESignComplete, ESignRequestCreate, ESignRequestResponse
from app.services.audit import add_audit_log

router = APIRouter(prefix="/esign-orch", tags=["Nitelikli E-İmza Orkestrasyon"])

# Menü company_admin'de değil; API erişimi saha + GA (mevcut belge onay ile uyumlu çekirdek)
VIEW = (
    UserRole.GLOBAL_ADMIN,
    UserRole.SAFETY_SPECIALIST,
    UserRole.WORKPLACE_PHYSICIAN,
)
EDIT = (UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST, UserRole.WORKPLACE_PHYSICIAN)

AGENT_BASE = "https://127.0.0.1:17000"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _event(
    db: Session,
    row: ESignatureRequest,
    user: User | None,
    event_type: str,
    detail: dict | None = None,
) -> None:
    payload = json.dumps(detail or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    stamp = datetime.utcnow().isoformat(timespec="microseconds")
    event_hash = _sha(f"{row.id}|{row.company_id}|{event_type}|{stamp}|{payload}|{user.id if user else ''}")
    db.add(
        ESignatureAuditEvent(
            request_id=row.id,
            company_id=row.company_id,
            event_type=event_type,
            actor_user_id=user.id if user else None,
            event_hash=event_hash,
            detail_json=payload,
        )
    )


@router.get("/meta")
def meta(user: User = Depends(get_current_user)):
    return {
        "engine": "osgb-esign-orchestrator-v1",
        "agent_url": AGENT_BASE,
        "formats": ["PAdES", "XAdES", "CAdES"],
        "recommended": "PAdES-B-LT/LTA",
        "security": [
            "single-use nonce",
            "SHA-256 document lock",
            "no PIN/private-key storage",
            "certificate/revocation/timestamp evidence",
        ],
        "legal_notice": (
            "Basit uygulama onayı nitelikli elektronik imza değildir. "
            "Gerçek imza, yetkili ESHS sertifikası ve doğrulanmış agent adaptörü gerektirir."
        ),
        "local_agent_pipeline": "/api/v1/esign",
        "note": "Bu uç orkestrasyon kaydıdır; PDF PAdES için mevcut /esign + OSGB Signer (17000) kullanılır.",
    }


@router.get("/requests", response_model=list[ESignRequestResponse])
def list_requests(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW)),
):
    stmt = select(ESignatureRequest).where(ESignatureRequest.is_active.is_(True)).order_by(ESignatureRequest.id.desc())
    ids = company_ids_for_query(db, user, company_id)
    if ids == []:
        return []
    if ids is not None:
        stmt = stmt.where(ESignatureRequest.company_id.in_(ids))
    return list(db.scalars(stmt.limit(1000)).all())


@router.post("/requests", response_model=ESignRequestResponse)
def create_request(
    payload: ESignRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT)),
):
    ensure_company_access(db, user, payload.company_id)
    row = ESignatureRequest(**payload.model_dump(), created_by_id=user.id, status="ready")
    db.add(row)
    db.flush()
    _event(db, row, user, "request_created", {"document_sha256": row.document_sha256, "format": row.signing_format})
    add_audit_log(
        db,
        user=user,
        action="create",
        entity_type="e_signature_request",
        entity_id=str(row.id),
        module="esign_orch",
        description=f"E-imza talebi oluşturuldu: {row.document_title}",
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(row)
    return row


@router.post("/requests/{request_id}/token")
def issue_token(
    request_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT)),
):
    row = db.get(ESignatureRequest, request_id)
    if not row or not row.is_active:
        raise HTTPException(404, "İmza talebi bulunamadı.")
    ensure_company_access(db, user, row.company_id)
    if row.status in {"signed", "verified"}:
        raise HTTPException(409, "Bu belge zaten imzalanmış.")
    nonce = secrets.token_urlsafe(48)
    row.nonce_hash = _sha(nonce)
    row.nonce_expires_at = datetime.utcnow() + timedelta(minutes=5)
    row.status = "token_issued"
    row.updated_at = datetime.utcnow()
    _event(db, row, user, "single_use_token_issued", {"expires_at": row.nonce_expires_at.isoformat()})
    db.commit()
    return {
        "request_id": row.id,
        "nonce": nonce,
        "expires_at": row.nonce_expires_at,
        "agent_url": f"{AGENT_BASE}/v1/sign",
        "agent_health": f"{AGENT_BASE}/health",
        "document_sha256": row.document_sha256,
        "signing_format": row.signing_format,
        "document_title": row.document_title,
    }


@router.post("/requests/{request_id}/complete", response_model=ESignRequestResponse)
def complete(
    request_id: int,
    payload: ESignComplete,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT)),
):
    row = db.get(ESignatureRequest, request_id)
    if not row or not row.is_active:
        raise HTTPException(404, "İmza talebi bulunamadı.")
    ensure_company_access(db, user, row.company_id)
    now = datetime.utcnow()
    if not row.nonce_hash or not row.nonce_expires_at or row.nonce_expires_at < now:
        raise HTTPException(409, "Tek kullanımlık imza anahtarının süresi dolmuş.")
    if not secrets.compare_digest(row.nonce_hash, _sha(payload.nonce)):
        _event(db, row, user, "nonce_rejected")
        db.commit()
        raise HTTPException(403, "İmza anahtarı geçersiz.")
    if payload.document_sha256.lower() != row.document_sha256.lower():
        _event(db, row, user, "document_hash_mismatch", {"received": payload.document_sha256})
        db.commit()
        raise HTTPException(409, "İmzalanan belge özeti kilitli belgeyle eşleşmiyor.")
    row.signature_value = payload.signature_value
    row.signed_document_sha256 = payload.signed_document_sha256.lower()
    row.certificate_subject = payload.certificate_subject
    row.certificate_serial = payload.certificate_serial
    row.certificate_issuer = payload.certificate_issuer
    row.certificate_valid_from = payload.certificate_valid_from
    row.certificate_valid_to = payload.certificate_valid_to
    row.certificate_qualified = payload.certificate_qualified
    row.revocation_status = payload.revocation_status
    row.timestamp_status = payload.timestamp_status
    row.signed_at = now
    row.status = "signed"
    row.nonce_hash = None
    row.nonce_expires_at = None
    row.updated_at = now
    qualified_ok = payload.certificate_qualified is True
    revocation_ok = (payload.revocation_status or "").lower() in {"good", "valid", "ok"}
    row.verification_status = "verified" if qualified_ok and revocation_ok else "needs_review"
    _event(
        db,
        row,
        user,
        "signature_completed",
        {"certificate_serial": payload.certificate_serial, "verification": row.verification_status},
    )
    add_audit_log(
        db,
        user=user,
        action="sign",
        entity_type="e_signature_request",
        entity_id=str(row.id),
        module="esign_orch",
        description=f"Belge e-imza sonucu alındı: {row.document_title}",
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(row)
    return row


@router.post("/requests/{request_id}/verify", response_model=ESignRequestResponse)
def verify(
    request_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW)),
):
    row = db.get(ESignatureRequest, request_id)
    if not row or not row.is_active:
        raise HTTPException(404, "İmza talebi bulunamadı.")
    ensure_company_access(db, user, row.company_id)
    if not row.signature_value:
        raise HTTPException(409, "Henüz imza verisi yok.")
    if row.certificate_valid_to and row.signed_at and row.signed_at > row.certificate_valid_to:
        row.verification_status = "certificate_expired_at_signing"
    elif row.certificate_qualified is not True:
        row.verification_status = "not_qualified"
    elif (row.revocation_status or "").lower() not in {"good", "valid", "ok"}:
        row.verification_status = "revocation_check_failed"
    else:
        row.verification_status = "verified"
        row.status = "verified"
    row.updated_at = datetime.utcnow()
    _event(db, row, user, "verification_run", {"result": row.verification_status})
    db.commit()
    db.refresh(row)
    return row
