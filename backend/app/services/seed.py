from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.entities import OsgbOrganization, User, UserRole

DEMO_OSGBS = (
    {
        "name": "[DEMO_TEST] OSGB Alfa Merkez",
        "authorization_number": "DEMO-OSGB-ALFA-001",
        "tax_number": "1111111111",
        "responsible_manager": "Demo Alfa Müdür",
        "email": "demo.osgb.alfa@example.com",
        "phone": "05551110001",
        "address": "Demo Alfa Adres",
    },
    {
        "name": "[DEMO_TEST] OSGB Beta Merkez",
        "authorization_number": "DEMO-OSGB-BETA-001",
        "tax_number": "2222222222",
        "responsible_manager": "Demo Beta Müdür",
        "email": "demo.osgb.beta@example.com",
        "phone": "05551110002",
        "address": "Demo Beta Adres",
    },
)


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


def seed_demo_osgbs(db: Session) -> list[str]:
    """Idempotent: 2 demo/test OSGB kaydı (yoksa ekler)."""
    created: list[str] = []
    for spec in DEMO_OSGBS:
        exists = db.scalar(
            select(OsgbOrganization).where(OsgbOrganization.name == spec["name"]).limit(1)
        )
        if exists:
            if not exists.is_active:
                exists.is_active = True
                db.commit()
            continue
        # yetki no çakışması
        if spec.get("authorization_number"):
            clash = db.scalar(
                select(OsgbOrganization)
                .where(OsgbOrganization.authorization_number == spec["authorization_number"])
                .limit(1)
            )
            if clash:
                continue
        org = OsgbOrganization(**spec, is_active=True)
        db.add(org)
        db.flush()
        try:
            from app.services.osgb_subscription import get_or_create_subscription

            get_or_create_subscription(db, org.id)
        except Exception:
            pass
        created.append(spec["name"])
    if created:
        db.commit()
    else:
        db.commit()
    return created
