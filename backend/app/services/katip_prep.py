"""KATİP / görevlendirme sözleşme hazırlık (stub — gerçek KATİP API yok).

Eksik İSG-KATİP no veya yüklenmemiş sözleşme dosyası olan aktif görevlendirmeleri listeler.
"""
from __future__ import annotations

import csv
import io
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    AssignmentStatus,
    Company,
    IsgProfessional,
    WorkplaceAssignment,
)

PREP_VERSION = "missing-contract-v1"


def _has_katip(a: WorkplaceAssignment) -> bool:
    return bool((a.isg_katip_contract_number or "").strip())


def _has_contract_file(a: WorkplaceAssignment) -> bool:
    return bool((a.contract_storage_path or "").strip() or (a.contract_file_name or "").strip())


def build_katip_prep(db: Session, *, osgb_id: int | None = None) -> dict[str, Any]:
    stmt = select(WorkplaceAssignment).where(WorkplaceAssignment.status == AssignmentStatus.ACTIVE)
    if osgb_id is not None:
        stmt = stmt.where(WorkplaceAssignment.osgb_id == osgb_id)
    assignments = list(db.scalars(stmt.order_by(WorkplaceAssignment.id)).all())

    company_ids = {a.company_id for a in assignments}
    pro_ids = {a.professional_id for a in assignments}
    companies = {
        c.id: c
        for c in db.scalars(select(Company).where(Company.id.in_(company_ids))).all()
    } if company_ids else {}
    pros = {
        p.id: p
        for p in db.scalars(select(IsgProfessional).where(IsgProfessional.id.in_(pro_ids))).all()
    } if pro_ids else {}

    gaps: list[dict[str, Any]] = []
    missing_katip = 0
    missing_file = 0
    complete = 0

    for a in assignments:
        has_k = _has_katip(a)
        has_f = _has_contract_file(a)
        if has_k and has_f:
            complete += 1
            continue
        if not has_k:
            missing_katip += 1
        if not has_f:
            missing_file += 1
        firm = companies.get(a.company_id)
        pro = pros.get(a.professional_id)
        gaps.append(
            {
                "assignment_id": a.id,
                "osgb_id": a.osgb_id,
                "company_id": a.company_id,
                "company_name": firm.name if firm else f"İşyeri #{a.company_id}",
                "professional_id": a.professional_id,
                "professional_name": pro.full_name if pro else f"Profesyonel #{a.professional_id}",
                "professional_type": a.professional_type.value if hasattr(a.professional_type, "value") else str(a.professional_type),
                "start_date": a.start_date.isoformat() if a.start_date else None,
                "end_date": a.end_date.isoformat() if a.end_date else None,
                "isg_katip_contract_number": (a.isg_katip_contract_number or "").strip() or None,
                "contract_file_name": a.contract_file_name,
                "missing_katip_number": not has_k,
                "missing_contract_file": not has_f,
                "reminder_hint": (
                    "KATİP no ve sözleşme dosyası eksik"
                    if (not has_k and not has_f)
                    else ("KATİP no eksik" if not has_k else "Sözleşme dosyası eksik")
                ),
            }
        )

    # Toplu hatırlatma sayıları (bildirim taraması ile uyumlu stub metrikleri)
    reminder_counts = {
        "missing_katip_number": missing_katip,
        "missing_contract_file": missing_file,
        "total_gaps": len(gaps),
        "ready_to_remind": len(gaps),
    }

    return {
        "prep_version": PREP_VERSION,
        "stub": True,
        "note": "Gerçek İSG-KATİP API bağlantısı yok; sistem kayıtlarından hazırlık listesi üretilir.",
        "osgb_id": osgb_id,
        "summary": {
            "active_assignments": len(assignments),
            "complete": complete,
            "gaps": len(gaps),
            "missing_katip_number": missing_katip,
            "missing_contract_file": missing_file,
        },
        "reminder_counts": reminder_counts,
        "gaps": gaps,
    }


def katip_prep_csv(db: Session, *, osgb_id: int | None = None) -> tuple[bytes, str]:
    data = build_katip_prep(db, osgb_id=osgb_id)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "assignment_id",
            "osgb_id",
            "company_id",
            "company_name",
            "professional_id",
            "professional_name",
            "professional_type",
            "start_date",
            "end_date",
            "isg_katip_contract_number",
            "contract_file_name",
            "missing_katip_number",
            "missing_contract_file",
            "reminder_hint",
        ]
    )
    for g in data["gaps"]:
        writer.writerow(
            [
                g["assignment_id"],
                g["osgb_id"],
                g["company_id"],
                g["company_name"],
                g["professional_id"],
                g["professional_name"],
                g["professional_type"],
                g["start_date"] or "",
                g["end_date"] or "",
                g["isg_katip_contract_number"] or "",
                g["contract_file_name"] or "",
                "1" if g["missing_katip_number"] else "0",
                "1" if g["missing_contract_file"] else "0",
                g["reminder_hint"],
            ]
        )
    # UTF-8 BOM for Excel
    raw = ("\ufeff" + buf.getvalue()).encode("utf-8")
    oid = osgb_id or "all"
    return raw, f"katip-hazirlik-{oid}.csv"
