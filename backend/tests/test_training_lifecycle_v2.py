from __future__ import annotations

import json
from datetime import date, datetime
from types import SimpleNamespace

import pytest

from app.schemas.training import TrainingCreate
from app.services.training_lifecycle_v2 import (
    PremiumTrainingLifecycleMiddleware,
    applies_to_created_at,
    duration_hours,
    install_training_lifecycle_v2,
    premium_lifecycle_active,
    public_policy,
    training_kind,
)


@pytest.fixture(autouse=True)
def lifecycle_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TRAINING_PREMIUM_LIFECYCLE_V2_ENABLED", "true")
    monkeypatch.setenv("TRAINING_PREMIUM_LIFECYCLE_V2_FORCE_OFF", "false")
    monkeypatch.delenv("TRAINING_PREMIUM_LIFECYCLE_V2_AFTER", raising=False)
    install_training_lifecycle_v2()


def test_official_2026_duration_policy_is_explicit():
    assert training_kind("İşe Başlama Eğitimi") == "work_start"
    assert duration_hours(
        training_type="İşe Başlama Eğitimi",
        title="İşe Başlama",
        hazard_class="Çok Tehlikeli",
    ) == 2
    assert duration_hours(
        training_type="Tekrar",
        title="Temel İSG",
        hazard_class="Çok Tehlikeli",
    ) == 8
    assert duration_hours(
        training_type="Bilgi Yenileme Eğitimi",
        title="Bilgi Yenileme",
        hazard_class="Çok Tehlikeli",
    ) == 4
    assert duration_hours(
        training_type="İlk Defa",
        title="Temel İSG",
        hazard_class="Çok Tehlikeli",
    ) == 16


def test_force_off_is_single_step_rollback(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TRAINING_PREMIUM_LIFECYCLE_V2_FORCE_OFF", "true")
    assert premium_lifecycle_active() is False
    assert public_policy()["enabled"] is False
    assert public_policy()["safety"]["migration_required"] is False


def test_cutover_preserves_historical_records(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TRAINING_PREMIUM_LIFECYCLE_V2_AFTER", "2026-08-09T06:00:00Z")
    assert applies_to_created_at(datetime(2026, 8, 9, 5, 59, 59)) is False
    assert applies_to_created_at(datetime(2026, 8, 9, 6, 0, 0)) is True


def test_new_training_request_never_preconfirms_attendance_or_success():
    body = json.dumps(
        {
            "training_type": "İşe Başlama Eğitimi",
            "title": "İşe Başlama İş Sağlığı ve Güvenliği Eğitimi",
            "delivery_method": "Uzaktan",
            "attendance_verified": True,
            "success_verified": True,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    rewritten = json.loads(PremiumTrainingLifecycleMiddleware._rewrite_new_training(body))
    assert rewritten["attendance_verified"] is False
    assert rewritten["success_verified"] is False
    assert rewritten["delivery_method"] == "Yüz yüze"


def test_repeat_training_validation_uses_eight_lesson_hours():
    payload = TrainingCreate(
        company_id=1,
        title="Tekrar Temel İş Sağlığı ve Güvenliği Eğitimi",
        training_type="Tekrar",
        delivery_method="Yüz yüze",
        location="Eğitim Salonu",
        start_date=date(2026, 8, 10),
        end_date=date(2026, 8, 10),
        hazard_class="Çok Tehlikeli",
        sector="nace_20_30_90",
        instructor_name="Abdullah Bozkır",
        evaluation_method="Sınav",
        passing_score=70,
        participant_ids=[1],
    )
    assert payload.training_type == "Tekrar"
    assert payload.hazard_class == "Çok Tehlikeli"


def test_work_start_training_can_be_planned_in_one_day():
    payload = TrainingCreate(
        company_id=1,
        title="İşe Başlama İş Sağlığı ve Güvenliği Eğitimi",
        training_type="İşe Başlama Eğitimi",
        delivery_method="Yüz yüze",
        location="İşyeri",
        start_date=date(2026, 8, 10),
        end_date=date(2026, 8, 10),
        hazard_class="Çok Tehlikeli",
        sector="nace_20_30_90",
        instructor_name="Abdullah Bozkır",
        evaluation_method="Katılım yeterlidir",
        participant_ids=[1],
    )
    assert payload.training_type == "İşe Başlama Eğitimi"


def test_work_start_does_not_satisfy_basic_renewal_tracking():
    from app.api import trainings

    row = SimpleNamespace(
        training_type="İşe Başlama Eğitimi",
        title="İşe Başlama İş Sağlığı ve Güvenliği Eğitimi",
        notes="",
        created_at=datetime(2026, 8, 9, 7, 0, 0),
    )
    assert trainings._is_basic_training(row) is False


def test_historical_work_start_keeps_legacy_predicate(monkeypatch: pytest.MonkeyPatch):
    from app.api import trainings

    monkeypatch.setenv("TRAINING_PREMIUM_LIFECYCLE_V2_AFTER", "2026-08-09T08:00:00Z")
    row = SimpleNamespace(
        training_type="İşe Başlama Eğitimi",
        title="İşe Başlama İş Sağlığı ve Güvenliği Eğitimi",
        notes="",
        created_at=datetime(2026, 8, 9, 7, 0, 0),
    )
    # Historical compatibility: this record predates the premium cutover, so the
    # old predicate remains untouched even if its free-text title resembles the
    # new work-start type.
    assert trainings._is_basic_training(row) is True


def test_work_start_attendance_pdf_uses_explicit_record_contract():
    from app.services import training_pdfs

    row = SimpleNamespace(
        training_type="İşe Başlama Eğitimi",
        title="İşe Başlama İş Sağlığı ve Güvenliği Eğitimi",
        notes="",
        created_at=datetime(2026, 8, 9, 7, 0, 0),
        sector="nace_20_30_90",
        hazard_class="Çok Tehlikeli",
    )
    curriculum = training_pdfs.resolve_training_curriculum(row)
    assert curriculum["attendance_title"] == "İŞE BAŞLAMA İŞ SAĞLIĞI VE GÜVENLİĞİ EĞİTİMİ"
    assert curriculum["duration_label"] == "EN AZ 2 SAAT"
    assert curriculum["is_special"] is True
    assert "Temel İSG Eğitimi yerine geçmez" in curriculum["disclaimer"]


def test_work_start_cannot_generate_misleading_basic_certificate():
    from app.services import training_completion

    row = SimpleNamespace(
        training_type="İşe Başlama Eğitimi",
        title="İşe Başlama İş Sağlığı ve Güvenliği Eğitimi",
        created_at=datetime(2026, 8, 9, 7, 0, 0),
    )
    with pytest.raises(ValueError, match="Temel İSG katılım belgesi oluşturulmaz"):
        training_completion._compliant_certificate_pdf(
            None,
            company_name="Test",
            training=row,
            employees={},
            participants=[],
        )
