from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models import entities  # noqa: F401
from app.models import personnel_profile  # noqa: F401
from app.models import personnel_profile_document  # noqa: F401
from app.models.entities import (
    Branch,
    Company,
    Employee,
    OsgbOrganization,
    User,
    UserRole,
)
from app.models.personnel_profile_document import PersonnelProfileDocument
from app.schemas.personnel_profile import PersonnelProfileInitialize
from app.schemas.personnel_profile_document import PersonnelProfileDocumentMetadata
from app.services.personnel_profile_core import initialize_personnel_profile
from app.services.personnel_profile_document import (
    archive_profile_document_version,
    list_latest_profile_documents,
    load_profile_document_content,
    upload_profile_document_version,
)


class MemoryStore:
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def put_bytes(self, key: str, content: bytes) -> str:
        self.objects[key] = bytes(content)
        return key

    def get_bytes(self, key: str) -> bytes:
        if key not in self.objects:
            raise HTTPException(404, "Dosya bulunamadı.")
        return self.objects[key]

    def exists(self, key: str) -> bool:
        return key in self.objects

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    def resolve_local_path(self, key: str):
        return None


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _scope(db: Session):
    osgb = OsgbOrganization(name="Belge Test OSGB", is_active=True)
    db.add(osgb)
    db.flush()
    company = Company(
        name="Belge Test İşyerim",
        osgb_id=osgb.id,
        is_active=True,
        hazard_class="Tehlikeli",
    )
    db.add(company)
    db.flush()
    branch = Branch(company_id=company.id, name="Merkez", is_active=True)
    db.add(branch)
    db.flush()
    admin = User(
        email="document-admin@example.com",
        full_name="Belge Yöneticisi",
        hashed_password="hash",
        role=UserRole.COMPANY_ADMIN,
        company_id=company.id,
        osgb_id=osgb.id,
        is_active=True,
    )
    outsider = User(
        email="document-readonly@example.com",
        full_name="Salt Okunur",
        hashed_password="hash",
        role=UserRole.READ_ONLY,
        company_id=company.id,
        osgb_id=osgb.id,
        is_active=True,
    )
    employee = Employee(
        company_id=company.id,
        branch_id=branch.id,
        full_name="Ayşe Yılmaz",
        national_id_masked="12345678990",
        job_title="Kaynakçı",
        is_active=True,
    )
    db.add_all([admin, outsider, employee])
    db.flush()
    profile, _ = initialize_personnel_profile(
        db,
        user=admin,
        payload=PersonnelProfileInitialize(
            company_id=company.id,
            subject_type="employee",
            subject_id=employee.id,
            branch_id=branch.id,
        ),
    )
    db.commit()
    return admin, outsider, profile


def _pdf(text: bytes = b"ordinary") -> bytes:
    return b"%PDF-1.4\n" + text + b"\n%%EOF\n"


def _metadata(**overrides):
    data = {
        "document_kind": "certificate",
        "category": "first_aid_certificate",
        "title": "İlk Yardımcı Belgesi",
        "access_classification": "internal_only",
    }
    data.update(overrides)
    return PersonnelProfileDocumentMetadata(**data)


def test_upload_is_private_versioned_and_idempotent(db: Session):
    admin, _, profile = _scope(db)
    store = MemoryStore()
    request_key = str(uuid4())

    first, created = upload_profile_document_version(
        db,
        user=admin,
        profile_id=profile.id,
        metadata=_metadata(),
        idempotency_key=request_key,
        filename="ayse-ilkyardim.pdf",
        content=_pdf(),
        store=store,
    )
    db.commit()

    same, second_created = upload_profile_document_version(
        db,
        user=admin,
        profile_id=profile.id,
        metadata=_metadata(),
        idempotency_key=request_key,
        filename="tekrar.pdf",
        content=_pdf(),
        store=store,
    )

    assert created is True
    assert second_created is False
    assert same.id == first.id
    assert first.version == 1
    assert first.object_key in store.objects
    assert "Ayşe" not in first.object_key
    assert "12345678990" not in first.object_key
    assert db.scalar(select(func.count()).select_from(PersonnelProfileDocument)) == 1


def test_new_version_preserves_previous_object(db: Session):
    admin, _, profile = _scope(db)
    store = MemoryStore()
    first, _ = upload_profile_document_version(
        db,
        user=admin,
        profile_id=profile.id,
        metadata=_metadata(),
        idempotency_key=str(uuid4()),
        filename="first.pdf",
        content=_pdf(b"v1"),
        store=store,
    )
    db.commit()

    second, _ = upload_profile_document_version(
        db,
        user=admin,
        profile_id=profile.id,
        metadata=_metadata(
            document_key=first.document_key,
            change_reason="Belgenin yenilenmiş sürümü",
        ),
        idempotency_key=str(uuid4()),
        filename="second.pdf",
        content=_pdf(b"v2"),
        store=store,
    )
    db.commit()

    assert second.version == 2
    assert second.supersedes_id == first.id
    assert first.object_key != second.object_key
    assert first.object_key in store.objects
    assert second.object_key in store.objects
    assert db.scalar(select(func.count()).select_from(PersonnelProfileDocument)) == 2


def test_archive_appends_history_without_deleting_storage(db: Session):
    admin, _, profile = _scope(db)
    store = MemoryStore()
    first, _ = upload_profile_document_version(
        db,
        user=admin,
        profile_id=profile.id,
        metadata=_metadata(),
        idempotency_key=str(uuid4()),
        filename="certificate.pdf",
        content=_pdf(),
        store=store,
    )
    db.commit()

    archived, created = archive_profile_document_version(
        db,
        user=admin,
        profile_id=profile.id,
        document_key=first.document_key,
        reason="Belge kullanım dışı kaldı",
        idempotency_key=str(uuid4()),
    )
    db.commit()

    assert created is True
    assert archived.version == 2
    assert archived.lifecycle_status == "archived"
    assert archived.object_key == first.object_key
    assert first.object_key in store.objects
    assert list_latest_profile_documents(
        db,
        user=admin,
        profile_id=profile.id,
    ) == []
    visible_history = list_latest_profile_documents(
        db,
        user=admin,
        profile_id=profile.id,
        include_archived=True,
    )
    assert visible_history[0]["validity_status"] == "archived"


def test_read_only_user_cannot_upload_or_read_documents(db: Session):
    admin, outsider, profile = _scope(db)
    store = MemoryStore()
    row, _ = upload_profile_document_version(
        db,
        user=admin,
        profile_id=profile.id,
        metadata=_metadata(),
        idempotency_key=str(uuid4()),
        filename="certificate.pdf",
        content=_pdf(),
        store=store,
    )
    db.commit()

    with pytest.raises(HTTPException) as upload_error:
        upload_profile_document_version(
            db,
            user=outsider,
            profile_id=profile.id,
            metadata=_metadata(),
            idempotency_key=str(uuid4()),
            filename="blocked.pdf",
            content=_pdf(),
            store=store,
        )
    assert upload_error.value.status_code == 403

    with pytest.raises(HTTPException) as download_error:
        load_profile_document_content(
            db,
            user=outsider,
            profile_id=profile.id,
            document_id=row.id,
            store=store,
        )
    assert download_error.value.status_code == 403


def test_download_verifies_checksum_before_returning_content(db: Session):
    admin, _, profile = _scope(db)
    store = MemoryStore()
    row, _ = upload_profile_document_version(
        db,
        user=admin,
        profile_id=profile.id,
        metadata=_metadata(),
        idempotency_key=str(uuid4()),
        filename="certificate.pdf",
        content=_pdf(),
        store=store,
    )
    db.commit()
    store.objects[row.object_key] = _pdf(b"tampered")

    with pytest.raises(HTTPException) as exc:
        load_profile_document_content(
            db,
            user=admin,
            profile_id=profile.id,
            document_id=row.id,
            store=store,
        )
    assert exc.value.status_code == 409


def test_executable_content_is_rejected_before_storage(db: Session):
    admin, _, profile = _scope(db)
    store = MemoryStore()

    with pytest.raises(HTTPException) as exc:
        upload_profile_document_version(
            db,
            user=admin,
            profile_id=profile.id,
            metadata=_metadata(),
            idempotency_key=str(uuid4()),
            filename="fake.pdf",
            content=b"MZ-not-a-pdf",
            store=store,
        )
    assert exc.value.status_code == 400
    assert store.objects == {}


def test_reused_idempotency_key_with_different_content_conflicts(db: Session):
    admin, _, profile = _scope(db)
    store = MemoryStore()
    request_key = str(uuid4())
    upload_profile_document_version(
        db,
        user=admin,
        profile_id=profile.id,
        metadata=_metadata(),
        idempotency_key=request_key,
        filename="first.pdf",
        content=_pdf(b"first"),
        store=store,
    )
    db.commit()

    with pytest.raises(HTTPException) as exc:
        upload_profile_document_version(
            db,
            user=admin,
            profile_id=profile.id,
            metadata=_metadata(),
            idempotency_key=request_key,
            filename="second.pdf",
            content=_pdf(b"second"),
            store=store,
        )
    assert exc.value.status_code == 409
