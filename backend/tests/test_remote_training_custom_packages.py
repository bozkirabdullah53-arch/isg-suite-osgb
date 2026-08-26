"""Focused regression tests for additive OSGB custom remote-training packages."""
from __future__ import annotations


def test_custom_package_code_keeps_selected_sector_and_reviewed_exam_pack():
    from app.services.remote_training_custom_packages import (
        automatic_exam_items_for_package_with_custom,
        custom_package_base_code,
        custom_package_sector_code,
    )

    code = "custom--working_at_height--abc123"
    assert custom_package_sector_code(code) == "working_at_height"
    assert custom_package_base_code(code) == "working-at-height-ohs"

    items = automatic_exam_items_for_package_with_custom(code)
    assert len(items) == 20
    assert len({item["question_code"] for item in items}) == 20
    assert len({item["topic_code"] for item in items}) == 20
    assert all(
        item["question_text"]
        and len(item["options"]) == 4
        and item["correct_option"] in "ABCD"
        and item["answer_explanation"]
        for item in items
    )


def test_emergency_teams_custom_package_uses_one_shared_ten_question_exam():
    from app.services.remote_training_custom_packages import (
        automatic_exam_items_for_package_with_custom,
        custom_package_base_code,
    )

    code = "custom--emergency_teams--abc123"
    assert custom_package_base_code(code) == "emergency-teams-ohs"

    items = automatic_exam_items_for_package_with_custom(code)
    assert len(items) == 10
    assert len({item["question_code"] for item in items}) == 10
    assert len({item["topic_code"] for item in items}) == 10
    assert all(item["scopes"] == [{"type": "common", "value": "*"}] for item in items)


def test_custom_package_unknown_or_unreviewed_sector_fails_closed():
    import pytest

    from app.services.remote_training_custom_packages import (
        automatic_exam_items_for_package_with_custom,
        custom_package_base_code,
        custom_package_sector_code,
    )

    assert custom_package_sector_code("custom--foundry--abc123") is None
    assert custom_package_base_code("custom--foundry--abc123") is None
    with pytest.raises(RuntimeError):
        automatic_exam_items_for_package_with_custom("custom--foundry--abc123")


def test_custom_package_uses_existing_strict_rollout_gate(monkeypatch):
    from app.core.config import settings
    from app.services.remote_training_custom_packages import strict_policy_active_with_custom

    monkeypatch.setattr(settings, "remote_basic_ohs_strict_policy_enabled", True)
    monkeypatch.setattr(settings, "remote_basic_ohs_strict_policy_force_off", False)
    monkeypatch.setattr(settings, "remote_basic_ohs_strict_policy_package_codes", "construction-ohs")
    monkeypatch.setattr(settings, "remote_basic_ohs_strict_policy_pilot_company_ids", "")

    assert strict_policy_active_with_custom("custom--construction--abc123", 77)
    assert not strict_policy_active_with_custom("custom--food--abc123", 77)


def test_custom_package_extension_installer_is_idempotent_and_routes_once():
    from app.api import remote_training as remote_api
    from app.services.remote_training_custom_packages import install_remote_training_custom_packages

    first = install_remote_training_custom_packages()
    second = install_remote_training_custom_packages()
    assert first["installed"] is True
    assert second["installed"] is True

    exact_routes = [
        route
        for route in remote_api.router.routes
        if str(getattr(route, "path", "") or "").endswith("/catalog/packages")
    ]
    get_routes = [route for route in exact_routes if "GET" in set(getattr(route, "methods", set()) or set())]
    post_routes = [route for route in exact_routes if "POST" in set(getattr(route, "methods", set()) or set())]
    assert len(get_routes) == 1
    assert len(post_routes) == 1
