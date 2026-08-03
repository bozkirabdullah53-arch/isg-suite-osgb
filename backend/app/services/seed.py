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
        "responsible_manager": "Demo Alfa Mudur",
        "email": "demo.osgb.alfa@example.com",
        "phone": "05551110001",
        "address": "Demo Alfa Adres",
    },
    {
        "name": "[DEMO_TEST] OSGB Beta Merkez",
        "authorization_number": "DEMO-OSGB-BETA-001",
        "tax_number": "2222222222",
        "responsible_manager": "Demo Beta Mudur",
        "email": "demo.osgb.beta@example.com",
        "phone": "05551110002",
        "address": "Demo Beta Adres",
    },
)


def seed_admin(db: Session) -> None:
    """Ortam degiskenleri tanimliysa ilk global yoneticiyi olusturur."""
    if not settings.seed_admin_email or not settings.seed_admin_password:
        return

    if len(settings.seed_admin_password) < 12:
        raise RuntimeError(
            "SEED_ADMIN_PASSWORD en az 12 karakter olmalidir."
        )

    existing_user = db.scalar(
        select(User)
        .where(User.email == settings.seed_admin_email)
        .limit(1)
    )

    if existing_user:
        return

    admin = User(
        email=settings.seed_admin_email,
        full_name="Global Yonetici",
        hashed_password=get_password_hash(
            settings.seed_admin_password
        ),
        role=UserRole.GLOBAL_ADMIN,
        is_active=True,
    )

    db.add(admin)
    db.commit()


def _demo_seed_allowed() -> bool:
    """Demo OSGB kayitlarinin olusturulmasina izin verilip verilmedigini belirler."""
    if settings.seed_demo_osgbs:
        return True

    environment = (settings.environment or "").strip().lower()

    return environment in {
        "development",
        "dev",
        "qa",
        "test",
        "local",
    }


def seed_demo_osgbs(db: Session) -> list[str]:
    """Demo OSGB kayitlarini olusturur."""
    if not _demo_seed_allowed():
        return []

    created: list[str] = []

    for spec in DEMO_OSGBS:
        existing_organization = db.scalar(
            select(OsgbOrganization)
            .where(OsgbOrganization.name == spec["name"])
            .limit(1)
        )

        if existing_organization:
            continue

        authorization_number = spec.get("authorization_number")

        if authorization_number:
            conflicting_organization = db.scalar(
                select(OsgbOrganization)
                .where(
                    OsgbOrganization.authorization_number
                    == authorization_number
                )
                .limit(1)
            )

            if conflicting_organization:
                continue

        organization = OsgbOrganization(
            **spec,
            is_active=True,
        )

        db.add(organization)
        db.commit()
        db.refresh(organization)

        try:
            from app.services.osgb_subscription import (
                get_or_create_subscription,
            )

            get_or_create_subscription(
                db,
                organization.id,
            )
        except Exception:
            db.rollback()

        created.append(spec["name"])

    return created