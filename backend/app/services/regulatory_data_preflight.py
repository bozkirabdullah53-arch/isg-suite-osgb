"""Read-only data preflight for İBYS and İSBS/e-Reçete application testing.

No undocumented Ministry field is declared mandatory.  The report highlights
high-confidence local data quality/security indicators and explicitly labels
authority-data-dictionary requirements as pending.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    Company,
    Employee,
    HealthRecord,
    IsgProfessional,
    Prescription,
    PrescriptionStatus,
    ProfessionalType,
    TrainingSession,
)


def _looks_like_full_identity(value: str | None) -> bool:
    text = "".join(ch for ch in str(value or "") if ch.isdigit())
    return len(text) in {10, 11} and "*" not in str(value or "")


def build_regulatory_data_preflight(db: Session, *, osgb_id: int | None = None) -> dict[str, Any]:
    companies_stmt = select(Company).where(Company.is_active.is_(True))
    if osgb_id is not None:
        companies_stmt = companies_stmt.where(Company.osgb_id == osgb_id)
    companies = list(db.scalars(companies_stmt).all())
    company_ids = [c.id for c in companies]

    employees: list[Employee] = []
    professionals: list[IsgProfessional] = []
    prescriptions: list[Prescription] = []
    if company_ids:
        employees = list(
            db.scalars(
                select(Employee).where(Employee.company_id.in_(company_ids), Employee.is_active.is_(True))
            ).all()
        )
        prescriptions = list(db.scalars(select(Prescription).where(Prescription.company_id.in_(company_ids))).all())
    if osgb_id is not None:
        professionals = list(
            db.scalars(
                select(IsgProfessional).where(
                    IsgProfessional.osgb_id == osgb_id,
                    IsgProfessional.is_active.is_(True),
                )
            ).all()
        )
    else:
        professionals = list(db.scalars(select(IsgProfessional).where(IsgProfessional.is_active.is_(True))).all())

    identity_rows: list[Any] = []
    identity_table_available = True
    try:
        from app.models.regulatory_identity import RegulatoryIdentity

        if company_ids:
            identity_rows = list(
                db.scalars(select(RegulatoryIdentity).where(RegulatoryIdentity.company_id.in_(company_ids))).all()
            )
    except Exception:
        identity_table_available = False
        db.rollback()

    identity_employee_ids = {int(r.employee_id) for r in identity_rows}
    legacy_full_identity = [e.id for e in employees if _looks_like_full_identity(e.national_id_masked)]
    missing_identity_vault = [e.id for e in employees if e.id not in identity_employee_ids]

    training_rows: list[TrainingSession] = []
    health_rows: list[HealthRecord] = []
    if company_ids:
        training_rows = list(
            db.scalars(select(TrainingSession).where(TrainingSession.company_id.in_(company_ids))).all()
        )
        health_rows = list(
            db.scalars(
                select(HealthRecord).where(
                    HealthRecord.company_id.in_(company_ids),
                    HealthRecord.deleted_at.is_(None),
                )
            ).all()
        )

    professional_identity_rows: list[Any] = []
    professional_identity_table_available = True
    try:
        from app.models.regulatory_identity import ProfessionalRegulatoryIdentity

        professional_ids = [p.id for p in professionals]
        if professional_ids:
            professional_identity_rows = list(
                db.scalars(
                    select(ProfessionalRegulatoryIdentity).where(
                        ProfessionalRegulatoryIdentity.professional_id.in_(professional_ids)
                    )
                ).all()
            )
    except Exception:
        professional_identity_table_available = False
        db.rollback()

    professional_identity_ids = {
        int(r.professional_id) for r in professional_identity_rows
        if str(r.identity_type) == "tckn"
    }
    linked_instructor_ids = {
        int(t.instructor_professional_id)
        for t in training_rows
        if t.instructor_professional_id is not None
    }
    trainings_without_professional_link = [
        t.id for t in training_rows if t.instructor_professional_id is None
    ]
    linked_instructors_without_tckn = sorted(
        linked_instructor_ids - professional_identity_ids
    )

    structured_anamnesis_fields = (
        "anamnesis_chronic_diseases",
        "anamnesis_past_medical_history",
        "anamnesis_family_history",
        "anamnesis_current_medications",
        "anamnesis_allergies",
        "anamnesis_smoking_status",
        "anamnesis_occupational_history",
        "anamnesis_previous_exposures",
        "anamnesis_current_complaints",
    )
    health_with_structured_anamnesis = sum(
        1
        for row in health_rows
        if any(getattr(row, field, None) not in (None, "") for field in structured_anamnesis_fields)
    )
    health_with_diagnosis = sum(1 for row in health_rows if getattr(row, "diagnosis", None))
    health_with_lab_summary = sum(
        1 for row in health_rows if getattr(row, "laboratory_result_summary", None)
    )

    physicians = [p for p in professionals if p.professional_type == ProfessionalType.WORKPLACE_PHYSICIAN]
    physicians_missing_certificate = [p.id for p in physicians if not (p.certificate_number or "").strip()]

    ready_prescriptions = [p.id for p in prescriptions if p.status == PrescriptionStatus.READY]
    sending_prescriptions = [p.id for p in prescriptions if p.status == PrescriptionStatus.SENDING]

    company_quality = {
        "active": len(companies),
        "missing_sgk_registry_no": sum(1 for c in companies if not (c.sgk_registry_no or "").strip()),
        "missing_nace_code": sum(1 for c in companies if not (c.nace_code or "").strip()),
        "missing_hazard_class": sum(1 for c in companies if not (c.hazard_class or "").strip()),
    }
    employee_quality = {
        "active": len(employees),
        "identity_vault_table_available": identity_table_available,
        "identity_vault_rows": len(identity_rows),
        "employees_missing_identity_vault": len(missing_identity_vault),
        "legacy_fields_that_look_like_full_identity": len(legacy_full_identity),
        "legacy_full_identity_employee_ids_sample": legacy_full_identity[:20],
    }
    physician_quality = {
        "active_workplace_physicians": len(physicians),
        "missing_certificate_number": len(physicians_missing_certificate),
    }
    training_quality = {
        "total": len(training_rows),
        "professional_identity_table_available": professional_identity_table_available,
        "linked_to_professional": len(training_rows) - len(trainings_without_professional_link),
        "missing_instructor_professional_link": len(trainings_without_professional_link),
        "missing_instructor_professional_link_sample": trainings_without_professional_link[:20],
        "linked_instructors_missing_tckn": len(linked_instructors_without_tckn),
        "linked_instructors_missing_tckn_sample": linked_instructors_without_tckn[:20],
    }
    health_quality = {
        "total": len(health_rows),
        "with_structured_anamnesis": health_with_structured_anamnesis,
        "with_diagnosis": health_with_diagnosis,
        "with_laboratory_result_summary": health_with_lab_summary,
    }
    prescription_quality = {
        "total": len(prescriptions),
        "ready_for_local_preflight": len(ready_prescriptions),
        "sending": len(sending_prescriptions),
        "approved": sum(1 for p in prescriptions if p.status == PrescriptionStatus.APPROVED),
        "rejected": sum(1 for p in prescriptions if p.status == PrescriptionStatus.REJECTED),
    }

    high_priority = []
    if employee_quality["legacy_fields_that_look_like_full_identity"]:
        high_priority.append("Legacy Employee.national_id_masked alanında tam kimlik gibi görünen değerler var; test başvurusundan önce vault'a taşınıp maskelenmeli.")
    if not identity_table_available:
        high_priority.append("Regulatory identity vault migration henüz uygulanmamış.")
    if company_quality["missing_sgk_registry_no"]:
        high_priority.append("Aktif işyerlerinde SGK sicil no eksikleri var.")
    if company_quality["missing_nace_code"]:
        high_priority.append("Aktif işyerlerinde NACE kodu eksikleri var.")
    if physician_quality["missing_certificate_number"]:
        high_priority.append("Aktif işyeri hekimlerinde sertifika numarası eksikleri var.")
    if not professional_identity_table_available:
        high_priority.append("Profesyonel/eğitici Regulatory Identity Vault migration henüz uygulanmamış.")
    if training_quality["missing_instructor_professional_link"]:
        high_priority.append(
            "Eğitim kayıtlarında eğitici-profesyonel bağlantısı eksik; İBYS eğitici TCKN eşlemesi için bağlanmalı."
        )
    if training_quality["linked_instructors_missing_tckn"]:
        high_priority.append(
            "Profesyonel bağlantısı olan bazı eğiticilerin şifreli TCKN kaydı eksik."
        )

    return {
        "preflight_version": "regulatory-data-preflight-v1",
        "osgb_id": osgb_id,
        "companies": company_quality,
        "employees": employee_quality,
        "physicians": physician_quality,
        "trainings": training_quality,
        "health_surveillance": health_quality,
        "prescriptions": prescription_quality,
        "high_priority_findings": high_priority,
        "authority_data_dictionary_pending": True,
        "note": (
            "Bu kontrol yalnız yerel veri kalitesi/güvenlik ön kontrolüdür. "
            "İBYS veya İSBS resmî veri sözlüğü yerine geçmez; Bakanlık test profili geldiğinde alan eşleme kuralları ayrıca uygulanır."
        ),
    }
