"""Object storage adapter (P0-06) — varsayılan local disk; S3/R2 hazır iskelet.

Mevcut endpoint'ler doğrudan Path yazmaya devam eder.
Gateway açıkken yazma bu katmandan geçer (local backend = aynı upload_dir düzeni).

S3'e geçiş: OBJECT_STORAGE_BACKEND=s3 + bucket/credential env;
boto3 yoksa net hata (sessiz fallback yok — yanlış 'başarı' yok).
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from fastapi import HTTPException

from app.core.config import settings


class ObjectStore(Protocol):
    def put_bytes(self, key: str, content: bytes) -> str: ...
    def get_bytes(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def delete(self, key: str) -> None: ...
    def resolve_local_path(self, key: str) -> Path | None:
        """Local backend için mutlak Path; uzak backend'de None."""
        ...


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


class S3ObjectStore:
    """S3-uyumlu iskelet — boto3 isteğe bağlı; production cutover sonraki PR."""

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
        self._client = boto3.client("s3", **kwargs)

    def _full_key(self, key: str) -> str:
        norm = _normalize_key(key)
        return f"{self.prefix}/{norm}" if self.prefix else norm

    def put_bytes(self, key: str, content: bytes) -> str:
        self._client.put_object(Bucket=self.bucket, Key=self._full_key(key), Body=content)
        return _normalize_key(key)

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


_store: ObjectStore | None = None


def get_object_store() -> ObjectStore:
    global _store
    if _store is not None:
        return _store
    backend = (settings.object_storage_backend or "local").strip().lower()
    if backend in ("local", "disk", "fs"):
        _store = LocalObjectStore()
    elif backend in ("s3", "r2", "minio"):
        _store = S3ObjectStore()
    else:
        raise RuntimeError(f"Bilinmeyen OBJECT_STORAGE_BACKEND: {backend}")
    return _store


def reset_object_store_for_tests() -> None:
    global _store
    _store = None


def storage_backend_label() -> str:
    backend = (settings.object_storage_backend or "local").strip().lower() or "local"
    if backend in ("s3", "r2", "minio"):
        return f"{backend}-ready-v1" if object_storage_config_ok() else f"{backend}-misconfig-v1"
    return f"{backend}-v1"


def object_storage_config_ok() -> bool:
    """S3/R2 seçildiyse bucket + credential (+ R2 için endpoint) zorunlu; local her zaman OK."""
    backend = (settings.object_storage_backend or "local").strip().lower() or "local"
    if backend in ("local", "disk", "fs"):
        return True
    if backend in ("s3", "r2", "minio"):
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
            "ok": True,
            "status": "local" if backend in ("local", "disk", "fs") else "incomplete",
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


def maybe_auto_cutover_object_storage() -> dict:
    """Production: credential + HeadBucket OK ise local → r2/s3. Store singleton sıfırlanır."""
    import logging

    log = logging.getLogger(__name__)
    env = (settings.environment or "").strip().lower()
    if env not in ("production", "prod", "live"):
        return {"status": "skipped-non-prod"}
    if bool(getattr(settings, "object_storage_force_local", False)):
        return {"status": "force-local"}
    if not bool(getattr(settings, "object_storage_auto_cutover", True)):
        return {"status": "auto-cutover-off"}

    backend = (settings.object_storage_backend or "local").strip().lower() or "local"
    if backend not in ("local", "disk", "fs"):
        return {"status": "already-remote", "backend": backend}

    if not remote_object_storage_credentials_ok():
        return {"status": "no-creds"}

    probe = probe_object_storage()
    if probe.get("status") != "reachable":
        return {"status": "unreachable", "probe": probe}

    endpoint = (settings.object_storage_endpoint or "").strip().lower()
    if "r2.cloudflarestorage.com" in endpoint or "cloudflarestorage.com" in endpoint:
        target = "r2"
    elif endpoint:
        target = "minio"
    else:
        target = "s3"

    settings.object_storage_backend = target
    reset_object_store_for_tests()
    log.info("object storage auto-cutover: local → %s", target)
    return {"status": "cutover", "backend": target, "probe": probe}


def persistent_disk_label() -> str:
    """UPLOAD_DIR /var/data altında ise Render persistent disk varsay."""
    from pathlib import Path

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
    """Canlı %100 için kalan operasyonel boşluklar (özet)."""
    gaps: list[str] = []
    label = storage_backend_label()
    if label.startswith("local"):
        gaps.append("object_storage_r2")
    if persistent_disk_label() != "mounted-v1" and label.startswith("local"):
        gaps.append("persistent_disk")
    # restore yazma bilerek kapalı — staging drill sonrası açılır
    if not bool(settings.backup_restore_enabled):
        gaps.append("backup_restore_staging_drill")
    return gaps


def infra_cutover_steps() -> list[dict]:
    """GA için net sonraki adımlar (R2 / disk / restore)."""
    remaining = set(infra_cutover_remaining())
    remote_ok = remote_object_storage_credentials_ok()
    probe = probe_object_storage() if remote_ok else {"status": "no-creds"}
    steps = [
        {
            "id": "persistent_disk",
            "status": "done" if "persistent_disk" not in remaining else "pending",
            "title": "Render persistent disk",
            "hint": "UPLOAD_DIR=/var/data/uploads ve BACKUP_DIR=/var/data/backups",
        },
        {
            "id": "object_storage_r2",
            "status": "done" if "object_storage_r2" not in remaining else "pending",
            "title": "Cloudflare R2 object storage",
            "hint": (
                "Render env: OBJECT_STORAGE_BUCKET, ACCESS_KEY, SECRET_KEY, "
                "ENDPOINT=https://<accountid>.r2.cloudflarestorage.com, REGION=auto. "
                "BACKEND=local bırak; HeadBucket OK olunca auto-cutover r2 yapar."
            ),
            "creds_present": remote_ok,
            "probe_status": probe.get("status"),
        },
        {
            "id": "backup_restore_staging_drill",
            "status": "done" if "backup_restore_staging_drill" not in remaining else "pending",
            "title": "Staging restore drill",
            "hint": (
                "python -m scripts.backup_restore_drill --out evidence.json; "
                "prod'da BACKUP_RESTORE_ENABLED açma."
            ),
        },
    ]
    return steps
