from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.config import settings
from app.core.database import get_db
from app.core.version import APP_VERSION
from app.models.entities import User, UserRole
from app.services.job_queue import JobStatus, async_jobs_enabled, get_job
from app.services.object_store import probe_object_storage, storage_backend_label

router = APIRouter(prefix="/system", tags=["Sistem"])


@router.get("/health")
def health(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    _ = user
    db.execute(text("SELECT 1"))
    return {
        "status": "healthy",
        "database": "connected",
        "timestamp": datetime.utcnow(),
        "version": APP_VERSION,
        "environment": (settings.environment or "development").strip().lower() or "development",
        "async_jobs": "on" if async_jobs_enabled() else "off",
    }


@router.get("/infra-detail")
def infra_detail(
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    """Tam feature registry + crypto/storage — yalnız global_admin (P1-07)."""
    _ = user
    from app.services.release_status import infra_detail_payload

    return infra_detail_payload()


@router.get("/storage-probe")
def storage_probe(
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    """Salt okunur S3/R2 HeadBucket — aktif backend'i değiştirmez."""
    _ = user
    result = probe_object_storage()
    return {
        "active_backend_label": storage_backend_label(),
        "object_storage_backend": (settings.object_storage_backend or "local").strip().lower(),
        "upload_gateway": "on" if settings.upload_gateway_enabled else "off",
        "probe": result,
        "cutover_hint": (
            "R2 credential dolduysa OBJECT_STORAGE_BACKEND=dual yapın (gateway açık kalsın)."
            if result.get("status") == "reachable"
            else "Önce Render'a OBJECT_STORAGE_* doldurun; backend local kalsın, probe reachable olunca dual moda geçin."
        ),
    }


@router.post("/object-storage/video-backfill")
def start_object_storage_video_backfill(
    confirm: str | None = None,
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    """Queue an additive local→R2 copy after explicit admin confirmation."""
    _ = user
    if (confirm or "").strip().upper() != "COPY_TO_R2":
        raise HTTPException(400, "Başlatmak için confirm=COPY_TO_R2 gerekli.")
    if not async_jobs_enabled():
        raise HTTPException(409, "Uzun R2 aktarımı için asenkron iş kuyruğu açık olmalıdır.")
    probe = probe_object_storage()
    if probe.get("status") != "reachable":
        raise HTTPException(
            409,
            f"R2 bağlantısı hazır değil (durum={probe.get('status') or 'unknown'}).",
        )
    from app.services.remote_training_video_r2_backfill import (
        enqueue_remote_training_video_r2_backfill,
    )

    record = enqueue_remote_training_video_r2_backfill()
    return {
        "job_id": record.id,
        "status": record.status.value,
        "local_files_will_be_deleted": False,
        "database_rows_will_change": False,
    }


@router.get("/object-storage/video-backfill/{job_id}")
def object_storage_video_backfill_status(
    job_id: str,
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    _ = user
    record = get_job(job_id)
    if not record:
        raise HTTPException(404, "R2 video kopyalama işi bulunamadı.")
    from app.services.remote_training_video_r2_backfill import (
        is_remote_training_video_r2_backfill_job,
    )

    if not is_remote_training_video_r2_backfill_job(record):
        raise HTTPException(404, "R2 video kopyalama işi bulunamadı.")
    return {
        "job_id": record.id,
        "status": record.status.value,
        "finished": record.status in {JobStatus.DONE, JobStatus.FAILED},
        "error": record.error,
        "result": record.result,
    }


@router.get("/health-crypto-inventory")
def health_crypto_inventory(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    """Sağlık şifreleme geçiş envanteri — yalnız sayım, içerik/anahtar yok."""
    _ = user
    from app.services.health_crypto_inventory import build_health_crypto_inventory

    return build_health_crypto_inventory(db)


@router.post("/health-crypto-backfill")
def health_crypto_backfill(
    dry_run: bool = True,
    confirm: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    """Düz metin sağlık alanlarını şifrele (GA). Varsayılan dry-run; yazma confirm=BACKFILL ister."""
    _ = user
    from app.services.health_field_crypto import backfill_plaintext_records

    commit = (not dry_run) and (confirm or "").strip().upper() == "BACKFILL"
    if not dry_run and not commit:
        raise HTTPException(
            status_code=400,
            detail="Yazma için dry_run=false ve confirm=BACKFILL gerekli.",
        )
    result = backfill_plaintext_records(db, commit=commit)
    result["requested_by"] = user.email
    result["dry_run"] = not commit
    return result


@router.get("/jobs/{job_id}")
def job_status(
    job_id: str,
    user: User = Depends(get_current_user),
):
    """Async iş durumu (P1-10). Kayıt yoksa 404."""
    _ = user
    rec = get_job(job_id)
    if not rec:
        raise HTTPException(404, "İş bulunamadı.")
    return {
        "id": rec.id,
        "name": rec.name,
        "status": rec.status.value,
        "error": rec.error,
        "created_at": rec.created_at.isoformat() + "Z",
        "finished_at": rec.finished_at.isoformat() + "Z" if rec.finished_at else None,
    }
