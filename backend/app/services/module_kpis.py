"""OSGB merkezi modül KPI özeti — risk/DÖF, eğitim yenileme, sağlık periyodik takip."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    Company,
    HealthFitnessStatus,
    HealthRecord,
    RiskAssessment,
    RiskDof,
    TrainingSession,
    TrainingStatus,
)


def _lead_high(record: HealthRecord) -> bool:
    return record.blood_lead_eval in ("yuksek", "kritik") or (
        record.blood_lead_value is not None
        and (record.blood_lead_ref or 30) < record.blood_lead_value
    )


def _company_map(db: Session, osgb_id: int) -> dict[int, str]:
    rows = db.scalars(
        select(Company).where(Company.osgb_id == osgb_id, Company.is_active.is_(True))
    ).all()
    return {c.id: c.name for c in rows}


def build_module_kpis(db: Session, osgb_id: int) -> dict:
    today = date.today()
    soon = today + timedelta(days=30)
    dof_soon = today + timedelta(days=7)

    companies = _company_map(db, osgb_id)
    company_ids = list(companies.keys()) or [0]

    risks = list(
        db.scalars(select(RiskAssessment).where(RiskAssessment.company_id.in_(company_ids))).all()
    )
    risk_ids = [r.id for r in risks] or [0]
    dofs = list(db.scalars(select(RiskDof).where(RiskDof.risk_id.in_(risk_ids))).all())

    open_risks = 0
    very_high = 0
    high = 0
    overdue_terms = 0
    risk_by_company: dict[int, int] = {}

    for r in risks:
        cid = r.company_id
        issues = 0
        if (r.status or "") == "Açık":
            open_risks += 1
            issues += 1
            if r.term_date and r.term_date < today:
                overdue_terms += 1
                issues += 1
        if r.risk_level == "Çok Yüksek":
            very_high += 1
            issues += 1
        elif r.risk_level == "Yüksek":
            high += 1
        if issues:
            risk_by_company[cid] = risk_by_company.get(cid, 0) + issues

    open_dofs = 0
    overdue_dofs = 0
    due_soon_dofs = 0
    risk_id_to_company = {r.id: r.company_id for r in risks}

    for d in dofs:
        if d.is_completed:
            continue
        open_dofs += 1
        cid = risk_id_to_company.get(d.risk_id)
        if d.term_date and d.term_date < today:
            overdue_dofs += 1
            if cid:
                risk_by_company[cid] = risk_by_company.get(cid, 0) + 1
        elif d.term_date and today <= d.term_date <= dof_soon:
            due_soon_dofs += 1

    trainings = list(
        db.scalars(select(TrainingSession).where(TrainingSession.company_id.in_(company_ids))).all()
    )
    planned = sum(1 for t in trainings if t.status == TrainingStatus.PLANNED)
    overdue_renewal = 0
    due_soon_renewal = 0
    training_by_company: dict[int, int] = {}

    for t in trainings:
        if not t.next_training_date:
            continue
        cid = t.company_id
        if t.next_training_date < today:
            overdue_renewal += 1
            training_by_company[cid] = training_by_company.get(cid, 0) + 1
        elif today <= t.next_training_date <= soon:
            due_soon_renewal += 1
            training_by_company[cid] = training_by_company.get(cid, 0) + 1

    health_items = list(
        db.scalars(
            select(HealthRecord).where(
                HealthRecord.company_id.in_(company_ids),
                HealthRecord.deleted_at.is_(None),
            )
        ).all()
    )
    overdue_health = 0
    due_soon_health = 0
    unfit = 0
    lead_high = 0
    health_by_company: dict[int, int] = {}

    for h in health_items:
        cid = h.company_id
        issues = 0
        if h.next_examination_date and h.next_examination_date < today:
            overdue_health += 1
            issues += 1
        elif h.next_examination_date and today <= h.next_examination_date <= soon:
            due_soon_health += 1
            issues += 1
        if h.fitness_status == HealthFitnessStatus.UNFIT:
            unfit += 1
            issues += 1
        if _lead_high(h):
            lead_high += 1
            issues += 1
        if issues:
            health_by_company[cid] = health_by_company.get(cid, 0) + issues

    top_companies = []
    for cid, name in companies.items():
        r_issues = risk_by_company.get(cid, 0)
        t_issues = training_by_company.get(cid, 0)
        h_issues = health_by_company.get(cid, 0)
        total = r_issues + t_issues + h_issues
        if total <= 0:
            continue
        top_companies.append(
            {
                "company_id": cid,
                "company_name": name,
                "risk_issues": r_issues,
                "training_issues": t_issues,
                "health_issues": h_issues,
                "total_issues": total,
            }
        )
    top_companies.sort(key=lambda x: (-x["total_issues"], x["company_name"]))
    top_companies = top_companies[:10]

    alerts: list[dict] = []
    if overdue_dofs:
        alerts.append({"level": "critical", "text": f"{overdue_dofs} gecikmiş risk DÖF kaydı var."})
    if overdue_health:
        alerts.append({"level": "warning", "text": f"{overdue_health} gecikmiş periyodik sağlık muayenesi."})
    if overdue_renewal:
        alerts.append({"level": "warning", "text": f"{overdue_renewal} eğitim yenileme tarihi geçmiş."})
    if lead_high:
        alerts.append({"level": "critical", "text": f"{lead_high} personelde yüksek kurşun / kritik tetkik bulgusu."})

    return {
        "osgb_id": osgb_id,
        "company_count": len(companies),
        "period": {"due_soon_days": 30, "dof_soon_days": 7},
        "risk": {
            "total_risks": len(risks),
            "open_risks": open_risks,
            "very_high": very_high,
            "high": high,
            "open_dofs": open_dofs,
            "overdue_dofs": overdue_dofs,
            "due_soon_dofs": due_soon_dofs,
            "overdue_terms": overdue_terms,
        },
        "training": {
            "total_sessions": len(trainings),
            "planned": planned,
            "overdue_renewal": overdue_renewal,
            "due_soon_renewal": due_soon_renewal,
            "companies_with_issues": len(training_by_company),
        },
        "health": {
            "tracked_records": len(health_items),
            "overdue": overdue_health,
            "due_soon": due_soon_health,
            "unfit": unfit,
            "lead_high": lead_high,
            "companies_with_issues": len(health_by_company),
        },
        "top_companies": top_companies,
        "alerts": alerts,
        "generated_at": today.isoformat(),
    }
