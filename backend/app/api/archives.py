"""Kurum yedekleme ve merkezi arşiv API."""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.company_access import ensure_company_access
from app.api.deps import get_current_user, require_roles
from app.api.tenant_access import accessible_company_ids_for_admin
from app.core.database import SessionLocal, get_db
from app.models.entities import ArchiveKind, Company, EisaArchiveRecord, OsgbOrganization, User, UserRole
from app.services.archive_store import create_tenant_backup, resolve_archive_path
from app.services.audit import add_audit_log
from app.services.backup_restore import inspect_backup_file, restore_files_from_backup
from app.services.backup_safety import validate_backup_archive, verify_archive_checksum
from app.services.job_queue import JobStatus, async_jobs_enabled, enqueue

router = APIRouter(prefix="/archives", tags=["Yedekleme ve Arşiv"])


class ArchiveResponse(BaseModel):
    id: int
    kind: str
    osgb_id: int | None
    company_id: int | None
    osgb_name: str | None = None
    company_name: str | None = None
    scope_label: str | None = None
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


def _to_response(
    row: EisaArchiveRecord,
    *,
    osgb_name: str | None = None,
    company_name: str | None = None,
) -> ArchiveResponse:
    resolved_osgb_name = osgb_name or (
        f"OSGB #{row.osgb_id}" if row.osgb_id is not None else None
    )
    resolved_company_name = company_name or (
        f"Firma #{row.company_id}" if row.company_id is not None else None
    )
    scope_label = (
        f"{resolved_company_name} · OSGB: {resolved_osgb_name or '—'}"
        if resolved_company_name
        else (
            f"{resolved_osgb_name} · tüm firmalar"
            if resolved_osgb_name
            else "Merkezi kayıt"
        )
    )
    return ArchiveResponse(
        id=row.id,
        kind=row.kind.value if hasattr(row.kind, "value") else str(row.kind),
        osgb_id=row.osgb_id,
        company_id=row.company_id,
        osgb_name=resolved_osgb_name,
        company_name=resolved_company_name,
        scope_label=scope_label,
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
    if user.company_id is not None:
        if row.company_id == user.company_id:
            return
        raise HTTPException(403, "Bu arşiv kaydına erişemezsiniz.")
    try:
        from app.core.tenant_context import assert_company_access, assert_osgb_access, current_tenant

        if current_tenant() is not None:
            if row.osgb_id is not None:
                assert_osgb_access(row.osgb_id)
            if row.company_id is not None and user.company_id:
                assert_company_access(row.company_id)
    except HTTPException:
        raise
    if user.osgb_id and row.osgb_id == user.osgb_id:
        return
    if row.company_id and row.company_id in accessible_company_ids_for_admin(db, user):
        return
    if user.company_id and row.company_id == user.company_id:
        return
    raise HTTPException(403, "Bu arşiv kaydına erişemezsiniz.")


def _archive_preflight(
    row: EisaArchiveRecord,
    path,
    *,
    validate_zip: bool,
) -> dict:
    checksum_status = verify_archive_checksum(path, row.checksum)
    result: dict = {"checksum": checksum_status}
    if validate_zip:
        result["zip_safety"] = validate_backup_archive(path)
    return result


@router.get("", response_model=list[ArchiveResponse])
def list_archives(
    kind: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    stmt = (
        select(EisaArchiveRecord, OsgbOrganization.name, Company.name)
        .outerjoin(
            OsgbOrganization,
            OsgbOrganization.id == EisaArchiveRecord.osgb_id,
        )
        .outerjoin(Company, Company.id == EisaArchiveRecord.company_id)
        .order_by(EisaArchiveRecord.created_at.desc())
        .limit(500)
    )
    if kind:
        try:
            stmt = stmt.where(EisaArchiveRecord.kind == ArchiveKind(kind))
        except ValueError:
            raise HTTPException(422, "Geçersiz arşiv türü.") from None
    if user.role != UserRole.GLOBAL_ADMIN:
        if user.company_id is not None:
            stmt = stmt.where(EisaArchiveRecord.company_id == user.company_id)
        elif user.osgb_id:
            stmt = stmt.where(EisaArchiveRecord.osgb_id == user.osgb_id)
        else:
            company_ids = accessible_company_ids_for_admin(db, user)
            if not company_ids:
                return []
            stmt = stmt.where(EisaArchiveRecord.company_id.in_(company_ids))
    return [
        _to_response(row, osgb_name=osgb_name, company_name=company_name)
        for row, osgb_name, company_name in db.execute(stmt).all()
    ]


def _run_tenant_backup_job(
    *,
    user_id: int,
    is_global_admin: bool,
    user_osgb_id: int | None,
    user_company_id: int | None,
    payload_osgb_id: int | None,
    payload_company_id: int | None,
) -> dict:
    """Kendi SessionLocal'ı ile yedek üretir (async worker güvenli)."""
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user or not user.is_active:
            raise ValueError("Kullanıcı bulunamadı veya pasif.")
        if is_global_admin:
            row = create_tenant_backup(
                db, user=user, osgb_id=payload_osgb_id, company_id=payload_company_id
            )
        else:
            row = create_tenant_backup(
                db,
                user=user,
                osgb_id=user_osgb_id,
                company_id=payload_company_id or user_company_id,
            )
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
        return {
            "archive_id": row.id,
            "original_name": row.original_name,
            "size_bytes": row.size_bytes,
        }


@router.post("/backup")
def create_backup(
    payload: BackupRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    """Yedek oluştur. ASYNC_JOBS_ENABLED açıkken 202 + job_id; kapalıyken senkron ArchiveResponse."""
    resolved_company_id = payload.company_id
    if user.role != UserRole.GLOBAL_ADMIN:
        if payload.osgb_id is not None and payload.osgb_id != user.osgb_id:
            raise HTTPException(403, "Başka bir OSGB için yedek oluşturamazsınız.")
        if user.company_id is not None:
            if payload.company_id is not None and payload.company_id != user.company_id:
                raise HTTPException(403, "Başka bir işyeri için yedek oluşturamazsınız.")
            resolved_company_id = user.company_id
        elif payload.company_id is not None:
            ensure_company_access(db, user, payload.company_id)
    job = enqueue(
        "tenant_backup",
        _run_tenant_backup_job,
        user_id=user.id,
        is_global_admin=user.role == UserRole.GLOBAL_ADMIN,
        user_osgb_id=user.osgb_id,
        user_company_id=user.company_id,
        payload_osgb_id=payload.osgb_id,
        payload_company_id=resolved_company_id,
    )
    if async_jobs_enabled():
        return JSONResponse(
            status_code=202,
            content={
                "job_id": job.id,
                "status": job.status.value,
                "name": job.name,
            },
        )
    if job.status == JobStatus.FAILED:
        raise HTTPException(400, job.error or "Yedek oluşturulamadı.")
    archive_id = (job.result or {}).get("archive_id")
    row = db.get(EisaArchiveRecord, archive_id) if archive_id else None
    if not row:
        raise HTTPException(500, "Yedek kaydı okunamadı.")
    osgb_name = (
        db.scalar(select(OsgbOrganization.name).where(OsgbOrganization.id == row.osgb_id))
        if row.osgb_id is not None
        else None
    )
    company_name = (
        db.scalar(select(Company.name).where(Company.id == row.company_id))
        if row.company_id is not None
        else None
    )
    return _to_response(row, osgb_name=osgb_name, company_name=company_name)


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
    _archive_preflight(row, path, validate_zip=False)
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
    integrity = _archive_preflight(row, path, validate_zip=True)
    plan = inspect_backup_file(path, archive_name=row.original_name).to_dict()
    plan["integrity"] = integrity
    return plan


@router.post("/{archive_id}/restore")
def archive_restore(
    archive_id: int,
    payload: RestoreRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    """Dosya geri yükleme — dry_run her zaman; diske yazma flag + confirm=RESTORE."""
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
    integrity = _archive_preflight(row, path, validate_zip=True)
    result = restore_files_from_backup(
        path,
        dry_run=payload.dry_run,
        confirm=payload.confirm,
    )
    result["integrity"] = integrity
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
