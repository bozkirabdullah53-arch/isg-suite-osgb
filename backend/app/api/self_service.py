"""Feature-flagged, read-only çalışan self-servis özeti.

Bu uç mevcut çalışan, kullanıcı ve eğitim tablolarına ek kayıt yazmaz. Hesap
ile çalışan arasındaki ilişki yalnızca açık ``RemoteTrainingEmployeeAccess``
eşleştirmesinden okunur; ad-soyad tahmini veya çapraz firma araması yapılmaz.
İBYS ve MEDULA/e-Reçete kapsamı bu modülün dışındadır.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.api.company_access import ensure_company_access
from app.api.deps import get_current_user
from app.core.config import employee_self_service_active, remote_basic_ohs_training_active
from app.core.database import get_db
from app.models.entities import (
    Branch,
    Company,
    Employee,
    HealthRecord,
    Notification,
    PpeAssignment,
    TrainingParticipant,
    TrainingSession,
    User,
    UserRole,
)
from app.models.remote_training import (
    RemoteTrainingAssignment,
    RemoteTrainingEmployeeAccess,
    RemoteTrainingProgram,
)
from app.services.health_audit import append_health_access
from app.services.remote_training import strict_policy_active

router = APIRouter(prefix="/self-service", tags=["Çalışan Self Servis"])


def _iso(value: date | datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _assert_self_service_user(user: User) -> None:
    if not employee_self_service_active():
        # Rollout kapısı kapalıyken endpoint keşfedilebilirliği azaltılır.
        raise HTTPException(status_code=404, detail="Çalışan self-servis modülü etkin değil.")
    if user.role != UserRole.READ_ONLY:
        raise HTTPException(status_code=403, detail="Bu panel yalnızca çalışan hesabına açıktır.")


def _resolve_employee_scope(
    db: Session,
    user: User,
) -> tuple[RemoteTrainingEmployeeAccess, Company, Employee, Branch | None]:
    """Resolve the explicit user→employee link and re-check its tenant."""
    mapping = db.scalar(
        select(RemoteTrainingEmployeeAccess).where(
            RemoteTrainingEmployeeAccess.user_id == user.id,
            RemoteTrainingEmployeeAccess.is_active.is_(True),
        )
    )
    if not mapping:
        raise HTTPException(status_code=404, detail="Çalışan hesabı eşleştirmesi bulunamadı.")

    # Provisioned employee accounts are company-bound.  Requiring the same
    # binding here prevents a stale or incorrectly edited mapping from
    # widening access to another tenant.
    if not user.company_id or mapping.company_id != user.company_id:
        raise HTTPException(status_code=403, detail="Çalışan hesabı firma kapsamı dışında.")
    if mapping.osgb_id is not None and mapping.osgb_id != user.osgb_id:
        raise HTTPException(status_code=403, detail="Çalışan hesabı OSGB kapsamı dışında.")

    ensure_company_access(db, user, mapping.company_id)
    company = db.scalar(
        select(Company).where(
            Company.id == mapping.company_id,
            Company.is_active.is_(True),
        )
    )
    employee = db.scalar(
        select(Employee).where(
            Employee.id == mapping.employee_id,
            Employee.company_id == mapping.company_id,
            Employee.is_active.is_(True),
        )
    )
    if not company or not employee:
        raise HTTPException(status_code=404, detail="Aktif çalışan kaydı bulunamadı.")

    branch = db.get(Branch, employee.branch_id) if employee.branch_id else None
    if branch is not None and branch.company_id != company.id:
        # Eski/bozuk bir branch bağlantısı çalışan özetine taşınmaz.
        branch = None
    return mapping, company, employee, branch


def _legacy_training_summary(db: Session, company_id: int, employee_id: int) -> dict[str, Any]:
    rows = db.execute(
        select(TrainingSession, TrainingParticipant)
        .join(TrainingParticipant, TrainingParticipant.training_id == TrainingSession.id)
        .where(
            TrainingSession.company_id == company_id,
            TrainingSession.archived_at.is_(None),
            TrainingParticipant.employee_id == employee_id,
        )
        .order_by(TrainingSession.start_date.desc(), TrainingSession.id.desc())
        .limit(20)
    ).all()

    history: list[dict[str, Any]] = []
    for session, participant in rows:
        history.append(
            {
                "id": session.id,
                "title": session.title,
                "training_type": session.training_type,
                "start_date": _iso(session.start_date),
                "status": _enum_value(session.status),
                "attended": bool(participant.attended),
                "successful": participant.successful,
                "score": participant.score,
            }
        )
    return {
        "total": len(history),
        "completed": sum(1 for row in history if row["successful"] is True),
        "pending": sum(1 for row in history if row["successful"] is not True),
        "history": history,
    }


def _remote_training_summary(db: Session, company_id: int, employee_id: int) -> dict[str, Any]:
    if not remote_basic_ohs_training_active():
        return {"available": False, "total": 0, "completed": 0, "assignments": []}

    assignments = db.scalars(
        select(RemoteTrainingAssignment)
        .where(
            RemoteTrainingAssignment.company_id == company_id,
            RemoteTrainingAssignment.employee_id == employee_id,
            RemoteTrainingAssignment.status != "revoked",
        )
        .order_by(RemoteTrainingAssignment.assigned_at.desc(), RemoteTrainingAssignment.id.desc())
        .limit(20)
    ).all()
    program_ids = {int(row.program_id) for row in assignments}
    programs = {
        program.id: program
        for program in db.scalars(
            select(RemoteTrainingProgram).where(RemoteTrainingProgram.id.in_(program_ids))
        ).all()
    } if program_ids else {}

    visible: list[dict[str, Any]] = []
    for assignment in assignments:
        program = programs.get(assignment.program_id)
        if not program or program.status != "published":
            continue
        if str(getattr(program, "policy_mode", "legacy") or "legacy").lower() == "strict" and not strict_policy_active(program):
            continue
        visible.append(
            {
                "id": assignment.id,
                "title": program.title,
                "status": assignment.status,
                "due_date": _iso(assignment.due_date),
                "assigned_at": _iso(assignment.assigned_at),
                "completed_at": _iso(assignment.completed_at),
            }
        )
    return {
        "available": True,
        "total": len(visible),
        "completed": sum(1 for row in visible if row["status"] == "completed"),
        "assignments": visible,
    }


def _ppe_summary(db: Session, company_id: int, employee_id: int) -> dict[str, Any]:
    rows = db.scalars(
        select(PpeAssignment)
        .where(
            PpeAssignment.company_id == company_id,
            PpeAssignment.employee_id == employee_id,
            PpeAssignment.deleted_at.is_(None),
        )
        .order_by(PpeAssignment.delivery_date.desc(), PpeAssignment.id.desc())
        .limit(20)
    ).all()
    return {
        "total": len(rows),
        "items": [
            {
                "id": row.id,
                "category": row.category,
                "item_type": row.item_type,
                "quantity": row.quantity,
                "delivery_date": _iso(row.delivery_date),
                "expiry_date": _iso(row.expiry_date),
                "renewal_date": _iso(row.renewal_date),
                "status": row.status,
            }
            for row in rows
        ],
    }


def _notification_summary(db: Session, user_id: int, company_id: int) -> dict[str, Any]:
    # Company/global notifications are management work queues.  They may
    # contain annual-plan, risk, document or another employee's health data;
    # they must never appear in a worker's panel.  Only direct user-targeted
    # notifications are eligible, and the company binding is rechecked.
    notification_filters = [
        Notification.user_id == user_id,
        or_(Notification.company_id == company_id, Notification.company_id.is_(None)),
    ]
    is_completed = getattr(Notification, "is_completed", None)
    if is_completed is not None:
        notification_filters.insert(0, is_completed.is_(False))
    rows = db.scalars(
        select(Notification)
        .where(*notification_filters)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(10)
    ).all()
    hidden_types = {
        "annual_plan",
        "annual_eval",
        "annual_plan_item",
        "annual_plan_evaluation",
        "annual_plan_evaluation_item",
    }
    visible_rows = [
        row for row in rows
        if str(row.entity_type or "").strip().lower() not in hidden_types
        and "yıllık plan" not in str(row.title or "").lower()
        and "yıllık değerlendirme" not in str(row.title or "").lower()
    ]
    return {
        "unread": sum(1 for row in visible_rows if not row.is_read),
        "items": [
            {
                "id": row.id,
                "type": _enum_value(row.type),
                "title": row.title,
                "message": row.message,
                "entity_type": row.entity_type,
                "is_read": bool(row.is_read),
                "created_at": _iso(row.created_at),
            }
            for row in visible_rows
        ],
    }


def _health_summary(
    db: Session,
    *,
    user: User,
    company_id: int,
    employee_id: int,
    request: Request | None,
) -> dict[str, Any]:
    row = db.scalar(
        select(HealthRecord)
        .where(
            HealthRecord.company_id == company_id,
            HealthRecord.employee_id == employee_id,
            HealthRecord.deleted_at.is_(None),
        )
        .order_by(HealthRecord.examination_date.desc(), HealthRecord.id.desc())
        .limit(1)
    )
    if row is None:
        return {
            "has_record": False,
            "last_examination_date": None,
            "next_examination_date": None,
            "details_included": False,
        }

    # The employee receives only scheduling metadata.  Clinical outcome,
    # diagnosis, restrictions, reports and notes never enter this payload.
    append_health_access(
        db,
        actor=user,
        company_id=company_id,
        record_id=row.id,
        action="self_service_schedule_view",
        request=request,
        purpose="employee_self_service",
        metadata={"data_minimized": True},
    )
    return {
        "has_record": True,
        "last_examination_date": _iso(row.examination_date),
        "next_examination_date": _iso(row.next_examination_date),
        "details_included": False,
    }


def build_self_service_payload(
    db: Session,
    *,
    user: User,
    company: Company,
    employee: Employee,
    branch: Branch | None,
    request: Request | None = None,
) -> dict[str, Any]:
    return {
        "summary_version": "v1",
        "scope": {
            "company_id": company.id,
            "company_name": company.name,
            "branch_id": branch.id if branch else None,
            "branch_name": branch.name if branch else None,
            "employee_id": employee.id,
        },
        "employee": {
            "id": employee.id,
            "full_name": employee.full_name,
            "job_title": employee.job_title,
            "department": employee.department,
            "start_date": _iso(employee.start_date),
        },
        "training": {
            "classroom": _legacy_training_summary(db, company.id, employee.id),
            "remote": _remote_training_summary(db, company.id, employee.id),
        },
        "ppe": _ppe_summary(db, company.id, employee.id),
        "notifications": _notification_summary(db, user.id, company.id),
        "health": _health_summary(
            db,
            user=user,
            company_id=company.id,
            employee_id=employee.id,
            request=request,
        ),
        "privacy": {
            "data_minimized": True,
            "read_only": True,
            "cross_employee_data": False,
            "health_details_included": False,
            "restricted_documents_included": False,
        },
        "capabilities": {
            "can_read": True,
            "can_write": False,
            "can_upload": False,
        },
    }


@router.get("/me")
def get_my_self_service(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _assert_self_service_user(user)
    _, company, employee, branch = _resolve_employee_scope(db, user)
    payload = build_self_service_payload(
        db,
        user=user,
        company=company,
        employee=employee,
        branch=branch,
        request=request,
    )
    # Health access log is an expected append-only audit side effect of a
    # health schedule read; it does not alter business records.
    db.commit()
    return payload
