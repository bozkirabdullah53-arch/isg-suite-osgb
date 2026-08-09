"""Unicode 16:9 companion-PDF patch for Teaching V3 presentations.

This replaces only Teaching V3's internal PDF function. The legacy presentation
renderer is untouched. It uses local Unicode fonts already available to the
application/runtime, so Turkish characters never depend on PDF core fonts.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app.services import training_presentation_teaching_renderer as renderer

PDF_FONT = "TeachingV3Sans"
PDF_FONT_BOLD = "TeachingV3Sans-Bold"


def _register_fonts() -> None:
    if PDF_FONT in pdfmetrics.getRegisteredFontNames() and PDF_FONT_BOLD in pdfmetrics.getRegisteredFontNames():
        return
    candidates = (
        (
            Path(__file__).resolve().parents[1] / "assets" / "fonts" / "DejaVuSans.ttf",
            Path(__file__).resolve().parents[1] / "assets" / "fonts" / "DejaVuSans-Bold.ttf",
        ),
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ),
        (
            Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
            Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
        ),
        (
            Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
            Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
        ),
    )
    for regular, bold in candidates:
        if regular.exists():
            pdfmetrics.registerFont(TTFont(PDF_FONT, str(regular)))
            pdfmetrics.registerFont(TTFont(PDF_FONT_BOLD, str(bold if bold.exists() else regular)))
            return
    raise RuntimeError("Ders Sunumu V3 PDF için Unicode font bulunamadı.")


def _wrap(c, text: str, max_width: float, *, font=PDF_FONT, size=9.0, max_lines=4) -> list[str]:
    words = renderer._clean(text, 1200).split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if pdfmetrics.stringWidth(trial, font, size) <= max_width:
            current = trial
            continue
        if current:
            lines.append(current)
        current = word
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and words:
        last = lines[-1]
        if not last.endswith("…"):
            lines[-1] = last.rstrip(".,;:") + "…"
    return lines


def _draw_wrapped(c, text: str, x: float, y: float, max_width: float, *, font=PDF_FONT, size=9.0, leading=12.0, max_lines=4):
    for line in _wrap(c, text, max_width, font=font, size=size, max_lines=max_lines):
        c.setFont(font, size)
        c.drawString(x, y, line)
        y -= leading
    return y


def _round_box(c, x, y, w, h, *, fill, stroke=None, radius=8):
    c.setFillColorRGB(*fill)
    if stroke:
        c.setStrokeColorRGB(*stroke)
        c.setLineWidth(0.8)
        c.roundRect(x, y, w, h, radius, fill=1, stroke=1)
    else:
        c.roundRect(x, y, w, h, radius, fill=1, stroke=0)


def _draw_visual_panel(c, item: dict, manifest: dict, *, x: float, y: float, w: float, h: float):
    _round_box(c, x, y, w, h, fill=(0.96, 0.975, 0.985), stroke=(0.82, 0.87, 0.90), radius=10)
    c.setFillColorRGB(0.06, 0.46, 0.43)
    c.setFont(PDF_FONT_BOLD, 9.5)
    c.drawString(x + 16, y + h - 24, "GÖRSEL ÖĞRENME HARİTASI")

    hazard = renderer._blocks(item, "hazard_control_behavior_visual")
    if hazard:
        row = hazard[0]
        controls = row.get("controls") or []
        cards = [
            ("1 · TEHLİKE", renderer._clean(row.get("hazard"), 260), (0.74, 0.20, 0.20)),
            ("2 · KONTROL", renderer._clean(controls[0] if controls else "Kontrol tedbirini doğrula", 260), (0.06, 0.46, 0.43)),
            ("3 · GÜVENLİ DAVRANIŞ", renderer._clean(row.get("safe_behavior"), 260), (0.13, 0.58, 0.28)),
        ]
    else:
        risk = renderer._blocks(item, "risk_map_visual")
        if risk:
            values = risk[0].get("values") or manifest.get("technical_risk_tags") or []
            cards = [(f"RİSK {i}", renderer._clean(value, 220).replace("_", " "), (0.82, 0.52, 0.10)) for i, value in enumerate(values[:4], 1)]
        elif renderer._blocks(item, "control_hierarchy_visual"):
            cards = [
                ("1", "Ortadan kaldırma / azaltma", (0.13, 0.58, 0.28)),
                ("2", "Mühendislik ve toplu korunma", (0.06, 0.46, 0.43)),
                ("3", "Organizasyon ve talimat", (0.82, 0.52, 0.10)),
                ("4", "KKD — son kontrol katmanı", (0.74, 0.20, 0.20)),
            ]
        elif renderer._blocks(item, "emergency_flow_visual"):
            cards = [
                ("1", "Tehlikeyi fark et", (0.06, 0.46, 0.43)),
                ("2", "Alarm / bildirim", (0.06, 0.46, 0.43)),
                ("3", "Güvenli tahliye", (0.06, 0.46, 0.43)),
                ("4", "Toplanma ve sayım", (0.13, 0.58, 0.28)),
            ]
        else:
            takeaway = renderer._value(item, "key_takeaway") or "Tehlikeyi tanı; kontrolü doğrula; güvenli davranışı uygula."
            cards = [("ANA MESAJ", takeaway, (0.06, 0.46, 0.43))]

    card_h = min(78.0, max(54.0, (h - 58 - max(0, len(cards) - 1) * 8) / max(1, len(cards))))
    cy = y + h - 48 - card_h
    for title, body, accent in cards:
        if cy < y + 12:
            break
        _round_box(c, x + 14, cy, w - 28, card_h, fill=(1, 1, 1), stroke=(0.86, 0.89, 0.92), radius=7)
        c.setFillColorRGB(*accent)
        c.setFont(PDF_FONT_BOLD, 8.2)
        c.drawString(x + 28, cy + card_h - 18, title)
        c.setFillColorRGB(0.08, 0.15, 0.22)
        _draw_wrapped(c, body, x + 28, cy + card_h - 34, w - 56, size=7.8, leading=9.4, max_lines=4)
        cy -= card_h + 8


def _unicode_pdf(manifest: dict) -> bytes:
    _register_fonts()
    page_w = renderer.SLIDE_W * 72.0
    page_h = renderer.SLIDE_H * 72.0
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_w, page_h))
    c.setTitle("İSG Suite Ders Sunumu V3")
    slides = manifest.get("slides") or []

    for item in slides:
        section = str(item.get("section_id") or "")
        title = renderer._clean(item.get("title"), 180)
        position = int(item.get("position") or 0)
        c.setFillColorRGB(1, 1, 1)
        c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

        c.setFillColorRGB(0.025, 0.105, 0.18)
        c.rect(0, page_h - 48, page_w, 48, fill=1, stroke=0)
        c.setFillColorRGB(0.14, 0.78, 0.55)
        c.rect(0, page_h - 48, 6, 48, fill=1, stroke=0)
        c.setFillColorRGB(0.88, 0.97, 0.94)
        c.setFont(PDF_FONT_BOLD, 9.2)
        c.drawString(26, page_h - 29, (section.replace("_", " ") or "DERS SUNUMU").upper())

        c.setFillColorRGB(0.025, 0.105, 0.18)
        c.setFont(PDF_FONT_BOLD, 20)
        title_y = page_h - 82
        for line in _wrap(c, title, page_w - 52, font=PDF_FONT_BOLD, size=20, max_lines=2):
            c.drawString(26, title_y, line)
            title_y -= 24

        if section == "cover":
            nace = manifest.get("nace_snapshot") or {}
            training = manifest.get("training") or {}
            cards = [
                ("NACE / FAALİYET", f"{nace.get('nace_code','')} · {nace.get('nace_description','')}", (0.06, 0.46, 0.43)),
                ("TEHLİKE SINIFI", str(nace.get("hazard_class") or "—"), (0.82, 0.52, 0.10)),
                ("EĞİTİM TARİHİ", f"{training.get('start_date','')} → {training.get('end_date','')}", (0.13, 0.58, 0.28)),
            ]
            x = 32
            widths = [430, 205, 235]
            for idx, (label, body, accent) in enumerate(cards):
                w = widths[idx]
                _round_box(c, x, 220, w, 118, fill=(0.97, 0.985, 0.99), stroke=(0.84, 0.88, 0.91), radius=10)
                c.setFillColorRGB(*accent)
                c.setFont(PDF_FONT_BOLD, 9)
                c.drawString(x + 16, 310, label)
                c.setFillColorRGB(0.04, 0.12, 0.20)
                _draw_wrapped(c, body, x + 16, 286, w - 32, font=PDF_FONT_BOLD, size=11.2, leading=14, max_lines=4)
                x += w + 10
            c.setFillColorRGB(0.35, 0.42, 0.48)
            c.setFont(PDF_FONT, 8)
            c.drawString(32, 68, "Kaynak kontrollü · çevrimdışı vektör görseller · Türkçe Unicode PDF")
        else:
            left_x, left_w = 32, 430
            right_x, right_w = 494, page_w - 526
            body_top = min(title_y - 8, 410)
            c.setFillColorRGB(0.06, 0.46, 0.43)
            c.setFont(PDF_FONT_BOLD, 9.5)
            c.drawString(left_x, body_top, "DERS ANLATIMI")
            y = body_top - 18
            c.setFillColorRGB(0.08, 0.15, 0.22)
            for idx, point in enumerate(renderer._lesson_points(item)[:5], 1):
                _round_box(c, left_x, y - 58, left_w, 52, fill=(0.985, 0.99, 0.995), stroke=(0.86, 0.89, 0.92), radius=7)
                c.setFillColorRGB(0.06, 0.46, 0.43)
                c.setFont(PDF_FONT_BOLD, 8.3)
                c.drawString(left_x + 12, y - 20, str(idx))
                c.setFillColorRGB(0.08, 0.15, 0.22)
                _draw_wrapped(c, point, left_x + 32, y - 20, left_w - 46, size=8.2, leading=10, max_lines=3)
                y -= 62

            _draw_visual_panel(c, item, manifest, x=right_x, y=132, w=right_w, h=278)

            scenario = renderer._value(item, "case_scenario") or renderer._value(item, "check_question")
            if scenario:
                _round_box(c, 32, 56, page_w - 64, 58, fill=(1.0, 0.975, 0.90), stroke=(0.94, 0.82, 0.47), radius=8)
                c.setFillColorRGB(0.58, 0.36, 0.02)
                c.setFont(PDF_FONT_BOLD, 8.4)
                c.drawString(46, 92, "VAKA / BİLGİ KONTROLÜ")
                c.setFillColorRGB(0.12, 0.16, 0.20)
                _draw_wrapped(c, scenario, 46, 76, page_w - 92, size=7.7, leading=9, max_lines=3)

        source = renderer._sources(manifest, item)
        c.setFillColorRGB(0.34, 0.40, 0.46)
        c.setFont(PDF_FONT, 6.8)
        c.drawString(28, 19, renderer._clean(f"Kaynak: {source or 'Manifest kaynak kayıtları'}", 180))
        c.setFont(PDF_FONT_BOLD, 7.2)
        c.drawRightString(page_w - 28, 19, f"{position}/{len(slides)}")
        c.showPage()

    c.save()
    return buf.getvalue()


def install_teaching_unicode_pdf() -> dict[str, str]:
    current = renderer._pdf
    if getattr(current, "_teaching_unicode_pdf_active", False):
        return {"teaching_v3_unicode_pdf": "already-active"}
    _unicode_pdf._teaching_unicode_pdf_active = True
    renderer._pdf = _unicode_pdf
    return {"teaching_v3_unicode_pdf": "active"}


__all__ = ["install_teaching_unicode_pdf", "PDF_FONT", "PDF_FONT_BOLD"]
