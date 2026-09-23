"""Firma bazında ilkyardımcı yeterlilik ve belge geçerliliği hesabı."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import Company, EmergencyTeamAssignment, Employee

FIRST_AID_REQUIRED_PER_EMPLOYEES = {
    "az tehlikeli": 20,
    "tehlikeli": 15,
    "çok tehlikeli": 10,
}
FIRST_AID_WARNING_DAYS = (90, 60, 30, 15, 7)


def _hazard_key(value: str | None) -> str:
    return " ".join(str(value or "").strip().casefold().replace("ı", "i").split())


def required_first_aiders(active_employee_count: int, hazard_class: str | None) -> int | None:
    per = FIRST_AID_REQUIRED_PER_EMPLOYEES.get(_hazard_key(hazard_class))
    if not per or active_employee_count < 1:
        return 0 if per else None
    return (int(active_employee_count) + per - 1) // per


def _status(end_date: date | None, today: date) -> tuple[str, int | None]:
    if not end_date:
        return "incomplete", None
    days = (end_date - today).days
    if days < 0:
        return "expired", days
    if days <= 90:
        return "expiring_soon", days
    return "valid", days


def build_first_aid_compliance(db: Session, company: Company, *, today: date | None = None) -> dict:
    today = today or date.today()
    employees = list(db.scalars(select(Employee).where(Employee.company_id == company.id)).all())
    active_ids = {
        employee.id for employee in employees
        if employee.is_active and not employee.exit_date
    }
    active_count = len(active_ids)
    required = required_first_aiders(active_count, company.hazard_class)
    assignments = list(db.scalars(
        select(EmergencyTeamAssignment)
        .where(
            EmergencyTeamAssignment.company_id == company.id,
            EmergencyTeamAssignment.is_active.is_(True),
            EmergencyTeamAssignment.employee_id.in_(active_ids or {0}),
        )
        .options(
            selectinload(EmergencyTeamAssignment.employee),
            selectinload(EmergencyTeamAssignment.trainings),
        )
    ).all())

    # Bir kişi birden fazla ekip/kayıt içinde olsa bile en iyi belge kaydı bir kez sayılır.
    by_employee: dict[int, dict] = {}
    for assignment in assignments:
        aid = assignment.employee_id
        for training in assignment.trainings or []:
            if not (training.first_aid_cert_no or training.first_aid_start or training.first_aid_end):
                continue
            row = by_employee.setdefault(aid, {
                "employee_id": aid,
                "name": assignment.employee.full_name if assignment.employee else "—",
                "job_title": assignment.employee.job_title if assignment.employee else None,
                "department": assignment.employee.department if assignment.employee else None,
                "certificate_no": None,
                "start_date": None,
                "end_date": None,
            })
            end_date = training.first_aid_end
            if row["end_date"] is None or (end_date and end_date > row["end_date"]):
                row.update({
                    "certificate_no": training.first_aid_cert_no,
                    "start_date": training.first_aid_start,
                    "end_date": end_date,
                })

    people = []
    counts = {"valid": 0, "expiring_soon": 0, "expired": 0, "incomplete": 0}
    for row in by_employee.values():
        status, days = _status(row["end_date"], today)
        counts[status] += 1
        people.append({**row, "status": status, "days_left": days,
                       "start_date": row["start_date"].isoformat() if row["start_date"] else None,
                       "end_date": row["end_date"].isoformat() if row["end_date"] else None})
    people.sort(key=lambda row: (0 if row["status"] == "expired" else 1 if row["status"] == "incomplete" else 2, row["days_left"] if row["days_left"] is not None else -1))
    # Süresi yaklaşan belge bugün hâlâ geçerlidir; yalnız gelecek risk hesabında
    # yenilenmemiş kabul edilerek ayrıca değerlendirilir.
    valid = counts["valid"] + counts["expiring_soon"]
    missing = max(0, (required or 0) - valid) if required is not None else None
    upcoming = [row for row in people if row["status"] == "expiring_soon"]
    future_valid = max(0, valid - len(upcoming))
    future_missing = max(0, (required or 0) - future_valid) if required is not None else None
    return {
        "hazard_class": company.hazard_class,
        "hazard_known": required is not None,
        "active_employee_count": active_count,
        "required_count": required,
        "record_count": len(people),
        "valid_count": valid,
        "expiring_soon_count": counts["expiring_soon"],
        "expired_count": counts["expired"],
        "incomplete_count": counts["incomplete"],
        "missing_count": missing,
        "future_valid_count": future_valid,
        "future_missing_count": future_missing,
        "future_window_days": 90,
        "people": people,
    }


def first_aid_alerts(summary: dict) -> list[dict]:
    if not summary.get("hazard_known"):
        return [{"level": "warning", "code": "first_aid_hazard_unknown", "text": "Tehlike sınıfı belirlenemedi — ilkyardımcı yeterlilik hesabı yapılamıyor."}]
    alerts = []
    if summary["missing_count"]:
        alerts.append({"level": "critical", "code": "first_aid_shortage", "text": f"İlkyardımcı sayısı yetersiz: {summary['missing_count']} eksik."})
    if summary["expired_count"]:
        alerts.append({"level": "critical", "code": "first_aid_expired", "text": f"{summary['expired_count']} ilkyardımcı belgesinin süresi dolmuş."})
    if summary["expiring_soon_count"]:
        alerts.append({"level": "warning", "code": "first_aid_expiring", "text": f"{summary['expiring_soon_count']} ilkyardımcı belgesi 90 gün içinde sona erecek."})
    if summary["incomplete_count"]:
        alerts.append({"level": "warning", "code": "first_aid_incomplete", "text": f"{summary['incomplete_count']} ilkyardımcı kaydında belge bilgisi eksik."})
    if summary["future_missing_count"] and not summary["missing_count"]:
        alerts.append({"level": "warning", "code": "first_aid_future_shortage", "text": f"Belgeler yenilenmezse 90 gün içinde {summary['future_missing_count']} ilkyardımcı eksik kalacak."})
    return alerts
