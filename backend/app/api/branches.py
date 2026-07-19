from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.company_access import company_ids_for_query, ensure_company_access
from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import Branch, User, UserRole
from app.schemas.branch import BranchCreate, BranchResponse, BranchUpdate
router=APIRouter(prefix="/branches", tags=["Şubeler"])

def allowed_company(db: Session, user: User, company_id: int) -> None:
    ensure_company_access(db, user, company_id)

@router.get("", response_model=list[BranchResponse])
def list_branches(company_id:int|None=Query(None), db:Session=Depends(get_db), user:User=Depends(get_current_user)):
    stmt=select(Branch).order_by(Branch.name)
    company_ids = company_ids_for_query(db, user, company_id)
    if company_ids == []:
        return []
    if company_ids is not None:
        stmt = stmt.where(Branch.company_id.in_(company_ids))
    return list(db.scalars(stmt).all())

@router.post("", response_model=BranchResponse)
def create_branch(payload:BranchCreate, db:Session=Depends(get_db), user:User=Depends(require_roles(UserRole.GLOBAL_ADMIN,UserRole.COMPANY_ADMIN))):
    allowed_company(db, user, payload.company_id)
    obj=Branch(**payload.model_dump()); db.add(obj); db.commit(); db.refresh(obj); return obj

@router.put("/{branch_id}", response_model=BranchResponse)
def update_branch(branch_id:int,payload:BranchUpdate,db:Session=Depends(get_db),user:User=Depends(require_roles(UserRole.GLOBAL_ADMIN,UserRole.COMPANY_ADMIN))):
    obj=db.get(Branch,branch_id)
    if not obj: raise HTTPException(404,"Şube bulunamadı.")
    allowed_company(db, user, obj.company_id)
    for k,v in payload.model_dump(exclude_unset=True).items(): setattr(obj,k,v)
    db.commit();db.refresh(obj);return obj

@router.delete("/{branch_id}")
def deactivate_branch(branch_id:int,db:Session=Depends(get_db),user:User=Depends(require_roles(UserRole.GLOBAL_ADMIN,UserRole.COMPANY_ADMIN))):
    obj=db.get(Branch,branch_id)
    if not obj: raise HTTPException(404,"Şube bulunamadı.")
    allowed_company(db, user, obj.company_id);obj.is_active=False;db.commit();return {"message":"Şube pasife alındı."}
