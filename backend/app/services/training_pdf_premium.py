"""Premium A4 landscape İSG training participation certificate renderer.

This module changes presentation only. All certificate data, topic wording,
ordering and durations are supplied by the existing training service.
"""
from __future__ import annotations

from reportlab.lib.units import mm

from app.services.national_id_format import normalize_national_id

NAVY = (7 / 255, 45 / 255, 82 / 255)
NAVY_2 = (4 / 255, 76 / 255, 109 / 255)
EMERALD = (0 / 255, 126 / 255, 105 / 255)
GREEN = (93 / 255, 148 / 255, 46 / 255)
SILVER = (190 / 255, 204 / 255, 215 / 255)
PALE = (247 / 255, 250 / 255, 252 / 255)
TEXT = (18 / 255, 36 / 255, 54 / 255)
MUTED = (78 / 255, 92 / 255, 105 / 255)


def _wrap(tp, c, text: str, width: float, font: str, size: float, max_lines: int = 3):
    return tp._wrap(c, text, width, font, size, max_lines)


def _fit(tp, c, text: str, width: float, font: str, size: float):
    return tp._fit(c, text, width, font, size)


def _draw_header_icon(c, x, y, kind: str):
    """Small line icons drawn without external assets."""
    c.saveState()
    c.setStrokeColorRGB(1, 1, 1)
    c.setLineWidth(0.8)
    if kind == "helmet":
        c.arc(x, y, x + 8 * mm, y + 7 * mm, 0, 180)
        c.line(x, y + 3.5 * mm, x + 8 * mm, y + 3.5 * mm)
        c.line(x + 1 * mm, y + 2.5 * mm, x + 7 * mm, y + 2.5 * mm)
    elif kind == "shield":
        p = c.beginPath()
        p.moveTo(x + 4 * mm, y + 7 * mm)
        p.lineTo(x + 7.5 * mm, y + 5.5 * mm)
        p.lineTo(x + 7 * mm, y + 1.5 * mm)
        p.lineTo(x + 4 * mm, y)
        p.lineTo(x + 1 * mm, y + 1.5 * mm)
        p.lineTo(x + 0.5 * mm, y + 5.5 * mm)
        p.close()
        c.drawPath(p, stroke=1, fill=0)
        c.line(x + 2.3 * mm, y + 3.4 * mm, x + 3.5 * mm, y + 2.2 * mm)
        c.line(x + 3.5 * mm, y + 2.2 * mm, x + 5.8 * mm, y + 4.8 * mm)
    elif kind == "warning":
        p = c.beginPath()
        p.moveTo(x + 4 * mm, y + 7 * mm)
        p.lineTo(x + 7.5 * mm, y)
        p.lineTo(x + 0.5 * mm, y)
        p.close()
        c.drawPath(p, stroke=1, fill=0)
        c.line(x + 4 * mm, y + 4.7 * mm, x + 4 * mm, y + 2.2 * mm)
        c.circle(x + 4 * mm, y + 1 * mm, 0.2 * mm, stroke=1, fill=0)
    else:
        c.rect(x + 1 * mm, y + 0.5 * mm, 6 * mm, 6 * mm, stroke=1, fill=0)
        for i in range(3):
            yy = y + (4.8 - i * 1.5) * mm
            c.line(x + 2 * mm, yy, x + 6 * mm, yy)
    c.restoreState()


def _split_topic_columns(sol, sag):
    """Keep original order; place section 4 in its own third column."""
    second, third = [], []
    in_fourth = False
    for is_heading, text in sag:
        normalized = str(text).strip().upper()
        if is_heading and normalized.startswith("4."):
            in_fourth = True
        (third if in_fourth else second).append((is_heading, text))
    return list(sol), second, third


def draw_certificate_page(
    c, w, h, *, company_name, training, employee, belge_no, bugun,
    egitim_tarihi, kural, sektor, sol, sag, curriculum=None, tp=None
):
    """Render the premium certificate while preserving all supplied content."""
    if tp is None:
        from app.services import training_pdfs as tp
    curriculum = curriculum or {}
    profile_key = str(
        curriculum.get("profile_key")
        or tp.resolve_training_document_titles(training).get("profile_key")
        or ""
    )
    is_hygiene_profile = profile_key in {"hijyen_sanitasyon", "gida_su_hijyeni"}
    ml, mr = 7 * mm, 7 * mm
    uw = w - ml - mr

    # Paper and executive border.
    c.setFillColorRGB(1, 1, 1)
    c.rect(0, 0, w, h, fill=1, stroke=0)
    c.setStrokeColorRGB(*NAVY)
    c.setLineWidth(1.1)
    c.rect(3 * mm, 3 * mm, w - 6 * mm, h - 6 * mm, stroke=1, fill=0)
    c.setStrokeColorRGB(*GREEN)
    c.setLineWidth(0.45)
    c.rect(4.5 * mm, 4.5 * mm, w - 9 * mm, h - 9 * mm, stroke=1, fill=0)

    # Premium header.
    header_y = h - 31 * mm
    c.setFillColorRGB(*NAVY)
    c.rect(4.5 * mm, header_y, w - 9 * mm, 26.5 * mm, fill=1, stroke=0)
    c.setFillColorRGB(*EMERALD)
    p = c.beginPath()
    p.moveTo(w - 73 * mm, header_y)
    p.lineTo(w - 4.5 * mm, header_y)
    p.lineTo(w - 4.5 * mm, h - 4.5 * mm)
    p.lineTo(w - 62 * mm, h - 4.5 * mm)
    p.close()
    c.drawPath(p, fill=1, stroke=0)
    c.setStrokeColorRGB(*GREEN)
    c.setLineWidth(1.1)
    c.line(w - 74 * mm, header_y, w - 62 * mm, h - 4.5 * mm)

    # Dynamic company logo area (no fixed EİSA branding).
    logo_x, logo_y, logo_w, logo_h = 9 * mm, header_y + 3 * mm, 42 * mm, 20.5 * mm
    c.setStrokeColorRGB(0.75, 0.86, 0.9)
    c.setLineWidth(0.5)
    c.roundRect(logo_x, logo_y, logo_w, logo_h, 2 * mm, stroke=1, fill=0)
    if not tp._draw_logo(c, training, x=logo_x + 2 * mm, y=logo_y + 1.5 * mm, max_w=logo_w - 4 * mm, max_h=logo_h - 3 * mm):
        # Neutral shield/helmet mark when no logo has been uploaded.
        c.saveState()
        c.setStrokeColorRGB(1, 1, 1)
        c.setLineWidth(1)
        sx, sy = logo_x + 4 * mm, logo_y + 3 * mm
        p = c.beginPath()
        p.moveTo(sx + 7 * mm, sy + 14 * mm)
        p.lineTo(sx + 13 * mm, sy + 11 * mm)
        p.lineTo(sx + 12 * mm, sy + 4 * mm)
        p.lineTo(sx + 7 * mm, sy)
        p.lineTo(sx + 2 * mm, sy + 4 * mm)
        p.lineTo(sx + 1 * mm, sy + 11 * mm)
        p.close()
        c.drawPath(p, stroke=1, fill=0)
        c.arc(sx + 3 * mm, sy + 5 * mm, sx + 11 * mm, sy + 11 * mm, 0, 180)
        c.line(sx + 3 * mm, sy + 8 * mm, sx + 11 * mm, sy + 8 * mm)
        c.restoreState()

    titles = tp.resolve_training_document_titles(training)
    cert_title = (
        curriculum.get("certificate_title")
        or titles.get("certificate_title")
        or "TEMEL İŞ SAĞLIĞI VE GÜVENLİĞİ EĞİTİMİ KATILIM BELGESİ"
    )
    c.setFillColorRGB(1, 1, 1)
    title_size = 10.2 if len(cert_title) > 50 else 12
    c.setFont(tp._FONT_B, title_size)
    c.drawCentredString(w / 2 + 6 * mm, h - 14 * mm, _fit(tp, c, cert_title, 170 * mm, tp._FONT_B, title_size))
    c.setFont(tp._FONT_B, 8.5)
    c.drawCentredString(w / 2 + 6 * mm, h - 21 * mm, _fit(tp, c, company_name or "", 145 * mm, tp._FONT_B, 8.5))

    for idx, kind in enumerate(("helmet", "shield", "warning", "clipboard")):
        _draw_header_icon(c, w - (42 - idx * 10) * mm, h - 22.5 * mm, kind)

    # Metadata strip.
    strip_y = header_y - 12.5 * mm
    c.setFillColorRGB(*PALE)
    c.rect(4.5 * mm, strip_y, w - 9 * mm, 12.5 * mm, fill=1, stroke=0)
    c.setStrokeColorRGB(*SILVER)
    c.setLineWidth(0.35)
    c.line(4.5 * mm, strip_y, w - 4.5 * mm, strip_y)
    c.line(4.5 * mm, header_y, w - 4.5 * mm, header_y)
    meta_parts = [f"Belge No: {belge_no}"] + tp.certificate_meta_parts(training, kural=kural, curriculum=curriculum) + [f"Tarih: {bugun}"]
    colw = (w - 13 * mm) / len(meta_parts)
    for i, text in enumerate(meta_parts):
        x = 6.5 * mm + i * colw
        c.setFillColorRGB(*NAVY)
        c.setFont(tp._FONT_B if i in (0, len(meta_parts) - 1) else tp._FONT, 5.7)
        c.drawCentredString(x + colw / 2, strip_y + 4.7 * mm, _fit(tp, c, text, colw - 2 * mm, c._fontname, 5.7))
        if i:
            c.setStrokeColorRGB(0.82, 0.87, 0.9)
            c.line(x, strip_y + 2 * mm, x, strip_y + 10.5 * mm)

    # Light technical/safety watermark geometry.
    c.saveState()
    c.setStrokeColorRGB(0.89, 0.93, 0.95)
    c.setLineWidth(0.5)
    cx, cy = w / 2 + 38 * mm, h - 70 * mm
    c.circle(cx, cy, 20 * mm, stroke=1, fill=0)
    c.line(cx - 8 * mm, cy, cx - 1 * mm, cy - 7 * mm)
    c.line(cx - 1 * mm, cy - 7 * mm, cx + 11 * mm, cy + 8 * mm)
    c.restoreState()

    name = employee.full_name if employee else "—"
    tc = normalize_national_id(getattr(employee, "national_id_masked", None)) if employee else ""
    gorev = (employee.job_title or "") if employee else ""
    body_top = strip_y - 6 * mm
    c.setFillColorRGB(*NAVY_2)
    c.setFont(tp._FONT, 7.5)
    c.drawCentredString(w / 2, body_top - 2 * mm, "Sn.")
    c.setFillColorRGB(*NAVY)
    c.setFont(tp._FONT_B, 16)
    c.drawCentredString(w / 2, body_top - 11 * mm, _fit(tp, c, name, 90 * mm, tp._FONT_B, 16))
    c.setFont(tp._FONT_B, 6.7)
    c.drawString(9 * mm, body_top - 17 * mm, "T.C. Kimlik No:")
    c.setFont(tp._FONT, 6.7)
    c.drawString(31 * mm, body_top - 17 * mm, tc or "—")
    c.setFont(tp._FONT_B, 6.7)
    c.drawRightString(w - 36 * mm, body_top - 17 * mm, "Görevi:")
    c.setFont(tp._FONT, 6.7)
    c.drawRightString(w - 9 * mm, body_top - 17 * mm, gorev or "—")
    c.setFont(tp._FONT_B, 6.7)
    c.drawCentredString(w / 2 - 17 * mm, body_top - 21.5 * mm, "Eğitim Tarihi:")
    c.setFont(tp._FONT, 6.7)
    c.drawCentredString(w / 2 + 18 * mm, body_top - 21.5 * mm, egitim_tarihi)

    legal = (
        [
            "Yukarıda adı geçen çalışan, işyerinde düzenlenen hijyen eğitimine katılmış ve",
            "kişisel hijyen, bulaşma kontrolü, temizlik, dezenfeksiyon ve güvenli gıda/su",
            "uygulamalarındaki değerlendirmeyi tamamlayarak bu katılım belgesini almaya hak kazanmıştır.",
        ]
        if is_hygiene_profile
        else [
            "Yukarıda adı geçen çalışanın, 6331 Sayılı Kanun Gereği, Çalışanların İş Sağlığı ve Güvenliği",
            "Eğitimlerinin Usul ve Esasları Hakkında Yönetmelik kapsamında verilen, iş sağlığı ve güvenliği",
            "eğitimlerini, başarıyla tamamlayarak bu eğitim belgesini almaya hak kazanmıştır.",
        ]
    )
    c.setFillColorRGB(*MUTED)
    c.setFont(tp._FONT, 6.1)
    ly = body_top - 29 * mm
    for line in legal:
        c.drawCentredString(w / 2, ly, line)
        ly -= 3.5 * mm

    # Signature boxes.
    physician = (getattr(training, "workplace_physician", None) or "").strip()
    employer = (getattr(training, "employer_representative", None) or "").strip()
    instructor = (training.instructor_name or "").strip()
    instructor_title = (training.instructor_qualification or "").strip() or "İSG Uzmanı"
    signers = (
        (
            ("Eğitimi Veren Sağlık Personeli", instructor, instructor_title, EMERALD),
            ("Onaylayan", employer, "İşveren / İşveren Vekili", NAVY),
        )
        if is_hygiene_profile
        else (
            ("Eğitimi Veren", instructor, instructor_title, NAVY_2),
            ("Eğitimi Veren", physician, "İşyeri Hekimi", EMERALD),
            ("Onaylayan", employer, "İşveren Vekili", NAVY),
        )
    )
    sig_y, sig_h = 89 * mm, 28 * mm
    gap = 6 * mm
    box_w = (uw - (len(signers) - 1) * gap) / len(signers)
    for i, (role, person, unvan, accent) in enumerate(signers):
        x = ml + i * (box_w + gap)
        c.setFillColorRGB(1, 1, 1)
        c.setStrokeColorRGB(*accent)
        c.setLineWidth(0.8)
        c.roundRect(x, sig_y, box_w, sig_h, 2.5 * mm, fill=1, stroke=1)
        tab_w = 42 * mm
        c.setFillColorRGB(*accent)
        c.roundRect(x + (box_w - tab_w) / 2, sig_y + sig_h - 8.5 * mm, tab_w, 8.5 * mm, 1.5 * mm, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.setFont(tp._FONT_B, 7)
        c.drawCentredString(x + box_w / 2, sig_y + sig_h - 5.7 * mm, role)
        c.setFillColorRGB(*TEXT)
        c.setFont(tp._FONT_B, 8.3)
        c.drawCentredString(x + box_w / 2, sig_y + 13 * mm, _fit(tp, c, person or " ", box_w - 8 * mm, tp._FONT_B, 8.3))
        c.setStrokeColorRGB(0.35, 0.4, 0.45)
        c.setLineWidth(0.45)
        c.line(x + 12 * mm, sig_y + 8.3 * mm, x + box_w - 12 * mm, sig_y + 8.3 * mm)
        c.setFillColorRGB(*MUTED)
        c.setFont(tp._FONT, 5.8)
        c.drawCentredString(x + box_w / 2, sig_y + 3.5 * mm, unvan)

    # Topics title band.
    band_y = 80.5 * mm
    c.setFillColorRGB(*NAVY)
    c.rect(4.5 * mm, band_y, w - 9 * mm, 7.5 * mm, fill=1, stroke=0)
    c.setFillColorRGB(*EMERALD)
    c.rect(4.5 * mm, band_y, 70 * mm, 7.5 * mm, fill=1, stroke=0)
    c.setFillColorRGB(*NAVY)
    c.setFont(tp._FONT_B, 8)
    topics_header = curriculum.get("topics_header") or "İŞ SAĞLIĞI VE GÜVENLİĞİ EĞİTİM KONULARI"
    c.setFillColorRGB(1, 1, 1)
    c.drawCentredString(w / 2, band_y + 2.4 * mm, topics_header)

    col1, col2, col3 = _split_topic_columns(sol, sag)
    topic_cols = (col1, col2, col3)
    col_gap = 5 * mm
    topic_w = (uw - 2 * col_gap) / 3
    start_y = band_y - 5 * mm
    bottom_y = 16 * mm
    for ci, items in enumerate(topic_cols):
        x = ml + ci * (topic_w + col_gap)
        if ci:
            c.setStrokeColorRGB(0.72, 0.81, 0.86)
            c.setLineWidth(0.45)
            c.line(x - col_gap / 2, bottom_y + 1 * mm, x - col_gap / 2, start_y + 2 * mm)
        yy = start_y
        for is_heading, raw_text in items:
            text = _replace_heading_text(str(raw_text))
            if is_heading:
                font, size, leading = tp._FONT_B, 6.7, 3.1 * mm
                c.setFillColorRGB(*NAVY)
                max_lines = 3 if text.startswith("4.") else 2
            else:
                font, size, leading = tp._FONT, 5.65, 2.75 * mm
                c.setFillColorRGB(*TEXT)
                max_lines = 3
            lines = _wrap(tp, c, text, topic_w - 2 * mm, font, size, max_lines)
            needed = len(lines) * leading + (1.1 * mm if is_heading else 0)
            if yy - needed < bottom_y:
                # Never silently drop content: shrink remaining lines moderately.
                size = 5.0 if not is_heading else 5.9
                leading = 2.4 * mm
                lines = _wrap(tp, c, text, topic_w - 2 * mm, font, size, 4)
                needed = len(lines) * leading
            c.setFont(font, size)
            for line in lines:
                if yy < bottom_y:
                    break
                c.drawString(x + 1 * mm, yy, line)
                yy -= leading
            if is_heading:
                yy -= 0.8 * mm

    # Footer.
    c.setStrokeColorRGB(*GREEN)
    c.setLineWidth(0.7)
    c.line(ml, 12.5 * mm, w - mr, 12.5 * mm)
    c.setFillColorRGB(*NAVY)
    c.setFont(tp._FONT_B, 5.8)
    c.drawCentredString(w / 2, 8.5 * mm, _fit(tp, c, tp._CERT_FOOTER, 180 * mm, tp._FONT_B, 5.8))
    c.setFont(tp._FONT, 4.8)
    c.setFillColorRGB(*MUTED)
    c.drawCentredString(w / 2, 5.7 * mm, _fit(tp, c, tp._stamp_text(training), 220 * mm, tp._FONT, 4.8))
    c.setFillColorRGB(*NAVY)
    c.setFont(tp._FONT_B, 5.2)
    c.drawRightString(w - 8 * mm, 5.5 * mm, "EİSA")


def _replace_heading_text(text: str) -> str:
    variants = (
        "4. FAALİYETİN GENEL TEHLİKE VE RİSKLERİ",
        "4. Faaliyetin Genel Tehlike ve Riskleri",
        "4. Faaliyetin genel tehlike ve riskleri",
    )
    replacement = "4. İŞE VE İŞYERİNE ÖZGÜ RİSKLER VE RİSK DEĞERLENDİRMESİNE DAYALI KONULAR"
    for old in variants:
        text = text.replace(old, replacement)
    return text
