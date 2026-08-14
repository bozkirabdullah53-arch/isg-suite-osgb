"""Domain services for the isolated Basic OHS remote video course."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import shutil
import subprocess
import tempfile
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi import HTTPException
from jose import JWTError, jwt
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.api.company_access import ensure_company_access
from app.core.config import remote_basic_ohs_strict_policy_active, settings
from app.core.database import SessionLocal
from app.core.security import ALGORITHM
from app.models.entities import (
    Branch,
    Company,
    Employee,
    TrainingQuestion,
    TrainingQuestionScope,
    User,
    UserRole,
)
from app.models.remote_training import (
    ASSET_TYPES,
    REMOTE_SECTOR_CATALOG,
    REMOTE_SECTOR_CODES,
    REMOTE_SECTOR_LABELS,
    REMOTE_CATALOG_PACKAGE_SECTOR_CODES,
    REMOTE_TRAINING_TYPE,
    RemoteTrainingAssignment,
    RemoteTrainingAssignmentSector,
    RemoteTrainingAuditLog,
    RemoteTrainingAsset,
    RemoteTrainingCertificate,
    RemoteTrainingCatalogPackage,
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
from app.services.job_queue import enqueue
from app.services.object_store import get_object_store
from app.services.training_nace_classification import resolve_exact_nace
from app.services.training_question_bank import _curated_pack
from app.services.upload_security import assert_safe_video_upload

logger = logging.getLogger(__name__)

MANAGE_ROLES = {
    UserRole.GLOBAL_ADMIN,
    UserRole.COMPANY_ADMIN,
    UserRole.SAFETY_SPECIALIST,
}
VIEW_ROLES = MANAGE_ROLES | {
    UserRole.WORKPLACE_PHYSICIAN,
    UserRole.OTHER_HEALTH_PERSONNEL,
    UserRole.READ_ONLY,
}

VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v"}
VIDEO_MIME_TYPES = {
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "video/x-m4v",
    "application/octet-stream",
}
VIDEO_MAGIC = {
    ".mp4": (b"ftyp",),
    ".m4v": (b"ftyp",),
    ".mov": (b"ftyp",),
    ".webm": (b"\x1a\x45\xdf\xa3",),
}
ASSET_EXTENSIONS = {
    "thumbnail": {".png", ".jpg", ".jpeg", ".webp"},
    "subtitle": {".vtt", ".srt"},
    "supporting_document": {".pdf", ".docx"},
}
ASSET_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".vtt": "text/vtt",
    ".srt": "application/x-subrip",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

# Each central package receives a vetted, sector-aligned ten-question exam.
# The source packs are versioned in the repository and copied into the
# company-scoped program, so a later question-bank edit cannot alter an
# already-created employee exam.
REMOTE_AUTO_EXAM_PACKS = {
    "common-basic-ohs": "common.json",
    "construction-ohs": "sector-construction.json",
    "metal-machine-ohs": "sector-metal.json",
    "battery-production-ohs": "sector-battery.json",
    "food-production-ohs": "sector-food-production.json",
    "logistics-warehouse-transport-ohs": "sector-logistics.json",
    "chemical-paint-production-ohs": "sector-chemicals.json",
    "open-mine-quarry-aggregate-ohs": "sector-mining.json",
    "road-asphalt-infrastructure-ohs": "sector-road-transport.json",
    "office-general-ohs": "sector-office.json",
    "working-at-height-ohs": "special-yuksekte-calisma.json",
}
# The curated file is also checked against the catalog scope.  A filename
# alone is not sufficient protection if a future content edit accidentally
# places an unrelated sector question in the package.
REMOTE_AUTO_EXAM_PACKAGE_SCOPES = {
    "common-basic-ohs": {"*"},
    "construction-ohs": {"F"},
    "metal-machine-ohs": {"kaynakli_imalat", "makine_imalat", "metal_isleme_torna_freze"},
    "battery-production-ohs": {"aku_uretimi"},
    "food-production-ohs": {"firin_unlu_mamuller", "gida_uretim", "gida_uretimi_isleme", "sut_sut_urunleri"},
    "logistics-warehouse-transport-ohs": {"depo_lojistik", "depolama_lojistik_depo", "e_ticaret_depo_fulfillment"},
    "chemical-paint-production-ohs": {"boyahaneler_boya_uretimi", "kimya_kimyasal_uretim", "kimyasal_boya"},
    "open-mine-quarry-aggregate-ohs": {"acik_maden", "madencilik_maden_ocagi", "tas_ocagi_maden_ocagi"},
    "road-asphalt-infrastructure-ohs": {"karayolu_tasimacilik", "nakliye_karayolu_tasimaciligi", "toplu_tasima_ulasim"},
    "office-general-ohs": {"ofis", "ofis_idari_hizmetler"},
    "working-at-height-ohs": {"yuksekte_calisma"},
}
REMOTE_AUTO_EXAM_QUESTION_COUNT = 10


def automatic_exam_items_for_package(package_code: str | None) -> list[dict[str, Any]]:
    """Return ten deterministic, reviewed questions for a catalog package.

    The bundled question-bank loader validates the four options, answer,
    explanation, source and scope before returning a pack.  Evenly spaced
    selection keeps the special ten-section height package representative
    instead of taking ten questions from its first topic only.
    """
    file_name = REMOTE_AUTO_EXAM_PACKS.get(str(package_code or "").strip().lower())
    if not file_name:
        raise RuntimeError(
            f"Otomatik final sınavı için doğrulanmış sektör paketi eşleşmesi yok: {package_code}"
        )
    items = list(_curated_pack(file_name))
    if len(items) < REMOTE_AUTO_EXAM_QUESTION_COUNT:
        raise RuntimeError(
            f"Otomatik final sınavı soru paketi en az {REMOTE_AUTO_EXAM_QUESTION_COUNT} soru içermelidir: {file_name}"
        )
    last_index = len(items) - 1
    selected = [
        items[(index * last_index) // (REMOTE_AUTO_EXAM_QUESTION_COUNT - 1)]
        for index in range(REMOTE_AUTO_EXAM_QUESTION_COUNT)
    ]
    question_codes = {
        str(item.get("question_code") or "").strip().casefold() for item in selected
    }
    if len(question_codes) != REMOTE_AUTO_EXAM_QUESTION_COUNT:
        raise RuntimeError(
            f"Otomatik final sınavı soru paketi tekrar eden sorular içeriyor: {file_name}"
        )
    topic_codes = {
        str(item.get("topic_code") or "").strip().casefold() for item in selected
    }
    if len(topic_codes) != REMOTE_AUTO_EXAM_QUESTION_COUNT:
        raise RuntimeError(
            f"Otomatik final sınavı aynı öğrenme konusunu tekrar ediyor: {file_name}"
        )
    expected_scopes = REMOTE_AUTO_EXAM_PACKAGE_SCOPES[str(package_code or "").strip().lower()]
    if any(
        not any(
            str(scope.get("value") or "").strip() in expected_scopes
            for scope in (item.get("scopes") or [])
            if isinstance(scope, dict)
        )
        for item in selected
    ):
        raise RuntimeError(
            f"Otomatik final sınavı sektör kapsamıyla uyumsuz soru içeriyor: {file_name}"
        )
    return [dict(item) for item in selected]


def feature_active() -> bool:
    from app.core.config import remote_basic_ohs_training_active

    return remote_basic_ohs_training_active()


def require_feature() -> None:
    if not feature_active():
        raise HTTPException(404, "Uzaktan Temel İSG Eğitim modülü etkin değil.")


def strict_policy_active(program: RemoteTrainingProgram) -> bool:
    """Return whether this program is inside the separately gated policy."""
    if str(getattr(program, "policy_mode", "legacy") or "legacy").lower() != "strict":
        return False
    return remote_basic_ohs_strict_policy_active(
        getattr(program, "source_catalog_code", None),
        getattr(program, "company_id", None),
    )


def require_strict_policy_active(program: RemoteTrainingProgram) -> None:
    if str(getattr(program, "policy_mode", "legacy") or "legacy").lower() != "strict":
        return
    if not strict_policy_active(program):
        raise HTTPException(
            409,
            "Bu sektör eğitim paketi firma bazlı dağıtım politikası etkin değilken kullanılamaz.",
        )
    if (
        int(getattr(program, "completion_threshold_percent", 0) or 0) < 100
        or int(getattr(program, "passing_score", 0) or 0) < 70
        or not bool(getattr(program, "sequence_enforced", False))
        or not bool(getattr(program, "exam_gate_enforced", False))
        or not bool(getattr(program, "requires_final_exam", False))
    ):
        raise HTTPException(
            409,
            "Sektör eğitim politikası eksik: %100 izleme, sıralı ders, %70 sınav ve sınav kilidi zorunludur.",
        )


def strict_sequence_enabled(program: RemoteTrainingProgram) -> bool:
    return strict_policy_active(program) and bool(getattr(program, "sequence_enforced", False))


def strict_exam_gate_enabled(program: RemoteTrainingProgram) -> bool:
    return strict_policy_active(program) and bool(getattr(program, "exam_gate_enforced", False))


def is_manager(user: User) -> bool:
    return user.role in MANAGE_ROLES


def _not_found(message: str = "Uzaktan eğitim kaydı bulunamadı.") -> HTTPException:
    return HTTPException(404, message)


def validate_sector_code(code: str | None, *, allow_none: bool = False) -> str | None:
    normalized = str(code or "").strip().lower()
    if allow_none and not normalized:
        return None
    if normalized not in REMOTE_SECTOR_CODES:
        raise HTTPException(422, "Geçersiz uzaktan eğitim sektör kodu.")
    return normalized


def sector_label(code: str) -> str:
    return REMOTE_SECTOR_LABELS.get(code, code)


def catalog_program_sector_code(program: RemoteTrainingProgram) -> str | None:
    """Return the immutable curriculum scope for a catalog-derived snapshot.

    A manually created legacy program deliberately returns ``None`` so its
    existing multi-sector behavior is preserved.  A company snapshot copied
    from the central catalog has exactly one curriculum sector; the common
    package is the only catalog package whose fixed sector is ``common``.
    """

    source_code = str(getattr(program, "source_catalog_code", None) or "").strip().lower()
    # Older company snapshots may retain the immutable catalog code without
    # the package FK. Known catalog codes must still have a fixed scope.
    if not getattr(program, "source_catalog_package_id", None) and source_code not in REMOTE_CATALOG_PACKAGE_SECTOR_CODES:
        return None
    return catalog_package_sector_code(source_code)


def validate_catalog_program_sector(
    program: RemoteTrainingProgram, sector_code: str
) -> str:
    """Reject unrelated sections/scope values on a catalog snapshot."""

    expected = catalog_program_sector_code(program)
    if expected is not None and sector_code != expected:
        raise HTTPException(
            422,
            "Bu firma eğitimi merkezi katalogdan hazırlanmıştır; kapsamı yalnızca "
            f"{sector_label(expected)} olabilir. Farklı eğitim için ilgili merkezi paketi firmaya hazırlayın.",
        )
    return sector_code


def catalog_question_is_compatible(
    db: Session, program: RemoteTrainingProgram, question_id: int
) -> bool:
    """Keep common and sector-specific catalog exams from being mixed.

    The question bank stores the authoritative scope on ``TrainingQuestion``.
    For a sector package, any published question with a non-common scope is
    eligible (NACE, sector profile, or hazard); a common-only question belongs
    to the separate common package.  Legacy/manual programs keep their
    historical linking behavior.
    """

    expected = catalog_program_sector_code(program)
    if expected is None:
        return True
    scopes = list(
        db.scalars(
            select(TrainingQuestionScope).where(
                TrainingQuestionScope.question_id == question_id
            )
        ).all()
    )
    if expected == "common":
        return any(
            scope.scope_type == "common" and str(scope.scope_value or "").strip() in {"", "*"}
            for scope in scopes
        )
    return any(scope.scope_type != "common" for scope in scopes)


def program_sector_codes(db: Session, program_id: int) -> set[str] | None:
    """Return the effective scope; ``None`` preserves pre-scope programs.

    Catalog-derived company snapshots have one immutable curriculum sector.
    Older snapshots can contain a stale ``common`` row beside the real package
    sector; using those rows caused false missing-video and exam errors.
    """
    program = db.get(RemoteTrainingProgram, program_id)
    catalog_sector_code = catalog_program_sector_code(program) if program else None
    if catalog_sector_code is not None:
        return {catalog_sector_code}
    rows = list(
        db.scalars(
            select(RemoteTrainingProgramSector).where(
                RemoteTrainingProgramSector.program_id == program_id
            )
        ).all()
    )
    if not rows:
        return None
    return {
        row.sector_code for row in rows if row.is_enabled and row.sector_code in REMOTE_SECTOR_CODES
    }


def assignment_sector_codes(
    db: Session, assignment: RemoteTrainingAssignment
) -> set[str] | None:
    rows = list(
        db.scalars(
            select(RemoteTrainingAssignmentSector).where(
                RemoteTrainingAssignmentSector.assignment_id == assignment.id
            )
        ).all()
    )
    if rows:
        return {
            row.sector_code for row in rows if row.sector_code in REMOTE_SECTOR_CODES
        }
    return program_sector_codes(db, assignment.program_id)


def assignment_allows_sector(
    db: Session, assignment: RemoteTrainingAssignment, sector_code: str
) -> bool:
    scope = assignment_sector_codes(db, assignment)
    return scope is None or sector_code in scope


def build_program_sector_catalog(
    db: Session,
    program: RemoteTrainingProgram,
    *,
    visible_sector_codes: set[str] | None = None,
) -> dict[str, Any]:
    rows = list(
        db.scalars(
            select(RemoteTrainingProgramSector).where(
                RemoteTrainingProgramSector.program_id == program.id
            )
        ).all()
    )
    configured = bool(rows)
    selected = program_sector_codes(db, program.id) or set()
    sections = list(
        db.scalars(
            select(RemoteTrainingSection).where(RemoteTrainingSection.program_id == program.id)
        ).all()
    )
    videos = list(
        db.scalars(
            select(RemoteTrainingVideo).where(RemoteTrainingVideo.program_id == program.id)
        ).all()
    )
    section_ids_by_sector: dict[str, set[int]] = {}
    for section in sections:
        section_ids_by_sector.setdefault(section.sector_code, set()).add(section.id)
    questions = list(
        db.scalars(
            select(RemoteTrainingQuestion).where(
                RemoteTrainingQuestion.program_id == program.id,
                RemoteTrainingQuestion.is_final_exam.is_(False),
            )
        ).all()
    )
    automatic_exam_questions = list(
        db.scalars(
            select(RemoteTrainingQuestion).where(
                RemoteTrainingQuestion.program_id == program.id,
                RemoteTrainingQuestion.is_final_exam.is_(True),
            )
        ).all()
    )
    catalog_sector_code = catalog_program_sector_code(program)
    catalog = []
    for code, label, description in REMOTE_SECTOR_CATALOG:
        if visible_sector_codes is not None and code not in visible_sector_codes:
            continue
        section_ids = section_ids_by_sector.get(code, set())
        catalog.append(
            {
                "code": code,
                "label": label,
                "description": description,
                "enabled": code in selected if configured else False,
                "locked": (
                    code == catalog_sector_code
                    if catalog_sector_code is not None
                    else code == "common" and code in selected
                ),
                "section_count": sum(1 for section in sections if section.sector_code == code and section.status != "archived"),
                "video_count": sum(
                    1
                    for video in videos
                    if video.section_id in section_ids
                    and video.is_current
                    and video.status != "archived"
                ),
                "question_count": sum(1 for question in questions if question.sector_code == code),
                "automatic_exam_question_count": sum(
                    1 for question in automatic_exam_questions if question.sector_code == code
                ),
            }
        )
    return {
        "program_id": program.id,
        "mode": "scoped" if configured else "legacy",
        "selected_sector_codes": sorted(selected) if configured else [],
        "selected_sector_labels": [sector_label(code) for code in sorted(selected)] if configured else [],
        "catalog_fixed": catalog_sector_code is not None,
        "catalog_sector_code": catalog_sector_code,
        "sectors": catalog,
    }


def load_program(db: Session, program_id: int) -> RemoteTrainingProgram:
    row = db.get(RemoteTrainingProgram, program_id)
    if not row:
        raise _not_found()
    return row


def load_section(db: Session, section_id: int) -> RemoteTrainingSection:
    row = db.get(RemoteTrainingSection, section_id)
    if not row:
        raise _not_found("Uzaktan eğitim bölümü bulunamadı.")
    return row


def load_video(db: Session, video_id: int) -> RemoteTrainingVideo:
    row = db.get(RemoteTrainingVideo, video_id)
    if not row:
        raise _not_found("Uzaktan eğitim videosu bulunamadı.")
    return row


def load_assignment(db: Session, assignment_id: int) -> RemoteTrainingAssignment:
    row = db.get(RemoteTrainingAssignment, assignment_id)
    if not row:
        raise _not_found("Uzaktan eğitim ataması bulunamadı.")
    return row


def assert_program_access(db: Session, user: User, program: RemoteTrainingProgram) -> None:
    if user.role not in VIEW_ROLES:
        raise HTTPException(403, "Bu uzaktan eğitim kaydını görüntüleme yetkiniz yok.")
    ensure_company_access(db, user, program.company_id)


def employee_access(db: Session, user: User) -> RemoteTrainingEmployeeAccess | None:
    return db.scalar(
        select(RemoteTrainingEmployeeAccess).where(
            RemoteTrainingEmployeeAccess.user_id == user.id,
            RemoteTrainingEmployeeAccess.is_active.is_(True),
        )
    )


def assert_assignment_access(
    db: Session,
    user: User,
    assignment: RemoteTrainingAssignment,
    *,
    write: bool = False,
) -> str:
    """Return ``manager`` or ``employee`` after applying the real scope."""
    if is_manager(user):
        ensure_company_access(db, user, assignment.company_id)
        return "manager"
    mapped = employee_access(db, user)
    if mapped:
        if bool(getattr(user, "password_change_required", False)):
            raise HTTPException(
                403,
                "Uzaktan eğitime başlamadan önce geçici şifrenizi Güvenlik bölümünden değiştirin.",
            )
        if mapped.company_id != assignment.company_id or mapped.employee_id != assignment.employee_id:
            raise HTTPException(403, "Bu çalışanın uzaktan eğitim kaydına erişemezsiniz.")
        return "employee"
    ensure_company_access(db, user, assignment.company_id)
    if write:
        raise HTTPException(403, "Bu işlem için çalışan eşleştirmesi veya eğitici yetkisi gerekir.")
    raise HTTPException(403, "Çalışan hesabınız uzaktan eğitim için eşleştirilmemiş.")


def validate_branch(db: Session, company_id: int, branch_id: int | None) -> Branch | None:
    if not branch_id:
        return None
    branch = db.get(Branch, branch_id)
    if not branch or branch.company_id != company_id or not branch.is_active:
        raise HTTPException(422, "Seçilen işyeri/şube firma ile uyumlu değil veya pasif.")
    return branch


def company_snapshot(db: Session, company_id: int, branch_id: int | None = None) -> dict[str, Any]:
    company = db.get(Company, company_id)
    if not company or not company.is_active:
        raise _not_found("İşyeri bulunamadı veya pasif.")
    branch = validate_branch(db, company_id, branch_id)
    nace_code = str(getattr(company, "nace_code", None) or "").strip() or None
    nace_description = None
    if nace_code:
        try:
            nace_description = resolve_exact_nace(nace_code).nace_description
        except (TypeError, ValueError):
            nace_description = None
    sgk = str((branch.sgk_registry_no if branch else None) or company.sgk_registry_no or "").strip() or None
    return {
        "osgb_id": getattr(company, "osgb_id", None),
        "company_id": company.id,
        "company_name": company.name,
        "branch_id": branch.id if branch else None,
        "workplace_name": branch.name if branch else company.name,
        "sgk_registration_number": sgk,
        "nace_code": nace_code,
        "nace_description": nace_description,
        "hazard_class": str(company.hazard_class or "").strip() or None,
        "warnings": [
            item
            for item, missing in (
                ("SGK sicil numarası işyeri kaydında bulunamadı.", not sgk),
                ("NACE kodu işyeri kaydında bulunamadı.", not nace_code),
                ("NACE kodunun açıklaması resmî katalogda çözülemedi.", bool(nace_code) and not nace_description),
                ("Tehlike sınıfı işyeri kaydında bulunamadı.", not company.hazard_class),
            )
            if missing
        ],
    }


def audit(
    db: Session,
    *,
    company_id: int,
    user: User | None,
    action: str,
    entity_type: str,
    entity_id: int | str | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    db.add(
        RemoteTrainingAuditLog(
            company_id=company_id,
            user_id=user.id if user else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            details_json=json.dumps(details or {}, ensure_ascii=False, default=str),
            ip_address=ip_address,
        )
    )


def _video_head_is_valid(content: bytes, extension: str) -> bool:
    ext = extension.lower()
    if ext in {".mp4", ".m4v", ".mov"}:
        return len(content) >= 12 and content[4:8] == b"ftyp"
    return any(content.startswith(sig) for sig in VIDEO_MAGIC.get(ext, ()))


def validate_video_bytes(content: bytes, *, extension: str, original_name: str) -> None:
    if not content:
        raise HTTPException(400, "Video dosyası boş olamaz.")
    if extension.lower() not in VIDEO_EXTENSIONS:
        raise HTTPException(400, "Video için MP4, WebM, MOV veya M4V yükleyin.")
    assert_safe_video_upload(content, extension, original_name)
    if not _video_head_is_valid(content[:64], extension):
        raise HTTPException(400, "Video uzantısı ile dosya içeriği uyuşmuyor.")
    if len(original_name or "") > 255:
        raise HTTPException(422, "Dosya adı çok uzun.")


def storage_key(*, company_id: int, program_id: int, prefix: str, extension: str) -> str:
    clean_ext = extension.lower()
    return f"{company_id}/remote-basic-ohs/{program_id}/{prefix}-{secrets.token_hex(16)}{clean_ext}"


def catalog_storage_key(*, package_id: int, prefix: str, extension: str) -> str:
    """Firma bağımsız katalog nesnesi için kalıcı ve tahmin edilemez anahtar."""
    clean_ext = extension.lower()
    return f"remote-basic-ohs/catalog/{package_id}/{prefix}-{secrets.token_hex(16)}{clean_ext}"


def _probe_video(path: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        # The deployment can still safely validate and stream the original
        # browser-compatible file.  Transcoding is an optional infrastructure
        # capability; absence must not make the existing application fail.
        return {"duration": 0, "processing_mode": "validated-original"}
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=codec_name,width,height,duration",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("Video teknik doğrulaması başlatılamadı.") from exc
    if result.returncode != 0:
        raise RuntimeError("Video işlenemedi veya bozuk görünüyor.")
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError("Video işleme çıktısı okunamadı.") from exc
    streams = [x for x in payload.get("streams") or [] if x.get("codec_type", "video") == "video"]
    stream = streams[0] if streams else (payload.get("streams") or [{}])[0]
    raw_duration = stream.get("duration") or (payload.get("format") or {}).get("duration") or 0
    try:
        duration = max(0, int(round(float(raw_duration))))
    except (TypeError, ValueError):
        duration = 0
    if duration <= 0:
        raise RuntimeError("Video süresi okunamadı.")
    return {
        "duration": duration,
        "width": int(stream["width"]) if stream.get("width") else None,
        "height": int(stream["height"]) if stream.get("height") else None,
        "codec": str(stream.get("codec_name") or "")[:80] or None,
        "processing_mode": "ffprobe-validated-original",
    }


def process_remote_video(video_id: int) -> dict[str, Any]:
    """Validate a stored video in a worker-safe, idempotent operation."""
    with SessionLocal() as db:
        video = db.get(RemoteTrainingVideo, video_id)
        if not video:
            return {"status": "missing", "video_id": video_id}
        if video.status == "archived":
            return {"status": "archived", "video_id": video_id}
        video.status = "processing"
        video.processing_error = None
        db.commit()
        temporary_path: Path | None = None
        try:
            store = get_object_store()
            path = store.resolve_local_path(video.storage_key)
            if path is None or not path.is_file():
                content = store.get_bytes(video.storage_key)
                tmp = tempfile.NamedTemporaryFile(prefix="remote-video-", suffix=Path(video.original_file_name).suffix, delete=False)
                tmp.write(content)
                tmp.close()
                temporary_path = Path(tmp.name)
                path = temporary_path
            metadata = _probe_video(path)
            video.duration_seconds = int(metadata.get("duration") or 0)
            video.width = metadata.get("width")
            video.height = metadata.get("height")
            video.codec = metadata.get("codec")
            video.status = "ready_for_review"
            video.processing_error = None
            program = db.get(RemoteTrainingProgram, video.program_id)
            if program is not None:
                durations = db.scalars(
                    select(RemoteTrainingVideo.duration_seconds).where(
                        RemoteTrainingVideo.program_id == video.program_id,
                        RemoteTrainingVideo.is_current.is_(True),
                        RemoteTrainingVideo.status.notin_(("archived", "processing_failed")),
                    )
                ).all()
                program.total_duration_seconds = int(sum(int(value or 0) for value in durations))
            db.commit()
            return {"status": video.status, "video_id": video.id, **metadata}
        except Exception as exc:
            logger.warning("Remote video processing failed: video_id=%s", video_id, exc_info=True)
            video.status = "processing_failed"
            video.processing_error = str(exc)[:1000]
            db.commit()
            return {"status": video.status, "video_id": video_id, "error": video.processing_error}
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)


def process_remote_catalog_video(video_id: int) -> dict[str, Any]:
    """Validate a central-catalog video without linking it to a company."""
    with SessionLocal() as db:
        video = db.get(RemoteTrainingCatalogVideo, video_id)
        if not video:
            return {"status": "missing", "video_id": video_id}
        if video.status == "archived":
            return {"status": "archived", "video_id": video_id}
        video.status = "processing"
        video.processing_error = None
        db.commit()
        temporary_path: Path | None = None
        try:
            store = get_object_store()
            path = store.resolve_local_path(video.storage_key)
            if path is None or not path.is_file():
                content = store.get_bytes(video.storage_key)
                tmp = tempfile.NamedTemporaryFile(
                    prefix="remote-catalog-video-",
                    suffix=Path(video.original_file_name).suffix,
                    delete=False,
                )
                tmp.write(content)
                tmp.close()
                temporary_path = Path(tmp.name)
                path = temporary_path
            metadata = _probe_video(path)
            video.duration_seconds = int(metadata.get("duration") or 0)
            video.width = metadata.get("width")
            video.height = metadata.get("height")
            video.codec = metadata.get("codec")
            video.status = "ready_for_review"
            video.processing_error = None
            package = db.get(RemoteTrainingCatalogPackage, video.package_id)
            if package is not None:
                durations = db.scalars(
                    select(RemoteTrainingCatalogVideo.duration_seconds).where(
                        RemoteTrainingCatalogVideo.package_id == video.package_id,
                        RemoteTrainingCatalogVideo.is_current.is_(True),
                        RemoteTrainingCatalogVideo.status.notin_(("archived", "processing_failed")),
                    )
                ).all()
                package.total_duration_seconds = int(sum(int(value or 0) for value in durations))
            db.commit()
            return {"status": video.status, "video_id": video.id, **metadata}
        except Exception as exc:
            logger.warning("Remote catalog video processing failed: video_id=%s", video_id, exc_info=True)
            video.status = "processing_failed"
            video.processing_error = str(exc)[:1000]
            db.commit()
            return {"status": video.status, "video_id": video_id, "error": video.processing_error}
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)


def enqueue_video_processing(db: Session, video: RemoteTrainingVideo) -> str:
    record = enqueue("remote_basic_ohs_video_processing", process_remote_video, video.id)
    video.processing_job_id = record.id
    return record.id


def enqueue_catalog_video_processing(db: Session, video: RemoteTrainingCatalogVideo) -> str:
    record = enqueue("remote_basic_ohs_catalog_video_processing", process_remote_catalog_video, video.id)
    video.processing_job_id = record.id
    return record.id


def recalculate_program_duration(db: Session, program_id: int) -> int:
    """Keep the program duration derived from the current video revisions."""
    program = db.get(RemoteTrainingProgram, program_id)
    if program is None:
        return 0
    durations = db.scalars(
        select(RemoteTrainingVideo.duration_seconds).where(
            RemoteTrainingVideo.program_id == program_id,
            RemoteTrainingVideo.is_current.is_(True),
            RemoteTrainingVideo.status.notin_(("archived", "processing_failed")),
        )
    ).all()
    program.total_duration_seconds = int(sum(int(value or 0) for value in durations))
    return program.total_duration_seconds


def recalculate_catalog_package_duration(db: Session, package_id: int) -> int:
    """Keep a central package duration derived from current video revisions."""
    package = db.get(RemoteTrainingCatalogPackage, package_id)
    if package is None:
        return 0
    durations = db.scalars(
        select(RemoteTrainingCatalogVideo.duration_seconds).where(
            RemoteTrainingCatalogVideo.package_id == package_id,
            RemoteTrainingCatalogVideo.is_current.is_(True),
            RemoteTrainingCatalogVideo.status.notin_(("archived", "processing_failed")),
        )
    ).all()
    package.total_duration_seconds = int(sum(int(value or 0) for value in durations))
    return package.total_duration_seconds


def _current_required_videos(
    db: Session, program_id: int, sector_codes: set[str] | None = None
) -> list[RemoteTrainingVideo]:
    program = db.get(RemoteTrainingProgram, program_id)
    strict_program = bool(
        program and str(getattr(program, "policy_mode", "legacy") or "legacy").lower() == "strict"
    )
    conditions = [
        RemoteTrainingVideo.program_id == program_id,
        RemoteTrainingVideo.is_current.is_(True),
        RemoteTrainingVideo.status == "published",
        RemoteTrainingSection.status == "active",
    ]
    # Legacy programs preserve their historical required-only semantics.  A
    # strict catalog snapshot treats every published video in every active
    # section as mandatory; an accidental optional flag cannot bypass the
    # common pilot rule.
    if not strict_program:
        conditions.extend(
            [
                RemoteTrainingVideo.is_required.is_(True),
                RemoteTrainingSection.is_required.is_(True),
            ]
        )
    stmt = (
        select(RemoteTrainingVideo)
        .join(RemoteTrainingSection, RemoteTrainingSection.id == RemoteTrainingVideo.section_id)
        .where(*conditions)
    )
    if sector_codes is not None:
        stmt = stmt.where(RemoteTrainingSection.sector_code.in_(sector_codes))
    return list(
        db.scalars(
            stmt.order_by(RemoteTrainingSection.order_index, RemoteTrainingVideo.order_index)
        ).all()
    )


def _decode_coverage(value: str | None) -> list[list[float]]:
    try:
        raw = json.loads(value or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    intervals: list[list[float]] = []
    if not isinstance(raw, list):
        return intervals
    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        try:
            start, end = float(item[0]), float(item[1])
        except (TypeError, ValueError):
            continue
        if end > start >= 0:
            intervals.append([start, end])
    return intervals


STRICT_END_RECONCILIATION_SECONDS = 8.0
STRICT_END_POSITION_TOLERANCE_SECONDS = 1.5


def reconcile_strict_video_end(
    intervals: list[list[float]],
    *,
    current_position: float,
    requested_position: float,
    duration: float,
) -> tuple[list[list[float]], float, float] | None:
    """Close only the final observed tail after a real media ``ended`` event.

    Mobile browsers can emit the last heartbeat a few seconds before the
    media element reaches its exact duration.  The server still knows that the
    learner was already in the final tail, so accepting that small tail on an
    ``ended`` event prevents a completed video from remaining locked.  The
    caller must still verify that the request is an ``ended`` event; this
    helper intentionally has no seek or forward-progress authority of its own.
    """
    if duration <= 0 or requested_position < duration - STRICT_END_POSITION_TOLERANCE_SECONDS:
        return None
    coverage_end = max((float(right) for _left, right in intervals), default=0.0)
    if max(float(current_position), coverage_end) < duration - STRICT_END_RECONCILIATION_SECONDS:
        return None
    tail_start = max(0.0, duration - STRICT_END_RECONCILIATION_SECONDS)
    merged, covered_seconds = _merge_coverage(intervals, tail_start, duration, duration)
    return merged, covered_seconds, duration


def _merge_coverage(
    intervals: list[list[float]], start: float, end: float, duration: float
) -> tuple[list[list[float]], float]:
    if end <= start:
        return intervals, sum(max(0.0, right - left) for left, right in intervals)
    # Copy existing rows before merging so a retry cannot mutate the object
    # decoded from the previous database value in place.
    values = [[float(left), float(right)] for left, right in intervals]
    values.append([max(0.0, start), min(duration, end)])
    values = [item for item in values if item[1] > item[0]]
    values.sort(key=lambda item: item[0])
    merged: list[list[float]] = []
    for left, right in values:
        if not merged or left > merged[-1][1] + 0.05:
            merged.append([left, right])
        else:
            merged[-1][1] = max(merged[-1][1], right)
    return merged, sum(max(0.0, right - left) for left, right in merged)


def _progress_complete_ids(
    db: Session, assignment_id: int
) -> set[int]:
    return {
        int(row.video_id)
        for row in db.scalars(
            select(RemoteTrainingVideoProgress).where(
                RemoteTrainingVideoProgress.assignment_id == assignment_id,
                RemoteTrainingVideoProgress.status == "completed",
            )
        ).all()
    }


def next_uncompleted_video(
    db: Session, assignment: RemoteTrainingAssignment
) -> RemoteTrainingVideo | None:
    program = load_program(db, assignment.program_id)
    required = _current_required_videos(db, program.id, assignment_sector_codes(db, assignment))
    complete_ids = _progress_complete_ids(db, assignment.id)
    return next((video for video in required if video.id not in complete_ids), None)


def assert_video_unlocked(
    db: Session, assignment: RemoteTrainingAssignment, video: RemoteTrainingVideo
) -> None:
    """Block opening/progressing a later lesson in the strict pilot.

    Previously completed lessons remain reviewable.  The first incomplete
    required lesson is the only forward lesson that can be opened.
    """
    program = load_program(db, assignment.program_id)
    if not strict_sequence_enabled(program):
        return
    required = _current_required_videos(db, program.id, assignment_sector_codes(db, assignment))
    order = {row.id: index for index, row in enumerate(required)}
    requested_index = order.get(video.id)
    if requested_index is None:
        raise HTTPException(403, "Bu video çalışanın zorunlu ders kapsamına dahil değil.")
    complete_ids = _progress_complete_ids(db, assignment.id)
    next_video = next((row for row in required if row.id not in complete_ids), None)
    if next_video is None:
        return
    if video.id != next_video.id and video.id not in complete_ids:
        raise HTTPException(
            409,
            f"Önce sıradaki dersi tamamlayın: {next_video.title}.",
        )


def _latest_checkpoint_answer(
    db: Session, assignment_id: int, question_id: int
) -> RemoteTrainingCheckpointAnswer | None:
    return db.scalar(
        select(RemoteTrainingCheckpointAnswer)
        .where(
            RemoteTrainingCheckpointAnswer.assignment_id == assignment_id,
            RemoteTrainingCheckpointAnswer.question_id == question_id,
        )
        .order_by(desc(RemoteTrainingCheckpointAnswer.id))
        .limit(1)
    )


def recalculate_assignment(db: Session, assignment: RemoteTrainingAssignment) -> dict[str, Any]:
    program = load_program(db, assignment.program_id)
    sector_codes = assignment_sector_codes(db, assignment)
    required_videos = _current_required_videos(db, program.id, sector_codes)
    progress_rows = list(
        db.scalars(
            select(RemoteTrainingVideoProgress).where(
                RemoteTrainingVideoProgress.assignment_id == assignment.id
            )
        ).all()
    )
    progress_by_video = {row.video_id: row for row in progress_rows}
    video_complete = {
        video.id: progress_by_video.get(video.id, None)
        and progress_by_video[video.id].status == "completed"
        for video in required_videos
    }
    question_stmt = select(RemoteTrainingQuestion).where(
        RemoteTrainingQuestion.program_id == program.id,
        RemoteTrainingQuestion.is_required.is_(True),
    )
    if sector_codes is not None:
        question_stmt = question_stmt.where(RemoteTrainingQuestion.sector_code.in_(sector_codes))
    required_questions = list(db.scalars(question_stmt).all())
    checkpoint_complete = all(
        (answer := _latest_checkpoint_answer(db, assignment.id, question.id)) is not None
        and bool(answer.is_correct)
        for question in required_questions
    )
    exam = db.scalar(
        select(RemoteTrainingExamAttempt)
        .where(
            RemoteTrainingExamAttempt.assignment_id == assignment.id,
            RemoteTrainingExamAttempt.passed.is_(True),
        )
        .order_by(desc(RemoteTrainingExamAttempt.id))
        .limit(1)
    )
    exam_complete = not program.requires_final_exam or exam is not None
    required_complete = bool(required_videos) and all(video_complete.values())
    complete = required_complete and checkpoint_complete and exam_complete
    now = datetime.utcnow()
    if complete:
        assignment.status = "completed"
        assignment.completed_at = assignment.completed_at or now
    elif assignment.status not in {"expired", "failed"}:
        started = any((row.status != "not_started") for row in progress_rows)
        assignment.status = "in_progress" if started else "not_started"
        assignment.completed_at = None
    return {
        "sector_codes": sorted(sector_codes) if sector_codes is not None else None,
        "sector_scope_mode": "scoped" if sector_codes is not None else "legacy",
        "required_video_count": len(required_videos),
        "completed_video_count": sum(1 for value in video_complete.values() if value),
        "required_videos_complete": required_complete,
        "required_checkpoint_count": len(required_questions),
        "required_checkpoints_complete": checkpoint_complete,
        "exam_required": bool(program.requires_final_exam),
        "exam_passed": bool(exam_complete),
        "complete": complete,
        "status": assignment.status,
        "exam_score": exam.score if exam else None,
    }


def ensure_certificate(db: Session, assignment: RemoteTrainingAssignment) -> RemoteTrainingCertificate | None:
    # A certificate request may be the first operation after the last progress
    # event.  Recalculate here so completion cannot depend on a prior UI call.
    if assignment.status != "completed":
        recalculate_assignment(db, assignment)
    if assignment.status != "completed":
        return None
    # Certificates are historical evidence.  Do not issue one with a guessed
    # workplace identity, SGK/NACE or hazard class.
    if not all(
        (
            assignment.employee_name_snapshot,
            assignment.workplace_name_snapshot,
            assignment.sgk_registration_number_snapshot,
            assignment.nace_code_snapshot,
            assignment.nace_description_snapshot,
            assignment.hazard_class_snapshot,
        )
    ):
        return None
    current = db.scalar(
        select(RemoteTrainingCertificate).where(
            RemoteTrainingCertificate.assignment_id == assignment.id
        )
    )
    if current:
        return current
    program = load_program(db, assignment.program_id)
    company = db.get(Company, assignment.company_id)
    score = db.scalar(
        select(RemoteTrainingExamAttempt.score)
        .where(
            RemoteTrainingExamAttempt.assignment_id == assignment.id,
            RemoteTrainingExamAttempt.passed.is_(True),
        )
        .order_by(desc(RemoteTrainingExamAttempt.id))
        .limit(1)
    )
    seed = f"remote-basic-ohs|{assignment.id}|{assignment.employee_id}|{datetime.utcnow().isoformat()}|{secrets.token_hex(8)}"
    certificate = RemoteTrainingCertificate(
        company_id=assignment.company_id,
        program_id=assignment.program_id,
        assignment_id=assignment.id,
        employee_id=assignment.employee_id,
        employee_name_snapshot=assignment.employee_name_snapshot,
        company_name_snapshot=company.name if company else str(assignment.company_id),
        workplace_name_snapshot=assignment.workplace_name_snapshot,
        sgk_registration_number_snapshot=assignment.sgk_registration_number_snapshot,
        nace_code_snapshot=assignment.nace_code_snapshot,
        nace_description_snapshot=assignment.nace_description_snapshot,
        hazard_class_snapshot=assignment.hazard_class_snapshot,
        training_name=program.title,
        training_type=REMOTE_TRAINING_TYPE,
        training_duration_seconds=program.total_duration_seconds,
        training_date=(assignment.completed_at.date() if assignment.completed_at else date.today()),
        instructor_name_snapshot=program.instructor_name,
        examination_score=int(score) if score is not None else None,
        certificate_number=f"ROHS-{date.today():%Y%m%d}-{assignment.id:08d}",
        verification_code=hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32].upper(),
    )
    db.add(certificate)
    db.flush()
    return certificate


def build_certificate_pdf(db: Session, certificate: RemoteTrainingCertificate) -> bytes:
    """Reuse the existing certificate renderer through a read-only adapter."""
    employee = SimpleNamespace(
        id=certificate.employee_id,
        full_name=certificate.employee_name_snapshot,
        national_id_masked=None,
        job_title="",
    )
    participant = SimpleNamespace(
        employee_id=certificate.employee_id,
        certificate_number=certificate.certificate_number,
    )
    duration_hours = max(1, (int(certificate.training_duration_seconds or 0) + 2699) // 2700)
    training = SimpleNamespace(
        id=certificate.program_id,
        title=certificate.training_name,
        training_type=REMOTE_TRAINING_TYPE,
        delivery_method="Uzaktan",
        start_date=certificate.training_date,
        end_date=certificate.training_date,
        duration_hours=duration_hours,
        # Do not infer an official hazard class for historical evidence.  The
        # existing renderer tolerates an empty display value; the certificate
        # keeps the exact snapshot captured at assignment time.
        hazard_class=certificate.hazard_class_snapshot or "",
        sector=certificate.nace_code_snapshot or "",
        instructor_name=certificate.instructor_name_snapshot or "",
        instructor_qualification="",
        workplace_physician=None,
        employer_representative=None,
        stamp_text=(
            "Bu kayıt, Basic Occupational Health and Safety Training uzaktan eğitim "
            "modülündeki video, sınav ve tamamlanma kayıtlarına dayanır."
        ),
        verification_code=certificate.verification_code,
        logo_path=None,
        participants=[participant],
    )
    from app.services.training_pdfs import build_certificates_pdf

    return build_certificates_pdf(
        company_name=certificate.company_name_snapshot,
        training=training,
        employees={certificate.employee_id: employee},
    )


def create_playback_token(
    *, user: User, video: RemoteTrainingVideo, assignment_id: int | None, mode: str
) -> str:
    ttl = max(60, min(int(getattr(settings, "remote_basic_ohs_playback_ttl_seconds", 300) or 300), 900))
    expires = datetime.now(timezone.utc) + timedelta(seconds=ttl)
    payload = {
        "sub": str(user.id),
        "purpose": "remote_video",
        "tv": int(getattr(user, "token_version", 0) or 0),
        "video_id": int(video.id),
        "assignment_id": int(assignment_id) if assignment_id else None,
        "mode": mode,
        "jti": secrets.token_hex(16),
        "exp": expires,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_catalog_playback_token(
    *, user: User, video: RemoteTrainingCatalogVideo
) -> str:
    ttl = max(60, min(int(getattr(settings, "remote_basic_ohs_playback_ttl_seconds", 300) or 300), 900))
    expires = datetime.now(timezone.utc) + timedelta(seconds=ttl)
    payload = {
        "sub": str(user.id),
        "purpose": "remote_catalog_video",
        "tv": int(getattr(user, "token_version", 0) or 0),
        "video_id": int(video.id),
        "jti": secrets.token_hex(16),
        "exp": expires,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_catalog_playback_token(
    db: Session, token: str, video_id: int
) -> tuple[User, RemoteTrainingCatalogVideo]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        if payload.get("purpose") != "remote_catalog_video" or int(payload.get("video_id")) != int(video_id):
            raise ValueError
        user_id = int(payload.get("sub"))
        tv = int(payload.get("tv") or 0)
    except (JWTError, TypeError, ValueError, KeyError):
        raise HTTPException(401, "Video oynatma bağlantısı geçersiz veya süresi dolmuş.")
    user = db.get(User, user_id)
    if not user or not user.is_active or int(getattr(user, "token_version", 0) or 0) != tv:
        raise HTTPException(401, "Video oynatma oturumu geçersiz.")
    from app.core.rls import apply_rls_user
    from app.core.tenant_context import bind_user_tenant

    bind_user_tenant(user)
    apply_rls_user(db, user)
    video = db.get(RemoteTrainingCatalogVideo, video_id)
    if video is None:
        raise HTTPException(404, "Merkezi eğitim videosu bulunamadı.")
    package = db.get(RemoteTrainingCatalogPackage, video.package_id)
    if package is None or not is_manager(user):
        raise HTTPException(403, "Merkezi video önizleme yetkiniz yok.")
    if user.role != UserRole.GLOBAL_ADMIN:
        allowed_osgb_id = user.osgb_id
        if not allowed_osgb_id and user.company_id:
            company = db.get(Company, user.company_id)
            allowed_osgb_id = company.osgb_id if company else None
        if package.osgb_id != allowed_osgb_id:
            raise HTTPException(403, "Merkezi video OSGB kapsamınız dışında.")
    if video.status not in {"ready_for_review", "published", "unpublished"}:
        raise HTTPException(409, "Bu durumdaki video önizlenemez.")
    return user, video


def decode_playback_token(db: Session, token: str, video_id: int) -> tuple[User, RemoteTrainingVideo, int | None, str]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        if payload.get("purpose") != "remote_video" or int(payload.get("video_id")) != int(video_id):
            raise ValueError
        user_id = int(payload.get("sub"))
        tv = int(payload.get("tv") or 0)
        assignment_id = int(payload["assignment_id"]) if payload.get("assignment_id") else None
        mode = str(payload.get("mode") or "")
    except (JWTError, TypeError, ValueError, KeyError):
        raise HTTPException(401, "Video oynatma bağlantısı geçersiz veya süresi dolmuş.")
    user = db.get(User, user_id)
    if not user or not user.is_active or int(getattr(user, "token_version", 0) or 0) != tv:
        raise HTTPException(401, "Video oynatma oturumu geçersiz.")
    # The stream route intentionally has no bearer dependency.  Recreate the
    # same tenant/RLS context from the signed subject before loading any row;
    # failure must remain fail-closed instead of silently bypassing RLS setup.
    from app.core.rls import apply_rls_user
    from app.core.tenant_context import bind_user_tenant

    bind_user_tenant(user)
    apply_rls_user(db, user)
    video = load_video(db, video_id)
    program = load_program(db, video.program_id)
    if mode == "preview":
        if not is_manager(user):
            raise HTTPException(403, "Önizleme yetkiniz yok.")
        assert_program_access(db, user, program)
    elif mode == "employee":
        if not assignment_id:
            raise HTTPException(401, "Video ataması bulunamadı.")
        assignment = load_assignment(db, assignment_id)
        if assignment.program_id != program.id or assignment.employee_id <= 0:
            raise HTTPException(403, "Video ataması geçersiz.")
        assert_assignment_access(db, user, assignment, write=False)
        section = load_section(db, video.section_id)
        if not assignment_allows_sector(db, assignment, section.sector_code):
            raise HTTPException(403, "Video bu çalışanın ders kapsamına dahil değil.")
        if program.status != "published" or video.status != "published" or not video.is_current:
            raise HTTPException(403, "Video henüz çalışana açık değil.")
    else:
        raise HTTPException(401, "Video oynatma bağlantısı geçersiz.")
    return user, video, assignment_id, mode


def response_for_video(video: RemoteTrainingVideo):
    """Return a protected inline response without exposing a permanent storage path."""
    from fastapi.responses import FileResponse, StreamingResponse

    store = get_object_store()
    local = store.resolve_local_path(video.storage_key)
    media_type = video.content_type or "video/mp4"
    safe_name = Path(video.original_file_name or "video").name
    safe_name = "".join(char for char in safe_name if char not in {"\r", "\n", '"'}) or "video"
    if local is not None and local.is_file():
        return FileResponse(
            local,
            media_type=media_type,
            filename=safe_name,
            headers={"Content-Disposition": f'inline; filename="{safe_name}"'},
        )
    if not store.exists(video.storage_key):
        raise HTTPException(404, "Video depolamada bulunamadı.")
    return StreamingResponse(
        BytesIO(store.get_bytes(video.storage_key)),
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{safe_name}"'},
    )
