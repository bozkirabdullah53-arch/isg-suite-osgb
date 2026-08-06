from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api import training_presentation as presentation_api
from app.core import config
from app.services.training_presentation_contract import CONTRACT_VERSION, TEMPLATE_VERSION
from app.services.training_presentation_readiness import (
    READINESS_VERSION,
    build_presentation_readiness_payload,
)
from app.services.training_presentation_renderer import RENDERER_VERSION


def _training(*, status: str = "planned"):
    return SimpleNamespace(
        id=101,
        company_id=35,
        branch_id=None,
        title="Temel İş Sağlığı ve Güvenliği Eğitimi",
        start_date=date(2026, 8, 6),
        end_date=date(2026, 8, 6),
        hazard_class="Tehlikeli",
        status=status,
    )


def _snapshot(*, status: str = "verified", topics: list[str] | None = None):
    topics = topics if topics is not None else [f"Konu {i}" for i in range(1, 6)]
    return SimpleNamespace(
        training_id=101,
        company_id=35,
        branch_id=None,
        catalog_key="nace_62_01_01",
        nace_code="62.01.01",
        nace_description="Bilgisayar programlama faaliyetleri",
        hazard_class="Az Tehlikeli",
        content_profile_code="bilisim_yazilim_it",
        classification_status=status,
        catalog_version="test-v1",
        catalog_hash="a" * 64,
        training_topics_json=json.dumps(topics, ensure_ascii=False),
        technical_risk_tags_json=json.dumps(
            ["display_screen", "server_room", "psychosocial"], ensure_ascii=False
        ),
        special_risks_json=json.dumps(["uzun_sureli_ekran"], ensure_ascii=False),
        required_duration_hours=8,
        required_duration_minutes=360,
    )


def _exam_ready(ready: bool = True):
    return {
        "ready": ready,
        "verified_snapshot": ready,
        "available": {"foundation": 5 if ready else 0, "work_specific": 15 if ready else 0},
        "required": {"foundation": 5, "work_specific": 15},
        "policy": "exact-nace-test",
    }


def test_presentation_feature_flag_defaults_to_safe_off_and_force_off_wins(monkeypatch):
    monkeypatch.setattr(config.settings, "nace_training_presentation_enabled", False)
    monkeypatch.setattr(config.settings, "nace_training_presentation_force_off", False)
    assert config.nace_training_presentation_active() is False

    monkeypatch.setattr(config.settings, "nace_training_presentation_enabled", True)
    assert config.nace_training_presentation_active() is True

    monkeypatch.setattr(config.settings, "nace_training_presentation_force_off", True)
    assert config.nace_training_presentation_active() is False


def test_disabled_feature_is_invisible_and_never_blocks_core_training():
    payload = build_presentation_readiness_payload(
        training=_training(),
        snapshot=_snapshot(),
        exam_readiness=_exam_ready(),
        enabled=False,
    )

    assert payload["readiness_version"] == READINESS_VERSION
    assert payload["enabled"] is False
    assert payload["visible"] is False
    assert payload["read_only"] is True
    assert payload["manifest_preview_supported"] is True
    assert payload["generation_supported"] is True
    assert payload["generation_allowed"] is False
    assert payload["renderer_version"] == RENDERER_VERSION
    assert payload["core_training_unaffected"] is True
    blocker_codes = {item["code"] for item in payload["blockers"]}
    assert blocker_codes == {"feature_flag"}
    renderer = next(item for item in payload["checks"] if item["code"] == "presentation_renderer")
    assert renderer["ok"] is True


def test_verified_snapshot_and_renderer_are_ready_when_feature_is_enabled():
    payload = build_presentation_readiness_payload(
        training=_training(),
        snapshot=_snapshot(),
        exam_readiness=_exam_ready(),
        enabled=True,
    )

    assert payload["visible"] is True
    assert payload["classification"]["status"] == "verified"
    assert payload["classification"]["nace_code"] == "62.01.01"
    assert len(payload["source_data"]["training_topics"]) == 5
    assert len(payload["source_data"]["technical_risk_tags"]) == 3
    assert payload["source_data"]["exam_readiness"]["ready"] is True
    contract = payload["template_contract"]
    assert contract["status"] == "approved_for_implementation"
    assert contract["version"] == CONTRACT_VERSION
    assert contract["template_version"] == TEMPLATE_VERSION
    assert len(contract["contract_hash"]) == 64
    assert contract["output_formats"] == ["pptx", "pdf"]
    assert contract["tracking_issue"] == 76
    assert payload["blockers"] == []
    assert payload["generation_supported"] is True
    assert payload["generation_allowed"] is True
    assert "sunum sürümü" in payload["next_action"].lower()


def test_legacy_or_incomplete_nace_is_never_invented_or_treated_as_ready():
    payload = build_presentation_readiness_payload(
        training=_training(),
        snapshot=None,
        exam_readiness=_exam_ready(False),
        enabled=True,
    )

    assert payload["classification"]["persisted"] is False
    assert payload["classification"]["status"] == "legacy_unverified"
    assert payload["classification"]["nace_code"] is None
    assert payload["source_data"]["training_topics"] == []
    blocker_codes = {item["code"] for item in payload["blockers"]}
    assert "verified_nace_snapshot" in blocker_codes
    assert "five_training_topics" in blocker_codes
    assert "technical_risks" in blocker_codes
    assert "exact_exam_readiness" in blocker_codes
    assert "template_contract" not in blocker_codes
    assert "presentation_renderer" not in blocker_codes
    assert payload["generation_allowed"] is False


def test_cancelled_training_stays_blocked_even_with_verified_snapshot():
    payload = build_presentation_readiness_payload(
        training=_training(status="cancelled"),
        snapshot=_snapshot(),
        exam_readiness=_exam_ready(),
        enabled=True,
    )
    assert any(item["code"] == "training_not_cancelled" for item in payload["blockers"])
    assert payload["generation_allowed"] is False
    assert payload["core_training_unaffected"] is True


def test_readiness_endpoint_uses_existing_company_access_boundary(monkeypatch):
    db = MagicMock()
    training = _training()
    db.get.return_value = training
    user = SimpleNamespace(id=9, company_id=35, osgb_id=4, role="company_admin")
    checked: list[int] = []

    monkeypatch.setattr(
        presentation_api,
        "ensure_company_access",
        lambda _db, _user, company_id: checked.append(company_id),
    )
    monkeypatch.setattr(
        presentation_api,
        "training_presentation_readiness",
        lambda _db, *, training: {"training_id": training.id, "enabled": False},
    )

    result = presentation_api.presentation_readiness(101, db=db, user=user)
    assert checked == [35]
    assert result == {"training_id": 101, "enabled": False}


def test_readiness_endpoint_propagates_forbidden_company_access(monkeypatch):
    db = MagicMock()
    db.get.return_value = _training()
    user = SimpleNamespace(id=9, company_id=99, osgb_id=4, role="company_admin")

    def deny(*_args, **_kwargs):
        raise HTTPException(403, "Bu firmaya erişim yetkiniz yok.")

    monkeypatch.setattr(presentation_api, "ensure_company_access", deny)
    with pytest.raises(HTTPException) as exc:
        presentation_api.presentation_readiness(101, db=db, user=user)
    assert exc.value.status_code == 403


def test_readiness_endpoint_returns_404_for_unknown_training():
    db = MagicMock()
    db.get.return_value = None
    with pytest.raises(HTTPException) as exc:
        presentation_api.presentation_readiness(
            999,
            db=db,
            user=SimpleNamespace(id=9, role="global_admin"),
        )
    assert exc.value.status_code == 404
