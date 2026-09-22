from datetime import date, timedelta
from types import SimpleNamespace

from app.api.annual_plans import _refresh_delayed, _status_for_completion
from app.models.entities import AnnualPlanStatus
from app.schemas.annual_plan import AnnualPlanCreate, AnnualPlanUpdate


class _FakeSession:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1

    def refresh(self, _item):
        return None


def test_completion_date_is_authoritative_for_status():
    assert _status_for_completion(
        AnnualPlanStatus.DELAYED,
        date.today(),
    ) == AnnualPlanStatus.COMPLETED


def test_create_and_update_payloads_normalize_completion_to_completed():
    created = AnnualPlanCreate(
        company_id=1,
        year=2026,
        month=1,
        activity="Yıllık plan kontrolü",
        status=AnnualPlanStatus.DELAYED,
        target_date=date.today() - timedelta(days=1),
        completion_date=date.today(),
    )
    updated = AnnualPlanUpdate(
        status=AnnualPlanStatus.DELAYED,
        completion_date=date.today(),
    )

    assert created.status == AnnualPlanStatus.COMPLETED
    assert updated.status == AnnualPlanStatus.COMPLETED


def test_update_accepts_template_responsible_role_with_completion_date():
    updated = AnnualPlanUpdate(
        activity="Yıllık İSG çalışma planının oluşturulması",
        responsible_name="İSG Uzmanı / İşveren",
        target_date=date(2026, 1, 15),
        status=AnnualPlanStatus.DELAYED,
        completion_date=date(2026, 1, 22),
    )

    assert updated.responsible_name == "İSG Uzmanı / İşveren"
    assert updated.status == AnnualPlanStatus.COMPLETED


def test_refresh_converts_legacy_completed_date_from_delayed_to_completed():
    item = SimpleNamespace(
        status=AnnualPlanStatus.DELAYED,
        target_date=date.today() - timedelta(days=30),
        completion_date=date.today(),
    )
    db = _FakeSession()

    _refresh_delayed(db, [item])

    assert item.status == AnnualPlanStatus.COMPLETED
    assert db.commits == 1


def test_refresh_only_marks_uncompleted_past_items_as_delayed():
    item = SimpleNamespace(
        status=AnnualPlanStatus.PLANNED,
        target_date=date.today() - timedelta(days=1),
        completion_date=None,
    )
    db = _FakeSession()

    _refresh_delayed(db, [item])

    assert item.status == AnnualPlanStatus.DELAYED

