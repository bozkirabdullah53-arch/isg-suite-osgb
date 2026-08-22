"""OSGB yetkili firma yönetimi: kart, belge, uygunluk, skor ve çıktılar."""
from __future__ import annotations

import json
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import reject_company_bound_admin_from_osgb_internal, require_roles
from app.core.database import get_db
from app.models.authorized_firm import (
    AuthorizedFirmDocument,
    AuthorizedFirmProfile,
    ProfessionalComplianceProfile,
)
from app.models.entities import (
    AuditLog,
    Company,
    DocumentRecord,
    IsgProfessional,
    User,
    UserRole,
    WorkplaceAssignment,
)
from app.schemas.authorized_firm import (
    AuthorizedFirmCreate,
    AuthorizedFirmDocumentCreate,
    AuthorizedFirmDocumentUpdate,
    AuthorizedFirmUpdate,
    OnboardingProgressUpdate,
    ProfessionalComplianceUpsert,
)
from app.services.authorized_firm_compliance import (
    build_dashboard_summary,
    build_osgb_comparison,
    build_profile_detail,
    evaluate_professional_compliance,
    list_profile_summaries,
    save_score_snapshot,
    validate_document_dates,
    validate_professional_dates,
    validate_profile_dates,
)
from app.services.authorized_firm_reports import (
    build_authorized_firm_excel,
    build_authorized_firm_pdf,
    build_inspection_package,
    build_status_report_excel,
    safe_filename,
)


router = APIRouter(
    prefix="/authorized-firms",
    tags=["Yetkili Firma Yönetimi"],
    dependencies=[Depends(reject_company_bound_admin_from_osgb_internal)],
)
ADMIN_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)


def _resolve_osgb(user: User, requested: int | None, *, required: bool = False) -> int | None:
    if user.role == UserRole.COMPANY_ADMIN:
        if not user.osgb_id:
            raise HTTPException(400, "OSGB kapsamınız tanımlı değil.")
        if requested is not None and requested != user.osgb_id:
            raise HTTPException(403, "Başka bir OSGB kapsamına erişemezsiniz.")
        return user.osgb_id
    if required and requested is None:
        raise HTTPException(400, "osgb_id zorunludur.")
    return requested


def _get_profile(db: Session, profile_id: int, user: User) -> AuthorizedFirmProfile:
    stmt = select(AuthorizedFirmProfile).where(AuthorizedFirmProfile.id == profile_id)
    target_osgb = _resolve_osgb(user, None)
    if target_osgb is not None:
        stmt = stmt.where(AuthorizedFirmProfile.osgb_id == target_osgb)
    profile = db.scalar(stmt)
    if not profile:
        raise HTTPException(404, "Yetkili firma kartı bulunamadı.")
    return profile


def _get_document(
    db: Session,
    profile: AuthorizedFirmProfile,
    document_id: int,
) -> AuthorizedFirmDocument:
    item = db.scalar(
        select(AuthorizedFirmDocument).where(
            AuthorizedFirmDocument.id == document_id,
            AuthorizedFirmDocument.profile_id == profile.id,
            AuthorizedFirmDocument.osgb_id == profile.osgb_id,
            AuthorizedFirmDocument.company_id == profile.company_id,
        )
    )
    if not item:
        raise HTTPException(404, "Yetkili firma belgesi bulunamadı.")
    return item


def _audit(
    db: Session,
    *,
    user: User,
    company_id: int,
    action: str,
    entity_type: str,
    entity_id: int,
    description: str,
    old_value=None,
    new_value=None,
) -> None:
    def serialize(value):
        return json.dumps(value, ensure_ascii=False, default=str) if value is not None else None

    db.add(
        AuditLog(
            user_id=user.id,
            company_id=company_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            description=description[:1200],
            module="authorized_firms",
            old_value=serialize(old_value),
            new_value=serialize(new_value),
        )
    )


def _merge_dates(obj, data: dict, names: tuple[str, ...]) -> dict:
    return {name: data.get(name, getattr(obj, name, None)) for name in names}


def _validate_linked_document(db: Session, company_id: int, document_record_id: int | None) -> None:
    if document_record_id is None:
        return
    linked = db.get(DocumentRecord, document_record_id)
    if not linked or linked.company_id != company_id:
        raise HTTPException(400, "Bağlı doküman kaydı bu işyerine ait değil.")


def _file_response(data: bytes, *, media_type: str, filename: str) -> StreamingResponse:
    return StreamingResponse(
        iter([data]),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _filtered_rows(
    db: Session,
    *,
    user: User,
    osgb_id: int | None,
    q: str | None,
    province: str | None,
    district: str | None,
    active: bool | None,
    hazard_class: str | None,
    document_status: str | None,
    professional_id: int | None,
    professional_status: str | None,
    expiry_from: date | None,
    expiry_to: date | None,
    readiness: str | None,
    min_score: int | None,
) -> list[dict]:
    target = _resolve_osgb(user, osgb_id)
    if expiry_from and expiry_to and expiry_to < expiry_from:
        raise HTTPException(400, "Bitiş filtresi başlangıç filtresinden önce olamaz.")
    return list_profile_summaries(
        db,
        osgb_id=target,
        viewer=user,
        query=q,
        province=province,
        district=district,
        active=active,
        hazard_class=hazard_class,
        document_status=document_status,
        professional_id=professional_id,
        professional_status=professional_status,
        expiry_from=expiry_from,
        expiry_to=expiry_to,
        readiness=readiness,
        min_score=min_score,
    )


@router.get("")
def list_authorized_firms(
    response: Response,
    osgb_id: int | None = None,
    q: str | None = Query(default=None, max_length=160),
    province: str | None = Query(default=None, max_length=80),
    district: str | None = Query(default=None, max_length=100),
    active: bool | None = None,
    hazard_class: str | None = Query(default=None, max_length=40),
    document_status: str | None = Query(default=None, pattern="^(missing|expired|expiring|valid)$"),
    professional_id: int | None = Query(default=None, gt=0),
    professional_status: str | None = Query(
        default=None,
        pattern="^(compliant|partially_compliant|missing_documents|expired_documents|assignment_problem|review_required)$",
    ),
    expiry_from: date | None = None,
    expiry_to: date | None = None,
    readiness: str | None = Query(default=None, pattern="^(ready|attention|significant|critical)$"),
    min_score: int | None = Query(default=None, ge=0, le=100),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    response.headers["Cache-Control"] = "no-store"
    rows = _filtered_rows(
        db,
        user=user,
        osgb_id=osgb_id,
        q=q,
        province=province,
        district=district,
        active=active,
        hazard_class=hazard_class,
        document_status=document_status,
        professional_id=professional_id,
        professional_status=professional_status,
        expiry_from=expiry_from,
        expiry_to=expiry_to,
        readiness=readiness,
        min_score=min_score,
    )
    return {"items": rows[offset: offset + limit], "total": len(rows), "offset": offset, "limit": limit}


@router.get("/dashboard")
def authorized_firm_dashboard(
    response: Response,
    osgb_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    response.headers["Cache-Control"] = "no-store"
    target = _resolve_osgb(user, osgb_id, required=True)
    return build_dashboard_summary(db, osgb_id=target, viewer=user)


@router.get("/comparison")
def authorized_firm_osgb_comparison(
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    response.headers["Cache-Control"] = "no-store"
    return build_osgb_comparison(db, viewer=user)


@router.get("/status-report.xlsx")
def authorized_firm_status_report(
    osgb_id: int | None = None,
    q: str | None = Query(default=None, max_length=160),
    province: str | None = Query(default=None, max_length=80),
    district: str | None = Query(default=None, max_length=100),
    active: bool | None = None,
    hazard_class: str | None = Query(default=None, max_length=40),
    document_status: str | None = Query(default=None, pattern="^(missing|expired|expiring|valid)$"),
    readiness: str | None = Query(default=None, pattern="^(ready|attention|significant|critical)$"),
    min_score: int | None = Query(default=None, ge=0, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    rows = _filtered_rows(
        db,
        user=user,
        osgb_id=osgb_id,
        q=q,
        province=province,
        district=district,
        active=active,
        hazard_class=hazard_class,
        document_status=document_status,
        professional_id=None,
        professional_status=None,
        expiry_from=None,
        expiry_to=None,
        readiness=readiness,
        min_score=min_score,
    )
    return _file_response(
        build_status_report_excel(rows),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"yetkili-firma-durum-{date.today().isoformat()}.xlsx",
    )


@router.get("/by-company/{company_id}")
def authorized_firm_by_company(
    company_id: int,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    stmt = select(AuthorizedFirmProfile).where(AuthorizedFirmProfile.company_id == company_id)
    target_osgb = _resolve_osgb(user, None)
    if target_osgb is not None:
        stmt = stmt.where(AuthorizedFirmProfile.osgb_id == target_osgb)
    profile = db.scalar(stmt)
    if not profile:
        raise HTTPException(404, "Bu işyeri için yetkili firma kartı bulunamadı.")
    response.headers["Cache-Control"] = "no-store"
    return build_profile_detail(db, profile, viewer=user)


@router.post("")
def create_authorized_firm(
    payload: AuthorizedFirmCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    osgb_id = _resolve_osgb(user, payload.osgb_id, required=True)
    company = db.get(Company, payload.company_id)
    if not company or company.osgb_id != osgb_id:
        raise HTTPException(400, "İşyeri bu OSGB kapsamına bağlı değil.")
    if db.scalar(
        select(AuthorizedFirmProfile.id).where(AuthorizedFirmProfile.company_id == company.id)
    ):
        raise HTTPException(409, "Bu işyeri için yetkili firma kartı zaten var.")
    data = payload.model_dump()
    data["osgb_id"] = osgb_id
    data["firm_name"] = data.get("firm_name") or company.name
    validate_profile_dates(data)
    now = datetime.utcnow()
    if data.get("review_state") == "manually_reviewed":
        data.update(reviewed_by_id=user.id, reviewed_at=now)
    profile = AuthorizedFirmProfile(
        **data,
        created_by_id=user.id,
        updated_by_id=user.id,
    )
    db.add(profile)
    try:
        db.flush()
        _audit(
            db,
            user=user,
            company_id=company.id,
            action="create",
            entity_type="authorized_firm_profile",
            entity_id=profile.id,
            description="Yetkili firma kartı oluşturuldu.",
            new_value=data,
        )
        save_score_snapshot(db, profile, user=user)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Yetkili firma kartı oluşturulamadı; kayıt çakışması var.") from exc
    db.refresh(profile)
    return build_profile_detail(db, profile, viewer=user)


@router.get("/{profile_id}")
def get_authorized_firm(
    profile_id: int,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    response.headers["Cache-Control"] = "no-store"
    return build_profile_detail(db, _get_profile(db, profile_id, user), viewer=user)


@router.patch("/{profile_id}")
def update_authorized_firm(
    profile_id: int,
    payload: AuthorizedFirmUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    profile = _get_profile(db, profile_id, user)
    data = payload.model_dump(exclude_unset=True)
    if "firm_name" in data and not data["firm_name"]:
        raise HTTPException(422, "Yetkili firma adı boş olamaz.")
    merged = _merge_dates(
        profile,
        data,
        ("authorization_issue_date", "authorization_start_date", "authorization_expiry_date"),
    )
    try:
        validate_profile_dates(merged)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    old = {key: getattr(profile, key) for key in data}
    if data.get("review_state") == "manually_reviewed":
        data.update(reviewed_by_id=user.id, reviewed_at=datetime.utcnow())
    elif data.get("review_state") == "internal_record":
        data.update(reviewed_by_id=None, reviewed_at=None)
    for key, value in data.items():
        setattr(profile, key, value)
    profile.updated_by_id = user.id
    _audit(
        db,
        user=user,
        company_id=profile.company_id,
        action="update",
        entity_type="authorized_firm_profile",
        entity_id=profile.id,
        description="Yetkili firma kartı güncellendi.",
        old_value=old,
        new_value=data,
    )
    save_score_snapshot(db, profile, user=user)
    db.commit()
    db.refresh(profile)
    return build_profile_detail(db, profile, viewer=user)


@router.delete("/{profile_id}")
def deactivate_authorized_firm(
    profile_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    profile = _get_profile(db, profile_id, user)
    profile.is_active = False
    profile.updated_by_id = user.id
    _audit(
        db,
        user=user,
        company_id=profile.company_id,
        action="deactivate",
        entity_type="authorized_firm_profile",
        entity_id=profile.id,
        description="Yetkili firma kartı pasife alındı; kayıtlar korunuyor.",
    )
    db.commit()
    return {"ok": True, "id": profile.id, "is_active": False}


@router.post("/{profile_id}/documents")
def create_authorized_firm_document(
    profile_id: int,
    payload: AuthorizedFirmDocumentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    profile = _get_profile(db, profile_id, user)
    data = payload.model_dump()
    _validate_linked_document(db, profile.company_id, data.get("document_record_id"))
    validate_document_dates(data)
    item = AuthorizedFirmDocument(
        **data,
        profile_id=profile.id,
        osgb_id=profile.osgb_id,
        company_id=profile.company_id,
        created_by_id=user.id,
    )
    db.add(item)
    db.flush()
    _audit(
        db,
        user=user,
        company_id=profile.company_id,
        action="create",
        entity_type="authorized_firm_document",
        entity_id=item.id,
        description="Yetkili firma belge kaydı oluşturuldu.",
        new_value=data,
    )
    save_score_snapshot(db, profile, user=user)
    db.commit()
    return build_profile_detail(db, profile, viewer=user)


@router.patch("/{profile_id}/documents/{document_id}")
def update_authorized_firm_document(
    profile_id: int,
    document_id: int,
    payload: AuthorizedFirmDocumentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    profile = _get_profile(db, profile_id, user)
    item = _get_document(db, profile, document_id)
    data = payload.model_dump(exclude_unset=True)
    if "title" in data and not data["title"]:
        raise HTTPException(422, "Belge adı boş olamaz.")
    if "document_type" in data and not data["document_type"]:
        raise HTTPException(422, "Belge türü boş olamaz.")
    _validate_linked_document(db, profile.company_id, data.get("document_record_id"))
    merged = _merge_dates(item, data, ("start_date", "expiry_date", "review_date", "renewal_date"))
    try:
        validate_document_dates(merged)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    old = {key: getattr(item, key) for key in data}
    for key, value in data.items():
        setattr(item, key, value)
    _audit(
        db,
        user=user,
        company_id=profile.company_id,
        action="update",
        entity_type="authorized_firm_document",
        entity_id=item.id,
        description="Yetkili firma belge kaydı güncellendi.",
        old_value=old,
        new_value=data,
    )
    save_score_snapshot(db, profile, user=user)
    db.commit()
    return build_profile_detail(db, profile, viewer=user)


@router.delete("/{profile_id}/documents/{document_id}")
def deactivate_authorized_firm_document(
    profile_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    profile = _get_profile(db, profile_id, user)
    item = _get_document(db, profile, document_id)
    item.is_active = False
    _audit(
        db,
        user=user,
        company_id=profile.company_id,
        action="deactivate",
        entity_type="authorized_firm_document",
        entity_id=item.id,
        description="Yetkili firma belge kaydı pasife alındı.",
    )
    save_score_snapshot(db, profile, user=user)
    db.commit()
    return {"ok": True, "id": item.id, "is_active": False}


@router.put("/{profile_id}/professionals/{professional_id}/compliance")
def upsert_professional_compliance(
    profile_id: int,
    professional_id: int,
    payload: ProfessionalComplianceUpsert,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    profile = _get_profile(db, profile_id, user)
    professional = db.get(IsgProfessional, professional_id)
    if not professional or professional.osgb_id != profile.osgb_id:
        raise HTTPException(404, "Profesyonel bu OSGB kapsamında bulunamadı.")
    assignment = db.scalar(
        select(WorkplaceAssignment.id).where(
            WorkplaceAssignment.osgb_id == profile.osgb_id,
            WorkplaceAssignment.company_id == profile.company_id,
            WorkplaceAssignment.professional_id == professional.id,
        )
    )
    if assignment is None:
        raise HTTPException(400, "Profesyonel bu işyerine görevlendirilmemiş.")
    data = payload.model_dump()
    validate_professional_dates(data)
    item = db.scalar(
        select(ProfessionalComplianceProfile).where(
            ProfessionalComplianceProfile.osgb_id == profile.osgb_id,
            ProfessionalComplianceProfile.professional_id == professional.id,
        )
    )
    old = None
    action = "create"
    if item:
        old = {key: getattr(item, key) for key in data}
        for key, value in data.items():
            setattr(item, key, value)
        item.updated_by_id = user.id
        action = "update"
    else:
        item = ProfessionalComplianceProfile(
            **data,
            osgb_id=profile.osgb_id,
            professional_id=professional.id,
            created_by_id=user.id,
            updated_by_id=user.id,
        )
        db.add(item)
    db.flush()
    _audit(
        db,
        user=user,
        company_id=profile.company_id,
        action=action,
        entity_type="professional_compliance",
        entity_id=professional.id,
        description="Profesyonel belge uygunluğu güncellendi.",
        old_value=old,
        new_value=data,
    )
    save_score_snapshot(db, profile, user=user)
    db.commit()
    return evaluate_professional_compliance(db, professional, company_id=profile.company_id)


@router.patch("/{profile_id}/onboarding")
def update_onboarding_progress(
    profile_id: int,
    payload: OnboardingProgressUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    profile = _get_profile(db, profile_id, user)
    old = {
        "current_step": profile.onboarding_current_step,
        "completed_steps": json.loads(profile.onboarding_completed_steps or "[]"),
        "status": profile.onboarding_status,
    }
    profile.onboarding_current_step = payload.current_step
    profile.onboarding_completed_steps = json.dumps(payload.completed_steps)
    profile.onboarding_status = payload.status
    profile.updated_by_id = user.id
    _audit(
        db,
        user=user,
        company_id=profile.company_id,
        action="update",
        entity_type="authorized_firm_profile",
        entity_id=profile.id,
        description="11 adımlı onboarding ilerlemesi güncellendi.",
        old_value=old,
        new_value=payload.model_dump(),
    )
    db.commit()
    return build_profile_detail(db, profile, viewer=user)


@router.post("/{profile_id}/score-snapshots")
def create_score_snapshot(
    profile_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    profile = _get_profile(db, profile_id, user)
    item = save_score_snapshot(db, profile, user=user)
    _audit(
        db,
        user=user,
        company_id=profile.company_id,
        action="snapshot",
        entity_type="authorized_firm_profile",
        entity_id=profile.id,
        description="Şeffaf uygunluk ve kalite skoru anlık görüntüsü kaydedildi.",
    )
    db.commit()
    return {
        "id": item.id,
        "overall_score": item.overall_score,
        "quality_score": item.quality_score,
        "status": item.status,
        "created_at": item.created_at,
    }


@router.get("/{profile_id}/export.pdf")
def export_authorized_firm_pdf(
    profile_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    detail = build_profile_detail(db, _get_profile(db, profile_id, user), viewer=user)
    return _file_response(
        build_authorized_firm_pdf(detail),
        media_type="application/pdf",
        filename=f"{safe_filename(detail.get('firm_name'))}-firma-dosyasi.pdf",
    )


@router.get("/{profile_id}/export.xlsx")
def export_authorized_firm_excel(
    profile_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    detail = build_profile_detail(db, _get_profile(db, profile_id, user), viewer=user)
    return _file_response(
        build_authorized_firm_excel(detail),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"{safe_filename(detail.get('firm_name'))}-firma-dosyasi.xlsx",
    )


@router.get("/{profile_id}/inspection-package.zip")
def export_inspection_package(
    profile_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    detail = build_profile_detail(db, _get_profile(db, profile_id, user), viewer=user)
    return _file_response(
        build_inspection_package(detail),
        media_type="application/zip",
        filename=f"{safe_filename(detail.get('firm_name'))}-denetim-hazirlik.zip",
    )


@router.get("/{profile_id}/inspection-day")
def inspection_day_mode(
    profile_id: int,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    response.headers["Cache-Control"] = "no-store"
    detail = build_profile_detail(db, _get_profile(db, profile_id, user), viewer=user)
    return {
        "mode": "inspection_day",
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "profile": {key: detail.get(key) for key in (
            "id", "company_id", "company_name", "firm_name", "province", "district",
            "authorized_representative", "hazard_class", "authorization_number",
            "authorization_start_date", "authorization_expiry_date", "record_notice",
        )},
        "compliance_score": detail.get("compliance_score"),
        "alerts": detail.get("alerts"),
        "automatic_task_checklist": detail.get("automatic_task_checklist"),
        "documents": detail.get("documents"),
        "professionals": detail.get("professionals"),
        "assignments": detail.get("assignments"),
        "contracts": detail.get("contracts"),
        "privacy": {"health_mode": "aggregate_only", "sensitive_fields_exposed": False},
    }
