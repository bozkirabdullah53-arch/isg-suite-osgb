"""Acil durum planı için okunabilir A4 çalışma çıktısı."""
from __future__ import annotations

from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.services.emergency_plan_compliance import SCENARIO_LABELS


_ASSETS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_FONT = "Helvetica"
_BOLD = "Helvetica-Bold"


def _register_fonts() -> None:
    global _FONT, _BOLD
    regular = _ASSETS / "DejaVuSans.ttf"
    bold = _ASSETS / "DejaVuSans-Bold.ttf"
    if not regular.exists():
        return
    try:
        pdfmetrics.registerFont(TTFont("EmergencyPlanSans", str(regular)))
        pdfmetrics.registerFont(TTFont("EmergencyPlanSans-Bold", str(bold if bold.exists() else regular)))
        _FONT = "EmergencyPlanSans"
        _BOLD = "EmergencyPlanSans-Bold"
    except Exception:
        # Aynı worker içinde ikinci kez kayıt yapılması güvenlidir; font zaten
        # varsa reportlab exception üretebilir.
        _FONT = "EmergencyPlanSans"
        _BOLD = "EmergencyPlanSans-Bold"


def _text(value: Any) -> str:
    return escape(str(value if value not in (None, "") else "-"))


def _date(value: Any) -> str:
    if not value:
        return "-"
    return value.strftime("%d.%m.%Y") if hasattr(value, "strftime") else str(value)


def _p(value: Any, style: ParagraphStyle) -> Paragraph:
    return Paragraph(_text(value).replace("\n", "<br/>"), style)


def _footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D8E2EC"))
    canvas.setLineWidth(0.4)
    canvas.line(14 * mm, 10 * mm, A4[0] - 14 * mm, 10 * mm)
    canvas.setFont(_FONT, 7)
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.drawString(14 * mm, 6 * mm, "İSG Suite · Acil durum planı çalışma çıktısı")
    canvas.drawRightString(A4[0] - 14 * mm, 6 * mm, f"Sayfa {doc.page}")
    canvas.restoreState()


def _status_label(status: str) -> str:
    return {"ok": "Tamam", "warn": "İncele", "error": "Eksik"}.get(status, "İncele")


def _approval_label(value: str | None) -> str:
    return {
        "not_confirmed": "Onay kaydı yok",
        "employer_signed": "İşveren imzası doğrulandı",
        "secure_esign": "Güvenli e-imza / EYAS doğrulandı",
    }.get(value or "not_confirmed", "Onay kaydı yok")


def build_emergency_plan_pdf(
    *,
    plan: Any,
    company: Any,
    details: dict[str, Any],
    floors: list[Any],
    readiness: dict[str, Any],
    teams: list[dict[str, Any]] | None = None,
    prepared_by: dict[str, Any] | None = None,
) -> bytes:
    """Metadata, uygulama adımları ve kontrol özetini tek PDF'te toplar."""
    _register_fonts()
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "EmergencyPlanTitle", parent=styles["Title"], fontName=_BOLD, fontSize=20,
        leading=24, alignment=TA_CENTER, textColor=colors.HexColor("#E6F7FF"), spaceAfter=4,
    )
    subtitle = ParagraphStyle(
        "EmergencyPlanSubtitle", parent=styles["Normal"], fontName=_FONT, fontSize=9.5,
        leading=13, alignment=TA_CENTER, textColor=colors.HexColor("#C7E9F5"),
    )
    section = ParagraphStyle(
        "EmergencyPlanSection", parent=styles["Heading2"], fontName=_BOLD, fontSize=11.5,
        leading=15, textColor=colors.HexColor("#0B5368"), spaceBefore=8, spaceAfter=5,
    )
    body = ParagraphStyle(
        "EmergencyPlanBody", parent=styles["BodyText"], fontName=_FONT, fontSize=8.7,
        leading=12.5, textColor=colors.HexColor("#243447"), wordWrap="CJK",
    )
    small = ParagraphStyle(
        "EmergencyPlanSmall", parent=body, fontSize=7.4, leading=10,
    )
    label = ParagraphStyle(
        "EmergencyPlanLabel", parent=body, fontName=_BOLD, fontSize=7.6,
        leading=10, textColor=colors.HexColor("#33566B"),
    )
    table_header = ParagraphStyle(
        "EmergencyPlanTableHeader", parent=body, fontName=_BOLD, fontSize=7.6,
        leading=9.5, textColor=colors.white,
    )
    callout = ParagraphStyle(
        "EmergencyPlanCallout", parent=body, fontSize=8.2, leading=11.5,
        textColor=colors.HexColor("#25404D"),
    )

    company_name = getattr(company, "name", None) or f"İşyeri #{getattr(plan, 'company_id', '-')}"
    company_address = getattr(company, "address", None) or "-"
    employer = getattr(company, "authorized_person", None) or "-"
    title_text = getattr(plan, "title", None) or "Acil Durum Planı"
    prepared_name = (prepared_by or {}).get("name") or "-"
    prepared_title = (prepared_by or {}).get("title") or "-"

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=13 * mm,
        bottomMargin=15 * mm,
        title=f"Acil Durum Planı - {company_name}",
        author="İSG Suite",
    )
    story: list[Any] = []
    header = Table(
        [[
            Paragraph("ACİL DURUM PLANI", title),
            Paragraph(f"{_text(company_name)}<br/>{_text(title_text)} · Rev. {_text(getattr(plan, 'revision_no', '00'))}", subtitle),
        ]],
        colWidths=[74 * mm, 96 * mm],
    )
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0A3445")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LINEBELOW", (0, 0), (-1, -1), 2, colors.HexColor("#32C5E6")),
    ]))
    story.extend([header, Spacer(1, 5 * mm)])

    pct = int(readiness.get("pct") or 0)
    status = readiness.get("label") or "İnceleme gerekli"
    readiness_box = Table([[
        Paragraph(f"<b>Hazırlık düzeyi: %{pct}</b> · {_text(status)}", callout),
        Paragraph(_text(readiness.get("summary") or "Kontrol özeti"), callout),
    ]], colWidths=[78 * mm, 92 * mm])
    readiness_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EAF8FB" if pct >= 70 else "#FFF6E8")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#9AD9E5" if pct >= 70 else "#F2C57C")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(readiness_box)

    story.append(Paragraph("1. Plan künyesi", section))
    meta_rows = [
        [_p("İşyeri", label), _p(company_name, body), _p("Adres", label), _p(company_address, body)],
        [_p("İşveren / vekil", label), _p(employer, body), _p("Plan / revizyon", label), _p(f"{title_text} · {getattr(plan, 'revision_no', '00')}", body)],
        [_p("Plan tarihi", label), _p(_date(getattr(plan, "plan_date", None)), body), _p("Gözden geçirme", label), _p(_date(getattr(plan, "next_review_date", None)), body)],
        [_p("Toplanma alanı", label), _p(getattr(plan, "assembly_areas", None), body), _p("Durum", label), _p(getattr(plan, "status", None), body)],
        [_p("Hazırlayan", label), _p(prepared_name, body), _p("Görevi", label), _p(prepared_title, body)],
    ]
    meta_table = Table(meta_rows, colWidths=[29 * mm, 56 * mm, 32 * mm, 53 * mm])
    meta_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F2F8FA")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#F2F8FA")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(meta_table)

    scenario_codes = details.get("emergency_types") or []
    scenario_text = ", ".join(SCENARIO_LABELS.get(code, str(code)) for code in scenario_codes) or "Belirtilmedi"
    story.append(Paragraph("2. Belirlenen acil durumlar", section))
    story.append(_p(scenario_text, body))
    story.append(Paragraph("3. Önleyici ve sınırlandırıcı tedbirler", section))
    story.append(_p(details.get("preventive_measures"), body))
    story.append(Paragraph("3a. Ölçüm, değerlendirme ve ekipman envanteri", section))
    inventory_rows = [
        [_p("Ölçüm / değerlendirme", label), _p(details.get("measurement_evaluation"), body)],
        [_p("Ekipman / KKD", label), _p(details.get("equipment_inventory"), body)],
    ]
    inventory_table = Table(inventory_rows, colWidths=[44 * mm, 126 * mm])
    inventory_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F8FAFC")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(inventory_table)
    story.append(Paragraph("4. Müdahale, haberleşme ve tahliye yöntemi", section))
    story.append(_p(details.get("response_methods"), body))

    story.append(Paragraph("5. Özel riskler ve kritik kesme noktaları", section))
    risk_rows = [
        [_p("Özel risk alanları", label), _p(details.get("special_risk_areas") or ("Uygulanamaz olarak işaretlendi" if details.get("special_risk_mode") == "not_applicable" else "Değerlendirme bekliyor"), body)],
        [_p("Enerji / vana noktaları", label), _p(details.get("energy_shutoff_points") or ("Uygulanamaz olarak işaretlendi" if details.get("energy_controls_mode") == "not_applicable" else "Değerlendirme bekliyor"), body)],
        [_p("Özel destek yöntemi", label), _p(details.get("special_groups"), body)],
        [_p("Onay / görünür yerde bulundurma", label), _p(
            f"{_approval_label(details.get('approval_status'))} · "
            f"{'Krokiler asıldı' if details.get('posted_confirmed') else 'Asılılık doğrulaması bekliyor'}",
            body,
        )],
        [_p("Son tamamlanmış tatbikat", label), _p(
            (readiness.get("drill_summary") or {}).get("last_date") or details.get("last_drill_date"),
            body,
        )],
        [_p("Ortak saha koordinasyonu", label), _p(
            details.get("shared_workplace_note") if details.get("shared_workplace") else "Ortak saha olarak işaretlenmedi",
            body,
        )],
    ]
    risk_table = Table(risk_rows, colWidths=[44 * mm, 126 * mm])
    risk_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F8FAFC")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(risk_table)

    story.append(Paragraph("6. Acil durum ekipleri / destek elemanları", section))
    team_rows = [[_p("Ekip", table_header), _p("Aktif üye", table_header), _p("Kayıt", table_header)]]
    for team in teams or []:
        team_rows.append([
            _p(team.get("name") or team.get("code"), body),
            _p(team.get("members") or 0, body),
            _p("Aktif", body),
        ])
    if len(team_rows) == 1:
        team_rows.append([_p("Ekip verisi bulunamadı", body), _p("-", body), _p("İnceleme gerekli", body)])
    team_table = Table(team_rows, colWidths=[95 * mm, 30 * mm, 45 * mm], repeatRows=1)
    team_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B5368")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(team_table)

    story.append(Paragraph("7. Krokiler ve uygulama", section))
    floor_rows = [[_p("Kat / saha", table_header), _p("Plan zemini", table_header), _p("İşaretleme özeti", table_header)]]
    map_data = readiness.get("map") or {}
    for floor in floors or []:
        floor_summary = next((item for item in map_data.get("floor_summaries", []) if item.get("id") == getattr(floor, "id", None)), {})
        objects = floor_summary.get("objects") or {}
        floor_rows.append([
            _p(getattr(floor, "name", None), body),
            _p("Arka plan" if getattr(floor, "background_storage_path", None) else "Vektör / boş", body),
            _p(f"Çıkış {objects.get('exit', 0) + objects.get('door_exit', 0)} · Kaçış {objects.get('route', 0)} · Toplanma {objects.get('assembly', 0)}", body),
        ])
    if len(floor_rows) == 1:
        floor_rows.append([_p("Kat krokisi bulunamadı", body), _p("-", body), _p("Kroki Studio'da oluşturulmalı", body)])
    floor_table = Table(floor_rows, colWidths=[45 * mm, 38 * mm, 87 * mm], repeatRows=1)
    floor_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B5368")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(floor_table)
    if getattr(plan, "kroki_file_name", None):
        story.append(Spacer(1, 2 * mm))
        story.append(_p(f"Duvar posteri / ek kroki dosyası: {plan.kroki_file_name}", small))

    story.append(Paragraph("8. Mevzuat odaklı hazırlık kontrolü", section))
    check_rows = [[_p("Kontrol", table_header), _p("Durum", table_header), _p("Açıklama", table_header), _p("Referans", table_header)]]
    for item in readiness.get("checks") or []:
        check_rows.append([
            _p(item.get("label"), body),
            _p(_status_label(item.get("status")), body),
            _p(item.get("detail"), small),
            _p(item.get("reference"), small),
        ])
    check_table = Table(check_rows, colWidths=[42 * mm, 20 * mm, 78 * mm, 30 * mm], repeatRows=1)
    check_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B5368")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for row_index, item in enumerate(readiness.get("checks") or [], start=1):
        if item.get("status") == "error":
            check_style.append(("TEXTCOLOR", (1, row_index), (1, row_index), colors.HexColor("#B42318")))
        elif item.get("status") == "warn":
            check_style.append(("TEXTCOLOR", (1, row_index), (1, row_index), colors.HexColor("#9A6700")))
        else:
            check_style.append(("TEXTCOLOR", (1, row_index), (1, row_index), colors.HexColor("#147D64")))
    check_table.setStyle(TableStyle(check_style))
    story.append(check_table)

    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph("9. Onay / imza kayıt alanı", section))
    signature_table = Table([
        [_p("Hazırlayan / İSG profesyoneli", label), _p("Ad soyad: ________________________________\nİmza / tarih: ______________________________", body)],
        [_p("İşveren / işveren vekili", label), _p("Ad soyad: ________________________________\nİmza / tarih: ______________________________", body)],
    ], colWidths=[53 * mm, 117 * mm])
    signature_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#CBD5E1")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F8FAFC")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(signature_table)
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "Bu belge, plan hazırlama ve saha doğrulama sürecini destekleyen bir çalışma çıktısıdır. "
        "Hazırlık yüzdesi hukuki uygunluk veya resmî onay anlamına gelmez. Krokiler işyerinde "
        "görünür yerlere asılmalı; ekip görevlendirmeleri, eğitimler, tatbikatlar ve işveren onayı "
        "saha kayıtlarıyla ayrıca doğrulanmalıdır.",
        ParagraphStyle("EmergencyPlanDisclaimer", parent=small, textColor=colors.HexColor("#5B3A00"),
                        backColor=colors.HexColor("#FFF7E6"), borderColor=colors.HexColor("#F2C57C"),
                        borderWidth=0.5, borderPadding=6, leading=10.5),
    ))
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
