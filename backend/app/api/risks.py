"""Risk değerlendirme API — İSG PRO 2026 risk modülü entegrasyonu."""
from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import (
    Branch,
    Company,
    Hazard,
    HazardCategory,
    RiskAssessment,
    RiskDof,
    User,
    UserRole,
    WorkplaceDepartment,
)
from app.schemas.risk import (
    DepartmentCreate,
    DepartmentResponse,
    HazardCategoryResponse,
    HazardResponse,
    RiskCalculateRequest,
    RiskCreate,
    RiskDofCreate,
    RiskDofResponse,
    RiskResponse,
    RiskUpdate,
)
from app.services.hazard_seed import seed_hazard_library
from app.services.risk_scoring import evaluate, meta_payload
from app.services.risk_suggestions import get_suggestions

router = APIRouter(prefix="/risks", tags=["Risk Değerlendirme"])
EDIT_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN, UserRole.SAFETY_SPECIALIST)


def ensure_access(user: User, company_id: int):
    if user.role != UserRole.GLOBAL_ADMIN and user.company_id != company_id:
        raise HTTPException(403, "Bu firmanın risk kayıtlarına erişemezsiniz.")


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
        .options(selectinload(RiskAssessment.dofs))
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
    effective = company_id if user.role == UserRole.GLOBAL_ADMIN else user.company_id
    if not effective:
        raise HTTPException(400, "Firma seçilmelidir.")
    ensure_access(user, effective)
    stmt = (
        select(WorkplaceDepartment)
        .where(WorkplaceDepartment.company_id == effective, WorkplaceDepartment.is_active.is_(True))
        .order_by(WorkplaceDepartment.name)
    )
    return list(db.scalars(stmt).all())


@router.post("/departments", response_model=DepartmentResponse)
def create_department(
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    ensure_access(user, payload.company_id)
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
    stmt = select(RiskAssessment).options(selectinload(RiskAssessment.dofs)).order_by(RiskAssessment.created_at.desc())
    effective = company_id if user.role == UserRole.GLOBAL_ADMIN else user.company_id
    if effective:
        stmt = stmt.where(RiskAssessment.company_id == effective)
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


@router.get("/{risk_id}", response_model=RiskResponse)
def get_risk(risk_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = _load_risk(db, risk_id)
    ensure_access(user, row.company_id)
    h = db.get(Hazard, row.hazard_id)
    c = db.get(HazardCategory, h.category_id) if h else None
    return _to_response(row, h, c)


@router.post("", response_model=RiskResponse)
def create_risk(
    payload: RiskCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    ensure_access(user, payload.company_id)
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
    ensure_access(user, row.company_id)
    data = payload.model_dump(exclude_unset=True)
    term_override = data.pop("term_override_days", None)
    for key, val in data.items():
        setattr(row, key, val)
    if "probability" in data or "severity" in data or term_override is not None:
        calc = evaluate(
            row.probability,
            row.severity,
            term_override_days=term_override if term_override is not None else (row.term_days if row.term_overridden else None),
        )
        row.risk_score = calc["risk_score"]
        row.risk_level = calc["risk_level"]
        row.term_suggested = calc["term_suggested"]
        row.term_days = calc["term_days"]
        row.term_date = date.fromisoformat(calc["term_date"])
        row.term_overridden = calc["term_overridden"]
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
    ensure_access(user, row.company_id)
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


@router.post("/{risk_id}/dofs/{dof_id}/complete", response_model=RiskDofResponse)
def complete_dof(
    risk_id: int,
    dof_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = _load_risk(db, risk_id)
    ensure_access(user, row.company_id)
    dof = db.get(RiskDof, dof_id)
    if not dof or dof.risk_id != risk_id:
        raise HTTPException(404, "DÖF bulunamadı.")
    dof.is_completed = True
    dof.status = "Tamamlandı"
    dof.completion_date = date.today()
    db.commit()
    db.refresh(dof)
    return dof
