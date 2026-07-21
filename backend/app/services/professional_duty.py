"""Profesyonel (uzman/hekim/DSP) kişisel sorumluluk uyarı paneli.

Göreve dayalı işyerleri için:
- günü geçenler (overdue)
- yaklaşanlar (due_soon, ≤14 gün)
- yapılması gereken ama yapılmayanlar (missing)

OSGB Hizmet Denetimi checklist’leri ile aynı değerlendirme çekirdeğini kullanır.
İleride e-posta bildirimi bu payload üzerinden bağlanacak.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.company_access import assigned_company_ids, find_professional_for_user
from app.models.entities import (
    AnnualPlanItem,
    AnnualPlanStatus,
    AssignmentStatus,
    ChemicalProduct,
    Company,
    HealthRecord,
    RiskAssessment,
    RiskDof,
    User,
    UserRole,
    WorkplaceAssignment,
)
from app.services.osgb_oversight import (
    PHYSICIAN_CHECKS,
    SPECIALIST_CHECKS,
    _eval_physician_firm,
    _eval_specialist_firm,
    _month_bounds,
)

APPROACHING_DAYS = 14

MODULE_FOR_CHECK = {
    "saha_sure": "visits",
    "risk_degerlendirme": "risk",
    "risk_dof": "risk",
    "yillik_plan": "annual_plans",
    "egitim": "training",
    "olay_takip": "near_miss",
    "saglik_gozetim": "health",
    "muayene_gecikme": "health",
    "uygunluk": "health",
    "gorevlendirme": "assignments",
    "sistem": "dashboard",
    "sds_review": "sds",
}

MODULE_LABEL = {
    "visits": "Saha Takvimi",
    "risk": "Risk Analizi",
    "annual_plans": "Yıllık Plan",
    "training": "Eğitimler",
    "near_miss": "Ramak Kala",
    "accident": "İş Kazaları",
    "health": "Sağlık",
    "assignments": "Görevlendirmeler",
    "capa": "DÖF",
    "dashboard": "Ana Sayfa",
    "sds": "SDS / PKD",
}

ROLE_LABEL = {
    UserRole.SAFETY_SPECIALIST: "İş Güvenliği Uzmanı",
    UserRole.WORKPLACE_PHYSICIAN: "İşyeri Hekimi",
    UserRole.OTHER_HEALTH_PERSONNEL: "Diğer Sağlık Personeli",
}


def _alert(
    *,
    severity: str,
    kind: str,
    title: str,
    detail: str,
    company_id: int | None,
    company_name: str,
    check_code: str,
    due_date: date | None = None,
    legal: str | None = None,
) -> dict[str, Any]:
    module = MODULE_FOR_CHECK.get(check_code, "dashboard")
    days_left = None
    if due_date:
        days_left = (due_date - date.today()).days
    return {
        "severity": severity,  # overdue | due_soon | missing | done
        "kind": kind,
        "title": title,
        "detail": detail,
        "company_id": company_id,
        "company_name": company_name,
        "check_code": check_code,
        "legal": legal,
        "due_date": due_date.isoformat() if due_date else None,
        "days_left": days_left,
        "module": module,
        "module_label": MODULE_LABEL.get(module, module),
        "email_ready": True,
        "reportable": True,
    }


def build_my_duty_board(db: Session, user: User) -> dict[str, Any]:
    today = date.today()
    soon = today + timedelta(days=APPROACHING_DAYS)
    month_start, month_end = _month_bounds(today)
    year = today.year

    role = user.role
    if role not in (
        UserRole.SAFETY_SPECIALIST,
        UserRole.WORKPLACE_PHYSICIAN,
        UserRole.OTHER_HEALTH_PERSONNEL,
    ):
        return {
            "role": role.value,
            "supported": False,
            "message": "Bu panel uzman / hekim / DSP içindir.",
            "summary": {},
            "alerts": [],
        }

    pro = find_professional_for_user(db, user)
    company_ids = assigned_company_ids(db, user)
    companies = {
        c.id: c
        for c in db.scalars(select(Company).where(Company.id.in_(company_ids))).all()
    } if company_ids else {}

    alerts: list[dict[str, Any]] = []
    done: list[dict[str, Any]] = []

    if not company_ids:
        alerts.append(
            _alert(
                severity="overdue",
                kind="assignment",
                title="İşyeri görevlendirmesi yok",
                detail="Size atanmış aktif işyeri bulunamadı. OSGB yönetimi Görevlendirmeler’den firma bağlamalı; profesyonel e-postanız kullanıcı e-postanızla aynı olmalı.",
                company_id=None,
                company_name="—",
                check_code="gorevlendirme",
                legal="İSG Hizmetleri Yön. — işyerine uzman/hekim/DSP görevlendirme",
            )
        )
        return _pack(user, pro, company_ids, alerts, done, today)

    # Aktif görevlendirmeler
    assign_q = select(WorkplaceAssignment).where(
        WorkplaceAssignment.status == AssignmentStatus.ACTIVE,
        WorkplaceAssignment.company_id.in_(company_ids),
    )
    if pro:
        assign_q = assign_q.where(WorkplaceAssignment.professional_id == pro.id)
    assignments = list(db.scalars(assign_q).all())
    by_company = {a.company_id: a for a in assignments}

    is_specialist = role == UserRole.SAFETY_SPECIALIST

    for cid in company_ids:
        company = companies.get(cid)
        if not company:
            continue
        assignment = by_company.get(cid)
        if not assignment and pro:
            # Atama listesinde id var ama satır yoksa atlanmış say
            continue
        if not assignment:
            # company_id fallback (tek firma hesabı) — sanal atama yok, eksik saha uyarısı
            alerts.append(
                _alert(
                    severity="missing",
                    kind="assignment",
                    title="Görevlendirme kaydı eksik",
                    detail=f"{company.name} için aktif görevlendirme satırı bulunamadı.",
                    company_id=cid,
                    company_name=company.name,
                    check_code="gorevlendirme",
                )
            )
            continue

        if is_specialist:
            try:
                checks, _visits = _eval_specialist_firm(db, company, assignment, month_start, month_end, year)
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
                checks = []
                alerts.append(
                    _alert(
                        severity="missing",
                        kind="duty",
                        title="Kontrol hesaplanamadı",
                        detail=f"{company.name} için uzman kontrolleri şu an hesaplanamadı. Yenile’yi deneyin.",
                        company_id=cid,
                        company_name=company.name,
                        check_code="sistem",
                    )
                )
        else:
            try:
                checks, _visits = _eval_physician_firm(db, company, assignment, month_start, month_end)
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
                checks = []
                alerts.append(
                    _alert(
                        severity="missing",
                        kind="duty",
                        title="Kontrol hesaplanamadı",
                        detail=f"{company.name} için sağlık kontrolleri şu an hesaplanamadı. Yenile’yi deneyin.",
                        company_id=cid,
                        company_name=company.name,
                        check_code="saglik_gozetim",
                    )
                )

        for c in checks:
            code = c["code"]
            if c.get("passed"):
                done.append(
                    _alert(
                        severity="done",
                        kind="duty",
                        title=c["title"],
                        detail=c.get("detail") or "Bu dönem için tamamlandı / uygun.",
                        company_id=cid,
                        company_name=company.name,
                        check_code=code,
                        legal=c.get("legal"),
                    )
                )
                continue
            # Tarihli sinyaller ayrı toplanır; genel eksikler missing
            if code in ("risk_dof", "muayene_gecikme", "yillik_plan"):
                # detaylı tarihler aşağıda; yine de checklist eksikliği missing olarak kalsın eğer sayı yoksa
                meta = c.get("metric") or {}
                if code == "risk_dof" and meta.get("overdue_dof", 0) > 0:
                    continue  # tarihli alertlerde
                if code == "muayene_gecikme" and (meta.get("overdue", 0) > 0 or meta.get("due_soon", 0) > 0):
                    continue
            alerts.append(
                _alert(
                    severity="missing",
                    kind="duty",
                    title=c["title"],
                    detail=c["detail"],
                    company_id=cid,
                    company_name=company.name,
                    check_code=code,
                    legal=c.get("legal"),
                )
            )

        # --- Tarihli uyarılar (uzman) ---
        if is_specialist:
            try:
                dofs = list(
                    db.scalars(
                        select(RiskDof)
                        .join(RiskAssessment, RiskDof.risk_id == RiskAssessment.id)
                        .where(
                            RiskAssessment.company_id == cid,
                            RiskDof.is_completed.is_(False),
                            RiskDof.term_date.is_not(None),
                        )
                    ).all()
                )
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
                dofs = []
            for d in dofs:
                term = d.term_date
                if not term:
                    continue
                if term < today:
                    sev = "overdue"
                elif term <= soon:
                    sev = "due_soon"
                else:
                    continue
                alerts.append(
                    _alert(
                        severity=sev,
                        kind="dof",
                        title=f"Risk DÖF termin — {d.dof_code}",
                        detail=(d.description or "")[:180],
                        company_id=cid,
                        company_name=company.name,
                        check_code="risk_dof",
                        due_date=term,
                        legal="6331 md.10 — önlem termin takibi",
                    )
                )

            try:
                plans = list(
                    db.scalars(
                        select(AnnualPlanItem).where(
                            AnnualPlanItem.company_id == cid,
                            AnnualPlanItem.year == year,
                            AnnualPlanItem.deleted_at.is_(None),
                            AnnualPlanItem.status.notin_(
                                [
                                    AnnualPlanStatus.COMPLETED.value,
                                    AnnualPlanStatus.CANCELLED.value,
                                ]
                            ),
                        )
                    ).all()
                )
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
                plans = []
            for p in plans:
                # Hedef tarih yoksa ay sonu varsay
                if p.target_date:
                    due = p.target_date
                else:
                    # ayın son gününe yaklaştır
                    m = max(1, min(12, int(p.month or 1)))
                    if m == 12:
                        due = date(year, 12, 31)
                    else:
                        due = date(year, m + 1, 1) - timedelta(days=1)
                if p.status == AnnualPlanStatus.DELAYED or due < today:
                    sev = "overdue"
                elif due <= soon:
                    sev = "due_soon"
                else:
                    continue
                alerts.append(
                    _alert(
                        severity=sev,
                        kind="annual_plan",
                        title=f"Yıllık plan — {p.activity}",
                        detail=p.description or f"{year}/{p.month}. ay faaliyeti",
                        company_id=cid,
                        company_name=company.name,
                        check_code="yillik_plan",
                        due_date=due,
                        legal="İSG Hizmetleri Yön. — yıllık çalışma planı",
                    )
                )

            # 0.9.122 — SDS/PKD gözden geçirme terminleri
            try:
                chemicals = list(
                    db.scalars(
                        select(ChemicalProduct).where(
                            ChemicalProduct.company_id == cid,
                            ChemicalProduct.is_active.is_(True),
                            ChemicalProduct.next_review_date.is_not(None),
                        )
                    ).all()
                )
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
                chemicals = []
            for chem in chemicals:
                due = chem.next_review_date
                if not due:
                    continue
                if due < today:
                    sev = "overdue"
                elif due <= soon:
                    sev = "due_soon"
                else:
                    continue
                sds_flag = "SDS dosyası var" if chem.has_sds_file else "SDS dosyası eksik"
                alerts.append(
                    _alert(
                        severity=sev,
                        kind="sds",
                        title=f"SDS gözden geçirme — {chem.product_name}",
                        detail=f"{sds_flag}"
                        + (f" · CAS {chem.cas_number}" if chem.cas_number else ""),
                        company_id=cid,
                        company_name=company.name,
                        check_code="sds_review",
                        due_date=due,
                        legal="KKDİY / SDS — kimyasal güvenlik bilgi formu periyodu",
                    )
                )

        # --- Tarihli uyarılar (hekim/DSP) ---
        if not is_specialist:
            try:
                health_rows = list(
                    db.scalars(
                        select(HealthRecord).where(
                            HealthRecord.company_id == cid,
                            HealthRecord.deleted_at.is_(None),
                            HealthRecord.next_examination_date.is_not(None),
                        )
                    ).all()
                )
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
                health_rows = []
            for h in health_rows:
                nxt = h.next_examination_date
                if not nxt:
                    continue
                if nxt < today:
                    sev = "overdue"
                elif nxt <= soon:
                    sev = "due_soon"
                else:
                    continue
                alerts.append(
                    _alert(
                        severity=sev,
                        kind="exam",
                        title="Periyodik muayene",
                        detail=f"Sonraki muayene: {nxt.isoformat()}",
                        company_id=cid,
                        company_name=company.name,
                        check_code="muayene_gecikme",
                        due_date=nxt,
                        legal="6331 md.15 — sağlık gözetimi periyodu",
                    )
                )

    return _pack(user, pro, company_ids, alerts, done, today)


def _pack(
    user: User,
    pro,
    company_ids: list[int],
    alerts: list[dict],
    done: list[dict],
    today: date,
) -> dict[str, Any]:
    # Öncelik: overdue → due_soon → missing; aynı grupta gün sırası
    order = {"overdue": 0, "due_soon": 1, "missing": 2}

    def sort_key(a: dict):
        d = a.get("due_date") or "9999-99-99"
        return (order.get(a["severity"], 9), d, a.get("company_name") or "")

    alerts.sort(key=sort_key)
    done_sorted = sorted(done, key=lambda a: (a.get("company_name") or "", a.get("title") or ""))

    overdue = [a for a in alerts if a["severity"] == "overdue"]
    due_soon = [a for a in alerts if a["severity"] == "due_soon"]
    missing = [a for a in alerts if a["severity"] == "missing"]

    catalog = (
        SPECIALIST_CHECKS
        if user.role == UserRole.SAFETY_SPECIALIST
        else PHYSICIAN_CHECKS
    )
    checks_total = len(done_sorted) + len(missing)
    # missing burada dönem checklist; overdue/due_soon ayrı (termin)
    completion_pct = round(100 * len(done_sorted) / checks_total) if checks_total else 100

    return {
        "supported": True,
        "role": user.role.value,
        "role_label": ROLE_LABEL.get(user.role, user.role.value),
        "full_name": user.full_name,
        "professional": (
            {
                "id": pro.id,
                "full_name": pro.full_name,
                "certificate_class": pro.certificate_class,
                "type": pro.professional_type.value,
            }
            if pro
            else None
        ),
        "period": {
            "today": today.isoformat(),
            "approaching_days": APPROACHING_DAYS,
        },
        "workplace_count": len(company_ids),
        "workplace_ids": company_ids,
        "check_catalog": catalog,
        "summary": {
            "overdue": len(overdue),
            "due_soon": len(due_soon),
            "missing": len(missing),
            "done": len(done_sorted),
            "total": len(alerts),
            "completion_pct": completion_pct,
        },
        "alerts": {
            "overdue": overdue,
            "due_soon": due_soon,
            "missing": missing,
            "done": done_sorted,
            "all": alerts,
        },
        "email_notifications": {
            "enabled": False,
            "planned": True,
            "note": "İleride OSGB yönetimi onayı ile yaklaşan/geçen faaliyetler personele e-posta ile bildirilecek.",
        },
    }


def format_duty_report_txt(board: dict[str, Any]) -> str:
    """Ana sayfa durum özeti — profesyonelin indirebileceği metin rapor."""
    sm = board.get("summary") or {}
    alerts = board.get("alerts") or {}
    lines = [
        "İSG Suite OSGB — Profesyonel Görev Durum Raporu",
        f"Ad: {board.get('full_name') or '—'}",
        f"Rol: {board.get('role_label') or board.get('role') or '—'}",
        f"Tarih: {(board.get('period') or {}).get('today') or date.today().isoformat()}",
        f"İşyeri sayısı: {board.get('workplace_count', 0)}",
        f"Tamamlanan: {sm.get('done', 0)} · Yapılmayan: {sm.get('missing', 0)} · "
        f"Yaklaşan: {sm.get('due_soon', 0)} · Günü geçen: {sm.get('overdue', 0)} · "
        f"Tamamlanma %{sm.get('completion_pct', 0)}",
        "-" * 72,
    ]

    def section(title: str, items: list[dict]):
        lines.append("")
        lines.append(title)
        lines.append("-" * len(title))
        if not items:
            lines.append("  (kayıt yok)")
            return
        for a in items:
            due = f" · Termin: {a['due_date']}" if a.get("due_date") else ""
            lines.append(f"  • [{a.get('company_name') or '—'}] {a.get('title')}{due}")
            if a.get("detail"):
                lines.append(f"      {a['detail']}")

    section("GÜNÜ GEÇENLER", alerts.get("overdue") or [])
    section("YAKLAŞANLAR (14 gün)", alerts.get("due_soon") or [])
    section("YAPILMAYANLAR", alerts.get("missing") or [])
    section("YAPILANLAR / UYGUN", alerts.get("done") or [])
    lines.append("")
    lines.append("Rapor, profesyonelin ana sayfa sorumluluk panelinden üretilmiştir.")
    return "\n".join(lines) + "\n"
