from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api import training_presentation as api
from app.services.training_presentation_approval import (
    APPLICATION_APPROVAL_NOTICE,
    PresentationApprovalError,
)


def _training():
    return SimpleNamespace(id=101, company_id=35, branch_id=None)


def _version(*, status: str = "generated"):
    return SimpleNamespace(
        id=501,
        training_id=101,
        company_id=35,
        branch_id=None,
        version=2,
        status=status,
        manifest_hash="c" * 64,
        pptx_file_hash="d" * 64,
        pdf_file_hash="e" * 64,
    )


def _approval():
    return SimpleNamespace(
        id=601,
        presentation_version_id=501,
        training_id=101,
        company_id=35,
        branch_id=None,
        approval_method="application_approval",
        manifest_hash="c" * 64,
        pptx_file_hash="d" * 64,
        pdf_file_hash="e" * 64,
        approver_user_id=9,
        approver_name="Test Uzman",
        approver_role="safety_specialist",
        approval_note="Kontrol edildi.",
        esign_request_id=None,
        esign_evidence_json=None,
        legal_notice=APPLICATION_APPROVAL_NOTICE,
        event_hash="f" * 64,
        created_at=None,
    )


def _user():
    return SimpleNamespace(id=9, role="safety_specialist", company_id=35, full_name="Test Uzman")


def test_approval_get_is_company_scoped_and_read_only(monkeypatch):
    db = MagicMock()
    db.get.return_value = _training()
    checked: list[int] = []
    monkeypatch.setattr(
        api,
        "ensure_company_access",
        lambda _db, _user, company_id: checked.append(company_id),
    )
    monkeypatch.setattr(api, "get_presentation_version", lambda *_args, **_kwargs: _version(status="approved"))
    monkeypatch.setattr(api, "get_presentation_approval", lambda *_args, **_kwargs: _approval())
    monkeypatch.setattr(api, "approval_payload", lambda row: {"id": row.id, "immutable": True})

    response = api.presentation_version_approval(101, 501, db=db, user=_user())
    assert checked == [35]
    assert response == {
        "training_id": 101,
        "version_id": 501,
        "approved": True,
        "approval": {"id": 601, "immutable": True},
        "read_only": True,
    }
    db.commit.assert_not_called()


def test_application_approval_passes_exact_hash_and_commits(monkeypatch):
    db = MagicMock()
    db.get.return_value = _training()
    row = _version()
    approval = _approval()
    monkeypatch.setattr(api, "ensure_company_access", lambda *_args, **_kwargs: 35)
    monkeypatch.setattr(api, "get_presentation_version", lambda *_args, **_kwargs: row)
    captured = {}

    def approve(_db, **kwargs):
        captured.update(kwargs)
        row.status = "approved"
        return approval

    monkeypatch.setattr(api, "approve_presentation_version", approve)
    monkeypatch.setattr(api, "approval_payload", lambda item: {"id": item.id, "method": item.approval_method})
    monkeypatch.setattr(api, "version_payload", lambda item, **_kwargs: {"id": item.id, "status": item.status})
    monkeypatch.setattr(api, "get_presentation_approval", lambda *_args, **_kwargs: approval)
    payload = api.PresentationApprovalRequest(
        approval_method="application_approval",
        confirmed_manifest_hash="c" * 64,
        approval_note="Kontrol edildi.",
    )

    response = api.approve_presentation(101, 501, payload, db=db, user=_user())
    assert captured["row"] is row
    assert captured["method"] == "application_approval"
    assert captured["confirmed_manifest_hash"] == "c" * 64
    assert captured["note"] == "Kontrol edildi."
    assert captured["esign_request_id"] is None
    db.commit.assert_called_once()
    db.refresh.assert_any_call(approval)
    db.refresh.assert_any_call(row)
    assert response["approval"] == {"id": 601, "method": "application_approval"}
    assert response["version"]["status"] == "approved"


def test_approval_error_rolls_back_and_reports_core_workflow_unchanged(monkeypatch):
    db = MagicMock()
    db.get.return_value = _training()
    monkeypatch.setattr(api, "ensure_company_access", lambda *_args, **_kwargs: 35)
    monkeypatch.setattr(api, "get_presentation_version", lambda *_args, **_kwargs: _version())

    def reject(*_args, **_kwargs):
        raise PresentationApprovalError(
            "manifest_confirmation_mismatch",
            "Manifest hash eşleşmiyor.",
        )

    monkeypatch.setattr(api, "approve_presentation_version", reject)
    payload = api.PresentationApprovalRequest(
        approval_method="application_approval",
        confirmed_manifest_hash="0" * 64,
    )
    with pytest.raises(HTTPException) as exc:
        api.approve_presentation(101, 501, payload, db=db, user=_user())
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "manifest_confirmation_mismatch"
    assert exc.value.detail["core_training_unaffected"] is True
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_unavailable_verified_esign_returns_service_error_without_core_effect(monkeypatch):
    db = MagicMock()
    db.get.return_value = _training()
    monkeypatch.setattr(api, "ensure_company_access", lambda *_args, **_kwargs: 35)
    monkeypatch.setattr(api, "get_presentation_version", lambda *_args, **_kwargs: _version())

    def reject(*_args, **_kwargs):
        raise PresentationApprovalError(
            "esign_not_verified",
            "E-imza talebi doğrulanmadı.",
        )

    monkeypatch.setattr(api, "approve_presentation_version", reject)
    payload = api.PresentationApprovalRequest(
        approval_method="qualified_esign",
        confirmed_manifest_hash="c" * 64,
        esign_request_id=701,
    )
    with pytest.raises(HTTPException) as exc:
        api.approve_presentation(101, 501, payload, db=db, user=_user())
    assert exc.value.status_code == 503
    assert exc.value.detail["code"] == "esign_not_verified"
    assert exc.value.detail["core_training_unaffected"] is True
    db.rollback.assert_called_once()


def test_archive_uses_company_access_commits_and_returns_approval(monkeypatch):
    db = MagicMock()
    db.get.return_value = _training()
    row = _version(status="approved")
    approval = _approval()
    monkeypatch.setattr(api, "ensure_company_access", lambda *_args, **_kwargs: 35)
    monkeypatch.setattr(api, "get_presentation_version", lambda *_args, **_kwargs: row)

    def archive(_db, **kwargs):
        assert kwargs["row"] is row
        row.status = "archived"
        return row

    monkeypatch.setattr(api, "archive_presentation_version", archive)
    monkeypatch.setattr(api, "version_payload", lambda item, **_kwargs: {"id": item.id, "status": item.status})
    monkeypatch.setattr(api, "get_presentation_approval", lambda *_args, **_kwargs: approval)
    monkeypatch.setattr(api, "approval_payload", lambda item: {"id": item.id})

    response = api.archive_presentation(101, 501, db=db, user=_user())
    assert response == {"id": 501, "status": "archived", "approval": {"id": 601}}
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(row)


def test_approval_endpoint_propagates_company_access_denial(monkeypatch):
    db = MagicMock()
    db.get.return_value = _training()

    def deny(*_args, **_kwargs):
        raise HTTPException(403, "Bu firmaya erişim yetkiniz yok.")

    monkeypatch.setattr(api, "ensure_company_access", deny)
    with pytest.raises(HTTPException) as exc:
        api.presentation_version_approval(101, 501, db=db, user=_user())
    assert exc.value.status_code == 403
