"""0.9.135 — Yıllık plan değerlendirme API (AnnualPlanItem alanlarını değiştirmez)."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.company_access import company_ids_for_query, ensure_company_access
from app.api.deps import get_current_user, require_roles
from app.core.config import settings
from app.core.database import get_db
from app.models.entities import (
    AnnualPlanEvalCapa,
    AnnualPlanEvalEvidence,
    AnnualPlanEvaluation,
    AnnualPlanEvaluationItem,
    AnnualPlanItem,
    AnnualPlanUnplannedActivity,
    Company,
    Employee,
    User,
    UserRole,
)
from app.schemas.annual_eval import (
    LOCKED_REPORT,
    AnnualEvalItemUpdate,
    AnnualEvalStart,
    CapaCreate,
    EvalItemResponse,
    EvalOverviewResponse,
    PlanItemSnapshot,
    UnplannedCreate,
)
from app.services.annual_eval_logic import (
    build_kpis,
    compute_delay_days,
    meta_payload,
    validate_outcome_fields,
)
from app.services.annual_eval_reports import build_eval_pdf, build_eval_xlsx
from app.services.audit import add_audit_log

router = APIRouter(prefix="/annual-evals", tags=["Yıllık Plan Değerlendirme"])
EDIT_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST)
VIEW_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST, UserRole.WORKPLACE_PHYSICIAN)
ALLOWED = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}


def _upload_root() -> Path:
    root = Path(settings.upload_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _plan_items(db: Session, company_id: int, year: int) -> list[AnnualPlanItem]:
    return list(
        db.scalars(
            select(AnnualPlanItem)
            .where(
                AnnualPlanItem.company_id == company_id,
                AnnualPlanItem.year == year,
                AnnualPlanItem.deleted_at.is_(None),
            )
            .order_by(AnnualPlanItem.month, AnnualPlanItem.id)
        ).all()
    )


def _get_eval(db: Session, company_id: int, year: int) -> AnnualPlanEvaluation | None:
    return db.scalar(
        select(AnnualPlanEvaluation).where(
            AnnualPlanEvaluation.company_id == company_id,
            AnnualPlanEvaluation.year == year,
            AnnualPlanEvaluation.is_active.is_(True),
        )
    )


def _assert_editable(ev: AnnualPlanEvaluation) -> None:
    if ev.report_status in LOCKED_REPORT:
        raise HTTPException(409, "Onaylı/arşiv rapor üzerinde değişiklik yapılamaz. Revizyon süreci gerekir.")


def _to_item_resp(row: AnnualPlanEvaluationItem, plan: AnnualPlanItem, evidence_count: int = 0) -> EvalItemResponse:
    return EvalItemResponse(
        id=row.id,
        evaluation_id=row.evaluation_id,
        plan_item_id=row.plan_item_id,
        company_id=row.company_id,
        year=row.year,
        outcome_status=row.outcome_status,
        actual_start=row.actual_start,
        actual_end=row.actual_end,
        completion_pct=row.completion_pct,
        result_text=row.result_text,
        deviation_reason=row.deviation_reason,
        delay_days=row.delay_days,
        specialist_note=row.specialist_note,
        physician_note=row.physician_note,
        employer_note=row.employer_note,
        next_year_suggestion=row.next_year_suggestion,
        target_met=row.target_met,
        capa_needed=bool(row.capa_needed),
        evidence_count=evidence_count,
        plan=PlanItemSnapshot(
            id=plan.id,
            activity=plan.activity,
            category=plan.category,
            month=plan.month,
            target_date=plan.target_date,
            responsible_name=plan.responsible_name,
            description=plan.description,
            plan_status=plan.status.value if hasattr(plan.status, "value") else str(plan.status),
        ),
    )


def _sync_items(db: Session, ev: AnnualPlanEvaluation, plans: list[AnnualPlanItem]) -> None:
    existing = {
        r.plan_item_id: r
        for r in db.scalars(
            select(AnnualPlanEvaluationItem).where(
                AnnualPlanEvaluationItem.evaluation_id == ev.id,
                AnnualPlanEvaluationItem.is_active.is_(True),
            )
        ).all()
    }
    for p in plans:
        if p.id in existing:
            continue
        db.add(
            AnnualPlanEvaluationItem(
                evaluation_id=ev.id,
                plan_item_id=p.id,
                company_id=ev.company_id,
                year=ev.year,
                outcome_status="planlandi",
            )
        )
    db.commit()


@router.get("/meta")
def meta(user: User = Depends(get_current_user)):
    return meta_payload()


@router.post("/start", response_model=EvalOverviewResponse)
def start_eval(
    payload: AnnualEvalStart,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    ensure_company_access(db, user, payload.company_id)
    plans = _plan_items(db, payload.company_id, payload.year)
    ev = _get_eval(db, payload.company_id, payload.year)
    if not ev:
        ev = AnnualPlanEvaluation(
            company_id=payload.company_id,
            year=payload.year,
            report_status="hazirlaniyor" if plans else "hazirlanmadi",
            specialist_name=user.full_name,
            plan_item_count_at_start=len(plans),
            created_by_id=user.id,
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)
        add_audit_log(
            db,
            user=user,
            action="annual_eval_start",
            module="annual_eval",
            entity_type="annual_plan_evaluation",
            entity_id=str(ev.id),
            description=f"Değerlendirme başlatıldı {payload.year}",
        )
        db.commit()
    _sync_items(db, ev, plans)
    return _overview(db, payload.company_id, payload.year, user)


@router.get("/overview", response_model=EvalOverviewResponse)
def overview(
    company_id: int,
    year: int = Query(..., ge=2020, le=2100),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    ensure_company_access(db, user, company_id)
    return _overview(db, company_id, year, user)


def _overview(db: Session, company_id: int, year: int, user: User) -> EvalOverviewResponse:
    company = db.get(Company, company_id)
    plans = _plan_items(db, company_id, year)
    ev = _get_eval(db, company_id, year)
    emp_count = db.scalar(
        select(func.count()).select_from(Employee).where(
            Employee.company_id == company_id, Employee.is_active.is_(True)
        )
    ) or 0
    item_dicts: list[dict] = []
    unplanned_n = 0
    warnings: list[str] = []
    if not plans:
        warnings.append("Seçilen yıl için onaylı/aktif yıllık çalışma planı kalemi bulunamadı.")
    if ev:
        rows = list(
            db.scalars(
                select(AnnualPlanEvaluationItem)
                .where(
                    AnnualPlanEvaluationItem.evaluation_id == ev.id,
                    AnnualPlanEvaluationItem.is_active.is_(True),
                )
                .options(selectinload(AnnualPlanEvaluationItem.evidences))
            ).all()
        )
        plan_map = {p.id: p for p in plans}
        for r in rows:
            plan = plan_map.get(r.plan_item_id) or db.get(AnnualPlanItem, r.plan_item_id)
            if not plan:
                continue
            evc = sum(1 for e in (r.evidences or []) if e.is_active)
            item_dicts.append(
                {
                    "outcome_status": r.outcome_status,
                    "completion_pct": r.completion_pct,
                    "evidence_count": evc,
                    "delay_days": r.delay_days,
                }
            )
            if evc < 1 and r.outcome_status not in ("planlandi", "iptal", "plan_revizyonuyla_kaldirildi"):
                warnings.append(f"Kanıt belgesi eklenmedi: {plan.activity[:60]}")
        unplanned_n = db.scalar(
            select(func.count()).select_from(AnnualPlanUnplannedActivity).where(
                AnnualPlanUnplannedActivity.evaluation_id == ev.id,
                AnnualPlanUnplannedActivity.is_active.is_(True),
            )
        ) or 0
        if ev.plan_item_count_at_start and len(plans) != ev.plan_item_count_at_start:
            warnings.append(
                "Kontrol edilmesi önerilir: Plan kalem sayısı değerlendirme başlangıcından farklı "
                f"({ev.plan_item_count_at_start} → {len(plans)})."
            )
    kpis = build_kpis(item_dicts, unplanned_n)
    return EvalOverviewResponse(
        evaluation_id=ev.id if ev else None,
        company_id=company_id,
        year=year,
        report_status=ev.report_status if ev else "hazirlanmadi",
        company_name=company.name if company else None,
        sgk_registry_no=company.sgk_registry_no if company else None,
        address=company.address if company else None,
        hazard_class=company.hazard_class if company else None,
        employee_count=int(emp_count),
        plan_item_count=len(plans),
        plan_item_count_at_start=ev.plan_item_count_at_start if ev else 0,
        plan_count_warning=warnings[0] if warnings and "kalem sayısı" in warnings[0] else None,
        kpis=kpis,
        warnings=warnings[:12],
    )


@router.get("/items", response_model=list[EvalItemResponse])
def list_items(
    company_id: int,
    year: int = Query(..., ge=2020, le=2100),
    outcome: str | None = None,
    q: str | None = None,
    category: str | None = None,
    missing_evidence: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    ensure_company_access(db, user, company_id)
    ev = _get_eval(db, company_id, year)
    if not ev:
        return []
    plans = {p.id: p for p in _plan_items(db, company_id, year)}
    rows = list(
        db.scalars(
            select(AnnualPlanEvaluationItem)
            .where(
                AnnualPlanEvaluationItem.evaluation_id == ev.id,
                AnnualPlanEvaluationItem.is_active.is_(True),
            )
            .options(selectinload(AnnualPlanEvaluationItem.evidences))
            .order_by(AnnualPlanEvaluationItem.id)
        ).all()
    )
    out: list[EvalItemResponse] = []
    for r in rows:
        plan = plans.get(r.plan_item_id) or db.get(AnnualPlanItem, r.plan_item_id)
        if not plan or plan.deleted_at:
            continue
        if outcome and r.outcome_status != outcome:
            continue
        if category and (plan.category or "") != category:
            continue
        if q:
            qq = q.strip().casefold()
            blob = f"{plan.activity} {plan.responsible_name or ''} {r.result_text or ''}".casefold()
            if qq not in blob:
                continue
        evc = sum(1 for e in (r.evidences or []) if e.is_active)
        if missing_evidence and evc > 0:
            continue
        out.append(_to_item_resp(r, plan, evc))
    return out


@router.put("/items/{item_id}", response_model=EvalItemResponse)
def update_item(
    item_id: int,
    payload: AnnualEvalItemUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = db.get(AnnualPlanEvaluationItem, item_id)
    if not row or not row.is_active:
        raise HTTPException(404, "Değerlendirme kalemi bulunamadı.")
    ensure_company_access(db, user, row.company_id)
    ev = db.get(AnnualPlanEvaluation, row.evaluation_id)
    if not ev:
        raise HTTPException(404, "Değerlendirme bulunamadı.")
    _assert_editable(ev)
    data = payload.model_dump(exclude_unset=True)
    outcome = data.get("outcome_status", row.outcome_status)
    merged = {
        "actual_end": data.get("actual_end", row.actual_end),
        "result_text": data.get("result_text", row.result_text),
        "completion_pct": data.get("completion_pct", row.completion_pct),
        "deviation_reason": data.get("deviation_reason", row.deviation_reason),
        "next_year_suggestion": data.get("next_year_suggestion", row.next_year_suggestion),
    }
    try:
        validate_outcome_fields(outcome, merged)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    for k, v in data.items():
        setattr(row, k, v)
    plan = db.get(AnnualPlanItem, row.plan_item_id)
    row.delay_days = compute_delay_days(plan.target_date if plan else None, row.actual_end)
    row.updated_at = datetime.utcnow()
    add_audit_log(
        db,
        user=user,
        action="annual_eval_item_update",
        module="annual_eval",
        entity_type="annual_plan_evaluation_item",
        entity_id=str(row.id),
        description=f"Durum: {row.outcome_status}",
    )
    db.commit()
    db.refresh(row)
    evc = db.scalar(
        select(func.count()).select_from(AnnualPlanEvalEvidence).where(
            AnnualPlanEvalEvidence.evaluation_item_id == row.id,
            AnnualPlanEvalEvidence.is_active.is_(True),
        )
    ) or 0
    if not plan:
        raise HTTPException(404, "Plan kalemi bulunamadı.")
    return _to_item_resp(row, plan, int(evc))


@router.post("/items/{item_id}/evidences")
async def upload_evidence(
    item_id: int,
    file: UploadFile = File(...),
    doc_type: str | None = None,
    title: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = db.get(AnnualPlanEvaluationItem, item_id)
    if not row or not row.is_active:
        raise HTTPException(404, "Değerlendirme kalemi bulunamadı.")
    ensure_company_access(db, user, row.company_id)
    ev = db.get(AnnualPlanEvaluation, row.evaluation_id)
    if ev:
        _assert_editable(ev)
    name = file.filename or "evidence.bin"
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(422, "Sadece pdf/jpg/png/webp yükleyin.")
    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"Dosya {settings.max_upload_mb} MB sınırını aşıyor.")
    rel = f"{row.company_id}/annual-eval/{row.id}_{uuid.uuid4().hex[:10]}{ext}"
    target = _upload_root() / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    evd = AnnualPlanEvalEvidence(
        evaluation_item_id=row.id,
        doc_type=doc_type,
        title=title or name,
        storage_path=rel.replace("\\", "/"),
        original_name=name,
        content_type=file.content_type,
        uploaded_by_id=user.id,
    )
    db.add(evd)
    db.commit()
    db.refresh(evd)
    return {"id": evd.id, "title": evd.title, "storage_path": evd.storage_path}


@router.get("/items/{item_id}/evidences")
def list_evidences(
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    row = db.get(AnnualPlanEvaluationItem, item_id)
    if not row:
        raise HTTPException(404, "Kayıt bulunamadı.")
    ensure_company_access(db, user, row.company_id)
    rows = list(
        db.scalars(
            select(AnnualPlanEvalEvidence).where(
                AnnualPlanEvalEvidence.evaluation_item_id == item_id,
                AnnualPlanEvalEvidence.is_active.is_(True),
            )
        ).all()
    )
    return [
        {
            "id": e.id,
            "doc_type": e.doc_type,
            "title": e.title,
            "doc_date": e.doc_date,
            "original_name": e.original_name,
            "created_at": e.created_at,
        }
        for e in rows
    ]


@router.post("/{evaluation_id}/unplanned")
def add_unplanned(
    evaluation_id: int,
    payload: UnplannedCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    ev = db.get(AnnualPlanEvaluation, evaluation_id)
    if not ev or not ev.is_active:
        raise HTTPException(404, "Değerlendirme bulunamadı.")
    ensure_company_access(db, user, ev.company_id)
    _assert_editable(ev)
    row = AnnualPlanUnplannedActivity(
        evaluation_id=ev.id,
        company_id=ev.company_id,
        year=ev.year,
        created_by_id=user.id,
        **payload.model_dump(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "activity": row.activity}


@router.get("/{evaluation_id}/unplanned")
def list_unplanned(
    evaluation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    ev = db.get(AnnualPlanEvaluation, evaluation_id)
    if not ev:
        raise HTTPException(404, "Değerlendirme bulunamadı.")
    ensure_company_access(db, user, ev.company_id)
    rows = list(
        db.scalars(
            select(AnnualPlanUnplannedActivity).where(
                AnnualPlanUnplannedActivity.evaluation_id == evaluation_id,
                AnnualPlanUnplannedActivity.is_active.is_(True),
            )
        ).all()
    )
    return [
        {
            "id": r.id,
            "activity": r.activity,
            "category": r.category,
            "done_date": r.done_date,
            "reason": r.reason,
            "result_text": r.result_text,
            "responsible_name": r.responsible_name,
            "suggest_next_year": r.suggest_next_year,
        }
        for r in rows
    ]


@router.post("/{evaluation_id}/capas")
def add_capa(
    evaluation_id: int,
    payload: CapaCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    ev = db.get(AnnualPlanEvaluation, evaluation_id)
    if not ev or not ev.is_active:
        raise HTTPException(404, "Değerlendirme bulunamadı.")
    ensure_company_access(db, user, ev.company_id)
    _assert_editable(ev)
    row = AnnualPlanEvalCapa(
        evaluation_id=ev.id,
        created_by_id=user.id,
        **payload.model_dump(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "title": row.title, "status": row.status}


@router.post("/{evaluation_id}/workflow/{action}")
def workflow(
    evaluation_id: int,
    action: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    ev = db.get(AnnualPlanEvaluation, evaluation_id)
    if not ev or not ev.is_active:
        raise HTTPException(404, "Değerlendirme bulunamadı.")
    ensure_company_access(db, user, ev.company_id)
    mapping = {
        "submit-specialist": "hekim_bekliyor",
        "approve-physician": "isveren_bekliyor",
        "approve-employer": "onaylandi",
        "request-revision": "revizyon",
        "archive": "arsiv",
    }
    if action not in mapping:
        raise HTTPException(400, "Geçersiz iş akışı adımı.")
    if ev.report_status in LOCKED_REPORT and action != "archive":
        raise HTTPException(409, "Kilitli rapor.")
    ev.report_status = mapping[action]
    if action == "approve-employer":
        ev.report_date = date.today()
    ev.updated_at = datetime.utcnow()
    add_audit_log(
        db,
        user=user,
        action=f"annual_eval_{action}",
        module="annual_eval",
        entity_type="annual_plan_evaluation",
        entity_id=str(ev.id),
        description=ev.report_status,
    )
    db.commit()
    return {"id": ev.id, "report_status": ev.report_status}


@router.get("/export.xlsx")
def export_xlsx(
    company_id: int,
    year: int = Query(..., ge=2020, le=2100),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    ensure_company_access(db, user, company_id)
    company = db.get(Company, company_id)
    ov = _overview(db, company_id, year, user)
    items = [i.model_dump() for i in list_items(company_id=company_id, year=year, db=db, user=user)]
    ev = _get_eval(db, company_id, year)
    unplanned: list[dict] = []
    if ev:
        unplanned = list_unplanned(evaluation_id=ev.id, db=db, user=user)
    data = build_eval_xlsx(
        company_name=company.name if company else str(company_id),
        year=year,
        items=items,
        unplanned=unplanned,
        kpis=ov.kpis,
    )
    return StreamingResponse(
        BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="yillik-degerlendirme-{year}.xlsx"'},
    )


@router.get("/export.pdf")
def export_pdf(
    company_id: int,
    year: int = Query(..., ge=2020, le=2100),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    ensure_company_access(db, user, company_id)
    company = db.get(Company, company_id)
    ov = _overview(db, company_id, year, user)
    items = [i.model_dump() for i in list_items(company_id=company_id, year=year, db=db, user=user)]
    data = build_eval_pdf(
        company_name=company.name if company else str(company_id),
        year=year,
        kpis=ov.kpis,
        items=items,
    )
    return StreamingResponse(
        BytesIO(data),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="yillik-degerlendirme-{year}.pdf"'},
    )


@router.get("/next-year-suggestions")
def next_year_suggestions(
    company_id: int,
    year: int = Query(..., ge=2020, le=2100),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    ensure_company_access(db, user, company_id)
    items = list_items(company_id=company_id, year=year, db=db, user=user)
    suggestions = []
    for it in items:
        if it.outcome_status in ("gerceklesmedi", "ertelendi", "kismi") or it.capa_needed:
            suggestions.append(
                {
                    "plan_item_id": it.plan_item_id,
                    "activity": it.plan.activity,
                    "reason": it.outcome_status,
                    "suggestion": it.next_year_suggestion,
                }
            )
    ev = _get_eval(db, company_id, year)
    if ev:
        for u in list_unplanned(evaluation_id=ev.id, db=db, user=user):
            if u.get("suggest_next_year"):
                suggestions.append(
                    {
                        "plan_item_id": None,
                        "activity": u["activity"],
                        "reason": "plan_disi",
                        "suggestion": "Sonraki yıl planına eklenmesi önerilir.",
                    }
                )
    return {"year": year + 1, "from_year": year, "items": suggestions, "note": "Otomatik ekleme yok; kontrollü aktarım kullanıcı onayıyla yapılır."}
