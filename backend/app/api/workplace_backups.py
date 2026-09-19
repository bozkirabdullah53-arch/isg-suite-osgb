from datetime import datetime
import hmac
from dataclasses import asdict
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, is_workplace_manager_account
from app.core.config import settings, workplace_backups_active
from app.core.database import get_db
from app.core.database import SessionLocal
from app.models.entities import ArchiveKind, BackupSource, BackupStatus, Company, EisaArchiveRecord, User
from app.services.archive_store import resolve_archive_path
from app.services.backup_safety import verify_archive_checksum
from app.services.workplace_backup import create_company_backup, read_company_backup_manifest
from app.services.workplace_backup import run_scheduled_company_backups

router = APIRouter(prefix="/workplace-backups", tags=["İşyeri Yedekleri"])
class CreateWorkplaceBackupRequest(BaseModel): model_config = ConfigDict(extra="forbid")
class WorkplaceBackupResponse(BaseModel):
    id: int; company_id: int; original_name: str | None; size_bytes: int; backup_source: str; backup_status: str
    started_at: datetime | None; completed_at: datetime | None; error_summary: str | None; created_at: datetime

def _require_workplace_manager(user: User = Depends(get_current_user)):
    if not workplace_backups_active(): raise HTTPException(404, "İşyeri yedekleri etkin değil.")
    if not is_workplace_manager_account(user): raise HTTPException(403, "Bu işlem yalnız işyeri yetkilisine açıktır.")
    return user
def _response(row):
    return WorkplaceBackupResponse(id=row.id, company_id=int(row.company_id), original_name=row.original_name,
        size_bytes=row.size_bytes, backup_source=row.backup_source.value, backup_status=row.backup_status.value,
        started_at=row.started_at, completed_at=row.completed_at, error_summary=row.error_summary, created_at=row.created_at)
def _own_backup(db, user, backup_id):
    row = db.scalar(select(EisaArchiveRecord).where(EisaArchiveRecord.id == backup_id,
        EisaArchiveRecord.kind == ArchiveKind.TENANT_BACKUP, EisaArchiveRecord.company_id == int(user.company_id),
        EisaArchiveRecord.entity_type == "workplace_backup_v4"))
    if row is None: raise HTTPException(404, "Yedek bulunamadı.")
    return row

@router.post("/internal/run-scheduled", include_in_schema=False)
def run_scheduled(x_workplace_backup_token: str = Header(default="")):
    expected = settings.workplace_backup_cron_token
    if not workplace_backups_active() or not expected or not hmac.compare_digest(x_workplace_backup_token, expected):
        raise HTTPException(404, "Bulunamadı.")
    return asdict(run_scheduled_company_backups(SessionLocal, now=datetime.utcnow()))

@router.get("/status")
def status(user: User = Depends(_require_workplace_manager)):
    return {"enabled": True, "automatic_enabled": True, "retention_days": settings.workplace_backup_retention_days,
        "backup_hour_tr": settings.workplace_backup_hour_tr, "company_id": int(user.company_id)}
@router.get("", response_model=list[WorkplaceBackupResponse])
def listing(db: Session = Depends(get_db), user: User = Depends(_require_workplace_manager)):
    rows = db.scalars(select(EisaArchiveRecord).where(EisaArchiveRecord.kind == ArchiveKind.TENANT_BACKUP,
        EisaArchiveRecord.company_id == int(user.company_id), EisaArchiveRecord.entity_type == "workplace_backup_v4")
        .order_by(EisaArchiveRecord.created_at.desc()).limit(500)).all()
    return [_response(row) for row in rows]
@router.post("", response_model=WorkplaceBackupResponse)
def create(_payload: CreateWorkplaceBackupRequest, db: Session = Depends(get_db), user: User = Depends(_require_workplace_manager)):
    if db.scalar(select(Company.id).where(Company.id == int(user.company_id), Company.is_active.is_(True))) is None:
        raise HTTPException(404, "Aktif işyeri bulunamadı.")
    return _response(create_company_backup(db, company_id=int(user.company_id), actor_user_id=user.id, source=BackupSource.MANUAL))
@router.get("/{backup_id}/download")
def download(backup_id: int, db: Session = Depends(get_db), user: User = Depends(_require_workplace_manager)):
    row = _own_backup(db, user, backup_id)
    if row.backup_status != BackupStatus.COMPLETED: raise HTTPException(409, "Yedek henüz hazır değil.")
    path = resolve_archive_path(row)
    if not path.is_file(): raise HTTPException(404, "Yedek dosyası bulunamadı.")
    return FileResponse(path, filename=row.original_name or path.name)
@router.get("/{backup_id}/contents")
def contents(backup_id: int, db: Session = Depends(get_db), user: User = Depends(_require_workplace_manager)):
    row = _own_backup(db, user, backup_id); path = resolve_archive_path(row)
    if row.backup_status != BackupStatus.COMPLETED: raise HTTPException(409, "Yedek henüz hazır değil.")
    if not path.is_file(): raise HTTPException(404, "Yedek dosyası bulunamadı.")
    checksum = verify_archive_checksum(path, row.checksum)
    if checksum.get("status") == "mismatch": raise HTTPException(409, "Yedek bütünlük kontrolünden geçemedi.")
    manifest = read_company_backup_manifest(row)
    if int(manifest.get("company_id", -1)) != int(user.company_id): raise HTTPException(409, "Yedek firma kapsamı doğrulanamadı.")
    return {"checksum": checksum, "manifest": manifest}
