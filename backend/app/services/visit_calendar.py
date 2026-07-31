"""Saha takvimi — planlı ziyaret, gecikme ve eksik uyarıları."""
from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    AssignmentStatus,
    Company,
    Employee,
    IsgProfessional,
    ServiceVisit,
    VisitStatus,
    WorkplaceAssignment,
)
from app.services.capacity_engine import compute_legal_required_minutes, normalize_hazard
from app.services.osgb_oversight import _month_bounds, _visit_minutes

STATUS_LABELS = {
    VisitStatus.PLANNED.value: "Planlandı",
    VisitStatus.COMPLETED.value: "Tamamlandı",
    VisitStatus.CANCELLED.value: "cancelled",
}


def _parse_month(month: str | None) -> tuple[date, date, str]:
    today = date.today()
    if month and len(month) >= 7:
        try:
            y, m = int(month[:4]), int(month[5:7])
            start = date(y, m, 1)
            last = monthrange(y, m)[1]
            end = date(y, m, last)
            return start, end, f"{y:04d}-{m:02d}"
        except ValueError:
            pass
    start, end = _month_bounds(today)
    return start, end, start.strftime("%Y-%m")


def _visit_row(v: ServiceVisit, companies: dict, pros: dict) -> dict:
    st = v.status.value if hasattr(v.status, "value") else str(v.status)
    return {
        "id": v.id,
        "visit_date": v.visit_date.isoformat() if v.visit_date else None,
        "company_id": v.company_id,
        "company_name": companies.get(v.company_id, f"#{v.company_id}"),
        "professional_id": v.professional_id,
        "professional_name": pros.get(v.professional_id, f"#{v.professional_id}"),
        "subject": v.subject,
        "duration_minutes": int(v.duration_minutes or 0),
        "status": st,
        "status_label": STATUS_LABELS.get(st, st),
        "has_notebook": bool(getattr(v, "notebook_storage_path", None) or getattr(v, "notebook_file_name", None)),
    }


def build_visit_calendar(db: Session, osgb_id: int | None, month: str | None = None) -> dict:
    month_start, month_end, period = _parse_month(month)
    today = date.today()
    horizon = today + timedelta(days=14)

    visit_q = select(ServiceVisit).where(
        ServiceVisit.visit_date >= month_start,
        ServiceVisit.visit_date <= month_end,
    )
    if osgb_id:
        visit_q = visit_q.where(ServiceVisit.osgb_id == osgb_id)
    visits = list(db.scalars(visit_q.order_by(ServiceVisit.visit_date, ServiceVisit.id)).all())

    company_ids = {v.company_id for v in visits}
    pro_ids = {v.professional_id for v in visits}

    assign_q = select(WorkplaceAssignment).where(WorkplaceAssignment.status == AssignmentStatus.ACTIVE)
    if osgb_id:
        assign_q = assign_q.where(WorkplaceAssignment.osgb_id == osgb_id)
    assignments = list(db.scalars(assign_q).all())
    for a in assignments:
        company_ids.add(a.company_id)
        pro_ids.add(a.professional_id)

    companies = {
        c.id: c.name
        for c in db.scalars(select(Company).where(Company.id.in_(company_ids or {0}))).all()
    }
    pros = {
        p.id: p.full_name
        for p in db.scalars(select(IsgProfessional).where(IsgProfessional.id.in_(pro_ids or {0}))).all()
    }

    visit_rows = [_visit_row(v, companies, pros) for v in visits]

    by_date: dict[str, list] = {}
    for row in visit_rows:
        by_date.setdefault(row["visit_date"], []).append(row)

    days = []
    d = month_start
    while d <= month_end:
        key = d.isoformat()
        day_visits = by_date.get(key, [])
        days.append(
            {
                "date": key,
                "weekday": d.weekday(),
                "is_today": d == today,
                "visit_count": len(day_visits),
                "planned_count": sum(1 for x in day_visits if x["status"] == VisitStatus.PLANNED.value),
                "completed_count": sum(1 for x in day_visits if x["status"] == VisitStatus.COMPLETED.value),
                "visits": day_visits,
            }
        )
        d += timedelta(days=1)

    overdue = [
        row
        for row in visit_rows
        if row["status"] == VisitStatus.PLANNED.value and row["visit_date"] and row["visit_date"] < today.isoformat()
    ]
    upcoming = [
        row
        for row in visit_rows
        if row["status"] == VisitStatus.PLANNED.value
        and row["visit_date"]
        and today.isoformat() <= row["visit_date"] <= horizon.isoformat()
    ]

    emp_counts: dict[int, int] = {}
    if company_ids:
        rows = db.execute(
            select(Employee.company_id, func.count()).where(Employee.company_id.in_(company_ids)).group_by(Employee.company_id)
        ).all()
        emp_counts = {int(cid): int(cnt) for cid, cnt in rows}

    missing: list[dict] = []
    cur_month_start, cur_month_end = _month_bounds(today)
    for a in assignments:
        company = db.get(Company, a.company_id)
        if not company:
            continue
        required = int(a.required_minutes_monthly or 0)
        if required <= 0:
            emp = emp_counts.get(a.company_id, 0)
            required = compute_legal_required_minutes(
                company.hazard_class, emp, a.professional_type
            )
        if required <= 0:
            continue
        visit_min, _, _ = _visit_minutes(db, a.professional_id, a.company_id, cur_month_start, cur_month_end)
        actual = visit_min if visit_min > 0 else int(a.actual_minutes_monthly or 0)
        if actual >= required * 0.8:
            continue
        has_future_plan = any(
            v.company_id == a.company_id
            and v.professional_id == a.professional_id
            and v.status == VisitStatus.PLANNED
            and v.visit_date >= today
            for v in visits
        )
        gap = required - actual
        missing.append(
            {
                "assignment_id": a.id,
                "company_id": a.company_id,
                "company_name": company.name,
                "professional_id": a.professional_id,
                "professional_name": pros.get(a.professional_id, f"#{a.professional_id}"),
                "required_minutes": required,
                "actual_minutes": actual,
                "gap_minutes": gap,
                "has_future_plan": has_future_plan,
                "hazard_class": normalize_hazard(company.hazard_class),
            }
        )
    missing.sort(key=lambda x: (-x["gap_minutes"], x["company_name"]))

    alerts: list[dict] = []
    if overdue:
        alerts.append({"level": "critical", "text": f"{len(overdue)} planlı ziyaret gecikmiş (tarihi geçti)."})
    no_plan = [m for m in missing if not m["has_future_plan"]]
    if no_plan:
        alerts.append({"level": "warning", "text": f"{len(no_plan)} görevlendirmede saha süresi eksik ve planlı ziyaret yok."})

    return {
        "osgb_id": osgb_id,
        "period": period,
        "period_start": month_start.isoformat(),
        "period_end": month_end.isoformat(),
        "summary": {
            "total_visits": len(visit_rows),
            "planned": sum(1 for r in visit_rows if r["status"] == VisitStatus.PLANNED.value),
            "completed": sum(1 for r in visit_rows if r["status"] == VisitStatus.COMPLETED.value),
            "overdue": len(overdue),
            "upcoming_14d": len(upcoming),
            "missing_coverage": len(missing),
            "missing_without_plan": len(no_plan),
        },
        "days": days,
        "overdue": overdue,
        "upcoming": upcoming,
        "missing": missing[:20],
        "alerts": alerts,
    }
