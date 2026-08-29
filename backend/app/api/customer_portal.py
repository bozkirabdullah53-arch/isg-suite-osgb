"""Read-only customer portal summary with tenant-scoped, minimized data."""
from __future__ import annotations

from datetime import date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.company_access import ensure_company_access
from app.api.deps import require_roles
from app.core.database import get_db
from app.models.entities import Employee, HealthRecord, PpeAssignment, RiskAssessment, RiskDof, TrainingParticipant, TrainingSession, User, UserRole
from app.models.field_inspection import FieldInspection
from app.models.work_permit import WorkPermit

router = APIRouter(prefix="/customer-portal", tags=["Müşteri Portalı"])
PORTAL_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)


@router.get("/{company_id}/summary")
def company_summary(company_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*PORTAL_ROLES))):
    ensure_company_access(db, user, company_id)
    today = date.today()
    horizon = today + timedelta(days=30)
    employee_count = db.scalar(select(func.count()).select_from(Employee).where(Employee.company_id == company_id, Employee.is_active.is_(True))) or 0
    open_risks = db.scalar(select(func.count()).select_from(RiskAssessment).where(RiskAssessment.company_id == company_id, RiskAssessment.status == "Açık")) or 0
    open_dofs = db.scalar(select(func.count()).select_from(RiskDof).join(RiskAssessment).where(RiskAssessment.company_id == company_id, RiskDof.is_completed.is_(False))) or 0
    overdue_dofs = db.scalar(select(func.count()).select_from(RiskDof).join(RiskAssessment).where(RiskAssessment.company_id == company_id, RiskDof.is_completed.is_(False), RiskDof.term_date < today)) or 0
    upcoming_health = db.scalar(select(func.count()).select_from(HealthRecord).where(HealthRecord.company_id == company_id, HealthRecord.deleted_at.is_(None), HealthRecord.next_examination_date >= today, HealthRecord.next_examination_date <= horizon)) or 0
    training_total = db.scalar(select(func.count()).select_from(TrainingParticipant).join(TrainingSession, TrainingParticipant.training_id == TrainingSession.id).where(TrainingSession.company_id == company_id, TrainingSession.archived_at.is_(None))) or 0
    training_completed = db.scalar(select(func.count()).select_from(TrainingParticipant).join(TrainingSession, TrainingParticipant.training_id == TrainingSession.id).where(TrainingSession.company_id == company_id, TrainingSession.archived_at.is_(None), TrainingParticipant.successful.is_(True))) or 0
    ppe_count = db.scalar(select(func.count()).select_from(PpeAssignment).where(PpeAssignment.company_id == company_id, PpeAssignment.deleted_at.is_(None))) or 0
    inspections = db.scalar(select(func.count()).select_from(FieldInspection).where(FieldInspection.company_id == company_id, FieldInspection.deleted_at.is_(None))) or 0
    active_permits = db.scalar(select(func.count()).select_from(WorkPermit).where(WorkPermit.company_id == company_id, WorkPermit.status == "active")) or 0
    return {"company_id": company_id, "as_of": today.isoformat(), "scope": {"tenant_checked": True, "company_id": company_id, "health_details_included": False, "employee_details_included": False}, "kpis": {"employee_count": employee_count, "open_risks": open_risks, "open_dofs": open_dofs, "overdue_dofs": overdue_dofs, "upcoming_health_30d": upcoming_health, "training_total": training_total, "training_completed": training_completed, "training_completion_rate": round(training_completed * 100 / training_total, 1) if training_total else 0, "ppe_records": ppe_count, "field_inspections": inspections, "active_work_permits": active_permits}}
