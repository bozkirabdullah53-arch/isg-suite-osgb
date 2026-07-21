from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
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
                                    VisitCreate, VisitGpsStamp, VisitPlanCreate, VisitResponse, VisitUpdate)
from app.services.visit_calendar import build_visit_calendar
from app.services.module_kpis import build_module_kpis

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


def _apply_gps_stamp(obj: ServiceVisit, lat: float | None, lng: float | None, accuracy: float | None = None):
    if lat is None or lng is None:
        return
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        raise HTTPException(422, "GPS koordinatları geçersiz.")
    obj.gps_lat = float(lat)
    obj.gps_lng = float(lng)
    obj.gps_accuracy_m = float(accuracy) if accuracy is not None else None
    obj.gps_captured_at = datetime.utcnow()


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
        # GA: query param > kullanıcıya bağlı OSGB > ilk aktif OSGB
        oid = requested or user.osgb_id
        if not oid and db is not None:
            row = db.scalar(
                select(OsgbOrganization)
                .where(OsgbOrganization.is_active.is_(True))
                .order_by(OsgbOrganization.id)
                .limit(1)
            )
            oid = row.id if row else None
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
    # EİSA, kendi OSGB yöneticisi veya ziyareti yapan saha personeli
    if user.role == UserRole.GLOBAL_ADMIN:
        return obj
    if user.role == UserRole.COMPANY_ADMIN:
        if user.osgb_id and obj.osgb_id == user.osgb_id:
            return obj
        raise HTTPException(403, "Bu ziyarete erişim yetkiniz yok.")
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


@router.get("/module-kpis")
def module_kpis(
    osgb_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN)),
):
    """OSGB merkezi modül KPI — risk/DÖF, eğitim yenileme, sağlık periyodik takip."""
    oid = active_osgb(user, osgb_id, db)
    return build_module_kpis(db, oid)


@router.get("/visits/calendar")
def visits_calendar(
    month: str | None = None,
    osgb_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Saha takvimi özeti — planlı/gecikmiş ziyaret ve eksik süre uyarıları."""
    pro = None
    if user.role in _FIELD_ROLES:
        pro = find_professional_for_user(db, user)
        if not pro:
            return build_visit_calendar(db, osgb_id=None, month=month)
        oid = pro.osgb_id
    elif user.role in (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN):
        oid = active_osgb(user, osgb_id, db)
    else:
        raise HTTPException(403, "Takvim görüntüleme yetkiniz yok.")
    data = build_visit_calendar(db, osgb_id=oid, month=month)
    if pro:
        pid = pro.id
        for key in ("days", "overdue", "upcoming", "missing"):
            if key == "days":
                for day in data.get("days", []):
                    day["visits"] = [v for v in day.get("visits", []) if v.get("professional_id") == pid]
                    day["visit_count"] = len(day["visits"])
            else:
                data[key] = [r for r in data.get(key, []) if r.get("professional_id") == pid]
    return data


@router.post("/visits/plan", response_model=VisitResponse)
def plan_visit(
    payload: VisitPlanCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN, *FIELD_VISIT_ROLES)),
):
    """Planlı ziyaret oluştur (defter zorunlu değil)."""
    scope(user, payload.osgb_id)
    ensure_company_access(db, user, payload.company_id)
    company = db.get(Company, payload.company_id)
    if not company or company.osgb_id != payload.osgb_id:
        raise HTTPException(400, "İşyeri OSGB ile eşleşmiyor.")
    professional = db.get(IsgProfessional, payload.professional_id)
    if not professional or professional.osgb_id != payload.osgb_id:
        raise HTTPException(400, "Profesyonel OSGB ile eşleşmiyor.")
    if user.role in _FIELD_ROLES:
        pro = find_professional_for_user(db, user)
        if not pro or pro.id != payload.professional_id:
            raise HTTPException(403, "Yalnız kendi adınıza planlı ziyaret oluşturabilirsiniz.")
    obj = ServiceVisit(
        osgb_id=payload.osgb_id,
        company_id=payload.company_id,
        professional_id=payload.professional_id,
        visit_date=payload.visit_date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        duration_minutes=payload.duration_minutes,
        subject=payload.subject,
        notes=payload.notes,
        status=VisitStatus.PLANNED,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


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
    # EİSA veya OSGB yöneticisi: kendi OSGB kapsamındaki tüm ziyaretler
    if user.role not in (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN):
        raise HTTPException(403, "Ziyaret listesine erişim yetkiniz yok.")
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


def _delete_notebook_file(
    obj: ServiceVisit,
    db: Session | None = None,
    user: User | None = None,
) -> None:
    if not obj.notebook_storage_path:
        return
    path = (_upload_root() / obj.notebook_storage_path).resolve()
    if _upload_root() in path.parents and path.exists():
        if db is not None:
            try:
                from app.services.archive_store import archive_file_before_delete

                archive_file_before_delete(
                    db,
                    source=path,
                    user=user,
                    company_id=obj.company_id,
                    osgb_id=obj.osgb_id,
                    entity_type="visit_notebook",
                    entity_id=str(obj.id),
                    original_name=obj.notebook_file_name,
                    notes="Ziyaret defteri silinmeden önce arşivlendi",
                )
            except Exception:
                pass
        try:
            path.unlink()
        except OSError:
            pass


@router.patch("/visits/{visit_id}", response_model=VisitResponse)
def update_visit(
    visit_id: int,
    payload: VisitUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*FIELD_VISIT_ROLES, UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    obj = _get_visit(db, visit_id, user)
    data = payload.model_dump(exclude_unset=True)
    if "company_id" in data and data["company_id"] is not None:
        company = db.get(Company, data["company_id"])
        if not company or not company.osgb_id:
            raise HTTPException(400, "İşyeri bir OSGB'ye bağlı değil.")
        ensure_company_access(db, user, data["company_id"])
        # Saha personeli yalnız kendi görevli olduğu işyerine taşıyabilir
        if user.role in _FIELD_ROLES:
            ensure_company_access(db, user, data["company_id"])
        obj.company_id = data["company_id"]
        obj.osgb_id = company.osgb_id
        data.pop("company_id", None)
    for key, value in data.items():
        setattr(obj, key, value)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/visits/{visit_id}")
def delete_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*FIELD_VISIT_ROLES, UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    obj = _get_visit(db, visit_id, user)
    _delete_notebook_file(obj, db=db, user=user)
    db.delete(obj)
    db.commit()
    return {"ok": True, "id": visit_id}


@router.post("/visits/{visit_id}/notebook", response_model=VisitResponse)
async def upload_visit_notebook(
    visit_id: int,
    file: UploadFile = File(...),
    gps_lat: float | None = Form(default=None),
    gps_lng: float | None = Form(default=None),
    gps_accuracy_m: float | None = Form(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*FIELD_VISIT_ROLES, UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
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
        _delete_notebook_file(obj, db=db, user=user)
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
    _apply_gps_stamp(obj, gps_lat, gps_lng, gps_accuracy_m)
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
def complete_visit(
    visit_id: int,
    payload: VisitGpsStamp | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*FIELD_VISIT_ROLES)),
):
    obj = _get_visit(db, visit_id, user)
    stamp = payload or VisitGpsStamp()
    _apply_gps_stamp(obj, stamp.gps_lat, stamp.gps_lng, stamp.gps_accuracy_m)
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
