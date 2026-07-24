"""Legal document versions and acceptance API (P1-12).

Aydınlatma ile açık rıza ayrı document_key; kabul kaydı immutable.
Metin içeriği hukuk onayı sonrası güncellenir — burada yalnızca sürüm anahtarları.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.entities import LegalAcceptance, User

router = APIRouter(prefix="/legal", tags=["Hukuki Onaylar"])

# Sabit kayıt: key → sürüm + hukuki dayanak (metin CMS/hukuk paketi ayrıca)
LEGAL_DOCUMENTS: dict[str, dict[str, str]] = {
    "privacy_notice": {
        "title": "Aydınlatma Metni",
        "version": "2026-07-01",
        "legal_basis": "kvkk_art_10",
        "summary": "Kişisel verilerin işlenmesine ilişkin bilgilendirme (açık rıza yerine geçmez).",
    },
    "explicit_consent_health": {
        "title": "Sağlık Verisi Açık Rıza",
        "version": "2026-07-01",
        "legal_basis": "explicit_consent",
        "summary": "Özel nitelikli sağlık verisi işleme için ayrı açık rıza.",
    },
    "terms_of_use": {
        "title": "Kullanım Koşulları",
        "version": "2026-07-01",
        "legal_basis": "contract",
        "summary": "Platform kullanım şartları.",
    },
}


class LegalDocumentOut(BaseModel):
    key: str
    title: str
    version: str
    legal_basis: str
    summary: str
    accepted: bool = False
    accepted_at: datetime | None = None


class AcceptRequest(BaseModel):
    document_key: str = Field(min_length=2, max_length=80)
    document_version: str | None = Field(default=None, max_length=40)


class AcceptanceOut(BaseModel):
    id: int
    document_key: str
    document_version: str
    legal_basis: str
    accepted_at: datetime

    model_config = ConfigDict(from_attributes=True)


def _client_ip(request: Request) -> str | None:
    xff = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if xff:
        return xff[:64]
    if request.client:
        return (request.client.host or "")[:64] or None
    return None


@router.get("/documents", response_model=list[LegalDocumentOut])
def list_legal_documents(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.scalars(
        select(LegalAcceptance).where(LegalAcceptance.user_id == user.id)
    ).all()
    by_key = {(r.document_key, r.document_version): r for r in rows}
    out: list[LegalDocumentOut] = []
    for key, meta in LEGAL_DOCUMENTS.items():
        ver = meta["version"]
        hit = by_key.get((key, ver))
        out.append(
            LegalDocumentOut(
                key=key,
                title=meta["title"],
                version=ver,
                legal_basis=meta["legal_basis"],
                summary=meta["summary"],
                accepted=hit is not None,
                accepted_at=hit.accepted_at if hit else None,
            )
        )
    return out


@router.post("/accept", response_model=AcceptanceOut)
def accept_legal_document(
    payload: AcceptRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    meta = LEGAL_DOCUMENTS.get(payload.document_key)
    if not meta:
        raise HTTPException(404, "Hukuki belge bulunamadı.")
    version = (payload.document_version or meta["version"]).strip()
    if version != meta["version"]:
        raise HTTPException(
            409,
            f"Belge sürümü güncel değil. Güncel sürüm: {meta['version']}",
        )

    existing = db.scalar(
        select(LegalAcceptance).where(
            LegalAcceptance.user_id == user.id,
            LegalAcceptance.document_key == payload.document_key,
            LegalAcceptance.document_version == version,
        )
    )
    if existing:
        return existing

    row = LegalAcceptance(
        user_id=user.id,
        osgb_id=user.osgb_id,
        company_id=user.company_id,
        document_key=payload.document_key,
        document_version=version,
        legal_basis=meta["legal_basis"],
        ip_address=_client_ip(request),
        user_agent=(request.headers.get("user-agent") or "")[:400] or None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/me", response_model=list[AcceptanceOut])
def my_acceptances(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return list(
        db.scalars(
            select(LegalAcceptance)
            .where(LegalAcceptance.user_id == user.id)
            .order_by(LegalAcceptance.accepted_at.desc())
        ).all()
    )
