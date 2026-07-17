from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.entities import Branch, Company, Employee, User, UserRole
router=APIRouter(prefix="/dashboard",tags=["Panel"])
@router.get("/summary")
def summary(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    if user.role==UserRole.GLOBAL_ADMIN:
        cc=db.scalar(select(func.count()).select_from(Company).where(Company.is_active==True)) or 0
        bc=db.scalar(select(func.count()).select_from(Branch).where(Branch.is_active==True)) or 0
        ec=db.scalar(select(func.count()).select_from(Employee).where(Employee.is_active==True)) or 0
        uc=db.scalar(select(func.count()).select_from(User).where(User.is_active==True)) or 0
    else:
        cc=1 if user.company_id else 0
        bc=db.scalar(select(func.count()).select_from(Branch).where(Branch.company_id==user.company_id,Branch.is_active==True)) or 0
        ec=db.scalar(select(func.count()).select_from(Employee).where(Employee.company_id==user.company_id,Employee.is_active==True)) or 0
        uc=db.scalar(select(func.count()).select_from(User).where(User.company_id==user.company_id,User.is_active==True)) or 0
    return {'company_count':cc,'branch_count':bc,'employee_count':ec,'user_count':uc,'role':user.role.value}
