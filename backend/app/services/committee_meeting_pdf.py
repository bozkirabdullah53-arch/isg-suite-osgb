"""Professional A4 OHS committee meeting PDF.

Uses only persisted meeting/member snapshots. It never marks a signature completed
unless the saved signature status says so.
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

_FONT = "Helvetica"
_FONT_B = "Helvetica-Bold"


def _ensure_fonts() -> None:
    global _FONT, _FONT_B
    regular = [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
    ]
    bold = [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
        Path(r"C:\Windows\Fonts\arialbd.ttf"),
    ]
    for path in regular:
        if path.is_file():
            if "CommitteeTR" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("CommitteeTR", str(path)))
            _FONT = "CommitteeTR"
            break
    for path in bold:
        if path.is_file():
            if "CommitteeTR-B" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("CommitteeTR-B", str(path)))
            _FONT_B = "CommitteeTR-B"
            break
    if _FONT == "CommitteeTR" and _FONT_B == "Helvetica-Bold":
        _FONT_B = _FONT


def _p(value, style):
    return Paragraph(escape(str(value or "—")).replace("\n", "<br/>"), style)


def build_committee_meeting_pdf(*, company: dict, meeting: dict, members: list[dict]) -> bytes:
    _ensure_fonts()
    buf = BytesIO()
    page_w, page_h = A4
    margin = 16 * mm
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("normal-tr", parent=styles["BodyText"], fontName=_FONT, fontSize=8.5, leading=11, textColor=colors.HexColor("#1f2937"))
    small = ParagraphStyle("small-tr", parent=normal, fontSize=7, leading=9)
    heading = ParagraphStyle("heading-tr", parent=normal, fontName=_FONT_B, fontSize=11, leading=14, textColor=colors.HexColor("#0f3d63"), spaceBefore=6, spaceAfter=5)
    title = ParagraphStyle("title-tr", parent=heading, fontSize=15, leading=18, alignment=TA_CENTER)
    center = ParagraphStyle("center-tr", parent=normal, alignment=TA_CENTER)
    label = ParagraphStyle("label-tr", parent=small, fontName=_FONT_B, textColor=colors.HexColor("#334155"))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#cbd5e1"))
        canvas.line(margin, 12 * mm, page_w - margin, 12 * mm)
        canvas.setFont(_FONT, 6.8)
        footer_text = f"İSG Kurulu Toplantı Tutanağı | {company.get('name') or '—'} | Belge No: {meeting.get('document_no') or '—'} | Rev: {meeting.get('revision_no') or '00'}"
        canvas.drawString(margin, 8 * mm, footer_text[:125])
        canvas.drawRightString(page_w - margin, 8 * mm, f"Sayfa {doc.page}")
        canvas.restoreState()

    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=15 * mm,
        bottomMargin=18 * mm,
        title=f"İSG Kurulu Toplantı Tutanağı - {meeting.get('meeting_no') or meeting.get('id')}",
        author="İSG Suite OSGB",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates(PageTemplate(id="committee", frames=[frame], onPage=footer))

    story = []
    header = Table(
        [[
            _p(company.get("name") or "İşyeri", heading),
            _p("İŞ SAĞLIĞI VE GÜVENLİĞİ KURULU<br/>TOPLANTI TUTANAĞI", title),
            Table([
                [_p("Belge No", label), _p(meeting.get("document_no"), small)],
                [_p("Toplantı No", label), _p(meeting.get("meeting_no"), small)],
                [_p("Revizyon", label), _p(meeting.get("revision_no") or "00", small)],
                [_p("Oluşturma", label), _p(datetime.now().strftime("%d.%m.%Y"), small)],
            ], colWidths=[22*mm, 25*mm])
        ]],
        colWidths=[45*mm, 82*mm, 49*mm],
    )
    header.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 0.8, colors.HexColor("#64748b")),
        ("INNERGRID", (0,0), (-1,-1), 0.35, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("BACKGROUND", (1,0), (1,0), colors.HexColor("#eef6fb")),
        ("LEFTPADDING", (0,0), (-1,-1), 5),
        ("RIGHTPADDING", (0,0), (-1,-1), 5),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    story += [header, Spacer(1, 7)]

    info_rows = [
        ["İşyeri", company.get("name"), "Adres", company.get("address")],
        ["Toplantı tarihi", meeting.get("meeting_date"), "Saat", f"{meeting.get('start_time') or '—'} - {meeting.get('end_time') or '—'}"],
        ["Toplantı yeri", meeting.get("location"), "Toplantı türü", meeting.get("meeting_type") or "Olağan"],
        ["Durum", meeting.get("status") or "draft", "İmza durumu", meeting.get("signature_status") or "not_signed"],
        ["Sonraki toplantı", meeting.get("next_meeting_date"), "Üye sayısı", len(members)],
    ]
    info = Table([[ _p(c, label if i % 2 == 0 else normal) for i, c in enumerate(row)] for row in info_rows], colWidths=[31*mm, 57*mm, 31*mm, 57*mm], repeatRows=0)
    info.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 0.6, colors.HexColor("#94a3b8")),
        ("INNERGRID", (0,0), (-1,-1), 0.3, colors.HexColor("#cbd5e1")),
        ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#f1f5f9")),
        ("BACKGROUND", (2,0), (2,-1), colors.HexColor("#f1f5f9")),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("PADDING", (0,0), (-1,-1), 4),
    ]))
    story += [info, Spacer(1, 7), Paragraph("Kurul Üyeleri ve Katılım", heading)]

    participant_data = [[_p("#", label), _p("Ad Soyad", label), _p("Görevi / Unvanı", label), _p("Kurul Rolü", label), _p("Katılım", label), _p("İmza", label)]]
    seen = set()
    unique_members = []
    for member in members:
        key = member.get("identity_key") or f"legacy:{str(member.get('full_name') or '').strip().casefold()}"
        if key in seen:
            continue
        seen.add(key)
        unique_members.append(member)
    for idx, member in enumerate(unique_members, 1):
        participant_data.append([
            _p(idx, center),
            _p(member.get("full_name"), normal),
            _p(member.get("job_title") or member.get("professional_role"), normal),
            _p(member.get("role_label") or member.get("role_code"), normal),
            _p(member.get("attendance_status") or "Belirtilmedi", center),
            _p(member.get("signature_status") or "İmzalanmadı", center),
        ])
    participants = Table(participant_data, colWidths=[8*mm, 40*mm, 42*mm, 36*mm, 25*mm, 25*mm], repeatRows=1)
    participants.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 0.6, colors.HexColor("#64748b")),
        ("INNERGRID", (0,0), (-1,-1), 0.25, colors.HexColor("#cbd5e1")),
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#dbeafe")),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("PADDING", (0,0), (-1,-1), 4),
    ]))
    story += [participants, Spacer(1, 7)]

    story += [Paragraph("Gündem", heading), _p(meeting.get("agenda") or "Gündem kaydı bulunmuyor.", normal), Spacer(1, 6)]
    story += [Paragraph("Kararlar ve Takip", heading), _p(meeting.get("decisions") or "Karar kaydı bulunmuyor.", normal), Spacer(1, 6)]
    if meeting.get("notes"):
        story += [Paragraph("Notlar", heading), _p(meeting.get("notes"), normal), Spacer(1, 8)]

    story.append(Paragraph("İmzalar", heading))
    story.append(_p("Aşağıdaki alanlar ıslak imza için ayrılmıştır. Elektronik imza durumu yalnız tamamlanmış kayıt varsa gösterilir.", small))
    story.append(Spacer(1, 5))
    signature_cards = []
    for member in unique_members:
        status = member.get("signature_status") or "İmzalanmadı"
        signed_at = member.get("signed_at") or "—"
        card = Table([
            [_p(member.get("full_name"), ParagraphStyle("sig-name", parent=center, fontName=_FONT_B, fontSize=8.5))],
            [_p(member.get("job_title") or member.get("professional_role"), center)],
            [_p(member.get("role_label") or member.get("role_code"), center)],
            [Spacer(1, 20*mm)],
            [_p(f"İmza Durumu: {status}", small)],
            [_p(f"İmza Tarihi: {signed_at}", small)],
        ], colWidths=[54*mm], rowHeights=[None, None, None, 20*mm, None, None])
        card.setStyle(TableStyle([
            ("BOX", (0,0), (-1,-1), 0.6, colors.HexColor("#94a3b8")),
            ("BACKGROUND", (0,0), (-1,2), colors.HexColor("#f8fafc")),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("ALIGN", (0,0), (-1,3), "CENTER"),
            ("PADDING", (0,0), (-1,-1), 4),
        ]))
        signature_cards.append(card)
    for i in range(0, len(signature_cards), 3):
        row = signature_cards[i:i+3]
        while len(row) < 3:
            row.append(Spacer(54*mm, 1))
        story.append(KeepTogether(Table([row], colWidths=[58*mm, 58*mm, 58*mm], style=TableStyle([("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 2), ("RIGHTPADDING", (0,0), (-1,-1), 2)]))))
        story.append(Spacer(1, 5))

    doc.build(story)
    return buf.getvalue()
