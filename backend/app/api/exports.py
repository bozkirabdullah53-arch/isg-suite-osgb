from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.company_access import assigned_company_ids
from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import Employee, IsgRecord, User, UserRole

router = APIRouter(prefix="/exports", tags=["Dışa Aktarım"])
ADMIN = (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)


def _scoped_company_ids(user: User, requested: int | None, db: Session) -> list[int] | None:
    """None = global tüm firmalar. Boş = erişim yok."""
    if user.role == UserRole.GLOBAL_ADMIN:
        return [requested] if requested else None
    allowed = assigned_company_ids(db, user)
    if not allowed:
        return []
    if requested:
        if requested not in allowed:
            raise HTTPException(403, "Bu firmaya erişemezsiniz.")
        return [requested]
    return allowed


@router.get("/employees.xlsx")
def export_employees_excel(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN)),
):
    scope = _scoped_company_ids(user, company_id, db)
    if scope is not None and not scope:
        rows = []
    else:
        query = select(Employee).order_by(Employee.full_name)
        if scope is not None:
            query = query.where(Employee.company_id.in_(scope))
        rows = list(db.scalars(query).all())

    wb = Workbook()
    ws = wb.active
    ws.title = "Personel"
    ws.append(["Adı Soyadı", "Görevi", "İşe Giriş Tarihi", "Özel Durum", "Aktif"])
    for r in rows:
        ws.append([
            r.full_name,
            r.job_title or "",
            r.start_date.isoformat() if r.start_date else "",
            r.special_status or "",
            "Evet" if r.is_active else "Hayır",
        ])
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="personel-listesi.xlsx"'},
    )


@router.get("/isg-summary.pdf")
def export_isg_pdf(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN)),
):
    scope = _scoped_company_ids(user, company_id, db)
    if scope is not None and not scope:
        rows = []
    else:
        query = select(IsgRecord).order_by(IsgRecord.created_at.desc())
        if scope is not None:
            query = query.where(IsgRecord.company_id.in_(scope))
        rows = list(db.scalars(query).all())

    stream = BytesIO()
    pdf = canvas.Canvas(stream, pagesize=A4)
    width, height = A4
    y = height - 50
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(45, y, "ISG Suite - ISG Kayit Ozeti")
    y -= 30
    pdf.setFont("Helvetica", 9)

    for item in rows:
        line = f"{item.module.value} | {item.title[:55]} | {item.status.value}"
        pdf.drawString(45, y, line)
        y -= 15
        if y < 50:
            pdf.showPage()
            y = height - 50
            pdf.setFont("Helvetica", 9)

    pdf.save()
    stream.seek(0)
    return StreamingResponse(
        stream,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="isg-ozet.pdf"'},
    )
