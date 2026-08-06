"""OSGB-only Digital Professional Card scope.

This compatibility layer keeps legacy workplace employee profiles untouched while
moving professional profiles to their owning OSGB. It is imported before routers.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, UniqueConstraint, func, select
from sqlalchemy.orm import Session

from app.core.personnel_profile_config import (
    personnel_profile_osgb_card_active,
    personnel_profile_osgb_rollout,
)
from app.models.entities import (
    AssignmentStatus,
    IsgProfessional,
    OsgbOrganization,
    User,
    UserRole,
    WorkplaceAssignment,
)
from app.models.personnel_profile import (
    PersonnelProfile,
    PersonnelProfileCompetency,
    PersonnelProfileContact,
    PersonnelProfileExperience,
)
from app.models.personnel_profile_document import PersonnelProfileDocument
from app.services.audit import add_audit_log

_FIELD_ROLES = {
    UserRole.SAFETY_SPECIALIST,
    UserRole.WORKPLACE_PHYSICIAN,
    UserRole.OTHER_HEALTH_PERSONNEL,
}
_WRITE_ROLES = {UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN}
_ALLOWED_PROFESSIONAL_TYPES = {
    "safety_specialist",
    "workplace_physician",
    "other_health_personnel",
}


def install_osgb_profile_metadata_scope() -> None:
    """Keep SQLAlchemy metadata aligned with migration 0083 without rewriting legacy models."""
    profile_table = PersonnelProfile.__table__
    profile_table.c.company_id.nullable = True
    if "legacy_company_id" not in profile_table.c:
        profile_table.append_column(
            Column(
                "legacy_company_id",
                Integer,
                ForeignKey("companies.id", ondelete="RESTRICT"),
                nullable=True,
            )
        )
    for constraint in list(profile_table.constraints):
        if getattr(constraint, "name", None) in {
            "uq_personnel_profile_company_professional",
            "ck_personnel_profile_exact_subject",
        }:
            profile_table.constraints.remove(constraint)
    if not any(
        getattr(constraint, "name", None) == "uq_personnel_profile_osgb_professional"
        for constraint in profile_table.constraints
    ):
        profile_table.append_constraint(
            UniqueConstraint(
                "osgb_id",
                "professional_id",
                name="uq_personnel_profile_osgb_professional",
            )
        )
    if not any(
        getattr(constraint, "name", None) == "ck_personnel_profile_exact_subject"
        for constraint in profile_table.constraints
    ):
        profile_table.append_constraint(
            CheckConstraint(
                "(subject_type = 'employee' AND company_id IS NOT NULL AND employee_id IS NOT NULL AND professional_id IS NULL) "
                "OR (subject_type = 'professional' AND company_id IS NULL AND professional_id IS NOT NULL AND employee_id IS NULL)",
                name="ck_personnel_profile_exact_subject",
            )
        )
    for model in (
        PersonnelProfileContact,
        PersonnelProfileCompetency,
        PersonnelProfileExperience,
        PersonnelProfileDocument,
    ):
        model.__table__.c.company_id.nullable = True


def _enum_value(value) -> str:
    return str(getattr(value, "value", value) or "").strip().lower()


def require_osgb_access(db: Session, user: User, osgb_id: int) -> int:
    osgb = db.get(OsgbOrganization, int(osgb_id))
    if not osgb:
        raise HTTPException(404, "OSGB bulunamadı.")
    if user.role == UserRole.GLOBAL_ADMIN:
        return int(osgb.id)
    if user.osgb_id and int(user.osgb_id) == int(osgb.id):
        return int(osgb.id)
    raise HTTPException(403, "Bu OSGB profesyonel kartlarına erişemezsiniz.")


def require_osgb_feature(osgb_id: int) -> dict[str, bool]:
    rollout = personnel_profile_osgb_rollout(osgb_id)
    if not personnel_profile_osgb_card_active(osgb_id):
        raise HTTPException(
            409,
            detail={
                "code": "personnel_profile_disabled",
                "message": "Dijital Profesyonel Kartı bu OSGB için kapalıdır.",
                "rollout": rollout,
            },
        )
    return rollout


def require_professional_access(
    db: Session,
    user: User,
    professional: IsgProfessional,
) -> None:
    require_osgb_access(db, user, int(professional.osgb_id))
    if user.role in {UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN}:
        return
    if user.role in _FIELD_ROLES:
        from app.api.company_access import find_professional_for_user

        own = find_professional_for_user(db, user)
        if own and int(own.id) == int(professional.id):
            return
    raise HTTPException(403, "Yalnızca kendi profesyonel kartınızı görüntüleyebilirsiniz.")


def list_osgb_professionals(db: Session, *, user: User, osgb_id: int) -> list[IsgProfessional]:
    require_osgb_access(db, user, osgb_id)
    require_osgb_feature(osgb_id)
    rows = list(
        db.scalars(
            select(IsgProfessional)
            .where(
                IsgProfessional.osgb_id == int(osgb_id),
                IsgProfessional.is_active.is_(True),
            )
            .order_by(IsgProfessional.full_name, IsgProfessional.id)
        ).all()
    )
    return [row for row in rows if _enum_value(row.professional_type) in _ALLOWED_PROFESSIONAL_TYPES]


def professional_summary(db: Session, *, user: User, professional_id: int) -> dict:
    professional = db.get(IsgProfessional, int(professional_id))
    if not professional or not professional.is_active:
        raise HTTPException(404, "Aktif OSGB profesyoneli bulunamadı.")
    if _enum_value(professional.professional_type) not in _ALLOWED_PROFESSIONAL_TYPES:
        raise HTTPException(404, "Bu kayıt OSGB dijital profesyonel kartı kapsamında değildir.")
    require_professional_access(db, user, professional)
    rollout = require_osgb_feature(int(professional.osgb_id))
    active_assignments = int(
        db.scalar(
            select(func.count())
            .select_from(WorkplaceAssignment)
            .where(
                WorkplaceAssignment.osgb_id == professional.osgb_id,
                WorkplaceAssignment.professional_id == professional.id,
                WorkplaceAssignment.status == AssignmentStatus.ACTIVE,
            )
        )
        or 0
    )
    return {
        "summary_version": "osgb-professional-profile-summary-v1",
        "subject": {"type": "professional", "id": int(professional.id)},
        "scope": {"osgb_id": int(professional.osgb_id), "company_id": None, "company_name": None},
        "profile": {
            "full_name": str(professional.full_name or "").strip(),
            "professional_type": _enum_value(professional.professional_type),
            "email": professional.email,
            "phone": professional.phone,
            "certificate_class": professional.certificate_class,
            "certificate_number": professional.certificate_number,
            "certificate_date": professional.certificate_date.isoformat() if professional.certificate_date else None,
            "employment_status": "active",
            "active_assignment_count": active_assignments,
        },
        "privacy": {
            "data_minimized": True,
            "national_identity_full_included": False,
            "special_status_included": False,
            "health_data_included": False,
            "criminal_record_included": False,
            "restricted_documents_included": False,
        },
        "capabilities": {
            "read_only_summary": True,
            "profile_record_management": True,
            "file_upload": True,
            "cv_generation": False,
            "external_sharing": False,
            "restricted_data": False,
        },
        "rollout": rollout,
    }


def initialize_osgb_professional_profile(
    db: Session,
    *,
    user: User,
    professional_id: int,
) -> tuple[PersonnelProfile, bool]:
    if user.role not in _WRITE_ROLES:
        raise HTTPException(403, "Profesyonel kartı oluşturma yetkiniz yok.")
    professional = db.get(IsgProfessional, int(professional_id))
    if not professional or not professional.is_active:
        raise HTTPException(404, "Aktif OSGB profesyoneli bulunamadı.")
    if _enum_value(professional.professional_type) not in _ALLOWED_PROFESSIONAL_TYPES:
        raise HTTPException(404, "Bu kayıt dijital profesyonel kartı kapsamında değildir.")
    require_osgb_access(db, user, int(professional.osgb_id))
    require_osgb_feature(int(professional.osgb_id))
    existing = db.scalar(
        select(PersonnelProfile)
        .where(
            PersonnelProfile.osgb_id == int(professional.osgb_id),
            PersonnelProfile.professional_id == int(professional.id),
            PersonnelProfile.subject_type == "professional",
        )
        .order_by(PersonnelProfile.id)
        .limit(1)
    )
    if existing:
        if existing.status == "archived":
            raise HTTPException(409, "Bu profesyonele ait tarihsel kart arşivlenmiştir.")
        return existing, False
    profile = PersonnelProfile(
        osgb_id=int(professional.osgb_id),
        company_id=None,
        branch_id=None,
        subject_type="professional",
        employee_id=None,
        professional_id=int(professional.id),
        user_id=None,
        status="active",
        created_by_id=user.id,
    )
    db.add(profile)
    db.flush()
    add_audit_log(
        db,
        user=user,
        action="osgb_professional_profile_initialized",
        entity_type="personnel_profile",
        entity_id=str(profile.id),
        module="personnel_profile",
        description=f"OSGB kapsamlı profesyonel kartı oluşturuldu; osgb_id={profile.osgb_id}, professional_id={profile.professional_id}.",
    )
    return profile, True


def require_osgb_profile_read(db: Session, user: User, profile: PersonnelProfile) -> None:
    if profile.subject_type != "professional" or profile.company_id is not None:
        raise HTTPException(404, "OSGB profesyonel kartı bulunamadı.")
    professional = db.get(IsgProfessional, profile.professional_id)
    if not professional or int(professional.osgb_id) != int(profile.osgb_id):
        raise HTTPException(409, "Profesyonel kartı OSGB ilişkisi geçersiz.")
    require_professional_access(db, user, professional)


def require_osgb_profile_write(db: Session, user: User, profile_id: int) -> PersonnelProfile:
    if user.role not in _WRITE_ROLES:
        raise HTTPException(403, "Profesyonel kartı güncelleme yetkiniz yok.")
    profile = db.get(PersonnelProfile, int(profile_id))
    if not profile:
        raise HTTPException(404, "Profesyonel kartı bulunamadı.")
    require_osgb_profile_read(db, user, profile)
    require_osgb_feature(int(profile.osgb_id))
    if profile.status != "active":
        raise HTTPException(409, "Arşivlenmiş profesyonel kartı değiştirilemez.")
    return profile


def archive_osgb_profile(db: Session, *, user: User, profile: PersonnelProfile) -> PersonnelProfile:
    require_osgb_profile_write(db, user, profile.id)
    if profile.status == "archived":
        return profile
    profile.status = "archived"
    profile.archived_by_id = user.id
    profile.archived_at = datetime.utcnow()
    add_audit_log(
        db,
        user=user,
        action="osgb_professional_profile_archived",
        entity_type="personnel_profile",
        entity_id=str(profile.id),
        module="personnel_profile",
        description="OSGB profesyonel kartı arşivlendi; tarihsel sürümler korundu.",
    )
    return profile


def install_osgb_service_overrides() -> None:
    """Reuse append-only services with OSGB access for nullable-company professional rows."""
    install_osgb_profile_metadata_scope()
    from app.services import personnel_profile_core as core
    from app.services import personnel_profile_document as documents

    original_profile_for_write = core._profile_for_write
    original_document_access = documents._require_document_access
    original_upload = documents.upload_profile_document_version

    def profile_for_write(db: Session, user: User, profile_id: int):
        profile = db.get(PersonnelProfile, int(profile_id))
        if profile and profile.subject_type == "professional" and profile.company_id is None:
            return require_osgb_profile_write(db, user, profile_id)
        return original_profile_for_write(db, user, profile_id)

    def document_access(db: Session, user: User, profile_id: int):
        profile = db.get(PersonnelProfile, int(profile_id))
        if profile and profile.subject_type == "professional" and profile.company_id is None:
            return require_osgb_profile_write(db, user, profile_id)
        return original_document_access(db, user, profile_id)

    def upload_document(*args, **kwargs):
        db = kwargs.get("db") or (args[0] if args else None)
        profile_id = kwargs.get("profile_id")
        user = kwargs.get("user")
        if db is None or profile_id is None or user is None:
            return original_upload(*args, **kwargs)
        profile = db.get(PersonnelProfile, int(profile_id))
        if not profile or profile.subject_type != "professional" or profile.company_id is not None:
            return original_upload(*args, **kwargs)

        metadata = kwargs["metadata"]
        idempotency_key = documents.normalize_idempotency_key(kwargs["idempotency_key"])
        filename = kwargs["filename"]
        content = kwargs["content"]
        store = kwargs.get("store")
        profile = require_osgb_profile_write(db, user, profile_id)
        extension, mime_type, checksum = documents._validate_upload(
            content=content,
            filename=filename,
            document_kind=metadata.document_kind,
        )
        prior = documents._by_idempotency(
            db, profile_id=profile.id, idempotency_key=idempotency_key
        )
        if prior:
            if documents._same_upload(prior, checksum=checksum, metadata=metadata):
                return prior, False
            raise HTTPException(409, "Aynı Idempotency-Key farklı bir belge isteğinde kullanılamaz.")
        document_key = str(metadata.document_key) if metadata.document_key else str(uuid4())
        previous = documents._latest_document(
            db, profile_id=profile.id, document_key=document_key
        )
        if previous:
            if previous.lifecycle_status == "archived":
                raise HTTPException(409, "Arşivlenmiş belge yeniden sürümlenemez.")
            if previous.document_kind != metadata.document_kind or previous.category != metadata.category:
                raise HTTPException(409, "Yeni sürüm mevcut belgenin türü ve kategorisiyle aynı olmalıdır.")
        version = int(previous.version) + 1 if previous else 1
        object_key = (
            f"osgb/{profile.osgb_id}/professionals/{profile.professional_id}/profiles/{profile.id}/"
            f"{metadata.document_kind}/{document_key}/versions/{version}/{uuid4().hex}{extension}"
        )
        active_store = store or documents.get_object_store()
        active_store.put_bytes(object_key, content)
        row = PersonnelProfileDocument(
            profile_id=profile.id,
            company_id=None,
            document_key=document_key,
            version=version,
            supersedes_id=previous.id if previous else None,
            idempotency_key=idempotency_key,
            document_kind=metadata.document_kind,
            category=metadata.category,
            title=metadata.title,
            document_number=metadata.document_number,
            issuing_organization=metadata.issuing_organization,
            issue_date=metadata.issue_date,
            valid_from=metadata.valid_from,
            expiration_date=metadata.expiration_date,
            no_expiration=metadata.no_expiration,
            object_key=object_key,
            mime_type=mime_type,
            file_extension=extension,
            file_size=len(content),
            checksum_sha256=checksum,
            access_classification=metadata.access_classification,
            processing_purpose="osgb_professional_profile_management",
            retention_policy="osgb_professional_profile_ordinary_v1",
            verification_status="unverified",
            lifecycle_status="active",
            change_reason=metadata.change_reason,
            created_by_id=user.id,
        )
        db.add(row)
        try:
            db.flush()
        except Exception:
            try:
                active_store.delete(object_key)
            except Exception:
                pass
            raise
        add_audit_log(
            db,
            user=user,
            action="osgb_professional_document_uploaded",
            entity_type="personnel_profile_document",
            entity_id=str(row.id),
            module="personnel_profile",
            description=(
                f"OSGB profesyonel belgesi private depolamaya yüklendi; profile_id={profile.id}, "
                f"version={version}, checksum_prefix={sha256(content).hexdigest()[:12]}."
            ),
        )
        return row, True

    core._profile_for_write = profile_for_write
    documents._require_document_access = document_access
    documents.upload_profile_document_version = upload_document
