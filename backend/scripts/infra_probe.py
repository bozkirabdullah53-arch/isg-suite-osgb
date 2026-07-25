"""Infra probe — Redis / object storage config (canlıyı değiştirmez).

Usage (backend/):
  python scripts/infra_probe.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from app.core.config import settings
    from app.core.rate_limit import redis_status_label
    from app.services.job_queue import async_jobs_enabled, job_backend_label
    from app.services.object_store import object_storage_config_ok, probe_object_storage, storage_backend_label

    backend = (settings.object_storage_backend or "local").strip().lower() or "local"
    print("object_storage:", storage_backend_label())
    print("object_storage_config:", "ok" if object_storage_config_ok() else "incomplete")
    probe = probe_object_storage()
    print("object_storage_probe:", probe.get("status"))
    if probe.get("elapsed_ms") is not None:
        print("object_storage_probe_ms:", probe["elapsed_ms"])
    if backend in ("s3", "r2", "minio") and not object_storage_config_ok():
        print(
            "object_storage_hint:",
            "BUCKET + ACCESS_KEY + SECRET_KEY (+ ENDPOINT for R2/minio, or REGION for AWS)",
        )
    elif backend in ("local", "disk", "fs") and probe.get("status") == "local":
        print(
            "object_storage_hint:",
            "fill R2/S3 env then re-run probe (keep OBJECT_STORAGE_BACKEND=local until reachable)",
        )
    print("upload_gateway:", "on" if settings.upload_gateway_enabled else "off")
    print("redis:", redis_status_label())
    print("async_jobs:", "on" if async_jobs_enabled() else "off")
    print("job_backend:", job_backend_label())
    print("async_force_off:", bool(settings.async_jobs_force_off))
    from app.services.health_field_crypto import encryption_key_status, health_crypto_ready_label

    print("health_field_encryption:", "on" if settings.health_field_encryption_enabled else "off")
    print("health_field_encryption_key:", encryption_key_status())
    print("health_field_crypto_ready:", health_crypto_ready_label())
    from app.services.backup_restore import backup_crypto_ready_label, backup_encryption_key_status

    print("backup_restore:", "on" if settings.backup_restore_enabled else "off")
    print("backup_encryption_key:", backup_encryption_key_status())
    print("backup_crypto_ready:", backup_crypto_ready_label())
    from app.services.clamav_scan import clamav_status_label

    print("clamav:", clamav_status_label())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
