from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api import personnel_profiles as profile_api
from app.core import personnel_profile_config as profile_config
from app.models.entities import Employee, IsgProfessional, UserRole
from app.services.personnel_profile_readonly import (
    READINESS_VERSION,
    SUMMARY_VERSION,
    build_employee_profile_summary,
    build_personnel_profile_readiness,
    build_professional_profile_summary,
    mask_national_identity,
)


def _employee(**overrides):
    values = {
        "id": 41,
        "company_id": 35,
        "branch_id": None,
        "full_name": "Ayşe Yılmaz",
        "national_id_masked": "12345678990",
        "job_title": "Kaynakçı",
        "department": "Üretim",
        "start_date": date(2024, 1, 15),
        "special_status": "Engelli/Hükümlü",
        "is_active": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _professional(**overrides):
    values = {
        "id": 7,
        "osgb_id": 4,
        "full_name": "Mehmet Uzman",
        "email": "uzman@example.test",
        "phone": "+90 555 000 00 00",
        "professional_type": "safety_specialist",
        "certificate_class": "A",
        "certificate_number": "UZM-123",
        "certificate_date": date(2020, 5, 1),
        "is_active": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _rollout(*, active: bool = False):
    return {
        "global_enabled": active,
        "force_off": False,
        "allowlist_configured": active,
        "pilot_company": active,
        "active": active,
    }


def test_rollout_is_disabled_by_default_and_force_off_always_wins(monkeypatch):
    settings = profile_config.personnel_profile_settings
    monkeypatch.setattr(settings, "personnel_profile_card_enabled", False)
    monkeypatch.setattr(settings, "personnel_profile_card_force_off", False)
    monkeypatch.setattr(settings, "personnel_profile_card_pilot_company_ids", "")

    assert profile_config.personnel_profile_card_active(35) is False
    assert profile_config.personnel_profile_pilot_company_ids() == frozenset()

    monkeypatch.setattr(settings, "personnel_profile_card_enabled", True)
    assert profile_config.personnel_profile_card_active(35) is False

    monkeypatch.setattr(
        settings,
        "personnel_profile_card_pilot_company_ids",
        "35, 99, bad, 0, -1, 35",
    )
    assert profile_config.personnel_profile_pilot_company_ids() == frozenset({35, 99})
    assert profile_config.personnel_profile_card_active(35) is True
    assert profile_config.personnel_profile_card_active(36) is False

    rollout = profile_config.personnel_profile_rollout(35)
    assert rollout == {
        "global_enabled": True,
        "force_off": False,
        "allowlist_configured": True,
        "pilot_company": True,
        "active": True,
    }
    assert "company_ids" not in rollout

    monkeypatch.setattr(settings, "personnel_profile_card_force_off", True)
    assert profile_config.personnel_profile_card_active(35) is False
    assert profile_config.personnel_profile_rollout(35)["active"] is False


def test_phase_two_config_does_not_offer_restricted_or_external_sharing_flags():
    settings = profile_config.personnel_profile_settings
    assert not hasattr(settings, "personnel_profile_restricted_data_enabled")
    assert not hasattr(settings, "personnel_profile_external_sharing_enabled")
    assert not hasattr(profile_config, "personnel_profile_restricted_data_active")
    assert not hasattr(profile_config, "personnel_profile_external_sharing_active")


def test_national_identity_is_never_returned_raw():
    assert mask_national_identity("12345678990") == "123******90"
    assert mask_national_identity("123******90") == "123******90"
    assert mask_national_identity("12") is None
    assert mask_national_identity(None) is None


def test_employee_summary_excludes_special_and_restricted_data():
    employee = _employee()
    result = build_employee_profile_summary(
        employee,
        company_name="Test İşyerim",
        rollout=_rollout(active=True),
    )

    assert result["summary_version"] == SUMMARY_VERSION
    assert result["profile"]["national_identity_masked"] == "123******90"
    assert result["privacy"]["special_status_included"] is False
    assert result["privacy"]["health_data_included"] is False
    assert result["privacy"]["criminal_record_included"] is False
    serialized = json.dumps(result, ensure_ascii=False)
    assert employee.special_status not in serialized
    assert employee.national_id_masked not in serialized
    assert "health" not in result["profile"]


def test_professional_summary_is_read_only_and_data_minimized():
    result = build_professional_profile_summary(
        _professional(),
        company_id=35,
        company_name="Test İşyerim",
        active_assignment_count=3,
        rollout=_rollout(active=True),
    )

    assert result["summary_version"] == SUMMARY_VERSION
    assert result["profile"]["active_assignment_count"] == 3
    assert result["capabilities"]["read_only_summary"] is True
    assert result["capabilities"]["file_upload"] is False
    assert result["capabilities"]["cv_generation"] is False
    assert result["capabilities"]["external_sharing"] is False
    assert result["capabilities"]["restricted_data"] is False


def test_readiness_never_exposes_allowlist_members():
    result = build_personnel_profile_readiness(company_id=35, rollout=_rollout(active=False))
    assert result["readiness_version"] == READINESS_VERSION
    assert result["enabled"] is False
    assert result["core_personnel_unaffected"] is True
    assert result["existing_employee_import_unaffected"] is True
    assert result["capabilities"]["restricted_data"] is False
    assert "company_ids" not in result["rollout"]


def test_readiness_endpoint_uses_existing_company_access_boundary(monkeypatch):
    db = MagicMock()
    user = SimpleNamespace(id=9, company_id=35, osgb_id=4, role=UserRole.COMPANY_ADMIN)
    checked: list[int] = []

    monkeypatch.setattr(
        profile_api,
        "ensure_company_access",
        lambda _db, _user, company_id: checked.append(company_id),
    )
    monkeypatch.setattr(profile_api, "personnel_profile_rollout", lambda _cid: _rollout())

    result = profile_api.personnel_profile_readiness(35, db=db, user=user)
    assert checked == [35]
    assert result["company_id"] == 35
    assert result["visible"] is False


def test_employee_summary_endpoint_is_fail_closed_while_feature_is_disabled(monkeypatch):
    db = MagicMock()
    employee = _employee()
    db.get.return_value = employee
    user = SimpleNamespace(id=9, company_id=35, osgb_id=4, role=UserRole.COMPANY_ADMIN)
    checked: list[int] = []

    monkeypatch.setattr(
        profile_api,
        "ensure_company_access",
        lambda _db, _user, company_id: checked.append(company_id),
    )
    monkeypatch.setattr(profile_api, "personnel_profile_card_active", lambda _cid: False)
    monkeypatch.setattr(profile_api, "personnel_profile_rollout", lambda _cid: _rollout())

    with pytest.raises(HTTPException) as exc:
        profile_api.employee_profile_summary(41, db=db, user=user)
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "personnel_profile_disabled"
    assert checked == [35]


def test_employee_summary_endpoint_returns_minimum_data_when_enabled(monkeypatch):
    db = MagicMock()
    employee = _employee()
    company = SimpleNamespace(id=35, name="Test İşyerim")

    def get(model, object_id):
        if model is Employee and object_id == 41:
            return employee
        if model.__name__ == "Company" and object_id == 35:
            return company
        return None

    db.get.side_effect = get
    user = SimpleNamespace(id=9, company_id=35, osgb_id=4, role=UserRole.COMPANY_ADMIN)
    monkeypatch.setattr(profile_api, "ensure_company_access", lambda *_: None)
    monkeypatch.setattr(profile_api, "personnel_profile_card_active", lambda _cid: True)
    monkeypatch.setattr(profile_api, "personnel_profile_rollout", lambda _cid: _rollout(active=True))

    result = profile_api.employee_profile_summary(41, db=db, user=user)
    assert result["profile"]["full_name"] == "Ayşe Yılmaz"
    assert result["profile"]["national_identity_masked"] == "123******90"
    assert "special_status" not in result["profile"]


def test_professional_context_requires_active_assignment(monkeypatch):
    db = MagicMock()
    db.scalar.return_value = None
    user = SimpleNamespace(id=9, company_id=None, osgb_id=4, role=UserRole.COMPANY_ADMIN)
    monkeypatch.setattr(profile_api, "ensure_company_access", lambda *_: None)

    with pytest.raises(HTTPException) as exc:
        profile_api._ensure_professional_access(db, user, _professional(), 35)
    assert exc.value.status_code == 404


def test_field_professional_cannot_open_another_professional(monkeypatch):
    db = MagicMock()
    db.scalar.return_value = 101
    user = SimpleNamespace(id=9, company_id=None, osgb_id=4, role=UserRole.SAFETY_SPECIALIST)
    monkeypatch.setattr(profile_api, "ensure_company_access", lambda *_: None)
    monkeypatch.setattr(profile_api, "find_professional_for_user", lambda *_: _professional(id=99))

    with pytest.raises(HTTPException) as exc:
        profile_api._ensure_professional_access(db, user, _professional(id=7), 35)
    assert exc.value.status_code == 403


def test_professional_summary_endpoint_uses_assignment_and_company_scope(monkeypatch):
    db = MagicMock()
    professional = _professional()
    company = SimpleNamespace(id=35, name="Test İşyerim")

    def get(model, object_id):
        if model is IsgProfessional and object_id == 7:
            return professional
        if model.__name__ == "Company" and object_id == 35:
            return company
        return None

    db.get.side_effect = get
    db.scalar.return_value = 3
    user = SimpleNamespace(id=9, company_id=None, osgb_id=4, role=UserRole.COMPANY_ADMIN)
    checked: list[tuple[int, int]] = []
    monkeypatch.setattr(
        profile_api,
        "_ensure_professional_access",
        lambda _db, _user, _professional, company_id: checked.append(
            (_professional.id, company_id)
        ),
    )
    monkeypatch.setattr(profile_api, "personnel_profile_card_active", lambda _cid: True)
    monkeypatch.setattr(profile_api, "personnel_profile_rollout", lambda _cid: _rollout(active=True))

    result = profile_api.professional_profile_summary(7, 35, db=db, user=user)
    assert checked == [(7, 35)]
    assert result["scope"]["company_id"] == 35
    assert result["profile"]["active_assignment_count"] == 3


def test_router_exposes_only_read_only_phase_two_routes():
    paths = {route.path for route in profile_api.router.routes}
    assert paths == {
        "/personnel-profiles/readiness",
        "/personnel-profiles/employee/{employee_id}/summary",
        "/personnel-profiles/professional/{professional_id}/summary",
    }
