from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.entities import (
    Branch,
    Company,
    Employee,
    IncidentDof,
    RiskAssessment,
    RiskDof,
    User,
    UserRole,
)

router = APIRouter(prefix="/dashboard", tags=["Panel"])


@router.get("/summary")
def summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role == UserRole.GLOBAL_ADMIN:
        cc = db.scalar(select(func.count()).select_from(Company).where(Company.is_active.is_(True))) or 0
        bc = db.scalar(select(func.count()).select_from(Branch).where(Branch.is_active.is_(True))) or 0
        ec = db.scalar(select(func.count()).select_from(Employee).where(Employee.is_active.is_(True))) or 0
        uc = db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True))) or 0
        open_risks = db.scalar(
            select(func.count()).select_from(RiskAssessment).where(RiskAssessment.status == "Açık")
        ) or 0
        open_capa = (
            db.scalar(
                select(func.count()).select_from(IncidentDof).where(IncidentDof.status != "Tamamlandı")
            )
            or 0
        ) + (
            db.scalar(
                select(func.count()).select_from(RiskDof).where(RiskDof.is_completed.is_(False))
            )
            or 0
        )
    else:
        cid = user.company_id
        cc = 1 if cid else 0
        bc = (
            db.scalar(
                select(func.count()).select_from(Branch).where(Branch.company_id == cid, Branch.is_active.is_(True))
            )
            or 0
        )
        ec = (
            db.scalar(
                select(func.count())
                .select_from(Employee)
                .where(Employee.company_id == cid, Employee.is_active.is_(True))
            )
            or 0
        )
        uc = (
            db.scalar(
                select(func.count()).select_from(User).where(User.company_id == cid, User.is_active.is_(True))
            )
            or 0
        )
        open_risks = 0
        open_capa = 0
        if cid:
            open_risks = (
                db.scalar(
                    select(func.count())
                    .select_from(RiskAssessment)
                    .where(RiskAssessment.company_id == cid, RiskAssessment.status == "Açık")
                )
                or 0
            )
            open_capa = (
                db.scalar(
                    select(func.count())
                    .select_from(RiskDof)
                    .where(
                        RiskDof.is_completed.is_(False),
                        RiskDof.risk_id.in_(
                            select(RiskAssessment.id).where(RiskAssessment.company_id == cid)
                        ),
                    )
                )
                or 0
            )

    return {
        "company_count": cc,
        "branch_count": bc,
        "employee_count": ec,
        "user_count": uc,
        "open_risks": open_risks,
        "open_capa": open_capa,
        "role": user.role.value,
    }
