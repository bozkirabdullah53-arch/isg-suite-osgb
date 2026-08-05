"""İBYS entegratör başvuru demosu için sözleşmeden bağımsız doğrulama API'si."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import require_roles
from app.core.version import APP_VERSION
from app.models.entities import User, UserRole
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
