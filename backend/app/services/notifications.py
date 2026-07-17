from datetime import date, datetime, timedelta
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.entities import (
    AnnualPlanItem,
    AnnualPlanStatus,
    DocumentRecord,
    HealthRecord,
    IsgRecord,
    Notification,
    NotificationType,
    RecordStatus,
)


def rebuild_company_notifications(db: Session, company_id: int) -> int:
    db.execute(delete(Notification).where(
        Notification.company_id == company_id,
        Notification.user_id.is_(None),
    ))
    today = date.today()
    warning_date = today + timedelta(days=30)
    notifications: list[Notification] = []

    overdue_isg = db.scalars(select(IsgRecord).where(
        IsgRecord.company_id == company_id,
        IsgRecord.due_date.is_not(None),
        IsgRecord.due_date < today,
        IsgRecord.status != RecordStatus.COMPLETED,
    )).all()
    for item in overdue_isg:
        notifications.append(Notification(
            company_id=company_id,
            type=NotificationType.CRITICAL,
            title="Termin tarihi geçen İSG kaydı",
            message=f"{item.title} kaydının termin tarihi {item.due_date} tarihinde doldu.",
            entity_type="isg_record",
            entity_id=str(item.id),
        ))

    expiring_docs = db.scalars(select(DocumentRecord).where(
        DocumentRecord.company_id == company_id,
        DocumentRecord.valid_until.is_not(None),
        DocumentRecord.valid_until <= warning_date,
        DocumentRecord.is_active.is_(True),
    )).all()
    for item in expiring_docs:
        notifications.append(Notification(
            company_id=company_id,
            type=NotificationType.WARNING if item.valid_until >= today else NotificationType.CRITICAL,
            title="Doküman geçerlilik uyarısı",
            message=f"{item.title} dokümanının geçerlilik tarihi {item.valid_until}.",
            entity_type="document",
            entity_id=str(item.id),
        ))

    exams = db.scalars(select(HealthRecord).where(
        HealthRecord.company_id == company_id,
        HealthRecord.next_examination_date.is_not(None),
        HealthRecord.next_examination_date <= warning_date,
    )).all()
    for item in exams:
        notifications.append(Notification(
            company_id=company_id,
            type=NotificationType.WARNING,
            title="Yaklaşan sağlık muayenesi",
            message=f"Personel #{item.employee_id} için muayene tarihi {item.next_examination_date}.",
            entity_type="health_record",
            entity_id=str(item.id),
        ))

    delayed = db.scalars(select(AnnualPlanItem).where(
        AnnualPlanItem.company_id == company_id,
        AnnualPlanItem.status == AnnualPlanStatus.DELAYED,
    )).all()
    for item in delayed:
        notifications.append(Notification(
            company_id=company_id,
            type=NotificationType.WARNING,
            title="Geciken yıllık plan faaliyeti",
            message=f"{item.year}/{item.month}: {item.activity}",
            entity_type="annual_plan",
            entity_id=str(item.id),
        ))

    db.add_all(notifications)
    db.commit()
    return len(notifications)
