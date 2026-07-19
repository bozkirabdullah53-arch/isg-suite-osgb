from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, require_roles
from app.core.config import settings
from app.core.database import get_db
from app.models.entities import (AssignmentStatus, Company, IsgProfessional, OsgbOrganization, ServiceContract,
                                 User, UserRole, WorkplaceAssignment)
from app.schemas.osgb import (AssignmentCreate, AssignmentResponse, ContractCreate,
                              ContractResponse, OsgbCreate, OsgbResponse,
                              ProfessionalCreate, ProfessionalResponse, ProfessionalUpdate)
from app.services.osgb_oversight import build_oversight, build_professional_performance, seed_oversight_demo
from app.services.csgb_audit_pack import build_csgb_audit_pack

router = APIRouter(prefix="/osgb", tags=["OSGB Yönetimi"])
ADMIN_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)

def _scope_osgb(user: User, osgb_id: int) -> None:
    if user.role != UserRole.GLOBAL_ADMIN and user.osgb_id != osgb_id:
        raise HTTPException(403, "Bu OSGB kaydına erişim yetkiniz yok.")

@router.get("", response_model=list[OsgbResponse])
def list_osgb(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(OsgbOrganization).order_by(OsgbOrganization.name)
    if user.role != UserRole.GLOBAL_ADMIN:
        stmt = stmt.where(OsgbOrganization.id == user.osgb_id)
    return list(db.scalars(stmt).all())

@router.post("", response_model=OsgbResponse)
def create_osgb(payload: OsgbCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN))):
    if db.scalar(select(OsgbOrganization).where(OsgbOrganization.name == payload.name)):
        raise HTTPException(409, "Bu OSGB zaten kayıtlı.")
    obj = OsgbOrganization(**payload.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.get("/oversight")
def osgb_oversight(
    osgb_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """OSGB yönetimi — profesyonel sorumluluk / 6331 hizmet denetimi."""
    if user.role != UserRole.GLOBAL_ADMIN:
        osgb_id = user.osgb_id
    return build_oversight(db, osgb_id=osgb_id)


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


@router.get("/csgb-audit-pack")
def csgb_audit_pack(
    osgb_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """ÇSGB OSGB denetimi — müfettiş belge paketi hazırlık durumu."""
    if user.role != UserRole.GLOBAL_ADMIN:
        osgb_id = user.osgb_id
    return build_csgb_audit_pack(db, osgb_id=osgb_id)


@router.get("/professionals/{professional_id}/performance")
def professional_performance(
    professional_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """Seçilen uzman/hekim/DSP için iş tamamlama / performans raporu."""
    pro = db.get(IsgProfessional, professional_id)
    if not pro:
        raise HTTPException(404, "Profesyonel bulunamadı.")
    if user.role != UserRole.GLOBAL_ADMIN and pro.osgb_id != user.osgb_id:
        raise HTTPException(403, "Bu profesyonelin performansına erişim yetkiniz yok.")
    try:
        return build_professional_performance(db, professional_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/professionals", response_model=list[ProfessionalResponse])
def list_professionals(osgb_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    target = osgb_id if user.role == UserRole.GLOBAL_ADMIN else user.osgb_id
    if not target: return []
    _scope_osgb(user, target)
    return list(db.scalars(select(IsgProfessional).where(IsgProfessional.osgb_id == target).order_by(IsgProfessional.full_name)).all())

@router.post("/professionals", response_model=ProfessionalResponse)
def create_professional(payload: ProfessionalCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN_ROLES))):
    _scope_osgb(user, payload.osgb_id)
    obj = IsgProfessional(**payload.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


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
    if user.role != UserRole.GLOBAL_ADMIN:
        if not user.osgb_id: return []
        stmt = stmt.where(WorkplaceAssignment.osgb_id == user.osgb_id)
    if company_id: stmt = stmt.where(WorkplaceAssignment.company_id == company_id)
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
    obj = WorkplaceAssignment(**payload.model_dump())
    db.add(obj)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409,
            "Bu profesyonel bu işyerine aynı görev türüyle zaten atanmış. Mevcut kaydı kontrol edin.",
        ) from None
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


@router.get("/contracts", response_model=list[ContractResponse])
def list_contracts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(ServiceContract)
    if user.role != UserRole.GLOBAL_ADMIN:
        if not user.osgb_id: return []
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
