from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import (Company, IsgProfessional, OsgbOrganization, ServiceContract,
                                 User, UserRole, WorkplaceAssignment)
from app.schemas.osgb import (AssignmentCreate, AssignmentResponse, ContractCreate,
                              ContractResponse, OsgbCreate, OsgbResponse,
                              ProfessionalCreate, ProfessionalResponse)
from app.services.osgb_oversight import build_oversight, seed_oversight_demo

router = APIRouter(prefix="/osgb", tags=["OSGB Yönetimi"])
ADMIN_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)

def _scope_osgb(user: User, osgb_id: int) -> None:
    if user.role != UserRole.GLOBAL_ADMIN and user.osgb_id != osgb_id:
        raise HTTPException(403, "Bu OSGB kaydına erişim yetkiniz yok.")

@router.get("", response_model=list[OsgbResponse])
def list_osgb(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(OsgbOrganization).order_by(OsgbOrganization.name)
    if user.role != UserRole.GLOBAL_ADMIN:
        stmt = stmt.where(OsgbOrganization.id == user.osgb_id)
    return list(db.scalars(stmt).all())

@router.post("", response_model=OsgbResponse)
def create_osgb(payload: OsgbCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN))):
    if db.scalar(select(OsgbOrganization).where(OsgbOrganization.name == payload.name)):
        raise HTTPException(409, "Bu OSGB zaten kayıtlı.")
    obj = OsgbOrganization(**payload.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.get("/oversight")
def osgb_oversight(
    osgb_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    """Yalnız global yönetici — profesyonel sorumluluk / 6331 hizmet denetimi."""
    _ = user
    return build_oversight(db, osgb_id=osgb_id)


@router.post("/oversight/seed-demo")
def osgb_oversight_seed_demo(
    osgb_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    """Test uzman / hekim / DSP + kasıtlı eksiklikler oluşturur."""
    _ = user
    try:
        seeded = seed_oversight_demo(db, osgb_id=osgb_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    overview = build_oversight(db, osgb_id=seeded["osgb_id"])
    return {"seeded": seeded, "oversight_summary": overview.get("summary"), "gap_count": overview.get("gap_count")}


@router.get("/professionals", response_model=list[ProfessionalResponse])
def list_professionals(osgb_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    target = osgb_id if user.role == UserRole.GLOBAL_ADMIN else user.osgb_id
    if not target: return []
    _scope_osgb(user, target)
    return list(db.scalars(select(IsgProfessional).where(IsgProfessional.osgb_id == target).order_by(IsgProfessional.full_name)).all())

@router.post("/professionals", response_model=ProfessionalResponse)
def create_professional(payload: ProfessionalCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN_ROLES))):
    _scope_osgb(user, payload.osgb_id)
    obj = IsgProfessional(**payload.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@router.get("/assignments", response_model=list[AssignmentResponse])
def list_assignments(company_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(WorkplaceAssignment)
    if user.role != UserRole.GLOBAL_ADMIN:
        if not user.osgb_id: return []
        stmt = stmt.where(WorkplaceAssignment.osgb_id == user.osgb_id)
    if company_id: stmt = stmt.where(WorkplaceAssignment.company_id == company_id)
    return list(db.scalars(stmt.order_by(WorkplaceAssignment.start_date.desc())).all())

@router.post("/assignments", response_model=AssignmentResponse)
def create_assignment(payload: AssignmentCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN_ROLES))):
    _scope_osgb(user, payload.osgb_id)
    company = db.get(Company, payload.company_id)
    professional = db.get(IsgProfessional, payload.professional_id)
    if not company or company.osgb_id != payload.osgb_id: raise HTTPException(400, "İşyeri bu OSGB'ye bağlı değil.")
    if not professional or professional.osgb_id != payload.osgb_id: raise HTTPException(400, "Profesyonel bu OSGB'ye bağlı değil.")
    obj = WorkplaceAssignment(**payload.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@router.get("/contracts", response_model=list[ContractResponse])
def list_contracts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(ServiceContract)
    if user.role != UserRole.GLOBAL_ADMIN:
        if not user.osgb_id: return []
        stmt = stmt.where(ServiceContract.osgb_id == user.osgb_id)
    return list(db.scalars(stmt.order_by(ServiceContract.start_date.desc())).all())

@router.post("/contracts", response_model=ContractResponse)
def create_contract(payload: ContractCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN_ROLES))):
    _scope_osgb(user, payload.osgb_id)
    company = db.get(Company, payload.company_id)
    if not company or company.osgb_id != payload.osgb_id: raise HTTPException(400, "İşyeri bu OSGB'ye bağlı değil.")
    obj = ServiceContract(**payload.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj
