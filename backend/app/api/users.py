from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.entities import User, UserRole
from app.schemas.user import UserCreate, UserResponse, UserUpdate
router=APIRouter(prefix="/users",tags=["Kullanıcılar"])

@router.get("",response_model=list[UserResponse])
def list_users(db:Session=Depends(get_db),current:User=Depends(require_roles(UserRole.GLOBAL_ADMIN,UserRole.COMPANY_ADMIN))):
    stmt=select(User).order_by(User.full_name)
    if current.role!=UserRole.GLOBAL_ADMIN: stmt=stmt.where(User.company_id==current.company_id)
    return list(db.scalars(stmt).all())

@router.post("",response_model=UserResponse)
def create_user(payload:UserCreate,db:Session=Depends(get_db),current:User=Depends(require_roles(UserRole.GLOBAL_ADMIN,UserRole.COMPANY_ADMIN))):
    if db.scalar(select(User).where(User.email==payload.email)): raise HTTPException(409,"Bu e-posta kullanılıyor.")
    if current.role!=UserRole.GLOBAL_ADMIN:
        if payload.company_id!=current.company_id or payload.role==UserRole.GLOBAL_ADMIN: raise HTTPException(403,"Bu kullanıcıyı oluşturamazsınız.")
    if payload.role!=UserRole.GLOBAL_ADMIN and not payload.company_id: raise HTTPException(422,"Firma seçilmelidir.")
    obj=User(email=payload.email,full_name=payload.full_name,hashed_password=get_password_hash(payload.password),role=payload.role,company_id=payload.company_id)
    db.add(obj);db.commit();db.refresh(obj);return obj

@router.put("/{user_id}",response_model=UserResponse)
def update_user(user_id:int,payload:UserUpdate,db:Session=Depends(get_db),current:User=Depends(require_roles(UserRole.GLOBAL_ADMIN,UserRole.COMPANY_ADMIN))):
    obj=db.get(User,user_id)
    if not obj: raise HTTPException(404,"Kullanıcı bulunamadı.")
    if current.role!=UserRole.GLOBAL_ADMIN and (obj.company_id!=current.company_id or payload.role==UserRole.GLOBAL_ADMIN): raise HTTPException(403,"Bu kullanıcıyı değiştiremezsiniz.")
    data=payload.model_dump(exclude_unset=True); password=data.pop("password",None)
    for k,v in data.items(): setattr(obj,k,v)
    if password: obj.hashed_password=get_password_hash(password)
    db.commit();db.refresh(obj);return obj

@router.patch("/{user_id}/suspend")
def suspend_user(user_id: int, db: Session = Depends(get_db), current: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN))):
    obj = db.get(User, user_id)
    if not obj:
        raise HTTPException(404, "Kullanıcı bulunamadı.")
    if obj.id == current.id:
        raise HTTPException(400, "Kendi hesabınızı askıya alamazsınız.")
    if current.role != UserRole.GLOBAL_ADMIN and obj.company_id != current.company_id:
        raise HTTPException(403, "Bu kullanıcıyı değiştiremezsiniz.")
    if obj.role == UserRole.GLOBAL_ADMIN and current.role != UserRole.GLOBAL_ADMIN:
        raise HTTPException(403, "Global yöneticiyi askıya alamazsınız.")
    obj.is_active = False
    db.commit()
    return {"ok": True, "id": user_id, "is_active": False, "message": "Kullanıcı askıya alındı."}


@router.patch("/{user_id}/activate")
def activate_user(user_id: int, db: Session = Depends(get_db), current: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN))):
    obj = db.get(User, user_id)
    if not obj:
        raise HTTPException(404, "Kullanıcı bulunamadı.")
    if current.role != UserRole.GLOBAL_ADMIN and obj.company_id != current.company_id:
        raise HTTPException(403, "Bu kullanıcıyı değiştiremezsiniz.")
    obj.is_active = True
    db.commit()
    return {"ok": True, "id": user_id, "is_active": True, "message": "Kullanıcı yeniden aktifleştirildi."}


@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), current: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN))):
    """Kalıcı silme. Kendi hesabı ve son global yönetici silinemez."""
    obj = db.get(User, user_id)
    if not obj:
        raise HTTPException(404, "Kullanıcı bulunamadı.")
    if obj.id == current.id:
        raise HTTPException(400, "Kendi hesabınızı silemezsiniz.")
    if current.role != UserRole.GLOBAL_ADMIN and obj.company_id != current.company_id:
        raise HTTPException(403, "Bu kullanıcıyı silemezsiniz.")
    if obj.role == UserRole.GLOBAL_ADMIN:
        if current.role != UserRole.GLOBAL_ADMIN:
            raise HTTPException(403, "Global yöneticiyi silemezsiniz.")
        other_admins = db.scalar(
            select(User).where(User.role == UserRole.GLOBAL_ADMIN, User.id != obj.id, User.is_active.is_(True)).limit(1)
        )
        if not other_admins:
            raise HTTPException(400, "Sistemde en az bir aktif global yönetici kalmalıdır.")
    db.delete(obj)
    db.commit()
    return {"ok": True, "id": user_id, "message": "Kullanıcı silindi."}
