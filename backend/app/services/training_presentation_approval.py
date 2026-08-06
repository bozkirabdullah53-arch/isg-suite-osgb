"""Hash-locked approval and archive workflow for presentation versions."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import nace_training_presentation_active
from app.models.entities import ESignatureRequest, User
from app.models.training_presentation import TrainingPresentationVersion
from app.models.training_presentation_approval import TrainingPresentationApproval

APPLICATION_APPROVAL_NOTICE = (
    "Bu kayıt uygulama içi uzman onayıdır; 5070 sayılı Kanun kapsamında "
    "nitelikli elektronik imza yerine geçmez."
)
QUALIFIED_ESIGN_NOTICE = (
    "Bu onay, mevcut e-imza orkestrasyonunda doğrulanmış PAdES talebinin "
    "sunum PDF hash'iyle eşleştirilmesiyle oluşturulmuştur."
)
APPROVAL_METHODS = frozenset({"application_approval", "qualified_esign"})
APPROVAL_ROLES = frozenset({"global_admin", "company_admin", "safety_specialist"})


class PresentationApprovalError(ValueError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _enum_value(value: object) -> str:
    """Normalize SQLAlchemy enum instances and plain strings consistently."""
    return str(getattr(value, "value", value) or "").strip()


def _role_value(user: User) -> str:
    return _enum_value(getattr(user, "role", ""))


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _event_hash(
    *,
    row: TrainingPresentationVersion,
    user: User,
    method: str,
    created_at: datetime,
    esign_request_id: int | None,
) -> str:
    raw = "|".join(
        [
            str(row.id),
            str(row.training_id),
            str(row.company_id),
            str(row.version),
            str(row.manifest_hash),
            str(row.pptx_file_hash),
            str(row.pdf_file_hash),
            str(getattr(user, "id", "")),
            method,
            str(esign_request_id or ""),
            created_at.isoformat(timespec="microseconds"),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _existing_approval(
    db: Session,
    row: TrainingPresentationVersion,
) -> TrainingPresentationApproval | None:
    return db.scalar(
        select(TrainingPresentationApproval).where(
            TrainingPresentationApproval.presentation_version_id == row.id
        )
    )


def _validate_ready_version(row: TrainingPresentationVersion) -> None:
    if _enum_value(row.status).lower() != "generated":
        raise PresentationApprovalError(
            "invalid_version_status",
            f"Yalnız dosyaları hazırlanmış sürüm onaylanabilir; mevcut durum: {_enum_value(row.status)}.",
        )
    hashes = {
        "manifest": str(row.manifest_hash or ""),
        "pptx": str(row.pptx_file_hash or ""),
        "pdf": str(row.pdf_file_hash or ""),
    }
    invalid = [name for name, value in hashes.items() if len(value) != 64]
    if invalid or not row.pptx_storage_key or not row.pdf_storage_key:
        raise PresentationApprovalError(
            "outputs_not_ready",
            "Onay için manifest, PPTX ve PDF dosyaları ile SHA-256 kayıtları hazır olmalıdır.",
        )


def _qualified_esign_evidence(
    db: Session,
    *,
    row: TrainingPresentationVersion,
    request_id: int | None,
) -> tuple[ESignatureRequest, dict[str, Any]]:
    if not request_id:
        raise PresentationApprovalError(
            "esign_request_required",
            "Nitelikli e-imza onayı için doğrulanmış e-imza talebi zorunludur.",
        )
    request = db.get(ESignatureRequest, request_id)
    if not request or not bool(getattr(request, "is_active", True)):
        raise PresentationApprovalError("esign_request_missing", "E-imza talebi bulunamadı.")
    if int(request.company_id) != int(row.company_id):
        raise PresentationApprovalError(
            "esign_company_mismatch",
            "E-imza talebi farklı bir şirkete aittir.",
        )
    status = _enum_value(request.status).lower()
    verification_status = _enum_value(request.verification_status).lower()
    signing_format = _enum_value(request.signing_format).upper()
    revocation_status = _enum_value(request.revocation_status).lower()
    if status != "verified" or verification_status != "verified":
        raise PresentationApprovalError(
            "esign_not_verified",
            "E-imza talebi henüz nitelikli ve doğrulanmış durumda değildir.",
        )
    if signing_format != "PADES":
        raise PresentationApprovalError(
            "esign_format_mismatch",
            "Sunum PDF onayı için PAdES e-imza talebi gereklidir.",
        )
    if str(request.document_sha256 or "").lower() != str(row.pdf_file_hash or "").lower():
        raise PresentationApprovalError(
            "esign_document_hash_mismatch",
            "E-imza talebindeki kilitli belge hash'i sunum PDF hash'iyle eşleşmiyor.",
        )
    if not request.signed_document_sha256:
        raise PresentationApprovalError(
            "esign_signed_hash_missing",
            "Doğrulanmış imzalı belge hash'i bulunmuyor.",
        )
    if request.certificate_qualified is not True:
        raise PresentationApprovalError(
            "esign_not_qualified",
            "E-imza sertifikası nitelikli olarak doğrulanmamış.",
        )
    if revocation_status not in {"good", "valid", "ok"}:
        raise PresentationApprovalError(
            "esign_revocation_invalid",
            "E-imza iptal/geçerlilik kontrolü başarılı değil.",
        )
    evidence = {
        "request_id": request.id,
        "status": status,
        "verification_status": verification_status,
        "signing_format": signing_format,
        "document_sha256": request.document_sha256,
        "signed_document_sha256": request.signed_document_sha256,
        "certificate_subject": request.certificate_subject,
        "certificate_serial": request.certificate_serial,
        "certificate_issuer": request.certificate_issuer,
        "certificate_qualified": request.certificate_qualified,
        "revocation_status": revocation_status,
        "timestamp_status": _enum_value(request.timestamp_status) or None,
        "signed_at": request.signed_at.isoformat() if request.signed_at else None,
    }
    return request, evidence


def approve_presentation_version(
    db: Session,
    *,
    row: TrainingPresentationVersion,
    user: User,
    method: str,
    confirmed_manifest_hash: str,
    note: str | None = None,
    esign_request_id: int | None = None,
) -> TrainingPresentationApproval:
    """Create one immutable approval and lock the generated version."""
    if not nace_training_presentation_active(getattr(row, "company_id", None)):
        raise PresentationApprovalError(
            "pilot_access_denied",
            "NACE eğitim sunumu onayı bu şirket için kontrollü pilot erişimine açık değildir.",
        )
    role = _role_value(user)
    if role not in APPROVAL_ROLES:
        raise PresentationApprovalError(
            "approval_role_forbidden",
            "Bu rol sunum onayı veremez.",
        )
    clean_method = str(method or "").strip().lower()
    if clean_method not in APPROVAL_METHODS:
        raise PresentationApprovalError("invalid_approval_method", "Geçersiz sunum onay yöntemi.")
    _validate_ready_version(row)
    if str(confirmed_manifest_hash or "").lower() != str(row.manifest_hash or "").lower():
        raise PresentationApprovalError(
            "manifest_confirmation_mismatch",
            "Onaylanan manifest hash'i mevcut sunum sürümüyle eşleşmiyor.",
        )
    if _existing_approval(db, row):
        raise PresentationApprovalError(
            "already_approved",
            "Bu sunum sürümü için değişmez onay kaydı zaten bulunuyor.",
        )

    request: ESignatureRequest | None = None
    evidence: dict[str, Any] | None = None
    legal_notice = APPLICATION_APPROVAL_NOTICE
    if clean_method == "qualified_esign":
        request, evidence = _qualified_esign_evidence(
            db,
            row=row,
            request_id=esign_request_id,
        )
        legal_notice = QUALIFIED_ESIGN_NOTICE
    elif esign_request_id is not None:
        raise PresentationApprovalError(
            "unexpected_esign_request",
            "Uygulama onayında e-imza talebi gönderilmemelidir.",
        )

    created_at = datetime.utcnow()
    approval = TrainingPresentationApproval(
        presentation_version_id=int(row.id),
        training_id=int(row.training_id),
        company_id=int(row.company_id),
        branch_id=row.branch_id,
        approval_method=clean_method,
        manifest_hash=str(row.manifest_hash),
        pptx_file_hash=str(row.pptx_file_hash),
        pdf_file_hash=str(row.pdf_file_hash),
        approver_user_id=getattr(user, "id", None),
        approver_name=str(getattr(user, "full_name", None) or getattr(user, "email", None) or "Yetkili kullanıcı"),
        approver_role=role,
        approval_note=(str(note).strip()[:2000] if note else None),
        esign_request_id=request.id if request else None,
        esign_document_hash=request.document_sha256 if request else None,
        esign_signed_document_hash=request.signed_document_sha256 if request else None,
        esign_verification_status=_enum_value(request.verification_status) if request else None,
        esign_certificate_serial=request.certificate_serial if request else None,
        esign_evidence_json=_canonical_json(evidence) if evidence else None,
        legal_notice=legal_notice,
        event_hash=_event_hash(
            row=row,
            user=user,
            method=clean_method,
            created_at=created_at,
            esign_request_id=request.id if request else None,
        ),
        created_at=created_at,
    )
    row.status = "approved"
    row.approved_by_id = getattr(user, "id", None)
    row.approved_at = created_at
    row.updated_at = created_at
    db.add(approval)
    db.flush()
    return approval


def archive_presentation_version(
    db: Session,
    *,
    row: TrainingPresentationVersion,
    user: User,
) -> TrainingPresentationVersion:
    if not nace_training_presentation_active(getattr(row, "company_id", None)):
        raise PresentationApprovalError(
            "pilot_access_denied",
            "NACE eğitim sunumu arşivleme işlemi bu şirket için açık değildir.",
        )
    if _role_value(user) not in APPROVAL_ROLES:
        raise PresentationApprovalError("archive_role_forbidden", "Bu rol sunumu arşivleyemez.")
    if _enum_value(row.status).lower() != "approved" or not _existing_approval(db, row):
        raise PresentationApprovalError(
            "approval_required",
            "Yalnız değişmez onay kaydı bulunan onaylı sürüm arşivlenebilir.",
        )
    row.status = "archived"
    row.archived_at = datetime.utcnow()
    row.updated_at = row.archived_at
    db.flush()
    return row


def approval_payload(row: TrainingPresentationApproval) -> dict[str, Any]:
    try:
        evidence = json.loads(row.esign_evidence_json or "null")
    except (TypeError, json.JSONDecodeError):
        evidence = None
    return {
        "id": row.id,
        "presentation_version_id": row.presentation_version_id,
        "training_id": row.training_id,
        "company_id": row.company_id,
        "branch_id": row.branch_id,
        "approval_method": row.approval_method,
        "hashes": {
            "manifest": row.manifest_hash,
            "pptx": row.pptx_file_hash,
            "pdf": row.pdf_file_hash,
        },
        "approver": {
            "user_id": row.approver_user_id,
            "name": row.approver_name,
            "role": row.approver_role,
        },
        "approval_note": row.approval_note,
        "esign_request_id": row.esign_request_id,
        "esign_evidence": evidence,
        "legal_notice": row.legal_notice,
        "event_hash": row.event_hash,
        "created_at": row.created_at,
        "immutable": True,
    }


def get_presentation_approval(
    db: Session,
    *,
    presentation_version_id: int,
) -> TrainingPresentationApproval | None:
    return db.scalar(
        select(TrainingPresentationApproval).where(
            TrainingPresentationApproval.presentation_version_id == presentation_version_id
        )
    )
