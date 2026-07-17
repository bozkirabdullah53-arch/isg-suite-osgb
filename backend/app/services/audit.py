from sqlalchemy.orm import Session
from app.models.entities import AuditLog, User


def add_audit_log(
    db: Session,
    *,
    user: User | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    description: str | None = None,
    ip_address: str | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            company_id=user.company_id if user else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            ip_address=ip_address,
        )
    )
