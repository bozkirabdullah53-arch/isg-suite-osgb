"""Legal document catalog + acceptance (P1-12 CMS)."""
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

LEGAL_DOCUMENTS: dict[str, dict[str, str]] = {
    "privacy_notice": {
        "title": "Aydınlatma Metni",
        "version": "2026-07-24",
        "legal_basis": "kvkk_art_10",
        "summary": "Kişisel verilerin işlenmesine ilişkin bilgilendirme (açık rıza yerine geçmez).",
        "body": (
            "İSG Suite, OSGB ve işyeri süreçlerinde kimlik, iletişim ve operasyon verilerinizi "
            "KVKK md.5/6 kapsamında hizmet sözleşmesi ve meşru menfaat hukuki dayanaklarıyla işler. "
            "Bu metin bilgilendirme amaçlıdır; özel nitelikli veri için ayrıca açık rıza alınır. "
            "Haklarınız: erişim, düzeltme, silme, itiraz. İletişim: platform destek kanalları."
        ),
    },
    "explicit_consent_health": {
        "title": "Sağlık Verisi Açık Rıza",
        "version": "2026-07-24",
        "legal_basis": "explicit_consent",
        "summary": "Özel nitelikli sağlık verisi işleme için ayrı açık rıza.",
        "body": (
            "İşyeri hekimliği ve İSG süreçlerinde sağlık verilerinizin (muayene, tetkik, maruziyet) "
            "yetkili rollerce işlenmesine açık rıza veriyorum. Rızamı geri çekme hakkım saklıdır; "
            "geri çekme yasal saklama yükümlülüklerini ortadan kaldırmaz."
        ),
    },
    "terms_of_use": {
        "title": "Kullanım Koşulları",
        "version": "2026-07-24",
        "legal_basis": "contract",
        "summary": "Platform kullanım şartları.",
        "body": (
            "Platform bir SaaS hizmetidir; yasal İSG yükümlülükleri müşteri OSGB/işverenindedir. "
            "Hesap güvenliği, doğru veri girişi ve yetkisiz paylaşım yasağı kullanıcı sorumluluğundadır. "
            "Hizmet kesintileri, bakım ve güncellemeler makul ölçüde bildirilir."
        ),
    },
}


class LegalDocumentOut(BaseModel):
    key: str
    title: str
    version: str
    legal_basis: str
    summary: str
    body: str | None = None
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
    rows = db.scalars(select(LegalAcceptance).where(LegalAcceptance.user_id == user.id)).all()
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
                body=meta.get("body"),
                accepted=hit is not None,
                accepted_at=hit.accepted_at if hit else None,
            )
        )
    return out


@router.get("/documents/{document_key}", response_model=LegalDocumentOut)
def get_legal_document(
    document_key: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    meta = LEGAL_DOCUMENTS.get(document_key)
    if not meta:
        raise HTTPException(404, "Hukuki belge bulunamadı.")
    hit = db.scalar(
        select(LegalAcceptance).where(
            LegalAcceptance.user_id == user.id,
            LegalAcceptance.document_key == document_key,
            LegalAcceptance.document_version == meta["version"],
        )
    )
    return LegalDocumentOut(
        key=document_key,
        title=meta["title"],
        version=meta["version"],
        legal_basis=meta["legal_basis"],
        summary=meta["summary"],
        body=meta.get("body"),
        accepted=hit is not None,
        accepted_at=hit.accepted_at if hit else None,
    )


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
        raise HTTPException(409, f"Belge sürümü güncel değil. Güncel sürüm: {meta['version']}")

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
