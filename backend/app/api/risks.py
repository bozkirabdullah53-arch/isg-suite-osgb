"""Risk değerlendirme API — İSG PRO 2026 risk modülü entegrasyonu."""
from __future__ import annotations

import json
import uuid
from datetime import date
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

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
    HazardCategoryResponse,
    HazardResponse,
    RiskCalculateRequest,
    RiskCreate,
    RiskDofComplete,
    RiskDofCreate,
    RiskDofResponse,
    RiskDofUpdate,
    RiskMediaResponse,
    RiskResponse,
    RiskUpdate,
)
from app.services.hazard_seed import seed_hazard_library
from app.services.risk_reports import build_risk_excel, build_risk_pdf
from app.services.risk_scoring import evaluate, meta_payload
from app.services.risk_suggestions import get_suggestions

router = APIRouter(prefix="/risks", tags=["Risk Değerlendirme"])
EDIT_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN, UserRole.SAFETY_SPECIALIST)
ALLOWED_PHOTO = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
LEGACY_TAG = "[ISG#"


def ensure_access(user: User, company_id: int):
    if user.role != UserRole.GLOBAL_ADMIN and user.company_id != company_id:
        raise HTTPException(403, "Bu firmanın risk kayıtlarına erişemezsiniz.")


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
        media=[RiskMediaResponse.model_validate(m) for m in (row.media_files or [])],
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
    stmt = (
        select(RiskAssessment)
        .options(
            selectinload(RiskAssessment.dofs),
            selectinload(RiskAssessment.media_files),
        )
        .order_by(RiskAssessment.created_at.desc())
    )
    if user.role == UserRole.GLOBAL_ADMIN:
        effective = company_id
        if not effective:
            raise HTTPException(422, "Global yönetici için company_id zorunludur.")
    else:
        if not user.company_id:
            raise HTTPException(403, "Firma atanmamış kullanıcı risk listesini göremez.")
        effective = user.company_id
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


def _load_company_risks(
    db: Session,
    user: User,
    company_id: int | None,
    level: str | None = None,
    status: str | None = None,
) -> tuple[Company, list[RiskAssessment], dict[int, Hazard]]:
    effective = company_id if user.role == UserRole.GLOBAL_ADMIN else user.company_id
    if not effective:
        raise HTTPException(422, "Firma seçiniz.")
    ensure_access(user, effective)
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
    effective = company_id if user.role == UserRole.GLOBAL_ADMIN else user.company_id
    if not effective:
        raise HTTPException(422, "Firma seçiniz.")
    ensure_access(user, effective)
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


@router.patch("/{risk_id}/dofs/{dof_id}", response_model=RiskDofResponse)
def update_dof(
    risk_id: int,
    dof_id: int,
    payload: RiskDofUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = _load_risk(db, risk_id)
    ensure_access(user, row.company_id)
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
    ensure_access(user, row.company_id)
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
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = _load_risk(db, risk_id)
    ensure_access(user, row.company_id)
    name = file.filename or "photo.jpg"
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_PHOTO:
        raise HTTPException(422, "Sadece jpg/png/webp/gif yükleyin.")
    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"Dosya {settings.max_upload_mb} MB sınırını aşıyor.")
    rel = f"{row.company_id}/risk/{row.id}_{uuid.uuid4().hex[:10]}{ext}"
    target = _upload_root() / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    media = RiskMedia(
        risk_id=row.id,
        storage_path=rel.replace("\\", "/"),
        original_name=name,
        content_type=file.content_type or "application/octet-stream",
        created_by_id=user.id,
    )
    db.add(media)
    db.commit()
    db.refresh(media)
    return RiskMediaResponse.model_validate(media)


@router.get("/{risk_id}/media/{media_id}")
def get_risk_media(
    risk_id: int,
    media_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = _load_risk(db, risk_id)
    ensure_access(user, row.company_id)
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
    ensure_access(user, row.company_id)
    media = next((m for m in (row.media_files or []) if m.id == media_id), None)
    if not media:
        raise HTTPException(404, "Medya bulunamadı.")
    path = (_upload_root() / media.storage_path).resolve()
    if _upload_root() in path.parents and path.exists():
        path.unlink(missing_ok=True)
    db.delete(media)
    db.commit()
    return {"ok": True, "id": media_id}
