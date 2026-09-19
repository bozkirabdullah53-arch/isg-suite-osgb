"""İşyeri paneli: sayfalama sınırlarından bağımsız ve firmaya bağlı toplamlar."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.company_access import ensure_company_access
from app.api.deps import get_current_user, is_workplace_operations_account
from app.core.database import get_db
from app.models.entities import (
    ChemicalProduct, Company, Employee, IncidentDof, IncidentEvent,
    PeriodicControl, PpeAssignment, RiskAssessment, RiskDof, DrillRecord, User,
    WorkplaceMeasurement,
)

router = APIRouter(prefix="/workplace-portal", tags=["İşyeri Paneli"])


@router.get("/summary")
def workplace_summary(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not is_workplace_operations_account(user):
        raise HTTPException(403, "Bu ekran işyeri hesabına aittir.")
    own_id = int(user.company_id)
    if company_id is not None and company_id != own_id:
        raise HTTPException(403, "Yalnız kendi işyerinizin kayıtlarını görebilirsiniz.")
    ensure_company_access(db, user, own_id)
    company = db.get(Company, own_id)
    if company is None:
        raise HTTPException(404, "İşyeri bulunamadı.")

    def total(model, *conditions):
        return int(db.scalar(
            select(func.count()).select_from(model).where(model.company_id == own_id, *conditions)
        ) or 0)

    incident_dofs = db.scalar(
        select(func.count()).select_from(IncidentDof)
        .join(IncidentEvent, IncidentDof.incident_id == IncidentEvent.id)
        .where(IncidentEvent.company_id == own_id)
    ) or 0
    risk_dofs = db.scalar(
        select(func.count()).select_from(RiskDof)
        .join(RiskAssessment, RiskDof.risk_id == RiskAssessment.id)
        .where(RiskAssessment.company_id == own_id)
    ) or 0
    return {
        "company_id": own_id,
        "company_name": company.name,
        "counts": {
            "employees": total(Employee),
            "ppe": total(PpeAssignment, PpeAssignment.deleted_at.is_(None)),
            "sds": total(ChemicalProduct, ChemicalProduct.is_active.is_(True)),
            "periodic": total(PeriodicControl, PeriodicControl.is_active.is_(True)),
            "measurements": total(WorkplaceMeasurement, WorkplaceMeasurement.is_active.is_(True)),
            "nearMiss": total(IncidentEvent, IncidentEvent.event_type == "ramak_kala"),
            "accidents": total(IncidentEvent, IncidentEvent.event_type == "is_kazasi"),
            "capa": int(incident_dofs + risk_dofs),
            "drills": total(DrillRecord, DrillRecord.is_active.is_(True)),
        },
    }
