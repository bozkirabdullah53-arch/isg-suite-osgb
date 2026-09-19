"""İşyeri Durum Merkezi PDF ve Excel çıktıları."""
from __future__ import annotations

from html import escape
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_ASSETS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
PDF_FONT = "Helvetica"
PDF_FONT_BOLD = "Helvetica-Bold"


def _excel_safe(value):
    """Kullanıcı metninin Excel formülü olarak çalışmasını engeller."""
    if value is None:
        return ""
    if not isinstance(value, str):
        return value
    text = value
    if text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def _pdf_text(value) -> str:
    return escape(str(value if value not in (None, "") else "—"))


def _register_fonts() -> None:
    global PDF_FONT, PDF_FONT_BOLD
    regular = _ASSETS / "DejaVuSans.ttf"
    bold = _ASSETS / "DejaVuSans-Bold.ttf"
    if regular.exists():
        pdfmetrics.registerFont(TTFont("StatusDejaVu", str(regular)))
        pdfmetrics.registerFont(TTFont("StatusDejaVu-Bold", str(bold if bold.exists() else regular)))
        PDF_FONT = "StatusDejaVu"
        PDF_FONT_BOLD = "StatusDejaVu-Bold"


def build_workplace_status_excel(payload: dict) -> bytes:
    company = payload.get("company") or {}
    center = payload.get("status_center") or {}
    wb = Workbook()
    ws = wb.active
    ws.title = "Durum Özeti"
    blue = PatternFill("solid", fgColor="0F4C81")
    white_bold = Font(color="FFFFFF", bold=True)

    ws.append(["İŞYERİ DURUM RAPORU", _excel_safe(company.get("name") or "—")])
    ws.append(["SGK Sicil", _excel_safe(company.get("sgk_registry_no") or "—")])
    ws.append(["Genel durum", _excel_safe(center.get("overall_label") or "—")])
    ws.append(["Tamamlanma", f"%{center.get('completion_pct', 0)}"])
    ws.append(["Üretim zamanı (UTC)", center.get("generated_at") or "—"])
    ws.append(["İBYS doğrulama", "Resmî doğrulama bekleniyor — hazır beyanı değildir"])
    for cell in ws[1]:
        cell.fill = blue
        cell.font = white_bold
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 70

    items_ws = wb.create_sheet("Süreç Durumları")
    headers = ["Kod", "Süreç", "Durum", "Detay", "Sorumlu", "Kaynak", "Modül", "Kritik"]
    items_ws.append(headers)
    for cell in items_ws[1]:
        cell.fill = blue
        cell.font = white_bold
    for item in center.get("items") or []:
        items_ws.append([
            _excel_safe(item.get("code")), _excel_safe(item.get("title")),
            _excel_safe(item.get("status_label")), _excel_safe(item.get("detail")),
            _excel_safe(item.get("responsible_role")), _excel_safe(item.get("source")),
            _excel_safe(item.get("module")),
            "Evet" if item.get("critical") else "Hayır",
        ])
    items_ws.freeze_panes = "A2"
    items_ws.auto_filter.ref = items_ws.dimensions
    for width, column in zip((22, 34, 18, 72, 34, 34, 24, 12), "ABCDEFGH"):
        items_ws.column_dimensions[column].width = width
    for row in items_ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    deadline_ws = wb.create_sheet("Terminler")
    headers = ["Kaynak", "Başlık", "Termin", "Kalan Gün", "Durum", "Sorumlu", "Modül"]
    deadline_ws.append(headers)
    for cell in deadline_ws[1]:
        cell.fill = blue
        cell.font = white_bold
    for item in center.get("deadlines") or []:
        deadline_ws.append([
            _excel_safe(item.get("source")), _excel_safe(item.get("title")),
            _excel_safe(item.get("due_date")), item.get("days_left"),
            _excel_safe(item.get("status")), _excel_safe(item.get("responsible_role")),
            _excel_safe(item.get("module")),
        ])
    deadline_ws.freeze_panes = "A2"
    deadline_ws.auto_filter.ref = deadline_ws.dimensions
    for width, column in zip((24, 54, 15, 14, 16, 34, 24), "ABCDEFG"):
        deadline_ws.column_dimensions[column].width = width
    for row in deadline_ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    stream = BytesIO()
    wb.save(stream)
    return stream.getvalue()


def build_workplace_status_pdf(payload: dict) -> bytes:
    _register_fonts()
    company = payload.get("company") or {}
    center = payload.get("status_center") or {}
    stream = BytesIO()
    doc = SimpleDocTemplate(
        stream,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=f"İşyeri Durum Raporu - {company.get('name') or ''}",
        author="İSG Suite",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "StatusTitle", parent=styles["Title"], fontName=PDF_FONT_BOLD, fontSize=18,
        textColor=colors.HexColor("#0F4C81"), spaceAfter=6,
    )
    normal = ParagraphStyle("StatusNormal", parent=styles["BodyText"], fontName=PDF_FONT, fontSize=8.2, leading=10)
    small = ParagraphStyle("StatusSmall", parent=normal, fontSize=7.2, leading=9)
    story = [
        Paragraph("İŞYERİ DURUM RAPORU", title_style),
        Paragraph(
            f"<b>{_pdf_text(company.get('name'))}</b> · SGK Sicil: {_pdf_text(company.get('sgk_registry_no'))} · "
            f"Genel durum: <b>{_pdf_text(center.get('overall_label'))}</b> · Tamamlanma: <b>%{int(center.get('completion_pct') or 0)}</b>",
            normal,
        ),
        Spacer(1, 5 * mm),
    ]
    rows = [["Süreç", "Durum", "Detay", "Sorumlu", "Kaynak / Modül"]]
    for item in center.get("items") or []:
        rows.append([
            Paragraph(_pdf_text(item.get("title")), small),
            Paragraph(_pdf_text(item.get("status_label")), small),
            Paragraph(_pdf_text(item.get("detail")), small),
            Paragraph(_pdf_text(item.get("responsible_role")), small),
            Paragraph(f"{_pdf_text(item.get('source'))} / {_pdf_text(item.get('module'))}", small),
        ])
    table = Table(rows, colWidths=[42 * mm, 25 * mm, 88 * mm, 53 * mm, 58 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F4C81")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), PDF_FONT_BOLD),
        ("FONTNAME", (0, 1), (-1, -1), PDF_FONT),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.extend([table, Spacer(1, 5 * mm)])

    deadlines = center.get("deadlines") or []
    if deadlines:
        story.append(Paragraph("Yaklaşan ve gecikmiş terminler", title_style))
        deadline_rows = [["Kaynak", "Başlık", "Termin", "Kalan gün", "Sorumlu"]]
        for item in deadlines[:40]:
            deadline_rows.append([
                Paragraph(_pdf_text(item.get("source")), small),
                Paragraph(_pdf_text(item.get("title")), small),
                item.get("due_date") or "—",
                str(item.get("days_left") if item.get("days_left") is not None else "—"),
                Paragraph(_pdf_text(item.get("responsible_role")), small),
            ])
        deadline_table = Table(deadline_rows, colWidths=[38 * mm, 95 * mm, 28 * mm, 25 * mm, 80 * mm], repeatRows=1)
        deadline_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), PDF_FONT_BOLD),
            ("FONTNAME", (0, 1), (-1, -1), PDF_FONT),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("FONTSIZE", (0, 0), (-1, -1), 7.2),
        ]))
        story.append(deadline_table)

    story.extend([
        Spacer(1, 5 * mm),
        Paragraph(
            "Gizlilik: Sağlık verileri yalnız anonim toplamlar olarak gösterilir. Bu rapor resmî İBYS uygunluk onayı veya “İBYS Ready” beyanı değildir; resmî doğrulama ve kabul beklenmektedir.",
            small,
        ),
    ])
    doc.build(story)
    return stream.getvalue()


def _money(value) -> str:
    try:
        return f"{int(value or 0):,}".replace(",", ".") + " TL"
    except (TypeError, ValueError):
        return "—"


def _pdf_paragraph(value, style) -> Paragraph:
    return Paragraph(_pdf_text(value), style)


def _report_table(rows, widths, *, header_color="#0F4C81", font_size=7.4):
    table = Table(rows, colWidths=[width * mm for width in widths], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_color)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), PDF_FONT_BOLD),
        ("FONTNAME", (0, 1), (-1, -1), PDF_FONT),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _add_excel_sheet(wb, title, headers, rows, widths=None):
    ws = wb.create_sheet(title[:31])
    blue = PatternFill("solid", fgColor="0F4C81")
    white_bold = Font(color="FFFFFF", bold=True)
    ws.append([_excel_safe(value) for value in headers])
    for cell in ws[1]:
        cell.fill = blue
        cell.font = white_bold
        cell.alignment = Alignment(vertical="top", wrap_text=True)
    for row in rows:
        ws.append([_excel_safe(value) for value in row])
    if not rows:
        ws.append(["Kayıt yok."] + [""] * max(0, len(headers) - 1))
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for index, width in enumerate(widths or [22] * len(headers), start=1):
        ws.column_dimensions[chr(64 + index) if index <= 26 else f"A{index}"].width = width
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    return ws


def build_company_file_excel(payload: dict) -> bytes:
    """Tam Firma Dosyası — filtrelenebilir, bölümlere ayrılmış Excel çıktısı."""
    company = payload.get("company") or {}
    report = payload.get("report") or {}
    center = payload.get("status_center") or {}
    wb = Workbook()
    cover = wb.active
    cover.title = "Kapak ve Özet"
    blue = PatternFill("solid", fgColor="0F4C81")
    teal = PatternFill("solid", fgColor="0F766E")
    white_bold = Font(color="FFFFFF", bold=True)
    cover.append([_excel_safe(report.get("title") or "TAM FİRMA DOSYASI"), _excel_safe(company.get("name"))])
    cover.append(["Rapor tarihi", _excel_safe(report.get("as_of_date"))])
    cover.append(["Oluşturulma zamanı", _excel_safe(report.get("generated_at"))])
    cover.append(["Genel durum", _excel_safe(center.get("overall_label"))])
    cover.append(["Tamamlanma", f"%{int(center.get('completion_pct') or 0)}"])
    cover.append(["Ticari detaylar", "Açık" if report.get("commercial_details_visible") else "Yetki kapsamı dışında"])
    cover.append(["Gizlilik", "Sağlık verileri yalnız toplu/anonim gösterilir."])
    for cell in cover[1]:
        cell.fill = blue
        cell.font = white_bold
    cover.column_dimensions["A"].width = 28
    cover.column_dimensions["B"].width = 78
    for row in cover.iter_rows():
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    _add_excel_sheet(
        wb,
        "Firma Kimliği",
        ["Alan", "Değer"],
        [
            ["Firma", company.get("name")],
            ["Vergi No", company.get("tax_number")],
            ["SGK Sicil No", company.get("sgk_registry_no")],
            ["NACE Kodu", company.get("nace_code")],
            ["Tehlike Sınıfı", company.get("hazard_class")],
            ["Yetkili", company.get("authorized_person")],
            ["Telefon", company.get("phone")],
            ["Adres", company.get("address")],
            ["Risk Değerlendirmesi Tarihi", company.get("risk_assessment_date")],
            ["Risk Doküman No", company.get("risk_document_no")],
            ["OSGB", (payload.get("osgb_profile") or {}).get("name")],
            ["OSGB Yetki No", (payload.get("osgb_profile") or {}).get("authorization_number")],
            ["OSGB Sorumlusu", (payload.get("osgb_profile") or {}).get("responsible_manager")],
        ],
        [32, 80],
    )

    workforce = payload.get("workforce") or {}
    _add_excel_sheet(
        wb,
        "İşgücü Özeti",
        ["Bölüm", "Ad", "Toplam", "Aktif"],
        [["Genel", "Tüm çalışanlar", workforce.get("total", 0), workforce.get("active", 0)]]
        + [["Şube", row.get("name"), row.get("total"), row.get("active")] for row in workforce.get("by_branch") or []]
        + [["Departman", row.get("name"), row.get("count"), "—"] for row in workforce.get("by_department") or []],
        [18, 55, 14, 14],
    )

    _add_excel_sheet(
        wb,
        "Şubeler",
        ["Şube", "SGK Sicil", "İl", "Adres", "Durum"],
        [
            [row.get("name"), row.get("sgk_registry_no"), row.get("city"), row.get("address"), "Aktif" if row.get("is_active") else "Pasif"]
            for row in payload.get("branches") or []
        ],
        [30, 22, 18, 65, 14],
    )

    contracts = payload.get("contracts") or []
    if report.get("commercial_details_visible"):
        _add_excel_sheet(
            wb,
            "OSGB Sözleşmeleri",
            ["Sözleşme No", "Başlangıç", "Bitiş", "Kalan Gün", "Aylık Ücret", "Durum"],
            [[row.get("contract_number"), row.get("start_date"), row.get("end_date"), row.get("days_left"), _money(row.get("monthly_fee")), row.get("status")] for row in contracts],
            [25, 15, 15, 14, 20, 16],
        )
        _add_excel_sheet(
            wb,
            "Sözleşme Belgeleri",
            ["Görevlendirme", "Profesyonel Türü", "Dosya", "İçerik Türü", "Dosya Durumu"],
            [[row.get("assignment_id"), row.get("professional_type"), row.get("file_name"), row.get("content_type"), "Mevcut" if row.get("has_file") else "Yok"] for row in payload.get("assignment_contract_files") or []],
            [18, 28, 48, 28, 18],
        )

        finance = payload.get("finance") or {}
        summary = finance.get("summary") or {}
        _add_excel_sheet(
            wb,
            "Cari Özet",
            ["Gösterge", "Tutar"],
            [
                ["Toplam tahakkuk / gelir", _money(summary.get("income_accrued"))],
                ["Tahsil edilen", _money(summary.get("income_paid"))],
                ["OSGB alacağı", _money(summary.get("receivable"))],
                ["Vadesi geçmiş alacak", _money(summary.get("overdue_receivable"))],
                ["Yaklaşan alacak", _money(summary.get("due_soon_receivable"))],
                ["Toplam gider", _money(summary.get("expense_total"))],
                ["Ödenen gider", _money(summary.get("expense_paid"))],
                ["Net ödenen", _money(summary.get("net_paid"))],
                ["Net pozisyon", _money(summary.get("net_position"))],
            ],
            [38, 32],
        )
        _add_excel_sheet(
            wb,
            "Finans İşlemleri",
            ["Tarih", "Tür", "Kategori", "Tutar", "Durum", "Vade", "Açıklama"],
            [[row.get("transaction_date"), row.get("transaction_type_label"), row.get("category"), _money(row.get("amount")), row.get("status_label"), row.get("due_date"), row.get("description")] for row in finance.get("transactions") or []],
            [15, 14, 24, 18, 18, 15, 60],
        )
        _add_excel_sheet(
            wb,
            "Aylık Finans",
            ["Ay", "Gelir", "Gider", "Net Ödenen"],
            [[row.get("month"), _money(row.get("income")), _money(row.get("expense")), _money(row.get("net_paid"))] for row in finance.get("monthly") or []],
            [15, 22, 22, 22],
        )

    _add_excel_sheet(
        wb,
        "Belge Envanteri",
        ["Kategori", "Belge", "Dosya", "Geçerlilik Başlangıcı", "Geçerlilik Sonu", "Versiyon", "Durum"],
        [[row.get("category"), row.get("title"), row.get("file_name"), row.get("valid_from"), row.get("valid_until"), row.get("version"), "Aktif" if row.get("is_active") else "Pasif"] for row in payload.get("documents") or []],
        [18, 48, 42, 22, 22, 14, 14],
    )
    _add_excel_sheet(
        wb,
        "Süreç Durumları",
        ["Kod", "Süreç", "Durum", "Detay", "Sorumlu", "Kaynak", "Modül", "Kritik"],
        [[row.get("code"), row.get("title"), row.get("status_label"), row.get("detail"), row.get("responsible_role"), row.get("source"), row.get("module"), "Evet" if row.get("critical") else "Hayır"] for row in center.get("items") or []],
        [22, 34, 18, 72, 34, 34, 24, 12],
    )
    _add_excel_sheet(
        wb,
        "Terminler",
        ["Kaynak", "Başlık", "Termin", "Kalan Gün", "Durum", "Sorumlu", "Modül"],
        [[row.get("source"), row.get("title"), row.get("due_date"), row.get("days_left"), row.get("status"), row.get("responsible_role"), row.get("module")] for row in center.get("deadlines") or []],
        [24, 54, 15, 14, 16, 34, 24],
    )
    _add_excel_sheet(
        wb,
        "Son Ziyaretler",
        ["Tarih", "Profesyonel", "Konu", "Süre (dk)", "Durum"],
        [[row.get("visit_date"), row.get("professional_name"), row.get("subject"), row.get("duration_minutes"), row.get("status")] for row in payload.get("visits") or []],
        [15, 32, 68, 15, 16],
    )
    _add_excel_sheet(
        wb,
        "Son Olaylar",
        ["Form", "Tür", "Özet", "Tarih", "Durum"],
        [[row.get("form_no"), row.get("event_type"), row.get("summary"), row.get("event_date"), row.get("status")] for row in payload.get("incidents") or []],
        [18, 18, 80, 15, 18],
    )

    # Teal rengi en az bir hücrede kullanarak özet sayfasını görsel olarak
    # raporun diğer sekmelerinden ayırır; veri ve formül davranışına etkisi yoktur.
    cover["A1"].fill = teal
    stream = BytesIO()
    wb.save(stream)
    return stream.getvalue()


def build_company_file_pdf(payload: dict) -> bytes:
    """A4 kurumsal Tam Firma Dosyası PDF'i."""
    _register_fonts()
    company = payload.get("company") or {}
    center = payload.get("status_center") or {}
    report = payload.get("report") or {}
    stream = BytesIO()
    doc = SimpleDocTemplate(
        stream,
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=14 * mm,
        bottomMargin=17 * mm,
        title=f"Tam Firma Dosyası - {company.get('name') or ''}",
        author="İSG Suite",
    )
    styles = getSampleStyleSheet()
    cover_title = ParagraphStyle("CompanyFileCover", parent=styles["Title"], fontName=PDF_FONT_BOLD, fontSize=25, leading=30, textColor=colors.HexColor("#0F4C81"), alignment=TA_CENTER, spaceAfter=8)
    section = ParagraphStyle("CompanyFileSection", parent=styles["Heading2"], fontName=PDF_FONT_BOLD, fontSize=14, leading=17, textColor=colors.HexColor("#0F4C81"), spaceBefore=4, spaceAfter=7)
    normal = ParagraphStyle("CompanyFileNormal", parent=styles["BodyText"], fontName=PDF_FONT, fontSize=8.5, leading=11, textColor=colors.HexColor("#334155"))
    small = ParagraphStyle("CompanyFileSmall", parent=normal, fontSize=7.2, leading=9)
    label = ParagraphStyle("CompanyFileLabel", parent=normal, fontName=PDF_FONT_BOLD, fontSize=7.4, textColor=colors.HexColor("#64748B"))
    value = ParagraphStyle("CompanyFileValue", parent=normal, fontSize=8.5, leading=11)
    big_value = ParagraphStyle("CompanyFileBigValue", parent=normal, fontName=PDF_FONT_BOLD, fontSize=14, leading=16, textColor=colors.HexColor("#0F766E"), alignment=TA_CENTER)

    def footer(canvas, current_doc):
        canvas.saveState()
        width, _ = A4
        canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
        canvas.line(12 * mm, 12 * mm, width - 12 * mm, 12 * mm)
        canvas.setFont(PDF_FONT, 7)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(12 * mm, 7 * mm, "İSG Suite · Tam Firma Dosyası · Yetkili kullanım")
        canvas.drawRightString(width - 12 * mm, 7 * mm, f"Sayfa {current_doc.page}")
        canvas.restoreState()

    story = [
        Spacer(1, 28 * mm),
        Paragraph("İSG SUITE OSGB", ParagraphStyle("Brand", parent=normal, fontName=PDF_FONT_BOLD, fontSize=10, textColor=colors.HexColor("#0F766E"), alignment=TA_CENTER, spaceAfter=12)),
        Paragraph("TAM FİRMA DOSYASI", cover_title),
        Paragraph(_pdf_text(company.get("name")), ParagraphStyle("CompanyName", parent=cover_title, fontSize=18, leading=22, textColor=colors.HexColor("#0F172A"))),
        Spacer(1, 10 * mm),
        _report_table([
            ["Rapor tarihi", _pdf_text(report.get("as_of_date")), "Genel durum", _pdf_text(center.get("overall_label"))],
            ["Tamamlanma", f"%{int(center.get('completion_pct') or 0)}", "Rapor kapsamı", "Ticari + operasyonel" if report.get("commercial_details_visible") else "Operasyonel görünüm"],
        ], [31, 55, 31, 55], font_size=8.2),
        Spacer(1, 12 * mm),
        Paragraph("Bu rapor mevcut uygulama kayıtlarının rapor tarihi itibarıyla salt okunur bir fotoğrafıdır. Sağlık bilgileri kişi, tanı ve hekim notu içermeyen toplu göstergeler olarak sunulmuştur.", normal),
        PageBreak(),
        Paragraph("Yönetici Özeti", section),
    ]

    summary = center.get("summary") or {}
    metrics = [
        ("Tamamlanan", summary.get("completed", 0)),
        ("Eksik", summary.get("missing", 0)),
        ("Gecikmiş", summary.get("overdue", 0)),
        ("Yaklaşan", summary.get("due_soon", 0)),
    ]
    story.append(Table(
        [[Paragraph(_pdf_text(label_text), label) for label_text, _ in metrics], [Paragraph(_pdf_text(number), big_value) for _, number in metrics]],
        colWidths=[46.5 * mm] * 4,
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0FDFA")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#99F6E4")),
            ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CCFBF1")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]),
    ))
    story.append(Spacer(1, 7 * mm))

    story.append(Paragraph("Firma Kimliği", section))
    identity_rows = [
        [_pdf_paragraph("Firma", label), _pdf_paragraph(company.get("name"), value), _pdf_paragraph("Vergi No", label), _pdf_paragraph(company.get("tax_number"), value)],
        [_pdf_paragraph("SGK Sicil No", label), _pdf_paragraph(company.get("sgk_registry_no"), value), _pdf_paragraph("NACE Kodu", label), _pdf_paragraph(company.get("nace_code"), value)],
        [_pdf_paragraph("Tehlike Sınıfı", label), _pdf_paragraph(company.get("hazard_class"), value), _pdf_paragraph("Yetkili", label), _pdf_paragraph(company.get("authorized_person"), value)],
        [_pdf_paragraph("Telefon", label), _pdf_paragraph(company.get("phone"), value), _pdf_paragraph("Durum", label), _pdf_paragraph("Aktif" if company.get("is_active") else "Pasif", value)],
        [_pdf_paragraph("Adres", label), _pdf_paragraph(company.get("address"), value), _pdf_paragraph("OSGB", label), _pdf_paragraph((payload.get("osgb_profile") or {}).get("name"), value)],
        [_pdf_paragraph("OSGB Yetki No", label), _pdf_paragraph((payload.get("osgb_profile") or {}).get("authorization_number"), value), _pdf_paragraph("OSGB Sorumlusu", label), _pdf_paragraph((payload.get("osgb_profile") or {}).get("responsible_manager"), value)],
    ]
    identity_table = Table(identity_rows, colWidths=[27 * mm, 66 * mm, 27 * mm, 66 * mm])
    identity_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F8FAFC")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#F8FAFC")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.extend([identity_table, Spacer(1, 7 * mm)])

    if report.get("commercial_details_visible"):
        finance = payload.get("finance") or {}
        fs = finance.get("summary") or {}
        story.append(Paragraph("Cari ve Finans Özeti", section))
        finance_rows = [
            ["Gösterge", "Tutar", "Gösterge", "Tutar"],
            ["OSGB alacağı", _money(fs.get("receivable")), "Vadesi geçmiş", _money(fs.get("overdue_receivable"))],
            ["Tahsil edilen", _money(fs.get("income_paid")), "Yaklaşan alacak", _money(fs.get("due_soon_receivable"))],
            ["Toplam gider", _money(fs.get("expense_total")), "Net ödenen", _money(fs.get("net_paid"))],
        ]
        story.append(_report_table(finance_rows, [31, 55, 31, 55], header_color="#0F766E", font_size=8.2))
        story.append(Spacer(1, 5 * mm))

        story.append(Paragraph("OSGB Sözleşmeleri", section))
        contract_rows = [["Sözleşme No", "Başlangıç", "Bitiş", "Kalan", "Aylık Ücret", "Durum"]]
        for row in payload.get("contracts") or []:
            contract_rows.append([
                _pdf_paragraph(row.get("contract_number"), small),
                _pdf_paragraph(row.get("start_date"), small),
                _pdf_paragraph(row.get("end_date"), small),
                _pdf_paragraph(row.get("days_left"), small),
                _pdf_paragraph(_money(row.get("monthly_fee")), small),
                _pdf_paragraph(row.get("status"), small),
            ])
        if len(contract_rows) == 1:
            contract_rows.append([_pdf_paragraph("Kayıt yok.", small), "", "", "", "", ""])
        story.append(_report_table(contract_rows, [32, 28, 28, 18, 34, 46], font_size=7.2))
        assignment_file_rows = [["Görevlendirme", "Profesyonel Türü", "Dosya", "İçerik Türü", "Durum"]]
        for row in payload.get("assignment_contract_files") or []:
            assignment_file_rows.append([
                _pdf_paragraph(row.get("assignment_id"), small),
                _pdf_paragraph(row.get("professional_type"), small),
                _pdf_paragraph(row.get("file_name"), small),
                _pdf_paragraph(row.get("content_type"), small),
                _pdf_paragraph("Mevcut" if row.get("has_file") else "Yok", small),
            ])
        if len(assignment_file_rows) > 1:
            story.append(Spacer(1, 4 * mm))
            story.append(Paragraph("Görevlendirme Sözleşme Belgeleri", section))
            story.append(_report_table(assignment_file_rows, [25, 39, 55, 39, 28], header_color="#334155", font_size=6.9))
        story.append(PageBreak())

        story.append(Paragraph("Finans İşlemleri", section))
        transaction_rows = [["Tarih", "Tür / Kategori", "Tutar", "Durum / Vade", "Açıklama"]]
        for row in finance.get("transactions") or []:
            transaction_rows.append([
                _pdf_paragraph(row.get("transaction_date"), small),
                _pdf_paragraph(f"{row.get('transaction_type_label')} · {row.get('category') or '—'}", small),
                _pdf_paragraph(_money(row.get("amount")), small),
                _pdf_paragraph(f"{row.get('status_label')} · {row.get('due_date') or 'Vade yok'}", small),
                _pdf_paragraph(row.get("description"), small),
            ])
        if len(transaction_rows) == 1:
            transaction_rows.append([_pdf_paragraph("Kayıt yok.", small), "", "", "", ""])
        story.append(_report_table(transaction_rows, [26, 43, 29, 43, 45], font_size=6.9))
        story.append(PageBreak())

    story.append(Paragraph("Şubeler ve İşgücü Özeti", section))
    workforce = payload.get("workforce") or {}
    story.append(_report_table([
        ["Gösterge", "Değer", "Gösterge", "Değer", "Gösterge", "Değer"],
        ["Toplam çalışan", workforce.get("total", 0), "Aktif", workforce.get("active", 0), "Pasif", workforce.get("inactive", 0)],
    ], [30, 31, 22, 31, 22, 50], header_color="#334155", font_size=8.2))
    story.append(Spacer(1, 4 * mm))
    branch_rows = [["Şube", "SGK Sicil", "İl", "Adres", "Durum"]]
    for row in payload.get("branches") or []:
        branch_rows.append([_pdf_paragraph(row.get("name"), small), _pdf_paragraph(row.get("sgk_registry_no"), small), _pdf_paragraph(row.get("city"), small), _pdf_paragraph(row.get("address"), small), _pdf_paragraph("Aktif" if row.get("is_active") else "Pasif", small)])
    if len(branch_rows) == 1:
        branch_rows.append([_pdf_paragraph("Şube kaydı yok.", small), "", "", "", ""])
    story.append(_report_table(branch_rows, [32, 27, 22, 83, 22], font_size=7.1))
    story.append(Spacer(1, 7 * mm))

    story.append(Paragraph("Belge Envanteri", section))
    document_rows = [["Kategori", "Belge", "Dosya", "Geçerlilik", "Durum"]]
    for row in payload.get("documents") or []:
        validity = f"{row.get('valid_from') or '—'} → {row.get('valid_until') or '—'}"
        document_rows.append([_pdf_paragraph(row.get("category"), small), _pdf_paragraph(row.get("title"), small), _pdf_paragraph(row.get("file_name"), small), _pdf_paragraph(validity, small), _pdf_paragraph("Aktif" if row.get("is_active") else "Pasif", small)])
    if len(document_rows) == 1:
        document_rows.append([_pdf_paragraph("Belge kaydı yok.", small), "", "", "", ""])
    story.append(_report_table(document_rows, [25, 52, 42, 43, 24], font_size=6.9))
    story.append(PageBreak())

    story.append(Paragraph("İSG Süreçleri ve Terminler", section))
    status_rows = [["Süreç", "Durum", "Gerçek veri sonucu", "Sorumlu", "Modül"]]
    for row in center.get("items") or []:
        status_rows.append([_pdf_paragraph(row.get("title"), small), _pdf_paragraph(row.get("status_label"), small), _pdf_paragraph(row.get("detail"), small), _pdf_paragraph(row.get("responsible_role"), small), _pdf_paragraph(row.get("module"), small)])
    if len(status_rows) == 1:
        status_rows.append([_pdf_paragraph("Süreç kaydı yok.", small), "", "", "", ""])
    story.append(_report_table(status_rows, [39, 22, 65, 40, 20], font_size=6.8))
    story.append(Spacer(1, 6 * mm))

    deadline_rows = [["Kaynak", "Başlık", "Termin", "Kalan", "Sorumlu"]]
    for row in (center.get("deadlines") or [])[:100]:
        deadline_rows.append([_pdf_paragraph(row.get("source"), small), _pdf_paragraph(row.get("title"), small), _pdf_paragraph(row.get("due_date"), small), _pdf_paragraph(row.get("days_left"), small), _pdf_paragraph(row.get("responsible_role"), small)])
    if len(deadline_rows) == 1:
        deadline_rows.append([_pdf_paragraph("Termin kaydı yok.", small), "", "", "", ""])
    story.append(Paragraph("Termin Takvimi", section))
    story.append(_report_table(deadline_rows, [29, 70, 25, 18, 44], header_color="#334155", font_size=6.9))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Gizlilik: Sağlık verileri kişi, tanı, tetkik ve hekim notu içermeden toplu olarak gösterilir. Bu çıktı resmî İBYS uygunluk onayı veya “İBYS Ready” beyanı değildir.", small))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return stream.getvalue()
