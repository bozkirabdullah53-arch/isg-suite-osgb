from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.company_access import assigned_company_ids
from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import Branch, Employee, IsgRecord, User, UserRole

router = APIRouter(prefix="/exports", tags=["Dışa Aktarım"])
ADMIN = (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)
EMPLOYEE_EXPORT = (
    UserRole.GLOBAL_ADMIN,
    UserRole.COMPANY_ADMIN,
    UserRole.SAFETY_SPECIALIST,
    UserRole.WORKPLACE_PHYSICIAN,
    UserRole.OTHER_HEALTH_PERSONNEL,
)


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
    user: User = Depends(require_roles(*EMPLOYEE_EXPORT)),
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
    branch_names = {
        branch.id: branch.name
        for branch in db.scalars(select(Branch).where(Branch.company_id.in_({row.company_id for row in rows}))).all()
    } if rows else {}
    ws.append(["#", "Adı Soyadı", "TC Kimlik No", "Görevi", "Departman", "Şube", "İşe Giriş", "İşten Çıkış", "Özel Durum", "Durum"])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = "A1:J1"
    for cell in ws[1]:
        cell.font = cell.font.copy(bold=True)
    for index, r in enumerate(rows, start=1):
        ws.append([
            index,
            r.full_name,
            r.national_id_masked or "",
            r.job_title or "",
            r.department or "",
            branch_names.get(r.branch_id, ""),
            r.start_date.isoformat() if r.start_date else "",
            r.exit_date.isoformat() if r.exit_date else "",
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


@router.get("/employees.pdf")
def export_employees_pdf(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EMPLOYEE_EXPORT)),
):
    """Seçili işyerinin personel listesini okunabilir yatay PDF olarak dışa aktarır."""
    scope = _scoped_company_ids(user, company_id, db)
    query = select(Employee).order_by(Employee.full_name)
    if scope is not None:
        query = query.where(Employee.company_id.in_(scope))
    rows = list(db.scalars(query).all())
    branch_names = {
        branch.id: branch.name
        for branch in db.scalars(select(Branch).where(Branch.company_id.in_({row.company_id for row in rows}))).all()
    } if rows else {}
    styles = getSampleStyleSheet()
    for row in ws.iter_rows(min_row=2, min_col=3, max_col=3):
        row[0].number_format = "@"
    stream = BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=landscape(A4), rightMargin=8 * mm, leftMargin=8 * mm, topMargin=10 * mm, bottomMargin=10 * mm)
    title = Paragraph("Personel Listesi", styles["Title"])
    data = [["#", "Ad Soyad", "TC Kimlik No", "Görev", "Departman", "Şube", "İşe Giriş", "İşten Çıkış", "Özel Durum", "Durum"]]
    data.extend([
        [str(index), r.full_name, r.national_id_masked or "", r.job_title or "", r.department or "", branch_names.get(r.branch_id, ""),
         r.start_date.isoformat() if r.start_date else "", r.exit_date.isoformat() if r.exit_date else "", r.special_status or "", "Aktif" if r.is_active else "Pasif"]
        for index, r in enumerate(rows, start=1)
    ])
    table = Table(data, repeatRows=1, colWidths=[8 * mm, 37 * mm, 31 * mm, 28 * mm, 28 * mm, 28 * mm, 24 * mm, 24 * mm, 28 * mm, 18 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F4C5C")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    doc.build([title, table])
    stream.seek(0)
    return StreamingResponse(stream, media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="personel-listesi.pdf"'})


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
