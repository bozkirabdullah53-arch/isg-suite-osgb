"""0.9.124 — İBYS/KATİP/ÇSGB entegrasyon hazırlık checklist (stub, salt okunur).

Gerçek İBYS / İSG-KATİP API bağlantısı yok; mevcut CSV paket, KATİP eksik listesi
ve ÇSGB denetim paketi özetinden hazırlık durumu üretilir.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.csgb_audit_pack import build_csgb_audit_dashboard_summary
from app.services.ibys_export import EXPORT_VERSION, build_ibys_export_summary
from app.services.katip_prep import PREP_VERSION, build_katip_prep

READINESS_VERSION = "checklist-v1"


def build_integration_readiness(db: Session, *, osgb_id: int | None = None) -> dict[str, Any]:
    ibys = build_ibys_export_summary(db, osgb_id=osgb_id)
    katip = build_katip_prep(db, osgb_id=osgb_id)
    csgb = build_csgb_audit_dashboard_summary(db, osgb_id=osgb_id)

    ibys_sum = ibys.get("summary") or {}
    companies = int(ibys_sum.get("companies") or 0)
    employees = int(ibys_sum.get("employees") or 0)
    # CSV export capability always exists (stub); data presence is informational.
    ibys_item = {
        "code": "ibys_csv_export",
        "title": "İBYS CSV export",
        "status": "ready",
        "ok": True,
        "detail": (
            f"CSV paket hazır (stub {EXPORT_VERSION}) · "
            f"{companies} işyeri, {employees} personel kaydı"
        ),
        "companies": companies,
        "employees": employees,
        "export_version": EXPORT_VERSION,
    }

    katip_sum = katip.get("summary") or {}
    gap_count = int(katip_sum.get("gaps") or len(katip.get("gaps") or []))
    missing_katip = int(katip_sum.get("missing_katip_number") or 0)
    missing_file = int(katip_sum.get("missing_contract_file") or 0)
    if gap_count == 0:
        katip_status, katip_ok = "ready", True
        katip_detail = f"Aktif görevlendirmelerde KATİP/sözleşme eksiği yok ({PREP_VERSION})"
    else:
        katip_status, katip_ok = "partial", False
        katip_detail = (
            f"{gap_count} eksik · KATİP no {missing_katip} · dosya {missing_file} "
            f"(stub {PREP_VERSION})"
        )
    katip_item = {
        "code": "katip_gaps",
        "title": "KATİP hazırlık",
        "status": katip_status,
        "ok": katip_ok,
        "detail": katip_detail,
        "gap_count": gap_count,
        "missing_katip_number": missing_katip,
        "missing_contract_file": missing_file,
        "prep_version": PREP_VERSION,
    }

    readiness_pct = int(csgb.get("readiness_pct") or (csgb.get("summary") or {}).get("readiness_pct") or 0)
    csgb_gaps = int(csgb.get("gap_count") or len(csgb.get("missing_items") or []))
    if readiness_pct >= 70 and csgb_gaps == 0:
        csgb_status, csgb_ok = "ready", True
        csgb_detail = f"ÇSGB paketi hazır · %{readiness_pct}"
    elif readiness_pct >= 40:
        csgb_status, csgb_ok = "partial", False
        csgb_detail = f"ÇSGB paketi kısmi · %{readiness_pct} · öncelik {csgb_gaps}"
    else:
        csgb_status, csgb_ok = "missing" if readiness_pct < 20 else "partial", False
        csgb_detail = f"ÇSGB paketi eksik/kısmi · %{readiness_pct} · öncelik {csgb_gaps}"
    csgb_item = {
        "code": "csgb_pack",
        "title": "ÇSGB denetim paketi",
        "status": csgb_status,
        "ok": csgb_ok,
        "detail": csgb_detail,
        "readiness_pct": readiness_pct,
        "gap_count": csgb_gaps,
        "bundle_version": csgb.get("bundle_version"),
    }

    checklist = [ibys_item, katip_item, csgb_item]
    ready_n = sum(1 for i in checklist if i["status"] == "ready")
    partial_n = sum(1 for i in checklist if i["status"] == "partial")
    missing_n = sum(1 for i in checklist if i["status"] == "missing")
    items_ok = sum(1 for i in checklist if i["ok"])

    return {
        "readiness_version": READINESS_VERSION,
        "stub": True,
        "note": (
            "Gerçek İBYS / İSG-KATİP API bağlantısı yok; "
            "CSV export, KATİP eksik listesi ve ÇSGB paket özeti üzerinden hazırlık kontrolü."
        ),
        "osgb_id": osgb_id,
        "checklist": checklist,
        "summary": {
            "ready": ready_n,
            "partial": partial_n,
            "missing": missing_n,
            "items_ok": items_ok,
            "items_total": len(checklist),
            "katip_gap_count": gap_count,
            "csgb_readiness_pct": readiness_pct,
            "ibys_csv_export": True,
        },
        "overall_ready": items_ok == len(checklist),
    }
