from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.entities import Company, TrainingSession, User, UserRole
from app.models.training_nace import TrainingNaceSnapshot
from app.services.training_nace_classification import resolve_exact_nace
from app.services.training_question_selection_v2 import (
    exact_nace_exam_strict_active,
    install_exact_nace_question_selection,
    question_selection_audit,
)
from app.services.training_runtime_patches import install_training_runtime_patches
from app.services.training_topics import sectors_list_for_api

install_training_runtime_patches()
install_exact_nace_question_selection()


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _catalog_key_for_profile(profile: str) -> str:
    for row in sectors_list_for_api():
        key = str(row.get("code") or "")
        if key.startswith("nace_") and resolve_exact_nace(key).content_profile_code == profile:
            return key
    raise AssertionError(f"Profil için NACE bulunamadı: {profile}")


def _user_company(db: Session):
    company = Company(name="Sınav Seçim Test", hazard_class="Tehlikeli")
    user = User(
        email="selection-v2@example.com",
        full_name="Sınav Seçim Yöneticisi",
        hashed_password="x",
        role=UserRole.GLOBAL_ADMIN,
    )
    db.add_all([company, user])
    db.flush()
    return company, user


def _verified_training(db: Session, profile: str = "guzellik_kuafor_spa"):
    company, user = _user_company(db)
    classification = resolve_exact_nace(_catalog_key_for_profile(profile))
    training = TrainingSession(
        company_id=company.id,
        title="Verified Temel İSG Eğitimi",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 2),
        hazard_class=classification.hazard_class,
        sector=classification.catalog_key,
        instructor_name="İSG Uzmanı",
        created_by_id=user.id,
    )
    db.add(training)
    db.flush()
    snapshot = db.scalar(
        select(TrainingNaceSnapshot).where(TrainingNaceSnapshot.training_id == training.id)
    )
    if snapshot is None:
        db.add(
            TrainingNaceSnapshot(
                **classification.database_values(
                    training_id=training.id,
                    company_id=company.id,
                    branch_id=None,
                )
            )
        )
    db.commit()
    return training, user, classification


def _legacy_training(db: Session):
    company, user = _user_company(db)
    training = TrainingSession(
        company_id=company.id,
        title="Legacy Temel İSG Eğitimi",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 2),
        hazard_class="Tehlikeli",
        sector="genel_uretim",
        instructor_name="İSG Uzmanı",
        created_by_id=user.id,
    )
    db.add(training)
    db.commit()
    return training, user


def test_verified_snapshot_audit_reports_exact_factory_ready(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("TRAINING_EXACT_NACE_EXAM_STRICT", "true")
    training, _user, classification = _verified_training(db)
    audit = question_selection_audit(db, training)
    assert exact_nace_exam_strict_active() is True
    assert audit["verified_snapshot"] is True
    assert audit["selection_mode"] == "exact_nace_snapshot_5_plus_15"
    assert audit["exact_factory"]["ready"] is True
    assert audit["exact_factory"]["available"] == {
        "foundation": 5,
        "work_specific": 15,
    }
    assert audit["context"]["nace"] == classification.nace_code
    assert audit["strict_activation_blocked"] is False


def test_legacy_training_remains_backward_compatible(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("TRAINING_EXACT_NACE_EXAM_STRICT", "true")
    training, _user = _legacy_training(db)
    audit = question_selection_audit(db, training)
    assert audit["verified_snapshot"] is False
    assert audit["selection_mode"] == "legacy_unverified"
    assert audit["exact_factory"] is None
    assert audit["strict_activation_blocked"] is True



def test_exact_nace_selection_is_enabled_by_default(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("TRAINING_EXACT_NACE_EXAM_STRICT", raising=False)
    training, _user, classification = _verified_training(db)
    audit = question_selection_audit(db, training)

    assert audit["strict_flag_enabled"] is True
    assert audit["selection_mode"] == "exact_nace_snapshot_5_plus_15"
    assert audit["context"]["nace"] == classification.nace_code

def test_flag_off_keeps_current_selection_mode(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("TRAINING_EXACT_NACE_EXAM_STRICT", "false")
    training, _user, _classification = _verified_training(db)
    audit = question_selection_audit(db, training)
    assert audit["strict_flag_enabled"] is False
    assert audit["selection_mode"] == "legacy_compatibility"
    assert audit["exact_factory"]["ready"] is True


def test_audit_still_exposes_cross_sector_alias_dependency(db: Session):
    training, _user, _classification = _verified_training(
        db, profile="guzellik_kuafor_spa"
    )
    audit = question_selection_audit(db, training)
    assert audit["verified_snapshot"] is True
    assert audit["legacy"]["curated"]["sector"] >= 5
    assert audit["alias_only_sector_question_count"] >= 5
