"""FAZ E — PWA-only large-touch field actions; no native app or manifest changes."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
import re
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.api.company_access import ensure_company_access
from app.api.deps import require_roles
from app.api.work_permits import _audit as ptw_audit, _load as load_ptw, _payload as ptw_payload
from app.core.database import get_db
from app.models.entities import IncidentEvent, User, UserRole
from app.models.premium_field import FieldMobileEvidence
from app.models.work_permit import WorkPermit, WorkPermitControl
from app.services.object_store import get_object_store
from app.services.object_upload_commit import commit_object_upload
from app.services.stored_files import response_for_storage_key
from app.services.upload_security import assert_safe_upload

router = APIRouter(prefix="/field-mobile", tags=["PWA Saha Hızlı İşlem"])
FIELD_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST, UserRole.OTHER_HEALTH_PERSONNEL)
INCIDENT_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST)
ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024


class MobileCloseInput(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


def _safe_image(raw: bytes, filename: str) -> None:
    if not raw:
        raise HTTPException(422, "Fotoğraf boş.")
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Fotoğraf 8 MB sınırını aşıyor.")
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_IMAGE_EXT:
        raise HTTPException(422, "Saha kanıtı JPG, PNG veya WEBP olmalıdır.")
    assert_safe_upload(raw, extension, filename)
    try:
        from PIL import Image
        with Image.open(BytesIO(raw)) as image:
            image.verify()
    except Exception as exc:
        raise HTTPException(422, "Yüklenen dosya geçerli bir görüntü değil.") from exc


def _entity_scope(db: Session, user: User, entity_type: str, entity_id: int) -> int:
    if entity_type == "work_permit":
        return load_ptw(db, user, entity_id).company_id
    if entity_type == "incident":
        if user.role not in INCIDENT_ROLES:
            raise HTTPException(403, "Olay fotoğrafı yalnız yetkili saha uzmanı tarafından eklenebilir.")
        row = db.get(IncidentEvent, entity_id)
        if not row:
            raise HTTPException(404, "Olay kaydı bulunamadı.")
        ensure_company_access(db, user, row.company_id)
        return row.company_id
    raise HTTPException(422, "Desteklenmeyen saha kanıt türü.")


def _ensure_evidence_read_role(user: User, row: FieldMobileEvidence) -> None:
    if row.entity_type == "incident" and user.role not in INCIDENT_ROLES:
        raise HTTPException(403, "Olay fotoğrafı yalnız yetkili saha uzmanı tarafından görüntülenebilir.")


@router.get("/ptw")
def mobile_ptw(company_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*FIELD_ROLES))):
    ensure_company_access(db, user, company_id)
    rows = db.scalars(select(WorkPermit).where(WorkPermit.company_id == company_id, WorkPermit.status == "active").order_by(WorkPermit.valid_until.asc())).all()
    return {"items": [ptw_payload(db, row) for row in rows]}


@router.post("/ptw/{permit_id}/close")
def mobile_close_ptw(permit_id: int, payload: MobileCloseInput, db: Session = Depends(get_db), user: User = Depends(require_roles(*FIELD_ROLES))):
    row = load_ptw(db, user, permit_id)
    if row.status != "active" or row.opening_checked_at is None:
        raise HTTPException(409, "Yalnız saha açılışı yapılmış aktif izin mobil kapatılabilir.")
    closing = db.scalar(select(WorkPermitControl).where(WorkPermitControl.permit_id == row.id, WorkPermitControl.control_type == "site_closing"))
    if not closing:
        closing = WorkPermitControl(permit_id=row.id, control_type="site_closing", status="passed", details=payload.note, checked_at=datetime.utcnow(), checked_by_id=user.id)
        db.add(closing)
    elif closing.status != "passed":
        raise HTTPException(409, "Saha kapanış kontrolü uygun olarak tamamlanmalıdır.")
    else:
        closing.status = "passed"; closing.details = payload.note; closing.checked_at = datetime.utcnow(); closing.checked_by_id = user.id
    row.status = "closed"; row.closed_at = datetime.utcnow(); row.closed_by_id = user.id
    ptw_audit(db, user, row.company_id, "work_permit_mobile_closed", row.id, payload.note or "PWA saha kapanış kontrolü yapıldı.")
    db.commit(); db.refresh(row)
    return ptw_payload(db, row)


@router.post("/evidence/{entity_type}/{entity_id}")
async def upload_evidence(entity_type: str, entity_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(require_roles(*FIELD_ROLES))):
    company_id = _entity_scope(db, user, entity_type, entity_id)
    name = Path(file.filename or "saha-kaniti.jpg").name[:255]
    raw = await file.read(MAX_IMAGE_BYTES + 1)
    _safe_image(raw, name)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name) or "saha-kaniti.jpg"
    key = f"{company_id}/field-mobile/{entity_type}/{entity_id}/{uuid.uuid4().hex[:12]}-{safe}"
    store = get_object_store()
    store.put_bytes(key, raw)
    row = FieldMobileEvidence(company_id=company_id, entity_type=entity_type, entity_id=entity_id, storage_key=key, original_name=name, content_type=(file.content_type or "image/jpeg")[:120], file_size=len(raw), captured_at=datetime.utcnow(), created_by_id=user.id)
    db.add(row); commit_object_upload(db, store, key); db.refresh(row)
    return {"id": row.id, "company_id": company_id, "entity_type": entity_type, "entity_id": entity_id, "file_name": name, "file_size": len(raw)}


@router.get("/evidence/{evidence_id}")
def download_evidence(evidence_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*FIELD_ROLES))):
    row = db.get(FieldMobileEvidence, evidence_id)
    if not row:
        raise HTTPException(404, "Saha kanıtı bulunamadı.")
    ensure_company_access(db, user, row.company_id)
    _ensure_evidence_read_role(user, row)
    return response_for_storage_key(row.storage_key, filename=row.original_name, media_type=row.content_type or "application/octet-stream")
