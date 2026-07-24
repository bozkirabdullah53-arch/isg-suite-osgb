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
    parts = [p for p in raw.split("/") if p and p != ".."]
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
        except Exception as exc:  # noqa: BLE001 — boto ClientError çeşitleri
            raise HTTPException(status_code=404, detail="Dosya bulunamadı.") from exc
        return obj["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=self._full_key(key))
            return True
        except Exception:  # noqa: BLE001
            return False

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
    return f"{backend}-v1"
