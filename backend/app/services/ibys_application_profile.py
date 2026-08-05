"""İBYS entegratör başvurusu için sözleşmeden bağımsız aday veri profili.

Bu modül Bakanlığın resmî veri şemasını TAKLİT ETMEZ ve resmî uygunluk iddiası
üretmez. Amaç; resmî sözleşme teslim edildiğinde yalnız profil/eşleme katmanının
güncellenmesiyle kullanılabilecek deterministik doğrulama, kayıt parmak izi,
idempotency ve kabul/ret raporlama altyapısı sağlamaktır.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

APPLICATION_PROFILE_VERSION = "application-candidate-v1"
CONTRACT_STATUS = "awaiting_ministry_contract"
VOLATILE_KEYS = frozenset({"created_at", "updated_at", "exported_at", "sent_at"})


@dataclass(frozen=True)
class FieldMapping:
    field: str
    internal_source: str
    required_for_demo: bool = False
    sensitive: bool = False
    official_field: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class DatasetDefinition:
    code: str
    title: str
    internal_entity: str
    official_dataset_code: str | None
    fields: tuple[FieldMapping, ...]


DATASETS: tuple[DatasetDefinition, ...] = (
    DatasetDefinition(
        code="workplace",
        title="İşyeri",
        internal_entity="Company",
        official_dataset_code=None,
        fields=(
            FieldMapping("source_id", "Company.id", True),
            FieldMapping("name", "Company.name", True),
            FieldMapping("sgk_registry_no", "Company.sgk_registry_no", True, True),
            FieldMapping("nace_code", "Company.nace_code", True),
            FieldMapping("hazard_class", "Company.hazard_class", True),
            FieldMapping("tax_number", "Company.tax_number", False, True),
            FieldMapping("address", "Company.address"),
            FieldMapping("active", "Company.is_active", True),
        ),
    ),
    DatasetDefinition(
        code="employee",
        title="Çalışan",
        internal_entity="Employee",
        official_dataset_code=None,
        fields=(
            FieldMapping("source_id", "Employee.id", True),
            FieldMapping("workplace_source_id", "Employee.company_id", True),
            FieldMapping("full_name", "Employee.full_name", True, True),
            FieldMapping("national_identifier", "Employee.national_id", True, True, note="Demo çıktısında maskelenir; gerçek gönderim resmî sözleşmeye bağlıdır."),
            FieldMapping("job_title", "Employee.job_title"),
            FieldMapping("department", "Employee.department"),
            FieldMapping("start_date", "Employee.start_date"),
            FieldMapping("active", "Employee.is_active", True),
        ),
    ),
    DatasetDefinition(
        code="professional_assignment",
        title="İSG Profesyoneli Görevlendirmesi",
        internal_entity="WorkplaceAssignment",
        official_dataset_code=None,
        fields=(
            FieldMapping("source_id", "WorkplaceAssignment.id", True),
            FieldMapping("workplace_source_id", "WorkplaceAssignment.company_id", True),
            FieldMapping("professional_source_id", "WorkplaceAssignment.professional_id", True),
            FieldMapping("professional_type", "IsgProfessional.professional_type", True),
            FieldMapping("certificate_number", "IsgProfessional.certificate_number", True, True),
            FieldMapping("katip_contract_number", "WorkplaceAssignment.katip_contract_number", False, True),
            FieldMapping("status", "WorkplaceAssignment.status", True),
        ),
    ),
    DatasetDefinition(
        code="training",
        title="İSG Eğitimi",
        internal_entity="TrainingRecord",
        official_dataset_code=None,
        fields=(
            FieldMapping("source_id", "TrainingRecord.id", True),
            FieldMapping("workplace_source_id", "TrainingRecord.company_id", True),
            FieldMapping("employee_source_id", "TrainingRecord.employee_id", True),
            FieldMapping("training_title", "TrainingRecord.title", True),
            FieldMapping("training_date", "TrainingRecord.training_date", True),
            FieldMapping("duration_minutes", "TrainingRecord.duration_minutes", True),
            FieldMapping("trainer", "TrainingRecord.trainer_name", True, True),
        ),
    ),
    DatasetDefinition(
        code="health_surveillance",
        title="Sağlık Gözetimi",
        internal_entity="HealthRecord",
        official_dataset_code=None,
        fields=(
            FieldMapping("source_id", "HealthRecord.id", True),
            FieldMapping("workplace_source_id", "HealthRecord.company_id", True),
            FieldMapping("employee_source_id", "HealthRecord.employee_id", True),
            FieldMapping("exam_date", "HealthRecord.exam_date", True, True),
            FieldMapping("exam_type", "HealthRecord.exam_type", True, True),
            FieldMapping("fitness_result", "HealthRecord.fitness_result", True, True),
            FieldMapping("physician_source_id", "HealthRecord.physician_id", True, True),
        ),
    ),
    DatasetDefinition(
        code="risk_assessment",
        title="Risk Değerlendirmesi",
        internal_entity="RiskAssessment",
        official_dataset_code=None,
        fields=(
            FieldMapping("source_id", "RiskAssessment.id", True),
            FieldMapping("workplace_source_id", "RiskAssessment.company_id", True),
            FieldMapping("assessment_date", "RiskAssessment.assessment_date", True),
            FieldMapping("method", "RiskAssessment.method", True),
            FieldMapping("revision_no", "RiskAssessment.revision_no", True),
            FieldMapping("status", "RiskAssessment.status", True),
        ),
    ),
    DatasetDefinition(
        code="incident",
        title="İş Kazası / Ramak Kala",
        internal_entity="Incident",
        official_dataset_code=None,
        fields=(
            FieldMapping("source_id", "Incident.id", True),
            FieldMapping("workplace_source_id", "Incident.company_id", True),
            FieldMapping("incident_type", "Incident.incident_type", True),
            FieldMapping("occurred_at", "Incident.occurred_at", True, True),
            FieldMapping("employee_source_id", "Incident.employee_id", False, True),
            FieldMapping("severity", "Incident.severity", True),
            FieldMapping("status", "Incident.status", True),
        ),
    ),
    DatasetDefinition(
        code="occupational_disease",
        title="Meslek Hastalığı",
        internal_entity="OccupationalDiseaseRecord",
        official_dataset_code=None,
        fields=(
            FieldMapping("source_id", "OccupationalDiseaseRecord.id", True),
            FieldMapping("workplace_source_id", "OccupationalDiseaseRecord.company_id", True),
            FieldMapping("employee_source_id", "OccupationalDiseaseRecord.employee_id", True, True),
            FieldMapping("diagnosis_code", "OccupationalDiseaseRecord.diagnosis_code", True, True, note="ICD-10 veya Bakanlık sözleşmesindeki kod sistemiyle eşlenecektir."),
            FieldMapping("diagnosis_date", "OccupationalDiseaseRecord.diagnosis_date", True, True),
            FieldMapping("status", "OccupationalDiseaseRecord.status", True),
        ),
    ),
    DatasetDefinition(
        code="site_visit",
        title="Saha Ziyareti",
        internal_entity="SiteVisit",
        official_dataset_code=None,
        fields=(
            FieldMapping("source_id", "SiteVisit.id", True),
            FieldMapping("workplace_source_id", "SiteVisit.company_id", True),
            FieldMapping("professional_source_id", "SiteVisit.professional_id", True),
            FieldMapping("visit_date", "SiteVisit.visit_date", True),
            FieldMapping("duration_minutes", "SiteVisit.duration_minutes", True),
            FieldMapping("notes_present", "SiteVisit.notes", False, True),
        ),
    ),
    DatasetDefinition(
        code="finding_recommendation",
        title="Tespit ve Öneri / DÖF",
        internal_entity="CorrectiveAction",
        official_dataset_code=None,
        fields=(
            FieldMapping("source_id", "CorrectiveAction.id", True),
            FieldMapping("workplace_source_id", "CorrectiveAction.company_id", True),
            FieldMapping("finding_date", "CorrectiveAction.finding_date", True),
            FieldMapping("finding", "CorrectiveAction.finding", True, True),
            FieldMapping("recommendation", "CorrectiveAction.recommendation", True, True),
            FieldMapping("due_date", "CorrectiveAction.due_date"),
            FieldMapping("status", "CorrectiveAction.status", True),
        ),
    ),
    DatasetDefinition(
        code="emergency_plan",
        title="Acil Durum Planı",
        internal_entity="EmergencyPlan",
        official_dataset_code=None,
        fields=(
            FieldMapping("source_id", "EmergencyPlan.id", True),
            FieldMapping("workplace_source_id", "EmergencyPlan.company_id", True),
            FieldMapping("plan_date", "EmergencyPlan.plan_date", True),
            FieldMapping("revision_no", "EmergencyPlan.revision_no", True),
            FieldMapping("status", "EmergencyPlan.status", True),
        ),
    ),
    DatasetDefinition(
        code="periodic_control",
        title="Periyodik Kontrol / Ölçüm",
        internal_entity="PeriodicControlRecord",
        official_dataset_code=None,
        fields=(
            FieldMapping("source_id", "PeriodicControlRecord.id", True),
            FieldMapping("workplace_source_id", "PeriodicControlRecord.company_id", True),
            FieldMapping("equipment_source_id", "PeriodicControlRecord.equipment_id", True),
            FieldMapping("control_date", "PeriodicControlRecord.control_date", True),
            FieldMapping("next_control_date", "PeriodicControlRecord.next_control_date", True),
            FieldMapping("result", "PeriodicControlRecord.result", True),
            FieldMapping("inspector", "PeriodicControlRecord.inspector_name", True, True),
        ),
    ),
)

_DATASET_BY_CODE = {item.code: item for item in DATASETS}


def dataset_codes() -> tuple[str, ...]:
    return tuple(item.code for item in DATASETS)


def build_application_mapping_matrix() -> dict[str, Any]:
    return {
        "profile_version": APPLICATION_PROFILE_VERSION,
        "contract_status": CONTRACT_STATUS,
        "official_compliance_claim": False,
        "note": "Resmî İBYS şeması teslim edildiğinde official_dataset_code/official_field alanları doldurulacaktır.",
        "datasets": [
            {
                **asdict(dataset),
                "fields": [asdict(field) for field in dataset.fields],
                "required_demo_fields": [field.field for field in dataset.fields if field.required_for_demo],
            }
            for dataset in DATASETS
        ],
    }


def _canonical_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, dict):
        return {
            str(key): _canonical_value(val)
            for key, val in sorted(value.items(), key=lambda item: str(item[0]))
            if str(key) not in VOLATILE_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    return value


def canonical_record_hash(dataset_code: str, record: dict[str, Any]) -> str:
    if dataset_code not in _DATASET_BY_CODE:
        raise ValueError(f"unknown dataset: {dataset_code}")
    canonical = json.dumps(
        {"dataset": dataset_code, "record": _canonical_value(record)},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def validate_candidate_records(dataset_code: str, records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    dataset = _DATASET_BY_CODE.get(dataset_code)
    if dataset is None:
        raise ValueError(f"unknown dataset: {dataset_code}")
    required = tuple(field.field for field in dataset.fields if field.required_for_demo)
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        missing = [
            field
            for field in required
            if field not in record or record.get(field) is None or record.get(field) == ""
        ]
        fingerprint = canonical_record_hash(dataset_code, record)
        if missing:
            rejected.append({"index": index, "fingerprint": fingerprint, "missing_fields": missing})
        else:
            accepted.append({"index": index, "fingerprint": fingerprint})
    return {
        "profile_version": APPLICATION_PROFILE_VERSION,
        "contract_status": CONTRACT_STATUS,
        "official_compliance_claim": False,
        "dataset_code": dataset_code,
        "record_count": len(accepted) + len(rejected),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "accepted": accepted,
        "rejected": rejected,
        "valid": not rejected,
    }


def build_submission_envelope(
    dataset_code: str,
    records: list[dict[str, Any]],
    *,
    osgb_id: int | None,
    source_system_version: str,
) -> dict[str, Any]:
    validation = validate_candidate_records(dataset_code, records)
    fingerprints = [canonical_record_hash(dataset_code, record) for record in records]
    idempotency_material = json.dumps(
        {
            "dataset": dataset_code,
            "osgb_id": osgb_id,
            "profile": APPLICATION_PROFILE_VERSION,
            "fingerprints": fingerprints,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "profile_version": APPLICATION_PROFILE_VERSION,
        "contract_status": CONTRACT_STATUS,
        "official_compliance_claim": False,
        "dataset_code": dataset_code,
        "osgb_id": osgb_id,
        "source_system": "isg-suite-osgb",
        "source_system_version": source_system_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "idempotency_key": hashlib.sha256(idempotency_material).hexdigest(),
        "record_count": len(records),
        "validation": validation,
        "records": records,
    }


def application_profile_readiness() -> dict[str, Any]:
    dataset_count = len(DATASETS)
    field_count = sum(len(dataset.fields) for dataset in DATASETS)
    unresolved_dataset_codes = [dataset.code for dataset in DATASETS if not dataset.official_dataset_code]
    unresolved_fields = sum(
        1 for dataset in DATASETS for field in dataset.fields if not field.official_field
    )
    return {
        "profile_version": APPLICATION_PROFILE_VERSION,
        "technical_application_profile_ready": True,
        "official_contract_received": False,
        "official_compliance_claim": False,
        "dataset_count": dataset_count,
        "field_count": field_count,
        "candidate_mapping_complete_pct": 100,
        "official_mapping_complete_pct": 0,
        "unresolved_dataset_codes": unresolved_dataset_codes,
        "unresolved_official_fields": unresolved_fields,
        "next_gate": "İSGGM tarafından sağlanacak güncel resmî veri seti ve servis sözleşmesinin profile işlenmesi.",
    }
