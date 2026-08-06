from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api import training_presentation as api
from app.services.training_presentation_generation import (
    PresentationDownload,
    PresentationGenerationError,
)


def _training():
    return SimpleNamespace(id=101, company_id=35, branch_id=None)


def _row():
    return SimpleNamespace(
        id=501,
        training_id=101,
        company_id=35,
        version=2,
        status="generated",
    )


def test_render_endpoint_uses_company_access_and_returns_local_status(monkeypatch):
    db = MagicMock()
    db.get.return_value = _training()
    user = SimpleNamespace(id=9, role="company_admin", company_id=35)
    checked: list[int] = []

    monkeypatch.setattr(
        api,
        "ensure_company_access",
        lambda _db, _user, company_id: checked.append(company_id),
    )
    monkeypatch.setattr(api, "nace_training_presentation_active", lambda *_: True)
    monkeypatch.setattr(api, "get_presentation_version", lambda *_args, **_kwargs: _row())
    monkeypatch.setattr(api, "generate_and_store_version", lambda _db, *, row: row)
    monkeypatch.setattr(
        api,
        "generation_status_payload",
        lambda row: {"version_id": row.id, "status": row.status},
    )

    response = api.render_presentation_version(101, 501, db=db, user=user)
    assert checked == [35]
    assert response == {"version_id": 501, "status": "generated"}


def test_render_endpoint_denies_non_pilot_before_version_lookup(monkeypatch):
    db = MagicMock()
    db.get.return_value = _training()
    user = SimpleNamespace(id=9, role="company_admin", company_id=35)
    monkeypatch.setattr(api, "ensure_company_access", lambda *_args, **_kwargs: 35)
    monkeypatch.setattr(api, "nace_training_presentation_active", lambda *_: False)
    version_lookup = MagicMock()
    monkeypatch.setattr(api, "get_presentation_version", version_lookup)

    with pytest.raises(HTTPException) as exc:
        api.render_presentation_version(101, 501, db=db, user=user)
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "pilot_access_denied"
    version_lookup.assert_not_called()


def test_render_endpoint_maps_generation_failure_without_touching_core(monkeypatch):
    db = MagicMock()
    db.get.return_value = _training()
    user = SimpleNamespace(id=9, role="company_admin", company_id=35)
    monkeypatch.setattr(api, "ensure_company_access", lambda *_args, **_kwargs: 35)
    monkeypatch.setattr(api, "nace_training_presentation_active", lambda *_: True)
    monkeypatch.setattr(api, "get_presentation_version", lambda *_args, **_kwargs: _row())

    def fail(*_args, **_kwargs):
        raise PresentationGenerationError("pilot_access_denied", "Sunum özelliği bu pilot için kapalıdır.")

    monkeypatch.setattr(api, "generate_and_store_version", fail)
    with pytest.raises(HTTPException) as exc:
        api.render_presentation_version(101, 501, db=db, user=user)
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "pilot_access_denied"
    assert exc.value.detail["core_training_unaffected"] is True


def test_download_endpoint_sets_safe_headers_after_hash_verified_read(monkeypatch):
    db = MagicMock()
    db.get.return_value = _training()
    user = SimpleNamespace(id=9, role="company_admin", company_id=35)
    monkeypatch.setattr(api, "ensure_company_access", lambda *_args, **_kwargs: 35)
    monkeypatch.setattr(api, "get_presentation_version", lambda *_args, **_kwargs: _row())
    monkeypatch.setattr(
        api,
        "read_generated_output",
        lambda **_kwargs: PresentationDownload(
            content=b"%PDF-test",
            content_type="application/pdf",
            filename="nace-egitim-101-v2.pdf",
            file_hash="a" * 64,
        ),
    )

    response = api.download_presentation_version(101, 501, "pdf", db=db, user=user)
    assert response.media_type == "application/pdf"
    assert response.headers["content-disposition"] == (
        'attachment; filename="nace-egitim-101-v2.pdf"'
    )
    assert response.headers["x-content-sha256"] == "a" * 64
    assert response.headers["cache-control"] == "private, no-store"


def test_download_remains_available_when_pilot_is_force_disabled(monkeypatch):
    db = MagicMock()
    db.get.return_value = _training()
    user = SimpleNamespace(id=9, role="company_admin", company_id=35)
    monkeypatch.setattr(api, "ensure_company_access", lambda *_args, **_kwargs: 35)
    monkeypatch.setattr(
        api,
        "nace_training_presentation_active",
        lambda *_: (_ for _ in ()).throw(AssertionError("download must not check rollout")),
    )
    monkeypatch.setattr(api, "get_presentation_version", lambda *_args, **_kwargs: _row())
    monkeypatch.setattr(
        api,
        "read_generated_output",
        lambda **_kwargs: PresentationDownload(
            content=b"%PDF-history",
            content_type="application/pdf",
            filename="nace-egitim-101-v2.pdf",
            file_hash="b" * 64,
        ),
    )

    response = api.download_presentation_version(101, 501, "pdf", db=db, user=user)
    assert response.headers["x-content-sha256"] == "b" * 64


def test_download_endpoint_propagates_company_access_denial(monkeypatch):
    db = MagicMock()
    db.get.return_value = _training()
    user = SimpleNamespace(id=9, role="company_admin", company_id=99)

    def deny(*_args, **_kwargs):
        raise HTTPException(403, "Bu firmaya erişim yetkiniz yok.")

    monkeypatch.setattr(api, "ensure_company_access", deny)
    with pytest.raises(HTTPException) as exc:
        api.download_presentation_version(101, 501, "pdf", db=db, user=user)
    assert exc.value.status_code == 403
