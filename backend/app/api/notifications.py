from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.company_access import assigned_company_ids
from app.api.tenant_access import accessible_company_ids_for_admin
from app.core.database import get_db
from app.models.entities import Company, Notification, User, UserRole
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


def _resolve_notification_company_id(
    db: Session,
    user: User,
    company_id: int | None,
) -> int | None:
    """Validate an optional company filter without widening notification scope."""
    if company_id is None:
        return None
    if user.role == UserRole.GLOBAL_ADMIN:
        if not db.get(Company, company_id):
            raise HTTPException(status_code=404, detail="Firma bulunamadı.")
        return company_id

    if company_id not in _notification_company_ids(db, user):
        raise HTTPException(
            status_code=403,
            detail="Bu firmaya ait bildirimlere erişemezsiniz.",
        )
    return company_id


def _can_see_notification(user: User, item: Notification) -> bool:
    """Klinik bildirimler yalnız hekim/DSP akışında görünür."""
    return not (
        item.entity_type in _CLINICAL_NOTIFICATION_TYPES
        and user.role not in _HEALTH_ROLES
    )


def _can_access_notification(db: Session, user: User, item: Notification) -> bool:
    """Private user notifications must never become company-wide rows."""
    if user.role == UserRole.GLOBAL_ADMIN:
        return True
    allowed_company_ids = _notification_company_ids(db, user)

    # Uzman görev bildirimleri kişiseldir. Eski kayıtlarda user_id boş kalmışsa
    # bunlar işyeri yöneticisine şirket-geneli bildirim gibi görünmemelidir.
    if item.entity_type == "specialist_duty":
        return bool(
            user.role == UserRole.SAFETY_SPECIALIST
            and item.user_id == user.id
            and item.company_id in allowed_company_ids
        )

    if item.company_id is None:
        return item.user_id == user.id
    if item.company_id not in allowed_company_ids:
        return False
    # Aynı işyerindeki kullanıcıya özel bildirimler yalnız sahibine aittir;
    # user_id boş şirket bildirimleri ise yetkili işyeri hesabına açıktır.
    return item.user_id in (None, user.id)


def _specialist_duty_visibility(user: User):
    """Keep specialist-only rows out of workplace/management notification feeds."""
    if user.role == UserRole.SAFETY_SPECIALIST:
        return or_(
            Notification.entity_type.is_(None),
            Notification.entity_type != "specialist_duty",
            Notification.user_id == user.id,
        )
    return or_(
        Notification.entity_type.is_(None),
        Notification.entity_type != "specialist_duty",
    )


@router.get("")
def list_notifications(
    unread_only: bool = False,
    company_id: int | None = Query(None, gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    selected_company_id = _resolve_notification_company_id(db, user, company_id)
    clinical_filter = None
    if user.role not in _HEALTH_ROLES:
        clinical_filter = or_(
            Notification.entity_type.is_(None),
            Notification.entity_type.notin_(tuple(_CLINICAL_NOTIFICATION_TYPES)),
        )
    if user.role == UserRole.GLOBAL_ADMIN:
        stmt = select(Notification)
        if selected_company_id is not None:
            stmt = stmt.where(Notification.company_id == selected_company_id)
        if clinical_filter is not None:
            stmt = stmt.where(clinical_filter)
        stmt = stmt.order_by(Notification.created_at.desc()).limit(300)
    else:
        if selected_company_id is not None:
            visibility = and_(
                Notification.company_id == selected_company_id,
                or_(Notification.user_id == user.id, Notification.user_id.is_(None)),
            )
        else:
            company_ids = _notification_company_ids(db, user)
            visibility = or_(
                and_(
                    Notification.company_id.in_(company_ids or [-1]),
                    or_(Notification.user_id == user.id, Notification.user_id.is_(None)),
                ),
                and_(
                    Notification.company_id.is_(None),
                    Notification.user_id == user.id,
                ),
            )
        filters = [visibility, _specialist_duty_visibility(user)]
        if clinical_filter is not None:
            filters.append(clinical_filter)
        stmt = (
            select(Notification)
            .where(and_(*filters))
            .order_by(Notification.created_at.desc())
            .limit(200)
        )
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    return list(db.scalars(stmt).all())


@router.post("/refresh")
def refresh_notifications(
    osgb_id: int | None = Query(None),
    company_id: int | None = Query(None, gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Süre / termin kontrolü — yalnızca kendi OSGB / firma kapsamı."""
    selected_company_id = _resolve_notification_company_id(db, user, company_id)
    if user.role == UserRole.GLOBAL_ADMIN:
        count = (
            rebuild_company_notifications(db, selected_company_id)
            if selected_company_id is not None
            else rebuild_all_notifications(db, osgb_id=osgb_id)
        )
        return {"message": "OSGB ve işyeri süreleri tarandı.", "count": count}

    if user.role == UserRole.COMPANY_ADMIN:
        if selected_company_id is not None:
            count = rebuild_company_notifications(db, selected_company_id)
            return {"message": "Seçili işyeri bildirimleri güncellendi.", "count": count}
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
        if selected_company_id is not None:
            count = rebuild_company_notifications(db, selected_company_id)
            count += rebuild_specialist_notifications(db, user)
            return {"message": "Seçili işyeri bildirimleri güncellendi.", "count": count}
        company_ids = _notification_company_ids(db, user)
        if not company_ids:
            raise HTTPException(400, "Aktif işyeri görevlendirmesi bulunamadı.")
        count = sum(rebuild_company_notifications(db, cid) for cid in company_ids)
        count += rebuild_specialist_notifications(db, user)
        return {"message": "Uzman bildirimleri güncellendi.", "count": count}

    if selected_company_id is not None:
        count = rebuild_company_notifications(db, selected_company_id)
        return {"message": "Seçili işyeri bildirimleri güncellendi.", "count": count}

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
    if not _can_access_notification(db, user, item):
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
    if not _can_access_notification(db, user, item):
        raise HTTPException(status_code=403, detail="Bu bildirime erişemezsiniz.")
    item.is_completed = True
    db.commit()
    return {"message": "Bildirim tamamlandı."}
