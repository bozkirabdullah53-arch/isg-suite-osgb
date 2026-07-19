from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.api.company_access import ensure_company_access, find_professional_for_user
from app.api.deps import get_current_user, require_roles
from app.core.config import settings
from app.core.database import get_db
from app.models.entities import (AssignmentStatus, Company, CrmLead, FinanceTransaction, IsgProfessional,
                                 OsgbOrganization, ServiceContract, ServiceVisit, User,
                                 UserRole, VisitStatus, WorkplaceAssignment)
from app.schemas.operations import (FinanceCreate, FinanceResponse, LeadCreate, LeadResponse,
                                    VisitCreate, VisitResponse)

router = APIRouter(prefix="/operations", tags=["OSGB Operasyonları"])
ADMIN = (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)
VISIT_ROLES = (
    UserRole.GLOBAL_ADMIN,
    UserRole.COMPANY_ADMIN,
    UserRole.SAFETY_SPECIALIST,
    UserRole.WORKPLACE_PHYSICIAN,
    UserRole.OTHER_HEALTH_PERSONNEL,
)
FIELD_VISIT_ROLES = (
    UserRole.SAFETY_SPECIALIST,
    UserRole.WORKPLACE_PHYSICIAN,
    UserRole.OTHER_HEALTH_PERSONNEL,
)
ALLOWED_NOTEBOOK = {".pdf", ".jpg", ".jpeg", ".png"}
_FIELD_ROLES = set(FIELD_VISIT_ROLES)


def scope(user: User, osgb_id: int):
    """OSGB kapsamı. Saha rolleri (uzman/hekim/DSP) işyeri görevlendirmesi ile doğrulanır."""
    if user.role == UserRole.GLOBAL_ADMIN:
        return
    if user.role in _FIELD_ROLES:
        return
    if user.osgb_id != osgb_id:
        raise HTTPException(403, "Bu OSGB verisine erişim yetkiniz yok.")


def active_osgb(user: User, requested: int | None = None, db: Session | None = None) -> int:
    if user.role == UserRole.GLOBAL_ADMIN:
        oid = requested
    elif user.role in _FIELD_ROLES:
        oid = user.osgb_id
        if not oid and db is not None:
            pro = find_professional_for_user(db, user)
            if pro:
                oid = pro.osgb_id
        if not oid:
            oid = requested
    else:
        oid = user.osgb_id
    if not oid:
        raise HTTPException(400, "Kullanıcıya bağlı bir OSGB bulunamadı.")
    scope(user, oid)
    return oid


def _upload_root() -> Path:
    root = Path(settings.upload_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _resolve_visit_professional(db: Session, user: User, payload: VisitCreate) -> IsgProfessional:
    if user.role in _FIELD_ROLES:
        pro = find_professional_for_user(db, user)
        if not pro:
            raise HTTPException(
                400,
                "Profesyonel kaydınız bulunamadı. Kullanıcı e-postanızın İSG Profesyonelleri kaydıyla aynı olduğundan emin olun.",
            )
        return pro
    if payload.professional_id:
        professional = db.get(IsgProfessional, payload.professional_id)
        if not professional or professional.osgb_id != payload.osgb_id:
            raise HTTPException(400, "Profesyonel OSGB ile eşleşmiyor.")
        return professional
    pro = find_professional_for_user(db, user)
    if pro:
        return pro
    assign = db.scalar(
        select(WorkplaceAssignment).where(
            WorkplaceAssignment.company_id == payload.company_id,
            WorkplaceAssignment.osgb_id == payload.osgb_id,
            WorkplaceAssignment.status == AssignmentStatus.ACTIVE,
        ).order_by(WorkplaceAssignment.id).limit(1)
    )
    if assign:
        professional = db.get(IsgProfessional, assign.professional_id)
        if professional:
            return professional
    raise HTTPException(400, "Bu işyerinde aktif görevlendirme yok; profesyonel belirlenemedi.")


def _get_visit(db: Session, visit_id: int, user: User) -> ServiceVisit:
    obj = db.get(ServiceVisit, visit_id)
    if not obj:
        raise HTTPException(404, "Ziyaret bulunamadı.")
    # Yalnız global yönetici veya ziyareti yapan saha personeli
    if user.role == UserRole.GLOBAL_ADMIN:
        return obj
    if user.role in _FIELD_ROLES:
        pro = find_professional_for_user(db, user)
        if not pro or obj.professional_id != pro.id:
            raise HTTPException(403, "Bu ziyarete erişim yetkiniz yok.")
        return obj
    raise HTTPException(403, "Bu ziyarete erişim yetkiniz yok.")

@router.get("/dashboard")
def osgb_dashboard(osgb_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN))):
    oid = active_osgb(user, osgb_id, db)
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
def visits(osgb_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # Saha personeli: yalnız kendi ziyaretleri
    if user.role in _FIELD_ROLES:
        pro = find_professional_for_user(db, user)
        if not pro:
            return []
        return list(
            db.scalars(
                select(ServiceVisit)
                .where(ServiceVisit.professional_id == pro.id)
                .order_by(ServiceVisit.visit_date.desc(), ServiceVisit.id.desc())
            ).all()
        )
    # Tüm OSGB ziyaret listesi yalnız global yönetici
    if user.role != UserRole.GLOBAL_ADMIN:
        raise HTTPException(403, "Tüm ziyaret listesi yalnız global yönetici içindir.")
    oid = active_osgb(user, osgb_id, db)
    return list(
        db.scalars(
            select(ServiceVisit)
            .where(ServiceVisit.osgb_id == oid)
            .order_by(ServiceVisit.visit_date.desc(), ServiceVisit.id.desc())
        ).all()
    )


@router.post("/visits", response_model=VisitResponse)
def create_visit(payload: VisitCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*FIELD_VISIT_ROLES))):
    company = db.get(Company, payload.company_id)
    if not company or not company.osgb_id:
        raise HTTPException(400, "İşyeri bir OSGB'ye bağlı değil.")
    ensure_company_access(db, user, payload.company_id)
    payload = payload.model_copy(update={"osgb_id": company.osgb_id})
    professional = _resolve_visit_professional(db, user, payload)
    data = payload.model_dump()
    data["professional_id"] = professional.id
    # Kullanıcı OSGB bağı boşsa profesyonelden senkronize et (liste/filtreler için)
    if user.role in _FIELD_ROLES and not user.osgb_id and professional.osgb_id:
        user.osgb_id = professional.osgb_id
    obj = ServiceVisit(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.post("/visits/{visit_id}/notebook", response_model=VisitResponse)
async def upload_visit_notebook(
    visit_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*FIELD_VISIT_ROLES)),
):
    obj = _get_visit(db, visit_id, user)
    name = file.filename or "tespit-oneri-defteri.pdf"
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_NOTEBOOK:
        raise HTTPException(422, "Sadece pdf, jpg veya png yükleyin.")
    data = await file.read()
    if not data:
        raise HTTPException(400, "Boş dosya yüklenemez.")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"Dosya {settings.max_upload_mb} MB sınırını aşıyor.")
    if obj.notebook_storage_path:
        old = (_upload_root() / obj.notebook_storage_path).resolve()
        if _upload_root() in old.parents and old.exists():
            try:
                old.unlink()
            except OSError:
                pass
    rel = f"{obj.osgb_id}/visits/{obj.id}_{uuid4().hex[:10]}{ext}"
    target = _upload_root() / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    obj.notebook_file_name = name
    obj.notebook_storage_path = rel.replace("\\", "/")
    obj.notebook_content_type = file.content_type or {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
    }.get(ext, "application/octet-stream")
    obj.status = VisitStatus.COMPLETED
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/visits/{visit_id}/notebook")
def download_visit_notebook(
    visit_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    obj = _get_visit(db, visit_id, user)
    if not obj.notebook_storage_path:
        raise HTTPException(404, "Tespit öneri defteri dosyası yok.")
    path = (_upload_root() / obj.notebook_storage_path).resolve()
    if _upload_root() not in path.parents or not path.exists():
        raise HTTPException(404, "Dosya bulunamadı.")
    return FileResponse(
        path,
        media_type=obj.notebook_content_type or "application/octet-stream",
        filename=obj.notebook_file_name or path.name,
    )


@router.patch("/visits/{visit_id}/complete", response_model=VisitResponse)
def complete_visit(visit_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*FIELD_VISIT_ROLES))):
    obj = _get_visit(db, visit_id, user)
    obj.status = VisitStatus.COMPLETED
    db.commit()
    db.refresh(obj)
    return obj

@router.get("/leads", response_model=list[LeadResponse])
def leads(osgb_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN))):
    oid = active_osgb(user, osgb_id, db)
    return list(db.scalars(select(CrmLead).where(CrmLead.osgb_id == oid).order_by(CrmLead.created_at.desc())).all())

@router.post("/leads", response_model=LeadResponse)
def create_lead(payload: LeadCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN))):
    scope(user, payload.osgb_id)
    obj = CrmLead(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.get("/finance", response_model=list[FinanceResponse])
def finance(osgb_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN))):
    oid = active_osgb(user, osgb_id, db)
    return list(db.scalars(select(FinanceTransaction).where(FinanceTransaction.osgb_id == oid).order_by(FinanceTransaction.transaction_date.desc())).all())

@router.post("/finance", response_model=FinanceResponse)
def create_finance(payload: FinanceCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN))):
    scope(user, payload.osgb_id)
    if payload.company_id:
        company = db.get(Company, payload.company_id)
        if not company or company.osgb_id != payload.osgb_id:
            raise HTTPException(400, "İşyeri OSGB ile eşleşmiyor.")
    obj = FinanceTransaction(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj
