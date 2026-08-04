"""Yayımlanmış soru bankası snapshot'ından 15 soruluk denetlenebilir sınav PDF'i üretir."""
from __future__ import annotations

import json
from datetime import datetime
from io import BytesIO
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import TrainingExamSnapshot
from app.services.training_question_bank import create_exam_snapshot

FONT_REGULAR = "ExamSans"
FONT_BOLD = "ExamSans-Bold"


def _register_fonts() -> None:
    regular_candidates = (
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
    )
    bold_candidates = (
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
    )
    regular = next((p for p in regular_candidates if p.exists()), None)
    bold = next((p for p in bold_candidates if p.exists()), None)
    if not regular or not bold:
        raise RuntimeError("Türkçe PDF fontu bulunamadı (DejaVu Sans).")
    if FONT_REGULAR not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(regular)))
    if FONT_BOLD not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(FONT_BOLD, str(bold)))


def _load_or_create_snapshot(db: Session, training, created_by_id: int) -> TrainingExamSnapshot:
    """Aynı eğitim tekrar indirildiğinde sınav içeriğini değiştirme."""
    snapshot = db.scalar(
        select(TrainingExamSnapshot)
        .options(selectinload(TrainingExamSnapshot.items))
        .where(TrainingExamSnapshot.training_id == training.id)
        .order_by(TrainingExamSnapshot.version.desc())
        .limit(1)
    )
    if snapshot is not None:
        return snapshot
    return create_exam_snapshot(db, training=training, created_by_id=created_by_id)


def _wrap(c, text: str, width: float, font: str, size: float) -> list[str]:
    words = str(text).split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if c.stringWidth(candidate, font, size) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _bucket_label(scopes_json: str) -> str:
    scopes = json.loads(scopes_json or "[]")
    kinds = {str(row.get("type") or "") for row in scopes}
    if "sector" in kinds or "nace" in kinds:
        return "Sektör"
    if "hazard" in kinds:
        return "Teknik"
    return "Ortak"


def build_exam_pdf(*, company_name: str, training, db: Session, created_by_id: int) -> bytes:
    _register_fonts()
    snapshot = _load_or_create_snapshot(db, training, created_by_id)
    items = list(snapshot.items)
    if len(items) != 15:
        raise RuntimeError(f"Sınav snapshot soru sayısı 15 değil: {len(items)}")

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle("İş Sağlığı ve Güvenliği Eğitim Sınavı")
    w, h = A4
    navy = (11 / 255, 46 / 255, 79 / 255)
    emerald = (15 / 255, 118 / 255, 110 / 255)
    light = (244 / 255, 248 / 255, 247 / 255)

    def header(page_no: int):
        c.setFillColorRGB(*navy)
        c.rect(0, h - 30 * mm, w, 30 * mm, fill=1, stroke=0)
        c.setFillColorRGB(*emerald)
        c.rect(0, h - 31.5 * mm, w, 1.5 * mm, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.setFont(FONT_BOLD, 14)
        c.drawCentredString(w / 2, h - 13 * mm, "İŞ SAĞLIĞI VE GÜVENLİĞİ EĞİTİM SINAVI")
        c.setFont(FONT_REGULAR, 7.5)
        subtitle = f"{training.hazard_class} • Sektör: {training.sector or '—'} • 15 Soru • Sürüm {snapshot.version}"
        c.drawCentredString(w / 2, h - 21 * mm, subtitle)
        c.setFillColorRGB(0.25, 0.3, 0.35)
        c.setFont(FONT_REGULAR, 7)
        c.drawRightString(w - 15 * mm, 10 * mm, f"Sayfa {page_no}")

    header(1)
    y = h - 39 * mm
    c.setFillColorRGB(*light)
    c.roundRect(14 * mm, y - 25 * mm, w - 28 * mm, 25 * mm, 3 * mm, fill=1, stroke=0)
    c.setFillColorRGB(0.08, 0.14, 0.22)
    c.setFont(FONT_BOLD, 8)
    fields = [
        ("Katılımcı Adı Soyadı", ""),
        ("Firma Adı", company_name or ""),
        ("Sınav Tarihi", datetime.now().strftime("%d.%m.%Y")),
        ("İmza", ""),
    ]
    col_w = (w - 34 * mm) / 2
    for i, (label, value) in enumerate(fields):
        row, col = divmod(i, 2)
        x = 18 * mm + col * col_w
        yy = y - 7 * mm - row * 11 * mm
        c.drawString(x, yy, f"{label}:")
        c.setFont(FONT_REGULAR, 8)
        c.drawString(x + 32 * mm, yy, value)
        c.line(x + 31 * mm, yy - 1.5 * mm, x + col_w - 4 * mm, yy - 1.5 * mm)
        c.setFont(FONT_BOLD, 8)

    y -= 31 * mm
    page_no = 1
    for item in items:
        options = json.loads(item.options_json)
        stem_lines = _wrap(c, f"{item.position}. {item.question_text}", w - 32 * mm, FONT_BOLD, 8.5)
        option_lines = sum(len(_wrap(c, f"{key}) {value}", w - 42 * mm, FONT_REGULAR, 7.5)) for key, value in options.items())
        needed_mm = len(stem_lines) * 4.2 + option_lines * 3.7 + 7
        if y < (25 + needed_mm) * mm:
            c.showPage()
            page_no += 1
            header(page_no)
            y = h - 38 * mm
        c.setFillColorRGB(*navy)
        c.setFont(FONT_BOLD, 8.5)
        for line in stem_lines:
            c.drawString(16 * mm, y, line)
            y -= 4.2 * mm
        c.setFillColorRGB(0.16, 0.2, 0.25)
        c.setFont(FONT_REGULAR, 7.5)
        for key in "ABCD":
            for line in _wrap(c, f"{key}) {options[key]}", w - 42 * mm, FONT_REGULAR, 7.5):
                c.drawString(22 * mm, y, line)
                y -= 3.7 * mm
        y -= 3 * mm

    c.showPage()
    page_no += 1
    header(page_no)
    c.setFillColorRGB(*navy)
    c.setFont(FONT_BOLD, 13)
    c.drawCentredString(w / 2, h - 45 * mm, "CEVAP ANAHTARI")
    c.setFont(FONT_BOLD, 9)
    y = h - 60 * mm
    for i, item in enumerate(items, 1):
        x = 25 * mm + ((i - 1) % 5) * 34 * mm
        yy = y - ((i - 1) // 5) * 14 * mm
        c.drawString(x, yy, f"{i}. {item.correct_option} ({_bucket_label(item.scopes_json)})")

    c.setFont(FONT_REGULAR, 6.5)
    c.setFillColorRGB(0.35, 0.4, 0.45)
    c.drawCentredString(w / 2, 27 * mm, f"Politika: {snapshot.selection_policy} • İçerik özeti: {snapshot.content_hash[:16]}")
    c.drawCentredString(w / 2, 20 * mm, "Sınav yalnız yayımlanmış soru bankasından oluşturulmuş ve snapshot olarak sabitlenmiştir.")

    c.save()
    return buf.getvalue()
