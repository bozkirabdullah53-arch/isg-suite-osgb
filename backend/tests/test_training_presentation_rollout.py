from __future__ import annotations

from app.core import config


def _set_rollout(monkeypatch, *, enabled: bool, force_off: bool, pilots: str) -> None:
    monkeypatch.setattr(config.settings, "nace_training_presentation_enabled", enabled)
    monkeypatch.setattr(config.settings, "nace_training_presentation_force_off", force_off)
    monkeypatch.setattr(config.settings, "nace_training_presentation_pilot_company_ids", pilots)


def test_rollout_defaults_fail_closed(monkeypatch):
    _set_rollout(monkeypatch, enabled=False, force_off=False, pilots="")
    assert config.nace_training_presentation_active() is False
    assert config.nace_training_presentation_active(35) is False
    assert config.nace_training_presentation_pilot_company_ids() == frozenset()
    assert config.nace_training_presentation_rollout(35) == {
        "global_enabled": False,
        "force_off": False,
        "allowlist_configured": False,
        "pilot_company": False,
        "active": False,
    }


def test_global_flag_without_allowlist_never_opens_a_company(monkeypatch):
    _set_rollout(monkeypatch, enabled=True, force_off=False, pilots="")
    assert config.nace_training_presentation_active() is True
    assert config.nace_training_presentation_active(35) is False
    rollout = config.nace_training_presentation_rollout(35)
    assert rollout["global_enabled"] is True
    assert rollout["allowlist_configured"] is False
    assert rollout["pilot_company"] is False
    assert rollout["active"] is False


def test_only_explicit_positive_company_ids_are_allowed(monkeypatch):
    _set_rollout(
        monkeypatch,
        enabled=True,
        force_off=False,
        pilots="35,  99,bad,0,-1,35,  ",
    )
    assert config.nace_training_presentation_pilot_company_ids() == frozenset({35, 99})
    assert config.nace_training_presentation_active(35) is True
    assert config.nace_training_presentation_active(99) is True
    assert config.nace_training_presentation_active(36) is False
    assert config.nace_training_presentation_active(None) is True


def test_force_off_wins_over_global_flag_and_allowlist(monkeypatch):
    _set_rollout(monkeypatch, enabled=True, force_off=True, pilots="35")
    assert config.nace_training_presentation_active() is False
    assert config.nace_training_presentation_active(35) is False
    rollout = config.nace_training_presentation_rollout(35)
    assert rollout["global_enabled"] is True
    assert rollout["force_off"] is True
    assert rollout["pilot_company"] is True
    assert rollout["active"] is False


def test_rollout_diagnostics_never_expose_allowlist_members(monkeypatch):
    _set_rollout(monkeypatch, enabled=True, force_off=False, pilots="35,99")
    rollout = config.nace_training_presentation_rollout(35)
    assert set(rollout) == {
        "global_enabled",
        "force_off",
        "allowlist_configured",
        "pilot_company",
        "active",
    }
    assert 99 not in rollout.values()
    assert "company_ids" not in rollout
    assert "pilot_company_ids" not in rollout
