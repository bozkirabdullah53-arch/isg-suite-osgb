import hashlib
from datetime import date
from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload
from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import Company, Employee, TrainingParticipant, TrainingSession, TrainingStatus, User, UserRole
from app.schemas.training import TrainingCreate, TrainingResponse, TrainingUpdate

router = APIRouter(prefix="/trainings", tags=["Eğitim Yönetimi"])
EDIT_ROLES=(UserRole.GLOBAL_ADMIN,UserRole.COMPANY_ADMIN,UserRole.SAFETY_SPECIALIST)
RULES={"Az Tehlikeli":(8,3),"Tehlikeli":(12,2),"Çok Tehlikeli":(16,1)}

def ensure_access(user:User, company_id:int):
    if user.role != UserRole.GLOBAL_ADMIN and user.company_id != company_id:
        raise HTTPException(403,"Bu firmanın eğitim kayıtlarına erişemezsiniz.")

def add_years(d:date, years:int)->date:
    try:return d.replace(year=d.year+years)
    except ValueError:return d.replace(month=2,day=28,year=d.year+years)

@router.get("",response_model=list[TrainingResponse])
def list_trainings(q:str|None=Query(None,max_length=100),company_id:int|None=None,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    query=select(TrainingSession).options(selectinload(TrainingSession.participants)).order_by(TrainingSession.start_date.desc())
    effective=company_id if user.role==UserRole.GLOBAL_ADMIN else user.company_id
    if effective:query=query.where(TrainingSession.company_id==effective)
    if q:
        p=f"%{q.strip()}%";query=query.where(or_(TrainingSession.title.ilike(p),TrainingSession.instructor_name.ilike(p),TrainingSession.sector.ilike(p)))
    return list(db.scalars(query).unique().all())

@router.post("",response_model=TrainingResponse)
def create_training(payload:TrainingCreate,db:Session=Depends(get_db),user:User=Depends(require_roles(*EDIT_ROLES))):
    ensure_access(user,payload.company_id)
    company=db.get(Company,payload.company_id)
    if not company:raise HTTPException(404,"Firma bulunamadı.")
    if payload.hazard_class not in RULES:raise HTTPException(422,"Geçersiz tehlike sınıfı.")
    if payload.participant_ids:
        employees=list(db.scalars(select(Employee).where(Employee.id.in_(payload.participant_ids),Employee.company_id==payload.company_id,Employee.is_active.is_(True))).all())
        if len(employees)!=len(set(payload.participant_ids)):raise HTTPException(422,"Katılımcılardan biri firmaya ait değil veya pasif.")
    hours,years=RULES[payload.hazard_class]
    raw=f"{payload.company_id}|{payload.title}|{payload.start_date.isoformat()}|{user.id}"
    code=hashlib.sha256(raw.encode()).hexdigest()[:16].upper()
    values=payload.model_dump(exclude={"participant_ids"})
    row=TrainingSession(**values,duration_hours=hours,renewal_years=years,next_training_date=add_years(payload.end_date or payload.start_date,years),verification_code=code,created_by_id=user.id)
    db.add(row);db.flush()
    for eid in sorted(set(payload.participant_ids)):
        db.add(TrainingParticipant(training_id=row.id,employee_id=eid,certificate_number=f"EGT-{row.id:06d}-{eid:06d}"))
    db.commit()
    return db.scalar(select(TrainingSession).options(selectinload(TrainingSession.participants)).where(TrainingSession.id==row.id))

@router.patch("/{training_id}",response_model=TrainingResponse)
def update_training(training_id:int,payload:TrainingUpdate,db:Session=Depends(get_db),user:User=Depends(require_roles(*EDIT_ROLES))):
    row=db.scalar(select(TrainingSession).options(selectinload(TrainingSession.participants)).where(TrainingSession.id==training_id))
    if not row:raise HTTPException(404,"Eğitim kaydı bulunamadı.")
    ensure_access(user,row.company_id)
    for k,v in payload.model_dump(exclude_unset=True).items():setattr(row,k,v)
    db.commit();db.refresh(row);return row

@router.get("/{training_id}/attendance.pdf")
def attendance_pdf(training_id:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    row=db.scalar(select(TrainingSession).options(selectinload(TrainingSession.participants)).where(TrainingSession.id==training_id))
    if not row:raise HTTPException(404,"Eğitim kaydı bulunamadı.")
    ensure_access(user,row.company_id)
    company=db.get(Company,row.company_id)
    employee_ids=[p.employee_id for p in row.participants]
    employees={e.id:e for e in db.scalars(select(Employee).where(Employee.id.in_(employee_ids))).all()} if employee_ids else {}
    out=BytesIO();pdf=canvas.Canvas(out,pagesize=A4);w,h=A4
    pdf.setTitle("Eğitim Katılım İmza Listesi");pdf.setFont("Helvetica-Bold",14);pdf.drawString(50,h-55,"EGITIM KATILIM VE IMZA LISTESI")
    pdf.setFont("Helvetica",10);y=h-85
    for text in [f"Firma: {company.name if company else row.company_id}",f"Egitim: {row.title}",f"Tarih: {row.start_date}",f"Sure: {row.duration_hours} saat",f"Egitici: {row.instructor_name}",f"Dogrulama: {row.verification_code}"]:
        pdf.drawString(50,y,text);y-=16
    y-=10;pdf.setFont("Helvetica-Bold",9);pdf.drawString(50,y,"No");pdf.drawString(80,y,"Ad Soyad");pdf.drawString(310,y,"Gorev");pdf.drawString(455,y,"Imza")
    y-=18;pdf.setFont("Helvetica",9)
    for i,p in enumerate(row.participants,1):
        e=employees.get(p.employee_id);pdf.drawString(50,y,str(i));pdf.drawString(80,y,(e.full_name if e else str(p.employee_id))[:38]);pdf.drawString(310,y,((e.job_title if e else "") or "")[:23]);pdf.line(455,y-2,545,y-2);y-=20
        if y<60:pdf.showPage();y=h-60
    pdf.save();out.seek(0)
    return StreamingResponse(out,media_type="application/pdf",headers={"Content-Disposition":f'attachment; filename="egitim-{training_id}-imza-listesi.pdf"'})
