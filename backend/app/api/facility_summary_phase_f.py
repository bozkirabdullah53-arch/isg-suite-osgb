"""FAZ F — read-only facility compliance summary across existing bounded contexts."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.company_access import ensure_company_access
from app.api.deps import require_roles
from app.core.database import get_db
from app.models.contractor import ContractorCompany, ContractorDocument, ContractorWorker
from app.models.entities import (
    AssignmentStatus,
    Company,
    Employee,
    HealthRecord,
    PeriodicControl,
    User,
    UserRole,
    WorkplaceAssignment,
)
from app.models.field_inspection import FieldInspection, FieldInspectionAction
from app.models.work_permit import WorkPermit
from app.services.action_projection import list_company_action_projection
from app.services.capacity_engine import (
    NORMAL_FULL_TIME_MONTHLY_MINUTES,
    _capacity_status,
    compute_company_service_requirements,
    count_active_employees,
)
from app.services.control_tower import build_control_tower
from app.services.health_audit import append_health_access

router = APIRouter(prefix="/facility-compliance-summary", tags=["Tesis Uygunluk Özeti"])
READ_ROLES = (
    UserRole.GLOBAL_ADMIN,
    UserRole.COMPANY_ADMIN,
    UserRole.SAFETY_SPECIALIST,
    UserRole.WORKPLACE_PHYSICIAN,
    UserRole.OTHER_HEALTH_PERSONNEL,
)
HEALTH_QUEUE_ROLES = (UserRole.WORKPLACE_PHYSICIAN, UserRole.OTHER_HEALTH_PERSONNEL)


def _open_actions_stmt(company_id: int):
    return select(FieldInspectionAction).join(
        FieldInspection, FieldInspection.id == FieldInspectionAction.inspection_id
    ).where(
        FieldInspectionAction.company_id == company_id,
        FieldInspectionAction.status.not_in(("completed", "cancelled")),
        FieldInspection.deleted_at.is_(None),
    )


def _action_is_closed(status: object) -> bool:
    return str(status or "").strip().casefold() in {
        "completed",
        "closed",
        "cancelled",
        "tamamlandı",
        "tamamlandi",
        "kapalı",
        "kapali",
        "iptal",
    }


def _company_capacity_summary(db: Session, company: Company) -> dict:
    """Selected-company-only capacity signal using the existing legal rule engine."""
    employees = list(
        db.scalars(
            select(Employee).where(
                Employee.company_id == company.id,
                Employee.is_active.is_(True),
            )
        ).all()
    )
    requirements = compute_company_service_requirements(company, count_active_employees(employees))
    assignments = list(
        db.scalars(
            select(WorkplaceAssignment).where(
                WorkplaceAssignment.company_id == company.id,
                WorkplaceAssignment.status == AssignmentStatus.ACTIVE,
            )
        ).all()
    )

    critical = 0
    warning = 0
    remaining = 0
    professional_ids: set[int] = set()
    for assignment in assignments:
        role = assignment.professional_type.value if assignment.professional_type else "safety_specialist"
        target = int((requirements.get("roles", {}).get(role) or {}).get("required_minutes", 0) or 0)
        actual = max(0, int(assignment.actual_minutes_monthly or 0))
        status = _capacity_status(target, actual)
        critical += int(status == "critical")
        warning += int(status == "warning")
        remaining += max(target - actual, 0)
        professional_ids.add(assignment.professional_id)

    overloaded = 0
    if professional_ids:
        load_rows = list(
            db.scalars(
                select(WorkplaceAssignment).where(
                    WorkplaceAssignment.professional_id.in_(professional_ids),
                    WorkplaceAssignment.status == AssignmentStatus.ACTIVE,
                )
            ).all()
        )
        planned_by_professional: dict[int, int] = {}
        for row in load_rows:
            planned_by_professional[row.professional_id] = (
                planned_by_professional.get(row.professional_id, 0)
                + max(0, int(row.planned_minutes_monthly or 0))
            )
        overloaded = sum(
            1 for value in planned_by_professional.values()
            if value > NORMAL_FULL_TIME_MONTHLY_MINUTES
        )

    return {
        "assignments": len(assignments),
        "critical_assignments": critical,
        "warning_assignments": warning,
        "remaining_required_minutes": remaining,
        "overloaded_professionals": overloaded,
        "normal_monthly_capacity_minutes": NORMAL_FULL_TIME_MONTHLY_MINUTES,
        "hazard_known": bool(requirements.get("hazard_known")),
        "hazard_warning": requirements.get("hazard_warning"),
    }


@router.get("")
def facility_summary(company_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    ensure_company_access(db, user, company_id)
    company = db.get(Company, company_id)
    if not company:
        return {"company_id": company_id, "company_name": None, "read_only": True, "missing": True}
    today = date.today()
    soon = today + timedelta(days=30)

    contractors = db.scalars(select(ContractorCompany).where(ContractorCompany.company_id == company_id, ContractorCompany.is_active.is_(True))).all()
    contractor_ids = [row.id for row in contractors]
    workers = int(db.scalar(select(func.count()).select_from(ContractorWorker).where(ContractorWorker.contractor_id.in_(contractor_ids), ContractorWorker.is_active.is_(True))) or 0) if contractor_ids else 0
    expired_contracts = sum(1 for row in contractors if row.contract_end and row.contract_end < today)
    expired_docs = int(db.scalar(select(func.count()).select_from(ContractorDocument).where(ContractorDocument.contractor_id.in_(contractor_ids), ContractorDocument.is_active.is_(True), ContractorDocument.valid_until.is_not(None), ContractorDocument.valid_until < today)) or 0) if contractor_ids else 0

    permits = db.scalars(select(WorkPermit).where(WorkPermit.company_id == company_id)).all()
    ptw_attention = sum(1 for row in permits if row.status in {"pending_approval", "active", "suspended", "expired"})

    periodic = db.scalars(select(PeriodicControl).where(PeriodicControl.company_id == company_id, PeriodicControl.is_active.is_(True))).all()
    periodic_overdue = sum(1 for row in periodic if row.next_due_date and row.next_due_date < today)
    periodic_due_soon = sum(1 for row in periodic if row.next_due_date and today <= row.next_due_date <= soon)
    periodic_unset = sum(1 for row in periodic if not row.next_due_date)

    inspections = db.scalars(select(FieldInspection).where(FieldInspection.company_id == company_id, FieldInspection.deleted_at.is_(None))).all()
    field_open_actions = db.scalars(_open_actions_stmt(company_id)).all()

    unified_actions = list_company_action_projection(db, company_ids=[company_id])
    open_actions = [row for row in unified_actions if not _action_is_closed(row.get("status"))]
    overdue_actions = sum(
        1
        for row in open_actions
        if row.get("term") and row["term"] < today.isoformat()
    )

    contractor_metrics = {
        "active": len(contractors),
        "active_workers": workers,
        "expired_contracts": expired_contracts,
        "expired_documents": expired_docs,
    }
    ptw_metrics = {
        "total": len(permits),
        "active": sum(1 for row in permits if row.status == "active"),
        "pending": sum(1 for row in permits if row.status == "pending_approval"),
        "closed": sum(1 for row in permits if row.status == "closed"),
        "attention": ptw_attention,
    }
    periodic_metrics = {
        "total": len(periodic),
        "overdue": periodic_overdue,
        "due_soon": periodic_due_soon,
        "due_date_missing": periodic_unset,
    }
    action_metrics = {
        "open": len(open_actions),
        "overdue": overdue_actions,
        "sources": {
            "risk": sum(1 for row in open_actions if row.get("source") == "Risk"),
            "incident": sum(1 for row in open_actions if row.get("source") == "Olay"),
            "field": sum(1 for row in open_actions if row.get("source") == "Saha"),
        },
    }
    capacity_metrics = _company_capacity_summary(db, company)
    control_tower = build_control_tower(
        contractors=contractor_metrics,
        ptw=ptw_metrics,
        periodic=periodic_metrics,
        actions=action_metrics,
        capacity=capacity_metrics,
    )

    attention = sum(item["count"] for item in control_tower["today_attention"])
    return {
        "company_id": company_id,
        "company_name": company.name,
        "read_only": True,
        "attention_count": attention,
        "compliance_score": control_tower["score"],
        "compliance_band": control_tower["band"],
        "control_tower": control_tower,
        "contractors": contractor_metrics,
        "ptw": ptw_metrics,
        "periodic": periodic_metrics,
        "capacity": capacity_metrics,
        "actions": action_metrics,
        "inspections": {
            "total": len(inspections),
            "approved": sum(1 for row in inspections if row.status == "approved"),
            "open_actions": len(field_open_actions),
            "overdue_actions": sum(1 for row in field_open_actions if row.term_date and row.term_date < today),
        },
        "privacy": {
            "health_in_general_score": False,
            "health_queue_role_protected": True,
        },
    }


@router.get("/health-ops")
def health_operations_queue(
    request: Request,
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*HEALTH_QUEUE_ROLES)),
):
    """Role-protected, data-minimized clinic work queue.

    Only scheduling metadata is returned. Diagnosis, fitness decision,
    restrictions, reports and confidential notes are never serialized here.
    """
    ensure_company_access(db, user, company_id)
    today = date.today()
    soon = today + timedelta(days=30)
    rows = list(
        db.scalars(
            select(HealthRecord)
            .where(
                HealthRecord.company_id == company_id,
                HealthRecord.deleted_at.is_(None),
            )
            .order_by(HealthRecord.employee_id, HealthRecord.examination_date.desc(), HealthRecord.id.desc())
            .limit(1000)
        ).all()
    )

    latest_by_employee: dict[int, HealthRecord] = {}
    for row in rows:
        latest_by_employee.setdefault(row.employee_id, row)

    employee_ids = set(latest_by_employee)
    employees = {
        employee.id: employee
        for employee in db.scalars(
            select(Employee).where(
                Employee.company_id == company_id,
                Employee.id.in_(employee_ids or {0}),
                Employee.is_active.is_(True),
            )
        ).all()
    }

    queue = []
    for employee_id, row in latest_by_employee.items():
        employee = employees.get(employee_id)
        if not employee:
            continue
        next_exam = row.next_examination_date
        if next_exam and next_exam < today:
            status, severity = "overdue", "critical"
        elif next_exam and next_exam <= soon:
            status, severity = "due_soon", "high"
        elif next_exam is None:
            status, severity = "unscheduled", "medium"
        else:
            continue
        queue.append({
            "record_id": row.id,
            "employee_id": employee_id,
            "employee_name": employee.full_name,
            "last_examination_date": row.examination_date.isoformat() if row.examination_date else None,
            "next_examination_date": next_exam.isoformat() if next_exam else None,
            "status": status,
            "severity": severity,
        })
        append_health_access(
            db,
            actor=user,
            company_id=company_id,
            record_id=row.id,
            action="health_operations_queue_view",
            request=request,
            purpose="health_operations_queue",
            metadata={"data_minimized": True, "scheduling_only": True},
        )

    rank = {"critical": 0, "high": 1, "medium": 2}
    queue.sort(key=lambda item: (rank[item["severity"]], item["next_examination_date"] or "9999-12-31", item["employee_name"]))
    db.commit()
    return {
        "company_id": company_id,
        "read_only": True,
        "data_minimized": True,
        "clinical_details_included": False,
        "counts": {
            "total_attention": len(queue),
            "overdue": sum(1 for item in queue if item["status"] == "overdue"),
            "due_soon": sum(1 for item in queue if item["status"] == "due_soon"),
            "unscheduled": sum(1 for item in queue if item["status"] == "unscheduled"),
        },
        "queue": queue[:100],
    }
