"""Object storage adapter — local, güvenli dual ve doğrudan S3/R2 modları.

Mevcut endpoint'ler doğrudan Path yazmaya devam eder.
Gateway açıkken yazma bu katmandan geçer (local backend = aynı upload_dir düzeni).

Üretimde önerilen geçiş: OBJECT_STORAGE_BACKEND=dual + bucket/credential env.
Dual mod yerel kopyayı korur, uzak kopyayı boyutuyla doğrular.
OBJECT_STORAGE_REMOTE_REQUIRED=true ise uzak doğrulama başarısız yazma kabul edilmez.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

from fastapi import HTTPException

from app.core.config import settings


logger = logging.getLogger(__name__)


def remote_mirror_required() -> bool:
    return bool(getattr(settings, "object_storage_remote_required", False))


class ObjectStore(Protocol):
    def put_bytes(self, key: str, content: bytes) -> str: ...
    def get_bytes(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def delete(self, key: str) -> None: ...
    def resolve_local_path(self, key: str) -> Path | None:
        """Local backend için mutlak Path; uzak backend'de None."""
        ...
    def presigned_get_url(self, key: str, *, expires_in_seconds: int) -> str | None: ...


def _normalize_key(key: str) -> str:
    raw = (key or "").replace("\\", "/").strip("/")
    parts: list[str] = []
    for part in raw.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            raise HTTPException(status_code=400, detail="Geçersiz depolama anahtarı.")
        parts.append(part)
    if not parts:
        raise HTTPException(status_code=400, detail="Geçersiz depolama anahtarı.")
    return "/".join(parts)


class LocalObjectStore:
    """Disk tabanlı depolama — mevcut upload_dir ile uyumlu."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or Path(settings.upload_dir)).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        norm = _normalize_key(key)
        target = (self.root / norm).resolve()
        if self.root not in target.parents and target != self.root:
            raise HTTPException(status_code=400, detail="Geçersiz depolama yolu.")
        return target

    def put_bytes(self, key: str, content: bytes) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return _normalize_key(key)

    def get_bytes(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Dosya bulunamadı.")
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.is_file():
            path.unlink()

    def resolve_local_path(self, key: str) -> Path | None:
        return self._path(key)

    def presigned_get_url(self, key: str, *, expires_in_seconds: int) -> str | None:
        return None


class S3ObjectStore:
    """S3 uyumlu R2/S3 istemcisi; her yazmayı HeadObject ile doğrular."""

    def __init__(self) -> None:
        try:
            import boto3  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "OBJECT_STORAGE_BACKEND=s3 için boto3 gerekir; "
                "şimdilik local kullanın veya boto3 ekleyin."
            ) from exc
        bucket = (settings.object_storage_bucket or "").strip()
        if not bucket:
            raise RuntimeError("OBJECT_STORAGE_BUCKET zorunlu (s3 backend).")
        self.bucket = bucket
        self.prefix = (settings.object_storage_prefix or "").strip().strip("/")
        kwargs: dict = {}
        if settings.object_storage_endpoint:
            kwargs["endpoint_url"] = settings.object_storage_endpoint
        if settings.object_storage_access_key and settings.object_storage_secret_key:
            kwargs["aws_access_key_id"] = settings.object_storage_access_key
            kwargs["aws_secret_access_key"] = settings.object_storage_secret_key
        if settings.object_storage_region:
            kwargs["region_name"] = settings.object_storage_region
        elif (
            settings.object_storage_endpoint
            and ".r2.cloudflarestorage.com" in settings.object_storage_endpoint
        ):
            # Cloudflare R2 is S3-compatible but does not expose an AWS
            # region. boto3 still requires one; Cloudflare documents "auto"
            # as the correct placeholder.
            kwargs["region_name"] = "auto"
        self._client = boto3.client("s3", **kwargs)

    def _full_key(self, key: str) -> str:
        norm = _normalize_key(key)
        return f"{self.prefix}/{norm}" if self.prefix else norm

    def put_bytes(self, key: str, content: bytes) -> str:
        normalized = _normalize_key(key)
        full_key = self._full_key(normalized)
        self._client.put_object(Bucket=self.bucket, Key=full_key, Body=content)
        metadata = self._client.head_object(Bucket=self.bucket, Key=full_key)
        remote_size = int(metadata.get("ContentLength", -1))
        if remote_size != len(content):
            try:
                self._client.delete_object(Bucket=self.bucket, Key=full_key)
            except Exception:
                logger.exception("Boyutu doğrulanamayan uzak nesne temizlenemedi: %s", full_key)
            raise RuntimeError(
                f"Uzak depolama boyut doğrulaması başarısız: beklenen={len(content)}, gelen={remote_size}"
            )
        return normalized

    def remote_size(self, key: str) -> int | None:
        """Return the remote object size without falling back to the local disk."""
        try:
            metadata = self._client.head_object(
                Bucket=self.bucket,
                Key=self._full_key(key),
            )
        except Exception as exc:
            response = getattr(exc, "response", {}) or {}
            error = response.get("Error", {}) if isinstance(response, dict) else {}
            code = str(error.get("Code") or "").strip().lower()
            status = (
                (response.get("ResponseMetadata", {}) or {}).get("HTTPStatusCode")
                if isinstance(response, dict)
                else None
            )
            if code in {"404", "nosuchkey", "notfound"} or status == 404:
                return None
            raise
        return int(metadata.get("ContentLength", -1))

    def put_file(
        self,
        key: str,
        path: Path,
        *,
        content_type: str | None = None,
    ) -> str:
        """Stream a local file with boto3's managed multipart uploader and verify size."""
        normalized = _normalize_key(key)
        source = Path(path)
        if not source.is_file():
            raise FileNotFoundError(str(source))
        expected_size = int(source.stat().st_size)
        full_key = self._full_key(normalized)
        upload_kwargs: dict = {}
        normalized_content_type = (content_type or "").strip()
        if normalized_content_type:
            upload_kwargs["ExtraArgs"] = {"ContentType": normalized_content_type[:120]}
        self._client.upload_file(
            str(source),
            self.bucket,
            full_key,
            **upload_kwargs,
        )
        remote_size = self.remote_size(normalized)
        if remote_size != expected_size:
            try:
                self._client.delete_object(Bucket=self.bucket, Key=full_key)
            except Exception:
                logger.exception("Boyutu doğrulanamayan uzak nesne temizlenemedi: %s", full_key)
            raise RuntimeError(
                f"Uzak depolama boyut doğrulaması başarısız: beklenen={expected_size}, gelen={remote_size}"
            )
        return normalized

    def get_range(self, key: str, *, start: int, end: int) -> bytes:
        """Read a byte range directly from R2/S3 for migration verification."""
        first = max(0, int(start))
        last = max(first, int(end))
        obj = self._client.get_object(
            Bucket=self.bucket,
            Key=self._full_key(key),
            Range=f"bytes={first}-{last}",
        )
        return bytes(obj["Body"].read())

    def get_bytes(self, key: str) -> bytes:
        try:
            obj = self._client.get_object(Bucket=self.bucket, Key=self._full_key(key))
        except Exception:
            # Cutover: S3'te yoksa eski local upload_dir
            legacy = LocalObjectStore().resolve_local_path(key)
            if legacy is not None and legacy.is_file():
                return legacy.read_bytes()
            raise HTTPException(status_code=404, detail="Dosya bulunamadı.")
        return obj["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=self._full_key(key))
            return True
        except Exception:
            legacy = LocalObjectStore().resolve_local_path(key)
            return bool(legacy is not None and legacy.is_file())

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self.bucket, Key=self._full_key(key))

    def resolve_local_path(self, key: str) -> Path | None:
        return None

    def presigned_get_url(self, key: str, *, expires_in_seconds: int) -> str | None:
        """Create a short-lived direct read URL only when the remote object exists."""
        full_key = self._full_key(key)
        self._client.head_object(Bucket=self.bucket, Key=full_key)
        ttl = max(60, min(int(expires_in_seconds or 3600), 7200))
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": full_key},
            ExpiresIn=ttl,
        )


class DualObjectStore:
    """Yerel diski ana kopya tutar, her yazmayı doğrulanmış biçimde R2/S3'e yansıtır.

    Varsayılan rollout modunda uzak servis geçici olarak erişilemezse yerel kopya
    korunur. OBJECT_STORAGE_REMOTE_REQUIRED=true olduğunda ise yazma atomik olarak
    başarısız sayılır ve yerel değişiklik eski durumuna geri döndürülür.
    """

    def __init__(
        self,
        local: LocalObjectStore | None = None,
        remote: S3ObjectStore | None = None,
    ) -> None:
        self.local = local or LocalObjectStore()
        self.remote = remote or S3ObjectStore()

    def put_bytes(self, key: str, content: bytes) -> str:
        normalized = _normalize_key(key)
        had_previous = self.local.exists(normalized)
        previous = self.local.get_bytes(normalized) if had_previous else None
        normalized = self.local.put_bytes(normalized, content)
        try:
            self.remote.put_bytes(normalized, content)
        except Exception as exc:
            if remote_mirror_required():
                try:
                    if had_previous and previous is not None:
                        self.local.put_bytes(normalized, previous)
                    else:
                        self.local.delete(normalized)
                except Exception:
                    logger.exception(
                        "Uzak aynalama hatası sonrası yerel rollback başarısız: key=%s",
                        normalized,
                    )
                raise RuntimeError(
                    "Uzak depolama aynalaması zorunlu; dosya kabul edilmedi."
                ) from exc
            logger.warning(
                "Uzak depolama aynalama başarısız; yerel kopya korundu: key=%s error=%s",
                normalized,
                type(exc).__name__,
            )
        return normalized

    def get_bytes(self, key: str) -> bytes:
        if self.local.exists(key):
            return self.local.get_bytes(key)
        return self.remote.get_bytes(key)

    def exists(self, key: str) -> bool:
        return self.local.exists(key) or self.remote.exists(key)

    def delete(self, key: str) -> None:
        if remote_mirror_required():
            # Uzak silme başarısızsa yerel kopyayı koru; kısmi silme kabul edilmez.
            self.remote.delete(key)
            self.local.delete(key)
            return
        self.local.delete(key)
        try:
            self.remote.delete(key)
        except Exception as exc:
            logger.warning(
                "Uzak depolama silme işlemi ertelendi: key=%s error=%s",
                _normalize_key(key),
                type(exc).__name__,
            )

    def resolve_local_path(self, key: str) -> Path | None:
        return self.local.resolve_local_path(key)

    def presigned_get_url(self, key: str, *, expires_in_seconds: int) -> str | None:
        return self.remote.presigned_get_url(
            key,
            expires_in_seconds=expires_in_seconds,
        )


_store: ObjectStore | None = None
_remote_store: S3ObjectStore | None = None


def get_object_store() -> ObjectStore:
    global _store
    if _store is not None:
        return _store
    backend = (settings.object_storage_backend or "local").strip().lower()
    if backend in ("local", "disk", "fs"):
        _store = LocalObjectStore()
    elif backend == "dual":
        _store = DualObjectStore()
    elif backend in ("s3", "r2", "minio"):
        _store = S3ObjectStore()
    else:
        raise RuntimeError(f"Bilinmeyen OBJECT_STORAGE_BACKEND: {backend}")
    return _store


def get_remote_object_store() -> S3ObjectStore | None:
    """Return a remote-first store when R2/S3 credentials are configured.

    This is deliberately separate from ``get_object_store``. Existing
    application uploads may still use the local/dual compatibility path, but
    large remote-training videos must not consume the small Render disk before
    they reach R2. ``OBJECT_STORAGE_FORCE_LOCAL`` remains an emergency
    rollback switch and disables this path.
    """
    global _remote_store
    if bool(getattr(settings, "object_storage_force_local", False)):
        return None
    if not remote_object_storage_credentials_ok():
        return None
    if _remote_store is None:
        _remote_store = S3ObjectStore()
    return _remote_store


def get_remote_video_store() -> ObjectStore:
    """Use R2/S3 for remote-training videos, with the old store as fallback."""
    return get_remote_object_store() or get_object_store()


def presigned_object_read_url(key: str, *, expires_in_seconds: int) -> str | None:
    """Best-effort direct R2/S3 delivery; callers retain their local fallback."""
    try:
        return get_remote_video_store().presigned_get_url(
            key,
            expires_in_seconds=expires_in_seconds,
        )
    except Exception as exc:
        logger.warning(
            "Doğrudan nesne oynatma kullanılamadı; yerel akış korunuyor: %s",
            type(exc).__name__,
        )
        return None


def reset_object_store_for_tests() -> None:
    global _remote_store, _store
    _store = None
    _remote_store = None


def storage_backend_label() -> str:
    backend = (settings.object_storage_backend or "local").strip().lower() or "local"
    suffix = "-required" if remote_mirror_required() else ""
    if backend in ("dual", "s3", "r2", "minio"):
        state = "ready-v2" if object_storage_config_ok() else "misconfig-v2"
        return f"{backend}{suffix}-{state}"
    return f"{backend}{suffix}-v2"


def object_storage_config_ok() -> bool:
    """S3/R2 seçildiyse bucket + credential (+ R2 için endpoint) zorunlu; local her zaman OK."""
    backend = (settings.object_storage_backend or "local").strip().lower() or "local"
    if backend in ("local", "disk", "fs"):
        return not remote_mirror_required()
    if backend in ("dual", "s3", "r2", "minio"):
        return remote_object_storage_credentials_ok(backend_hint=backend)
    return False


def remote_object_storage_credentials_ok(backend_hint: str | None = None) -> bool:
    """Aktif backend local olsa bile R2/S3 env dolu mu? (cutover öncesi probe)."""
    bucket = (settings.object_storage_bucket or "").strip()
    key = (settings.object_storage_access_key or "").strip()
    secret = (settings.object_storage_secret_key or "").strip()
    endpoint = (settings.object_storage_endpoint or "").strip()
    region = (settings.object_storage_region or "").strip()
    if not (bucket and key and secret):
        return False
    hint = (backend_hint or settings.object_storage_backend or "s3").strip().lower()
    if hint in ("r2", "minio"):
        return bool(endpoint)
    # AWS veya henüz backend=local iken doldurulmuş credential: endpoint veya region
    return bool(region or endpoint)


def probe_object_storage() -> dict:
    """Salt okunur depolama ön kontrolü — put/delete yok; aktif store'u değiştirmez.

    - Credential yok / local → status=local (skipped)
    - Credential var → HeadBucket (backend hâlâ local olabilir)
    """
    import time

    backend = (settings.object_storage_backend or "local").strip().lower() or "local"
    if not remote_object_storage_credentials_ok(
        backend_hint=backend if backend in ("s3", "r2", "minio") else None
    ):
        return {
            "ok": not remote_mirror_required(),
            "status": "required-missing" if remote_mirror_required() else (
                "local" if backend in ("local", "disk", "fs") else "incomplete"
            ),
            "remote": "skipped",
            "active_backend": backend,
        }

    bucket = (settings.object_storage_bucket or "").strip()
    try:
        import boto3  # type: ignore
        from botocore.config import Config  # type: ignore
    except ImportError:
        return {
            "ok": False,
            "status": "missing_boto3",
            "remote": "skipped",
            "active_backend": backend,
        }

    kwargs: dict = {
        "aws_access_key_id": (settings.object_storage_access_key or "").strip(),
        "aws_secret_access_key": (settings.object_storage_secret_key or "").strip(),
        "config": Config(
            connect_timeout=2,
            read_timeout=2,
            retries={"max_attempts": 1},
        ),
    }
    if settings.object_storage_endpoint:
        kwargs["endpoint_url"] = settings.object_storage_endpoint
    if settings.object_storage_region:
        kwargs["region_name"] = settings.object_storage_region
    elif (
        settings.object_storage_endpoint
        and ".r2.cloudflarestorage.com" in settings.object_storage_endpoint
    ):
        kwargs["region_name"] = "auto"

    started = time.monotonic()
    try:
        client = boto3.client("s3", **kwargs)
        client.head_bucket(Bucket=bucket)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return {
            "ok": True,
            "status": "reachable",
            "remote": "probed",
            "elapsed_ms": elapsed_ms,
            "active_backend": backend,
        }
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return {
            "ok": False,
            "status": "unreachable",
            "remote": "probed",
            "elapsed_ms": elapsed_ms,
            "active_backend": backend,
            "error_class": type(exc).__name__,
        }


def object_storage_durability_readiness(*, probe: bool = False) -> dict:
    """Secret-free durability state for release gates and admin diagnostics."""
    backend = (settings.object_storage_backend or "local").strip().lower() or "local"
    credentials = remote_object_storage_credentials_ok(
        backend_hint=backend if backend in ("s3", "r2", "minio") else None
    )
    probe_result = (
        probe_object_storage()
        if probe and credentials
        else {"status": "configured-unprobed" if credentials else "not-configured"}
    )
    remote_active = backend in ("dual", "s3", "r2", "minio")
    remote_ready = credentials and probe_result.get("status") in {
        "configured-unprobed",
        "reachable",
    }
    required = remote_mirror_required()
    return {
        "required": required,
        "active_backend": backend,
        "credentials_configured": credentials,
        "probe_status": probe_result.get("status"),
        "persistent_disk": persistent_disk_label(),
        "remote_active": remote_active,
        "remote_ready": remote_ready,
        "write_policy": "remote-required" if required else "local-fallback-allowed",
        "ready": (
            remote_active and remote_ready
            if required
            else (persistent_disk_label() == "mounted-v1" or remote_ready)
        ),
    }


def maybe_auto_cutover_object_storage() -> dict:
    """Production: credential + HeadBucket OK ise local → güvenli dual yazma."""
    env = (settings.environment or "").strip().lower()
    if env not in ("production", "prod", "live"):
        return {"status": "skipped-non-prod"}

    required = remote_mirror_required()
    if bool(getattr(settings, "object_storage_force_local", False)):
        if required:
            raise RuntimeError(
                "Uzak object storage zorunluyken force-local kullanılamaz."
            )
        return {"status": "force-local"}
    if not bool(getattr(settings, "object_storage_auto_cutover", True)):
        backend = (settings.object_storage_backend or "local").strip().lower() or "local"
        if required and backend in ("local", "disk", "fs"):
            raise RuntimeError(
                "Uzak object storage zorunlu fakat auto-cutover kapalı ve backend local."
            )
        return {"status": "auto-cutover-off"}

    backend = (settings.object_storage_backend or "local").strip().lower() or "local"
    if backend not in ("local", "disk", "fs"):
        if required:
            probe = probe_object_storage()
            if probe.get("status") != "reachable":
                raise RuntimeError("Zorunlu uzak object storage erişilemiyor.")
            return {"status": "remote-required-ready", "backend": backend, "probe": probe}
        return {"status": "already-remote", "backend": backend}

    if not remote_object_storage_credentials_ok():
        if required:
            raise RuntimeError("Zorunlu uzak object storage credential eksik.")
        return {"status": "no-creds"}

    probe = probe_object_storage()
    if probe.get("status") != "reachable":
        if required:
            raise RuntimeError("Zorunlu uzak object storage probe başarısız.")
        return {"status": "unreachable", "probe": probe}

    target = "dual"
    settings.object_storage_backend = target
    reset_object_store_for_tests()
    logger.info("object storage auto-cutover: local → %s", target)
    return {
        "status": "cutover-required" if required else "cutover",
        "backend": target,
        "probe": probe,
    }


def verify_object_storage_write() -> dict:
    """R2/S3 üzerinde yaz-oku-sil doğrulaması; kalıcı test nesnesi bırakmaz."""
    import secrets
    import time

    if not remote_object_storage_credentials_ok():
        return {"ok": False, "status": "incomplete"}

    payload = secrets.token_bytes(64)
    key = f"_system/probes/{secrets.token_hex(12)}.bin"
    started = time.monotonic()
    remote = S3ObjectStore()
    try:
        remote.put_bytes(key, payload)
        downloaded = remote.get_bytes(key)
        if downloaded != payload:
            raise RuntimeError("Uzak depolama içerik doğrulaması başarısız.")
        return {
            "ok": True,
            "status": "write-verified",
            "verified_bytes": len(payload),
            "elapsed_ms": int((time.monotonic() - started) * 1000),
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": "write-failed",
            "error_class": type(exc).__name__,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
        }
    finally:
        try:
            remote.delete(key)
        except Exception:
            logger.warning("R2 doğrulama nesnesi temizlenemedi: %s", key)


def persistent_disk_label() -> str:
    """UPLOAD_DIR /var/data altında ise Render persistent disk varsay."""
    candidates = [(settings.upload_dir or "").replace("\\", "/").strip()]
    try:
        candidates.append(str(Path(settings.upload_dir).resolve()).replace("\\", "/"))
    except OSError:
        pass
    for raw in candidates:
        if not raw:
            continue
        # Windows resolve: C:/var/data/... → /var/data/...
        norm = raw[2:] if len(raw) >= 2 and raw[1] == ":" else raw
        if not norm.startswith("/"):
            norm = "/" + norm.lstrip("/")
        if norm.startswith("/var/data"):
            return "mounted-v1"
    return "ephemeral-v1"


def infra_cutover_remaining() -> list[str]:
    """Bloklayan depolama boşlukları."""
    readiness = object_storage_durability_readiness(probe=False)
    if readiness["ready"]:
        return []
    return ["remote_object_storage"] if remote_mirror_required() else ["durable_storage"]


def infra_cutover_optional() -> list[str]:
    """İsteğe bağlı iyileştirmeler (zorunlu uzak ayna açıksa artık opsiyonel değildir)."""
    opts: list[str] = []
    if not remote_mirror_required() and storage_backend_label().startswith("local"):
        opts.append("object_storage_r2_multi_instance")
    if not bool(settings.backup_restore_enabled):
        opts.append("backup_restore_writes_off_by_design")
    return opts


def hardening_complete_label() -> str:
    """Boş remaining ⇒ complete-v2."""
    return "complete-v2" if not infra_cutover_remaining() else "in-progress"


def infra_cutover_steps() -> list[dict]:
    """GA için depolama adımları; uzak zorunluluk açıldığında blocking olur."""
    disk_ok = persistent_disk_label() == "mounted-v1"
    remote_ok = remote_object_storage_credentials_ok()
    probe = probe_object_storage() if remote_ok else {"status": "no-creds"}
    remote_live = (
        (not storage_backend_label().startswith("local"))
        and probe.get("status") == "reachable"
    ) or (
        storage_backend_label().startswith("local")
        and probe.get("status") == "reachable"
    )
    required = remote_mirror_required()
    return [
        {
            "id": "persistent_disk",
            "status": "done" if disk_ok else ("optional" if remote_live else "pending"),
            "title": "Render persistent disk",
            "hint": "UPLOAD_DIR=/var/data/uploads ve BACKUP_DIR=/var/data/backups",
            "blocking": not remote_live,
        },
        {
            "id": "object_storage_r2",
            "status": "done" if remote_live else ("pending" if required or not disk_ok else "optional"),
            "title": "Cloudflare R2 / S3 uzak ayna",
            "hint": (
                "OBJECT_STORAGE_* + HeadBucket + yaz/oku/sil doğrulaması. "
                "OBJECT_STORAGE_REMOTE_REQUIRED=true olduğunda mirror hatası fail-closed olur."
            ),
            "creds_present": remote_ok,
            "probe_status": probe.get("status"),
            "blocking": required,
        },
        {
            "id": "backup_restore_staging_drill",
            "status": "pending",
            "title": "Gerçek staging backup/restore dry-run tatbikatı",
            "hint": "Tenant yedeği üret, checksum doğrula ve restore dry-run kanıtı kaydet.",
            "blocking": True,
        },
    ]
