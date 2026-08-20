from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.company_access import assigned_company_ids
from app.api.tenant_access import accessible_company_ids_for_admin
from app.core.database import get_db
from app.models.entities import Notification, User, UserRole
from app.services.notifications import (
    rebuild_all_notifications,
    rebuild_company_notifications,
    rebuild_specialist_notifications,
)

router = APIRouter(prefix="/notifications", tags=["Bildirimler"])

_CLINICAL_NOTIFICATION_TYPES = {"health_record"}
_HEALTH_ROLES = {UserRole.WORKPLACE_PHYSICIAN, UserRole.OTHER_HEALTH_PERSONNEL}


def _notification_company_ids(db: Session, user: User) -> list[int]:
    if user.role == UserRole.COMPANY_ADMIN:
        return accessible_company_ids_for_admin(db, user)
    if user.role in (
        UserRole.SAFETY_SPECIALIST,
        UserRole.WORKPLACE_PHYSICIAN,
        UserRole.OTHER_HEALTH_PERSONNEL,
    ):
        return assigned_company_ids(db, user)
    if user.company_id:
        return [user.company_id]
    return []


def _can_see_notification(user: User, item: Notification) -> bool:
    """Klinik bildirimler yalnız hekim/DSP akışında görünür."""
    return not (
        item.entity_type in _CLINICAL_NOTIFICATION_TYPES
        and user.role not in _HEALTH_ROLES
    )


@router.get("")
def list_notifications(
    unread_only: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    clinical_filter = None
    if user.role not in _HEALTH_ROLES:
        clinical_filter = or_(
            Notification.entity_type.is_(None),
            Notification.entity_type.notin_(tuple(_CLINICAL_NOTIFICATION_TYPES)),
        )
    if user.role == UserRole.GLOBAL_ADMIN:
        stmt = select(Notification)
        if clinical_filter is not None:
            stmt = stmt.where(clinical_filter)
        stmt = stmt.order_by(Notification.created_at.desc()).limit(300)
    else:
        company_ids = _notification_company_ids(db, user)
        conds = [Notification.user_id == user.id]
        if company_ids:
            conds.append(Notification.company_id.in_(company_ids))
        stmt = (
            select(Notification)
            .where(
                and_(or_(*conds), clinical_filter)
                if clinical_filter is not None
                else or_(*conds)
            )
            .order_by(Notification.created_at.desc())
            .limit(200)
        )
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    return list(db.scalars(stmt).all())


@router.post("/refresh")
def refresh_notifications(
    osgb_id: int | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Süre / termin kontrolü — yalnızca kendi OSGB / firma kapsamı."""
    if user.role == UserRole.GLOBAL_ADMIN:
        count = rebuild_all_notifications(db, osgb_id=osgb_id)
        return {"message": "OSGB ve işyeri süreleri tarandı.", "count": count}

    if user.role == UserRole.COMPANY_ADMIN:
        oid = user.osgb_id
        if osgb_id is not None and oid and osgb_id != oid:
            raise HTTPException(403, "Başka bir OSGB için bildirim taraması yapamazsınız.")
        if oid:
            count = rebuild_all_notifications(db, osgb_id=oid, company_id=user.company_id)
        elif user.company_id:
            count = rebuild_company_notifications(db, user.company_id)
        else:
            raise HTTPException(400, "OSGB veya firma bağlantısı bulunamadı.")
        return {"message": "Bildirimler güncellendi.", "count": count}

    if user.role == UserRole.SAFETY_SPECIALIST:
        company_ids = _notification_company_ids(db, user)
        if not company_ids:
            raise HTTPException(400, "Aktif işyeri görevlendirmesi bulunamadı.")
        count = sum(rebuild_company_notifications(db, cid) for cid in company_ids)
        count += rebuild_specialist_notifications(db, user)
        return {"message": "Uzman bildirimleri güncellendi.", "count": count}

    company_ids = _notification_company_ids(db, user)
    if not company_ids:
        raise HTTPException(400, "Aktif işyeri görevlendirmesi bulunamadı.")
    count = sum(rebuild_company_notifications(db, cid) for cid in company_ids)
    return {"message": "Bildirimler güncellendi.", "count": count}


@router.patch("/{notification_id}/read")
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = db.get(Notification, notification_id)
    if not item:
        raise HTTPException(status_code=404, detail="Bildirim bulunamadı.")
    if not _can_see_notification(user, item):
        raise HTTPException(status_code=403, detail="Bu klinik bildirime erişemezsiniz.")
    if user.role == UserRole.GLOBAL_ADMIN:
        pass
    elif item.user_id == user.id:
        pass
    elif item.company_id:
        allowed = _notification_company_ids(db, user)
        if item.company_id not in allowed:
            raise HTTPException(status_code=403, detail="Bu bildirime erişemezsiniz.")
    else:
        # user_id yok + company_id yok → yalnızca global
        raise HTTPException(status_code=403, detail="Bu bildirime erişemezsiniz.")
    item.is_read = True
    db.commit()
    return {"message": "Bildirim okundu."}


@router.patch("/{notification_id}/complete")
def mark_completed(
    notification_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = db.get(Notification, notification_id)
    if not item:
        raise HTTPException(status_code=404, detail="Bildirim bulunamadı.")
    if not _can_see_notification(user, item):
        raise HTTPException(status_code=403, detail="Bu klinik bildirime erişemezsiniz.")
    if user.role != UserRole.GLOBAL_ADMIN:
        if item.user_id == user.id:
            pass
        elif item.company_id:
            if item.company_id not in _notification_company_ids(db, user):
                raise HTTPException(status_code=403, detail="Bu bildirime erişemezsiniz.")
        else:
            raise HTTPException(status_code=403, detail="Bu bildirime erişemezsiniz.")
    item.is_completed = True
    db.commit()
    return {"message": "Bildirim tamamlandı."}
