"""İşyeri Durum Merkezi — mevcut modüllerden salt okunur, tenant-kapsamlı özet.

Bu servis yeni bir kayıt kaynağı oluşturmaz. Üretimdeki modül tablolarını tek bir
kararlı sözleşmede birleştirir. Sağlık verileri yalnız anonim toplamlar olarak
döner; çalışan, tanı, tetkik ve hekim notları bu sözleşmeye dahil edilmez.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.entities import (
    AnnualPlanItem,
    AnnualPlanStatus,
    DocumentCategory,
    DocumentRecord,
    EmergencyPlan,
    HealthRecord,
    IncidentDof,
    IncidentEvent,
    Notification,
    PeriodicControl,
    RiskAssessment,
    RiskDof,
    TrainingSession,
    TrainingStatus,
    UserRole,
)
from app.services.company_overview import build_company_overview


STATUS_LABELS = {
    "completed": "Tamamlandı",
    "missing": "Eksik",
    "attention": "Dikkat",
    "due_soon": "Yaklaşıyor",
    "overdue": "Gecikmiş",
    "informational": "Bilgi",
}


def _item(
    *,
    code: str,
    title: str,
    status: str,
    detail: str,
    module: str,
    responsible_role: str,
    source: str,
    count: int | None = None,
    critical: bool = False,
    required: bool = True,
) -> dict:
    return {
        "code": code,
        "title": title,
        "status": status,
        "status_label": STATUS_LABELS[status],
        "detail": detail,
        "module": module,
        "responsible_role": responsible_role,
        "source": source,
        "count": count,
        "critical": bool(critical),
        "required": bool(required),
    }


def _deadline(
    *,
    source: str,
    title: str,
    due_date: date,
    module: str,
    responsible_role: str,
    today: date,
    reference_id: int | None = None,
) -> dict:
    days_left = (due_date - today).days
    if days_left < 0:
        status = "overdue"
    elif days_left <= 30:
        status = "due_soon"
    else:
        status = "scheduled"
    return {
        "source": source,
        "title": title,
        "due_date": due_date.isoformat(),
        "days_left": days_left,
        "status": status,
        "module": module,
        "responsible_role": responsible_role,
        "reference_id": reference_id,
    }


def _count(db: Session, model, *criteria) -> int:
    return int(db.scalar(select(func.count()).select_from(model).where(*criteria)) or 0)


def build_workplace_status(db: Session, company, *, viewer=None) -> dict:
    """Mevcut Müşteri 360 çıktısını standart durum merkezi alanlarıyla genişletir."""
    cid = int(company.id)
    today = date.today()
    soon = today + timedelta(days=30)
    overview = build_company_overview(db, company)
    counts = overview.get("counts") or {}
    health = overview.get("health") or {}
    plan = overview.get("annual_plan") or {}
    ppe = overview.get("ppe") or {}

    risk_total = _count(db, RiskAssessment, RiskAssessment.company_id == cid)
    risk_overdue = _count(
        db,
        RiskAssessment,
        RiskAssessment.company_id == cid,
        RiskAssessment.status == "Açık",
        RiskAssessment.term_date.is_not(None),
        RiskAssessment.term_date < today,
    )
    emergency_total = _count(
        db,
        EmergencyPlan,
        EmergencyPlan.company_id == cid,
        EmergencyPlan.is_active.is_(True),
    )
    training_completed = _count(
        db,
        TrainingSession,
        TrainingSession.company_id == cid,
        TrainingSession.status == TrainingStatus.COMPLETED,
    )
    document_total = _count(
        db,
        DocumentRecord,
        DocumentRecord.company_id == cid,
        DocumentRecord.is_active.is_(True),
    )
    periodic_total = _count(
        db,
        PeriodicControl,
        PeriodicControl.company_id == cid,
        PeriodicControl.is_active.is_(True),
    )
    periodic_overdue = _count(
        db,
        PeriodicControl,
        PeriodicControl.company_id == cid,
        PeriodicControl.is_active.is_(True),
        PeriodicControl.next_due_date.is_not(None),
        PeriodicControl.next_due_date < today,
    )
    notification_criteria = [Notification.company_id == cid, Notification.is_read.is_(False)]
    if viewer is not None:
        notification_criteria.append(
            or_(Notification.user_id.is_(None), Notification.user_id == int(viewer.id))
        )
    unread_notifications = _count(db, Notification, *notification_criteria)
    near_miss_count = _count(
        db,
        IncidentEvent,
        IncidentEvent.company_id == cid,
        IncidentEvent.event_type.in_(("near_miss", "ramak_kala")),
    )

    items: list[dict] = []
    assignment_count = int(counts.get("assignments") or 0)
    items.append(
        _item(
            code="assignments",
            title="İSG profesyoneli görevlendirmeleri",
            status="completed" if assignment_count else "missing",
            detail=(
                f"{assignment_count} aktif görevlendirme bulunuyor."
                if assignment_count
                else "Aktif uzman/hekim/DSP görevlendirmesi bulunamadı."
            ),
            module="assignments",
            responsible_role="OSGB Yöneticisi",
            source="workplace_assignments",
            count=assignment_count,
            critical=not assignment_count,
        )
    )

    employee_count = int(counts.get("employees") or 0)
    items.append(
        _item(
            code="employees",
            title="Çalışan kayıtları",
            status="completed" if employee_count else "missing",
            detail=f"{employee_count} aktif çalışan kayıtlı.",
            module="employees",
            responsible_role="İşveren / OSGB Yöneticisi",
            source="employees",
            count=employee_count,
            critical=not employee_count,
        )
    )

    open_risks = int(counts.get("open_risks") or 0)
    risk_status = "missing" if not risk_total else "overdue" if risk_overdue else "attention" if open_risks else "completed"
    items.append(
        _item(
            code="risk_assessment",
            title="Risk değerlendirmesi",
            status=risk_status,
            detail=(
                "Risk değerlendirmesi kaydı bulunamadı."
                if not risk_total
                else f"{risk_total} risk kaydı; {open_risks} açık, {risk_overdue} gecikmiş."
            ),
            module="risk",
            responsible_role="İş Güvenliği Uzmanı",
            source="risk_assessments",
            count=risk_total,
            critical=(not risk_total or risk_overdue > 0),
        )
    )

    emergency_overdue = _count(
        db,
        EmergencyPlan,
        EmergencyPlan.company_id == cid,
        EmergencyPlan.is_active.is_(True),
        EmergencyPlan.next_review_date.is_not(None),
        EmergencyPlan.next_review_date < today,
    )
    emergency_due = _count(
        db,
        EmergencyPlan,
        EmergencyPlan.company_id == cid,
        EmergencyPlan.is_active.is_(True),
        EmergencyPlan.next_review_date.between(today, soon),
    )
    emergency_status = "missing" if not emergency_total else "overdue" if emergency_overdue else "due_soon" if emergency_due else "completed"
    items.append(
        _item(
            code="emergency_plan",
            title="Acil durum planı",
            status=emergency_status,
            detail=f"{emergency_total} aktif plan; {emergency_overdue} gecikmiş, {emergency_due} yaklaşan revizyon.",
            module="acil_plan",
            responsible_role="İş Güvenliği Uzmanı / İşveren",
            source="emergency_plans",
            count=emergency_total,
            critical=(not emergency_total or emergency_overdue > 0),
        )
    )

    training_total = int(counts.get("trainings") or 0)
    items.append(
        _item(
            code="training",
            title="İSG eğitimleri",
            status="missing" if not training_total else "attention" if not training_completed else "completed",
            detail=f"{training_total} eğitim kaydı; {training_completed} tamamlandı.",
            module="training",
            responsible_role="İş Güvenliği Uzmanı / İşyeri Hekimi",
            source="training_sessions",
            count=training_total,
            critical=not training_total,
        )
    )

    health_total = int(health.get("total") or 0)
    health_overdue = int(health.get("overdue") or 0)
    health_due = int(health.get("due_soon") or 0)
    health_status = "missing" if employee_count and not health_total else "overdue" if health_overdue else "due_soon" if health_due else "completed"
    items.append(
        _item(
            code="health_examinations",
            title="Sağlık gözetimi",
            status=health_status,
            detail=f"{health_total} muayene kaydı; {health_overdue} gecikmiş, {health_due} yaklaşan. Kişisel sağlık detayı gösterilmez.",
            module="health",
            responsible_role="İşyeri Hekimi",
            source="health_records (aggregate-only)",
            count=health_total,
            critical=bool(health_overdue or (employee_count and not health_total)),
        )
    )

    open_dofs = int(counts.get("open_dofs") or 0)
    overdue_dofs = int(counts.get("overdue_dofs") or 0)
    items.append(
        _item(
            code="capa",
            title="Düzeltici ve önleyici faaliyetler",
            status="overdue" if overdue_dofs else "attention" if open_dofs else "completed",
            detail=f"{open_dofs} açık DÖF; {overdue_dofs} gecikmiş.",
            module="capa",
            responsible_role="Kayıt sorumlusu / İşveren",
            source="risk_dofs + incident_dofs",
            count=open_dofs,
            critical=overdue_dofs > 0,
            required=False,
        )
    )

    items.append(
        _item(
            code="periodic_controls",
            title="Periyodik kontroller",
            status="missing" if not periodic_total else "overdue" if periodic_overdue else "completed",
            detail=f"{periodic_total} aktif kontrol kaydı; {periodic_overdue} gecikmiş.",
            module="periyodik_kontrol",
            responsible_role="İşveren / İş Güvenliği Uzmanı",
            source="periodic_controls",
            count=periodic_total,
            critical=(not periodic_total or periodic_overdue > 0),
        )
    )

    expired_documents = int(counts.get("expired_documents") or 0)
    items.append(
        _item(
            code="documents",
            title="Dokümanlar",
            status="missing" if not document_total else "overdue" if expired_documents else "completed",
            detail=f"{document_total} aktif doküman; {expired_documents} süresi geçmiş.",
            module="documents",
            responsible_role="Kayıt sorumlusu",
            source="document_records",
            count=document_total,
            critical=expired_documents > 0,
        )
    )

    plan_total = int(plan.get("total") or 0)
    plan_delayed = int(plan.get("delayed") or 0)
    items.append(
        _item(
            code="annual_plan",
            title="Yıllık çalışma planı",
            status="missing" if not plan_total else "overdue" if plan_delayed else "completed",
            detail=f"{plan_total} plan maddesi; {plan_delayed} gecikmiş.",
            module="annual_plans",
            responsible_role="İSG Profesyonelleri / İşveren",
            source="annual_plan_items",
            count=plan_total,
            critical=(not plan_total or plan_delayed > 0),
        )
    )

    incident_total = len(overview.get("incidents") or [])
    items.append(
        _item(
            code="incidents",
            title="İş kazası ve ramak kala kayıtları",
            status="informational",
            detail=f"Son kayıtlarda {incident_total} olay, toplam {near_miss_count} ramak kala bildirimi bulunuyor.",
            module="near_miss",
            responsible_role="İş Güvenliği Uzmanı / İşveren",
            source="incident_events",
            count=incident_total,
            required=False,
        )
    )

    items.append(
        _item(
            code="notifications",
            title="Bildirimler",
            status="attention" if unread_notifications else "completed",
            detail=f"{unread_notifications} okunmamış işyeri bildirimi.",
            module="notifications",
            responsible_role="Yetkili kullanıcılar",
            source="notifications",
            count=unread_notifications,
            required=False,
        )
    )

    deadlines: list[dict] = []
    for row in db.scalars(
        select(RiskAssessment)
        .where(
            RiskAssessment.company_id == cid,
            RiskAssessment.status == "Açık",
            RiskAssessment.term_date.is_not(None),
        )
        .order_by(RiskAssessment.term_date, RiskAssessment.id)
        .limit(25)
    ).all():
        deadlines.append(
            _deadline(
                source="Risk",
                title=f"Risk termin tarihi ({row.risk_code})",
                due_date=row.term_date,
                module="risk",
                responsible_role="İş Güvenliği Uzmanı",
                today=today,
                reference_id=row.id,
            )
        )

    risk_ids = select(RiskAssessment.id).where(RiskAssessment.company_id == cid)
    for row in db.scalars(
        select(RiskDof)
        .where(
            RiskDof.risk_id.in_(risk_ids),
            RiskDof.is_completed.is_(False),
            RiskDof.term_date.is_not(None),
        )
        .order_by(RiskDof.term_date, RiskDof.id)
        .limit(25)
    ).all():
        deadlines.append(
            _deadline(
                source="DÖF",
                title=f"Risk DÖF termini ({row.dof_code})",
                due_date=row.term_date,
                module="capa",
                responsible_role=row.responsible_person or "DÖF sorumlusu",
                today=today,
                reference_id=row.id,
            )
        )

    incident_ids = select(IncidentEvent.id).where(IncidentEvent.company_id == cid)
    for row in db.scalars(
        select(IncidentDof)
        .where(
            IncidentDof.incident_id.in_(incident_ids),
            IncidentDof.status != "Tamamlandı",
            IncidentDof.term_date.is_not(None),
        )
        .order_by(IncidentDof.term_date, IncidentDof.id)
        .limit(25)
    ).all():
        deadlines.append(
            _deadline(
                source="DÖF",
                title=f"Olay DÖF termini ({row.dof_no})",
                due_date=row.term_date,
                module="capa",
                responsible_role=row.responsible_person or "DÖF sorumlusu",
                today=today,
                reference_id=row.id,
            )
        )

    for row in db.scalars(
        select(PeriodicControl)
        .where(
            PeriodicControl.company_id == cid,
            PeriodicControl.is_active.is_(True),
            PeriodicControl.next_due_date.is_not(None),
        )
        .order_by(PeriodicControl.next_due_date, PeriodicControl.id)
        .limit(25)
    ).all():
        deadlines.append(
            _deadline(
                source="Periyodik Kontrol",
                title=row.equipment_name,
                due_date=row.next_due_date,
                module="periyodik_kontrol",
                responsible_role="İşveren / Kontrol sorumlusu",
                today=today,
                reference_id=row.id,
            )
        )

    for row in db.scalars(
        select(DocumentRecord)
        .where(
            DocumentRecord.company_id == cid,
            DocumentRecord.is_active.is_(True),
            DocumentRecord.valid_until.is_not(None),
        )
        .order_by(DocumentRecord.valid_until, DocumentRecord.id)
        .limit(25)
    ).all():
        safe_title = "Sağlık belgesi" if row.category == DocumentCategory.HEALTH else row.title
        deadlines.append(
            _deadline(
                source="Doküman",
                title=safe_title,
                due_date=row.valid_until,
                module="documents",
                responsible_role="Kayıt sorumlusu",
                today=today,
                reference_id=row.id,
            )
        )

    for row in db.scalars(
        select(EmergencyPlan)
        .where(
            EmergencyPlan.company_id == cid,
            EmergencyPlan.is_active.is_(True),
            EmergencyPlan.next_review_date.is_not(None),
        )
        .order_by(EmergencyPlan.next_review_date, EmergencyPlan.id)
        .limit(10)
    ).all():
        deadlines.append(
            _deadline(
                source="Acil Durum Planı",
                title=row.title,
                due_date=row.next_review_date,
                module="acil_plan",
                responsible_role="İş Güvenliği Uzmanı / İşveren",
                today=today,
                reference_id=row.id,
            )
        )

    for row in db.scalars(
        select(AnnualPlanItem)
        .where(
            AnnualPlanItem.company_id == cid,
            AnnualPlanItem.year == today.year,
            AnnualPlanItem.deleted_at.is_(None),
            AnnualPlanItem.status.not_in((AnnualPlanStatus.COMPLETED, AnnualPlanStatus.CANCELLED)),
            AnnualPlanItem.target_date.is_not(None),
        )
        .order_by(AnnualPlanItem.target_date, AnnualPlanItem.id)
        .limit(25)
    ).all():
        deadlines.append(
            _deadline(
                source="Yıllık Plan",
                title=row.activity,
                due_date=row.target_date,
                module="annual_plans",
                responsible_role=row.responsible_name or "Plan sorumlusu",
                today=today,
                reference_id=row.id,
            )
        )

    # Sağlık terminleri kişi ve kayıt kimliği içermeden gün bazında gruplanır.
    health_due_rows = db.execute(
        select(HealthRecord.next_examination_date, func.count(HealthRecord.id))
        .where(
            HealthRecord.company_id == cid,
            HealthRecord.deleted_at.is_(None),
            HealthRecord.next_examination_date.is_not(None),
        )
        .group_by(HealthRecord.next_examination_date)
        .order_by(HealthRecord.next_examination_date)
        .limit(25)
    ).all()
    for due, total in health_due_rows:
        deadlines.append(
            _deadline(
                source="Sağlık Gözetimi",
                title=f"{int(total)} çalışanın periyodik muayene tarihi",
                due_date=due,
                module="health",
                responsible_role="İşyeri Hekimi",
                today=today,
            )
        )

    deadlines.sort(key=lambda d: (d["due_date"], d["source"], d["title"]))
    deadlines = deadlines[:100]

    required_items = [i for i in items if i["required"]]
    completed_required = sum(1 for i in required_items if i["status"] in ("completed", "due_soon"))
    completion_pct = round(100 * completed_required / len(required_items)) if required_items else 100
    missing_count = sum(1 for i in items if i["status"] == "missing")
    overdue_count = sum(1 for i in items if i["status"] == "overdue")
    due_soon_count = sum(1 for i in items if i["status"] == "due_soon")
    critical_count = sum(1 for i in items if i["critical"])
    if critical_count or overdue_count:
        overall_status = "critical"
    elif missing_count or due_soon_count or any(i["status"] == "attention" for i in items):
        overall_status = "warning"
    else:
        overall_status = "compliant"

    overview["status_center"] = {
        "schema_version": "1.0",
        "overall_status": overall_status,
        "overall_label": {
            "critical": "Kritik eksikler var",
            "warning": "İzleme gerekiyor",
            "compliant": "Mevcut kayıtlara göre uygun",
        }[overall_status],
        "completion_pct": completion_pct,
        "summary": {
            "total": len(items),
            "required": len(required_items),
            "completed": sum(1 for i in items if i["status"] == "completed"),
            "missing": missing_count,
            "overdue": overdue_count,
            "due_soon": due_soon_count,
            "critical": critical_count,
            "unread_notifications": unread_notifications,
            "ppe_overdue": int(ppe.get("overdue") or 0),
        },
        "items": items,
        "deadlines": deadlines,
        "privacy": {
            "medical_data_mode": "aggregate_only",
            "sensitive_fields_exposed": False,
        },
        "ibys_validation": {
            "status": "pending_official_validation",
            "officially_verified": False,
            "readiness_claim": False,
            "note": "Resmî İBYS doğrulama ve kabul tamamlanmadan hazır beyanı yapılamaz.",
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Yeni durum sözleşmesi sağlık ayrıntısı taşımaz. Küçük işyerlerinde yeniden
    # kimliklendirme riskine karşı "uygunsuz" kişi sayısı dahi dışarı verilmez.
    overview["health"] = {
        "total": health_total,
        "overdue": health_overdue,
        "due_soon": health_due,
    }

    # Saha rolleri ve salt-okunur kullanıcılar işyeri operasyonunu görür; OSGB'nin
    # ticari sözleşme/ücret verisi en az yetki ilkesi gereği bu sözleşmeden çıkarılır.
    if viewer is not None and viewer.role not in (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN):
        overview.pop("finance", None)
        overview.pop("contracts", None)
    return overview
