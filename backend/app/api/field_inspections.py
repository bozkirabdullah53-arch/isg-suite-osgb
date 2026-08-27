"""GPS'li görsel saha denetimi API'si.

Mevcut ``/risks`` hızlı saha akışıyla aynı tabloları kullanmaz. Bu router yeni
fotoğraf kanıtı, uzman incelemesi ve rapor sürecini ayrı bir bounded context
olarak tutar; her endpoint tenant kapsamını tekrar doğrular.
"""
from __future__ import annotations

import json
import logging
import math
import mimetypes
import re
import uuid
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.company_access import companies_query_for_user, ensure_company_access
from app.api.deps import get_current_user, require_roles
from app.core.config import settings
from app.core.database import get_db
from app.models.entities import AuditLog, Company, Employee, User, UserRole
from app.models.field_inspection import (
    FieldHazard,
    FieldHazardCategory,
    FieldInspection,
    FieldInspectionAction,
    FieldInspectionAnnotation,
    FieldInspectionArea,
    FieldInspectionEquipment,
    FieldInspectionFinding,
    FieldInspectionLegalReference,
    FieldInspectionPhoto,
    FieldInspectionSite,
)
from app.schemas.field_inspection import (
    ActionCreate,
    ActionUpdate,
    AnnotationCreate,
    AnnotationUpdate,
    ApprovalPayload,
    AreaCreate,
    EquipmentCreate,
    FieldHazardCreate,
    FieldHazardUpdate,
    FieldInspectionCreate,
    FieldInspectionUpdate,
    FindingReview,
    GpsUpdate,
    LegalReferenceInput,
    LegalReferenceUpdate,
    ManualFindingCreate,
    SiteCreate,
)
from app.services.field_inspection_catalog import (
    FIELD_AREA_TYPES,
    FIELD_EQUIPMENT_TYPES,
    FIELD_HAZARD_CATEGORIES,
    FIELD_SITE_TYPES,
    legal_entry,
    normalize_name,
    seed_field_catalog,
)
from app.services.field_inspection_media import (
    prepare_photo_variants,
    render_marked_photo,
    store_photo_variants,
)
from app.services.field_inspection_reports import build_field_inspection_excel, build_field_inspection_pdf
from app.services.field_inspection_ai import field_ai_is_configured, run_visual_field_analysis_job
from app.services.job_queue import enqueue
from app.services.object_store import get_object_store
from app.services.stored_files import response_for_storage_key
from app.services.upload_security import assert_safe_upload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/field-inspections", tags=["Görsel Saha Denetimi"])
EDIT_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST)
READ_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN, UserRole.SAFETY_SPECIALIST)
_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_PHOTO_VARIANTS = {"original", "analysis", "marked", "preview"}
_OFFICIAL_LEGAL_HOSTS = {"mevzuat.gov.tr", "resmigazete.gov.tr"}
_VALID_GPS_STATUSES = {"captured", "low_accuracy", "denied", "unavailable", "not_available", "manual"}
_ACTIVE_FINDING_STATUSES = {"ai_draft", "under_review"}
_REPORT_FINDING_STATUSES = {"accepted", "corrected"}
_VALID_INSPECTION_STATUSES = {"draft", "in_review", "approved", "archived"}


def _naive_datetime(value: datetime | None) -> datetime:
    value = value or datetime.utcnow()
    return value.replace(tzinfo=None) if value.tzinfo else value


def _safe_original_name(value: str | None) -> str:
    raw = re.sub(r"[\x00-\x1f\x7f]", "", str(value or "foto.jpg").replace("\\", "/"))
    return Path(raw).name[:255] or "foto.jpg"


def _is_official_legal_url(value: str | None) -> bool:
    parsed = urlparse(str(value or "").strip())
    host = (parsed.hostname or "").lower().rstrip(".")
    return parsed.scheme in {"http", "https"} and any(
        host == allowed or host.endswith(f".{allowed}")
        for allowed in _OFFICIAL_LEGAL_HOSTS
    )


def _audit(db: Session, user: User, company_id: int, *, action: str, entity_type: str, entity_id: int | str, description: str) -> None:
    db.add(AuditLog(
        user_id=user.id,
        company_id=company_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        description=description[:1200],
        module="field_inspection",
    ))


def _company(db: Session, user: User, company_id: int) -> Company:
    ensure_company_access(db, user, company_id)
    row = db.get(Company, company_id)
    if not row:
        raise HTTPException(404, "İşyeri bulunamadı.")
    return row


def _load_inspection(db: Session, user: User, inspection_id: int) -> FieldInspection:
    row = db.scalar(
        select(FieldInspection)
        .options(
            selectinload(FieldInspection.photos).selectinload(FieldInspectionPhoto.annotations),
            selectinload(FieldInspection.findings).selectinload(FieldInspectionFinding.legal_references),
            selectinload(FieldInspection.findings).selectinload(FieldInspectionFinding.actions),
            selectinload(FieldInspection.actions),
        )
        .where(FieldInspection.id == inspection_id, FieldInspection.deleted_at.is_(None))
    )
    if not row:
        raise HTTPException(404, "Görsel saha denetimi bulunamadı.")
    ensure_company_access(db, user, row.company_id)
    return row


def _require_edit(user: User) -> User:
    if user.role not in EDIT_ROLES:
        raise HTTPException(403, "Bu işlem yalnızca iş güvenliği uzmanı veya global yöneticiye açıktır.")
    return user


def _validate_site(db: Session, company_id: int, site_id: int) -> FieldInspectionSite:
    row = db.scalar(select(FieldInspectionSite).where(FieldInspectionSite.id == site_id, FieldInspectionSite.company_id == company_id, FieldInspectionSite.is_active.is_(True)))
    if not row:
        raise HTTPException(422, "Tesis/saha seçimi bu işyerine ait değil veya pasif.")
    return row


def _validate_area(db: Session, company_id: int, site_id: int, area_id: int) -> FieldInspectionArea:
    row = db.scalar(select(FieldInspectionArea).where(FieldInspectionArea.id == area_id, FieldInspectionArea.company_id == company_id, FieldInspectionArea.site_id == site_id, FieldInspectionArea.is_active.is_(True)))
    if not row:
        raise HTTPException(422, "Bölüm/alan seçimi tesis/saha ile eşleşmiyor.")
    return row


def _validate_equipment(db: Session, company_id: int, site_id: int, area_id: int, equipment_id: int | None) -> FieldInspectionEquipment | None:
    if equipment_id is None:
        return None
    row = db.scalar(select(FieldInspectionEquipment).where(FieldInspectionEquipment.id == equipment_id, FieldInspectionEquipment.company_id == company_id, FieldInspectionEquipment.site_id == site_id, FieldInspectionEquipment.area_id == area_id, FieldInspectionEquipment.is_active.is_(True)))
    if not row:
        raise HTTPException(422, "Ekipman/nokta seçimi bölüm/alan ile eşleşmiyor.")
    return row


def _hazard_scope_clause(company: Company):
    return or_(
        FieldHazard.company_id == company.id,
        and_(FieldHazard.company_id.is_(None), FieldHazard.osgb_id == company.osgb_id),
        and_(FieldHazard.company_id.is_(None), FieldHazard.osgb_id.is_(None), FieldHazard.is_system.is_(True)),
    )


def _validate_selection(db: Session, company: Company, category_ids: list[int], hazard_ids: list[int]) -> None:
    if category_ids:
        rows = list(db.scalars(select(FieldHazardCategory).where(FieldHazardCategory.id.in_(category_ids), FieldHazardCategory.is_active.is_(True))).all())
        if len({row.id for row in rows}) != len(set(category_ids)):
            raise HTTPException(422, "Seçilen tehlike kategorilerinden biri geçersiz veya pasif.")
    if hazard_ids:
        rows = list(db.scalars(select(FieldHazard).where(FieldHazard.id.in_(hazard_ids), FieldHazard.is_active.is_(True), _hazard_scope_clause(company))).all())
        if len({row.id for row in rows}) != len(set(hazard_ids)):
            raise HTTPException(422, "Seçilen özel tehlikeler bu işyerinde kullanılamaz.")


def _selected_names(db: Session, inspection: FieldInspection) -> list[str]:
    try:
        ids = json.loads(inspection.selected_category_ids_json or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        ids = []
    if not ids:
        return []
    rows = db.scalars(select(FieldHazardCategory).where(FieldHazardCategory.id.in_(ids))).all()
    by_id = {row.id: row.name for row in rows}
    return [by_id[item] for item in ids if item in by_id]


def _gps_dict(row, *, visible: bool) -> dict | None:
    if not visible:
        return None
    return {
        "lat": row.gps_lat,
        "lng": row.gps_lng,
        "accuracy_m": row.gps_accuracy_m,
        "captured_at": row.gps_captured_at,
        "status": row.gps_status,
        "provider": row.gps_provider,
        "reason": row.gps_reason,
        "manual_note": row.manual_location_note,
    }


def _photo_payload(db: Session, photo: FieldInspectionPhoto, inspection_id: int, *, visible_gps: bool) -> dict:
    site = db.get(FieldInspectionSite, photo.site_id) if photo.site_id else None
    area = db.get(FieldInspectionArea, photo.area_id) if photo.area_id else None
    equipment = db.get(FieldInspectionEquipment, photo.equipment_id) if photo.equipment_id else None
    try:
        edit_meta = json.loads(photo.edit_meta_json or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        edit_meta = {}
    return {
        "id": photo.id,
        "original_name": photo.original_name,
        "content_type": photo.content_type,
        "file_size": photo.file_size,
        "width": photo.width,
        "height": photo.height,
        "edit_meta": edit_meta,
        "captured_at": photo.captured_at,
        "timezone": photo.timezone,
        "location": {
            "site": {"id": site.id, "name": site.name} if site else None,
            "area": {"id": area.id, "name": area.name} if area else None,
            "equipment": {"id": equipment.id, "name": equipment.name, "equipment_type": equipment.equipment_type} if equipment else None,
        },
        "gps": _gps_dict(photo, visible=visible_gps),
        "blur_applied": bool(photo.blur_applied),
        "client_reference": photo.client_reference,
        "variants": {variant: f"/field-inspections/{inspection_id}/photos/{photo.id}/{variant}" for variant in _PHOTO_VARIANTS},
        "annotations": [_annotation_payload(row) for row in photo.annotations if not row.is_deleted],
    }


def _annotation_payload(row: FieldInspectionAnnotation) -> dict:
    try:
        points = json.loads(row.points_json or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        points = []
    return {"id": row.id, "photo_id": row.photo_id, "finding_id": row.finding_id, "shape_type": row.shape_type, "x": row.x, "y": row.y, "width": row.width, "height": row.height, "points": points, "label": row.label, "color": row.color, "source": row.source}


def _finding_payload(row: FieldInspectionFinding) -> dict:
    return {
        "id": row.id,
        "finding_no": row.finding_no,
        "photo_id": row.photo_id,
        "category_id": row.field_category_id,
        "category_name": row.category_name,
        "hazard_id": row.field_hazard_id,
        "hazard_name": row.hazard_name,
        "area_name": row.area_name,
        "equipment_name": row.equipment_name,
        "visual_evidence": row.visual_evidence,
        "nonconformity_description": row.nonconformity_description,
        "possible_cause": row.possible_cause,
        "possible_harm": row.possible_harm,
        "possible_accident_or_disease": row.possible_accident_or_disease,
        "suggested_priority": row.suggested_priority,
        "priority_reason": row.priority_reason,
        "confidence": row.confidence,
        "uncertainty_note": row.uncertainty_note,
        "urgent_action": row.urgent_action,
        "corrective_action": row.corrective_action,
        "preventive_action": row.preventive_action,
        "engineering_control": row.engineering_control,
        "administrative_control": row.administrative_control,
        "training_need": row.training_need,
        "required_ppe": row.required_ppe,
        "suggested_responsible_role": row.suggested_responsible_role,
        "suggested_term_date": row.suggested_term_date,
        "status": row.status,
        "source": row.source,
        "ai_model_name": row.ai_model_name,
        "ai_model_version": row.ai_model_version,
        "ai_prompt_version": row.ai_prompt_version,
        "reviewed_by_id": row.reviewed_by_id,
        "reviewed_at": row.reviewed_at,
        "review_note": row.review_note,
        "legal_references": [{"id": ref.id, "regulation_name": ref.regulation_name, "article": ref.article, "paragraph": ref.paragraph, "source_url": ref.source_url, "source_version": ref.source_version, "relation_explanation": ref.relation_explanation, "verification_status": ref.verification_status, "verified_at": ref.verified_at} for ref in row.legal_references],
        "actions": [_action_payload(action) for action in row.actions],
    }


def _action_payload(row: FieldInspectionAction) -> dict:
    overdue = bool(row.term_date and row.term_date < date.today() and row.status not in {"completed", "cancelled"})
    return {"id": row.id, "finding_id": row.finding_id, "title": row.title, "activity": row.activity, "urgent_action": row.urgent_action, "permanent_solution": row.permanent_solution, "preventive_action": row.preventive_action, "responsible_employee_id": row.responsible_employee_id, "responsible_person": row.responsible_person, "responsible_role": row.responsible_role, "term_date": row.term_date, "priority": row.priority, "status": row.status, "completion_date": row.completion_date, "evidence_photo_id": row.evidence_photo_id, "notes": row.notes, "overdue": overdue, "expert_control_by_id": row.expert_control_by_id, "expert_control_at": row.expert_control_at}


def _revision_items(db: Session, row: FieldInspection, *, limit: int = 100) -> list[dict]:
    """Return audit-backed revisions belonging only to this inspection."""
    entity_ids: dict[str, set[str]] = {"field_inspection": {str(row.id)}}
    for entity_type, values in (
        ("field_inspection_photo", row.photos),
        ("field_inspection_finding", row.findings),
        ("field_inspection_action", row.actions),
    ):
        entity_ids[entity_type] = {str(item.id) for item in values}
    annotations = [annotation for photo in row.photos for annotation in photo.annotations]
    entity_ids["field_inspection_annotation"] = {str(item.id) for item in annotations}
    clauses = [
        and_(AuditLog.entity_type == entity_type, AuditLog.entity_id.in_(values))
        for entity_type, values in entity_ids.items()
        if values
    ]
    if not clauses:
        return []
    logs = db.scalars(
        select(AuditLog)
        .where(AuditLog.company_id == row.company_id, AuditLog.module == "field_inspection", or_(*clauses))
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(max(1, min(int(limit or 100), 200)))
    ).all()
    return [{"id": item.id, "action": item.action, "entity_type": item.entity_type, "entity_id": item.entity_id, "description": item.description, "user_id": item.user_id, "created_at": item.created_at} for item in logs]


def _inspection_payload(db: Session, row: FieldInspection, user: User) -> dict:
    gps_visible = user.role in {UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST}
    site = db.get(FieldInspectionSite, row.site_id)
    area = db.get(FieldInspectionArea, row.area_id)
    equipment = db.get(FieldInspectionEquipment, row.equipment_id) if row.equipment_id else None
    try:
        selected_category_ids = json.loads(row.selected_category_ids_json or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        selected_category_ids = []
    try:
        selected_hazard_ids = json.loads(row.selected_hazard_ids_json or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        selected_hazard_ids = []
    return {
        "id": row.id,
        "inspection_no": row.inspection_no,
        "company_id": row.company_id,
        "site": {"id": site.id, "name": site.name, "site_type": site.site_type} if site else None,
        "area": {"id": area.id, "name": area.name} if area else None,
        "equipment": {"id": equipment.id, "name": equipment.name, "equipment_type": equipment.equipment_type} if equipment else None,
        "inspection_date": row.inspection_date,
        "inspection_at": row.inspection_at,
        "timezone": row.timezone,
        "gps": _gps_dict(row, visible=gps_visible),
        "selected_category_ids": selected_category_ids,
        "selected_category_names": _selected_names(db, row),
        "selected_hazard_ids": selected_hazard_ids,
        "scan_all_hazards": row.scan_all_hazards,
        "notes": row.notes,
        "client_reference": row.client_reference,
        "status": row.status,
        "ai_status": row.ai_status,
        "ai_job_id": row.ai_job_id,
        "ai_error": row.ai_error if user.role in {UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST} else None,
        "ai_model_name": row.ai_model_name,
        "ai_model_version": row.ai_model_version,
        "ai_prompt_version": row.ai_prompt_version,
        "ai_analysis_at": row.ai_analysis_at,
        "ai_general_assessment": row.ai_general_assessment,
        "ai_warning": row.ai_warning,
        "report_revision_no": row.report_revision_no,
        "approved_by_id": row.approved_by_id,
        "approved_at": row.approved_at,
        "created_by_id": row.created_by_id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "revisions": _revision_items(db, row),
        "photos": [_photo_payload(db, photo, row.id, visible_gps=gps_visible) for photo in row.photos if photo.deleted_at is None],
        "findings": [_finding_payload(finding) for finding in row.findings if finding.status not in {"superseded"}],
        "actions": [_action_payload(action) for action in row.actions if action.status != "cancelled"],
        "gps_visible": gps_visible,
    }


def _refresh_marked(photo: FieldInspectionPhoto, db: Session) -> None:
    store = get_object_store()
    analysis = store.get_bytes(photo.analysis_storage_path)
    annotations = list(db.scalars(select(FieldInspectionAnnotation).where(FieldInspectionAnnotation.photo_id == photo.id, FieldInspectionAnnotation.is_deleted.is_(False))).all())
    marked = render_marked_photo(analysis_bytes=analysis, annotations=annotations) if annotations else analysis
    store.put_bytes(photo.marked_storage_path, marked)


def _validate_employee(db: Session, company_id: int, employee_id: int | None) -> Employee | None:
    if employee_id is None:
        return None
    row = db.scalar(select(Employee).where(Employee.id == employee_id, Employee.company_id == company_id, Employee.is_active.is_(True)))
    if not row:
        raise HTTPException(422, "Sorumlu çalışan bu işyerine ait değil veya pasif.")
    return row


def _validate_photo(db: Session, inspection_id: int, photo_id: int | None) -> FieldInspectionPhoto | None:
    if photo_id is None:
        return None
    row = db.scalar(select(FieldInspectionPhoto).where(FieldInspectionPhoto.id == photo_id, FieldInspectionPhoto.inspection_id == inspection_id, FieldInspectionPhoto.deleted_at.is_(None)))
    if not row:
        raise HTTPException(422, "Fotoğraf bu denetime ait değil veya silinmiş.")
    return row


def _validate_form_gps(values: dict) -> None:
    status = values.get("gps_status")
    if status not in _VALID_GPS_STATUSES:
        raise HTTPException(422, "Fotoğraf GPS durumu geçersiz.")
    for key, minimum, maximum in (("gps_lat", -90, 90), ("gps_lng", -180, 180), ("gps_accuracy_m", 0, 100000)):
        value = values.get(key)
        if value is not None and (not math.isfinite(value) or value < minimum or value > maximum):
            raise HTTPException(422, "Fotoğraf GPS değeri geçersiz.")
    has_coordinates = values.get("gps_lat") is not None or values.get("gps_lng") is not None
    if has_coordinates and (values.get("gps_lat") is None or values.get("gps_lng") is None):
        raise HTTPException(422, "Fotoğraf GPS enlem ve boylamı birlikte taşımalıdır.")
    if has_coordinates and status not in {"captured", "low_accuracy"}:
        raise HTTPException(422, "Fotoğraf GPS durumu koordinatlarla uyumlu değil.")
    if not has_coordinates and status in {"captured", "low_accuracy"}:
        raise HTTPException(422, "Koordinat yokken fotoğraf GPS durumu captured olamaz.")


@router.get("/catalog")
def field_catalog(
    company_id: int | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*READ_ROLES)),
):
    seed_field_catalog(db)
    scope = companies_query_for_user(db, user)
    company_stmt = select(Company).where(Company.is_active.is_(True)).order_by(Company.name)
    if scope is not None:
        company_stmt = company_stmt.where(scope)
    companies = list(db.scalars(company_stmt).all())
    # The first catalog load must not silently choose a workplace.  The caller
    # must explicitly provide company_id before company-scoped site/area/
    # equipment data is returned or used for a new inspection.
    selected = _company(db, user, company_id) if company_id is not None else None
    payload = {
        "companies": [{"id": row.id, "name": row.name, "authorized_person": row.authorized_person, "address": row.address, "sgk_registry_no": row.sgk_registry_no, "nace_code": row.nace_code, "hazard_class": row.hazard_class} for row in companies],
        "selected_company_id": selected.id if selected else None,
        "categories": [{"id": row.id, "name": row.name, "sort_order": row.sort_order, "icon": row.icon, "is_system": row.is_system} for row in db.scalars(select(FieldHazardCategory).where(FieldHazardCategory.is_active.is_(True)).order_by(FieldHazardCategory.sort_order, FieldHazardCategory.id)).all()],
        "site_types": list(FIELD_SITE_TYPES), "area_types": list(FIELD_AREA_TYPES), "equipment_types": list(FIELD_EQUIPMENT_TYPES),
        "legal_catalog": [{"name": item["name"], "source_url": item["source_url"], "verified_source": item.get("verified", False), "version": item.get("version")} for item in __import__("app.services.field_inspection_catalog", fromlist=["FIELD_LEGAL_CATALOG"]).FIELD_LEGAL_CATALOG],
    }
    if not selected:
        payload.update({"sites": [], "areas": [], "equipment": [], "custom_hazards": []})
        return payload
    sites = db.scalars(select(FieldInspectionSite).where(FieldInspectionSite.company_id == selected.id, FieldInspectionSite.is_active.is_(True)).order_by(FieldInspectionSite.name)).all()
    areas = db.scalars(select(FieldInspectionArea).where(FieldInspectionArea.company_id == selected.id, FieldInspectionArea.is_active.is_(True)).order_by(FieldInspectionArea.name)).all()
    equipment = db.scalars(select(FieldInspectionEquipment).where(FieldInspectionEquipment.company_id == selected.id, FieldInspectionEquipment.is_active.is_(True)).order_by(FieldInspectionEquipment.name)).all()
    hazards = db.scalars(select(FieldHazard).where(FieldHazard.is_active.is_(True), _hazard_scope_clause(selected)).order_by(FieldHazard.name)).all()
    payload.update({
        "sites": [{"id": row.id, "name": row.name, "site_type": row.site_type, "address": row.address, "description": row.description} for row in sites],
        "areas": [{"id": row.id, "site_id": row.site_id, "name": row.name, "description": row.description} for row in areas],
        "equipment": [{"id": row.id, "site_id": row.site_id, "area_id": row.area_id, "name": row.name, "equipment_type": row.equipment_type, "description": row.description} for row in equipment],
        "custom_hazards": [{"id": row.id, "category_id": row.category_id, "name": row.name, "description": row.description, "equipment_scope": row.equipment_scope, "keywords": json.loads(row.keywords_json or "[]"), "scope": "company" if row.company_id else "osgb" if row.osgb_id else "system"} for row in hazards],
    })
    return payload


@router.get("/responsibles")
def field_responsibles(company_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    _company(db, user, company_id)
    rows = db.scalars(select(Employee).where(Employee.company_id == company_id, Employee.is_active.is_(True)).order_by(Employee.full_name)).all()
    return {"items": [{"id": row.id, "full_name": row.full_name, "job_title": row.job_title, "department": row.department} for row in rows]}


@router.post("/sites")
def create_field_site(payload: SiteCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    company = _company(db, user, payload.company_id)
    key = normalize_name(payload.name)
    existing = db.scalar(select(FieldInspectionSite).where(FieldInspectionSite.company_id == company.id, FieldInspectionSite.name_key == key))
    if existing:
        return {"created": False, "item": {"id": existing.id, "name": existing.name, "site_type": existing.site_type, "address": existing.address}}
    row = FieldInspectionSite(company_id=company.id, name=payload.name, name_key=key, site_type=payload.site_type, address=payload.address, description=payload.description, created_by_id=user.id)
    db.add(row)
    try:
        db.flush()
        _audit(db, user, company.id, action="field_site_created", entity_type="field_inspection_site", entity_id=row.id, description=f"Tesis/saha eklendi: {row.name}")
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Aynı isimde tesis/saha zaten bulunuyor.") from None
    return {"created": True, "item": {"id": row.id, "name": row.name, "site_type": row.site_type, "address": row.address}}


@router.post("/areas")
def create_field_area(payload: AreaCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    _company(db, user, payload.company_id)
    _validate_site(db, payload.company_id, payload.site_id)
    key = normalize_name(payload.name)
    existing = db.scalar(select(FieldInspectionArea).where(FieldInspectionArea.site_id == payload.site_id, FieldInspectionArea.name_key == key))
    if existing:
        return {"created": False, "item": {"id": existing.id, "site_id": existing.site_id, "name": existing.name}}
    row = FieldInspectionArea(company_id=payload.company_id, site_id=payload.site_id, name=payload.name, name_key=key, description=payload.description, created_by_id=user.id)
    db.add(row)
    try:
        db.flush()
        _audit(db, user, payload.company_id, action="field_area_created", entity_type="field_inspection_area", entity_id=row.id, description=f"Bölüm/alan eklendi: {row.name}")
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Aynı isimde bölüm/alan zaten bulunuyor.") from None
    return {"created": True, "item": {"id": row.id, "site_id": row.site_id, "name": row.name}}


@router.post("/equipment")
def create_field_equipment(payload: EquipmentCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    _company(db, user, payload.company_id)
    _validate_site(db, payload.company_id, payload.site_id)
    _validate_area(db, payload.company_id, payload.site_id, payload.area_id)
    key = normalize_name(payload.name)
    existing = db.scalar(select(FieldInspectionEquipment).where(FieldInspectionEquipment.area_id == payload.area_id, FieldInspectionEquipment.name_key == key))
    if existing:
        return {"created": False, "item": {"id": existing.id, "area_id": existing.area_id, "name": existing.name, "equipment_type": existing.equipment_type}}
    row = FieldInspectionEquipment(company_id=payload.company_id, site_id=payload.site_id, area_id=payload.area_id, name=payload.name, name_key=key, equipment_type=payload.equipment_type, description=payload.description, created_by_id=user.id)
    db.add(row)
    try:
        db.flush()
        _audit(db, user, payload.company_id, action="field_equipment_created", entity_type="field_inspection_equipment", entity_id=row.id, description=f"Ekipman/nokta eklendi: {row.name}")
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Aynı isimde ekipman/nokta zaten bulunuyor.") from None
    return {"created": True, "item": {"id": row.id, "area_id": row.area_id, "name": row.name, "equipment_type": row.equipment_type}}


@router.post("/hazards")
def create_field_hazard(payload: FieldHazardCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    company = _company(db, user, payload.company_id)
    _validate_selection(db, company, [payload.category_id], [])
    company_id = company.id if payload.scope == "company" else None
    osgb_id = None if payload.scope == "company" else company.osgb_id
    if payload.scope == "osgb" and not osgb_id:
        raise HTTPException(422, "OSGB kapsamlı tehlike için işyerinin OSGB bağlantısı bulunmalıdır.")
    duplicate = db.scalar(select(FieldHazard).where(FieldHazard.category_id == payload.category_id, FieldHazard.name == payload.name, FieldHazard.company_id == company_id, FieldHazard.osgb_id == osgb_id))
    if duplicate:
        return {"created": False, "item": {"id": duplicate.id, "name": duplicate.name, "category_id": duplicate.category_id, "scope": payload.scope, "is_active": duplicate.is_active}}
    row = FieldHazard(category_id=payload.category_id, company_id=company_id, osgb_id=osgb_id, name=payload.name, description=payload.description, equipment_scope=payload.equipment_scope, keywords_json=json.dumps(payload.keywords, ensure_ascii=False), is_system=False, is_active=payload.is_active, created_by_id=user.id)
    db.add(row)
    db.flush()
    _audit(db, user, company.id, action="field_hazard_created", entity_type="field_hazard", entity_id=row.id, description=f"Özel tehlike eklendi: {row.name}")
    db.commit()
    return {"created": True, "item": {"id": row.id, "name": row.name, "category_id": row.category_id, "scope": payload.scope, "is_active": row.is_active}}


@router.patch("/hazards/{hazard_id}")
def update_field_hazard(hazard_id: int, payload: FieldHazardUpdate, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    hazard = db.get(FieldHazard, hazard_id)
    if not hazard or hazard.is_system:
        raise HTTPException(404, "Özel tehlike bulunamadı.")
    scope_company = db.get(Company, hazard.company_id) if hazard.company_id else db.scalar(
        select(Company).where(Company.osgb_id == hazard.osgb_id, Company.is_active.is_(True)).order_by(Company.id)
    )
    if not scope_company:
        raise HTTPException(404, "Özel tehlike kapsamı bulunamadı.")
    _company(db, user, scope_company.id)
    data = payload.model_dump(exclude_unset=True)
    if "keywords" in data:
        data["keywords_json"] = json.dumps(data.pop("keywords"), ensure_ascii=False)
    for field, value in data.items():
        setattr(hazard, field, value)
    _audit(db, user, scope_company.id, action="field_hazard_updated", entity_type="field_hazard", entity_id=hazard.id, description=f"Özel tehlike güncellendi: {hazard.name}")
    db.commit()
    return {"id": hazard.id, "name": hazard.name, "category_id": hazard.category_id, "scope": "company" if hazard.company_id else "osgb", "is_active": hazard.is_active, "description": hazard.description, "equipment_scope": hazard.equipment_scope, "keywords": json.loads(hazard.keywords_json or "[]")}


@router.post("")
def create_field_inspection(payload: FieldInspectionCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    company = _company(db, user, payload.company_id)
    if payload.client_reference:
        existing = db.scalar(select(FieldInspection).where(FieldInspection.company_id == company.id, FieldInspection.client_reference == payload.client_reference, FieldInspection.deleted_at.is_(None)))
        if existing:
            return _inspection_payload(db, existing, user)
    _validate_site(db, company.id, payload.site_id)
    _validate_area(db, company.id, payload.site_id, payload.area_id)
    _validate_equipment(db, company.id, payload.site_id, payload.area_id, payload.equipment_id)
    _validate_selection(db, company, payload.selected_category_ids, payload.selected_hazard_ids)
    inspection = FieldInspection(
        inspection_no=f"SF-{datetime.utcnow():%Y%m%d}-{uuid.uuid4().hex[:8].upper()}", osgb_id=company.osgb_id, company_id=company.id,
        site_id=payload.site_id, area_id=payload.area_id, equipment_id=payload.equipment_id,
        inspection_date=payload.inspection_date or date.today(), inspection_at=_naive_datetime(payload.inspection_at), timezone=payload.timezone,
        gps_lat=payload.gps_lat, gps_lng=payload.gps_lng, gps_accuracy_m=payload.gps_accuracy_m, gps_captured_at=_naive_datetime(payload.gps_captured_at) if payload.gps_captured_at else None,
        gps_status=payload.gps_status, gps_provider=payload.gps_provider, gps_reason=payload.gps_reason, manual_location_note=payload.manual_location_note,
        selected_category_ids_json=json.dumps(payload.selected_category_ids), selected_hazard_ids_json=json.dumps(payload.selected_hazard_ids), scan_all_hazards=payload.scan_all_hazards,
        notes=payload.notes, client_reference=payload.client_reference, status="draft", ai_status="not_started", created_by_id=user.id,
    )
    db.add(inspection)
    db.flush()
    _audit(db, user, company.id, action="field_inspection_created", entity_type="field_inspection", entity_id=inspection.id, description=f"Görsel saha denetimi oluşturuldu: {inspection.inspection_no}")
    db.commit()
    return _inspection_payload(db, _load_inspection(db, user, inspection.id), user)


@router.get("")
def list_field_inspections(company_id: int | None = Query(None), status: str | None = Query(None), limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    ids = None
    if company_id:
        ensure_company_access(db, user, company_id)
        ids = [company_id]
    else:
        scope = companies_query_for_user(db, user)
        if scope is None:
            ids = None
        else:
            ids = [int(value) for value in db.scalars(select(Company.id).where(scope)).all()]
    stmt = select(FieldInspection).where(FieldInspection.deleted_at.is_(None)).order_by(FieldInspection.inspection_at.desc()).limit(limit)
    if ids is not None:
        if not ids:
            return {"items": []}
        stmt = stmt.where(FieldInspection.company_id.in_(ids))
    if status:
        if status not in _VALID_INSPECTION_STATUSES:
            raise HTTPException(422, "Denetim durumu geçersiz.")
        stmt = stmt.where(FieldInspection.status == status)
    rows = db.scalars(stmt).all()
    return {"items": [{"id": row.id, "inspection_no": row.inspection_no, "company_id": row.company_id, "inspection_date": row.inspection_date, "inspection_at": row.inspection_at, "status": row.status, "ai_status": row.ai_status, "photo_count": db.scalar(select(func.count(FieldInspectionPhoto.id)).where(FieldInspectionPhoto.inspection_id == row.id, FieldInspectionPhoto.deleted_at.is_(None))) or 0, "finding_count": db.scalar(select(func.count(FieldInspectionFinding.id)).where(FieldInspectionFinding.inspection_id == row.id, FieldInspectionFinding.status.not_in(["superseded", "rejected"]))) or 0} for row in rows]}


@router.get("/{inspection_id}")
def get_field_inspection(inspection_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    return _inspection_payload(db, _load_inspection(db, user, inspection_id), user)


@router.patch("/{inspection_id}")
def update_field_inspection(inspection_id: int, payload: FieldInspectionUpdate, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    row = _load_inspection(db, user, inspection_id)
    if row.status == "approved":
        raise HTTPException(409, "Onaylanmış denetim doğrudan değiştirilemez; yeni revizyon oluşturulmalıdır.")
    data = payload.model_dump(exclude_unset=True)
    for field in ("site_id", "area_id", "inspection_date", "inspection_at", "timezone"):
        if field in data and data[field] is None:
            raise HTTPException(422, f"{field} alanı boş bırakılamaz.")
    if payload.status and payload.status not in {"draft", "in_review", "archived"}:
        raise HTTPException(422, "Denetim durumu bu uçtan atanamaz.")
    site_id = payload.site_id if payload.site_id is not None else row.site_id
    area_id = payload.area_id if payload.area_id is not None else row.area_id
    equipment_id = payload.equipment_id if "equipment_id" in data else row.equipment_id
    _validate_site(db, row.company_id, site_id)
    _validate_area(db, row.company_id, site_id, area_id)
    _validate_equipment(db, row.company_id, site_id, area_id, equipment_id)
    category_ids = payload.selected_category_ids if payload.selected_category_ids is not None else json.loads(row.selected_category_ids_json or "[]")
    hazard_ids = payload.selected_hazard_ids if payload.selected_hazard_ids is not None else json.loads(row.selected_hazard_ids_json or "[]")
    company = _company(db, user, row.company_id)
    _validate_selection(db, company, category_ids, hazard_ids)
    if payload.selected_category_ids is not None:
        row.selected_category_ids_json = json.dumps(category_ids)
    if payload.selected_hazard_ids is not None:
        row.selected_hazard_ids_json = json.dumps(hazard_ids)
    for field in ("site_id", "area_id", "equipment_id", "inspection_date", "inspection_at", "timezone", "notes", "status", "scan_all_hazards"):
        if field in data:
            setattr(row, field, _naive_datetime(data[field]) if field == "inspection_at" and data[field] else data[field])
    row.report_revision_no += 1
    _audit(db, user, row.company_id, action="field_inspection_updated", entity_type="field_inspection", entity_id=row.id, description="Görsel saha denetimi güncellendi.")
    db.commit()
    return _inspection_payload(db, _load_inspection(db, user, row.id), user)


@router.post("/{inspection_id}/gps")
def update_field_gps(inspection_id: int, payload: GpsUpdate, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    row = _load_inspection(db, user, inspection_id)
    if row.status == "approved":
        raise HTTPException(409, "Onaylanmış denetimin GPS bilgisi değiştirilemez.")
    for field in ("gps_lat", "gps_lng", "gps_accuracy_m", "gps_captured_at", "gps_status", "gps_provider", "gps_reason", "manual_location_note"):
        value = getattr(payload, field)
        if field == "gps_captured_at" and value:
            value = _naive_datetime(value)
        setattr(row, field, value)
    _audit(db, user, row.company_id, action="field_gps_updated", entity_type="field_inspection", entity_id=row.id, description=f"GPS durumu güncellendi: {row.gps_status}")
    db.commit()
    return _inspection_payload(db, _load_inspection(db, user, row.id), user)


@router.post("/{inspection_id}/photos")
async def upload_field_photo(
    inspection_id: int,
    file: UploadFile = File(...),
    captured_at: datetime | None = Form(None),
    timezone: str | None = Form(None),
    site_id: int | None = Form(None), area_id: int | None = Form(None), equipment_id: int | None = Form(None),
    gps_lat: float | None = Form(None), gps_lng: float | None = Form(None), gps_accuracy_m: float | None = Form(None),
    gps_captured_at: datetime | None = Form(None), gps_status: str | None = Form(None), gps_provider: str | None = Form(None), gps_reason: str | None = Form(None), manual_location_note: str | None = Form(None),
    client_reference: str | None = Form(None), privacy_blur: bool = Form(False), rotation_degrees: int = Form(0), crop_to_square: bool = Form(False),
    db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = _load_inspection(db, user, inspection_id)
    if row.status == "approved":
        raise HTTPException(409, "Onaylanmış denetime yeni fotoğraf eklenemez.")
    if client_reference:
        existing = db.scalar(select(FieldInspectionPhoto).where(FieldInspectionPhoto.inspection_id == row.id, FieldInspectionPhoto.client_reference == client_reference, FieldInspectionPhoto.deleted_at.is_(None)))
        if existing:
            return _photo_payload(db, existing, row.id, visible_gps=user.role in {UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST})
    extension = Path(file.filename or "").suffix.lower()
    if extension not in _PHOTO_EXTENSIONS:
        raise HTTPException(415, "Yalnızca JPG, PNG veya WEBP fotoğraf kabul edilir.")
    limit = int(getattr(settings, "field_inspection_max_upload_mb", 15)) * 1024 * 1024
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(413, f"Fotoğraf {getattr(settings, 'field_inspection_max_upload_mb', 15)} MB sınırını aşıyor.")
    assert_safe_upload(content, extension, file.filename or "")
    if int(rotation_degrees or 0) % 90 != 0 or int(rotation_degrees or 0) % 360 not in {0, 90, 180, 270}:
        raise HTTPException(422, "Fotoğraf döndürme değeri 0, 90, 180 veya 270 olmalıdır.")
    try:
        analysis, preview, width, height = prepare_photo_variants(content, privacy_blur=bool(privacy_blur), rotation_degrees=int(rotation_degrees or 0), crop_to_square=bool(crop_to_square))
    except Exception as exc:
        raise HTTPException(400, "Fotoğraf okunamadı veya geçerli bir görsel değil.") from exc
    photo_gps = {
        "gps_lat": gps_lat if gps_lat is not None else row.gps_lat,
        "gps_lng": gps_lng if gps_lng is not None else row.gps_lng,
        "gps_accuracy_m": gps_accuracy_m if gps_accuracy_m is not None else row.gps_accuracy_m,
        "gps_captured_at": _naive_datetime(gps_captured_at or row.gps_captured_at) if (gps_captured_at or row.gps_captured_at) else None,
        "gps_status": gps_status or row.gps_status,
        "gps_provider": gps_provider or row.gps_provider,
        "gps_reason": gps_reason or row.gps_reason,
        "manual_location_note": manual_location_note or row.manual_location_note,
    }
    _validate_form_gps(photo_gps)
    photo_site_id = site_id if site_id is not None else row.site_id
    photo_area_id = area_id if area_id is not None else row.area_id
    photo_equipment_id = equipment_id if equipment_id is not None else row.equipment_id
    _validate_site(db, row.company_id, photo_site_id)
    _validate_area(db, row.company_id, photo_site_id, photo_area_id)
    _validate_equipment(db, row.company_id, photo_site_id, photo_area_id, photo_equipment_id)
    photo = FieldInspectionPhoto(
        inspection_id=row.id, site_id=photo_site_id, area_id=photo_area_id, equipment_id=photo_equipment_id,
        original_storage_path="", analysis_storage_path="", marked_storage_path="", preview_storage_path="",
        original_name=_safe_original_name(file.filename), content_type=mimetypes.types_map.get(extension, "image/jpeg"), file_size=len(content), width=width, height=height,
        edit_meta_json=json.dumps({"rotation_degrees": int(rotation_degrees or 0) % 360, "crop_to_square": bool(crop_to_square), "privacy_blur": bool(privacy_blur)}),
        captured_at=_naive_datetime(captured_at) if captured_at else datetime.utcnow(), timezone=(timezone or row.timezone), **photo_gps,
        blur_applied=bool(privacy_blur), client_reference=(client_reference or None), created_by_id=user.id,
    )
    db.add(photo)
    db.flush()
    token = uuid.uuid4().hex
    prefix = f"{row.company_id}/field-inspections/{row.id}/{token}"
    photo.original_storage_path = f"{prefix}/original{extension}"
    photo.analysis_storage_path = f"{prefix}/analysis.jpg"
    photo.marked_storage_path = f"{prefix}/marked.jpg"
    photo.preview_storage_path = f"{prefix}/preview.jpg"
    try:
        store_photo_variants(paths={"original": photo.original_storage_path, "analysis": photo.analysis_storage_path, "marked": photo.marked_storage_path, "preview": photo.preview_storage_path}, original=content, analysis=analysis, preview=preview)
        _audit(db, user, row.company_id, action="field_photo_uploaded", entity_type="field_inspection_photo", entity_id=photo.id, description=f"Fotoğraf yüklendi: {photo.original_name}")
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Field inspection photo storage failed: inspection_id=%s", inspection_id)
        raise HTTPException(503, "Fotoğraf güvenli depolamaya alınamadı; tekrar deneyin.") from None
    return _photo_payload(db, photo, row.id, visible_gps=user.role in {UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST})


@router.get("/{inspection_id}/photos/{photo_id}/{variant}")
def get_field_photo(inspection_id: int, photo_id: int, variant: str, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    row = _load_inspection(db, user, inspection_id)
    if variant not in _PHOTO_VARIANTS:
        raise HTTPException(404, "Fotoğraf türevi bulunamadı.")
    photo = _validate_photo(db, row.id, photo_id)
    path = {"original": photo.original_storage_path, "analysis": photo.analysis_storage_path, "marked": photo.marked_storage_path, "preview": photo.preview_storage_path}[variant]
    media_type = photo.content_type if variant == "original" else "image/jpeg"
    _audit(db, user, row.company_id, action="field_photo_viewed", entity_type="field_inspection_photo", entity_id=photo.id, description=f"Fotoğraf türevi görüntülendi: {variant}")
    db.commit()
    return response_for_storage_key(path, filename=photo.original_name if variant == "original" else f"{Path(photo.original_name or 'foto').stem}-{variant}.jpg", media_type=media_type)


@router.delete("/{inspection_id}/photos/{photo_id}")
def delete_field_photo(inspection_id: int, photo_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    row = _load_inspection(db, user, inspection_id)
    if row.status == "approved":
        raise HTTPException(409, "Onaylanmış denetimin fotoğrafı silinemez.")
    photo = _validate_photo(db, row.id, photo_id)
    photo.deleted_at = datetime.utcnow()
    for annotation in photo.annotations:
        annotation.is_deleted = True
    _refresh_marked(photo, db)
    _audit(db, user, row.company_id, action="field_photo_deleted", entity_type="field_inspection_photo", entity_id=photo.id, description="Fotoğraf soft-delete yapıldı.")
    db.commit()
    return {"ok": True, "id": photo.id}


@router.post("/{inspection_id}/analyze")
def queue_field_analysis(inspection_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    row = _load_inspection(db, user, inspection_id)
    if row.status == "approved":
        raise HTTPException(409, "Onaylanmış denetim tekrar analiz edilemez.")
    if not any(photo.deleted_at is None for photo in row.photos):
        raise HTTPException(422, "Analiz için en az bir fotoğraf yükleyin.")
    row.ai_status = "queued"
    row.ai_error = None
    row.status = "in_review"
    db.commit()
    if not field_ai_is_configured():
        row.ai_status = "failed"
        row.ai_error = "Görsel AI yapılandırılmamış veya kapalı. Bulgular oluşturulmadı."
        row.status = "draft"
        _audit(db, user, row.company_id, action="field_ai_not_configured", entity_type="field_inspection", entity_id=row.id, description=row.ai_error)
        db.commit()
        fresh = _load_inspection(db, user, inspection_id)
        return {"job_id": None, "job_status": "failed", "inspection": _inspection_payload(db, fresh, user)}
    try:
        job = enqueue("field_visual_analysis", run_visual_field_analysis_job, row.id, _force_async=True)
        row = db.get(FieldInspection, row.id)
        if row:
            row.ai_job_id = job.id
            db.commit()
    except Exception as exc:
        db.rollback()
        row = db.get(FieldInspection, inspection_id)
        if row:
            row.ai_status = "failed"
            row.ai_error = "Analiz kuyruğa alınamadı: " + str(exc)[:3800]
            row.status = "draft"
            db.commit()
        raise HTTPException(503, "AI analiz işi kuyruğa alınamadı; mevcut fotoğraflar korunuyor.") from exc
    fresh = _load_inspection(db, user, inspection_id)
    return {"job_id": job.id, "job_status": getattr(job.status, "value", str(job.status)), "inspection": _inspection_payload(db, fresh, user)}


@router.get("/{inspection_id}/analysis")
def field_analysis_status(inspection_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    row = _load_inspection(db, user, inspection_id)
    return {"inspection_id": row.id, "ai_status": row.ai_status, "ai_job_id": row.ai_job_id, "ai_error": row.ai_error if user.role in {UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST} else None, "status": row.status, "finding_count": len([item for item in row.findings if item.status != "superseded"])}


@router.get("/{inspection_id}/revisions")
def field_inspection_revisions(inspection_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    row = _load_inspection(db, user, inspection_id)
    return {"inspection_id": row.id, "revision_no": row.report_revision_no, "items": _revision_items(db, row)}


@router.post("/{inspection_id}/findings")
def create_manual_finding(inspection_id: int, payload: ManualFindingCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    row = _load_inspection(db, user, inspection_id)
    if row.status == "approved":
        raise HTTPException(409, "Onaylanmış denetime yeni bulgu eklenemez.")
    photo = _validate_photo(db, row.id, payload.photo_id)
    category = db.get(FieldHazardCategory, payload.category_id) if payload.category_id else None
    if category and not category.is_active:
        raise HTTPException(422, "Tehlike kategorisi pasif.")
    hazard = db.get(FieldHazard, payload.hazard_id) if payload.hazard_id else None
    if hazard:
        _validate_selection(db, _company(db, user, row.company_id), [hazard.category_id], [hazard.id])
    number = max((int(item.finding_no or 0) for item in row.findings), default=0) + 1
    area = db.get(FieldInspectionArea, row.area_id)
    equipment = db.get(FieldInspectionEquipment, row.equipment_id) if row.equipment_id else None
    finding = FieldInspectionFinding(inspection_id=row.id, photo_id=photo.id if photo else None, field_category_id=category.id if category else None, field_hazard_id=hazard.id if hazard else None, finding_no=number, category_name=category.name if category else None, hazard_name=payload.hazard_name, area_name=area.name if area else None, equipment_name=equipment.name if equipment else None, visual_evidence=payload.visual_evidence, nonconformity_description=payload.nonconformity_description, possible_cause=payload.possible_cause, possible_harm=payload.possible_harm, possible_accident_or_disease=payload.possible_accident_or_disease, suggested_priority=payload.suggested_priority, priority_reason=payload.priority_reason, urgent_action=payload.urgent_action, corrective_action=payload.corrective_action, preventive_action=payload.preventive_action, suggested_responsible_role=payload.suggested_responsible_role, suggested_term_date=payload.suggested_term_date, status="under_review", source="manual", created_by_id=user.id)
    db.add(finding)
    row.status = "in_review"
    row.report_revision_no += 1
    db.flush()
    _audit(db, user, row.company_id, action="field_finding_created", entity_type="field_inspection_finding", entity_id=finding.id, description="Manuel bulgu uzman incelemesine alındı.")
    db.commit()
    return _finding_payload(db.get(FieldInspectionFinding, finding.id))


@router.patch("/{inspection_id}/findings/{finding_id}")
@router.post("/{inspection_id}/findings/{finding_id}/review")
def review_field_finding(inspection_id: int, finding_id: int, payload: FindingReview, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    row = _load_inspection(db, user, inspection_id)
    if row.status == "approved":
        raise HTTPException(409, "Onaylanmış denetim bulgusu değiştirilemez.")
    finding = db.scalar(select(FieldInspectionFinding).options(selectinload(FieldInspectionFinding.legal_references), selectinload(FieldInspectionFinding.actions)).where(FieldInspectionFinding.id == finding_id, FieldInspectionFinding.inspection_id == row.id))
    if not finding:
        raise HTTPException(404, "Bulgu bulunamadı.")
    data = payload.model_dump(exclude_unset=True)
    status_value = data.pop("status")
    if "review_note" in data:
        finding.review_note = data.pop("review_note")
    for field, value in data.items():
        if hasattr(finding, field):
            setattr(finding, field, value)
    finding.status = status_value
    finding.reviewed_by_id = user.id
    finding.reviewed_at = datetime.utcnow()
    row.status = "in_review"
    row.report_revision_no += 1
    _audit(db, user, row.company_id, action="field_finding_reviewed", entity_type="field_inspection_finding", entity_id=finding.id, description=f"Bulgu uzman tarafından {status_value} durumuna getirildi.")
    db.commit()
    fresh = db.scalar(select(FieldInspectionFinding).options(selectinload(FieldInspectionFinding.legal_references), selectinload(FieldInspectionFinding.actions)).where(FieldInspectionFinding.id == finding.id))
    return _finding_payload(fresh)


@router.put("/{inspection_id}/findings/{finding_id}/legal-references")
def update_field_legal_references(inspection_id: int, finding_id: int, payload: LegalReferenceUpdate, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    row = _load_inspection(db, user, inspection_id)
    finding = db.scalar(select(FieldInspectionFinding).where(FieldInspectionFinding.id == finding_id, FieldInspectionFinding.inspection_id == row.id))
    if not finding:
        raise HTTPException(404, "Bulgu bulunamadı.")
    if row.status == "approved":
        raise HTTPException(409, "Onaylanmış denetim mevzuat atfını değiştiremez.")
    db.execute(delete(FieldInspectionLegalReference).where(FieldInspectionLegalReference.finding_id == finding.id))
    for reference in payload.references:
        entry = legal_entry(reference.regulation_name)
        if not entry:
            raise HTTPException(422, "Mevzuat başlığı başlangıç kataloğunda değil; otomatik atıf eklenmedi.")
        source_url = reference.source_url or str(entry["source_url"])
        if not _is_official_legal_url(source_url):
            raise HTTPException(422, "Mevzuat kaynağı yalnızca resmî alan adlarından olabilir.")
        db.add(FieldInspectionLegalReference(finding_id=finding.id, regulation_name=reference.regulation_name, article=reference.article, paragraph=reference.paragraph, source_url=source_url, source_version=reference.source_version or str(entry.get("version") or "uzman kontrolü"), relation_explanation=reference.relation_explanation, verification_status=reference.verification_status, verified_at=datetime.utcnow() if reference.verification_status == "verified" else None))
    row.report_revision_no += 1
    _audit(db, user, row.company_id, action="field_legal_references_updated", entity_type="field_inspection_finding", entity_id=finding.id, description="Bulgunun mevzuat atıfları uzman tarafından güncellendi.")
    db.commit()
    fresh = db.scalar(select(FieldInspectionFinding).options(selectinload(FieldInspectionFinding.legal_references), selectinload(FieldInspectionFinding.actions)).where(FieldInspectionFinding.id == finding.id))
    return _finding_payload(fresh)


@router.post("/{inspection_id}/findings/{finding_id}/actions")
def create_field_action(inspection_id: int, finding_id: int, payload: ActionCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    row = _load_inspection(db, user, inspection_id)
    if row.status == "approved":
        raise HTTPException(409, "Onaylanmış denetime yeni faaliyet eklenemez.")
    if payload.finding_id is not None and payload.finding_id != finding_id:
        raise HTTPException(422, "Faaliyet bulguyla eşleşmiyor.")
    finding = db.scalar(select(FieldInspectionFinding).where(FieldInspectionFinding.id == finding_id, FieldInspectionFinding.inspection_id == row.id))
    if not finding:
        raise HTTPException(422, "Faaliyet bulguyla eşleşmiyor.")
    employee = _validate_employee(db, row.company_id, payload.responsible_employee_id)
    evidence = _validate_photo(db, row.id, payload.evidence_photo_id)
    action = FieldInspectionAction(inspection_id=row.id, finding_id=finding.id if finding else None, company_id=row.company_id, title=payload.title, activity=payload.activity, urgent_action=payload.urgent_action, permanent_solution=payload.permanent_solution, preventive_action=payload.preventive_action, responsible_employee_id=employee.id if employee else None, responsible_person=payload.responsible_person, responsible_role=payload.responsible_role, term_date=payload.term_date, priority=payload.priority, status="open", evidence_photo_id=evidence.id if evidence else None, notes=payload.notes, created_by_id=user.id)
    db.add(action)
    row.report_revision_no += 1
    db.flush()
    _audit(db, user, row.company_id, action="field_action_created", entity_type="field_inspection_action", entity_id=action.id, description=f"Faaliyet eklendi: {action.title}")
    db.commit()
    return _action_payload(action)


@router.patch("/{inspection_id}/actions/{action_id}")
def update_field_action(inspection_id: int, action_id: int, payload: ActionUpdate, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    row = _load_inspection(db, user, inspection_id)
    action = db.scalar(select(FieldInspectionAction).where(FieldInspectionAction.id == action_id, FieldInspectionAction.inspection_id == row.id))
    if not action:
        raise HTTPException(404, "Faaliyet bulunamadı.")
    if row.status == "approved":
        raise HTTPException(409, "Onaylanmış denetim faaliyeti değiştirilemez.")
    data = payload.model_dump(exclude_unset=True)
    if "responsible_employee_id" in data:
        employee = _validate_employee(db, row.company_id, data["responsible_employee_id"])
        data["responsible_employee_id"] = employee.id if employee else None
    if "status" in data and data["status"] not in {"open", "in_progress", "completed", "cancelled"}:
        raise HTTPException(422, "Faaliyet durumu geçersiz.")
    if data.get("status") == "completed" and not data.get("completion_date"):
        data["completion_date"] = date.today()
    for field, value in data.items():
        setattr(action, field, value)
    row.report_revision_no += 1
    _audit(db, user, row.company_id, action="field_action_updated", entity_type="field_inspection_action", entity_id=action.id, description="DÖF/faaliyet güncellendi.")
    db.commit()
    return _action_payload(action)


@router.post("/{inspection_id}/actions/{action_id}/complete")
def complete_field_action(inspection_id: int, action_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    row = _load_inspection(db, user, inspection_id)
    action = db.scalar(select(FieldInspectionAction).where(FieldInspectionAction.id == action_id, FieldInspectionAction.inspection_id == row.id))
    if not action:
        raise HTTPException(404, "Faaliyet bulunamadı.")
    action.status, action.completion_date, action.expert_control_by_id, action.expert_control_at = "completed", date.today(), user.id, datetime.utcnow()
    row.report_revision_no += 1
    _audit(db, user, row.company_id, action="field_action_completed", entity_type="field_inspection_action", entity_id=action.id, description="Faaliyet uzman kontrolüyle tamamlandı.")
    db.commit()
    return _action_payload(action)


@router.post("/{inspection_id}/photos/{photo_id}/annotations")
def create_field_annotation(inspection_id: int, photo_id: int, payload: AnnotationCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    row = _load_inspection(db, user, inspection_id)
    if row.status == "approved":
        raise HTTPException(409, "Onaylanmış fotoğraf işaretleri değiştirilemez.")
    if payload.photo_id != photo_id:
        raise HTTPException(422, "Fotoğraf kimliği eşleşmiyor.")
    photo = _validate_photo(db, row.id, photo_id)
    finding = db.scalar(select(FieldInspectionFinding).where(FieldInspectionFinding.id == payload.finding_id, FieldInspectionFinding.inspection_id == row.id)) if payload.finding_id else None
    if payload.finding_id and not finding:
        raise HTTPException(422, "İşaret bulguyla eşleşmiyor.")
    annotation = FieldInspectionAnnotation(inspection_id=row.id, photo_id=photo.id, finding_id=finding.id if finding else None, shape_type=payload.shape_type, x=payload.x, y=payload.y, width=payload.width, height=payload.height, points_json=json.dumps(payload.points), label=payload.label, color=payload.color if re.fullmatch(r"#[0-9a-fA-F]{3,8}", payload.color) else "#dc2626", source="manual", created_by_id=user.id)
    db.add(annotation)
    db.flush()
    _refresh_marked(photo, db)
    row.report_revision_no += 1
    _audit(db, user, row.company_id, action="field_annotation_created", entity_type="field_inspection_annotation", entity_id=annotation.id, description="Fotoğraf işareti eklendi.")
    db.commit()
    return _annotation_payload(annotation)


@router.patch("/{inspection_id}/annotations/{annotation_id}")
def update_field_annotation(inspection_id: int, annotation_id: int, payload: AnnotationUpdate, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    row = _load_inspection(db, user, inspection_id)
    if row.status == "approved":
        raise HTTPException(409, "Onaylanmış fotoğraf işaretleri değiştirilemez.")
    annotation = db.scalar(select(FieldInspectionAnnotation).where(FieldInspectionAnnotation.id == annotation_id, FieldInspectionAnnotation.inspection_id == row.id, FieldInspectionAnnotation.is_deleted.is_(False)))
    if not annotation:
        raise HTTPException(404, "Fotoğraf işareti bulunamadı.")
    data = payload.model_dump(exclude_unset=True)
    if "points" in data:
        data["points_json"] = json.dumps(data.pop("points"))
    if "color" in data and not re.fullmatch(r"#[0-9a-fA-F]{3,8}", data["color"] or ""):
        data["color"] = "#dc2626"
    for field, value in data.items():
        setattr(annotation, field, value)
    photo = _validate_photo(db, row.id, annotation.photo_id)
    _refresh_marked(photo, db)
    row.report_revision_no += 1
    db.commit()
    return _annotation_payload(annotation)


@router.delete("/{inspection_id}/annotations/{annotation_id}")
def delete_field_annotation(inspection_id: int, annotation_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    row = _load_inspection(db, user, inspection_id)
    annotation = db.scalar(select(FieldInspectionAnnotation).where(FieldInspectionAnnotation.id == annotation_id, FieldInspectionAnnotation.inspection_id == row.id, FieldInspectionAnnotation.is_deleted.is_(False)))
    if not annotation:
        raise HTTPException(404, "Fotoğraf işareti bulunamadı.")
    annotation.is_deleted = True
    photo = _validate_photo(db, row.id, annotation.photo_id)
    _refresh_marked(photo, db)
    row.report_revision_no += 1
    db.commit()
    return {"ok": True, "id": annotation.id}


@router.post("/{inspection_id}/approve")
def approve_field_inspection(inspection_id: int, payload: ApprovalPayload | None = None, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    row = _load_inspection(db, user, inspection_id)
    blocked = [finding for finding in row.findings if finding.status in _ACTIVE_FINDING_STATUSES]
    if blocked:
        raise HTTPException(409, "Tüm AI ve manuel taslak bulgular uzman tarafından kabul veya reddedilmeden onay verilemez.")
    if row.ai_status in {"queued", "running"}:
        raise HTTPException(409, "AI analizi devam ederken onay verilemez.")
    row.status = "approved"
    row.approved_by_id = user.id
    row.approved_at = datetime.utcnow()
    row.report_revision_no += 1
    _audit(db, user, row.company_id, action="field_inspection_approved", entity_type="field_inspection", entity_id=row.id, description=(payload.note if payload else None) or "Görsel saha denetimi uzman tarafından onaylandı.")
    db.commit()
    return _inspection_payload(db, _load_inspection(db, user, row.id), user)


def _report_context(db: Session, user: User, inspection_id: int):
    row = _load_inspection(db, user, inspection_id)
    if row.status != "approved":
        raise HTTPException(409, "Rapor yalnızca uzman onayından sonra oluşturulabilir.")
    company = db.get(Company, row.company_id)
    site = db.get(FieldInspectionSite, row.site_id)
    area = db.get(FieldInspectionArea, row.area_id)
    equipment = db.get(FieldInspectionEquipment, row.equipment_id) if row.equipment_id else None
    photos = [photo for photo in row.photos if photo.deleted_at is None]
    findings = [finding for finding in row.findings if finding.status in _REPORT_FINDING_STATUSES]
    actions = [action for action in row.actions if action.status != "cancelled"]
    row.selected_category_names = _selected_names(db, row)
    creator = db.get(User, row.created_by_id) if row.created_by_id else None
    row.report_creator_name = getattr(creator, "full_name", None) or user.full_name
    row.report_approver_name = getattr(db.get(User, row.approved_by_id), "full_name", None) if row.approved_by_id else None
    for photo in photos:
        photo.report_site_name = getattr(db.get(FieldInspectionSite, photo.site_id), "name", None) if photo.site_id else None
        photo.report_area_name = getattr(db.get(FieldInspectionArea, photo.area_id), "name", None) if photo.area_id else None
        photo.report_equipment_name = getattr(db.get(FieldInspectionEquipment, photo.equipment_id), "name", None) if photo.equipment_id else None
    for action in actions:
        employee = db.get(Employee, action.responsible_employee_id) if action.responsible_employee_id else None
        action.report_responsible_name = getattr(employee, "full_name", None)
    row.revision_history = _revision_items(db, row)
    return row, company, site, area, equipment, photos, findings, actions


@router.get("/{inspection_id}/report.pdf")
def field_inspection_report_pdf(inspection_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    row, company, site, area, equipment, photos, findings, actions = _report_context(db, user, inspection_id)
    _audit(db, user, row.company_id, action="field_report_pdf_downloaded", entity_type="field_inspection", entity_id=row.id, description="Görsel saha denetimi PDF raporu indirildi.")
    db.commit()
    content = build_field_inspection_pdf(inspection=row, company=company, site=site, area=area, equipment=equipment, photos=photos, findings=findings, actions=actions, include_gps=user.role in {UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST})
    return Response(content=content, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="saha-denetim-{row.inspection_no}.pdf"', "Cache-Control": "no-store"})


@router.get("/{inspection_id}/report.xlsx")
def field_inspection_report_xlsx(inspection_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    row, company, site, area, equipment, photos, findings, actions = _report_context(db, user, inspection_id)
    _audit(db, user, row.company_id, action="field_report_xlsx_downloaded", entity_type="field_inspection", entity_id=row.id, description="Görsel saha denetimi Excel raporu indirildi.")
    db.commit()
    content = build_field_inspection_excel(inspection=row, company=company, site=site, area=area, equipment=equipment, photos=photos, findings=findings, actions=actions, include_gps=user.role in {UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST})
    return Response(content=content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="saha-denetim-{row.inspection_no}.xlsx"', "Cache-Control": "no-store"})


@router.delete("/{inspection_id}")
def archive_field_inspection(inspection_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*EDIT_ROLES))):
    row = _load_inspection(db, user, inspection_id)
    if row.status == "approved":
        raise HTTPException(409, "Onaylanmış denetim arşivlenemez; rapor geçmişi korunmalıdır.")
    row.deleted_at = datetime.utcnow()
    row.status = "archived"
    _audit(db, user, row.company_id, action="field_inspection_archived", entity_type="field_inspection", entity_id=row.id, description="Görsel saha denetimi arşivlendi.")
    db.commit()
    return {"ok": True, "id": row.id, "status": row.status}
