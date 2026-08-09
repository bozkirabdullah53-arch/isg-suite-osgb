"""Sabit 5 temel ve mevcut 15 banka sorusundan denetlenebilir sınav PDF'i üretir."""
from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import Branch, Company, Employee, TrainingExamSnapshot
from app.services.training_question_bank import QUESTION_COUNT, create_exam_snapshot
from app.services.training_topics import sectors_list_for_api

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
    if (
        snapshot is not None
        and snapshot.question_count == QUESTION_COUNT
        and len(snapshot.items) == QUESTION_COUNT
    ):
        return snapshot
    # The managed PDF action remains usable while the reviewed database bank is
    # being expanded. Bundled questions are used only to fill missing buckets;
    # they are frozen into the snapshot without mutating or publishing DB rows.
    return create_exam_snapshot(
        db,
        training=training,
        created_by_id=created_by_id,
        allow_curated_fallback=True,
    )


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
    if "foundation" in kinds:
        return "Temel İSG"
    if "sector" in kinds or "nace" in kinds:
        return "Sektör"
    if "hazard" in kinds:
        return "Teknik"
    return "Ortak"


def _training_exam_date_text(training) -> str:
    """Sınav tarihi eğitim bitiş tarihidir; indirme zamanı belge tarihini değiştirmez.

    Tarihsel/eksik eski kayıtlar için bitiş yoksa başlangıç tarihine düşer. Her iki
    alan da yoksa boş bırakılır; bugünün tarihi asla uydurulmaz.
    """
    value = getattr(training, "end_date", None) or getattr(training, "start_date", None)
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%d.%m.%Y")
    text = str(value).strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        year, month, day = text[:10].split("-")
        return f"{day}.{month}.{year}"
    return text



def _sector_display_name(sector_code: str | None) -> str:
    """İç sistem kodu yerine kullanıcıya gösterilen NACE/faaliyet adını döndür."""
    raw = str(sector_code or "").strip()
    if not raw:
        return "—"
    for row in sectors_list_for_api():
        if str(row.get("code") or "") == raw:
            return str(row.get("name") or row.get("label") or raw)
    return raw


def _exam_company_registry_no(db: Session, training) -> str:
    """Şube eğitimi için şube sicili, aksi halde firma SGK sicili."""
    branch_id = getattr(training, "branch_id", None)
    if branch_id:
        branch = db.get(Branch, branch_id)
        if branch and str(branch.sgk_registry_no or "").strip():
            return str(branch.sgk_registry_no).strip()
    company = db.get(Company, training.company_id)
    return str(getattr(company, "sgk_registry_no", "") or "").strip()


def _exam_participant_names(db: Session, training) -> list[str]:
    """Katılımcı sırasını koruyarak kişiye özel sınav formu adlarını üret."""
    participants = list(getattr(training, "participants", None) or [])
    employee_ids = [int(row.employee_id) for row in participants]
    if not employee_ids:
        return [""]
    employees = {
        row.id: row.full_name
        for row in db.scalars(select(Employee).where(Employee.id.in_(employee_ids))).all()
    }
    names = [str(employees.get(employee_id) or f"Personel #{employee_id}") for employee_id in employee_ids]
    return names or [""]


def build_exam_pdf(*, company_name: str, training, db: Session, created_by_id: int) -> bytes:
    _register_fonts()
    snapshot = _load_or_create_snapshot(db, training, created_by_id)
    items = list(snapshot.items)
    if len(items) != QUESTION_COUNT:
        raise RuntimeError(
            f"Sınav snapshot soru sayısı {QUESTION_COUNT} değil: {len(items)}"
        )

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle("İş Sağlığı ve Güvenliği Eğitim Sınavı")
    w, h = A4
    navy = (11 / 255, 46 / 255, 79 / 255)
    emerald = (15 / 255, 118 / 255, 110 / 255)
    light = (244 / 255, 248 / 255, 247 / 255)
    sector_name = _sector_display_name(getattr(training, "sector", None))
    registry_no = _exam_company_registry_no(db, training)
    participant_names = _exam_participant_names(db, training)

    def header(page_no: int):
        c.setFillColorRGB(*navy)
        c.rect(0, h - 30 * mm, w, 30 * mm, fill=1, stroke=0)
        c.setFillColorRGB(*emerald)
        c.rect(0, h - 31.5 * mm, w, 1.5 * mm, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.setFont(FONT_BOLD, 14)
        c.drawCentredString(w / 2, h - 13 * mm, "İŞ SAĞLIĞI VE GÜVENLİĞİ EĞİTİM SINAVI")
        c.setFont(FONT_REGULAR, 7.5)
        subtitle = (
            f"{training.hazard_class} • Sektör: {sector_name} • "
            f"{QUESTION_COUNT} Soru • Sürüm {snapshot.version}"
        )
        c.drawCentredString(w / 2, h - 21 * mm, subtitle)
        c.setFillColorRGB(0.25, 0.3, 0.35)
        c.setFont(FONT_REGULAR, 7)
        c.drawRightString(w - 15 * mm, 10 * mm, f"Sayfa {page_no}")

    page_no = 0
    for participant_index, participant_name in enumerate(participant_names):
        if participant_index:
            c.showPage()
        page_no += 1
        header(page_no)
        y = h - 39 * mm
        c.setFillColorRGB(*light)
        c.roundRect(14 * mm, y - 36 * mm, w - 28 * mm, 36 * mm, 3 * mm, fill=1, stroke=0)
        c.setFillColorRGB(0.08, 0.14, 0.22)
        c.setFont(FONT_BOLD, 8)
        fields = [
            ("Çalışanın Adı Soyadı", participant_name),
            ("İmza", ""),
            ("Firma Ünvanı", company_name or ""),
            ("SGK Sicil No", registry_no),
            ("Sektör / Faaliyet", sector_name),
            ("Sınav Tarihi", _training_exam_date_text(training)),
        ]
        col_w = (w - 34 * mm) / 2
        for i, (label, value) in enumerate(fields):
            row, col = divmod(i, 2)
            x = 18 * mm + col * col_w
            yy = y - 7 * mm - row * 10.5 * mm
            c.drawString(x, yy, f"{label}:")
            c.setFont(FONT_REGULAR, 7.5)
            value_lines = _wrap(c, value, col_w - 34 * mm, FONT_REGULAR, 7.5)
            c.drawString(x + 34 * mm, yy, value_lines[0] if value_lines else "")
            c.line(x + 33 * mm, yy - 1.5 * mm, x + col_w - 4 * mm, yy - 1.5 * mm)
            c.setFont(FONT_BOLD, 8)

        y -= 42 * mm
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
