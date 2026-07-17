from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.entities import User, UserRole


def seed_admin(db: Session) -> None:
    """Create an initial administrator only when explicit environment values exist."""
    if not settings.seed_admin_email or not settings.seed_admin_password:
        return
    if len(settings.seed_admin_password) < 12:
        raise RuntimeError("SEED_ADMIN_PASSWORD en az 12 karakter olmalıdır.")
    if db.scalar(select(User).where(User.email == settings.seed_admin_email)):
        return
    db.add(User(email=settings.seed_admin_email, full_name="Global Yönetici",
                hashed_password=get_password_hash(settings.seed_admin_password),
                role=UserRole.GLOBAL_ADMIN, is_active=True))
    db.commit()
