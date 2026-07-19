from io import BytesIO
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from openpyxl import load_workbook
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.company_access import accessible_company_ids_or_empty, ensure_company_access, resolve_employee_company_id
from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import Branch, Employee, User, UserRole
from app.schemas.employee import EmployeeCreate, EmployeeResponse, EmployeeUpdate
router=APIRouter(prefix="/employees",tags=["Personel"])
EDIT_ROLES=(UserRole.GLOBAL_ADMIN,UserRole.COMPANY_ADMIN,UserRole.SAFETY_SPECIALIST)

def check_company(db:Session,user:User,cid:int):
    ensure_company_access(db,user,cid)

def validate_branch(db:Session,cid:int,bid:int|None):
    if bid:
        branch=db.get(Branch,bid)
        if not branch or branch.company_id!=cid: raise HTTPException(422,"Şube firma ile uyumlu değil.")

@router.get("",response_model=list[EmployeeResponse])
def list_employees(company_id:int|None=Query(None),q:str|None=Query(None),active:bool|None=Query(None),db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    cid=resolve_employee_company_id(db,user,company_id)
    stmt=select(Employee).order_by(Employee.full_name)
    if cid == -1:
        return []
    if cid is not None:
        stmt=stmt.where(Employee.company_id==cid)
    else:
        ids=accessible_company_ids_or_empty(db,user)
        if not ids:
            return []
        stmt=stmt.where(Employee.company_id.in_(ids))
    if q: stmt=stmt.where(or_(Employee.full_name.ilike(f"%{q}%"),Employee.job_title.ilike(f"%{q}%"),Employee.department.ilike(f"%{q}%")))
    if active is not None: stmt=stmt.where(Employee.is_active==active)
    return list(db.scalars(stmt).all())

@router.post("",response_model=EmployeeResponse)
def create_employee(payload:EmployeeCreate,db:Session=Depends(get_db),user:User=Depends(require_roles(*EDIT_ROLES))):
    check_company(db,user,payload.company_id);validate_branch(db,payload.company_id,payload.branch_id)
    obj=Employee(**payload.model_dump());db.add(obj)
    try: db.commit()
    except IntegrityError: db.rollback();raise HTTPException(409,"Bu personel kaydı zaten mevcut olabilir.")
    db.refresh(obj);return obj

@router.put("/{employee_id}",response_model=EmployeeResponse)
def update_employee(employee_id:int,payload:EmployeeUpdate,db:Session=Depends(get_db),user:User=Depends(require_roles(*EDIT_ROLES))):
    obj=db.get(Employee,employee_id)
    if not obj: raise HTTPException(404,"Personel bulunamadı.")
    check_company(db,user,obj.company_id);validate_branch(db,obj.company_id,payload.branch_id)
    for k,v in payload.model_dump(exclude_unset=True).items(): setattr(obj,k,v)
    db.commit();db.refresh(obj);return obj

@router.delete("/{employee_id}")
def deactivate_employee(employee_id:int,db:Session=Depends(get_db),user:User=Depends(require_roles(*EDIT_ROLES))):
    obj=db.get(Employee,employee_id)
    if not obj: raise HTTPException(404,"Personel bulunamadı.")
    check_company(db,user,obj.company_id);obj.is_active=False;db.commit();return {"message":"Personel pasife alındı."}

@router.post("/import-excel")
def import_excel(company_id:int,branch_id:int|None=None,file:UploadFile=File(...),db:Session=Depends(get_db),user:User=Depends(require_roles(*EDIT_ROLES))):
    check_company(db,user,company_id);validate_branch(db,company_id,branch_id)
    if not file.filename.lower().endswith('.xlsx'): raise HTTPException(422,"Yalnızca .xlsx dosyası yükleyebilirsiniz.")
    wb=load_workbook(BytesIO(file.file.read()),read_only=True,data_only=True); ws=wb.active
    headers=[str(c.value or '').strip().lower() for c in next(ws.iter_rows(max_row=1))]
    aliases={'adı soyadı':'full_name','adi soyadi':'full_name','tc kimlik':'national_id_masked','t.c. kimlik':'national_id_masked','branş/görevi':'job_title','brans/gorevi':'job_title','görevi':'job_title','işe giriş tarihi':'start_date','ise giris tarihi':'start_date','engelli/hükümlü durumu':'special_status','engelli/hukumlu durumu':'special_status','departman':'department'}
    mapped=[aliases.get(h,h) for h in headers]
    if 'full_name' not in mapped: raise HTTPException(422,"Excel dosyasında 'Adı Soyadı' sütunu bulunmalıdır.")
    created=0;errors=[]
    for row_no,row in enumerate(ws.iter_rows(min_row=2,values_only=True),start=2):
        data={mapped[i]:row[i] for i in range(min(len(mapped),len(row))) if mapped[i] in {'full_name','national_id_masked','job_title','start_date','special_status','department'}}
        if not data.get('full_name'): continue
        obj=Employee(company_id=company_id,branch_id=branch_id,**data);db.add(obj)
        try: db.flush();created+=1
        except IntegrityError: db.rollback();errors.append(f"Satır {row_no}: mükerrer veya geçersiz kayıt")
    db.commit();return {'created':created,'errors':errors[:50]}
