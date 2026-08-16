"""Copy legacy remote-training videos from the persistent disk to R2/S3.

The operation is intentionally additive and idempotent:

* local files and database rows are never changed or deleted;
* matching remote objects are skipped;
* conflicting remote objects are reported, never overwritten;
* files are streamed with boto3's managed multipart uploader;
* a read/write/delete probe runs before the first real video is touched;
* the first usable video is range-read from R2 as a pilot gate.
"""
from __future__ import annotations

import json
import logging
import threading
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.remote_training import RemoteTrainingCatalogVideo, RemoteTrainingVideo
from app.services.job_queue import JobRecord, enqueue
from app.services.object_store import (
    LocalObjectStore,
    S3ObjectStore,
    probe_object_storage,
    verify_object_storage_write,
)


logger = logging.getLogger(__name__)
_BACKFILL_LOCK = threading.Lock()
_JOB_NAME = "remote_training_video_r2_backfill"
_SAMPLE_BYTES = 64


def _inventory(db: Session) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for source, model in (
        ("company", RemoteTrainingVideo),
        ("catalog", RemoteTrainingCatalogVideo),
    ):
        rows = db.execute(
            select(
                model.id,
                model.storage_key,
                model.file_size_bytes,
                model.content_type,
            ).order_by(model.id)
        ).all()
        for row in rows:
            inventory.append(
                {
                    "source": source,
                    "id": int(row.id),
                    "storage_key": str(row.storage_key or ""),
                    "declared_size": int(row.file_size_bytes or 0),
                    "content_type": str(row.content_type or "application/octet-stream"),
                }
            )

    # Storage keys are unique per table, but de-duplicate defensively across both
    # tables so a historical data anomaly can never upload the same object twice.
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in inventory:
        key = item["storage_key"]
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _local_range(path: Path, *, start: int, end: int) -> bytes:
    length = max(0, int(end) - int(start) + 1)
    with path.open("rb") as handle:
        handle.seek(max(0, int(start)))
        return handle.read(length)


def _verify_remote_sample(remote: S3ObjectStore, key: str, path: Path) -> None:
    size = int(path.stat().st_size)
    if size <= 0:
        raise RuntimeError("Boş video nesnesi pilot doğrulamayı geçemedi.")
    windows = [(0, min(size - 1, _SAMPLE_BYTES - 1))]
    if size > _SAMPLE_BYTES:
        windows.append((max(0, size - _SAMPLE_BYTES), size - 1))
    for start, end in windows:
        local_bytes = _local_range(path, start=start, end=end)
        remote_bytes = remote.get_range(key, start=start, end=end)
        if remote_bytes != local_bytes:
            raise RuntimeError("R2 video örnek içerik doğrulaması başarısız.")


def copy_video_inventory_to_remote(
    inventory: Iterable[dict[str, Any]],
    *,
    local: LocalObjectStore,
    remote: S3ObjectStore,
    max_objects: int = 0,
) -> dict[str, Any]:
    """Copy inventory entries without changing local files or database state."""
    items = list(inventory)
    selected = items[: max(0, int(max_objects))] if int(max_objects or 0) > 0 else items
    counters: Counter[str] = Counter()
    error_classes: Counter[str] = Counter()
    copied_bytes = 0
    pilot_verified = False
    pilot_key: str | None = None

    for index, item in enumerate(selected, start=1):
        counters["processed"] += 1
        key = str(item.get("storage_key") or "")
        declared_size = int(item.get("declared_size") or 0)
        content_type = str(item.get("content_type") or "application/octet-stream")
        try:
            path = local.resolve_local_path(key)
        except Exception as exc:
            counters["invalid_key"] += 1
            error_classes[type(exc).__name__] += 1
            continue
        if path is None or not path.is_file():
            try:
                remote_size = remote.remote_size(key)
            except Exception as exc:
                counters["failed"] += 1
                error_classes[type(exc).__name__] += 1
                continue
            if remote_size is not None and (declared_size <= 0 or remote_size == declared_size):
                counters["remote_only"] += 1
            else:
                counters["missing_local"] += 1
            continue

        actual_size = int(path.stat().st_size)
        counters["local_bytes"] += actual_size
        try:
            remote_size = remote.remote_size(key)
            newly_copied = False
            if remote_size is None:
                remote.put_file(key, path, content_type=content_type)
                newly_copied = True
                counters["copied"] += 1
                copied_bytes += actual_size
            elif remote_size == actual_size:
                counters["already_remote"] += 1
            else:
                # Never replace an existing object automatically. A mismatched
                # object needs explicit operator review before any overwrite.
                counters["conflict"] += 1
                continue

            if not pilot_verified:
                try:
                    _verify_remote_sample(remote, key, path)
                    if not remote.presigned_get_url(key, expires_in_seconds=300):
                        raise RuntimeError("R2 geçici okuma bağlantısı üretilemedi.")
                except Exception:
                    if newly_copied:
                        try:
                            remote.delete(key)
                        except Exception:
                            logger.exception("Başarısız pilot nesnesi temizlenemedi.")
                    raise
                pilot_verified = True
                pilot_key = key
        except Exception as exc:
            counters["failed"] += 1
            error_classes[type(exc).__name__] += 1
            if not pilot_verified:
                raise RuntimeError(
                    f"İlk R2 video pilotu başarısız oldu ({type(exc).__name__}); toplu kopya durduruldu."
                ) from exc

        if index % 10 == 0 or index == len(selected):
            logger.info(
                "R2 video backfill progress: processed=%s total=%s copied=%s already=%s",
                index,
                len(selected),
                counters["copied"],
                counters["already_remote"],
            )

    blocking_issues = sum(
        counters[name]
        for name in ("invalid_key", "missing_local", "conflict", "failed")
    )
    result = {
        "status": "completed" if blocking_issues == 0 and pilot_verified else "completed_with_issues",
        "total_inventory": len(items),
        "selected": len(selected),
        "processed": counters["processed"],
        "copied": counters["copied"],
        "copied_bytes": copied_bytes,
        "already_remote": counters["already_remote"],
        "remote_only": counters["remote_only"],
        "missing_local": counters["missing_local"],
        "conflict": counters["conflict"],
        "invalid_key": counters["invalid_key"],
        "failed": counters["failed"],
        "pilot_range_read_verified": pilot_verified,
        "presigned_read_verified": pilot_key is not None,
        "local_files_deleted": 0,
        "database_rows_changed": 0,
        "error_classes": dict(sorted(error_classes.items())),
    }
    return result


def run_remote_training_video_r2_backfill(*, max_objects: int = 0) -> dict[str, Any]:
    """Worker-safe, secret-free orchestration entry point."""
    if not _BACKFILL_LOCK.acquire(blocking=False):
        raise RuntimeError("R2 video kopyalama işi zaten çalışıyor.")
    try:
        probe = probe_object_storage()
        if probe.get("status") != "reachable":
            raise RuntimeError(
                f"R2 bağlantısı hazır değil (durum={probe.get('status') or 'unknown'})."
            )
        write_probe = verify_object_storage_write()
        if write_probe.get("status") != "write-verified":
            raise RuntimeError(
                f"R2 yaz/oku/sil doğrulaması başarısız (durum={write_probe.get('status') or 'unknown'})."
            )

        with SessionLocal() as db:
            inventory = _inventory(db)
        if not inventory:
            return {
                "status": "nothing_to_copy",
                "total_inventory": 0,
                "local_files_deleted": 0,
                "database_rows_changed": 0,
            }

        result = copy_video_inventory_to_remote(
            inventory,
            local=LocalObjectStore(),
            remote=S3ObjectStore(),
            max_objects=max_objects,
        )
        result["head_bucket_verified"] = True
        result["write_read_delete_probe_verified"] = True
        # Only aggregate counts are logged. Object keys, URLs and credentials are
        # deliberately excluded because application logs are operational data.
        logger.warning("R2 video backfill result: %s", json.dumps(result, sort_keys=True))
        return result
    finally:
        _BACKFILL_LOCK.release()


def enqueue_remote_training_video_r2_backfill(*, max_objects: int = 0) -> JobRecord:
    return enqueue(
        _JOB_NAME,
        run_remote_training_video_r2_backfill,
        max_objects=max(0, int(max_objects or 0)),
    )


def is_remote_training_video_r2_backfill_job(record: JobRecord) -> bool:
    return record.name == _JOB_NAME
