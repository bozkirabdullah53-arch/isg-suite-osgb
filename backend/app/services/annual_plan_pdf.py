"""Yıllık çalışma planı PDF — imza kutulu, mevzuat dayanaklı."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

_FONT = "Helvetica"
_FONT_B = "Helvetica-Bold"
_fonts_ok = False

MONTHS = [
    "",
    "Ocak",
    "Şubat",
    "Mart",
    "Nisan",
    "Mayıs",
    "Haziran",
    "Temmuz",
    "Ağustos",
    "Eylül",
    "Ekim",
    "Kasım",
    "Aralık",
]

STATUS_TR = {
    "planned": "Planlandı",
    "in_progress": "Devam Ediyor",
    "completed": "Tamamlandı",
    "delayed": "Gecikti",
    "cancelled": "İptal",
}

CATEGORIES = {
    "yillik_calisma": "Yıllık Çalışma",
    "egitim": "Eğitim",
    "saglik": "Sağlık",
    "periyodik": "Periyodik",
    "tatbikat": "Tatbikat",
    "kkd": "KKD",
    "diger": "Diğer",
}


def _ensure_fonts() -> None:
    global _FONT, _FONT_B, _fonts_ok
    if _fonts_ok:
        return
    candidates = [
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\segoeui.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    ]
    bold_candidates = [
        Path(r"C:\Windows\Fonts\arialbd.ttf"),
        Path(r"C:\Windows\Fonts\segoeuib.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ]
    for p in candidates:
        if p.is_file():
            pdfmetrics.registerFont(TTFont("PlanTR", str(p)))
            _FONT = "PlanTR"
            break
    for p in bold_candidates:
        if p.is_file():
            pdfmetrics.registerFont(TTFont("PlanTR-B", str(p)))
            _FONT_B = "PlanTR-B"
            break
    else:
        if _FONT == "PlanTR":
            _FONT_B = "PlanTR"
    _fonts_ok = True


def _fit(c, text: str, width: float, font: str, size: float) -> str:
    t = text or ""
    if c.stringWidth(t, font, size) <= width:
        return t
    while t and c.stringWidth(t + "…", font, size) > width:
        t = t[:-1]
    return (t + "…") if t else ""


def build_annual_plan_pdf(
    *,
    company_name: str,
    year: int,
    items: list,
    hazard_class: str | None = None,
    specialist_name: str | None = None,
    physician_name: str | None = None,
    employer_name: str | None = None,
) -> bytes:
    """Yıl başı yıllık çalışma planı PDF (imza alanlı)."""
    _ensure_fonts()
    buf = BytesIO()
    page = A4
    c = canvas.Canvas(buf, pagesize=page)
    w, h = page
    ml, mr = 36, 36
    uw = w - ml - mr
    bugun = datetime.now().strftime("%d.%m.%Y")

    def new_header(page_no: int) -> float:
        c.setFillColorRGB(0.12, 0.27, 0.55)
        c.rect(0, h - 48, w, 48, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.setFont(_FONT_B, 12)
        c.drawCentredString(w / 2, h - 22, f"YILLIK ÇALIŞMA PLANI — {year}")
        c.setFont(_FONT, 8)
        c.drawCentredString(w / 2, h - 36, company_name or "")
        y = h - 64
        c.setFillColorRGB(0.2, 0.2, 0.2)
        c.setFont(_FONT, 8)
        meta = f"Tehlike sınıfı: {hazard_class or '—'}  |  Düzenleme: {bugun}  |  Sayfa {page_no}"
        c.drawString(ml, y, meta)
        y -= 14
        c.setFont(_FONT, 7)
        c.setFillColorRGB(0.35, 0.35, 0.35)
        note = (
            "Dayanak: İSG Hizmetleri Yönetmeliği — yıllık çalışma planı; "
            "6331 sayılı İSG Kanunu ve ilgili alt yönetmelikler. "
            "Bu belge planlanan faaliyetleri gösterir; gerçekleşme yıllık değerlendirme raporunda izlenir."
        )
        c.drawString(ml, y, _fit(c, note, uw, _FONT, 7))
        return y - 16

    page_no = 1
    y = new_header(page_no)

    # Column header
    headers = [
        (28, "Ay"),
        (70, "Kategori"),
        (170, "Faaliyet"),
        (90, "Mevzuat"),
        (70, "Sorumlu"),
        (55, "Hedef"),
        (50, "Durum"),
    ]
    c.setFillColorRGB(0.93, 0.95, 0.98)
    c.rect(ml, y - 4, uw, 16, fill=1, stroke=0)
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.setFont(_FONT_B, 7)
    x = ml + 2
    for width, label in headers:
        c.drawString(x, y, label)
        x += width
    y -= 18

    sorted_items = sorted(items, key=lambda it: (getattr(it, "month", 0) or 0, getattr(it, "id", 0) or 0))
    for it in sorted_items:
        if y < 110:
            c.showPage()
            page_no += 1
            y = new_header(page_no)
            c.setFillColorRGB(0.93, 0.95, 0.98)
            c.rect(ml, y - 4, uw, 16, fill=1, stroke=0)
            c.setFillColorRGB(0.1, 0.1, 0.1)
            c.setFont(_FONT_B, 7)
            x = ml + 2
            for width, label in headers:
                c.drawString(x, y, label)
                x += width
            y -= 18

        month = int(getattr(it, "month", 0) or 0)
        cat = CATEGORIES.get(getattr(it, "category", None) or "", getattr(it, "category", None) or "—")
        activity = getattr(it, "activity", None) or "—"
        legal = getattr(it, "legal_basis", None) or "—"
        resp = getattr(it, "responsible_name", None) or "—"
        target = getattr(it, "target_date", None)
        target_s = target.strftime("%d.%m.%Y") if target else "—"
        st = getattr(it, "status", None)
        st_s = STATUS_TR.get(st.value if hasattr(st, "value") else str(st or ""), str(st or "—"))

        c.setFillColorRGB(0.15, 0.15, 0.15)
        c.setFont(_FONT, 7)
        vals = [
            (28, MONTHS[month] if 1 <= month <= 12 else str(month)),
            (70, cat),
            (170, activity),
            (90, legal),
            (70, resp),
            (55, target_s),
            (50, st_s),
        ]
        x = ml + 2
        row_h = 11
        for width, text in vals:
            c.drawString(x, y, _fit(c, str(text), width - 4, _FONT, 7))
            x += width
        y -= row_h

    # Signature block
    if y < 130:
        c.showPage()
        page_no += 1
        y = new_header(page_no)
    y -= 10
    c.setStrokeColorRGB(0.7, 0.75, 0.85)
    c.line(ml, y, w - mr, y)
    y -= 18
    c.setFillColorRGB(0.12, 0.27, 0.55)
    c.setFont(_FONT_B, 9)
    c.drawString(ml, y, "Onay")
    y -= 12
    c.setFillColorRGB(0.3, 0.3, 0.3)
    c.setFont(_FONT, 7)
    c.drawString(ml, y, "Plan, ilgili mevzuat çerçevesinde hazırlanmış olup işveren onayına sunulur.")
    y -= 28
    box_w = (uw - 20) / 3
    signers = [
        ("İSG Uzmanı", specialist_name or ""),
        ("İşyeri Hekimi", physician_name or ""),
        ("İşveren / Vekil", employer_name or ""),
    ]
    for i, (role, name) in enumerate(signers):
        x = ml + i * (box_w + 10)
        c.setStrokeColorRGB(0.75, 0.78, 0.88)
        c.setFillColorRGB(0.97, 0.98, 1)
        c.rect(x, y - 50, box_w, 62, fill=1, stroke=1)
        c.setFillColorRGB(0.12, 0.27, 0.55)
        c.setFont(_FONT_B, 8)
        c.drawCentredString(x + box_w / 2, y + 2, role)
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.setFont(_FONT, 8)
        c.drawCentredString(x + box_w / 2, y - 16, _fit(c, name or " ", box_w - 8, _FONT, 8))
        c.setStrokeColorRGB(0.4, 0.4, 0.4)
        c.line(x + 10, y - 34, x + box_w - 10, y - 34)
        c.setFillColorRGB(0.45, 0.45, 0.45)
        c.setFont(_FONT, 6)
        c.drawCentredString(x + box_w / 2, y - 44, "İmza / Tarih")

    c.save()
    buf.seek(0)
    return buf.read()
