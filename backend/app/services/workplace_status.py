"""İşyeri Durum Merkezi — mevcut modüllerden salt okunur, tenant-kapsamlı özet.

Bu servis yeni bir kayıt kaynağı oluşturmaz. Üretimdeki modül tablolarını tek bir
kararlı sözleşmede birleştirir. Sağlık verileri yalnız anonim toplamlar olarak
döner; çalışan, tanı, tetkik ve hekim notları bu sözleşmeye dahil edilmez.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import and_, func, inspect as sa_inspect, or_, select
from sqlalchemy.orm import Session

from app.models.entities import (
    AnnualPlanItem,
    AnnualPlanStatus,
    ChemicalProduct,
    DocumentCategory,
    DocumentRecord,
    DrillRecord,
    EmergencyPlan,
    HealthRecord,
    IncidentDof,
    IncidentEvent,
    Notification,
    OhsCommitteeMeeting,
    PeriodicControl,
    PpeAssignment,
    PpeInventoryItem,
    RiskAssessment,
    RiskDof,
    TrainingSession,
    TrainingStatus,
    UserRole,
    WorkplaceMeasurement,
)
from app.models.remote_training import RemoteTrainingAssignment
from app.services.company_overview import build_company_overview
from app.services.notifications import (
    SPECIALIST_ONLY_NOTIFICATION_ENTITY_TYPES,
    SPECIALIST_ONLY_NOTIFICATION_TITLE_PREFIXES,
)
from app.services.risk_validity import add_years, build_validity


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


def _due_counts(values, *, today: date, soon: date) -> tuple[int, int]:
    """Return overdue and due-soon counts for explicit dates only."""
    overdue = 0
    due_soon = 0
    for value in values:
        if value is None:
            continue
        if value < today:
            overdue += 1
        elif value <= soon:
            due_soon += 1
    return overdue, due_soon


def _earliest_date(*values: date | None) -> date | None:
    present = [value for value in values if value is not None]
    return min(present) if present else None


def build_workplace_status(db: Session, company, *, viewer=None) -> dict:
    """Mevcut Müşteri 360 çıktısını standart durum merkezi alanlarıyla genişletir."""
    cid = int(company.id)
    today = date.today()
    soon = today + timedelta(days=30)
    overview = build_company_overview(db, company)
    counts = overview.get("counts") or {}
    health = overview.get("health") or {}
    plan = overview.get("annual_plan") or {}

    training_rows = list(
        db.scalars(
            select(TrainingSession).where(
                TrainingSession.company_id == cid,
                TrainingSession.archived_at.is_(None),
                TrainingSession.status != TrainingStatus.CANCELLED,
            )
        ).all()
    )
    remote_training_rows = []
    # Uzaktan eğitim tabloları ayrı, geriye uyumlu bir katmandır. Eski/veri
    # aktarımı tamamlanmamış kurulumlarda durum merkezi bütünüyle 500 vermesin.
    if sa_inspect(db.get_bind()).has_table(RemoteTrainingAssignment.__tablename__):
        remote_training_rows = list(
            db.scalars(
                select(RemoteTrainingAssignment).where(
                    RemoteTrainingAssignment.company_id == cid,
                    RemoteTrainingAssignment.status.not_in(("completed", "revoked")),
                )
            ).all()
        )
    training_due_dates = [
        row.start_date if row.status == TrainingStatus.PLANNED else row.next_training_date
        for row in training_rows
    ]
    training_overdue, training_due_soon = _due_counts(
        training_due_dates, today=today, soon=soon
    )
    remote_overdue = sum(
        1
        for row in remote_training_rows
        if row.status == "expired" or (row.due_date is not None and row.due_date < today)
    )
    remote_due_soon = sum(
        1
        for row in remote_training_rows
        if row.status != "expired"
        and row.due_date is not None
        and today <= row.due_date <= soon
    )
    training_overdue += remote_overdue
    training_due_soon += remote_due_soon

    ppe_rows = list(
        db.scalars(
            select(PpeAssignment).where(
                PpeAssignment.company_id == cid,
                PpeAssignment.deleted_at.is_(None),
                PpeAssignment.status.in_(("teslim", "yenilenecek")),
            )
        ).all()
    )
    ppe_inventory_rows = list(
        db.scalars(
            select(PpeInventoryItem).where(
                PpeInventoryItem.company_id == cid,
                PpeInventoryItem.is_active.is_(True),
            )
        ).all()
    )
    ppe_due_dates = [
        _earliest_date(row.renewal_date, row.expiry_date) for row in ppe_rows
    ] + [
        _earliest_date(row.renewal_date, row.expiry_date) for row in ppe_inventory_rows
    ]
    ppe_overdue, ppe_due_soon = _due_counts(ppe_due_dates, today=today, soon=soon)

    chemical_rows = list(
        db.scalars(
            select(ChemicalProduct).where(
                ChemicalProduct.company_id == cid,
                ChemicalProduct.is_active.is_(True),
            )
        ).all()
    )
    sds_overdue, sds_due_soon = _due_counts(
        [row.next_review_date for row in chemical_rows], today=today, soon=soon
    )
    missing_sds = sum(1 for row in chemical_rows if not row.has_sds_file)

    drill_rows = list(
        db.scalars(
            select(DrillRecord).where(
                DrillRecord.company_id == cid,
                DrillRecord.is_active.is_(True),
                DrillRecord.status != "iptal",
            )
        ).all()
    )
    planned_drills = [row for row in drill_rows if row.status == "planlandi"]
    completed_drills = [row for row in drill_rows if row.status == "yapildi"]
    latest_completed_drill = max(
        completed_drills, key=lambda row: (row.drill_date, row.id), default=None
    )
    drill_renewal_date = (
        add_years(latest_completed_drill.drill_date, 1) if latest_completed_drill else None
    )
    drill_due_dates = [row.drill_date for row in planned_drills]
    drill_renewal_covered = bool(
        drill_renewal_date
        and any(row.drill_date <= drill_renewal_date for row in planned_drills)
    )
    if drill_renewal_date and not drill_renewal_covered:
        drill_due_dates.append(drill_renewal_date)
    drill_overdue, drill_due_soon = _due_counts(
        drill_due_dates, today=today, soon=soon
    )

    measurement_rows = list(
        db.scalars(
            select(WorkplaceMeasurement).where(
                WorkplaceMeasurement.company_id == cid,
                WorkplaceMeasurement.is_active.is_(True),
            )
        ).all()
    )
    measurement_overdue, measurement_due_soon = _due_counts(
        [row.next_due_date for row in measurement_rows], today=today, soon=soon
    )

    committee_rows = list(
        db.scalars(
            select(OhsCommitteeMeeting).where(
                OhsCommitteeMeeting.company_id == cid,
                OhsCommitteeMeeting.is_active.is_(True),
            )
        ).all()
    )
    committee_overdue, committee_due_soon = _due_counts(
        [row.next_meeting_date for row in committee_rows], today=today, soon=soon
    )

    pending_sgk_rows = list(
        db.scalars(
            select(IncidentEvent).where(
                IncidentEvent.company_id == cid,
                IncidentEvent.sgk_reported.is_(False),
                IncidentEvent.sgk_due_date.is_not(None),
            )
        ).all()
    )
    sgk_overdue, sgk_due_soon = _due_counts(
        [row.sgk_due_date for row in pending_sgk_rows], today=today, soon=soon
    )

    first_risk_created = db.scalar(
        select(func.min(RiskAssessment.created_at)).where(RiskAssessment.company_id == cid)
    )
    risk_fallback_date = (
        first_risk_created.date() if hasattr(first_risk_created, "date") else first_risk_created
    )
    risk_validity = build_validity(
        hazard_class=company.hazard_class,
        assessment_date=company.risk_assessment_date,
        fallback_date=risk_fallback_date,
        method_code=getattr(company, "risk_method", None),
        today=today,
    )

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
    periodic_due_soon = _count(
        db,
        PeriodicControl,
        PeriodicControl.company_id == cid,
        PeriodicControl.is_active.is_(True),
        PeriodicControl.next_due_date.between(today, soon),
    )
    notification_criteria = [Notification.company_id == cid, Notification.is_read.is_(False)]
    non_specialist_notification = and_(
        or_(
            Notification.entity_type.is_(None),
            Notification.entity_type.notin_(tuple(SPECIALIST_ONLY_NOTIFICATION_ENTITY_TYPES)),
        ),
        Notification.title.notlike(f"{SPECIALIST_ONLY_NOTIFICATION_TITLE_PREFIXES[0]}%"),
        Notification.title.notlike(f"{SPECIALIST_ONLY_NOTIFICATION_TITLE_PREFIXES[1]}%"),
    )
    if viewer is not None:
        notification_criteria.append(
            or_(Notification.user_id.is_(None), Notification.user_id == int(viewer.id))
        )
        if viewer.role == UserRole.SAFETY_SPECIALIST:
            notification_criteria.append(
                or_(
                    non_specialist_notification,
                    Notification.user_id == int(viewer.id),
                )
            )
        else:
            notification_criteria.append(non_specialist_notification)
    else:
        notification_criteria.append(non_specialist_notification)
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
    # This row reports whether the workplace has a risk assessment on record.
    # Open risk treatments and their deadlines are tracked separately in the
    # obligation feed; they must not make an uploaded assessment look missing
    # or overdue. Document renewal is reported by risk_assessment_validity.
    risk_status = "missing" if not risk_total else "completed"
    items.append(
        _item(
            code="risk_assessment",
            title="Risk değerlendirmesi",
            status=risk_status,
            detail=(
                "Risk değerlendirmesi kaydı bulunamadı."
                if not risk_total
                else f"{risk_total} risk kaydı; {open_risks} açık risk kaydı, {risk_overdue} geçmiş termin tarihi."
            ),
            module="risk",
            responsible_role="İş Güvenliği Uzmanı",
            source="risk_assessments",
            count=risk_total,
            critical=not risk_total,
        )
    )

    risk_validity_status = {
        "expired": "overdue",
        "due_soon": "due_soon",
        "ok": "completed",
        "unknown": "missing",
    }.get(risk_validity.get("status"), "attention")
    items.append(
        _item(
            code="risk_assessment_validity",
            title="Risk değerlendirmesi yenileme süresi",
            status=risk_validity_status,
            detail=risk_validity.get("message") or "Yenileme durumu hesaplanamadı.",
            module="risk",
            responsible_role="İş Güvenliği Uzmanı / İşveren",
            source="company.risk_assessment_date + risk_validity",
            count=1 if risk_validity.get("assessment_date") else 0,
            critical=risk_validity_status in ("missing", "overdue"),
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

    training_total = len(training_rows)
    remote_training_total = len(remote_training_rows)
    training_status = (
        "missing"
        if not training_total and not remote_training_total
        else "overdue"
        if training_overdue
        else "due_soon"
        if training_due_soon
        else "attention"
        if any(row.status == TrainingStatus.PLANNED for row in training_rows)
        or any(row.status in ("not_started", "in_progress", "failed") for row in remote_training_rows)
        else "completed"
    )
    items.append(
        _item(
            code="training",
            title="İSG eğitimleri ve yenilemeler",
            status=training_status,
            detail=(
                f"{training_total} sınıf eğitimi, {remote_training_total} açık uzaktan eğitim; "
                f"{training_overdue} gecikmiş, {training_due_soon} yaklaşan tarih."
            ),
            module="personnel_training_records",
            responsible_role="İş Güvenliği Uzmanı / İşyeri Hekimi",
            source="training_sessions + remote_training_assignments",
            count=training_total + remote_training_total,
            critical=bool(training_overdue or (not training_total and not remote_training_total)),
        )
    )

    health_total = int(health.get("total") or 0)
    health_overdue = int(health.get("overdue") or 0)
    health_due = int(health.get("due_soon") or 0)
    active_employee_count = int(counts.get("active_employees") or 0)
    # Boş bir işyerinde sağlık kaydı olmaması tamamlanmış bir süreç değildir;
    # ancak çalışan da olmadığı için "Eksik" yerine yalnızca bilgi durumudur.
    # Çalışanı bulunan işyerinde 0 muayene kaydı gerçek bir eksikliktir.
    health_status = (
        "missing"
        if active_employee_count and not health_total
        else "overdue"
        if health_overdue
        else "due_soon"
        if health_due
        else "informational"
        if not health_total
        else "completed"
    )
    health_detail = (
        "Aktif çalışan kaydı bulunmuyor; sağlık gözetimi için kayıt yok. "
        "Tamamlanmış işlem olarak değerlendirilmez. Kişisel sağlık detayı gösterilmez."
        if not active_employee_count and not health_total
        else f"{health_total} muayene kaydı; {health_overdue} gecikmiş, {health_due} yaklaşan. "
        "Kişisel sağlık detayı gösterilmez."
    )
    items.append(
        _item(
            code="health_examinations",
            title="Sağlık gözetimi",
            status=health_status,
            detail=health_detail,
            module="health",
            responsible_role="İşyeri Hekimi",
            source="health_records (aggregate-only)",
            count=health_total,
            critical=bool(health_overdue or (active_employee_count and not health_total)),
        )
    )

    risk_ids = select(RiskAssessment.id).where(RiskAssessment.company_id == cid)
    risk_dofs = list(db.scalars(select(RiskDof).where(RiskDof.risk_id.in_(risk_ids))).all())
    incident_ids = select(IncidentEvent.id).where(IncidentEvent.company_id == cid)
    incident_dofs = list(
        db.scalars(select(IncidentDof).where(IncidentDof.incident_id.in_(incident_ids))).all()
    )
    incident_completed_statuses = {
        "tamamlandı",
        "tamamlandi",
        "completed",
        "closed",
        "kapatıldı",
        "kapatildi",
        "kapalı",
        "kapali",
    }
    open_risk_dofs = [row for row in risk_dofs if not row.is_completed]
    open_incident_dofs = [
        row
        for row in incident_dofs
        if str(row.status or "").strip().casefold() not in incident_completed_statuses
    ]
    dof_total = len(risk_dofs) + len(incident_dofs)
    open_dofs = len(open_risk_dofs) + len(open_incident_dofs)
    overdue_dofs = sum(
        1
        for row in (*open_risk_dofs, *open_incident_dofs)
        if row.term_date and row.term_date < today
    )
    capa_status = (
        "informational"
        if not dof_total
        else "overdue"
        if overdue_dofs
        else "attention"
        if open_dofs
        else "completed"
    )
    items.append(
        _item(
            code="capa",
            title="Düzeltici ve önleyici faaliyetler",
            status=capa_status,
            detail=(
                "Henüz DÖF kaydı bulunmuyor."
                if not dof_total
                else f"{dof_total} DÖF kaydı; {open_dofs} açık DÖF; {overdue_dofs} gecikmiş."
            ),
            module="capa",
            responsible_role="Kayıt sorumlusu / İşveren",
            source="risk_dofs + incident_dofs",
            count=open_dofs,
            critical=overdue_dofs > 0,
            required=False,
        )
    )

    ppe_total = len(ppe_rows) + len(ppe_inventory_rows)
    ppe_status = (
        "missing"
        if not ppe_total
        else "overdue"
        if ppe_overdue
        else "due_soon"
        if ppe_due_soon
        else "completed"
    )
    items.append(
        _item(
            code="ppe",
            title="KKD değişim ve kullanım süreleri",
            status=ppe_status,
            detail=(
                f"{len(ppe_rows)} zimmet, {len(ppe_inventory_rows)} stok kartı; "
                f"{ppe_overdue} gecikmiş, {ppe_due_soon} yaklaşan değişim/son kullanım tarihi."
            ),
            module="ppe",
            responsible_role="İşveren / İş Güvenliği Uzmanı",
            source="ppe_assignments + ppe_inventory_items",
            count=ppe_total,
            critical=ppe_overdue > 0,
            required=False,
        )
    )

    sds_total = len(chemical_rows)
    sds_status = (
        "informational"
        if not sds_total
        else "overdue"
        if sds_overdue
        else "due_soon"
        if sds_due_soon
        else "attention"
        if missing_sds
        else "completed"
    )
    items.append(
        _item(
            code="sds",
            title="SDS / kimyasal belge takibi",
            status=sds_status,
            detail=(
                f"{sds_total} aktif kimyasal; {missing_sds} SDS belgesi eksik, "
                f"{sds_overdue} gecikmiş, {sds_due_soon} yaklaşan gözden geçirme."
            ),
            module="sds",
            responsible_role="İşveren / İş Güvenliği Uzmanı",
            source="chemical_products",
            count=sds_total,
            critical=bool(sds_overdue or missing_sds),
            required=False,
        )
    )

    drill_status = (
        "missing"
        if not drill_rows
        else "overdue"
        if drill_overdue
        else "due_soon"
        if drill_due_soon
        else "attention"
        if planned_drills
        else "completed"
    )
    items.append(
        _item(
            code="drills",
            title="Acil durum tatbikatları",
            status=drill_status,
            detail=(
                f"{len(drill_rows)} tatbikat kaydı; {len(planned_drills)} planlı, "
                f"{drill_overdue} gecikmiş, {drill_due_soon} yaklaşan tatbikat."
            ),
            module="tatbikat",
            responsible_role="İş Güvenliği Uzmanı / İşveren",
            source="drill_records",
            count=len(drill_rows),
            critical=bool(not drill_rows or drill_overdue),
        )
    )

    items.append(
        _item(
            code="periodic_controls",
            title="Periyodik kontroller",
            status="missing" if not periodic_total else "overdue" if periodic_overdue else "due_soon" if periodic_due_soon else "completed",
            detail=f"{periodic_total} aktif kontrol kaydı; {periodic_overdue} gecikmiş, {periodic_due_soon} yaklaşan.",
            module="periyodik_kontrol",
            responsible_role="İşveren / İş Güvenliği Uzmanı",
            source="periodic_controls",
            count=periodic_total,
            critical=(not periodic_total or periodic_overdue > 0),
        )
    )

    measurement_status = (
        "informational"
        if not measurement_rows
        else "overdue"
        if measurement_overdue
        else "due_soon"
        if measurement_due_soon
        else "completed"
    )
    items.append(
        _item(
            code="workplace_measurements",
            title="Ortam ve hijyen ölçümleri",
            status=measurement_status,
            detail=(
                f"{len(measurement_rows)} aktif ölçüm kaydı; {measurement_overdue} gecikmiş, "
                f"{measurement_due_soon} yaklaşan tekrar ölçümü."
            ),
            module="ortam_olcum",
            responsible_role="İşveren / İş Güvenliği Uzmanı",
            source="workplace_measurements",
            count=len(measurement_rows),
            critical=measurement_overdue > 0,
            required=False,
        )
    )

    committee_required = employee_count >= 50
    committee_status = (
        "attention"
        if committee_required and not committee_rows
        else "informational"
        if not committee_rows
        else "overdue"
        if committee_overdue
        else "due_soon"
        if committee_due_soon
        else "completed"
    )
    items.append(
        _item(
            code="ohs_committee",
            title="İSG Kurulu toplantıları",
            status=committee_status,
            detail=(
                f"{len(committee_rows)} toplantı kaydı; {committee_overdue} gecikmiş, "
                f"{committee_due_soon} yaklaşan toplantı."
                + (
                    " Çalışan sayısı 50 ve üzeri; altı aydan uzun sürekli iş koşulu ayrıca kontrol edilmelidir."
                    if committee_required and not committee_rows
                    else ""
                )
            ),
            module="isg_kurulu",
            responsible_role="İşveren / Kurul sekreteryası",
            source="ohs_committee_meetings",
            count=len(committee_rows),
            critical=committee_overdue > 0,
            required=False,
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
            status="overdue" if sgk_overdue else "due_soon" if sgk_due_soon else "informational",
            detail=(
                f"Son kayıtlarda {incident_total} olay, toplam {near_miss_count} ramak kala; "
                f"{sgk_overdue} gecikmiş, {sgk_due_soon} yaklaşan SGK bildirim tarihi bulunuyor."
            ),
            module="near_miss",
            responsible_role="İş Güvenliği Uzmanı / İşveren",
            source="incident_events",
            count=incident_total,
            critical=sgk_overdue > 0,
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

    risk_valid_until = risk_validity.get("valid_until")
    if risk_valid_until:
        deadlines.append(
            _deadline(
                source="Risk Değerlendirmesi",
                title="Risk değerlendirmesi yenileme tarihi",
                due_date=date.fromisoformat(risk_valid_until),
                module="risk",
                responsible_role="İş Güvenliği Uzmanı / İşveren",
                today=today,
            )
        )

    for row in training_rows:
        if row.status == TrainingStatus.PLANNED:
            deadlines.append(
                _deadline(
                    source="Planlı Eğitim",
                    title=row.title,
                    due_date=row.start_date,
                    module="personnel_training_records",
                    responsible_role="İş Güvenliği Uzmanı / İşyeri Hekimi",
                    today=today,
                    reference_id=row.id,
                )
            )
        elif row.next_training_date:
            deadlines.append(
                _deadline(
                    source="Eğitim Yenileme",
                    title=row.title,
                    due_date=row.next_training_date,
                    module="personnel_training_records",
                    responsible_role="İş Güvenliği Uzmanı / İşyeri Hekimi",
                    today=today,
                    reference_id=row.id,
                )
            )

    for row in remote_training_rows:
        if not row.due_date:
            continue
        deadlines.append(
            _deadline(
                source="Uzaktan Eğitim",
                title=f"Çalışan eğitim görevi #{row.id}",
                due_date=row.due_date,
                module="remote_training",
                responsible_role="İşyeri yetkilisi / İnsan Kaynakları",
                today=today,
                reference_id=row.id,
            )
        )

    for row in ppe_rows:
        next_due = _earliest_date(row.renewal_date, row.expiry_date)
        if not next_due:
            continue
        deadlines.append(
            _deadline(
                source="KKD Değişim",
                title=row.item_type,
                due_date=next_due,
                module="ppe",
                responsible_role="İşyeri yetkilisi / KKD sorumlusu",
                today=today,
                reference_id=row.id,
            )
        )

    for row in ppe_inventory_rows:
        next_due = _earliest_date(row.renewal_date, row.expiry_date)
        if not next_due:
            continue
        deadlines.append(
            _deadline(
                source="KKD Stok",
                title=row.item_type,
                due_date=next_due,
                module="ppe",
                responsible_role="İşyeri yetkilisi / Depo sorumlusu",
                today=today,
                reference_id=row.id,
            )
        )

    for row in chemical_rows:
        if not row.next_review_date:
            continue
        deadlines.append(
            _deadline(
                source="SDS / PKD",
                title=row.product_name,
                due_date=row.next_review_date,
                module="sds",
                responsible_role="İşveren / İş Güvenliği Uzmanı",
                today=today,
                reference_id=row.id,
            )
        )

    for row in planned_drills:
        deadlines.append(
            _deadline(
                source="Tatbikat",
                title=row.drill_type,
                due_date=row.drill_date,
                module="tatbikat",
                responsible_role=row.responsible or "İş Güvenliği Uzmanı / İşveren",
                today=today,
                reference_id=row.id,
            )
        )

    if drill_renewal_date and not drill_renewal_covered:
        deadlines.append(
            _deadline(
                source="Tatbikat Yenileme",
                title="Yıllık acil durum tatbikatı",
                due_date=drill_renewal_date,
                module="tatbikat",
                responsible_role="İş Güvenliği Uzmanı / İşveren",
                today=today,
                reference_id=latest_completed_drill.id,
            )
        )

    for row in measurement_rows:
        if not row.next_due_date:
            continue
        deadlines.append(
            _deadline(
                source="Ortam Ölçümü",
                title=(
                    f"{row.measurement_type} — {row.location}"
                    if row.location
                    else row.measurement_type
                ),
                due_date=row.next_due_date,
                module="ortam_olcum",
                responsible_role="İşveren / İş Güvenliği Uzmanı",
                today=today,
                reference_id=row.id,
            )
        )

    for row in committee_rows:
        if not row.next_meeting_date:
            continue
        deadlines.append(
            _deadline(
                source="İSG Kurulu",
                title="Sonraki kurul toplantısı",
                due_date=row.next_meeting_date,
                module="isg_kurulu",
                responsible_role="İşveren / Kurul sekreteryası",
                today=today,
                reference_id=row.id,
            )
        )

    for row in pending_sgk_rows:
        deadlines.append(
            _deadline(
                source="İş Kazası Bildirimi",
                title=f"SGK bildirim süresi — {row.form_no}",
                due_date=row.sgk_due_date,
                module="accident",
                responsible_role="İşveren / İşveren vekili",
                today=today,
                reference_id=row.id,
            )
        )

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
    deadline_summary = {
        "total": len(deadlines),
        "overdue": sum(1 for row in deadlines if row["status"] == "overdue"),
        "due_soon": sum(1 for row in deadlines if row["status"] == "due_soon"),
        "scheduled": sum(1 for row in deadlines if row["status"] == "scheduled"),
    }

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
        "schema_version": "1.1",
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
            "ppe_overdue": ppe_overdue,
            "ppe_due_soon": ppe_due_soon,
            "training_overdue": training_overdue,
            "training_due_soon": training_due_soon,
        },
        "deadline_summary": deadline_summary,
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

    # Tek işyerine bağlı company_admin bir işyeri yetkilisidir; OSGB yöneticisi
    # değildir. Finans/sözleşme verisi yalnız global veya company_id'siz OSGB
    # yöneticisine bırakılır.
    can_view_commercial = viewer is not None and (
        viewer.role == UserRole.GLOBAL_ADMIN
        or (viewer.role == UserRole.COMPANY_ADMIN and not viewer.company_id)
    )
    if viewer is not None and not can_view_commercial:
        overview.pop("finance", None)
        overview.pop("contracts", None)
    return overview
