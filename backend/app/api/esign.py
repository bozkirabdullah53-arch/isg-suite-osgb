"""OSGB e-imza API — tek kullanımlık talep + sunucu doğrulama hattı.

Mevcut Belge Onay / PDF / canvas imza akışlarını bozmaz. Kurul toplantısı
imzaları ayrıca gerçek katılımcı, sıra ve belge sürümüne bağlanır.
"""
from __future__ import annotations

import base64
from datetime import date, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.company_access import company_ids_for_query, ensure_company_access
from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import DocumentApproval, ESignArtifact, ESignRequest, User, UserRole
from app.services import esign_pipeline as pipe
from app.services.committee_signature import authorize_completion, complete_signature_step

VIEW = (UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST, UserRole.WORKPLACE_PHYSICIAN)
EDIT = (UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST)

router = APIRouter(prefix="/esign", tags=["E-İmza"])


class ESignRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    company_id: int
    approval_id: int | None = None
    document_title: str
    document_kind: str
    source_sha256: str
    source_bytes: int
    one_time_token: str
    token_expires_at: datetime
    status: str
    created_at: datetime
    agent_hint: dict | None = None


class ESignArtifactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    company_id: int
    request_id: int
    approval_id: int | None = None
    signed_sha256: str
    signed_bytes: int
    signer_cn: str | None = None
    signer_subject: str | None = None
    cert_serial: str | None = None
    sign_mode: str | None = None
    verification_status: str
    ocsp_status: str | None = None
    crl_status: str | None = None
    timestamp_status: str | None = None
    is_locked: bool
    qualified_claim: bool
    locked_at: datetime | None = None
    created_at: datetime


class CompleteBody(BaseModel):
    one_time_token: str = Field(min_length=16, max_length=80)
    signed_pdf_base64: str = Field(min_length=16)
    agent_mode: str | None = Field(default=None, max_length=40)
    agent_signature_id: str | None = Field(default=None, max_length=64)
    signer_cn: str | None = None
    signer_subject: str | None = None
    cert_serial: str | None = None
    cert_sha256: str | None = None
    mark_approval: bool = True


def _role_value(user: User) -> str:
    return user.role.value if hasattr(user.role, "value") else str(user.role)


def _is_general_editor(user: User) -> bool:
    return _role_value(user) in {"global_admin", "safety_specialist"}


@router.get("/meta")
def esign_meta(user: User = Depends(require_roles(*VIEW))):
    return {
        "product": "OSGB Signer",
        "agent_port": pipe.AGENT_PORT,
        "agent_health": f"https://127.0.0.1:{pipe.AGENT_PORT}/health",
        "token_ttl_minutes": pipe.TOKEN_TTL_MINUTES,
        "max_pdf_mb": pipe.MAX_PDF_BYTES // (1024 * 1024),
        "origins_for_agent": pipe.AGENT_ORIGINS_HINT,
        "pipeline": [
            "one_time_request", "windows_agent_pkcs11", "verify", "ocsp",
            "crl", "timestamp", "document_lock", "audit",
        ],
        "ocsp_enabled": bool(__import__("app.core.config", fromlist=["settings"]).settings.esign_ocsp_enabled),
        "crl_enabled": bool(__import__("app.core.config", fromlist=["settings"]).settings.esign_crl_enabled),
        "tsa_configured": bool((__import__("app.core.config", fromlist=["settings"]).settings.esign_tsa_url or "").strip()),
        "note": "PIN yalnızca Windows agent üzerinde girilir; sunucuya gitmez.",
    }


@router.post("/requests", response_model=ESignRequestOut)
async def create_sign_request(
    company_id: int = Form(...),
    document_title: str = Form(...),
    document_kind: str = Form("genel"),
    approval_id: int | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT)),
):
    ensure_company_access(db, user, company_id)
    if approval_id:
        approval = db.get(DocumentApproval, approval_id)
        if not approval or approval.company_id != company_id:
            raise HTTPException(400, "Onay kaydı bulunamadı veya firma uyuşmuyor.")
    raw = await file.read()
    try:
        relative = pipe.store_esign_bytes(company_id, "source", raw)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    row = ESignRequest(
        company_id=company_id,
        approval_id=approval_id,
        document_title=(document_title or file.filename or "belge")[:220],
        document_kind=(document_kind or "genel")[:80],
        source_sha256=pipe.sha256_hex(raw),
        source_storage_path=relative,
        source_bytes=len(raw),
        one_time_token=pipe.new_one_time_token(),
        token_expires_at=pipe.token_expiry(),
        status="pending",
        created_by_id=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    output = ESignRequestOut.model_validate(row)
    output.agent_hint = {
        "port": pipe.AGENT_PORT,
        "sign_path": "/v1/sign",
        "pass_token_field": "request_token",
        "pass_sha256_field": "expected_sha256",
    }
    return output


@router.get("/requests", response_model=list[ESignRequestOut])
def list_requests(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW)),
):
    statement = select(ESignRequest).where(ESignRequest.is_active.is_(True)).order_by(ESignRequest.id.desc())
    ids = company_ids_for_query(db, user, company_id)
    if ids == []:
        return []
    if ids is not None:
        statement = statement.where(ESignRequest.company_id.in_(ids))
    rows = list(db.scalars(statement.limit(100)).all())
    return [ESignRequestOut.model_validate(row) for row in rows]


@router.get("/requests/by-token/{token}", response_model=ESignRequestOut)
def get_by_token(
    token: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.scalars(select(ESignRequest).where(ESignRequest.one_time_token == token)).first()
    if not row:
        raise HTTPException(404, "İmza talebi bulunamadı.")
    ensure_company_access(db, user, row.company_id)
    linked = authorize_completion(db, row, user)
    if not linked and not _is_general_editor(user):
        raise HTTPException(403, "Bu imza talebine erişim yetkiniz yok.")
    return ESignRequestOut.model_validate(row)


@router.post("/complete", response_model=ESignArtifactOut)
def complete_sign(
    payload: CompleteBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.scalars(
        select(ESignRequest).where(ESignRequest.one_time_token == payload.one_time_token)
    ).first()
    if not row:
        raise HTTPException(404, "Tek kullanımlık imza talebi geçersiz.")
    ensure_company_access(db, user, row.company_id)
    linked_committee_request = authorize_completion(db, row, user)
    if not linked_committee_request and not _is_general_editor(user):
        raise HTTPException(403, "Bu elektronik imza talebini tamamlama yetkiniz yok.")
    if row.status != "pending" or not row.is_active:
        raise HTTPException(409, f"Talep kullanılamaz (durum={row.status}).")
    if row.token_expires_at < datetime.utcnow():
        row.status = "expired"
        db.commit()
        raise HTTPException(410, "İmza talebinin süresi doldu. Yeni talep oluşturun.")
    existing = db.scalars(select(ESignArtifact).where(ESignArtifact.request_id == row.id)).first()
    if existing:
        raise HTTPException(409, "Bu talep zaten tamamlanmış.")
    try:
        signed = base64.b64decode(payload.signed_pdf_base64, validate=False)
        source = pipe.read_stored(row.source_storage_path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Dosya okunamadı: {exc}") from exc
    agent_meta = {
        "mode": payload.agent_mode,
        "signature_id": payload.agent_signature_id,
        "signer_cn": payload.signer_cn,
        "signer_subject": payload.signer_subject,
        "cert_serial": payload.cert_serial,
        "cert_sha256": payload.cert_sha256,
    }
    try:
        result = pipe.pipeline_complete(
            source_pdf=source,
            signed_pdf=signed,
            source_sha256=row.source_sha256,
            agent_meta=agent_meta,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if result["verification_status"] == "failed":
        raise HTTPException(422, f"İmza doğrulanamadı: {result.get('verify_detail')}")
    try:
        relative = pipe.store_esign_bytes(row.company_id, "signed", result["signed_pdf"])
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    now = datetime.utcnow()
    audit = pipe.build_audit_event(
        action="esign.complete",
        user_id=user.id,
        company_id=row.company_id,
        request_id=row.id,
        extra={
            "verification_status": result["verification_status"],
            "ocsp": result["ocsp_status"],
            "crl": result["crl_status"],
            "tsa": result["timestamp_status"],
            "locked": result["is_locked"],
            "sign_mode": result.get("sign_mode"),
            "verify_engine": result.get("verify_engine"),
        },
    )
    artifact = ESignArtifact(
        company_id=row.company_id,
        request_id=row.id,
        approval_id=row.approval_id,
        signed_sha256=result["signed_sha256"],
        signed_storage_path=relative,
        signed_bytes=len(result["signed_pdf"]),
        signer_cn=(result.get("signer_cn") or "")[:220] or None,
        signer_subject=(result.get("signer_subject") or "")[:500] or None,
        cert_serial=(result.get("cert_serial") or "")[:120] or None,
        cert_sha256=(result.get("cert_sha256") or "")[:64] or None,
        sign_mode=(result.get("sign_mode") or "")[:40] or None,
        agent_signature_id=(result.get("agent_signature_id") or "")[:64] or None,
        verification_status=result["verification_status"],
        ocsp_status=result["ocsp_status"],
        crl_status=result["crl_status"],
        timestamp_status=result["timestamp_status"],
        timestamp_token=result.get("timestamp_token"),
        locked_at=now if result["is_locked"] else None,
        is_locked=bool(result["is_locked"]),
        qualified_claim=bool(result["qualified_claim"]),
        audit_json=audit,
        created_by_id=user.id,
    )
    row.status = "consumed"
    row.consumed_at = now
    if payload.mark_approval and row.approval_id:
        approval = db.get(DocumentApproval, row.approval_id)
        if approval:
            approval.status = "Onaylandı"
            approval.approved_at = date.today()
            approval.signature_note = (
                f"OSGB Signer — {artifact.signer_cn or 'imzalayan'}; "
                f"doğrulama={artifact.verification_status}; OCSP={artifact.ocsp_status}; "
                f"CRL={artifact.crl_status}; TSA={artifact.timestamp_status}; "
                f"kilit={'evet' if artifact.is_locked else 'hayır'}; "
                f"SHA256={artifact.signed_sha256[:16]}…"
            )[:1000]
    db.add(artifact)
    db.flush()
    if linked_committee_request:
        complete_signature_step(
            db,
            request_id=row.id,
            artifact_id=artifact.id,
            user=user,
            signed_at=now,
        )
    db.commit()
    db.refresh(artifact)
    return artifact


@router.get("/artifacts", response_model=list[ESignArtifactOut])
def list_artifacts(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW)),
):
    statement = select(ESignArtifact).where(ESignArtifact.is_active.is_(True)).order_by(ESignArtifact.id.desc())
    ids = company_ids_for_query(db, user, company_id)
    if ids == []:
        return []
    if ids is not None:
        statement = statement.where(ESignArtifact.company_id.in_(ids))
    return list(db.scalars(statement.limit(100)).all())


@router.get("/artifacts/{artifact_id}/download")
def download_artifact(
    artifact_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW)),
):
    artifact = db.get(ESignArtifact, artifact_id)
    if not artifact:
        raise HTTPException(404, "Artefakt bulunamadı.")
    ensure_company_access(db, user, artifact.company_id)
    path = (pipe.upload_root() / artifact.signed_storage_path).resolve()
    if pipe.upload_root() not in path.parents or not path.exists():
        raise HTTPException(404, "Dosya bulunamadı.")
    return FileResponse(path, media_type="application/pdf", filename=f"imzali-{artifact.id}.pdf")
