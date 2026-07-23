from pathlib import Path
from uuid import uuid4

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.api.company_access import ensure_company_access
from app.core.config import settings
from app.core.database import get_db
from app.models.entities import DocumentRecord, User, UserRole
from app.services.audit import add_audit_log
from app.services.upload_security import assert_safe_upload

router = APIRouter(prefix="/files", tags=["Dosyalar"])

ALLOWED_EXTENSIONS = {".pdf", ".xlsx", ".xls", ".docx", ".png", ".jpg", ".jpeg"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/png",
    "image/jpeg",
}


def safe_upload_root() -> Path:
    root = Path(settings.upload_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _assert_document_access(db: Session, user: User, document: DocumentRecord) -> None:
    ensure_company_access(db, user, document.company_id)


@router.post("/documents/{document_id}")
async def upload_document_file(
    document_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(
        UserRole.GLOBAL_ADMIN,
        UserRole.COMPANY_ADMIN,
        UserRole.SAFETY_SPECIALIST,
        UserRole.WORKPLACE_PHYSICIAN,
    )),
):
    document = db.get(DocumentRecord, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Doküman kaydı bulunamadı.")
    _assert_document_access(db, user, document)

    original = Path(file.filename or "file")
    extension = original.suffix.lower()
    if extension not in ALLOWED_EXTENSIONS or file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Desteklenmeyen dosya türü.")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Dosya {settings.max_upload_mb} MB sınırını aşıyor.")

    assert_safe_upload(content, extension, original.name)

    company_dir = safe_upload_root() / str(document.company_id)
    company_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}{extension}"
    target = (company_dir / stored_name).resolve()
    if safe_upload_root() not in target.parents:
        raise HTTPException(status_code=400, detail="Geçersiz dosya yolu.")

    async with aiofiles.open(target, "wb") as out:
        await out.write(content)

    document.file_name = original.name
    document.description = ((document.description or "") + f"\n[stored:{stored_name}]").strip()
    add_audit_log(
        db,
        user=user,
        action="file_uploaded",
        entity_type="document",
        entity_id=str(document.id),
        description=f"{original.name} yüklendi.",
    )
    db.commit()
    return {"message": "Dosya başarıyla yüklendi.", "file_name": original.name}


@router.get("/documents/{document_id}/download")
def download_document_file(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    document = db.get(DocumentRecord, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Doküman bulunamadı.")
    _assert_document_access(db, user, document)

    marker = "[stored:"
    description = document.description or ""
    if marker not in description:
        raise HTTPException(status_code=404, detail="Bu kayda bağlı dosya bulunmuyor.")
    raw_name = description.split(marker, 1)[1].split("]", 1)[0].strip()
    # Cross-tenant path traversal engeli: yalnızca dosya adı, ayırıcı/`..` yok
    stored_name = Path(raw_name).name
    if (
        not stored_name
        or stored_name != raw_name
        or ".." in stored_name
        or "/" in raw_name
        or "\\" in raw_name
    ):
        raise HTTPException(status_code=400, detail="Geçersiz dosya referansı.")
    path = (safe_upload_root() / str(document.company_id) / stored_name).resolve()
    company_root = (safe_upload_root() / str(document.company_id)).resolve()
    if company_root not in path.parents and path != company_root:
        raise HTTPException(status_code=404, detail="Dosya fiziksel depolamada bulunamadı.")
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Dosya fiziksel depolamada bulunamadı.")

    # İstemci Content-Type'ına güvenme — uzantıdan güvenli MIME
    mime_by_ext = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    media = mime_by_ext.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, filename=document.file_name or stored_name, media_type=media)
