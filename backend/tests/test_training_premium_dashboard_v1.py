from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.models.entities import TrainingStatus
from app.services.training_premium_dashboard_v1 import (
    _basic_state,
    _work_start_state,
    build_dashboard,
    dashboard_active,
)


@pytest.fixture(autouse=True)
def premium_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TRAINING_PREMIUM_LIFECYCLE_V2_ENABLED", "true")
    monkeypatch.setenv("TRAINING_PREMIUM_LIFECYCLE_V2_FORCE_OFF", "false")
    monkeypatch.setenv("TRAINING_PREMIUM_LIFECYCLE_V2_AFTER", "2026-08-09T07:12:00Z")
    monkeypatch.setenv("TRAINING_PREMIUM_DASHBOARD_V1_ENABLED", "true")
    monkeypatch.setenv("TRAINING_PREMIUM_DASHBOARD_V1_FORCE_OFF", "false")


def participant(*, pid=1, employee_id=11, attended=False):
    return SimpleNamespace(
        id=pid,
        employee_id=employee_id,
        attended=attended,
        score=None,
        successful=None,
        certificate_number=f"EGT-000001-{employee_id:06d}",
    )


def training(
    *,
    tid=1,
    training_type="İşe Başlama Eğitimi",
    title="İşe Başlama İş Sağlığı ve Güvenliği Eğitimi",
    status=TrainingStatus.PLANNED,
    start=None,
    end=None,
    next_due=None,
):
    start = start or date.today()
    return SimpleNamespace(
        id=tid,
        training_type=training_type,
        title=title,
        notes="",
        status=status,
        start_date=start,
        end_date=end or start,
        next_training_date=next_due,
        created_at=datetime(2026, 8, 10, 8, 0, 0),
    )


def employee(*, eid=11, start_date=None, name="Ali Çalışan"):
    return SimpleNamespace(
        id=eid,
        full_name=name,
        department="Üretim",
        job_title="Operatör",
        start_date=start_date,
        is_active=True,
        company_id=118,
    )


def test_dashboard_force_off_is_visual_and_api_rollback(monkeypatch: pytest.MonkeyPatch):
    assert dashboard_active() is True
    monkeypatch.setenv("TRAINING_PREMIUM_DASHBOARD_V1_FORCE_OFF", "true")
    assert dashboard_active() is False


def test_pre_cutover_employee_is_neutral_not_retroactive_red():
    emp = employee(start_date=date(2026, 8, 1))
    state = _work_start_state(emp, [], cutover=date(2026, 8, 9))
    assert state["status"] == "historical"
    assert state["tone"] == "neutral"


def test_post_cutover_work_start_progresses_missing_pending_ok():
    emp = employee(start_date=date(2026, 8, 10))
    missing = _work_start_state(emp, [], cutover=date(2026, 8, 9))
    assert missing["status"] == "missing"

    row = training(status=TrainingStatus.PLANNED)
    pending = _work_start_state(emp, [(participant(attended=False), row)], cutover=date(2026, 8, 9))
    assert pending["status"] == "pending"

    row.status = TrainingStatus.COMPLETED
    ok = _work_start_state(emp, [(participant(attended=True), row)], cutover=date(2026, 8, 9))
    assert ok["status"] == "ok"


def test_basic_training_within_first_three_months_is_warning_not_overdue():
    emp = employee(start_date=date.today() - timedelta(days=15))
    state = _basic_state(emp, [])
    assert state["status"] == "never"
    assert state["days_left"] is not None and state["days_left"] > 0
    assert state["tone"] == "warning"
    assert state["label"] == "İlk temel eğitim bekliyor"


def test_basic_training_after_three_month_deadline_is_danger():
    emp = employee(start_date=date.today() - timedelta(days=130))
    state = _basic_state(emp, [])
    assert state["status"] == "never"
    assert state["days_left"] is not None and state["days_left"] < 0
    assert state["tone"] == "danger"


class _Scalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class FakeDashboardDb:
    def __init__(self, *, employees, pairs, trainings):
        self._scalar_results = [employees, trainings]
        self._pairs = pairs
        self.scalar_calls = 0
        self.execute_calls = 0
        self.writes = 0

    def scalars(self, _statement):
        rows = self._scalar_results[self.scalar_calls]
        self.scalar_calls += 1
        return _Scalars(rows)

    def execute(self, _statement):
        self.execute_calls += 1
        return _Result(self._pairs)

    def add(self, *_args, **_kwargs):
        self.writes += 1
        raise AssertionError("Read-only dashboard must not add rows")

    def commit(self):
        self.writes += 1
        raise AssertionError("Read-only dashboard must not commit")


def test_dashboard_build_is_read_only_and_has_two_traffic_lights():
    emp = employee(start_date=date(2026, 8, 10))
    work = training(tid=9, status=TrainingStatus.COMPLETED, start=date.today() - timedelta(days=1), end=date.today())
    p = participant(attended=True)
    db = FakeDashboardDb(employees=[emp], pairs=[(p, work)], trainings=[work])

    payload = build_dashboard(db, company_id=118)

    assert payload["safety"]["read_only"] is True
    assert payload["safety"]["automatic_training_completion"] is False
    assert payload["rows"][0]["work_start"]["status"] == "ok"
    assert "basic" in payload["rows"][0]
    assert db.writes == 0
    assert db.scalar_calls == 2
    assert db.execute_calls == 1
