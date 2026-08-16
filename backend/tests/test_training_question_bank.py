from datetime import date
from io import BytesIO

from pypdf import PdfReader

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.entities import (
    Company,
    Employee,
    TrainingExamSnapshot,
    TrainingQuestion,
    TrainingQuestionScope,
    TrainingQuestionSource,
    TrainingParticipant,
    TrainingSession,
    User,
    UserRole,
)
from app.services.training_question_bank import (
    FOUNDATIONAL_QUESTION_COUNT,
    InsufficientQuestionBankError,
    QUESTION_COUNT,
    _curated_buckets,
    create_exam_snapshot,
    nace_scope_matches,
    question_bank_coverage,
    question_bank_readiness,
    valid_nace_scope,
    validate_question_for_publish,
)
from app.services.training_exam_pdf import (
    _exam_pdf_question_text,
    _load_or_create_snapshot,
    build_exam_pdf,
)
from app.services.training_pdfs import build_attendance_pdf, build_certificates_pdf
from app.services.training_topics import sectors_list_for_api


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


def _question(
    db: Session,
    *,
    code: str,
    scope_type: str,
    scope_value: str,
    creator: int,
    version: int = 1,
    status: str = "published",
):
    row = TrainingQuestion(
        question_code=code,
        version=version,
        status=status,
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


def test_nace_scope_requires_official_segment_boundary():
    assert valid_nace_scope("30") is True
    assert valid_nace_scope("30.11") is True
    assert valid_nace_scope("30.11.01") is True
    assert valid_nace_scope("30.1") is False
    assert valid_nace_scope("99.99") is False
    assert nace_scope_matches("30.11.01", "30.11") is True
    assert nace_scope_matches("30.12.01", "30.11") is False


def test_publish_validation_rejects_unknown_nace_scope(db: Session):
    _, user = _seed_training(db)
    row = _question(db, code="BAD-NACE", scope_type="nace", scope_value="30.1", creator=user.id)
    with pytest.raises(ValueError, match="NACE kapsamı"):
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


def test_pdf_only_curated_fallback_creates_snapshot_without_mutating_bank(db: Session):
    training, user = _seed_training(db)
    training.sector = "genel_uretim"
    db.commit()

    exam = create_exam_snapshot(
        db,
        training=training,
        created_by_id=user.id,
        allow_curated_fallback=True,
    )

    assert exam.question_count == QUESTION_COUNT == 20
    assert len(exam.items) == QUESTION_COUNT
    assert exam.selection_policy == "foundation-5-plus-approved-db-curated-5x3-v1"
    assert {item.question_id for item in exam.items} == {None}
    assert len({item.question_code for item in exam.items}) == QUESTION_COUNT
    assert [item.question_code for item in exam.items[:FOUNDATIONAL_QUESTION_COUNT]] == [
        "TR-TEMEL-ISG-001",
        "TR-TEMEL-ISG-002",
        "TR-TEMEL-ISG-003",
        "TR-TEMEL-ISG-004",
        "TR-TEMEL-ISG-005",
    ]
    assert db.query(TrainingQuestion).count() == 0


def test_curated_fallback_covers_every_official_nace_record():
    checked = 0
    for sector in sectors_list_for_api():
        if not sector.get("nace"):
            continue
        training = TrainingSession(
            hazard_class=sector["hazard_class"],
            sector=sector["code"],
        )
        bucket = _curated_buckets(training)["sector"]
        assert len(bucket) >= 5, (
            sector["nace"],
            sector["code"],
            sector.get("profile"),
        )
        checked += 1
    assert checked == 2141


def test_battery_nace_uses_battery_sector_questions():
    training = TrainingSession(
        hazard_class="Çok Tehlikeli",
        sector="nace_27_20_01",
    )
    codes = {
        question["question_code"]
        for question in _curated_buckets(training)["sector"]
    }
    assert codes
    assert all(code.startswith("TR-SEK-AKU-") for code in codes)


def test_approved_bank_preserves_existing_15_after_fixed_foundational_five(db: Session):
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
    assert readiness["release_ready"] is False
    assert readiness["available"] == {"common": 5, "technical": 5, "sector": 5}

    exam = create_exam_snapshot(db, training=training, created_by_id=user.id)
    assert exam.question_count == QUESTION_COUNT == 20
    assert len(exam.items) == QUESTION_COUNT
    assert [item.position for item in exam.items] == list(range(1, QUESTION_COUNT + 1))
    assert len(exam.content_hash) == 64
    assert len({item.question_code for item in exam.items}) == QUESTION_COUNT
    assert [item.question_code for item in exam.items[:FOUNDATIONAL_QUESTION_COUNT]] == [
        "TR-TEMEL-ISG-001",
        "TR-TEMEL-ISG-002",
        "TR-TEMEL-ISG-003",
        "TR-TEMEL-ISG-004",
        "TR-TEMEL-ISG-005",
    ]
    dynamic_items = exam.items[FOUNDATIONAL_QUESTION_COUNT:]
    assert len(dynamic_items) == 15
    assert sum(item.question_code.startswith("C-") for item in dynamic_items) == 5
    assert sum(item.question_code.startswith("H-") for item in dynamic_items) == 5
    assert sum(item.question_code.startswith("S-") for item in dynamic_items) == 5
    for item in dynamic_items:
        options = __import__("json").loads(item.options_json)
        assert options[item.correct_option] == f"{item.question_code} doğru güvenli uygulama"

    # Banka sorusu sonradan taslakta değişse bile sınav kopyası değişmez.
    frozen_item = next(item for item in exam.items if item.question_id is not None)
    original = frozen_item.question_text
    bank_row = db.get(TrainingQuestion, frozen_item.question_id)
    bank_row.question_text = "Sonradan değiştirilen banka metni"
    db.commit()
    db.refresh(frozen_item)
    assert frozen_item.question_text == original


def test_foundational_five_keep_same_order_options_and_answers_in_every_exam(db: Session):
    training, user = _seed_training(db)
    training.sector = "genel_uretim"
    db.commit()

    first = create_exam_snapshot(
        db,
        training=training,
        created_by_id=user.id,
        allow_curated_fallback=True,
    )
    second = create_exam_snapshot(
        db,
        training=training,
        created_by_id=user.id,
        allow_curated_fallback=True,
    )

    def signature(snapshot):
        return [
            (
                item.position,
                item.question_code,
                item.question_text,
                item.options_json,
                item.correct_option,
                item.scopes_json,
            )
            for item in snapshot.items[:FOUNDATIONAL_QUESTION_COUNT]
        ]

    assert signature(first) == signature(second)
    assert all('"foundation"' in item.scopes_json for item in first.items[:5])


def test_existing_15_question_snapshot_is_upgraded_without_deleting_history(db: Session):
    training, user = _seed_training(db)
    old = TrainingExamSnapshot(
        training_id=training.id,
        version=1,
        question_count=15,
        random_seed="legacy-seed",
        content_hash="0" * 64,
        selection_policy="approved-db-plus-curated-5x3-v1",
        created_by_id=user.id,
    )
    db.add(old)
    db.commit()

    upgraded = _load_or_create_snapshot(db, training, user.id)

    assert upgraded.version == 2
    assert upgraded.question_count == QUESTION_COUNT
    assert len(upgraded.items) == QUESTION_COUNT
    assert db.get(TrainingExamSnapshot, old.id) is old


def test_exam_pdf_is_generated_with_twenty_questions(db: Session):
    training, user = _seed_training(db)
    training.sector = "genel_uretim"
    db.commit()

    pdf = build_exam_pdf(
        company_name="Tersane Test",
        training=training,
        db=db,
        created_by_id=user.id,
    )

    assert pdf.startswith(b"%PDF")
    snapshot = _load_or_create_snapshot(db, training, user.id)
    assert snapshot.question_count == QUESTION_COUNT
    assert len(snapshot.items) == QUESTION_COUNT


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "Kesici-delici yaralanmaları ve tıbbi atıklar - 30 DK "
            "eğitiminin sahada etkili olduğunun göstergesi hangisidir?",
            "Kesici-delici yaralanmaları ve tıbbi atıklar eğitiminin "
            "sahada etkili olduğunun göstergesi hangisidir?",
        ),
        (
            "Makine güvenliği – 45 dk konusu için doğru uygulama hangisidir?",
            "Makine güvenliği konusu için doğru uygulama hangisidir?",
        ),
        (
            "Kimyasal riskler — 25 DK kapsamında hangi kontrol önceliklidir?",
            "Kimyasal riskler kapsamında hangi kontrol önceliklidir?",
        ),
        (
            "Yaralanma en geç 30 dk içinde bildirilmelidir.",
            "Yaralanma en geç 30 dk içinde bildirilmelidir.",
        ),
    ],
)
def test_exam_pdf_question_text_removes_only_generated_topic_duration(
    source: str, expected: str
):
    assert _exam_pdf_question_text(source) == expected


def test_exam_pdf_hides_topic_duration_without_rewriting_snapshot(db: Session):
    training, user = _seed_training(db)
    training.sector = "genel_uretim"
    db.commit()
    snapshot = _load_or_create_snapshot(db, training, user.id)
    item = snapshot.items[FOUNDATIONAL_QUESTION_COUNT]
    stored_question = (
        "Kesici-delici yaralanmaları ve tıbbi atıklar - 30 DK "
        "eğitiminin sahada etkili olduğunun en güvenilir göstergesi hangisidir?"
    )
    item.question_text = stored_question
    db.commit()

    pdf = build_exam_pdf(
        company_name="Tersane Test",
        training=training,
        db=db,
        created_by_id=user.id,
    )
    pdf_text = " ".join(
        (page.extract_text() or "") for page in PdfReader(BytesIO(pdf)).pages
    )
    pdf_text = " ".join(pdf_text.split())

    assert "- 30 DK" not in pdf_text
    assert (
        "Kesici-delici yaralanmaları ve tıbbi atıklar eğitiminin sahada etkili"
        in pdf_text
    )
    db.refresh(item)
    assert item.question_text == stored_question


def test_food_water_hygiene_exam_uses_ten_dedicated_questions(db: Session):
    training, user = _seed_training(db)
    company = db.get(Company, training.company_id)
    training.title = "Gıda ve Su Sektöründe Hijyen Eğitimi"
    training.training_type = "Gıda ve Su Sektöründe Hijyen Eğitimi"
    training.instructor_name = "Dr. Ayşe Yılmaz"
    training.instructor_qualification = "İşyeri Hekimi"
    training.workplace_physician = "Dr. Mehmet Hekim"
    training.sector = "nace_27_20_01"
    company.sgk_registry_no = "22720010112126660100753000"
    training.employer_representative = "Mehmet İşveren"
    training.attendance_verified = True
    training.success_verified = True
    employee = Employee(
        company_id=company.id,
        full_name="Fatma Çalışan",
        job_title="Gıda Üretim Personeli",
        national_id_masked="***********",
    )
    db.add(employee)
    db.flush()
    db.add(TrainingParticipant(training_id=training.id, employee_id=employee.id))
    db.commit()
    db.refresh(training)

    exam = create_exam_snapshot(db, training=training, created_by_id=user.id)

    assert exam.question_count == 10
    assert len(exam.items) == 10
    assert exam.selection_policy == "special-gida-su-hijyeni-v2-20x10"
    assert len({item.question_code for item in exam.items}) == 10
    assert all(item.question_code.startswith("GSH-") for item in exam.items)
    assert all('"gida_su_hijyeni"' in item.scopes_json for item in exam.items)

    pdf = build_exam_pdf(
        company_name="Gıda İşletmesi",
        training=training,
        db=db,
        created_by_id=user.id,
    )
    assert pdf.startswith(b"%PDF")
    assert _load_or_create_snapshot(db, training, user.id).id == exam.id

    employees = {employee.id: employee}
    certificate_text = "\n".join(
        page.extract_text() or ""
        for page in PdfReader(
            BytesIO(
                build_certificates_pdf(
                    company_name=company.name,
                    training=training,
                    employees=employees,
                )
            )
        ).pages
    )
    attendance_text = "\n".join(
        page.extract_text() or ""
        for page in PdfReader(
            BytesIO(
                build_attendance_pdf(
                    company_name=company.name,
                    training=training,
                    employees=employees,
                    workplace_sgk_registry_no=company.sgk_registry_no,
                    nace_code=company.nace_code,
                    physician_name=training.workplace_physician,
                )
            )
        ).pages
    )
    assert "GIDA VE SU SEKTÖRÜNDE HİJYEN EĞİTİMİ KATILIM BELGESİ" in certificate_text
    assert "Eğitimi Veren Sağlık Personeli" in certificate_text
    assert "GIDA VE SU SEKTÖRÜNDE HİJYEN EĞİTİMİ" in attendance_text
    assert "Eğitimi Veren Sağlık Personeli" in attendance_text
    assert "22720010112126660100753000" in attendance_text
    assert "27.20.01" in attendance_text
    assert "Elektrik akümülatör parçalarının imalatı" in attendance_text
    assert "Dr. Mehmet Hekim" in attendance_text



def test_employee_exam_has_identity_fields_and_no_answer_key(db: Session):
    training, user = _seed_training(db)
    company = db.get(Company, training.company_id)
    company.sgk_registry_no = "12345678901234567890123"
    training.sector = "nace_30_11_01"
    employee = Employee(
        company_id=company.id,
        full_name="Ayşe Yılmaz",
        national_id_masked="***********",
    )
    db.add(employee)
    db.flush()
    db.add(TrainingParticipant(training_id=training.id, employee_id=employee.id))
    db.commit()

    employee_pdf = build_exam_pdf(
        company_name=company.name,
        training=training,
        db=db,
        created_by_id=user.id,
    )
    employee_text = "\n".join(
        page.extract_text() or "" for page in PdfReader(BytesIO(employee_pdf)).pages
    )
    assert "Ayşe Yılmaz" in employee_text
    assert "Tersane Test" in employee_text
    assert "12345678901234567890123" in employee_text
    assert "CEVAP ANAHTARI" not in employee_text
    assert "nace_30_11_01" not in employee_text

    answer_pdf = build_exam_pdf(
        company_name=company.name,
        training=training,
        db=db,
        created_by_id=user.id,
        include_answer_key=True,
        answer_key_only=True,
    )
    answer_text = "\n".join(
        page.extract_text() or "" for page in PdfReader(BytesIO(answer_pdf)).pages
    )
    assert "CEVAP ANAHTARI" in answer_text
    assert "Ayşe Yılmaz" not in answer_text


def test_retired_latest_terminal_version_does_not_reactivate_old_version(db: Session):
    training, user = _seed_training(db)
    _question(db, code="VERSIONED", scope_type="common", scope_value="*", creator=user.id)
    _question(
        db,
        code="VERSIONED",
        scope_type="common",
        scope_value="*",
        creator=user.id,
        version=2,
        status="retired",
    )
    db.commit()
    readiness = question_bank_readiness(db, training)
    assert readiness["available"]["common"] == 0


def test_coverage_reports_every_official_nace_and_general_fallback(db: Session):
    report = question_bank_coverage(db)
    assert report["catalog_records_total"] == 2142
    assert report["nace_total"] == 2141
    assert report["general_fallback_total"] == 1
    assert report["profile_total"] == 108
    assert report["exam_ready_count"] == 0
    assert report["release_ready_count"] == 0
    assert report["blocked_count"] == 2141
    assert len(report["items"]) == 2141


def test_coverage_index_preserves_common_hazard_and_nace_buckets(db: Session):
    _, user = _seed_training(db)
    _question(db, code="COV-C", scope_type="common", scope_value="*", creator=user.id)
    _question(
        db,
        code="COV-H",
        scope_type="hazard",
        scope_value="Çok Tehlikeli",
        creator=user.id,
    )
    _question(db, code="COV-N", scope_type="nace", scope_value="30.11", creator=user.id)
    db.commit()

    report = question_bank_coverage(db)
    item = next(row for row in report["items"] if row["nace"] == "30.11.01")
    assert item["available"] == {"common": 1, "technical": 1, "sector": 1}
