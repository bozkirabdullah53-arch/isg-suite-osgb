from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.entities import Company, Notification, User, UserRole
from app.services.notifications import rebuild_all_notifications, rebuild_company_notifications

router = APIRouter(prefix="/notifications", tags=["Bildirimler"])


@router.get("")
def list_notifications(
    unread_only: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == UserRole.GLOBAL_ADMIN:
        stmt = select(Notification).order_by(Notification.created_at.desc()).limit(300)
    elif user.osgb_id and user.role == UserRole.COMPANY_ADMIN:
        company_ids = list(
            db.scalars(select(Company.id).where(Company.osgb_id == user.osgb_id)).all()
        )
        conds = [Notification.user_id == user.id, Notification.company_id.is_(None)]
        if company_ids:
            conds.append(Notification.company_id.in_(company_ids))
        if user.company_id:
            conds.append(Notification.company_id == user.company_id)
        stmt = (
            select(Notification)
            .where(or_(*conds))
            .order_by(Notification.created_at.desc())
            .limit(200)
        )
    else:
        conds = [Notification.user_id == user.id]
        if user.company_id:
            conds.append(Notification.company_id == user.company_id)
        stmt = (
            select(Notification)
            .where(or_(*conds))
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
    """Süre / termin kontrolü — OSGB ve/veya firma kayıtlarından bildirim üretir."""
    if user.role == UserRole.GLOBAL_ADMIN:
        count = rebuild_all_notifications(db, osgb_id=osgb_id)
        return {
            "message": "OSGB ve işyeri süreleri tarandı.",
            "count": count,
        }
    if user.role == UserRole.COMPANY_ADMIN:
        oid = osgb_id or user.osgb_id
        if oid:
            count = rebuild_all_notifications(db, osgb_id=oid, company_id=user.company_id)
        elif user.company_id:
            count = rebuild_company_notifications(db, user.company_id)
        else:
            raise HTTPException(400, "OSGB veya firma bağlantısı bulunamadı.")
        return {"message": "Bildirimler güncellendi.", "count": count}
    if not user.company_id:
        raise HTTPException(400, "Firma bağlantısı bulunamadı.")
    count = rebuild_company_notifications(db, user.company_id)
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
    if user.role == UserRole.GLOBAL_ADMIN:
        pass
    elif item.user_id not in (None, user.id):
        raise HTTPException(status_code=403, detail="Bu bildirime erişemezsiniz.")
    elif item.company_id and user.company_id and item.company_id != user.company_id:
        if not (
            user.osgb_id
            and db.scalar(
                select(Company.id).where(
                    Company.id == item.company_id,
                    Company.osgb_id == user.osgb_id,
                )
            )
        ):
            raise HTTPException(status_code=403, detail="Bu bildirime erişemezsiniz.")
    item.is_read = True
    db.commit()
    return {"message": "Bildirim okundu."}
