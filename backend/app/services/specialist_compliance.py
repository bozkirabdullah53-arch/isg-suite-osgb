"""İş güvenliği uzmanı odası için ek sorumluluk ve uygunluk kontrolleri.

Bu servis mevcut kayıtları yalnızca okur. Yeni tablo veya mevcut kayıt değişikliği
yapmaz; görev paneli ve uzman raporları için aynı, işyeri kapsamlı hesapları
paylaştırır. Sağlık kayıtları özellikle bu servisin dışında tutulur.
"""
from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    ChemicalProduct,
    Company,
    DocumentRecord,
    DrillRecord,
    EmergencyPlan,
    EmergencyTeam,
    EmergencyTeamAssignment,
    EmergencyTeamTraining,
    Employee,
    OhsCommitteeMeeting,
    OhsCommitteeMember,
    PeriodicControl,
    PpeAssignment,
    TrainingSession,
    TrainingStatus,
    WorkplaceMeasurement,
)
from app.models.training_nace import TrainingNaceSnapshot
from app.services import training_validity
from app.services.special_training_profiles import resolve_special_duration_hours


SPECIALIST_EXTENDED_CHECKS: list[dict[str, Any]] = [
    {
        "code": "training_compliance",
        "title": "NACE / çalışan eğitim uygunluğu",
        "legal": "6331 md.17 — çalışan eğitimi; seçilen NACE eğitim profili",
        "weight": 2,
    },
    {
        "code": "ppe_register",
        "title": "KKD zimmet ve yenileme takibi",
        "legal": "Kişisel Koruyucu Donanımların İşyerlerinde Kullanılması Hakkında Yönetmelik",
        "weight": 1,
    },
    {
        "code": "periodic_control",
        "title": "Periyodik kontrol sicili",
        "legal": "İş Ekipmanlarının Kullanımında Sağlık ve Güvenlik Şartları Yönetmeliği",
        "weight": 1,
    },
    {
        "code": "workplace_measurement",
        "title": "Ortam ölçüm takip kaydı",
        "legal": "İşyeri ortam ölçümleri ve risk değerlendirmesi takibi",
        "weight": 1,
    },
    {
        "code": "emergency_plan",
        "title": "Acil durum planı ve kroki",
        "legal": "İşyerlerinde Acil Durumlar Hakkında Yönetmelik",
        "weight": 1,
    },
    {
        "code": "emergency_team",
        "title": "Acil durum ekipleri",
        "legal": "İşyerlerinde Acil Durumlar Hakkında Yönetmelik",
        "weight": 1,
    },
    {
        "code": "drill",
        "title": "Tatbikat ve aksiyon takibi",
        "legal": "İşyerlerinde Acil Durumlar Hakkında Yönetmelik",
        "weight": 1,
    },
    {
        "code": "ohs_committee",
        "title": "İSG kurulu toplantı takibi",
        "legal": "İş Sağlığı ve Güvenliği Kurulları Hakkında Yönetmelik",
        "weight": 1,
    },
]


def _check(code: str, title: str, legal: str, weight: int, passed: bool, detail: str, metric: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": code,
        "title": title,
        "legal": legal,
        "weight": weight,
        "passed": bool(passed),
        "status": "ok" if passed else "critical",
        "detail": detail,
        "metric": metric,
    }


def _event(
    *,
    code: str,
    title: str,
    detail: str,
    due_date: date | None,
    kind: str,
) -> dict[str, Any]:
    return {
        "check_code": code,
        "title": title,
        "detail": detail,
        "due_date": due_date,
        "kind": kind,
    }


def _is_special_training(row: TrainingSession) -> bool:
    return bool(
        resolve_special_duration_hours(
            SimpleNamespace(
                training_type=row.training_type or "",
                title=row.title or "",
                notes=row.notes or "",
            )
        )
    )


def _normalise_nace(value: str | None) -> str:
    return "".join(ch for ch in str(value or "").strip() if ch.isdigit())


def _training_check(
    db: Session,
    company: Company,
    *,
    today: date,
    soon: date,
    year: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    employees = list(
        db.scalars(
            select(Employee).where(
                Employee.company_id == company.id,
                Employee.is_active.is_(True),
            )
        ).all()
    )
    if not employees:
        return (
            _check(
                "training_compliance",
                "NACE / çalışan eğitim uygunluğu",
                "6331 md.17 — çalışan eğitimi; seçilen NACE eğitim profili",
                2,
                True,
                "Aktif çalışan bulunmadığı için eğitim uygunluğu kapsamı oluşmadı.",
                {"total_employees": 0, "action_needed": 0},
            ),
            [],
        )

    sessions = list(
        db.scalars(
            select(TrainingSession)
            .options(selectinload(TrainingSession.participants))
            .where(
                TrainingSession.company_id == company.id,
                TrainingSession.status != TrainingStatus.CANCELLED,
                TrainingSession.start_date <= today,
            )
            .order_by(TrainingSession.end_date.desc(), TrainingSession.id.desc())
        ).unique().all()
    )
    snapshots = {
        row.training_id: row
        for row in db.scalars(
            select(TrainingNaceSnapshot).where(
                TrainingNaceSnapshot.company_id == company.id,
                TrainingNaceSnapshot.training_id.in_({s.id for s in sessions} or {-1}),
            )
        ).all()
    }
    company_nace = _normalise_nace(company.nace_code)
    nace_verified = 0
    nace_mismatch = 0
    duration_short = 0
    latest: dict[int, dict[str, Any]] = {}

    for session in sessions:
        snapshot = snapshots.get(session.id)
        if snapshot and snapshot.classification_status == "verified":
            nace_verified += 1
            if company_nace and _normalise_nace(snapshot.nace_code) != company_nace:
                nace_mismatch += 1
            required = snapshot.required_duration_hours
            if required and int(session.duration_hours or 0) < int(required):
                duration_short += 1
        # Özel profil eğitimleri ayrı uygunluk akışında değerlendirilir; temel
        # çalışan eğitimi statüsünü yanlışlıkla tamamlamasın.
        if _is_special_training(session) or session.status != TrainingStatus.COMPLETED:
            continue
        finished = session.end_date or session.start_date
        if not finished or finished > today:
            continue
        for participant in session.participants or []:
            if not participant.attended or participant.successful is False:
                continue
            current = latest.get(participant.employee_id)
            if current is None or finished > current["end"]:
                latest[participant.employee_id] = {
                    "end": finished,
                    "due": session.next_training_date,
                    "training_id": session.id,
                    "title": session.title,
                }

    events: list[dict[str, Any]] = []
    status_counts = {"never": 0, "expired": 0, "due_soon": 0, "ok": 0}
    for employee in employees:
        current = latest.get(employee.id)
        state = training_validity.evaluate_employee(
            hire_date=employee.start_date,
            last_training_end=current["end"] if current else None,
            next_due=current["due"] if current else None,
            today=today,
        )
        status = state.get("status") or "never"
        status_counts[status] = status_counts.get(status, 0) + 1
        if status == "never":
            events.append(
                _event(
                    code="training_compliance",
                    title=f"Eğitim kaydı eksik — {employee.full_name}",
                    detail="Aktif çalışan için tamamlanmış ve katılımı doğrulanmış temel eğitim bulunamadı.",
                    due_date=None,
                    kind="training_missing",
                )
            )
        elif status in ("expired", "due_soon"):
            due = current.get("due") if current else None
            if due and due <= soon:
                events.append(
                    _event(
                        code="training_compliance",
                        title=f"Eğitim yenileme — {employee.full_name}",
                        detail=state.get("message") or "Çalışan eğitimi yenilenmelidir.",
                        due_date=due,
                        kind="training_due",
                    )
                )

    action_needed = sum(status_counts.get(k, 0) for k in ("never", "expired", "due_soon"))
    nace_issue = bool(sessions and company_nace and (nace_verified == 0 or nace_mismatch > 0))
    passed = action_needed == 0 and not nace_issue and duration_short == 0
    detail = (
        f"{len(employees)} aktif çalışan: geçerli {status_counts.get('ok', 0)}, "
        f"işlem gereken {action_needed}; doğrulanmış NACE eğitimi {nace_verified}, "
        f"NACE uyumsuzluğu {nace_mismatch}, süre açığı {duration_short}."
    )
    if not sessions:
        detail += " Bu yıl tamamlanmış temel eğitim kaydı yok."
    return (
        _check(
            "training_compliance",
            "NACE / çalışan eğitim uygunluğu",
            "6331 md.17 — çalışan eğitimi; seçilen NACE eğitim profili",
            2,
            passed,
            detail,
            {
                "total_employees": len(employees),
                "status_counts": status_counts,
                "action_needed": action_needed,
                "nace_code": company.nace_code,
                "nace_verified": nace_verified,
                "nace_mismatch": nace_mismatch,
                "duration_short": duration_short,
                "training_count": len(sessions),
                "year": year,
            },
        ),
        events,
    )


def evaluate_extended_specialist_checks(
    db: Session,
    company: Company,
    *,
    today: date | None = None,
    soon: date | None = None,
    year: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Uzman odasına özel, sağlık dışı ek kontrolleri üretir."""
    now = today or date.today()
    approaching = soon or (now + timedelta(days=14))
    target_year = year or now.year
    checks: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []

    training, training_events = _training_check(
        db, company, today=now, soon=approaching, year=target_year
    )
    checks.append(training)
    events.extend(training_events)

    active_employees = db.scalar(
        select(func.count()).select_from(Employee).where(
            Employee.company_id == company.id,
            Employee.is_active.is_(True),
        )
    ) or 0
    ppe_rows = list(
        db.scalars(
            select(PpeAssignment).where(
                PpeAssignment.company_id == company.id,
                PpeAssignment.deleted_at.is_(None),
                PpeAssignment.status.notin_(("iade", "iptal", "returned", "cancelled")),
            )
        ).all()
    )
    ppe_due = 0
    for row in ppe_rows:
        due = row.renewal_date or row.expiry_date
        if due and due <= approaching:
            ppe_due += 1
            events.append(
                _event(
                    code="ppe_register",
                    title=f"KKD yenileme — {row.item_type}",
                    detail=f"Çalışan #{row.employee_id}; kayıt tarihi: {due}.",
                    due_date=due,
                    kind="ppe_due",
                )
            )
    ppe_passed = active_employees == 0 or bool(ppe_rows)
    checks.append(
        _check(
            "ppe_register",
            "KKD zimmet ve yenileme takibi",
            "Kişisel Koruyucu Donanımların İşyerlerinde Kullanılması Hakkında Yönetmelik",
            1,
            ppe_passed and ppe_due == 0,
            f"Aktif çalışan {active_employees}, aktif zimmet {len(ppe_rows)}, yaklaşan/geciken yenileme {ppe_due}.",
            {"active_employees": active_employees, "assignments": len(ppe_rows), "due": ppe_due},
        )
    )

    periodic = list(
        db.scalars(
            select(PeriodicControl).where(
                PeriodicControl.company_id == company.id,
                PeriodicControl.is_active.is_(True),
            )
        ).all()
    )
    periodic_due = 0
    for row in periodic:
        if row.next_due_date and row.next_due_date <= approaching:
            periodic_due += 1
            events.append(
                _event(
                    code="periodic_control",
                    title=f"Periyodik kontrol — {row.equipment_name}",
                    detail=f"{row.category}; termin: {row.next_due_date}.",
                    due_date=row.next_due_date,
                    kind="periodic_due",
                )
            )
    checks.append(
        _check(
            "periodic_control",
            "Periyodik kontrol sicili",
            "İş Ekipmanlarının Kullanımında Sağlık ve Güvenlik Şartları Yönetmeliği",
            1,
            bool(periodic) and periodic_due == 0,
            f"Aktif ekipman kaydı {len(periodic)}, yaklaşan/geciken kontrol {periodic_due}.",
            {"controls": len(periodic), "due": periodic_due},
        )
    )

    measurements = list(
        db.scalars(
            select(WorkplaceMeasurement).where(
                WorkplaceMeasurement.company_id == company.id,
                WorkplaceMeasurement.is_active.is_(True),
            )
        ).all()
    )
    measurement_due = 0
    for row in measurements:
        if row.next_due_date and row.next_due_date <= approaching:
            measurement_due += 1
            events.append(
                _event(
                    code="workplace_measurement",
                    title=f"Ortam ölçümü — {row.measurement_type}",
                    detail=f"{row.location or 'Lokasyon belirtilmemiş'}; termin: {row.next_due_date}.",
                    due_date=row.next_due_date,
                    kind="measurement_due",
                )
            )
    checks.append(
        _check(
            "workplace_measurement",
            "Ortam ölçüm takip kaydı",
            "İşyeri ortam ölçümleri ve risk değerlendirmesi takibi",
            1,
            bool(measurements) and measurement_due == 0,
            f"Aktif ölçüm kaydı {len(measurements)}, yaklaşan/geciken yenileme {measurement_due}.",
            {"measurements": len(measurements), "due": measurement_due},
        )
    )

    plans = list(
        db.scalars(
            select(EmergencyPlan).where(
                EmergencyPlan.company_id == company.id,
                EmergencyPlan.is_active.is_(True),
            )
        ).all()
    )
    plan_due = 0
    missing_kroki = 0
    for row in plans:
        if not row.kroki_storage_path and not row.kroki_file_name:
            missing_kroki += 1
        if row.next_review_date and row.next_review_date <= approaching:
            plan_due += 1
            events.append(
                _event(
                    code="emergency_plan",
                    title=f"Acil durum planı — {row.title}",
                    detail=f"Revizyon {row.revision_no}; gözden geçirme: {row.next_review_date}.",
                    due_date=row.next_review_date,
                    kind="emergency_plan_due",
                )
            )
    checks.append(
        _check(
            "emergency_plan",
            "Acil durum planı ve kroki",
            "İşyerlerinde Acil Durumlar Hakkında Yönetmelik",
            1,
            bool(plans) and missing_kroki == 0 and plan_due == 0,
            f"Aktif plan {len(plans)}, krokisi eksik {missing_kroki}, yaklaşan/geciken gözden geçirme {plan_due}.",
            {"plans": len(plans), "missing_kroki": missing_kroki, "due": plan_due},
        )
    )

    teams = list(
        db.scalars(
            select(EmergencyTeam).where(
                EmergencyTeam.company_id == company.id,
                EmergencyTeam.is_active.is_(True),
            )
        ).all()
    )
    team_ids = [team.id for team in teams]
    team_counts: dict[int, int] = {}
    if team_ids:
        rows = db.execute(
            select(EmergencyTeamAssignment.team_id, func.count(EmergencyTeamAssignment.id))
            .where(
                EmergencyTeamAssignment.company_id == company.id,
                EmergencyTeamAssignment.team_id.in_(team_ids),
                EmergencyTeamAssignment.is_active.is_(True),
            )
            .group_by(EmergencyTeamAssignment.team_id)
        ).all()
        team_counts = {int(team_id): int(count) for team_id, count in rows}
    insufficient = sum(1 for team in teams if team_counts.get(team.id, 0) < int(team.min_members or 0))
    team_training_due = 0
    if team_ids:
        team_training_rows = list(
            db.scalars(
                select(EmergencyTeamTraining)
                .join(EmergencyTeamAssignment, EmergencyTeamTraining.assignment_id == EmergencyTeamAssignment.id)
                .where(EmergencyTeamAssignment.company_id == company.id)
            ).all()
        )
        for row in team_training_rows:
            due = row.valid_until or row.refresh_date or row.first_aid_end
            if due and due <= approaching:
                team_training_due += 1
                events.append(
                    _event(
                        code="emergency_team",
                        title="Acil ekip sertifikası",
                        detail=f"Ekip üyesi eğitim/sertifika termin: {due}.",
                        due_date=due,
                        kind="emergency_team_due",
                    )
                )
    checks.append(
        _check(
            "emergency_team",
            "Acil durum ekipleri",
            "İşyerlerinde Acil Durumlar Hakkında Yönetmelik",
            1,
            bool(teams) and insufficient == 0 and team_training_due == 0,
            f"Aktif ekip {len(teams)}, asgari üye açığı {insufficient}, sertifika terminleri {team_training_due}.",
            {"teams": len(teams), "insufficient": insufficient, "training_due": team_training_due},
        )
    )

    drills = list(
        db.scalars(
            select(DrillRecord).where(
                DrillRecord.company_id == company.id,
                DrillRecord.is_active.is_(True),
            ).order_by(DrillRecord.drill_date.desc(), DrillRecord.id.desc())
        ).all()
    )
    latest_drill = drills[0] if drills else None
    drill_due = None
    if latest_drill and latest_drill.drill_date:
        drill_due = latest_drill.drill_date + timedelta(days=365)
        if drill_due <= approaching:
            events.append(
                _event(
                    code="drill",
                    title="Tatbikat yenileme takibi",
                    detail=f"Son tatbikat {latest_drill.drill_date}; takip tarihi {drill_due}.",
                    due_date=drill_due,
                    kind="drill_due",
                )
            )
    checks.append(
        _check(
            "drill",
            "Tatbikat ve aksiyon takibi",
            "İşyerlerinde Acil Durumlar Hakkında Yönetmelik",
            1,
            bool(latest_drill) and not (drill_due and drill_due <= approaching),
            f"Aktif tatbikat {len(drills)}, son tarih {latest_drill.drill_date if latest_drill else '—'}.",
            {"drills": len(drills), "latest_date": latest_drill.drill_date.isoformat() if latest_drill and latest_drill.drill_date else None, "due": drill_due.isoformat() if drill_due else None},
        )
    )

    member_count = db.scalar(
        select(func.count()).select_from(OhsCommitteeMember).where(
            OhsCommitteeMember.company_id == company.id,
            OhsCommitteeMember.is_active.is_(True),
        )
    ) or 0
    meetings = list(
        db.scalars(
            select(OhsCommitteeMeeting).where(
                OhsCommitteeMeeting.company_id == company.id,
                OhsCommitteeMeeting.is_active.is_(True),
            ).order_by(OhsCommitteeMeeting.meeting_date.desc(), OhsCommitteeMeeting.id.desc())
        ).all()
    )
    committee_due = None
    if meetings:
        committee_due = meetings[0].next_meeting_date
        if committee_due and committee_due <= approaching:
            events.append(
                _event(
                    code="ohs_committee",
                    title="İSG kurulu toplantısı",
                    detail=f"Bir sonraki toplantı: {committee_due}.",
                    due_date=committee_due,
                    kind="committee_due",
                )
            )
    checks.append(
        _check(
            "ohs_committee",
            "İSG kurulu toplantı takibi",
            "İş Sağlığı ve Güvenliği Kurulları Hakkında Yönetmelik",
            1,
            member_count > 0 and bool(meetings) and not (committee_due and committee_due <= approaching),
            f"Aktif kurul üyesi {member_count}, toplantı kaydı {len(meetings)}, yaklaşan toplantı {committee_due or '—'}.",
            {"members": member_count, "meetings": len(meetings), "next_meeting": committee_due.isoformat() if committee_due else None},
        )
    )

    # Aşağıdaki sorgu gelecekte rapor merkezinde kullanılacak belge kapsama
    # göstergesini de hesaplar; sağlık belgesi içeriği okunmaz.
    active_documents = db.scalar(
        select(func.count()).select_from(DocumentRecord).where(
            DocumentRecord.company_id == company.id,
            DocumentRecord.is_active.is_(True),
        )
    ) or 0
    active_chemicals = db.scalar(
        select(func.count()).select_from(ChemicalProduct).where(
            ChemicalProduct.company_id == company.id,
            ChemicalProduct.is_active.is_(True),
        )
    ) or 0
    for check in checks:
        check.setdefault("metric", {})
        check["metric"].update({"active_documents": active_documents, "active_chemicals": active_chemicals})

    return checks, events


def build_specialist_report_snapshot(db: Session, company_ids: list[int]) -> dict[str, Any]:
    """Rapor merkezi için sağlık dışı, atanmış işyeri kapsamlı özet."""
    today = date.today()
    soon = today + timedelta(days=14)
    companies = list(
        db.scalars(
            select(Company).where(Company.id.in_(company_ids), Company.is_active.is_(True)).order_by(Company.name)
        ).all()
    )
    rows: list[dict[str, Any]] = []
    all_events: list[dict[str, Any]] = []
    totals = {
        "workplaces": len(companies),
        "employees": 0,
        "open_risks": 0,
        "open_incidents": 0,
        "active_ppe": 0,
        "periodic_controls": 0,
        "measurements": 0,
        "emergency_plans": 0,
        "emergency_teams": 0,
        "drills": 0,
        "committee_meetings": 0,
        "overdue_or_due": 0,
    }
    # Import locally to keep this service independent from the shared oversight
    # evaluator and to avoid exposing clinical counts.
    from app.models.entities import IncidentEvent, RiskAssessment

    for company in companies:
        checks, events = evaluate_extended_specialist_checks(
            db, company, today=today, soon=soon, year=today.year
        )
        employee_count = db.scalar(
            select(func.count()).select_from(Employee).where(
                Employee.company_id == company.id,
                Employee.is_active.is_(True),
            )
        ) or 0
        open_risks = db.scalar(
            select(func.count()).select_from(RiskAssessment).where(
                RiskAssessment.company_id == company.id,
                RiskAssessment.status == "Açık",
            )
        ) or 0
        open_incidents = db.scalar(
            select(func.count()).select_from(IncidentEvent).where(
                IncidentEvent.company_id == company.id,
                IncidentEvent.status.in_(("Aktif", "Açık", "open", "in_progress")),
            )
        ) or 0
        metric_by_code = {c["code"]: c.get("metric") or {} for c in checks}
        due_events = [
            e for e in events
            if e.get("due_date") is not None and e["due_date"] <= soon
        ]
        state = "critical" if any(not c.get("passed") for c in checks) else "ok"
        rows.append(
            {
                "company_id": company.id,
                "company_name": company.name,
                "nace_code": company.nace_code,
                "hazard_class": company.hazard_class,
                "state": state,
                "open_risks": open_risks,
                "open_incidents": open_incidents,
                "employees": employee_count,
                "checks_total": len(checks),
                "checks_failed": sum(1 for c in checks if not c.get("passed")),
                "due_count": len(due_events),
                "checks": checks,
            }
        )
        for event in events:
            all_events.append({"company_id": company.id, "company_name": company.name, **event})
        totals["employees"] += employee_count
        totals["open_risks"] += open_risks
        totals["open_incidents"] += open_incidents
        totals["active_ppe"] += int(metric_by_code.get("ppe_register", {}).get("assignments") or 0)
        totals["periodic_controls"] += int(metric_by_code.get("periodic_control", {}).get("controls") or 0)
        totals["measurements"] += int(metric_by_code.get("workplace_measurement", {}).get("measurements") or 0)
        totals["emergency_plans"] += int(metric_by_code.get("emergency_plan", {}).get("plans") or 0)
        totals["emergency_teams"] += int(metric_by_code.get("emergency_team", {}).get("teams") or 0)
        totals["drills"] += int(metric_by_code.get("drill", {}).get("drills") or 0)
        totals["committee_meetings"] += int(metric_by_code.get("ohs_committee", {}).get("meetings") or 0)
        totals["overdue_or_due"] += len(due_events)

    all_events.sort(key=lambda e: (e.get("due_date") or date.max, e.get("company_name") or ""))
    return {
        "generated_at": today.isoformat(),
        "period": {"today": today.isoformat(), "approaching_days": 14},
        "totals": totals,
        "companies": rows,
        "events": [
            {**event, "due_date": event["due_date"].isoformat() if event.get("due_date") else None}
            for event in all_events[:200]
        ],
    }
