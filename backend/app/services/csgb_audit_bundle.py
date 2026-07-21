"""ÇSGB denetim paketi — tek tık ZIP (checklist PDF + JSON kanıt özetleri)."""
from __future__ import annotations

import json
import zipfile
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.entities import (
    AssignmentStatus,
    Company,
    ServiceContract,
    ServiceVisit,
    WorkplaceAssignment,
)
from app.services.capacity_engine import build_capacity_overview
from app.services.csgb_audit_pack import build_csgb_audit_pack

PDF_FONT = "Helvetica"
PDF_FONT_BOLD = "Helvetica-Bold"
_ASSETS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_STATUS_TR = {"ready": "Hazır", "partial": "Kısmi", "missing": "Eksik"}


def _register_fonts() -> None:
    global PDF_FONT, PDF_FONT_BOLD
    candidates = [
        (_ASSETS / "DejaVuSans.ttf", _ASSETS / "DejaVuSans-Bold.ttf", "CsgbDejaVu", "CsgbDejaVu-Bold"),
        (Path(r"C:\Windows\Fonts\arial.ttf"), Path(r"C:\Windows\Fonts\arialbd.ttf"), "CsgbArial", "CsgbArial-Bold"),
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            "CsgbDejaVu",
            "CsgbDejaVu-Bold",
        ),
    ]
    for regular, bold, name, bold_name in candidates:
        if not regular.exists():
            continue
        try:
            pdfmetrics.registerFont(TTFont(name, str(regular)))
            pdfmetrics.registerFont(TTFont(bold_name, str(bold if bold.exists() else regular)))
            registerFontFamily(name, normal=name, bold=bold_name, italic=name, boldItalic=bold_name)
            PDF_FONT, PDF_FONT_BOLD = name, bold_name
            return
        except Exception:
            continue
    # Helvetica fallback (Latin-1); Turkish glyphs may be missing but PDF still builds
    PDF_FONT, PDF_FONT_BOLD = "Helvetica", "Helvetica-Bold"


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if hasattr(obj, "value"):
        return obj.value
    return str(obj)


def _esc(text: Any) -> str:
    s = str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return s


def build_checklist_pdf(pack: dict[str, Any]) -> bytes:
    """Müfettiş checklist PDF — pack özeti + kalem tablosu."""
    _register_fonts()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=12 * mm,
    )
    styles = getSampleStyleSheet()
    for s in styles.byName.values():
        s.fontName = PDF_FONT
    title = ParagraphStyle(
        "CsgbTitle",
        parent=styles["Title"],
        fontName=PDF_FONT_BOLD,
        fontSize=13,
        textColor=colors.white,
        alignment=TA_CENTER,
        leading=16,
    )
    h = ParagraphStyle(
        "CsgbH",
        parent=styles["Heading2"],
        fontName=PDF_FONT_BOLD,
        fontSize=11,
        textColor=colors.HexColor("#0d6efd"),
        spaceBefore=8,
        spaceAfter=4,
    )
    body = ParagraphStyle("CsgbB", parent=styles["Normal"], fontName=PDF_FONT, fontSize=9, leading=12, alignment=TA_LEFT)
    small = ParagraphStyle("CsgbS", parent=body, fontSize=8, leading=10, textColor=colors.HexColor("#475569"))

    osgb = pack.get("osgb") or {}
    sum_ = pack.get("summary") or {}
    elements: list[Any] = []

    cover = Table(
        [
            [Paragraph("ÇSGB OSGB DENETİM BELGE PAKETİ", title)],
            [
                Paragraph(
                    _esc(osgb.get("name") or "OSGB"),
                    ParagraphStyle("CsgbSub", parent=body, textColor=colors.white, alignment=TA_CENTER),
                )
            ],
            [
                Paragraph(
                    f"Hazırlık %{sum_.get('readiness_pct', 0)} · {pack.get('generated_at', '')}",
                    ParagraphStyle("CsgbMeta", parent=body, textColor=colors.white, alignment=TA_CENTER, fontSize=8),
                )
            ],
        ],
        colWidths=[182 * mm],
    )
    cover.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0d6efd")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    elements.append(cover)
    elements.append(Spacer(1, 5 * mm))
    elements.append(
        Paragraph(
            f"Yetki: {_esc(osgb.get('authorization_number') or '—')} · "
            f"İşyeri: {osgb.get('company_count', 0)} · "
            f"Profesyonel: {osgb.get('professional_count', 0)} · "
            f"Görevlendirme: {osgb.get('assignment_count', 0)}",
            body,
        )
    )
    elements.append(
        Paragraph(
            f"Özet — Hazır: {sum_.get('ready', 0)} · Kısmi: {sum_.get('partial', 0)} · "
            f"Eksik: {sum_.get('missing', 0)} · Toplam: {sum_.get('total', 0)}",
            body,
        )
    )
    if pack.get("legal_note"):
        elements.append(Spacer(1, 2 * mm))
        elements.append(Paragraph(_esc(pack["legal_note"]), small))

    elements.append(Paragraph("Denetim checklist", h))
    rows = [
        [
            Paragraph("<b>Durum</b>", small),
            Paragraph("<b>Kalem</b>", small),
            Paragraph("<b>Adet</b>", small),
            Paragraph("<b>Açıklama</b>", small),
        ]
    ]
    for it in pack.get("items") or []:
        st = _STATUS_TR.get(it.get("status"), it.get("status") or "—")
        rows.append(
            [
                Paragraph(_esc(st), small),
                Paragraph(_esc(it.get("title")), small),
                Paragraph(str(it.get("count") or 0), small),
                Paragraph(_esc((it.get("detail") or "")[:180]), small),
            ]
        )
    tbl = Table(rows, colWidths=[22 * mm, 48 * mm, 14 * mm, 98 * mm])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    elements.append(tbl)

    gaps = pack.get("gaps") or []
    if gaps:
        elements.append(Paragraph("Öncelikli eksikler", h))
        for g in gaps[:25]:
            elements.append(Paragraph(f"• {_esc(g)}", small))

    elements.append(Spacer(1, 6 * mm))
    elements.append(
        Paragraph(
            f"Üretilme: {datetime.utcnow().strftime('%d.%m.%Y %H:%M')} UTC · "
            "İSG Suite OSGB — müfettiş hazırlık paketi (İBYS/KATİP API bağlantısı yok).",
            small,
        )
    )
    doc.build(elements)
    return buf.getvalue()


def _assignment_rows(db: Session, oid: int, company_id: int | None = None) -> list[dict[str, Any]]:
    stmt = select(WorkplaceAssignment).where(
        WorkplaceAssignment.osgb_id == oid,
        or_(
            WorkplaceAssignment.status == AssignmentStatus.ACTIVE,
            WorkplaceAssignment.status == "active",
            WorkplaceAssignment.status == "ACTIVE",
        ),
    )
    if company_id is not None:
        stmt = stmt.where(WorkplaceAssignment.company_id == company_id)
    assignments = list(db.scalars(stmt).all())
    company_ids = {a.company_id for a in assignments}
    companies = {
        c.id: c
        for c in db.scalars(select(Company).where(Company.id.in_(company_ids or {0}))).all()
    } if company_ids else {}
    out = []
    for a in assignments:
        co = companies.get(a.company_id)
        out.append(
            {
                "id": a.id,
                "company_id": a.company_id,
                "company_name": co.name if co else None,
                "professional_id": a.professional_id,
                "professional_type": a.professional_type.value if a.professional_type else None,
                "start_date": a.start_date.isoformat() if a.start_date else None,
                "end_date": a.end_date.isoformat() if a.end_date else None,
                "required_minutes_monthly": a.required_minutes_monthly,
                "planned_minutes_monthly": a.planned_minutes_monthly,
                "actual_minutes_monthly": a.actual_minutes_monthly,
                "isg_katip_contract_number": a.isg_katip_contract_number,
                "has_contract_file": bool(a.contract_storage_path),
                "status": a.status.value if hasattr(a.status, "value") else str(a.status),
            }
        )
    return out


def _visit_rows(db: Session, oid: int, company_id: int | None = None) -> list[dict[str, Any]]:
    stmt = select(ServiceVisit).where(ServiceVisit.osgb_id == oid).order_by(ServiceVisit.visit_date.desc())
    if company_id is not None:
        stmt = stmt.where(ServiceVisit.company_id == company_id)
    visits = list(db.scalars(stmt).all())
    return [
        {
            "id": v.id,
            "company_id": v.company_id,
            "professional_id": v.professional_id,
            "visit_date": v.visit_date.isoformat() if v.visit_date else None,
            "duration_minutes": v.duration_minutes,
            "subject": v.subject,
            "status": v.status.value if hasattr(v.status, "value") else str(v.status),
            "has_notebook": bool(v.notebook_storage_path or v.notebook_file_name),
            "notebook_file_name": v.notebook_file_name,
        }
        for v in visits[:500]
    ]


def _contract_rows(db: Session, oid: int, company_id: int | None = None) -> list[dict[str, Any]]:
    stmt = select(ServiceContract).where(ServiceContract.osgb_id == oid)
    if company_id is not None:
        stmt = stmt.where(ServiceContract.company_id == company_id)
    contracts = list(db.scalars(stmt).all())
    company_ids = {c.company_id for c in contracts}
    companies = {
        c.id: c
        for c in db.scalars(select(Company).where(Company.id.in_(company_ids or {0}))).all()
    } if company_ids else {}
    return [
        {
            "id": c.id,
            "contract_number": c.contract_number,
            "company_id": c.company_id,
            "company_name": companies[c.company_id].name if c.company_id in companies else None,
            "start_date": c.start_date.isoformat() if c.start_date else None,
            "end_date": c.end_date.isoformat() if c.end_date else None,
            "monthly_fee": c.monthly_fee,
            "status": c.status,
        }
        for c in contracts
    ]


def build_csgb_audit_bundle_zip(
    db: Session,
    osgb_id: int | None = None,
    company_id: int | None = None,
) -> tuple[bytes, str]:
    """Tek tık denetim ZIP: checklist PDF/JSON + görevlendirme / ziyaret / sözleşme / kapasite.

    company_id verilirse müfettiş işyeri snapshot’ı (salt okunur filtre).
    Returns (zip_bytes, filename).
    """
    pack = build_csgb_audit_pack(db, osgb_id=osgb_id, company_id=company_id)
    osgb = pack.get("osgb") or {}
    scope = pack.get("scope") or {}
    oid = osgb.get("id")
    stamp = date.today().isoformat()
    if company_id is not None:
        raw_co = scope.get("company_name") or f"isyeri-{company_id}"
        safe_co = "".join(ch if (ch.isascii() and (ch.isalnum() or ch in ("-", "_"))) else "_" for ch in raw_co)[:40]
        safe_co = safe_co.strip("_") or f"isyeri-{company_id}"
        filename = f"csgb-isyeri-snapshot-{safe_co}-{stamp}.zip"
    else:
        safe_osgb = "".join(
            ch if (ch.isascii() and (ch.isalnum() or ch in ("-", "_"))) else "_"
            for ch in (osgb.get("name") or "osgb")
        )[:40]
        safe_osgb = safe_osgb.strip("_") or "osgb"
        filename = f"csgb-denetim-paketi-{safe_osgb}-{stamp}.zip"

    assignments = _assignment_rows(db, oid, company_id=company_id) if oid else []
    visits = _visit_rows(db, oid, company_id=company_id) if oid else []
    contracts = _contract_rows(db, oid, company_id=company_id) if oid else []
    capacity = build_capacity_overview(db, oid) if oid else {"summary": {}, "firms": [], "professionals": []}
    if company_id is not None and capacity.get("firms"):
        capacity = {
            **capacity,
            "firms": [f for f in capacity["firms"] if f.get("company_id") == company_id],
            "scope_company_id": company_id,
        }

    manifest = {
        "bundle_version": "audit-bundle-v3",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "osgb_id": oid,
        "osgb_name": osgb.get("name"),
        "scope": scope,
        "read_only": True,
        "files": [
            "00-README.txt",
            "01-checklist.pdf",
            "01-checklist.json",
            "02-assignments.json",
            "03-visits-notebook.json",
            "04-contracts.json",
            "05-capacity-snapshot.json",
        ],
        "counts": {
            "checklist_items": len(pack.get("items") or []),
            "assignments": len(assignments),
            "visits": len(visits),
            "visits_with_notebook": sum(1 for v in visits if v.get("has_notebook")),
            "contracts": len(contracts),
            "capacity_firms": len(capacity.get("firms") or []),
        },
    }

    scope_line = (
        f"Kapsam: işyeri snapshot — {scope.get('company_name')} (id={company_id})\n"
        if company_id is not None
        else "Kapsam: OSGB geneli\n"
    )
    readme = (
        "ÇSGB / müfettiş denetim hazırlık paketi (İSG Suite OSGB)\n"
        f"OSGB: {osgb.get('name') or '—'} (id={oid})\n"
        f"{scope_line}"
        f"Üretilme: {manifest['generated_at']}\n"
        f"Sürüm: {manifest['bundle_version']}\n"
        "Mod: salt okunur snapshot (indirme; sistemde değişiklik yok)\n\n"
        "İçerik:\n"
        "- 01-checklist.pdf / .json : hazırlık checklist ve eksikler\n"
        "- 02-assignments.json      : aktif görevlendirmeler + KATİP no\n"
        "- 03-visits-notebook.json  : saha ziyaretleri (has_notebook bayrağı)\n"
        "- 04-contracts.json        : hizmet sözleşmeleri\n"
        "- 05-capacity-snapshot.json: 6331 kapasite / asgari süre özeti\n\n"
        "Not: Gerçek İBYS/KATİP API entegrasyonu yoktur; sistem kayıtlarından üretilir.\n"
    )

    pdf_bytes = build_checklist_pdf(pack)

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("00-README.txt", readme)
        zf.writestr("01-checklist.pdf", pdf_bytes)
        zf.writestr(
            "01-checklist.json",
            json.dumps(pack, ensure_ascii=False, indent=2, default=_json_default),
        )
        zf.writestr(
            "02-assignments.json",
            json.dumps({"count": len(assignments), "items": assignments}, ensure_ascii=False, indent=2),
        )
        zf.writestr(
            "03-visits-notebook.json",
            json.dumps(
                {
                    "count": len(visits),
                    "with_notebook": sum(1 for v in visits if v.get("has_notebook")),
                    "items": visits,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        zf.writestr(
            "04-contracts.json",
            json.dumps({"count": len(contracts), "items": contracts}, ensure_ascii=False, indent=2),
        )
        zf.writestr(
            "05-capacity-snapshot.json",
            json.dumps(capacity, ensure_ascii=False, indent=2, default=_json_default),
        )
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    return buf.getvalue(), filename
