"""OSGB profesyonel hizmet denetimi — 6331 ve İSG Hizmetleri Yönetmeliği odaklı.

Global yönetici, görevlendirilmiş uzman/hekim/DSP'nin atanmış işyerlerindeki
zorunlu faaliyetleri yerine getirip getirmediğini takip eder.

Not: Modül kayıtları firma bazlıdır; uzmanla bağ `WorkplaceAssignment` üzerinden
kurulur (firma hijyeni = o görevlendirme altındaki sorumluluk göstergesi).
Saha süresi `ServiceVisit` ile doğrudan profesyonele bağlanır.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    AnnualPlanItem,
    AnnualPlanStatus,
    AssignmentStatus,
    Company,
    Employee,
    HealthFitnessStatus,
    HealthRecord,
    HealthRecordType,
    IncidentEvent,
    IsgProfessional,
    OsgbOrganization,
    ProfessionalType,
    RiskAssessment,
    RiskDof,
    ServiceVisit,
    TrainingSession,
    TrainingStatus,
    User,
    UserRole,
    VisitStatus,
    WorkplaceAssignment,
)

logger = logging.getLogger(__name__)

# 6331 / İSG Hizmetleri Yön. — uzman sorumlulukları (firma göstergeleri)
SPECIALIST_CHECKS = [
    {
        "code": "saha_sure",
        "title": "Aylık saha süresi",
        "legal": "İSG Hizmetleri Yön. — işyerinde fiilen bulunma / hizmet süresi",
        "weight": 2,
    },
    {
        "code": "risk_degerlendirme",
        "title": "Risk değerlendirmesi",
        "legal": "6331 md.10 — risk değerlendirmesi yapılması ve güncelliği",
        "weight": 2,
    },
    {
        "code": "risk_dof",
        "title": "Risk DÖF / termin",
        "legal": "6331 md.10 — belirlenen önlemlerin takibi",
        "weight": 1,
    },
    {
        "code": "yillik_plan",
        "title": "Yıllık çalışma planı",
        "legal": "İSG Hizmetleri Yön. — yıllık çalışma planı",
        "weight": 2,
    },
    {
        "code": "egitim",
        "title": "Çalışan eğitimi",
        "legal": "6331 md.17 — çalışanların eğitimi",
        "weight": 2,
    },
    {
        "code": "olay_takip",
        "title": "Ramak kala / kaza takibi",
        "legal": "6331 md.14 — iş kazası ve meslek hastalıklarının bildirimi/takibi",
        "weight": 1,
    },
]

# Hekim / DSP
PHYSICIAN_CHECKS = [
    {
        "code": "saha_sure",
        "title": "Aylık saha süresi",
        "legal": "İSG Hizmetleri Yön. — hekim/DSP işyerinde bulunma süresi",
        "weight": 2,
    },
    {
        "code": "saglik_gozetim",
        "title": "Sağlık gözetimi kayıtları",
        "legal": "6331 md.15 — sağlık gözetimi",
        "weight": 2,
    },
    {
        "code": "muayene_gecikme",
        "title": "Geciken / yaklaşan muayene",
        "legal": "Sağlık gözetimi periyotlarına uyum",
        "weight": 2,
    },
    {
        "code": "uygunluk",
        "title": "Uygunluk / takip durumları",
        "legal": "İşe giriş ve periyodik muayene sonuçlarının takibi",
        "weight": 1,
    },
]


def _month_bounds(ref: date | None = None) -> tuple[date, date]:
    today = ref or date.today()
    start = today.replace(day=1)
    if today.month == 12:
        end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    return start, end


def _status_from_ratio(ok: int, total: int) -> str:
    if total <= 0:
        return "unknown"
    ratio = ok / total
    if ratio >= 0.85:
        return "ok"
    if ratio >= 0.55:
        return "warning"
    return "critical"


def _check_result(code: str, title: str, legal: str, weight: int, passed: bool, detail: str, metric: Any = None) -> dict:
    return {
        "code": code,
        "title": title,
        "legal": legal,
        "weight": weight,
        "passed": passed,
        "status": "ok" if passed else "critical",
        "detail": detail,
        "metric": metric,
    }


def _list_firm_visits(
    db: Session, professional_id: int, company_id: int, start: date, end: date
) -> list[ServiceVisit]:
    try:
        return list(
            db.scalars(
                select(ServiceVisit)
                .where(
                    ServiceVisit.professional_id == professional_id,
                    ServiceVisit.company_id == company_id,
                    ServiceVisit.visit_date >= start,
                    ServiceVisit.visit_date <= end,
                )
                .order_by(ServiceVisit.visit_date.desc(), ServiceVisit.id.desc())
            ).all()
        )
    except Exception:
        logger.exception(
            "Visit list failed professional=%s company=%s; retrying after rollback",
            professional_id,
            company_id,
        )
        try:
            db.rollback()
        except Exception:
            pass
        return []


def _visit_payload(rows: list[ServiceVisit]) -> list[dict]:
    out = []
    for v in rows:
        notebook_path = getattr(v, "notebook_storage_path", None)
        out.append(
            {
                "id": v.id,
                "visit_date": v.visit_date.isoformat() if v.visit_date else None,
                "start_time": v.start_time,
                "end_time": v.end_time,
                "duration_minutes": int(v.duration_minutes or 0),
                "subject": v.subject,
                "notes": v.notes,
                "status": v.status.value if hasattr(v.status, "value") else str(v.status),
                "notebook_file_name": getattr(v, "notebook_file_name", None),
                "has_notebook": bool(notebook_path),
                "notebook_url": f"/operations/visits/{v.id}/notebook" if notebook_path else None,
            }
        )
    return out


def _visit_minutes(db: Session, professional_id: int, company_id: int, start: date, end: date) -> tuple[int, int, list[dict]]:
    """Tamamlanan veya tespit defteri yüklenmiş ziyaretler süreye sayılır."""
    rows = _list_firm_visits(db, professional_id, company_id, start, end)
    counted = []
    for v in rows:
        st = v.status.value if hasattr(v.status, "value") else str(v.status)
        has_nb = bool(getattr(v, "notebook_storage_path", None))
        if st == VisitStatus.COMPLETED.value or st == "COMPLETED" or has_nb:
            counted.append(v)
    minutes = sum(int(v.duration_minutes or 0) for v in counted)
    return minutes, len(counted), _visit_payload(rows)


def _eval_specialist_firm(
    db: Session,
    company: Company,
    assignment: WorkplaceAssignment,
    month_start: date,
    month_end: date,
    year: int,
) -> tuple[list[dict], list[dict]]:
    cid = company.id
    required = int(assignment.required_minutes_monthly or 0)
    visit_min, visit_count, visits = _visit_minutes(db, assignment.professional_id, cid, month_start, month_end)
    # Manuel actual alanı yedek sinyal
    actual_fallback = int(assignment.actual_minutes_monthly or 0)
    effective_min = visit_min if visit_min > 0 else actual_fallback
    notebook_count = sum(1 for v in visits if v.get("has_notebook"))
    time_ok = required <= 0 or effective_min >= required * 0.8
    # notebook_ok unused — shown in metric / UI visits list

    risk_count = db.scalar(
        select(func.count()).select_from(RiskAssessment).where(RiskAssessment.company_id == cid)
    ) or 0
    open_high = db.scalar(
        select(func.count())
        .select_from(RiskAssessment)
        .where(
            RiskAssessment.company_id == cid,
            RiskAssessment.status == "Açık",
            RiskAssessment.risk_level.in_(["Yüksek", "Çok Yüksek"]),
        )
    ) or 0
    risk_ok = risk_count > 0 and open_high == 0

    overdue_dof = db.scalar(
        select(func.count())
        .select_from(RiskDof)
        .join(RiskAssessment, RiskDof.risk_id == RiskAssessment.id)
        .where(
            RiskAssessment.company_id == cid,
            RiskDof.is_completed.is_(False),
            RiskDof.term_date.is_not(None),
            RiskDof.term_date < date.today(),
        )
    ) or 0
    dof_ok = overdue_dof == 0

    plan_count = db.scalar(
        select(func.count())
        .select_from(AnnualPlanItem)
        .where(
            AnnualPlanItem.company_id == cid,
            AnnualPlanItem.year == year,
            AnnualPlanItem.deleted_at.is_(None),
        )
    ) or 0
    delayed_plans = db.scalar(
        select(func.count())
        .select_from(AnnualPlanItem)
        .where(
            AnnualPlanItem.company_id == cid,
            AnnualPlanItem.year == year,
            AnnualPlanItem.deleted_at.is_(None),
            AnnualPlanItem.status == AnnualPlanStatus.DELAYED,
        )
    ) or 0
    plan_ok = plan_count > 0 and delayed_plans == 0

    trainings = db.scalar(
        select(func.count())
        .select_from(TrainingSession)
        .where(
            TrainingSession.company_id == cid,
            TrainingSession.start_date >= date(year, 1, 1),
            TrainingSession.status != TrainingStatus.CANCELLED,
        )
    ) or 0
    train_ok = trainings > 0

    open_incidents = db.scalar(
        select(func.count())
        .select_from(IncidentEvent)
        .where(
            IncidentEvent.company_id == cid,
            IncidentEvent.status.in_(["Aktif", "Açık", "open", "in_progress"]),
        )
    ) or 0
    incident_ok = open_incidents == 0

    return [
        _check_result(
            "saha_sure",
            "Aylık saha süresi",
            "İSG Hizmetleri Yön. — işyerinde fiilen bulunma / hizmet süresi",
            2,
            time_ok,
            f"Bu ay {effective_min} dk / zorunlu {required or '—'} dk ({visit_count} ziyaret, {notebook_count} tespit defteri)",
            {
                "visit_minutes": visit_min,
                "required": required,
                "visits": visit_count,
                "notebooks": notebook_count,
            },
        ),
        _check_result(
            "risk_degerlendirme",
            "Risk değerlendirmesi",
            "6331 md.10 — risk değerlendirmesi yapılması ve güncelliği",
            2,
            risk_ok,
            f"{risk_count} risk kaydı; açık yüksek/çok yüksek: {open_high}",
            {"risk_count": risk_count, "open_high": open_high},
        ),
        _check_result(
            "risk_dof",
            "Risk DÖF / termin",
            "6331 md.10 — belirlenen önlemlerin takibi",
            1,
            dof_ok,
            f"Geciken DÖF: {overdue_dof}",
            {"overdue_dof": overdue_dof},
        ),
        _check_result(
            "yillik_plan",
            "Yıllık çalışma planı",
            "İSG Hizmetleri Yön. — yıllık çalışma planı",
            2,
            plan_ok,
            f"{year} yılı: {plan_count} madde, geciken {delayed_plans}",
            {"plan_items": plan_count, "delayed": delayed_plans},
        ),
        _check_result(
            "egitim",
            "Çalışan eğitimi",
            "6331 md.17 — çalışanların eğitimi",
            2,
            train_ok,
            f"{year} yılı eğitim kaydı: {trainings}",
            {"trainings": trainings},
        ),
        _check_result(
            "olay_takip",
            "Ramak kala / kaza takibi",
            "6331 md.14 — iş kazası ve meslek hastalıklarının bildirimi/takibi",
            1,
            incident_ok,
            f"Açık olay kaydı: {open_incidents}",
            {"open_incidents": open_incidents},
        ),
    ], visits


def _eval_physician_firm(
    db: Session,
    company: Company,
    assignment: WorkplaceAssignment,
    month_start: date,
    month_end: date,
) -> tuple[list[dict], list[dict]]:
    cid = company.id
    required = int(assignment.required_minutes_monthly or 0)
    visit_min, visit_count, visits = _visit_minutes(db, assignment.professional_id, cid, month_start, month_end)
    actual_fallback = int(assignment.actual_minutes_monthly or 0)
    effective_min = visit_min if visit_min > 0 else actual_fallback
    notebook_count = sum(1 for v in visits if v.get("has_notebook"))
    time_ok = required <= 0 or effective_min >= required * 0.8

    health_total = db.scalar(
        select(func.count())
        .select_from(HealthRecord)
        .where(HealthRecord.company_id == cid, HealthRecord.deleted_at.is_(None))
    ) or 0
    today = date.today()
    overdue = db.scalar(
        select(func.count())
        .select_from(HealthRecord)
        .where(
            HealthRecord.company_id == cid,
            HealthRecord.deleted_at.is_(None),
            HealthRecord.next_examination_date.is_not(None),
            HealthRecord.next_examination_date < today,
        )
    ) or 0
    due_soon = db.scalar(
        select(func.count())
        .select_from(HealthRecord)
        .where(
            HealthRecord.company_id == cid,
            HealthRecord.deleted_at.is_(None),
            HealthRecord.next_examination_date.is_not(None),
            HealthRecord.next_examination_date >= today,
            HealthRecord.next_examination_date <= today + timedelta(days=30),
        )
    ) or 0
    tracking = db.scalar(
        select(func.count())
        .select_from(HealthRecord)
        .where(
            HealthRecord.company_id == cid,
            HealthRecord.deleted_at.is_(None),
            HealthRecord.fitness_status.in_(
                [
                    HealthFitnessStatus.CONDITIONAL.value,
                    HealthFitnessStatus.TRACKING.value,
                    HealthFitnessStatus.UNFIT.value,
                ]
            ),
        )
    ) or 0

    return [
        _check_result(
            "saha_sure",
            "Aylık saha süresi",
            "İSG Hizmetleri Yön. — hekim/DSP işyerinde bulunma süresi",
            2,
            time_ok,
            f"Bu ay {effective_min} dk / zorunlu {required or '—'} dk ({visit_count} ziyaret, {notebook_count} tespit defteri)",
            {
                "visit_minutes": visit_min,
                "required": required,
                "visits": visit_count,
                "notebooks": notebook_count,
            },
        ),
        _check_result(
            "saglik_gozetim",
            "Sağlık gözetimi kayıtları",
            "6331 md.15 — sağlık gözetimi",
            2,
            health_total > 0,
            f"Aktif sağlık kaydı: {health_total}",
            {"health_total": health_total},
        ),
        _check_result(
            "muayene_gecikme",
            "Geciken / yaklaşan muayene",
            "Sağlık gözetimi periyotlarına uyum",
            2,
            overdue == 0,
            f"Geciken {overdue}, 30 gün içinde {due_soon}",
            {"overdue": overdue, "due_soon": due_soon},
        ),
        _check_result(
            "uygunluk",
            "Uygunluk / takip durumları",
            "İşe giriş ve periyodik muayene sonuçlarının takibi",
            1,
            tracking <= max(1, health_total // 5) if health_total else True,
            f"Kısıtlı/takip/uygun değil: {tracking}",
            {"tracking": tracking},
        ),
    ], visits


def build_oversight(db: Session, osgb_id: int | None = None) -> dict:
    month_start, month_end = _month_bounds()
    year = date.today().year

    # Aktif + pasif: isim listesinde herkes görünür (askıdaki uzman da seçilebilsin)
    pros_q = select(IsgProfessional).order_by(IsgProfessional.full_name)
    assign_q = select(WorkplaceAssignment).where(WorkplaceAssignment.status == AssignmentStatus.ACTIVE)
    if osgb_id:
        pros_q = pros_q.where(IsgProfessional.osgb_id == osgb_id)
        assign_q = assign_q.where(WorkplaceAssignment.osgb_id == osgb_id)

    professionals = list(db.scalars(pros_q).all())
    directory = [
        {
            "professional_id": p.id,
            "full_name": p.full_name,
            "professional_type": p.professional_type.value,
            "certificate_class": p.certificate_class,
            "is_active": bool(p.is_active),
        }
        for p in professionals
    ]
    assignments = list(db.scalars(assign_q).all())
    company_ids = {a.company_id for a in assignments}
    companies = {
        c.id: c
        for c in db.scalars(select(Company).where(Company.id.in_(company_ids))).all()
    } if company_ids else {}

    by_pro: dict[int, list[WorkplaceAssignment]] = {}
    for a in assignments:
        by_pro.setdefault(a.professional_id, []).append(a)

    rows = []
    summary = {
        "professionals": 0,
        "assignments": 0,
        "ok": 0,
        "warning": 0,
        "critical": 0,
        "unknown": 0,
        "unassigned": 0,
    }

    for pro in professionals:
        firms = []
        firm_statuses = []
        for a in by_pro.get(pro.id, []):
            company = companies.get(a.company_id)
            if not company:
                continue
            try:
                if pro.professional_type == ProfessionalType.SAFETY_SPECIALIST:
                    checks, visits = _eval_specialist_firm(db, company, a, month_start, month_end, year)
                else:
                    checks, visits = _eval_physician_firm(db, company, a, month_start, month_end)
            except Exception as exc:
                logger.exception(
                    "Oversight eval failed pro=%s company=%s assignment=%s",
                    pro.id,
                    company.id,
                    a.id,
                )
                try:
                    db.rollback()
                except Exception:
                    pass
                err = str(exc).strip() or exc.__class__.__name__
                if len(err) > 220:
                    err = err[:217] + "…"
                checks = [
                    _check_result(
                        "sistem",
                        "Değerlendirme hatası",
                        "Sistem",
                        1,
                        False,
                        f"{company.name} için kontrol hesaplanamadı ({err}). Yenile’ye basın; sürerse yöneticiye bildirin.",
                    )
                ]
                visits = []

            weight_total = sum(c["weight"] for c in checks) or 1
            weight_ok = sum(c["weight"] for c in checks if c["passed"])
            score = round(100 * weight_ok / weight_total)
            status = _status_from_ratio(weight_ok, weight_total)
            firm_statuses.append(status)
            firms.append(
                {
                    "assignment_id": a.id,
                    "company_id": company.id,
                    "company_name": company.name,
                    "hazard_class": company.hazard_class,
                    "required_minutes_monthly": a.required_minutes_monthly,
                    "isg_katip_contract_number": a.isg_katip_contract_number,
                    "score": score,
                    "status": status,
                    "checks": checks,
                    "visits": visits,
                    "visit_count": len(visits),
                    "notebook_count": sum(1 for v in visits if v.get("has_notebook")),
                    "failed_count": sum(1 for c in checks if not c["passed"]),
                }
            )

        # Atanmamış profesyoneller de listede kalsın (kritik — görevlendirme eksik)
        if not firms:
            summary["professionals"] += 1
            summary["unassigned"] += 1
            summary["critical"] += 1
            unassigned_gap = {
                "company_id": None,
                "company_name": "—",
                "check_code": "gorevlendirme",
                "check_title": "İşyeri görevlendirmesi yok",
                "detail": "Bu profesyonel henüz hiçbir işyerine atanmamış. Önce Görevlendirmeler’den atayın.",
                "legal": "İSG Hizmetleri Yön. — işyerine uzman/hekim/DSP görevlendirme zorunluluğu",
            }
            rows.append(
                {
                    "professional_id": pro.id,
                    "full_name": pro.full_name,
                    "professional_type": pro.professional_type.value,
                    "certificate_class": pro.certificate_class,
                    "certificate_number": pro.certificate_number,
                    "osgb_id": pro.osgb_id,
                    "is_active": bool(pro.is_active),
                    "firm_count": 0,
                    "score": 0,
                    "status": "critical",
                    "firms": [],
                    "check_columns": [
                        {
                            "code": "gorevlendirme",
                            "title": "Görevlendirme",
                            "legal": unassigned_gap["legal"],
                            "passed": 0,
                            "total": 1,
                            "pct": 0,
                            "failed": 1,
                            "status": "critical",
                        }
                    ],
                    "gaps": [unassigned_gap],
                    "gap_count": 1,
                    "unassigned": True,
                }
            )
            continue

        # Profesyonel düzeyinde sütun grafik verisi (sorumluluk alanları)
        check_agg: dict[str, dict] = {}
        gaps = []
        for f in firms:
            for c in f["checks"]:
                bucket = check_agg.setdefault(
                    c["code"],
                    {"code": c["code"], "title": c["title"], "legal": c["legal"], "passed": 0, "total": 0},
                )
                bucket["total"] += 1
                if c["passed"]:
                    bucket["passed"] += 1
                else:
                    gaps.append(
                        {
                            "company_id": f["company_id"],
                            "company_name": f["company_name"],
                            "check_code": c["code"],
                            "check_title": c["title"],
                            "detail": c["detail"],
                            "legal": c["legal"],
                        }
                    )
        check_columns = []
        for b in check_agg.values():
            pct = round(100 * b["passed"] / b["total"]) if b["total"] else 0
            check_columns.append(
                {
                    **b,
                    "pct": pct,
                    "failed": b["total"] - b["passed"],
                    "status": "ok" if pct >= 85 else "warning" if pct >= 55 else "critical",
                }
            )

        avg_score = round(sum(f["score"] for f in firms) / len(firms))
        if "critical" in firm_statuses:
            overall = "critical"
        elif "warning" in firm_statuses:
            overall = "warning"
        elif all(s == "ok" for s in firm_statuses):
            overall = "ok"
        else:
            overall = "unknown"

        summary["professionals"] += 1
        summary["assignments"] += len(firms)
        summary[overall] = summary.get(overall, 0) + 1

        rows.append(
            {
                "professional_id": pro.id,
                "full_name": pro.full_name,
                "professional_type": pro.professional_type.value,
                "certificate_class": pro.certificate_class,
                "certificate_number": pro.certificate_number,
                "osgb_id": pro.osgb_id,
                "is_active": bool(pro.is_active),
                "firm_count": len(firms),
                "score": avg_score,
                "status": overall,
                "firms": firms,
                "check_columns": check_columns,
                "gaps": gaps,
                "gap_count": len(gaps),
                "unassigned": False,
            }
        )

    rows.sort(key=lambda r: (0 if r["status"] == "critical" else 1 if r["status"] == "warning" else 2, r["score"]))

    # OSGB geneli sorumluluk sütunları
    global_agg: dict[str, dict] = {}
    global_gaps = []
    for r in rows:
        for c in r["check_columns"]:
            g = global_agg.setdefault(
                c["code"],
                {"code": c["code"], "title": c["title"], "legal": c.get("legal", ""), "passed": 0, "total": 0},
            )
            g["passed"] += c["passed"]
            g["total"] += c["total"]
        for gap in r["gaps"]:
            global_gaps.append({**gap, "professional_id": r["professional_id"], "full_name": r["full_name"], "professional_type": r["professional_type"]})

    check_columns = []
    for b in global_agg.values():
        pct = round(100 * b["passed"] / b["total"]) if b["total"] else 0
        check_columns.append(
            {
                **b,
                "pct": pct,
                "failed": b["total"] - b["passed"],
                "status": "ok" if pct >= 85 else "warning" if pct >= 55 else "critical",
            }
        )
    check_columns.sort(key=lambda x: x["pct"])

    return {
        "period": {
            "year": year,
            "month": date.today().month,
            "month_start": month_start.isoformat(),
            "month_end": month_end.isoformat(),
        },
        "legal_basis": [
            "6331 sayılı İş Sağlığı ve Güvenliği Kanunu",
            "İş Sağlığı ve Güvenliği Hizmetleri Yönetmeliği",
            "İşyeri Hekimi ve Diğer Sağlık Personeli ile İş Güvenliği Uzmanlarının Görev, Yetki, Sorumluluk ve Eğitimleri Hakkında Yönetmelik",
        ],
        "check_catalog": {
            "safety_specialist": SPECIALIST_CHECKS,
            "workplace_physician": PHYSICIAN_CHECKS,
            "other_health_personnel": PHYSICIAN_CHECKS,
        },
        "summary": summary,
        "check_columns": check_columns,
        "gaps": global_gaps,
        "gap_count": len(global_gaps),
        "directory": directory,
        "professionals": rows,
    }


def build_professional_performance(db: Session, professional_id: int) -> dict:
    """Tek profesyonel için iş tamamlama / performans raporu (global yönetici)."""
    pro = db.get(IsgProfessional, professional_id)
    if not pro:
        raise ValueError("Profesyonel bulunamadı.")

    overview = build_oversight(db, osgb_id=pro.osgb_id)
    row = next(
        (p for p in overview.get("professionals") or [] if p["professional_id"] == professional_id),
        None,
    )

    type_labels = {
        "safety_specialist": "İş Güvenliği Uzmanı",
        "workplace_physician": "İşyeri Hekimi",
        "other_health_personnel": "Diğer Sağlık Personeli",
    }

    if not row:
        # Oversight listesinde yok (pasif / filtre) — yine de kimlik dön
        return {
            "professional": {
                "id": pro.id,
                "full_name": pro.full_name,
                "professional_type": pro.professional_type.value,
                "role_label": type_labels.get(pro.professional_type.value, pro.professional_type.value),
                "certificate_class": pro.certificate_class,
                "certificate_number": pro.certificate_number,
                "is_active": bool(pro.is_active),
                "osgb_id": pro.osgb_id,
            },
            "period": overview.get("period"),
            "legal_basis": overview.get("legal_basis"),
            "performance": {
                "score": 0,
                "status": "critical",
                "firm_count": 0,
                "completed_checks": 0,
                "total_checks": 0,
                "completion_pct": 0,
                "gap_count": 1,
            },
            "firms": [],
            "completed": [],
            "incomplete": [
                {
                    "company_id": None,
                    "company_name": "—",
                    "check_code": "gorevlendirme",
                    "check_title": "Değerlendirme verisi yok",
                    "detail": "Aktif görevlendirme veya dönem verisi bulunamadı.",
                    "legal": "",
                }
            ],
            "check_columns": [],
            "report_title": f"İş Tamamlama / Performans Raporu — {pro.full_name}",
            "generated_at": date.today().isoformat(),
        }

    completed = []
    incomplete = []
    total_checks = 0
    passed_checks = 0
    for f in row.get("firms") or []:
        for c in f.get("checks") or []:
            total_checks += 1
            item = {
                "company_id": f["company_id"],
                "company_name": f["company_name"],
                "check_code": c["code"],
                "check_title": c["title"],
                "detail": c["detail"],
                "legal": c.get("legal"),
            }
            if c.get("passed"):
                passed_checks += 1
                completed.append(item)
            else:
                incomplete.append(item)

    # Unassigned: firms empty — use oversight gaps (görevlendirme)
    if row.get("unassigned") or (not row.get("firms") and row.get("gaps")):
        if not incomplete:
            incomplete = list(row.get("gaps") or [])

    completion_pct = round(100 * passed_checks / total_checks) if total_checks else (0 if incomplete else 100)

    return {
        "professional": {
            "id": pro.id,
            "full_name": pro.full_name,
            "professional_type": row["professional_type"],
            "role_label": type_labels.get(row["professional_type"], row["professional_type"]),
            "certificate_class": row.get("certificate_class"),
            "certificate_number": row.get("certificate_number"),
            "is_active": row.get("is_active", True),
            "osgb_id": pro.osgb_id,
        },
        "period": overview.get("period"),
        "legal_basis": overview.get("legal_basis"),
        "performance": {
            "score": row.get("score", 0),
            "status": row.get("status", "unknown"),
            "firm_count": row.get("firm_count", 0),
            "completed_checks": passed_checks,
            "total_checks": total_checks,
            "completion_pct": completion_pct,
            "gap_count": len(incomplete),
            "unassigned": bool(row.get("unassigned")),
        },
        "firms": row.get("firms") or [],
        "completed": completed,
        "incomplete": incomplete,
        "check_columns": row.get("check_columns") or [],
        "report_title": f"İş Tamamlama / Performans Raporu — {pro.full_name}",
        "generated_at": date.today().isoformat(),
    }


def seed_oversight_demo(db: Session, osgb_id: int | None = None) -> dict:
    """Test uzman / hekim / DSP + kasıtlı eksiklikler (denetim paneli smoke)."""
    osgb = None
    if osgb_id:
        osgb = db.get(OsgbOrganization, osgb_id)
    if not osgb:
        osgb = db.scalar(select(OsgbOrganization).order_by(OsgbOrganization.id).limit(1))
    if not osgb:
        osgb = OsgbOrganization(
            name="Demo OSGB Denetim",
            authorization_number="DEMO-OSGB-001",
            tax_number="1111111111",
            responsible_manager="Demo Yönetici",
            email="demo.osgb@example.com",
            is_active=True,
        )
        db.add(osgb)
        db.flush()

    company = db.scalar(
        select(Company).where(Company.osgb_id == osgb.id, Company.is_active.is_(True)).order_by(Company.id).limit(1)
    )
    if not company:
        company = db.scalar(
            select(Company).where(Company.name.like("%Denetim Demo%")).limit(1)
        )
    if not company:
        # OSGB'ye bağlı işyeri yoksa mevcut herhangi bir aktif işyeri bağla
        company = db.scalar(select(Company).where(Company.is_active.is_(True)).order_by(Company.id).limit(1))
        if company and company.osgb_id is None:
            company.osgb_id = osgb.id
            db.flush()
    if not company:
        company = Company(
            name=f"Denetim Demo İşyeri ({osgb.id})",
            tax_number=f"9{osgb.id:09d}"[:10],
            nace_code="25.11",
            hazard_class="Tehlikeli",
            is_active=True,
            osgb_id=osgb.id,
        )
        db.add(company)
        db.flush()
    elif company.osgb_id != osgb.id:
        company.osgb_id = osgb.id
        db.flush()

    admin = db.scalar(select(User).where(User.role == UserRole.GLOBAL_ADMIN).limit(1))
    if not admin:
        raise ValueError("Global yönetici kullanıcısı yok.")

    specs = [
        (ProfessionalType.SAFETY_SPECIALIST, "TEST Uzman — Denetim", "DENETIM-UZM-001", "A"),
        (ProfessionalType.WORKPLACE_PHYSICIAN, "TEST Hekim — Denetim", "DENETIM-HEK-001", "A"),
        (ProfessionalType.OTHER_HEALTH_PERSONNEL, "TEST DSP — Denetim", "DENETIM-DSP-001", "B"),
    ]
    created = []
    for ptype, name, cert, cls in specs:
        pro = db.scalar(
            select(IsgProfessional).where(
                IsgProfessional.osgb_id == osgb.id,
                IsgProfessional.certificate_number == cert,
            )
        )
        if not pro:
            pro = IsgProfessional(
                osgb_id=osgb.id,
                full_name=name,
                email=f"denetim.{ptype.value}@example.com",
                phone="05551234567",
                professional_type=ptype,
                certificate_class=cls,
                certificate_number=cert,
                certificate_date=date(2022, 1, 1),
                is_active=True,
            )
            db.add(pro)
            db.flush()
        else:
            pro.full_name = name
            pro.is_active = True

        assign = db.scalar(
            select(WorkplaceAssignment).where(
                WorkplaceAssignment.company_id == company.id,
                WorkplaceAssignment.professional_id == pro.id,
            )
        )
        if not assign:
            assign = WorkplaceAssignment(
                osgb_id=osgb.id,
                company_id=company.id,
                professional_id=pro.id,
                professional_type=ptype,
                start_date=date(2025, 1, 1),
                required_minutes_monthly=480,
                planned_minutes_monthly=480,
                actual_minutes_monthly=60,
                isg_katip_contract_number=f"DEMO-KATIP-{pro.id}",
                status=AssignmentStatus.ACTIVE,
            )
            db.add(assign)
        else:
            assign.status = AssignmentStatus.ACTIVE
            assign.required_minutes_monthly = 480
            assign.actual_minutes_monthly = 60

        created.append({"id": pro.id, "name": name, "type": ptype.value})

    db.flush()
    uzman = db.scalar(select(IsgProfessional).where(IsgProfessional.certificate_number == "DENETIM-UZM-001"))
    hekim = db.scalar(select(IsgProfessional).where(IsgProfessional.certificate_number == "DENETIM-HEK-001"))

    if uzman:
        existing_v = db.scalar(
            select(ServiceVisit).where(
                ServiceVisit.professional_id == uzman.id,
                ServiceVisit.company_id == company.id,
                ServiceVisit.subject.like("%Denetim Demo%"),
            )
        )
        if not existing_v:
            db.add(
                ServiceVisit(
                    osgb_id=osgb.id,
                    company_id=company.id,
                    professional_id=uzman.id,
                    visit_date=date.today(),
                    start_time="09:00",
                    end_time="10:00",
                    duration_minutes=60,
                    subject="Denetim Demo — yetersiz saha süresi",
                    notes="Kasıtlı düşük dakika (test)",
                    status=VisitStatus.COMPLETED,
                )
            )
        plan = db.scalar(
            select(AnnualPlanItem).where(
                AnnualPlanItem.company_id == company.id,
                AnnualPlanItem.activity.like("%Denetim Demo%"),
            )
        )
        if not plan:
            db.add(
                AnnualPlanItem(
                    company_id=company.id,
                    year=date.today().year,
                    month=date.today().month,
                    category="yillik_calisma",
                    activity="Denetim Demo — geciken plan maddesi",
                    description="Test eksikliği",
                    responsible_name="TEST Uzman",
                    target_date=date.today() - timedelta(days=10),
                    status=AnnualPlanStatus.DELAYED,
                    created_by_id=admin.id,
                )
            )

    if hekim:
        emp = db.scalar(select(Employee).where(Employee.company_id == company.id).limit(1))
        if not emp:
            emp = Employee(
                company_id=company.id,
                full_name="Denetim Demo Çalışan",
                job_title="Kaynakçı",
                department="Üretim",
                is_active=True,
            )
            db.add(emp)
            db.flush()
        hr = db.scalar(
            select(HealthRecord).where(
                HealthRecord.company_id == company.id,
                HealthRecord.summary.like("%Denetim Demo%"),
            )
        )
        if not hr:
            db.add(
                HealthRecord(
                    company_id=company.id,
                    employee_id=emp.id,
                    record_type=HealthRecordType.PERIODIC_EXAM,
                    examination_date=date.today() - timedelta(days=400),
                    next_examination_date=date.today() - timedelta(days=30),
                    fitness_status=HealthFitnessStatus.TRACKING,
                    physician_name="TEST Hekim — Denetim",
                    summary="Denetim Demo — geciken muayene",
                    created_by_id=admin.id,
                )
            )

    db.commit()
    return {
        "osgb_id": osgb.id,
        "company_id": company.id,
        "company_name": company.name,
        "professionals": created,
        "note": "Uzmanda düşük saha + geciken plan; hekimde geciken muayene — panoda kritik görünmeli.",
    }
