"""Read-only premium Education action dashboard.

This service answers one user question: "Bugün ne yapmalıyım?"
It never creates, updates, finalizes or deletes a training record. Existing
training/PDF/exam/certificate/presentation flows remain untouched.
"""
from __future__ import annotations

import os
from calendar import monthrange
from datetime import date, datetime, timezone
from types import SimpleNamespace
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Employee, TrainingParticipant, TrainingSession, TrainingStatus
from app.services import training_validity
from app.services.special_training_profiles import resolve_special_duration_hours
from app.services.training_lifecycle_v2 import premium_lifecycle_active, training_kind

DASHBOARD_ENV = "TRAINING_PREMIUM_DASHBOARD_V1_ENABLED"
DASHBOARD_FORCE_OFF_ENV = "TRAINING_PREMIUM_DASHBOARD_V1_FORCE_OFF"
LIFECYCLE_AFTER_ENV = "TRAINING_PREMIUM_LIFECYCLE_V2_AFTER"
DASHBOARD_VERSION = "training-premium-dashboard-v1"


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


def dashboard_active() -> bool:
    return (
        premium_lifecycle_active()
        and _truthy(os.getenv(DASHBOARD_ENV))
        and not _truthy(os.getenv(DASHBOARD_FORCE_OFF_ENV))
    )


def _cutover_date() -> date | None:
    raw = str(os.getenv(LIFECYCLE_AFTER_ENV, "") or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc)
    return parsed.date()


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def _status_value(training: TrainingSession) -> str:
    value = getattr(training.status, "value", training.status)
    return str(value or "")


def _is_basic_training(training: TrainingSession) -> bool:
    special = resolve_special_duration_hours(
        SimpleNamespace(
            training_type=training.training_type or "",
            title=training.title or "",
            notes=training.notes or "",
        )
    )
    if special:
        return False
    return training_kind(training.training_type, training.title) in {"initial_basic", "repeat_basic"}


def _work_start_state(employee: Employee, pairs: list[tuple[TrainingParticipant, TrainingSession]], *, cutover: date | None) -> dict[str, Any]:
    hire = employee.start_date
    if cutover is None or hire is None or hire < cutover:
        return {"status":"historical","label":"Tarihsel / takip dışı","tone":"neutral","training_id":None,"message":"Premium İşe Başlama takibi bu çalışanın işe girişinden sonra devreye alınmadığı için geriye dönük eksik kaydı üretilmez."}
    work_start = [(participant, training) for participant, training in pairs if _status_value(training) != TrainingStatus.CANCELLED.value and training_kind(training.training_type, training.title) == "work_start"]
    work_start.sort(key=lambda item: (item[1].end_date or item[1].start_date or date.min, item[1].id or 0), reverse=True)
    for participant, training in work_start:
        if _status_value(training) == TrainingStatus.COMPLETED.value and bool(participant.attended):
            return {"status":"ok","label":"Tamamlandı","tone":"ok","training_id":training.id,"message":"İşe Başlama Eğitimi katılımı doğrulanmış."}
    if work_start:
        _participant, training = work_start[0]
        return {"status":"pending","label":"Sonuç bekliyor","tone":"warning","training_id":training.id,"message":"İşe Başlama Eğitimi kaydı var; gerçek katılımın kesinleştirilmesi gerekiyor."}
    return {"status":"missing","label":"Eksik","tone":"danger","training_id":None,"message":"İşe Başlama Eğitimi kaydı bulunamadı; çalışan fiilen işe başlamadan önce planlayın."}


def _basic_state(employee: Employee, pairs: list[tuple[TrainingParticipant, TrainingSession]]) -> dict[str, Any]:
    basic = [(participant, training) for participant, training in pairs if _status_value(training) != TrainingStatus.CANCELLED.value and _is_basic_training(training)]
    basic.sort(key=lambda item: (item[1].end_date or item[1].start_date or date.min, item[1].id or 0), reverse=True)
    latest = basic[0][1] if basic else None
    evaluated = training_validity.evaluate_employee(hire_date=employee.start_date, last_training_end=(latest.end_date or latest.start_date) if latest else None, next_due=latest.next_training_date if latest else None)
    if latest is None and employee.start_date is not None:
        deadline = _add_months(employee.start_date, 3)
        days_left = (deadline - date.today()).days
        evaluated = {**evaluated,"days_left":days_left,"next_due":deadline.isoformat(),"message":f"İlk Temel İSG eğitimi en geç {deadline.strftime('%d.%m.%Y')} tarihinde tamamlanmalı" + (f" — {days_left} gün kaldı." if days_left >= 0 else f" — {abs(days_left)} gün gecikti.")}
    status = str(evaluated.get("status") or "never")
    days_left = evaluated.get("days_left")
    if status == "ok": tone, label = "ok", "Geçerli"
    elif status == "due_soon": tone, label = "warning", "Yakında yenilenecek"
    elif status == "never" and days_left is not None and int(days_left) >= 0: tone, label = "warning", "İlk temel eğitim bekliyor"
    else: tone, label = "danger", "Gecikmiş / eksik"
    return {**evaluated,"tone":tone,"label":label,"training_id":latest.id if latest else None}


def build_dashboard(db: Session, *, company_id: int) -> dict[str, Any]:
    employees = list(db.scalars(select(Employee).where(Employee.company_id == company_id, Employee.is_active.is_(True)).order_by(Employee.full_name)).all())
    employee_ids = [employee.id for employee in employees]
    pairs_by_employee: dict[int, list[tuple[TrainingParticipant, TrainingSession]]] = {employee_id: [] for employee_id in employee_ids}
    if employee_ids:
        pairs = db.execute(select(TrainingParticipant, TrainingSession).join(TrainingSession, TrainingSession.id == TrainingParticipant.training_id).where(TrainingSession.company_id == company_id, TrainingParticipant.employee_id.in_(employee_ids))).all()
        for participant, training in pairs: pairs_by_employee.setdefault(participant.employee_id, []).append((participant, training))
    cutover = _cutover_date()
    rows: list[dict[str, Any]] = []
    counts = {"work_start_missing":0,"work_start_pending":0,"work_start_ok":0,"work_start_historical":0,"basic_overdue":0,"basic_waiting":0,"basic_due_soon":0,"basic_ok":0}
    for employee in employees:
        pairs = pairs_by_employee.get(employee.id, [])
        work_start = _work_start_state(employee, pairs, cutover=cutover)
        basic = _basic_state(employee, pairs)
        counts[f"work_start_{work_start['status']}"] = counts.get(f"work_start_{work_start['status']}", 0) + 1
        if basic["status"] == "ok": counts["basic_ok"] += 1
        elif basic["status"] == "due_soon": counts["basic_due_soon"] += 1
        elif basic["status"] == "never" and basic.get("days_left") is not None and int(basic["days_left"]) >= 0: counts["basic_waiting"] += 1
        else: counts["basic_overdue"] += 1
        rows.append({"employee_id":employee.id,"full_name":employee.full_name,"department":employee.department,"job_title":employee.job_title,"start_date":employee.start_date.isoformat() if employee.start_date else None,"work_start":work_start,"basic":basic})
    trainings = list(db.scalars(select(TrainingSession).where(TrainingSession.company_id == company_id).order_by(TrainingSession.start_date.desc())).all())
    today = date.today()
    result_pending = sum(1 for training in trainings if _status_value(training) == TrainingStatus.PLANNED.value and (training.end_date or training.start_date) <= today and bool(training.participants))
    planned_future = sum(1 for training in trainings if _status_value(training) == TrainingStatus.PLANNED.value and training.start_date > today)
    actions = [
        {"code":"work_start_missing","severity":"danger","count":counts["work_start_missing"],"title":"İşe Başlama Eğitimi eksik","instruction":"Bu çalışanlar için işe başlamadan önce İşe Başlama Eğitimi planlayın.","target":"temel"},
        {"code":"basic_overdue","severity":"danger","count":counts["basic_overdue"],"title":"Temel İSG eğitimi gecikmiş / eksik","instruction":"Önce kırmızı durumdaki çalışanları eğitime alın.","target":"yenileme"},
        {"code":"basic_due_soon","severity":"warning","count":counts["basic_due_soon"],"title":"Temel İSG yenilemesi yaklaşıyor","instruction":"Süresi dolmadan yenileme eğitimini planlayın.","target":"yenileme"},
        {"code":"basic_waiting","severity":"warning","count":counts["basic_waiting"],"title":"İlk temel eğitim bekliyor","instruction":"İşe başladıktan sonra en kısa sürede ve en geç üç ay içinde tamamlayın.","target":"temel"},
        {"code":"result_pending","severity":"warning","count":result_pending,"title":"Katılım / sonuç bekleyen eğitim","instruction":"Gerçek katılımı ve gerekiyorsa sınav puanlarını girip sonuçları kesinleştirin.","target":"kayitlar"},
        {"code":"planned_future","severity":"info","count":planned_future,"title":"Planlanmış yaklaşan eğitim","instruction":"Eğitim tarihi ve katılımcı listesini kontrol edin.","target":"kayitlar"},
    ]
    actions = [action for action in actions if action["count"] > 0]
    severity_order = {"danger":0,"warning":1,"info":2,"ok":3}
    actions.sort(key=lambda action:(severity_order.get(action["severity"],9), -action["count"]))
    row_order = {"danger":0,"warning":1,"neutral":2,"ok":3}
    rows.sort(key=lambda row:(min(row_order.get(row["work_start"]["tone"],9), row_order.get(row["basic"]["tone"],9)), row["full_name"] or ""))
    return {"enabled":dashboard_active(),"version":DASHBOARD_VERSION,"company_id":company_id,"today":today.isoformat(),"work_start_tracking_from":cutover.isoformat() if cutover else None,"summary":{"active_employees":len(employees),**counts,"result_pending":result_pending,"planned_future":planned_future},"actions":actions,"rows":rows,"safety":{"read_only":True,"automatic_training_completion":False,"historical_work_start_backfill_required":False}}
