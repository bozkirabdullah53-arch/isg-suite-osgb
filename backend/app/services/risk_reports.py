"""Risk değerlendirme PDF / Excel raporları — İSG PRO reports.py Suite uyarlaması."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path

import openpyxl
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

PDF_FONT = "Helvetica"
PDF_FONT_BOLD = "Helvetica-Bold"
_ASSETS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
CREATOR_LINE = "İSG Suite OSGB"
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}


def _upload_root() -> Path:
    try:
        from app.core.config import settings

        root = Path(settings.upload_dir).resolve()
    except Exception:
        root = Path("uploads").resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _risk_excel_photo_path(risk) -> str | None:
    """Risk kaydına bağlı ilk uygun fotoğraf dosyasını döndürür (PRO parity)."""
    try:
        media_items = list(getattr(risk, "media_files", None) or [])
    except Exception:
        media_items = []
    root = _upload_root()
    for media in media_items:
        name = getattr(media, "original_name", "") or ""
        rel = getattr(media, "storage_path", "") or ""
        ctype = (getattr(media, "content_type", "") or "").lower()
        ext = Path(name or rel).suffix.lower()
        if not (ctype.startswith("image/") or ext in _IMAGE_EXTS):
            continue
        candidate = (root / rel).resolve()
        if root in candidate.parents and candidate.exists():
            return str(candidate)
    return None


def _register_pdf_fonts() -> None:
    global PDF_FONT, PDF_FONT_BOLD
    candidates = [
        (_ASSETS / "DejaVuSans.ttf", _ASSETS / "DejaVuSans-Bold.ttf", "RiskDejaVu", "RiskDejaVu-Bold"),
        (Path(r"C:\Windows\Fonts\arial.ttf"), Path(r"C:\Windows\Fonts\arialbd.ttf"), "RiskArial", "RiskArial-Bold"),
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            "RiskDejaVu",
            "RiskDejaVu-Bold",
        ),
    ]
    for regular, bold, name, bold_name in candidates:
        if not regular.exists():
            continue
        try:
            pdfmetrics.registerFont(TTFont(name, str(regular)))
            PDF_FONT = name
            if bold.exists():
                pdfmetrics.registerFont(TTFont(bold_name, str(bold)))
                PDF_FONT_BOLD = bold_name
            else:
                PDF_FONT_BOLD = name
            try:
                registerFontFamily(name, normal=name, bold=PDF_FONT_BOLD, italic=name, boldItalic=PDF_FONT_BOLD)
            except Exception:
                pass
            return
        except Exception:
            continue


_register_pdf_fonts()


def _fmt_date(d) -> str:
    if not d:
        return "—"
    if hasattr(d, "strftime"):
        return d.strftime("%d.%m.%Y")
    s = str(d)
    if len(s) >= 10 and s[4] == "-":
        y, m, day = s[:10].split("-")
        return f"{day}.{m}.{y}"
    return s


def _dept(risk) -> str:
    return getattr(risk, "department_name", None) or "—"


def _hazard_name(risk, hazard_map: dict) -> str:
    h = hazard_map.get(getattr(risk, "hazard_id", None))
    return h.name if h else "—"


def _hazard_code(risk, hazard_map: dict) -> str:
    h = hazard_map.get(getattr(risk, "hazard_id", None))
    return h.code if h else "—"


def _level_color(level: str):
    if "Kabul" in (level or ""):
        return colors.HexColor("#95a5a6")
    if "Düşük" in (level or ""):
        return colors.HexColor("#2ecc71")
    if "Orta" in (level or ""):
        return colors.HexColor("#f1c40f")
    if "Çok" in (level or ""):
        return colors.HexColor("#e74c3c")
    if "Yüksek" in (level or ""):
        return colors.HexColor("#f39c12")
    return colors.white


def _add_pdf_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(PDF_FONT, 7)
    canvas.setFillColor(colors.HexColor("#6c757d"))
    canvas.drawString(doc.leftMargin, 10 * mm, f"Program tasarımı ve raporlama: {CREATOR_LINE}")
    canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 10 * mm, f"Sayfa {doc.page}")
    canvas.restoreState()


def build_risk_pdf(
    *,
    company,
    risks,
    hazard_map: dict | None = None,
    prepared_by: str | None = None,
    sgk_no: str | None = None,
    workplace_physician: str | None = None,
    employer_representative: str | None = None,
) -> bytes:
    """Firma risk değerlendirme PDF raporu."""
    hazard_map = hazard_map or {}
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=20 * mm,
        bottomMargin=15 * mm,
    )
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = PDF_FONT
    styles["Title"].fontName = PDF_FONT_BOLD

    title_style = ParagraphStyle(
        "RiskTitle",
        parent=styles["Title"],
        fontSize=18,
        fontName=PDF_FONT_BOLD,
        spaceAfter=6,
        textColor=colors.HexColor("#1a5276"),
        alignment=TA_CENTER,
    )
    subtitle = ParagraphStyle(
        "RiskSub",
        parent=styles["Normal"],
        fontSize=10,
        fontName=PDF_FONT,
        spaceAfter=4,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#2c3e50"),
    )
    info = ParagraphStyle("RiskInfo", parent=styles["Normal"], fontSize=9, fontName=PDF_FONT, spaceAfter=2)
    section = ParagraphStyle(
        "RiskSection", parent=styles["Normal"], fontSize=12, fontName=PDF_FONT_BOLD, spaceAfter=6
    )

    elements = [
        Paragraph("RİSK DEĞERLENDİRME RAPORU", title_style),
        Paragraph("6331 Sayılı İş Sağlığı ve Güvenliği Kanunu'na Uygun", subtitle),
        Paragraph(f"Hazırlanma Tarihi: {datetime.now().strftime('%d.%m.%Y')}", subtitle),
        Paragraph(f"Program: {CREATOR_LINE}", subtitle),
        Spacer(1, 8 * mm),
        Paragraph(f"<b>Firma Adı:</b> {company.name}", info),
        Paragraph(f"<b>SGK Sicil No:</b> {sgk_no or '—'}", info),
        Paragraph(f"<b>Yetkili Kişi:</b> {getattr(company, 'authorized_person', None) or '—'}", info),
        Paragraph(f"<b>Telefon:</b> {getattr(company, 'phone', None) or '—'}", info),
        Paragraph(f"<b>Adres:</b> {getattr(company, 'address', None) or '—'}", info),
        Paragraph(f"<b>Tehlike Sınıfı:</b> {getattr(company, 'hazard_class', None) or '—'}", info),
        Paragraph(f"<b>İSG Uzmanı / Hazırlayan:</b> {prepared_by or '—'}", info),
        Paragraph(f"<b>İşyeri Hekimi:</b> {workplace_physician or '—'}", info),
        Paragraph(f"<b>İşveren / Vekili:</b> {employer_representative or '—'}", info),
        Spacer(1, 5 * mm),
    ]

    total = len(risks)
    risk_levels: dict[str, int] = {}
    for r in risks:
        rl = r.risk_level or "Tanımsız"
        risk_levels[rl] = risk_levels.get(rl, 0) + 1

    elements.append(Paragraph("<b>RİSK ÖZETİ</b>", info))
    summary_data = [["Risk Seviyesi", "Adet", "Yüzde"]]
    for level in ["Çok Yüksek", "Yüksek", "Orta", "Düşük", "Kabul Edilebilir"]:
        count = risk_levels.get(level, 0)
        pct = f"{(count / total * 100):.1f}%" if total else "%0"
        summary_data.append([level, str(count), pct])

    summary_table = Table(summary_data, colWidths=[100, 50, 50])
    summary_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), PDF_FONT),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a5276")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (2, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 1), (0, 1), colors.HexColor("#e74c3c")),
                ("BACKGROUND", (0, 2), (0, 2), colors.HexColor("#f39c12")),
                ("BACKGROUND", (0, 3), (0, 3), colors.HexColor("#f1c40f")),
                ("BACKGROUND", (0, 4), (0, 4), colors.HexColor("#2ecc71")),
                ("BACKGROUND", (0, 5), (0, 5), colors.HexColor("#95a5a6")),
            ]
        )
    )
    elements.append(summary_table)
    elements.append(Spacer(1, 8 * mm))
    elements.append(PageBreak())
    elements.append(Paragraph("<b>RİSK DETAY LİSTESİ</b>", section))
    elements.append(Spacer(1, 3 * mm))

    cell = ParagraphStyle("RiskCell", parent=styles["Normal"], fontSize=8, fontName=PDF_FONT, leading=10)

    for risk in risks:
        risk_data = [
            ["Risk Kodu", risk.risk_code],
            ["Bölüm", _dept(risk)],
            ["Faaliyet", Paragraph(str(risk.activity or "—"), cell)],
            ["Tehlike", f"{_hazard_code(risk, hazard_map)} — {_hazard_name(risk, hazard_map)}"],
            ["Risk Tanımı", Paragraph(str(risk.risk_definition or "—"), cell)],
            ["Etkilenenler", risk.affected_people or "—"],
            ["Olasılık", str(risk.probability)],
            ["Şiddet", str(risk.severity)],
            ["Risk Skoru", str(risk.risk_score)],
            ["Risk Seviyesi", risk.risk_level or "—"],
            ["Termin Tarihi", _fmt_date(risk.term_date)],
            ["Durum", risk.status or "Açık"],
            ["DÖF sayısı", str(len(getattr(risk, "dofs", None) or []))],
        ]
        risk_table = Table(risk_data, colWidths=[100, 370])
        bg = _level_color(risk.risk_level or "")
        risk_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), PDF_FONT),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#ecf0f1")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("FONTNAME", (0, 0), (0, -1), PDF_FONT_BOLD),
                    ("BACKGROUND", (1, 8), (1, 9), bg),
                ]
            )
        )
        elements.append(risk_table)
        elements.append(Spacer(1, 2 * mm))

        measures = [
            ["Mevcut Önlemler", Paragraph(str(risk.existing_measures or "—"), cell)],
            ["İlave Önlemler", Paragraph(str(risk.additional_measures or "—"), cell)],
        ]
        measures_table = Table(measures, colWidths=[100, 370])
        measures_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), PDF_FONT),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        elements.append(measures_table)

        dofs = list(getattr(risk, "dofs", None) or [])
        if dofs:
            elements.append(Spacer(1, 2 * mm))
            dof_rows = [["DÖF No", "Yapılacak İş", "Sorumlu", "Termin", "Durum"]]
            for d in dofs:
                dof_rows.append(
                    [
                        d.dof_code,
                        Paragraph(str(d.description or "—")[:200], cell),
                        d.responsible_person or "—",
                        _fmt_date(d.term_date),
                        d.status or "Açık",
                    ]
                )
            dof_table = Table(dof_rows, colWidths=[55, 200, 80, 60, 55])
            dof_table.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (-1, -1), PDF_FONT),
                        ("FONTSIZE", (0, 0), (-1, -1), 7),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#34495e")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                )
            )
            elements.append(dof_table)

        elements.append(Spacer(1, 6 * mm))

    elements.append(PageBreak())
    elements.append(Paragraph("<b>İMZA / ONAY ALANLARI</b>", section))
    elements.append(Spacer(1, 4 * mm))
    sign_data = [
        ["İSG Uzmanı / Hazırlayan", prepared_by or " ", "Kaşe / İmza"],
        ["İşyeri Hekimi", workplace_physician or " ", "Kaşe / İmza"],
        ["İşveren / Vekili", employer_representative or " ", "Kaşe / İmza"],
    ]
    sign_table = Table([["Unvan", "Ad Soyad", "Onay"]] + sign_data, colWidths=[160, 180, 130])
    sign_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), PDF_FONT),
                ("FONTNAME", (0, 0), (-1, 0), PDF_FONT_BOLD),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a5276")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 1), (-1, -1), 14),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 14),
            ]
        )
    )
    elements.append(sign_table)

    doc.build(elements, onFirstPage=_add_pdf_footer, onLaterPages=_add_pdf_footer)
    buf.seek(0)
    return buf.read()


def build_risk_excel(*, company, risks, hazard_map: dict | None = None) -> bytes:
    """Excel: Risk tablosu + DÖF listesi + istatistikler."""
    hazard_map = hazard_map or {}
    wb = openpyxl.Workbook()
    wb.properties.creator = CREATOR_LINE
    wb.properties.title = "İSG Risk Değerlendirme Raporu"

    header_font = Font(name="Calibri", bold=True, size=11, color="FFFFFF")
    header_fill = PatternFill(start_color="1a5276", end_color="1a5276", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )
    level_fills = {
        "Kabul Edilebilir": PatternFill(start_color="95a5a6", end_color="95a5a6", fill_type="solid"),
        "Düşük": PatternFill(start_color="2ecc71", end_color="2ecc71", fill_type="solid"),
        "Orta": PatternFill(start_color="f1c40f", end_color="f1c40f", fill_type="solid"),
        "Yüksek": PatternFill(start_color="f39c12", end_color="f39c12", fill_type="solid"),
        "Çok Yüksek": PatternFill(start_color="e74c3c", end_color="e74c3c", fill_type="solid"),
    }

    ws = wb.active
    ws.title = "Risk Değerlendirme"
    ws.merge_cells("A1:Q1")
    ws["A1"] = f"RİSK DEĞERLENDİRME RAPORU - {company.name}"
    ws["A1"].font = Font(name="Calibri", bold=True, size=14, color="1a5276")
    ws["A1"].alignment = Alignment(horizontal="center")

    ws.merge_cells("A2:Q2")
    ws["A2"] = (
        f"Yetkili: {getattr(company, 'authorized_person', None) or '—'} | "
        f"Tel: {getattr(company, 'phone', None) or '—'} | "
        f"Tehlike Sınıfı: {getattr(company, 'hazard_class', None) or '—'} | "
        f"Tarih: {datetime.now().strftime('%d.%m.%Y')}"
    )
    ws["A2"].font = Font(size=9, color="2c3e50")
    ws["A2"].alignment = Alignment(horizontal="center")

    ws.merge_cells("A3:Q3")
    ws["A3"] = f"Program: {CREATOR_LINE} · 6331 sayılı Kanun kapsamında"
    ws["A3"].font = Font(size=9, italic=True, color="6c757d")
    ws["A3"].alignment = Alignment(horizontal="center")

    headers = [
        "Risk Kodu",
        "Bölüm",
        "Faaliyet",
        "Tehlike",
        "Tehlike Kodu",
        "Risk Tanımı",
        "Etkilenenler",
        "Olasılık (1-5)",
        "Şiddet (1-5)",
        "Risk Skoru",
        "Risk Seviyesi",
        "Termin Tarihi",
        "Mevcut Önlemler",
        "İlave Önlemler",
        "Durum",
        "DÖF Sayısı",
        "Fotoğraf",
    ]
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin

    for idx, risk in enumerate(risks, 5):
        dofs = list(getattr(risk, "dofs", None) or [])
        data = [
            risk.risk_code,
            _dept(risk),
            risk.activity,
            _hazard_name(risk, hazard_map),
            _hazard_code(risk, hazard_map),
            risk.risk_definition,
            risk.affected_people or "—",
            risk.probability,
            risk.severity,
            risk.risk_score,
            risk.risk_level or "—",
            _fmt_date(risk.term_date),
            risk.existing_measures or "—",
            risk.additional_measures or "—",
            risk.status or "Açık",
            len(dofs),
            "",
        ]
        for col, value in enumerate(data, 1):
            cell = ws.cell(row=idx, column=col, value=value)
            cell.border = thin
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            cell.font = Font(size=9)
        level = risk.risk_level or ""
        if level in level_fills:
            ws.cell(row=idx, column=10).fill = level_fills[level]
            ws.cell(row=idx, column=11).fill = level_fills[level]

        photo_path = _risk_excel_photo_path(risk)
        if photo_path:
            try:
                img = XLImage(photo_path)
                max_w, max_h = 140, 95
                if img.width and img.height:
                    ratio = min(max_w / img.width, max_h / img.height, 1)
                    img.width = int(img.width * ratio)
                    img.height = int(img.height * ratio)
                img.anchor = f"Q{idx}"
                ws.add_image(img)
                ws.row_dimensions[idx].height = max(ws.row_dimensions[idx].height or 15, 72)
            except Exception:
                ws.cell(row=idx, column=17, value="Fotoğraf var / eklenemedi")

    for i, w in enumerate([12, 15, 20, 18, 12, 28, 16, 10, 10, 10, 14, 12, 28, 28, 10, 10, 18], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A5"
    ws.auto_filter.ref = f"A4:Q{max(4, 4 + len(risks))}"

    # DÖF sheet
    ws2 = wb.create_sheet("DÖF Listesi")
    dof_headers = [
        "DÖF No",
        "Risk Kodu",
        "Faaliyet",
        "Tehlike",
        "Yapılacak İş",
        "Sorumlu",
        "Sorumlu Bölüm",
        "Termin",
        "Maliyet",
        "Durum",
        "Tamamlanma Notu",
    ]
    for col, header in enumerate(dof_headers, 1):
        cell = ws2.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin

    row = 2
    for risk in risks:
        for dof in getattr(risk, "dofs", None) or []:
            data = [
                dof.dof_code,
                risk.risk_code,
                risk.activity,
                _hazard_name(risk, hazard_map),
                dof.description,
                dof.responsible_person or "—",
                dof.responsible_department or "—",
                _fmt_date(dof.term_date),
                dof.cost_estimate if dof.cost_estimate is not None else "—",
                dof.status or "Açık",
                dof.completion_note or "—",
            ]
            for col, value in enumerate(data, 1):
                cell = ws2.cell(row=row, column=col, value=value)
                cell.border = thin
                cell.font = Font(size=9)
                cell.alignment = Alignment(wrap_text=True)
            row += 1
    for i, w in enumerate([12, 12, 18, 16, 32, 16, 16, 12, 10, 12, 24], 1):
        ws2.column_dimensions[get_column_letter(i)].width = w

    # Stats
    ws3 = wb.create_sheet("İstatistikler")
    ws3.merge_cells("A1:C1")
    ws3["A1"] = "RİSK İSTATİSTİKLERİ"
    ws3["A1"].font = Font(bold=True, size=14, color="1a5276")
    ws3["A3"] = "Risk Seviyesi"
    ws3["B3"] = "Adet"
    ws3["C3"] = "Yüzde"
    for col in ["A3", "B3", "C3"]:
        ws3[col].font = header_font
        ws3[col].fill = header_fill
        ws3[col].border = thin

    risk_levels: dict[str, int] = {}
    for r in risks:
        rl = r.risk_level or "Tanımsız"
        risk_levels[rl] = risk_levels.get(rl, 0) + 1
    total = len(risks)
    for i, level in enumerate(["Çok Yüksek", "Yüksek", "Orta", "Düşük", "Kabul Edilebilir"], 4):
        count = risk_levels.get(level, 0)
        ws3.cell(row=i, column=1, value=level).border = thin
        ws3.cell(row=i, column=2, value=count).border = thin
        ws3.cell(row=i, column=3, value=f"{(count / total * 100):.1f}%" if total else "%0").border = thin

    open_dofs = sum(1 for r in risks for d in (getattr(r, "dofs", None) or []) if not d.is_completed)
    done_dofs = sum(1 for r in risks for d in (getattr(r, "dofs", None) or []) if d.is_completed)
    ws3["A10"] = "Açık DÖF"
    ws3["B10"] = open_dofs
    ws3["A11"] = "Tamamlanan DÖF"
    ws3["B11"] = done_dofs
    ws3.column_dimensions["A"].width = 20
    ws3.column_dimensions["B"].width = 10

    for sheet in wb.worksheets:
        sheet.oddFooter.center.text = CREATOR_LINE
        sheet.oddFooter.right.text = "Sayfa &P / &N"

    out = BytesIO()
    wb.save(out)
    out.seek(0)
    return out.read()
