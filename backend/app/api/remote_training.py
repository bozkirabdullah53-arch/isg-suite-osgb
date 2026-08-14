"""Secure, additive API for Basic Occupational Health and Safety video training.

This router deliberately has its own tables, feature flag and storage keys.  It
does not change the existing in-person training routes or their records.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.company_access import accessible_company_ids_or_empty, ensure_company_access
from app.api.deps import get_current_user
from app.core.config import (
    remote_basic_ohs_strict_policy_active,
    remote_basic_ohs_strict_policy_package_codes,
    settings,
)
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.entities import Branch, Company, Employee, TrainingQuestion, User, UserRole
from app.models.remote_training import (
    ASSET_TYPES,
    PROGRAM_STATUSES,
    REMOTE_SECTOR_CATALOG,
    REMOTE_TRAINING_TYPE,
    VIDEO_STATUSES,
    RemoteTrainingAssignment,
    RemoteTrainingAssignmentSector,
    RemoteTrainingAsset,
    RemoteTrainingCertificate,
    REMOTE_CATALOG_PACKAGE_SPECS,
    RemoteTrainingCatalogPackage,
    RemoteTrainingCatalogSection,
    RemoteTrainingCatalogVideo,
    RemoteTrainingCheckpointAnswer,
    RemoteTrainingEmployeeAccess,
    RemoteTrainingEvent,
    RemoteTrainingExamAttempt,
    RemoteTrainingProgram,
    RemoteTrainingProgramQuestion,
    RemoteTrainingProgramSector,
    RemoteTrainingQuestion,
    RemoteTrainingSection,
    RemoteTrainingVideo,
    RemoteTrainingVideoProgress,
    catalog_package_sector_code,
)
from app.schemas.remote_training import (
    RemoteCatalogSectionCreate,
    RemoteCatalogSectionUpdate,
    RemoteCatalogMaterialize,
    RemoteAssignmentCreate,
    RemoteCheckpointQuestionCreate,
    RemoteEmployeeAccessCreate,
    RemoteEmployeeAccountProvision,
    RemoteExamSubmit,
    RemoteFinalExamQuestionUpdate,
    RemoteProgramCreate,
    RemoteProgramQuestionLink,
    RemoteProgramSectorUpdate,
    RemoteProgramUpdate,
    RemoteProgressCreate,
    RemoteSectionCreate,
    RemoteSectionUpdate,
    RemoteVideoUpdate,
)
from app.services.object_store import get_object_store
from app.services.osgb_admin import generate_temporary_password
from app.services.remote_training import (
    MANAGE_ROLES,
    REMOTE_AUTO_EXAM_QUESTION_COUNT,
    VIEW_ROLES,
    assert_assignment_access,
    assert_program_access,
    assignment_allows_sector,
    assignment_sector_codes,
    audit,
    automatic_exam_items_for_package,
    build_program_sector_catalog,
    build_certificate_pdf,
    company_snapshot,
    create_catalog_playback_token,
    create_playback_token,
    decode_catalog_playback_token,
    decode_playback_token,
    employee_access,
    catalog_storage_key,
    catalog_program_sector_code,
    catalog_question_is_compatible,
    enqueue_video_processing,
    enqueue_catalog_video_processing,
    ensure_certificate,
    feature_active,
    is_manager,
    load_assignment,
    load_program,
    load_section,
    load_video,
    program_sector_codes,
    recalculate_assignment,
    recalculate_catalog_package_duration,
    recalculate_program_duration,
    reconcile_strict_video_end,
    assert_video_unlocked,
    strict_exam_gate_enabled,
    strict_policy_active,
    require_strict_policy_active,
    _decode_coverage,
    _merge_coverage,
    require_feature,
    response_for_video,
    storage_key,
    sector_label,
    validate_sector_code,
    validate_catalog_program_sector,
    validate_branch,
    validate_video_bytes,
)

router = APIRouter(prefix="/trainings/remote", tags=["Uzaktan Temel İSG Eğitimi"])
logger = logging.getLogger(__name__)


def _manager(user: User) -> None:
    if user.role not in MANAGE_ROLES:
        raise HTTPException(403, "Bu uzaktan eğitim işlemi için eğitici/yönetici yetkisi gerekir.")


def _viewer(user: User) -> None:
    if user.role not in VIEW_ROLES:
        raise HTTPException(403, "Bu uzaktan eğitim kaydını görüntüleme yetkiniz yok.")


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None and hasattr(value, "isoformat") else None


def _company_ids(db: Session, user: User, company_id: int | None) -> list[int] | None:
    if company_id is not None:
        ensure_company_access(db, user, company_id)
        return [company_id]
    if user.role == UserRole.GLOBAL_ADMIN:
        return None
    ids = accessible_company_ids_or_empty(db, user)
    return [int(item) for item in ids]


def _program_query_for_user(
    db: Session, user: User, company_id: int | None = None
):
    stmt = select(RemoteTrainingProgram)
    ids = _company_ids(db, user, company_id)
    if ids is not None:
        if not ids:
            stmt = stmt.where(RemoteTrainingProgram.id == -1)
        else:
            stmt = stmt.where(RemoteTrainingProgram.company_id.in_(ids))
    return stmt


def _assert_program_manager(db: Session, user: User, program_id: int) -> RemoteTrainingProgram:
    require_feature()
    _manager(user)
    program = load_program(db, program_id)
    ensure_company_access(db, user, program.company_id)
    return program

def _assert_assignment_document_manager(
    db: Session, user: User, assignment: RemoteTrainingAssignment
) -> None:
    """Participation documents are management outputs, never employee self-service."""
    program = _assert_program_manager(db, user, assignment.program_id)
    if assignment.company_id != program.company_id:
        raise HTTPException(403, "Atama firma kapsamı dışında.")


def _assert_section_manager(db: Session, user: User, section_id: int) -> RemoteTrainingSection:
    section = load_section(db, section_id)
    program = _assert_program_manager(db, user, section.program_id)
    if section.company_id != program.company_id:
        raise HTTPException(403, "Bölüm firma kapsamı dışında.")
    return section


def _assert_video_manager(db: Session, user: User, video_id: int) -> RemoteTrainingVideo:
    video = load_video(db, video_id)
    program = _assert_program_manager(db, user, video.program_id)
    if video.company_id != program.company_id:
        raise HTTPException(403, "Video firma kapsamı dışında.")
    return video


def _program_output(program: RemoteTrainingProgram) -> dict[str, Any]:
    return {
        "id": program.id,
        "company_id": program.company_id,
        "branch_id": program.branch_id,
        "source_catalog_package_id": program.source_catalog_package_id,
        "source_catalog_code": program.source_catalog_code,
        "source_catalog_revision_no": program.source_catalog_revision_no,
        "title": program.title,
        "training_type": REMOTE_TRAINING_TYPE,
        "description": program.description,
        "learning_objectives": program.learning_objectives,
        "instructor_name": program.instructor_name,
        "instructor_qualification": program.instructor_qualification,
        "total_duration_seconds": program.total_duration_seconds,
        "completion_threshold_percent": program.completion_threshold_percent,
        "passing_score": program.passing_score,
        "attempt_limit": program.attempt_limit,
        "requires_final_exam": bool(program.requires_final_exam),
        "policy_mode": program.policy_mode,
        "sequence_enforced": bool(program.sequence_enforced),
        "exam_gate_enforced": bool(program.exam_gate_enforced),
        "status": program.status,
        "revision_no": program.revision_no,
        "published_at": _iso(program.published_at),
        "archived_at": _iso(program.archived_at),
        "created_at": _iso(program.created_at),
        "updated_at": _iso(program.updated_at),
    }


def _video_output(video: RemoteTrainingVideo, *, employee: bool = False) -> dict[str, Any]:
    result = {
        "id": video.id,
        "program_id": video.program_id,
        "section_id": video.section_id,
        "revision_of_id": video.revision_of_id,
        "title": video.title,
        "description": video.description,
        "learning_objectives": video.learning_objectives,
        "order_index": video.order_index,
        "is_required": bool(video.is_required),
        "revision_no": video.revision_no,
        "is_current": bool(video.is_current),
        "status": video.status,
        "original_file_name": video.original_file_name if not employee else None,
        "content_type": video.content_type,
        "file_size_bytes": video.file_size_bytes,
        "duration_seconds": video.duration_seconds,
        "width": video.width,
        "height": video.height,
        "codec": video.codec,
        "processing_job_id": video.processing_job_id if not employee else None,
        "processing_error": video.processing_error if not employee else None,
        "published_at": _iso(video.published_at),
        "created_at": _iso(video.created_at),
    }
    return result


def _asset_output(asset: RemoteTrainingAsset) -> dict[str, Any]:
    return {
        "id": asset.id,
        "video_id": asset.video_id,
        "asset_type": asset.asset_type,
        "original_file_name": asset.original_file_name,
        "content_type": asset.content_type,
        "file_size_bytes": asset.file_size_bytes,
        "created_at": _iso(asset.created_at),
    }


def _question_output(question: RemoteTrainingQuestion, *, reveal_answer: bool) -> dict[str, Any]:
    options = json.loads(question.options_json or "{}")
    result = {
        "id": question.id,
        "program_id": question.program_id,
        "section_id": question.section_id,
        "video_id": question.video_id,
        "sector_code": question.sector_code,
        "question_text": question.question_text,
        "options": options,
        "explanation": question.explanation if reveal_answer else None,
        "timestamp_seconds": question.timestamp_seconds,
        "order_index": question.order_index,
        "is_required": bool(question.is_required),
    }
    if reveal_answer:
        result["correct_option"] = question.correct_option
    return result


def _automatic_final_exam_question_validation(
    question: RemoteTrainingQuestion, position: int
) -> list[str]:
    """Validate one editable question without blocking it on other rows.

    A draft may contain an older malformed row.  A manager must still be able
    to repair one question at a time; the complete ten-question validation is
    reserved for publication.
    """
    errors: list[str] = []
    text = " ".join(str(question.question_text or "").split()).casefold()
    if not text:
        errors.append(f"{position}. final sorusunun metni boş olamaz.")
    try:
        parsed_options = json.loads(question.options_json or "{}")
    except (TypeError, json.JSONDecodeError):
        parsed_options = {}
    options = parsed_options if isinstance(parsed_options, dict) else {}
    if set(options) != {"A", "B", "C", "D"} or any(
        not str(options.get(letter) or "").strip()
        for letter in ("A", "B", "C", "D")
    ):
        errors.append(f"{position}. final soruda A, B, C ve D seçenekleri eksiksiz olmalıdır.")
    elif len(
        {
            str(options[letter]).strip().casefold()
            for letter in ("A", "B", "C", "D")
        }
    ) != 4:
        errors.append(f"{position}. final sorunun seçenekleri birbirinden farklı olmalıdır.")
    if str(question.correct_option or "").upper() not in {"A", "B", "C", "D"}:
        errors.append(f"{position}. final sorunun doğru seçeneği geçersiz.")
    return errors


def _automatic_final_exam_validation(
    questions: list[RemoteTrainingQuestion],
) -> list[str]:
    """Validate the complete frozen catalog exam before publication.

    The source pack is curated, but the manager may edit wording and options
    while the program is still a draft.  Publishing therefore re-validates the
    complete set on the server instead of trusting the browser.
    """
    errors: list[str] = []
    if len(questions) != REMOTE_AUTO_EXAM_QUESTION_COUNT:
        errors.append(
            f"Final sınavı tam olarak {REMOTE_AUTO_EXAM_QUESTION_COUNT} soru içermelidir."
        )
    seen_texts: set[str] = set()
    for position, question in enumerate(questions, start=1):
        errors.extend(_automatic_final_exam_question_validation(question, position))
        text = " ".join(str(question.question_text or "").split()).casefold()
        if text and text in seen_texts:
            errors.append(f"{position}. final sorusu başka bir soruyla aynı.")
        elif text:
            seen_texts.add(text)
    return errors


def _section_output(
    db: Session,
    section: RemoteTrainingSection,
    *,
    employee: bool = False,
    sector_codes: set[str] | None = None,
) -> dict[str, Any]:
    videos = list(
        db.scalars(
            select(RemoteTrainingVideo)
            .where(RemoteTrainingVideo.section_id == section.id)
            .order_by(RemoteTrainingVideo.order_index, RemoteTrainingVideo.id)
        ).all()
    )
    if employee:
        videos = [v for v in videos if v.status == "published" and v.is_current]
    return {
        "id": section.id,
        "program_id": section.program_id,
        "sector_code": section.sector_code,
        "title": section.title,
        "description": section.description,
        "learning_objectives": section.learning_objectives,
        "order_index": section.order_index,
        "is_required": bool(section.is_required),
        "status": section.status,
        "videos": [_video_output(video, employee=employee) for video in videos],
    }


def _program_detail(
    db: Session,
    program: RemoteTrainingProgram,
    *,
    employee: bool = False,
    sector_codes: set[str] | None = None,
) -> dict[str, Any]:
    if employee and program.status != "published":
        raise HTTPException(403, "Bu eğitim şu anda çalışana açık değil.")
    data = _program_output(program)
    sections = list(
        db.scalars(
            select(RemoteTrainingSection)
            .where(RemoteTrainingSection.program_id == program.id)
            .order_by(RemoteTrainingSection.order_index, RemoteTrainingSection.id)
        ).all()
    )
    if employee:
        sections = [s for s in sections if s.status == "active"]
    if sector_codes is not None:
        sections = [s for s in sections if s.sector_code in sector_codes]
    data["sections"] = [
        _section_output(db, section, employee=employee, sector_codes=sector_codes)
        for section in sections
    ]
    questions = list(
        db.scalars(
            select(RemoteTrainingQuestion)
            .where(RemoteTrainingQuestion.program_id == program.id)
            .where(RemoteTrainingQuestion.is_final_exam.is_(False))
            .order_by(RemoteTrainingQuestion.order_index, RemoteTrainingQuestion.id)
        ).all()
    )
    if sector_codes is not None:
        questions = [question for question in questions if question.sector_code in sector_codes]
    data["checkpoint_questions"] = [
        _question_output(question, reveal_answer=not employee) for question in questions
    ]
    automatic_exam_questions = list(
        db.scalars(
            select(RemoteTrainingQuestion)
            .where(
                RemoteTrainingQuestion.program_id == program.id,
                RemoteTrainingQuestion.is_final_exam.is_(True),
            )
            .order_by(RemoteTrainingQuestion.order_index, RemoteTrainingQuestion.id)
        ).all()
    )
    if sector_codes is not None:
        automatic_exam_questions = [
            question
            for question in automatic_exam_questions
            if question.sector_code in sector_codes
        ]
    automatic_exam_errors = _automatic_final_exam_validation(automatic_exam_questions)
    manual_exam_link_count = db.scalar(
        select(func.count(RemoteTrainingProgramQuestion.id)).where(
            RemoteTrainingProgramQuestion.program_id == program.id
        )
    ) or 0
    data["automatic_final_exam"] = {
        "enabled": bool(program.requires_final_exam),
        "automatic": bool(automatic_exam_questions),
        "question_count": len(automatic_exam_questions),
        "required_question_count": (
            REMOTE_AUTO_EXAM_QUESTION_COUNT if strict_policy_active(program) else None
        ),
        "passing_score": program.passing_score,
        "valid": bool(automatic_exam_questions) and not automatic_exam_errors,
        "validation_errors": automatic_exam_errors if not employee else [],
        "ready": (
            not program.requires_final_exam
            or (
                (bool(automatic_exam_questions) and not automatic_exam_errors)
                if automatic_exam_questions
                else bool(manual_exam_link_count)
            )
        ),
    }
    if not employee:
        data["automatic_final_exam"]["questions"] = [
            _question_output(question, reveal_answer=True)
            for question in automatic_exam_questions
        ]
    if not employee:
        links = list(
            db.scalars(
                select(RemoteTrainingProgramQuestion)
                .where(RemoteTrainingProgramQuestion.program_id == program.id)
                .order_by(RemoteTrainingProgramQuestion.position, RemoteTrainingProgramQuestion.id)
            ).all()
        )
        data["exam_question_links"] = [
            {
                "id": link.id,
                "question_id": link.question_id,
                "position": link.position,
                "sector_code": link.sector_code or "common",
            }
            for link in links
        ]
    data["sector_scope"] = build_program_sector_catalog(
        db,
        program,
        visible_sector_codes=sector_codes if employee and sector_codes is not None else None,
    )
    return data


def _assignment_warnings(assignment: RemoteTrainingAssignment) -> list[str]:
    warnings: list[str] = []
    if not assignment.sgk_registration_number_snapshot:
        warnings.append("Atama tarihinde SGK sicil numarası bulunamadı.")
    if not assignment.nace_code_snapshot:
        warnings.append("Atama tarihinde NACE kodu bulunamadı.")
    elif not assignment.nace_description_snapshot:
        warnings.append("Atama tarihinde NACE açıklaması çözülemedi.")
    if not assignment.hazard_class_snapshot:
        warnings.append("Atama tarihinde tehlike sınıfı bulunamadı.")
    return warnings


def _exam_links_for_assignment(
    db: Session, assignment: RemoteTrainingAssignment
) -> list[RemoteTrainingProgramQuestion]:
    links = list(
        db.scalars(
            select(RemoteTrainingProgramQuestion)
            .where(RemoteTrainingProgramQuestion.program_id == assignment.program_id)
            .order_by(RemoteTrainingProgramQuestion.position, RemoteTrainingProgramQuestion.id)
        ).all()
    )
    scope = assignment_sector_codes(db, assignment)
    if scope is None:
        return links
    return [link for link in links if (link.sector_code or "common") in scope]


def _automatic_exam_questions_for_assignment(
    db: Session, assignment: RemoteTrainingAssignment
) -> list[RemoteTrainingQuestion]:
    """Return frozen catalog questions for the assignment's sector scope."""
    questions = list(
        db.scalars(
            select(RemoteTrainingQuestion)
            .where(
                RemoteTrainingQuestion.program_id == assignment.program_id,
                RemoteTrainingQuestion.is_final_exam.is_(True),
            )
            .order_by(RemoteTrainingQuestion.order_index, RemoteTrainingQuestion.id)
        ).all()
    )
    scope = assignment_sector_codes(db, assignment)
    if scope is None:
        return questions
    return [question for question in questions if question.sector_code in scope]


def _assignment_output(
    db: Session,
    assignment: RemoteTrainingAssignment,
    *,
    include_program: bool = False,
    employee: bool = False,
) -> dict[str, Any]:
    summary = recalculate_assignment(db, assignment)
    sector_codes = assignment_sector_codes(db, assignment)
    result = {
        "id": assignment.id,
        "company_id": assignment.company_id,
        "branch_id": assignment.branch_id,
        "program_id": assignment.program_id,
        "employee_id": assignment.employee_id,
        "employee_name": assignment.employee_name_snapshot,
        "status": assignment.status,
        "due_date": _iso(assignment.due_date),
        "assigned_at": _iso(assignment.assigned_at),
        "started_at": _iso(assignment.started_at),
        "completed_at": _iso(assignment.completed_at),
        "workplace_name_snapshot": assignment.workplace_name_snapshot,
        "sgk_registration_number_snapshot": assignment.sgk_registration_number_snapshot,
        "nace_code_snapshot": assignment.nace_code_snapshot,
        "nace_description_snapshot": assignment.nace_description_snapshot,
        "hazard_class_snapshot": assignment.hazard_class_snapshot,
        "snapshot_warnings": _assignment_warnings(assignment),
        "summary": summary,
        "sector_scope_mode": "scoped" if sector_codes is not None else "legacy",
        "sector_codes": sorted(sector_codes) if sector_codes is not None else None,
        "sector_names": [sector_label(code) for code in sorted(sector_codes)]
        if sector_codes is not None
        else [],
    }
    progress_rows = db.scalars(
        select(RemoteTrainingVideoProgress).where(
            RemoteTrainingVideoProgress.assignment_id == assignment.id
        )
    ).all()
    result["video_progress"] = [
        {
            "video_id": row.video_id,
            "last_position_seconds": float(row.last_position_seconds or 0),
            "watched_duration_seconds": float(row.watched_duration_seconds or 0),
            "watched_percentage": float(row.watched_percentage or 0),
            "status": row.status,
            "viewing_sessions": row.viewing_sessions,
            "last_access_at": _iso(row.last_access_at),
        }
        for row in progress_rows
    ]
    if include_program:
        program = load_program(db, assignment.program_id)
        result["program"] = _program_detail(
            db,
            program,
            employee=employee,
            sector_codes=sector_codes if employee else None,
        )
    return result


def _commit(db: Session, message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, message) from exc


def _safe_asset_content(asset_type: str, extension: str, content: bytes) -> None:
    if asset_type not in ASSET_TYPES:
        raise HTTPException(422, "Desteklenmeyen ek türü.")
    allowed = {
        "thumbnail": {".png", ".jpg", ".jpeg", ".webp"},
        "subtitle": {".vtt", ".srt"},
        "supporting_document": {".pdf", ".docx"},
    }[asset_type]
    if extension not in allowed:
        raise HTTPException(400, "Ek türü ile dosya uzantısı uyuşmuyor.")
    if not content:
        raise HTTPException(400, "Ek dosyası boş olamaz.")
    if extension == ".png" and not content.startswith(b"\x89PNG"):
        raise HTTPException(400, "PNG içeriği doğrulanamadı.")
    if extension in {".jpg", ".jpeg"} and not content.startswith(b"\xff\xd8\xff"):
        raise HTTPException(400, "JPEG içeriği doğrulanamadı.")
    if extension == ".webp" and content[:4] != b"RIFF":
        raise HTTPException(400, "WebP içeriği doğrulanamadı.")
    if extension == ".vtt" and not content.lstrip().startswith(b"WEBVTT"):
        raise HTTPException(400, "VTT altyazı başlığı bulunamadı.")
    if extension == ".pdf" and not content.startswith(b"%PDF"):
        raise HTTPException(400, "PDF içeriği doğrulanamadı.")
    if extension == ".docx" and not content.startswith(b"PK"):
        raise HTTPException(400, "DOCX içeriği doğrulanamadı.")


def _catalog_scope(db: Session, user: User) -> int | None:
    """Return the OSGB scope used by the central catalog.

    Global administrators own the shared catalog (``osgb_id IS NULL``).  Other
    managers must have an OSGB either directly or through their company; a
    missing tenant is never treated as a wildcard.
    """
    if user.role == UserRole.GLOBAL_ADMIN:
        return None
    if user.osgb_id:
        return int(user.osgb_id)
    if user.company_id:
        company = db.get(Company, user.company_id)
        if company and company.osgb_id:
            return int(company.osgb_id)
    raise HTTPException(403, "Merkezi eğitim kataloğu için OSGB kapsamı bulunamadı.")


def _catalog_package_for_manager(
    db: Session, user: User, package_id: int
) -> RemoteTrainingCatalogPackage:
    require_feature()
    _manager(user)
    package = db.get(RemoteTrainingCatalogPackage, package_id)
    if package is None:
        raise HTTPException(404, "Merkezi eğitim paketi bulunamadı.")
    if user.role != UserRole.GLOBAL_ADMIN:
        scope = _catalog_scope(db, user)
        if package.osgb_id != scope:
            raise HTTPException(403, "Bu merkezi eğitim paketi OSGB kapsamınız dışında.")
    return package


def _catalog_section_for_manager(
    db: Session, user: User, section_id: int
) -> RemoteTrainingCatalogSection:
    section = db.get(RemoteTrainingCatalogSection, section_id)
    if section is None:
        raise HTTPException(404, "Merkezi eğitim bölümü bulunamadı.")
    _catalog_package_for_manager(db, user, section.package_id)
    return section


def _catalog_video_for_manager(
    db: Session, user: User, video_id: int
) -> RemoteTrainingCatalogVideo:
    video = db.get(RemoteTrainingCatalogVideo, video_id)
    if video is None:
        raise HTTPException(404, "Merkezi eğitim videosu bulunamadı.")
    _catalog_package_for_manager(db, user, video.package_id)
    return video


def _catalog_video_output(video: RemoteTrainingCatalogVideo) -> dict[str, Any]:
    return {
        "id": video.id,
        "package_id": video.package_id,
        "section_id": video.section_id,
        "revision_of_id": video.revision_of_id,
        "title": video.title,
        "description": video.description,
        "learning_objectives": video.learning_objectives,
        "order_index": video.order_index,
        "is_required": bool(video.is_required),
        "revision_no": video.revision_no,
        "is_current": bool(video.is_current),
        "status": video.status,
        "original_file_name": video.original_file_name,
        "content_type": video.content_type,
        "file_size_bytes": video.file_size_bytes,
        "duration_seconds": video.duration_seconds,
        "width": video.width,
        "height": video.height,
        "codec": video.codec,
        "processing_job_id": video.processing_job_id,
        "processing_error": video.processing_error,
        "published_at": _iso(video.published_at),
        "created_at": _iso(video.created_at),
    }


def _catalog_section_output(
    db: Session, section: RemoteTrainingCatalogSection
) -> dict[str, Any]:
    videos = list(
        db.scalars(
            select(RemoteTrainingCatalogVideo)
            .where(RemoteTrainingCatalogVideo.section_id == section.id)
            .order_by(RemoteTrainingCatalogVideo.order_index, RemoteTrainingCatalogVideo.id)
        ).all()
    )
    return {
        "id": section.id,
        "package_id": section.package_id,
        "code": section.code,
        "title": section.title,
        "description": section.description,
        "order_index": section.order_index,
        "is_required": bool(section.is_required),
        "status": section.status,
        "videos": [_catalog_video_output(video) for video in videos],
    }


def _catalog_package_output(
    db: Session, package: RemoteTrainingCatalogPackage, *, detail: bool = False
) -> dict[str, Any]:
    sections = list(
        db.scalars(
            select(RemoteTrainingCatalogSection)
            .where(RemoteTrainingCatalogSection.package_id == package.id)
            .order_by(RemoteTrainingCatalogSection.order_index, RemoteTrainingCatalogSection.id)
        ).all()
    )
    videos = list(
        db.scalars(
            select(RemoteTrainingCatalogVideo).where(
                RemoteTrainingCatalogVideo.package_id == package.id
            )
        ).all()
    )
    automatic_exam_ready = True
    automatic_exam_warning = None
    automatic_exam_count = 0
    if package.requires_final_exam:
        try:
            automatic_exam_count = len(automatic_exam_items_for_package(package.code))
        except RuntimeError:
            automatic_exam_ready = False
            automatic_exam_warning = (
                f"{package.title} için doğrulanmış 10 soruluk soru paketi hazır değil. "
                "Firma programı hazırlanamaz; içerik yöneticisi soru paketini düzeltmelidir."
            )
    result = {
        "id": package.id,
        "code": package.code,
        "title": package.title,
        "description": package.description,
        "training_type": REMOTE_TRAINING_TYPE,
        "total_duration_seconds": package.total_duration_seconds,
        "requires_final_exam": bool(package.requires_final_exam),
        "completion_threshold_percent": package.completion_threshold_percent,
        "passing_score": package.passing_score,
        "attempt_limit": package.attempt_limit,
        "automatic_exam_question_count": automatic_exam_count,
        "automatic_exam_passing_score": package.passing_score if package.requires_final_exam else None,
        "automatic_exam_ready": automatic_exam_ready,
        "automatic_exam_warning": automatic_exam_warning,
        "policy_mode": package.policy_mode,
        "sequence_enforced": bool(package.sequence_enforced),
        "exam_gate_enforced": bool(package.exam_gate_enforced),
        "status": package.status,
        "revision_no": package.revision_no,
        "published_at": _iso(package.published_at),
        "archived_at": _iso(package.archived_at),
        "section_count": len(sections),
        "video_count": len(videos),
        "published_video_count": sum(
            1 for video in videos if video.status == "published" and video.is_current
        ),
        "created_at": _iso(package.created_at),
        "updated_at": _iso(package.updated_at),
    }
    if detail:
        result["sections"] = [_catalog_section_output(db, section) for section in sections]
    return result


def _ensure_catalog_seed(db: Session, user: User) -> int | None:
    """Idempotently create the requested package catalog in the current scope."""
    scope = _catalog_scope(db, user)
    changed = False
    for spec in REMOTE_CATALOG_PACKAGE_SPECS:
        scope_filter = (
            RemoteTrainingCatalogPackage.osgb_id.is_(None)
            if scope is None
            else RemoteTrainingCatalogPackage.osgb_id == scope
        )
        package = db.scalar(
            select(RemoteTrainingCatalogPackage).where(
                RemoteTrainingCatalogPackage.code == spec["code"], scope_filter
            )
        )
        if package is None:
            package = RemoteTrainingCatalogPackage(
                osgb_id=scope,
                code=spec["code"],
                title=spec["title"],
                description=spec["description"],
                training_type=REMOTE_TRAINING_TYPE,
                created_by_id=user.id,
            )
            db.add(package)
            db.flush()
            changed = True
        else:
            # Keep rows created by an earlier catalog draft aligned with the
            # approved package names without touching their videos or revisions.
            if package.title != spec["title"] or package.description != spec["description"]:
                package.title = spec["title"]
                package.description = spec["description"]
                changed = True
        existing_codes = set(
            db.scalars(
                select(RemoteTrainingCatalogSection.code).where(
                    RemoteTrainingCatalogSection.package_id == package.id
                )
            ).all()
        )
        for order, (code, title) in enumerate(spec["sections"], start=1):
            if code in existing_codes:
                continue
            db.add(
                RemoteTrainingCatalogSection(
                    package_id=package.id,
                    code=code,
                    title=title,
                    order_index=order,
                    created_by_id=user.id,
                )
            )
            changed = True
    if changed:
        _commit(db, "Merkezi eğitim paketleri oluşturulamadı.")
    return scope


@router.get("/meta")
def remote_training_meta(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _viewer(user)
    return {
        "enabled": feature_active(),
        "training_type": REMOTE_TRAINING_TYPE,
        "sector_catalog": [
            {"code": code, "label": label, "description": description}
            for code, label, description in REMOTE_SECTOR_CATALOG
        ],
        "program_statuses": list(PROGRAM_STATUSES),
        "video_statuses": list(VIDEO_STATUSES),
        "asset_types": list(ASSET_TYPES),
        "catalog_statuses": list(PROGRAM_STATUSES),
        "can_manage": is_manager(user),
        "can_view_employee_panel": bool(feature_active() and employee_access(db, user) is not None),
        "strict_policy": {
            "enabled": bool(getattr(settings, "remote_basic_ohs_strict_policy_enabled", False)),
            "force_off": bool(getattr(settings, "remote_basic_ohs_strict_policy_force_off", False)),
            "package_codes": sorted(remote_basic_ohs_strict_policy_package_codes()),
            "company_allowlist_configured": bool(
                str(getattr(settings, "remote_basic_ohs_strict_policy_pilot_company_ids", "") or "").strip()
            ),
        },
    }


@router.get("/catalog/packages")
def list_catalog_packages(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_feature()
    _manager(user)
    _ensure_catalog_seed(db, user)
    scope = _catalog_scope(db, user)
    stmt = select(RemoteTrainingCatalogPackage)
    allowed_codes = tuple(spec["code"] for spec in REMOTE_CATALOG_PACKAGE_SPECS)
    # Retired/experimental rows remain recoverable in the database, but the
    # preparation screen exposes only the approved package catalog.
    stmt = stmt.where(RemoteTrainingCatalogPackage.code.in_(allowed_codes))
    if user.role != UserRole.GLOBAL_ADMIN:
        stmt = stmt.where(RemoteTrainingCatalogPackage.osgb_id == scope)
    rows = db.scalars(
        stmt.order_by(RemoteTrainingCatalogPackage.code, RemoteTrainingCatalogPackage.id)
    ).all()
    # SQL ordering is intentionally not used for the user-facing catalog.  The
    # package specification order is the same order in which the administrator
    # prepares the content.
    order = {
        spec["code"]: index
        for index, spec in enumerate(REMOTE_CATALOG_PACKAGE_SPECS)
    }
    rows = sorted(rows, key=lambda row: (order.get(row.code, len(order)), row.id))
    return [_catalog_package_output(db, row) for row in rows]


@router.get("/catalog/packages/{package_id}")
def get_catalog_package(
    package_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    package = _catalog_package_for_manager(db, user, package_id)
    return _catalog_package_output(db, package, detail=True)


@router.post("/catalog/packages/{package_id}/materialize", status_code=201)
def materialize_catalog_package(
    package_id: int,
    payload: RemoteCatalogMaterialize,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Snapshot a published central package into one company's program.

    The company program owns its section/video rows after this operation.  A
    later catalog revision therefore cannot rewrite an employee's historical
    assignment or progress records.
    """
    package = _catalog_package_for_manager(db, user, package_id)
    if package.status != "published":
        raise HTTPException(409, "Yalnızca yayımlanmış merkezi paket firmaya hazırlanabilir.")
    ensure_company_access(db, user, payload.company_id)
    if not remote_basic_ohs_strict_policy_active(package.code, payload.company_id):
        raise HTTPException(
            409,
            "Bu paket merkezi katalogda yayımlandı; çalışanlara açılacak firma sürümü "
            "firma bazlı dağıtım politikası etkinleştirildiğinde hazırlanabilir.",
        )
    branch = validate_branch(db, payload.company_id, payload.branch_id)
    snapshot_branch_id = branch.id if branch else None
    company = db.get(Company, payload.company_id)
    if not company or not company.is_active:
        raise HTTPException(404, "Firma bulunamadı veya pasif.")
    existing_snapshot = db.scalar(
        select(RemoteTrainingProgram).where(
            RemoteTrainingProgram.company_id == company.id,
            RemoteTrainingProgram.source_catalog_package_id == package.id,
            RemoteTrainingProgram.source_catalog_revision_no == package.revision_no,
            RemoteTrainingProgram.branch_id == snapshot_branch_id,
            RemoteTrainingProgram.status != "archived",
        )
    )
    if existing_snapshot:
        raise HTTPException(
            409,
            f"Bu paket revizyonu firma için zaten hazırlandı (program #{existing_snapshot.id}).",
        )

    catalog_sections = list(
        db.scalars(
            select(RemoteTrainingCatalogSection)
            .where(
                RemoteTrainingCatalogSection.package_id == package.id,
                RemoteTrainingCatalogSection.status == "active",
            )
            .order_by(RemoteTrainingCatalogSection.order_index, RemoteTrainingCatalogSection.id)
        ).all()
    )
    if not catalog_sections:
        raise HTTPException(409, "Merkezi pakette aktif bölüm bulunmuyor.")

    automatic_exam_items: list[dict[str, Any]] = []
    if package.requires_final_exam:
        try:
            automatic_exam_items = automatic_exam_items_for_package(package.code)
        except RuntimeError as exc:
            # Fail closed if the reviewed content pack is damaged or incomplete;
            # never create a publishable program with guessed questions.
            raise HTTPException(
                409,
                f"{package.title} için otomatik final sınavı hazırlanamadı. "
                "Onaylı 10 soruluk paket eksik veya okunamıyor; rastgele soru üretilmedi. "
                "İçerik yöneticisi soru paketini düzeltmelidir.",
            ) from exc

    videos_by_section: dict[int, list[RemoteTrainingCatalogVideo]] = {}
    missing_required: list[str] = []
    for section in catalog_sections:
        rows = list(
            db.scalars(
                select(RemoteTrainingCatalogVideo)
                .where(
                    RemoteTrainingCatalogVideo.section_id == section.id,
                    RemoteTrainingCatalogVideo.status == "published",
                    RemoteTrainingCatalogVideo.is_current.is_(True),
                )
                .order_by(RemoteTrainingCatalogVideo.order_index, RemoteTrainingCatalogVideo.id)
            ).all()
        )
        videos_by_section[section.id] = rows
        if section.is_required and not rows:
            missing_required.append(section.code)
    if missing_required:
        raise HTTPException(
            409,
            "Yayımlanmış videosu olmayan zorunlu bölümler: " + ", ".join(missing_required),
        )

    program = RemoteTrainingProgram(
        osgb_id=company.osgb_id,
        company_id=company.id,
        branch_id=snapshot_branch_id,
        source_catalog_package_id=package.id,
        source_catalog_code=package.code,
        source_catalog_revision_no=package.revision_no,
        title=(payload.title or package.title).strip(),
        training_type=REMOTE_TRAINING_TYPE,
        description=package.description,
        instructor_name=payload.instructor_name,
        instructor_qualification=payload.instructor_qualification,
        completion_threshold_percent=int(package.completion_threshold_percent),
        passing_score=int(package.passing_score),
        attempt_limit=int(package.attempt_limit),
        requires_final_exam=bool(package.requires_final_exam),
        policy_mode=str(package.policy_mode or "strict"),
        sequence_enforced=bool(package.sequence_enforced),
        exam_gate_enforced=bool(package.exam_gate_enforced),
        created_by_id=user.id,
    )
    db.add(program)
    db.flush()
    catalog_sector_code = catalog_package_sector_code(package.code)
    for code, label, _description in REMOTE_SECTOR_CATALOG:
        db.add(
            RemoteTrainingProgramSector(
                osgb_id=program.osgb_id,
                company_id=program.company_id,
                program_id=program.id,
                sector_code=code,
                sector_name_snapshot=label,
                is_enabled=code == catalog_sector_code,
                created_by_id=user.id,
            )
        )

    copied_keys: list[str] = []
    store = get_object_store()
    try:
        for catalog_section in catalog_sections:
            section = RemoteTrainingSection(
                osgb_id=program.osgb_id,
                company_id=program.company_id,
                program_id=program.id,
                sector_code=catalog_sector_code,
                title=catalog_section.title,
                description=catalog_section.description,
                order_index=catalog_section.order_index,
                is_required=bool(catalog_section.is_required),
                created_by_id=user.id,
            )
            db.add(section)
            db.flush()
            for catalog_video in videos_by_section[catalog_section.id]:
                extension = Path(catalog_video.original_file_name or "video.mp4").suffix.lower() or ".mp4"
                target_key = storage_key(
                    company_id=program.company_id,
                    program_id=program.id,
                    prefix="video",
                    extension=extension,
                )
                store.put_bytes(target_key, store.get_bytes(catalog_video.storage_key))
                copied_keys.append(target_key)
                db.add(
                    RemoteTrainingVideo(
                        osgb_id=program.osgb_id,
                        company_id=program.company_id,
                        program_id=program.id,
                        section_id=section.id,
                        title=catalog_video.title,
                        description=catalog_video.description,
                        learning_objectives=catalog_video.learning_objectives,
                        order_index=catalog_video.order_index,
                        is_required=bool(catalog_video.is_required),
                        revision_no=catalog_video.revision_no,
                        is_current=True,
                        status="published",
                        original_file_name=catalog_video.original_file_name,
                        content_type=catalog_video.content_type,
                        file_size_bytes=catalog_video.file_size_bytes,
                        duration_seconds=catalog_video.duration_seconds,
                        width=catalog_video.width,
                        height=catalog_video.height,
                        codec=catalog_video.codec,
                        storage_key=target_key,
                        published_at=catalog_video.published_at or datetime.utcnow(),
                        created_by_id=user.id,
                    )
                )

        for position, item in enumerate(automatic_exam_items, start=1):
            options = item.get("options") or []
            db.add(
                RemoteTrainingQuestion(
                    osgb_id=program.osgb_id,
                    company_id=program.company_id,
                    program_id=program.id,
                    sector_code=catalog_sector_code,
                    question_text=str(item["question_text"]).strip(),
                    options_json=json.dumps(
                        {letter: str(options[index]).strip() for index, letter in enumerate("ABCD")},
                        ensure_ascii=False,
                    ),
                    correct_option=str(item["correct_option"]).upper(),
                    explanation=str(item["answer_explanation"]).strip(),
                    order_index=position,
                    is_required=False,
                    is_final_exam=True,
                    created_by_id=user.id,
                )
            )

        recalculate_program_duration(db, program.id)
        audit(
            db,
            company_id=program.company_id,
            user=user,
            action="catalog_package_materialized",
            entity_type="program",
            entity_id=program.id,
            details={"catalog_package_id": package.id, "catalog_code": package.code, "revision_no": package.revision_no},
        )
        _commit(db, "Merkezi paket firma programına hazırlanamadı.")
    except Exception:
        db.rollback()
        for key in copied_keys:
            try:
                store.delete(key)
            except Exception:
                logger.exception("Firma paket kopyası temizlenemedi: %s", key)
        raise
    return _program_detail(db, program)


@router.post("/catalog/packages/{package_id}/ready-for-review")
def mark_catalog_package_ready_for_review(
    package_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    package = _catalog_package_for_manager(db, user, package_id)
    if package.status in {"published", "archived"}:
        raise HTTPException(409, "Yayımlanmış veya arşivlenmiş paket incelemeye alınamaz.")
    sections = db.scalars(
        select(RemoteTrainingCatalogSection).where(
            RemoteTrainingCatalogSection.package_id == package.id,
            RemoteTrainingCatalogSection.status == "active",
        )
    ).all()
    if not sections:
        raise HTTPException(409, "İnceleme için pakete en az bir aktif bölüm ekleyin.")
    missing = []
    for section in sections:
        count = db.scalar(
            select(func.count(RemoteTrainingCatalogVideo.id)).where(
                RemoteTrainingCatalogVideo.section_id == section.id,
                RemoteTrainingCatalogVideo.status == "published",
                RemoteTrainingCatalogVideo.is_current.is_(True),
            )
        ) or 0
        if not count:
            missing.append(section.code)
    if missing:
        raise HTTPException(409, "Yayımlanmış videosu olmayan bölümler: " + ", ".join(missing))
    package.status = "ready_for_review"
    package.revision_no += 1
    _commit(db, "Merkezi paket incelemeye alınamadı.")
    return _catalog_package_output(db, package)


@router.post("/catalog/packages/{package_id}/publish")
def publish_catalog_package(
    package_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    package = _catalog_package_for_manager(db, user, package_id)
    if package.status == "archived":
        raise HTTPException(409, "Arşivlenmiş paket yayımlanamaz.")
    sections = db.scalars(
        select(RemoteTrainingCatalogSection).where(
            RemoteTrainingCatalogSection.package_id == package.id,
            RemoteTrainingCatalogSection.status == "active",
        )
    ).all()
    if not sections:
        raise HTTPException(409, "Yayın için pakete en az bir aktif bölüm ekleyin.")
    missing = []
    for section in sections:
        count = db.scalar(
            select(func.count(RemoteTrainingCatalogVideo.id)).where(
                RemoteTrainingCatalogVideo.section_id == section.id,
                RemoteTrainingCatalogVideo.status == "published",
                RemoteTrainingCatalogVideo.is_current.is_(True),
            )
        ) or 0
        if not count:
            missing.append(section.code)
    if missing:
        raise HTTPException(409, "Yayımlanmış videosu olmayan bölümler: " + ", ".join(missing))
    package.status = "published"
    package.published_at = datetime.utcnow()
    package.revision_no += 1
    _commit(db, "Merkezi paket yayımlanamadı.")
    return _catalog_package_output(db, package)


@router.post("/catalog/packages/{package_id}/unpublish")
def unpublish_catalog_package(
    package_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    package = _catalog_package_for_manager(db, user, package_id)
    if package.status == "archived":
        raise HTTPException(409, "Arşivlenmiş paket yayımdan kaldırılamaz.")
    package.status = "unpublished"
    package.published_at = None
    package.revision_no += 1
    _commit(db, "Merkezi paket yayımdan kaldırılamadı.")
    return _catalog_package_output(db, package)


@router.post("/catalog/packages/{package_id}/archive")
def archive_catalog_package(
    package_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    package = _catalog_package_for_manager(db, user, package_id)
    package.status = "archived"
    package.archived_at = datetime.utcnow()
    package.published_at = None
    _commit(db, "Merkezi paket arşivlenemedi.")
    return _catalog_package_output(db, package)


@router.post("/catalog/packages/{package_id}/sections", status_code=201)
def create_catalog_section(
    package_id: int,
    payload: RemoteCatalogSectionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    package = _catalog_package_for_manager(db, user, package_id)
    if package.status in {"published", "archived"}:
        raise HTTPException(409, "Yayımlanmış/arşivlenmiş pakete bölüm eklenemez.")
    order = payload.order_index
    if order is None:
        order = (
            db.scalar(
                select(func.max(RemoteTrainingCatalogSection.order_index)).where(
                    RemoteTrainingCatalogSection.package_id == package.id
                )
            )
            or 0
        ) + 1
    row = RemoteTrainingCatalogSection(
        package_id=package.id,
        code=payload.code.strip().upper(),
        title=payload.title.strip(),
        description=payload.description,
        order_index=order,
        is_required=payload.is_required,
        created_by_id=user.id,
    )
    db.add(row)
    _commit(db, "Merkezi eğitim bölümü oluşturulamadı; kod veya sıra numarası çakışabilir.")
    db.refresh(row)
    return _catalog_section_output(db, row)


@router.patch("/catalog/sections/{section_id}")
def update_catalog_section(
    section_id: int,
    payload: RemoteCatalogSectionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    section = _catalog_section_for_manager(db, user, section_id)
    package = _catalog_package_for_manager(db, user, section.package_id)
    if package.status in {"published", "archived"}:
        raise HTTPException(409, "Yayımlanmış/arşivlenmiş bölüm değiştirilemez.")
    values = payload.model_dump(exclude_unset=True)
    for key, value in values.items():
        if isinstance(value, str):
            value = value.strip().upper() if key == "code" else value.strip()
        setattr(section, key, value)
    _commit(db, "Merkezi eğitim bölümü güncellenemedi.")
    return _catalog_section_output(db, section)


@router.post("/catalog/sections/{section_id}/archive")
def archive_catalog_section(
    section_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    section = _catalog_section_for_manager(db, user, section_id)
    package = _catalog_package_for_manager(db, user, section.package_id)
    if package.status == "archived":
        raise HTTPException(409, "Arşivlenmiş paketin bölümü değiştirilemez.")
    section.status = "archived"
    _commit(db, "Merkezi eğitim bölümü arşivlenemedi.")
    return _catalog_section_output(db, section)


@router.post("/catalog/sections/{section_id}/videos", status_code=201)
async def upload_catalog_video(
    section_id: int,
    file: UploadFile = File(...),
    title: str = Form(..., min_length=2, max_length=220),
    description: str | None = Form(default=None, max_length=5000),
    learning_objectives: str | None = Form(default=None, max_length=5000),
    order_index: int = Form(default=1, ge=1),
    is_required: bool = Form(default=True),
    revision_of_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    section = _catalog_section_for_manager(db, user, section_id)
    package = _catalog_package_for_manager(db, user, section.package_id)
    if package.status == "archived" or section.status == "archived":
        raise HTTPException(409, "Arşivlenmiş pakete veya bölüme video yüklenemez.")
    if package.status == "published" and revision_of_id is None:
        raise HTTPException(409, "Yayımlanmış pakette mevcut videonun yanındaki yeni sürüm işlemini kullanın.")
    original_name = Path(file.filename or "video").name
    extension = Path(original_name).suffix.lower()
    max_bytes = max(1, int(settings.remote_basic_ohs_video_max_upload_mb)) * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(413, f"Video {settings.remote_basic_ohs_video_max_upload_mb} MB sınırını aşıyor.")
    validate_video_bytes(content, extension=extension, original_name=original_name)

    revision_of = None
    revision_no = 1
    is_current = True
    if revision_of_id is not None:
        revision_of = _catalog_video_for_manager(db, user, revision_of_id)
        if revision_of.package_id != package.id or revision_of.section_id != section.id:
            raise HTTPException(422, "Video revizyonu aynı paket ve bölüm içinde olmalıdır.")
        if not revision_of.is_current:
            raise HTTPException(409, "Yeni sürüm yalnızca bölümün güncel videosundan oluşturulabilir.")
        if package.status == "published" and revision_of.status != "published":
            raise HTTPException(409, "Yayımlanmış pakette yalnızca çalışanlara açık video güncellenebilir.")
        revision_no = revision_of.revision_no + 1
        is_current = False

    key = catalog_storage_key(package_id=package.id, prefix="video", extension=extension)
    store = None
    try:
        store = get_object_store()
        store.put_bytes(key, content)
        row = RemoteTrainingCatalogVideo(
            package_id=package.id,
            section_id=section.id,
            revision_of_id=revision_of.id if revision_of else None,
            title=title.strip(),
            description=description,
            learning_objectives=learning_objectives,
            order_index=order_index,
            is_required=is_required,
            revision_no=revision_no,
            is_current=is_current,
            status="uploading",
            original_file_name=original_name,
            content_type=(file.content_type or "application/octet-stream")[:120],
            file_size_bytes=len(content),
            storage_key=key,
            created_by_id=user.id,
        )
        db.add(row)
        db.flush()
        _commit(db, "Merkezi video kaydı oluşturulamadı.")
        job_id = enqueue_catalog_video_processing(db, row)
        row.processing_job_id = job_id
        db.commit()
        db.refresh(row)
        return _catalog_video_output(row)
    except HTTPException:
        if store is not None:
            try:
                store.delete(key)
            except Exception:
                pass
        raise
    except Exception as exc:
        db.rollback()
        if store is not None:
            try:
                store.delete(key)
            except Exception:
                pass
        raise HTTPException(500, "Merkezi video yüklenirken güvenli depolama işlemi tamamlanamadı.") from exc


@router.patch("/catalog/videos/{video_id}")
def update_catalog_video(
    video_id: int,
    payload: RemoteVideoUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    video = _catalog_video_for_manager(db, user, video_id)
    package = _catalog_package_for_manager(db, user, video.package_id)
    if package.status == "archived" or video.status in {"published", "unpublished", "archived"}:
        raise HTTPException(409, "Tarihsel video doğrudan değiştirilemez; yeni sürüm yükleyin.")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(video, key, value.strip() if isinstance(value, str) else value)
    _commit(db, "Merkezi video güncellenemedi.")
    return _catalog_video_output(video)


@router.delete("/catalog/videos/{video_id}")
def delete_catalog_video(
    video_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    video = _catalog_video_for_manager(db, user, video_id)
    package = _catalog_package_for_manager(db, user, video.package_id)
    if package.status == "archived":
        raise HTTPException(409, "Arşivlenmiş pakete ait video silinemez.")
    if video.status in {"published", "unpublished", "archived"}:
        raise HTTPException(409, "Yayımlanmış veya tarihsel video silinemez; yeni sürüm yükleyin.")
    if package.status == "published" and video.revision_of_id is None:
        raise HTTPException(409, "Yayımlanmış pakette yalnızca yeni sürüm adayı silinebilir.")
    key = video.storage_key
    db.delete(video)
    db.flush()
    recalculate_catalog_package_duration(db, package.id)
    _commit(db, "Merkezi video silinemedi.")
    cleanup_pending = False
    try:
        get_object_store().delete(key)
    except Exception:
        cleanup_pending = True
        logger.exception("Silinen katalog videosu temizlenemedi: video_id=%s", video_id)
    return {"deleted": True, "id": video_id, "storage_cleanup_pending": cleanup_pending}


@router.post("/catalog/videos/{video_id}/publish")
def publish_catalog_video(
    video_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    video = _catalog_video_for_manager(db, user, video_id)
    if video.status != "ready_for_review":
        raise HTTPException(409, "Video yalnızca incelemeye hazır durumdayken yayımlanabilir.")
    if not video.duration_seconds or not video.storage_key:
        raise HTTPException(409, "Video işleme süresi veya güvenli depolama kaydı eksik.")
    package = _catalog_package_for_manager(db, user, video.package_id)
    if package.status == "archived":
        raise HTTPException(409, "Arşivlenmiş pakete video yayımlanamaz.")
    current = db.scalars(
        select(RemoteTrainingCatalogVideo).where(
            RemoteTrainingCatalogVideo.package_id == video.package_id,
            RemoteTrainingCatalogVideo.section_id == video.section_id,
            RemoteTrainingCatalogVideo.is_current.is_(True),
            RemoteTrainingCatalogVideo.id != video.id,
            RemoteTrainingCatalogVideo.status == "published",
        )
    ).all()
    for old in current:
        old.is_current = False
        old.status = "unpublished"
    video.is_current = True
    video.status = "published"
    video.published_at = datetime.utcnow()
    recalculate_catalog_package_duration(db, video.package_id)
    _commit(db, "Merkezi video yayımlanamadı.")
    return _catalog_video_output(video)


@router.post("/catalog/videos/{video_id}/unpublish")
def unpublish_catalog_video(
    video_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    video = _catalog_video_for_manager(db, user, video_id)
    if video.status == "archived":
        raise HTTPException(409, "Arşivlenmiş video yayımdan kaldırılamaz.")
    video.status = "unpublished"
    video.published_at = None
    recalculate_catalog_package_duration(db, video.package_id)
    _commit(db, "Merkezi video yayımdan kaldırılamadı.")
    return _catalog_video_output(video)


@router.post("/catalog/videos/{video_id}/archive")
def archive_catalog_video(
    video_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    video = _catalog_video_for_manager(db, user, video_id)
    video.status = "archived"
    video.is_current = False
    video.archived_at = datetime.utcnow()
    recalculate_catalog_package_duration(db, video.package_id)
    _commit(db, "Merkezi video arşivlenemedi.")
    return _catalog_video_output(video)


@router.post("/catalog/videos/{video_id}/retry-processing")
def retry_catalog_video_processing(
    video_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    video = _catalog_video_for_manager(db, user, video_id)
    if video.status == "archived":
        raise HTTPException(409, "Arşivlenmiş video yeniden işlenemez.")
    video.status = "uploading"
    video.processing_error = None
    db.commit()
    job_id = enqueue_catalog_video_processing(db, video)
    video.processing_job_id = job_id
    db.commit()
    return _catalog_video_output(video)


@router.get("/catalog/videos/{video_id}/playback")
def create_catalog_playback(
    video_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    video = _catalog_video_for_manager(db, user, video_id)
    if video.status not in {"ready_for_review", "published", "unpublished"}:
        raise HTTPException(409, "Bu durumdaki video önizlenemez.")
    token = create_catalog_playback_token(user=user, video=video)
    ttl = max(60, min(int(settings.remote_basic_ohs_playback_ttl_seconds), 900))
    return {
        "video_id": video.id,
        "mode": "preview",
        "url": f"/api/v1/trainings/remote/catalog/videos/{video.id}/stream?token={token}",
        "expires_in_seconds": ttl,
    }


@router.get("/catalog/videos/{video_id}/stream")
def stream_catalog_video(
    video_id: int,
    token: str = Query(..., min_length=20),
    db: Session = Depends(get_db),
):
    require_feature()
    _user, video = decode_catalog_playback_token(db, token, video_id)
    response = response_for_video(video)
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@router.get("/programs")
def list_remote_programs(
    company_id: int | None = Query(default=None, gt=0),
    status: str | None = Query(default=None, max_length=32),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_feature()
    _manager(user)
    stmt = _program_query_for_user(db, user, company_id)
    if status:
        if status not in PROGRAM_STATUSES:
            raise HTTPException(422, "Geçersiz eğitim durumu.")
        stmt = stmt.where(RemoteTrainingProgram.status == status)
    rows = db.scalars(stmt.order_by(RemoteTrainingProgram.updated_at.desc())).all()
    return [_program_output(row) for row in rows]


@router.post("/programs", status_code=201)
def create_remote_program(
    payload: RemoteProgramCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_feature()
    _manager(user)
    ensure_company_access(db, user, payload.company_id)
    branch = None
    if payload.branch_id is not None:
        branch = db.get(Branch, payload.branch_id)
        if not branch or branch.company_id != payload.company_id or not branch.is_active:
            raise HTTPException(422, "Seçilen işyeri/şube firma ile uyumlu değil veya pasif.")
    company = db.get(Company, payload.company_id)
    row = RemoteTrainingProgram(
        osgb_id=company.osgb_id if company else None,
        company_id=payload.company_id,
        branch_id=payload.branch_id,
        title=payload.title.strip(),
        training_type=REMOTE_TRAINING_TYPE,
        description=payload.description,
        learning_objectives=payload.learning_objectives,
        instructor_name=payload.instructor_name,
        instructor_qualification=payload.instructor_qualification,
        completion_threshold_percent=payload.completion_threshold_percent,
        passing_score=payload.passing_score,
        attempt_limit=payload.attempt_limit,
        requires_final_exam=payload.requires_final_exam,
        created_by_id=user.id,
    )
    db.add(row)
    db.flush()
    for code, label, _description in REMOTE_SECTOR_CATALOG:
        db.add(
            RemoteTrainingProgramSector(
                osgb_id=row.osgb_id,
                company_id=row.company_id,
                program_id=row.id,
                sector_code=code,
                sector_name_snapshot=label,
                is_enabled=code == "common",
                created_by_id=user.id,
            )
        )
    audit(db, company_id=row.company_id, user=user, action="program_created", entity_type="program", entity_id=row.id)
    _commit(db, "Uzaktan eğitim oluşturulamadı; kayıt çakışması oluştu.")
    db.refresh(row)
    return _program_output(row)


@router.get("/programs/{program_id}/sectors")
def list_remote_program_sectors(
    program_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    program = _assert_program_manager(db, user, program_id)
    return build_program_sector_catalog(db, program)


@router.put("/programs/{program_id}/sectors")
def update_remote_program_sectors(
    program_id: int,
    payload: RemoteProgramSectorUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    program = _assert_program_manager(db, user, program_id)
    if program.status in {"published", "archived"}:
        raise HTTPException(409, "Yayımlanmış/arşivlenmiş eğitimde sektör kapsamı değiştirilemez.")
    requested = {validate_sector_code(code) for code in payload.sector_codes}
    if not requested:
        raise HTTPException(422, "En az bir sektör/ders kapsamı seçilmelidir.")
    unknown = requested - {code for code, _label, _description in REMOTE_SECTOR_CATALOG}
    if unknown:
        raise HTTPException(422, "Sektör kapsamı katalogda bulunmayan bir kod içeriyor.")
    catalog_sector_code = catalog_program_sector_code(program)
    if catalog_sector_code is not None and requested != {catalog_sector_code}:
        raise HTTPException(
            422,
            "Bu firma eğitimi merkezi katalogdan hazırlanmıştır; yalnızca "
            f"{sector_label(catalog_sector_code)} kapsamı seçilebilir. "
            "Farklı eğitim için ilgili merkezi paketi firmaya hazırlayın.",
        )
    assignment_count = db.scalar(
        select(func.count(RemoteTrainingAssignment.id)).where(
            RemoteTrainingAssignment.program_id == program.id
        )
    ) or 0
    if assignment_count:
        raise HTTPException(
            409,
            "Atama yapılmış eğitimde sektör kapsamı değiştirilemez; mevcut çalışan kayıtları korunmalıdır.",
        )
    rows = {
        row.sector_code: row
        for row in db.scalars(
            select(RemoteTrainingProgramSector).where(
                RemoteTrainingProgramSector.program_id == program.id
            )
        ).all()
    }
    for code, label, _description in REMOTE_SECTOR_CATALOG:
        row = rows.get(code)
        if row is None:
            row = RemoteTrainingProgramSector(
                osgb_id=program.osgb_id,
                company_id=program.company_id,
                program_id=program.id,
                sector_code=code,
                sector_name_snapshot=label,
                created_by_id=user.id,
            )
            db.add(row)
        row.sector_name_snapshot = label
        row.is_enabled = code in requested
        row.updated_at = datetime.utcnow()
    audit(
        db,
        company_id=program.company_id,
        user=user,
        action="program_sector_scope_updated",
        entity_type="program_sector_scope",
        entity_id=program.id,
        details={"sector_codes": sorted(requested), "ip": request.client.host if request.client else None},
    )
    _commit(db, "Firma ders kapsamı kaydedilemedi.")
    return build_program_sector_catalog(db, program)


@router.get("/programs/{program_id}")
def get_remote_program(
    program_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_feature()
    _manager(user)
    program = load_program(db, program_id)
    assert_program_access(db, user, program)
    return _program_detail(db, program)


@router.patch("/programs/{program_id}")
def update_remote_program(
    program_id: int,
    payload: RemoteProgramUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    program = _assert_program_manager(db, user, program_id)
    if program.status in {"published", "archived"}:
        raise HTTPException(409, "Yayımlanmış/arşivlenmiş eğitim önce taslak akışına alınmalıdır.")
    values = payload.model_dump(exclude_unset=True)
    if str(getattr(program, "policy_mode", "legacy") or "legacy") == "strict":
        if values.get("completion_threshold_percent", program.completion_threshold_percent) < 100:
            raise HTTPException(422, "Sektör eğitimlerinde video tamamlanma eşiği %100 olmalıdır.")
        if values.get("passing_score", program.passing_score) < 70:
            raise HTTPException(422, "Sektör eğitimlerinde geçme puanı en az %70 olmalıdır.")
        if values.get("requires_final_exam", program.requires_final_exam) is False:
            raise HTTPException(422, "Sektör eğitimlerinde final sınavı zorunludur.")
    if "branch_id" in values and values["branch_id"] is not None:
        branch = db.get(Branch, values["branch_id"])
        if not branch or branch.company_id != program.company_id or not branch.is_active:
            raise HTTPException(422, "Seçilen işyeri/şube firma ile uyumlu değil veya pasif.")
    for key, value in values.items():
        setattr(program, key, value.strip() if isinstance(value, str) else value)
    program.training_type = REMOTE_TRAINING_TYPE
    program.revision_no += 1
    audit(db, company_id=program.company_id, user=user, action="program_updated", entity_type="program", entity_id=program.id)
    _commit(db, "Uzaktan eğitim güncellenemedi; kayıt çakışması oluştu.")
    db.refresh(program)
    return _program_output(program)


@router.post("/programs/{program_id}/ready-for-review")
def mark_program_ready_for_review(
    program_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    program = _assert_program_manager(db, user, program_id)
    if program.status in {"published", "archived"}:
        raise HTTPException(409, "Bu eğitim taslak incelemesine alınamaz.")
    program.status = "ready_for_review"
    audit(db, company_id=program.company_id, user=user, action="program_ready_for_review", entity_type="program", entity_id=program.id)
    _commit(db, "Eğitim incelemeye alınamadı.")
    return _program_output(program)


@router.post("/programs/{program_id}/publish")
def publish_remote_program(
    program_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    program = _assert_program_manager(db, user, program_id)
    require_strict_policy_active(program)
    if program.status == "archived":
        raise HTTPException(409, "Arşivlenmiş eğitim yayımlanamaz.")
    active_sections = db.scalar(
        select(func.count(RemoteTrainingSection.id)).where(
            RemoteTrainingSection.program_id == program.id,
            RemoteTrainingSection.status == "active",
        )
    ) or 0
    published_videos = db.scalar(
        select(func.count(RemoteTrainingVideo.id)).where(
            RemoteTrainingVideo.program_id == program.id,
            RemoteTrainingVideo.status == "published",
            RemoteTrainingVideo.is_current.is_(True),
        )
    ) or 0
    if not active_sections or not published_videos:
        raise HTTPException(409, "Yayın için en az bir aktif bölüm ve yayımlanmış video gerekir.")
    if strict_policy_active(program):
        incomplete_sections = []
        for section in db.scalars(
            select(RemoteTrainingSection).where(
                RemoteTrainingSection.program_id == program.id,
                RemoteTrainingSection.status == "active",
            )
        ).all():
            has_required_video = db.scalar(
                select(func.count(RemoteTrainingVideo.id)).where(
                    RemoteTrainingVideo.program_id == program.id,
                    RemoteTrainingVideo.section_id == section.id,
                    RemoteTrainingVideo.status == "published",
                    RemoteTrainingVideo.is_current.is_(True),
                )
            ) or 0
            if not has_required_video:
                incomplete_sections.append(section.title)
        if incomplete_sections:
            raise HTTPException(
                409,
                "Sektör eğitim paketinde her aktif bölüm için yayımlanmış bir video gerekir: "
                + ", ".join(incomplete_sections),
            )
    sector_scope = program_sector_codes(db, program.id)
    if sector_scope is not None:
        missing_content = []
        for sector_code in sorted(sector_scope):
            has_video = db.scalar(
                select(func.count(RemoteTrainingVideo.id))
                .join(RemoteTrainingSection, RemoteTrainingSection.id == RemoteTrainingVideo.section_id)
                .where(
                    RemoteTrainingVideo.program_id == program.id,
                    RemoteTrainingVideo.status == "published",
                    RemoteTrainingVideo.is_current.is_(True),
                    RemoteTrainingSection.status == "active",
                    RemoteTrainingSection.sector_code == sector_code,
                )
            ) or 0
            if not has_video:
                missing_content.append(sector_label(sector_code))
        if missing_content:
            raise HTTPException(
                409,
                "Seçilen sektörlerde yayımlanmış video bulunmuyor: " + ", ".join(missing_content),
            )
    if program.requires_final_exam:
        automatic_exam_questions = db.scalars(
            select(RemoteTrainingQuestion).where(
                RemoteTrainingQuestion.program_id == program.id,
                RemoteTrainingQuestion.is_final_exam.is_(True),
            )
        ).all()
        exam_links = db.scalars(
            select(RemoteTrainingProgramQuestion).where(
                RemoteTrainingProgramQuestion.program_id == program.id
            )
        ).all()
        if strict_policy_active(program) and (
            automatic_exam_questions or program.source_catalog_code
        ):
            validation_errors = _automatic_final_exam_validation(automatic_exam_questions)
            if validation_errors:
                raise HTTPException(
                    409,
                    "Otomatik final sınavı yayımlanamıyor: " + " ".join(validation_errors),
                )
        elif not exam_links:
            raise HTTPException(409, "Final sınavı açıkken mevcut soru bankasından en az bir soru bağlanmalıdır.")
        incompatible_questions = [
            str(link.question_id)
            for link in exam_links
            if not catalog_question_is_compatible(db, program, link.question_id)
        ]
        if incompatible_questions:
            raise HTTPException(
                409,
                "Sınavda eğitim kapsamıyla uyumsuz soru var (ID: "
                + ", ".join(incompatible_questions)
                + "). Bu soruyu sınavdan çıkarıp ilgili kapsam sorusunu bağlayın.",
            )
        scope = program_sector_codes(db, program.id)
        if scope is not None and not automatic_exam_questions:
            linked_codes = {link.sector_code or "common" for link in exam_links}
            missing_codes = sorted(scope - linked_codes)
            if missing_codes:
                raise HTTPException(
                    409,
                    "Seçilen her sektör için en az bir final sınavı sorusu bağlanmalıdır: "
                    + ", ".join(sector_label(code) for code in missing_codes),
                )
    program.status = "published"
    program.published_at = datetime.utcnow()
    audit(db, company_id=program.company_id, user=user, action="program_published", entity_type="program", entity_id=program.id)
    _commit(db, "Uzaktan eğitim yayımlanamadı.")
    return _program_output(program)


@router.post("/programs/{program_id}/unpublish")
def unpublish_remote_program(
    program_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    program = _assert_program_manager(db, user, program_id)
    if program.status == "archived":
        raise HTTPException(409, "Arşivlenmiş eğitim yayımdan kaldırılamaz.")
    program.status = "unpublished"
    program.published_at = None
    audit(db, company_id=program.company_id, user=user, action="program_unpublished", entity_type="program", entity_id=program.id)
    _commit(db, "Uzaktan eğitim yayımdan kaldırılamadı.")
    return _program_output(program)


@router.post("/programs/{program_id}/archive")
def archive_remote_program(
    program_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    program = _assert_program_manager(db, user, program_id)
    program.status = "archived"
    program.archived_at = datetime.utcnow()
    program.published_at = None
    audit(db, company_id=program.company_id, user=user, action="program_archived", entity_type="program", entity_id=program.id)
    _commit(db, "Uzaktan eğitim arşivlenemedi.")
    return _program_output(program)


@router.post("/programs/{program_id}/sections", status_code=201)
def create_remote_section(
    program_id: int,
    payload: RemoteSectionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    program = _assert_program_manager(db, user, program_id)
    if program.status in {"published", "archived"}:
        raise HTTPException(409, "Yayımlanmış/arşivlenmiş eğitime bölüm eklenemez.")
    order = payload.order_index
    if order is None:
        order = (db.scalar(select(func.max(RemoteTrainingSection.order_index)).where(RemoteTrainingSection.program_id == program.id)) or 0) + 1
    sector_code = validate_catalog_program_sector(
        program, validate_sector_code(payload.sector_code)
    )
    row = RemoteTrainingSection(
        osgb_id=program.osgb_id,
        company_id=program.company_id,
        program_id=program.id,
        sector_code=sector_code,
        title=payload.title.strip(),
        description=payload.description,
        learning_objectives=payload.learning_objectives,
        order_index=order,
        is_required=payload.is_required,
        created_by_id=user.id,
    )
    db.add(row)
    db.flush()
    audit(db, company_id=program.company_id, user=user, action="section_created", entity_type="section", entity_id=row.id)
    _commit(db, "Bölüm oluşturulamadı; sıra numarası çakışması olabilir.")
    return {
        "id": row.id,
        "program_id": row.program_id,
        "sector_code": row.sector_code,
        "title": row.title,
        "description": row.description,
        "learning_objectives": row.learning_objectives,
        "order_index": row.order_index,
        "is_required": row.is_required,
        "status": row.status,
        "videos": [],
    }


@router.patch("/sections/{section_id}")
def update_remote_section(
    section_id: int,
    payload: RemoteSectionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    section = _assert_section_manager(db, user, section_id)
    program = load_program(db, section.program_id)
    if program.status in {"published", "archived"}:
        raise HTTPException(409, "Yayımlanmış/arşivlenmiş bölüm değiştirilemez.")
    values = payload.model_dump(exclude_unset=True)
    if "sector_code" in values:
        values["sector_code"] = validate_catalog_program_sector(
            program, validate_sector_code(values["sector_code"])
        )
        if values["sector_code"] != section.sector_code:
            question_count = db.scalar(
                select(func.count(RemoteTrainingQuestion.id)).where(
                    RemoteTrainingQuestion.section_id == section.id
                )
            ) or 0
            if question_count:
                raise HTTPException(
                    409,
                    "Video içi sorusu bulunan bölümün sektörü değiştirilemez; soruları önce yeniden tanımlayın.",
                )
    for key, value in values.items():
        setattr(section, key, value.strip() if isinstance(value, str) else value)
    audit(db, company_id=section.company_id, user=user, action="section_updated", entity_type="section", entity_id=section.id)
    _commit(db, "Bölüm güncellenemedi; sıra numarası çakışması olabilir.")
    return _section_output(db, section)


@router.post("/sections/{section_id}/archive")
def archive_remote_section(
    section_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    section = _assert_section_manager(db, user, section_id)
    section.status = "archived"
    audit(db, company_id=section.company_id, user=user, action="section_archived", entity_type="section", entity_id=section.id)
    _commit(db, "Bölüm arşivlenemedi.")
    return {"id": section.id, "status": section.status}


@router.post("/sections/{section_id}/videos", status_code=201)
async def upload_remote_video(
    section_id: int,
    file: UploadFile = File(...),
    title: str = Form(..., min_length=2, max_length=220),
    description: str | None = Form(default=None, max_length=5000),
    learning_objectives: str | None = Form(default=None, max_length=5000),
    order_index: int = Form(default=1, ge=1),
    is_required: bool = Form(default=True),
    revision_of_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    section = _assert_section_manager(db, user, section_id)
    program = load_program(db, section.program_id)
    if program.status == "archived":
        raise HTTPException(409, "Arşivlenmiş eğitime video yüklenemez.")
    if program.status == "published" and revision_of_id is None:
        raise HTTPException(
            409,
            "Yayımlanmış eğitimde mevcut videonun yanındaki 'Yeni sürüm yükle' işlemi kullanılmalıdır.",
        )
    original_name = Path(file.filename or "video").name
    extension = Path(original_name).suffix.lower()
    max_bytes = max(1, int(settings.remote_basic_ohs_video_max_upload_mb)) * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(413, f"Video {settings.remote_basic_ohs_video_max_upload_mb} MB sınırını aşıyor.")
    validate_video_bytes(content, extension=extension, original_name=original_name)

    revision_of = None
    revision_no = 1
    is_current = True
    if revision_of_id is not None:
        revision_of = load_video(db, revision_of_id)
        if revision_of.program_id != program.id or revision_of.section_id != section.id:
            raise HTTPException(422, "Video revizyonu aynı program ve bölüm içinde olmalıdır.")
        if not revision_of.is_current:
            raise HTTPException(409, "Yeni sürüm yalnızca bölümün güncel videosundan oluşturulabilir.")
        if program.status == "published" and revision_of.status != "published":
            raise HTTPException(409, "Yayımlanmış eğitimde yalnızca çalışanlara açık güncel video güncellenebilir.")
        revision_no = revision_of.revision_no + 1
        is_current = False
    key = storage_key(company_id=program.company_id, program_id=program.id, prefix="video", extension=extension)
    store = None
    try:
        from app.services.object_store import get_object_store

        store = get_object_store()
        store.put_bytes(key, content)
        row = RemoteTrainingVideo(
            osgb_id=program.osgb_id,
            company_id=program.company_id,
            program_id=program.id,
            section_id=section.id,
            revision_of_id=revision_of.id if revision_of else None,
            title=title.strip(),
            description=description,
            learning_objectives=learning_objectives,
            order_index=order_index,
            is_required=is_required,
            revision_no=revision_no,
            is_current=is_current,
            status="uploading",
            original_file_name=original_name,
            content_type=(file.content_type or "application/octet-stream")[:120],
            file_size_bytes=len(content),
            storage_key=key,
            created_by_id=user.id,
        )
        db.add(row)
        db.flush()
        audit(db, company_id=program.company_id, user=user, action="video_uploaded", entity_type="video", entity_id=row.id, details={"revision_of_id": revision_of_id, "bytes": len(content)})
        _commit(db, "Video kaydı oluşturulamadı.")
        # Commit before queueing: sync workers use a separate DB session.
        job_id = enqueue_video_processing(db, row)
        row.processing_job_id = job_id
        db.commit()
        db.refresh(row)
        return _video_output(row)
    except HTTPException:
        if store is not None:
            try:
                store.delete(key)
            except Exception:
                pass
        raise
    except Exception as exc:
        db.rollback()
        if store is not None:
            try:
                store.delete(key)
            except Exception:
                pass
        raise HTTPException(500, "Video yüklenirken güvenli depolama işlemi tamamlanamadı.") from exc


@router.patch("/videos/{video_id}")
def update_remote_video(
    video_id: int,
    payload: RemoteVideoUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    video = _assert_video_manager(db, user, video_id)
    program = load_program(db, video.program_id)
    if program.status == "archived" or video.status in {"published", "unpublished", "archived"}:
        raise HTTPException(409, "Arşivlenmiş veya tarihsel video değiştirilemez; güncelleme için yeni sürüm oluşturun.")
    if program.status == "published" and video.revision_of_id is None:
        raise HTTPException(409, "Yayımlanmış video doğrudan değiştirilemez; yanındaki yeni sürüm işlemini kullanın.")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(video, key, value.strip() if isinstance(value, str) else value)
    audit(db, company_id=video.company_id, user=user, action="video_updated", entity_type="video", entity_id=video.id)
    _commit(db, "Video güncellenemedi.")
    return _video_output(video)


@router.delete("/videos/{video_id}")
def delete_remote_video(
    video_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete an accidental upload while preserving published video history."""
    video = _assert_video_manager(db, user, video_id)
    program = load_program(db, video.program_id)
    if program.status == "archived":
        raise HTTPException(409, "Arşivlenmiş eğitime ait video silinemez.")
    if video.status in {"published", "unpublished", "archived"}:
        raise HTTPException(409, "Yayımlanmış veya tarihsel video silinemez; yeni video revizyonu oluşturun.")
    if program.status == "published" and video.revision_of_id is None:
        raise HTTPException(409, "Yayımlanmış eğitimde yalnızca yeni sürüm adayı silinebilir.")

    program_id = video.program_id
    storage_key = video.storage_key
    original_status = video.status
    audit(
        db,
        company_id=video.company_id,
        user=user,
        action="video_deleted",
        entity_type="video",
        entity_id=video.id,
        details={"status": original_status, "storage_key": storage_key},
    )
    db.delete(video)
    db.flush()
    recalculate_program_duration(db, program_id)
    _commit(db, "Video silinemedi.")

    storage_cleanup_pending = False
    try:
        get_object_store().delete(storage_key)
    except Exception:
        # The database deletion is authoritative; retain an operational signal
        # so an orphaned object can be cleaned by the storage maintenance job.
        storage_cleanup_pending = True
        logger.exception("Silinen remote video nesnesi temizlenemedi: video_id=%s", video_id)
    return {
        "deleted": True,
        "id": video_id,
        "storage_cleanup_pending": storage_cleanup_pending,
    }


@router.post("/videos/{video_id}/publish")
def publish_remote_video(
    video_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    video = _assert_video_manager(db, user, video_id)
    if video.status != "ready_for_review":
        raise HTTPException(409, "Video yalnızca incelemeye hazır durumdayken yayımlanabilir.")
    if not video.duration_seconds or not video.storage_key:
        raise HTTPException(409, "Video işleme süresi veya güvenli depolama kaydı eksik.")
    program = load_program(db, video.program_id)
    if program.status == "archived":
        raise HTTPException(409, "Arşivlenmiş programa video yayımlanamaz.")
    current = db.scalars(
        select(RemoteTrainingVideo).where(
            RemoteTrainingVideo.program_id == video.program_id,
            RemoteTrainingVideo.section_id == video.section_id,
            RemoteTrainingVideo.is_current.is_(True),
            RemoteTrainingVideo.id != video.id,
            RemoteTrainingVideo.status == "published",
        )
    ).all()
    for old in current:
        old.is_current = False
        old.status = "unpublished"
    video.is_current = True
    video.status = "published"
    video.published_at = datetime.utcnow()
    recalculate_program_duration(db, video.program_id)
    audit(db, company_id=video.company_id, user=user, action="video_published", entity_type="video", entity_id=video.id)
    _commit(db, "Video yayımlanamadı.")
    return _video_output(video)


@router.post("/videos/{video_id}/unpublish")
def unpublish_remote_video(
    video_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    video = _assert_video_manager(db, user, video_id)
    if video.status == "archived":
        raise HTTPException(409, "Arşivlenmiş video yayımdan kaldırılamaz.")
    video.status = "unpublished"
    video.published_at = None
    recalculate_program_duration(db, video.program_id)
    audit(db, company_id=video.company_id, user=user, action="video_unpublished", entity_type="video", entity_id=video.id)
    _commit(db, "Video yayımdan kaldırılamadı.")
    return _video_output(video)


@router.post("/videos/{video_id}/archive")
def archive_remote_video(
    video_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    video = _assert_video_manager(db, user, video_id)
    video.status = "archived"
    video.is_current = False
    video.archived_at = datetime.utcnow()
    recalculate_program_duration(db, video.program_id)
    audit(db, company_id=video.company_id, user=user, action="video_archived", entity_type="video", entity_id=video.id)
    _commit(db, "Video arşivlenemedi.")
    return _video_output(video)


@router.post("/videos/{video_id}/retry-processing")
def retry_remote_video_processing(
    video_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    video = _assert_video_manager(db, user, video_id)
    if video.status == "archived":
        raise HTTPException(409, "Arşivlenmiş video yeniden işlenemez.")
    video.status = "uploading"
    video.processing_error = None
    db.commit()
    job_id = enqueue_video_processing(db, video)
    video.processing_job_id = job_id
    db.commit()
    return _video_output(video)


@router.post("/videos/{video_id}/assets", status_code=201)
async def upload_remote_asset(
    video_id: int,
    asset_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    video = _assert_video_manager(db, user, video_id)
    original_name = Path(file.filename or "asset").name
    extension = Path(original_name).suffix.lower()
    max_bytes = min(max(1, int(settings.max_upload_mb)), 64) * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(413, "Ek dosyası boyut sınırını aşıyor.")
    _safe_asset_content(asset_type, extension, content)
    from app.services.object_store import get_object_store

    key = storage_key(company_id=video.company_id, program_id=video.program_id, prefix=f"asset-{asset_type}", extension=extension)
    store = get_object_store()
    store.put_bytes(key, content)
    row = RemoteTrainingAsset(
        osgb_id=video.osgb_id,
        company_id=video.company_id,
        program_id=video.program_id,
        video_id=video.id,
        asset_type=asset_type,
        original_file_name=original_name,
        content_type=(file.content_type or "application/octet-stream")[:120],
        file_size_bytes=len(content),
        storage_key=key,
        created_by_id=user.id,
    )
    db.add(row)
    db.flush()
    audit(db, company_id=video.company_id, user=user, action="asset_uploaded", entity_type="asset", entity_id=row.id, details={"asset_type": asset_type, "video_id": video.id})
    try:
        db.commit()
    except Exception:
        db.rollback()
        try:
            store.delete(key)
        except Exception:
            pass
        raise HTTPException(409, "Video eki kaydedilemedi.")
    return _asset_output(row)


@router.get("/videos/{video_id}/assets/{asset_id}")
def download_remote_asset(
    video_id: int,
    asset_id: int,
    assignment_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_feature()
    asset = db.get(RemoteTrainingAsset, asset_id)
    if not asset or asset.video_id != video_id:
        raise HTTPException(404, "Video eki bulunamadı.")
    video = load_video(db, video_id)
    if is_manager(user):
        assert_program_access(db, user, load_program(db, video.program_id))
    else:
        if not assignment_id:
            raise HTTPException(403, "Çalışan video eki için atama bilgisi gerekir.")
        assignment = load_assignment(db, assignment_id)
        assert_assignment_access(db, user, assignment)
        if assignment.program_id != video.program_id or video.status != "published" or not video.is_current:
            raise HTTPException(403, "Video eki çalışana açık değil.")
        section = load_section(db, video.section_id)
        if not assignment_allows_sector(db, assignment, section.sector_code):
            raise HTTPException(403, "Video eki bu çalışanın ders kapsamına dahil değil.")
    from app.services.stored_files import response_for_storage_key

    return response_for_storage_key(asset.storage_key, filename=asset.original_file_name, media_type=asset.content_type)


@router.get("/videos/{video_id}/playback")
def create_remote_playback(
    video_id: int,
    assignment_id: int | None = Query(default=None, gt=0),
    preview: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_feature()
    video = load_video(db, video_id)
    program = load_program(db, video.program_id)
    mode = "preview" if preview else "employee"
    if preview:
        if not is_manager(user):
            raise HTTPException(403, "Önizleme yetkiniz yok.")
        assert_program_access(db, user, program)
        if video.status not in {"ready_for_review", "published", "unpublished"}:
            raise HTTPException(409, "Bu durumdaki video önizlenemez.")
        assignment_id = None
    else:
        if assignment_id is None:
            raise HTTPException(422, "Çalışan oynatması için atama seçilmelidir.")
        assignment = load_assignment(db, assignment_id)
        assert_assignment_access(db, user, assignment)
        require_strict_policy_active(program)
        if assignment.program_id != program.id:
            raise HTTPException(403, "Video bu atamaya bağlı değil.")
        section = load_section(db, video.section_id)
        if not assignment_allows_sector(db, assignment, section.sector_code):
            raise HTTPException(403, "Video bu çalışanın ders kapsamına dahil değil.")
        assert_video_unlocked(db, assignment, video)
        if program.status != "published" or video.status != "published" or not video.is_current:
            raise HTTPException(403, "Video henüz çalışana açık değil.")
    token = create_playback_token(user=user, video=video, assignment_id=assignment_id, mode=mode)
    ttl = max(60, min(int(settings.remote_basic_ohs_playback_ttl_seconds), 900))
    return {
        "video_id": video.id,
        "assignment_id": assignment_id,
        "mode": mode,
        "url": f"/api/v1/trainings/remote/videos/{video.id}/stream?token={token}",
        "expires_in_seconds": ttl,
    }


@router.get("/videos/{video_id}/stream")
def stream_remote_video(
    video_id: int,
    token: str = Query(..., min_length=20),
    db: Session = Depends(get_db),
):
    require_feature()
    _user, video, _assignment_id, _mode = decode_playback_token(db, token, video_id)
    response = response_for_video(video)
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@router.post("/programs/{program_id}/assign")
def assign_remote_program(
    program_id: int,
    payload: RemoteAssignmentCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    program = _assert_program_manager(db, user, program_id)
    if program.status != "published":
        raise HTTPException(409, "Yalnızca yayımlanmış eğitim çalışanlara atanabilir.")
    require_strict_policy_active(program)
    sector_codes = program_sector_codes(db, program.id)
    branch_id = payload.branch_id or program.branch_id
    if payload.branch_id and program.branch_id and payload.branch_id != program.branch_id:
        raise HTTPException(422, "Atama işyeri/şubesi programın işyeri/şubesi ile aynı olmalıdır.")
    if branch_id is not None:
        branch = db.get(Branch, branch_id)
        if not branch or branch.company_id != program.company_id or not branch.is_active:
            raise HTTPException(422, "Atama işyeri/şubesi firma ile uyumlu değil veya pasif.")
    employees = list(
        db.scalars(
            select(Employee).where(
                Employee.id.in_(payload.employee_ids),
                Employee.company_id == program.company_id,
                Employee.is_active.is_(True),
            )
        ).all()
    )
    found = {employee.id for employee in employees}
    missing = [employee_id for employee_id in payload.employee_ids if employee_id not in found]
    if missing:
        raise HTTPException(422, "Seçilen çalışanlardan bazıları firma dışı, pasif veya bulunamadı.")
    if strict_policy_active(program):
        mapped_employee_ids = {
            int(employee_id)
            for employee_id in db.scalars(
                select(RemoteTrainingEmployeeAccess.employee_id).where(
                    RemoteTrainingEmployeeAccess.company_id == program.company_id,
                    RemoteTrainingEmployeeAccess.employee_id.in_(payload.employee_ids),
                    RemoteTrainingEmployeeAccess.is_active.is_(True),
                )
            ).all()
        }
        without_login = sorted(set(payload.employee_ids) - mapped_employee_ids)
        if without_login:
            raise HTTPException(
                409,
                "Atama için önce seçilen çalışanların aktif giriş hesabı oluşturulup eşlenmelidir: "
                + ", ".join(str(item) for item in without_login),
            )
    created: list[RemoteTrainingAssignment] = []
    skipped: list[int] = []
    for employee in employees:
        employee_branch_id = branch_id or employee.branch_id
        if branch_id and employee.branch_id != branch_id:
            raise HTTPException(422, f"{employee.full_name} seçilen işyerine bağlı değil.")
        existing = db.scalar(
            select(RemoteTrainingAssignment).where(
                RemoteTrainingAssignment.program_id == program.id,
                RemoteTrainingAssignment.employee_id == employee.id,
            )
        )
        if existing:
            skipped.append(employee.id)
            continue
        snapshot = company_snapshot(db, program.company_id, employee_branch_id)
        row = RemoteTrainingAssignment(
            osgb_id=program.osgb_id,
            company_id=program.company_id,
            branch_id=employee_branch_id,
            program_id=program.id,
            employee_id=employee.id,
            workplace_name_snapshot=snapshot["workplace_name"],
            sgk_registration_number_snapshot=snapshot["sgk_registration_number"],
            nace_code_snapshot=snapshot["nace_code"],
            nace_description_snapshot=snapshot["nace_description"],
            hazard_class_snapshot=snapshot["hazard_class"],
            employee_name_snapshot=employee.full_name,
            due_date=payload.due_date,
            assigned_by_id=user.id,
        )
        db.add(row)
        db.flush()
        if sector_codes is not None:
            for sector_code in sorted(sector_codes):
                db.add(
                    RemoteTrainingAssignmentSector(
                        osgb_id=program.osgb_id,
                        company_id=program.company_id,
                        program_id=program.id,
                        assignment_id=row.id,
                        employee_id=employee.id,
                        sector_code=sector_code,
                        sector_name_snapshot=sector_label(sector_code),
                        created_by_id=user.id,
                    )
                )
        created.append(row)
    audit(
        db,
        company_id=program.company_id,
        user=user,
        action="program_assigned",
        entity_type="program",
        entity_id=program.id,
        details={
            "created": len(created),
            "skipped": skipped,
            "sector_codes": sorted(sector_codes) if sector_codes is not None else None,
            "ip": request.client.host if request.client else None,
        },
    )
    _commit(db, "Çalışan ataması kaydedilemedi; işlem geri alındı.")
    return {
        "program_id": program.id,
        "created": [_assignment_output(db, row) for row in created],
        "created_count": len(created),
        "skipped_employee_ids": skipped,
    }


@router.get("/programs/{program_id}/assignments")
def list_remote_assignments(
    program_id: int,
    status: str | None = Query(default=None, max_length=24),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    program = _assert_program_manager(db, user, program_id)
    stmt = select(RemoteTrainingAssignment).where(RemoteTrainingAssignment.program_id == program.id)
    if status:
        stmt = stmt.where(RemoteTrainingAssignment.status == status)
    rows = db.scalars(stmt.order_by(RemoteTrainingAssignment.assigned_at.desc())).all()
    return [_assignment_output(db, row) for row in rows]


@router.get("/my-assignments")
def list_my_remote_assignments(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_feature()
    _viewer(user)
    mapping = employee_access(db, user)
    if not mapping:
        return []
    rows = db.scalars(
        select(RemoteTrainingAssignment)
        .where(
            RemoteTrainingAssignment.company_id == mapping.company_id,
            RemoteTrainingAssignment.employee_id == mapping.employee_id,
        )
        .order_by(RemoteTrainingAssignment.assigned_at.desc())
    ).all()
    visible = []
    for row in rows:
        program = load_program(db, row.program_id)
        if program.status != "published":
            continue
        if str(getattr(program, "policy_mode", "legacy") or "legacy").lower() == "strict" and not strict_policy_active(program):
            continue
        visible.append(_assignment_output(db, row, include_program=True, employee=True))
    return visible


@router.get("/assignments/{assignment_id}")
def get_remote_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_feature()
    assignment = load_assignment(db, assignment_id)
    mode = assert_assignment_access(db, user, assignment)
    program = load_program(db, assignment.program_id)
    if mode == "employee":
        require_strict_policy_active(program)
    if mode == "employee" and program.status != "published":
        raise HTTPException(403, "Bu eğitim şu anda çalışana açık değil.")
    return _assignment_output(db, assignment, include_program=True, employee=(mode == "employee"))


@router.post("/employee-access/provision", status_code=201)
def provision_remote_employee_account(
    payload: RemoteEmployeeAccountProvision,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a restricted employee login and bind it in one transaction.

    The generated password is returned once to the manager and never written
    to audit logs or database columns.  The employee must change it before a
    strict remote-training assignment can be opened.
    """
    require_feature()
    _manager(user)
    ensure_company_access(db, user, payload.company_id)
    company = db.get(Company, payload.company_id)
    employee = db.get(Employee, payload.employee_id)
    if not company or not company.is_active:
        raise HTTPException(404, "Firma bulunamadı veya pasif.")
    if not employee or not employee.is_active or employee.company_id != payload.company_id:
        raise HTTPException(422, "Çalışan firma kapsamında değil veya pasif.")
    if db.scalar(select(User).where(func.lower(User.email) == str(payload.email).lower())):
        raise HTTPException(409, "Bu e-posta zaten bir kullanıcı hesabına bağlıdır.")
    if db.scalar(
        select(RemoteTrainingEmployeeAccess).where(
            RemoteTrainingEmployeeAccess.employee_id == employee.id,
            RemoteTrainingEmployeeAccess.is_active.is_(True),
        )
    ):
        raise HTTPException(409, "Bu çalışan zaten aktif bir uzaktan eğitim hesabına eşlenmiş.")

    temporary_password = generate_temporary_password()
    account = User(
        email=str(payload.email).lower(),
        full_name=employee.full_name,
        hashed_password=get_password_hash(temporary_password),
        role=UserRole.READ_ONLY,
        company_id=company.id,
        osgb_id=company.osgb_id,
        password_change_required=True,
    )
    db.add(account)
    db.flush()
    access = RemoteTrainingEmployeeAccess(
        osgb_id=company.osgb_id,
        company_id=company.id,
        user_id=account.id,
        employee_id=employee.id,
        created_by_id=user.id,
    )
    db.add(access)
    audit(
        db,
        company_id=company.id,
        user=user,
        action="employee_account_provisioned",
        entity_type="employee_access",
        entity_id=employee.id,
        details={"user_id": account.id, "email": account.email},
    )
    _commit(db, "Çalışan giriş hesabı oluşturulamadı.")
    return {
        "access_id": access.id,
        "user_id": account.id,
        "employee_id": employee.id,
        "email": account.email,
        "full_name": account.full_name,
        "temporary_password": temporary_password,
        "password_change_required": True,
        "message": "Geçici parola yalnızca bu yanıtta gösterildi. Çalışan ilk girişten sonra parolasını değiştirmelidir.",
    }


@router.post("/employee-access", status_code=201)
def create_remote_employee_access(
    payload: RemoteEmployeeAccessCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_feature()
    _manager(user)
    ensure_company_access(db, user, payload.company_id)
    target_user = db.get(User, payload.user_id)
    employee = db.get(Employee, payload.employee_id)
    company = db.get(Company, payload.company_id)
    if not target_user or not target_user.is_active:
        raise HTTPException(404, "Eşlenecek kullanıcı bulunamadı veya pasif.")
    if target_user.role in MANAGE_ROLES or target_user.role == UserRole.GLOBAL_ADMIN:
        raise HTTPException(422, "Yönetici hesabı çalışan hesabı olarak eşlenemez; çalışan hesabı için salt-okunur rol kullanın.")
    if not employee or not employee.is_active or employee.company_id != payload.company_id:
        raise HTTPException(422, "Çalışan firma kapsamında değil veya pasif.")
    if target_user.company_id not in (None, payload.company_id) and target_user.role != UserRole.GLOBAL_ADMIN:
        raise HTTPException(422, "Kullanıcı aynı firma kapsamında değil.")
    # The existing RLS context derives a non-global user's company scope from
    # User.company_id.  Employee accounts historically had no employee_id
    # binding; this explicit mapping also establishes the tenant scope when it
    # was previously unset.
    if target_user.company_id is None and target_user.role != UserRole.GLOBAL_ADMIN:
        target_user.company_id = payload.company_id
    if target_user.osgb_id is None and target_user.role != UserRole.GLOBAL_ADMIN and company is not None:
        target_user.osgb_id = company.osgb_id
    by_user = db.scalar(select(RemoteTrainingEmployeeAccess).where(RemoteTrainingEmployeeAccess.user_id == payload.user_id))
    by_employee = db.scalar(select(RemoteTrainingEmployeeAccess).where(RemoteTrainingEmployeeAccess.employee_id == payload.employee_id))
    if by_user and by_user.id != (by_employee.id if by_employee else by_user.id):
        raise HTTPException(409, "Kullanıcı zaten başka bir çalışanla eşlenmiş.")
    if by_employee and by_employee.user_id != payload.user_id:
        raise HTTPException(409, "Çalışan zaten başka bir kullanıcıyla eşlenmiş.")
    row = by_user or by_employee
    if row:
        row.company_id = payload.company_id
        row.osgb_id = company.osgb_id if company else None
        row.user_id = payload.user_id
        row.employee_id = payload.employee_id
        row.is_active = True
        row.created_by_id = user.id
    else:
        row = RemoteTrainingEmployeeAccess(
            osgb_id=company.osgb_id if company else None,
            company_id=payload.company_id,
            user_id=payload.user_id,
            employee_id=payload.employee_id,
            created_by_id=user.id,
        )
        db.add(row)
    audit(db, company_id=payload.company_id, user=user, action="employee_access_created", entity_type="employee_access", entity_id=payload.employee_id)
    _commit(db, "Çalışan kullanıcı eşleştirmesi kaydedilemedi.")
    return {"id": row.id, "company_id": row.company_id, "user_id": row.user_id, "employee_id": row.employee_id, "is_active": row.is_active}


@router.get("/employee-access/candidates")
def list_remote_employee_access_candidates(
    company_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return the safe account/personnel choices needed for employee onboarding."""
    require_feature()
    _manager(user)
    ensure_company_access(db, user, company_id)
    employees = db.scalars(
        select(Employee)
        .where(Employee.company_id == company_id, Employee.is_active.is_(True))
        .order_by(Employee.full_name)
    ).all()
    users = db.scalars(
        select(User)
        .where(
            User.is_active.is_(True),
            User.role.notin_((*MANAGE_ROLES, UserRole.GLOBAL_ADMIN)),
            or_(User.company_id == company_id, User.company_id.is_(None)),
        )
        .order_by(User.full_name)
    ).all()
    access_rows = db.scalars(
        select(RemoteTrainingEmployeeAccess)
        .where(
            RemoteTrainingEmployeeAccess.company_id == company_id,
            RemoteTrainingEmployeeAccess.is_active.is_(True),
        )
        .order_by(RemoteTrainingEmployeeAccess.id)
    ).all()
    return {
        "company_id": company_id,
        "employees": [
            {"id": row.id, "full_name": row.full_name, "branch_id": row.branch_id}
            for row in employees
        ],
        "users": [
            {
                "id": row.id,
                "full_name": row.full_name,
                "email": row.email,
                "role": row.role.value if hasattr(row.role, "value") else str(row.role),
                "company_id": row.company_id,
            }
            for row in users
        ],
        "access": [
            {
                "id": row.id,
                "user_id": row.user_id,
                "employee_id": row.employee_id,
                "is_active": row.is_active,
            }
            for row in access_rows
        ],
    }


@router.get("/employee-access")
def list_remote_employee_access(
    company_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_feature()
    _manager(user)
    ids = _company_ids(db, user, company_id)
    stmt = select(RemoteTrainingEmployeeAccess).where(RemoteTrainingEmployeeAccess.is_active.is_(True))
    if ids is not None:
        stmt = stmt.where(RemoteTrainingEmployeeAccess.company_id.in_(ids)) if ids else stmt.where(RemoteTrainingEmployeeAccess.id == -1)
    rows = db.scalars(stmt.order_by(RemoteTrainingEmployeeAccess.id)).all()
    output = []
    for row in rows:
        target_user = db.get(User, row.user_id)
        employee = db.get(Employee, row.employee_id)
        output.append({"id": row.id, "company_id": row.company_id, "user_id": row.user_id, "user_email": target_user.email if target_user else None, "user_name": target_user.full_name if target_user else None, "employee_id": row.employee_id, "employee_name": employee.full_name if employee else None, "is_active": row.is_active})
    return output


@router.delete("/employee-access/{access_id}")
def deactivate_remote_employee_access(
    access_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_feature()
    _manager(user)
    row = db.get(RemoteTrainingEmployeeAccess, access_id)
    if not row:
        raise HTTPException(404, "Çalışan kullanıcı eşleştirmesi bulunamadı.")
    ensure_company_access(db, user, row.company_id)
    row.is_active = False
    audit(db, company_id=row.company_id, user=user, action="employee_access_deactivated", entity_type="employee_access", entity_id=row.id)
    _commit(db, "Çalışan kullanıcı eşleştirmesi pasifleştirilemedi.")
    return {"id": row.id, "is_active": False}


@router.post("/programs/{program_id}/checkpoint-questions", status_code=201)
def create_remote_checkpoint_question(
    program_id: int,
    payload: RemoteCheckpointQuestionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    program = _assert_program_manager(db, user, program_id)
    section = None
    video = None
    if payload.section_id is not None:
        section = load_section(db, payload.section_id)
        if section.program_id != program.id:
            raise HTTPException(422, "Soru bölümü programla uyumlu değil.")
    if payload.video_id is not None:
        video = load_video(db, payload.video_id)
        if video.program_id != program.id:
            raise HTTPException(422, "Soru videosu programla uyumlu değil.")
        if section is not None and video.section_id != section.id:
            raise HTTPException(422, "Soru bölümü ile video aynı uzaktan eğitim bölümünde olmalıdır.")
        if section is None:
            section = load_section(db, video.section_id)
    parent_sector = section.sector_code if section is not None else None
    sector_code = validate_catalog_program_sector(
        program,
        validate_sector_code(payload.sector_code or parent_sector or "common"),
    )
    if parent_sector and payload.sector_code and sector_code != parent_sector:
        raise HTTPException(422, "Video içi soru, bağlı olduğu bölümün sektör kapsamıyla aynı olmalıdır.")
    row = RemoteTrainingQuestion(
        osgb_id=program.osgb_id,
        company_id=program.company_id,
        program_id=program.id,
        section_id=payload.section_id,
        video_id=payload.video_id,
        sector_code=sector_code,
        question_text=payload.question_text.strip(),
        options_json=json.dumps(payload.options, ensure_ascii=False),
        correct_option=payload.correct_option,
        explanation=payload.explanation,
        timestamp_seconds=payload.timestamp_seconds,
        order_index=payload.order_index,
        is_required=payload.is_required,
        created_by_id=user.id,
    )
    db.add(row)
    db.flush()
    audit(db, company_id=program.company_id, user=user, action="checkpoint_question_created", entity_type="checkpoint_question", entity_id=row.id)
    _commit(db, "Video içi soru kaydedilemedi.")
    return _question_output(row, reveal_answer=True)


@router.get("/programs/{program_id}/checkpoint-questions")
def list_remote_checkpoint_questions(
    program_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    program = _assert_program_manager(db, user, program_id)
    rows = db.scalars(
        select(RemoteTrainingQuestion).where(
            RemoteTrainingQuestion.program_id == program.id,
            RemoteTrainingQuestion.is_final_exam.is_(False),
        ).order_by(RemoteTrainingQuestion.order_index, RemoteTrainingQuestion.id)
    ).all()
    return [_question_output(row, reveal_answer=True) for row in rows]


@router.patch("/programs/{program_id}/final-exam-questions/{question_id}")
def update_remote_final_exam_question(
    program_id: int,
    question_id: int,
    payload: RemoteFinalExamQuestionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Allow managers to review/edit an automatic question before publishing."""
    program = _assert_program_manager(db, user, program_id)
    if program.status in {"published", "archived"}:
        raise HTTPException(409, "Yayımlanmış veya arşivlenmiş eğitimde final soruları değiştirilemez.")
    questions = list(
        db.scalars(
            select(RemoteTrainingQuestion)
            .where(
                RemoteTrainingQuestion.program_id == program.id,
                RemoteTrainingQuestion.is_final_exam.is_(True),
            )
            .order_by(RemoteTrainingQuestion.order_index, RemoteTrainingQuestion.id)
        ).all()
    )
    question = next((row for row in questions if row.id == question_id), None)
    if question is None:
        raise HTTPException(404, "Otomatik final sorusu bulunamadı.")

    original = {
        "question_text": question.question_text,
        "options_json": question.options_json,
        "correct_option": question.correct_option,
        "explanation": question.explanation,
    }
    question.question_text = payload.question_text.strip()
    question.options_json = json.dumps(payload.options, ensure_ascii=False, sort_keys=True)
    question.correct_option = payload.correct_option
    question.explanation = payload.explanation.strip() if payload.explanation else None
    question_position = next(
        (index for index, row in enumerate(questions, start=1) if row.id == question_id),
        1,
    )
    validation_errors = _automatic_final_exam_question_validation(question, question_position)
    if validation_errors:
        for key, value in original.items():
            setattr(question, key, value)
        raise HTTPException(
            422,
            "Final sorusu kaydedilemedi: " + " ".join(validation_errors),
        )
    program.revision_no += 1
    audit(
        db,
        company_id=program.company_id,
        user=user,
        action="automatic_final_exam_question_updated",
        entity_type="final_exam_question",
        entity_id=question.id,
    )
    _commit(db, "Otomatik final sorusu kaydedilemedi.")
    db.refresh(question)
    return _question_output(question, reveal_answer=True)


@router.post("/programs/{program_id}/exam/questions", status_code=201)
def link_remote_exam_question(
    program_id: int,
    payload: RemoteProgramQuestionLink,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    program = _assert_program_manager(db, user, program_id)
    if program.status in {"published", "archived"}:
        raise HTTPException(409, "Yayımlanmış/arşivlenmiş eğitimde sınav soruları değiştirilemez.")
    question = db.get(TrainingQuestion, payload.question_id)
    if not question or question.status != "published":
        raise HTTPException(422, "Yalnızca yayımlanmış mevcut soru bankası soruları bağlanabilir.")
    sector_code = validate_catalog_program_sector(
        program, validate_sector_code(payload.sector_code or "common")
    )
    scope = program_sector_codes(db, program.id)
    if scope is not None and sector_code not in scope:
        raise HTTPException(422, "Soru, firmanın seçili ders kapsamı dışında bir sektöre bağlanamaz.")
    if not catalog_question_is_compatible(db, program, question.id):
        expected = catalog_program_sector_code(program)
        raise HTTPException(
            422,
            "Bu soru yalnızca ortak kapsamda yayımlanmış; "
            f"{sector_label(expected or sector_code)} paketinin sınavına bağlanamaz.",
        )
    row = RemoteTrainingProgramQuestion(
        company_id=program.company_id,
        program_id=program.id,
        question_id=question.id,
        sector_code=sector_code,
        position=payload.position,
        created_by_id=user.id,
    )
    db.add(row)
    db.flush()
    audit(db, company_id=program.company_id, user=user, action="exam_question_linked", entity_type="exam_question", entity_id=row.id, details={"question_id": question.id})
    _commit(db, "Soru programa bağlanamadı; sıra veya soru daha önce kullanılmış olabilir.")
    return {
        "id": row.id,
        "program_id": row.program_id,
        "question_id": row.question_id,
        "position": row.position,
        "sector_code": row.sector_code,
    }


@router.delete("/programs/{program_id}/exam/questions/{link_id}")
def unlink_remote_exam_question(
    program_id: int,
    link_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    program = _assert_program_manager(db, user, program_id)
    if program.status in {"published", "archived"}:
        raise HTTPException(409, "Yayımlanmış/arşivlenmiş eğitimde sınav soruları değiştirilemez.")
    assignment_count = db.scalar(
        select(func.count(RemoteTrainingAssignment.id)).where(
            RemoteTrainingAssignment.program_id == program.id
        )
    ) or 0
    if assignment_count:
        raise HTTPException(
            409,
            "Atama yapılmış eğitimde sınav soruları değiştirilemez; çalışan kayıtları korunmalıdır.",
        )
    row = db.get(RemoteTrainingProgramQuestion, link_id)
    if not row or row.program_id != program.id:
        raise HTTPException(404, "Bu programa bağlı sınav sorusu bulunamadı.")
    db.delete(row)
    audit(
        db,
        company_id=program.company_id,
        user=user,
        action="exam_question_unlinked",
        entity_type="exam_question",
        entity_id=link_id,
        details={"question_id": row.question_id, "ip": request.client.host if request.client else None},
    )
    _commit(db, "Soru sınavdan çıkarılamadı.")
    return {"deleted": True, "id": link_id, "question_id": row.question_id}


@router.get("/assignments/{assignment_id}/exam")
def get_remote_exam(
    assignment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_feature()
    assignment = load_assignment(db, assignment_id)
    assert_assignment_access(db, user, assignment)
    program = load_program(db, assignment.program_id)
    require_strict_policy_active(program)
    if strict_exam_gate_enabled(program):
        summary = recalculate_assignment(db, assignment)
        if not summary["required_videos_complete"] or not summary["required_checkpoints_complete"]:
            raise HTTPException(
                409,
                "Final sınavı açılmadan önce tüm zorunlu videolar ve video içi kontrol soruları tamamlanmalıdır.",
            )
    automatic_questions = _automatic_exam_questions_for_assignment(db, assignment)
    questions = []
    if automatic_questions:
        for question in automatic_questions:
            questions.append(
                {
                    "id": question.id,
                    "position": question.order_index,
                    "sector_code": question.sector_code or "common",
                    "question_text": question.question_text,
                    "options": json.loads(question.options_json or "{}"),
                }
            )
    else:
        links = _exam_links_for_assignment(db, assignment)
        for link in links:
            question = db.get(TrainingQuestion, link.question_id)
            if not question or question.status != "published":
                continue
            questions.append(
                {
                    "id": question.id,
                    "position": link.position,
                    "sector_code": link.sector_code or "common",
                    "question_text": question.question_text,
                    "options": {"A": question.option_a, "B": question.option_b, "C": question.option_c, "D": question.option_d},
                }
            )
    scope = assignment_sector_codes(db, assignment)
    return {
        "assignment_id": assignment.id,
        "program_id": program.id,
        "passing_score": program.passing_score,
        "attempt_limit": program.attempt_limit,
        "sector_codes": sorted(scope) if scope is not None else None,
        "sector_names": [sector_label(code) for code in sorted(scope)] if scope is not None else [],
        "questions": questions,
    }


@router.post("/assignments/{assignment_id}/exam/attempts")
def submit_remote_exam(
    assignment_id: int,
    payload: RemoteExamSubmit,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_feature()
    assignment = load_assignment(db, assignment_id)
    mode = assert_assignment_access(db, user, assignment, write=True)
    program = load_program(db, assignment.program_id)
    require_strict_policy_active(program)
    if strict_policy_active(program) and mode != "employee":
        raise HTTPException(403, "Bu sınavı yalnızca eşlenmiş çalışan gönderebilir.")
    if strict_exam_gate_enabled(program):
        summary = recalculate_assignment(db, assignment)
        if not summary["required_videos_complete"] or not summary["required_checkpoints_complete"]:
            raise HTTPException(
                409,
                "Final sınavı gönderilemez: tüm zorunlu videolar ve video içi kontrol soruları tamamlanmalıdır.",
            )
    if not program.requires_final_exam:
        raise HTTPException(409, "Bu eğitimde final sınavı zorunlu değil.")
    automatic_questions = _automatic_exam_questions_for_assignment(db, assignment)
    links = [] if automatic_questions else _exam_links_for_assignment(db, assignment)
    if not automatic_questions and not links:
        raise HTTPException(409, "Bu eğitim için final sınavı sorusu tanımlanmamış.")
    previous_count = db.scalar(select(func.count(RemoteTrainingExamAttempt.id)).where(RemoteTrainingExamAttempt.assignment_id == assignment.id)) or 0
    if previous_count >= program.attempt_limit:
        raise HTTPException(409, "Final sınavı deneme limiti doldu.")
    question_ids = (
        [question.id for question in automatic_questions]
        if automatic_questions
        else [link.question_id for link in links]
    )
    normalized_answers = {str(key): str(value).upper() for key, value in payload.answers.items()}
    if set(normalized_answers) != {str(question_id) for question_id in question_ids}:
        raise HTTPException(422, "Final sınavındaki tüm sorular yanıtlanmalıdır.")
    correct = 0
    for question_id in question_ids:
        answer = normalized_answers[str(question_id)]
        if answer not in {"A", "B", "C", "D"}:
            raise HTTPException(422, "Sınav yanıtı yalnız A, B, C veya D olabilir.")
        question = (
            next((row for row in automatic_questions if row.id == question_id), None)
            if automatic_questions
            else db.get(TrainingQuestion, question_id)
        )
        if question and answer == question.correct_option:
            correct += 1
    score = round(correct * 100 / len(question_ids))
    passed = score >= program.passing_score
    attempt = RemoteTrainingExamAttempt(
        company_id=assignment.company_id,
        program_id=program.id,
        assignment_id=assignment.id,
        employee_id=assignment.employee_id,
        attempt_no=previous_count + 1,
        question_ids_json=json.dumps(question_ids),
        answers_json=json.dumps(normalized_answers),
        score=score,
        passed=passed,
        submitted_at=datetime.utcnow(),
        submitted_by_id=user.id,
    )
    db.add(attempt)
    db.flush()
    summary = recalculate_assignment(db, assignment)
    certificate = ensure_certificate(db, assignment)
    audit(db, company_id=assignment.company_id, user=user, action="exam_submitted", entity_type="exam_attempt", entity_id=attempt.id, details={"score": score, "passed": passed, "ip": request.client.host if request.client else None})
    _commit(db, "Final sınav sonucu kaydedilemedi.")
    return {"attempt_id": attempt.id, "attempt_no": attempt.attempt_no, "score": score, "passed": passed, "summary": summary, "certificate_id": certificate.id if certificate else None}


@router.post("/assignments/{assignment_id}/videos/{video_id}/progress")
def save_remote_progress(
    assignment_id: int,
    video_id: int,
    payload: RemoteProgressCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_feature()
    assignment = load_assignment(db, assignment_id)
    mode = assert_assignment_access(db, user, assignment, write=True)
    video = load_video(db, video_id)
    program = load_program(db, assignment.program_id)
    require_strict_policy_active(program)
    if strict_policy_active(program) and mode != "employee":
        raise HTTPException(403, "Bu video ilerlemesini yalnızca eşlenmiş çalışan gönderebilir.")
    if video.program_id != program.id or video.status != "published" or not video.is_current:
        raise HTTPException(403, "Video bu atamaya açık değil.")
    section = load_section(db, video.section_id)
    if not assignment_allows_sector(db, assignment, section.sector_code):
        raise HTTPException(403, "Video bu çalışanın ders kapsamına dahil değil.")
    assert_video_unlocked(db, assignment, video)
    if not video.duration_seconds:
        raise HTTPException(409, "Video süresi işlenmeden ilerleme kaydı alınamaz.")
    position = min(float(payload.position_seconds), float(video.duration_seconds))
    existing = db.scalar(
        select(RemoteTrainingVideoProgress).where(
            RemoteTrainingVideoProgress.assignment_id == assignment.id,
            RemoteTrainingVideoProgress.video_id == video.id,
        )
    )
    now = datetime.utcnow()
    if not existing:
        existing = RemoteTrainingVideoProgress(
            company_id=assignment.company_id,
            program_id=program.id,
            assignment_id=assignment.id,
            section_id=video.section_id,
            video_id=video.id,
            employee_id=assignment.employee_id,
        )
        db.add(existing)
    current_position = float(existing.last_position_seconds or 0)
    current_watched = float(existing.watched_duration_seconds or 0)
    previous_access = existing.last_access_at
    if previous_access is None:
        elapsed_seconds = 0.0
    else:
        elapsed_seconds = max(0.0, (now - previous_access).total_seconds())
    forward_delta = max(0.0, position - current_position)
    strict = strict_policy_active(program)
    if strict:
        # A strict heartbeat can only credit elapsed server wall-clock time.
        # There is intentionally no minimum or positive tolerance: repeated
        # instant API calls must not farm seconds, and a forward seek cannot
        # create credit that the server did not observe.
        credit_cap = min(float(video.duration_seconds), max(0.0, elapsed_seconds))
        accepted_delta = min(forward_delta, credit_cap)
        accepted_position = (
            min(float(video.duration_seconds), current_position + accepted_delta)
            if position >= current_position
            else position
        )
        coverage, covered_seconds = _merge_coverage(
            _decode_coverage(existing.coverage_json),
            current_position,
            accepted_position,
            float(video.duration_seconds),
        )
        if payload.event_type == "ended":
            reconciled = reconcile_strict_video_end(
                coverage,
                current_position=current_position,
                requested_position=position,
                duration=float(video.duration_seconds),
            )
            if reconciled is not None:
                coverage, covered_seconds, accepted_position = reconciled
        existing.coverage_json = json.dumps(coverage, separators=(",", ":"))
        existing.last_position_seconds = accepted_position
        existing.watched_duration_seconds = min(float(video.duration_seconds), covered_seconds)
    else:
        # Legacy programs retain their previous capped-delta behavior exactly.
        credit_cap = min(float(video.duration_seconds), max(5.0, elapsed_seconds + 5.0))
        credited_delta = min(forward_delta, credit_cap)
        existing.last_position_seconds = position
        existing.watched_duration_seconds = min(
            float(video.duration_seconds), current_watched + credited_delta
        )
    existing.watched_percentage = min(100.0, existing.watched_duration_seconds / float(video.duration_seconds) * 100)
    existing.last_access_at = now
    existing.device_info = payload.device_info
    if payload.event_type in {"start", "resume"}:
        existing.viewing_sessions = int(existing.viewing_sessions or 0) + (1 if payload.event_type == "start" else 0)
        existing.started_at = existing.started_at or now
        assignment.started_at = assignment.started_at or now
    threshold = max(1, min(int(program.completion_threshold_percent), 100))
    if existing.watched_percentage >= threshold:
        existing.status = "completed"
        existing.completed_at = existing.completed_at or now
        event_type = "completed"
    else:
        existing.status = "in_progress"
        event_type = payload.event_type
    db.add(
        RemoteTrainingEvent(
            company_id=assignment.company_id,
            program_id=program.id,
            assignment_id=assignment.id,
            employee_id=assignment.employee_id,
            video_id=video.id,
            user_id=user.id,
            event_type=event_type,
            position_seconds=existing.last_position_seconds,
            watched_seconds=existing.watched_duration_seconds,
            device_info=payload.device_info,
            ip_address=request.client.host if request.client else None,
            user_agent=(request.headers.get("user-agent") or "")[:500] or None,
        )
    )
    summary = recalculate_assignment(db, assignment)
    certificate = ensure_certificate(db, assignment) if summary["complete"] else None
    _commit(db, "Video ilerlemesi kaydedilemedi.")
    return {"video_id": video.id, "position_seconds": float(existing.last_position_seconds), "accepted_position_seconds": float(existing.last_position_seconds), "watched_percentage": float(existing.watched_percentage), "status": existing.status, "summary": summary, "certificate_id": certificate.id if certificate else None}


@router.post("/assignments/{assignment_id}/checkpoint-questions/{question_id}")
def answer_remote_checkpoint(
    assignment_id: int,
    question_id: int,
    answer: str = Query(..., min_length=1, max_length=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_feature()
    assignment = load_assignment(db, assignment_id)
    mode = assert_assignment_access(db, user, assignment, write=True)
    program = load_program(db, assignment.program_id)
    require_strict_policy_active(program)
    if strict_policy_active(program) and mode != "employee":
        raise HTTPException(403, "Bu kontrol sorusunu yalnızca eşlenmiş çalışan yanıtlayabilir.")
    question = db.get(RemoteTrainingQuestion, question_id)
    if not question or question.program_id != assignment.program_id or question.is_final_exam:
        raise HTTPException(404, "Video içi soru bulunamadı.")
    if not assignment_allows_sector(db, assignment, question.sector_code):
        raise HTTPException(403, "Video içi soru bu çalışanın ders kapsamına dahil değil.")
    if strict_policy_active(program) and question.video_id:
        checkpoint_video = load_video(db, question.video_id)
        if checkpoint_video.program_id != program.id or not checkpoint_video.is_current:
            raise HTTPException(409, "Video içi soru güncel bir videoya bağlı değil.")
        completed = db.scalar(
            select(RemoteTrainingVideoProgress.id).where(
                RemoteTrainingVideoProgress.assignment_id == assignment.id,
                RemoteTrainingVideoProgress.video_id == checkpoint_video.id,
                RemoteTrainingVideoProgress.status == "completed",
            )
        )
        if completed is None:
            raise HTTPException(409, "Önce bu sorunun bağlı olduğu videoyu tamamlayın.")
    normalized = answer.upper()
    options = json.loads(question.options_json or "{}")
    if normalized not in options:
        raise HTTPException(422, "Yanıt soru seçenekleri içinde değil.")
    previous = db.scalar(
        select(func.count(RemoteTrainingCheckpointAnswer.id)).where(
            RemoteTrainingCheckpointAnswer.assignment_id == assignment.id,
            RemoteTrainingCheckpointAnswer.question_id == question.id,
        )
    ) or 0
    row = RemoteTrainingCheckpointAnswer(
        company_id=assignment.company_id,
        program_id=assignment.program_id,
        assignment_id=assignment.id,
        employee_id=assignment.employee_id,
        question_id=question.id,
        answer=normalized,
        is_correct=normalized == question.correct_option,
        attempt_no=previous + 1,
    )
    db.add(row)
    db.flush()
    summary = recalculate_assignment(db, assignment)
    certificate = ensure_certificate(db, assignment)
    audit(db, company_id=assignment.company_id, user=user, action="checkpoint_answered", entity_type="checkpoint_answer", entity_id=row.id, details={"question_id": question.id, "is_correct": row.is_correct})
    _commit(db, "Video içi soru yanıtı kaydedilemedi.")
    return {"question_id": question.id, "is_correct": row.is_correct, "summary": summary, "certificate_id": certificate.id if certificate else None}


@router.get("/assignments/{assignment_id}/certificate")
def get_remote_certificate(
    assignment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_feature()
    assignment = load_assignment(db, assignment_id)
    _assert_assignment_document_manager(db, user, assignment)
    certificate = ensure_certificate(db, assignment)
    if not certificate:
        if assignment.status != "completed":
            raise HTTPException(409, "Katılım belgesi için video, video içi sorular ve final sınavı tamamlanmalıdır.")
        raise HTTPException(409, "Katılım belgesi için atama tarihindeki SGK/NACE/tehlike sınıfı snapshot alanları eksik; veri uydurulmadı.")
    db.commit()
    return {
        "id": certificate.id,
        "assignment_id": certificate.assignment_id,
        "employee_name": certificate.employee_name_snapshot,
        "company_name": certificate.company_name_snapshot,
        "workplace_name": certificate.workplace_name_snapshot,
        "sgk_registration_number": certificate.sgk_registration_number_snapshot,
        "nace_code": certificate.nace_code_snapshot,
        "nace_description": certificate.nace_description_snapshot,
        "hazard_class": certificate.hazard_class_snapshot,
        "training_name": certificate.training_name,
        "training_type": REMOTE_TRAINING_TYPE,
        "training_duration_seconds": certificate.training_duration_seconds,
        "training_date": _iso(certificate.training_date),
        "instructor_name": certificate.instructor_name_snapshot,
        "examination_score": certificate.examination_score,
        "certificate_number": certificate.certificate_number,
        "verification_code": certificate.verification_code,
        "issue_date": _iso(certificate.issue_date),
    }


@router.get("/assignments/{assignment_id}/certificate.pdf")
def download_remote_certificate(
    assignment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_feature()
    assignment = load_assignment(db, assignment_id)
    _assert_assignment_document_manager(db, user, assignment)
    certificate = ensure_certificate(db, assignment)
    if not certificate:
        raise HTTPException(409, "Katılım belgesi üretimi için tamamlanma ve tarihsel kimlik snapshotları gereklidir.")
    db.commit()
    data = build_certificate_pdf(db, certificate)
    return StreamingResponse(
        iter([data]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{certificate.certificate_number}.pdf"'},
    )


@router.get("/certificates/verify/{verification_code}")
def verify_remote_certificate(
    verification_code: str,
    db: Session = Depends(get_db),
):
    clean = (verification_code or "").strip().upper()
    if not feature_active():
        return {"valid": False, "verification_code": clean, "message": "Uzaktan eğitim katılım belgesi doğrulaması etkin değil."}
    certificate = db.scalar(
        select(RemoteTrainingCertificate).where(RemoteTrainingCertificate.verification_code == clean)
    ) if clean else None
    if not certificate:
        return {"valid": False, "verification_code": clean, "message": "Bu kodla eşleşen uzaktan eğitim katılım belgesi bulunamadı."}
    return {
        "valid": True,
        "verification_code": clean,
        "certificate_number": certificate.certificate_number,
        "employee_name": certificate.employee_name_snapshot,
        "company_name": certificate.company_name_snapshot,
        "workplace_name": certificate.workplace_name_snapshot,
        "training_name": certificate.training_name,
        "training_type": REMOTE_TRAINING_TYPE,
        "training_date": _iso(certificate.training_date),
        "examination_score": certificate.examination_score,
        "nace_code": certificate.nace_code_snapshot,
        "hazard_class": certificate.hazard_class_snapshot,
        "message": "Katılım belgesi doğrulandı.",
    }


@router.get("/programs/{program_id}/report")
def remote_training_report(
    program_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    program = _assert_program_manager(db, user, program_id)
    rows = db.scalars(
        select(RemoteTrainingAssignment).where(RemoteTrainingAssignment.program_id == program.id).order_by(RemoteTrainingAssignment.employee_name_snapshot)
    ).all()
    items = [_assignment_output(db, row) for row in rows]
    by_status: dict[str, int] = {}
    for item in items:
        by_status[item["status"]] = by_status.get(item["status"], 0) + 1
    progress_rows = db.scalars(select(RemoteTrainingVideoProgress).where(RemoteTrainingVideoProgress.program_id == program.id)).all()
    avg_progress = round(sum(float(item.watched_percentage or 0) for item in progress_rows) / len(progress_rows), 2) if progress_rows else 0
    exam_rows = db.scalars(select(RemoteTrainingExamAttempt).where(RemoteTrainingExamAttempt.program_id == program.id)).all()
    certificate_count = db.scalar(select(func.count(RemoteTrainingCertificate.id)).where(RemoteTrainingCertificate.program_id == program.id)) or 0
    return {
        "program": _program_output(program),
        "assignment_count": len(items),
        "status_counts": by_status,
        "average_video_progress_percent": avg_progress,
        "exam_attempt_count": len(exam_rows),
        "certificate_count": int(certificate_count),  # legacy API key
        "participation_document_count": int(certificate_count),
        "rows": items,
    }


@router.get("/programs/{program_id}/audit")
def remote_training_audit(
    program_id: int,
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    program = _assert_program_manager(db, user, program_id)
    rows = db.scalars(
        select(RemoteTrainingEvent)
        .where(RemoteTrainingEvent.program_id == program.id)
        .order_by(desc(RemoteTrainingEvent.created_at))
        .limit(limit)
    ).all()
    return [{"id": row.id, "assignment_id": row.assignment_id, "employee_id": row.employee_id, "video_id": row.video_id, "user_id": row.user_id, "event_type": row.event_type, "position_seconds": float(row.position_seconds) if row.position_seconds is not None else None, "watched_seconds": float(row.watched_seconds) if row.watched_seconds is not None else None, "created_at": _iso(row.created_at)} for row in rows]
