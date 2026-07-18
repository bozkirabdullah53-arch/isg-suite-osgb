from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.entities import (
    AnnualPlanItem,
    AnnualPlanStatus,
    DocumentRecord,
    Employee,
    HealthRecord,
    IsgModule,
    IsgRecord,
    RiskAssessment,
    User,
    UserRole,
)

router = APIRouter(prefix="/reports", tags=["Raporlama"])


@router.get("/summary")
def report_summary(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    effective_company = company_id if user.role == UserRole.GLOBAL_ADMIN else user.company_id
    filters = [] if not effective_company else [Employee.company_id == effective_company]
    employee_count = db.scalar(select(func.count()).select_from(Employee).where(*filters)) or 0

    isg_filter = [] if not effective_company else [IsgRecord.company_id == effective_company]
    risk_filter = [] if not effective_company else [RiskAssessment.company_id == effective_company]
    open_risks = db.scalar(select(func.count()).select_from(RiskAssessment).where(
        RiskAssessment.status == "Açık",
        *risk_filter,
    )) or 0
    accidents = db.scalar(select(func.count()).select_from(IsgRecord).where(
        IsgRecord.module == IsgModule.ACCIDENT,
        *isg_filter,
    )) or 0

    health_filter = [] if not effective_company else [HealthRecord.company_id == effective_company]
    health_records = db.scalar(select(func.count()).select_from(HealthRecord).where(*health_filter)) or 0

    doc_filter = [] if not effective_company else [DocumentRecord.company_id == effective_company]
    expired_documents = db.scalar(select(func.count()).select_from(DocumentRecord).where(
        DocumentRecord.valid_until.is_not(None),
        DocumentRecord.valid_until < date.today(),
        *doc_filter,
    )) or 0

    plan_filter = [] if not effective_company else [AnnualPlanItem.company_id == effective_company]
    delayed_plans = db.scalar(select(func.count()).select_from(AnnualPlanItem).where(
        AnnualPlanItem.status == AnnualPlanStatus.DELAYED,
        *plan_filter,
    )) or 0

    return {
        "employee_count": employee_count,
        "open_risks": open_risks,
        "accident_count": accidents,
        "health_record_count": health_records,
        "expired_document_count": expired_documents,
        "delayed_plan_count": delayed_plans,
    }
