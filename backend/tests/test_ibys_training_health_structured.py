from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.entities import IsgProfessional, OsgbOrganization, ProfessionalType
from app.models.regulatory_identity import ProfessionalRegulatoryIdentity
from app.schemas.health import HealthRecordCreate
from app.services.health_field_crypto import decrypt_field, encrypt_payload
from app.services.regulatory_identity_vault import (
    professional_identity_for_authority,
    public_professional_identity_status,
    upsert_professional_identity,
)


def test_professional_regulatory_identity_is_encrypted_and_public_status_is_masked(monkeypatch):
    monkeypatch.setenv("REGULATORY_IDENTITY_ENCRYPTION_KEY", "P" * 48)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        osgb = OsgbOrganization(name="IBYS Test OSGB", is_active=True)
        db.add(osgb)
        db.flush()
        professional = IsgProfessional(
            osgb_id=osgb.id,
            full_name="Test Eğitmen",
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            certificate_class="A",
            certificate_number="TEST-001",
            is_active=True,
        )
        db.add(professional)
        db.flush()

        synthetic_tckn = "10000000146"
        row = upsert_professional_identity(
            db,
            osgb_id=osgb.id,
            professional_id=professional.id,
            identity_type="tckn",
            raw_value=synthetic_tckn,
        )
        db.commit()

        assert isinstance(row, ProfessionalRegulatoryIdentity)
        assert synthetic_tckn not in row.ciphertext
        assert row.masked_value == "*******0146"

        public = public_professional_identity_status(
            db, osgb_id=osgb.id, professional_id=professional.id
        )
        assert public["full_identity_exposed"] is False
        assert public["identities"][0]["masked_value"] == "*******0146"
        assert synthetic_tckn not in str(public)

        assert professional_identity_for_authority(
            db, osgb_id=osgb.id, professional_id=professional.id
        ) == synthetic_tckn


def test_structured_anamnesis_schema_accepts_ibys_health_fields():
    payload = HealthRecordCreate(
        company_id=1,
        employee_id=2,
        examination_date=date(2026, 9, 1),
        informed_consent=True,
        diagnosis="Mesleki maruziyet yönünden klinik değerlendirme",
        laboratory_result_summary="Laboratuvar sonuçları hekim tarafından değerlendirildi.",
        anamnesis_chronic_diseases="Hipertansiyon öyküsü",
        anamnesis_past_medical_history="Geçirilmiş operasyon yok",
        anamnesis_family_history="Özellik yok",
        anamnesis_current_medications="Düzenli ilaç bilgisi",
        anamnesis_allergies="Bilinen alerji yok",
        anamnesis_smoking_status="former",
        anamnesis_smoking_pack_years=7.5,
        anamnesis_alcohol_use="Kullanmıyor",
        anamnesis_occupational_history="10 yıl metal sektörü",
        anamnesis_previous_exposures="Gürültü ve metal dumanı",
        anamnesis_current_complaints="Aktif yakınma yok",
    )
    assert payload.anamnesis_smoking_pack_years == 7.5
    assert payload.diagnosis
    assert payload.laboratory_result_summary


def test_structured_anamnesis_sensitive_text_is_encrypted(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "health_field_encryption_enabled", True)
    monkeypatch.setattr(settings, "health_field_encryption_key", "H" * 48)

    plain = {
        "diagnosis": "Gizli klinik tanı",
        "laboratory_result_summary": "Gizli laboratuvar özeti",
        "anamnesis_family_history": "Gizli aile öyküsü",
        "anamnesis_current_complaints": "Gizli yakınma",
    }
    encrypted = encrypt_payload(plain)

    for key, value in plain.items():
        assert encrypted[key].startswith("enc:v1:")
        assert value not in encrypted[key]
        assert decrypt_field(encrypted[key]) == value



def test_instructor_readiness_backfill_is_masked_and_exact_scope(monkeypatch):
    import json

    from app.api.trainings import instructor_regulatory_readiness
    from app.models.entities import (
        Company,
        TrainingSession,
        User,
        UserRole,
    )

    monkeypatch.setenv("REGULATORY_IDENTITY_ENCRYPTION_KEY", "Q" * 48)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        osgb = OsgbOrganization(name="Readiness OSGB", is_active=True)
        db.add(osgb)
        db.flush()
        company = Company(
            name="Readiness Firma",
            osgb_id=osgb.id,
            hazard_class="Tehlikeli",
            is_active=True,
        )
        db.add(company)
        db.flush()
        manager = User(
            email="readiness-global@test.local",
            full_name="Readiness Global",
            hashed_password="not-used-in-unit-test",
            role=UserRole.GLOBAL_ADMIN,
            is_active=True,
        )
        professional = IsgProfessional(
            osgb_id=osgb.id,
            full_name="Test Eğitmen",
            professional_type=ProfessionalType.SAFETY_SPECIALIST,
            certificate_class="A",
            certificate_number="EGT-A-001",
            is_active=True,
        )
        db.add_all([manager, professional])
        db.flush()
        training = TrainingSession(
            company_id=company.id,
            title="Readiness Eğitimi",
            training_type="İlk Defa",
            delivery_method="Yüz yüze",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 2),
            duration_hours=12,
            renewal_years=2,
            hazard_class="Tehlikeli",
            sector="nace_test",
            instructor_name="  TEST   EĞİTMEN ",
            evaluation_method="Sınav",
            attendance_verified=True,
            success_verified=True,
            created_by_id=manager.id,
        )
        db.add(training)
        db.commit()

        first = instructor_regulatory_readiness(
            company_id=None,
            include_archived=True,
            db=db,
            user=manager,
        )
        assert first["full_identity_exposed"] is False
        assert first["counts"]["link_available"] == 1
        assert first["rows"][0]["candidate_professionals"][0]["professional_id"] == professional.id
        assert first["rows"][0]["identities"] == []

        synthetic_tckn = "10000000146"
        upsert_professional_identity(
            db,
            osgb_id=osgb.id,
            professional_id=professional.id,
            identity_type="tckn",
            raw_value=synthetic_tckn,
        )
        training.instructor_professional_id = professional.id
        db.commit()

        ready = instructor_regulatory_readiness(
            company_id=None,
            include_archived=True,
            db=db,
            user=manager,
        )
        assert ready["counts"]["ready"] == 1
        row = ready["rows"][0]
        assert row["status"] == "ready"
        assert row["identities"][0]["masked_value"] == "*******0146"
        assert synthetic_tckn not in json.dumps(ready, ensure_ascii=False)
