"""render.yaml yedekleme yapılandırması — kaynak kontrollü rollout sözleşmesi.

İBYS Yedekleme Prosedürü'nün kod karşılığı: otomatik DB yedeği, işyeri yedeği,
offsite kopya ve aylık tatbikat cron'ları blueprint'te tanımlı olmalıdır.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

RENDER_YAML = Path(__file__).resolve().parents[2] / "render.yaml"

_SERVICE_RE = re.compile(r"^\s{2}- type:\s*(\S+)\s*$")
_NAME_RE = re.compile(r"^\s{4}name:\s*(\S+)\s*$")
_KEY_RE = re.compile(r"^\s*- key:\s*(\S+)\s*$")
_VALUE_RE = re.compile(r'^\s*value:\s*"?(.*?)"?\s*$')
_SCHEDULE_RE = re.compile(r"^\s{4}schedule:\s*\"?([^\"]+)\"?\s*$")
_START_RE = re.compile(r"^\s{4}startCommand:\s*(.+?)\s*$")


def _parse(text: str) -> dict[str, dict]:
    services: dict[str, dict] = {}
    current: dict | None = None
    pending_key: str | None = None
    for line in text.splitlines():
        match = _SERVICE_RE.match(line)
        if match:
            current = {"type": match.group(1), "env": {}}
            continue
        if current is None:
            continue
        match = _NAME_RE.match(line)
        if match:
            current["name"] = match.group(1)
            services[match.group(1)] = current
            continue
        match = _SCHEDULE_RE.match(line)
        if match:
            current["schedule"] = match.group(1)
            continue
        match = _START_RE.match(line)
        if match:
            current["start"] = match.group(1)
            continue
        match = _KEY_RE.match(line)
        if match:
            pending_key = match.group(1)
            continue
        if pending_key:
            match = _VALUE_RE.match(line)
            if match:
                current["env"][pending_key] = match.group(1)
                pending_key = None
    return services


@pytest.fixture(scope="module")
def services() -> dict[str, dict]:
    return _parse(RENDER_YAML.read_text(encoding="utf-8"))


def test_render_yaml_exists():
    assert RENDER_YAML.is_file()


def test_workplace_backups_enabled_in_api(services):
    api = services["isg-suite-api"]
    assert api["env"]["WORKPLACE_BACKUPS_ENABLED"] == "true"
    assert api["env"]["WORKPLACE_BACKUPS_FORCE_OFF"] == "false"


def test_workplace_backup_remote_enabled_in_api(services):
    api = services["isg-suite-api"]
    assert api["env"]["WORKPLACE_BACKUP_REMOTE_ENABLED"] == "true"


def test_frontend_flag_enabled(services):
    assert services["isg-suite-web"]["env"]["VITE_WORKPLACE_BACKUPS_ENABLED"] == "true"


def test_db_backup_enabled_and_offsite_in_api(services):
    api = services["isg-suite-api"]
    assert api["env"]["DB_BACKUP_ENABLED"] == "true"
    assert api["env"]["BACKUP_REMOTE_ENABLED"] == "true"
    assert api["env"]["BACKUP_ENCRYPTION_FORCE_OFF"] == "false"


def test_backup_restore_writes_stay_disabled_by_default(services):
    api = services["isg-suite-api"]
    assert api["env"]["BACKUP_RESTORE_ENABLED"] == "false"


def test_nightly_db_backup_cron_exists(services):
    cron = services["isg-suite-db-backup-nightly"]
    assert cron["type"] == "cron"
    assert cron["schedule"] == "0 22 * * *"
    assert "scripts.backup_database" in cron["start"]


def test_db_backup_cron_has_required_env(services):
    env = services["isg-suite-db-backup-nightly"]["env"]
    assert env["BACKUP_DIR"] == "/var/data/backups"
    assert env["BACKUP_REMOTE_ENABLED"] == "true"
    assert env["DB_BACKUP_ENABLED"] == "true"
    assert env["ENVIRONMENT"] == "production"


def test_workplace_backup_cron_enabled(services):
    cron = services["isg-suite-workplace-backups-nightly"]
    assert cron["env"]["WORKPLACE_BACKUPS_ENABLED"] == "true"


def test_monthly_restore_drill_cron_exists(services):
    cron = services["isg-suite-backup-restore-drill-monthly"]
    assert cron["type"] == "cron"
    assert cron["schedule"] == "0 21 15 * *"
    assert "scripts.backup_restore_drill" in cron["start"]
    assert "--latest" in cron["start"]


def test_backup_max_age_configured(services):
    assert services["isg-suite-api"]["env"]["BACKUP_MAX_AGE_HOURS"] == "36"


def test_backup_dir_is_persistent_disk(services):
    assert services["isg-suite-api"]["env"]["BACKUP_DIR"] == "/var/data/backups"
    assert services["isg-suite-api"]["env"]["UPLOAD_DIR"] == "/var/data/uploads"


def test_retention_days_configured(services):
    env = services["isg-suite-api"]["env"]
    assert env["DB_BACKUP_RETENTION_DAYS"] == "30"
    assert env["DB_BACKUP_WEEKLY_RETENTION_WEEKS"] == "12"
    assert env["DB_BACKUP_MONTHLY_RETENTION_MONTHS"] == "12"
    assert env["WORKPLACE_BACKUP_RETENTION_DAYS"] == "30"


def test_parser_finds_all_cron_services(services):
    crons = [name for name, cfg in services.items() if cfg["type"] == "cron"]
    assert "isg-suite-workplace-backups-nightly" in crons
    assert "isg-suite-db-backup-nightly" in crons
    assert "isg-suite-backup-restore-drill-monthly" in crons
    assert "isg-suite-backup-integrity-weekly" in crons
    assert "isg-suite-audit-chain-verify-daily" in crons


def test_integrity_scan_cron_exists(services):
    cron = services["isg-suite-backup-integrity-weekly"]
    assert cron["schedule"] == "0 20 * * 0"
    assert "scripts.backup_key_rotation" in cron["start"]


def test_audit_chain_cron_exists(services):
    cron = services["isg-suite-audit-chain-verify-daily"]
    assert cron["schedule"] == "30 21 * * *"
    assert "scripts.audit_chain_verify" in cron["start"]


def test_secrets_are_not_hardcoded(services):
    api_env = services["isg-suite-api"]["env"]
    assert "BACKUP_ENCRYPTION_KEY" not in api_env
    assert "SMTP_PASSWORD" not in api_env
    assert "SECRET_KEY" not in api_env


def test_offsite_staged_rollout_is_safe(services):
    """Aşama 1: offsite açık ama zorunlu değil — eksik kimlik bilgisi canlıyı düşürmez."""
    api_env = services["isg-suite-api"]["env"]
    cron_env = services["isg-suite-db-backup-nightly"]["env"]
    assert api_env["BACKUP_REMOTE_ENABLED"] == "true"
    assert api_env["BACKUP_REMOTE_REQUIRED"] == "false"
    assert cron_env["BACKUP_REMOTE_ENABLED"] == "true"
    assert cron_env["BACKUP_REMOTE_REQUIRED"] == "false"


def test_offsite_required_can_be_enabled_for_stage_two():
    """Aşama 2 anahtarı belgelenmiş olmalı (operatör tek satırla açar)."""
    text = RENDER_YAML.read_text(encoding="utf-8")
    assert "Aşama 2" in text
    assert "BACKUP_REMOTE_REQUIRED=true" in text


def test_db_backup_cron_can_reach_offsite(services):
    env = services["isg-suite-db-backup-nightly"]["env"]
    assert env["BACKUP_REMOTE_ENABLED"] == "true"
    # Kimlik bilgileri `sync: false` (Render Dashboard) olarak tanımlıdır.
    text = RENDER_YAML.read_text(encoding="utf-8")
    for key in (
        "OBJECT_STORAGE_BUCKET",
        "OBJECT_STORAGE_ACCESS_KEY",
        "OBJECT_STORAGE_SECRET_KEY",
    ):
        assert f"- key: {key}" in text


def test_api_environment_is_production(services):
    assert services["isg-suite-api"]["env"]["ENVIRONMENT"] == "production"


def test_parser_handles_comments_and_blank_lines():
    parsed = _parse(
        """
services:
  - type: web
    name: demo
    envVars:
      # yorum satırı
      - key: FLAG
        value: "true"
"""
    )
    assert parsed["demo"]["env"]["FLAG"] == "true"


def test_db_backup_cron_uses_database_connection(services):
    text = RENDER_YAML.read_text(encoding="utf-8")
    assert text.count("isg-suite-db") >= 2


def test_no_duplicate_service_names(services):
    text = RENDER_YAML.read_text(encoding="utf-8")
    names = _NAME_RE.findall(text)
    assert len(names) == len(set(names))
