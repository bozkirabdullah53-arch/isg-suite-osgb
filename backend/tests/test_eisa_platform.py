"""EİSA platform servisleri için ek testler."""
from datetime import datetime, timedelta
from decimal import Decimal

from app.models.entities import OsgbSubscription, SubscriptionStatus
from app.services.eisa_platform import days_remaining, is_expired, is_expiring


def test_days_remaining_trial():
    sub = OsgbSubscription(
        status=SubscriptionStatus.TRIAL,
        trial_ends_at=datetime.utcnow() + timedelta(days=5),
    )
    assert days_remaining(sub) == 5


def test_is_expiring_active():
    sub = OsgbSubscription(
        status=SubscriptionStatus.ACTIVE,
        current_period_ends_at=datetime.utcnow() + timedelta(days=7),
    )
    assert is_expiring(sub, window=14)


def test_is_expired_past_due():
    sub = OsgbSubscription(
        status=SubscriptionStatus.TRIAL,
        trial_ends_at=datetime.utcnow() - timedelta(days=1),
    )
    assert is_expired(sub)
