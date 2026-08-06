from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api import training_presentation as presentation_api
from app.core.database import Base
from app.models import entities  # noqa: F401
from app.models import training_nace  # noqa: F401
from app.models.training_presentation import (
    IMMUTABLE_PRESENTATION_SOURCE_FIELDS,
    TrainingPresentationVersion,
)
from app.services import training_presentation_versions as versions


def _manifest() -> dict:
    return {
        "manifest_version": "nace-training-presentation-manifest-v1",
        "contract_version": "nace-training-presentation-contract-v1",
        "contract_hash": "b" * 64,
        "template_version": "osgb-training-presentation-template-v1",
        "output_formats": ["pptx", "pdf"],
        "content_hash": "c" * 64,
        "slides": [],
    }


def _training():
    return SimpleNamespace(
        id=101,
        company_id=35,
        branch_id=None,
        title="Temel İSG Eğitimi",
        start_date=date(2026, 8, 6),
        end_date=date(2026, 8, 6),
    )


def _snapshot():
    return SimpleNamespace(
        id=201,
        training_id=101,
        catalog_key="nace_62_01_01",
        nace_code="62.01.01",
        nace_description="Bilgisayar programlama faaliyetleri",
        hazard_class="Az Tehlikeli",
        content_profile_code="bilisim_yazilim_it",
        catalog_version="test-v1",
        catalog_hash="a" * 64,
        source_snapshot_json=json.dumps({"source": "test"}),
        training_topics_json=json.dumps([f"Konu {i}" for i in range(1, 6)]),
        technical_risk_tags_json=json.dumps(["display_screen", "server_room"]),
        special_risks_json=json.dumps(["long_screen_time"]),
    )


def _row(**overrides):
    values = {
        "training_id": 101,
        "company_id": 35,
        "branch_id": None,
        "nace_snapshot_id": 201,
        "version": 1,
        "status": "draft",
        "contract_version": "nace-training-presentation-contract-v1",
        "contract_hash": "b" * 64,
        "template_version": "osgb-training-presentation-template-v1",
        "manifest_version": "nace-training-presentation-manifest-v1",
        "manifest_json": json.dumps(_manifest(), sort_keys=True),
        "manifest_hash": "c" * 64,
        "catalog_key": "nace_62_01_01",
        "nace_code": "62.01.01",
        "nace_description": "Bilgisayar programlama faaliyetleri",
        "hazard_class": "Az Tehlikeli",
        "content_profile_code": "bilisim_yazilim_it",
        "catalog_version": "test-v1",
        "catalog_hash": "a" * 64,
        "source_snapshot_json": json.dumps({"source": "test"}),
        "training_topics_json": json.dumps([f"Konu {i}" for i in range(1, 6)]),
        "technical_risk_tags_json": json.dumps(["display_screen"]),
        "special_risks_json": "[]",
        "output_formats_json": '["pptx","pdf"]',
        "primary_output_format": "pptx",
        "created_by_id": 9,
    }
    values.update(overrides)
    return TrainingPresentationVersion(**values)


def test_model_is_isolated_versioned_and_has_future_output_fields():
    table = TrainingPresentationVersion.__table__
    assert table.name == "training_presentation_versions"
    columns = set(table.columns.keys())
    assert {
        "training_id",
        "company_id",
        "version",
        "status",
        "manifest_json",
        "manifest_hash",
        "catalog_hash",
        "pptx_storage_key",
        "pdf_storage_key",
        "created_by_id",
        "approved_by_id",
        "archived_at",
    } <= columns
    unique_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("training_id", "version") in unique_sets
    assert "manifest_json" in IMMUTABLE_PRESENTATION_SOURCE_FIELDS
    assert "status" not in IMMUTABLE_PRESENTATION_SOURCE_FIELDS
    assert "pptx_storage_key" not in IMMUTABLE_PRESENTATION_SOURCE_FIELDS


def test_pilot_access_denied_rejects_before_any_database_query(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr(versions, "nace_training_presentation_active", lambda *_: False)

    with pytest.raises(versions.PresentationVersionError) as exc:
        versions.create_draft_version(
            db,
            training=_training(),
            created_by_id=9,
        )

    assert exc.value.code == "pilot_access_denied"
    db.scalar.assert_not_called()
    db.add.assert_not_called()
    db.flush.assert_not_called()


def test_create_draft_freezes_manifest_and_uses_next_version(monkeypatch):
    db = MagicMock()
    snapshot = _snapshot()
    db.scalar.side_effect = [snapshot, 2]
    monkeypatch.setattr(versions, "nace_training_presentation_active", lambda *_: True)
    monkeypatch.setattr(versions, "exact_question_readiness", lambda *_: {"ready": True})
    monkeypatch.setattr(
        versions,
        "build_presentation_manifest_preview",
        lambda **_: _manifest(),
    )

    row = versions.create_draft_version(
        db,
        training=_training(),
        created_by_id=9,
    )

    assert row.version == 3
    assert row.status == "draft"
    assert row.manifest_hash == "c" * 64
    assert row.catalog_hash == "a" * 64
    assert row.output_formats_json == '["pptx","pdf"]'
    assert row.pptx_storage_key is None
    assert row.pdf_storage_key is None
    db.add.assert_called_once_with(row)
    db.flush.assert_called_once()


def test_historical_list_does_not_depend_on_feature_flag(monkeypatch):
    db = MagicMock()
    result = MagicMock()
    result.all.return_value = [_row(version=2), _row(version=1)]
    db.scalars.return_value = result
    monkeypatch.setattr(
        versions,
        "nace_training_presentation_active",
        lambda *_: (_ for _ in ()).throw(AssertionError("flag must not be checked")),
    )

    rows = versions.list_presentation_versions(db, training_id=101)
    assert [row.version for row in rows] == [2, 1]


def test_frozen_source_fields_cannot_be_edited_but_lifecycle_fields_can():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        row = _row()
        db.add(row)
        db.commit()

        row.status = "failed"
        row.failure_code = "renderer_unavailable"
        db.commit()
        assert row.status == "failed"

        row.manifest_hash = "d" * 64
        with pytest.raises(ValueError, match="yeni sürüm oluşturun"):
            db.commit()
        db.rollback()
        assert row.manifest_hash == "c" * 64


def test_payload_exposes_manifest_only_in_detail_mode():
    row = _row()
    row.id = 501
    summary = versions.version_payload(row)
    detail = versions.version_payload(row, include_manifest=True)
    assert "manifest" not in summary
    assert detail["manifest"]["content_hash"] == "c" * 64
    assert detail["read_only_source_snapshot"] is True
    assert detail["renderer_available"] is True
    assert detail["storage_write"] is False


def test_api_list_history_uses_company_access_and_remains_read_only(monkeypatch):
    db = MagicMock()
    db.get.return_value = _training()
    user = SimpleNamespace(id=9, company_id=35, role="company_admin")
    checked: list[int] = []
    monkeypatch.setattr(
        presentation_api,
        "ensure_company_access",
        lambda _db, _user, company_id: checked.append(company_id),
    )
    monkeypatch.setattr(
        presentation_api,
        "list_presentation_versions",
        lambda _db, *, training_id: [_row(version=2), _row(version=1)],
    )
    monkeypatch.setattr(
        presentation_api,
        "version_payload",
        lambda row, **_: {"version": row.version},
    )

    response = presentation_api.presentation_versions(101, db=db, user=user)
    assert checked == [35]
    assert response == {
        "training_id": 101,
        "count": 2,
        "rows": [{"version": 2}, {"version": 1}],
        "read_only_history": True,
    }
    db.commit.assert_not_called()


def test_api_create_service_error_rolls_back_without_affecting_training(monkeypatch):
    db = MagicMock()
    db.get.return_value = _training()
    user = SimpleNamespace(id=9, company_id=35, role="company_admin")
    monkeypatch.setattr(
        presentation_api,
        "ensure_company_access",
        lambda *_args, **_kwargs: 35,
    )
    monkeypatch.setattr(
        presentation_api,
        "nace_training_presentation_active",
        lambda *_: True,
    )

    def disabled(*_args, **_kwargs):
        raise versions.PresentationVersionError(
            "pilot_access_denied",
            "Sunum özelliği bu pilot şirket için kapalıdır.",
        )

    monkeypatch.setattr(presentation_api, "create_draft_version", disabled)
    with pytest.raises(HTTPException) as exc:
        presentation_api.create_presentation_version(101, db=db, user=user)
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "pilot_access_denied"
    assert exc.value.detail["core_training_unaffected"] is True
    assert exc.value.detail["storage_write"] is False
    db.rollback.assert_called_once()
    db.commit.assert_not_called()
