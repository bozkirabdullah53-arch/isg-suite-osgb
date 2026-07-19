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
    today = date.today(); soon = today + timedelta(days=30)
    def count(model, *where): return db.scalar(select(func.count()).select_from(model).where(*where)) or 0
    income = db.scalar(select(func.coalesce(func.sum(FinanceTransaction.amount),0)).where(FinanceTransaction.osgb_id==oid, FinanceTransaction.transaction_type=="income", FinanceTransaction.status=="paid")) or 0
    expense = db.scalar(select(func.coalesce(func.sum(FinanceTransaction.amount),0)).where(FinanceTransaction.osgb_id==oid, FinanceTransaction.transaction_type=="expense", FinanceTransaction.status=="paid")) or 0

    professionals = count(IsgProfessional, IsgProfessional.osgb_id == oid, IsgProfessional.is_active == True)
    active_assignments = count(
        WorkplaceAssignment,
        WorkplaceAssignment.osgb_id == oid,
        WorkplaceAssignment.status == AssignmentStatus.ACTIVE,
    )
    assigned_pro_ids = set(
        db.scalars(
            select(WorkplaceAssignment.professional_id).where(
                WorkplaceAssignment.osgb_id == oid,
                WorkplaceAssignment.status == AssignmentStatus.ACTIVE,
            )
        ).all()
    )
    unassigned_professionals = max(0, professionals - len(assigned_pro_ids))

    oversight_summary = {
        "ok": 0,
        "warning": 0,
        "critical": 0,
        "unknown": 0,
        "gap_count": 0,
        "unassigned": unassigned_professionals,
        "professionals_tracked": 0,
    }
    try:
        from app.services.osgb_oversight import build_oversight
        ov = build_oversight(db, osgb_id=oid)
        oversight_summary.update({
            "ok": ov["summary"].get("ok", 0),
            "warning": ov["summary"].get("warning", 0),
            "critical": ov["summary"].get("critical", 0),
            "unknown": ov["summary"].get("unknown", 0),
            "gap_count": ov.get("gap_count", 0),
            "unassigned": ov["summary"].get("unassigned", unassigned_professionals),
            "professionals_tracked": ov["summary"].get("professionals", 0),
        })
    except Exception:
        pass

    return {
        "osgb_id": oid,
        "workplaces": count(Company, Company.osgb_id == oid, Company.is_active == True),
        "professionals": professionals,
        "active_assignments": active_assignments,
        "unassigned_professionals": unassigned_professionals,
        "visits_today": count(ServiceVisit, ServiceVisit.osgb_id == oid, ServiceVisit.visit_date == today),
        "upcoming_contract_expiries": count(
            ServiceContract,
            ServiceContract.osgb_id == oid,
            ServiceContract.end_date != None,
            ServiceContract.end_date.between(today, soon),
        ),
        "open_leads": count(CrmLead, CrmLead.osgb_id == oid, CrmLead.stage.notin_(["won", "lost"])),
        "pending_receivables": db.scalar(
            select(func.coalesce(func.sum(FinanceTransaction.amount), 0)).where(
                FinanceTransaction.osgb_id == oid,
                FinanceTransaction.transaction_type == "income",
                FinanceTransaction.status == "pending",
            )
        ) or 0,
        "net_cash": income - expense,
        "oversight": oversight_summary,
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
