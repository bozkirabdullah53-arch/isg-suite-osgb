from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import Company, User, UserRole
from app.schemas.company import CompanyCreate, CompanyResponse, CompanyUpdate
router = APIRouter(prefix="/companies", tags=["Firmalar"])

@router.get("", response_model=list[CompanyResponse])
def list_companies(q: str | None = Query(None), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(Company).order_by(Company.name)
    if user.role != UserRole.GLOBAL_ADMIN: stmt = stmt.where(Company.id == user.company_id)
    if q: stmt = stmt.where(or_(Company.name.ilike(f"%{q}%"), Company.nace_code.ilike(f"%{q}%")))
    return list(db.scalars(stmt).all())

@router.post("", response_model=CompanyResponse)
def create_company(payload: CompanyCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN))):
    if db.scalar(select(Company).where(Company.name == payload.name)): raise HTTPException(409, "Bu firma zaten kayıtlı.")
    obj=Company(**payload.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj

@router.put("/{company_id}", response_model=CompanyResponse)
def update_company(company_id:int, payload:CompanyUpdate, db:Session=Depends(get_db), _:User=Depends(require_roles(UserRole.GLOBAL_ADMIN))):
    obj=db.get(Company, company_id)
    if not obj: raise HTTPException(404,"Firma bulunamadı.")
    for k,v in payload.model_dump(exclude_unset=True).items(): setattr(obj,k,v)
    db.commit(); db.refresh(obj); return obj

@router.delete("/{company_id}")
def deactivate_company(company_id:int, db:Session=Depends(get_db), _:User=Depends(require_roles(UserRole.GLOBAL_ADMIN))):
    obj=db.get(Company,company_id)
    if not obj: raise HTTPException(404,"Firma bulunamadı.")
    obj.is_active=False; db.commit(); return {"message":"Firma pasife alındı."}
