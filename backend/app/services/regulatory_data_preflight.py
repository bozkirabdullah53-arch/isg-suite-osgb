"""Read-only data preflight for İBYS and İSBS/e-Reçete application testing.

No undocumented Ministry field is declared mandatory.  The report highlights
high-confidence local data quality/security indicators and explicitly labels
authority-data-dictionary requirements as pending.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Company, Employee, IsgProfessional, Prescription, PrescriptionStatus, ProfessionalType


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

    return {
        "preflight_version": "regulatory-data-preflight-v1",
        "osgb_id": osgb_id,
        "companies": company_quality,
        "employees": employee_quality,
        "physicians": physician_quality,
        "prescriptions": prescription_quality,
        "high_priority_findings": high_priority,
        "authority_data_dictionary_pending": True,
        "note": (
            "Bu kontrol yalnız yerel veri kalitesi/güvenlik ön kontrolüdür. "
            "İBYS veya İSBS resmî veri sözlüğü yerine geçmez; Bakanlık test profili geldiğinde alan eşleme kuralları ayrıca uygulanır."
        ),
    }
