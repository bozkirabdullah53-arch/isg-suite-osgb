"""6331 / İSG Hizmetleri Yönetmeliği kapasite motoru — mevzuat asgari süre vs fiili yük."""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    AssignmentStatus,
    Company,
    Employee,
    IsgProfessional,
    ProfessionalType,
    WorkplaceAssignment,
)
from app.services.osgb_oversight import _month_bounds, _visit_minutes

# İSG Hizmetleri Yönetmeliği — işyeri başına aylık asgari dakika (basitleştirilmiş tablo).
# Çalışan dilimleri: 1-9, 10-49, 50-249, 250+
_BRACKETS = ("1-9", "10-49", "50-249", "250+")

LEGAL_MINUTES_MONTHLY: dict[str, dict[str, dict[str, int]]] = {
    "safety_specialist": {
        "Az Tehlikeli": {"1-9": 120, "10-49": 240, "50-249": 480, "250+": 960},
        "Tehlikeli": {"1-9": 240, "10-49": 480, "50-249": 960, "250+": 1440},
        "Çok Tehlikeli": {"1-9": 480, "10-49": 960, "50-249": 1440, "250+": 1920},
    },
    "workplace_physician": {
        "Az Tehlikeli": {"1-9": 60, "10-49": 120, "50-249": 240, "250+": 480},
        "Tehlikeli": {"1-9": 120, "10-49": 240, "50-249": 480, "250+": 960},
        "Çok Tehlikeli": {"1-9": 240, "10-49": 480, "50-249": 960, "250+": 1440},
    },
    "other_health_personnel": {
        "Az Tehlikeli": {"1-9": 60, "10-49": 120, "50-249": 240, "250+": 480},
        "Tehlikeli": {"1-9": 120, "10-49": 240, "50-249": 480, "250+": 960},
        "Çok Tehlikeli": {"1-9": 240, "10-49": 480, "50-249": 960, "250+": 1440},
    },
}

# Uzman sertifika sınıfı — eşzamanlı işyeri üst sınırı (yönetmelik özeti)
SPECIALIST_FIRM_LIMITS = {"A": 20, "B": 10, "C": 5}

ROLE_LABELS = {
    "safety_specialist": "İSG Uzmanı",
    "workplace_physician": "İşyeri Hekimi",
    "other_health_personnel": "DSP",
}

HAZARD_ALIASES = {
    "az tehlikeli": "Az Tehlikeli",
    "tehlikeli": "Tehlikeli",
    "cok tehlikeli": "Çok Tehlikeli",
    "çok tehlikeli": "Çok Tehlikeli",
}


def normalize_hazard(hazard: str | None) -> str:
    raw = (hazard or "Tehlikeli").strip()
    key = raw.casefold().replace("ı", "i")
    return HAZARD_ALIASES.get(key, raw if raw in LEGAL_MINUTES_MONTHLY["safety_specialist"] else "Tehlikeli")


def employee_bracket(count: int) -> str:
    n = max(0, int(count or 0))
    if n <= 9:
        return "1-9"
    if n <= 49:
        return "10-49"
    if n <= 249:
        return "50-249"
    return "250+"


def compute_legal_required_minutes(
    hazard_class: str | None,
    employee_count: int,
    role: ProfessionalType | str,
) -> int:
    """İşyeri başına aylık mevzuat asgari dakika."""
    if isinstance(role, ProfessionalType):
        role_key = role.value
    else:
        role_key = str(role)
    table = LEGAL_MINUTES_MONTHLY.get(role_key)
    if not table:
        return 0
    hazard = normalize_hazard(hazard_class)
    bracket = employee_bracket(employee_count)
    return int(table.get(hazard, table.get("Tehlikeli", {})).get(bracket, 0))


def _capacity_status(required: int, actual: int) -> str:
    if required <= 0:
        return "unknown"
    ratio = actual / required if required else 1
    if ratio >= 0.8:
        return "ok"
    if ratio >= 0.5:
        return "warning"
    return "critical"


def build_capacity_overview(db: Session, osgb_id: int | None) -> dict:
    month_start, month_end = _month_bounds()
    period_label = month_start.strftime("%Y-%m")

    assign_q = select(WorkplaceAssignment).where(WorkplaceAssignment.status == AssignmentStatus.ACTIVE)
    if osgb_id:
        assign_q = assign_q.where(WorkplaceAssignment.osgb_id == osgb_id)
    assignments = list(db.scalars(assign_q).all())

    company_ids = {a.company_id for a in assignments}
    companies = {
        c.id: c for c in db.scalars(select(Company).where(Company.id.in_(company_ids or {0}))).all()
    } if company_ids else {}

    emp_counts: dict[int, int] = {}
    if company_ids:
        rows = db.execute(
            select(Employee.company_id, func.count())
            .where(Employee.company_id.in_(company_ids))
            .group_by(Employee.company_id)
        ).all()
        emp_counts = {int(cid): int(cnt) for cid, cnt in rows}

    pro_ids = {a.professional_id for a in assignments}
    pros = {
        p.id: p for p in db.scalars(select(IsgProfessional).where(IsgProfessional.id.in_(pro_ids or {0}))).all()
    } if pro_ids else {}

    firm_rows: list[dict] = []
    pro_load: dict[int, dict] = {}

    for a in assignments:
        company = companies.get(a.company_id)
        if not company:
            continue
        pro = pros.get(a.professional_id)
        emp = emp_counts.get(a.company_id, 0)
        hazard = normalize_hazard(company.hazard_class)
        role = a.professional_type.value if a.professional_type else "safety_specialist"
        legal = compute_legal_required_minutes(hazard, emp, role)
        stored = int(a.required_minutes_monthly or 0)
        visit_min, visit_count, _ = _visit_minutes(db, a.professional_id, a.company_id, month_start, month_end)
        actual = visit_min if visit_min > 0 else int(a.actual_minutes_monthly or 0)
        target = stored if stored > 0 else legal
        gap = target - actual
        stored_mismatch = stored > 0 and legal > 0 and abs(stored - legal) > max(30, legal * 0.15)

        firm_rows.append(
            {
                "assignment_id": a.id,
                "company_id": company.id,
                "company_name": company.name,
                "hazard_class": hazard,
                "employee_count": emp,
                "employee_bracket": employee_bracket(emp),
                "professional_id": a.professional_id,
                "professional_name": pro.full_name if pro else f"#{a.professional_id}",
                "professional_type": role,
                "role_label": ROLE_LABELS.get(role, role),
                "certificate_class": getattr(pro, "certificate_class", None) if pro else None,
                "legal_required_minutes": legal,
                "stored_required_minutes": stored,
                "planned_minutes": int(a.planned_minutes_monthly or 0),
                "actual_minutes": actual,
                "visit_count": visit_count,
                "gap_minutes": gap,
                "stored_mismatch": stored_mismatch,
                "status": _capacity_status(target, actual),
            }
        )

        bucket = pro_load.setdefault(
            a.professional_id,
            {
                "professional_id": a.professional_id,
                "full_name": pro.full_name if pro else f"#{a.professional_id}",
                "professional_type": pro.professional_type.value if pro and pro.professional_type else role,
                "certificate_class": getattr(pro, "certificate_class", None) if pro else None,
                "firm_count": 0,
                "required_total": 0,
                "legal_total": 0,
                "actual_total": 0,
            },
        )
        bucket["firm_count"] += 1
        bucket["required_total"] += target
        bucket["legal_total"] += legal
        bucket["actual_total"] += actual

    pro_rows: list[dict] = []
    for pid, row in pro_load.items():
        pro = pros.get(pid)
        ptype = row["professional_type"]
        firm_limit = None
        overload_firms = False
        if ptype == "safety_specialist" and row.get("certificate_class"):
            firm_limit = SPECIALIST_FIRM_LIMITS.get(str(row["certificate_class"]).upper())
            overload_firms = firm_limit is not None and row["firm_count"] > firm_limit
        req = row["required_total"]
        act = row["actual_total"]
        utilization = round(100 * act / req) if req > 0 else (100 if act == 0 else 0)
        pro_rows.append(
            {
                **row,
                "firm_limit": firm_limit,
                "overload_firms": overload_firms,
                "utilization_pct": utilization,
                "status": _capacity_status(req, act),
                "is_active": bool(pro.is_active) if pro else True,
            }
        )
    pro_rows.sort(key=lambda r: (-r["utilization_pct"], r["full_name"]))

    under_served = sum(1 for r in firm_rows if r["status"] == "critical")
    at_risk = sum(1 for r in firm_rows if r["status"] == "warning")
    mismatch = sum(1 for r in firm_rows if r["stored_mismatch"])
    overloaded = sum(1 for r in pro_rows if r["overload_firms"] or r["status"] == "critical")

    firm_rows.sort(key=lambda r: ({"critical": 0, "warning": 1, "ok": 2, "unknown": 3}[r["status"]], r["company_name"]))

    return {
        "osgb_id": osgb_id,
        "period": period_label,
        "period_start": month_start.isoformat(),
        "period_end": month_end.isoformat(),
        "legal_basis": "6331 / İSG Hizmetleri Yönetmeliği — işyeri asgari aylık süre tablosu (basitleştirilmiş)",
        "summary": {
            "assignments": len(firm_rows),
            "professionals": len(pro_rows),
            "under_served_firms": under_served,
            "at_risk_firms": at_risk,
            "stored_mismatch": mismatch,
            "overloaded_professionals": overloaded,
        },
        "firms": firm_rows,
        "professionals": pro_rows,
    }


def sync_assignment_required(db: Session, assignment: WorkplaceAssignment) -> int:
    company = db.get(Company, assignment.company_id)
    if not company:
        return 0
    emp = db.scalar(select(func.count()).select_from(Employee).where(Employee.company_id == company.id)) or 0
    legal = compute_legal_required_minutes(company.hazard_class, emp, assignment.professional_type)
    assignment.required_minutes_monthly = legal
    if not assignment.planned_minutes_monthly:
        assignment.planned_minutes_monthly = legal
    db.commit()
    db.refresh(assignment)
    return legal
