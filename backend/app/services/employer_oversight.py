"""İşveren / işyeri denetim paneli — salt okunur özet.

Müdahale yok: yalnızca ziyaret, iş kalemleri ve ÇSGB hazırlık sinyali.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    AnnualPlanItem,
    Company,
    EmergencyPlan,
    EyasStep,
    EyasWorkflow,
    HealthRecord,
    PpeAssignment,
    RiskAssessment,
    ServiceVisit,
    TrainingSession,
    TrainingStatus,
    User,
    VisitStatus,
)
from app.services.csgb_audit_pack import build_csgb_audit_pack
from app.services.company_overview import build_company_overview


def build_employer_oversight(db: Session, company: Company, viewer: User | None = None) -> dict[str, Any]:
    cid = company.id
    today = date.today()
    period_start = today.replace(day=1)
    period = f"{today.year:04d}-{today.month:02d}"

    visits_month = list(
        db.scalars(
            select(ServiceVisit).where(
                ServiceVisit.company_id == cid,
                ServiceVisit.visit_date >= period_start,
                ServiceVisit.visit_date <= today,
            )
        ).all()
    )
    completed = sum(1 for v in visits_month if v.status == VisitStatus.COMPLETED)
    planned = sum(1 for v in visits_month if v.status == VisitStatus.PLANNED)
    open_on_site = sum(
        1 for v in visits_month if v.checked_in_at and not v.checked_out_at
    )

    risk_open = (
        db.scalar(
            select(func.count())
            .select_from(RiskAssessment)
            .where(
                RiskAssessment.company_id == cid,
                RiskAssessment.status.notin_(["Tamamlandı", "Kapatıldı", "Kapalı"]),
            )
        )
        or 0
    )
    risk_total = (
        db.scalar(
            select(func.count()).select_from(RiskAssessment).where(RiskAssessment.company_id == cid)
        )
        or 0
    )
    risk_done = max(0, risk_total - risk_open)

    training_done = (
        db.scalar(
            select(func.count())
            .select_from(TrainingSession)
            .where(
                TrainingSession.company_id == cid,
                TrainingSession.status == TrainingStatus.COMPLETED,
            )
        )
        or 0
    )
    training_open = (
        db.scalar(
            select(func.count())
            .select_from(TrainingSession)
            .where(
                TrainingSession.company_id == cid,
                TrainingSession.status != TrainingStatus.COMPLETED,
            )
        )
        or 0
    )

    health_n = (
        db.scalar(select(func.count()).select_from(HealthRecord).where(HealthRecord.company_id == cid))
        or 0
    )
    health_with_file = (
        db.scalar(
            select(func.count())
            .select_from(HealthRecord)
            .where(
                HealthRecord.company_id == cid,
                HealthRecord.report_storage_path.is_not(None),
            )
        )
        or 0
    )

    emergency_n = (
        db.scalar(
            select(func.count())
            .select_from(EmergencyPlan)
            .where(EmergencyPlan.company_id == cid, EmergencyPlan.is_active.is_(True))
        )
        or 0
    )
    ppe_n = (
        db.scalar(select(func.count()).select_from(PpeAssignment).where(PpeAssignment.company_id == cid))
        or 0
    )
    annual_n = (
        db.scalar(
            select(func.count())
            .select_from(AnnualPlanItem)
            .where(AnnualPlanItem.company_id == cid, AnnualPlanItem.deleted_at.is_(None))
        )
        or 0
    )
    eyas_open = (
        db.scalar(
            select(func.count())
            .select_from(EyasWorkflow)
            .where(
                EyasWorkflow.company_id == cid,
                EyasWorkflow.is_active.is_(True),
                EyasWorkflow.status == "in_progress",
            )
        )
        or 0
    )
    eyas_locked = (
        db.scalar(
            select(func.count())
            .select_from(EyasWorkflow)
            .where(
                EyasWorkflow.company_id == cid,
                EyasWorkflow.is_active.is_(True),
                EyasWorkflow.status == "locked",
            )
        )
        or 0
    )

    work_items = [
        {
            "kind": "risk",
            "label": "Risk değerlendirme",
            "done": risk_done,
            "open": risk_open,
            "status": "done" if risk_total > 0 and risk_open == 0 else ("open" if risk_open else "missing"),
            "count": risk_total,
        },
        {
            "kind": "training",
            "label": "Eğitim",
            "done": training_done,
            "open": training_open,
            "status": "done" if training_done and not training_open else ("open" if training_open else "missing"),
            "count": training_done + training_open,
        },
        {
            "kind": "health",
            "label": "Sağlık kayıtları",
            "done": health_with_file,
            "open": max(0, health_n - health_with_file),
            "status": "done" if health_n and health_with_file == health_n else ("open" if health_n else "missing"),
            "count": health_n,
        },
        {
            "kind": "emergency",
            "label": "Acil durum planı",
            "done": emergency_n,
            "open": 0 if emergency_n else 1,
            "status": "done" if emergency_n else "missing",
            "count": emergency_n,
        },
        {
            "kind": "ppe",
            "label": "KKD teslim",
            "done": ppe_n,
            "open": 0 if ppe_n else 1,
            "status": "done" if ppe_n else "missing",
            "count": ppe_n,
        },
        {
            "kind": "annual_plan",
            "label": "Yıllık çalışma planı",
            "done": annual_n,
            "open": 0 if annual_n else 1,
            "status": "done" if annual_n else "missing",
            "count": annual_n,
        },
        {
            "kind": "eyas",
            "label": "Dijital onay akışları",
            "done": eyas_locked,
            "open": eyas_open,
            "status": "open" if eyas_open else ("done" if eyas_locked else "missing"),
            "count": eyas_open + eyas_locked,
        },
    ]
    work_done = sum(i["done"] for i in work_items)
    work_open = sum(i["open"] for i in work_items)

    readiness = {"pct": 0, "ready": 0, "partial": 0, "missing": 0, "items": [], "gaps": []}
    try:
        pack = build_csgb_audit_pack(db, osgb_id=company.osgb_id, company_id=cid)
        summary = pack.get("summary") or {}
        readiness = {
            "pct": int(summary.get("readiness_pct") or 0),
            "ready": int(summary.get("ready") or 0),
            "partial": int(summary.get("partial") or 0),
            "missing": int(summary.get("missing") or 0),
            "items": [
                {
                    "code": i.get("code"),
                    "title": i.get("title"),
                    "status": i.get("status"),
                    "detail": i.get("detail"),
                }
                for i in (pack.get("items") or [])[:40]
            ],
            "gaps": list(pack.get("gaps") or [])[:15],
        }
    except Exception:
        pass

    team = {"professionals": [], "gap_count": 0, "gaps": [], "worst_score": None, "worst_status": None}
    try:
        overview = build_company_overview(db, company)
        compliance = overview.get("compliance") or {}
        team = {
            "professionals": compliance.get("professionals") or [],
            "gap_count": int(compliance.get("gap_count") or 0),
            "gaps": compliance.get("gaps") or [],
            "worst_score": compliance.get("worst_score"),
            "worst_status": compliance.get("worst_status"),
            "assignments": overview.get("assignments") or [],
        }
    except Exception:
        pass

    # İmza / dijital onay akışları: Uzman → Hekim → İşveren/vekil
    approval_flows: list[dict[str, Any]] = []
    try:
        workflows = list(
            db.scalars(
                select(EyasWorkflow)
                .where(
                    EyasWorkflow.company_id == cid,
                    EyasWorkflow.is_active.is_(True),
                )
                .order_by(EyasWorkflow.id.desc())
                .limit(30)
            ).all()
        )
        for wf in workflows:
            steps = list(
                db.scalars(
                    select(EyasStep)
                    .where(EyasStep.workflow_id == wf.id)
                    .order_by(EyasStep.step_order)
                ).all()
            )
            step_out = []
            for st in steps:
                u = db.get(User, st.assignee_user_id)
                step_out.append(
                    {
                        "id": st.id,
                        "step_order": st.step_order,
                        "role_label": st.role_label,
                        "assignee_user_id": st.assignee_user_id,
                        "assignee_name": u.full_name if u else None,
                        "status": st.status,
                        "decided_at": st.decided_at.isoformat() + "Z" if st.decided_at else None,
                    }
                )
            active = next((s for s in step_out if s["status"] == "active"), None)
            can_approve = False
            if viewer and wf.status == "in_progress" and active:
                role_l = (active.get("role_label") or "").casefold()
                is_emp = "işveren" in role_l or "isveren" in role_l
                workplace_admin = (
                    getattr(viewer.role, "value", str(viewer.role)) == "company_admin"
                    and getattr(viewer, "company_id", None) == cid
                )
                if active.get("assignee_user_id") == viewer.id or (is_emp and workplace_admin):
                    can_approve = True
            approval_flows.append(
                {
                    "id": wf.id,
                    "title": wf.title,
                    "document_kind": wf.document_kind,
                    "source_key": wf.source_key,
                    "status": wf.status,
                    "current_step_order": wf.current_step_order,
                    "steps": step_out,
                    "waiting_on": active["role_label"] if active else None,
                    "waiting_user_id": active["assignee_user_id"] if active else None,
                    "can_approve": can_approve,
                }
            )
    except Exception:
        approval_flows = []

    # Verdict for single-screen "denetime hazır mı?"
    pct = readiness["pct"]
    if pct >= 80 and work_open == 0:
        verdict = "hazir"
        verdict_label = "Denetime hazır görünüyor"
    elif pct >= 50:
        verdict = "kismi"
        verdict_label = "Kısmen hazır — eksikler var"
    else:
        verdict = "riskli"
        verdict_label = "Denetime hazır değil — öncelikli eksikler var"

    return {
        "company_id": cid,
        "company_name": company.name,
        "period": period,
        "visits": {
            "this_month": len(visits_month),
            "completed": completed,
            "planned": planned,
            "open_on_site": open_on_site,
        },
        "work": {
            "done": work_done,
            "open": work_open,
            "items": work_items,
        },
        "readiness": readiness,
        "team": team,
        "approval_flows": approval_flows,
        "approval_chain": ["İş Güvenliği Uzmanı", "İşyeri Hekimi", "İşveren / vekili"],
        "verdict": verdict,
        "verdict_label": verdict_label,
        "notice": (
            "İmza akışı: Uzman → Hekim → İşveren/vekil. "
            "Sırası gelen kişi kendi hesabıyla onaylar. "
            "Diğer metrikler salt görüntülemedir."
        ),
        "read_only": True,
    }
