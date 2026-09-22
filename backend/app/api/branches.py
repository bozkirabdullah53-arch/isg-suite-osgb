from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.company_access import company_ids_for_query, ensure_company_access
from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import Branch, User, UserRole
from app.schemas.branch import BranchCreate, BranchResponse, BranchUpdate
from app.services.audit import add_audit_log, request_ip, request_user_agent, serialize_audit_value
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
def create_branch(payload:BranchCreate, request:Request, db:Session=Depends(get_db), user:User=Depends(require_roles(UserRole.GLOBAL_ADMIN,UserRole.COMPANY_ADMIN))):
    allowed_company(db, user, payload.company_id)
    obj=Branch(**payload.model_dump()); db.add(obj); db.flush()
    add_audit_log(
        db,
        user=user,
        action="branch_created",
        module="branch",
        entity_type="branch",
        entity_id=str(obj.id),
        company_id=obj.company_id,
        description=f"Şube oluşturuldu: {obj.name}",
        ip_address=request_ip(request),
        user_agent=request_user_agent(request),
        new_value=serialize_audit_value(
            {
                "id": obj.id,
                "company_id": obj.company_id,
                "name": obj.name,
                "sgk_registry_no": obj.sgk_registry_no,
                "city": obj.city,
                "address": obj.address,
                "is_active": obj.is_active,
            }
        ),
    )
    db.commit(); db.refresh(obj); return obj

@router.put("/{branch_id}", response_model=BranchResponse)
def update_branch(branch_id:int,payload:BranchUpdate,request:Request,db:Session=Depends(get_db),user:User=Depends(require_roles(UserRole.GLOBAL_ADMIN,UserRole.COMPANY_ADMIN))):
    obj=db.get(Branch,branch_id)
    if not obj: raise HTTPException(404,"Şube bulunamadı.")
    allowed_company(db, user, obj.company_id)
    data = payload.model_dump(exclude_unset=True)
    old_value = {k: getattr(obj, k, None) for k in data}
    for k,v in data.items(): setattr(obj,k,v)
    add_audit_log(
        db,
        user=user,
        action="branch_updated",
        module="branch",
        entity_type="branch",
        entity_id=str(obj.id),
        company_id=obj.company_id,
        description=f"Şube güncellendi: {obj.name}",
        ip_address=request_ip(request),
        user_agent=request_user_agent(request),
        old_value=serialize_audit_value({"id": obj.id, **old_value}),
        new_value=serialize_audit_value({"id": obj.id, **{k: getattr(obj, k, None) for k in data}}),
    )
    db.commit();db.refresh(obj);return obj

@router.delete("/{branch_id}")
def deactivate_branch(branch_id:int,request:Request,db:Session=Depends(get_db),user:User=Depends(require_roles(UserRole.GLOBAL_ADMIN,UserRole.COMPANY_ADMIN))):
    obj=db.get(Branch,branch_id)
    if not obj: raise HTTPException(404,"Şube bulunamadı.")
    allowed_company(db, user, obj.company_id)
    old_value = {"id": obj.id, "name": obj.name, "is_active": bool(obj.is_active)}
    obj.is_active=False
    add_audit_log(
        db,
        user=user,
        action="branch_deactivated",
        module="branch",
        entity_type="branch",
        entity_id=str(obj.id),
        company_id=obj.company_id,
        description=f"Şube pasife alındı: {obj.name}",
        ip_address=request_ip(request),
        user_agent=request_user_agent(request),
        old_value=serialize_audit_value(old_value),
        new_value=serialize_audit_value({"id": obj.id, "name": obj.name, "is_active": False}),
    )
    db.commit();return {"message":"Şube pasife alındı."}
