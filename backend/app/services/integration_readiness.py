"""İBYS/KATİP/ÇSGB entegrasyon hazırlık checklist (stub, salt okunur).

Gerçek İBYS / İSG-KATİP API bağlantısı yok; mevcut CSV paket, KATİP eksik listesi
ve ÇSGB denetim paketi özetinden hazırlık durumu üretilir.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.csgb_audit_pack import build_csgb_audit_pack
from app.services.csgb_readiness_advice import build_csgb_readiness_advice
from app.services.ibys_export import EXPORT_VERSION, build_ibys_export_summary
from app.services.katip_prep import PREP_VERSION, build_katip_prep

READINESS_VERSION = "checklist-v1"


def build_integration_readiness(db: Session, *, osgb_id: int | None = None) -> dict[str, Any]:
    ibys = build_ibys_export_summary(db, osgb_id=osgb_id)
    katip = build_katip_prep(db, osgb_id=osgb_id)
    csgb_pack = build_csgb_audit_pack(db, osgb_id=osgb_id)

    ibys_sum = ibys.get("summary") or {}
    companies = int(ibys_sum.get("companies") or 0)
    employees = int(ibys_sum.get("employees") or 0)
    active_employees = int(ibys_sum.get("active_employees") or 0)
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
        "active_employees": active_employees,
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

    csgb_sum = csgb_pack.get("summary") or {}
    readiness_pct = int(csgb_sum.get("readiness_pct") or 0)
    missing_items = list(csgb_pack.get("missing_items") or [])
    csgb_gaps = len(missing_items)
    advice = build_csgb_readiness_advice(
        missing_items=missing_items,
        active_employees=active_employees,
        company_count=companies,
    )

    if readiness_pct >= 70 and csgb_gaps == 0:
        csgb_status, csgb_ok = "ready", True
        csgb_detail = f"ÇSGB paketi hazır · %{readiness_pct}"
    elif readiness_pct >= 40:
        csgb_status, csgb_ok = "partial", False
        csgb_detail = f"ÇSGB paketi kısmi · %{readiness_pct} · öncelik {csgb_gaps}"
    else:
        csgb_status, csgb_ok = "missing" if readiness_pct < 20 else "partial", False
        csgb_detail = f"ÇSGB paketi eksik/kısmi · %{readiness_pct} · öncelik {csgb_gaps}"

    first_titles = [
        str(item.get("title") or "").strip()
        for item in advice.get("first_actions") or []
        if str(item.get("title") or "").strip()
    ][:3]
    if first_titles:
        csgb_detail += f" · ilk adımlar: {', '.join(first_titles)}"
    contextual_review_count = int(advice.get("contextual_review_count") or 0)
    if contextual_review_count:
        csgb_detail += f" · bağlamsal inceleme {contextual_review_count}"

    csgb_item = {
        "code": "csgb_pack",
        "title": "ÇSGB denetim paketi",
        "status": csgb_status,
        "ok": csgb_ok,
        "detail": csgb_detail,
        "readiness_pct": readiness_pct,
        "gap_count": csgb_gaps,
        "bundle_version": csgb_pack.get("bundle_version"),
        "advice_version": advice.get("advice_version"),
        "priority_items": advice.get("priority_items") or [],
        "first_actions": advice.get("first_actions") or [],
        "contextual_notes": advice.get("contextual_notes") or [],
        "contextual_review_count": contextual_review_count,
        "score_changed": False,
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
            "csgb_priority_count": csgb_gaps,
            "csgb_contextual_review_count": contextual_review_count,
            "ibys_csv_export": True,
        },
        "overall_ready": items_ok == len(checklist),
    }
