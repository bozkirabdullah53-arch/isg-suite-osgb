"""Merkezi tarihli arşiv — tenant yedekleri + silinen dosya kopyaları."""
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import (
    ArchiveKind,
    Company,
    DocumentRecord,
    EisaArchiveRecord,
    Employee,
    OsgbOrganization,
    User,
)


def archive_root() -> Path:
    root = Path(settings.backup_dir).resolve() / "central_archive"
    root.mkdir(parents=True, exist_ok=True)
    return root


def upload_root() -> Path:
    root = Path(settings.upload_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _checksum(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _rel_store(path: Path) -> str:
    return str(path.relative_to(archive_root())).replace("\\", "/")


def archive_file_before_delete(
    db: Session,
    *,
    source: Path,
    user: User | None,
    company_id: int | None,
    osgb_id: int | None = None,
    entity_type: str,
    entity_id: str | None,
    original_name: str | None = None,
    notes: str | None = None,
) -> EisaArchiveRecord | None:
    """Silmeden önce dosyayı merkezi arşive kopyala. Kaynak yoksa None."""
    try:
        src = source.resolve()
    except OSError:
        return None
    if not src.exists() or not src.is_file():
        return None

    if company_id and not osgb_id:
        company = db.get(Company, company_id)
        osgb_id = company.osgb_id if company else None

    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    folder = archive_root() / "deleted" / f"osgb-{osgb_id or 0}" / f"company-{company_id or 0}" / stamp
    folder.mkdir(parents=True, exist_ok=True)
    dest_name = f"{entity_type}-{entity_id or 'x'}-{uuid4().hex[:10]}{src.suffix}"
    dest = folder / dest_name
    shutil.copy2(src, dest)

    row = EisaArchiveRecord(
        kind=ArchiveKind.DELETED_FILE,
        osgb_id=osgb_id,
        company_id=company_id,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        original_name=original_name or src.name,
        storage_path=_rel_store(dest),
        size_bytes=dest.stat().st_size,
        checksum=_checksum(dest),
        notes=notes or "Silme öncesi otomatik arşiv",
        created_by_user_id=user.id if user else None,
    )
    db.add(row)
    db.flush()
    return row


def create_tenant_backup(
    db: Session,
    *,
    user: User,
    osgb_id: int | None = None,
    company_id: int | None = None,
) -> EisaArchiveRecord:
    """Kurum / OSGB kapsamındaki metadata + dosyaları tarihli zip olarak arşivle."""
    if user.role.value == "global_admin":
        target_osgb = osgb_id
        target_company = company_id
    else:
        target_osgb = user.osgb_id
        target_company = company_id or user.company_id

    if not target_osgb and not target_company:
        raise ValueError("Yedek için OSGB veya firma kapsamı gerekli.")

    companies: list[Company] = []
    if target_company:
        c = db.get(Company, target_company)
        if not c:
            raise ValueError("Firma bulunamadı.")
        if target_osgb and c.osgb_id and c.osgb_id != target_osgb:
            raise ValueError("Firma bu OSGB kapsamında değil.")
        companies = [c]
        target_osgb = target_osgb or c.osgb_id
    elif target_osgb:
        companies = list(
            db.scalars(select(Company).where(Company.osgb_id == target_osgb).order_by(Company.name)).all()
        )

    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    folder = archive_root() / "backups" / f"osgb-{target_osgb or 0}"
    folder.mkdir(parents=True, exist_ok=True)
    zip_name = f"backup-{stamp}-{uuid4().hex[:8]}.zip"
    zip_path = folder / zip_name

    org = db.get(OsgbOrganization, target_osgb) if target_osgb else None
    manifest = {
        "created_at": datetime.utcnow().isoformat() + "Z",
        "created_by": user.email,
        "osgb_id": target_osgb,
        "osgb_name": org.name if org else None,
        "companies": [{"id": c.id, "name": c.name} for c in companies],
    }

    company_ids = [c.id for c in companies]
    docs = []
    employees = []
    if company_ids:
        docs = list(
            db.scalars(select(DocumentRecord).where(DocumentRecord.company_id.in_(company_ids))).all()
        )
        employees = list(
            db.scalars(select(Employee).where(Employee.company_id.in_(company_ids))).all()
        )

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.writestr(
            "documents.json",
            json.dumps(
                [
                    {
                        "id": d.id,
                        "company_id": d.company_id,
                        "title": d.title,
                        "file_name": d.file_name,
                        "category": d.category.value if hasattr(d.category, "value") else str(d.category),
                        "description": d.description,
                        "is_active": d.is_active,
                        "created_at": d.created_at.isoformat() if d.created_at else None,
                    }
                    for d in docs
                ],
                ensure_ascii=False,
                indent=2,
            ),
        )
        zf.writestr(
            "employees.json",
            json.dumps(
                [
                    {
                        "id": e.id,
                        "company_id": e.company_id,
                        "full_name": e.full_name,
                        "job_title": e.job_title,
                        "is_active": e.is_active,
                    }
                    for e in employees
                ],
                ensure_ascii=False,
                indent=2,
            ),
        )
        root = upload_root()
        for cid in company_ids:
            company_dir = root / str(cid)
            if not company_dir.exists():
                continue
            for path in company_dir.rglob("*"):
                if path.is_file():
                    arcname = f"files/{cid}/{path.relative_to(company_dir).as_posix()}"
                    zf.write(path, arcname)
        if target_osgb:
            for sub in ("assignments", "visits"):
                osgb_dir = root / str(target_osgb) / sub
                if not osgb_dir.exists():
                    continue
                for path in osgb_dir.rglob("*"):
                    if path.is_file():
                        arcname = f"osgb_files/{sub}/{path.relative_to(osgb_dir).as_posix()}"
                        zf.write(path, arcname)

    row = EisaArchiveRecord(
        kind=ArchiveKind.TENANT_BACKUP,
        osgb_id=target_osgb,
        company_id=target_company,
        entity_type="tenant_backup",
        entity_id=str(target_osgb or target_company),
        original_name=zip_name,
        storage_path=_rel_store(zip_path),
        size_bytes=zip_path.stat().st_size,
        checksum=_checksum(zip_path),
        notes=f"Tenant yedek — {len(companies)} işyeri, {len(docs)} doküman",
        created_by_user_id=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def resolve_archive_path(row: EisaArchiveRecord) -> Path:
    path = (archive_root() / row.storage_path).resolve()
    if archive_root() not in path.parents and path != archive_root():
        raise FileNotFoundError("Geçersiz arşiv yolu.")
    if not path.exists():
        raise FileNotFoundError("Arşiv dosyası bulunamadı.")
    return path
