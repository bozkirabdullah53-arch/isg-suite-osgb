"""Risk değerlendirme API — İSG PRO 2026 risk modülü entegrasyonu."""
from __future__ import annotations

import json
import uuid
from datetime import date
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

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
    RecordStatus,
    RiskAssessment,
    RiskDof,
    RiskMedia,
    User,
    UserRole,
    WorkplaceDepartment,
)
from app.schemas.risk import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
    HazardHintRequest,
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
    RiskUpdate,
)
from app.services.ai_hazard_hint import HINT_ENGINE, suggest_hazard_from_text
from app.services.hazard_seed import seed_hazard_library
from app.services.risk_photo_tags import (
    TAGS_ENGINE,
    catalog as photo_tag_catalog,
    parse_form_tags,
    parse_tags,
    serialize_selected,
)
from app.services.risk_reports import build_risk_excel, build_risk_pdf
from app.services.risk_scoring import evaluate, meta_payload
from app.services.risk_suggestions import get_suggestions
from app.services.upload_gateway import persist_relative

router = APIRouter(prefix="/risks", tags=["Risk Değerlendirme"])
EDIT_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN, UserRole.SAFETY_SPECIALIST)
ALLOWED_PHOTO = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
LEGACY_TAG = "[ISG#"


def ensure_access(db: Session, user: User, company_id: int) -> None:
    ensure_company_access(db, user, company_id)


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


def _media_response(m: RiskMedia) -> RiskMediaResponse:
    parsed = parse_tags(getattr(m, "tags_json", None))
    return RiskMediaResponse(
        id=m.id,
        risk_id=m.risk_id,
        original_name=m.original_name,
        content_type=m.content_type,
        created_at=m.created_at,
        tags=list(parsed["selected"]),
        tag_labels=list(parsed["labels"]),
    )


def _to_response(row: RiskAssessment, hazard: Hazard | None = None, category: HazardCategory | None = None) -> RiskResponse:
    return RiskResponse(
        id=row.id,
        risk_code=row.risk_code,
        company_id=row.company_id,
        branch_id=row.branch_id,
        department_id=getattr(row, "department_id", None),
        hazard_id=row.hazard_id,
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
        severity=row.severity,
        risk_score=row.risk_score,
        risk_level=row.risk_level,
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
    )


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


def _load_risk(db: Session, risk_id: int) -> RiskAssessment:
    row = db.scalar(
        select(RiskAssessment)
        .options(
            selectinload(RiskAssessment.dofs),
            selectinload(RiskAssessment.media_files),
        )
        .where(RiskAssessment.id == risk_id)
    )
    if not row:
        raise HTTPException(404, "Risk kaydı bulunamadı.")
    return row


@router.get("/meta")
def risk_meta(user: User = Depends(get_current_user)):
    return meta_payload()


@router.post("/calculate")
def risk_calculate(payload: RiskCalculateRequest, user: User = Depends(get_current_user)):
    return evaluate(payload.probability, payload.severity, term_override_days=payload.term_override_days)


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
        if r.risk_level in level_counts:
            level_counts[r.risk_level] += 1
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
    db.delete(row)
    db.commit()
    return {"ok": True, "id": risk_id}


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
        stmt = stmt.where(RiskAssessment.risk_level == level)
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
) -> tuple[Company, list[RiskAssessment], dict[int, Hazard]]:
    effective = effective_company_id(db, user, company_id)
    company = db.get(Company, effective)
    if not company:
        raise HTTPException(404, "Firma bulunamadı.")
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
        stmt = stmt.where(RiskAssessment.risk_level == level)
    if status:
        stmt = stmt.where(RiskAssessment.status == status)
    risks = list(db.scalars(stmt).unique().all())
    hids = {r.hazard_id for r in risks}
    hazard_map = {}
    if hids:
        hazard_map = {h.id: h for h in db.scalars(select(Hazard).where(Hazard.id.in_(hids))).all()}
    return company, risks, hazard_map


@router.get("/report.pdf")
def risk_report_pdf(
    company_id: int | None = None,
    level: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Firma risk değerlendirme PDF raporu."""
    company, risks, hazard_map = _load_company_risks(db, user, company_id, level, status)
    if not risks:
        raise HTTPException(422, "Bu filtreyle raporlanacak risk kaydı yok.")
    branch = db.scalar(select(Branch).where(Branch.company_id == company.id).order_by(Branch.id.asc()))
    pdf = build_risk_pdf(
        company=company,
        risks=risks,
        hazard_map=hazard_map,
        prepared_by=user.full_name,
        sgk_no=branch.sgk_registry_no if branch else None,
    )
    return StreamingResponse(
        BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="risk-raporu-{company.id}.pdf"'},
    )


@router.get("/report.xlsx")
def risk_report_excel(
    company_id: int | None = None,
    level: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Firma risk değerlendirme Excel raporu (risk + DÖF + istatistik)."""
    company, risks, hazard_map = _load_company_risks(db, user, company_id, level, status)
    if not risks:
        raise HTTPException(422, "Bu filtreyle raporlanacak risk kaydı yok.")
    xlsx = build_risk_excel(company=company, risks=risks, hazard_map=hazard_map)
    return StreamingResponse(
        BytesIO(xlsx),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="risk-raporu-{company.id}.xlsx"'},
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
            activity=(rec.title or "Eski risk kaydı")[:500],
            risk_definition=definition,
            affected_people=None,
            existing_measures=None,
            additional_measures=f"Kaynak: IsgRecord#{rec.id}"[:2000],
            probability=calc["probability"],
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
    if not db.get(Company, payload.company_id):
        raise HTTPException(404, "Firma bulunamadı.")
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
    calc = evaluate(payload.probability, payload.severity, term_override_days=payload.term_override_days)
    code = _next_code(db, "RSK", RiskAssessment, RiskAssessment.risk_code)
    # uniqueness retry
    while db.scalar(select(RiskAssessment).where(RiskAssessment.risk_code == code)):
        code = f"RSK-{int(code.split('-')[1]) + 1:04d}"
    row = RiskAssessment(
        risk_code=code,
        company_id=payload.company_id,
        branch_id=payload.branch_id,
        department_id=dep_id,
        hazard_id=payload.hazard_id,
        department_name=dep_name,
        activity=payload.activity,
        risk_definition=payload.risk_definition,
        affected_people=payload.affected_people,
        affected_group=payload.affected_group,
        existing_measures=payload.existing_measures,
        additional_measures=payload.additional_measures,
        probability=calc["probability"],
        severity=calc["severity"],
        risk_score=calc["risk_score"],
        risk_level=calc["risk_level"],
        term_days=calc["term_days"],
        term_date=date.fromisoformat(calc["term_date"]),
        term_suggested=calc["term_suggested"],
        term_overridden=calc["term_overridden"],
        status=payload.status or "Açık",
        created_by_id=user.id,
    )
    db.add(row)
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
    data = payload.model_dump(exclude_unset=True)
    term_override = data.pop("term_override_days", None)
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

    changed = has_dep_id or has_dep_name
    for key, val in data.items():
        if getattr(row, key, None) != val:
            changed = True
        setattr(row, key, val)

    if "hazard_id" in data:
        hazard = db.get(Hazard, row.hazard_id)
        if not hazard or not hazard.is_active:
            raise HTTPException(422, "Geçersiz tehlike seçimi.")

    if "probability" in data or "severity" in data or term_override is not None:
        calc = evaluate(
            row.probability,
            row.severity,
            term_override_days=term_override
            if term_override is not None
            else (row.term_days if row.term_overridden else None),
        )
        row.risk_score = calc["risk_score"]
        row.risk_level = calc["risk_level"]
        row.term_suggested = calc["term_suggested"]
        row.term_days = calc["term_days"]
        row.term_date = date.fromisoformat(calc["term_date"])
        row.term_overridden = calc["term_overridden"]
        changed = True

    if changed:
        row.revision_no = (row.revision_no or 0) + 1
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
    code = _next_code(db, "DÖF", RiskDof, RiskDof.dof_code)
    while db.scalar(select(RiskDof).where(RiskDof.dof_code == code)):
        n = int("".join(ch for ch in code if ch.isdigit()) or "0") + 1
        code = f"DÖF-{n:04d}"
    dof = RiskDof(
        dof_code=code,
        risk_id=row.id,
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
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = _load_risk(db, risk_id)
    ensure_access(db, user, row.company_id)
    name = file.filename or "photo.jpg"
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_PHOTO:
        raise HTTPException(422, "Sadece jpg/png/webp/gif yükleyin.")
    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"Dosya {settings.max_upload_mb} MB sınırını aşıyor.")
    rel = f"{row.company_id}/risk/{row.id}_{uuid.uuid4().hex[:10]}{ext}"
    if settings.upload_gateway_enabled:
        persist_relative(data, relative_path=rel, original_name=name)
    else:
        target = _upload_root() / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    media = RiskMedia(
        risk_id=row.id,
        storage_path=rel.replace("\\", "/"),
        original_name=name,
        content_type=file.content_type or "application/octet-stream",
        tags_json=serialize_selected(parse_form_tags(tags)),
        created_by_id=user.id,
    )
    db.add(media)
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
    path = (_upload_root() / media.storage_path).resolve()
    if _upload_root() not in path.parents or not path.exists():
        raise HTTPException(404, "Dosya bulunamadı.")
    return FileResponse(
        path,
        media_type=media.content_type or "application/octet-stream",
        filename=media.original_name or path.name,
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
            pass
        path.unlink(missing_ok=True)
    db.delete(media)
    db.commit()
    return {"ok": True, "id": media_id}
