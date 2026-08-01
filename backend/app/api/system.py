from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.config import settings
from app.core.database import get_db
from app.core.version import APP_VERSION
from app.models.entities import User, UserRole
from app.services.job_queue import async_jobs_enabled, get_job
from app.services.object_store import probe_object_storage, storage_backend_label

router = APIRouter(prefix="/system", tags=["Sistem"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
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
def job_status(job_id: str):
    """Async iş durumu (P1-10). Kayıt yoksa 404."""
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
