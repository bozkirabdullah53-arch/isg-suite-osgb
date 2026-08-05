from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.entities import (
    Company,
    TrainingQuestion,
    TrainingQuestionScope,
    TrainingQuestionSource,
    TrainingSession,
    User,
    UserRole,
)
from app.models.training_nace import TrainingNaceSnapshot
from app.services.training_nace_classification import resolve_exact_nace
from app.services.training_question_bank import (
    create_exam_snapshot,
    question_bank_readiness,
)
from app.services.training_question_selection_v2 import (
    STRICT_DB_POLICY,
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
        if not key.startswith("nace_"):
            continue
        if resolve_exact_nace(key).content_profile_code == profile:
            return key
    raise AssertionError(f"Profil için NACE bulunamadı: {profile}")


def _seed_user_company(db: Session) -> tuple[Company, User]:
    company = Company(name="Exact NACE Test", hazard_class="Tehlikeli")
    user = User(
        email="exact-nace@example.com",
        full_name="Exact NACE Test Yöneticisi",
        hashed_password="x",
        role=UserRole.GLOBAL_ADMIN,
    )
    db.add_all([company, user])
    db.flush()
    return company, user


def _verified_training(
    db: Session, *, profile: str = "guzellik_kuafor_spa"
) -> tuple[TrainingSession, User, object]:
    company, user = _seed_user_company(db)
    key = _catalog_key_for_profile(profile)
    classification = resolve_exact_nace(key)
    training = TrainingSession(
        company_id=company.id,
        title="Exact NACE Temel İSG Eğitimi",
        start_date=date(2026, 8, 5),
        end_date=date(2026, 8, 7),
        hazard_class=classification.hazard_class,
        sector=classification.catalog_key,
        instructor_name="İSG Uzmanı",
        created_by_id=user.id,
    )
    db.add(training)
    db.flush()

    snapshot = db.scalar(
        select(TrainingNaceSnapshot).where(
            TrainingNaceSnapshot.training_id == training.id
        )
    )
    if snapshot is None:
        snapshot = TrainingNaceSnapshot(
            **classification.database_values(
                training_id=training.id,
                company_id=company.id,
                branch_id=None,
            )
        )
        db.add(snapshot)
    db.commit()
    return training, user, classification


def _legacy_training(db: Session) -> tuple[TrainingSession, User]:
    company, user = _seed_user_company(db)
    training = TrainingSession(
        company_id=company.id,
        title="Legacy Temel İSG Eğitimi",
        start_date=date(2026, 8, 5),
        end_date=date(2026, 8, 7),
        hazard_class="Tehlikeli",
        sector="genel_uretim",
        instructor_name="İSG Uzmanı",
        created_by_id=user.id,
    )
    db.add(training)
    db.commit()
    return training, user


def _question(
    db: Session,
    *,
    code: str,
    scope_type: str,
    scope_value: str,
    creator: int,
):
    row = TrainingQuestion(
        question_code=code,
        version=1,
        status="published",
        topic_code=f"topic-{code}",
        topic_label=f"Konu {code}",
        question_text=f"{code} için güvenli çalışma uygulaması hangisidir?",
        option_a=f"{code} doğru güvenli uygulama",
        option_b=f"{code} yanlış seçenek bir",
        option_c=f"{code} yanlış seçenek iki",
        option_d=f"{code} yanlış seçenek üç",
        correct_option="A",
        answer_explanation=f"{code} için doğru uygulamanın mevzuat gerekçesi budur.",
        created_by_id=creator,
    )
    row.scopes.append(
        TrainingQuestionScope(scope_type=scope_type, scope_value=scope_value)
    )
    row.sources.append(
        TrainingQuestionSource(
            title="Resmî Gazete",
            url="https://www.resmigazete.gov.tr/ornek",
            reference="Madde 1",
            effective_date=date(2025, 3, 13),
        )
    )
    db.add(row)


def _seed_common_hazard_and_sector(
    db: Session,
    *,
    user_id: int,
    hazard: str,
    sector_scope: str,
):
    for index in range(5):
        _question(
            db,
            code=f"C-{sector_scope}-{index}",
            scope_type="common",
            scope_value="*",
            creator=user_id,
        )
        _question(
            db,
            code=f"H-{sector_scope}-{index}",
            scope_type="hazard",
            scope_value=hazard,
            creator=user_id,
        )
        _question(
            db,
            code=f"S-{sector_scope}-{index}",
            scope_type="sector",
            scope_value=sector_scope,
            creator=user_id,
        )
    db.commit()


def test_verified_snapshot_strict_mode_rejects_general_production_questions(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("TRAINING_EXACT_NACE_EXAM_STRICT", "true")
    training, user, classification = _verified_training(db)
    _seed_common_hazard_and_sector(
        db,
        user_id=user.id,
        hazard=classification.hazard_class,
        sector_scope="genel_uretim",
    )

    readiness = question_bank_readiness(db, training)
    assert readiness["available"] == {"common": 5, "technical": 5, "sector": 0}
    assert readiness["ready"] is False

    audit = question_selection_audit(db, training)
    assert audit["verified_snapshot"] is True
    assert audit["strict"]["database"]["sector"] == 0
    assert audit["legacy"]["database"]["sector"] == 5
    assert audit["legacy_ready_but_strict_blocked"] is True


def test_verified_snapshot_strict_mode_accepts_reviewed_profile_scope(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("TRAINING_EXACT_NACE_EXAM_STRICT", "true")
    training, user, classification = _verified_training(db)
    _seed_common_hazard_and_sector(
        db,
        user_id=user.id,
        hazard=classification.hazard_class,
        sector_scope=classification.content_profile_code,
    )

    readiness = question_bank_readiness(db, training)
    assert readiness["available"] == {"common": 5, "technical": 5, "sector": 5}
    assert readiness["ready"] is True

    exam = create_exam_snapshot(db, training=training, created_by_id=user.id)
    assert exam.selection_policy == STRICT_DB_POLICY
    assert exam.question_count == 20
    assert len(exam.items) == 20


def test_legacy_training_keeps_backward_compatible_selection(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("TRAINING_EXACT_NACE_EXAM_STRICT", "true")
    training, user = _legacy_training(db)
    _seed_common_hazard_and_sector(
        db,
        user_id=user.id,
        hazard=training.hazard_class,
        sector_scope="genel_uretim",
    )

    readiness = question_bank_readiness(db, training)
    assert readiness["ready"] is True
    assert readiness["available"] == {"common": 5, "technical": 5, "sector": 5}

    audit = question_selection_audit(db, training)
    assert audit["verified_snapshot"] is False
    assert audit["selection_mode"] == "legacy_unverified"
    assert audit["strict"] is None


def test_feature_flag_off_preserves_current_behavior_for_verified_snapshot(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("TRAINING_EXACT_NACE_EXAM_STRICT", raising=False)
    training, user, classification = _verified_training(db)
    _seed_common_hazard_and_sector(
        db,
        user_id=user.id,
        hazard=classification.hazard_class,
        sector_scope="genel_uretim",
    )

    readiness = question_bank_readiness(db, training)
    assert readiness["ready"] is True
    assert readiness["available"]["sector"] == 5

    audit = question_selection_audit(db, training)
    assert audit["selection_mode"] == "legacy_compatibility"
    assert audit["strict_flag_enabled"] is False


def test_audit_identifies_curated_alias_only_sector_questions(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("TRAINING_EXACT_NACE_EXAM_STRICT", raising=False)
    training, _user, _classification = _verified_training(
        db, profile="guzellik_kuafor_spa"
    )

    audit = question_selection_audit(db, training)
    assert audit["verified_snapshot"] is True
    assert audit["legacy"]["curated"]["sector"] >= 5
    assert audit["alias_only_sector_question_count"] >= 5
    assert all(
        code not in set(audit["strict"].get("sector_question_codes", []))
        for code in audit["alias_only_sector_question_codes"]
    )
