from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.company_access import companies_query_for_user
from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import (
    AnnualPlanItem,
    AuditLog,
    Branch,
    Company,
    CompanySubscription,
    DocumentRecord,
    Employee,
    FinanceTransaction,
    HealthRecord,
    IncidentDof,
    IncidentEvent,
    IncidentRootCause,
    IsgRecord,
    Notification,
    PpeAssignment,
    PpeAssignmentPhoto,
    RiskAssessment,
    RiskDof,
    RiskMedia,
    ServiceContract,
    ServiceVisit,
    TrainingParticipant,
    TrainingSession,
    User,
    UserRole,
    WorkplaceAssignment,
    WorkplaceDepartment,
)
from app.schemas.company import CompanyCreate, CompanyResponse, CompanyUpdate

router = APIRouter(prefix="/companies", tags=["Firmalar"])


def _ids(db: Session, model, company_id: int) -> list[int]:
    return list(db.scalars(select(model.id).where(model.company_id == company_id)).all())


def _purge_company_data(db: Session, company_id: int) -> None:
    """Firma ve bağlı tüm operasyonel kayıtları kalıcı siler (kullanıcıları ayırır)."""
    risk_ids = _ids(db, RiskAssessment, company_id)
    if risk_ids:
        db.execute(delete(RiskMedia).where(RiskMedia.risk_id.in_(risk_ids)))
        db.execute(delete(RiskDof).where(RiskDof.risk_id.in_(risk_ids)))
        db.execute(delete(RiskAssessment).where(RiskAssessment.id.in_(risk_ids)))

    incident_ids = _ids(db, IncidentEvent, company_id)
    if incident_ids:
        db.execute(delete(IncidentRootCause).where(IncidentRootCause.incident_id.in_(incident_ids)))
        db.execute(delete(IncidentDof).where(IncidentDof.incident_id.in_(incident_ids)))
        db.execute(delete(IncidentEvent).where(IncidentEvent.id.in_(incident_ids)))

    ppe_ids = _ids(db, PpeAssignment, company_id)
    if ppe_ids:
        db.execute(delete(PpeAssignmentPhoto).where(PpeAssignmentPhoto.assignment_id.in_(ppe_ids)))
        db.execute(delete(PpeAssignment).where(PpeAssignment.id.in_(ppe_ids)))

    training_ids = _ids(db, TrainingSession, company_id)
    if training_ids:
        db.execute(delete(TrainingParticipant).where(TrainingParticipant.training_id.in_(training_ids)))
        db.execute(delete(TrainingSession).where(TrainingSession.id.in_(training_ids)))

    emp_ids = list(db.scalars(select(Employee.id).where(Employee.company_id == company_id)).all())
    if emp_ids:
        # Başka firmaya taşınmış eğitim katılımı kalmış olabilir
        db.execute(delete(TrainingParticipant).where(TrainingParticipant.employee_id.in_(emp_ids)))
        db.execute(delete(HealthRecord).where(HealthRecord.employee_id.in_(emp_ids)))
        db.execute(delete(PpeAssignment).where(PpeAssignment.employee_id.in_(emp_ids)))

    db.execute(delete(HealthRecord).where(HealthRecord.company_id == company_id))
    db.execute(delete(IsgRecord).where(IsgRecord.company_id == company_id))
    db.execute(delete(DocumentRecord).where(DocumentRecord.company_id == company_id))
    db.execute(delete(AnnualPlanItem).where(AnnualPlanItem.company_id == company_id))
    db.execute(delete(ServiceVisit).where(ServiceVisit.company_id == company_id))
    db.execute(delete(WorkplaceAssignment).where(WorkplaceAssignment.company_id == company_id))
    db.execute(delete(ServiceContract).where(ServiceContract.company_id == company_id))
    db.execute(delete(CompanySubscription).where(CompanySubscription.company_id == company_id))
    db.execute(delete(WorkplaceDepartment).where(WorkplaceDepartment.company_id == company_id))
    db.execute(delete(Employee).where(Employee.company_id == company_id))
    db.execute(delete(Branch).where(Branch.company_id == company_id))

    # Nullable bağlar: ayır
    db.execute(update(User).where(User.company_id == company_id).values(company_id=None))
    db.execute(update(AuditLog).where(AuditLog.company_id == company_id).values(company_id=None))
    db.execute(update(Notification).where(Notification.company_id == company_id).values(company_id=None))
    db.execute(
        update(FinanceTransaction)
        .where(FinanceTransaction.company_id == company_id)
        .values(company_id=None)
    )


@router.get("", response_model=list[CompanyResponse])
def list_companies(
    q: str | None = Query(None),
    active: bool | None = Query(None, description="True=yalnız aktif, False=yalnız pasif, None=hepsi (yönetici)"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(Company).order_by(Company.name)
    # Saha / firma kullanıcıları varsayılan yalnız aktif; global admin hepsini görür
    if active is not None:
        stmt = stmt.where(Company.is_active.is_(active))
    elif user.role != UserRole.GLOBAL_ADMIN:
        stmt = stmt.where(Company.is_active.is_(True))
    scope = companies_query_for_user(db, user)
    if scope is not None:
        stmt = stmt.where(scope)
    if q:
        stmt = stmt.where(
            or_(
                Company.name.ilike(f"%{q}%"),
                Company.nace_code.ilike(f"%{q}%"),
                Company.sgk_registry_no.ilike(f"%{q}%"),
            )
        )
    return list(db.scalars(stmt).all())


@router.post("", response_model=CompanyResponse)
def create_company(
    payload: CompanyCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    if db.scalar(select(Company).where(Company.name == payload.name)):
        raise HTTPException(409, "Bu firma zaten kayıtlı.")
    obj = Company(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{company_id}", response_model=CompanyResponse)
def update_company(
    company_id: int,
    payload: CompanyUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    obj = db.get(Company, company_id)
    if not obj:
        raise HTTPException(404, "Firma bulunamadı.")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{company_id}/deactivate")
def deactivate_company(
    company_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    obj = db.get(Company, company_id)
    if not obj:
        raise HTTPException(404, "Firma bulunamadı.")
    obj.is_active = False
    db.commit()
    return {"ok": True, "id": company_id, "is_active": False, "message": "Firma pasife alındı."}


@router.patch("/{company_id}/activate")
def activate_company(
    company_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    obj = db.get(Company, company_id)
    if not obj:
        raise HTTPException(404, "Firma bulunamadı.")
    obj.is_active = True
    db.commit()
    return {"ok": True, "id": company_id, "is_active": True, "message": "Firma yeniden aktifleştirildi."}


@router.delete("/{company_id}")
def delete_company(
    company_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    """Kalıcı sil: bağlı operasyonel kayıtlar da silinir. Pasife alma yapılmaz."""
    obj = db.get(Company, company_id)
    if not obj:
        raise HTTPException(404, "Firma bulunamadı.")
    name = obj.name
    try:
        _purge_company_data(db, company_id)
        db.delete(obj)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409,
            f"“{name}” silinemedi: beklenmeyen bağlı kayıt. Detay: {exc.orig or exc}",
        ) from None
    return {"ok": True, "id": company_id, "deleted": True, "message": f"“{name}” ve bağlı kayıtlar kalıcı silindi."}
