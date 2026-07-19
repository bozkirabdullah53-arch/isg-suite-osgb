from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import (AssignmentStatus, Company, CrmLead, FinanceTransaction, IsgProfessional,
                                 OsgbOrganization, ServiceContract, ServiceVisit, User,
                                 UserRole, VisitStatus, WorkplaceAssignment)
from app.schemas.operations import (FinanceCreate, FinanceResponse, LeadCreate, LeadResponse,
                                    VisitCreate, VisitResponse)

router = APIRouter(prefix="/operations", tags=["OSGB Operasyonları"])
ADMIN = (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)

def scope(user: User, osgb_id: int):
    if user.role != UserRole.GLOBAL_ADMIN and user.osgb_id != osgb_id:
        raise HTTPException(403, "Bu OSGB verisine erişim yetkiniz yok.")

def active_osgb(user: User, requested: int | None = None) -> int:
    oid = requested if user.role == UserRole.GLOBAL_ADMIN else user.osgb_id
    if not oid:
        raise HTTPException(400, "Kullanıcıya bağlı bir OSGB bulunamadı.")
    scope(user, oid)
    return oid

@router.get("/dashboard")
def osgb_dashboard(osgb_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    oid = active_osgb(user, osgb_id)
    today = date.today()
    soon = today + timedelta(days=30)

    def count(model, *where):
        return db.scalar(select(func.count()).select_from(model).where(*where)) or 0

    workplaces = count(Company, Company.osgb_id == oid, Company.is_active == True)

    pros = list(
        db.scalars(
            select(IsgProfessional).where(
                IsgProfessional.osgb_id == oid,
                IsgProfessional.is_active == True,
            ).order_by(IsgProfessional.full_name)
        ).all()
    )
    assigned_pro_ids = set(
        db.scalars(
            select(WorkplaceAssignment.professional_id).where(
                WorkplaceAssignment.osgb_id == oid,
                WorkplaceAssignment.status == AssignmentStatus.ACTIVE,
            )
        ).all()
    )

    type_order = ("safety_specialist", "workplace_physician", "other_health_personnel")
    type_labels = {
        "safety_specialist": "İş Güvenliği Uzmanları",
        "workplace_physician": "İşyeri Hekimleri",
        "other_health_personnel": "Diğer Sağlık Personeli",
    }

    by_type: dict[str, dict] = {}
    unassigned_by_type: dict[str, dict] = {}
    for t in type_order:
        typed = [p for p in pros if p.professional_type.value == t]
        unassigned = [p for p in typed if p.id not in assigned_pro_ids]
        by_type[t] = {
            "type": t,
            "label": type_labels[t],
            "count": len(typed),
        }
        unassigned_by_type[t] = {
            "type": t,
            "label": type_labels[t],
            "count": len(unassigned),
            "items": [
                {
                    "id": p.id,
                    "full_name": p.full_name,
                    "certificate_class": p.certificate_class,
                    "certificate_number": p.certificate_number,
                    "email": p.email,
                    "phone": p.phone,
                }
                for p in unassigned
            ],
        }

    companies = {
        c.id: c.name
        for c in db.scalars(select(Company).where(Company.osgb_id == oid)).all()
    }
    expiring = list(
        db.scalars(
            select(ServiceContract).where(
                ServiceContract.osgb_id == oid,
                ServiceContract.end_date.is_not(None),
                ServiceContract.end_date.between(today, soon),
            ).order_by(ServiceContract.end_date)
        ).all()
    )
    upcoming_contracts = [
        {
            "id": c.id,
            "contract_number": c.contract_number,
            "company_id": c.company_id,
            "company_name": companies.get(c.company_id, f"#{c.company_id}"),
            "start_date": c.start_date.isoformat() if c.start_date else None,
            "end_date": c.end_date.isoformat() if c.end_date else None,
            "days_left": (c.end_date - today).days if c.end_date else None,
            "status": c.status,
            "monthly_fee": c.monthly_fee,
        }
        for c in expiring
    ]

    return {
        "osgb_id": oid,
        "workplaces": workplaces,
        "professionals_by_type": by_type,
        "unassigned_by_type": unassigned_by_type,
        "unassigned_professionals": sum(v["count"] for v in unassigned_by_type.values()),
        "professionals": len(pros),
        "upcoming_contract_expiries": len(upcoming_contracts),
        "upcoming_contracts": upcoming_contracts,
        "period_days": 30,
    }

@router.get("/visits", response_model=list[VisitResponse])
def visits(osgb_id:int|None=None, db:Session=Depends(get_db), user:User=Depends(get_current_user)):
    oid=active_osgb(user,osgb_id)
    return list(db.scalars(select(ServiceVisit).where(ServiceVisit.osgb_id==oid).order_by(ServiceVisit.visit_date.desc())).all())

@router.post("/visits", response_model=VisitResponse)
def create_visit(payload:VisitCreate, db:Session=Depends(get_db), user:User=Depends(require_roles(*ADMIN))):
    scope(user,payload.osgb_id)
    company=db.get(Company,payload.company_id); professional=db.get(IsgProfessional,payload.professional_id)
    if not company or company.osgb_id!=payload.osgb_id: raise HTTPException(400,"İşyeri OSGB ile eşleşmiyor.")
    if not professional or professional.osgb_id!=payload.osgb_id: raise HTTPException(400,"Profesyonel OSGB ile eşleşmiyor.")
    obj=ServiceVisit(**payload.model_dump());db.add(obj);db.commit();db.refresh(obj);return obj

@router.patch("/visits/{visit_id}/complete", response_model=VisitResponse)
def complete_visit(visit_id:int, db:Session=Depends(get_db), user:User=Depends(require_roles(*ADMIN))):
    obj=db.get(ServiceVisit,visit_id)
    if not obj: raise HTTPException(404,"Ziyaret bulunamadı.")
    scope(user,obj.osgb_id);obj.status=VisitStatus.COMPLETED;db.commit();db.refresh(obj);return obj

@router.get("/leads", response_model=list[LeadResponse])
def leads(osgb_id:int|None=None, db:Session=Depends(get_db), user:User=Depends(get_current_user)):
    oid=active_osgb(user,osgb_id)
    return list(db.scalars(select(CrmLead).where(CrmLead.osgb_id==oid).order_by(CrmLead.created_at.desc())).all())

@router.post("/leads", response_model=LeadResponse)
def create_lead(payload:LeadCreate, db:Session=Depends(get_db), user:User=Depends(require_roles(*ADMIN))):
    scope(user,payload.osgb_id);obj=CrmLead(**payload.model_dump());db.add(obj);db.commit();db.refresh(obj);return obj

@router.get("/finance", response_model=list[FinanceResponse])
def finance(osgb_id:int|None=None, db:Session=Depends(get_db), user:User=Depends(get_current_user)):
    oid=active_osgb(user,osgb_id)
    return list(db.scalars(select(FinanceTransaction).where(FinanceTransaction.osgb_id==oid).order_by(FinanceTransaction.transaction_date.desc())).all())

@router.post("/finance", response_model=FinanceResponse)
def create_finance(payload:FinanceCreate, db:Session=Depends(get_db), user:User=Depends(require_roles(*ADMIN))):
    scope(user,payload.osgb_id)
    if payload.company_id:
        company=db.get(Company,payload.company_id)
        if not company or company.osgb_id!=payload.osgb_id: raise HTTPException(400,"İşyeri OSGB ile eşleşmiyor.")
    obj=FinanceTransaction(**payload.model_dump());db.add(obj);db.commit();db.refresh(obj);return obj
