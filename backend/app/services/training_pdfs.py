"""Eğitim katılım belgesi + imza formu PDF — İSG PRO 2026 layout parity (reportlab)."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily, stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app.core.config import settings
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

# PRO dayanak / dipnot (ürün adı yok)
_DEFAULT_STAMP = (
    "6331 sayılı İş Sağlığı ve Güvenliği Kanunu ve "
    "Çalışanların İş Sağlığı ve Güvenliği Eğitimlerinin Usul ve Esasları Hakkında Yönetmelik "
    "kapsamında düzenlenmiştir."
)
_CERT_FOOTER = "6331 Sayılı İş Sağlığı ve Güvenliği Kanunu kapsamında düzenlenmiştir."

# PRO palette
_BLUE = (13 / 255, 110 / 255, 253 / 255)
_BLUE_DARK = (10 / 255, 90 / 255, 210 / 255)
_SLATE = (45 / 255, 70 / 255, 95 / 255)
_SLATE_SOFT = (185 / 255, 200 / 255, 215 / 255)


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
    last_err: Exception | None = None
    for regular, bold in candidates:
        if not regular.exists():
            continue
        try:
            pdfmetrics.registerFont(TTFont("IsgSans", str(regular)))
            pdfmetrics.registerFont(TTFont("IsgSans-Bold", str(bold if bold.exists() else regular)))
            try:
                registerFontFamily(
                    "IsgSans",
                    normal="IsgSans",
                    bold="IsgSans-Bold",
                    italic="IsgSans",
                    boldItalic="IsgSans-Bold",
                )
            except Exception:
                pass
            _FONT, _FONT_B = "IsgSans", "IsgSans-Bold"
            if stringWidth("ğüşıİÖÇ", _FONT, 10) < 1:
                raise RuntimeError("Font Türkçe glyph taşımıyor.")
            return
        except Exception as exc:
            last_err = exc
            continue
    raise RuntimeError(f"Eğitim PDF için Unicode font bulunamadı. Son hata: {last_err}")


try:
    _register_fonts()
except Exception:
    pass


def _ensure_fonts() -> None:
    if _FONT in ("Helvetica", "Helvetica-Bold") or not _FONT:
        _register_fonts()


def _rgb(c: canvas.Canvas, rgb: tuple[float, float, float], *, fill=False, stroke=False):
    if fill:
        c.setFillColorRGB(*rgb)
    if stroke:
        c.setStrokeColorRGB(*rgb)


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


def _resolve_logo(training) -> Path | None:
    rel = getattr(training, "logo_path", None) or ""
    if not rel:
        return None
    root = Path(settings.upload_dir).resolve()
    path = (root / rel).resolve()
    if root not in path.parents and path != root:
        return None
    return path if path.is_file() else None


def _draw_logo(c: canvas.Canvas, training, *, x: float, y: float, max_w: float, max_h: float) -> bool:
    path = _resolve_logo(training)
    if not path:
        return False
    try:
        img = ImageReader(str(path))
        iw, ih = img.getSize()
        if not iw or not ih:
            return False
        scale = min(max_w / iw, max_h / ih)
        dw, dh = iw * scale, ih * scale
        c.drawImage(img, x, y + (max_h - dh) / 2, width=dw, height=dh, mask="auto")
        return True
    except Exception:
        return False


def _stamp_text(training) -> str:
    return (getattr(training, "stamp_text", None) or "").strip() or _DEFAULT_STAMP


def build_attendance_pdf(*, company_name: str, training, employees: dict) -> bytes:
    """PRO: KATILIMCI İMZA FORMU (İSG-EĞT-KF-01), 10 kişi/sayfa."""
    _ensure_fonts()
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
    # PRO: outer slate frame + inner soft frame
    c.setLineWidth(0.9)
    _rgb(c, _SLATE, stroke=True)
    c.rect(5 * mm, 5 * mm, w - 10 * mm, h - 10 * mm, stroke=1, fill=0)
    c.setLineWidth(0.4)
    _rgb(c, _SLATE_SOFT, stroke=True)
    c.rect(7 * mm, 7 * mm, w - 14 * mm, h - 14 * mm, stroke=1, fill=0)

    ml, mr = 8 * mm, 8 * mm
    uw = w - ml - mr  # ~281mm

    # Header band
    _rgb(c, (226 / 255, 235 / 255, 244 / 255), fill=True)
    c.rect(7 * mm, h - 29 * mm, w - 14 * mm, 22 * mm, fill=1, stroke=0)
    _rgb(c, _SLATE, stroke=True)
    c.setLineWidth(0.8)
    c.line(7 * mm, h - 29 * mm, w - 7 * mm, h - 29 * mm)

    has_logo = bool(_resolve_logo(training))
    if has_logo:
        c.setFillColorRGB(1, 1, 1)
        c.setStrokeColorRGB(*_SLATE_SOFT)
        c.rect(10 * mm, h - 27 * mm, 18 * mm, 18 * mm, fill=1, stroke=1)
        _draw_logo(c, training, x=11.5 * mm, y=h - 25.5 * mm, max_w=15 * mm, max_h=15 * mm)

    _rgb(c, _SLATE, fill=True)
    c.setFont(_FONT_B, 10.5)
    c.drawCentredString(w / 2, h - 15 * mm, "İŞ SAĞLIĞI VE GÜVENLİĞİ TEMEL EĞİTİMİ")
    c.setFont(_FONT_B, 12)
    c.drawCentredString(w / 2, h - 21 * mm, "KATILIMCI İMZA FORMU")
    c.setFont(_FONT, 6.5)
    c.setFillColorRGB(0.35, 0.35, 0.4)
    c.drawCentredString(
        w / 2,
        h - 26.5 * mm,
        "Eğitim kaydı, katılımcı listesi ve eğitim konuları aynı veri setine bağlıdır.",
    )

    c.setFont(_FONT, 6.5)
    c.setFillColorRGB(0.3, 0.35, 0.4)
    c.drawRightString(w - mr, h - 12 * mm, "Form No: İSG-EĞT-KF-01")
    c.drawRightString(w - mr, h - 16 * mm, f"Düzenleme: {bugun}")
    c.drawRightString(w - mr, h - 20 * mm, f"Sayfa: {page_no}/{total_pages}")

    # Info grid — PRO 13 cells
    egitici = training.instructor_name or "—"
    if training.instructor_qualification:
        egitici = f"{egitici} — {training.instructor_qualification}"
    deger = training.evaluation_method or "—"
    if training.passing_score:
        deger = f"{deger} / Geçme: {training.passing_score}"

    info = [
        ("Firma", company_name),
        ("Eğitimin Adı", training.title),
        ("Eğitim Tarihi", _fmt_date(training.start_date)),
        ("Eğitim Süresi", kural["sure"]),
        ("Yenileme Periyodu", kural["yenileme"]),
        ("Tehlike Sınıfı", training.hazard_class),
        ("Eğitim Türü", training.training_type),
        ("Eğitim Şekli", training.delivery_method),
        ("Sektör / İş Kolu", sektor_label),
        ("Eğitim Yeri", training.location or "—"),
        ("Eğitici / Yeterlilik", egitici),
        ("Değerlendirme / Puan", deger),
        ("Doğrulama Kodu", training.verification_code or "—"),
    ]
    col_w = uw / 4
    row_h = 8 * mm
    y0 = h - 34 * mm
    for i, (lab, val) in enumerate(info):
        r, col = divmod(i, 4)
        x = ml + col * col_w
        y = y0 - r * row_h
        c.setStrokeColorRGB(180 / 255, 195 / 255, 210 / 255)
        c.setFillColorRGB(247 / 255, 249 / 255, 252 / 255)
        c.rect(x, y - row_h, col_w, row_h, fill=1, stroke=1)
        c.setFillColorRGB(0.3, 0.35, 0.4)
        c.setFont(_FONT_B, 6)
        c.drawString(x + 1.5 * mm, y - 3 * mm, lab)
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.setFont(_FONT, 7)
        c.drawString(x + 1.5 * mm, y - 6.5 * mm, _fit(c, val, col_w - 3 * mm, _FONT, 7))

    # Purpose / topics / dayanak box (PRO)
    konu_y_top = h - 72 * mm
    konu_h = 22 * mm
    c.setFillColorRGB(235 / 255, 241 / 255, 247 / 255)
    c.setStrokeColorRGB(160 / 255, 180 / 255, 200 / 255)
    c.rect(ml, konu_y_top - konu_h, uw, konu_h, fill=1, stroke=1)

    c.setFillColorRGB(*_SLATE)
    c.setFont(_FONT_B, 7)
    c.drawString(ml + 2 * mm, konu_y_top - 4 * mm, "Eğitimin Amacı:")
    c.setFont(_FONT, 6.2)
    purpose = (
        "Çalışanların meslek hastalığı ve iş kazasına maruz kalma riskini azaltmak; "
        "sağlıklı ve güvenli çalışma ortamı oluşturmak."
    )
    for li, line in enumerate(_wrap(c, purpose, uw - 36 * mm, _FONT, 6.2, 2)):
        c.drawString(ml + 32 * mm, konu_y_top - 4 * mm - li * 3.2 * mm, line)

    c.setFont(_FONT_B, 7)
    c.drawString(ml + 2 * mm, konu_y_top - 11 * mm, "Belgedeki Konu Başlıkları:")
    c.setFont(_FONT, 5.8)
    for li, line in enumerate(_wrap(c, konu_ozeti, uw - 48 * mm, _FONT, 5.8, 3)):
        c.drawString(ml + 42 * mm, konu_y_top - 11 * mm - li * 3.1 * mm, line)

    c.setFont(_FONT_B, 7)
    c.drawString(ml + 2 * mm, konu_y_top - 20 * mm, "Dayanak:")
    c.setFont(_FONT, 6)
    dayanak = (
        "6331 sayılı İş Sağlığı ve Güvenliği Kanunu ve çalışanların İSG eğitimlerine "
        "ilişkin mevzuat kapsamında düzenlenmiştir."
    )
    c.drawString(
        ml + 18 * mm,
        konu_y_top - 20 * mm,
        _fit(c, dayanak, uw - 22 * mm, _FONT, 6),
    )

    # Table — PRO column widths (mm): 10,55,31,45,58,20,62
    table_y = h - 80 * mm
    cols_mm = [10, 55, 31, 45, 58, 20, 62]
    scale = uw / (sum(cols_mm) * mm)
    cols = [x * mm * scale for x in cols_mm]
    headers = ["Sıra", "Adı Soyadı", "T.C. Kimlik No", "Görevi / Bölümü", "İmzası", "Not", "Açıklama"]
    header_h = 7 * mm
    row_h = 8.4 * mm

    x = ml
    for cw, ht in zip(cols, headers):
        c.setFillColorRGB(*_SLATE)
        c.setStrokeColorRGB(*_SLATE)
        c.rect(x, table_y - header_h, cw, header_h, fill=1, stroke=1)
        c.setFillColorRGB(1, 1, 1)
        c.setFont(_FONT_B, 6.5)
        c.drawCentredString(x + cw / 2, table_y - 4.6 * mm, ht)
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
            c.setStrokeColorRGB(180 / 255, 190 / 255, 200 / 255)
            c.setFillColorRGB(1, 1, 1)
            c.rect(x, y - row_h, cw, row_h, fill=1, stroke=1)
            c.setFillColorRGB(0.1, 0.1, 0.1)
            font = _FONT_B if ci == 1 and val else _FONT
            size = 6.2 if ci == 3 else 7
            c.setFont(font, size)
            txt = _fit(c, val, cw - 2 * mm, font, size)
            if ci in (0, 2, 5):
                c.drawCentredString(x + cw / 2, y - 5.2 * mm, txt)
            else:
                c.drawString(x + 1.2 * mm, y - 5.2 * mm, txt)
            x += cw
        y -= row_h

    # Signature boxes — PRO titles
    physician = (getattr(training, "workplace_physician", None) or "").strip()
    employer = (getattr(training, "employer_representative", None) or "").strip()
    imza_cols = [
        ("Eğitimi Veren", training.instructor_name or ""),
        ("Eğitimi Veren İşyeri Hekimi", physician),
        ("İşveren / İşveren Vekili", employer),
    ]
    imza_y = 12 * mm
    imza_h = 23 * mm
    box_w = uw / 3
    for i, (title, name) in enumerate(imza_cols):
        x = ml + i * box_w
        c.setFillColorRGB(247 / 255, 249 / 255, 252 / 255)
        c.setStrokeColorRGB(160 / 255, 180 / 255, 200 / 255)
        c.rect(x, imza_y, box_w, imza_h, fill=1, stroke=1)
        c.setFillColorRGB(*_SLATE)
        c.setFont(_FONT_B, 6.5)
        c.drawCentredString(x + box_w / 2, imza_y + imza_h - 5 * mm, title)
        c.setFont(_FONT_B, 7)
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.drawCentredString(x + box_w / 2, imza_y + imza_h - 10.5 * mm, _fit(c, name or " ", box_w - 6 * mm, _FONT_B, 7))
        c.setStrokeColorRGB(0.4, 0.4, 0.4)
        c.line(x + 12 * mm, imza_y + 8 * mm, x + box_w - 12 * mm, imza_y + 8 * mm)
        c.setFont(_FONT, 5.8)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.drawCentredString(x + box_w / 2, imza_y + 3.5 * mm, "Kaşe / İmza")

    c.setFont(_FONT, 5.5)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawCentredString(
        w / 2,
        8 * mm,
        _fit(
            c,
            "Bu form, aynı eğitim kaydına bağlı katılımcı imza listesi olarak hazırlanmıştır. "
            "İmzalar eğitim katılımının doğrulanması amacıyla alınır.",
            uw - 8 * mm,
            _FONT,
            5.5,
        ),
    )


def build_certificates_pdf(*, company_name: str, training, employees: dict) -> bytes:
    """PRO: kişi başı katılım belgesi — 2 sütun konular + dakika."""
    _ensure_fonts()
    participants = list(training.participants or [])
    if not participants:
        raise ValueError("Katılım belgesi için en az bir katılımcı gerekli. Eğitim kaydına personel ekleyin.")

    buf = BytesIO()
    page = landscape(A4)
    c = canvas.Canvas(buf, pagesize=page)
    w, h = page
    bugun = datetime.now().strftime("%d.%m.%Y")
    bugun_kod = datetime.now().strftime("%d%m%Y")
    egitim_tarihi = _fmt_date(training.start_date)
    if getattr(training, "end_date", None):
        end = _fmt_date(training.end_date)
        if end and end != egitim_tarihi:
            egitim_tarihi = f"{egitim_tarihi} - {end}"
    kural = tehlike_kurali(training.hazard_class)
    sektor = sektor_kodu_cozumle(training.sector)
    sol, sag, _, _ = egitim_konularini_hazirla(training.hazard_class, sektor)

    for i, p in enumerate(participants, 1):
        e = employees.get(p.employee_id)
        # PRO belge no: ISG-GGAAYYYY-001 (üretim tarihi + sıra)
        belge_no = f"ISG-{bugun_kod}-{i:03d}"
        _draw_certificate_page(
            c, w, h,
            company_name=company_name,
            training=training,
            employee=e,
            belge_no=belge_no,
            bugun=bugun,
            egitim_tarihi=egitim_tarihi,
            kural=kural,
            sektor=sektor,
            sol=sol,
            sag=sag,
        )
        c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()


def _draw_certificate_page(c, w, h, *, company_name, training, employee, belge_no, bugun, egitim_tarihi, kural, sektor, sol, sag):
    ml, mr = 8 * mm, 8 * mm
    uw = w - ml - mr

    # Double border — PRO
    c.setLineWidth(1.2)
    _rgb(c, _BLUE, stroke=True)
    c.rect(3 * mm, 3 * mm, w - 6 * mm, h - 6 * mm, stroke=1, fill=0)
    c.setLineWidth(0.4)
    c.setStrokeColorRGB(200 / 255, 215 / 255, 240 / 255)
    c.rect(5 * mm, 5 * mm, w - 10 * mm, h - 10 * mm, stroke=1, fill=0)

    # Blue header band
    _rgb(c, _BLUE, fill=True)
    c.rect(3 * mm, h - 27 * mm, w - 6 * mm, 24 * mm, fill=1, stroke=0)
    _rgb(c, _BLUE_DARK, fill=True)
    c.rect(3 * mm, h - 27.5 * mm, w - 6 * mm, 0.5 * mm, fill=1, stroke=0)

    has_logo = bool(_resolve_logo(training))
    if has_logo:
        c.setFillColorRGB(1, 1, 1)
        c.setStrokeColorRGB(200 / 255, 215 / 255, 240 / 255)
        c.rect(7 * mm, h - 25 * mm, 22 * mm, 20 * mm, fill=1, stroke=1)
        _draw_logo(c, training, x=8.5 * mm, y=h - 23.5 * mm, max_w=19 * mm, max_h=17 * mm)

    c.setFillColorRGB(1, 1, 1)
    c.setFont(_FONT_B, 11)
    c.drawCentredString(w / 2, h - 12 * mm, "TEMEL İŞ SAĞLIĞI VE GÜVENLİĞİ EĞİTİMİ KATILIM BELGESİ")
    c.setFont(_FONT_B, 9)
    c.drawCentredString(w / 2, h - 19 * mm, company_name or "")

    # Referans — PRO: Belge No / Tarih + yalnızca Süre│Tür│Şekil│Doğrulama
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.setFont(_FONT, 7)
    c.drawString(ml, h - 33 * mm, f"Belge No: {belge_no}")
    c.drawRightString(w - mr, h - 33 * mm, f"Tarih: {bugun}")
    meta_parts = [
        f"Süre: {kural['sure']}",
        f"Tür: {training.training_type}",
        f"Şekil: {training.delivery_method}",
    ]
    if training.verification_code:
        meta_parts.append(f"Doğrulama: {training.verification_code}")
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.drawCentredString(w / 2, h - 38 * mm, _fit(c, "  │  ".join(meta_parts), uw, _FONT, 7))

    name = employee.full_name if employee else "—"
    tc = (getattr(employee, "national_id_masked", None) or "") if employee else ""
    gorev = (employee.job_title or "") if employee else ""

    c.setFillColorRGB(*_BLUE)
    c.setFont(_FONT, 8)
    c.drawCentredString(w / 2, h - 46 * mm, "Sn.")
    c.setFillColorRGB(0, 0, 0)
    c.setFont(_FONT_B, 16)
    c.drawCentredString(w / 2, h - 54 * mm, name)
    c.setFillColorRGB(0.35, 0.35, 0.35)
    c.setFont(_FONT, 7.5)
    c.drawString(ml, h - 62 * mm, f"T.C. Kimlik No: {tc}" if tc else "T.C. Kimlik No: —")
    c.drawRightString(w - mr, h - 62 * mm, f"Görevi: {gorev}" if gorev else "Görevi: —")
    c.drawCentredString(w / 2, h - 67 * mm, f"Eğitim Tarihi: {egitim_tarihi}")

    # Legal — PRO exact lines
    c.setFillColorRGB(60 / 255, 60 / 255, 60 / 255)
    c.setFont(_FONT, 6.5)
    legal = [
        "Yukarıda adı geçen çalışanın, 6331 Sayılı Kanun Gereği, Çalışanların İş Sağlığı ve Güvenliği",
        "Eğitimlerinin Usul ve Esasları Hakkında Yönetmelik kapsamında verilen, iş sağlığı ve güvenliği",
        "eğitimlerini, başarıyla tamamlayarak bu eğitim belgesini almaya hak kazanmıştır.",
    ]
    y = h - 74 * mm
    for line in legal:
        c.drawCentredString(w / 2, y, line)
        y -= 4 * mm

    # Signature boxes — PRO roles (unvan altta, isim üstte)
    physician = (getattr(training, "workplace_physician", None) or "").strip()
    employer = (getattr(training, "employer_representative", None) or "").strip()
    instructor = (training.instructor_name or "").strip()
    instructor_title = (training.instructor_qualification or "").strip() or "İSG Uzmanı"
    cert_signers = (
        ("Eğitim Veren", instructor, instructor_title),
        ("Eğitim Veren", physician, "İşyeri Hekimi"),
        ("Onaylayan", employer, "İşveren Vekili"),
    )
    box_w = (uw - 16 * mm) / 3
    gap = (uw - 3 * box_w) / 2
    bh = 28 * mm
    iy = y - 3 * mm - bh
    for i, (role, person, unvan) in enumerate(cert_signers):
        x = ml + i * (box_w + gap)
        c.setFillColorRGB(248 / 255, 250 / 255, 255 / 255)
        c.setStrokeColorRGB(210 / 255, 220 / 255, 240 / 255)
        c.rect(x, iy, box_w, bh, fill=1, stroke=1)
        _rgb(c, _BLUE, fill=True)
        c.rect(x, iy + bh - 0.8 * mm, box_w, 0.8 * mm, fill=1, stroke=0)
        c.setFont(_FONT_B, 7)
        _rgb(c, _BLUE, fill=True)
        c.drawCentredString(x + box_w / 2, iy + bh - 6 * mm, role)
        c.setFillColorRGB(0.1, 0.1, 0.1)
        name_size = 8 if len(person or "") < 22 else 7
        c.setFont(_FONT_B, name_size)
        c.drawCentredString(x + box_w / 2, iy + bh - 13 * mm, _fit(c, person or " ", box_w - 4 * mm, _FONT_B, name_size))
        c.setStrokeColorRGB(0.4, 0.4, 0.4)
        c.line(x + 5 * mm, iy + 10 * mm, x + box_w - 5 * mm, iy + 10 * mm)
        c.setFillColorRGB(0.45, 0.45, 0.45)
        c.setFont(_FONT, 6)
        c.drawCentredString(x + box_w / 2, iy + 4 * mm, unvan)

    # Topics header
    ty = iy - 4 * mm
    _rgb(c, _BLUE, stroke=True)
    c.setLineWidth(1)
    c.line(ml, ty, w - mr, ty)
    c.setFillColorRGB(245 / 255, 247 / 255, 255 / 255)
    c.rect(ml, ty - 6.5 * mm, uw, 6.5 * mm, fill=1, stroke=0)
    _rgb(c, _BLUE, fill=True)
    c.setFont(_FONT_B, 8)
    c.drawCentredString(w / 2, ty - 4.5 * mm, "İŞ SAĞLIĞI VE GÜVENLİĞİ EĞİTİM KONULARI")

    top = ty - 9 * mm
    cw = (uw - 10 * mm) / 2
    bottom_limit = 14 * mm

    def draw_col(items, x, start_y, lh):
        yy = start_y
        for is_h, text in items:
            if yy < bottom_limit:
                break
            if is_h:
                c.setFillColorRGB(0, 0, 0)
                font, size = _FONT_B, 8
            else:
                c.setFillColorRGB(80 / 255, 80 / 255, 80 / 255)
                font, size = _FONT, 7.2
            c.setFont(font, size)
            c.drawString(x, yy, _fit(c, text, cw - 2 * mm, font, size))
            yy -= lh
        return yy

    draw_col(sol, ml + 2 * mm, top, 4.0 * mm)
    draw_col(sag, ml + 2 * mm + cw + 6 * mm, top, 4.3 * mm)

    # Footer — PRO: orta kanun + sağ stamp (uzman satırı)
    c.setStrokeColorRGB(200 / 255, 215 / 255, 240 / 255)
    c.setLineWidth(0.5)
    c.line(ml + 20 * mm, 10 * mm, w - mr - 20 * mm, 10 * mm)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.setFont(_FONT, 5.8)
    c.drawCentredString(w / 2, 7 * mm, _fit(c, _CERT_FOOTER, uw - 30 * mm, _FONT, 5.8))
    stamp_right = (getattr(training, "stamp_text", None) or "").strip()
    if not stamp_right:
        if instructor and instructor_title:
            stamp_right = f"{instructor} - {instructor_title}"
        else:
            stamp_right = _stamp_text(training)
    c.setFont(_FONT, 5.2)
    c.setFillColorRGB(65 / 255, 65 / 255, 65 / 255)
    c.drawRightString(w - mr, 4.5 * mm, _fit(c, stamp_right, uw * 0.55, _FONT, 5.2))
