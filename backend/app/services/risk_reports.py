"""Risk değerlendirme PDF / Excel raporları — İSG PRO reports.py Suite uyarlaması."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path

import openpyxl
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.services.risk_validity import METHOD_LABEL, document_meta_rows

PDF_FONT = "Helvetica"
PDF_FONT_BOLD = "Helvetica-Bold"
_ASSETS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
CREATOR_LINE = "İSG Suite OSGB"
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}


def _upload_root() -> Path:
    try:
        from app.core.config import settings

        root = Path(settings.upload_dir).resolve()
    except Exception:
        root = Path("uploads").resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _risk_excel_photo_path(risk) -> str | None:
    """Risk kaydına bağlı ilk uygun fotoğraf dosyasını döndürür (PRO parity)."""
    try:
        media_items = list(getattr(risk, "media_files", None) or [])
    except Exception:
        media_items = []
    root = _upload_root()
    for media in media_items:
        name = getattr(media, "original_name", "") or ""
        rel = getattr(media, "storage_path", "") or ""
        ctype = (getattr(media, "content_type", "") or "").lower()
        ext = Path(name or rel).suffix.lower()
        if not (ctype.startswith("image/") or ext in _IMAGE_EXTS):
            continue
        candidate = (root / rel).resolve()
        if root in candidate.parents and candidate.exists():
            return str(candidate)
    return None


def _register_pdf_fonts() -> None:
    global PDF_FONT, PDF_FONT_BOLD
    candidates = [
        (_ASSETS / "DejaVuSans.ttf", _ASSETS / "DejaVuSans-Bold.ttf", "RiskDejaVu", "RiskDejaVu-Bold"),
        (Path(r"C:\Windows\Fonts\arial.ttf"), Path(r"C:\Windows\Fonts\arialbd.ttf"), "RiskArial", "RiskArial-Bold"),
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            "RiskDejaVu",
            "RiskDejaVu-Bold",
        ),
    ]
    for regular, bold, name, bold_name in candidates:
        if not regular.exists():
            continue
        try:
            pdfmetrics.registerFont(TTFont(name, str(regular)))
            PDF_FONT = name
            if bold.exists():
                pdfmetrics.registerFont(TTFont(bold_name, str(bold)))
                PDF_FONT_BOLD = bold_name
            else:
                PDF_FONT_BOLD = name
            try:
                registerFontFamily(name, normal=name, bold=PDF_FONT_BOLD, italic=name, boldItalic=PDF_FONT_BOLD)
            except Exception:
                pass
            return
        except Exception:
            continue


_register_pdf_fonts()


def _fmt_date(d) -> str:
    if not d:
        return "—"
    if hasattr(d, "strftime"):
        return d.strftime("%d.%m.%Y")
    s = str(d)
    if len(s) >= 10 and s[4] == "-":
        y, m, day = s[:10].split("-")
        return f"{day}.{m}.{y}"
    return s


def _dept(risk) -> str:
    return getattr(risk, "department_name", None) or "—"


def _hazard_name(risk, hazard_map: dict) -> str:
    h = hazard_map.get(getattr(risk, "hazard_id", None))
    return h.name if h else "—"


def _hazard_code(risk, hazard_map: dict) -> str:
    h = hazard_map.get(getattr(risk, "hazard_id", None))
    return h.code if h else "—"


def _level_color(level: str):
    if "Kabul" in (level or ""):
        return colors.HexColor("#95a5a6")
    if "Düşük" in (level or ""):
        return colors.HexColor("#2ecc71")
    if "Orta" in (level or ""):
        return colors.HexColor("#f1c40f")
    if "Çok" in (level or ""):
        return colors.HexColor("#e74c3c")
    if "Yüksek" in (level or ""):
        return colors.HexColor("#f39c12")
    return colors.white


def _add_pdf_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(PDF_FONT, 7)
    canvas.setFillColor(colors.HexColor("#6c757d"))
    canvas.drawString(doc.leftMargin, 10 * mm, f"Program tasarımı ve raporlama: {CREATOR_LINE}")
    canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 10 * mm, f"Sayfa {doc.page}")
    canvas.restoreState()


def build_risk_pdf(
    *,
    company,
    risks,
    hazard_map: dict | None = None,
    prepared_by: str | None = None,
    sgk_no: str | None = None,
    workplace_physician: str | None = None,
    employer_representative: str | None = None,
    employee_representative: str | None = None,
    support_staff: str | None = None,
    validity: dict | None = None,
    team_details: dict | None = None,
    employee_count: int | None = None,
    document_no: str | None = None,
    revision_no: str | None = None,
    revision_reason: str | None = None,
    scope_note: str | None = None,
    tax_number: str | None = None,
    nace_code: str | None = None,
) -> bytes:
    """Firma risk değerlendirme PDF raporu — kapak, yöntem, ekip, kayıt, imza."""
    from app.services.risk_methods import (
        CONTROL_HIERARCHY,
        DEFINITIONS,
        LEGAL_BASIS,
        PURPOSE,
        SCOPE,
        resolve_method,
    )

    hazard_map = hazard_map or {}
    team_details = team_details or {}
    method = resolve_method((validity or {}).get("method_code") or getattr(company, "risk_method", None))
    doc_no = document_no or getattr(company, "risk_document_no", None) or f"RD-{getattr(company, 'id', 0)}"
    rev_no = revision_no or getattr(company, "risk_revision_no", None) or "00"
    rev_reason = revision_reason or getattr(company, "risk_revision_reason", None)
    scope_extra = scope_note or getattr(company, "risk_scope_note", None)
    prepared_on = datetime.now().strftime("%d.%m.%Y")

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=16 * mm,
        bottomMargin=14 * mm,
    )
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = PDF_FONT
    styles["Title"].fontName = PDF_FONT_BOLD

    title_style = ParagraphStyle(
        "RiskTitle",
        parent=styles["Title"],
        fontSize=16,
        fontName=PDF_FONT_BOLD,
        spaceAfter=4,
        textColor=colors.HexColor("#1a5276"),
        alignment=TA_CENTER,
    )
    subtitle = ParagraphStyle(
        "RiskSub",
        parent=styles["Normal"],
        fontSize=9,
        fontName=PDF_FONT,
        spaceAfter=2,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#2c3e50"),
    )
    info = ParagraphStyle("RiskInfo", parent=styles["Normal"], fontSize=9, fontName=PDF_FONT, spaceAfter=2, leading=12)
    section = ParagraphStyle(
        "RiskSection",
        parent=styles["Normal"],
        fontSize=11,
        fontName=PDF_FONT_BOLD,
        spaceBefore=4,
        spaceAfter=6,
        textColor=colors.HexColor("#1a5276"),
    )
    body = ParagraphStyle("RiskBody", parent=styles["Normal"], fontSize=8.5, fontName=PDF_FONT, leading=11, spaceAfter=3)
    cell = ParagraphStyle("RiskCell", parent=styles["Normal"], fontSize=8, fontName=PDF_FONT, leading=10)

    def _person_line(role_key: str, fallback_name: str | None, fallback_title: str) -> str:
        detail = team_details.get(role_key) or {}
        name = detail.get("full_name") or fallback_name or "—"
        title = detail.get("title") or fallback_title
        cert = detail.get("certificate_number") or detail.get("certificate_class")
        if cert:
            return f"{name} — {title} (Sertifika: {cert})"
        return f"{name} — {title}"

    elements: list = [
        Paragraph("RİSK DEĞERLENDİRME RAPORU", title_style),
        Paragraph(str(getattr(company, "name", "") or ""), subtitle),
        Paragraph("6331 sayılı İş Sağlığı ve Güvenliği Kanunu ve Risk Değerlendirmesi Yönetmeliği kapsamında", subtitle),
        Paragraph(
            f"Belge No: {doc_no}  |  Revizyon: {rev_no}  |  Düzenleme: {prepared_on}  |  Program: {CREATOR_LINE}",
            subtitle,
        ),
        Spacer(1, 5 * mm),
        Paragraph("1. İŞYERİ KÜNYESİ", section),
        Paragraph(f"<b>İşyeri Ünvanı:</b> {getattr(company, 'name', None) or '—'}", info),
        Paragraph(
            f"<b>SGK Sicil No:</b> {sgk_no or getattr(company, 'sgk_registry_no', None) or '—'}  |  "
            f"<b>Vergi No:</b> {tax_number or getattr(company, 'tax_number', None) or '—'}  |  "
            f"<b>NACE:</b> {nace_code or getattr(company, 'nace_code', None) or '—'}",
            info,
        ),
        Paragraph(f"<b>Adres:</b> {getattr(company, 'address', None) or '—'}", info),
        Paragraph(
            f"<b>Telefon:</b> {getattr(company, 'phone', None) or '—'}  |  "
            f"<b>Tehlike Sınıfı:</b> {getattr(company, 'hazard_class', None) or '—'}  |  "
            f"<b>Çalışan Sayısı:</b> {employee_count if employee_count is not None else '—'}",
            info,
        ),
        Paragraph(
            f"<b>İşveren / Yetkili:</b> {employer_representative or getattr(company, 'authorized_person', None) or '—'}",
            info,
        ),
        Spacer(1, 3 * mm),
        Paragraph("2. BELGE KONTROLÜ VE GEÇERLİLİK", section),
    ]

    for label, value in document_meta_rows(
        validity=validity,
        prepared_by=prepared_by,
        workplace_physician=workplace_physician,
        employer_representative=employer_representative,
        employee_representative=employee_representative,
        support_staff=support_staff,
        document_no=doc_no,
        revision_no=rev_no,
        revision_reason=rev_reason,
    ):
        elements.append(Paragraph(f"<b>{label}:</b> {value}", info))
    if validity and validity.get("message"):
        elements.append(Paragraph(f"<i>{validity['message']}</i>", body))
    triggers = (validity or {}).get("renewal_triggers") or []
    if triggers:
        elements.append(Paragraph("<b>Süre beklenmeden yenileme tetikleyicileri (md.12/2):</b>", info))
        for t in triggers:
            elements.append(Paragraph(f"• {t}", body))

    elements.extend(
        [
            Spacer(1, 3 * mm),
            Paragraph("3. AMAÇ, KAPSAM VE MEVZUAT DAYANAĞI", section),
            Paragraph(f"<b>Amaç:</b> {PURPOSE}", body),
            Paragraph(f"<b>Kapsam:</b> {scope_extra or SCOPE}", body),
            Paragraph("<b>Yasal dayanak:</b>", info),
        ]
    )
    for law in LEGAL_BASIS:
        elements.append(Paragraph(f"• {law}", body))

    elements.extend(
        [
            Spacer(1, 3 * mm),
            Paragraph("4. TANIMLAR VE KISALTMALAR", section),
        ]
    )
    for term, meaning in DEFINITIONS:
        elements.append(Paragraph(f"<b>{term}:</b> {meaning}", body))

    elements.extend(
        [
            Spacer(1, 3 * mm),
            Paragraph("5. YÖNTEM VE SKORLAMA KRİTERLERİ", section),
            Paragraph(f"<b>Seçilen yöntem:</b> {method['label']}", info),
            Paragraph(f"<b>Formül:</b> {method['formula']}", info),
            Paragraph(method["narrative"], body),
            Paragraph("<b>Olasılık / maruziyet tanımları:</b>", info),
        ]
    )
    for val, txt in method.get("probability_defs") or []:
        elements.append(Paragraph(f"• {val}: {txt}", body))
    if not method.get("probability_defs"):
        elements.append(Paragraph("• Nitel değerlendirme (yönteme özgü skorlama ekip tutanağında).", body))
    elements.append(Paragraph("<b>Şiddet tanımları:</b>", info))
    for val, txt in method.get("severity_defs") or []:
        elements.append(Paragraph(f"• {val}: {txt}", body))
    if not method.get("severity_defs"):
        elements.append(Paragraph("• Nitel değerlendirme (yönteme özgü).", body))
    elements.append(Paragraph("<b>Risk seviyesi / öncelik:</b>", info))
    for rng, level, note in method.get("levels") or []:
        elements.append(Paragraph(f"• {rng} → <b>{level}</b>: {note}", body))

    elements.extend(
        [
            Spacer(1, 3 * mm),
            Paragraph("6. ÖNLEM HİYERARŞİSİ VE DÜZELTİCİ FAALİYET İLKELERİ", section),
        ]
    )
    for line in CONTROL_HIERARCHY:
        elements.append(Paragraph(f"• {line}", body))
    elements.append(
        Paragraph(
            "İlave önlemler sonrası artık risk yeniden değerlendirilir; DÖF ile sorumlu, termin ve durum izlenir. "
            "Onaylı/imzalı raporlar tarihsel belge olarak korunur; işyeri kartındaki sonraki değişiklikler "
            "geçmiş raporları otomatik değiştirmez.",
            body,
        )
    )

    elements.append(PageBreak())
    elements.append(Paragraph("7. RİSK DEĞERLENDİRME EKİBİ (md.15)", section))
    elements.append(
        Paragraph(
            "Aşağıdaki kişiler yönetmelik gereği değerlendirmeye katılır / onaylar. "
            "Görevlendirme kayıtlarından gelen unvan ve sertifika bilgileri otomatik doldurulur.",
            body,
        )
    )
    team_rows = [
        ["Rol / Görev", "Ad Soyad / Unvan / Sertifika", "Sorumluluk", "İmza"],
        [
            "İşveren / Vekil",
            Paragraph(_person_line("employer", employer_representative, "İşveren / Vekil"), cell),
            "Onay / yetkilendirme",
            "",
        ],
        [
            "İSG Uzmanı",
            Paragraph(
                _person_line("safety_specialist", prepared_by, "İş Güvenliği Uzmanı"),
                cell,
            ),
            "Hazırlama / koordinasyon",
            "",
        ],
        [
            "İşyeri Hekimi",
            Paragraph(
                _person_line("workplace_physician", workplace_physician, "İşyeri Hekimi"),
                cell,
            ),
            "Sağlık boyutu / inceleme",
            "",
        ],
        [
            "Çalışan Temsilcisi",
            Paragraph(employee_representative or "—", cell),
            "Katılım / görüş",
            "",
        ],
        [
            "Destek Elemanı",
            Paragraph(support_staff or "—", cell),
            "Destek / uygulama",
            "",
        ],
        [
            "Diğer Sağlık Personeli",
            Paragraph(_person_line("other_health_personnel", None, "DSP"), cell),
            "Gerektiğinde katılım",
            "",
        ],
    ]
    team_table = Table(team_rows, colWidths=[85, 200, 100, 70])
    team_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), PDF_FONT),
                ("FONTNAME", (0, 0), (-1, 0), PDF_FONT_BOLD),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a5276")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 1), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 10),
            ]
        )
    )
    elements.append(team_table)

    # Summary
    total = len(risks)
    risk_levels: dict[str, int] = {}
    for r in risks:
        rl = r.risk_level or "Tanımsız"
        risk_levels[rl] = risk_levels.get(rl, 0) + 1

    elements.append(Spacer(1, 5 * mm))
    elements.append(Paragraph("8. RİSK ÖZETİ", section))
    summary_data = [["Risk Seviyesi", "Adet", "Yüzde"]]
    for level in ["Çok Yüksek", "Yüksek", "Orta", "Düşük", "Kabul Edilebilir"]:
        count = risk_levels.get(level, 0)
        pct = f"{(count / total * 100):.1f}%" if total else "%0"
        summary_data.append([level, str(count), pct])
    summary_table = Table(summary_data, colWidths=[120, 50, 50])
    summary_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), PDF_FONT),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a5276")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (2, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 1), (0, 1), colors.HexColor("#e74c3c")),
                ("BACKGROUND", (0, 2), (0, 2), colors.HexColor("#f39c12")),
                ("BACKGROUND", (0, 3), (0, 3), colors.HexColor("#f1c40f")),
                ("BACKGROUND", (0, 4), (0, 4), colors.HexColor("#2ecc71")),
                ("BACKGROUND", (0, 5), (0, 5), colors.HexColor("#95a5a6")),
            ]
        )
    )
    elements.append(summary_table)

    elements.append(PageBreak())
    elements.append(Paragraph("9. RİSK KAYIT LİSTESİ", section))
    elements.append(
        Paragraph(
            f"Yöntem eksenleri: {method.get('probability_axis')} / {method.get('severity_axis')}. "
            "Skorlar mevcut kayıt motoruna göredir; Fine-Kinney vb. seçildiğinde skorlama kriterleri "
            "bölüm 5’te yer alır, saha kayıtları 5×5 ile tutuluyorsa dönüşüm notu ekibe aittir.",
            body,
        )
    )
    elements.append(Spacer(1, 2 * mm))

    for risk in risks:
        regs = []
        h = hazard_map.get(getattr(risk, "hazard_id", None))
        if h and getattr(h, "regulations", None):
            try:
                import json

                raw = h.regulations
                regs = json.loads(raw) if isinstance(raw, str) else (raw or [])
            except Exception:
                regs = []
        risk_data = [
            ["Risk Kodu", risk.risk_code],
            ["Bölüm", _dept(risk)],
            ["Faaliyet", Paragraph(str(risk.activity or "—"), cell)],
            ["Tehlike", f"{_hazard_code(risk, hazard_map)} — {_hazard_name(risk, hazard_map)}"],
            ["Risk Tanımı", Paragraph(str(risk.risk_definition or "—"), cell)],
            ["Etkilenenler", risk.affected_people or getattr(risk, "affected_group", None) or "—"],
            [method.get("probability_axis") or "Olasılık", str(risk.probability)],
            [method.get("severity_axis") or "Şiddet", str(risk.severity)],
            ["Risk Skoru", str(risk.risk_score)],
            ["Risk Seviyesi", risk.risk_level or "—"],
            ["Termin Tarihi", _fmt_date(risk.term_date)],
            ["Durum", risk.status or "Açık"],
            ["DÖF sayısı", str(len(getattr(risk, "dofs", None) or []))],
            ["Revizyon (kayıt)", str(getattr(risk, "revision_no", None) or "—")],
            ["Mevzuat ref.", Paragraph(", ".join(regs) if regs else "—", cell)],
        ]
        risk_table = Table(risk_data, colWidths=[100, 370])
        bg = _level_color(risk.risk_level or "")
        risk_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), PDF_FONT),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#ecf0f1")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("FONTNAME", (0, 0), (0, -1), PDF_FONT_BOLD),
                    ("BACKGROUND", (1, 8), (1, 9), bg),
                ]
            )
        )
        elements.append(risk_table)
        elements.append(Spacer(1, 2 * mm))

        measures = [
            ["Mevcut Önlemler", Paragraph(str(risk.existing_measures or "—"), cell)],
            ["İlave Önlemler", Paragraph(str(risk.additional_measures or "—"), cell)],
            [
                "Artık risk",
                Paragraph(
                    "İlave önlem / DÖF tamamlandıktan sonra yeniden değerlendirilir "
                    "(önlem sonrası skor sahada güncellenir).",
                    cell,
                ),
            ],
        ]
        measures_table = Table(measures, colWidths=[100, 370])
        measures_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), PDF_FONT),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        elements.append(measures_table)

        dofs = list(getattr(risk, "dofs", None) or [])
        if dofs:
            elements.append(Spacer(1, 2 * mm))
            dof_rows = [["DÖF No", "Yapılacak İş", "Sorumlu", "Termin", "Durum"]]
            for d in dofs:
                dof_rows.append(
                    [
                        d.dof_code,
                        Paragraph(str(d.description or "—")[:200], cell),
                        d.responsible_person or "—",
                        _fmt_date(d.term_date),
                        d.status or "Açık",
                    ]
                )
            dof_table = Table(dof_rows, colWidths=[55, 200, 80, 60, 55])
            dof_table.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (-1, -1), PDF_FONT),
                        ("FONTSIZE", (0, 0), (-1, -1), 7),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#34495e")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                )
            )
            elements.append(dof_table)

        elements.append(Spacer(1, 6 * mm))

    elements.append(PageBreak())
    elements.append(Paragraph("10. İMZA / ONAY", section))
    elements.append(
        Paragraph(
            "Bu belgeyi hazırlayan, inceleyen, katılan ve onaylayan kişiler aşağıda imza altına alır. "
            "İşveren onayı olmadan risk değerlendirmesi resmi sayılmaz.",
            body,
        )
    )
    elements.append(Spacer(1, 3 * mm))
    sign_data = [
        ["İSG Uzmanı / Hazırlayan", prepared_by or " ", "Kaşe / İmza / Tarih"],
        ["İşyeri Hekimi", workplace_physician or " ", "Kaşe / İmza / Tarih"],
        ["İşveren / Vekili", employer_representative or " ", "Kaşe / İmza / Tarih"],
        ["Çalışan Temsilcisi", employee_representative or " ", "İmza / Tarih"],
    ]
    if support_staff:
        sign_data.append(["Destek Elemanı", support_staff, "İmza / Tarih"])
    dsp = (team_details.get("other_health_personnel") or {}).get("full_name")
    if dsp:
        sign_data.append(["Diğer Sağlık Personeli", dsp, "İmza / Tarih"])
    sign_table = Table([["Unvan", "Ad Soyad", "Onay"]] + sign_data, colWidths=[160, 180, 130])
    sign_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), PDF_FONT),
                ("FONTNAME", (0, 0), (-1, 0), PDF_FONT_BOLD),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a5276")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 1), (-1, -1), 14),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 14),
            ]
        )
    )
    elements.append(sign_table)

    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph("11. DAĞITIM, SAKLAMA VE ARŞİV", section))
    elements.append(
        Paragraph(
            "Dağıtım: İşveren / vekil, İSG uzmanı, işyeri hekimi, çalışan temsilcisi, ilgili birim sorumluları. "
            "Saklama: İşyerinde erişilebilir; denetim ve müfettiş talebinde sunulur. "
            "Arşiv: Onaylı PDF/Excel kopyaları tarihsel belge olarak saklanır; sonraki işyeri kartı "
            "değişiklikleri onaylı sürümü otomatik değiştirmez.",
            body,
        )
    )
    elements.append(
        Paragraph(
            f"Belge kontrol: {doc_no} / Rev {rev_no} / {prepared_on} / {CREATOR_LINE}",
            body,
        )
    )

    doc.build(elements, onFirstPage=_add_pdf_footer, onLaterPages=_add_pdf_footer)
    buf.seek(0)
    return buf.read()


def build_risk_excel(
    *, company, risks, hazard_map: dict | None = None, validity: dict | None = None
) -> bytes:
    """Excel: Risk tablosu + DÖF listesi + istatistikler."""
    hazard_map = hazard_map or {}
    wb = openpyxl.Workbook()
    wb.properties.creator = CREATOR_LINE
    wb.properties.title = "İSG Risk Değerlendirme Raporu"

    header_font = Font(name="Calibri", bold=True, size=11, color="FFFFFF")
    header_fill = PatternFill(start_color="1a5276", end_color="1a5276", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )
    level_fills = {
        "Kabul Edilebilir": PatternFill(start_color="95a5a6", end_color="95a5a6", fill_type="solid"),
        "Düşük": PatternFill(start_color="2ecc71", end_color="2ecc71", fill_type="solid"),
        "Orta": PatternFill(start_color="f1c40f", end_color="f1c40f", fill_type="solid"),
        "Yüksek": PatternFill(start_color="f39c12", end_color="f39c12", fill_type="solid"),
        "Çok Yüksek": PatternFill(start_color="e74c3c", end_color="e74c3c", fill_type="solid"),
    }

    ws = wb.active
    ws.title = "Risk Değerlendirme"
    ws.merge_cells("A1:Q1")
    ws["A1"] = f"RİSK DEĞERLENDİRME RAPORU - {company.name}"
    ws["A1"].font = Font(name="Calibri", bold=True, size=14, color="1a5276")
    ws["A1"].alignment = Alignment(horizontal="center")

    doc_no = getattr(company, "risk_document_no", None) or f"RD-{getattr(company, 'id', '')}"
    rev_no = getattr(company, "risk_revision_no", None) or "00"
    ws.merge_cells("A2:Q2")
    ws["A2"] = (
        f"Yetkili: {getattr(company, 'authorized_person', None) or '—'} | "
        f"Tel: {getattr(company, 'phone', None) or '—'} | "
        f"Tehlike Sınıfı: {getattr(company, 'hazard_class', None) or '—'} | "
        f"SGK: {getattr(company, 'sgk_registry_no', None) or '—'} | "
        f"NACE: {getattr(company, 'nace_code', None) or '—'} | "
        f"Belge: {doc_no} / Rev {rev_no} | "
        f"Tarih: {datetime.now().strftime('%d.%m.%Y')}"
    )
    ws["A2"].font = Font(size=9, color="2c3e50")
    ws["A2"].alignment = Alignment(horizontal="center")

    ws.merge_cells("A3:Q3")
    method = (validity or {}).get("method") or METHOD_LABEL
    valid_line = ""
    if validity and validity.get("valid_until"):
        valid_line = f" · Geçerlilik: {_fmt_date(validity['valid_until'])}"
    assess_line = ""
    if validity and validity.get("assessment_date"):
        assess_line = f" · Değerlendirme: {_fmt_date(validity['assessment_date'])}"
    ws["A3"] = (
        f"Yöntem: {method}{assess_line}{valid_line} · "
        f"Program: {CREATOR_LINE} · 6331 sayılı Kanun / Risk Değerlendirmesi Yönetmeliği"
    )
    ws["A3"].font = Font(size=9, italic=True, color="6c757d")
    ws["A3"].alignment = Alignment(horizontal="center")

    headers = [
        "Risk Kodu",
        "Bölüm",
        "Faaliyet",
        "Tehlike",
        "Tehlike Kodu",
        "Risk Tanımı",
        "Etkilenenler",
        "Olasılık (1-5)",
        "Şiddet (1-5)",
        "Risk Skoru",
        "Risk Seviyesi",
        "Termin Tarihi",
        "Mevcut Önlemler",
        "İlave Önlemler",
        "Durum",
        "DÖF Sayısı",
        "Fotoğraf",
    ]
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin

    for idx, risk in enumerate(risks, 5):
        dofs = list(getattr(risk, "dofs", None) or [])
        data = [
            risk.risk_code,
            _dept(risk),
            risk.activity,
            _hazard_name(risk, hazard_map),
            _hazard_code(risk, hazard_map),
            risk.risk_definition,
            risk.affected_people or "—",
            risk.probability,
            risk.severity,
            risk.risk_score,
            risk.risk_level or "—",
            _fmt_date(risk.term_date),
            risk.existing_measures or "—",
            risk.additional_measures or "—",
            risk.status or "Açık",
            len(dofs),
            "",
        ]
        for col, value in enumerate(data, 1):
            cell = ws.cell(row=idx, column=col, value=value)
            cell.border = thin
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            cell.font = Font(size=9)
        level = risk.risk_level or ""
        if level in level_fills:
            ws.cell(row=idx, column=10).fill = level_fills[level]
            ws.cell(row=idx, column=11).fill = level_fills[level]

        photo_path = _risk_excel_photo_path(risk)
        if photo_path:
            try:
                img = XLImage(photo_path)
                max_w, max_h = 140, 95
                if img.width and img.height:
                    ratio = min(max_w / img.width, max_h / img.height, 1)
                    img.width = int(img.width * ratio)
                    img.height = int(img.height * ratio)
                img.anchor = f"Q{idx}"
                ws.add_image(img)
                ws.row_dimensions[idx].height = max(ws.row_dimensions[idx].height or 15, 72)
            except Exception:
                ws.cell(row=idx, column=17, value="Fotoğraf var / eklenemedi")

    for i, w in enumerate([12, 15, 20, 18, 12, 28, 16, 10, 10, 10, 14, 12, 28, 28, 10, 10, 18], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A5"
    ws.auto_filter.ref = f"A4:Q{max(4, 4 + len(risks))}"

    # DÖF sheet
    ws2 = wb.create_sheet("DÖF Listesi")
    dof_headers = [
        "DÖF No",
        "Risk Kodu",
        "Faaliyet",
        "Tehlike",
        "Yapılacak İş",
        "Sorumlu",
        "Sorumlu Bölüm",
        "Termin",
        "Maliyet",
        "Durum",
        "Tamamlanma Notu",
    ]
    for col, header in enumerate(dof_headers, 1):
        cell = ws2.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin

    row = 2
    for risk in risks:
        for dof in getattr(risk, "dofs", None) or []:
            data = [
                dof.dof_code,
                risk.risk_code,
                risk.activity,
                _hazard_name(risk, hazard_map),
                dof.description,
                dof.responsible_person or "—",
                dof.responsible_department or "—",
                _fmt_date(dof.term_date),
                dof.cost_estimate if dof.cost_estimate is not None else "—",
                dof.status or "Açık",
                dof.completion_note or "—",
            ]
            for col, value in enumerate(data, 1):
                cell = ws2.cell(row=row, column=col, value=value)
                cell.border = thin
                cell.font = Font(size=9)
                cell.alignment = Alignment(wrap_text=True)
            row += 1
    for i, w in enumerate([12, 12, 18, 16, 32, 16, 16, 12, 10, 12, 24], 1):
        ws2.column_dimensions[get_column_letter(i)].width = w

    # Stats
    ws3 = wb.create_sheet("İstatistikler")
    ws3.merge_cells("A1:C1")
    ws3["A1"] = "RİSK İSTATİSTİKLERİ"
    ws3["A1"].font = Font(bold=True, size=14, color="1a5276")
    ws3["A3"] = "Risk Seviyesi"
    ws3["B3"] = "Adet"
    ws3["C3"] = "Yüzde"
    for col in ["A3", "B3", "C3"]:
        ws3[col].font = header_font
        ws3[col].fill = header_fill
        ws3[col].border = thin

    risk_levels: dict[str, int] = {}
    for r in risks:
        rl = r.risk_level or "Tanımsız"
        risk_levels[rl] = risk_levels.get(rl, 0) + 1
    total = len(risks)
    for i, level in enumerate(["Çok Yüksek", "Yüksek", "Orta", "Düşük", "Kabul Edilebilir"], 4):
        count = risk_levels.get(level, 0)
        ws3.cell(row=i, column=1, value=level).border = thin
        ws3.cell(row=i, column=2, value=count).border = thin
        ws3.cell(row=i, column=3, value=f"{(count / total * 100):.1f}%" if total else "%0").border = thin

    open_dofs = sum(1 for r in risks for d in (getattr(r, "dofs", None) or []) if not d.is_completed)
    done_dofs = sum(1 for r in risks for d in (getattr(r, "dofs", None) or []) if d.is_completed)
    ws3["A10"] = "Açık DÖF"
    ws3["B10"] = open_dofs
    ws3["A11"] = "Tamamlanan DÖF"
    ws3["B11"] = done_dofs
    ws3.column_dimensions["A"].width = 20
    ws3.column_dimensions["B"].width = 10

    for sheet in wb.worksheets:
        sheet.oddFooter.center.text = CREATOR_LINE
        sheet.oddFooter.right.text = "Sayfa &P / &N"

    out = BytesIO()
    wb.save(out)
    out.seek(0)
    return out.read()


def build_dof_excel(*, company, risks: list, hazard_map: dict | None = None) -> bytes:
    """PRO /rapor/dof-excel — yalnız DÖF listesi."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    hazard_map = hazard_map or {}
    wb = Workbook()
    ws = wb.active
    ws.title = "DÖF Listesi"
    header_font = Font(bold=True, size=11, color="FFFFFF")
    header_fill = PatternFill(start_color="1A5276", end_color="1A5276", fill_type="solid")
    thin = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )
    wb.properties.creator = CREATOR_LINE
    wb.properties.title = "DÖF Listesi"

    ws.merge_cells("A1:I1")
    ws["A1"] = f"DÜZELTİCİ-ÖNLEYİCİ FAALİYET LİSTESİ - {getattr(company, 'name', '')}"
    ws["A1"].font = Font(bold=True, size=14, color="1A5276")
    ws.merge_cells("A2:I2")
    ws["A2"] = CREATOR_LINE
    ws["A2"].font = Font(size=9, italic=True, color="6C757D")
    ws["A2"].alignment = Alignment(horizontal="center")

    headers = [
        "DÖF No",
        "Risk Kodu",
        "Bölüm",
        "Tehlike",
        "Yapılacak İş",
        "Sorumlu",
        "Termin Tarihi",
        "Durum",
        "Tamamlanma Tarihi",
    ]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = thin
        cell.alignment = Alignment(horizontal="center", wrap_text=True)

    row_i = 5
    for risk in risks:
        haz = hazard_map.get(getattr(risk, "hazard_id", None))
        haz_name = getattr(haz, "name", None) if haz else "—"
        for dof in getattr(risk, "dofs", None) or []:
            values = [
                dof.dof_code,
                getattr(risk, "risk_code", "") or "—",
                getattr(risk, "department_name", None) or "—",
                haz_name or "—",
                dof.description,
                dof.responsible_person or "—",
                _fmt_date(dof.term_date),
                dof.status or "Açık",
                _fmt_date(dof.completion_date),
            ]
            for col, val in enumerate(values, 1):
                cell = ws.cell(row=row_i, column=col, value=val)
                cell.border = thin
                cell.font = Font(size=9)
                cell.alignment = Alignment(wrap_text=True)
            row_i += 1

    for i, w in enumerate([12, 12, 15, 18, 30, 18, 12, 12, 15], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.oddFooter.center.text = CREATOR_LINE

    out = BytesIO()
    wb.save(out)
    out.seek(0)
    return out.read()
