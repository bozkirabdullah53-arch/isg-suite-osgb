from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.entities import Notification, User, UserRole
from app.services.notifications import rebuild_company_notifications

router = APIRouter(prefix="/notifications", tags=["Bildirimler"])


@router.get("")
def list_notifications(
    unread_only: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conditions = [Notification.user_id == user.id]
    if user.company_id:
        conditions.append(Notification.company_id == user.company_id)
    query = select(Notification).where(or_(*conditions)).order_by(Notification.created_at.desc()).limit(200)
    if unread_only:
        query = query.where(Notification.is_read.is_(False))
    return db.scalars(query).all()


@router.post("/refresh")
def refresh_notifications(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.company_id and user.role != UserRole.GLOBAL_ADMIN:
        raise HTTPException(status_code=400, detail="Firma bağlantısı bulunamadı.")
    if user.role == UserRole.GLOBAL_ADMIN:
        raise HTTPException(status_code=400, detail="Global yönetici firma panelinden yenileme yapmalıdır.")
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
    if item.user_id not in (None, user.id) or (item.company_id and item.company_id != user.company_id):
        raise HTTPException(status_code=403, detail="Bu bildirime erişemezsiniz.")
    item.is_read = True
    db.commit()
    return {"message": "Bildirim okundu."}
