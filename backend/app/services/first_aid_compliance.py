"""Firma bazında ilkyardımcı yeterlilik ve belge geçerliliği hesabı."""
from __future__ import annotations

from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.input_rules import application_today
from app.models.entities import (
    Company, EmergencyTeam, EmergencyTeamAssignment, EmergencyTeamTraining, Employee,
)

FIRST_AID_REQUIRED_PER_EMPLOYEES = {
    "az tehlikeli": 20,
    "tehlikeli": 15,
    "çok tehlikeli": 10,
}
FIRST_AID_WARNING_DAYS = (90, 60, 30, 15, 7)


def _hazard_key(value: str | None) -> str:
    return " ".join(str(value or "").strip().casefold().replace("ı", "i").replace("\u0307", "").split())


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


def _certificate_fields(training: EmergencyTeamTraining, *, first_aid_team: bool):
    if training.first_aid_cert_no or training.first_aid_start or training.first_aid_end:
        return training.first_aid_cert_no, training.first_aid_start, training.first_aid_end
    # İlk yardım ekibinin genel sertifika alanları da aynı belgeyi taşıyabilir.
    # Diğer ekiplerin veya açıkça başka türdeki eğitimlerin belgeleri sayılmaz.
    training_kind = _hazard_key(training.training_type).replace(" ", "")
    if first_aid_team and (
        not training_kind or "ilkyard" in training_kind or training_kind == "sertifikabelgesi"
    ) and (training.certificate_no or training.valid_until or training.file_path):
        return training.certificate_no, training.training_date, training.valid_until
    return None


def build_first_aid_compliance(db: Session, company: Company, *, today: date | None = None) -> dict:
    today = today or application_today()
    employees = list(db.scalars(select(Employee).where(Employee.company_id == company.id)).all())
    active_ids = {
        employee.id for employee in employees
        if employee.is_active
        and (not employee.start_date or employee.start_date <= today)
        and (not employee.exit_date or employee.exit_date > today)
    }
    active_count = len(active_ids)
    required = required_first_aiders(active_count, company.hazard_class)
    assignments = list(db.scalars(
        select(EmergencyTeamAssignment)
        .join(EmergencyTeam, EmergencyTeamAssignment.team_id == EmergencyTeam.id)
        .where(
            EmergencyTeamAssignment.company_id == company.id,
            EmergencyTeam.company_id == company.id,
            EmergencyTeam.is_active.is_(True),
            EmergencyTeamAssignment.is_active.is_(True),
            EmergencyTeamAssignment.employee_id.in_(active_ids or {0}),
            or_(EmergencyTeamAssignment.assign_start.is_(None), EmergencyTeamAssignment.assign_start <= today),
            or_(EmergencyTeamAssignment.assign_end.is_(None), EmergencyTeamAssignment.assign_end >= today),
        )
        .options(
            selectinload(EmergencyTeamAssignment.employee),
            selectinload(EmergencyTeamAssignment.trainings),
            selectinload(EmergencyTeamAssignment.team).selectinload(EmergencyTeam.team_type),
        )
    ).all())

    # Bir kişi birden fazla ekip/kayıt içinde olsa bile en iyi belge kaydı bir kez sayılır.
    by_employee: dict[int, dict] = {}
    primary_ids: set[int] = set()
    reserve_ids: set[int] = set()

    def person_row(assignment):
        return by_employee.setdefault(assignment.employee_id, {
            "employee_id": assignment.employee_id,
            "name": assignment.employee.full_name,
            "job_title": assignment.employee.job_title,
            "department": assignment.employee.department,
            "membership": None,
            "certificate_no": None,
            "start_date": None,
            "end_date": None,
        })

    for assignment in assignments:
        aid = assignment.employee_id
        first_aid_team = assignment.team.team_type.code == "ilk_yardim"
        if first_aid_team:
            row = person_row(assignment)
            if assignment.membership == "asil":
                primary_ids.add(aid)
                row["membership"] = "asil"
            elif assignment.membership == "yedek":
                reserve_ids.add(aid)
                if row["membership"] != "asil":
                    row["membership"] = "yedek"
        for training in assignment.trainings or []:
            certificate = _certificate_fields(training, first_aid_team=first_aid_team)
            if certificate is None:
                continue
            certificate_no, start_date, end_date = certificate
            # Henüz başlamamış bir eğitim bugünkü yeterliliği tamamlamaz.
            if start_date and start_date > today:
                continue
            row = person_row(assignment)
            if row["end_date"] is None or (end_date and end_date > row["end_date"]):
                row.update({
                    "certificate_no": certificate_no,
                    "start_date": start_date,
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
    assignment_missing = max(0, required - len(primary_ids)) if required is not None else None
    return {
        "hazard_class": company.hazard_class,
        "hazard_known": required is not None,
        "active_employee_count": active_count,
        "required_count": required,
        "assigned_count": len(primary_ids | reserve_ids),
        "assigned_primary_count": len(primary_ids),
        "assigned_reserve_count": len(reserve_ids - primary_ids),
        "assignment_missing_count": assignment_missing,
        "assignment_complete": assignment_missing == 0 if required is not None and active_count else None,
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
    if summary["assignment_missing_count"]:
        alerts.append({"level": "critical", "code": "first_aid_assignment_shortage", "text": f"İlkyardım ekibinde {summary['assignment_missing_count']} asıl görevlendirme eksik ({summary['assigned_primary_count']}/{summary['required_count']})."})
    if summary["missing_count"]:
        if summary["assignment_complete"] and summary["incomplete_count"]:
            alerts.append({"level": "warning", "code": "first_aid_incomplete", "text": f"İlkyardım görevlendirmeleri tamamlandı ({summary['assigned_primary_count']}/{summary['required_count']} asıl); {summary['incomplete_count']} kişinin belge bilgisi eksik."})
        else:
            alerts.append({"level": "critical", "code": "first_aid_shortage", "text": f"Geçerli ilkyardımcı belgesi sayısı yetersiz: {summary['valid_count']}/{summary['required_count']}; {summary['missing_count']} geçerli belge gerekli."})
    if summary["expired_count"]:
        alerts.append({"level": "critical", "code": "first_aid_expired", "text": f"{summary['expired_count']} ilkyardımcı belgesinin süresi dolmuş."})
    if summary["expiring_soon_count"]:
        alerts.append({"level": "warning", "code": "first_aid_expiring", "text": f"{summary['expiring_soon_count']} ilkyardımcı belgesi 90 gün içinde sona erecek."})
    if summary["incomplete_count"] and not any(alert["code"] == "first_aid_incomplete" for alert in alerts):
        alerts.append({"level": "warning", "code": "first_aid_incomplete", "text": f"{summary['incomplete_count']} ilkyardımcı kaydında belge bilgisi eksik."})
    if summary["future_missing_count"] and not summary["missing_count"]:
        alerts.append({"level": "warning", "code": "first_aid_future_shortage", "text": f"Belgeler yenilenmezse 90 gün içinde {summary['future_missing_count']} ilkyardımcı eksik kalacak."})
    return alerts
