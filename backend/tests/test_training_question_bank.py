from datetime import date

import pytest
from sqlalchemy import create_engine
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
from app.services.training_question_bank import (
    InsufficientQuestionBankError,
    create_exam_snapshot,
    question_bank_readiness,
    validate_question_for_publish,
)


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _seed_training(db: Session) -> tuple[TrainingSession, User]:
    company = Company(name="Tersane Test", hazard_class="Çok Tehlikeli")
    user = User(
        email="bank@example.com",
        full_name="Soru Bankası Yöneticisi",
        hashed_password="x",
        role=UserRole.GLOBAL_ADMIN,
    )
    db.add_all([company, user])
    db.flush()
    training = TrainingSession(
        company_id=company.id,
        title="Tersane Temel İSG Eğitimi",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 2),
        hazard_class="Çok Tehlikeli",
        sector="nace_30_11_01",
        instructor_name="İSG Uzmanı",
        created_by_id=user.id,
    )
    db.add(training)
    db.commit()
    return training, user


def _question(db: Session, *, code: str, scope_type: str, scope_value: str, creator: int):
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
    row.scopes.append(TrainingQuestionScope(scope_type=scope_type, scope_value=scope_value))
    row.sources.append(
        TrainingQuestionSource(
            title="Resmî Gazete",
            url="https://www.resmigazete.gov.tr/ornek",
            reference="Madde 1",
            effective_date=date(2025, 3, 13),
        )
    )
    db.add(row)
    return row


def test_publish_validation_rejects_duplicate_options(db: Session):
    _, user = _seed_training(db)
    row = _question(db, code="BAD-1", scope_type="common", scope_value="*", creator=user.id)
    row.option_b = row.option_a
    with pytest.raises(ValueError, match="farklı"):
        validate_question_for_publish(row)


def test_insufficient_bank_blocks_exam_instead_of_generic_fallback(db: Session):
    training, user = _seed_training(db)
    for i in range(5):
        _question(db, code=f"C-{i}", scope_type="common", scope_value="*", creator=user.id)
    db.commit()
    readiness = question_bank_readiness(db, training)
    assert readiness["ready"] is False
    assert readiness["available"] == {"common": 5, "technical": 0, "sector": 0}
    with pytest.raises(InsufficientQuestionBankError):
        create_exam_snapshot(db, training=training, created_by_id=user.id)


def test_approved_bank_creates_frozen_15_question_snapshot_and_answer_key(db: Session):
    training, user = _seed_training(db)
    for i in range(5):
        _question(db, code=f"C-{i}", scope_type="common", scope_value="*", creator=user.id)
        _question(
            db,
            code=f"H-{i}",
            scope_type="hazard",
            scope_value="Çok Tehlikeli",
            creator=user.id,
        )
        _question(
            db,
            code=f"S-{i}",
            scope_type="sector",
            scope_value="gemi_insa_tersane",
            creator=user.id,
        )
    db.commit()

    readiness = question_bank_readiness(db, training)
    assert readiness["ready"] is True
    assert readiness["available"] == {"common": 5, "technical": 5, "sector": 5}

    exam = create_exam_snapshot(db, training=training, created_by_id=user.id)
    assert exam.question_count == 15
    assert len(exam.items) == 15
    assert [item.position for item in exam.items] == list(range(1, 16))
    assert len(exam.content_hash) == 64
    assert len({item.question_code for item in exam.items}) == 15
    for item in exam.items:
        options = __import__("json").loads(item.options_json)
        assert options[item.correct_option] == f"{item.question_code} doğru güvenli uygulama"

    # Banka sorusu sonradan taslakta değişse bile sınav kopyası değişmez.
    original = exam.items[0].question_text
    bank_row = db.get(TrainingQuestion, exam.items[0].question_id)
    bank_row.question_text = "Sonradan değiştirilen banka metni"
    db.commit()
    db.refresh(exam.items[0])
    assert exam.items[0].question_text == original
