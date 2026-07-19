"""KKD zimmet API — PRO KKD Takip parity (multi-tenant)."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from openpyxl import Workbook
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_roles
from app.core.config import settings
from app.core.database import get_db
from app.models.entities import (
    Branch,
    Company,
    Employee,
    PpeAssignment,
    PpeAssignmentPhoto,
    User,
    UserRole,
)
from app.schemas.ppe import (
    PpeAssignmentCreate,
    PpeAssignmentResponse,
    PpeAssignmentUpdate,
    PpeDueSummary,
    PpePhotoResponse,
)
from app.services.ppe_catalog import catalog_payload, status_label

router = APIRouter(prefix="/ppe", tags=["KKD Takip"])
EDIT_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN, UserRole.SAFETY_SPECIALIST)
ALLOWED_PHOTO = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def ensure_access(user: User, company_id: int):
    if user.role != UserRole.GLOBAL_ADMIN and user.company_id != company_id:
        raise HTTPException(403, "Bu firmanın KKD kayıtlarına erişemezsiniz.")


def _upload_root() -> Path:
    root = Path(settings.upload_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _to_response(row: PpeAssignment, employee: Employee | None = None) -> PpeAssignmentResponse:
    emp = employee
    return PpeAssignmentResponse(
        id=row.id,
        company_id=row.company_id,
        branch_id=row.branch_id,
        employee_id=row.employee_id,
        employee_name=emp.full_name if emp else None,
        employee_department=emp.department if emp else None,
        employee_job_title=emp.job_title if emp else None,
        delivery_date=row.delivery_date,
        category=row.category,
        item_type=row.item_type,
        quantity=row.quantity,
        brand=row.brand,
        model=row.model,
        size=row.size,
        serial_no=row.serial_no,
        shelf_life_text=row.shelf_life_text,
        expiry_date=row.expiry_date,
        warranty_text=row.warranty_text,
        renewal_date=row.renewal_date,
        status=row.status,
        status_label=status_label(row.status),
        delivered_by=row.delivered_by,
        risk_note=row.risk_note,
        notes=row.notes,
        created_by_id=row.created_by_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        photos=[PpePhotoResponse.model_validate(p) for p in (row.photos or [])],
    )


def _load(db: Session, assignment_id: int) -> PpeAssignment:
    row = db.scalar(
        select(PpeAssignment)
        .options(selectinload(PpeAssignment.photos))
        .where(PpeAssignment.id == assignment_id, PpeAssignment.deleted_at.is_(None))
    )
    if not row:
        raise HTTPException(404, "KKD kaydı bulunamadı.")
    return row


@router.get("/catalog")
def ppe_catalog(user: User = Depends(get_current_user)):
    return catalog_payload()


@router.get("/due-summary", response_model=PpeDueSummary)
def due_summary(
    company_id: int | None = None,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    effective = company_id if user.role == UserRole.GLOBAL_ADMIN else user.company_id
    if not effective:
        raise HTTPException(422, "Firma seçiniz.")
    ensure_access(user, effective)
    today = date.today()
    soon = today + timedelta(days=days)
    rows = list(
        db.scalars(
            select(PpeAssignment).where(
                PpeAssignment.company_id == effective,
                PpeAssignment.deleted_at.is_(None),
                PpeAssignment.status.in_(("teslim", "yenilenecek")),
            )
        ).all()
    )
    overdue = 0
    due_soon = 0
    for r in rows:
        dates = [d for d in (r.renewal_date, r.expiry_date) if d]
        if not dates:
            continue
        dmin = min(dates)
        if dmin < today:
            overdue += 1
        elif dmin <= soon:
            due_soon += 1
    return PpeDueSummary(overdue=overdue, due_soon=due_soon, total_active=len(rows))


@router.get("/assignments", response_model=list[PpeAssignmentResponse])
def list_assignments(
    company_id: int | None = None,
    employee_id: int | None = None,
    status: str | None = None,
    q: str | None = Query(None, max_length=120),
    due_within_days: int | None = Query(None, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == UserRole.GLOBAL_ADMIN:
        effective = company_id
        if not effective:
            raise HTTPException(422, "Global yönetici için company_id zorunludur.")
    else:
        if not user.company_id:
            raise HTTPException(403, "Firma atanmamış kullanıcı KKD listesini göremez.")
        effective = user.company_id
    ensure_access(user, effective)

    stmt = (
        select(PpeAssignment)
        .options(selectinload(PpeAssignment.photos))
        .where(PpeAssignment.company_id == effective, PpeAssignment.deleted_at.is_(None))
        .order_by(PpeAssignment.delivery_date.desc(), PpeAssignment.id.desc())
    )
    if employee_id:
        stmt = stmt.where(PpeAssignment.employee_id == employee_id)
    if status:
        stmt = stmt.where(PpeAssignment.status == status)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                PpeAssignment.category.ilike(like),
                PpeAssignment.item_type.ilike(like),
                PpeAssignment.brand.ilike(like),
                PpeAssignment.model.ilike(like),
                PpeAssignment.serial_no.ilike(like),
            )
        )
    rows = list(db.scalars(stmt.limit(500)).unique().all())
    if due_within_days is not None:
        today = date.today()
        soon = today + timedelta(days=due_within_days)
        filtered = []
        for r in rows:
            dates = [d for d in (r.renewal_date, r.expiry_date) if d]
            if dates and min(dates) <= soon:
                filtered.append(r)
        rows = filtered

    emp_ids = {r.employee_id for r in rows}
    employees = {
        e.id: e
        for e in db.scalars(select(Employee).where(Employee.id.in_(emp_ids))).all()
    } if emp_ids else {}
    return [_to_response(r, employees.get(r.employee_id)) for r in rows]


@router.post("/assignments", response_model=PpeAssignmentResponse)
def create_assignment(
    payload: PpeAssignmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    ensure_access(user, payload.company_id)
    if not db.get(Company, payload.company_id):
        raise HTTPException(404, "Firma bulunamadı.")
    emp = db.get(Employee, payload.employee_id)
    if not emp or emp.company_id != payload.company_id or not emp.is_active:
        raise HTTPException(422, "Personel firmaya ait değil veya pasif.")
    if payload.branch_id:
        b = db.get(Branch, payload.branch_id)
        if not b or b.company_id != payload.company_id:
            raise HTTPException(422, "Şube firmaya ait değil.")
    row = PpeAssignment(
        **payload.model_dump(),
        delivered_by=payload.delivered_by or user.full_name,
        created_by_id=user.id,
    )
    db.add(row)
    db.commit()
    row = _load(db, row.id)
    return _to_response(row, emp)


@router.get("/assignments/{assignment_id}", response_model=PpeAssignmentResponse)
def get_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = _load(db, assignment_id)
    ensure_access(user, row.company_id)
    emp = db.get(Employee, row.employee_id)
    return _to_response(row, emp)


@router.patch("/assignments/{assignment_id}", response_model=PpeAssignmentResponse)
def update_assignment(
    assignment_id: int,
    payload: PpeAssignmentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = _load(db, assignment_id)
    ensure_access(user, row.company_id)
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] and data["status"] not in ("teslim", "yenilenecek", "iade", "kayip"):
        raise HTTPException(422, "Geçersiz durum.")
    for k, v in data.items():
        setattr(row, k, v)
    db.commit()
    row = _load(db, assignment_id)
    emp = db.get(Employee, row.employee_id)
    return _to_response(row, emp)


@router.delete("/assignments/{assignment_id}")
def delete_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = _load(db, assignment_id)
    ensure_access(user, row.company_id)
    row.deleted_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "id": assignment_id}


@router.post("/assignments/{assignment_id}/photos", response_model=PpePhotoResponse)
async def upload_photo(
    assignment_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = _load(db, assignment_id)
    ensure_access(user, row.company_id)
    name = file.filename or "photo.jpg"
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_PHOTO:
        raise HTTPException(422, "Sadece jpg/png/webp/gif yükleyin.")
    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"Dosya {settings.max_upload_mb} MB sınırını aşıyor.")
    rel = f"{row.company_id}/ppe/{row.id}_{uuid.uuid4().hex[:10]}{ext}"
    target = _upload_root() / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    photo = PpeAssignmentPhoto(
        assignment_id=row.id,
        storage_path=rel.replace("\\", "/"),
        original_name=name,
        content_type=file.content_type or "application/octet-stream",
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return PpePhotoResponse.model_validate(photo)


@router.get("/assignments/{assignment_id}/photos/{photo_id}")
def get_photo(
    assignment_id: int,
    photo_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = _load(db, assignment_id)
    ensure_access(user, row.company_id)
    photo = next((p for p in (row.photos or []) if p.id == photo_id), None)
    if not photo:
        raise HTTPException(404, "Fotoğraf bulunamadı.")
    path = (_upload_root() / photo.storage_path).resolve()
    if _upload_root() not in path.parents or not path.exists():
        raise HTTPException(404, "Dosya bulunamadı.")
    return FileResponse(path, media_type=photo.content_type or "application/octet-stream", filename=photo.original_name or path.name)


@router.get("/export.xlsx")
def export_assignments_excel(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == UserRole.GLOBAL_ADMIN:
        effective = company_id
        if not effective:
            raise HTTPException(422, "Firma seçiniz.")
    else:
        effective = user.company_id
        if not effective:
            raise HTTPException(403, "Firma atanmamış.")
    ensure_access(user, effective)
    rows = list(
        db.scalars(
            select(PpeAssignment)
            .where(PpeAssignment.company_id == effective, PpeAssignment.deleted_at.is_(None))
            .order_by(PpeAssignment.delivery_date.desc())
        ).all()
    )
    emp_ids = {r.employee_id for r in rows}
    employees = {
        e.id: e for e in db.scalars(select(Employee).where(Employee.id.in_(emp_ids))).all()
    } if emp_ids else {}
    wb = Workbook()
    ws = wb.active
    ws.title = "KKD Kayıtları"
    ws.append([
        "No", "Teslim", "Personel", "Bölüm", "Kategori", "Tür", "Adet",
        "Marka", "Model", "Beden", "Seri No", "Yenileme", "SKT", "Durum", "Teslim Eden", "Risk",
    ])
    for r in rows:
        e = employees.get(r.employee_id)
        ws.append([
            r.id,
            r.delivery_date.isoformat() if r.delivery_date else "",
            e.full_name if e else r.employee_id,
            (e.department if e else "") or "",
            r.category,
            r.item_type,
            r.quantity,
            r.brand or "",
            r.model or "",
            r.size or "",
            r.serial_no or "",
            r.renewal_date.isoformat() if r.renewal_date else "",
            r.expiry_date.isoformat() if r.expiry_date else "",
            status_label(r.status),
            r.delivered_by or "",
            r.risk_note or "",
        ])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="kkd-kayitlari-{effective}.xlsx"'},
    )
