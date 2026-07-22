from datetime import datetime, timedelta

from app.models.entities import OsgbSubscription, SubscriptionStatus
from app.services.osgb_subscription import (
    effective_subscription_status,
    normalize_id,
    subscription_allows_write,
)


def test_normalize_id():
    assert normalize_id(" 12-34.56/78 ") == "12345678"


def test_subscription_write_trial_expired():
    sub = OsgbSubscription(status=SubscriptionStatus.TRIAL, trial_ends_at=datetime.utcnow() + timedelta(days=1))
    assert subscription_allows_write(sub)
    sub.trial_ends_at = datetime.utcnow() - timedelta(days=1)
    assert not subscription_allows_write(sub)
    assert effective_subscription_status(sub) == SubscriptionStatus.PAST_DUE


def test_subscription_active_period():
    sub = OsgbSubscription(
        status=SubscriptionStatus.ACTIVE,
        current_period_ends_at=datetime.utcnow() + timedelta(days=30),
    )
    assert subscription_allows_write(sub)


def test_resolved_trial_days_default_and_clamp(tmp_path, monkeypatch):
    db_file = tmp_path / "trial_days.db"
    url = f"sqlite:///{db_file.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long!!")

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import app.core.database as dbmod
    import app.models.entities as ent
    from app.core.config import settings
    from app.services.eisa_platform import resolved_trial_days, set_settings
    from app.services.osgb_subscription import get_or_create_subscription
    from app.models.entities import OsgbOrganization

    settings.database_url = url
    engine = create_engine(url, connect_args={"check_same_thread": False})
    dbmod.engine = engine
    dbmod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    ent.Base.metadata.create_all(bind=engine)

    with dbmod.SessionLocal() as db:
        assert resolved_trial_days(db) == 90
        set_settings(db, {"trial_days": "45"})
        assert resolved_trial_days(db) == 45
        set_settings(db, {"trial_days": "999"})
        assert resolved_trial_days(db) == 90
        set_settings(db, {"trial_days": "0"})
        assert resolved_trial_days(db) == 1
        set_settings(db, {"trial_days": "60"})
        osgb = OsgbOrganization(
            name="Trial OSGB",
            authorization_number="YETKI-T-1",
            tax_number="9988776655",
            responsible_manager="Yonetici",
            email="trial@test.com",
            is_active=True,
        )
        db.add(osgb)
        db.commit()
        db.refresh(osgb)
        sub = get_or_create_subscription(db, osgb.id)
        assert sub.status == SubscriptionStatus.TRIAL
        assert sub.trial_ends_at is not None
        delta = sub.trial_ends_at - datetime.utcnow()
        assert 59 <= delta.days <= 60
