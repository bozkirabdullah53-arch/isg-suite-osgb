"""İşyerine görevlendirilmiş İSG ekibi — tek kaynak.

Eğitim belgesi, risk raporu ve benzeri çıktılarda eğitici/uzman/hekim adının
elle yazılması hem yazım hatası (aynı kişi "Ahmet Yılmaz" / "A. Yılmaz")
hem de görevlendirme ile uyumsuzluk üretiyordu. Bu modül aktif
`WorkplaceAssignment` kaydından ekibi çözer; adı yazan tek yer burasıdır.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    AssignmentStatus,
    Company,
    IsgProfessional,
    ProfessionalType,
    WorkplaceAssignment,
)

CERTIFICATE_CLASS_LABELS = {
    "A": "A Sınıfı İş Güvenliği Uzmanı",
    "B": "B Sınıfı İş Güvenliği Uzmanı",
    "C": "C Sınıfı İş Güvenliği Uzmanı",
}

TYPE_LABELS = {
    ProfessionalType.SAFETY_SPECIALIST: "İş Güvenliği Uzmanı",
    ProfessionalType.WORKPLACE_PHYSICIAN: "İşyeri Hekimi",
    ProfessionalType.OTHER_HEALTH_PERSONNEL: "Diğer Sağlık Personeli",
}


def professional_title(pro: IsgProfessional) -> str:
    """Belgeye basılacak unvan; uzmanda sertifika sınıfı da yazılır."""
    if pro.professional_type == ProfessionalType.SAFETY_SPECIALIST:
        key = (pro.certificate_class or "").strip().upper()
        return CERTIFICATE_CLASS_LABELS.get(key, TYPE_LABELS[ProfessionalType.SAFETY_SPECIALIST])
    return TYPE_LABELS.get(pro.professional_type, "")


def assigned_team(db: Session, company_id: int) -> dict:
    """İşyerinin aktif görevlileri: uzman, hekim, DSP.

    Aynı türde birden fazla aktif görevlendirme varsa en yenisi alınır.
    """
    rows = db.execute(
        select(IsgProfessional, WorkplaceAssignment)
        .join(WorkplaceAssignment, WorkplaceAssignment.professional_id == IsgProfessional.id)
        .where(
            WorkplaceAssignment.company_id == company_id,
            WorkplaceAssignment.status == AssignmentStatus.ACTIVE,
        )
        .order_by(WorkplaceAssignment.id)
    ).all()

    team: dict[str, dict | None] = {
        ProfessionalType.SAFETY_SPECIALIST.value: None,
        ProfessionalType.WORKPLACE_PHYSICIAN.value: None,
        ProfessionalType.OTHER_HEALTH_PERSONNEL.value: None,
    }
    for pro, assignment in rows:
        key = (assignment.professional_type or pro.professional_type).value
        if key not in team:
            continue
        team[key] = {
            "professional_id": pro.id,
            "full_name": pro.full_name,
            "title": professional_title(pro),
            "certificate_class": pro.certificate_class,
            "certificate_number": pro.certificate_number,
            "assignment_id": assignment.id,
        }
    return team


def team_names(db: Session, company_id: int) -> dict:
    """Ad-soyad sözlüğü — rapor/PDF satırları için."""
    team = assigned_team(db, company_id)
    return {key: (value or {}).get("full_name") for key, value in team.items()}


def training_defaults(db: Session, company_id: int) -> dict:
    """Eğitim formunun kendiliğinden dolacak alanları.

    Eğitici varsayılanı uzmandır; hekim tarafından verilen eğitimlerde
    kullanıcı listeden hekimi seçebilir.
    """
    team = assigned_team(db, company_id)
    company = db.get(Company, company_id)
    specialist = team[ProfessionalType.SAFETY_SPECIALIST.value]
    physician = team[ProfessionalType.WORKPLACE_PHYSICIAN.value]
    other = team[ProfessionalType.OTHER_HEALTH_PERSONNEL.value]

    options = [
        {
            "value": person["full_name"],
            "qualification": person["title"],
            "role": role,
        }
        for role, person in (
            ("safety_specialist", specialist),
            ("workplace_physician", physician),
            ("other_health_personnel", other),
        )
        if person
    ]

    return {
        "company_id": company_id,
        "company_name": company.name if company else None,
        "hazard_class": company.hazard_class if company else None,
        "team": team,
        "instructor_options": options,
        "defaults": {
            "instructor_name": (specialist or physician or {}).get("full_name"),
            "instructor_qualification": (specialist or physician or {}).get("title"),
            "workplace_physician": (physician or {}).get("full_name"),
            "employer_representative": company.authorized_person if company else None,
        },
    }
