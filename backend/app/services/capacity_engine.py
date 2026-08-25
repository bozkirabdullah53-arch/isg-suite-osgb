"""6331 / İSG Hizmetleri Yönetmeliği kapasite motoru — mevzuat asgari süre vs fiili yük."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date
import re
import unicodedata

from sqlalchemy import or_, select
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
from app.services.training_nace_classification import resolve_exact_nace

# Merkezî iş kuralı: asgari hizmet süresi aktif çalışan başına aylık dakika olarak
# tutulur. Bütün API, rapor ve ekranlar bu tablodan hesaplama alır.
SERVICE_MINUTES_PER_EMPLOYEE: dict[str, dict[str, int]] = {
    "Az Tehlikeli": {
        "safety_specialist": 10,
        "workplace_physician": 5,
        # Mevcut DSP ekranlarını bozmamak için hekim kuralıyla aynı kapsamda tutulur.
        "other_health_personnel": 5,
    },
    "Tehlikeli": {
        "safety_specialist": 20,
        "workplace_physician": 10,
        "other_health_personnel": 10,
    },
    "Çok Tehlikeli": {
        "safety_specialist": 40,
        "workplace_physician": 15,
        "other_health_personnel": 15,
    },
}

# Dışarıdan eski sabit adını kullanan çağrılar için uyumluluk alias'ı.
LEGAL_MINUTES_MONTHLY = SERVICE_MINUTES_PER_EMPLOYEE

SERVICE_ROLE_KEYS = (
    "safety_specialist",
    "workplace_physician",
    "other_health_personnel",
)
CAPACITY_ROLE_KEYS = ("safety_specialist", "workplace_physician")

# Tam süreli normal çalışma kapasitesi raporlama tabanıdır. Bu değer bir
# görevlendirmeyi engelleyen sert bir limit değildir; OSGB yöneticisine
# planlanan/gerçekleşen yükün normal tam süreli kapasiteye göre durumunu
# gösterir. Yıllık fazla çalışma limiti aylık kapasiteye otomatik eklenmez.
NORMAL_FULL_TIME_MONTHLY_MINUTES = 11_700
NORMAL_FULL_TIME_MONTHLY_HOURS = 195
NORMAL_WEEKLY_WORKING_HOURS = 45
ANNUAL_OVERTIME_HOURS = 270

# Tam süreli görevlendirme eşiği, kişi başı aylık asgari dakika kuralından
# ayrıdır. Eşik aşılınca tam süreli profesyonel sayısı ve kalan çalışanlar için
# ayrıca kısmi süreli dakika ihtiyacı birlikte raporlanır.
FULL_TIME_EMPLOYEE_THRESHOLDS: dict[str, dict[str, int]] = {
    "safety_specialist": {
        "Az Tehlikeli": 1_000,
        "Tehlikeli": 500,
        "Çok Tehlikeli": 250,
    },
    "workplace_physician": {
        "Az Tehlikeli": 2_000,
        "Tehlikeli": 1_000,
        "Çok Tehlikeli": 750,
    },
}

_BRACKETS = ("1-9", "10-49", "50-249", "250+")

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


def normalize_hazard(hazard: str | None) -> str | None:
    """Normalize a known hazard class without guessing an unknown value."""
    raw = str(hazard or "").strip()
    if not raw:
        return None
    key = raw.casefold().replace("ı", "i")
    return HAZARD_ALIASES.get(key)


def normalize_employee_count(count: object) -> int:
    """Return a safe non-negative employee count for all calculations."""
    try:
        value = int(count or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, value)


def _normalize_employee_identity(value: object) -> str:
    """Normalize the personnel identity the same way for Turkish casing/spacing."""
    compact = " ".join(str(value or "").split()).casefold().replace("ı", "i")
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", compact)
        if not unicodedata.combining(char)
    )


def count_active_employees(employees: Iterable[Employee]) -> int:
    """Count the existing active population once per business identity.

    The personnel importer already matches by national-id or normalized name;
    capacity follows that same identity rule so accidental duplicate rows cannot
    inflate legally required service minutes.
    """
    identities: set[tuple[str, str]] = set()
    for employee in employees:
        if not bool(getattr(employee, "is_active", False)):
            continue
        national_id = _normalize_employee_identity(getattr(employee, "national_id_masked", None))
        if national_id:
            identity = ("national_id", national_id)
        else:
            name = _normalize_employee_identity(getattr(employee, "full_name", None))
            identity = ("name", name) if name else ("record", str(getattr(employee, "id", id(employee))))
        identities.add(identity)
    return len(identities)


def minutes_to_display(total_minutes: object) -> dict[str, int | str]:
    """Convert authoritative minutes to display-only hours and remaining minutes."""
    total = normalize_employee_count(total_minutes)
    hours, remaining = divmod(total, 60)
    return {
        "total_minutes": total,
        "hours": hours,
        "remaining_minutes": remaining,
        "equivalent": f"{hours} saat {remaining:02d} dakika / ay",
    }


def _nace_from_sgk_registry(value: object) -> str | None:
    """Read the existing six-digit NACE identity embedded in an SGK number."""
    compact = re.sub(r"\D", "", str(value or "").strip())
    if re.fullmatch(r"\d{6}", compact):
        return f"{compact[:2]}.{compact[2:4]}.{compact[4:]}"
    if re.fullmatch(r"\d{4}", compact):
        return f"{compact[:2]}.{compact[2:]}"
    if len(compact) not in {23, 26, 27}:
        return None
    nace_digits = compact[1:7]
    if not re.fullmatch(r"\d{6}", nace_digits) or nace_digits == "000000":
        return None
    return f"{nace_digits[:2]}.{nace_digits[2:4]}.{nace_digits[4:]}"


def _exact_nace(value: object):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return resolve_exact_nace(raw)
    except ValueError:
        return None


def resolve_company_service_context(company: Company) -> dict[str, str | None]:
    """Resolve NACE → hazard from the existing workplace identity.

    The company card remains the source of stored data. When a valid exact NACE
    exists, its catalog hazard class wins; otherwise the existing company hazard
    value is used. Unknown values remain unknown and never fall back to
    ``Tehlikeli``.
    """
    direct_nace = str(getattr(company, "nace_code", None) or "").strip() or None
    candidates: list[tuple[str, str]] = []
    if direct_nace:
        candidates.append((direct_nace, "company_nace"))
    sgk_nace = _nace_from_sgk_registry(getattr(company, "sgk_registry_no", None))
    if sgk_nace and sgk_nace != direct_nace:
        candidates.append((sgk_nace, "sgk_registry_nace"))

    for candidate, source in candidates:
        classification = _exact_nace(candidate)
        hazard = normalize_hazard(getattr(classification, "hazard_class", None)) if classification else None
        if hazard:
            return {
                "nace_code": getattr(classification, "nace_code", None) or candidate,
                "nace_source": source,
                "hazard_class": hazard,
                "hazard_source": "nace_catalog",
                "warning": None,
            }

    hazard = normalize_hazard(getattr(company, "hazard_class", None))
    if hazard:
        return {
            "nace_code": direct_nace or sgk_nace,
            "nace_source": "company" if direct_nace else ("sgk_registry_nace" if sgk_nace else None),
            "hazard_class": hazard,
            "hazard_source": "company_hazard_class",
            "warning": None,
        }
    return {
        "nace_code": direct_nace or sgk_nace,
        "nace_source": "company" if direct_nace else ("sgk_registry_nace" if sgk_nace else None),
        "hazard_class": None,
        "hazard_source": None,
        "warning": "Tehlike sınıfı NACE kataloğundan veya işyeri kartından belirlenemedi; süre hesaplanmadı.",
    }


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
    """Return active-employee-based monthly minutes for one professional role."""
    if isinstance(role, ProfessionalType):
        role_key = role.value
    else:
        role_key = str(role)
    hazard = normalize_hazard(hazard_class)
    if not hazard or role_key not in SERVICE_ROLE_KEYS:
        return 0
    per_employee = int(SERVICE_MINUTES_PER_EMPLOYEE[hazard].get(role_key, 0))
    return normalize_employee_count(employee_count) * per_employee


def build_service_requirement_summary(
    hazard_class: str | None,
    employee_count: int,
    *,
    nace_code: str | None = None,
    nace_source: str | None = None,
    hazard_source: str | None = None,
    warning: str | None = None,
) -> dict:
    """Build the authoritative workplace-level monthly OHS service summary."""
    count = normalize_employee_count(employee_count)
    hazard = normalize_hazard(hazard_class)
    known_hazard = bool(hazard)
    role_rows: dict[str, dict] = {}
    for role in SERVICE_ROLE_KEYS:
        per_employee = int(SERVICE_MINUTES_PER_EMPLOYEE.get(hazard or "", {}).get(role, 0))
        total = count * per_employee if known_hazard else 0
        display = minutes_to_display(total)
        full_time_rule = _full_time_rule(hazard, count, role, per_employee)
        role_rows[role] = {
            "role": role,
            "minutes_per_employee": per_employee,
            "calculation": f"{count} × {per_employee}" if known_hazard else None,
            "required_minutes": display["total_minutes"],
            "hours": display["hours"],
            "remaining_minutes": display["remaining_minutes"],
            "equivalent": display["equivalent"] if known_hazard else "Hesaplanamadı",
            **full_time_rule,
        }

    return {
        "nace_code": nace_code,
        "nace_source": nace_source,
        "hazard_class": hazard,
        "hazard_source": hazard_source,
        "hazard_known": known_hazard,
        "hazard_warning": warning if warning else (None if known_hazard else "Tehlike sınıfı bilinmediği için asgari süre hesaplanmadı."),
        "employee_count": count,
        "roles": role_rows,
    }


def compute_company_service_requirements(company: Company, employee_count: int) -> dict:
    """Resolve one existing workplace identity and calculate both required roles."""
    context = resolve_company_service_context(company)
    return build_service_requirement_summary(
        context.get("hazard_class"),
        employee_count,
        nace_code=context.get("nace_code"),
        nace_source=context.get("nace_source"),
        hazard_source=context.get("hazard_source"),
        warning=context.get("warning"),
    )


def _full_time_rule(hazard: str | None, employee_count: int, role: str, per_employee: int) -> dict:
    """Return full-time trigger information without changing the minute target."""
    threshold = int(FULL_TIME_EMPLOYEE_THRESHOLDS.get(role, {}).get(hazard or "", 0) or 0)
    if threshold <= 0:
        return {
            "full_time_threshold_employees": None,
            "full_time_units": 0,
            "full_time_remainder_employees": 0,
            "full_time_remainder_minutes": 0,
            "full_time_triggered": False,
        }
    units, remainder = divmod(normalize_employee_count(employee_count), threshold)
    return {
        "full_time_threshold_employees": threshold,
        "full_time_units": units,
        "full_time_remainder_employees": remainder,
        "full_time_remainder_minutes": remainder * max(0, int(per_employee or 0)),
        "full_time_triggered": units > 0,
    }


def _capacity_status(required: int, actual: int) -> str:
    if required <= 0:
        return "unknown"
    ratio = actual / required if required else 1
    if ratio >= 0.8:
        return "ok"
    if ratio >= 0.5:
        return "warning"
    return "critical"


def build_capacity_overview(
    db: Session,
    osgb_id: int | None,
    *,
    professional_id: int | None = None,
) -> dict:
    """Build the current monthly capacity view.

    ``professional_id`` is an optional server-side scope used by the personal
    specialist/physician panel. The existing OSGB view remains unchanged when
    it is omitted; when supplied, both assignments and workplaces are limited
    to that professional's own records.
    """
    month_start, month_end = _month_bounds()
    period_label = month_start.strftime("%Y-%m")

    assign_q = select(WorkplaceAssignment).where(WorkplaceAssignment.status == AssignmentStatus.ACTIVE)
    if osgb_id is not None:
        assign_q = assign_q.where(WorkplaceAssignment.osgb_id == osgb_id)
    if professional_id is not None:
        assign_q = assign_q.where(WorkplaceAssignment.professional_id == professional_id)
    assignments = list(db.scalars(assign_q).all())

    assigned_company_ids = {a.company_id for a in assignments}
    if professional_id is not None:
        # Kişisel panelde OSGB'nin diğer firmalarının varlığını bile
        # göstermemek için işyeri kapsamını görevlendirme üzerinden daralt.
        company_scope = Company.id.in_(assigned_company_ids or {0})
    else:
        company_scope = or_(Company.is_active.is_(True), Company.id.in_(assigned_company_ids or {0}))
    if osgb_id is not None and professional_id is None:
        company_scope = or_(Company.osgb_id == osgb_id, Company.id.in_(assigned_company_ids or {0}))
    companies = {
        c.id: c
        for c in db.scalars(select(Company).where(company_scope).order_by(Company.name)).all()
    }
    company_ids = set(companies)

    emp_counts: dict[int, int] = {}
    if company_ids:
        active_employees = list(
            db.scalars(
                select(Employee).where(
                    Employee.company_id.in_(company_ids),
                    Employee.is_active.is_(True),
                )
            ).all()
        )
        employees_by_company: dict[int, list[Employee]] = {}
        for employee in active_employees:
            employees_by_company.setdefault(employee.company_id, []).append(employee)
        emp_counts = {
            company_id: count_active_employees(rows)
            for company_id, rows in employees_by_company.items()
        }

    pro_ids = {a.professional_id for a in assignments}
    if professional_id is None:
        pro_scope = select(IsgProfessional.id).where(IsgProfessional.is_active.is_(True))
        if osgb_id is not None:
            pro_scope = pro_scope.where(IsgProfessional.osgb_id == osgb_id)
        pro_ids.update(db.scalars(pro_scope).all())
    elif professional_id is not None:
        pro_ids.add(professional_id)
    pros = {
        p.id: p for p in db.scalars(select(IsgProfessional).where(IsgProfessional.id.in_(pro_ids or {0}))).all()
    } if pro_ids else {}

    workplace_rows: list[dict] = []
    for company in companies.values():
        emp = emp_counts.get(company.id, 0)
        requirements = compute_company_service_requirements(company, emp)
        workplace_rows.append(
            {
                "company_id": company.id,
                "company_name": company.name,
                "nace_code": requirements["nace_code"],
                "nace_source": requirements["nace_source"],
                "hazard_class": requirements["hazard_class"],
                "hazard_source": requirements["hazard_source"],
                "hazard_known": requirements["hazard_known"],
                "hazard_warning": requirements["hazard_warning"],
                "employee_count": requirements["employee_count"],
                "specialist_requirement": requirements["roles"]["safety_specialist"],
                "physician_requirement": requirements["roles"]["workplace_physician"],
                "service_requirements": requirements,
            }
        )

    firm_rows: list[dict] = []
    pro_load: dict[int, dict] = {}

    for a in assignments:
        company = companies.get(a.company_id)
        if not company:
            continue
        pro = pros.get(a.professional_id)
        emp = emp_counts.get(a.company_id, 0)
        role = a.professional_type.value if a.professional_type else "safety_specialist"
        requirements = compute_company_service_requirements(company, emp)
        role_requirement = requirements["roles"].get(role) or {
            "required_minutes": 0,
            "minutes_per_employee": 0,
            "hours": 0,
            "remaining_minutes": 0,
            "equivalent": "Hesaplanamadı",
        }
        legal = int(role_requirement["required_minutes"] or 0)
        stored = normalize_employee_count(a.required_minutes_monthly)
        visit_min, visit_count, _ = _visit_minutes(db, a.professional_id, a.company_id, month_start, month_end)
        actual = normalize_employee_count(visit_min if visit_min > 0 else a.actual_minutes_monthly)
        # Zorunlu süre backend hesabıdır; eski kayıtlı değer yalnızca uyumsuzluk
        # göstergesi olarak tutulur ve hedefi hiçbir zaman geçersiz kılmaz.
        target = legal
        gap = target - actual
        planned = normalize_employee_count(a.planned_minutes_monthly)
        remaining = max(target - actual, 0)
        surplus = max(actual - target, 0)
        completion_pct = round(100 * actual / target) if target > 0 else (100 if actual == 0 else 0)
        stored_mismatch = stored != legal

        firm_rows.append(
            {
                "assignment_id": a.id,
                "company_id": company.id,
                "company_name": company.name,
                "nace_code": requirements["nace_code"],
                "hazard_class": requirements["hazard_class"],
                "hazard_source": requirements["hazard_source"],
                "hazard_warning": requirements["hazard_warning"],
                "hazard_known": requirements["hazard_known"],
                "employee_count": emp,
                "employee_bracket": employee_bracket(emp),
                "professional_id": a.professional_id,
                "professional_name": pro.full_name if pro else f"#{a.professional_id}",
                "professional_type": role,
                "role_label": ROLE_LABELS.get(role, role),
                "certificate_class": getattr(pro, "certificate_class", None) if pro else None,
                "legal_required_minutes": legal,
                "stored_required_minutes": stored,
                "minutes_per_employee": role_requirement["minutes_per_employee"],
                "required_hours": role_requirement["hours"],
                "required_remaining_minutes": role_requirement["remaining_minutes"],
                "required_equivalent": role_requirement["equivalent"],
                "planned_minutes": planned,
                "actual_minutes": actual,
                "visit_count": visit_count,
                "gap_minutes": gap,
                "remaining_minutes": remaining,
                "surplus_minutes": surplus,
                "completion_pct": completion_pct,
                "stored_mismatch": stored_mismatch,
                "status": _capacity_status(target, actual),
                "service_requirement": requirements,
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
                "planned_total": 0,
                "actual_total": 0,
                "remaining_total": 0,
                "surplus_total": 0,
            },
        )
        bucket["firm_count"] += 1
        bucket["required_total"] += target
        bucket["legal_total"] += legal
        bucket["planned_total"] += planned
        bucket["actual_total"] += actual
        bucket["remaining_total"] += remaining
        bucket["surplus_total"] += surplus

    # Aktif görevlendirmesi olmayan uzman/hekim de OSGB yöneticisinin toplam
    # kapasite görünümünde yer alır; böylece 11.700 dakikalık boş kapasite
    # kaybolmaz. Kişisel panelde de eşleşen profesyonel boş olarak gösterilir.
    for pid, pro in pros.items():
        pro_load.setdefault(
            pid,
            {
                "professional_id": pid,
                "full_name": pro.full_name,
                "professional_type": pro.professional_type.value if pro.professional_type else "safety_specialist",
                "certificate_class": getattr(pro, "certificate_class", None),
                "firm_count": 0,
                "required_total": 0,
                "legal_total": 0,
                "planned_total": 0,
                "actual_total": 0,
                "remaining_total": 0,
                "surplus_total": 0,
            },
        )

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
        planned = row["planned_total"]
        capacity_applicable = ptype in CAPACITY_ROLE_KEYS
        capacity_remaining = max(NORMAL_FULL_TIME_MONTHLY_MINUTES - planned, 0) if capacity_applicable else None
        actual_capacity_remaining = max(NORMAL_FULL_TIME_MONTHLY_MINUTES - act, 0) if capacity_applicable else None
        capacity_utilization = round(100 * planned / NORMAL_FULL_TIME_MONTHLY_MINUTES) if capacity_applicable else None
        actual_capacity_utilization = round(100 * act / NORMAL_FULL_TIME_MONTHLY_MINUTES) if capacity_applicable else None
        capacity_overflow = max(planned - NORMAL_FULL_TIME_MONTHLY_MINUTES, 0) if capacity_applicable else 0
        pro_rows.append(
            {
                **row,
                "role_label": ROLE_LABELS.get(ptype, ptype),
                "firm_limit": firm_limit,
                "overload_firms": overload_firms,
                "utilization_pct": utilization,
                "completion_pct": utilization,
                "normal_capacity_minutes_monthly": NORMAL_FULL_TIME_MONTHLY_MINUTES if capacity_applicable else None,
                "normal_capacity_hours_monthly": NORMAL_FULL_TIME_MONTHLY_HOURS if capacity_applicable else None,
                "capacity_remaining_minutes": capacity_remaining,
                "actual_capacity_remaining_minutes": actual_capacity_remaining,
                "capacity_utilization_pct": capacity_utilization,
                "actual_capacity_utilization_pct": actual_capacity_utilization,
                "capacity_overflow_minutes": capacity_overflow,
                "capacity_overloaded": capacity_overflow > 0,
                "status": _capacity_status(req, act),
                "is_active": bool(pro.is_active) if pro else True,
            }
        )
    pro_rows.sort(key=lambda r: (-r["utilization_pct"], r["full_name"]))

    under_served = sum(1 for r in firm_rows if r["status"] == "critical")
    at_risk = sum(1 for r in firm_rows if r["status"] == "warning")
    mismatch = sum(1 for r in firm_rows if r["stored_mismatch"])
    overloaded = sum(1 for r in pro_rows if r["overload_firms"] or r["status"] == "critical")
    capacity_overloaded = sum(1 for r in pro_rows if r["capacity_overloaded"])

    firm_rows.sort(key=lambda r: ({"critical": 0, "warning": 1, "ok": 2, "unknown": 3}[r["status"]], r["company_name"]))
    workplace_rows.sort(key=lambda r: r["company_name"])

    return {
        "osgb_id": osgb_id,
        "period": period_label,
        "period_start": month_start.isoformat(),
        "period_end": month_end.isoformat(),
        "legal_basis": "6331 / İSG Hizmetleri Yönetmeliği — aktif çalışan başına aylık asgari dakika kuralları",
        "summary": {
            "assignments": len(firm_rows),
            "professionals": len(pro_rows),
            "workplaces": len(workplace_rows),
            "under_served_firms": under_served,
            "at_risk_firms": at_risk,
            "stored_mismatch": mismatch,
            "overloaded_professionals": overloaded,
            "capacity_overloaded_professionals": capacity_overloaded,
            "unknown_hazard_workplaces": sum(1 for r in workplace_rows if not r["hazard_known"]),
            "required_minutes_total": sum(r["legal_required_minutes"] for r in firm_rows),
            "planned_minutes_total": sum(r["planned_minutes"] for r in firm_rows),
            "actual_minutes_total": sum(r["actual_minutes"] for r in firm_rows),
            "remaining_minutes_total": sum(r["remaining_minutes"] for r in firm_rows),
            "surplus_minutes_total": sum(r["surplus_minutes"] for r in firm_rows),
            "normal_capacity_minutes_total": sum(
                r["normal_capacity_minutes_monthly"] or 0 for r in pro_rows
            ),
        },
        "workplaces": workplace_rows,
        "firms": firm_rows,
        "professionals": pro_rows,
        "capacity_basis": {
            "normal_full_time_monthly_minutes": NORMAL_FULL_TIME_MONTHLY_MINUTES,
            "normal_full_time_monthly_hours": NORMAL_FULL_TIME_MONTHLY_HOURS,
            "normal_weekly_working_hours": NORMAL_WEEKLY_WORKING_HOURS,
            "annual_overtime_hours": ANNUAL_OVERTIME_HOURS,
            "overtime_added_to_monthly_capacity": False,
            "note": "11.700 dakika / 195 saat normal tam süreli aylık kapasite raporlama tabanıdır; yıllık 270 saat fazla çalışma aylık sabit kapasiteye eklenmez.",
            "full_time_external_work_note": "Tam süreli görevlendirilen uzman/hekim için tam gün çalıştığı işyeri dışında fazla çalışma kuralı ayrıca dikkate alınmalıdır.",
        },
        "full_time_employee_thresholds": FULL_TIME_EMPLOYEE_THRESHOLDS,
    }


def sync_company_service_requirements(
    db: Session,
    company_id: int,
    *,
    commit: bool = False,
) -> dict | None:
    """Recalculate every active assignment for one existing workplace.

    The helper deliberately flushes pending employee/company changes before the
    count. This lets create, deactivate, update and import endpoints share one
    authoritative recalculation path without introducing a second data model.
    """
    db.flush()
    company = db.get(Company, company_id)
    if not company:
        return None
    employees = list(
        db.scalars(
            select(Employee).where(
                Employee.company_id == company.id,
                Employee.is_active.is_(True),
            )
        ).all()
    )
    employee_count = count_active_employees(employees)
    requirements = compute_company_service_requirements(company, employee_count)
    assignments = list(
        db.scalars(
            select(WorkplaceAssignment).where(
                WorkplaceAssignment.company_id == company.id,
                WorkplaceAssignment.status == AssignmentStatus.ACTIVE,
            )
        ).all()
    )
    for assignment in assignments:
        role = assignment.professional_type.value if assignment.professional_type else "safety_specialist"
        required = int(requirements["roles"].get(role, {}).get("required_minutes", 0) or 0)
        assignment.required_minutes_monthly = required
        if not assignment.planned_minutes_monthly:
            assignment.planned_minutes_monthly = required
    db.flush()
    if commit:
        db.commit()
        db.refresh(company)
    return requirements


def sync_assignment_required(
    db: Session,
    assignment: WorkplaceAssignment,
    *,
    commit: bool = True,
) -> int:
    """Backward-compatible single-assignment wrapper around the central sync."""
    requirements = sync_company_service_requirements(db, assignment.company_id, commit=False)
    if not requirements:
        return 0
    role = assignment.professional_type.value if assignment.professional_type else "safety_specialist"
    required = int(requirements["roles"].get(role, {}).get("required_minutes", 0) or 0)
    assignment.required_minutes_monthly = required
    if not assignment.planned_minutes_monthly:
        assignment.planned_minutes_monthly = required
    db.flush()
    if commit:
        db.commit()
        db.refresh(assignment)
    return required
