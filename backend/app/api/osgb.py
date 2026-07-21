from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.company_access import find_professional_for_user, link_user_to_professional
from app.api.deps import get_current_user, require_roles
from app.core.config import settings
from app.core.database import get_db
from app.models.entities import (AssignmentStatus, Company, IsgProfessional, OsgbOrganization, ServiceContract,
                                 User, UserRole, WorkplaceAssignment)
from app.schemas.osgb import (AssignmentCreate, AssignmentResponse, ContractCreate,
                              ContractResponse, OsgbCreate, OsgbResponse, OsgbUpdate,
                              ProfessionalCreate, ProfessionalCreateResponse, ProfessionalLoginAccount,
                              ProfessionalResponse, ProfessionalUpdate)
from app.services.osgb_admin import provision_professional_login
from app.services.osgb_oversight import build_oversight, build_professional_performance, seed_oversight_demo
from app.services.csgb_audit_pack import build_csgb_audit_pack
from app.services.capacity_engine import build_capacity_overview, sync_assignment_required

router = APIRouter(prefix="/osgb", tags=["OSGB Yönetimi"])
ADMIN_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)

def _scope_osgb(user: User, osgb_id: int) -> None:
    if user.role != UserRole.GLOBAL_ADMIN and user.osgb_id != osgb_id:
        raise HTTPException(403, "Bu OSGB kaydına erişim yetkiniz yok.")

@router.get("", response_model=list[OsgbResponse])
def list_osgb(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(OsgbOrganization).order_by(OsgbOrganization.name)
    if user.role != UserRole.GLOBAL_ADMIN:
        oid = user.osgb_id
        if not oid:
            pro = find_professional_for_user(db, user)
            oid = pro.osgb_id if pro else None
        if not oid:
            return []
        stmt = stmt.where(OsgbOrganization.id == oid)
    return list(db.scalars(stmt).all())

@router.post("", response_model=OsgbResponse)
def create_osgb(payload: OsgbCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN))):
    if db.scalar(select(OsgbOrganization).where(OsgbOrganization.name == payload.name)):
        raise HTTPException(409, "Bu OSGB zaten kayıtlı.")
    obj = OsgbOrganization(**payload.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.patch("/{osgb_id}", response_model=OsgbResponse)
def update_osgb(
    osgb_id: int,
    payload: OsgbUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    if user.role == UserRole.COMPANY_ADMIN and user.osgb_id != osgb_id:
        raise HTTPException(403, "Yalnız kendi OSGB kaydınızı güncelleyebilirsiniz.")
    obj = db.get(OsgbOrganization, osgb_id)
    if not obj:
        raise HTTPException(404, "OSGB bulunamadı.")
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] != obj.name:
        if db.scalar(select(OsgbOrganization).where(OsgbOrganization.name == data["name"], OsgbOrganization.id != osgb_id)):
            raise HTTPException(409, "Bu OSGB adı zaten kayıtlı.")
    for k, v in data.items():
        if isinstance(v, str):
            v = v.strip() or None
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/oversight")
def osgb_oversight(
    osgb_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    """Profesyonel sorumluluk / 6331 hizmet denetimi — EİSA veya OSGB yöneticisi."""
    if user.role == UserRole.COMPANY_ADMIN:
        if not user.osgb_id:
            raise HTTPException(400, "OSGB kapsamınız tanımlı değil.")
        osgb_id = user.osgb_id
    return build_oversight(db, osgb_id=osgb_id)


@router.get("/capacity")
def osgb_capacity(
    osgb_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """6331 kapasite motoru — mevzuat asgari süre vs fiili saha yükü."""
    if user.role == UserRole.COMPANY_ADMIN:
        if not user.osgb_id:
            raise HTTPException(400, "OSGB kapsamınız tanımlı değil.")
        osgb_id = user.osgb_id
    return build_capacity_overview(db, osgb_id=osgb_id)


@router.post("/assignments/{assignment_id}/sync-required")
def sync_assignment_required_minutes(
    assignment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """Görevlendirme zorunlu dakikasını mevzuat tablosuna göre günceller."""
    obj = db.get(WorkplaceAssignment, assignment_id)
    if not obj:
        raise HTTPException(404, "Görevlendirme bulunamadı.")
    if user.role == UserRole.COMPANY_ADMIN and user.osgb_id != obj.osgb_id:
        raise HTTPException(403, "Bu görevlendirmeyi güncelleyemezsiniz.")
    legal = sync_assignment_required(db, obj)
    return {
        "ok": True,
        "assignment_id": assignment_id,
        "required_minutes_monthly": legal,
        "message": f"Zorunlu aylık süre mevzuata göre {legal} dk olarak güncellendi.",
    }


@router.post("/capacity/sync-all-required")
def sync_all_required_minutes(
    osgb_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """OSGB kapsamındaki tüm aktif görevlendirmelerin zorunlu dakikasını günceller."""
    if user.role == UserRole.COMPANY_ADMIN:
        if not user.osgb_id:
            raise HTTPException(400, "OSGB kapsamınız tanımlı değil.")
        osgb_id = user.osgb_id
    stmt = select(WorkplaceAssignment).where(WorkplaceAssignment.status == AssignmentStatus.ACTIVE)
    if osgb_id:
        stmt = stmt.where(WorkplaceAssignment.osgb_id == osgb_id)
    rows = list(db.scalars(stmt).all())
    updated = 0
    for a in rows:
        sync_assignment_required(db, a)
        updated += 1
    return {"ok": True, "updated": updated, "message": f"{updated} görevlendirme güncellendi."}


@router.post("/oversight/seed-demo")
def osgb_oversight_seed_demo(
    osgb_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    """Test uzman / hekim / DSP + kasıtlı eksiklikler oluşturur."""
    _ = user
    try:
        seeded = seed_oversight_demo(db, osgb_id=osgb_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    overview = build_oversight(db, osgb_id=seeded["osgb_id"])
    return {"seeded": seeded, "oversight_summary": overview.get("summary"), "gap_count": overview.get("gap_count")}


@router.post("/sync-field-roles")
def sync_field_roles(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    """Aktif görevlendirmedeki hekim/uzman/DSP kullanıcı rollerini eşle.

    Firma / OSGB admini yalnızca kendi OSGB kapsamında çalıştırabilir.
    """
    from app.api.company_access import sync_all_assigned_field_roles

    if user.role == UserRole.GLOBAL_ADMIN:
        return {"ok": True, **sync_all_assigned_field_roles(db)}
    if not user.osgb_id:
        raise HTTPException(400, "OSGB bağlantısı bulunamadı.")
    return {"ok": True, **sync_all_assigned_field_roles(db, osgb_id=user.osgb_id)}


@router.get("/csgb-audit-pack")
def csgb_audit_pack(
    osgb_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    """ÇSGB OSGB denetim paketi — EİSA veya kendi OSGB yöneticisi."""
    if user.role == UserRole.COMPANY_ADMIN:
        if not user.osgb_id:
            raise HTTPException(400, "Kullanıcıya bağlı OSGB yok.")
        osgb_id = user.osgb_id
    return build_csgb_audit_pack(db, osgb_id=osgb_id)


@router.get("/professionals/{professional_id}/performance")
def professional_performance(
    professional_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    """Seçilen uzman/hekim/DSP performans raporu — EİSA veya kendi OSGB yöneticisi."""
    pro = db.get(IsgProfessional, professional_id)
    if not pro:
        raise HTTPException(404, "Profesyonel bulunamadı.")
    if user.role == UserRole.COMPANY_ADMIN:
        if not user.osgb_id or pro.osgb_id != user.osgb_id:
            raise HTTPException(403, "Bu profesyonelin performansına erişemezsiniz.")
    try:
        return build_professional_performance(db, professional_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/professionals", response_model=list[ProfessionalResponse])
def list_professionals(osgb_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # Saha rolleri yalnızca kendi profesyonel kaydını görür
    if user.role in (
        UserRole.SAFETY_SPECIALIST,
        UserRole.WORKPLACE_PHYSICIAN,
        UserRole.OTHER_HEALTH_PERSONNEL,
    ):
        pro = find_professional_for_user(db, user)
        return [pro] if pro else []
    target = osgb_id if user.role == UserRole.GLOBAL_ADMIN else user.osgb_id
    if not target and user.role == UserRole.GLOBAL_ADMIN:
        target = db.scalar(select(OsgbOrganization.id).order_by(OsgbOrganization.id).limit(1))
    if not target:
        return []
    _scope_osgb(user, target)
    return list(db.scalars(select(IsgProfessional).where(IsgProfessional.osgb_id == target).order_by(IsgProfessional.full_name)).all())

@router.post("/professionals", response_model=ProfessionalCreateResponse)
def create_professional(payload: ProfessionalCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN_ROLES))):
    _scope_osgb(user, payload.osgb_id)
    obj = IsgProfessional(**payload.model_dump())
    db.add(obj)
    db.flush()
    wp_user, temp_password, created = provision_professional_login(db, obj)
    link_user_to_professional(db, obj)
    db.commit()
    db.refresh(obj)
    return ProfessionalCreateResponse(
        **ProfessionalResponse.model_validate(obj).model_dump(),
        login_account=ProfessionalLoginAccount(
            user_id=wp_user.id,
            email=wp_user.email,
            full_name=wp_user.full_name,
            temporary_password=temp_password,
            created=created,
            message=(
                "Giriş hesabı oluşturuldu."
                if created
                else "Mevcut hesaba yeni geçici şifre atandı."
            )
            + " Profesyonel e-posta ve bu şifre ile giriş yapar; isterse Güvenlik menüsünden değiştirir.",
        ),
    )


@router.patch("/professionals/{professional_id}/suspend")
def suspend_professional(professional_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN_ROLES))):
    obj = db.get(IsgProfessional, professional_id)
    if not obj:
        raise HTTPException(404, "Profesyonel bulunamadı.")
    _scope_osgb(user, obj.osgb_id)
    obj.is_active = False
    db.commit()
    return {"ok": True, "id": professional_id, "is_active": False, "message": "Profesyonel askıya alındı."}


@router.patch("/professionals/{professional_id}/activate")
def activate_professional(professional_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN_ROLES))):
    obj = db.get(IsgProfessional, professional_id)
    if not obj:
        raise HTTPException(404, "Profesyonel bulunamadı.")
    _scope_osgb(user, obj.osgb_id)
    obj.is_active = True
    link_user_to_professional(db, obj)
    db.commit()
    return {"ok": True, "id": professional_id, "is_active": True, "message": "Profesyonel aktifleştirildi."}


@router.patch("/professionals/{professional_id}", response_model=ProfessionalResponse)
def update_professional(
    professional_id: int,
    payload: ProfessionalUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    obj = db.get(IsgProfessional, professional_id)
    if not obj:
        raise HTTPException(404, "Profesyonel bulunamadı.")
    _scope_osgb(user, obj.osgb_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    link_user_to_professional(db, obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/professionals/{professional_id}")
def delete_professional(professional_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN_ROLES))):
    obj = db.get(IsgProfessional, professional_id)
    if not obj:
        raise HTTPException(404, "Profesyonel bulunamadı.")
    _scope_osgb(user, obj.osgb_id)
    active_assign = db.scalar(
        select(WorkplaceAssignment).where(
            WorkplaceAssignment.professional_id == professional_id,
            WorkplaceAssignment.status == AssignmentStatus.ACTIVE,
        ).limit(1)
    )
    if active_assign:
        raise HTTPException(
            400,
            "Aktif görevlendirmesi olan profesyonel silinemez. Önce görevlendirmeleri sonlandırın veya askıya alın.",
        )
    try:
        db.delete(obj)
        db.commit()
    except IntegrityError:
        db.rollback()
        # Geçmiş ziyaret/görevlendirme varsa soft-delete
        obj.is_active = False
        db.commit()
        return {
            "ok": True,
            "id": professional_id,
            "soft_deleted": True,
            "message": "Bağlı kayıtlar nedeniyle kalıcı silinemedi; askıya alındı.",
        }
    return {"ok": True, "id": professional_id, "message": "Profesyonel silindi."}


@router.get("/assignments", response_model=list[AssignmentResponse])
def list_assignments(company_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(WorkplaceAssignment)
    if user.role in (
        UserRole.SAFETY_SPECIALIST,
        UserRole.WORKPLACE_PHYSICIAN,
        UserRole.OTHER_HEALTH_PERSONNEL,
    ):
        pro = find_professional_for_user(db, user)
        if not pro:
            return []
        stmt = stmt.where(WorkplaceAssignment.professional_id == pro.id)
    elif user.role != UserRole.GLOBAL_ADMIN:
        if not user.osgb_id:
            return []
        stmt = stmt.where(WorkplaceAssignment.osgb_id == user.osgb_id)
    if company_id:
        stmt = stmt.where(WorkplaceAssignment.company_id == company_id)
    return list(db.scalars(stmt.order_by(WorkplaceAssignment.start_date.desc())).all())

ALLOWED_CONTRACT = {".pdf", ".jpg", ".jpeg", ".png"}


def _upload_root() -> Path:
    root = Path(settings.upload_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _get_assignment(db: Session, assignment_id: int, user: User) -> WorkplaceAssignment:
    obj = db.get(WorkplaceAssignment, assignment_id)
    if not obj:
        raise HTTPException(404, "Görevlendirme bulunamadı.")
    if user.role in (
        UserRole.SAFETY_SPECIALIST,
        UserRole.WORKPLACE_PHYSICIAN,
        UserRole.OTHER_HEALTH_PERSONNEL,
    ):
        pro = find_professional_for_user(db, user)
        if not pro or obj.professional_id != pro.id:
            raise HTTPException(403, "Bu görevlendirmeye erişim yetkiniz yok.")
        return obj
    _scope_osgb(user, obj.osgb_id)
    return obj


@router.post("/assignments", response_model=AssignmentResponse)
def create_assignment(payload: AssignmentCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN_ROLES))):
    _scope_osgb(user, payload.osgb_id)
    katip = (payload.isg_katip_contract_number or "").strip()
    if not katip:
        raise HTTPException(400, "İSG-KATİP sözleşme numarası zorunludur.")
    payload = payload.model_copy(update={"isg_katip_contract_number": katip})
    company = db.get(Company, payload.company_id)
    professional = db.get(IsgProfessional, payload.professional_id)
    if not company:
        raise HTTPException(400, "İşyeri bulunamadı.")
    if not professional:
        raise HTTPException(400, "Profesyonel bulunamadı.")
    if professional.osgb_id != payload.osgb_id:
        raise HTTPException(400, "Profesyonel bu OSGB'ye bağlı değil.")
    # Global yönetici: işyerinin OSGB bağı yoksa görevlendirme ile bağla
    if company.osgb_id is None:
        if user.role != UserRole.GLOBAL_ADMIN:
            raise HTTPException(400, "İşyeri bir OSGB'ye bağlı değil. Önce işyerini OSGB'ye bağlayın.")
        company.osgb_id = payload.osgb_id
    elif company.osgb_id != payload.osgb_id:
        raise HTTPException(
            400,
            "İşyeri başka bir OSGB'ye bağlı. Görevlendirme için aynı OSGB'deki işyerini seçin "
            "veya işyerinin OSGB bağlantısını güncelleyin.",
        )
    if professional.professional_type != payload.professional_type:
        payload = payload.model_copy(update={"professional_type": professional.professional_type})
    existing = db.scalar(
        select(WorkplaceAssignment).where(
            WorkplaceAssignment.company_id == payload.company_id,
            WorkplaceAssignment.professional_id == payload.professional_id,
            WorkplaceAssignment.professional_type == payload.professional_type,
        ).limit(1)
    )
    if existing:
        if existing.status == AssignmentStatus.ACTIVE:
            raise HTTPException(
                409,
                "Bu profesyonel bu işyerine aynı görev türüyle zaten atanmış. Mevcut kaydı kontrol edin.",
            )
        # Sonlanmış / askıdaki kaydı yeniden aktifleştir
        data = payload.model_dump()
        for k, v in data.items():
            if k in ("company_id", "professional_id", "professional_type", "osgb_id"):
                continue
            setattr(existing, k, v)
        existing.status = AssignmentStatus.ACTIVE
        existing.end_date = payload.end_date
        link_user_to_professional(db, professional)
        db.commit()
        try:
            from app.api.company_access import sync_all_assigned_field_roles
            sync_all_assigned_field_roles(db)
        except Exception:
            pass
        db.refresh(existing)
        return existing
    obj = WorkplaceAssignment(**payload.model_dump())
    db.add(obj)
    link_user_to_professional(db, professional)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409,
            "Bu profesyonel bu işyerine aynı görev türüyle zaten atanmış. Mevcut kaydı kontrol edin.",
        ) from None
    try:
        from app.api.company_access import sync_all_assigned_field_roles
        sync_all_assigned_field_roles(db)
    except Exception:
        pass
    db.refresh(obj)
    return obj


@router.post("/assignments/{assignment_id}/contract", response_model=AssignmentResponse)
async def upload_assignment_contract(
    assignment_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    obj = _get_assignment(db, assignment_id, user)
    name = file.filename or "sozlesme.pdf"
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_CONTRACT:
        raise HTTPException(422, "Sadece pdf, jpg veya png yükleyin.")
    data = await file.read()
    if not data:
        raise HTTPException(400, "Boş dosya yüklenemez.")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"Dosya {settings.max_upload_mb} MB sınırını aşıyor.")
    if obj.contract_storage_path:
        old = (_upload_root() / obj.contract_storage_path).resolve()
        if _upload_root() in old.parents and old.exists():
            try:
                from app.services.archive_store import archive_file_before_delete

                archive_file_before_delete(
                    db,
                    source=old,
                    user=user,
                    company_id=obj.company_id,
                    osgb_id=obj.osgb_id,
                    entity_type="assignment_contract",
                    entity_id=str(obj.id),
                    original_name=obj.contract_file_name,
                    notes="Görev sözleşmesi değiştirilmeden önce arşivlendi",
                )
            except Exception:
                pass
            try:
                old.unlink()
            except OSError:
                pass
    rel = f"{obj.osgb_id}/assignments/{obj.id}_{uuid4().hex[:10]}{ext}"
    target = _upload_root() / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    obj.contract_file_name = name
    obj.contract_storage_path = rel.replace("\\", "/")
    obj.contract_content_type = file.content_type or {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
    }.get(ext, "application/octet-stream")
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/assignments/{assignment_id}/contract")
def download_assignment_contract(
    assignment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    obj = _get_assignment(db, assignment_id, user)
    if not obj.contract_storage_path:
        raise HTTPException(404, "Sözleşme dosyası yok.")
    path = (_upload_root() / obj.contract_storage_path).resolve()
    if _upload_root() not in path.parents or not path.exists():
        raise HTTPException(404, "Dosya bulunamadı.")
    return FileResponse(
        path,
        media_type=obj.contract_content_type or "application/octet-stream",
        filename=obj.contract_file_name or path.name,
    )


@router.patch("/assignments/{assignment_id}/suspend", response_model=AssignmentResponse)
def suspend_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    obj = _get_assignment(db, assignment_id, user)
    if obj.status == AssignmentStatus.ENDED:
        raise HTTPException(400, "Sonlandırılmış görevlendirme askıya alınamaz. Yeniden aktifleştirin veya silin.")
    obj.status = AssignmentStatus.SUSPENDED
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/assignments/{assignment_id}/activate", response_model=AssignmentResponse)
def activate_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    obj = _get_assignment(db, assignment_id, user)
    obj.status = AssignmentStatus.ACTIVE
    if obj.end_date:
        obj.end_date = None
    db.commit()
    db.refresh(obj)
    try:
        from app.api.company_access import sync_all_assigned_field_roles
        sync_all_assigned_field_roles(db)
    except Exception:
        pass
    return obj


@router.patch("/assignments/{assignment_id}/end", response_model=AssignmentResponse)
def end_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """Görevlendirmeyi sonlandır (bitiş tarihi bugün)."""
    from datetime import date as date_cls

    obj = _get_assignment(db, assignment_id, user)
    obj.status = AssignmentStatus.ENDED
    obj.end_date = date_cls.today()
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/assignments/{assignment_id}")
def delete_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """Kalıcı sil. Bağlı kayıt varsa sonlandırır."""
    from datetime import date as date_cls

    obj = _get_assignment(db, assignment_id, user)
    aid = obj.id
    try:
        db.delete(obj)
        db.commit()
    except IntegrityError:
        db.rollback()
        obj = db.get(WorkplaceAssignment, aid)
        if not obj:
            raise HTTPException(404, "Görevlendirme bulunamadı.") from None
        obj.status = AssignmentStatus.ENDED
        obj.end_date = obj.end_date or date_cls.today()
        db.commit()
        return {
            "ok": True,
            "id": aid,
            "status": obj.status.value,
            "soft_ended": True,
            "message": "Bağlı kayıtlar nedeniyle silinemedi; görevlendirme sonlandırıldı.",
        }
    return {"ok": True, "id": aid, "message": "Görevlendirme silindi."}


@router.get("/contracts", response_model=list[ContractResponse])
def list_contracts(db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN_ROLES))):
    stmt = select(ServiceContract)
    if user.role != UserRole.GLOBAL_ADMIN:
        if not user.osgb_id:
            return []
        stmt = stmt.where(ServiceContract.osgb_id == user.osgb_id)
    return list(db.scalars(stmt.order_by(ServiceContract.start_date.desc())).all())

@router.post("/contracts", response_model=ContractResponse)
def create_contract(payload: ContractCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN_ROLES))):
    _scope_osgb(user, payload.osgb_id)
    company = db.get(Company, payload.company_id)
    if not company or company.osgb_id != payload.osgb_id: raise HTTPException(400, "İşyeri bu OSGB'ye bağlı değil.")
    obj = ServiceContract(**payload.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj
