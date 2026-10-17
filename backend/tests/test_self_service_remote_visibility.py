"""Çalışan paneli, yayında olan uzaktan eğitim atamalarını eksiksiz göstermeli.

Eski veya yayından kalkmış (arşiv/taslak) atamalar, çalışanın görmesi gereken
yayında eğitimleri 20 kayıtlık pencereden itmemelidir.
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.api.self_service import _remote_training_summary
from app.core.config import settings
from app.models.remote_training import RemoteTrainingAssignment, RemoteTrainingProgram
from test_employee_self_service import _seed, db  # noqa: F401  (paylaşılan kurulum ve oturum)


def _add_assignment(
    db: Session,
    *,
    osgb,
    company,
    employee,
    title: str,
    status: str,
    assigned_at: datetime,
    policy_mode: str = "legacy",
) -> None:
    program = RemoteTrainingProgram(
        osgb_id=osgb.id,
        company_id=company.id,
        title=title,
        status=status,
        policy_mode=policy_mode,
        total_duration_seconds=600,
    )
    db.add(program)
    db.flush()
    db.add(
        RemoteTrainingAssignment(
            osgb_id=osgb.id,
            company_id=company.id,
            program_id=program.id,
            employee_id=employee.id,
            employee_name_snapshot=employee.full_name,
            assigned_at=assigned_at,
        )
    )
    db.flush()


def _enable_remote_training(monkeypatch) -> None:
    monkeypatch.setattr(settings, "remote_basic_ohs_training_enabled", True)
    monkeypatch.setattr(settings, "remote_basic_ohs_training_force_off", False)


def test_visible_assignment_is_not_pushed_out_by_newer_hidden_rows(db: Session, monkeypatch):
    osgb, company, _other_company, employee, _user, _mapping = _seed(db)
    _enable_remote_training(monkeypatch)
    base = datetime(2026, 10, 1, 9, 0, 0)
    _add_assignment(
        db, osgb=osgb, company=company, employee=employee,
        title="Açık Eğitim", status="published", assigned_at=base,
    )
    for index in range(25):
        _add_assignment(
            db, osgb=osgb, company=company, employee=employee,
            title=f"Arşiv {index}", status="archived",
            assigned_at=base + timedelta(hours=index + 1),
        )
    db.commit()

    summary = _remote_training_summary(db, company.id, employee.id)

    assert [row["title"] for row in summary["assignments"]] == ["Açık Eğitim"]
    assert summary["total"] == 1


def test_remote_summary_keeps_newest_twenty_visible_assignments(db: Session, monkeypatch):
    osgb, company, _other_company, employee, _user, _mapping = _seed(db)
    _enable_remote_training(monkeypatch)
    base = datetime(2026, 10, 1, 9, 0, 0)
    for index in range(22):
        _add_assignment(
            db, osgb=osgb, company=company, employee=employee,
            title=f"Yayında {index}", status="published",
            assigned_at=base + timedelta(hours=index),
        )
    db.commit()

    summary = _remote_training_summary(db, company.id, employee.id)

    assert summary["total"] == 20
    assert len(summary["assignments"]) == 20
    assert summary["assignments"][0]["title"] == "Yayında 21"


def test_remote_summary_still_hides_strict_program_when_policy_is_closed(db: Session, monkeypatch):
    osgb, company, _other_company, employee, _user, _mapping = _seed(db)
    _enable_remote_training(monkeypatch)
    monkeypatch.setattr(settings, "remote_basic_ohs_strict_policy_enabled", False)
    base = datetime(2026, 10, 1, 9, 0, 0)
    _add_assignment(
        db, osgb=osgb, company=company, employee=employee,
        title="Serbest Eğitim", status="published", assigned_at=base,
    )
    _add_assignment(
        db, osgb=osgb, company=company, employee=employee,
        title="Sıkı Politika Eğitimi", status="published",
        assigned_at=base + timedelta(hours=1), policy_mode="strict",
    )
    db.commit()

    summary = _remote_training_summary(db, company.id, employee.id)

    assert [row["title"] for row in summary["assignments"]] == ["Serbest Eğitim"]
