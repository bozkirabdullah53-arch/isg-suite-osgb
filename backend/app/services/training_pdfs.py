"""Eğitim katılım belgesi ve imza listesi PDF — bakanlık denetimine uygun yatay A4."""
from __future__ import annotations

import os
from datetime import datetime
from io import BytesIO
from pathlib import Path

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app.services.training_topics import (
    egitim_konularini_hazirla,
    katilim_formu_konu_ozeti,
    sektor_adi,
    sektor_kodu_cozumle,
    tehlike_kurali,
)

_FONT = "Helvetica"
_FONT_B = "Helvetica-Bold"
_ASSETS = Path(__file__).resolve().parent.parent / "assets" / "fonts"


def _register_fonts() -> None:
    global _FONT, _FONT_B
    candidates = [
        (_ASSETS / "DejaVuSans.ttf", _ASSETS / "DejaVuSans-Bold.ttf"),
        (Path(r"C:\Windows\Fonts\arial.ttf"), Path(r"C:\Windows\Fonts\arialbd.ttf")),
        (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
         Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
        (Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
         Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf")),
    ]
    for regular, bold in candidates:
        if regular.exists():
            try:
                pdfmetrics.registerFont(TTFont("IsgSans", str(regular)))
                pdfmetrics.registerFont(TTFont("IsgSans-Bold", str(bold if bold.exists() else regular)))
                _FONT, _FONT_B = "IsgSans", "IsgSans-Bold"
            except Exception:
                continue
            return


_register_fonts()


def _fit(c: canvas.Canvas, text: str, width: float, font: str, size: float) -> str:
    text = str(text or "").replace("\n", " ").strip()
    c.setFont(font, size)
    if c.stringWidth(text, font, size) <= width:
        return text
    while text and c.stringWidth(text + "...", font, size) > width:
        text = text[:-1]
    return (text.rstrip() + "...") if text else ""


def _wrap(c: canvas.Canvas, text: str, width: float, font: str, size: float, max_lines: int = 4) -> list[str]:
    words = str(text or "").split()
    if not words:
        return [""]
    lines: list[str] = []
    cur = ""
    c.setFont(font, size)
    for w in words:
        trial = f"{cur} {w}".strip()
        if c.stringWidth(trial, font, size) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
            if len(lines) >= max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(lines) == max_lines and words:
        lines[-1] = _fit(c, lines[-1], width, font, size)
    return lines or [""]


def _fmt_date(d) -> str:
    if not d:
        return "—"
    if hasattr(d, "strftime"):
        return d.strftime("%d.%m.%Y")
    s = str(d)
    if len(s) == 10 and s[4] == "-":
        y, m, day = s.split("-")
        return f"{day}.{m}.{y}"
    return s


def build_attendance_pdf(*, company_name: str, training, employees: dict) -> bytes:
    """Katılımcı imza / yoklama formu (İSG-EĞT-KF-01)."""
    participants = list(training.participants or [])
    if not participants:
        raise ValueError("İmza listesi için en az bir katılımcı gerekli. Eğitim kaydına personel ekleyin.")

    buf = BytesIO()
    page = landscape(A4)
    c = canvas.Canvas(buf, pagesize=page)
    w, h = page
    per_page = 10
    total_pages = max(1, (len(participants) + per_page - 1) // per_page)
    bugun = datetime.now().strftime("%d.%m.%Y")
    kural = tehlike_kurali(training.hazard_class)
    sektor = sektor_kodu_cozumle(training.sector)
    konu_ozeti = katilim_formu_konu_ozeti(training.hazard_class, sektor)

    for page_i in range(total_pages):
        chunk = participants[page_i * per_page : (page_i + 1) * per_page]
        _draw_attendance_page(
            c, w, h,
            company_name=company_name,
            training=training,
            employees=employees,
            chunk=chunk,
            page_no=page_i + 1,
            total_pages=total_pages,
            bugun=bugun,
            kural=kural,
            sektor_label=sektor_adi(sektor),
            konu_ozeti=konu_ozeti,
            start_index=page_i * per_page,
        )
        c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()


def _draw_attendance_page(
    c, w, h, *, company_name, training, employees, chunk, page_no, total_pages, bugun, kural, sektor_label, konu_ozeti, start_index
):
    ml, mr = 10 * mm, 10 * mm
    uw = w - ml - mr

    c.setStrokeColorRGB(0.18, 0.27, 0.37)
    c.setLineWidth(1.2)
    c.rect(8 * mm, 8 * mm, w - 16 * mm, h - 16 * mm)

    c.setFillColorRGB(0.89, 0.92, 0.96)
    c.rect(ml, h - 28 * mm, uw, 16 * mm, fill=1, stroke=0)
    c.setFillColorRGB(0.08, 0.14, 0.2)
    c.setFont(_FONT_B, 12)
    c.drawCentredString(w / 2, h - 15 * mm, "İŞ SAĞLIĞI VE GÜVENLİĞİ TEMEL EĞİTİMİ")
    c.setFont(_FONT_B, 14)
    c.drawCentredString(w / 2, h - 22 * mm, "KATILIMCI İMZA FORMU")
    c.setFont(_FONT, 7)
    c.setFillColorRGB(0.35, 0.35, 0.35)
    c.drawRightString(w - mr, h - 13 * mm, "Form No: İSG-EĞT-KF-01")
    c.drawRightString(w - mr, h - 17 * mm, f"Sayfa: {page_no}/{total_pages}")
    c.drawRightString(w - mr, h - 21 * mm, f"Düzenleme: {bugun}")
    c.drawString(ml, h - 21 * mm, f"Doğrulama: {training.verification_code or '—'}")

    info = [
        ("Firma", company_name),
        ("Eğitimin Adı", training.title),
        ("Eğitim Tarihi", _fmt_date(training.start_date)),
        ("Eğitim Süresi", kural["sure"]),
        ("Yenileme", kural["yenileme"]),
        ("Tehlike Sınıfı", training.hazard_class),
        ("Eğitim Türü", training.training_type),
        ("Eğitim Şekli", training.delivery_method),
        ("Sektör / İş Kolu", sektor_label),
        ("Eğitim Yeri", training.location or "—"),
        ("Eğitici / Yeterlilik", f"{training.instructor_name}" + (f" — {training.instructor_qualification}" if training.instructor_qualification else "")),
        ("Değerlendirme", f"{training.evaluation_method or '—'}" + (f" (Geçme: {training.passing_score})" if training.passing_score else "")),
    ]
    col_w = uw / 4
    row_h = 7.5 * mm
    y0 = h - 36 * mm
    for i, (lab, val) in enumerate(info):
        r, col = divmod(i, 4)
        x = ml + col * col_w
        y = y0 - r * row_h
        c.setStrokeColorRGB(0.7, 0.76, 0.82)
        c.setFillColorRGB(0.97, 0.98, 0.99)
        c.rect(x, y - row_h, col_w, row_h, fill=1, stroke=1)
        c.setFillColorRGB(0.3, 0.35, 0.4)
        c.setFont(_FONT_B, 6)
        c.drawString(x + 1.5 * mm, y - 3 * mm, lab)
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.setFont(_FONT, 7)
        c.drawString(x + 1.5 * mm, y - 6.2 * mm, _fit(c, val, col_w - 3 * mm, _FONT, 7))

    box_y = y0 - 3 * row_h - 2 * mm
    box_h = 22 * mm
    c.setFillColorRGB(0.92, 0.95, 0.97)
    c.rect(ml, box_y - box_h, uw, box_h, fill=1, stroke=1)
    c.setFillColorRGB(0.08, 0.14, 0.2)
    c.setFont(_FONT_B, 7)
    c.drawString(ml + 2 * mm, box_y - 4 * mm, "Eğitimin Amacı:")
    c.setFont(_FONT, 6.5)
    purpose = (
        "Çalışanların meslek hastalığı ve iş kazasına maruz kalma riskini azaltmak; "
        "sağlıklı ve güvenli çalışma ortamı oluşturmak."
    )
    for li, line in enumerate(_wrap(c, purpose, uw - 32 * mm, _FONT, 6.5, 2)):
        c.drawString(ml + 30 * mm, box_y - 4 * mm - li * 3.2 * mm, line)

    c.setFont(_FONT_B, 7)
    c.drawString(ml + 2 * mm, box_y - 11 * mm, "Eğitim Konuları (özet):")
    c.setFont(_FONT, 6)
    konu_lines = _wrap(c, konu_ozeti, uw - 42 * mm, _FONT, 6, 3)
    for li, line in enumerate(konu_lines):
        c.drawString(ml + 38 * mm, box_y - 11 * mm - li * 3 * mm, line)

    c.setFont(_FONT_B, 7)
    c.drawString(ml + 2 * mm, box_y - 20 * mm, "Dayanak:")
    c.setFont(_FONT, 6.5)
    c.drawString(
        ml + 18 * mm,
        box_y - 20 * mm,
        _fit(
            c,
            "6331 sayılı İş Sağlığı ve Güvenliği Kanunu ve Çalışanların İSG Eğitimleri Yönetmeliği.",
            uw - 22 * mm,
            _FONT,
            6.5,
        ),
    )

    table_y = box_y - box_h - 3 * mm
    cols = [10 * mm, 52 * mm, 32 * mm, 48 * mm, 55 * mm, 18 * mm]
    cols.append(uw - sum(cols))
    headers = ["Sıra", "Adı Soyadı", "T.C. Kimlik", "Görevi / Bölümü", "İmzası", "Not", "Açıklama"]
    header_h = 7 * mm
    row_h = 8 * mm
    x = ml
    c.setFillColorRGB(0.18, 0.27, 0.37)
    for cw, ht in zip(cols, headers):
        c.rect(x, table_y - header_h, cw, header_h, fill=1, stroke=1)
        c.setFillColorRGB(1, 1, 1)
        c.setFont(_FONT_B, 6.5)
        c.drawCentredString(x + cw / 2, table_y - 4.5 * mm, ht)
        c.setFillColorRGB(0.18, 0.27, 0.37)
        x += cw

    y = table_y - header_h
    for i in range(10):
        p = chunk[i] if i < len(chunk) else None
        e = employees.get(p.employee_id) if p else None
        sira = str(start_index + i + 1) if p else ""
        ad = (e.full_name if e else "") if p else ""
        tc = (getattr(e, "national_id_masked", None) or "") if e else ""
        gorev = ""
        if e:
            gorev = e.job_title or ""
            if e.department:
                gorev = f"{gorev} / {e.department}" if gorev else e.department
        vals = [sira, ad, tc, gorev, "", "", ""]
        x = ml
        for ci, (cw, val) in enumerate(zip(cols, vals)):
            c.setStrokeColorRGB(0.7, 0.74, 0.78)
            c.setFillColorRGB(1, 1, 1)
            c.rect(x, y - row_h, cw, row_h, fill=1, stroke=1)
            c.setFillColorRGB(0.1, 0.1, 0.1)
            c.setFont(_FONT_B if ci == 1 and val else _FONT, 7)
            txt = _fit(c, val, cw - 2 * mm, _FONT, 7)
            if ci in (0, 2, 5):
                c.drawCentredString(x + cw / 2, y - 5 * mm, txt)
            else:
                c.drawString(x + 1 * mm, y - 5 * mm, txt)
            x += cw
        y -= row_h

    iy = 12 * mm
    ih = 22 * mm
    box_w = uw / 3
    labels = (
        ("Eğitimi Veren (İSG)", training.instructor_name or "", training.instructor_qualification or "İSG Uzmanı"),
        ("İşyeri Hekimi", "", "İşyeri Hekimi"),
        ("İşveren / Vekili", "", "İşveren Vekili"),
    )
    for i, (title, name, role) in enumerate(labels):
        x = ml + i * box_w
        c.setStrokeColorRGB(0.63, 0.7, 0.78)
        c.setFillColorRGB(0.97, 0.98, 0.99)
        c.rect(x, iy, box_w, ih, fill=1, stroke=1)
        c.setFillColorRGB(0.08, 0.14, 0.2)
        c.setFont(_FONT_B, 7)
        c.drawCentredString(x + box_w / 2, iy + ih - 5 * mm, title)
        c.setFont(_FONT, 7)
        c.drawCentredString(x + box_w / 2, iy + ih - 10 * mm, name or role)
        c.setStrokeColorRGB(0.35, 0.35, 0.35)
        c.line(x + 8 * mm, iy + 7 * mm, x + box_w - 8 * mm, iy + 7 * mm)
        c.setFont(_FONT, 6)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.drawCentredString(x + box_w / 2, iy + 3 * mm, "Kaşe / İmza")

    c.setFont(_FONT, 5.5)
    c.setFillColorRGB(0.45, 0.45, 0.45)
    c.drawCentredString(
        w / 2,
        9.5 * mm,
        "Bu formdaki imzalar, belirtilen tarihte eğitimin verildiğini ve ilgili kişilerin katıldığını belgeler.",
    )


def build_certificates_pdf(*, company_name: str, training, employees: dict) -> bytes:
    """Kişi başı katılım belgesi — eğitim konuları zorunlu (Çalışma Bakanlığı)."""
    participants = list(training.participants or [])
    if not participants:
        raise ValueError("Katılım belgesi için en az bir katılımcı gerekli. Eğitim kaydına personel ekleyin.")

    buf = BytesIO()
    page = landscape(A4)
    c = canvas.Canvas(buf, pagesize=page)
    w, h = page
    bugun = datetime.now().strftime("%d.%m.%Y")
    egitim_tarihi = _fmt_date(training.start_date)
    kural = tehlike_kurali(training.hazard_class)
    sektor = sektor_kodu_cozumle(training.sector)
    sol, sag, _, _ = egitim_konularini_hazirla(training.hazard_class, sektor)

    for i, p in enumerate(participants, 1):
        e = employees.get(p.employee_id)
        belge_no = p.certificate_number or f"ISG-{egitim_tarihi.replace('.', '')}-{i:03d}"
        _draw_certificate_page(
            c, w, h,
            company_name=company_name,
            training=training,
            employee=e,
            belge_no=belge_no,
            bugun=bugun,
            egitim_tarihi=egitim_tarihi,
            kural=kural,
            sol=sol,
            sag=sag,
        )
        c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()


def _draw_certificate_page(c, w, h, *, company_name, training, employee, belge_no, bugun, egitim_tarihi, kural, sol, sag):
    ml, mr = 8 * mm, 8 * mm
    uw = w - ml - mr

    c.setStrokeColorRGB(0.05, 0.43, 0.99)
    c.setLineWidth(1.5)
    c.rect(5 * mm, 5 * mm, w - 10 * mm, h - 10 * mm)
    c.setLineWidth(0.6)
    c.setStrokeColorRGB(0.78, 0.84, 0.94)
    c.rect(7 * mm, 7 * mm, w - 14 * mm, h - 14 * mm)

    c.setFillColorRGB(0.05, 0.43, 0.99)
    c.rect(5 * mm, h - 28 * mm, w - 10 * mm, 23 * mm, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont(_FONT_B, 11)
    c.drawCentredString(w / 2, h - 14 * mm, "TEMEL İŞ SAĞLIĞI VE GÜVENLİĞİ EĞİTİMİ KATILIM BELGESİ")
    c.setFont(_FONT_B, 9)
    c.drawCentredString(w / 2, h - 20 * mm, company_name or "")

    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.setFont(_FONT, 7)
    c.drawString(ml, h - 34 * mm, f"Belge No: {belge_no}")
    c.drawRightString(w - mr, h - 34 * mm, f"Düzenleme Tarihi: {bugun}")
    meta = (
        f"Süre: {kural['sure']}  │  Tür: {training.training_type}  │  "
        f"Şekil: {training.delivery_method}  │  Doğrulama: {training.verification_code or ''}"
    )
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.drawCentredString(w / 2, h - 39 * mm, _fit(c, meta, uw, _FONT, 7))

    name = employee.full_name if employee else "—"
    tc = (getattr(employee, "national_id_masked", None) or "") if employee else ""
    gorev = (employee.job_title or "") if employee else ""

    c.setFillColorRGB(0.05, 0.43, 0.99)
    c.setFont(_FONT, 8)
    c.drawCentredString(w / 2, h - 48 * mm, "Sn.")
    c.setFillColorRGB(0, 0, 0)
    c.setFont(_FONT_B, 16)
    c.drawCentredString(w / 2, h - 56 * mm, name)
    c.setFillColorRGB(0.35, 0.35, 0.35)
    c.setFont(_FONT, 7.5)
    c.drawString(ml, h - 64 * mm, f"T.C. Kimlik No: {tc}" if tc else "T.C. Kimlik No: —")
    c.drawRightString(w - mr, h - 64 * mm, f"Görevi: {gorev}" if gorev else "Görevi: —")
    c.drawCentredString(w / 2, h - 69 * mm, f"Eğitim Tarihi: {egitim_tarihi}")

    c.setFillColorRGB(0.25, 0.25, 0.25)
    c.setFont(_FONT, 7)
    lines = [
        "Yukarıda adı geçen çalışanın, 6331 Sayılı Kanun Gereği, Çalışanların İş Sağlığı ve Güvenliği",
        "Eğitimlerinin Usul ve Esasları Hakkında Yönetmelik kapsamında verilen iş sağlığı ve güvenliği",
        "eğitimlerini başarıyla tamamlayarak bu eğitim belgesini almaya hak kazanmıştır.",
    ]
    y = h - 78 * mm
    for line in lines:
        c.drawCentredString(w / 2, y, line)
        y -= 4 * mm

    box_w = (uw - 10 * mm) / 3
    gap = 5 * mm
    bh = 24 * mm
    iy = y - 4 * mm - bh
    titles = [
        ("Eğitim Veren", training.instructor_name or "", training.instructor_qualification or "İSG Uzmanı"),
        ("Eğitim Veren", "", "İşyeri Hekimi"),
        ("Onaylayan", "", "İşveren Vekili"),
    ]
    for i, (role, person, unvan) in enumerate(titles):
        x = ml + i * (box_w + gap)
        c.setFillColorRGB(0.97, 0.98, 1)
        c.setStrokeColorRGB(0.82, 0.86, 0.94)
        c.rect(x, iy, box_w, bh, fill=1, stroke=1)
        c.setFillColorRGB(0.05, 0.43, 0.99)
        c.rect(x, iy + bh - 1.2 * mm, box_w, 1.2 * mm, fill=1, stroke=0)
        c.setFont(_FONT_B, 7)
        c.setFillColorRGB(0.05, 0.43, 0.99)
        c.drawCentredString(x + box_w / 2, iy + bh - 6 * mm, role)
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.setFont(_FONT_B, 8)
        c.drawCentredString(x + box_w / 2, iy + bh - 12 * mm, person or " ")
        c.setStrokeColorRGB(0.4, 0.4, 0.4)
        c.line(x + 5 * mm, iy + 8 * mm, x + box_w - 5 * mm, iy + 8 * mm)
        c.setFillColorRGB(0.45, 0.45, 0.45)
        c.setFont(_FONT, 6)
        c.drawCentredString(x + box_w / 2, iy + 3.5 * mm, unvan)

    ty = iy - 4 * mm
    c.setStrokeColorRGB(0.05, 0.43, 0.99)
    c.setLineWidth(1)
    c.line(ml, ty, w - mr, ty)
    c.setFillColorRGB(0.96, 0.97, 1)
    c.rect(ml, ty - 7 * mm, uw, 6.5 * mm, fill=1, stroke=0)
    c.setFillColorRGB(0.05, 0.43, 0.99)
    c.setFont(_FONT_B, 8)
    c.drawCentredString(w / 2, ty - 4.5 * mm, "İŞ SAĞLIĞI VE GÜVENLİĞİ EĞİTİM KONULARI (Zorunlu)")

    top = ty - 9 * mm
    cw = (uw - 8 * mm) / 2

    def draw_col(items, x, start_y, lh):
        yy = start_y
        for is_h, text in items:
            if yy < 12 * mm:
                break
            c.setFillColorRGB(0, 0, 0) if is_h else c.setFillColorRGB(0.25, 0.25, 0.25)
            font = _FONT_B if is_h else _FONT
            size = 7.2 if is_h else 6.5
            c.setFont(font, size)
            c.drawString(x, yy, _fit(c, text, cw - 2 * mm, font, size))
            yy -= lh
        return yy

    draw_col(sol, ml + 1 * mm, top, 3.8 * mm)
    draw_col(sag, ml + cw + 7 * mm, top, 4.0 * mm)

    c.setStrokeColorRGB(0.78, 0.84, 0.94)
    c.line(ml + 30 * mm, 9 * mm, w - mr - 30 * mm, 9 * mm)
    c.setFillColorRGB(0.55, 0.55, 0.55)
    c.setFont(_FONT, 5.5)
    c.drawCentredString(
        w / 2,
        6.5 * mm,
        "6331 Sayılı İş Sağlığı ve Güvenliği Kanunu ve ilgili yönetmelik kapsamında düzenlenmiştir.",
    )
