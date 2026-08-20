from app.models.entities import Notification


def test_notification_has_persistent_completion_column():
    column = Notification.__table__.c.is_completed

    assert column.nullable is False
    assert column.default is not None
    assert column.default.arg is False
