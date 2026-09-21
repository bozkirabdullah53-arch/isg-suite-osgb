"""EİSA — abone listesi PDF dışa aktarımları (global panel).

OSGB üyeleri ve bireysel üyeler için ortak yatay A4 tablo düzeni;
``annual_plan_pdf`` ile aynı reportlab desenini kullanır.
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

_FONT = "Helvetica"
_FONT_B = "Helvetica-Bold"
_fonts_ok = False

STATUS_TR = {
    "trial": "Deneme",
    "active": "Aktif",
    "past_due": "Süresi doldu",
    "suspended": "Askıda",
    "cancelled": "İptal",
}

OSGB_COLUMNS = [
    (26, "#"),
    (168, "Abone (OSGB)"),
    (112, "Yetkili"),
    (140, "E-posta"),
    (78, "Telefon"),
    (96, "Paket"),
    (62, "Abonelik"),
    (54, "Bitiş"),
    (46, "Hesap"),
]

INDIVIDUAL_COLUMNS = [
    (26, "#"),
    (140, "Üye"),
    (150, "E-posta"),
    (80, "Telefon"),
    (110, "Belge"),
    (80, "Paket"),
    (60, "Abonelik"),
    (40, "Kalan"),
    (55, "Bitiş"),
    (45, "Hesap"),
]


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
            pdfmetrics.registerFont(TTFont("EisaTR", str(p)))
            _FONT = "EisaTR"
            break
    for p in bold_candidates:
        if p.is_file():
            pdfmetrics.registerFont(TTFont("EisaTR-B", str(p)))
            _FONT_B = "EisaTR-B"
            break
    else:
        if _FONT == "EisaTR":
            _FONT_B = "EisaTR"
    _fonts_ok = True


def _fit(c, text: str, width: float, font: str, size: float) -> str:
    t = text or ""
    if c.stringWidth(t, font, size) <= width:
        return t
    while t and c.stringWidth(t + "…", font, size) > width:
        t = t[:-1]
    return (t + "…") if t else ""


def _fmt_date(value) -> str:
    if not value:
        return "—"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y")
    return str(value)


def _cert_label(row: dict) -> str:
    parts = [row.get("certificate_class"), row.get("certificate_number")]
    parts = [str(p) for p in parts if p]
    return " / ".join(parts) if parts else "—"


def _days_label(row: dict) -> str:
    days = row.get("days_remaining")
    if days is None:
        return "—"
    try:
        return str(int(days))
    except (TypeError, ValueError):
        return "—"


def _build_list_pdf(
    *,
    header_title: str,
    title: str,
    count_label: str,
    columns: list[tuple[int, str]],
    rows: list[dict],
    cell_values,
    search: str | None,
    generated_at: datetime | None,
) -> bytes:
    _ensure_fonts()
    buf = BytesIO()
    page = landscape(A4)
    c = canvas.Canvas(buf, pagesize=page)
    w, h = page
    ml, mr = 28, 28
    uw = w - ml - mr
    olusturma = (generated_at or datetime.now()).strftime("%d.%m.%Y %H:%M")

    def draw_table_head(y: float) -> float:
        c.setFillColorRGB(0.93, 0.95, 0.98)
        c.rect(ml, y - 4, uw, 16, fill=1, stroke=0)
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.setFont(_FONT_B, 7)
        x = ml + 2
        for width, label in columns:
            c.drawString(x, y, label)
            x += width
        return y - 18

    def new_header(page_no: int) -> float:
        c.setFillColorRGB(0.12, 0.27, 0.55)
        c.rect(0, h - 48, w, 48, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.setFont(_FONT_B, 12)
        c.drawCentredString(w / 2, h - 22, header_title)
        c.setFont(_FONT, 8)
        c.drawCentredString(w / 2, h - 36, title or "")
        y = h - 64
        c.setFillColorRGB(0.2, 0.2, 0.2)
        c.setFont(_FONT, 8)
        meta = f"Oluşturma: {olusturma}  |  {count_label}: {len(rows)}  |  Sayfa {page_no}"
        if search:
            meta += f"  |  Arama: “{search}”"
        c.drawString(ml, y, _fit(c, meta, uw, _FONT, 8))
        y -= 16
        return draw_table_head(y)

    page_no = 1
    y = new_header(page_no)
    row_h = 12

    if not rows:
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.setFont(_FONT, 8)
        c.drawString(ml + 2, y, "Listelenecek kayıt yok.")
        y -= row_h

    for idx, row in enumerate(rows, start=1):
        if y < 56:
            c.showPage()
            page_no += 1
            y = new_header(page_no)

        if idx % 2 == 0:
            c.setFillColorRGB(0.97, 0.98, 1)
            c.rect(ml, y - 4, uw, row_h, fill=1, stroke=0)

        vals = cell_values(row, idx)
        c.setFillColorRGB(0.15, 0.15, 0.15)
        c.setFont(_FONT, 7)
        x = ml + 2
        for (width, _label), text in zip(columns, vals):
            c.drawString(x, y, _fit(c, str(text), width - 4, _FONT, 7))
            x += width
        y -= row_h

    y -= 6
    c.setStrokeColorRGB(0.7, 0.75, 0.85)
    c.line(ml, y, w - mr, y)
    y -= 12
    c.setFillColorRGB(0.45, 0.45, 0.45)
    c.setFont(_FONT, 6)
    c.drawString(ml, y, "İSG Suite OSGB — EİSA Platform. Bu liste yalnızca platform yönetimi içindir; üçüncü kişilerle paylaşılamaz.")

    c.save()
    buf.seek(0)
    return buf.read()


def _osgb_cells(row: dict, idx: int) -> list[str]:
    if not row.get("is_active", True):
        status = "Askıda"
    else:
        raw = row.get("effective_status") or row.get("subscription_status")
        status = STATUS_TR.get(str(raw or ""), "—")
    if row.get("effective_status") == "trial" or row.get("subscription_status") == "trial":
        end = _fmt_date(row.get("trial_ends_at"))
    else:
        end = _fmt_date(row.get("current_period_ends_at"))
    return [
        str(idx),
        row.get("name") or "—",
        row.get("responsible_manager") or "—",
        row.get("contact_email") or "—",
        row.get("contact_phone") or "—",
        row.get("package_name") or "—",
        status,
        end,
        "Aktif" if row.get("is_active", True) else "Pasif",
    ]


def build_osgb_subscribers_pdf(
    *,
    rows: list[dict],
    title: str = "OSGB Abone Listesi",
    search: str | None = None,
    generated_at: datetime | None = None,
) -> bytes:
    """EİSA global panel — abone (OSGB üyesi) liste PDF'i."""
    return _build_list_pdf(
        header_title="EİSA — OSGB ABONE LİSTESİ",
        title=title,
        count_label="Toplam abone",
        columns=OSGB_COLUMNS,
        rows=rows,
        cell_values=_osgb_cells,
        search=search,
        generated_at=generated_at,
    )


def _individual_cells(row: dict, idx: int) -> list[str]:
    raw = row.get("effective_status") or row.get("status")
    status = STATUS_TR.get(str(raw or ""), "—")
    if str(raw or "") == "trial":
        end = _fmt_date(row.get("trial_ends_at"))
    else:
        end = _fmt_date(row.get("current_period_ends_at"))
    account_active = row.get("account_active")
    if account_active is None:
        account_active = True
    return [
        str(idx),
        row.get("specialist_name") or row.get("osgb_name") or "—",
        row.get("specialist_email") or row.get("contact_email") or "—",
        row.get("specialist_phone") or row.get("contact_phone") or "—",
        _cert_label(row),
        row.get("package_name") or "—",
        status,
        _days_label(row),
        end,
        "Aktif" if account_active else "Pasif",
    ]


def build_individual_subscribers_pdf(
    *,
    rows: list[dict],
    title: str = "Bireysel Üye Listesi",
    search: str | None = None,
    generated_at: datetime | None = None,
) -> bytes:
    """EİSA global panel — bireysel İSG uzmanı üye liste PDF'i."""
    return _build_list_pdf(
        header_title="EİSA — BİREYSEL ÜYE LİSTESİ",
        title=title,
        count_label="Toplam bireysel üye",
        columns=INDIVIDUAL_COLUMNS,
        rows=rows,
        cell_values=_individual_cells,
        search=search,
        generated_at=generated_at,
    )
