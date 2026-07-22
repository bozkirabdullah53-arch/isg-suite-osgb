"""0.9.141 — Yıllık plan değerlendirme API (AnnualPlanItem alanlarını değiştirmez)."""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.company_access import ensure_company_access
from app.api.deps import get_current_user, require_roles
from app.core.config import settings
from app.core.database import get_db
from app.models.entities import (
    AnnualPlanEvalCapa,
    AnnualPlanEvalEvidence,
    AnnualPlanEvalRevision,
    AnnualPlanEvaluation,
    AnnualPlanEvaluationItem,
    AnnualPlanItem,
    AnnualPlanStatus,
    AnnualPlanUnplannedActivity,
    Company,
    DrillRecord,
    Employee,
    HealthRecord,
    IncidentEvent,
    RiskAssessment,
    TrainingSession,
    TrainingStatus,
    User,
    UserRole,
)
from app.schemas.annual_eval import (
    LOCKED_REPORT,
    AnnualEvalItemUpdate,
    AnnualEvalStart,
    BulkEvalAction,
    CapaCreate,
    EvalItemResponse,
    EvalOverviewResponse,
    EvidenceLinkCreate,
    PlanItemSnapshot,
    TransferNextYear,
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
from app.services.mailer import send_email, smtp_configured

router = APIRouter(prefix="/annual-evals", tags=["Yıllık Plan Değerlendirme"])
EDIT_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST)
VIEW_ROLES = (
    UserRole.GLOBAL_ADMIN,
    UserRole.SAFETY_SPECIALIST,
    UserRole.WORKPLACE_PHYSICIAN,
    UserRole.READ_ONLY,
)
ITEM_WRITE_ROLES = (*EDIT_ROLES, UserRole.WORKPLACE_PHYSICIAN)
WORKFLOW_ROLES = (*EDIT_ROLES, UserRole.WORKPLACE_PHYSICIAN, UserRole.READ_ONLY)
ALLOWED = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
LINKABLE_MODULES = frozenset({"training", "drill", "incident", "risk", "visit", "health_summary"})
_SNAPSHOT_FIELDS = (
    "id",
    "plan_item_id",
    "outcome_status",
    "actual_start",
    "actual_end",
    "completion_pct",
    "result_text",
    "deviation_reason",
    "delay_days",
    "specialist_note",
    "physician_note",
    "employer_note",
    "next_year_suggestion",
    "target_met",
    "capa_needed",
)


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


def _ensure_verify_code(ev: AnnualPlanEvaluation) -> str:
    if ev.verify_code:
        return ev.verify_code
    ev.verify_code = f"YPD-{ev.year}-{uuid.uuid4().hex[:10].upper()}"
    return ev.verify_code


def _item_snapshot(row: AnnualPlanEvaluationItem) -> dict:
    out: dict = {}
    for f in _SNAPSHOT_FIELDS:
        val = getattr(row, f)
        if isinstance(val, date):
            val = val.isoformat()
        out[f] = val
    return out


def _diff_snapshots(prev: list[dict], curr: list[dict]) -> list[dict]:
    by_id = {str(p.get("plan_item_id")): p for p in prev}
    changes: list[dict] = []
    for c in curr:
        key = str(c.get("plan_item_id"))
        old = by_id.get(key)
        if not old:
            changes.append({"plan_item_id": c.get("plan_item_id"), "kind": "added", "fields": {}})
            continue
        fields = {}
        for f in _SNAPSHOT_FIELDS:
            if f in ("id", "plan_item_id"):
                continue
            if old.get(f) != c.get(f):
                fields[f] = {"from": old.get(f), "to": c.get(f)}
        if fields:
            changes.append({"plan_item_id": c.get("plan_item_id"), "kind": "changed", "fields": fields})
    return changes


def _create_revision_snapshot(
    db: Session, ev: AnnualPlanEvaluation, user: User, reason: str | None = None
) -> AnnualPlanEvalRevision:
    items = list(
        db.scalars(
            select(AnnualPlanEvaluationItem).where(
                AnnualPlanEvaluationItem.evaluation_id == ev.id,
                AnnualPlanEvaluationItem.is_active.is_(True),
            )
        ).all()
    )
    curr = [_item_snapshot(i) for i in items]
    last = db.scalar(
        select(AnnualPlanEvalRevision)
        .where(AnnualPlanEvalRevision.evaluation_id == ev.id)
        .order_by(AnnualPlanEvalRevision.revision_no.desc())
        .limit(1)
    )
    prev = json.loads(last.snapshot_json) if last and last.snapshot_json else []
    changes = _diff_snapshots(prev, curr) if last else []
    rev_no = (last.revision_no + 1) if last else 1
    row = AnnualPlanEvalRevision(
        evaluation_id=ev.id,
        revision_no=rev_no,
        reason=reason or f"Revizyon {rev_no}",
        snapshot_json=json.dumps(curr, ensure_ascii=False),
        changes_json=json.dumps(changes, ensure_ascii=False),
        created_by_id=user.id,
    )
    db.add(row)
    return row


def _email_company_roles(db: Session, company_id: int, roles: tuple[UserRole, ...], subject: str, body: str) -> list[dict]:
    if not smtp_configured():
        return [{"ok": False, "status": "smtp_not_configured"}]
    users = list(
        db.scalars(
            select(User).where(
                User.company_id == company_id,
                User.is_active.is_(True),
                User.role.in_(roles),
            )
        ).all()
    )
    return [send_email(to=u.email, subject=subject, body=body) for u in users if u.email]


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
            verify_code=f"YPD-{payload.year}-{uuid.uuid4().hex[:10].upper()}",
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
    else:
        if not ev.verify_code:
            _ensure_verify_code(ev)
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
        verify_code=ev.verify_code if ev else None,
        report_date=ev.report_date if ev else None,
        specialist_name=ev.specialist_name if ev else None,
        physician_name=ev.physician_name if ev else None,
        employer_name=ev.employer_name if ev else None,
    )


@router.get("/items", response_model=list[EvalItemResponse])
def list_items(
    company_id: int,
    year: int = Query(..., ge=2020, le=2100),
    outcome: str | None = None,
    q: str | None = None,
    category: str | None = None,
    month: int | None = Query(None, ge=1, le=12),
    month_from: int | None = Query(None, ge=1, le=12),
    month_to: int | None = Query(None, ge=1, le=12),
    missing_evidence: bool = False,
    overdue: bool = False,
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
    today = date.today()
    out: list[EvalItemResponse] = []
    for r in rows:
        plan = plans.get(r.plan_item_id) or db.get(AnnualPlanItem, r.plan_item_id)
        if not plan or plan.deleted_at:
            continue
        if outcome and r.outcome_status != outcome:
            continue
        if category and (plan.category or "") != category:
            continue
        if month is not None and plan.month != month:
            continue
        if month_from is not None and plan.month < month_from:
            continue
        if month_to is not None and plan.month > month_to:
            continue
        if q:
            qq = q.strip().casefold()
            blob = f"{plan.activity} {plan.responsible_name or ''} {r.result_text or ''}".casefold()
            if qq not in blob:
                continue
        evc = sum(1 for e in (r.evidences or []) if e.is_active)
        if missing_evidence and evc > 0:
            continue
        if overdue:
            if not plan.target_date or plan.target_date >= today:
                continue
            if r.outcome_status not in ("planlandi", "devam", "ertelendi", "kismi"):
                continue
        out.append(_to_item_resp(r, plan, evc))
    return out


@router.get("/analytics")
def analytics(
    company_id: int,
    year: int = Query(..., ge=2020, le=2100),
    period: str = Query("month"),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    ensure_company_access(db, user, company_id)
    items = list_items(company_id=company_id, year=year, db=db, user=user)
    month_names = [
        "", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
        "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
    ]

    def _done(st: str) -> bool:
        return st in ("tamam", "gecikmeli_tamam")

    buckets: list[dict] = []
    if period == "quarter":
        ranges = [(1, 3, "Q1"), (4, 6, "Q2"), (7, 9, "Q3"), (10, 12, "Q4")]
    elif period == "half":
        ranges = [(1, 6, "1. Yarı"), (7, 12, "2. Yarı")]
    elif period == "year":
        ranges = [(1, 12, str(year))]
    else:
        ranges = [(m, m, month_names[m]) for m in range(1, 13)]

    for a, b, label in ranges:
        subset = [it for it in items if a <= (it.plan.month or 0) <= b]
        planned = len(subset)
        completed = sum(1 for it in subset if _done(it.outcome_status))
        buckets.append(
            {
                "key": f"{a}-{b}",
                "label": label,
                "month_from": a,
                "month_to": b,
                "planned": planned,
                "completed": completed,
                "rate": round(100.0 * completed / planned, 1) if planned else None,
            }
        )

    by_cat: dict[str, dict] = {}
    by_resp: dict[str, dict] = {}
    for it in items:
        cat = it.plan.category or "diger"
        resp = it.plan.responsible_name or "Belirtilmemiş"
        for bag, key in ((by_cat, cat), (by_resp, resp)):
            row = bag.setdefault(key, {"key": key, "planned": 0, "completed": 0})
            row["planned"] += 1
            if _done(it.outcome_status):
                row["completed"] += 1
    for bag in (by_cat, by_resp):
        for row in bag.values():
            row["rate"] = round(100.0 * row["completed"] / row["planned"], 1) if row["planned"] else None

    return {
        "year": year,
        "period": period,
        "buckets": buckets,
        "by_category": sorted(by_cat.values(), key=lambda x: -x["planned"]),
        "by_responsible": sorted(by_resp.values(), key=lambda x: -x["planned"]),
        "note": "Grafik/tablo tıklanınca ilgili ay aralığı filtrelenir. Plan dışı faaliyetler dahil değildir.",
    }


@router.post("/bulk")
def bulk_action(
    payload: BulkEvalAction,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    if payload.action not in ("note", "suggest_next", "mark_capa", "complete"):
        raise HTTPException(400, "Geçersiz toplu işlem.")
    rows = list(
        db.scalars(
            select(AnnualPlanEvaluationItem).where(
                AnnualPlanEvaluationItem.id.in_(payload.item_ids),
                AnnualPlanEvaluationItem.is_active.is_(True),
            )
        ).all()
    )
    if not rows:
        raise HTTPException(404, "Seçili değerlendirme kalemi bulunamadı.")
    company_ids = {r.company_id for r in rows}
    if len(company_ids) != 1:
        raise HTTPException(400, "Toplu işlem tek firma kapsamında olmalı.")
    company_id = next(iter(company_ids))
    ensure_company_access(db, user, company_id)
    eval_ids = {r.evaluation_id for r in rows}
    for eid in eval_ids:
        ev = db.get(AnnualPlanEvaluation, eid)
        if not ev:
            raise HTTPException(404, "Değerlendirme bulunamadı.")
        _assert_editable(ev)

    updated = 0
    skipped = []
    for row in rows:
        if payload.action == "note":
            if not (payload.specialist_note or "").strip():
                raise HTTPException(422, "Toplu not metni zorunlu.")
            note = payload.specialist_note.strip()
            row.specialist_note = ((row.specialist_note or "") + "\n" + note).strip()
            updated += 1
        elif payload.action == "suggest_next":
            sug = (payload.next_year_suggestion or "Bir sonraki yıl planına aktarılsın.").strip()
            row.next_year_suggestion = sug
            if row.outcome_status in ("planlandi", "devam"):
                # sadece öneri; durum değişmez
                pass
            updated += 1
        elif payload.action == "mark_capa":
            row.capa_needed = True
            updated += 1
        elif payload.action == "complete":
            if not payload.actual_end or not (payload.result_text or "").strip():
                raise HTTPException(422, "Toplu tamamlamada gerçekleşme tarihi ve sonuç zorunlu.")
            evc = db.scalar(
                select(func.count()).select_from(AnnualPlanEvalEvidence).where(
                    AnnualPlanEvalEvidence.evaluation_item_id == row.id,
                    AnnualPlanEvalEvidence.is_active.is_(True),
                )
            ) or 0
            if evc < 1:
                skipped.append({"id": row.id, "reason": "Kanıt belgesi yok"})
                continue
            plan = db.get(AnnualPlanItem, row.plan_item_id)
            row.outcome_status = "tamam"
            row.actual_end = payload.actual_end
            row.result_text = payload.result_text
            row.completion_pct = 100
            row.delay_days = compute_delay_days(plan.target_date if plan else None, row.actual_end)
            if row.delay_days and row.delay_days > 0:
                row.outcome_status = "gecikmeli_tamam"
            updated += 1
        row.updated_at = datetime.utcnow()

    add_audit_log(
        db,
        user=user,
        action=f"annual_eval_bulk_{payload.action}",
        module="annual_eval",
        entity_type="annual_plan_evaluation_item",
        entity_id=",".join(str(i) for i in payload.item_ids[:20]),
        description=f"updated={updated} skipped={len(skipped)}",
    )
    db.commit()
    return {"updated": updated, "skipped": skipped, "action": payload.action}


@router.put("/items/{item_id}", response_model=EvalItemResponse)
def update_item(
    item_id: int,
    payload: AnnualEvalItemUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ITEM_WRITE_ROLES)),
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
    if user.role == UserRole.WORKPLACE_PHYSICIAN:
        if set(data.keys()) - {"physician_note"}:
            raise HTTPException(403, "Hekim yalnızca hekim değerlendirmesi ekleyebilir.")
        row.physician_note = data.get("physician_note")
        row.updated_at = datetime.utcnow()
        add_audit_log(
            db,
            user=user,
            action="annual_eval_physician_note",
            module="annual_eval",
            entity_type="annual_plan_evaluation_item",
            entity_id=str(row.id),
            description="Hekim görüşü güncellendi",
        )
        db.commit()
        db.refresh(row)
        plan = db.get(AnnualPlanItem, row.plan_item_id)
        if not plan:
            raise HTTPException(404, "Plan kalemi bulunamadı.")
        evc = db.scalar(
            select(func.count()).select_from(AnnualPlanEvalEvidence).where(
                AnnualPlanEvalEvidence.evaluation_item_id == row.id,
                AnnualPlanEvalEvidence.is_active.is_(True),
            )
        ) or 0
        return _to_item_resp(row, plan, int(evc))

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


@router.post("/items/{item_id}/evidences/link")
def link_evidence(
    item_id: int,
    payload: EvidenceLinkCreate,
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
    mod = payload.source_module.strip().lower()
    if mod not in LINKABLE_MODULES:
        raise HTTPException(422, "Desteklenmeyen kaynak modül.")
    note = f"link:{mod}:{payload.source_id}"
    dup = db.scalar(
        select(AnnualPlanEvalEvidence).where(
            AnnualPlanEvalEvidence.evaluation_item_id == row.id,
            AnnualPlanEvalEvidence.notes == note,
            AnnualPlanEvalEvidence.is_active.is_(True),
        )
    )
    if dup:
        return {"id": dup.id, "title": dup.title, "linked": True, "duplicate": True}
    evd = AnnualPlanEvalEvidence(
        evaluation_item_id=row.id,
        doc_type=payload.doc_type or "modul_link",
        title=payload.title or f"{mod}#{payload.source_id}",
        notes=note,
        uploaded_by_id=user.id,
    )
    db.add(evd)
    db.commit()
    db.refresh(evd)
    add_audit_log(
        db,
        user=user,
        action="annual_eval_evidence_link",
        module="annual_eval",
        entity_type="annual_plan_eval_evidence",
        entity_id=str(evd.id),
        description=note,
    )
    db.commit()
    return {"id": evd.id, "title": evd.title, "linked": True, "duplicate": False}


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
            "notes": e.notes,
            "created_at": e.created_at,
        }
        for e in rows
    ]


@router.delete("/evidences/{evidence_id}")
def unlink_evidence(
    evidence_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    """İlişkiyi kaldırır (soft delete); dosya/geçmiş bozulmaz."""
    evd = db.get(AnnualPlanEvalEvidence, evidence_id)
    if not evd or not evd.is_active:
        raise HTTPException(404, "Kanıt bulunamadı.")
    item = db.get(AnnualPlanEvaluationItem, evd.evaluation_item_id)
    if not item:
        raise HTTPException(404, "Değerlendirme kalemi bulunamadı.")
    ensure_company_access(db, user, item.company_id)
    ev = db.get(AnnualPlanEvaluation, item.evaluation_id)
    if ev:
        _assert_editable(ev)
    evd.is_active = False
    add_audit_log(
        db,
        user=user,
        action="annual_eval_evidence_unlink",
        module="annual_eval",
        entity_type="annual_plan_eval_evidence",
        entity_id=str(evd.id),
        description=evd.title or evd.notes,
    )
    db.commit()
    return {"ok": True, "id": evidence_id}


@router.get("/items/{item_id}/history")
def item_history(
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    from app.models.entities import AuditLog

    row = db.get(AnnualPlanEvaluationItem, item_id)
    if not row:
        raise HTTPException(404, "Kayıt bulunamadı.")
    ensure_company_access(db, user, row.company_id)
    logs = list(
        db.scalars(
            select(AuditLog)
            .where(
                AuditLog.module == "annual_eval",
                AuditLog.entity_id == str(item_id),
            )
            .order_by(AuditLog.created_at.desc())
            .limit(50)
        ).all()
    )
    # Also evaluation-level and evidence actions mentioning this item
    return [
        {
            "id": a.id,
            "action": a.action,
            "description": a.description,
            "created_at": a.created_at,
            "user_id": a.user_id,
            "old_value": a.old_value,
            "new_value": a.new_value,
        }
        for a in logs
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
    add_audit_log(
        db,
        user=user,
        action="annual_eval_capa_create",
        module="annual_eval",
        entity_type="annual_plan_eval_capa",
        entity_id=str(row.id),
        description=row.title,
    )
    db.commit()
    return {"id": row.id, "title": row.title, "status": row.status}


@router.get("/{evaluation_id}/capas")
def list_capas(
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
            select(AnnualPlanEvalCapa).where(
                AnnualPlanEvalCapa.evaluation_id == evaluation_id,
                AnnualPlanEvalCapa.is_active.is_(True),
            )
        ).all()
    )
    return [
        {
            "id": r.id,
            "evaluation_item_id": r.evaluation_item_id,
            "title": r.title,
            "root_cause": r.root_cause,
            "action": r.action,
            "responsible": r.responsible,
            "due_date": r.due_date,
            "priority": r.priority,
            "status": r.status,
            "notes": r.notes,
        }
        for r in rows
    ]


@router.post("/{evaluation_id}/workflow/{action}")
def workflow(
    evaluation_id: int,
    action: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*WORKFLOW_ROLES)),
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
        "create-revision": "revizyon",
        "archive": "arsiv",
    }
    if action not in mapping:
        raise HTTPException(400, "Geçersiz iş akışı adımı.")
    if user.role == UserRole.READ_ONLY and action not in ("approve-employer", "request-revision"):
        raise HTTPException(403, "İşveren görünümü yalnızca onay / revizyon isteği uygulayabilir.")
    if user.role == UserRole.WORKPLACE_PHYSICIAN and action not in ("approve-physician", "request-revision"):
        raise HTTPException(403, "Hekim bu iş akışı adımını uygulayamaz.")
    if action == "create-revision":
        if ev.report_status not in ("onaylandi", "arsiv", "revizyon"):
            raise HTTPException(409, "Revizyon yalnızca onaylı/arşiv rapordan açılır.")
        if user.role not in EDIT_ROLES:
            raise HTTPException(403, "Revizyon açma yalnızca uzman/yönetici.")
    elif ev.report_status in LOCKED_REPORT and action != "archive":
        raise HTTPException(409, "Kilitli rapor.")
    if action == "approve-employer" and user.role == UserRole.WORKPLACE_PHYSICIAN:
        raise HTTPException(403, "İşveren onayı hekim rolüyle verilemez.")
    revision_payload = None
    if action == "create-revision":
        rev = _create_revision_snapshot(db, ev, user)
        revision_payload = {"revision_id": None, "revision_no": rev.revision_no, "change_count": len(json.loads(rev.changes_json or "[]"))}
        ev.notes = ((ev.notes or "") + f"\nRevizyon #{rev.revision_no} açıldı: {date.today().isoformat()}").strip()
    ev.report_status = mapping[action]
    if action == "approve-employer":
        ev.report_date = date.today()
        _ensure_verify_code(ev)
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
    if action == "create-revision" and revision_payload is not None:
        last = db.scalar(
            select(AnnualPlanEvalRevision)
            .where(AnnualPlanEvalRevision.evaluation_id == ev.id)
            .order_by(AnnualPlanEvalRevision.revision_no.desc())
            .limit(1)
        )
        if last:
            revision_payload["revision_id"] = last.id
            revision_payload["change_count"] = len(json.loads(last.changes_json or "[]"))
    # E-posta hatırlatma (SMTP yoksa sessizce atlanır)
    company = db.get(Company, ev.company_id)
    cname = company.name if company else str(ev.company_id)
    mail_map = {
        "submit-specialist": (
            (UserRole.WORKPLACE_PHYSICIAN,),
            f"Yıllık değerlendirme hekim onayı — {cname} / {ev.year}",
            f"{cname} {ev.year} yıllık değerlendirme hekim onayına gönderildi.",
        ),
        "approve-physician": (
            (UserRole.READ_ONLY, UserRole.SAFETY_SPECIALIST),
            f"Yıllık değerlendirme işveren onayı — {cname} / {ev.year}",
            f"{cname} {ev.year} yıllık değerlendirme işveren onayında.",
        ),
        "approve-employer": (
            (UserRole.SAFETY_SPECIALIST, UserRole.WORKPLACE_PHYSICIAN),
            f"Yıllık değerlendirme onaylandı — {cname} / {ev.year}",
            f"{cname} {ev.year} yıllık değerlendirme onaylandı. Kod: {ev.verify_code or '-'}",
        ),
        "request-revision": (
            (UserRole.SAFETY_SPECIALIST,),
            f"Yıllık değerlendirme revizyon — {cname} / {ev.year}",
            f"{cname} {ev.year} yıllık değerlendirme için revizyon istendi.",
        ),
    }
    mail_result = []
    if action in mail_map:
        roles, subject, body = mail_map[action]
        mail_result = _email_company_roles(db, ev.company_id, roles, subject, body)
    out = {"id": ev.id, "report_status": ev.report_status, "email": mail_result}
    if revision_payload:
        out["revision"] = revision_payload
    return out


@router.get("/{evaluation_id}/revisions")
def list_revisions(
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
            select(AnnualPlanEvalRevision)
            .where(AnnualPlanEvalRevision.evaluation_id == evaluation_id)
            .order_by(AnnualPlanEvalRevision.revision_no.desc())
        ).all()
    )
    return [
        {
            "id": r.id,
            "revision_no": r.revision_no,
            "reason": r.reason,
            "change_count": len(json.loads(r.changes_json or "[]")),
            "changes": json.loads(r.changes_json or "[]"),
            "created_at": r.created_at,
            "created_by_id": r.created_by_id,
        }
        for r in rows
    ]


def _suggestions_payload(db: Session, company_id: int, year: int, user: User) -> dict:
    items = list_items(company_id=company_id, year=year, db=db, user=user)
    suggestions = []
    for it in items:
        if it.outcome_status in ("gerceklesmedi", "ertelendi", "kismi") or it.capa_needed:
            suggestions.append(
                {
                    "source_eval_item_id": it.id,
                    "plan_item_id": it.plan_item_id,
                    "activity": it.plan.activity,
                    "category": it.plan.category,
                    "month": it.plan.month or 1,
                    "responsible_name": it.plan.responsible_name,
                    "reason": it.outcome_status if not it.capa_needed else "capa",
                    "suggestion": it.next_year_suggestion,
                }
            )
    ev = _get_eval(db, company_id, year)
    if ev:
        for u in list_unplanned(evaluation_id=ev.id, db=db, user=user):
            if u.get("suggest_next_year"):
                suggestions.append(
                    {
                        "source_unplanned_id": u["id"],
                        "plan_item_id": None,
                        "activity": u["activity"],
                        "category": u.get("category"),
                        "month": 1,
                        "responsible_name": u.get("responsible_name"),
                        "reason": "plan_disi",
                        "suggestion": "Sonraki yıl planına eklenmesi önerilir.",
                    }
                )
    return {
        "year": year + 1,
        "from_year": year,
        "items": suggestions,
        "note": "Otomatik ekleme yok; kontrollü aktarım kullanıcı onayıyla yapılır.",
    }


@router.get("/related-evidence")
def related_evidence(
    company_id: int,
    year: int = Query(..., ge=2020, le=2100),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    """Modül kayıtlarından salt okunur kanıt önerileri (sağlık verisi toplulaştırılmış)."""
    ensure_company_access(db, user, company_id)
    y0, y1 = date(year, 1, 1), date(year, 12, 31)

    trainings = list(
        db.scalars(
            select(TrainingSession).where(
                TrainingSession.company_id == company_id,
                TrainingSession.start_date >= y0,
                TrainingSession.start_date <= y1,
            ).order_by(TrainingSession.start_date.desc()).limit(30)
        ).all()
    )
    drills = list(
        db.scalars(
            select(DrillRecord).where(
                DrillRecord.company_id == company_id,
                DrillRecord.is_active.is_(True),
                DrillRecord.drill_date >= y0,
                DrillRecord.drill_date <= y1,
            ).order_by(DrillRecord.drill_date.desc()).limit(30)
        ).all()
    )
    incidents = list(
        db.scalars(
            select(IncidentEvent).where(
                IncidentEvent.company_id == company_id,
                IncidentEvent.event_date >= y0,
                IncidentEvent.event_date <= y1,
            ).order_by(IncidentEvent.event_date.desc()).limit(30)
        ).all()
    )
    risks = list(
        db.scalars(
            select(RiskAssessment).where(
                RiskAssessment.company_id == company_id,
                RiskAssessment.created_at >= datetime(year, 1, 1),
                RiskAssessment.created_at < datetime(year + 1, 1, 1),
            ).order_by(RiskAssessment.id.desc()).limit(30)
        ).all()
    )
    health_done = db.scalar(
        select(func.count()).select_from(HealthRecord).where(
            HealthRecord.company_id == company_id,
            HealthRecord.examination_date >= y0,
            HealthRecord.examination_date <= y1,
        )
    ) or 0
    health_pending_next = db.scalar(
        select(func.count()).select_from(HealthRecord).where(
            HealthRecord.company_id == company_id,
            HealthRecord.next_examination_date.is_not(None),
            HealthRecord.next_examination_date >= y0,
            HealthRecord.next_examination_date <= y1,
        )
    ) or 0

    return {
        "year": year,
        "trainings": {
            "count": len(trainings),
            "completed": sum(1 for t in trainings if t.status == TrainingStatus.COMPLETED),
            "items": [
                {"id": t.id, "title": t.title, "date": t.start_date, "status": t.status.value if hasattr(t.status, "value") else str(t.status)}
                for t in trainings[:15]
            ],
        },
        "drills": {
            "count": len(drills),
            "items": [
                {"id": d.id, "title": d.drill_type, "date": d.drill_date, "status": d.status}
                for d in drills[:15]
            ],
        },
        "incidents": {
            "count": len(incidents),
            "accident": sum(1 for i in incidents if i.event_type == "accident"),
            "near_miss": sum(1 for i in incidents if i.event_type == "near_miss"),
            "items": [
                {"id": i.id, "title": (i.short_summary or "")[:80], "date": i.event_date, "type": i.event_type}
                for i in incidents[:15]
            ],
        },
        "risks": {
            "count": len(risks),
            "items": [
                {
                    "id": r.id,
                    "title": (r.activity or r.risk_definition or r.risk_code or f"Risk#{r.id}")[:80],
                    "date": r.created_at.date() if r.created_at else None,
                }
                for r in risks[:15]
            ],
        },
        "health_summary": {
            "exams_completed": int(health_done),
            "followups_in_year": int(health_pending_next),
            "note": "Tanı/teşhis gibi özel nitelikli sağlık verisi aktarılmaz; yalnızca toplulaştırılmış sayılar.",
        },
        "note": "Önerilen kayıtlar silinmez; kullanıcı ilişkiyi kanıt olarak bağlayabilir.",
    }


@router.post("/transfer-to-next-year")
def transfer_to_next_year(
    payload: TransferNextYear,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    """Kontrollü aktarım: yeni yıl için bağımsız AnnualPlanItem oluşturur; eski değerlendirmeyi değiştirmez."""
    ensure_company_access(db, user, payload.company_id)
    target_year = payload.from_year + 1
    created = []
    for it in payload.items:
        row = AnnualPlanItem(
            company_id=payload.company_id,
            year=target_year,
            month=it.month,
            category=it.category or "yillik_calisma",
            activity=it.activity,
            description=(it.description or f"Önceki yıl ({payload.from_year}) değerlendirmesinden aktarıldı.")[:2000],
            responsible_name=it.responsible_name,
            status=AnnualPlanStatus.PLANNED,
            created_by_id=user.id,
        )
        db.add(row)
        db.flush()
        created.append({"id": row.id, "activity": row.activity, "year": target_year})
    add_audit_log(
        db,
        user=user,
        action="annual_eval_transfer_next_year",
        module="annual_eval",
        entity_type="annual_plan_item",
        entity_id=str(payload.company_id),
        description=f"{payload.from_year}->{target_year} {len(created)} kalem",
    )
    db.commit()
    return {
        "from_year": payload.from_year,
        "to_year": target_year,
        "created_count": len(created),
        "items": created,
        "note": "Yeni plan kalemleri oluşturuldu; önceki yıl değerlendirme kayıtları değiştirilmedi.",
    }


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
    capas: list[dict] = []
    if ev:
        unplanned = list_unplanned(evaluation_id=ev.id, db=db, user=user)
        capas = list_capas(evaluation_id=ev.id, db=db, user=user)
    suggestions = _suggestions_payload(db, company_id, year, user).get("items") or []
    data = build_eval_xlsx(
        company_name=company.name if company else str(company_id),
        year=year,
        items=items,
        unplanned=unplanned,
        kpis=ov.kpis,
        capas=capas,
        suggestions=suggestions,
    )
    return StreamingResponse(
        BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="yillik-degerlendirme-{year}.xlsx"'},
    )


@router.get("/year-compare")
def year_compare(
    company_id: int,
    year: int = Query(..., ge=2020, le=2100),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    ensure_company_access(db, user, company_id)
    curr = _overview(db, company_id, year, user)
    prev = _overview(db, company_id, year - 1, user)
    return {
        "year": year,
        "prev_year": year - 1,
        "curr_planned": curr.kpis.get("planned_total"),
        "curr_rate": curr.kpis.get("completion_rate"),
        "prev_planned": prev.kpis.get("planned_total"),
        "prev_rate": prev.kpis.get("completion_rate"),
        "delta_rate": (
            None
            if curr.kpis.get("completion_rate") is None or prev.kpis.get("completion_rate") is None
            else round(float(curr.kpis["completion_rate"]) - float(prev.kpis["completion_rate"]), 1)
        ),
        "note": "Önceki yıl değerlendirmesi yoksa oran boş kalır; eski kayıtlar değiştirilmez.",
    }


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
    ev = _get_eval(db, company_id, year)
    unplanned: list[dict] = []
    capas: list[dict] = []
    if ev:
        unplanned = list_unplanned(evaluation_id=ev.id, db=db, user=user)
        capas = list_capas(evaluation_id=ev.id, db=db, user=user)
        _ensure_verify_code(ev)
        db.commit()
        db.refresh(ev)
    suggestions = _suggestions_payload(db, company_id, year, user).get("items") or []
    related = related_evidence(company_id=company_id, year=year, db=db, user=user)
    compare = year_compare(company_id=company_id, year=year, db=db, user=user)
    data = build_eval_pdf(
        company_name=company.name if company else str(company_id),
        year=year,
        kpis=ov.kpis,
        items=items,
        unplanned=unplanned,
        suggestions=suggestions,
        capas=capas,
        related=related,
        compare=compare,
        meta={
            "sgk_registry_no": ov.sgk_registry_no,
            "hazard_class": ov.hazard_class,
            "employee_count": ov.employee_count,
            "address": ov.address,
            "report_status": ov.report_status,
            "report_date": str(ev.report_date) if ev and ev.report_date else None,
            "specialist_name": ev.specialist_name if ev else None,
            "physician_name": ev.physician_name if ev else None,
            "employer_name": ev.employer_name if ev else None,
            "verify_code": ev.verify_code if ev else None,
            "verify_url": f"/api/v1/annual-evals/verify/{ev.verify_code}" if ev and ev.verify_code else None,
        },
    )
    return StreamingResponse(
        BytesIO(data),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="yillik-degerlendirme-{year}.pdf"'},
    )


@router.get("/verify/{code}")
def verify_report(
    code: str,
    db: Session = Depends(get_db),
):
    """Herkese açık doğrulama — yalnızca özet; firma içeriği yok."""
    ev = db.scalar(
        select(AnnualPlanEvaluation).where(
            AnnualPlanEvaluation.verify_code == code.strip(),
            AnnualPlanEvaluation.is_active.is_(True),
        )
    )
    if not ev:
        raise HTTPException(404, "Doğrulama kodu bulunamadı.")
    company = db.get(Company, ev.company_id)
    return {
        "valid": True,
        "verify_code": ev.verify_code,
        "year": ev.year,
        "report_status": ev.report_status,
        "report_date": ev.report_date,
        "company_name": company.name if company else None,
        "note": "Bu doğrulama yalnızca rapor kimliğini teyit eder; içerik erişimi vermez.",
    }


@router.get("/next-year-suggestions")
def next_year_suggestions(
    company_id: int,
    year: int = Query(..., ge=2020, le=2100),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    ensure_company_access(db, user, company_id)
    return _suggestions_payload(db, company_id, year, user)
