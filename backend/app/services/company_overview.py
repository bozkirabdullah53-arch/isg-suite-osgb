"""Müşteri 360 — işyeri bazlı birleşik özet."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    AnnualPlanItem,
    AnnualPlanStatus,
    AssignmentStatus,
    Branch,
    Company,
    DocumentRecord,
    Employee,
    FinanceTransaction,
    HealthFitnessStatus,
    HealthRecord,
    IncidentEvent,
    IsgModule,
    IsgProfessional,
    IsgRecord,
    PpeAssignment,
    RiskAssessment,
    RiskDof,
    ServiceContract,
    ServiceVisit,
    TrainingSession,
    User,
    UserRole,
    WorkplaceAssignment,
)
from app.services.osgb_oversight import build_oversight

TYPE_LABELS = {
    "safety_specialist": "İSG Uzmanı",
    "workplace_physician": "İşyeri Hekimi",
    "other_health_personnel": "Diğer Sağlık Personeli",
}


def _compliance_slice(db: Session, company: Company) -> dict:
    overview = build_oversight(db, company.osgb_id)
    firm_rows: list[dict] = []
    gaps: list[dict] = []

    for row in overview.get("rows") or []:
        pro_name = row.get("full_name") or "—"
        pro_type = row.get("professional_type") or ""
        for firm in row.get("firms") or []:
            if firm.get("company_id") != company.id:
                continue
            firm_rows.append(
                {
                    "professional_name": pro_name,
                    "professional_type": pro_type,
                    "role_label": TYPE_LABELS.get(pro_type, pro_type),
                    "score": firm.get("score", 0),
                    "status": firm.get("status", "unknown"),
                    "failed_count": firm.get("failed_count", 0),
                    "visit_count": firm.get("visit_count", 0),
                    "assignment_id": firm.get("assignment_id"),
                }
            )
            for check in firm.get("checks") or []:
                if check.get("passed"):
                    continue
                gaps.append(
                    {
                        "professional_name": pro_name,
                        "role_label": TYPE_LABELS.get(pro_type, pro_type),
                        "code": check.get("code"),
                        "title": check.get("title"),
                        "detail": check.get("detail"),
                        "legal": check.get("legal"),
                    }
                )

    worst = min(firm_rows, key=lambda f: f.get("score", 100)) if firm_rows else None
    return {
        "professionals": firm_rows,
        "worst_score": worst.get("score") if worst else None,
        "worst_status": worst.get("status") if worst else None,
        "gap_count": len(gaps),
        "gaps": gaps[:12],
    }


def build_company_overview(db: Session, company: Company) -> dict:
    cid = company.id
    today = date.today()
    year = today.year
    soon = today + timedelta(days=30)

    branches_count = db.scalar(select(func.count()).select_from(Branch).where(Branch.company_id == cid)) or 0
    employee_count = db.scalar(select(func.count()).select_from(Employee).where(Employee.company_id == cid)) or 0

    assignments = list(
        db.scalars(
            select(WorkplaceAssignment)
            .where(
                WorkplaceAssignment.company_id == cid,
                WorkplaceAssignment.status == AssignmentStatus.ACTIVE,
            )
            .order_by(WorkplaceAssignment.id)
        ).all()
    )
    pro_map = {
        p.id: p
        for p in db.scalars(
            select(IsgProfessional).where(
                IsgProfessional.id.in_({a.professional_id for a in assignments} or {0})
            )
        ).all()
    }
    assignment_rows = []
    for a in assignments:
        pro = pro_map.get(a.professional_id)
        assignment_rows.append(
            {
                "id": a.id,
                "professional_name": pro.full_name if pro else f"#{a.professional_id}",
                "professional_type": a.professional_type.value if a.professional_type else "",
                "role_label": TYPE_LABELS.get(
                    a.professional_type.value if a.professional_type else "", ""
                ),
                "required_minutes_monthly": a.required_minutes_monthly,
                "isg_katip_contract_number": a.isg_katip_contract_number,
                "start_date": a.start_date.isoformat() if a.start_date else None,
                "end_date": a.end_date.isoformat() if a.end_date else None,
            }
        )

    visits = list(
        db.scalars(
            select(ServiceVisit)
            .where(ServiceVisit.company_id == cid)
            .order_by(ServiceVisit.visit_date.desc(), ServiceVisit.id.desc())
            .limit(8)
        ).all()
    )
    visit_rows = []
    for v in visits:
        pro = db.get(IsgProfessional, v.professional_id)
        visit_rows.append(
            {
                "id": v.id,
                "visit_date": v.visit_date.isoformat() if v.visit_date else None,
                "subject": v.subject,
                "duration_minutes": v.duration_minutes,
                "status": v.status.value if v.status else None,
                "professional_name": pro.full_name if pro else None,
                "has_notebook": bool(v.notebook_storage_path or v.notebook_file_name),
            }
        )

    contracts = list(
        db.scalars(
            select(ServiceContract)
            .where(ServiceContract.company_id == cid)
            .order_by(ServiceContract.end_date.asc().nullslast(), ServiceContract.id.desc())
        ).all()
    )
    contract_rows = []
    for c in contracts:
        days_left = (c.end_date - today).days if c.end_date else None
        contract_rows.append(
            {
                "id": c.id,
                "contract_number": c.contract_number,
                "start_date": c.start_date.isoformat() if c.start_date else None,
                "end_date": c.end_date.isoformat() if c.end_date else None,
                "days_left": days_left,
                "status": c.status,
                "monthly_fee": c.monthly_fee,
                "expiring_soon": days_left is not None and 0 <= days_left <= 30,
            }
        )

    open_risks = db.scalar(
        select(func.count()).select_from(RiskAssessment).where(
            RiskAssessment.company_id == cid,
            RiskAssessment.status == "Açık",
        )
    ) or 0
    risk_ids = list(db.scalars(select(RiskAssessment.id).where(RiskAssessment.company_id == cid)).all())
    open_dofs = 0
    overdue_dofs = 0
    if risk_ids:
        dofs = list(db.scalars(select(RiskDof).where(RiskDof.risk_id.in_(risk_ids))).all())
        open_dofs = sum(1 for d in dofs if not d.is_completed)
        overdue_dofs = sum(
            1 for d in dofs if (not d.is_completed) and d.term_date and d.term_date < today
        )

    health_items = list(
        db.scalars(
            select(HealthRecord).where(
                HealthRecord.company_id == cid,
                HealthRecord.deleted_at.is_(None),
            )
        ).all()
    )
    health_summary = {
        "total": len(health_items),
        "overdue": sum(1 for i in health_items if i.next_examination_date and i.next_examination_date < today),
        "due_soon": sum(
            1 for i in health_items if i.next_examination_date and today <= i.next_examination_date <= soon
        ),
        "unfit": sum(1 for i in health_items if i.fitness_status == HealthFitnessStatus.UNFIT),
    }

    plan_items = list(
        db.scalars(
            select(AnnualPlanItem).where(
                AnnualPlanItem.company_id == cid,
                AnnualPlanItem.year == year,
                AnnualPlanItem.deleted_at.is_(None),
            )
        ).all()
    )
    plan_summary = {
        "year": year,
        "total": len(plan_items),
        "completed": sum(1 for i in plan_items if i.status == AnnualPlanStatus.COMPLETED),
        "delayed": sum(1 for i in plan_items if i.status == AnnualPlanStatus.DELAYED),
    }

    ppe_rows = list(
        db.scalars(
            select(PpeAssignment).where(
                PpeAssignment.company_id == cid,
                PpeAssignment.deleted_at.is_(None),
                PpeAssignment.status.in_(("teslim", "yenilenecek")),
            )
        ).all()
    )
    ppe_overdue = 0
    ppe_due_soon = 0
    for r in ppe_rows:
        dates = [d for d in (r.renewal_date, r.expiry_date) if d]
        if not dates:
            continue
        dmin = min(dates)
        if dmin < today:
            ppe_overdue += 1
        elif today <= dmin <= soon:
            ppe_due_soon += 1

    incidents = list(
        db.scalars(
            select(IncidentEvent)
            .where(IncidentEvent.company_id == cid)
            .order_by(IncidentEvent.event_date.desc(), IncidentEvent.id.desc())
            .limit(6)
        ).all()
    )
    incident_rows = [
        {
            "id": i.id,
            "form_no": i.form_no,
            "event_type": i.event_type,
            "summary": i.short_summary,
            "event_date": i.event_date.isoformat() if i.event_date else None,
            "status": i.status,
        }
        for i in incidents
    ]

    training_count = db.scalar(
        select(func.count()).select_from(TrainingSession).where(TrainingSession.company_id == cid)
    ) or 0
    expired_documents = db.scalar(
        select(func.count()).select_from(DocumentRecord).where(
            DocumentRecord.company_id == cid,
            DocumentRecord.valid_until.is_not(None),
            DocumentRecord.valid_until < today,
        )
    ) or 0
    accident_count = db.scalar(
        select(func.count()).select_from(IsgRecord).where(
            IsgRecord.company_id == cid,
            IsgRecord.module == IsgModule.ACCIDENT,
        )
    ) or 0

    finance_rows = list(
        db.scalars(
            select(FinanceTransaction)
            .where(FinanceTransaction.company_id == cid)
            .order_by(FinanceTransaction.transaction_date.desc(), FinanceTransaction.id.desc())
            .limit(6)
        ).all()
    )
    finance_summary = {
        "recent": [
            {
                "id": f.id,
                "description": f.description,
                "transaction_type": f.transaction_type,
                "amount": f.amount,
                "status": f.status,
                "transaction_date": f.transaction_date.isoformat() if f.transaction_date else None,
                "due_date": f.due_date.isoformat() if f.due_date else None,
            }
            for f in finance_rows
        ],
        "pending_amount": db.scalar(
            select(func.coalesce(func.sum(FinanceTransaction.amount), 0)).where(
                FinanceTransaction.company_id == cid,
                FinanceTransaction.status.in_(("pending", "overdue")),
            )
        )
        or 0,
    }

    compliance = _compliance_slice(db, company)

    alerts: list[dict] = []
    if compliance.get("worst_status") == "critical":
        alerts.append({"level": "critical", "text": "6331 hizmet denetimi kritik eksiklik var."})
    if open_dofs or overdue_dofs:
        alerts.append({"level": "warning", "text": f"{open_dofs} açık risk DÖF ({overdue_dofs} gecikmiş)."})
    if health_summary["overdue"]:
        alerts.append({"level": "warning", "text": f"{health_summary['overdue']} gecikmiş sağlık muayenesi."})
    if plan_summary["delayed"]:
        alerts.append({"level": "warning", "text": f"{plan_summary['delayed']} gecikmiş yıllık plan maddesi."})
    for c in contract_rows:
        if c.get("expiring_soon"):
            alerts.append(
                {
                    "level": "warning",
                    "text": f"Sözleşme {c['contract_number']} {c['days_left']} gün içinde bitiyor.",
                }
            )
            break

    return {
        "company": {
            "id": company.id,
            "name": company.name,
            "sgk_registry_no": company.sgk_registry_no,
            "hazard_class": company.hazard_class,
            "address": company.address,
            "phone": company.phone,
            "authorized_person": company.authorized_person,
            "is_active": company.is_active,
            "osgb_id": company.osgb_id,
        },
        "counts": {
            "branches": branches_count,
            "employees": employee_count,
            "assignments": len(assignment_rows),
            "trainings": training_count,
            "open_risks": open_risks,
            "open_dofs": open_dofs,
            "overdue_dofs": overdue_dofs,
            "accidents": accident_count,
            "expired_documents": expired_documents,
        },
        "assignments": assignment_rows,
        "visits": visit_rows,
        "contracts": contract_rows,
        "compliance": compliance,
        "health": health_summary,
        "annual_plan": plan_summary,
        "ppe": {"overdue": ppe_overdue, "due_soon": ppe_due_soon},
        "incidents": incident_rows,
        "finance": finance_summary,
        "alerts": alerts[:8],
        "generated_at": today.isoformat(),
    }
