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
