from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.api.tenant_access import (
    assert_can_manage_user,
    assert_company_in_admin_scope,
    users_scope_filter,
)
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.entities import (
    AnnualPlanItem,
    AuditLog,
    DocumentRecord,
    HealthRecord,
    IncidentDof,
    IncidentEvent,
    IsgRecord,
    Notification,
    PpeAssignment,
    RiskAssessment,
    RiskDof,
    RiskMedia,
    TrainingSession,
    User,
    UserRole,
)
from app.schemas.user import UserCreate, UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["Kullanıcılar"])

_REASSIGN_CREATED_BY = (
    AnnualPlanItem,
    HealthRecord,
    DocumentRecord,
    IsgRecord,
    TrainingSession,
    RiskAssessment,
    RiskMedia,
    RiskDof,
    IncidentEvent,
    IncidentDof,
    PpeAssignment,
)

_FIELD_ROLES = {
    UserRole.SAFETY_SPECIALIST,
    UserRole.WORKPLACE_PHYSICIAN,
    UserRole.OTHER_HEALTH_PERSONNEL,
}


def _detach_user_refs(db: Session, user_id: int, successor_id: int) -> None:
    for model in _REASSIGN_CREATED_BY:
        db.execute(
            update(model).where(model.created_by_id == user_id).values(created_by_id=successor_id)
        )
    db.execute(update(AuditLog).where(AuditLog.user_id == user_id).values(user_id=None))
    db.execute(update(Notification).where(Notification.user_id == user_id).values(user_id=None))


@router.get("", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    stmt = select(User).order_by(User.full_name)
    scope = users_scope_filter(db, current)
    if scope is not None:
        stmt = stmt.where(scope)
    return list(db.scalars(stmt).all())


@router.post("", response_model=UserResponse)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(409, "Bu e-posta kullanılıyor.")
    if current.role != UserRole.GLOBAL_ADMIN:
        if payload.role == UserRole.GLOBAL_ADMIN:
            raise HTTPException(403, "Bu kullanıcıyı oluşturamazsınız.")
        assert_company_in_admin_scope(db, current, payload.company_id)
        if payload.role not in _FIELD_ROLES and not payload.company_id and not current.osgb_id:
            raise HTTPException(422, "Firma seçilmelidir.")
        if payload.role not in _FIELD_ROLES and not payload.company_id and current.osgb_id:
            # OSGB admin firma seçmeden yalnızca kendi OSGB kapsamlı company_admin açabilir
            if payload.role != UserRole.COMPANY_ADMIN:
                raise HTTPException(422, "Firma seçilmelidir.")
    elif payload.role != UserRole.GLOBAL_ADMIN and not payload.company_id and payload.role not in _FIELD_ROLES:
        raise HTTPException(422, "Firma seçilmelidir.")

    osgb_id = None
    if current.role == UserRole.GLOBAL_ADMIN:
        osgb_id = None
    else:
        osgb_id = current.osgb_id

    obj = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
        role=payload.role,
        company_id=payload.company_id,
        osgb_id=osgb_id,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    obj = db.get(User, user_id)
    if not obj:
        raise HTTPException(404, "Kullanıcı bulunamadı.")
    assert_can_manage_user(db, current, obj)
    if current.role != UserRole.GLOBAL_ADMIN and payload.role == UserRole.GLOBAL_ADMIN:
        raise HTTPException(403, "Bu kullanıcıyı değiştiremezsiniz.")

    data = payload.model_dump(exclude_unset=True)
    password = data.pop("password", None)

    if "company_id" in data and current.role != UserRole.GLOBAL_ADMIN:
        new_company_id = data["company_id"]
        assert_company_in_admin_scope(db, current, new_company_id)
        # Tenant dışına taşımayı engelle
        if new_company_id is None and not current.osgb_id:
            raise HTTPException(403, "Firma bağlantısı kaldırılamaz.")

    for k, v in data.items():
        setattr(obj, k, v)
    if password:
        obj.hashed_password = get_password_hash(password)
    # OSGB admin kapsamı korunur
    if current.role != UserRole.GLOBAL_ADMIN and current.osgb_id and not obj.osgb_id:
        obj.osgb_id = current.osgb_id
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/{user_id}/suspend")
def suspend_user(
    user_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    obj = db.get(User, user_id)
    if not obj:
        raise HTTPException(404, "Kullanıcı bulunamadı.")
    if obj.id == current.id:
        raise HTTPException(400, "Kendi hesabınızı askıya alamazsınız.")
    assert_can_manage_user(db, current, obj)
    obj.is_active = False
    db.commit()
    return {"ok": True, "id": user_id, "is_active": False, "message": "Kullanıcı askıya alındı."}


@router.patch("/{user_id}/activate")
def activate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    obj = db.get(User, user_id)
    if not obj:
        raise HTTPException(404, "Kullanıcı bulunamadı.")
    assert_can_manage_user(db, current, obj)
    obj.is_active = True
    db.commit()
    return {"ok": True, "id": user_id, "is_active": True, "message": "Kullanıcı yeniden aktifleştirildi."}


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    obj = db.get(User, user_id)
    if not obj:
        raise HTTPException(404, "Kullanıcı bulunamadı.")
    if obj.id == current.id:
        raise HTTPException(400, "Kendi hesabınızı silemezsiniz.")
    assert_can_manage_user(db, current, obj)
    if obj.role == UserRole.GLOBAL_ADMIN:
        other_admins = db.scalar(
            select(User).where(
                User.role == UserRole.GLOBAL_ADMIN,
                User.id != obj.id,
                User.is_active.is_(True),
            ).limit(1)
        )
        if not other_admins:
            raise HTTPException(400, "Sistemde en az bir aktif global yönetici kalmalıdır.")

    try:
        _detach_user_refs(db, obj.id, current.id)
        db.delete(obj)
        db.commit()
    except IntegrityError:
        db.rollback()
        obj = db.get(User, user_id)
        if obj:
            obj.is_active = False
            db.commit()
            return {
                "ok": True,
                "id": user_id,
                "is_active": False,
                "message": "Kullanıcıya bağlı kayıtlar var; kalıcı silinemedi, askıya alındı.",
            }
        raise HTTPException(
            409,
            "Kullanıcı silinemedi: bağlı kayıtlar (ör. yıllık plan) mevcut. Önce Askıya Al kullanın.",
        ) from None
    return {"ok": True, "id": user_id, "message": "Kullanıcı silindi."}
