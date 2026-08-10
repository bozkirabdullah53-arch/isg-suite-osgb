from __future__ import annotations

import json
from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.entities import Company, TrainingSession, User, UserRole
from app.models.training_nace import TrainingNaceSnapshot
from app.services import training_question_bank
from app.services.training_exact_question_factory import (
    EXACT_NACE_POLICY,
    WORK_SPECIFIC_COUNT,
    exact_question_readiness,
    exact_questions_from_snapshot,
)
from app.services.training_nace_classification import resolve_exact_nace
from app.services.training_question_selection_v2 import install_exact_nace_question_selection
from app.services.training_runtime_patches import install_training_runtime_patches
from app.services.training_topics import sectors_list_for_api

install_training_runtime_patches()
install_exact_nace_question_selection()


def _snapshot_from_classification(classification) -> TrainingNaceSnapshot:
    return TrainingNaceSnapshot(
        **classification.database_values(training_id=1, company_id=1, branch_id=None)
    )


def test_every_official_nace_gets_fifteen_unique_source_controlled_questions():
    checked = 0
    for row in sectors_list_for_api():
        key = str(row.get("code") or "")
        if not key.startswith("nace_") or not row.get("nace"):
            continue
        classification = resolve_exact_nace(key)
        questions = exact_questions_from_snapshot(_snapshot_from_classification(classification))
        assert len(questions) == WORK_SPECIFIC_COUNT == 15
        assert len({item["question_code"] for item in questions}) == 15
        assert {item["topic_label"] for item in questions} == set(classification.training_topics)
        for item in questions:
            assert len(item["options"]) == 4
            assert len({str(option).casefold() for option in item["options"]}) == 4
            assert item["correct_option"] == "A"
            assert item["answer_explanation"]
            assert any(
                scope["type"] == "nace" and scope["value"] == classification.nace_code
                for scope in item["scopes"]
            )
            assert all(str(source["url"]).startswith("https://www.csgb.gov.tr/") for source in item["sources"])
        checked += 1
    assert checked == 2141


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _seed_verified_training(db: Session):
    company = Company(name="Exact NACE Sınav Test", hazard_class="Çok Tehlikeli")
    user = User(
        email="exact-factory@example.com",
        full_name="Exact Factory Yönetici",
        hashed_password="x",
        role=UserRole.GLOBAL_ADMIN,
    )
    db.add_all([company, user])
    db.flush()
    classification = resolve_exact_nace("nace_30_11_01")
    training = TrainingSession(
        company_id=company.id,
        title="Tersane Temel İSG Eğitimi",
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


def test_strict_verified_exam_is_five_foundational_plus_fifteen_work_specific(
    db: Session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("TRAINING_EXACT_NACE_EXAM_STRICT", "true")
    training, user, classification = _seed_verified_training(db)

    readiness = training_question_bank.question_bank_readiness(db, training)
    assert readiness["ready"] is True
    assert readiness["release_ready"] is True
    assert readiness["available"] == {"foundation": 5, "work_specific": 15}

    exam = training_question_bank.create_exam_snapshot(
        db,
        training=training,
        created_by_id=user.id,
        allow_curated_fallback=True,
    )
    assert exam.selection_policy == EXACT_NACE_POLICY
    assert exam.question_count == 20
    assert len(exam.items) == 20
    assert [item.question_code for item in exam.items[:5]] == [
        "TR-TEMEL-ISG-001",
        "TR-TEMEL-ISG-002",
        "TR-TEMEL-ISG-003",
        "TR-TEMEL-ISG-004",
        "TR-TEMEL-ISG-005",
    ]
    dynamic = exam.items[5:]
    assert len(dynamic) == 15
    assert all(item.question_code.startswith("TR-NACE-301101-") for item in dynamic)
    assert len({item.question_code for item in dynamic}) == 15
    assert all(
        any(
            scope["type"] == "nace" and scope["value"] == classification.nace_code
            for scope in json.loads(item.scopes_json)
        )
        for item in dynamic
    )


def test_feature_flag_off_keeps_legacy_engine(db: Session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TRAINING_EXACT_NACE_EXAM_STRICT", "false")
    training, _user, _classification = _seed_verified_training(db)
    readiness = training_question_bank.question_bank_readiness(db, training)
    assert readiness["policy"] != EXACT_NACE_POLICY


def test_exact_readiness_fails_closed_for_missing_topics(db: Session):
    training, _user, _classification = _seed_verified_training(db)
    snapshot = db.scalar(
        select(TrainingNaceSnapshot).where(TrainingNaceSnapshot.training_id == training.id)
    )
    snapshot.training_topics_json = json.dumps(["Tek konu"], ensure_ascii=False)
    db.commit()
    readiness = exact_question_readiness(db, training)
    assert readiness["ready"] is False
    assert readiness["available"] == {"foundation": 5, "work_specific": 0}
