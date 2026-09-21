"""Additive remote-training document identity and logo support.

This extension deliberately leaves the existing remote-training tables and
classic face-to-face training flow untouched. It patches only the document
projection used by remote-training certificates and registers isolated logo
management routes on the existing remote-training router.
"""
from __future__ import annotations

import logging
from functools import wraps
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi import Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.api import remote_training as remote_api
from app.api.deps import get_current_user
from app.api.files import safe_upload_root
from app.core.config import settings
from app.core.database import get_db
from app.models.entities import Company, Employee, User
from app.services import remote_training as remote_service
from app.services.object_store import get_object_store
from app.services.upload_gateway import delete_relative, persist_relative
from app.services.upload_security import assert_safe_upload

logger = logging.getLogger(__name__)
_INSTALLED = False

REMOTE_LOGO_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
REMOTE_LOGO_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
}
REMOTE_LOGO_MAX_BYTES = 2 * 1024 * 1024
COMPANY_LOGO_DIRECTORY = "remote-training-company-logo"


def _logo_relative_path(company_id: int, program_id: int, extension: str) -> str:
    return (
        Path(str(int(company_id)))
        / "remote-training-logos"
        / str(int(program_id))
        / f"logo{extension.lower()}"
    ).as_posix()


def _company_logo_relative_path(company_id: int, extension: str) -> str:
    return (
        Path(str(int(company_id)))
        / COMPANY_LOGO_DIRECTORY
        / f"logo{extension.lower()}"
    ).as_posix()


def _safe_local_logo_path(relative_path: str) -> Path | None:
    root = Path(settings.upload_dir).resolve()
    path = (root / relative_path).resolve()
    if root not in path.parents:
        return None
    return path


def remote_program_logo_relative_path(company_id: int, program_id: int) -> str | None:
    """Return the deterministic logo key without changing training records."""
    for extension in REMOTE_LOGO_EXTENSIONS:
        relative = _logo_relative_path(company_id, program_id, extension)
        local = _safe_local_logo_path(relative)
        if local is not None and local.is_file():
            return relative
        if settings.upload_gateway_enabled:
            try:
                if get_object_store().exists(relative):
                    return relative
            except Exception:
                logger.warning(
                    "remote training logo lookup failed: company=%s program=%s path=%s",
                    company_id,
                    program_id,
                    relative,
                    exc_info=True,
                )
    return None


def remote_company_logo_relative_path(company_id: int) -> str | None:
    """Return the company-wide remote-training logo key when one exists."""
    for extension in REMOTE_LOGO_EXTENSIONS:
        relative = _company_logo_relative_path(company_id, extension)
        local = _safe_local_logo_path(relative)
        if local is not None and local.is_file():
            return relative
        if settings.upload_gateway_enabled:
            try:
                if get_object_store().exists(relative):
                    return relative
            except Exception:
                logger.warning(
                    "remote training company logo lookup failed: company=%s path=%s",
                    company_id,
                    relative,
                    exc_info=True,
                )
    return None


def _materialize_logo_for_pdf(relative_path: str | None) -> str | None:
    """Make a remote-backed logo readable by the existing PDF renderer.

    ``training_pdfs`` intentionally resolves logos only inside ``upload_dir``.
    For a remote upload backend we keep that safety contract: fetch the known
    deterministic object key into the same jailed local cache before rendering.
    """
    if not relative_path:
        return None
    local = _safe_local_logo_path(relative_path)
    if local is None:
        return None
    if local.is_file():
        return relative_path
    if not settings.upload_gateway_enabled:
        return None
    try:
        content = get_object_store().get_bytes(relative_path)
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(content)
        return relative_path
    except Exception:
        logger.exception("remote training logo could not be materialized for PDF: %s", relative_path)
        return None


def materialize_remote_company_logo_for_pdf(company_id: int) -> str | None:
    """Resolve the company-wide logo into the PDF renderer's safe local cache."""
    return _materialize_logo_for_pdf(remote_company_logo_relative_path(company_id))


def build_remote_certificate_pdf(db: Session, certificate) -> bytes:
    """Render a remote certificate with real employee identity and optional logo."""
    program = remote_service.load_program(db, certificate.program_id)
    defaults = remote_service._remote_document_defaults(db, certificate.company_id)
    current_employee = db.get(Employee, certificate.employee_id)

    employee = SimpleNamespace(
        id=certificate.employee_id,
        # Preserve the certificate's historical name snapshot; only the two
        # fields missing from the old remote document adapter are projected
        # from the current employee master record.
        full_name=certificate.employee_name_snapshot,
        national_id_masked=(
            getattr(current_employee, "national_id_masked", None)
            if current_employee is not None
            else None
        ),
        job_title=(
            str(getattr(current_employee, "job_title", None) or "").strip()
            if current_employee is not None
            else ""
        ),
    )
    participant = SimpleNamespace(
        employee_id=certificate.employee_id,
        certificate_number=certificate.certificate_number,
    )
    duration_hours = max(
        1,
        (int(certificate.training_duration_seconds or 0) + 2699) // 2700,
    )
    instructor_name = (
        certificate.instructor_name_snapshot
        or program.instructor_name
        or defaults.get("instructor_name")
        or ""
    )
    instructor_qualification = (
        certificate.instructor_qualification_snapshot
        or program.instructor_qualification
        or defaults.get("instructor_qualification")
        or ""
    )
    # A workplace-uploaded company logo is the visible identity on its own
    # documents. The OSGB/program logo remains the fallback for companies that
    # have not uploaded one themselves.
    logo_path = materialize_remote_company_logo_for_pdf(certificate.company_id)
    if not logo_path:
        logo_path = _materialize_logo_for_pdf(
            remote_program_logo_relative_path(certificate.company_id, certificate.program_id)
        )
    training = SimpleNamespace(
        id=certificate.program_id,
        title=certificate.training_name,
        training_type=remote_service.REMOTE_CERTIFICATE_TRAINING_TYPE,
        delivery_method=remote_service.REMOTE_CERTIFICATE_TRAINING_TYPE,
        start_date=certificate.training_date,
        end_date=certificate.training_date,
        duration_hours=duration_hours,
        evaluation_method="Final sınavı",
        passing_score=program.passing_score,
        location=certificate.workplace_name_snapshot or "Uzaktan eğitim",
        hazard_class=certificate.hazard_class_snapshot or "",
        sector=certificate.nace_code_snapshot or "",
        instructor_name=instructor_name,
        instructor_qualification=instructor_qualification,
        workplace_physician=(
            certificate.workplace_physician_snapshot
            or defaults.get("workplace_physician")
        ),
        employer_representative=(
            certificate.employer_representative_snapshot
            or defaults.get("employer_representative")
        ),
        stamp_text=(
            "Bu belge, uzaktan eğitim video, video içi kontrol soruları ve "
            "final sınavı tamamlanma kayıtlarına dayanır."
        ),
        verification_code=certificate.verification_code,
        logo_path=logo_path,
        _remote_certificate_view=True,
        participants=[participant],
    )
    from app.services.training_pdfs import build_certificates_pdf

    return build_certificates_pdf(
        company_name=certificate.company_name_snapshot,
        training=training,
        employees={certificate.employee_id: employee},
    )


def _program_output_with_logo(original):
    @wraps(original)
    def wrapped(program):
        result = original(program)
        result["logo_path"] = remote_program_logo_relative_path(
            program.company_id,
            program.id,
        )
        return result

    wrapped._remote_document_logo_output_active = True
    return wrapped


def _delete_existing_logo(company_id: int, program_id: int) -> None:
    for extension in REMOTE_LOGO_EXTENSIONS:
        relative = _logo_relative_path(company_id, program_id, extension)
        local = _safe_local_logo_path(relative)
        exists = bool(local is not None and local.is_file())
        if settings.upload_gateway_enabled and not exists:
            try:
                exists = bool(get_object_store().exists(relative))
            except Exception:
                logger.warning("remote logo existence check failed before delete: %s", relative, exc_info=True)
        if not exists:
            continue
        try:
            delete_relative(relative)
        except Exception:
            logger.exception("remote training logo cleanup failed: %s", relative)
            raise HTTPException(500, "Önceki logo güvenli biçimde kaldırılamadı.")


def _delete_existing_company_logo(company_id: int) -> None:
    for extension in REMOTE_LOGO_EXTENSIONS:
        relative = _company_logo_relative_path(company_id, extension)
        local = _safe_local_logo_path(relative)
        exists = bool(local is not None and local.is_file())
        if settings.upload_gateway_enabled and not exists:
            try:
                exists = bool(get_object_store().exists(relative))
            except Exception:
                logger.warning(
                    "remote company logo existence check failed: %s",
                    relative,
                    exc_info=True,
                )
        if not exists:
            continue
        try:
            delete_relative(relative)
        except Exception:
            logger.exception("remote company logo cleanup failed: %s", relative)
            raise HTTPException(500, "Önceki firma logosu güvenli biçimde kaldırılamadı.")


def _assert_workplace_company_logo_manager(
    db: Session,
    user: User,
    requested_company_id: int | None = None,
) -> Company:
    """Allow workplace accounts and assigned safety specialists to manage their own accessible company logo."""
    remote_api._manager(user)
    if remote_service.is_workplace_account(user):
        company_id = int(user.company_id or 0)
    else:
        if getattr(user, "role", None) != getattr(remote_api.UserRole, "SAFETY_SPECIALIST", None):
            raise HTTPException(403, "Firma logosunu bu hesap yönetemez.")
        company_id = int(requested_company_id or 0)
    if company_id <= 0:
        raise HTTPException(422, "Firma seçilmelidir.")
    remote_api.ensure_company_access(db, user, company_id)
    company = db.get(Company, company_id)
    if not company or not company.is_active:
        raise HTTPException(404, "İşyeri bulunamadı veya pasif.")
    return company


def _company_logo_output(company: Company) -> dict[str, Any]:
    relative = remote_company_logo_relative_path(company.id)
    return {
        "company_id": company.id,
        "company_name": company.name,
        "logo_path": relative,
        "has_logo": bool(relative),
    }


def get_remote_company_logo(
    company_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    company = _assert_workplace_company_logo_manager(db, user, company_id)
    return _company_logo_output(company)


async def upload_remote_company_logo(
    file: UploadFile = File(...),
    company_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    company = _assert_workplace_company_logo_manager(db, user, company_id)
    original = Path(file.filename or "logo.png")
    extension = original.suffix.lower()
    if extension not in REMOTE_LOGO_EXTENSIONS or (
        file.content_type and file.content_type.lower() not in REMOTE_LOGO_MIME_TYPES
    ):
        raise HTTPException(400, "Logo için PNG, JPG, JPEG veya WebP yükleyin.")

    content = await file.read(REMOTE_LOGO_MAX_BYTES + 1)
    if len(content) > REMOTE_LOGO_MAX_BYTES:
        raise HTTPException(413, "Logo en fazla 2 MB olabilir.")
    assert_safe_upload(content, extension, original.name)

    _delete_existing_company_logo(company.id)
    relative = _company_logo_relative_path(company.id, extension)
    if settings.upload_gateway_enabled:
        persist_relative(
            content,
            relative_path=relative,
            original_name=original.name,
            max_bytes=REMOTE_LOGO_MAX_BYTES,
        )
    else:
        root = safe_upload_root()
        target = (root / relative).resolve()
        if root not in target.parents:
            raise HTTPException(400, "Geçersiz dosya yolu.")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    remote_service.audit(
        db,
        company_id=company.id,
        user=user,
        action="company_remote_training_logo_updated",
        entity_type="company",
        entity_id=company.id,
        details={"logo_path": relative},
    )
    remote_api._commit(db, "Firma logosu kaydedilemedi.")
    return _company_logo_output(company)


def delete_remote_company_logo(
    company_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    company = _assert_workplace_company_logo_manager(db, user, company_id)
    _delete_existing_company_logo(company.id)
    remote_service.audit(
        db,
        company_id=company.id,
        user=user,
        action="company_remote_training_logo_deleted",
        entity_type="company",
        entity_id=company.id,
    )
    remote_api._commit(db, "Firma logosu kaldırılamadı.")
    return _company_logo_output(company)


async def upload_remote_program_logo(
    program_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    remote_api._catalog_manager(user)
    program = remote_api._assert_program_manager(db, user, program_id)
    original = Path(file.filename or "logo.png")
    extension = original.suffix.lower()
    if extension not in REMOTE_LOGO_EXTENSIONS or (
        file.content_type and file.content_type.lower() not in REMOTE_LOGO_MIME_TYPES
    ):
        raise HTTPException(400, "Logo için PNG, JPG, JPEG veya WebP yükleyin.")

    content = await file.read(REMOTE_LOGO_MAX_BYTES + 1)
    if len(content) > REMOTE_LOGO_MAX_BYTES:
        raise HTTPException(413, "Logo en fazla 2 MB olabilir.")
    assert_safe_upload(content, extension, original.name)

    _delete_existing_logo(program.company_id, program.id)
    relative = _logo_relative_path(program.company_id, program.id, extension)
    if settings.upload_gateway_enabled:
        persist_relative(
            content,
            relative_path=relative,
            original_name=original.name,
            max_bytes=REMOTE_LOGO_MAX_BYTES,
        )
    else:
        root = safe_upload_root()
        target = (root / relative).resolve()
        if root not in target.parents:
            raise HTTPException(400, "Geçersiz dosya yolu.")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    remote_service.audit(
        db,
        company_id=program.company_id,
        user=user,
        action="program_logo_updated",
        entity_type="program",
        entity_id=program.id,
        details={"logo_path": relative},
    )
    remote_api._commit(db, "Uzaktan eğitim logosu kaydedilemedi.")
    db.refresh(program)
    return remote_api._program_output(program)


def delete_remote_program_logo(
    program_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    remote_api._catalog_manager(user)
    program = remote_api._assert_program_manager(db, user, program_id)
    _delete_existing_logo(program.company_id, program.id)
    remote_service.audit(
        db,
        company_id=program.company_id,
        user=user,
        action="program_logo_deleted",
        entity_type="program",
        entity_id=program.id,
    )
    remote_api._commit(db, "Uzaktan eğitim logosu kaldırılamadı.")
    db.refresh(program)
    return remote_api._program_output(program)


def _route_exists(path_suffix: str, method: str) -> bool:
    method = method.upper()
    for route in remote_api.router.routes:
        route_path = str(getattr(route, "path", "") or "")
        methods = set(getattr(route, "methods", set()) or set())
        if route_path.endswith(path_suffix) and method in methods:
            return True
    return False


def install_remote_training_document_extension() -> dict[str, Any]:
    """Install only the additive remote-document behavior, idempotently."""
    global _INSTALLED
    if _INSTALLED:
        return {"installed": True, "already_installed": True}

    current_output = remote_api._program_output
    if not getattr(current_output, "_remote_document_logo_output_active", False):
        remote_api._program_output = _program_output_with_logo(current_output)

    # The API imported this function by name, so patch both references. The
    # combined certificate builder resolves the service module's global
    # ``build_certificate_pdf`` at call time and therefore picks this up too.
    remote_service.build_certificate_pdf = build_remote_certificate_pdf
    remote_api.build_certificate_pdf = build_remote_certificate_pdf

    routes = (
        ("/company-logo", get_remote_company_logo, ["GET"]),
        ("/company-logo", upload_remote_company_logo, ["POST"]),
        ("/company-logo", delete_remote_company_logo, ["DELETE"]),
        ("/programs/{program_id}/logo", upload_remote_program_logo, ["POST"]),
        ("/programs/{program_id}/logo", delete_remote_program_logo, ["DELETE"]),
    )
    added: list[str] = []
    for path, endpoint, methods in routes:
        method = methods[0]
        if _route_exists(path, method):
            continue
        remote_api.router.add_api_route(
            path,
            endpoint,
            methods=methods,
            tags=["Uzaktan Temel İSG Eğitimi"],
        )
        added.append(f"{method} {path}")

    _INSTALLED = True
    return {
        "installed": True,
        "already_installed": False,
        "routes_added": added,
        "certificate_identity": True,
        "certificate_logo": True,
    }
