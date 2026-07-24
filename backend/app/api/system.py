from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.version import APP_VERSION
from app.services.job_queue import async_jobs_enabled, get_job

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
