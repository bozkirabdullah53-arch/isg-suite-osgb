from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.models.training_presentation import TrainingPresentationVersion
from app.services import training_presentation_generation as generation
from app.services.training_presentation_renderer import (
    PDF_CONTENT_TYPE,
    PPTX_CONTENT_TYPE,
    RenderedPresentation,
)


class FakeStore:
    def __init__(self, *, fail_on: str | None = None):
        self.data: dict[str, bytes] = {}
        self.fail_on = fail_on
        self.put_calls: list[str] = []
        self.delete_calls: list[str] = []

    def put_bytes(self, key: str, content: bytes) -> str:
        self.put_calls.append(key)
        if self.fail_on and key.endswith(self.fail_on):
            raise RuntimeError("simulated storage failure")
        self.data[key] = bytes(content)
        return key

    def get_bytes(self, key: str) -> bytes:
        if key not in self.data:
            raise FileNotFoundError(key)
        return self.data[key]

    def exists(self, key: str) -> bool:
        return key in self.data

    def delete(self, key: str) -> None:
        self.delete_calls.append(key)
        self.data.pop(key, None)

    def resolve_local_path(self, key: str):
        return None


def _manifest() -> dict:
    value = {
        "manifest_version": "nace-training-presentation-manifest-v1",
        "contract_version": "nace-training-presentation-contract-v1",
        "contract_hash": "b" * 64,
        "template_version": "osgb-training-presentation-template-v1",
        "output_formats": ["pptx", "pdf"],
        "training": {"training_id": 101, "company_id": 35, "title": "İSG Eğitimi"},
        "source_registry": [],
        "slides": [
            {
                "position": 1,
                "section_id": "cover",
                "title": "İSG Eğitimi",
                "source_refs": [],
                "content_blocks": [],
                "speaker_notes_required": True,
                "approval_required": False,
            }
        ],
        "slide_count": 1,
        "core_training_unaffected": True,
    }
    value["content_hash"] = hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return value


def _row(*, status: str = "draft") -> TrainingPresentationVersion:
    manifest = _manifest()
    row = TrainingPresentationVersion(
        training_id=101,
        company_id=35,
        branch_id=None,
        nace_snapshot_id=201,
        version=2,
        status=status,
        contract_version=manifest["contract_version"],
        contract_hash=manifest["contract_hash"],
        template_version=manifest["template_version"],
        manifest_version=manifest["manifest_version"],
        manifest_json=json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        manifest_hash=manifest["content_hash"],
        catalog_key="nace_62_01_01",
        nace_code="62.01.01",
        nace_description="Bilgisayar programlama faaliyetleri",
        hazard_class="Az Tehlikeli",
        content_profile_code="bilisim_yazilim_it",
        catalog_version="test-v1",
        catalog_hash="a" * 64,
        source_snapshot_json="{}",
        training_topics_json="[]",
        technical_risk_tags_json="[]",
        special_risks_json="[]",
        output_formats_json='["pptx","pdf"]',
        primary_output_format="pptx",
        created_by_id=9,
    )
    row.id = 501
    return row


def _rendered() -> RenderedPresentation:
    return RenderedPresentation(
        pptx_bytes=b"PK-pptx-test-bytes",
        pdf_bytes=b"%PDF-test-bytes",
        slide_count=1,
    )


def test_feature_disabled_stops_before_renderer_or_storage(monkeypatch):
    row = _row()
    db = MagicMock()
    store = FakeStore()
    monkeypatch.setattr(generation, "nace_training_presentation_active", lambda: False)
    renderer = MagicMock()
    monkeypatch.setattr(generation, "render_presentation", renderer)

    with pytest.raises(generation.PresentationGenerationError) as exc:
        generation.generate_and_store_version(db, row=row, store=store)

    assert exc.value.code == "feature_disabled"
    renderer.assert_not_called()
    assert store.put_calls == []
    db.commit.assert_not_called()


def test_success_stores_both_outputs_and_commits_generated_state(monkeypatch):
    row = _row()
    db = MagicMock()
    store = FakeStore()
    monkeypatch.setattr(generation, "nace_training_presentation_active", lambda: True)
    monkeypatch.setattr(generation, "render_presentation", lambda _manifest: _rendered())

    result = generation.generate_and_store_version(db, row=row, store=store)

    assert result is row
    assert row.status == "generated"
    assert row.pptx_storage_key and row.pptx_storage_key.endswith(".pptx")
    assert row.pdf_storage_key and row.pdf_storage_key.endswith(".pdf")
    assert set(store.data) == {row.pptx_storage_key, row.pdf_storage_key}
    assert row.pptx_file_hash == hashlib.sha256(_rendered().pptx_bytes).hexdigest()
    assert row.pdf_file_hash == hashlib.sha256(_rendered().pdf_bytes).hexdigest()
    assert row.pptx_content_type == PPTX_CONTENT_TYPE
    assert row.pdf_content_type == PDF_CONTENT_TYPE
    assert row.failure_code is None
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(row)

    pptx = generation.read_generated_output(row=row, output_format="pptx", store=store)
    pdf = generation.read_generated_output(row=row, output_format="pdf", store=store)
    assert pptx.content == _rendered().pptx_bytes
    assert pdf.content == _rendered().pdf_bytes
    assert pptx.filename == "nace-egitim-101-v2.pptx"
    assert pdf.filename == "nace-egitim-101-v2.pdf"


def test_second_storage_failure_deletes_first_and_marks_version_failed(monkeypatch):
    row = _row()
    db = MagicMock()
    store = FakeStore(fail_on=".pdf")
    monkeypatch.setattr(generation, "nace_training_presentation_active", lambda: True)
    monkeypatch.setattr(generation, "render_presentation", lambda _manifest: _rendered())

    with pytest.raises(generation.PresentationGenerationError) as exc:
        generation.generate_and_store_version(db, row=row, store=store)

    assert exc.value.code == "storage_failed"
    assert row.status == "failed"
    assert row.failure_code == "storage_failed"
    assert row.pptx_storage_key is None
    assert row.pdf_storage_key is None
    assert store.data == {}
    assert any(key.endswith(".pptx") for key in store.delete_calls)
    db.commit.assert_called_once()


def test_database_commit_failure_deletes_both_objects(monkeypatch):
    row = _row()
    db = MagicMock()
    db.commit.side_effect = RuntimeError("db down")
    store = FakeStore()
    monkeypatch.setattr(generation, "nace_training_presentation_active", lambda: True)
    monkeypatch.setattr(generation, "render_presentation", lambda _manifest: _rendered())

    with pytest.raises(generation.PresentationGenerationError) as exc:
        generation.generate_and_store_version(db, row=row, store=store)

    assert exc.value.code == "database_commit_failed"
    assert store.data == {}
    assert len(store.delete_calls) == 2
    db.rollback.assert_called_once()


def test_download_detects_missing_or_tampered_file():
    row = _row(status="generated")
    store = FakeStore()
    row.pptx_storage_key = "presentations/a.pptx"
    row.pptx_file_hash = hashlib.sha256(b"original").hexdigest()
    row.pptx_content_type = PPTX_CONTENT_TYPE

    with pytest.raises(generation.PresentationGenerationError) as missing:
        generation.read_generated_output(row=row, output_format="pptx", store=store)
    assert missing.value.code == "output_missing"

    store.data[row.pptx_storage_key] = b"tampered"
    with pytest.raises(generation.PresentationGenerationError) as mismatch:
        generation.read_generated_output(row=row, output_format="pptx", store=store)
    assert mismatch.value.code == "output_hash_mismatch"


def test_generated_or_approved_version_is_not_overwritten(monkeypatch):
    row = _row(status="generated")
    db = MagicMock()
    store = FakeStore()
    monkeypatch.setattr(generation, "nace_training_presentation_active", lambda: True)
    with pytest.raises(generation.PresentationGenerationError) as exc:
        generation.generate_and_store_version(db, row=row, store=store)
    assert exc.value.code == "invalid_version_status"
    assert store.put_calls == []
