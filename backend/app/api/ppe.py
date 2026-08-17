"""KKD zimmet API — PRO KKD Takip parity (multi-tenant)."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
import uuid
import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.company_access import company_ids_for_query, effective_company_id, ensure_company_access
from app.api.deps import get_current_user, require_roles
from app.core.config import settings
from app.core.database import get_db
from app.services.upload_gateway import persist_relative
from app.services.upload_security import assert_safe_upload
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
logger = logging.getLogger(__name__)
EDIT_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN, UserRole.SAFETY_SPECIALIST)
ALLOWED_PHOTO = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def ensure_access(db: Session, user: User, company_id: int) -> None:
    ensure_company_access(db, user, company_id)


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
    effective = effective_company_id(db, user, company_id)
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
    stmt = (
        select(PpeAssignment)
        .options(selectinload(PpeAssignment.photos))
        .where(PpeAssignment.deleted_at.is_(None))
        .order_by(PpeAssignment.delivery_date.desc(), PpeAssignment.id.desc())
    )
    company_ids = company_ids_for_query(db, user, company_id)
    if company_ids == []:
        return []
    if company_ids is not None:
        stmt = stmt.where(PpeAssignment.company_id.in_(company_ids))
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
    ensure_access(db, user, payload.company_id)
    if not db.get(Company, payload.company_id):
        raise HTTPException(404, "Firma bulunamadı.")
    emp = db.get(Employee, payload.employee_id)
    if not emp or emp.company_id != payload.company_id or not emp.is_active:
        raise HTTPException(422, "Personel firmaya ait değil veya pasif.")
    if payload.branch_id:
        b = db.get(Branch, payload.branch_id)
        if not b or b.company_id != payload.company_id:
            raise HTTPException(422, "Şube firmaya ait değil.")
    data = payload.model_dump()
    data["delivered_by"] = payload.delivered_by or user.full_name
    row = PpeAssignment(**data, created_by_id=user.id)
    db.add(row)
    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("KKD zimmet kaydı oluşturulamadı")
        raise HTTPException(500, "KKD zimmet kaydı oluşturulamadı. Lütfen bilgileri kontrol edip tekrar deneyin.")
    row = _load(db, row.id)
    return _to_response(row, emp)


@router.get("/assignments/{assignment_id}", response_model=PpeAssignmentResponse)
def get_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = _load(db, assignment_id)
    ensure_access(db, user, row.company_id)
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
    ensure_access(db, user, row.company_id)
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
    ensure_access(db, user, row.company_id)
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
    ensure_access(db, user, row.company_id)
    name = file.filename or "photo.jpg"
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_PHOTO:
        raise HTTPException(422, "Sadece jpg/png/webp/gif yükleyin.")
    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"Dosya {settings.max_upload_mb} MB sınırını aşıyor.")
    rel = f"{row.company_id}/ppe/{row.id}_{uuid.uuid4().hex[:10]}{ext}"
    if settings.upload_gateway_enabled:
        persist_relative(data, relative_path=rel, original_name=name)
    else:
        assert_safe_upload(data, ext, name)
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
    ensure_access(db, user, row.company_id)
    photo = next((p for p in (row.photos or []) if p.id == photo_id), None)
    if not photo:
        raise HTTPException(404, "Fotoğraf bulunamadı.")
    from app.services.stored_files import response_for_storage_key

    return response_for_storage_key(
        photo.storage_path,
        filename=photo.original_name,
        media_type=photo.content_type or "application/octet-stream",
    )


def _pdf_font_name() -> str:
    candidates = [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    ]
    bold_candidates = [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
    ]
    try:
        normal = next((x for x in candidates if x.exists()), None)
        bold = next((x for x in bold_candidates if x.exists()), None)
        if normal and bold:
            pdfmetrics.registerFont(TTFont("PpeSans", str(normal)))
            pdfmetrics.registerFont(TTFont("PpeSans-Bold", str(bold)))
            return "PpeSans"
    except Exception:
        logger.exception("PDF yazı tipi yüklenemedi")
    return "Helvetica"


def _fmt_date(value) -> str:
    return value.strftime("%d.%m.%Y") if value else "—"


@router.get("/assignments/{assignment_id}/pdf")
def assignment_pdf(
    assignment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = _load(db, assignment_id)
    ensure_access(db, user, row.company_id)
    employee = db.get(Employee, row.employee_id)
    company = db.get(Company, row.company_id)
    branch = db.get(Branch, row.branch_id) if row.branch_id else None
    if not employee or employee.company_id != row.company_id:
        raise HTTPException(422, "Zimmet kaydına bağlı personel bulunamadı.")

    font = _pdf_font_name()
    bold_font = "PpeSans-Bold" if font == "PpeSans" else "Helvetica-Bold"
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "PpeTitle", parent=styles["Title"], fontName=bold_font, fontSize=16,
        leading=20, alignment=TA_CENTER, textColor=colors.HexColor("#0f3f4a"), spaceAfter=8,
    )
    subtitle_style = ParagraphStyle(
        "PpeSubtitle", parent=styles["Normal"], fontName=font, fontSize=9.5,
        leading=13, alignment=TA_CENTER, textColor=colors.HexColor("#475569"),
    )
    label_style = ParagraphStyle(
        "PpeLabel", parent=styles["Normal"], fontName=bold_font, fontSize=8.5,
        leading=11, textColor=colors.HexColor("#334155"),
    )
    value_style = ParagraphStyle(
        "PpeValue", parent=styles["Normal"], fontName=font, fontSize=9,
        leading=12, textColor=colors.HexColor("#111827"), wordWrap="CJK",
    )
    note_style = ParagraphStyle(
        "PpeNote", parent=styles["Normal"], fontName=font, fontSize=9,
        leading=13, alignment=TA_LEFT, textColor=colors.HexColor("#1f2937"),
    )

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, rightMargin=14*mm, leftMargin=14*mm,
        topMargin=12*mm, bottomMargin=12*mm,
        title=f"KKD Zimmet Formu #{row.id}", author="İSG Suite OSGB",
    )
    story = []
    story.append(Paragraph("KİŞİSEL KORUYUCU DONANIM ZİMMET VE TESLİM FORMU", title_style))
    company_line = company.name if company else f"İşyeri #{row.company_id}"
    if branch:
        company_line += f" / {branch.name}"
    story.append(Paragraph(company_line, subtitle_style))
    story.append(Paragraph(f"Belge No: KKD-{row.id:06d} &nbsp;&nbsp;|&nbsp;&nbsp; Düzenleme Tarihi: {_fmt_date(date.today())}", subtitle_style))
    story.append(Spacer(1, 6*mm))

    def cell(label, value):
        return [Paragraph(label, label_style), Paragraph(str(value or "—"), value_style)]

    info_rows = [
        [*cell("Personel", employee.full_name), *cell("Görev / Bölüm", " / ".join(x for x in [employee.job_title, employee.department] if x) or "—")],
        [*cell("Teslim Tarihi", _fmt_date(row.delivery_date)), *cell("Teslim Eden", row.delivered_by or "—")],
        [*cell("KKD Kategorisi", row.category), *cell("KKD Türü", row.item_type)],
        [*cell("Adet", row.quantity), *cell("Durum", status_label(row.status))],
        [*cell("Marka", row.brand), *cell("Model", row.model)],
        [*cell("Beden", row.size), *cell("Seri No", row.serial_no)],
        [*cell("Raf Ömrü", row.shelf_life_text), *cell("Garanti", row.warranty_text)],
        [*cell("Son Kullanma", _fmt_date(row.expiry_date)), *cell("Yenileme / Kontrol", _fmt_date(row.renewal_date))],
    ]
    info = Table(info_rows, colWidths=[31*mm, 57*mm, 31*mm, 57*mm], repeatRows=0)
    info.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("GRID", (0,0), (-1,-1), 0.45, colors.HexColor("#cbd5e1")),
        ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#eef7f7")),
        ("BACKGROUND", (2,0), (2,-1), colors.HexColor("#eef7f7")),
        ("LEFTPADDING", (0,0), (-1,-1), 6), ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(info)
    story.append(Spacer(1, 5*mm))

    notes = Table([
        [Paragraph("Risk / Kullanım Alanı", label_style)],
        [Paragraph(row.risk_note or "—", value_style)],
        [Paragraph("Açıklama", label_style)],
        [Paragraph(row.notes or "—", value_style)],
    ], colWidths=[176*mm])
    notes.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.45, colors.HexColor("#cbd5e1")),
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#eef7f7")),
        ("BACKGROUND", (0,2), (-1,2), colors.HexColor("#eef7f7")),
        ("LEFTPADDING", (0,0), (-1,-1), 7), ("RIGHTPADDING", (0,0), (-1,-1), 7),
        ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(notes)
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph(
        "Yukarıda tanımı ve özellikleri bulunan kişisel koruyucu donanımı sağlam ve eksiksiz olarak teslim aldım. "
        "Donanımı verilen eğitim ve talimatlara uygun kullanacağımı, bakım ve muhafazasını sağlayacağımı; kayıp, "
        "hasar veya yenileme ihtiyacını gecikmeden işverene/İSG birimine bildireceğimi kabul ve taahhüt ederim.",
        note_style,
    ))
    story.append(Spacer(1, 8*mm))

    sig_data = [
        [Paragraph("TESLİM EDEN", label_style), Paragraph("TESLİM ALAN ÇALIŞAN", label_style), Paragraph("İŞVEREN / İŞVEREN VEKİLİ", label_style)],
        [
            Paragraph(row.delivered_by or "", value_style),
            Paragraph(employee.full_name or "", value_style),
            Paragraph((company.authorized_person if company else None) or "", value_style),
        ],
        [Paragraph("Tarih / Kaşe / İmza", subtitle_style), Paragraph("Tarih / İmza", subtitle_style), Paragraph("Tarih / Kaşe / İmza", subtitle_style)],
    ]
    sig = Table(sig_data, colWidths=[58.6*mm, 58.6*mm, 58.6*mm], rowHeights=[9*mm, 22*mm, 10*mm])
    sig.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.55, colors.HexColor("#94a3b8")),
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#eef7f7")),
        ("ALIGN", (0,0), (-1,-1), "CENTER"), ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(sig)

    def footer(canvas, doc_obj):
        canvas.saveState()
        canvas.setFont(font, 8)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(14*mm, 8*mm, "İSG Suite OSGB — KKD Zimmet Formu")
        canvas.drawRightString(A4[0]-14*mm, 8*mm, f"Sayfa {doc_obj.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    buf.seek(0)
    filename = f"kkd-zimmet-{row.id}-{employee.full_name.strip().replace(' ', '-')}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export.xlsx")
def export_assignments_excel(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    effective = effective_company_id(db, user, company_id)
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
