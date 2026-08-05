"""İBYS entegratör başvuru demosu için sözleşmeden bağımsız doğrulama API'si."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import require_roles
from app.core.version import APP_VERSION
from app.models.entities import User, UserRole
from app.services.ibys_application_evidence import (
    assess_verified_application_preflight,
    validate_evidence_ledger,
)
from app.services.ibys_application_preflight import assess_application_preflight
from app.services.ibys_application_profile import (
    application_profile_readiness,
    build_application_mapping_matrix,
    build_submission_envelope,
    validate_candidate_records,
)

router = APIRouter(prefix="/ibys-application", tags=["İBYS Başvuru Hazırlığı"])
ADMIN_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)


class CandidateRecordsRequest(BaseModel):
    records: list[dict[str, Any]] = Field(default_factory=list, max_length=1000)


class CandidateEnvelopeRequest(CandidateRecordsRequest):
    osgb_id: int | None = Field(default=None, ge=1)


class ApplicationPreflightRequest(BaseModel):
    company_profile: dict[str, Any] = Field(default_factory=dict)
    attachment_filenames: list[str] = Field(default_factory=list, max_length=20)
    legal_kvkk_approved: bool = False
    external_authorization_smoke_completed: bool = False
    application_letter_signed: bool = False
    appointment_package_approved: bool = False


class EvidenceValidationRequest(BaseModel):
    evidence_ledger: dict[str, Any] = Field(default_factory=dict)


class VerifiedApplicationPreflightRequest(EvidenceValidationRequest):
    company_profile: dict[str, Any] = Field(default_factory=dict)


def _scoped_osgb_id(user: User, requested: int | None) -> int | None:
    if user.role == UserRole.COMPANY_ADMIN:
        if not user.osgb_id:
            raise HTTPException(400, "Kullanıcıya bağlı OSGB bulunamadı.")
        if requested is not None and requested != user.osgb_id:
            raise HTTPException(403, "Yalnız kendi OSGB kapsamınız için başvuru paketi üretebilirsiniz.")
        return user.osgb_id
    return requested


@router.get("/profile")
def ibys_application_profile(
    _: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """Aday veri-seti/alan eşleme matrisi; resmî uygunluk iddiası içermez."""
    return build_application_mapping_matrix()


@router.get("/readiness")
def ibys_application_readiness(
    _: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """Teknik başvuru profilinin ve resmî sözleşme kapısının ayrı durumunu döndürür."""
    return application_profile_readiness()


@router.post("/preflight")
def ibys_application_preflight(
    payload: ApplicationPreflightRequest,
    _: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """Şirket profili, belge adları ve beyan kapılarıyla ön kontrol raporu üretir."""
    return assess_application_preflight(
        payload.company_profile,
        attachment_filenames=payload.attachment_filenames,
        legal_kvkk_approved=payload.legal_kvkk_approved,
        external_authorization_smoke_completed=payload.external_authorization_smoke_completed,
        application_letter_signed=payload.application_letter_signed,
        appointment_package_approved=payload.appointment_package_approved,
    )


@router.post("/evidence/validate")
def ibys_application_evidence_validate(
    payload: EvidenceValidationRequest,
    _: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """Kanıt defterini SHA-256, tarih, doğrulayan ve hassas veri sınırlarıyla doğrular."""
    return validate_evidence_ledger(payload.evidence_ledger)


@router.post("/preflight/verified")
def ibys_application_verified_preflight(
    payload: VerifiedApplicationPreflightRequest,
    _: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """Puanı beyanlardan değil doğrulanmış kanıt defterinden türeten katı ön kontrol."""
    return assess_verified_application_preflight(
        payload.company_profile,
        payload.evidence_ledger,
    )


@router.post("/validate/{dataset_code}")
def ibys_application_validate(
    dataset_code: str,
    payload: CandidateRecordsRequest,
    _: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """Kayıt içeriklerini loglamadan zorunlu alan ve fingerprint raporu üretir."""
    try:
        return validate_candidate_records(dataset_code.strip().lower(), payload.records)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/envelope/{dataset_code}")
def ibys_application_envelope(
    dataset_code: str,
    payload: CandidateEnvelopeRequest,
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """İdempotency anahtarlı aday gönderim zarfı üretir; harici HTTP çağrısı yapmaz."""
    osgb_id = _scoped_osgb_id(user, payload.osgb_id)
    try:
        return build_submission_envelope(
            dataset_code.strip().lower(),
            payload.records,
            osgb_id=osgb_id,
            source_system_version=APP_VERSION,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
