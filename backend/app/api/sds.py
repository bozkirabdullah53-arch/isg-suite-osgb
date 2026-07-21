"""0.9.119 — SDS/PKD kimyasal ürün sicili (saha uzmanı MVP)."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.company_access import company_ids_for_query, ensure_company_access
from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import (
    ChemicalProduct,
    DocumentCategory,
    DocumentRecord,
    User,
    UserRole,
)
from app.schemas.sds import (
    ChemicalProductCreate,
    ChemicalProductResponse,
    ChemicalProductUpdate,
    SdsDueSummary,
)

router = APIRouter(prefix="/sds", tags=["SDS / PKD"])

EDIT_ROLES = (
    UserRole.GLOBAL_ADMIN,
    UserRole.SAFETY_SPECIALIST,
)
VIEW_ROLES = (
    UserRole.GLOBAL_ADMIN,
    UserRole.SAFETY_SPECIALIST,
    UserRole.WORKPLACE_PHYSICIAN,
    UserRole.OTHER_HEALTH_PERSONNEL,
)

REGISTER_ENGINE = "chemical-register-v1"


def _review_status(next_review: date | None) -> str:
    if not next_review:
        return "unset"
    today = date.today()
    if next_review < today:
        return "overdue"
    if next_review <= today + timedelta(days=30):
        return "due_soon"
    return "ok"


def _to_response(row: ChemicalProduct) -> ChemicalProductResponse:
    return ChemicalProductResponse(
        id=row.id,
        company_id=row.company_id,
        branch_id=row.branch_id,
        product_name=row.product_name,
        cas_number=row.cas_number,
        has_sds_file=bool(row.has_sds_file),
        document_id=row.document_id,
        next_review_date=row.next_review_date,
        notes=row.notes,
        is_active=bool(row.is_active),
        created_by_id=row.created_by_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        review_status=_review_status(row.next_review_date),
    )


def _ensure_edit(db: Session, user: User, company_id: int) -> None:
    ensure_company_access(db, user, company_id)


@router.get("/meta")
def sds_meta(user: User = Depends(get_current_user)):
    return {
        "engine": REGISTER_ENGINE,
        "version_feature": "0.9.119",
        "fields": ["product_name", "cas_number", "has_sds_file", "next_review_date", "document_id"],
        "note": "SDS dosyası Dokümanlar kaydı üzerinden yüklenir; sicil kaydı belgeye bağlanır.",
    }


@router.get("/due-summary", response_model=SdsDueSummary)
def due_summary(
    company_id: int | None = None,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    company_ids = company_ids_for_query(db, user, company_id)
    if company_ids == []:
        return SdsDueSummary(total=0, with_sds=0, missing_sds=0, due_soon=0, overdue=0)

    q = select(ChemicalProduct).where(ChemicalProduct.is_active.is_(True))
    if company_ids is not None:
        q = q.where(ChemicalProduct.company_id.in_(company_ids))
    rows = list(db.scalars(q).all())
    today = date.today()
    soon = today + timedelta(days=days)
    with_sds = sum(1 for r in rows if r.has_sds_file)
    return SdsDueSummary(
        total=len(rows),
        with_sds=with_sds,
        missing_sds=len(rows) - with_sds,
        due_soon=sum(
            1
            for r in rows
            if r.next_review_date and today <= r.next_review_date <= soon
        ),
        overdue=sum(1 for r in rows if r.next_review_date and r.next_review_date < today),
    )


@router.get("", response_model=list[ChemicalProductResponse])
def list_products(
    company_id: int | None = None,
    q: str | None = Query(default=None, max_length=100),
    active_only: bool = True,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    stmt = select(ChemicalProduct).order_by(ChemicalProduct.product_name.asc())
    company_ids = company_ids_for_query(db, user, company_id)
    if company_ids == []:
        return []
    if company_ids is not None:
        stmt = stmt.where(ChemicalProduct.company_id.in_(company_ids))
    if active_only:
        stmt = stmt.where(ChemicalProduct.is_active.is_(True))
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                ChemicalProduct.product_name.ilike(pattern),
                ChemicalProduct.cas_number.ilike(pattern),
                ChemicalProduct.notes.ilike(pattern),
            )
        )
    return [_to_response(r) for r in db.scalars(stmt).all()]


@router.post("", response_model=ChemicalProductResponse)
def create_product(
    payload: ChemicalProductCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    _ensure_edit(db, user, payload.company_id)
    now = datetime.utcnow()
    row = ChemicalProduct(
        company_id=payload.company_id,
        branch_id=payload.branch_id,
        product_name=payload.product_name,
        cas_number=payload.cas_number,
        has_sds_file=payload.has_sds_file,
        next_review_date=payload.next_review_date,
        notes=payload.notes,
        is_active=True,
        created_by_id=user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_response(row)


@router.patch("/{product_id}", response_model=ChemicalProductResponse)
def update_product(
    product_id: int,
    payload: ChemicalProductUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = db.get(ChemicalProduct, product_id)
    if not row:
        raise HTTPException(404, "Kimyasal ürün bulunamadı.")
    _ensure_edit(db, user, row.company_id)
    data = payload.model_dump(exclude_unset=True)
    for key, val in data.items():
        setattr(row, key, val)
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _to_response(row)


@router.post("/{product_id}/ensure-document", response_model=ChemicalProductResponse)
def ensure_sds_document(
    product_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    """Dokümanlar modülüne SDS kaydı oluşturur / bağlar (dosya yükleme için)."""
    row = db.get(ChemicalProduct, product_id)
    if not row:
        raise HTTPException(404, "Kimyasal ürün bulunamadı.")
    _ensure_edit(db, user, row.company_id)

    if row.document_id:
        doc = db.get(DocumentRecord, row.document_id)
        if doc and doc.is_active:
            return _to_response(row)

    title = f"SDS — {row.product_name}"
    if row.cas_number:
        title = f"{title} (CAS {row.cas_number})"
    desc = "PKD/SDS kimyasal ürün sicilinden oluşturuldu."
    if row.notes:
        desc = f"{desc}\n{row.notes}"[:1500]

    doc = DocumentRecord(
        company_id=row.company_id,
        branch_id=row.branch_id,
        category=DocumentCategory.LEGAL,
        title=title[:220],
        file_name=None,
        description=desc,
        valid_from=date.today(),
        valid_until=row.next_review_date,
        version="1.0",
        is_active=True,
        created_by_id=user.id,
    )
    db.add(doc)
    db.flush()
    row.document_id = doc.id
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _to_response(row)


@router.post("/{product_id}/mark-sds-uploaded", response_model=ChemicalProductResponse)
def mark_sds_uploaded(
    product_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    """Doküman dosyası yüklendikten sonra has_sds_file bayrağını günceller."""
    row = db.get(ChemicalProduct, product_id)
    if not row:
        raise HTTPException(404, "Kimyasal ürün bulunamadı.")
    _ensure_edit(db, user, row.company_id)
    if not row.document_id:
        raise HTTPException(400, "Önce SDS doküman kaydı oluşturun.")
    doc = db.get(DocumentRecord, row.document_id)
    if not doc:
        raise HTTPException(404, "Bağlı doküman bulunamadı.")
    has_file = bool(doc.file_name) or ("[stored:" in (doc.description or ""))
    if not has_file:
        raise HTTPException(400, "Dokümana henüz dosya yüklenmemiş.")
    row.has_sds_file = True
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _to_response(row)
