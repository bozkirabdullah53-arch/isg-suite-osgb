from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.company_access import assigned_company_ids
from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import (
    AnnualPlanItem,
    AnnualPlanStatus,
    DocumentRecord,
    Employee,
    HealthRecord,
    IsgModule,
    IsgRecord,
    RiskAssessment,
    User,
    UserRole,
)
from app.services.specialist_compliance import build_specialist_report_snapshot

router = APIRouter(prefix="/reports", tags=["Raporlama"])
ADMIN = (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)
SPECIALIST = (UserRole.SAFETY_SPECIALIST,)


def _company_scope(user: User, company_id: int | None, db: Session) -> list[int] | None:
    """None = global (filtre yok). Boş liste = erişim yok."""
    if user.role == UserRole.GLOBAL_ADMIN:
        if company_id:
            return [company_id]
        return None
    allowed = assigned_company_ids(db, user)
    if not allowed:
        return []
    if company_id:
        if company_id not in allowed:
            raise HTTPException(403, "Bu firmaya erişemezsiniz.")
        return [company_id]
    return allowed


@router.get("/summary")
def report_summary(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN)),
):
    scope = _company_scope(user, company_id, db)
    if scope is not None and not scope:
        return {
            "employee_count": 0,
            "open_risks": 0,
            "accident_count": 0,
            "health_record_count": 0,
            "expired_document_count": 0,
            "delayed_plan_count": 0,
        }

    emp_f = [] if scope is None else [Employee.company_id.in_(scope)]
    employee_count = db.scalar(select(func.count()).select_from(Employee).where(*emp_f)) or 0

    risk_f = [] if scope is None else [RiskAssessment.company_id.in_(scope)]
    open_risks = db.scalar(select(func.count()).select_from(RiskAssessment).where(
        RiskAssessment.status == "Açık",
        *risk_f,
    )) or 0

    isg_f = [] if scope is None else [IsgRecord.company_id.in_(scope)]
    accidents = db.scalar(select(func.count()).select_from(IsgRecord).where(
        IsgRecord.module == IsgModule.ACCIDENT,
        *isg_f,
    )) or 0

    health_f = [HealthRecord.deleted_at.is_(None)]
    if scope is not None:
        health_f.append(HealthRecord.company_id.in_(scope))
    health_records = db.scalar(select(func.count()).select_from(HealthRecord).where(*health_f)) or 0

    doc_f = [] if scope is None else [DocumentRecord.company_id.in_(scope)]
    expired_documents = db.scalar(select(func.count()).select_from(DocumentRecord).where(
        DocumentRecord.valid_until.is_not(None),
        DocumentRecord.valid_until < date.today(),
        *doc_f,
    )) or 0

    plan_f = [AnnualPlanItem.deleted_at.is_(None), AnnualPlanItem.status == AnnualPlanStatus.DELAYED]
    if scope is not None:
        plan_f.append(AnnualPlanItem.company_id.in_(scope))
    delayed_plans = db.scalar(select(func.count()).select_from(AnnualPlanItem).where(*plan_f)) or 0

    return {
        "employee_count": employee_count,
        "open_risks": open_risks,
        "accident_count": accidents,
        "health_record_count": health_records,
        "expired_document_count": expired_documents,
        "delayed_plan_count": delayed_plans,
    }


@router.get("/specialist-summary")
def specialist_report_summary(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*SPECIALIST)),
):
    """Uzmanın yalnız aktif görevlendirmeli işyerleri için sağlık dışı özeti."""
    scope = _company_scope(user, company_id, db) or []
    return build_specialist_report_snapshot(db, scope)


@router.get("/specialist-summary.txt", response_class=PlainTextResponse)
def specialist_report_summary_txt(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*SPECIALIST)),
):
    """Uzman rapor merkezinin klinik veri içermeyen metin çıktısı."""
    scope = _company_scope(user, company_id, db) or []
    snapshot = build_specialist_report_snapshot(db, scope)
    totals = snapshot.get("totals") or {}
    lines = [
        "İSG Suite OSGB — Uzman Rapor Merkezi",
        f"Üretim tarihi: {snapshot.get('generated_at') or date.today().isoformat()}",
        "Kapsam: Aktif görevlendirmeli işyerleri; klinik sağlık verisi içermez.",
        "",
        "GENEL ÖZET",
        f"İşyeri: {totals.get('workplaces', 0)} · Çalışan: {totals.get('employees', 0)} · "
        f"Açık risk: {totals.get('open_risks', 0)} · Açık olay: {totals.get('open_incidents', 0)}",
        f"Yaklaşan/geciken kontrol: {totals.get('overdue_or_due', 0)}",
        "",
        "İŞYERLERİ",
    ]
    for row in snapshot.get("companies") or []:
        lines.append(
            f"- {row.get('company_name') or '—'} | NACE {row.get('nace_code') or '—'} | "
            f"Tehlike {row.get('hazard_class') or '—'} | Çalışan {row.get('employees', 0)} | "
            f"Açık risk {row.get('open_risks', 0)} | Başarısız kontrol {row.get('checks_failed', 0)} | "
            f"Yaklaşan/geciken {row.get('due_count', 0)}"
        )
    lines.extend(("", "AKSİYONLAR"))
    for event in snapshot.get("events") or []:
        due = f" · Termin {event['due_date']}" if event.get("due_date") else ""
        lines.append(
            f"- [{event.get('company_name') or '—'}] {event.get('title') or '—'}{due}: "
            f"{event.get('detail') or ''}"
        )
    return PlainTextResponse(
        "\n".join(lines) + "\n",
        headers={"Content-Disposition": "attachment; filename=specialist-report.txt"},
    )
