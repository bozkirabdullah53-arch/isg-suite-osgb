"""Kurum yedekleme ve merkezi arşiv API."""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.api.tenant_access import accessible_company_ids_for_admin
from app.core.database import get_db
from app.models.entities import ArchiveKind, EisaArchiveRecord, User, UserRole
from app.services.archive_store import create_tenant_backup, resolve_archive_path
from app.services.audit import add_audit_log
from app.services.backup_restore import inspect_backup_file, restore_files_from_backup

router = APIRouter(prefix="/archives", tags=["Yedekleme ve Arşiv"])


class ArchiveResponse(BaseModel):
    id: int
    kind: str
    osgb_id: int | None
    company_id: int | None
    entity_type: str | None
    entity_id: str | None
    original_name: str | None
    size_bytes: int
    notes: str | None
    created_by_user_id: int | None
    created_at: object

    model_config = ConfigDict(from_attributes=True)


class BackupRequest(BaseModel):
    company_id: int | None = None
    osgb_id: int | None = None


class RestoreRequest(BaseModel):
    dry_run: bool = True
    confirm: str | None = None


def _to_response(row: EisaArchiveRecord) -> ArchiveResponse:
    return ArchiveResponse(
        id=row.id,
        kind=row.kind.value if hasattr(row.kind, "value") else str(row.kind),
        osgb_id=row.osgb_id,
        company_id=row.company_id,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        original_name=row.original_name,
        size_bytes=row.size_bytes,
        notes=row.notes,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at,
    )


def _assert_can_access(db: Session, user: User, row: EisaArchiveRecord) -> None:
    if user.role == UserRole.GLOBAL_ADMIN:
        return
    if user.role != UserRole.COMPANY_ADMIN:
        raise HTTPException(403, "Arşive erişim yetkiniz yok.")
    if user.osgb_id and row.osgb_id == user.osgb_id:
        return
    if row.company_id and row.company_id in accessible_company_ids_for_admin(db, user):
        return
    if user.company_id and row.company_id == user.company_id:
        return
    raise HTTPException(403, "Bu arşiv kaydına erişemezsiniz.")


@router.get("", response_model=list[ArchiveResponse])
def list_archives(
    kind: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    stmt = select(EisaArchiveRecord).order_by(EisaArchiveRecord.created_at.desc()).limit(500)
    if kind:
        try:
            stmt = stmt.where(EisaArchiveRecord.kind == ArchiveKind(kind))
        except ValueError:
            raise HTTPException(422, "Geçersiz arşiv türü.") from None
    if user.role != UserRole.GLOBAL_ADMIN:
        if user.osgb_id:
            stmt = stmt.where(EisaArchiveRecord.osgb_id == user.osgb_id)
        else:
            company_ids = accessible_company_ids_for_admin(db, user)
            if not company_ids:
                return []
            stmt = stmt.where(EisaArchiveRecord.company_id.in_(company_ids))
    return [_to_response(r) for r in db.scalars(stmt).all()]


@router.post("/backup", response_model=ArchiveResponse)
def create_backup(
    payload: BackupRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    try:
        if user.role == UserRole.GLOBAL_ADMIN:
            row = create_tenant_backup(
                db, user=user, osgb_id=payload.osgb_id, company_id=payload.company_id
            )
        else:
            row = create_tenant_backup(
                db,
                user=user,
                osgb_id=user.osgb_id,
                company_id=payload.company_id or user.company_id,
            )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    add_audit_log(
        db,
        user=user,
        action="tenant_backup_created",
        module="archives",
        entity_type="eisa_archive",
        entity_id=str(row.id),
        description=f"Tenant yedeği oluşturuldu: {row.original_name}",
    )
    db.commit()
    return _to_response(row)


@router.get("/{archive_id}/download")
def download_archive(
    archive_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    row = db.get(EisaArchiveRecord, archive_id)
    if not row:
        raise HTTPException(404, "Arşiv bulunamadı.")
    _assert_can_access(db, user, row)
    try:
        path = resolve_archive_path(row)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return FileResponse(path, filename=row.original_name or path.name)


@router.get("/{archive_id}/restore-plan")
def archive_restore_plan(
    archive_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    """Yedek içeriğini salt okunur inceler — hiçbir şey yazmaz."""
    row = db.get(EisaArchiveRecord, archive_id)
    if not row:
        raise HTTPException(404, "Arşiv bulunamadı.")
    if row.kind != ArchiveKind.TENANT_BACKUP:
        raise HTTPException(400, "Restore planı yalnızca kurum yedekleri için geçerlidir.")
    _assert_can_access(db, user, row)
    try:
        path = resolve_archive_path(row)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    plan = inspect_backup_file(path, archive_name=row.original_name)
    return plan.to_dict()


@router.post("/{archive_id}/restore")
def archive_restore(
    archive_id: int,
    payload: RestoreRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    """Dosya geri yükleme — varsayılan kapalı; dry_run ile güvenli prova."""
    row = db.get(EisaArchiveRecord, archive_id)
    if not row:
        raise HTTPException(404, "Arşiv bulunamadı.")
    if row.kind != ArchiveKind.TENANT_BACKUP:
        raise HTTPException(400, "Restore yalnızca kurum yedekleri için.")
    _assert_can_access(db, user, row)
    try:
        path = resolve_archive_path(row)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    result = restore_files_from_backup(
        path,
        dry_run=payload.dry_run,
        confirm=payload.confirm,
    )
    add_audit_log(
        db,
        user=user,
        action="tenant_backup_restore_dry_run" if payload.dry_run else "tenant_backup_restore",
        module="archives",
        entity_type="eisa_archive",
        entity_id=str(row.id),
        description=result.get("message") or "restore",
    )
    db.commit()
    return result
