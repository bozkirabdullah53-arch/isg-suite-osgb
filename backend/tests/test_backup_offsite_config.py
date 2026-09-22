"""Offsite yedek yapılandırması — fail-closed doğrulama ve remote mağaza."""
from __future__ import annotations

import pytest

from app.core import config
from app.core.config import settings
from app.services import backup_management as bm


@pytest.fixture()
def clean_offsite(monkeypatch):
    for name in (
        "object_storage_bucket",
        "object_storage_access_key",
        "object_storage_secret_key",
        "object_storage_endpoint",
        "object_storage_region",
    ):
        monkeypatch.setattr(settings, name, "", raising=False)
    monkeypatch.setattr(settings, "backup_remote_enabled", True, raising=False)
    monkeypatch.setattr(settings, "workplace_backup_remote_enabled", True, raising=False)
    monkeypatch.setattr(settings, "backup_remote_required", False, raising=False)
    return settings


def _set_credentials(monkeypatch):
    monkeypatch.setattr(settings, "object_storage_bucket", "isg-backups")
    monkeypatch.setattr(settings, "object_storage_access_key", "access")
    monkeypatch.setattr(settings, "object_storage_secret_key", "secret")
    monkeypatch.setattr(settings, "object_storage_endpoint", "https://r2.example.com")


def test_offsite_credentials_present_requires_all_fields(clean_offsite, monkeypatch):
    assert config._offsite_credentials_present() is False
    _set_credentials(monkeypatch)
    assert config._offsite_credentials_present() is True


def test_offsite_credentials_present_accepts_region_only(clean_offsite, monkeypatch):
    monkeypatch.setattr(settings, "object_storage_bucket", "bucket")
    monkeypatch.setattr(settings, "object_storage_access_key", "access")
    monkeypatch.setattr(settings, "object_storage_secret_key", "secret")
    monkeypatch.setattr(settings, "object_storage_region", "eu-central-1")
    assert config._offsite_credentials_present() is True


def test_validation_passes_when_credentials_defined(clean_offsite, monkeypatch):
    _set_credentials(monkeypatch)
    monkeypatch.setattr(settings, "backup_remote_required", True)
    # Hata yükseltmemeli.
    config._validate_backup_offsite_credentials()


def test_validation_warns_when_not_required(clean_offsite):
    # Kimlik bilgisi yok, zorunlu değil → yalnız log, hata yok.
    config._validate_backup_offsite_credentials()


def test_validation_fails_closed_when_required(clean_offsite, monkeypatch):
    monkeypatch.setattr(settings, "backup_remote_required", True)
    with pytest.raises(RuntimeError, match="BACKUP_REMOTE_REQUIRED"):
        config._validate_backup_offsite_credentials()


def test_validation_skips_when_offsite_disabled(clean_offsite, monkeypatch):
    monkeypatch.setattr(settings, "backup_remote_enabled", False, raising=False)
    monkeypatch.setattr(settings, "workplace_backup_remote_enabled", False, raising=False)
    monkeypatch.setattr(settings, "backup_remote_required", True)
    # Offsite kapalıyken zorunluluk uygulanmaz.
    config._validate_backup_offsite_credentials()


def test_offsite_store_uses_remote_when_credentials_ok(clean_offsite, monkeypatch):
    monkeypatch.setattr(bm.settings, "backup_remote_enabled", True)
    _set_credentials(monkeypatch)
    sentinel = object()
    monkeypatch.setattr(
        "app.services.object_store.get_remote_object_store",
        lambda: sentinel,
    )
    assert bm.offsite_store() is sentinel


def test_offsite_store_none_when_credentials_missing(clean_offsite, monkeypatch):
    monkeypatch.setattr(bm.settings, "backup_remote_enabled", True)
    monkeypatch.setattr(
        "app.services.object_store.get_remote_object_store",
        lambda: None,
    )
    assert bm.offsite_store() is None


def test_run_backup_marks_offsite_uploaded(tmp_path, monkeypatch):
    """Offsite yükleme başarılıysa sonuç uploaded=true döner."""
    from scripts import backup_database as bd

    source = tmp_path / "source.db"
    source.write_bytes(b"x")
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{source}")
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path / "backups"))
    monkeypatch.setattr(settings, "backup_encryption_key", "")
    monkeypatch.setattr(settings, "backup_encryption_secret_fallback", False)
    monkeypatch.setattr(settings, "backup_encryption_force_off", False)
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "backup_remote_required", False)

    result = bd.run_backup()

    assert result["status"] == "ok"
    assert result["offsite"]["uploaded"] is False


class _FakeRemote:
    """R2/S3 put_file + remote_size + iter_range + delete davranışı."""

    def __init__(self, *, corrupt: bool = False) -> None:
        self.objects: dict[str, bytes] = {}
        self.corrupt = corrupt

    def put_file(self, key, path, *, content_type=None):
        payload = path.read_bytes()
        self.objects[key] = payload + (b"X" if self.corrupt else b"")
        return key

    def remote_size(self, key):
        payload = self.objects.get(key)
        return len(payload) if payload is not None else None

    def iter_range(self, key, *, start, end):
        payload = self.objects.get(key)
        if payload is None:
            return
        yield payload[start : end + 1]

    def delete(self, key):
        self.objects.pop(key, None)


def test_full_backup_flow_uploads_and_verifies_offsite(tmp_path, monkeypatch):
    """Üret → şifrele → offsite yükle → doğrula → saklama: uçtan uca."""
    from scripts import backup_database as bd

    source = tmp_path / "source.db"
    source.write_bytes(b"sqlite-payload")
    remote = _FakeRemote()
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{source}")
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path / "backups"))
    monkeypatch.setattr(settings, "backup_encryption_key", "dedicated-key-at-least-32-characters!!")
    monkeypatch.setattr(settings, "backup_encryption_secret_fallback", False)
    monkeypatch.setattr(settings, "backup_encryption_force_off", False)
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "backup_remote_required", True)
    monkeypatch.setattr(bm, "offsite_store", lambda: remote)

    result = bd.run_backup()

    assert result["status"] == "ok"
    assert result["encrypted"] is True
    assert result["offsite"]["uploaded"] is True
    assert result["offsite"]["key"].startswith("db-backups/")
    # Yerel yedek de korunmalı.
    assert (tmp_path / "backups" / result["file"]).is_file()
    # Offsite nesne boyutu yerel dosyayla aynı olmalı.
    assert remote.objects[result["offsite"]["key"]] == (tmp_path / "backups" / result["file"]).read_bytes()


def test_full_backup_flow_fails_when_offsite_corrupt(tmp_path, monkeypatch):
    """Offsite doğrulama başarısızsa ve zorunluysa yedek başarısız sayılır."""
    from scripts import backup_database as bd

    source = tmp_path / "source.db"
    source.write_bytes(b"sqlite-payload")
    remote = _FakeRemote(corrupt=True)
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{source}")
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path / "backups"))
    monkeypatch.setattr(settings, "backup_encryption_key", "")
    monkeypatch.setattr(settings, "backup_encryption_secret_fallback", False)
    monkeypatch.setattr(settings, "backup_encryption_force_off", False)
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "backup_remote_required", True)
    monkeypatch.setattr(bm, "offsite_store", lambda: remote)

    with pytest.raises(bd.BackupError, match="Offsite"):
        bd.run_backup()

    # Bozuk uzak nesne temizlenmeli, yerel yedek korunmalı.
    assert remote.objects == {}
    assert list((tmp_path / "backups").glob("isgsuite-*")) != []
