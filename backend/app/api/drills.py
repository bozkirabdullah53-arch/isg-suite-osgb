"""0.9.131 — Tatbikat yönetimi API (İSG uzmanı; mevcut modüllere dokunmaz)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.company_access import company_ids_for_query, ensure_company_access
from app.api.deps import get_current_user, require_roles
from app.core.config import settings
from app.core.database import get_db
from app.models.entities import Company, DrillPhoto, DrillRecord, Employee, User, UserRole
from app.schemas.drills import (
    DRILL_STATUSES,
    DRILL_TYPES,
    DrillCreate,
    DrillParticipant,
    DrillPhotoResponse,
    DrillResponse,
)

router = APIRouter(prefix="/drills", tags=["Tatbikat Yönetimi"])

EDIT_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST)
VIEW_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST)
ALLOWED_PHOTO = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
ENGINE = "drill-management-v1"


def _upload_root() -> Path:
    root = Path(settings.upload_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _parse_participants(raw: str | None) -> list[DrillParticipant]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if not isinstance(data, list):
            return []
        out: list[DrillParticipant] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            name = str(item.get("full_name") or "").strip()
            if not name:
                continue
            out.append(
                DrillParticipant(
                    id=item.get("id"),
                    full_name=name,
                    job_title=item.get("job_title"),
                    department=item.get("department"),
                )
            )
        return out
    except Exception:
        return []


def _to_response(row: DrillRecord) -> DrillResponse:
    photos = [
        DrillPhotoResponse.model_validate(p) for p in (row.photos or [])
    ]
    return DrillResponse(
        id=row.id,
        company_id=row.company_id,
        drill_type=row.drill_type,
        drill_date=row.drill_date,
        start_time=row.start_time,
        end_time=row.end_time,
        responsible=row.responsible,
        participant_count=int(row.participant_count or 0),
        assembly_area=row.assembly_area,
        status=row.status,
        scenario=row.scenario,
        gaps=row.gaps,
        result=row.result,
        participants=_parse_participants(row.participants_json),
        photos=photos,
        is_active=bool(row.is_active),
        created_by_id=row.created_by_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _load(db: Session, drill_id: int) -> DrillRecord:
    row = db.scalar(
        select(DrillRecord)
        .where(DrillRecord.id == drill_id)
        .options(selectinload(DrillRecord.photos))
    )
    if not row or not row.is_active:
        raise HTTPException(404, "Tatbikat kaydı bulunamadı.")
    return row


@router.get("/meta")
def drills_meta(user: User = Depends(get_current_user)):
    return {
        "engine": ENGINE,
        "types": list(DRILL_TYPES),
        "statuses": list(DRILL_STATUSES),
        "note": "Tatbikat yönetimi — oluştur, listele, fotoğraf, TXT tutanak; soft silme.",
    }


@router.get("", response_model=list[DrillResponse])
def list_drills(
    company_id: int | None = None,
    q: str | None = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    stmt = (
        select(DrillRecord)
        .options(selectinload(DrillRecord.photos))
        .order_by(DrillRecord.drill_date.desc(), DrillRecord.id.desc())
    )
    company_ids = company_ids_for_query(db, user, company_id)
    if company_ids == []:
        return []
    if company_ids is not None:
        stmt = stmt.where(DrillRecord.company_id.in_(company_ids))
    if active_only:
        stmt = stmt.where(DrillRecord.is_active.is_(True))
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                DrillRecord.drill_type.ilike(pattern),
                DrillRecord.responsible.ilike(pattern),
                DrillRecord.assembly_area.ilike(pattern),
                DrillRecord.scenario.ilike(pattern),
            )
        )
    return [_to_response(r) for r in db.scalars(stmt).all()]


@router.post("", response_model=DrillResponse)
def create_drill(
    payload: DrillCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    ensure_company_access(db, user, payload.company_id)
    if payload.start_time and payload.end_time and payload.start_time >= payload.end_time:
        raise HTTPException(422, "Başlangıç saati bitişten önce olmalıdır.")

    participants: list[dict] = []
    if payload.employee_ids:
        emps = list(
            db.scalars(
                select(Employee).where(
                    Employee.company_id == payload.company_id,
                    Employee.id.in_(payload.employee_ids),
                    Employee.is_active.is_(True),
                )
            ).all()
        )
        for e in emps:
            participants.append(
                {
                    "id": e.id,
                    "full_name": e.full_name,
                    "job_title": e.job_title,
                    "department": e.department,
                }
            )

    count = payload.participant_count
    if count is None:
        count = len(participants)

    row = DrillRecord(
        company_id=payload.company_id,
        drill_type=payload.drill_type,
        drill_date=payload.drill_date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        responsible=payload.responsible,
        participant_count=int(count or 0),
        assembly_area=payload.assembly_area,
        status=payload.status,
        scenario=payload.scenario,
        gaps=payload.gaps,
        result=payload.result,
        participants_json=json.dumps(participants, ensure_ascii=False) if participants else None,
        created_by_id=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_response(_load(db, row.id))


@router.delete("/{drill_id}")
def deactivate_drill(
    drill_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = _load(db, drill_id)
    ensure_company_access(db, user, row.company_id)
    row.is_active = False
    row.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "id": drill_id}


@router.post("/{drill_id}/photos", response_model=DrillPhotoResponse)
async def upload_photo(
    drill_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = _load(db, drill_id)
    ensure_company_access(db, user, row.company_id)
    name = file.filename or "photo.jpg"
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_PHOTO:
        raise HTTPException(422, "Sadece jpg/png/webp/gif yükleyin.")
    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"Dosya {settings.max_upload_mb} MB sınırını aşıyor.")
    rel = f"{row.company_id}/drills/{row.id}_{uuid.uuid4().hex[:10]}{ext}"
    target = _upload_root() / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    photo = DrillPhoto(
        drill_id=row.id,
        storage_path=rel.replace("\\", "/"),
        original_name=name,
        content_type=file.content_type or "application/octet-stream",
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return DrillPhotoResponse.model_validate(photo)


@router.get("/{drill_id}/photos/{photo_id}")
def get_photo(
    drill_id: int,
    photo_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    row = _load(db, drill_id)
    ensure_company_access(db, user, row.company_id)
    photo = next((p for p in (row.photos or []) if p.id == photo_id), None)
    if not photo:
        raise HTTPException(404, "Fotoğraf bulunamadı.")
    path = (_upload_root() / photo.storage_path).resolve()
    if _upload_root() not in path.parents or not path.exists():
        raise HTTPException(404, "Dosya bulunamadı.")
    return FileResponse(
        path,
        media_type=photo.content_type or "application/octet-stream",
        filename=photo.original_name or path.name,
    )


@router.get("/{drill_id}/export.txt")
def export_txt(
    drill_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    row = _load(db, drill_id)
    ensure_company_access(db, user, row.company_id)
    company = db.get(Company, row.company_id)
    parts = _parse_participants(row.participants_json)
    names = ", ".join(p.full_name for p in parts) or "—"
    time_range = "—"
    if row.start_time or row.end_time:
        time_range = f"{row.start_time or '?'} – {row.end_time or '?'}"
    lines = [
        "TATBİKAT TUTANAĞI",
        "=" * 40,
        f"İşyeri: {company.name if company else row.company_id}",
        f"Tür: {row.drill_type}",
        f"Tarih: {row.drill_date}",
        f"Saat: {time_range}",
        f"Sorumlu: {row.responsible or '—'}",
        f"Toplanma alanı: {row.assembly_area or '—'}",
        f"Durum: {row.status}",
        f"Katılımcı sayısı: {row.participant_count}",
        f"Katılımcılar: {names}",
        f"Fotoğraf: {len(row.photos or [])}",
        "",
        "Senaryo:",
        row.scenario,
        "",
        "Eksikler:",
        row.gaps or "—",
        "",
        "Sonuç:",
        row.result or "—",
        "",
        f"Kayıt: {row.created_at}",
    ]
    return PlainTextResponse(
        "\n".join(lines),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="tatbikat-tutanagi-{drill_id}.txt"'},
    )
