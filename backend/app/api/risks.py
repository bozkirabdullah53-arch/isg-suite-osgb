"""Risk değerlendirme API — İSG PRO 2026 risk modülü entegrasyonu."""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import date, datetime, timezone
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, selectinload

logger = logging.getLogger(__name__)

from app.api.company_access import company_ids_for_query, effective_company_id, ensure_company_access
from app.api.deps import get_current_user, require_roles
from app.core.config import settings
from app.core.database import get_db
from app.models.entities import (
    Branch,
    Company,
    Hazard,
    HazardCategory,
    IsgModule,
    IsgRecord,
    ProfessionalType,
    RecordStatus,
    RiskAssessment,
    RiskDof,
    RiskMedia,
    RiskRevision,
    TrainingSession,
    User,
    UserRole,
    WorkplaceDepartment,
)
from app.schemas.risk import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
    HazopData,
    HazardHintRequest,
    RiskAssessmentInfoUpdate,
    RiskDofListItem,
    HazardCategoryResponse,
    HazardResponse,
    RiskCalculateRequest,
    RiskCreate,
    RiskDofComplete,
    RiskDofCreate,
    RiskDofResponse,
    RiskDofUpdate,
    RiskMediaResponse,
    RiskMediaTagsUpdate,
    RiskResponse,
    RiskRevisionResponse,
    RiskUpdate,
)
from app.services.ai_hazard_hint import HINT_ENGINE, suggest_hazard_from_text
from app.services.assigned_team import team_names
from app.services.audit import add_audit_log
from app.services.hazard_seed import seed_hazard_library
from app.services.risk_photo_tags import (
    TAGS_ENGINE,
    catalog as photo_tag_catalog,
    parse_form_tags,
    parse_tags,
    serialize_selected,
)
from app.services.risk_reports import build_dof_excel, build_risk_excel, build_risk_pdf
from app.services.risk_nace_roadmap import build_risk_nace_roadmap
from app.services.training_nace_classification import resolve_exact_nace
from app.models.training_nace import TrainingNaceSnapshot
from app.services.risk_methods import DEFAULT_METHOD, METHOD_CATALOG, resolve_method
from app.services.risk_hazop import hazop_meta_payload, normalize_hazop_data, priority_details
from app.services.risk_scoring import (
    SUPPORTED_SCORING_METHODS,
    evaluate,
    evaluate_method,
    canonical_risk_level,
    fine_kinney_level_details,
    fine_kinney_meta_payload,
    meta_payload,
)
from app.services.risk_suggestions import get_suggestions
from app.services.risk_validity import build_validity, document_meta_rows
from app.services.upload_gateway import delete_relative, persist_relative
from app.services.upload_security import assert_safe_upload

router = APIRouter(prefix="/risks", tags=["Risk Değerlendirme"])
# OSGB company_admin menüde risk yok; yazma da saha uzmanı + global admin.
EDIT_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST)
ALLOWED_PHOTO = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
ALLOWED_MEDIA = ALLOWED_PHOTO | {".pdf", ".mp4", ".avi", ".mov", ".bmp", ".doc", ".docx", ".xls", ".xlsx"}
LEGACY_TAG = "[ISG#"
REVISION_FIELDS = (
    "method_code",
    "hazop_data_json",
    "department_name",
    "hazard_id",
    "activity",
    "risk_definition",
    "affected_people",
    "affected_group",
    "existing_measures",
    "additional_measures",
    "probability",
    "frequency",
    "severity",
    "risk_score",
    "risk_level",
    "residual_probability",
    "residual_frequency",
    "residual_severity",
    "residual_score",
    "residual_level",
    "term_days",
    "term_date",
    "status",
)


def _implemented_method(code: str | None, *, fallback: str = DEFAULT_METHOD) -> str:
    """Resolve and validate a method without allowing an accidental fallback."""
    explicit = code is not None and bool(str(code).strip())
    key = (code if explicit else fallback or DEFAULT_METHOD).strip()
    method = METHOD_CATALOG.get(key)
    if not method:
        if not explicit:
            return DEFAULT_METHOD
        raise HTTPException(422, "Geçersiz risk değerlendirme yöntemi.")
    if key not in SUPPORTED_SCORING_METHODS or not method.get("implemented"):
        if not explicit:
            return DEFAULT_METHOD
        raise HTTPException(422, f"{method['label']} henüz aktif değil; bu yöntem sırayla geliştirilecek.")
    return key


def _display_risk_level(row: RiskAssessment) -> str:
    """Use the score for 5x5 display so legacy labels cannot drift."""
    return (
        canonical_risk_level(
            getattr(row, "method_code", None),
            getattr(row, "risk_score", None),
            getattr(row, "risk_level", None),
        )
        or "Tanımsız"
    )


def _risk_level_filter(level: str):
    """Filter 5x5 rows by score while keeping other methods' labels intact."""
    method_is_5x5 = or_(
        RiskAssessment.method_code == "5x5_l",
        RiskAssessment.method_code.is_(None),
    )
    method_is_other = and_(
        RiskAssessment.method_code.is_not(None),
        RiskAssessment.method_code != "5x5_l",
    )
    score = RiskAssessment.risk_score
    bounds = {
        "Kabul Edilebilir": score <= 5,
        "Düşük": and_(score >= 6, score <= 8),
        "Orta": and_(score >= 9, score <= 12),
        "Yüksek": and_(score >= 13, score <= 16),
        "Çok Yüksek": score >= 17,
    }
    if level not in bounds:
        return RiskAssessment.risk_level == level
    return or_(
        and_(method_is_5x5, bounds[level]),
        and_(method_is_other, RiskAssessment.risk_level == level),
    )


def _calculate_risk(
    *,
    method_code: str,
    probability: float | None,
    severity: float | None,
    frequency: float | None = None,
    hazop_data: dict | None = None,
    term_override_days: int | None = None,
) -> dict:
    try:
        if method_code == "5x5_l" and frequency is not None:
            raise ValueError("5x5 yönteminde frekans alanı kullanılamaz.")
        if method_code == "hazop" and term_override_days is not None:
            raise ValueError("HAZOP termin önerisi öncelikten türetilir; sayısal override kullanılamaz.")
        if method_code != "hazop" and (probability is None or severity is None):
            raise ValueError("Seçilen yöntem için gerekli puan alanları zorunludur.")
        return evaluate_method(
            method_code,
            probability,
            severity,
            frequency=frequency,
            hazop_data=hazop_data,
            term_override_days=term_override_days,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def _calculate_residual(
    *,
    method_code: str,
    probability: float | None,
    frequency: float | None,
    severity: float | None,
) -> dict | None:
    if method_code == "hazop" and any(value is not None for value in (probability, frequency, severity)):
        raise HTTPException(422, "HAZOP yönteminde sayısal artık risk alanları kullanılmaz; sapma önceliğini güncelleyin.")
    if method_code == "5x5_l" and frequency is not None:
        raise HTTPException(422, "5x5 yönteminde frekans/artık frekans alanı kullanılamaz.")
    values = (probability, frequency, severity) if method_code == "fine_kinney" else (probability, severity)
    if all(value is None for value in values):
        return None
    if any(value is None for value in values):
        raise HTTPException(422, "Artık risk için tüm yöntem değerleri birlikte girilmelidir.")
    return _calculate_risk(
        method_code=method_code,
        probability=float(probability),
        frequency=float(frequency) if frequency is not None else None,
        severity=float(severity),
    )


def ensure_access(db: Session, user: User, company_id: int) -> None:
    ensure_company_access(db, user, company_id)


def _assessment_context(db: Session, company: Company) -> dict:
    """Belge geçerliliği + değerlendirme ekibi.

    Belge tarihi girilmemişse ilk risk kaydının tarihi tahmini olarak kullanılır.
    """
    from app.models.entities import Employee
    from app.services.assigned_team import assigned_team

    first_created = db.scalar(
        select(func.min(RiskAssessment.created_at)).where(RiskAssessment.company_id == company.id)
    )
    fallback = first_created.date() if hasattr(first_created, "date") else first_created
    names = team_names(db, company.id)
    team = assigned_team(db, company.id)
    emp_count = db.scalar(
        select(func.count()).select_from(Employee).where(
            Employee.company_id == company.id,
            Employee.is_active.is_(True),
        )
    ) or 0
    return {
        "validity": build_validity(
            hazard_class=company.hazard_class,
            assessment_date=company.risk_assessment_date,
            fallback_date=fallback,
            method_code=getattr(company, "risk_method", None),
        ),
        "workplace_physician": names.get(ProfessionalType.WORKPLACE_PHYSICIAN.value),
        "safety_specialist": names.get(ProfessionalType.SAFETY_SPECIALIST.value),
        "employer_representative": company.authorized_person,
        "employee_representative": company.risk_team_employee_rep,
        "support_staff": company.risk_team_support_staff,
        "team_details": team,
        "employee_count": int(emp_count),
        "document_no": getattr(company, "risk_document_no", None),
        "revision_no": getattr(company, "risk_revision_no", None),
        "revision_reason": getattr(company, "risk_revision_reason", None),
        "scope_note": getattr(company, "risk_scope_note", None),
        "method_code": getattr(company, "risk_method", None) or "5x5_l",
    }


def _upload_root() -> Path:
    root = Path(settings.upload_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _parse_regs(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _next_code(db: Session, prefix: str, model, field) -> str:
    count = db.scalar(select(func.count()).select_from(model)) or 0
    return f"{prefix}-{count + 1:04d}"


def _media_file_type(ext: str) -> str:
    e = (ext or "").lower()
    if e in ALLOWED_PHOTO or e == ".bmp":
        return "photo"
    if e in {".mp4", ".avi", ".mov"}:
        return "video"
    if e == ".pdf":
        return "pdf"
    return "drawing"




def _as_naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _parse_form_datetime(value: str | None) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return _as_naive_utc(datetime.fromisoformat(raw.replace("Z", "+00:00")))
    except ValueError as exc:
        raise HTTPException(422, "Fotoğraf tarihi geçersiz.") from exc


def _media_response(m: RiskMedia) -> RiskMediaResponse:
    parsed = parse_tags(getattr(m, "tags_json", None))
    return RiskMediaResponse(
        id=m.id,
        risk_id=m.risk_id,
        client_reference=getattr(m, "client_reference", None),
        original_name=m.original_name,
        content_type=m.content_type,
        file_type=getattr(m, "file_type", None),
        file_size=getattr(m, "file_size", None),
        description=getattr(m, "description", None),
        dof_id=getattr(m, "dof_id", None),
        captured_at=getattr(m, "captured_at", None),
        gps_lat=getattr(m, "gps_lat", None),
        gps_lng=getattr(m, "gps_lng", None),
        gps_accuracy_m=getattr(m, "gps_accuracy_m", None),
        created_at=m.created_at,
        tags=list(parsed["selected"]),
        tag_labels=list(parsed["labels"]),
    )


def _to_response(row: RiskAssessment, hazard: Hazard | None = None, category: HazardCategory | None = None) -> RiskResponse:
    method_code = getattr(row, "method_code", None) or DEFAULT_METHOD
    method = resolve_method(method_code)
    hazop_data = None
    if method_code == "hazop" and getattr(row, "hazop_data_json", None):
        try:
            hazop_data = HazopData.model_validate(json.loads(row.hazop_data_json))
        except (TypeError, ValueError, json.JSONDecodeError):
            logger.warning("Geçersiz HAZOP verisi risk kaydında bulundu: %s", row.id)
    display_level = _display_risk_level(row)
    if method_code == "fine_kinney":
        _, level_label, risk_action = fine_kinney_level_details(float(row.risk_score or 0))
    elif method_code == "hazop":
        priority = priority_details(hazop_data.priority if hazop_data else None)
        level_label = priority["label"]
        risk_action = priority["action"]
    else:
        level_label = display_level
        risk_action = next(
            (note for _, level, note in method.get("levels", []) if level == display_level),
            None,
        )
    revisions = [
        RiskRevisionResponse.model_validate(r)
        for r in list(getattr(row, "revisions", None) or [])[:40]
    ]
    return RiskResponse(
        id=row.id,
        risk_code=row.risk_code,
        company_id=row.company_id,
        branch_id=row.branch_id,
        record_origin=getattr(row, "record_origin", None) or "risk",
        client_reference=getattr(row, "client_reference", None),
        observed_at=getattr(row, "observed_at", None),
        observation_location=getattr(row, "observation_location", None),
        gps_lat=getattr(row, "gps_lat", None),
        gps_lng=getattr(row, "gps_lng", None),
        gps_accuracy_m=getattr(row, "gps_accuracy_m", None),
        department_id=getattr(row, "department_id", None),
        hazard_id=row.hazard_id,
        method_code=method_code,
        method_label=method.get("label"),
        method_formula=method.get("formula"),
        hazop_data=hazop_data,
        hazard_code=hazard.code if hazard else None,
        hazard_name=hazard.name if hazard else None,
        category_name=category.name if category else None,
        department_name=row.department_name,
        activity=row.activity,
        risk_definition=row.risk_definition,
        affected_people=row.affected_people,
        affected_group=row.affected_group,
        existing_measures=row.existing_measures,
        additional_measures=row.additional_measures,
        probability=row.probability,
        frequency=getattr(row, "frequency", None),
        severity=row.severity,
        risk_score=row.risk_score,
        risk_level=display_level,
        risk_level_label=level_label,
        risk_action=risk_action,
        residual_probability=getattr(row, "residual_probability", None),
        residual_frequency=getattr(row, "residual_frequency", None),
        residual_severity=getattr(row, "residual_severity", None),
        residual_score=getattr(row, "residual_score", None),
        residual_level=getattr(row, "residual_level", None),
        term_days=row.term_days,
        term_date=row.term_date,
        term_suggested=row.term_suggested,
        term_overridden=row.term_overridden,
        status=row.status,
        revision_no=row.revision_no,
        created_by_id=row.created_by_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        dofs=[RiskDofResponse.model_validate(d) for d in (row.dofs or [])],
        media=[_media_response(m) for m in (row.media_files or [])],
        revisions=revisions,
    )


def _snapshot_fields(row: RiskAssessment) -> dict:
    out = {}
    for key in REVISION_FIELDS:
        val = getattr(row, key, None)
        out[key] = "" if val is None else str(val)
    return out


def _record_field_revisions(
    db: Session,
    *,
    row: RiskAssessment,
    before: dict,
    user: User,
    reason: str | None,
) -> int:
    """Alan bazlı revizyon satırları yazar; yeni revision_no döner."""
    after = _snapshot_fields(row)
    changes = [(k, before.get(k, ""), after.get(k, "")) for k in REVISION_FIELDS if before.get(k, "") != after.get(k, "")]
    if not changes:
        return int(row.revision_no or 0)
    next_no = int(row.revision_no or 0) + 1
    for field_name, old_value, new_value in changes:
        db.add(
            RiskRevision(
                risk_id=row.id,
                revision_no=next_no,
                changed_by_id=user.id,
                field_name=field_name,
                old_value=old_value[:4000] if old_value else "",
                new_value=new_value[:4000] if new_value else "",
                change_reason=(reason or "")[:500] or None,
            )
        )
    row.revision_no = next_no
    return next_no


def _load_risk(db: Session, risk_id: int) -> RiskAssessment:
    row = db.scalar(
        select(RiskAssessment)
        .options(
            selectinload(RiskAssessment.dofs),
            selectinload(RiskAssessment.media_files),
            selectinload(RiskAssessment.revisions),
        )
        .where(RiskAssessment.id == risk_id)
    )
    if not row:
        raise HTTPException(404, "Risk kaydı bulunamadı.")
    return row


def _resolve_department(
    db: Session,
    *,
    company_id: int,
    department_id: int | None,
    department_name: str | None,
) -> tuple[int | None, str | None]:
    """Seçilen bölüm veya yeni ad ile bölüm oluştur/çöz."""
    if department_id:
        dep = db.get(WorkplaceDepartment, department_id)
        if not dep or dep.company_id != company_id:
            raise HTTPException(422, "Bölüm firma ile uyumlu değil.")
        return dep.id, dep.name
    name = (department_name or "").strip()
    if not name:
        return None, None
    existing = db.scalar(
        select(WorkplaceDepartment).where(
            WorkplaceDepartment.company_id == company_id,
            WorkplaceDepartment.name == name,
        )
    )
    if existing:
        if not existing.is_active:
            existing.is_active = True
            db.flush()
        return existing.id, existing.name
    dep = WorkplaceDepartment(company_id=company_id, name=name, is_active=True)
    db.add(dep)
    db.flush()
    return dep.id, dep.name


def _ensure_library(db: Session) -> None:
    count = db.scalar(select(func.count()).select_from(HazardCategory)) or 0
    if count == 0:
        seed_hazard_library(db)


@router.get("/meta")
def risk_meta(
    method_code: str = DEFAULT_METHOD,
    user: User = Depends(get_current_user),
):
    code = _implemented_method(method_code)
    if code == "hazop":
        return hazop_meta_payload()
    return fine_kinney_meta_payload() if code == "fine_kinney" else meta_payload()


@router.post("/calculate")
def risk_calculate(payload: RiskCalculateRequest, user: User = Depends(get_current_user)):
    code = _implemented_method(payload.method_code)
    return _calculate_risk(
        method_code=code,
        probability=payload.probability,
        frequency=payload.frequency,
        severity=payload.severity,
        hazop_data=payload.hazop_data.model_dump() if payload.hazop_data else None,
        term_override_days=payload.term_override_days,
    )


@router.post("/hazard-hint")
def hazard_hint(
    payload: HazardHintRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Türkçe anahtar kelime → önerilen tehlike kategorisi (AI stub, keyword-v1)."""
    text = (payload.text or "").strip()
    if not text:
        parts = [payload.activity or "", payload.risk_definition or ""]
        text = " ".join(p.strip() for p in parts if p and p.strip())
    hint = suggest_hazard_from_text(text, activity=payload.activity)
    category_id = None
    cat_name = hint.get("suggested_category")
    if cat_name:
        _ensure_library(db)
        row = db.scalar(select(HazardCategory).where(HazardCategory.name == cat_name))
        if row:
            category_id = row.id
    alts = []
    for alt in hint.get("alternatives") or []:
        aid = None
        aname = alt.get("category")
        if aname:
            arow = db.scalar(select(HazardCategory).where(HazardCategory.name == aname))
            if arow:
                aid = arow.id
        alts.append({**alt, "category_id": aid})
    return {
        **hint,
        "category_id": category_id,
        "alternatives": alts,
        "engine": HINT_ENGINE,
    }


@router.get("/photo-tag-catalog")
def get_photo_tag_catalog(user: User = Depends(get_current_user)):
    """0.9.121 — Risk fotoğrafı tehlike etiketi checklist kataloğu."""
    return {"engine": TAGS_ENGINE, "items": photo_tag_catalog()}


@router.post("/seed-library")
def seed_library(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    return seed_hazard_library(db)


@router.get("/categories", response_model=list[HazardCategoryResponse])
def list_categories(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _ensure_library(db)
    rows = list(db.scalars(select(HazardCategory).order_by(HazardCategory.sort_order, HazardCategory.name)).all())
    counts = dict(
        db.execute(
            select(Hazard.category_id, func.count())
            .where(Hazard.is_active.is_(True))
            .group_by(Hazard.category_id)
        ).all()
    )
    return [
        HazardCategoryResponse(
            id=r.id,
            name=r.name,
            icon=r.icon,
            sort_order=r.sort_order,
            hazard_count=int(counts.get(r.id, 0)),
        )
        for r in rows
    ]


@router.get("/departments", response_model=list[DepartmentResponse])
def list_departments(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    effective = effective_company_id(db, user, company_id)
    deps = list(
        db.scalars(
            select(WorkplaceDepartment)
            .where(WorkplaceDepartment.company_id == effective, WorkplaceDepartment.is_active.is_(True))
            .order_by(WorkplaceDepartment.name)
        ).all()
    )
    out = []
    for d in deps:
        cnt = db.scalar(
            select(func.count()).select_from(RiskAssessment).where(RiskAssessment.department_id == d.id)
        ) or 0
        out.append(
            DepartmentResponse(
                id=d.id,
                company_id=d.company_id,
                name=d.name,
                description=d.description,
                is_active=d.is_active,
                created_at=d.created_at,
                risk_count=int(cnt),
            )
        )
    return out


@router.post("/departments", response_model=DepartmentResponse)
def create_department(
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    ensure_access(db, user, payload.company_id)
    if not db.get(Company, payload.company_id):
        raise HTTPException(404, "Firma bulunamadı.")
    name = payload.name.strip()
    if len(name) < 2:
        raise HTTPException(422, "Bölüm adı en az 2 karakter olmalıdır.")
    existing = db.scalar(
        select(WorkplaceDepartment).where(
            WorkplaceDepartment.company_id == payload.company_id,
            WorkplaceDepartment.name == name,
        )
    )
    if existing:
        if not existing.is_active:
            existing.is_active = True
            existing.description = payload.description or existing.description
            db.commit()
            db.refresh(existing)
        return existing
    dep = WorkplaceDepartment(
        company_id=payload.company_id,
        name=name,
        description=payload.description,
        is_active=True,
    )
    db.add(dep)
    db.commit()
    db.refresh(dep)
    return dep



SUGGESTED_DEPARTMENTS = [
    "İdari Ofis", "Üretim", "Bakım", "Depo", "Sevkiyat", "Laboratuvar",
    "Kimyasal Depo", "Elektrik Odası", "Kazan Dairesi", "Atölye",
    "İnşaat Sahası", "Çatı", "Vinç Sahası",
]


def _dept_with_counts(db: Session, company_id: int) -> list[DepartmentResponse]:
    deps = list(
        db.scalars(
            select(WorkplaceDepartment)
            .where(WorkplaceDepartment.company_id == company_id, WorkplaceDepartment.is_active.is_(True))
            .order_by(WorkplaceDepartment.name)
        ).all()
    )
    out = []
    for d in deps:
        cnt = db.scalar(
            select(func.count()).select_from(RiskAssessment).where(RiskAssessment.department_id == d.id)
        ) or 0
        out.append(
            DepartmentResponse(
                id=d.id,
                company_id=d.company_id,
                name=d.name,
                description=d.description,
                is_active=d.is_active,
                created_at=d.created_at,
                risk_count=int(cnt),
            )
        )
    return out


@router.get("/stats")
def risk_stats(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """PRO /api/risk-istatistik parity + KPI sayaçları."""
    effective = effective_company_id(db, user, company_id)
    today = date.today()
    base = select(RiskAssessment).where(RiskAssessment.company_id == effective)
    risks = list(db.scalars(base).all())
    levels = ["Çok Yüksek", "Yüksek", "Orta", "Düşük", "Kabul Edilebilir"]
    level_counts = {lv: 0 for lv in levels}
    open_risks = 0
    overdue_terms = 0
    for r in risks:
        level = _display_risk_level(r)
        if level in level_counts:
            level_counts[level] += 1
        if (r.status or "") == "Açık":
            open_risks += 1
            if r.term_date and r.term_date < today:
                overdue_terms += 1

    dofs = list(
        db.scalars(
            select(RiskDof).where(
                RiskDof.risk_id.in_(select(RiskAssessment.id).where(RiskAssessment.company_id == effective))
            )
        ).all()
    )
    open_dofs = sum(1 for d in dofs if not d.is_completed)
    overdue_dofs = sum(
        1 for d in dofs if (not d.is_completed) and d.term_date and d.term_date < today
    )
    due_soon = sum(
        1
        for d in dofs
        if (not d.is_completed)
        and d.term_date
        and today <= d.term_date <= date.fromordinal(today.toordinal() + 7)
    )

    dept_rows = (
        db.execute(
            select(WorkplaceDepartment.name, func.count(RiskAssessment.id))
            .select_from(WorkplaceDepartment)
            .outerjoin(RiskAssessment, RiskAssessment.department_id == WorkplaceDepartment.id)
            .where(WorkplaceDepartment.company_id == effective, WorkplaceDepartment.is_active.is_(True))
            .group_by(WorkplaceDepartment.name)
            .order_by(func.count(RiskAssessment.id).desc())
        ).all()
    )

    company = db.get(Company, effective)
    return {
        "company_id": effective,
        "total_risks": len(risks),
        "open_risks": open_risks,
        "very_high": level_counts.get("Çok Yüksek", 0),
        "high": level_counts.get("Yüksek", 0),
        "open_dofs": open_dofs,
        "overdue_dofs": overdue_dofs,
        "overdue_terms": overdue_terms,
        "due_soon_dofs": due_soon,
        "levels": level_counts,
        "departments": [{"name": n or "—", "count": int(c)} for n, c in dept_rows],
        "suggested_departments": SUGGESTED_DEPARTMENTS,
        "validity": _assessment_context(db, company)["validity"] if company else None,
    }


@router.get("/methods")
def risk_methods_meta(user: User = Depends(get_current_user)):
    """Desteklenen risk değerlendirme yöntemleri (rapor künyesi)."""
    from app.services.risk_methods import method_choices

    return {"methods": method_choices()}


@router.get("/validity")
def risk_assessment_validity(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Risk değerlendirmesi geçerlilik / yenileme durumu (yönetmelik md.12)."""
    effective = effective_company_id(db, user, company_id)
    company = db.get(Company, effective)
    if not company:
        raise HTTPException(404, "Firma bulunamadı.")
    ctx = _assessment_context(db, company)
    return {
        "company_id": effective,
        "company_name": company.name,
        **ctx["validity"],
        "document_no": ctx["document_no"],
        "revision_no": ctx["revision_no"],
        "revision_reason": ctx["revision_reason"],
        "scope_note": ctx["scope_note"],
        "method_code": ctx["method_code"],
        "employee_count": ctx["employee_count"],
        "team": {
            "safety_specialist": ctx["safety_specialist"],
            "workplace_physician": ctx["workplace_physician"],
            "employer_representative": ctx["employer_representative"],
            "employee_representative": ctx["employee_representative"],
            "support_staff": ctx["support_staff"],
        },
        "team_details": ctx["team_details"],
    }


def _canonical_nace_code(value: object) -> str | None:
    """Return the catalog's canonical code without accepting fuzzy aliases."""
    raw = str(value or "").strip()
    if not raw:
        return None
    candidates = [raw]
    normalized = raw.removeprefix("nace_").replace("_", ".")
    if normalized != raw:
        candidates.append(normalized)
    for candidate in candidates:
        try:
            classification = resolve_exact_nace(candidate)
        except ValueError:
            continue
        if classification.nace_code:
            return classification.nace_code
    return None


def _nace_from_sgk_registry(value: object) -> str | None:
    """Read the six-digit NACE code embedded in a workplace registry number.

    This application receives SGK numbers in the form where the first digit
    is the nature code and the following six digits are the NACE digits. For
    example ``224100101...`` becomes ``24.10.01``. The transformation is
    deterministic and is applied only to a company SGK registry value.
    """
    raw = str(value or "").strip()
    if not raw:
        return None

    # Allow a pasted six-digit NACE code as well as a four-digit legacy
    # work-code value. Full SGK numbers use the structured path below.
    compact = re.sub(r"\D", "", raw)
    if re.fullmatch(r"\d{6}", compact):
        return f"{compact[:2]}.{compact[2:4]}.{compact[4:]}"
    if re.fullmatch(r"\d{4}", compact):
        return f"{compact[:2]}.{compact[2:]}"

    # A standard SGK workplace registry is commonly pasted with spaces,
    # dashes or no separators. The first digit is discarded; the next six
    # digits are the application NACE code.
    if len(compact) not in {23, 26, 27}:
        return None
    nace_digits = compact[1:7]
    if not re.fullmatch(r"\d{6}", nace_digits) or nace_digits == "000000":
        return None
    return f"{nace_digits[:2]}.{nace_digits[2:4]}.{nace_digits[4:]}"


def _resolve_company_nace(
    db: Session,
    company: Company,
) -> tuple[str | None, str | None]:
    """Use the company card first; fall back only to one unique exact legacy NACE.

    Older training records may already contain the selected workplace NACE while
    the legacy company form did not persist it. Multiple different codes are
    treated as ambiguous and never guessed.
    """
    direct_raw = str(getattr(company, "nace_code", None) or "").strip() or None
    if direct_raw:
        return _canonical_nace_code(direct_raw) or direct_raw, "company"

    sgk_nace = _nace_from_sgk_registry(getattr(company, "sgk_registry_no", None))
    if sgk_nace:
        return sgk_nace, "sgk_registry_nace"

    candidates: list[str] = []

    def add_candidate(value: object) -> None:
        text = str(value or "").strip()
        if text:
            candidates.append(text)

    try:
        snapshot_rows = db.execute(
            select(
                TrainingNaceSnapshot.nace_code,
                TrainingNaceSnapshot.catalog_key,
                TrainingNaceSnapshot.source_snapshot_json,
            ).where(TrainingNaceSnapshot.company_id == company.id)
        ).all()
        for row in snapshot_rows:
            add_candidate(row[0])
            add_candidate(row[1])
            try:
                source = json.loads(row[2] or "{}")
            except (TypeError, json.JSONDecodeError):
                source = {}
            if isinstance(source, dict):
                add_candidate(source.get("nace_code"))
                add_candidate(source.get("catalog_key"))
                catalog_row = source.get("catalog_row")
                if isinstance(catalog_row, dict):
                    add_candidate(catalog_row.get("nace"))
                    add_candidate(catalog_row.get("code"))
    except OperationalError:
        # Migration öncesi izole kurulumlarda snapshot tablosu bulunmayabilir.
        pass

    try:
        candidates.extend(
            str(value or "").strip()
            for value in db.scalars(
                select(TrainingSession.sector)
                .where(TrainingSession.company_id == company.id)
            ).all()
            if str(value or "").strip()
        )
    except OperationalError:
        pass

    exact_codes = {
        canonical
        for raw in candidates
        if (canonical := _canonical_nace_code(raw))
    }
    if len(exact_codes) == 1:
        return next(iter(exact_codes)), "legacy_training_nace"
    return None, "ambiguous_training_nace" if exact_codes else "company_missing"


def _roadmap_coverage(
    db: Session,
    company_id: int,
    risks: list[RiskAssessment] | None = None,
) -> dict[str, int]:
    """Read-only coverage counters used by the NACE roadmap and reports."""
    if risks is None:
        risk_count = int(
            db.scalar(
                select(func.count()).select_from(RiskAssessment).where(RiskAssessment.company_id == company_id)
            )
            or 0
        )
        dof_rows = list(
            db.scalars(
                select(RiskDof)
                .join(RiskAssessment, RiskAssessment.id == RiskDof.risk_id)
                .where(RiskAssessment.company_id == company_id)
            ).all()
        )
    else:
        risk_count = len(risks)
        dof_rows = [d for risk in risks for d in (getattr(risk, "dofs", None) or [])]
    departments = int(
        db.scalar(
            select(func.count())
            .select_from(WorkplaceDepartment)
            .where(
                WorkplaceDepartment.company_id == company_id,
                WorkplaceDepartment.is_active.is_(True),
            )
        )
        or 0
    )
    return {
        "risk_records": risk_count,
        "departments": departments,
        "open_dofs": sum(1 for row in dof_rows if not getattr(row, "is_completed", False)),
        "completed_dofs": sum(1 for row in dof_rows if getattr(row, "is_completed", False)),
    }


@router.get("/nace-roadmap")
def risk_nace_roadmap(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Selected workplace NACE identity, report checklist and safe roadmap.

    The endpoint is read-only and uses the same active-assignment/tenant scope
    as the rest of the risk module.  An unknown NACE never falls back to a
    neighbouring activity.
    """
    effective = effective_company_id(db, user, company_id)
    company = db.get(Company, effective)
    if not company:
        raise HTTPException(404, "Firma bulunamadı.")
    nace_code, nace_source = _resolve_company_nace(db, company)
    return build_risk_nace_roadmap(
        company,
        coverage=_roadmap_coverage(db, effective),
        nace_code_override=nace_code,
        nace_source=nace_source,
    )


@router.put("/assessment-info")
def update_assessment_info(
    payload: RiskAssessmentInfoUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    """Belge tarihi + ekip + yöntem + belge kontrol alanları."""
    from app.services.risk_methods import METHOD_CATALOG

    ensure_access(db, user, payload.company_id)
    company = db.get(Company, payload.company_id)
    if not company:
        raise HTTPException(404, "Firma bulunamadı.")
    selected_method = _implemented_method(payload.method, fallback=company.risk_method or DEFAULT_METHOD)
    company.risk_assessment_date = payload.assessment_date
    company.risk_team_employee_rep = payload.employee_representative
    company.risk_team_support_staff = payload.support_staff
    if payload.method is not None:
        company.risk_method = selected_method
    if payload.document_no is not None:
        company.risk_document_no = payload.document_no
    if payload.revision_no is not None:
        company.risk_revision_no = payload.revision_no
    if payload.revision_reason is not None:
        company.risk_revision_reason = payload.revision_reason
    if payload.scope_note is not None:
        company.risk_scope_note = payload.scope_note
    add_audit_log(
        db,
        user=user,
        action="UPDATE",
        entity_type="company",
        entity_id=str(company.id),
        description=f"Risk değerlendirme künyesi güncellendi: {company.name}",
        module="risk",
    )
    db.commit()
    ctx = _assessment_context(db, company)
    return {
        "company_id": company.id,
        **ctx["validity"],
        "document_no": ctx["document_no"],
        "revision_no": ctx["revision_no"],
        "revision_reason": ctx["revision_reason"],
        "scope_note": ctx["scope_note"],
        "method_code": ctx["method_code"],
        "team": {
            "safety_specialist": ctx["safety_specialist"],
            "workplace_physician": ctx["workplace_physician"],
            "employer_representative": ctx["employer_representative"],
            "employee_representative": ctx["employee_representative"],
            "support_staff": ctx["support_staff"],
        },
    }


@router.get("/dofs")
def list_company_dofs(
    company_id: int | None = None,
    status: str | None = None,
    overdue_only: bool = Query(False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """PRO /dof/liste — firma geneli DÖF listesi."""
    from app.schemas.risk import RiskDofListItem

    effective = effective_company_id(db, user, company_id)
    today = date.today()
    stmt = (
        select(RiskDof, RiskAssessment)
        .join(RiskAssessment, RiskAssessment.id == RiskDof.risk_id)
        .where(RiskAssessment.company_id == effective)
        .order_by(RiskDof.term_date.asc().nulls_last(), RiskDof.id.desc())
    )
    if status == "open":
        stmt = stmt.where(RiskDof.is_completed.is_(False))
    elif status == "done":
        stmt = stmt.where(RiskDof.is_completed.is_(True))
    rows = db.execute(stmt).all()
    out = []
    for dof, risk in rows:
        is_overdue = (not dof.is_completed) and bool(dof.term_date) and dof.term_date < today
        if overdue_only and not is_overdue:
            continue
        out.append(
            RiskDofListItem(
                id=dof.id,
                dof_code=dof.dof_code,
                risk_id=risk.id,
                risk_code=risk.risk_code,
                description=dof.description,
                responsible_person=dof.responsible_person,
                responsible_department=dof.responsible_department,
                term_date=dof.term_date,
                status=dof.status,
                is_completed=dof.is_completed,
                is_overdue=is_overdue,
                cost_estimate=dof.cost_estimate,
                currency=dof.currency,
            )
        )
    return out


@router.patch("/departments/{department_id}", response_model=DepartmentResponse)
def update_department(
    department_id: int,
    payload: DepartmentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    from app.schemas.risk import DepartmentUpdate

    dep = db.get(WorkplaceDepartment, department_id)
    if not dep:
        raise HTTPException(404, "Bölüm bulunamadı.")
    ensure_access(db, user, dep.company_id)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"]:
        data["name"] = data["name"].strip()
    for k, v in data.items():
        setattr(dep, k, v)
    db.commit()
    db.refresh(dep)
    cnt = db.scalar(
        select(func.count()).select_from(RiskAssessment).where(RiskAssessment.department_id == dep.id)
    ) or 0
    return DepartmentResponse(
        id=dep.id,
        company_id=dep.company_id,
        name=dep.name,
        description=dep.description,
        is_active=dep.is_active,
        created_at=dep.created_at,
        risk_count=int(cnt),
    )


@router.delete("/departments/{department_id}")
def delete_department(
    department_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    dep = db.get(WorkplaceDepartment, department_id)
    if not dep:
        raise HTTPException(404, "Bölüm bulunamadı.")
    ensure_access(db, user, dep.company_id)
    cnt = db.scalar(
        select(func.count()).select_from(RiskAssessment).where(RiskAssessment.department_id == dep.id)
    ) or 0
    if cnt:
        raise HTTPException(422, f"Bu bölüme ait {cnt} risk kaydı var. Önce riskleri taşıyın veya silin.")
    dep.is_active = False
    db.commit()
    return {"ok": True, "id": department_id}


@router.delete("/{risk_id}/dofs/{dof_id}")
def delete_dof(
    risk_id: int,
    dof_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = _load_risk(db, risk_id)
    ensure_access(db, user, row.company_id)
    dof = db.get(RiskDof, dof_id)
    if not dof or dof.risk_id != risk_id:
        raise HTTPException(404, "DÖF bulunamadı.")
    db.delete(dof)
    db.commit()
    return {"ok": True, "id": dof_id}


@router.delete("/{risk_id}")
def delete_risk(
    risk_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = _load_risk(db, risk_id)
    ensure_access(db, user, row.company_id)
    code = row.risk_code
    cid = row.company_id
    db.delete(row)
    add_audit_log(
        db,
        user=user,
        action="DELETE",
        entity_type="risk_assessment",
        entity_id=str(risk_id),
        description=f"Risk silindi: {code}",
        module="risk",
    )
    db.commit()
    return {"ok": True, "id": risk_id, "company_id": cid}


@router.get("/hazards", response_model=list[HazardResponse])
def list_hazards(
    category_id: int | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _ensure_library(db)
    stmt = select(Hazard).where(Hazard.is_active.is_(True)).order_by(Hazard.code)
    if category_id:
        stmt = stmt.where(Hazard.category_id == category_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Hazard.name.ilike(like), Hazard.code.ilike(like), Hazard.description.ilike(like)))
    rows = list(db.scalars(stmt.limit(500)).all())
    return [
        HazardResponse(
            id=h.id,
            category_id=h.category_id,
            code=h.code,
            name=h.name,
            description=h.description,
            risk_source=h.risk_source,
            default_probability=h.default_probability,
            default_severity=h.default_severity,
            regulations=_parse_regs(h.regulations),
            is_active=h.is_active,
        )
        for h in rows
    ]


@router.get("/hazards/{hazard_id}")
def hazard_detail(hazard_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    h = db.get(Hazard, hazard_id)
    if not h:
        raise HTTPException(404, "Tehlike bulunamadı.")
    cat = db.get(HazardCategory, h.category_id)
    return {
        "hazard": HazardResponse(
            id=h.id,
            category_id=h.category_id,
            code=h.code,
            name=h.name,
            description=h.description,
            risk_source=h.risk_source,
            default_probability=h.default_probability,
            default_severity=h.default_severity,
            regulations=_parse_regs(h.regulations),
            is_active=h.is_active,
        ),
        "category": cat.name if cat else None,
        "suggestions": get_suggestions(cat.name if cat else ""),
    }


@router.get("", response_model=list[RiskResponse])
def list_risks(
    company_id: int | None = None,
    level: str | None = None,
    status: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(RiskAssessment)
        .options(
            selectinload(RiskAssessment.dofs),
            selectinload(RiskAssessment.media_files),
        )
        .order_by(RiskAssessment.created_at.desc())
    )
    company_ids = company_ids_for_query(db, user, company_id)
    if company_ids == []:
        return []
    if company_ids is not None:
        stmt = stmt.where(RiskAssessment.company_id.in_(company_ids))
    if level:
        stmt = stmt.where(_risk_level_filter(level))
    if status:
        stmt = stmt.where(RiskAssessment.status == status)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                RiskAssessment.activity.ilike(like),
                RiskAssessment.risk_definition.ilike(like),
                RiskAssessment.risk_code.ilike(like),
            )
        )
    rows = list(db.scalars(stmt.limit(500)).all())
    hazard_ids = {r.hazard_id for r in rows}
    hazards = {h.id: h for h in db.scalars(select(Hazard).where(Hazard.id.in_(hazard_ids))).all()} if hazard_ids else {}
    cat_ids = {h.category_id for h in hazards.values()}
    cats = {c.id: c for c in db.scalars(select(HazardCategory).where(HazardCategory.id.in_(cat_ids))).all()} if cat_ids else {}
    out = []
    for r in rows:
        h = hazards.get(r.hazard_id)
        c = cats.get(h.category_id) if h else None
        out.append(_to_response(r, h, c))
    return out


def _load_company_risks(
    db: Session,
    user: User,
    company_id: int | None,
    level: str | None = None,
    status: str | None = None,
    method_code: str | None = None,
) -> tuple[Company, list[RiskAssessment], dict[int, Hazard]]:
    effective = effective_company_id(db, user, company_id)
    company = db.get(Company, effective)
    if not company:
        raise HTTPException(404, "Firma bulunamadı.")
    selected_method = _implemented_method(method_code) if method_code else None
    stmt = (
        select(RiskAssessment)
        .options(
            selectinload(RiskAssessment.dofs),
            selectinload(RiskAssessment.media_files),
        )
        .where(RiskAssessment.company_id == effective)
        .order_by(RiskAssessment.risk_score.desc(), RiskAssessment.id.asc())
    )
    if level:
        stmt = stmt.where(_risk_level_filter(level))
    if status:
        stmt = stmt.where(RiskAssessment.status == status)
    if selected_method:
        stmt = stmt.where(RiskAssessment.method_code == selected_method)
    risks = list(db.scalars(stmt).unique().all())
    hids = {r.hazard_id for r in risks}
    hazard_map = {}
    if hids:
        hazard_map = {h.id: h for h in db.scalars(select(Hazard).where(Hazard.id.in_(hids))).all()}
    return company, risks, hazard_map


def _report_validity(ctx: dict, method_code: str | None) -> dict:
    """Raporun seçilen yöntemini belge künyesini değiştirmeden gösterir."""
    if not method_code:
        return ctx["validity"]
    method = resolve_method(method_code)
    return {
        **(ctx["validity"] or {}),
        "method_code": method_code,
        "method": method["short"],
    }


def _report_empty_message(method_code: str | None) -> str:
    if method_code:
        return f"Seçilen yönteme ait raporlanacak risk kaydı yok: {resolve_method(method_code)['label']}."
    return "Bu filtreyle raporlanacak risk kaydı yok."


@router.get("/report.pdf")
def risk_report_pdf(
    company_id: int | None = None,
    level: str | None = None,
    status: str | None = None,
    method_code: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Firma risk değerlendirme PDF raporu."""
    selected_method = _implemented_method(method_code) if method_code else None
    company, risks, hazard_map = _load_company_risks(
        db, user, company_id, level, status, method_code=selected_method
    )
    if not risks:
        raise HTTPException(422, _report_empty_message(selected_method))
    branch = db.scalar(select(Branch).where(Branch.company_id == company.id).order_by(Branch.id.asc()))
    ctx = _assessment_context(db, company)
    sgk = None
    if branch and branch.sgk_registry_no:
        sgk = branch.sgk_registry_no
    elif company.sgk_registry_no:
        sgk = company.sgk_registry_no
    nace_code, nace_source = _resolve_company_nace(db, company)
    nace_roadmap = build_risk_nace_roadmap(
        company,
        coverage=_roadmap_coverage(db, company.id, risks),
        nace_code_override=nace_code,
        nace_source=nace_source,
    )
    report_validity = _report_validity(ctx, selected_method)
    pdf = build_risk_pdf(
        company=company,
        risks=risks,
        hazard_map=hazard_map,
        prepared_by=ctx["safety_specialist"] or user.full_name,
        sgk_no=sgk,
        workplace_physician=ctx["workplace_physician"],
        employer_representative=ctx["employer_representative"],
        employee_representative=ctx["employee_representative"],
        support_staff=ctx["support_staff"],
        validity=report_validity,
        team_details=ctx["team_details"],
        employee_count=ctx["employee_count"],
        document_no=ctx["document_no"],
        revision_no=ctx["revision_no"],
        revision_reason=ctx["revision_reason"],
        scope_note=ctx["scope_note"],
        tax_number=company.tax_number,
        nace_code=nace_code,
        nace_roadmap=nace_roadmap,
    )
    return StreamingResponse(
        BytesIO(pdf),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="risk-raporu-'
                f'{selected_method + "-" if selected_method else ""}{company.id}.pdf"'
            )
        },
    )


@router.get("/report.xlsx")
def risk_report_excel(
    company_id: int | None = None,
    level: str | None = None,
    status: str | None = None,
    method_code: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Firma risk değerlendirme Excel raporu (risk + DÖF + istatistik)."""
    selected_method = _implemented_method(method_code) if method_code else None
    company, risks, hazard_map = _load_company_risks(
        db, user, company_id, level, status, method_code=selected_method
    )
    if not risks:
        raise HTTPException(422, _report_empty_message(selected_method))
    ctx = _assessment_context(db, company)
    nace_code, nace_source = _resolve_company_nace(db, company)
    nace_roadmap = build_risk_nace_roadmap(
        company,
        coverage=_roadmap_coverage(db, company.id, risks),
        nace_code_override=nace_code,
        nace_source=nace_source,
    )
    report_validity = _report_validity(ctx, selected_method)
    xlsx = build_risk_excel(
        company=company,
        risks=risks,
        hazard_map=hazard_map,
        validity=report_validity,
        prepared_by=ctx["safety_specialist"] or user.full_name,
        workplace_physician=ctx["workplace_physician"],
        employer_representative=ctx["employer_representative"],
        employee_representative=ctx["employee_representative"],
        support_staff=ctx["support_staff"],
        nace_roadmap=nace_roadmap,
    )
    return StreamingResponse(
        BytesIO(xlsx),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": (
                f'attachment; filename="risk-raporu-'
                f'{selected_method + "-" if selected_method else ""}{company.id}.xlsx"'
            )
        },
    )


@router.get("/report/dof.xlsx")
def risk_dof_excel(
    company_id: int | None = None,
    method_code: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """PRO /rapor/dof-excel — sadece DÖF listesi Excel."""
    selected_method = _implemented_method(method_code) if method_code else None
    company, risks, hazard_map = _load_company_risks(
        db, user, company_id, None, None, method_code=selected_method
    )
    xlsx = build_dof_excel(
        company=company,
        risks=risks,
        hazard_map=hazard_map,
        method_code=selected_method,
    )
    return StreamingResponse(
        BytesIO(xlsx),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": (
                f'attachment; filename="dof-listesi-'
                f'{selected_method + "-" if selected_method else ""}{company.id}.xlsx"'
            )
        },
    )


def _legacy_status(status: RecordStatus) -> str:
    return {
        RecordStatus.OPEN: "Açık",
        RecordStatus.IN_PROGRESS: "Açık",
        RecordStatus.COMPLETED: "Tamamlandı",
        RecordStatus.CANCELLED: "İptal",
    }.get(status, "Açık")


@router.post("/migrate-isg-records")
def migrate_isg_records(
    company_id: int | None = None,
    dry_run: bool = Query(True, description="True ise sadece sayım; yazmaz"),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    """Eski IsgRecord(module=risk) satırlarını RiskAssessment'a aktarır."""
    effective = effective_company_id(db, user, company_id)
    _ensure_library(db)
    hazard = db.scalar(select(Hazard).where(Hazard.is_active.is_(True)).order_by(Hazard.id.asc()))
    if not hazard:
        raise HTTPException(422, "Tehlike kütüphanesi boş. Önce seed-library çalıştırın.")

    legacy = list(
        db.scalars(
            select(IsgRecord).where(
                IsgRecord.company_id == effective,
                IsgRecord.module == IsgModule.RISK,
            )
        ).all()
    )
    created = 0
    skipped = 0
    preview = []
    for rec in legacy:
        tag = f"{LEGACY_TAG}{rec.id}] "
        exists = db.scalar(
            select(RiskAssessment.id).where(
                RiskAssessment.company_id == effective,
                RiskAssessment.risk_definition.like(f"{tag}%"),
            )
        )
        if exists:
            skipped += 1
            continue

        prob = max(1, min(5, int(rec.probability or 3)))
        sev = max(1, min(5, int(rec.impact or 3)))
        calc = evaluate(prob, sev)
        definition = f"{tag}{rec.description or rec.title}".strip()[:2000]
        item = {
            "isg_record_id": rec.id,
            "title": rec.title,
            "risk_score": calc["risk_score"],
            "risk_level": calc["risk_level"],
        }
        preview.append(item)
        if dry_run:
            created += 1
            continue
        code = _next_code(db, "RSK", RiskAssessment, RiskAssessment.risk_code)
        while db.scalar(select(RiskAssessment).where(RiskAssessment.risk_code == code)):
            code = f"RSK-{int(code.split('-')[1]) + 1:04d}"
        row = RiskAssessment(
            risk_code=code,
            company_id=rec.company_id,
            branch_id=rec.branch_id,
            hazard_id=hazard.id,
            method_code="5x5_l",
            activity=(rec.title or "Eski risk kaydı")[:500],
            risk_definition=definition,
            affected_people=None,
            existing_measures=None,
            additional_measures=f"Kaynak: IsgRecord#{rec.id}"[:2000],
            probability=calc["probability"],
            frequency=None,
            severity=calc["severity"],
            risk_score=calc["risk_score"],
            risk_level=calc["risk_level"],
            term_days=calc["term_days"],
            term_date=date.fromisoformat(calc["term_date"]),
            term_suggested=calc["term_suggested"],
            term_overridden=False,
            status=_legacy_status(rec.status),
            created_by_id=user.id,
        )
        db.add(row)
        rec.status = RecordStatus.CANCELLED
        created += 1
    if not dry_run:
        db.commit()
    return {
        "dry_run": dry_run,
        "company_id": effective,
        "legacy_total": len(legacy),
        "migrated_or_would_migrate": created,
        "skipped_already": skipped,
        "default_hazard_id": hazard.id,
        "default_hazard_code": hazard.code,
        "preview": preview[:50],
    }


@router.get("/{risk_id}", response_model=RiskResponse)
def get_risk(risk_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = _load_risk(db, risk_id)
    ensure_access(db, user, row.company_id)
    h = db.get(Hazard, row.hazard_id)
    c = db.get(HazardCategory, h.category_id) if h else None
    return _to_response(row, h, c)


@router.post("", response_model=RiskResponse)
def create_risk(
    payload: RiskCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    ensure_access(db, user, payload.company_id)
    company = db.get(Company, payload.company_id)
    if not company:
        raise HTTPException(404, "Firma bulunamadı.")
    # Mobil/offline tekrar denemesinde ağ yanıtı kaybolsa bile ikinci POST
    # aynı saha kaydını üretmez.
    if payload.client_reference:
        existing = db.scalar(
            select(RiskAssessment).where(
                RiskAssessment.company_id == payload.company_id,
                RiskAssessment.client_reference == payload.client_reference,
            )
        )
        if existing:
            row = _load_risk(db, existing.id)
            hazard = db.get(Hazard, row.hazard_id)
            category = db.get(HazardCategory, hazard.category_id) if hazard else None
            return _to_response(row, hazard, category)
    method_code = _implemented_method(payload.method_code, fallback=company.risk_method or DEFAULT_METHOD)
    if method_code == "hazop" and payload.hazop_data is None:
        raise HTTPException(422, "HAZOP kaydı için çalışma satırını doldurmalısınız.")
    if method_code != "hazop" and payload.hazop_data is not None:
        raise HTTPException(422, "HAZOP alanları yalnızca HAZOP yöntemiyle kullanılabilir.")
    hazop_data = normalize_hazop_data(payload.hazop_data.model_dump()) if payload.hazop_data else None
    if payload.branch_id:
        b = db.get(Branch, payload.branch_id)
        if not b or b.company_id != payload.company_id:
            raise HTTPException(422, "Şube firma ile uyumlu değil.")
    hazard = db.get(Hazard, payload.hazard_id)
    if not hazard or not hazard.is_active:
        raise HTTPException(404, "Tehlike bulunamadı. Tehlike kütüphanesinden seçim yapın.")
    dep_id, dep_name = _resolve_department(
        db,
        company_id=payload.company_id,
        department_id=payload.department_id,
        department_name=payload.department_name,
    )
    calc = _calculate_risk(
        method_code=method_code,
        probability=payload.probability,
        frequency=payload.frequency,
        severity=payload.severity,
        hazop_data=hazop_data,
        term_override_days=payload.term_override_days,
    )
    residual = _calculate_residual(
        method_code=method_code,
        probability=payload.residual_probability,
        frequency=payload.residual_frequency,
        severity=payload.residual_severity,
    )
    code = _next_code(db, "RSK", RiskAssessment, RiskAssessment.risk_code)
    # uniqueness retry
    while db.scalar(select(RiskAssessment).where(RiskAssessment.risk_code == code)):
        code = f"RSK-{int(code.split('-')[1]) + 1:04d}"
    row = RiskAssessment(
        risk_code=code,
        company_id=payload.company_id,
        branch_id=payload.branch_id,
        record_origin=payload.record_origin,
        client_reference=payload.client_reference,
        observed_at=_as_naive_utc(payload.observed_at),
        observation_location=payload.observation_location,
        gps_lat=payload.gps_lat,
        gps_lng=payload.gps_lng,
        gps_accuracy_m=payload.gps_accuracy_m,
        department_id=dep_id,
        hazard_id=payload.hazard_id,
        method_code=method_code,
        hazop_data_json=json.dumps(hazop_data, ensure_ascii=False) if hazop_data else None,
        department_name=dep_name,
        activity=payload.activity,
        risk_definition=payload.risk_definition,
        affected_people=payload.affected_people,
        affected_group=payload.affected_group,
        existing_measures=payload.existing_measures,
        additional_measures=payload.additional_measures,
        probability=calc["probability"],
        frequency=calc.get("frequency"),
        severity=calc["severity"],
        risk_score=calc["risk_score"],
        risk_level=calc["risk_level"],
        term_days=calc["term_days"],
        term_date=date.fromisoformat(calc["term_date"]),
        term_suggested=calc["term_suggested"],
        term_overridden=calc["term_overridden"],
        residual_probability=residual.get("probability") if residual else None,
        residual_frequency=residual.get("frequency") if residual else None,
        residual_severity=residual.get("severity") if residual else None,
        residual_score=residual.get("risk_score") if residual else None,
        residual_level=residual.get("risk_level") if residual else None,
        status=payload.status or "Açık",
        created_by_id=user.id,
    )
    db.add(row)
    db.commit()
    add_audit_log(
        db,
        user=user,
        action="CREATE",
        entity_type="risk_assessment",
        entity_id=str(row.id),
        description=f"Risk oluşturuldu: {row.risk_code}",
        module="risk",
    )
    db.commit()
    row = _load_risk(db, row.id)
    cat = db.get(HazardCategory, hazard.category_id)
    return _to_response(row, hazard, cat)


@router.patch("/{risk_id}", response_model=RiskResponse)
def update_risk(
    risk_id: int,
    payload: RiskUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = _load_risk(db, risk_id)
    ensure_access(db, user, row.company_id)
    before = _snapshot_fields(row)
    data = payload.model_dump(exclude_unset=True)
    reason = data.pop("change_reason", None)
    term_override = data.pop("term_override_days", None)
    has_hazop_data = "hazop_data" in data
    hazop_data = data.pop("hazop_data", None)
    requested_method = data.get("method_code", getattr(row, "method_code", None) or DEFAULT_METHOD)
    method_code = _implemented_method(requested_method)
    if "method_code" in data and requested_method != (getattr(row, "method_code", None) or DEFAULT_METHOD):
        raise HTTPException(422, "Kayıt oluşturulduktan sonra yöntemi değiştirilemez; seçilen yöntemle yeni risk kaydı oluşturun.")
    if method_code == "hazop" and has_hazop_data:
        if hazop_data is None:
            raise HTTPException(422, "HAZOP çalışma satırı silinemez; gerekli alanları doldurun.")
        hazop_data = normalize_hazop_data(hazop_data)
        row.hazop_data_json = json.dumps(hazop_data, ensure_ascii=False)
    elif method_code != "hazop" and has_hazop_data and hazop_data is not None:
        raise HTTPException(422, "HAZOP alanları yalnızca HAZOP yöntemiyle kullanılabilir.")
    has_dep_id = "department_id" in data
    has_dep_name = "department_name" in data
    dep_id = data.pop("department_id", None) if has_dep_id else None
    dep_name = data.pop("department_name", None) if has_dep_name else None
    if has_dep_id or has_dep_name:
        resolved_id, resolved_name = _resolve_department(
            db,
            company_id=row.company_id,
            department_id=dep_id,
            department_name=dep_name,
        )
        if resolved_id is not None:
            row.department_id = resolved_id
        if resolved_name is not None:
            row.department_name = resolved_name

    for key, val in data.items():
        setattr(row, key, val)

    if "hazard_id" in data:
        hazard = db.get(Hazard, row.hazard_id)
        if not hazard or not hazard.is_active:
            raise HTTPException(422, "Geçersiz tehlike seçimi.")

    if "probability" in data or "frequency" in data or "severity" in data or term_override is not None or has_hazop_data:
        stored_hazop_data = None
        if method_code == "hazop" and not hazop_data and getattr(row, "hazop_data_json", None):
            try:
                stored_hazop_data = normalize_hazop_data(json.loads(row.hazop_data_json))
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise HTTPException(422, "Mevcut HAZOP çalışma satırı okunamadı; kayıt düzenlenmelidir.") from exc
        calc = _calculate_risk(
            method_code=method_code,
            probability=row.probability,
            frequency=getattr(row, "frequency", None),
            severity=row.severity,
            hazop_data=hazop_data or stored_hazop_data,
            term_override_days=term_override
            if term_override is not None
            else (row.term_days if row.term_overridden else None),
        )
        row.probability = calc["probability"]
        row.severity = calc["severity"]
        row.risk_score = calc["risk_score"]
        row.risk_level = calc["risk_level"]
        row.frequency = calc.get("frequency")
        row.term_suggested = calc["term_suggested"]
        row.term_days = calc["term_days"]
        row.term_date = date.fromisoformat(calc["term_date"])
        row.term_overridden = calc["term_overridden"]

    residual_keys = {"residual_probability", "residual_frequency", "residual_severity"}
    if residual_keys.intersection(data):
        residual = _calculate_residual(
            method_code=method_code,
            probability=getattr(row, "residual_probability", None),
            frequency=getattr(row, "residual_frequency", None),
            severity=getattr(row, "residual_severity", None),
        )
        row.residual_score = residual.get("risk_score") if residual else None
        row.residual_level = residual.get("risk_level") if residual else None

    old_rev = int(row.revision_no or 0)
    rev_no = _record_field_revisions(db, row=row, before=before, user=user, reason=reason)
    if rev_no > old_rev:
        add_audit_log(
            db,
            user=user,
            action="UPDATE",
            entity_type="risk_assessment",
            entity_id=str(row.id),
            description=f"Risk güncellendi: {row.risk_code} (rev {rev_no})",
            module="risk",
        )
    db.commit()
    row = _load_risk(db, row.id)
    h = db.get(Hazard, row.hazard_id)
    c = db.get(HazardCategory, h.category_id) if h else None
    return _to_response(row, h, c)


@router.post("/{risk_id}/dofs", response_model=RiskDofResponse)
def add_dof(
    risk_id: int,
    payload: RiskDofCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = _load_risk(db, risk_id)
    ensure_access(db, user, row.company_id)
    if payload.client_reference:
        existing = db.scalar(
            select(RiskDof).where(
                RiskDof.risk_id == row.id,
                RiskDof.client_reference == payload.client_reference,
            )
        )
        if existing:
            return existing
    code = _next_code(db, "DÖF", RiskDof, RiskDof.dof_code)
    while db.scalar(select(RiskDof).where(RiskDof.dof_code == code)):
        n = int("".join(ch for ch in code if ch.isdigit()) or "0") + 1
        code = f"DÖF-{n:04d}"
    dof = RiskDof(
        dof_code=code,
        risk_id=row.id,
        client_reference=payload.client_reference,
        description=payload.description,
        responsible_person=payload.responsible_person,
        responsible_department=payload.responsible_department,
        term_date=payload.term_date or row.term_date,
        cost_estimate=payload.cost_estimate,
        created_by_id=user.id,
    )
    db.add(dof)
    db.commit()
    db.refresh(dof)
    return dof


@router.patch("/{risk_id}/dofs/{dof_id}", response_model=RiskDofResponse)
def update_dof(
    risk_id: int,
    dof_id: int,
    payload: RiskDofUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = _load_risk(db, risk_id)
    ensure_access(db, user, row.company_id)
    dof = db.get(RiskDof, dof_id)
    if not dof or dof.risk_id != risk_id:
        raise HTTPException(404, "DÖF bulunamadı.")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(dof, k, v)
    db.commit()
    db.refresh(dof)
    return dof


@router.post("/{risk_id}/dofs/{dof_id}/complete", response_model=RiskDofResponse)
def complete_dof(
    risk_id: int,
    dof_id: int,
    payload: RiskDofComplete = RiskDofComplete(),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = _load_risk(db, risk_id)
    ensure_access(db, user, row.company_id)
    dof = db.get(RiskDof, dof_id)
    if not dof or dof.risk_id != risk_id:
        raise HTTPException(404, "DÖF bulunamadı.")
    dof.is_completed = True
    dof.status = "Tamamlandı"
    dof.completion_date = date.today()
    if payload.completion_note:
        dof.completion_note = payload.completion_note
    db.commit()
    db.refresh(dof)
    return dof


@router.post("/{risk_id}/media", response_model=RiskMediaResponse)
async def upload_risk_media(
    risk_id: int,
    file: UploadFile = File(...),
    tags: str | None = Form(default=None),
    description: str | None = Form(default=None),
    dof_id: int | None = Form(default=None),
    client_reference: str | None = Form(default=None),
    captured_at: str | None = Form(default=None),
    gps_lat: float | None = Form(default=None),
    gps_lng: float | None = Form(default=None),
    gps_accuracy_m: float | None = Form(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = _load_risk(db, risk_id)
    ensure_access(db, user, row.company_id)
    name = file.filename or "photo.jpg"
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_MEDIA:
        raise HTTPException(422, "Desteklenen: jpg/png/webp/gif/pdf/mp4/avi/mov/doc/docx/xls/xlsx.")
    if dof_id is not None:
        dof = db.get(RiskDof, dof_id)
        if not dof or dof.risk_id != risk_id:
            raise HTTPException(422, "DÖF bu riske ait değil.")
    if client_reference:
        existing = db.scalar(
            select(RiskMedia).where(
                RiskMedia.risk_id == row.id,
                RiskMedia.client_reference == client_reference,
            )
        )
        if existing:
            return _media_response(existing)
    if gps_lat is not None and not -90 <= gps_lat <= 90:
        raise HTTPException(422, "Fotoğraf enlemi geçersiz.")
    if gps_lng is not None and not -180 <= gps_lng <= 180:
        raise HTTPException(422, "Fotoğraf boylamı geçersiz.")
    if gps_accuracy_m is not None and not 0 <= gps_accuracy_m <= 100000:
        raise HTTPException(422, "Fotoğraf GPS doğruluğu geçersiz.")
    captured_at_value = _parse_form_datetime(captured_at)
    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"Dosya {settings.max_upload_mb} MB sınırını aşıyor.")
    rel = f"{row.company_id}/risk/{row.id}_{uuid.uuid4().hex[:10]}{ext}"
    if settings.upload_gateway_enabled:
        persist_relative(data, relative_path=rel, original_name=name)
    else:
        assert_safe_upload(data, ext, name)
        target = _upload_root() / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    ftype = _media_file_type(ext)
    media = RiskMedia(
        risk_id=row.id,
        dof_id=dof_id,
        storage_path=rel.replace("\\", "/"),
        original_name=name,
        content_type=file.content_type or "application/octet-stream",
        file_type=ftype,
        file_size=len(data),
        description=(description or "").strip() or None,
        client_reference=(client_reference or "").strip() or None,
        captured_at=captured_at_value,
        gps_lat=gps_lat,
        gps_lng=gps_lng,
        gps_accuracy_m=gps_accuracy_m,
        tags_json=serialize_selected(parse_form_tags(tags)) if ftype == "photo" else None,
        created_by_id=user.id,
    )
    db.add(media)
    add_audit_log(
        db,
        user=user,
        action="CREATE",
        entity_type="risk_media",
        entity_id=str(row.id),
        description=f"Medya yüklendi: {name} ({ftype})",
        module="risk",
    )
    db.commit()
    db.refresh(media)
    return _media_response(media)


@router.put("/{risk_id}/media/{media_id}/tags", response_model=RiskMediaResponse)
def put_risk_media_tags(
    risk_id: int,
    media_id: int,
    payload: RiskMediaTagsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    """0.9.121 — Mevcut risk medyasına tehlike etiketi checklist güncelle."""
    row = _load_risk(db, risk_id)
    ensure_access(db, user, row.company_id)
    media = next((m for m in (row.media_files or []) if m.id == media_id), None)
    if not media:
        raise HTTPException(404, "Medya bulunamadı.")
    media.tags_json = serialize_selected(payload.selected)
    db.commit()
    db.refresh(media)
    return _media_response(media)


@router.get("/{risk_id}/media/{media_id}")
def get_risk_media(
    risk_id: int,
    media_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = _load_risk(db, risk_id)
    ensure_access(db, user, row.company_id)
    media = next((m for m in (row.media_files or []) if m.id == media_id), None)
    if not media:
        raise HTTPException(404, "Medya bulunamadı.")
    from app.services.stored_files import response_for_storage_key

    return response_for_storage_key(
        media.storage_path,
        filename=media.original_name,
        media_type=media.content_type or "application/octet-stream",
    )


@router.delete("/{risk_id}/media/{media_id}")
def delete_risk_media(
    risk_id: int,
    media_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = _load_risk(db, risk_id)
    ensure_access(db, user, row.company_id)
    media = next((m for m in (row.media_files or []) if m.id == media_id), None)
    if not media:
        raise HTTPException(404, "Medya bulunamadı.")
    path = (_upload_root() / media.storage_path).resolve()
    if _upload_root() in path.parents and path.exists():
        try:
            from app.services.archive_store import archive_file_before_delete

            archive_file_before_delete(
                db,
                source=path,
                user=user,
                company_id=row.company_id,
                entity_type="risk_media",
                entity_id=str(media_id),
                original_name=media.original_name,
                notes="Risk medyası silinmeden önce arşivlendi",
            )
        except Exception:
            logger.warning(
                "risk media: archive-before-delete failed media_id=%s",
                media_id,
                exc_info=True,
            )
    delete_relative(media.storage_path)
    db.delete(media)
    db.commit()
    return {"ok": True, "id": media_id}
