from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models import entities  # noqa: F401
from app.models import training_nace  # noqa: F401
from app.models import training_presentation  # noqa: F401
from app.models.training_presentation import TrainingPresentationVersion
from app.models.training_presentation_approval import TrainingPresentationApproval
from app.services import training_presentation_approval as approval_service


class EnumLike:
    def __init__(self, value: str):
        self.value = value


def _user(*, role: object = "safety_specialist"):
    return SimpleNamespace(
        id=9,
        role=role,
        full_name="Test Uzman",
        email="uzman@example.com",
    )


def _version(*, status: str = "generated") -> TrainingPresentationVersion:
    row = TrainingPresentationVersion(
        training_id=101,
        company_id=35,
        branch_id=None,
        nace_snapshot_id=201,
        version=2,
        status=status,
        contract_version="nace-training-presentation-contract-v1",
        contract_hash="b" * 64,
        template_version="osgb-training-presentation-template-v1",
        manifest_version="nace-training-presentation-manifest-v1",
        manifest_json=json.dumps({"content_hash": "c" * 64}),
        manifest_hash="c" * 64,
        catalog_key="nace_62_01_01",
        nace_code="62.01.01",
        nace_description="Bilgisayar programlama faaliyetleri",
        hazard_class="Az Tehlikeli",
        content_profile_code="bilisim_yazilim_it",
        catalog_version="test-v1",
        catalog_hash="a" * 64,
        source_snapshot_json="{}",
        training_topics_json=json.dumps([f"Konu {index}" for index in range(1, 6)]),
        technical_risk_tags_json=json.dumps(["display_screen", "server_room"]),
        special_risks_json="[]",
        output_formats_json='["pptx","pdf"]',
        primary_output_format="pptx",
        pptx_storage_key="training-presentations/a.pptx",
        pptx_file_hash="d" * 64,
        pptx_file_size=1200,
        pptx_content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        pdf_storage_key="training-presentations/a.pdf",
        pdf_file_hash="e" * 64,
        pdf_file_size=800,
        pdf_content_type="application/pdf",
        created_by_id=9,
    )
    row.id = 501
    return row


def _approval_row(version: TrainingPresentationVersion | None = None):
    row = version or _version(status="approved")
    approval = TrainingPresentationApproval(
        presentation_version_id=int(row.id),
        training_id=int(row.training_id),
        company_id=int(row.company_id),
        branch_id=row.branch_id,
        approval_method="application_approval",
        manifest_hash=str(row.manifest_hash),
        pptx_file_hash=str(row.pptx_file_hash),
        pdf_file_hash=str(row.pdf_file_hash),
        approver_user_id=9,
        approver_name="Test Uzman",
        approver_role="safety_specialist",
        approval_note="Kontrol edildi.",
        legal_notice=approval_service.APPLICATION_APPROVAL_NOTICE,
        event_hash="f" * 64,
    )
    approval.id = 601
    return approval


def _verified_esign_request(*, pdf_hash: str = "e" * 64, company_id: int = 35):
    return SimpleNamespace(
        id=701,
        company_id=company_id,
        is_active=True,
        status=EnumLike("verified"),
        verification_status=EnumLike("verified"),
        signing_format=EnumLike("PAdES"),
        document_sha256=pdf_hash,
        signed_document_sha256="9" * 64,
        certificate_subject="CN=Test Uzman",
        certificate_serial="SERIAL-123",
        certificate_issuer="CN=Test Qualified CA",
        certificate_qualified=True,
        revocation_status=EnumLike("good"),
        timestamp_status=EnumLike("verified"),
        signed_at=None,
    )


def test_approval_model_is_isolated_unique_and_hash_locked():
    table = TrainingPresentationApproval.__table__
    assert table.name == "training_presentation_approvals"
    columns = set(table.columns.keys())
    assert {
        "presentation_version_id",
        "training_id",
        "company_id",
        "approval_method",
        "manifest_hash",
        "pptx_file_hash",
        "pdf_file_hash",
        "approver_user_id",
        "esign_request_id",
        "legal_notice",
        "event_hash",
    } <= columns
    unique_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("presentation_version_id",) in unique_sets
    assert ("event_hash",) in unique_sets


def test_feature_disabled_rejects_approval_before_database_query(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr(approval_service, "nace_training_presentation_active", lambda: False)

    with pytest.raises(approval_service.PresentationApprovalError) as exc:
        approval_service.approve_presentation_version(
            db,
            row=_version(),
            user=_user(),
            method="application_approval",
            confirmed_manifest_hash="c" * 64,
        )

    assert exc.value.code == "feature_disabled"
    db.scalar.assert_not_called()
    db.add.assert_not_called()
    db.flush.assert_not_called()


def test_application_approval_freezes_three_hashes_and_discloses_legal_status(monkeypatch):
    db = MagicMock()
    db.scalar.return_value = None
    row = _version()
    monkeypatch.setattr(approval_service, "nace_training_presentation_active", lambda: True)

    approval = approval_service.approve_presentation_version(
        db,
        row=row,
        user=_user(role=EnumLike("safety_specialist")),
        method="application_approval",
        confirmed_manifest_hash=row.manifest_hash,
        note="Sunum ve kaynaklar incelendi.",
    )

    assert row.status == "approved"
    assert row.approved_by_id == 9
    assert row.approved_at is not None
    assert approval.approval_method == "application_approval"
    assert approval.manifest_hash == row.manifest_hash
    assert approval.pptx_file_hash == row.pptx_file_hash
    assert approval.pdf_file_hash == row.pdf_file_hash
    assert approval.esign_request_id is None
    assert "nitelikli elektronik imza yerine geçmez" in approval.legal_notice
    assert len(approval.event_hash) == 64
    db.add.assert_called_once_with(approval)
    db.flush.assert_called_once()


def test_manifest_confirmation_and_duplicate_approval_fail_closed(monkeypatch):
    monkeypatch.setattr(approval_service, "nace_training_presentation_active", lambda: True)
    row = _version()

    db = MagicMock()
    with pytest.raises(approval_service.PresentationApprovalError) as mismatch:
        approval_service.approve_presentation_version(
            db,
            row=row,
            user=_user(),
            method="application_approval",
            confirmed_manifest_hash="0" * 64,
        )
    assert mismatch.value.code == "manifest_confirmation_mismatch"
    db.add.assert_not_called()

    db.scalar.return_value = _approval_row(row)
    with pytest.raises(approval_service.PresentationApprovalError) as duplicate:
        approval_service.approve_presentation_version(
            db,
            row=row,
            user=_user(),
            method="application_approval",
            confirmed_manifest_hash=row.manifest_hash,
        )
    assert duplicate.value.code == "already_approved"


def test_verified_pades_approval_accepts_enum_values_and_matching_pdf_hash(monkeypatch):
    db = MagicMock()
    db.scalar.return_value = None
    request = _verified_esign_request()
    db.get.return_value = request
    row = _version()
    monkeypatch.setattr(approval_service, "nace_training_presentation_active", lambda: True)

    approval = approval_service.approve_presentation_version(
        db,
        row=row,
        user=_user(role=EnumLike("company_admin")),
        method="qualified_esign",
        confirmed_manifest_hash=row.manifest_hash,
        esign_request_id=request.id,
    )

    assert approval.approval_method == "qualified_esign"
    assert approval.esign_request_id == request.id
    assert approval.esign_document_hash == row.pdf_file_hash
    assert approval.esign_signed_document_hash == request.signed_document_sha256
    evidence = json.loads(approval.esign_evidence_json)
    assert evidence["status"] == "verified"
    assert evidence["verification_status"] == "verified"
    assert evidence["signing_format"] == "PADES"
    assert evidence["revocation_status"] == "good"
    assert "doğrulanmış PAdES" in approval.legal_notice


@pytest.mark.parametrize(
    ("request_patch", "expected_code"),
    [
        ({"document_sha256": "0" * 64}, "esign_document_hash_mismatch"),
        ({"verification_status": EnumLike("pending")}, "esign_not_verified"),
        ({"signing_format": EnumLike("XAdES")}, "esign_format_mismatch"),
        ({"certificate_qualified": False}, "esign_not_qualified"),
        ({"revocation_status": EnumLike("revoked")}, "esign_revocation_invalid"),
        ({"company_id": 99}, "esign_company_mismatch"),
    ],
)
def test_qualified_esign_rejects_unverified_or_mismatched_evidence(
    monkeypatch,
    request_patch,
    expected_code,
):
    request = _verified_esign_request()
    for key, value in request_patch.items():
        setattr(request, key, value)
    db = MagicMock()
    db.scalar.return_value = None
    db.get.return_value = request
    row = _version()
    monkeypatch.setattr(approval_service, "nace_training_presentation_active", lambda: True)

    with pytest.raises(approval_service.PresentationApprovalError) as exc:
        approval_service.approve_presentation_version(
            db,
            row=row,
            user=_user(),
            method="qualified_esign",
            confirmed_manifest_hash=row.manifest_hash,
            esign_request_id=request.id,
        )
    assert exc.value.code == expected_code
    db.add.assert_not_called()


def test_approved_outputs_are_locked_and_only_archive_transition_is_allowed():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        row = _version(status="approved")
        db.add(row)
        db.commit()

        original_hash = row.pdf_file_hash
        row.pdf_file_hash = "1" * 64
        with pytest.raises(ValueError, match="Onaylı sunum dosyaları"):
            db.commit()
        db.rollback()
        assert row.pdf_file_hash == original_hash

        row.status = "failed"
        with pytest.raises(ValueError, match="yalnız arşivlenebilir"):
            db.commit()
        db.rollback()
        assert row.status == "approved"

        row.status = "archived"
        db.commit()
        assert row.status == "archived"

        row.status = "approved"
        with pytest.raises(ValueError, match="Arşivlenmiş sunum"):
            db.commit()
        db.rollback()
        assert row.status == "archived"


def test_approval_records_cannot_be_updated_or_deleted():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        approval = _approval_row()
        db.add(approval)
        db.commit()

        approval.approval_note = "Değiştirildi"
        with pytest.raises(ValueError, match="değiştirilemez"):
            db.commit()
        db.rollback()

        db.delete(approval)
        with pytest.raises(ValueError, match="silinemez"):
            db.commit()
        db.rollback()


def test_archive_requires_existing_approval_and_keeps_history(monkeypatch):
    row = _version(status="approved")
    user = _user()
    db = MagicMock()
    monkeypatch.setattr(approval_service, "nace_training_presentation_active", lambda: True)

    db.scalar.return_value = None
    with pytest.raises(approval_service.PresentationApprovalError) as missing:
        approval_service.archive_presentation_version(db, row=row, user=user)
    assert missing.value.code == "approval_required"

    db.scalar.return_value = _approval_row(row)
    archived = approval_service.archive_presentation_version(db, row=row, user=user)
    assert archived.status == "archived"
    assert archived.archived_at is not None
    db.flush.assert_called_once()
