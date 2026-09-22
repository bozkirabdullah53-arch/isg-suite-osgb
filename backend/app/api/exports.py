from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.company_access import assigned_company_ids
from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import Branch, Company, Employee, IsgRecord, User, UserRole
from app.schemas.employee import normalize_gender

router = APIRouter(prefix="/exports", tags=["Dışa Aktarım"])
ADMIN = (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)
EMPLOYEE_EXPORT = (
    UserRole.GLOBAL_ADMIN,
    UserRole.COMPANY_ADMIN,
    UserRole.SAFETY_SPECIALIST,
    UserRole.WORKPLACE_PHYSICIAN,
    UserRole.OTHER_HEALTH_PERSONNEL,
)


def _gender_summary(rows: list[Employee]) -> tuple[int, int, int]:
    """Return women, men and genuinely unspecified counts for a report."""
    values = [normalize_gender(row.gender) for row in rows]
    women = values.count("Kadın")
    men = values.count("Erkek")
    unknown = len(values) - women - men
    return women, men, unknown


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
    ws.append(["#", "Adı Soyadı", "TC Kimlik No", "Görevi", "Departman", "Şube", "Cinsiyet", "İşe Giriş", "İşten Çıkış", "Özel Durum", "Durum"])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = "A1:K1"
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
            normalize_gender(r.gender) or "",
            r.start_date.isoformat() if r.start_date else "",
            r.exit_date.isoformat() if r.exit_date else "",
            r.special_status or "",
            "Aktif" if r.is_active else "Pasif",
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
    font_path = Path(__file__).resolve().parents[1] / "assets" / "fonts" / "DejaVuSans.ttf"
    bold_path = Path(__file__).resolve().parents[1] / "assets" / "fonts" / "DejaVuSans-Bold.ttf"
    if font_path.exists():
        pdfmetrics.registerFont(TTFont("EmployeeReportSans", str(font_path)))
        if bold_path.exists():
            pdfmetrics.registerFont(TTFont("EmployeeReportSans-Bold", str(bold_path)))
    font = "EmployeeReportSans" if font_path.exists() else "Helvetica"
    bold_font = "EmployeeReportSans-Bold" if bold_path.exists() else "Helvetica-Bold"
    company = db.get(Company, company_id) if company_id else None
    safe = lambda value: escape(str(value or ""))
    women, men, unknown_gender = _gender_summary(rows)
    disabled = sum(1 for row in rows if row.special_status and "engelli" in row.special_status.lower())
    stream = BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=landscape(A4), rightMargin=8 * mm, leftMargin=8 * mm, topMargin=10 * mm, bottomMargin=10 * mm)
    title_style = ParagraphStyle("EmployeeTitle", parent=styles["Title"], fontName=bold_font, fontSize=16, leading=20, spaceAfter=0)
    date_style = ParagraphStyle("EmployeeDate", parent=styles["BodyText"], fontName=font, fontSize=8, textColor=colors.HexColor("#475569"), alignment=2)
    body_style = ParagraphStyle("EmployeeBody", parent=styles["BodyText"], fontName=font, fontSize=8, leading=10)
    label_style = ParagraphStyle("EmployeeLabel", parent=body_style, fontName=bold_font, textColor=colors.HexColor("#0F4C5C"))
    company_text = company.name if company else "Tüm işyerleri"
    title = Paragraph(safe(company_text), title_style)
    report_time = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%d.%m.%Y %H:%M")
    title_block = Table(
        [[title, Paragraph(f"Rapor tarihi<br/>{report_time} (Türkiye saati)", date_style)]],
        colWidths=[140 * mm, 45 * mm],
    )
    title_block.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    meta = Table([
        [Paragraph("Firma Unvanı", label_style), Paragraph(safe(company_text), body_style), Paragraph("SGK Sicil No", label_style), Paragraph(safe(company.sgk_registry_no if company else None) or "—", body_style)],
        [Paragraph("NACE Kodu", label_style), Paragraph(safe(company.nace_code if company else None) or "—", body_style), Paragraph("Tehlike Sınıfı", label_style), Paragraph(safe(company.hazard_class if company else None) or "—", body_style)],
        [Paragraph("Adres", label_style), Paragraph(safe(company.address if company else None) or "—", body_style), Paragraph("Telefon", label_style), Paragraph(safe(company.phone if company else None) or "—", body_style)],
    ], colWidths=[27 * mm, 72 * mm, 31 * mm, 55 * mm])
    meta.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    summary = Paragraph(
        f"<b>Personel Özeti</b> &nbsp; Toplam: {len(rows)} &nbsp; | &nbsp; Kadın: {women} &nbsp; | &nbsp; Erkek: {men} &nbsp; | &nbsp; Cinsiyet belirtilmemiş: {unknown_gender} &nbsp; | &nbsp; Engelli: {disabled}", body_style)
    data = [["#", "Ad Soyad", "TC Kimlik No", "Görev", "Departman", "Şube", "Cinsiyet", "İşe Giriş", "İşten Çıkış", "Özel Durum", "Durum"]]
    data.extend([
        [str(index), r.full_name, r.national_id_masked or "", r.job_title or "", r.department or "", branch_names.get(r.branch_id, ""), normalize_gender(r.gender) or "",
         r.start_date.isoformat() if r.start_date else "", r.exit_date.isoformat() if r.exit_date else "", r.special_status or "", "Aktif" if r.is_active else "Pasif"]
        for index, r in enumerate(rows, start=1)
    ])
    raw_header, *raw_rows = data
    header_style = ParagraphStyle("EmployeeHeader", parent=body_style, fontName=bold_font, textColor=colors.white, alignment=1)
    data = [[Paragraph(safe(value), body_style) for value in row] for row in raw_rows]
    data.insert(0, [Paragraph(safe(value), header_style) for value in raw_header])
    table = Table(data, repeatRows=1, colWidths=[12 * mm, 30 * mm, 25 * mm, 23 * mm, 23 * mm, 23 * mm, 19 * mm, 23 * mm, 23 * mm, 25 * mm, 17 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F4C5C")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), bold_font),
        ("FONTNAME", (0, 1), (-1, -1), font),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    doc.build([title_block, Spacer(1, 4 * mm), meta, Spacer(1, 3 * mm), summary, Spacer(1, 5 * mm), table])
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
